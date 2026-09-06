"""Evidence-backed Route analysis for the integrated Market Report contract."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal, InvalidOperation
from math import ceil
from typing import Any, Iterable, Mapping

from amazon_product_intelligence.competition_intelligence import (
    CompetitionIntelligenceSnapshotV0_1,
)
from amazon_product_intelligence.opportunity_intelligence import (
    OpportunityIntelligenceSnapshotV0_1,
)
from amazon_product_intelligence.product_route_opportunity.models import MembershipStatus
from amazon_product_intelligence.route_discovery_input import RouteDiscoveryInputPackage
from amazon_product_intelligence.route_discovery_v2 import RouteDiscoveryV2Result
from amazon_product_intelligence.semantic_engine_v2 import SemanticEngineV2Result

from .models import BUSINESS_VALUE_REVIEW_QUESTIONS, build_integrated_market_report


INTEGRATED_MARKET_REPORT_BUILDER_VERSION = (
    "integrated-market-report-route-builder-v1.0"
)

_HEADERS = {
    "monthly_sales": "\u6708\u9500\u91cf",
    "monthly_revenue": "\u6708\u9500\u552e\u989d($)",
    "price": "\u4ef7\u683c($)",
    "review_count": "\u8bc4\u5206\u6570",
    "rating": "\u8bc4\u5206",
    "brand": "\u54c1\u724c",
    "seller": "BuyBox\u5356\u5bb6",
    "listing_age_days": "\u4e0a\u67b6\u5929\u6570",
    "bsr": "\u5927\u7c7bBSR",
    "subcategory_bsr": "\u5c0f\u7c7bBSR",
    "title": "\u5546\u54c1\u6807\u9898",
    "details": "\u8be6\u7ec6\u53c2\u6570",
}


def _available(record: Any, name: str) -> Any | None:
    header = _HEADERS[name]
    field = next((item for item in record.fields if item.header == header), None)
    if (
        field is None
        or getattr(field.import_status, "value", None) != "NORMALIZED"
        or field.value is None
    ):
        return None
    return field.value


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() else None


def _float(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _nearest_rank(values: Iterable[Decimal]) -> dict[str, Any] | None:
    ordered = sorted(values)
    if not ordered:
        return None

    def percentile(value: Decimal) -> float:
        rank = max(1, ceil(float(value * Decimal(len(ordered)))))
        return float(ordered[rank - 1])

    return {
        "count": len(ordered),
        "p25": percentile(Decimal("0.25")),
        "median": percentile(Decimal("0.50")),
        "p75": percentile(Decimal("0.75")),
        "method": "NEAREST_RANK",
    }


def _distribution(records: Iterable[Any], field: str) -> dict[str, Any]:
    rows = tuple(records)
    values = tuple(
        number
        for item in rows
        if (number := _decimal(_available(item, field))) is not None
    )
    distribution = _nearest_rank(values)
    return {
        "availability": (
            "UNAVAILABLE" if distribution is None
            else "AVAILABLE" if len(values) == len(rows)
            else "PARTIAL"
        ),
        "value": distribution,
        "coverage": len(values) / len(rows) if rows else 0.0,
        "unknown_count": len(rows) - len(values),
        "missing_values_are_zero": False,
    }


def _sum_metric(records: Iterable[Any], field: str, unit: str) -> dict[str, Any]:
    rows = tuple(records)
    values = tuple(
        number
        for item in rows
        if (number := _decimal(_available(item, field))) is not None
    )
    return {
        "availability": (
            "UNAVAILABLE" if not values
            else "AVAILABLE" if len(values) == len(rows)
            else "PARTIAL"
        ),
        "value": _float(sum(values, Decimal("0"))) if values else None,
        "unit": unit,
        "coverage": len(values) / len(rows) if rows else 0.0,
        "included_count": len(values),
        "unknown_count": len(rows) - len(values),
        "missing_values_are_zero": False,
    }


def _concentration(records: Iterable[Any], field: str) -> dict[str, Any]:
    rows = tuple(records)
    counts: Counter[str] = Counter()
    for item in rows:
        value = _available(item, field)
        if value is not None and str(value).strip():
            counts[" ".join(str(value).split()).casefold()] += 1
    total = sum(counts.values())
    shares = sorted((Decimal(value) / Decimal(total) for value in counts.values()), reverse=True) if total else []
    return {
        "availability": "UNAVAILABLE" if not shares else "AVAILABLE" if total == len(rows) else "PARTIAL",
        "basis": "KNOWN_IDENTITY_LISTINGS",
        "entity_count": len(counts),
        "top_1_share": _float(shares[0]) if shares else None,
        "top_3_share": _float(sum(shares[:3], Decimal("0"))) if shares else None,
        "hhi": _float(sum((value * value for value in shares), Decimal("0"))) if shares else None,
        "coverage": total / len(rows) if rows else 0.0,
        "unknown_count": len(rows) - total,
    }


def _source_metric(route: Any, name: str) -> dict[str, Any]:
    metric = route.metric(name)
    payload = metric.to_dict()
    return {
        "availability": payload["availability"],
        "value": payload["value"],
        "coverage": payload["coverage"],
        "sample_context": payload["sample_context"],
        "method_policy_id": payload["method_policy_id"],
        "limitations": payload["limitations"],
    }


def _definition(route: Any) -> str:
    dimension_labels = {
        "product_form": "Product form",
        "structural_form": "Structural form",
        "installation_architecture": "Installation",
        "attachment_mechanism": "Attachment",
        "operation_mechanism": "Operation",
    }
    pieces = []
    for item in route.defining_features:
        values = ", ".join(
            str(value).replace("_", " ").title() for value in item.values
        )
        pieces.append(f"{dimension_labels.get(item.dimension, item.dimension.replace('_', ' ').title())}: {values}")
    return "; ".join(pieces)


def _operator_label(route: Any) -> str:
    parts = []
    for item in route.defining_features:
        for value in item.values:
            label = str(value).replace("_", " ").title()
            if label not in parts:
                parts.append(label)
    return " / ".join(parts) if parts else f"Route {route.route_id.rsplit(':', 1)[-1][:8]}"


def _route_row(
    route: Any,
    records: Mapping[str, Any],
    *,
    accepted_count: int,
    candidate: Any | None,
) -> dict[str, Any]:
    members = tuple(records[item] for item in route.member_listing_references)
    return {
        "route_id": route.route_id,
        "route_short_id": route.route_id.rsplit(":", 1)[-1][:12],
        "route_label": _operator_label(route),
        "route_definition": _definition(route),
        "products": route.member_count,
        "share_of_accepted": route.member_count / accepted_count,
        "share_of_assigned": _source_metric(route, "route_listing_share"),
        "monthly_sales": _sum_metric(members, "monthly_sales", "units/month"),
        "sales_share": _source_metric(route, "route_sales_share"),
        "monthly_revenue": _sum_metric(members, "monthly_revenue", "USD/month"),
        "demand_efficiency": _source_metric(route, "demand_efficiency"),
        "price_distribution": _source_metric(route, "price_distribution"),
        "review_count_distribution": _source_metric(route, "review_count_distribution"),
        "rating_distribution": _distribution(members, "rating"),
        "bsr_distribution": _distribution(members, "bsr"),
        "subcategory_bsr_distribution": _distribution(members, "subcategory_bsr"),
        "brand_listing_concentration": _source_metric(route, "brand_listing_concentration"),
        "brand_sales_concentration": _source_metric(route, "brand_sales_concentration"),
        "seller_listing_concentration": _source_metric(route, "seller_listing_concentration"),
        "seller_sales_concentration": _source_metric(route, "seller_sales_concentration"),
        "new_product_listing_share": _source_metric(route, "new_product_listing_share"),
        "new_product_sales_share": _source_metric(route, "new_product_sales_share"),
        "new_product_demand_efficiency": _source_metric(route, "new_product_demand_efficiency"),
        "mom_growth": _source_metric(route, "mom_aggregate_growth"),
        "yoy_growth": _source_metric(route, "yoy_aggregate_growth"),
        "evidence_coverage": {
            "title": sum(_available(item, "title") is not None for item in members) / len(members),
            "structured_parameters": sum(_available(item, "details") is not None for item in members) / len(members),
            "route_feature_coverage": dict(route.feature_coverage),
        },
        "review_required_exposure": {
            "availability": "UNAVAILABLE",
            "value": None,
            "limitation": "unresolved listings have no fabricated Route membership",
        },
        "candidate_priority": None if candidate is None else candidate.priority,
        "candidate_reason_codes": [] if candidate is None else list(candidate.reason_codes),
        "assignment_limitations": list(route.assignment_limitations),
    }


def _number(row: Mapping[str, Any], key: str, nested: str | None = None) -> float | None:
    value = row[key]
    if isinstance(value, Mapping):
        value = value.get("value")
    if nested is not None and isinstance(value, Mapping):
        value = value.get(nested)
    return float(value) if type(value) in {int, float} else None


def _comparison(rows: tuple[Mapping[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    definitions = (
        ("largest_by_sales_share", "sales_share", None, max),
        ("highest_demand_efficiency", "demand_efficiency", None, max),
        ("lowest_review_barrier", "review_count_distribution", "median", min),
        ("highest_price_median", "price_distribution", "median", max),
        ("strongest_new_product_efficiency", "new_product_demand_efficiency", None, max),
    )
    result = []
    for comparison, key, nested, selector in definitions:
        available = tuple(
            (value, row)
            for row in rows
            if (value := _number(row, key, nested)) is not None
        )
        if not available:
            result.append({
                "comparison": comparison,
                "availability": "UNAVAILABLE",
                "route_id": None,
                "route_label": None,
                "value": None,
                "basis": key if nested is None else f"{key}.{nested}",
            })
            continue
        value, row = selector(available, key=lambda item: (item[0], item[1]["route_id"]))
        result.append({
            "comparison": comparison,
            "availability": "AVAILABLE",
            "route_id": row["route_id"],
            "route_label": row["route_label"],
            "value": value,
            "basis": key if nested is None else f"{key}.{nested}",
        })
    return tuple(result)


def _recommendations(rows: tuple[Mapping[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    candidates = {row["route_id"]: row for row in rows if row["candidate_priority"] is not None}
    result = [
        {
            "priority": int(row["candidate_priority"]),
            "classification": "PRIORITY_RESEARCH",
            "route_id": route_id,
            "route_label": row["route_label"],
            "basis": list(row["candidate_reason_codes"]),
        }
        for route_id, row in sorted(
            candidates.items(), key=lambda item: int(item[1]["candidate_priority"])
        )
    ]
    non_candidates = tuple(row for row in rows if row["route_id"] not in candidates)
    sales_ranked = tuple(sorted(
        (
            (_number(row, "sales_share"), row)
            for row in non_candidates
            if _number(row, "sales_share") is not None
        ),
        key=lambda item: (item[0], item[1]["route_id"]),
    ))
    low_priority_id = None
    if sales_ranked:
        _, lowest = sales_ranked[0]
        efficiency = _number(lowest, "demand_efficiency")
        if efficiency is not None and efficiency < 1:
            low_priority_id = lowest["route_id"]
    for row in sorted(non_candidates, key=lambda item: item["route_id"]):
        classification = "LOW_PRIORITY" if row["route_id"] == low_priority_id else "WATCH"
        basis = (
            ["LOWEST_NON_CANDIDATE_SALES_SHARE", "DEMAND_EFFICIENCY_BELOW_PAR"]
            if classification == "LOW_PRIORITY"
            else ["NOT_SELECTED_BY_GOVERNED_ROUTE_CANDIDATE_POLICY"]
        )
        result.append({
            "priority": None,
            "classification": classification,
            "route_id": row["route_id"],
            "route_label": row["route_label"],
            "basis": basis,
        })
    return tuple(result)


def build_route_aware_market_report(
    *,
    generated_at: str,
    canonical_bundle_fingerprints: tuple[str, ...],
    route_input: RouteDiscoveryInputPackage,
    semantic_result: SemanticEngineV2Result,
    route_result: RouteDiscoveryV2Result,
    competition_result: CompetitionIntelligenceSnapshotV0_1,
    opportunity_result: OpportunityIntelligenceSnapshotV0_1,
):
    dataset = route_input.dataset
    if semantic_result.upstream_dataset_id != dataset.dataset_id:
        raise ValueError("Semantic result is not bound to the governed dataset")
    if route_result.upstream_semantic_result_id != semantic_result.result_id:
        raise ValueError("Route result is not bound to the Semantic result")
    if route_result.upstream_dataset_id != dataset.dataset_id:
        raise ValueError("Route result is not bound to the governed dataset")
    records = {item.asin: item for item in dataset.records}
    candidates = {item.route_id: item for item in route_result.candidates}
    rows = tuple(sorted(
        (
            _route_row(
                route,
                records,
                accepted_count=route_result.listing_count,
                candidate=candidates.get(route.route_id),
            )
            for route in route_result.routes
        ),
        key=lambda item: (-item["products"], item["route_id"]),
    ))
    assigned_records = tuple(
        records[item.listing_reference]
        for item in route_result.memberships
        if item.status is MembershipStatus.ASSIGNED
    )
    all_records = tuple(records.values())
    review_rate = route_result.review_required_count / route_result.listing_count
    overview = {
        "category_size": route_result.listing_count,
        "coverage_counts": {
            "accepted": route_result.listing_count,
            "primary_cohort": route_result.primary_cohort_eligible_count,
            "assigned": route_result.assigned_count,
            "unclassified": route_result.unclassified_count,
            "review_required": route_result.review_required_count,
        },
        "coverage_rates": {
            "assigned": route_result.assigned_count / route_result.listing_count,
            "unclassified": route_result.unclassified_count / route_result.listing_count,
            "review_required": review_rate,
        },
        "route_count": len(rows),
        "candidate_count": len(route_result.candidates),
        "monthly_sales": _sum_metric(all_records, "monthly_sales", "units/month"),
        "monthly_revenue": _sum_metric(all_records, "monthly_revenue", "USD/month"),
        "price_distribution": _distribution(all_records, "price"),
        "review_count_distribution": _distribution(all_records, "review_count"),
        "rating_distribution": _distribution(all_records, "rating"),
        "brand_concentration": _concentration(all_records, "brand"),
        "seller_concentration": _concentration(all_records, "seller"),
        "assigned_market_monthly_sales": _sum_metric(assigned_records, "monthly_sales", "units/month"),
        "data_limitations": [
            "monthly sales and revenue are third-party estimates",
            "unclassified and review-required listings are excluded from Route aggregates",
            "missing values are excluded and never converted to zero",
        ],
    }
    risk_counts = Counter(item.risk_type.value for item in opportunity_result.risk_evidence)
    missing_kinds = tuple(
        sorted(item.evidence_kind.value for item in opportunity_result.missing_evidence.items)
    )
    buyer_needs = {
        "availability": "UNAVAILABLE",
        "contract_reused": "buyer-need-analysis-v0.3",
        "themes": [],
        "route_links": [],
        "limitations": [
            "the governed corpus contains listing titles and attributes but no governed review or search-term Buyer Need evidence",
            "listing marketing text is not relabeled as buyer-need truth",
        ],
    }
    comparison = _comparison(rows)
    recommendations = _recommendations(rows)
    risks = (
        {
            "risk": "REVIEW_REQUIRED_EXPOSURE",
            "value": review_rate,
            "basis": f"{route_result.review_required_count}/{route_result.listing_count}",
        },
        {
            "risk": "UNCLASSIFIED_EXPOSURE",
            "value": route_result.unclassified_count / route_result.listing_count,
            "basis": f"{route_result.unclassified_count}/{route_result.listing_count}",
        },
        {
            "risk": "BUYER_NEED_EVIDENCE_UNAVAILABLE",
            "value": None,
            "basis": "no governed review or search-term evidence supplied",
        },
        {
            "risk": "PROVIDER_DATA_LIMITATIONS",
            "value": None,
            "basis": "one manually exported provider corpus; provider methods remain source metadata",
        },
    )
    return build_integrated_market_report(
        generated_at=generated_at,
        category=dataset.category,
        marketplace=dataset.marketplace,
        source_lineage={
            "builder_version": INTEGRATED_MARKET_REPORT_BUILDER_VERSION,
            "canonical_bundle_fingerprints": list(canonical_bundle_fingerprints),
            "route_input_contract_version": route_input.contract_version,
            "route_input_mapping_version": route_input.mapping_version,
            "route_input_package_id": route_input.package_id,
            "route_input_semantic_fingerprint": route_input.semantic_fingerprint,
            "governed_dataset_id": dataset.dataset_id,
            "governed_dataset_fingerprint": dataset.semantic_fingerprint,
            "semantic_result_id": semantic_result.result_id,
            "semantic_result_fingerprint": semantic_result.semantic_fingerprint,
            "semantic_profile_fingerprint": semantic_result.profile_fingerprint,
            "route_result_id": route_result.result_id,
            "route_result_fingerprint": route_result.semantic_fingerprint,
            "route_config_fingerprint": route_result.route_config_fingerprint,
            "competition_snapshot_id": competition_result.snapshot_id,
            "competition_ruleset_version": competition_result.ruleset_version,
            "opportunity_snapshot_id": opportunity_result.snapshot_id,
            "opportunity_ruleset_version": opportunity_result.ruleset_version,
        },
        market_overview=overview,
        route_landscape=rows,
        route_comparison=comparison,
        buyer_needs=buyer_needs,
        competition={
            "canonical_intelligence_snapshot_id": competition_result.snapshot_id,
            "coverage": competition_result.coverage.to_dict(),
            "route_competition_dimensions": [
                "review_count_distribution",
                "brand_listing_concentration",
                "brand_sales_concentration",
                "seller_listing_concentration",
                "seller_sales_concentration",
            ],
            "interpretation": "descriptive barriers and concentration, not procurement truth",
        },
        opportunity={
            "canonical_intelligence_snapshot_id": opportunity_result.snapshot_id,
            "coverage": opportunity_result.coverage.to_dict(),
            "canonical_risk_type_counts": dict(sorted(risk_counts.items())),
            "canonical_missing_evidence_kinds": list(missing_kinds),
            "candidate_selection_status": route_result.candidate_selection_status.value,
            "recommendations": list(recommendations),
            "interpretation": "research priority only; not a launch or profit decision",
        },
        risks_unknowns=risks,
        business_value_review=tuple(
            {"question": question, "human_verdict": None, "notes": None}
            for question in BUSINESS_VALUE_REVIEW_QUESTIONS
        ),
        limitations=tuple(sorted({
            *overview["data_limitations"],
            *buyer_needs["limitations"],
            "Route Discovery V2 behavior and thresholds are unchanged",
            "recommendations identify investigation priority and do not assert launch viability",
        })),
    )


__all__ = (
    "INTEGRATED_MARKET_REPORT_BUILDER_VERSION",
    "build_route_aware_market_report",
)
