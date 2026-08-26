"""Deterministic, explainable, cross-category product-route engine."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import replace
from decimal import Decimal
from hashlib import sha256
from typing import Any

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.listing_attribute_map.models import ProductAttributeMapV1
from amazon_product_intelligence.market_report.v0_2.models.common import (
    Availability,
    ReferenceKind,
    build_reference,
)
from amazon_product_intelligence.sellersprite_import.models import GovernedMarketDatasetV1

from .config import ROUTE_ENGINE_VERSION, RouteDiscoveryConfig
from .errors import ProductRouteOpportunityError
from .metrics import build_route_metrics
from .models import (
    CandidateRoute,
    CandidateSelectionStatus,
    MembershipStatus,
    ProductMapRecord,
    ProductRoute,
    ProductRouteOpportunityResult,
    RouteMembership,
)
from .product_map import build_product_map_records, structural_signature


_DISCOVERY_METHOD = "EXACT_KNOWN_STRUCTURAL_ATTRIBUTE_SIGNATURE"


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _route_id(signature: tuple[tuple[str, str], ...], config: RouteDiscoveryConfig) -> str:
    return deterministic_id(
        "product-route",
        {
            "method": _DISCOVERY_METHOD, "version": ROUTE_ENGINE_VERSION,
            "config_fingerprint": config.fingerprint,
            "defining_attributes": signature,
        },
    )


def _label(signature: tuple[tuple[str, str], ...]) -> str:
    return " | ".join(f"{dimension}={value_key}" for dimension, value_key in signature)[:320]


def _assignment_state(
    record: ProductMapRecord, config: RouteDiscoveryConfig
) -> tuple[MembershipStatus, tuple[tuple[str, str], ...] | None, tuple[str, ...]]:
    conflicted = [
        item.dimension for item in record.attributes
        if item.dimension in config.core_dimensions and item.conflict_ids
    ]
    review = [
        item.dimension for item in record.attributes
        if item.dimension in config.core_dimensions and item.status == "REVIEW_REQUIRED"
    ]
    if conflicted or review:
        return MembershipStatus.REVIEW_REQUIRED, None, tuple(sorted({
            *(f"CORE_ATTRIBUTE_CONFLICT:{item}" for item in conflicted),
            *(f"CORE_ATTRIBUTE_REVIEW_REQUIRED:{item}" for item in review),
        }))
    signature = structural_signature(record, config)
    if signature is None:
        return MembershipStatus.UNCLASSIFIED, None, (
            "INSUFFICIENT_KNOWN_STRUCTURAL_ATTRIBUTES",
        )
    return MembershipStatus.ASSIGNED, signature, ()


def _membership(
    record: ProductMapRecord,
    *,
    status: MembershipStatus,
    signature: tuple[tuple[str, str], ...] | None,
    route_id: str | None,
    limitations: tuple[str, ...],
) -> RouteMembership:
    evidence: set[str] = set()
    for dimension, _ in signature or ():
        evidence.update(record.attribute(dimension).evidence_ids)
    logical = {
        "product_map_record_id": record.record_id, "listing_reference": record.asin,
        "status": status.value, "primary_route_id": route_id,
        "assignment_attributes": signature or (),
        "evidence_ids": sorted(evidence), "limitations": sorted(limitations),
    }
    return RouteMembership(
        membership_id=deterministic_id("route-membership", logical),
        product_map_record_id=record.record_id, listing_reference=record.asin,
        status=status, primary_route_id=route_id,
        assignment_attributes=signature or (),
        evidence_ids=tuple(logical["evidence_ids"]),
        limitations=tuple(logical["limitations"]),
    )


def _secondary_descriptors(
    members: tuple[ProductMapRecord, ...], config: RouteDiscoveryConfig
) -> tuple[tuple[str, str], ...]:
    descriptors: list[tuple[str, str]] = []
    for dimension in config.secondary_dimensions:
        counts: Counter[str] = Counter()
        for record in members:
            attribute = record.attribute(dimension)
            if attribute.status != "AVAILABLE" or not attribute.values:
                continue
            for value in attribute.values:
                counts[canonical_json(value)] += 1
        if not counts:
            continue
        value, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
        if Decimal(count) / Decimal(len(members)) >= Decimal("0.5"):
            descriptors.append((dimension, value))
    return tuple(descriptors[:4])


def _coverage(
    members: tuple[ProductMapRecord, ...], config: RouteDiscoveryConfig
) -> tuple[tuple[str, float], ...]:
    result: list[tuple[str, float]] = []
    dimensions = tuple(dict.fromkeys((*config.core_dimensions, *config.adoption_dimensions)))
    for dimension in dimensions:
        known = sum(
            record.attribute(dimension).status == "AVAILABLE"
            and bool(record.attribute(dimension).values)
            for record in members
        )
        result.append((dimension, float(Decimal(known) / Decimal(len(members)))))
    return tuple(result)


def _metric_number(route: ProductRoute, name: str) -> Decimal | None:
    metric = route.metric(name)
    if metric.availability is Availability.UNAVAILABLE or metric.value is None:
        return None
    if type(metric.value) not in {int, float}:
        return None
    return Decimal(str(metric.value))


def _growth_number(route: ProductRoute, name: str) -> Decimal | None:
    metric = route.metric(name)
    if metric.value is None or not isinstance(metric.value, Mapping):
        return None
    value = metric.value.get("aggregate_growth")
    return None if value is None else Decimal(str(value))


def _candidate_reasons(route: ProductRoute) -> tuple[str, ...]:
    reasons: list[str] = []
    efficiency = _metric_number(route, "demand_efficiency")
    if efficiency is not None and efficiency > 1:
        reasons.append("DEMAND_EFFICIENCY_ABOVE_PAR")
    for metric_name, code in (
        ("mom_aggregate_growth", "POSITIVE_MOM_AGGREGATE_GROWTH"),
        ("yoy_aggregate_growth", "POSITIVE_YOY_AGGREGATE_GROWTH"),
    ):
        value = _growth_number(route, metric_name)
        if value is not None and value > 0:
            reasons.append(code)
    new_efficiency = _metric_number(route, "new_product_demand_efficiency")
    if new_efficiency is not None and new_efficiency > 1:
        reasons.append("NEW_PRODUCT_DEMAND_EFFICIENCY_ABOVE_PAR")
    if route.metric("route_sales_share").availability is not Availability.UNAVAILABLE:
        reasons.append("SALES_SHARE_EVIDENCE_AVAILABLE")
    if route.metric("review_count_distribution").availability is not Availability.UNAVAILABLE:
        reasons.append("REVIEW_BARRIER_EVIDENCE_AVAILABLE")
    if route.metric("price_distribution").availability is not Availability.UNAVAILABLE:
        reasons.append("PRICE_DISTRIBUTION_EVIDENCE_AVAILABLE")
    return tuple(reasons)


def _distance(left: ProductRoute, right: ProductRoute) -> Decimal:
    first = set(left.defining_attributes)
    second = set(right.defining_attributes)
    union = first | second
    if not union:
        return Decimal("0")
    return Decimal(len(first ^ second)) / Decimal(len(union))


def _select_candidates(
    routes: tuple[ProductRoute, ...], config: RouteDiscoveryConfig
) -> tuple[CandidateSelectionStatus, tuple[CandidateRoute, ...]]:
    qualified = []
    for route in routes:
        reasons = _candidate_reasons(route)
        if len(reasons) < config.candidate_min_reason_count:
            continue
        efficiency = _metric_number(route, "demand_efficiency") or Decimal("-1")
        sales_share = _metric_number(route, "route_sales_share") or Decimal("-1")
        qualified.append((route, reasons, efficiency, sales_share))
    qualified.sort(
        key=lambda item: (-len(item[1]), -item[2], -item[3], item[0].route_id)
    )
    selected: list[tuple[ProductRoute, tuple[str, ...], Decimal | None]] = []
    for route, reasons, _, _ in qualified:
        distances = [_distance(route, previous[0]) for previous in selected]
        minimum = min(distances) if distances else None
        if minimum is not None and minimum < config.candidate_min_structural_distance:
            continue
        selected.append((route, reasons, minimum))
        if len(selected) == config.candidate_max_count:
            break
    if len(selected) < config.candidate_min_count:
        return CandidateSelectionStatus.INSUFFICIENT_EVIDENCE, ()
    return CandidateSelectionStatus.SELECTED, tuple(
        CandidateRoute(
            priority=index, route_id=route.route_id, reason_codes=reasons,
            minimum_distance_to_prior=None if distance is None else float(distance),
        )
        for index, (route, reasons, distance) in enumerate(selected, start=1)
    )


def build_product_route_opportunity(
    dataset: GovernedMarketDatasetV1,
    attribute_map: ProductAttributeMapV1,
    *,
    config: RouteDiscoveryConfig,
) -> ProductRouteOpportunityResult:
    """Build Product Map records, deterministic routes, metrics, and candidates."""

    product_records = build_product_map_records(dataset, attribute_map, config=config)
    by_id = {record.record_id: record for record in product_records}
    preliminary: dict[str, tuple[MembershipStatus, tuple[tuple[str, str], ...] | None, tuple[str, ...]]] = {}
    signature_groups: dict[tuple[tuple[str, str], ...], list[ProductMapRecord]] = defaultdict(list)
    for record in product_records:
        state = _assignment_state(record, config)
        preliminary[record.record_id] = state
        if state[0] is MembershipStatus.ASSIGNED and state[1] is not None:
            signature_groups[state[1]].append(record)

    viable = {
        signature: tuple(sorted(records, key=lambda item: item.asin))
        for signature, records in signature_groups.items()
        if len(records) >= config.min_route_size
    }
    memberships: list[RouteMembership] = []
    for record in product_records:
        status, signature, limitations = preliminary[record.record_id]
        route_id = None
        if status is MembershipStatus.ASSIGNED and signature not in viable:
            status = MembershipStatus.UNCLASSIFIED
            limitations = (*limitations, "SIGNATURE_GROUP_BELOW_MIN_ROUTE_SIZE")
        elif status is MembershipStatus.ASSIGNED and signature is not None:
            route_id = _route_id(signature, config)
            if len(signature) < len(config.core_dimensions):
                limitations = (*limitations, "PARTIAL_STRUCTURAL_SIGNATURE")
        memberships.append(_membership(
            record, status=status, signature=signature, route_id=route_id,
            limitations=tuple(sorted(set(limitations))),
        ))
    memberships_tuple = tuple(sorted(memberships, key=lambda item: item.listing_reference))
    if sum(item.status is MembershipStatus.ASSIGNED for item in memberships_tuple) == 0 and product_records:
        # A governed insufficiency result is returned; no route is fabricated.
        pass

    dataset_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="governed-market-dataset",
        target_id=dataset.dataset_id, target_version=dataset.contract_version,
        content_fingerprint=dataset.semantic_fingerprint,
    )
    attribute_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="product-attribute-map",
        target_id=attribute_map.dataset_id, target_version=attribute_map.contract_version,
        content_fingerprint=attribute_map.semantic_fingerprint,
        provenance_reference_ids=(dataset_reference.reference_id,),
    )
    config_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="product-route-config",
        target_id=config.config_id, target_version=config.version,
        content_fingerprint=config.fingerprint,
    )
    grain_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="product-grain",
        target_id="LISTING_ASIN_NO_PARENT_COLLAPSE", target_version="1.0",
        provenance_reference_ids=(dataset_reference.reference_id,),
    )
    references: list[Any] = [
        dataset_reference, attribute_reference, config_reference, grain_reference,
    ]
    provenance_ids = tuple(sorted((
        dataset_reference.reference_id, attribute_reference.reference_id,
        config_reference.reference_id,
    )))

    assigned_memberships = tuple(
        item for item in memberships_tuple if item.status is MembershipStatus.ASSIGNED
    )
    assigned_records = tuple(
        sorted((by_id[item.product_map_record_id] for item in assigned_memberships), key=lambda item: item.asin)
    )
    unclassified_count = sum(
        item.status is MembershipStatus.UNCLASSIFIED for item in memberships_tuple
    )
    review_count = sum(
        item.status is MembershipStatus.REVIEW_REQUIRED for item in memberships_tuple
    )
    routes: list[ProductRoute] = []
    denominators: list[Any] = []
    for signature, members in sorted(viable.items(), key=lambda item: item[0]):
        route_id = _route_id(signature, config)
        route_memberships = tuple(
            item for item in assigned_memberships if item.primary_route_id == route_id
        )
        route_reference = build_reference(
            kind=ReferenceKind.REPORT_LOCAL, namespace="product-route",
            target_id=route_id, target_version=ROUTE_ENGINE_VERSION,
            provenance_reference_ids=provenance_ids,
        )
        references.append(route_reference)
        metrics, route_denominators, metric_references = build_route_metrics(
            route_id=route_id, route_reference_id=route_reference.reference_id,
            members=members, assigned_records=assigned_records,
            total_listing_count=len(product_records),
            unclassified_count=unclassified_count,
            review_required_count=review_count, marketplace=dataset.marketplace,
            config=config, product_grain_reference_id=grain_reference.reference_id,
            provenance_reference_ids=provenance_ids,
        )
        denominators.extend(route_denominators)
        references.extend(metric_references)
        logical = {
            "route_id": route_id, "label": _label(signature),
            "defining_attributes": signature,
            "secondary_descriptors": _secondary_descriptors(members, config),
            "member_listing_references": [record.asin for record in members],
            "membership_ids": [item.membership_id for item in route_memberships],
            "assignment_evidence_ids": sorted({
                evidence for item in route_memberships for evidence in item.evidence_ids
            }),
            "assignment_limitations": sorted({
                limitation for item in route_memberships for limitation in item.limitations
            }),
            "attribute_coverage": _coverage(members, config),
            "discovery_method": _DISCOVERY_METHOD,
            "discovery_version": ROUTE_ENGINE_VERSION,
            "config_fingerprint": config.fingerprint,
            "metrics": [(key, value.to_dict()) for key, value in metrics],
        }
        routes.append(ProductRoute(
            route_id=route_id, semantic_fingerprint=_hash(logical),
            label=logical["label"], defining_attributes=signature,
            secondary_descriptors=logical["secondary_descriptors"],
            member_count=len(members),
            member_listing_references=tuple(logical["member_listing_references"]),
            membership_ids=tuple(logical["membership_ids"]),
            assignment_evidence_ids=tuple(logical["assignment_evidence_ids"]),
            assignment_limitations=tuple(logical["assignment_limitations"]),
            attribute_coverage=logical["attribute_coverage"],
            discovery_method=_DISCOVERY_METHOD,
            discovery_version=ROUTE_ENGINE_VERSION,
            config_fingerprint=config.fingerprint, metrics=metrics,
        ))
    routes_tuple = tuple(sorted(routes, key=lambda item: item.route_id))

    if routes_tuple:
        listing_sum = sum(
            Decimal(str(route.metric("route_listing_share").value)) for route in routes_tuple
        )
        if abs(listing_sum - Decimal("1")) > Decimal("0.000000001"):
            raise ProductRouteOpportunityError(
                "LISTING_SHARE_INVARIANT_FAILED", "primary route listing shares do not sum to one"
            )
        sales_values = [
            route.metric("route_sales_share").value for route in routes_tuple
            if route.metric("route_sales_share").value is not None
        ]
        if sales_values and abs(
            sum((Decimal(str(value)) for value in sales_values), Decimal("0")) - Decimal("1")
        ) > Decimal("0.000000001"):
            raise ProductRouteOpportunityError(
                "SALES_SHARE_INVARIANT_FAILED", "available-sales route shares do not sum to one"
            )

    candidate_status, candidates = _select_candidates(routes_tuple, config)
    diagnostics = (
        ("route_ids", tuple(route.route_id for route in routes_tuple)),
        ("route_fingerprints", tuple(route.semantic_fingerprint for route in routes_tuple)),
        ("membership_counts", {
            "assigned": len(assigned_memberships), "unclassified": unclassified_count,
            "review_required": review_count,
        }),
        ("route_size_distribution", tuple(sorted(route.member_count for route in routes_tuple))),
        ("candidate_reason_codes", tuple(
            {"route_id": item.route_id, "reason_codes": item.reason_codes}
            for item in candidates
        )),
        ("private_values_in_diagnostics", False),
    )
    logical_result = {
        "upstream_dataset_id": dataset.dataset_id,
        "upstream_dataset_fingerprint": dataset.semantic_fingerprint,
        "upstream_attribute_map_id": attribute_map.dataset_id,
        "upstream_attribute_map_fingerprint": attribute_map.semantic_fingerprint,
        "route_engine_version": ROUTE_ENGINE_VERSION,
        "route_config_id": config.config_id, "route_config_version": config.version,
        "route_config_fingerprint": config.fingerprint,
        "counts": {
            "listing": len(product_records), "assigned": len(assigned_memberships),
            "unclassified": unclassified_count, "review_required": review_count,
        },
        "product_map_records": [item.to_dict() for item in product_records],
        "memberships": [item.to_dict() for item in memberships_tuple],
        "routes": [item.to_dict() for item in routes_tuple],
        "denominators": [item.to_dict() for item in denominators],
        "candidate_status": candidate_status.value,
        "candidates": [item.to_dict() for item in candidates],
        "diagnostics": {key: value for key, value in diagnostics},
    }
    fingerprint = _hash(logical_result)
    return ProductRouteOpportunityResult(
        result_id=deterministic_id("product-route-opportunity-result", logical_result),
        semantic_fingerprint=fingerprint,
        upstream_dataset_id=dataset.dataset_id,
        upstream_dataset_fingerprint=dataset.semantic_fingerprint,
        upstream_attribute_map_id=attribute_map.dataset_id,
        upstream_attribute_map_fingerprint=attribute_map.semantic_fingerprint,
        route_engine_version=ROUTE_ENGINE_VERSION,
        route_config_id=config.config_id, route_config_version=config.version,
        route_config_fingerprint=config.fingerprint,
        listing_count=len(product_records), assigned_count=len(assigned_memberships),
        unclassified_count=unclassified_count, review_required_count=review_count,
        product_map_records=product_records, memberships=memberships_tuple,
        routes=routes_tuple, denominators=tuple(sorted(denominators, key=lambda item: item.denominator_id)),
        references=tuple(sorted(references, key=lambda item: item.reference_id)),
        candidate_selection_status=candidate_status, candidates=candidates,
        diagnostics=diagnostics,
    )


__all__ = ("build_product_route_opportunity",)
