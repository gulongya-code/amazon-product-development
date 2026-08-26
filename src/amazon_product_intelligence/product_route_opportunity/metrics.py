"""Decimal-safe, denominator-explicit route opportunity metrics."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Any, Iterable

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.market_report.v0_2.models.common import (
    Availability,
    CompletenessStatus,
    EvidenceSemantics,
    PresenceStatus,
    ReferenceKind,
    build_reference,
)
from amazon_product_intelligence.market_report.v0_2.models.metric_context import (
    MetricContextEnvelope,
    MetricSampleContext,
    MetricValueType,
    build_metric_context,
)

from .config import (
    ROUTE_METRIC_POLICY_ID,
    ROUTE_METRIC_POLICY_VERSION,
    RouteDiscoveryConfig,
)
from .models import MetricDenominator, ProductMapRecord


def _decimal(value: Any) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return result if result.is_finite() else None


def _ratio(numerator: Decimal, denominator: Decimal) -> Decimal | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _field_value(record: ProductMapRecord, name: str) -> tuple[Decimal | str | None, str | None]:
    field = record.field(name)
    if field.availability is not Availability.AVAILABLE:
        return None, None
    if name in {"brand", "seller"}:
        value = " ".join(str(field.value).split()).casefold()
        return (value or None), field.field_id
    return _decimal(field.value), field.field_id


def _new_flag(record: ProductMapRecord) -> bool | None:
    return dict(record.flags)["is_new_product"]


def _denominator(
    *,
    name: str,
    numerator: Decimal | int,
    denominator: Decimal | int,
    eligible_count: int,
    unclassified_count: int,
    review_required_count: int,
    unknown_count: int,
    member_ids: Iterable[str],
    limitations: Iterable[str],
    provenance_reference_ids: tuple[str, ...],
) -> tuple[MetricDenominator, Any]:
    logical = {
        "name": name, "numerator": str(numerator), "denominator": str(denominator),
        "eligible_count": eligible_count,
        "excluded_unclassified_count": unclassified_count,
        "excluded_review_required_count": review_required_count,
        "unknown_count": unknown_count,
        "member_reference_ids": sorted(set(member_ids)),
        "limitations": sorted(set(limitations)),
    }
    item = MetricDenominator(
        denominator_id=deterministic_id("route-metric-denominator", logical),
        name=name, numerator=str(numerator), denominator=str(denominator),
        eligible_count=eligible_count,
        excluded_unclassified_count=unclassified_count,
        excluded_review_required_count=review_required_count,
        unknown_count=unknown_count,
        member_reference_ids=tuple(logical["member_reference_ids"]),
        limitations=tuple(logical["limitations"]),
    )
    reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL,
        namespace="product-route-opportunity-denominator",
        target_id=item.denominator_id,
        target_version="1.0",
        content_fingerprint=deterministic_id("denominator-content", logical),
        provenance_reference_ids=provenance_reference_ids,
    )
    return item, reference


def _metric(
    *,
    name: str,
    value_type: MetricValueType,
    value: Any,
    total: int,
    included: int,
    excluded: int,
    unknown: int,
    evidence_ids: Iterable[str],
    limitations: Iterable[str],
    marketplace: str,
    route_reference_id: str,
    product_grain_reference_id: str,
    denominator_reference_id: str,
    provenance_reference_ids: tuple[str, ...],
    unit: str | None = None,
    currency: str | None = None,
) -> MetricContextEnvelope:
    evidence = tuple(sorted(set(evidence_ids)))
    limitation_values = tuple(sorted(set(limitations)))
    coverage_decimal = Decimal(included) / Decimal(total) if total else Decimal("0")
    coverage = float(coverage_decimal)
    if value is None:
        availability = Availability.UNAVAILABLE
        presence = PresenceStatus.UNKNOWN
        semantics = EvidenceSemantics.UNKNOWN
        completeness = CompletenessStatus.UNKNOWN
        limitation_values = tuple(sorted({*limitation_values, "METRIC_VALUE_UNAVAILABLE"}))
        method_id = None
        method_version = None
    else:
        availability = Availability.AVAILABLE if included == total else Availability.PARTIAL
        presence = PresenceStatus.PRESENT
        semantics = EvidenceSemantics.DERIVED
        completeness = (
            CompletenessStatus.COMPLETE
            if availability is Availability.AVAILABLE
            else CompletenessStatus.PARTIAL
        )
        if availability is Availability.PARTIAL:
            limitation_values = tuple(sorted({*limitation_values, "PARTIAL_INPUT_COVERAGE"}))
        method_id = ROUTE_METRIC_POLICY_ID
        method_version = ROUTE_METRIC_POLICY_VERSION
    return build_metric_context(
        metric_name=name, value_type=value_type, availability=availability,
        presence_status=presence, evidence_semantics=semantics, value=value,
        unit=unit, currency=currency, period_reference_id=None,
        marketplace=marketplace.upper(), subject_reference_ids=(route_reference_id,),
        cohort_reference_id=None, denominator_reference_id=denominator_reference_id,
        product_grain_reference_id=product_grain_reference_id,
        method_policy_id=method_id, method_policy_version=method_version,
        sample_context=MetricSampleContext(
            total_count=total, included_count=included,
            excluded_count=excluded, unknown_count=unknown,
        ),
        coverage=coverage, completeness=completeness, confidence=None,
        evidence_ids=evidence, provenance_reference_ids=provenance_reference_ids,
        limitations=limitation_values,
    )


def _nearest_rank(values: list[Decimal], percentile: Decimal) -> Decimal:
    ordered = sorted(values)
    rank = max(1, ceil(float(percentile * Decimal(len(ordered)))))
    return ordered[rank - 1]


def _distribution(records: tuple[ProductMapRecord, ...], field_name: str) -> tuple[dict[str, Any] | None, tuple[str, ...]]:
    values: list[Decimal] = []
    evidence: list[str] = []
    for record in records:
        value, evidence_id = _field_value(record, field_name)
        if isinstance(value, Decimal):
            values.append(value)
            evidence.append(str(evidence_id))
    if not values:
        return None, ()
    return {
        "count": len(values),
        "p25": _float(_nearest_rank(values, Decimal("0.25"))),
        "median": _float(_nearest_rank(values, Decimal("0.50"))),
        "p75": _float(_nearest_rank(values, Decimal("0.75"))),
        "method": "NEAREST_RANK",
    }, tuple(evidence)


def _growth(records: tuple[ProductMapRecord, ...], growth_name: str) -> tuple[dict[str, Any] | None, tuple[str, ...], int, int, int, tuple[str, ...]]:
    current_sum = Decimal("0")
    prior_sum = Decimal("0")
    evidence: list[str] = []
    missing = 0
    invalid = 0
    current_available = 0
    growth_available = 0
    included = 0
    for record in records:
        current, current_id = _field_value(record, "monthly_sales")
        growth, growth_id = _field_value(record, growth_name)
        if isinstance(current, Decimal):
            current_available += 1
        if isinstance(growth, Decimal):
            growth_available += 1
        if not isinstance(current, Decimal) or not isinstance(growth, Decimal):
            missing += 1
            continue
        if growth <= Decimal("-1"):
            invalid += 1
            continue
        prior = current / (Decimal("1") + growth)
        if prior <= 0:
            invalid += 1
            continue
        current_sum += current
        prior_sum += prior
        included += 1
        evidence.extend((str(current_id), str(growth_id)))
    aggregate = _ratio(current_sum, prior_sum)
    value = None if aggregate is None else {
        "aggregate_growth": _float(aggregate - Decimal("1")),
        "input_representation": "DECIMAL_FRACTION",
        "aggregation": "SUM_CURRENT_DIV_SUM_RECONSTRUCTED_PRIOR_MINUS_ONE",
        "current_sales_coverage": float(Decimal(current_available) / Decimal(len(records))) if records else 0.0,
        "growth_rate_coverage": float(Decimal(growth_available) / Decimal(len(records))) if records else 0.0,
        "reconstruction_coverage": float(Decimal(included) / Decimal(len(records))) if records else 0.0,
        "invalid_reconstruction_count": invalid,
    }
    limitations = (
        "INVALID_GROWTH_AT_OR_BELOW_MINUS_100_EXCLUDED",
    ) if invalid else ()
    return value, tuple(evidence), included, invalid, missing, limitations


def _concentration(
    records: tuple[ProductMapRecord, ...], identity_field: str, *, sales_weighted: bool
) -> tuple[dict[str, Any] | None, tuple[str, ...], int, int]:
    weights: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    evidence: list[str] = []
    unknown = 0
    for record in records:
        if identity_field == "product":
            identity = record.asin
            identity_id = record.record_id
        else:
            identity, identity_id = _field_value(record, identity_field)
        sales, sales_id = _field_value(record, "monthly_sales")
        if not isinstance(identity, str) or (sales_weighted and not isinstance(sales, Decimal)):
            unknown += 1
            continue
        weight = sales if sales_weighted else Decimal("1")
        assert isinstance(weight, Decimal)
        weights[identity] += weight
        evidence.append(str(identity_id))
        if sales_weighted:
            evidence.append(str(sales_id))
    total = sum(weights.values(), Decimal("0"))
    if total <= 0:
        return None, (), 0, unknown
    shares = sorted((value / total for value in weights.values()), reverse=True)
    top = lambda count: sum(shares[:count], Decimal("0"))
    return {
        "basis": "AVAILABLE_MONTHLY_SALES" if sales_weighted else "KNOWN_IDENTITY_LISTINGS",
        "entity_count": len(weights), "top_1_share": _float(top(1)),
        "top_3_share": _float(top(3)), "top_5_share": _float(top(5)),
        "hhi": _float(sum((share * share for share in shares), Decimal("0"))),
        "unknown_listing_count": unknown,
    }, tuple(evidence), len(records) - unknown, unknown


def _adoption(records: tuple[ProductMapRecord, ...], dimensions: tuple[str, ...]) -> tuple[dict[str, Any] | None, tuple[str, ...], int, int]:
    result: dict[str, Any] = {}
    evidence: list[str] = []
    known_slots = 0
    total_slots = len(records) * len(dimensions)
    for dimension in dimensions:
        counts: dict[str, int] = defaultdict(int)
        known = 0
        for record in records:
            attribute = record.attribute(dimension)
            if attribute.status != "AVAILABLE" or not attribute.values:
                continue
            known += 1
            known_slots += 1
            evidence.extend(attribute.evidence_ids)
            for value in attribute.values:
                counts[canonical_json(value)] += 1
        if known:
            result[dimension] = {
                "known_count": known, "unknown_count": len(records) - known,
                "known_coverage": float(Decimal(known) / Decimal(len(records))),
                "values": [
                    {"value_key": key, "listing_count": count,
                     "share_among_known": float(Decimal(count) / Decimal(known))}
                    for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
                ],
            }
    return (result or None), tuple(evidence), known_slots, total_slots - known_slots


def build_route_metrics(
    *,
    route_id: str,
    route_reference_id: str,
    members: tuple[ProductMapRecord, ...],
    assigned_records: tuple[ProductMapRecord, ...],
    total_listing_count: int,
    unclassified_count: int,
    review_required_count: int,
    marketplace: str,
    config: RouteDiscoveryConfig,
    product_grain_reference_id: str,
    provenance_reference_ids: tuple[str, ...],
) -> tuple[tuple[tuple[str, MetricContextEnvelope], ...], tuple[MetricDenominator, ...], tuple[Any, ...]]:
    """Build a route scorecard without an opaque composite score."""

    metrics: list[tuple[str, MetricContextEnvelope]] = []
    denominators: list[MetricDenominator] = []
    references: list[Any] = []

    def add(
        key: str, value_type: MetricValueType, value: Any, *,
        numerator: Decimal | int, denominator: Decimal | int,
        eligible_count: int, included: int, excluded: int, unknown: int,
        member_ids: Iterable[str], evidence_ids: Iterable[str],
        limitations: Iterable[str] = (), unit: str | None = None,
        currency: str | None = None,
    ) -> None:
        denom, reference = _denominator(
            name=f"{route_id}:{key}", numerator=numerator, denominator=denominator,
            eligible_count=eligible_count, unclassified_count=unclassified_count,
            review_required_count=review_required_count, unknown_count=unknown,
            member_ids=member_ids, limitations=limitations,
            provenance_reference_ids=provenance_reference_ids,
        )
        denominators.append(denom)
        references.append(reference)
        metrics.append((key, _metric(
            name=key, value_type=value_type, value=value,
            total=included + excluded + unknown, included=included,
            excluded=excluded, unknown=unknown,
            evidence_ids=evidence_ids, limitations=limitations,
            marketplace=marketplace, route_reference_id=route_reference_id,
            product_grain_reference_id=product_grain_reference_id,
            denominator_reference_id=reference.reference_id,
            provenance_reference_ids=provenance_reference_ids,
            unit=unit, currency=currency,
        )))

    assigned_count = len(assigned_records)
    listing_share = _ratio(Decimal(len(members)), Decimal(assigned_count))
    membership_evidence = tuple(record.record_id for record in assigned_records)
    add(
        "route_listing_share", MetricValueType.SHARE, _float(listing_share),
        numerator=len(members), denominator=assigned_count,
        eligible_count=assigned_count, included=assigned_count,
        excluded=unclassified_count + review_required_count, unknown=0,
        member_ids=membership_evidence, evidence_ids=membership_evidence,
        limitations=("UNCLASSIFIED_AND_REVIEW_REQUIRED_EXCLUDED_FROM_ASSIGNED_COHORT",)
        if unclassified_count or review_required_count else (),
    )

    available_sales: list[tuple[ProductMapRecord, Decimal, str]] = []
    for record in assigned_records:
        sales, evidence_id = _field_value(record, "monthly_sales")
        if isinstance(sales, Decimal):
            available_sales.append((record, sales, str(evidence_id)))
    total_sales = sum((item[1] for item in available_sales), Decimal("0"))
    route_sales_rows = [item for item in available_sales if item[0] in members]
    route_sales = sum((item[1] for item in route_sales_rows), Decimal("0"))
    sales_share = _ratio(route_sales, total_sales)
    sales_limitations = ["SELLERSPRITE_MONTHLY_SALES_IS_THIRD_PARTY_ESTIMATE"]
    if len(available_sales) < assigned_count:
        sales_limitations.append("MISSING_SALES_EXCLUDED_NOT_ZERO_FILLED")
    add(
        "route_sales_share", MetricValueType.SHARE, _float(sales_share),
        numerator=route_sales, denominator=total_sales,
        eligible_count=len(available_sales), included=len(available_sales), excluded=0,
        unknown=assigned_count - len(available_sales),
        member_ids=(item[0].record_id for item in available_sales),
        evidence_ids=(item[2] for item in available_sales), limitations=sales_limitations,
    )
    efficiency = None
    if sales_share is not None and listing_share is not None and listing_share > 0:
        efficiency = sales_share / listing_share
    add(
        "demand_efficiency", MetricValueType.NUMBER, _float(efficiency),
        numerator=sales_share or Decimal("0"), denominator=listing_share or Decimal("0"),
        eligible_count=len(available_sales), included=len(available_sales), excluded=0,
        unknown=assigned_count - len(available_sales),
        member_ids=(item[0].record_id for item in available_sales),
        evidence_ids=(item[2] for item in available_sales),
        limitations=(
            "STRUCTURAL_DEMAND_VS_LISTING_INDEX_NOT_PROFIT_MARGIN_OR_GUARANTEE",
            *sales_limitations,
        ),
        unit="sales_share_per_listing_share",
    )

    for growth_name, key in (("mom_growth", "mom_aggregate_growth"), ("yoy_growth", "yoy_aggregate_growth")):
        value, evidence, included, invalid, missing, limits = _growth(members, growth_name)
        add(
            key, MetricValueType.DISTRIBUTION, value,
            numerator=included, denominator=len(members), eligible_count=included,
            included=included, excluded=invalid, unknown=missing,
            member_ids=(record.record_id for record in members), evidence_ids=evidence,
            limitations=limits,
        )

    known_age = [record for record in members if _new_flag(record) is not None]
    new_records = [record for record in known_age if _new_flag(record)]
    new_listing_share = _ratio(Decimal(len(new_records)), Decimal(len(known_age)))
    age_evidence = [record.field("listing_age_days").field_id for record in known_age]
    new_limits = (
        f"NEW_PRODUCT_THRESHOLD_DAYS={config.new_product_max_age_days}",
        f"NEW_PRODUCT_THRESHOLD_SOURCE={config.new_product_threshold_source}",
        "MISSING_AGE_EXCLUDED_NOT_CLASSIFIED_OLD",
    )
    add(
        "new_product_listing_share", MetricValueType.SHARE, _float(new_listing_share),
        numerator=len(new_records), denominator=len(known_age), eligible_count=len(known_age),
        included=len(known_age), excluded=0, unknown=len(members) - len(known_age),
        member_ids=(record.record_id for record in known_age), evidence_ids=age_evidence,
        limitations=new_limits,
    )
    age_sales: list[tuple[ProductMapRecord, Decimal, str]] = []
    for record in known_age:
        sales, evidence_id = _field_value(record, "monthly_sales")
        if isinstance(sales, Decimal):
            age_sales.append((record, sales, str(evidence_id)))
    new_sales = sum((sales for record, sales, _ in age_sales if _new_flag(record)), Decimal("0"))
    age_sales_total = sum((sales for _, sales, _ in age_sales), Decimal("0"))
    new_sales_share = _ratio(new_sales, age_sales_total)
    add(
        "new_product_sales_share", MetricValueType.SHARE, _float(new_sales_share),
        numerator=new_sales, denominator=age_sales_total, eligible_count=len(age_sales),
        included=len(age_sales), excluded=0, unknown=len(members) - len(age_sales),
        member_ids=(record.record_id for record, _, _ in age_sales),
        evidence_ids=(*age_evidence, *(evidence for _, _, evidence in age_sales)),
        limitations=(*new_limits, "SELLERSPRITE_MONTHLY_SALES_IS_THIRD_PARTY_ESTIMATE"),
    )
    new_efficiency = None
    if new_sales_share is not None and new_listing_share is not None and new_listing_share > 0:
        new_efficiency = new_sales_share / new_listing_share
    add(
        "new_product_demand_efficiency", MetricValueType.NUMBER, _float(new_efficiency),
        numerator=new_sales_share or Decimal("0"), denominator=new_listing_share or Decimal("0"),
        eligible_count=len(age_sales), included=len(age_sales), excluded=0,
        unknown=len(members) - len(age_sales),
        member_ids=(record.record_id for record, _, _ in age_sales),
        evidence_ids=(*age_evidence, *(evidence for _, _, evidence in age_sales)),
        limitations=(*new_limits, "STRUCTURAL_INDEX_NOT_PROFIT_MARGIN_OR_GUARANTEE"),
    )

    for field_name, key, unit in (
        ("review_count", "review_count_distribution", "reviews"),
        ("price_usd", "price_distribution", "USD"),
    ):
        value, evidence = _distribution(members, field_name)
        included = 0 if value is None else int(value["count"])
        add(
            key, MetricValueType.DISTRIBUTION, value,
            numerator=included, denominator=len(members), eligible_count=included,
            included=included, excluded=0, unknown=len(members) - included,
            member_ids=(record.record_id for record in members), evidence_ids=evidence,
            limitations=(
                "DESCRIPTIVE_DISTRIBUTION_NOT_EASE_OR_PROFIT_CONCLUSION",
                "MISSING_VALUES_EXCLUDED_NOT_ZERO_FILLED",
            ), unit=unit,
        )

    for identity, sales_weighted in (
        ("brand", False), ("brand", True), ("seller", False),
        ("seller", True), ("product", True),
    ):
        key = f"{identity}_{'sales' if sales_weighted else 'listing'}_concentration"
        value, evidence, included, unknown = _concentration(
            members, identity, sales_weighted=sales_weighted
        )
        add(
            key, MetricValueType.DISTRIBUTION, value,
            numerator=included, denominator=len(members), eligible_count=included,
            included=included, excluded=0, unknown=unknown,
            member_ids=(record.record_id for record in members), evidence_ids=evidence,
            limitations=(
                "UNKNOWN_IDENTITIES_EXCLUDED_NOT_MERGED",
                "SALES_WEIGHTED_DENOMINATOR_USES_AVAILABLE_SALE_ESTIMATES_ONLY"
                if sales_weighted else "LISTING_WEIGHTED_DENOMINATOR_USES_KNOWN_IDENTITIES_ONLY",
            ),
        )

    adoption, evidence, included, unknown = _adoption(members, config.adoption_dimensions)
    add(
        "structural_feature_adoption", MetricValueType.DISTRIBUTION, adoption,
        numerator=included, denominator=included + unknown, eligible_count=included,
        included=included, excluded=0, unknown=unknown,
        member_ids=(record.record_id for record in members), evidence_ids=evidence,
        limitations=(
            "MISSING_ATTRIBUTE_EVIDENCE_EXCLUDED_NOT_NEGATIVE_ADOPTION",
            "DESCRIPTIVE_NOT_CAUSAL_DEMAND_ATTRIBUTION",
        ),
    )

    return tuple(metrics), tuple(denominators), tuple(references)


__all__ = ("build_route_metrics",)
