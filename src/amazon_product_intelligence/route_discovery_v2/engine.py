"""Deterministic S2-backed compatible sparse Route Discovery V2."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from typing import Any

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.market_report.v0_2.models.common import (
    Availability,
    ReferenceKind,
    build_reference,
)
from amazon_product_intelligence.product_route_opportunity.engine import (
    candidate_metric_reason_codes,
)
from amazon_product_intelligence.product_route_opportunity.metrics import (
    build_route_metrics,
)
from amazon_product_intelligence.product_route_opportunity.models import (
    CandidateSelectionStatus,
    MembershipStatus,
    ProductMapRecord,
    RouteAttribute,
)
from amazon_product_intelligence.product_route_opportunity.product_map import (
    build_governed_market_fields,
)
from amazon_product_intelligence.sellersprite_import.models import (
    GovernedMarketDatasetV1,
)
from amazon_product_intelligence.semantic_engine_v2.models import (
    CohortEligibilityState,
    EvidenceRelationshipState,
    RoleRelevance,
    SemanticEngineV2Result,
)
from amazon_product_intelligence.semantic_engine_v2.profile import (
    CategorySemanticProfileV1_1,
)

from .config import (
    ROUTE_V2_ENGINE_VERSION,
    ROUTE_V2_METHOD,
    RouteDiscoveryV2Config,
)
from .errors import RouteDiscoveryV2Error
from .models import (
    CandidateRouteV2,
    ProductRouteV2,
    RouteDescriptor,
    RouteDiscoveryV2Result,
    RouteSemanticKey,
    RouteV2Membership,
    SemanticRouteFeatureView,
)
from .projection import build_semantic_route_feature_views


_CONFLICT_STATES = frozenset((
    EvidenceRelationshipState.TRUE_CONFLICT.value,
    EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT.value,
))


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _signature(
    view: SemanticRouteFeatureView,
    config: RouteDiscoveryV2Config,
) -> tuple[RouteSemanticKey, ...]:
    signature: list[RouteSemanticKey] = []
    for dimension in config.route_dimensions:
        feature = view.feature(dimension)
        if feature is None:
            continue
        # The S2 source policy has already separated primary/fallback facts from
        # corroborating-only observations.  Corroboration remains visible in
        # the feature view, but it cannot manufacture a route anchor when the
        # accepted profile declares no fallback source.
        if not feature.defining_values:
            continue
        signature.append(RouteSemanticKey(
            role=feature.role,
            dimension=dimension,
            values=feature.defining_values,
        ))
    return tuple(signature)


def _signature_key(signature: tuple[RouteSemanticKey, ...]) -> str:
    return canonical_json([item.to_dict() for item in signature])


@dataclass(frozen=True, slots=True)
class _Cluster:
    anchor: tuple[RouteSemanticKey, ...]
    signature_keys: tuple[str, ...]
    member_views: tuple[SemanticRouteFeatureView, ...]

    @property
    def anchor_key(self) -> str:
        return _signature_key(self.anchor)

    @property
    def cluster_key(self) -> str:
        return canonical_json(list(self.signature_keys))


def _definition_map(
    definition: tuple[RouteSemanticKey, ...],
) -> dict[str, tuple[Any, dict[str, Any]]]:
    return {
        item.dimension: (
            item.role,
            {canonical_json(value): value for value in item.values},
        )
        for item in definition
    }


@dataclass(frozen=True, slots=True)
class _Node:
    prefix: tuple[RouteSemanticKey, ...]
    groups: tuple[_Cluster, ...]

    @property
    def member_count(self) -> int:
        return sum(len(item.member_views) for item in self.groups)

    @property
    def node_key(self) -> str:
        return canonical_json({
            "prefix": [item.to_dict() for item in self.prefix],
            "signatures": sorted(
                key for group in self.groups for key in group.signature_keys
            ),
        })


def _semantic_key(
    signature: tuple[RouteSemanticKey, ...], dimension: str,
) -> RouteSemanticKey | None:
    return next((item for item in signature if item.dimension == dimension), None)


def _value_map(key: RouteSemanticKey) -> dict[str, Any]:
    return {canonical_json(value): value for value in key.values}


def _consensus_key(
    keys: tuple[RouteSemanticKey, ...],
) -> RouteSemanticKey | None:
    if not keys:
        return None
    role = keys[0].role
    dimension = keys[0].dimension
    if any(item.role is not role or item.dimension != dimension for item in keys[1:]):
        return None
    values = _value_map(keys[0])
    value_keys = set(values)
    for item in keys[1:]:
        value_keys &= set(_value_map(item))
    if not value_keys:
        return None
    return RouteSemanticKey(
        role=role, dimension=dimension,
        values=tuple(values[item] for item in sorted(value_keys)),
    )


def _route_cluster(
    prefix: tuple[RouteSemanticKey, ...],
    groups: tuple[_Cluster, ...],
) -> _Cluster:
    return _Cluster(
        anchor=prefix,
        signature_keys=tuple(sorted(
            key for group in groups for key in group.signature_keys
        )),
        member_views=tuple(sorted((
            view for group in groups for view in group.member_views
        ), key=lambda item: item.listing_reference)),
    )


def _base_nodes(
    exact_groups: tuple[_Cluster, ...],
) -> tuple[_Node, ...]:
    buckets: dict[str, tuple[RouteSemanticKey, list[_Cluster]]] = {}
    for group in exact_groups:
        base = group.anchor[0]
        key = canonical_json(base.to_dict())
        if key not in buckets:
            buckets[key] = (base, [])
        buckets[key][1].append(group)
    return tuple(
        _Node(
            prefix=(base,),
            groups=tuple(sorted(groups, key=lambda item: item.cluster_key)),
        )
        for _, (base, groups) in sorted(buckets.items())
    )


def _merge_tiny_bases(
    nodes: tuple[_Node, ...],
    *,
    config: RouteDiscoveryV2Config,
) -> tuple[tuple[_Node, ...], tuple[_Cluster, ...]]:
    viable = tuple(
        index for index, node in enumerate(nodes)
        if node.member_count >= config.min_route_size
    )
    tiny = tuple(index for index in range(len(nodes)) if index not in viable)
    targets: dict[int, list[int]] = defaultdict(list)
    for tiny_index in tiny:
        tiny_key = nodes[tiny_index].prefix[0]
        compatible = []
        for viable_index in viable:
            viable_key = nodes[viable_index].prefix[0]
            if (
                viable_key.dimension == tiny_key.dimension
                and _consensus_key((viable_key, tiny_key)) is not None
            ):
                compatible.append(viable_index)
        if len(compatible) == 1:
            targets[compatible[0]].append(tiny_index)

    merged_nodes: list[_Node] = []
    consumed: set[int] = set()
    for viable_index in sorted(viable, key=lambda index: nodes[index].node_key):
        tiny_indexes = tuple(sorted(
            targets.get(viable_index, ()),
            key=lambda index: nodes[index].node_key,
        ))
        keys = (
            nodes[viable_index].prefix[0],
            *(nodes[index].prefix[0] for index in tiny_indexes),
        )
        consensus = _consensus_key(keys)
        if consensus is None:
            tiny_indexes = ()
            consensus = nodes[viable_index].prefix[0]
        else:
            consumed.update(tiny_indexes)
        groups = tuple(sorted((
            *nodes[viable_index].groups,
            *(
                group
                for index in tiny_indexes
                for group in nodes[index].groups
            ),
        ), key=lambda item: item.cluster_key))
        merged_nodes.append(_Node(prefix=(consensus,), groups=groups))

    unassigned = tuple(
        group
        for index in tiny
        if index not in consumed
        for group in nodes[index].groups
    )
    return (
        tuple(sorted(merged_nodes, key=lambda item: item.node_key)),
        tuple(sorted(unassigned, key=lambda item: item.cluster_key)),
    )


def _refine_node(
    node: _Node,
    *,
    start_dimension: int,
    config: RouteDiscoveryV2Config,
) -> tuple[_Cluster, ...]:
    split_index = None
    split_buckets: dict[
        str, tuple[RouteSemanticKey, tuple[_Cluster, ...]]
    ] = {}
    for index in range(start_dimension, len(config.route_dimensions)):
        dimension = config.route_dimensions[index]
        buckets: dict[str, tuple[RouteSemanticKey, list[_Cluster]]] = {}
        for group in node.groups:
            key = _semantic_key(group.anchor, dimension)
            if key is None or len(key.values) != 1:
                continue
            bucket_key = canonical_json(key.to_dict())
            if bucket_key not in buckets:
                buckets[bucket_key] = (key, [])
            buckets[bucket_key][1].append(group)
        viable = {
            key: (semantic_key, tuple(sorted(
                groups, key=lambda item: item.cluster_key,
            )))
            for key, (semantic_key, groups) in buckets.items()
            if sum(len(item.member_views) for item in groups)
            >= config.min_route_size
        }
        if len(viable) >= 2:
            split_index = index
            split_buckets = viable
            break
    if split_index is None:
        return (_route_cluster(node.prefix, node.groups),)

    split_dimension = config.route_dimensions[split_index]
    bucket_by_signature = {
        signature_key: bucket_key
        for bucket_key, (_, groups) in split_buckets.items()
        for group in groups
        for signature_key in group.signature_keys
    }
    children: dict[str, list[_Cluster]] = {
        key: list(groups) for key, (_, groups) in split_buckets.items()
    }
    remainder = tuple(
        group for group in node.groups
        if not any(key in bucket_by_signature for key in group.signature_keys)
    )
    remainder_count = sum(len(item.member_views) for item in remainder)
    output: list[_Cluster] = []
    if remainder_count >= config.min_route_size:
        output.append(_route_cluster(node.prefix, remainder))
    else:
        unassigned: list[_Cluster] = []
        child_values = {
            bucket_key: set(_value_map(semantic_key))
            for bucket_key, (semantic_key, _) in split_buckets.items()
        }
        for group in remainder:
            key = _semantic_key(group.anchor, split_dimension)
            if key is None:
                unassigned.append(group)
                continue
            if len(key.values) <= 1:
                unassigned.append(group)
                continue
            value_keys = set(_value_map(key))
            compatible = [
                bucket_key for bucket_key, values in child_values.items()
                if value_keys & values
            ]
            if len(compatible) == 1:
                children[compatible[0]].append(group)
            else:
                unassigned.append(group)
        output.extend(unassigned)

    for bucket_key, groups in sorted(children.items()):
        semantic_key = split_buckets[bucket_key][0]
        child = _Node(
            prefix=(*node.prefix, semantic_key),
            groups=tuple(sorted(groups, key=lambda item: item.cluster_key)),
        )
        output.extend(_refine_node(
            child, start_dimension=split_index + 1, config=config,
        ))
    return tuple(sorted(output, key=lambda item: item.cluster_key))


def _clusters(
    grouped: dict[str, tuple[tuple[RouteSemanticKey, ...], list[SemanticRouteFeatureView]]],
    *,
    config: RouteDiscoveryV2Config,
) -> tuple[tuple[_Cluster, ...], dict[str, str]]:
    exact_groups: tuple[_Cluster, ...] = tuple(
        _Cluster(
            anchor=signature,
            signature_keys=(signature_key,),
            member_views=tuple(sorted(
                views, key=lambda item: item.listing_reference,
            )),
        )
        for signature_key, (signature, views) in sorted(grouped.items())
    )
    bases, unassigned = _merge_tiny_bases(
        _base_nodes(exact_groups), config=config,
    )
    clusters = [*unassigned]
    dimension_indexes = {
        dimension: index for index, dimension in enumerate(config.route_dimensions)
    }
    for base in bases:
        clusters.extend(_refine_node(
            base,
            start_dimension=dimension_indexes[base.prefix[0].dimension] + 1,
            config=config,
        ))
    clusters_tuple = tuple(sorted(clusters, key=lambda item: item.cluster_key))
    signature_cluster = {
        signature_key: cluster.anchor_key
        for cluster in clusters_tuple
        for signature_key in cluster.signature_keys
    }
    return clusters_tuple, signature_cluster


def _compatible_with_route(
    signature: tuple[RouteSemanticKey, ...],
    route_definition: tuple[RouteSemanticKey, ...],
) -> bool:
    """Return compatibility using only shared, profile-authorized facts."""

    signature_map = _definition_map(signature)
    route_map = _definition_map(route_definition)
    shared_dimensions = set(signature_map) & set(route_map)
    if not shared_dimensions:
        return False
    for dimension in shared_dimensions:
        signature_role, signature_values = signature_map[dimension]
        route_role, route_values = route_map[dimension]
        if signature_role is not route_role:
            return False
        if not (set(signature_values) & set(route_values)):
            return False
    return True


def _resolve_unclustered_signatures(
    clusters: tuple[_Cluster, ...],
    viable: dict[str, _Cluster],
    signature_cluster: dict[str, str],
) -> tuple[dict[str, _Cluster], dict[str, str], dict[str, str]]:
    """Resolve only against already-formed routes without changing identity."""

    attachments: dict[str, list[_Cluster]] = defaultdict(list)
    resolution_reasons: dict[str, str] = {}
    for cluster in clusters:
        if cluster.anchor_key in viable:
            continue
        compatible = tuple(
            anchor_key
            for anchor_key, route in sorted(viable.items())
            if _compatible_with_route(cluster.anchor, route.anchor)
        )
        if len(compatible) == 1:
            target = compatible[0]
            attachments[target].append(cluster)
            reason = "UNIQUE_COMPATIBLE_VIABLE_ROUTE_ATTACHMENT"
            for signature_key in cluster.signature_keys:
                signature_cluster[signature_key] = target
                resolution_reasons[signature_key] = reason
        elif compatible:
            reason = "AMBIGUOUS_MULTIPLE_COMPATIBLE_VIABLE_ROUTES"
            for signature_key in cluster.signature_keys:
                resolution_reasons[signature_key] = reason
        else:
            reason = "NO_COMPATIBLE_VIABLE_ROUTE"
            for signature_key in cluster.signature_keys:
                resolution_reasons[signature_key] = reason

    resolved: dict[str, _Cluster] = {}
    for anchor_key, route in sorted(viable.items()):
        attached = tuple(sorted(
            attachments.get(anchor_key, ()),
            key=lambda item: item.cluster_key,
        ))
        resolved[anchor_key] = _Cluster(
            anchor=route.anchor,
            signature_keys=tuple(sorted((
                *route.signature_keys,
                *(key for item in attached for key in item.signature_keys),
            ))),
            member_views=tuple(sorted((
                *route.member_views,
                *(view for item in attached for view in item.member_views),
            ), key=lambda item: item.listing_reference)),
        )
    return resolved, signature_cluster, resolution_reasons


def _route_id(
    definition: tuple[RouteSemanticKey, ...],
    *,
    profile: CategorySemanticProfileV1_1,
    config: RouteDiscoveryV2Config,
) -> str:
    return deterministic_id("product-route-v2", {
        "method": ROUTE_V2_METHOD, "version": ROUTE_V2_ENGINE_VERSION,
        "profile_fingerprint": profile.fingerprint,
        "config_fingerprint": config.fingerprint,
        "defining_features": [item.to_dict() for item in definition],
    })


def _preliminary_state(
    view: SemanticRouteFeatureView,
    config: RouteDiscoveryV2Config,
) -> tuple[MembershipStatus, tuple[RouteSemanticKey, ...], tuple[str, ...]]:
    if not view.eligible_for_primary_cohort:
        if view.cohort_state is CohortEligibilityState.REVIEW_REQUIRED:
            return MembershipStatus.REVIEW_REQUIRED, (), (
                "S2_PRIMARY_COHORT_REVIEW_REQUIRED",
            )
        return MembershipStatus.UNCLASSIFIED, (), (
            f"S2_COHORT_EXCLUDED:{view.cohort_state.value}",
        )
    conflicted = tuple(sorted(
        dimension for dimension in config.route_dimensions
        if (feature := view.feature(dimension)) is not None
        and bool(set(feature.relationship_states) & _CONFLICT_STATES)
    ))
    if conflicted:
        return MembershipStatus.REVIEW_REQUIRED, (), tuple(
            f"ROUTE_FEATURE_CONFLICT:{dimension}" for dimension in conflicted
        )
    signature = _signature(view, config)
    if len(signature) < config.min_defining_dimensions:
        return MembershipStatus.UNCLASSIFIED, signature, (
            "INSUFFICIENT_PROFILE_AUTHORIZED_ROUTE_SEMANTICS",
        )
    return MembershipStatus.ASSIGNED, signature, ()


def _membership(
    view: SemanticRouteFeatureView,
    *,
    status: MembershipStatus,
    route_id: str | None,
    signature: tuple[RouteSemanticKey, ...],
    reasons: tuple[str, ...],
    limitations: tuple[str, ...],
    profile: CategorySemanticProfileV1_1,
    config: RouteDiscoveryV2Config,
) -> RouteV2Membership:
    assignment_features = tuple(sorted(
        signature, key=lambda item: (item.role.value, item.dimension),
    ))
    evidence_ids = tuple(sorted({
        evidence_id
        for key in assignment_features
        if (feature := view.feature(key.dimension)) is not None
        for evidence_id in feature.evidence_ids
    }))
    logical = {
        "contract_version": "route-membership-v2.0",
        "feature_view_id": view.view_id,
        "semantic_listing_result_id": view.semantic_listing_result_id,
        "listing_reference": view.listing_reference, "status": status.value,
        "primary_route_id": route_id,
        "assignment_features": [item.to_dict() for item in assignment_features],
        "membership_reason_codes": sorted(set(reasons)),
        "evidence_ids": list(evidence_ids),
        "profile_fingerprint": profile.fingerprint,
        "route_config_fingerprint": config.fingerprint,
        "limitations": sorted(set(limitations)),
    }
    return RouteV2Membership(
        membership_id=deterministic_id("route-membership-v2", logical),
        semantic_fingerprint=_hash(logical),
        feature_view_id=view.view_id,
        semantic_listing_result_id=view.semantic_listing_result_id,
        listing_reference=view.listing_reference, status=status,
        primary_route_id=route_id, assignment_features=assignment_features,
        membership_reason_codes=tuple(logical["membership_reason_codes"]),
        evidence_ids=evidence_ids, profile_fingerprint=profile.fingerprint,
        route_config_fingerprint=config.fingerprint,
        limitations=tuple(logical["limitations"]),
    )


def _metric_records(
    dataset: GovernedMarketDatasetV1,
    views: tuple[SemanticRouteFeatureView, ...],
    *,
    config: RouteDiscoveryV2Config,
) -> dict[str, ProductMapRecord]:
    listings = {item.asin: item for item in dataset.records}
    result: dict[str, ProductMapRecord] = {}
    dimensions = tuple(dict.fromkeys((
        *config.route_dimensions, *config.adoption_dimensions,
    )))
    for view in views:
        listing = listings[view.listing_reference]
        attributes = []
        for dimension in dimensions:
            feature = view.feature(dimension)
            conflict = (
                feature is not None
                and bool(set(feature.relationship_states) & _CONFLICT_STATES)
            )
            attributes.append(RouteAttribute(
                dimension=dimension,
                status=(
                    "UNAVAILABLE" if feature is None
                    else "REVIEW_REQUIRED" if conflict
                    else "AVAILABLE"
                ),
                values=() if feature is None else feature.values,
                evidence_ids=() if feature is None else feature.evidence_ids,
                conflict_ids=() if feature is None or not conflict else feature.relationship_ids,
                limitations=() if feature is None else feature.limitations,
            ))
        fields = build_governed_market_fields(
            listing, observed_date=dataset.observed_date,
        )
        age = next(item for item in fields if item.name == "listing_age_days")
        is_new = None
        if age.availability is Availability.AVAILABLE:
            is_new = int(age.value) <= config.new_product_max_age_days
        limitations = set(view.limitations)
        if is_new is None:
            limitations.add("NEW_PRODUCT_FLAG_UNAVAILABLE_MISSING_AGE")
        parent_evidence_id = deterministic_id("product-map-parent-evidence", {
            "record": listing.record_fingerprint, "parent_asin": listing.parent_asin,
        })
        logical = {
            "asin": listing.asin, "parent_asin": listing.parent_asin,
            "parent_evidence_id": parent_evidence_id,
            "upstream_listing_fingerprint": listing.record_fingerprint,
            "semantic_feature_view_id": view.view_id,
            "semantic_feature_view_fingerprint": view.semantic_fingerprint,
            "attributes": [item.to_dict() for item in attributes],
            "fields": [item.to_dict() for item in fields],
            "flags": {"is_new_product": is_new},
            "limitations": sorted(limitations),
        }
        result[view.listing_reference] = ProductMapRecord(
            record_id=deterministic_id("semantic-product-map-record-v2", logical),
            semantic_fingerprint=_hash(logical), asin=listing.asin,
            parent_asin=listing.parent_asin, parent_evidence_id=parent_evidence_id,
            upstream_listing_fingerprint=listing.record_fingerprint,
            attribute_record_id=view.view_id,
            attribute_record_fingerprint=view.semantic_fingerprint,
            attributes=tuple(sorted(attributes, key=lambda item: item.dimension)),
            fields=fields, flags=(("is_new_product", is_new),),
            limitations=tuple(sorted(limitations)),
        )
    return result


def _descriptors(
    members: tuple[SemanticRouteFeatureView, ...],
    *,
    dimensions: tuple[str, ...],
    relevance: RoleRelevance,
    maximum: int = 4,
) -> tuple[RouteDescriptor, ...]:
    descriptors: list[RouteDescriptor] = []
    for dimension in dimensions:
        counts: Counter[str] = Counter()
        values: dict[str, Any] = {}
        role = None
        for view in members:
            feature = view.feature(dimension)
            if feature is None or feature.relevance is not relevance:
                continue
            role = feature.role
            for value in feature.values:
                key = canonical_json(value)
                counts[key] += 1
                values[key] = value
        if role is None:
            continue
        for key, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:2]:
            if Decimal(count) / Decimal(len(members)) < Decimal("0.25"):
                continue
            descriptors.append(RouteDescriptor(
                role=role, dimension=dimension, value=values[key], member_count=count,
                share=float(Decimal(count) / Decimal(len(members))),
            ))
    return tuple(descriptors[:maximum])


def _coverage(
    members: tuple[SemanticRouteFeatureView, ...],
    config: RouteDiscoveryV2Config,
) -> tuple[tuple[str, float], ...]:
    return tuple((dimension, float(
        Decimal(sum(
            (feature := view.feature(dimension)) is not None
            and bool(feature.defining_values)
            for view in members
        )) / Decimal(len(members))
    )) for dimension in config.route_dimensions)


def _label(definition: tuple[RouteSemanticKey, ...]) -> str:
    return " | ".join(
        f"{item.role.value}:{item.dimension}={canonical_json(list(item.values))}"
        for item in definition
    )[:320]


def _semantic_distance(left: ProductRouteV2, right: ProductRouteV2) -> Decimal:
    union = left.semantic_tokens | right.semantic_tokens
    if not union:
        return Decimal("0")
    return Decimal(len(left.semantic_tokens ^ right.semantic_tokens)) / Decimal(len(union))


def _materially_distinct(left: ProductRouteV2, right: ProductRouteV2) -> bool:
    """Require contradictory known route semantics, never missingness, as diversity."""

    left_map = _definition_map(left.defining_features)
    right_map = _definition_map(right.defining_features)
    return any(
        set(left_map[dimension][1]).isdisjoint(right_map[dimension][1])
        for dimension in set(left_map) & set(right_map)
    )


def _metric_number(route: ProductRouteV2, name: str) -> Decimal:
    value = route.metric(name).value
    if type(value) not in {int, float}:
        return Decimal("-1")
    return Decimal(str(value))


def _select_candidates(
    routes: tuple[ProductRouteV2, ...],
    config: RouteDiscoveryV2Config,
) -> tuple[CandidateSelectionStatus, tuple[CandidateRouteV2, ...]]:
    qualified: list[tuple[ProductRouteV2, tuple[str, ...]]] = []
    seen_semantics: set[frozenset[tuple[str, str]]] = set()
    for route in sorted(routes, key=lambda item: item.route_id):
        if route.semantic_tokens in seen_semantics:
            continue
        seen_semantics.add(route.semantic_tokens)
        reasons = candidate_metric_reason_codes(route)  # frozen SP-041D evidence reasons
        if len(reasons) >= config.candidate_min_reason_count:
            qualified.append((route, reasons))
    qualified.sort(key=lambda item: (
        -item[0].member_count, -len(item[1]),
        -_metric_number(item[0], "demand_efficiency"),
        -_metric_number(item[0], "route_sales_share"),
        item[0].route_id,
    ))
    adjacency: dict[int, frozenset[int]] = {}
    for left_index, (left, _) in enumerate(qualified):
        neighbours = {
            right_index
            for right_index, (right, _) in enumerate(qualified)
            if left_index != right_index
            and _materially_distinct(left, right)
            and _semantic_distance(left, right) >= config.candidate_min_semantic_distance
        }
        adjacency[left_index] = frozenset(neighbours)

    def first_clique(
        target: int,
        selected: tuple[int, ...] = (),
        available: tuple[int, ...] | None = None,
    ) -> tuple[int, ...] | None:
        candidates = tuple(range(len(qualified))) if available is None else available
        if len(selected) == target:
            return selected
        needed = target - len(selected)
        if len(candidates) < needed:
            return None
        for offset, index in enumerate(candidates):
            if len(candidates) - offset < needed:
                break
            remaining = tuple(
                candidate for candidate in candidates[offset + 1:]
                if candidate in adjacency[index]
            )
            found = first_clique(target, (*selected, index), remaining)
            if found is not None:
                return found
        return None

    selected_indexes = None
    for target in range(
        min(config.candidate_max_count, len(qualified)),
        config.candidate_min_count - 1,
        -1,
    ):
        selected_indexes = first_clique(target)
        if selected_indexes is not None:
            break
    if selected_indexes is None:
        return CandidateSelectionStatus.INSUFFICIENT_EVIDENCE, ()
    selected: list[tuple[ProductRouteV2, tuple[str, ...], Decimal | None]] = []
    for index in selected_indexes:
        route, reasons = qualified[index]
        distances = [_semantic_distance(route, item[0]) for item in selected]
        selected.append((route, reasons, min(distances) if distances else None))
    return CandidateSelectionStatus.SELECTED, tuple(
        CandidateRouteV2(
            priority=index, route_id=route.route_id, reason_codes=reasons,
            minimum_semantic_distance_to_prior=(
                None if distance is None else float(distance)
            ),
        )
        for index, (route, reasons, distance) in enumerate(selected, start=1)
    )


def build_route_discovery_v2(
    dataset: GovernedMarketDatasetV1,
    semantic_result: SemanticEngineV2Result,
    *,
    profile: CategorySemanticProfileV1_1,
    config: RouteDiscoveryV2Config,
) -> RouteDiscoveryV2Result:
    """Build deterministic routes without re-evaluating S2 identity or role."""

    views = build_semantic_route_feature_views(
        dataset, semantic_result, profile=profile, config=config,
    )
    preliminary = {
        view.view_id: _preliminary_state(view, config) for view in views
    }
    grouped: dict[
        str, tuple[tuple[RouteSemanticKey, ...], list[SemanticRouteFeatureView]]
    ] = {}
    for view in views:
        status, signature, _ = preliminary[view.view_id]
        if status is not MembershipStatus.ASSIGNED:
            continue
        key = _signature_key(signature)
        if key not in grouped:
            grouped[key] = (signature, [])
        grouped[key][1].append(view)
    clusters, signature_cluster = _clusters(
        grouped, config=config,
    )
    viable = {
        cluster.anchor_key: cluster for cluster in clusters
        if len(cluster.member_views) >= config.min_route_size
    }
    viable, signature_cluster, resolution_reasons = (
        _resolve_unclustered_signatures(
            clusters, viable, signature_cluster,
        )
    )
    route_ids = {
        anchor_key: _route_id(
            cluster.anchor, profile=profile, config=config,
        )
        for anchor_key, cluster in viable.items()
    }
    memberships = []
    for view in views:
        status, signature, state_reasons = preliminary[view.view_id]
        route_id = None
        limitations = list(view.limitations)
        reasons = list(state_reasons)
        if status is MembershipStatus.ASSIGNED:
            signature_key = _signature_key(signature)
            anchor_key = signature_cluster[signature_key]
            cluster = viable.get(anchor_key)
            if cluster is None:
                resolution_reason = resolution_reasons[signature_key]
                if resolution_reason == "AMBIGUOUS_MULTIPLE_COMPATIBLE_VIABLE_ROUTES":
                    status = MembershipStatus.REVIEW_REQUIRED
                    reasons.extend((
                        "AMBIGUOUS_HIERARCHICAL_ROUTE_MEMBERSHIP",
                        resolution_reason,
                    ))
                else:
                    status = MembershipStatus.UNCLASSIFIED
                    reasons.extend((
                        "HIERARCHICAL_SEMANTIC_GROUP_NOT_VIABLE",
                        resolution_reason,
                    ))
            else:
                route_id = route_ids[anchor_key]
                reasons.extend((
                    "PRIMARY_ONLY_COHORT_ELIGIBLE",
                    "PROFILE_AUTHORIZED_ROUTE_FEATURES",
                    "FULL_DEFINING_VALUE_SETS_PRESERVED",
                    "HIERARCHICAL_SPARSE_SEMANTIC_CONSENSUS",
                ))
                resolution_reason = resolution_reasons.get(signature_key)
                if resolution_reason is not None:
                    reasons.append(resolution_reason)
                    limitations.append(
                        "ROUTE_DEFINITION_UNCHANGED_BY_COMPATIBLE_ATTACHMENT"
                    )
                if len(cluster.anchor) > 1:
                    reasons.append("HIERARCHICAL_REFINED_CHILD_ROUTE")
                else:
                    reasons.append("HIERARCHICAL_BASE_OR_BROAD_PARENT_ROUTE")
                if signature_key != anchor_key:
                    limitations.append(
                        "NONDEFINING_OR_RARE_SEMANTICS_OUTSIDE_ROUTE_IDENTITY"
                    )
                if len(signature) < len(config.route_dimensions):
                    limitations.append("SPARSE_ROUTE_SEMANTICS_PRESERVED")
        memberships.append(_membership(
            view, status=status, route_id=route_id, signature=signature,
            reasons=tuple(reasons), limitations=tuple(limitations),
            profile=profile, config=config,
        ))
    memberships_tuple = tuple(sorted(
        memberships, key=lambda item: item.listing_reference,
    ))
    membership_by_listing = {
        item.listing_reference: item for item in memberships_tuple
    }
    metric_records = _metric_records(dataset, views, config=config)
    assigned_memberships = tuple(
        item for item in memberships_tuple if item.status is MembershipStatus.ASSIGNED
    )
    assigned_records = tuple(
        metric_records[item.listing_reference] for item in assigned_memberships
    )
    unclassified_count = sum(
        item.status is MembershipStatus.UNCLASSIFIED for item in memberships_tuple
    )
    review_count = sum(
        item.status is MembershipStatus.REVIEW_REQUIRED for item in memberships_tuple
    )

    dataset_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="governed-market-dataset",
        target_id=dataset.dataset_id, target_version=dataset.contract_version,
        content_fingerprint=dataset.semantic_fingerprint,
    )
    semantic_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="semantic-engine-v2-result",
        target_id=semantic_result.result_id,
        target_version=semantic_result.contract_version,
        content_fingerprint=semantic_result.semantic_fingerprint,
        provenance_reference_ids=(dataset_reference.reference_id,),
    )
    profile_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="category-semantic-profile",
        target_id=profile.profile_id, target_version=profile.version,
        content_fingerprint=profile.fingerprint,
    )
    config_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="route-discovery-v2-config",
        target_id=config.config_id, target_version=config.version,
        content_fingerprint=config.fingerprint,
    )
    grain_reference = build_reference(
        kind=ReferenceKind.REPORT_LOCAL, namespace="product-grain",
        target_id="LISTING_ASIN_NO_PARENT_COLLAPSE", target_version="1.0",
        provenance_reference_ids=(dataset_reference.reference_id,),
    )
    references: list[Any] = [
        dataset_reference, semantic_reference, profile_reference,
        config_reference, grain_reference,
    ]
    provenance_ids = tuple(sorted((
        dataset_reference.reference_id, semantic_reference.reference_id,
        profile_reference.reference_id, config_reference.reference_id,
    )))

    denominators: list[Any] = []
    routes: list[ProductRouteV2] = []
    for anchor_key, cluster in sorted(viable.items()):
        route_id = route_ids[anchor_key]
        member_views = tuple(cluster.member_views)
        route_memberships = tuple(
            membership_by_listing[item.listing_reference] for item in member_views
        )
        members = tuple(
            metric_records[item.listing_reference] for item in member_views
        )
        route_reference = build_reference(
            kind=ReferenceKind.REPORT_LOCAL, namespace="product-route-v2",
            target_id=route_id, target_version=ROUTE_V2_ENGINE_VERSION,
            provenance_reference_ids=provenance_ids,
        )
        references.append(route_reference)
        metrics, route_denominators, metric_references = build_route_metrics(
            route_id=route_id, route_reference_id=route_reference.reference_id,
            members=members, assigned_records=assigned_records,
            total_listing_count=len(views), unclassified_count=unclassified_count,
            review_required_count=review_count, marketplace=dataset.marketplace,
            config=config, product_grain_reference_id=grain_reference.reference_id,
            provenance_reference_ids=provenance_ids,
        )
        denominators.extend(route_denominators)
        references.extend(metric_references)
        secondary = _descriptors(
            member_views, dimensions=config.descriptor_dimensions,
            relevance=RoleRelevance.SECONDARY,
        )
        facets = _descriptors(
            member_views, dimensions=config.descriptor_dimensions,
            relevance=RoleRelevance.FACET_ONLY,
        )
        logical = {
            "route_id": route_id, "label": _label(cluster.anchor),
            "defining_features": [item.to_dict() for item in cluster.anchor],
            "secondary_descriptors": [item.to_dict() for item in secondary],
            "facet_descriptors": [item.to_dict() for item in facets],
            "member_count": len(member_views),
            "member_listing_references": [item.listing_reference for item in member_views],
            "membership_ids": [item.membership_id for item in route_memberships],
            "assignment_evidence_ids": sorted({
                evidence for item in route_memberships for evidence in item.evidence_ids
            }),
            "assignment_limitations": sorted({
                limitation for item in route_memberships for limitation in item.limitations
            }),
            "feature_coverage": _coverage(member_views, config),
            "discovery_method": ROUTE_V2_METHOD,
            "discovery_version": ROUTE_V2_ENGINE_VERSION,
            "profile_fingerprint": profile.fingerprint,
            "config_fingerprint": config.fingerprint,
            "metrics": [(key, value.to_dict()) for key, value in metrics],
        }
        routes.append(ProductRouteV2(
            route_id=route_id, semantic_fingerprint=_hash(logical),
            label=logical["label"], defining_features=cluster.anchor,
            secondary_descriptors=secondary, facet_descriptors=facets,
            member_count=len(member_views),
            member_listing_references=tuple(logical["member_listing_references"]),
            membership_ids=tuple(logical["membership_ids"]),
            assignment_evidence_ids=tuple(logical["assignment_evidence_ids"]),
            assignment_limitations=tuple(logical["assignment_limitations"]),
            feature_coverage=logical["feature_coverage"],
            discovery_method=ROUTE_V2_METHOD,
            discovery_version=ROUTE_V2_ENGINE_VERSION,
            profile_fingerprint=profile.fingerprint,
            config_fingerprint=config.fingerprint, metrics=metrics,
        ))
    routes_tuple = tuple(sorted(routes, key=lambda item: item.route_id))

    if routes_tuple:
        listing_sum = sum((
            Decimal(str(route.metric("route_listing_share").value))
            for route in routes_tuple
        ), Decimal("0"))
        if abs(listing_sum - Decimal("1")) > Decimal("0.000000001"):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_LISTING_SHARE_INVARIANT_FAILED",
                "primary route listing shares do not sum to one",
            )
        sales = [
            route.metric("route_sales_share").value for route in routes_tuple
            if route.metric("route_sales_share").value is not None
        ]
        if sales and abs(
            sum((Decimal(str(value)) for value in sales), Decimal("0")) - Decimal("1")
        ) > Decimal("0.000000001"):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_SALES_SHARE_INVARIANT_FAILED",
                "available-sales route shares do not sum to one",
            )
    candidate_status, candidates = _select_candidates(routes_tuple, config)
    diagnostics = (
        ("route_ids", tuple(item.route_id for item in routes_tuple)),
        ("route_fingerprints", tuple(item.semantic_fingerprint for item in routes_tuple)),
        ("route_size_distribution", tuple(sorted(item.member_count for item in routes_tuple))),
        ("membership_counts", {
            "assigned": len(assigned_memberships),
            "unclassified": unclassified_count, "review_required": review_count,
        }),
        ("candidate_reason_codes", tuple(
            {"route_id": item.route_id, "reason_codes": item.reason_codes}
            for item in candidates
        )),
        ("network_calls", 0), ("provider_calls", 0),
        ("credential_accesses", 0), ("llm_authoritative_decisions", 0),
        ("category_specific_generic_branches", 0),
        ("downstream_representation_selection_count", 0),
        ("private_values_in_diagnostics", False),
    )
    sorted_denominators = tuple(sorted(
        denominators, key=lambda item: item.denominator_id,
    ))
    sorted_references = tuple(sorted(
        references, key=lambda item: item.reference_id,
    ))
    logical_result = {
        "contract_version": "route-discovery-v2-result-v1.0",
        "upstream_dataset_id": dataset.dataset_id,
        "upstream_dataset_fingerprint": dataset.semantic_fingerprint,
        "upstream_semantic_result_id": semantic_result.result_id,
        "upstream_semantic_fingerprint": semantic_result.semantic_fingerprint,
        "semantic_profile_id": profile.profile_id,
        "semantic_profile_version": profile.version,
        "semantic_profile_fingerprint": profile.fingerprint,
        "route_engine_version": ROUTE_V2_ENGINE_VERSION,
        "route_config_id": config.config_id,
        "route_config_version": config.version,
        "route_config_fingerprint": config.fingerprint,
        "counts": {
            "listing": len(views),
            "primary_cohort_eligible": sum(
                item.eligible_for_primary_cohort for item in views
            ),
            "assigned": len(assigned_memberships),
            "unclassified": unclassified_count,
            "review_required": review_count,
        },
        "feature_views": [item.to_dict() for item in views],
        "memberships": [item.to_dict() for item in memberships_tuple],
        "routes": [item.to_dict() for item in routes_tuple],
        "denominators": [item.to_dict() for item in sorted_denominators],
        "references": [item.to_dict() for item in sorted_references],
        "candidate_selection_status": candidate_status.value,
        "candidates": [item.to_dict() for item in candidates],
        "diagnostics": {key: value for key, value in diagnostics},
    }
    return RouteDiscoveryV2Result(
        result_id=deterministic_id("route-discovery-v2-result", logical_result),
        semantic_fingerprint=_hash(logical_result),
        upstream_dataset_id=dataset.dataset_id,
        upstream_dataset_fingerprint=dataset.semantic_fingerprint,
        upstream_semantic_result_id=semantic_result.result_id,
        upstream_semantic_fingerprint=semantic_result.semantic_fingerprint,
        semantic_profile_id=profile.profile_id,
        semantic_profile_version=profile.version,
        semantic_profile_fingerprint=profile.fingerprint,
        route_engine_version=ROUTE_V2_ENGINE_VERSION,
        route_config_id=config.config_id, route_config_version=config.version,
        route_config_fingerprint=config.fingerprint,
        listing_count=len(views),
        primary_cohort_eligible_count=sum(
            item.eligible_for_primary_cohort for item in views
        ),
        assigned_count=len(assigned_memberships),
        unclassified_count=unclassified_count, review_required_count=review_count,
        feature_views=views, memberships=memberships_tuple, routes=routes_tuple,
        denominators=sorted_denominators, references=sorted_references,
        candidate_selection_status=candidate_status, candidates=candidates,
        diagnostics=diagnostics,
    )


__all__ = ("build_route_discovery_v2",)
