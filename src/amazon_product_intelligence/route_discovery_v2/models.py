"""Explainable contracts for S2-backed Route Discovery V2."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.market_report.v0_2.models.common import (
    ContractReference,
)
from amazon_product_intelligence.market_report.v0_2.models.metric_context import (
    MetricContextEnvelope,
)
from amazon_product_intelligence.product_route_opportunity.models import (
    CandidateSelectionStatus,
    MembershipStatus,
    MetricDenominator,
)
from amazon_product_intelligence.semantic_engine_v2.models import (
    CohortEligibilityState,
    RoleRelevance,
    UniversalSemanticRole,
)

from .config import (
    ROUTE_V2_ENGINE_VERSION,
    ROUTE_V2_MEMBERSHIP_CONTRACT_VERSION,
    ROUTE_V2_METHOD,
    ROUTE_V2_RESULT_CONTRACT_VERSION,
)
from .errors import RouteDiscoveryV2Error


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _texts(values: Iterable[str], name: str) -> tuple[str, ...]:
    result = tuple(sorted(set(values)))
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", f"{name} is blank")
    return result


def _values(values: Iterable[Any]) -> tuple[Any, ...]:
    unique = {canonical_json(value): _json_value(value) for value in values}
    return tuple(unique[key] for key in sorted(unique))


@dataclass(frozen=True, slots=True)
class SemanticRouteFeature:
    feature_id: str
    semantic_fingerprint: str
    role: UniversalSemanticRole
    dimension: str
    values: tuple[Any, ...]
    defining_values: tuple[Any, ...]
    profile_id: str
    profile_version: str
    profile_fingerprint: str
    source_policy_id: str
    relevance: RoleRelevance
    route_critical: bool
    exact_specification: bool
    multi_value: bool
    fact_ids: tuple[str, ...]
    defining_fact_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    relationship_ids: tuple[str, ...]
    relationship_states: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.role, UniversalSemanticRole):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "invalid feature role")
        if not isinstance(self.relevance, RoleRelevance):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "invalid relevance")
        object.__setattr__(self, "values", _values(self.values))
        object.__setattr__(self, "defining_values", _values(self.defining_values))
        if set(map(canonical_json, self.defining_values)) - set(map(canonical_json, self.values)):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "defining values must be observed feature values",
            )
        for name in (
            "fact_ids", "defining_fact_ids", "evidence_ids", "relationship_ids",
            "relationship_states", "limitations",
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        if set(self.defining_fact_ids) - set(self.fact_ids):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID",
                "defining fact IDs must reference observed feature facts",
            )
        if self.defining_values and (
            not self.defining_fact_ids or not self.evidence_ids
        ):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID",
                "defining values require facts and evidence",
            )
        if self.values and (not self.fact_ids or not self.evidence_ids):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID",
                "observed values require facts and evidence",
            )
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "feature fingerprint mismatch",
            )
        if self.feature_id != deterministic_id("semantic-route-feature-v2", logical):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "feature ID mismatch")

    @property
    def defining_value_keys(self) -> tuple[str, ...]:
        return tuple(canonical_json(item) for item in self.defining_values)

    def logical_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value, "dimension": self.dimension,
            "values": list(self.values), "defining_values": list(self.defining_values),
            "profile_id": self.profile_id, "profile_version": self.profile_version,
            "profile_fingerprint": self.profile_fingerprint,
            "source_policy_id": self.source_policy_id,
            "relevance": self.relevance.value, "route_critical": self.route_critical,
            "exact_specification": self.exact_specification, "multi_value": self.multi_value,
            "fact_ids": list(self.fact_ids),
            "defining_fact_ids": list(self.defining_fact_ids),
            "evidence_ids": list(self.evidence_ids),
            "relationship_ids": list(self.relationship_ids),
            "relationship_states": list(self.relationship_states),
            "limitations": list(self.limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_id": self.feature_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            **self.logical_dict(),
        }


def build_semantic_route_feature(**content: Any) -> SemanticRouteFeature:
    material = dict(content)
    material["values"] = _values(material["values"])
    material["defining_values"] = _values(material["defining_values"])
    for name in (
        "fact_ids", "defining_fact_ids", "evidence_ids", "relationship_ids",
        "relationship_states", "limitations",
    ):
        material[name] = tuple(sorted(set(material[name])))
    logical = {
        key: (
            value.value if hasattr(value, "value")
            else list(value) if isinstance(value, tuple)
            else value
        )
        for key, value in material.items()
    }
    logical["values"] = list(material["values"])
    logical["defining_values"] = list(material["defining_values"])
    fingerprint = _hash(logical)
    return SemanticRouteFeature(
        feature_id=deterministic_id("semantic-route-feature-v2", logical),
        semantic_fingerprint=fingerprint,
        **material,
    )


@dataclass(frozen=True, slots=True)
class SemanticRouteFeatureView:
    view_id: str
    semantic_fingerprint: str
    listing_reference: str
    upstream_record_fingerprint: str
    semantic_listing_result_id: str
    semantic_listing_fingerprint: str
    cohort_state: CohortEligibilityState
    eligible_for_primary_cohort: bool
    features: tuple[SemanticRouteFeature, ...]
    review_reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.eligible_for_primary_cohort != (
            self.cohort_state is CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE
        ):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "feature-view cohort state mismatch",
            )
        dimensions = tuple(item.dimension for item in self.features)
        if len(dimensions) != len(set(dimensions)):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "feature-view dimensions duplicate",
            )
        object.__setattr__(self, "features", tuple(sorted(
            self.features, key=lambda item: (item.role.value, item.dimension),
        )))
        object.__setattr__(
            self, "review_reason_codes", _texts(self.review_reason_codes, "review reasons"),
        )
        object.__setattr__(self, "limitations", _texts(self.limitations, "limitations"))
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "feature-view fingerprint mismatch",
            )
        if self.view_id != deterministic_id("semantic-route-feature-view-v2", logical):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "feature-view ID mismatch")

    def feature(self, dimension: str) -> SemanticRouteFeature | None:
        return next((item for item in self.features if item.dimension == dimension), None)

    def logical_dict(self) -> dict[str, Any]:
        return {
            "listing_reference": self.listing_reference,
            "upstream_record_fingerprint": self.upstream_record_fingerprint,
            "semantic_listing_result_id": self.semantic_listing_result_id,
            "semantic_listing_fingerprint": self.semantic_listing_fingerprint,
            "cohort_state": self.cohort_state.value,
            "eligible_for_primary_cohort": self.eligible_for_primary_cohort,
            "features": [item.to_dict() for item in self.features],
            "review_reason_codes": list(self.review_reason_codes),
            "limitations": list(self.limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "view_id": self.view_id, "semantic_fingerprint": self.semantic_fingerprint,
            **self.logical_dict(),
        }


@dataclass(frozen=True, slots=True)
class RouteSemanticKey:
    role: UniversalSemanticRole
    dimension: str
    values: tuple[Any, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "values", _values(self.values))
        if not self.values:
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "route key is empty")

    @property
    def value_keys(self) -> tuple[str, ...]:
        return tuple(canonical_json(item) for item in self.values)

    @property
    def token_set(self) -> frozenset[tuple[str, str]]:
        return frozenset((self.dimension, value) for value in self.value_keys)

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value, "dimension": self.dimension,
            "values": list(self.values),
        }


@dataclass(frozen=True, slots=True)
class RouteV2Membership:
    membership_id: str
    semantic_fingerprint: str
    feature_view_id: str
    semantic_listing_result_id: str
    listing_reference: str
    status: MembershipStatus
    primary_route_id: str | None
    assignment_features: tuple[RouteSemanticKey, ...]
    membership_reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    profile_fingerprint: str
    route_config_fingerprint: str
    limitations: tuple[str, ...]
    contract_version: str = ROUTE_V2_MEMBERSHIP_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != ROUTE_V2_MEMBERSHIP_CONTRACT_VERSION:
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "membership version")
        if (self.status is MembershipStatus.ASSIGNED) != (self.primary_route_id is not None):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "membership status/route mismatch",
            )
        object.__setattr__(self, "assignment_features", tuple(sorted(
            self.assignment_features, key=lambda item: (item.role.value, item.dimension),
        )))
        for name in ("membership_reason_codes", "evidence_ids", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "membership fingerprint mismatch",
            )
        if self.membership_id != deterministic_id("route-membership-v2", logical):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "membership ID mismatch")

    def logical_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "feature_view_id": self.feature_view_id,
            "semantic_listing_result_id": self.semantic_listing_result_id,
            "listing_reference": self.listing_reference, "status": self.status.value,
            "primary_route_id": self.primary_route_id,
            "assignment_features": [item.to_dict() for item in self.assignment_features],
            "membership_reason_codes": list(self.membership_reason_codes),
            "evidence_ids": list(self.evidence_ids),
            "profile_fingerprint": self.profile_fingerprint,
            "route_config_fingerprint": self.route_config_fingerprint,
            "limitations": list(self.limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "membership_id": self.membership_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            **self.logical_dict(),
        }


@dataclass(frozen=True, slots=True)
class RouteDescriptor:
    role: UniversalSemanticRole
    dimension: str
    value: Any
    member_count: int
    share: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role.value, "dimension": self.dimension,
            "value": _json_value(self.value), "member_count": self.member_count,
            "share": self.share,
        }


@dataclass(frozen=True, slots=True)
class ProductRouteV2:
    route_id: str
    semantic_fingerprint: str
    label: str
    defining_features: tuple[RouteSemanticKey, ...]
    secondary_descriptors: tuple[RouteDescriptor, ...]
    facet_descriptors: tuple[RouteDescriptor, ...]
    member_count: int
    member_listing_references: tuple[str, ...]
    membership_ids: tuple[str, ...]
    assignment_evidence_ids: tuple[str, ...]
    assignment_limitations: tuple[str, ...]
    feature_coverage: tuple[tuple[str, float], ...]
    discovery_method: str
    discovery_version: str
    profile_fingerprint: str
    config_fingerprint: str
    metrics: tuple[tuple[str, MetricContextEnvelope], ...]

    def __post_init__(self) -> None:
        if self.discovery_method != ROUTE_V2_METHOD:
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "route discovery method",
            )
        if self.discovery_version != ROUTE_V2_ENGINE_VERSION:
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "route discovery version",
            )
        if self.member_count != len(self.member_listing_references):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "route member count")
        if self.member_count != len(self.membership_ids):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "route membership count")
        if not self.defining_features:
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "route has no definition")
        if len(self.member_listing_references) != len(set(self.member_listing_references)):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "route member references duplicate",
            )
        if len(self.membership_ids) != len(set(self.membership_ids)):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "route membership IDs duplicate",
            )
        expected_route_id = deterministic_id("product-route-v2", {
            "method": self.discovery_method,
            "version": self.discovery_version,
            "profile_fingerprint": self.profile_fingerprint,
            "config_fingerprint": self.config_fingerprint,
            "defining_features": [
                item.to_dict() for item in self.defining_features
            ],
        })
        if self.route_id != expected_route_id:
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "route ID mismatch",
            )
        if self.semantic_fingerprint != _hash(self.logical_dict()):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "route fingerprint mismatch",
            )

    @property
    def semantic_tokens(self) -> frozenset[tuple[str, str]]:
        return frozenset(token for item in self.defining_features for token in item.token_set)

    def metric(self, name: str) -> MetricContextEnvelope:
        return dict(self.metrics)[name]

    def logical_dict(self) -> dict[str, Any]:
        """Return the exact canonical material covered by the route fingerprint."""

        return {
            "route_id": self.route_id,
            "label": self.label,
            "defining_features": [
                item.to_dict() for item in self.defining_features
            ],
            "secondary_descriptors": [
                item.to_dict() for item in self.secondary_descriptors
            ],
            "facet_descriptors": [
                item.to_dict() for item in self.facet_descriptors
            ],
            "member_count": self.member_count,
            "member_listing_references": list(self.member_listing_references),
            "membership_ids": list(self.membership_ids),
            "assignment_evidence_ids": list(self.assignment_evidence_ids),
            "assignment_limitations": list(self.assignment_limitations),
            "feature_coverage": self.feature_coverage,
            "discovery_method": self.discovery_method,
            "discovery_version": self.discovery_version,
            "profile_fingerprint": self.profile_fingerprint,
            "config_fingerprint": self.config_fingerprint,
            "metrics": [
                (key, value.to_dict()) for key, value in self.metrics
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id, "semantic_fingerprint": self.semantic_fingerprint,
            "label": self.label,
            "defining_features": [item.to_dict() for item in self.defining_features],
            "secondary_descriptors": [item.to_dict() for item in self.secondary_descriptors],
            "facet_descriptors": [item.to_dict() for item in self.facet_descriptors],
            "member_count": self.member_count,
            "member_listing_references": list(self.member_listing_references),
            "membership_ids": list(self.membership_ids),
            "assignment_evidence_ids": list(self.assignment_evidence_ids),
            "assignment_limitations": list(self.assignment_limitations),
            "feature_coverage": dict(self.feature_coverage),
            "discovery": {
                "method": self.discovery_method, "version": self.discovery_version,
                "profile_fingerprint": self.profile_fingerprint,
                "config_fingerprint": self.config_fingerprint,
            },
            "metrics": {key: value.to_dict() for key, value in self.metrics},
        }


@dataclass(frozen=True, slots=True)
class CandidateRouteV2:
    priority: int
    route_id: str
    reason_codes: tuple[str, ...]
    minimum_semantic_distance_to_prior: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority, "route_id": self.route_id,
            "reason_codes": list(self.reason_codes),
            "minimum_semantic_distance_to_prior": self.minimum_semantic_distance_to_prior,
        }


@dataclass(frozen=True, slots=True)
class RouteDiscoveryV2Result:
    result_id: str
    semantic_fingerprint: str
    upstream_dataset_id: str
    upstream_dataset_fingerprint: str
    upstream_semantic_result_id: str
    upstream_semantic_fingerprint: str
    semantic_profile_id: str
    semantic_profile_version: str
    semantic_profile_fingerprint: str
    route_engine_version: str
    route_config_id: str
    route_config_version: str
    route_config_fingerprint: str
    listing_count: int
    primary_cohort_eligible_count: int
    assigned_count: int
    unclassified_count: int
    review_required_count: int
    feature_views: tuple[SemanticRouteFeatureView, ...]
    memberships: tuple[RouteV2Membership, ...]
    routes: tuple[ProductRouteV2, ...]
    denominators: tuple[MetricDenominator, ...]
    references: tuple[ContractReference, ...]
    candidate_selection_status: CandidateSelectionStatus
    candidates: tuple[CandidateRouteV2, ...]
    diagnostics: tuple[tuple[str, Any], ...]
    contract_version: str = ROUTE_V2_RESULT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != ROUTE_V2_RESULT_CONTRACT_VERSION:
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "result version")
        if self.route_engine_version != ROUTE_V2_ENGINE_VERSION:
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "engine version")
        if self.listing_count != len(self.feature_views) or self.listing_count != len(self.memberships):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "listing grain mismatch")
        if self.listing_count != self.assigned_count + self.unclassified_count + self.review_required_count:
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "membership count invariant")
        view_refs = [item.listing_reference for item in self.feature_views]
        if len(view_refs) != len(set(view_refs)):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "duplicate feature view",
            )
        listing_refs = [item.listing_reference for item in self.memberships]
        if len(listing_refs) != len(set(listing_refs)):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "duplicate membership")
        if set(view_refs) != set(listing_refs):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "feature-view/membership grain mismatch",
            )
        view_by_listing = {
            item.listing_reference: item for item in self.feature_views
        }
        if any(
            membership.feature_view_id
            != view_by_listing[membership.listing_reference].view_id
            or membership.semantic_listing_result_id
            != view_by_listing[membership.listing_reference].semantic_listing_result_id
            for membership in self.memberships
        ):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "membership feature-view lineage mismatch",
            )
        actual_primary = sum(
            item.eligible_for_primary_cohort for item in self.feature_views
        )
        if self.primary_cohort_eligible_count != actual_primary:
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "primary cohort count mismatch",
            )
        actual_counts = {
            MembershipStatus.ASSIGNED: sum(
                item.status is MembershipStatus.ASSIGNED for item in self.memberships
            ),
            MembershipStatus.UNCLASSIFIED: sum(
                item.status is MembershipStatus.UNCLASSIFIED for item in self.memberships
            ),
            MembershipStatus.REVIEW_REQUIRED: sum(
                item.status is MembershipStatus.REVIEW_REQUIRED for item in self.memberships
            ),
        }
        if (
            self.assigned_count != actual_counts[MembershipStatus.ASSIGNED]
            or self.unclassified_count != actual_counts[MembershipStatus.UNCLASSIFIED]
            or self.review_required_count
            != actual_counts[MembershipStatus.REVIEW_REQUIRED]
        ):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "declared membership status counts mismatch",
            )
        if any(
            item.profile_fingerprint != self.semantic_profile_fingerprint
            or item.route_config_fingerprint != self.route_config_fingerprint
            for item in self.memberships
        ):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "membership authority lineage mismatch",
            )
        route_ids = {item.route_id for item in self.routes}
        if len(route_ids) != len(self.routes):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "duplicate route")
        if any(
            item.profile_fingerprint != self.semantic_profile_fingerprint
            or item.config_fingerprint != self.route_config_fingerprint
            for item in self.routes
        ):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "route authority lineage mismatch",
            )
        if any(
            item.status is MembershipStatus.ASSIGNED and item.primary_route_id not in route_ids
            for item in self.memberships
        ):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "unknown assigned route")
        assigned_by_route = {
            route_id: tuple(sorted((
                item for item in self.memberships
                if item.status is MembershipStatus.ASSIGNED
                and item.primary_route_id == route_id
            ), key=lambda item: item.listing_reference))
            for route_id in route_ids
        }
        for route in self.routes:
            expected = assigned_by_route[route.route_id]
            if route.member_listing_references != tuple(
                item.listing_reference for item in expected
            ) or route.membership_ids != tuple(
                item.membership_id for item in expected
            ):
                raise RouteDiscoveryV2Error(
                    "ROUTE_V2_CONTRACT_INVALID",
                    "assigned membership/route member mapping mismatch",
                )
        if any(item.route_id not in route_ids for item in self.candidates):
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_CONTRACT_INVALID", "candidate references unknown route",
            )
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "result fingerprint")
        if self.result_id != deterministic_id("route-discovery-v2-result", logical):
            raise RouteDiscoveryV2Error("ROUTE_V2_CONTRACT_INVALID", "result ID")

    def logical_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "upstream_dataset_id": self.upstream_dataset_id,
            "upstream_dataset_fingerprint": self.upstream_dataset_fingerprint,
            "upstream_semantic_result_id": self.upstream_semantic_result_id,
            "upstream_semantic_fingerprint": self.upstream_semantic_fingerprint,
            "semantic_profile_id": self.semantic_profile_id,
            "semantic_profile_version": self.semantic_profile_version,
            "semantic_profile_fingerprint": self.semantic_profile_fingerprint,
            "route_engine_version": self.route_engine_version,
            "route_config_id": self.route_config_id,
            "route_config_version": self.route_config_version,
            "route_config_fingerprint": self.route_config_fingerprint,
            "counts": {
                "listing": self.listing_count,
                "primary_cohort_eligible": self.primary_cohort_eligible_count,
                "assigned": self.assigned_count, "unclassified": self.unclassified_count,
                "review_required": self.review_required_count,
            },
            "feature_views": [item.to_dict() for item in self.feature_views],
            "memberships": [item.to_dict() for item in self.memberships],
            "routes": [item.to_dict() for item in self.routes],
            "denominators": [item.to_dict() for item in self.denominators],
            "references": [item.to_dict() for item in self.references],
            "candidate_selection_status": self.candidate_selection_status.value,
            "candidates": [item.to_dict() for item in self.candidates],
            "diagnostics": {key: value for key, value in self.diagnostics},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id, "semantic_fingerprint": self.semantic_fingerprint,
            **self.logical_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )


__all__ = (
    "CandidateRouteV2", "ProductRouteV2", "RouteDescriptor",
    "RouteDiscoveryV2Result", "RouteSemanticKey", "RouteV2Membership",
    "SemanticRouteFeature", "SemanticRouteFeatureView",
    "build_semantic_route_feature",
)
