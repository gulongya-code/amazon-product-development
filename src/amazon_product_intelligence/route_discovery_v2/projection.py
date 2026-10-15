"""Project accepted S2 output into profile-authorized route semantics."""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.market_report.v0_2.models.common import Availability
from amazon_product_intelligence.sellersprite_import.models import GovernedMarketDatasetV1
from amazon_product_intelligence.semantic_engine_v2.models import (
    EvidenceRelationshipState,
    ListingSemanticResult,
    SemanticDecisionStatus,
    SemanticEngineV2Result,
)
from amazon_product_intelligence.semantic_engine_v2.profile import (
    CategorySemanticProfileV1_1,
    RouteDimensionPrecedencePolicy,
    SourcePolicy,
)

from .config import RouteDiscoveryV2Config, validate_route_v2_authority
from .errors import RouteDiscoveryV2Error
from .models import (
    SemanticRouteFeature,
    SemanticRouteFeatureView,
    build_semantic_route_feature,
)


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _feature(
    listing: ListingSemanticResult,
    *,
    policy: SourcePolicy,
    profile: CategorySemanticProfileV1_1,
    route_precedence_policies: tuple[RouteDimensionPrecedencePolicy, ...],
) -> SemanticRouteFeature | None:
    facts = tuple(sorted((
        item for item in listing.facts
        if item.dimension == policy.dimension
        and item.availability is not Availability.UNAVAILABLE
    ), key=lambda item: item.fact_id))
    if not facts:
        return None
    relationships = tuple(sorted((
        item for item in listing.relationships if item.dimension == policy.dimension
    ), key=lambda item: item.relationship_id))
    precedence_resolved = any(
        item.state is EvidenceRelationshipState.RESOLVED_BY_GOVERNED_PRECEDENCE
        for item in relationships
    )
    authoritative_facts = facts
    if precedence_resolved:
        dimension_rule_ids = tuple(item.rule_id for item in facts)
        all_rule_ids = tuple((
            *(item.rule_id for item in listing.facts),
            *(item.profile_rule_id for item in listing.evidence),
        ))
        priorities = {
            item.fact_id: profile.fact_authority_priority(
                item.rule_id,
                dimension_rule_ids=dimension_rule_ids,
                all_rule_ids=all_rule_ids,
            )
            for item in facts
        }
        minimum = min(priorities.values())
        authoritative_facts = tuple(
            item for item in facts if priorities[item.fact_id] == minimum
        )
    primary = tuple(
        item for item in authoritative_facts
        if set(item.source_classes) & set(policy.primary_sources)
    )
    fallback = tuple(
        item for item in authoritative_facts
        if set(item.source_classes) & set(policy.fallback_sources)
    )
    # Corroborating-only signals remain visible but cannot manufacture an
    # architecture value.  A governed fallback is used only when primary facts
    # are genuinely absent.
    defining = primary or fallback
    limitations = {
        limitation for item in facts for limitation in item.limitations
    }
    for route_policy in route_precedence_policies:
        if policy.dimension not in route_policy.nondefining_dimensions:
            continue
        preserved_rule_ids = set(route_policy.preserved_fact_rule_ids)
        retained = tuple(
            item for item in defining if item.rule_id in preserved_rule_ids
        )
        if retained != defining:
            defining = retained
            limitations.add(
                "PROFILE_GOVERNED_ROUTE_DIMENSION_PRECEDENCE:"
                f"{route_policy.policy_id}"
            )
    if not defining:
        limitations.add("CORROBORATING_ONLY_NOT_ROUTE_DEFINING")
    if precedence_resolved:
        limitations.add("PROFILE_GOVERNED_FACT_AUTHORITY_PRECEDENCE_APPLIED")
    if any(item.state is EvidenceRelationshipState.TRUE_CONFLICT for item in relationships):
        limitations.add("TRUE_CONFLICT_PRESERVED")
    if any(
        item.state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
        for item in relationships
    ):
        limitations.add("ROUTE_CRITICAL_CONFLICT_PRESERVED")
    return build_semantic_route_feature(
        role=policy.role,
        dimension=policy.dimension,
        values=tuple(item.normalized_value for item in facts),
        defining_values=tuple(item.normalized_value for item in defining),
        profile_id=profile.profile_id,
        profile_version=profile.version,
        profile_fingerprint=profile.fingerprint,
        source_policy_id=policy.policy_id,
        relevance=policy.relevance,
        route_critical=policy.route_critical,
        exact_specification=policy.exact_specification,
        multi_value=policy.multi_value,
        fact_ids=tuple(item.fact_id for item in facts),
        defining_fact_ids=tuple(item.fact_id for item in defining),
        evidence_ids=tuple({
            evidence_id for item in facts for evidence_id in item.evidence_ids
        }),
        relationship_ids=tuple(item.relationship_id for item in relationships),
        relationship_states=tuple(item.state.value for item in relationships),
        limitations=tuple(limitations),
    )


def _route_precedence_policy_applies(
    listing: ListingSemanticResult,
    policy: RouteDimensionPrecedencePolicy,
) -> bool:
    """Require governed identity, role, fact, and a non-conflicting relationship."""

    identity = listing.product_identity
    product_role = listing.product_role
    if (
        identity.status is not SemanticDecisionStatus.GOVERNED
        or identity.is_target_identity is not True
        or identity.normalized_identity not in policy.trigger_product_identities
        or product_role.relation_status is not SemanticDecisionStatus.GOVERNED
        or product_role.relation_role not in policy.trigger_relation_roles
    ):
        return False
    trigger_facts = tuple(
        item for item in listing.facts
        if item.dimension == policy.trigger_dimension
        and item.availability is not Availability.UNAVAILABLE
        and isinstance(item.normalized_value, str)
        and item.normalized_value.casefold() in policy.trigger_values
    )
    if not trigger_facts:
        return False
    relationship = next((
        item for item in listing.relationships
        if item.dimension == policy.trigger_dimension
    ), None)
    return relationship is not None and relationship.state not in {
        EvidenceRelationshipState.TRUE_CONFLICT,
        EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT,
        EvidenceRelationshipState.UNAVAILABLE,
    }


def _view(
    listing: ListingSemanticResult,
    *,
    policies: tuple[SourcePolicy, ...],
    profile: CategorySemanticProfileV1_1,
) -> SemanticRouteFeatureView:
    route_precedence_policies = tuple(
        item for item in profile.route_dimension_precedence_policies
        if _route_precedence_policy_applies(listing, item)
    )
    features = tuple(sorted((
        feature for policy in policies
        if (
            feature := _feature(
                listing,
                policy=policy,
                profile=profile,
                route_precedence_policies=route_precedence_policies,
            )
        ) is not None
    ), key=lambda item: (item.role.value, item.dimension)))
    limitations = set(listing.limitations)
    if not listing.market_cohort_eligibility.eligible_for_primary_cohort:
        limitations.add("OUTSIDE_PRIMARY_ONLY_DISCOVERY_COHORT")
    logical = {
        "listing_reference": listing.listing_reference,
        "upstream_record_fingerprint": listing.upstream_record_fingerprint,
        "semantic_listing_result_id": listing.listing_result_id,
        "semantic_listing_fingerprint": listing.semantic_fingerprint,
        "cohort_state": listing.market_cohort_eligibility.state.value,
        "eligible_for_primary_cohort": (
            listing.market_cohort_eligibility.eligible_for_primary_cohort
        ),
        "features": [item.to_dict() for item in features],
        "review_reason_codes": sorted(listing.review_reason_codes),
        "limitations": sorted(limitations),
    }
    return SemanticRouteFeatureView(
        view_id=deterministic_id("semantic-route-feature-view-v2", logical),
        semantic_fingerprint=_hash(logical),
        listing_reference=listing.listing_reference,
        upstream_record_fingerprint=listing.upstream_record_fingerprint,
        semantic_listing_result_id=listing.listing_result_id,
        semantic_listing_fingerprint=listing.semantic_fingerprint,
        cohort_state=listing.market_cohort_eligibility.state,
        eligible_for_primary_cohort=(
            listing.market_cohort_eligibility.eligible_for_primary_cohort
        ),
        features=features,
        review_reason_codes=tuple(sorted(listing.review_reason_codes)),
        limitations=tuple(sorted(limitations)),
    )


def build_semantic_route_feature_views(
    dataset: GovernedMarketDatasetV1,
    semantic_result: SemanticEngineV2Result,
    *,
    profile: CategorySemanticProfileV1_1,
    config: RouteDiscoveryV2Config,
) -> tuple[SemanticRouteFeatureView, ...]:
    """Join B/S2 exactly and expose only configured profile-governed dimensions."""

    validate_route_v2_authority(config, profile, dataset.category)
    if semantic_result.upstream_dataset_id != dataset.dataset_id:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_UPSTREAM_ID_MISMATCH", "S2 result references a different dataset",
        )
    if semantic_result.upstream_dataset_fingerprint != dataset.semantic_fingerprint:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_UPSTREAM_FINGERPRINT_MISMATCH",
            "S2 result fingerprint link is invalid",
        )
    if (
        semantic_result.profile_id != profile.profile_id
        or semantic_result.profile_version != profile.version
        or semantic_result.profile_fingerprint != profile.fingerprint
    ):
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_PROFILE_LINEAGE_MISMATCH", "S2/profile lineage differs",
        )
    records = {item.asin: item for item in dataset.records}
    semantics = {item.listing_reference: item for item in semantic_result.listings}
    if set(records) != set(semantics):
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_LISTING_GRAIN_MISMATCH", "SP-041B and S2 listing sets differ",
        )
    if any(
        semantics[asin].upstream_record_fingerprint != record.record_fingerprint
        for asin, record in records.items()
    ):
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_LISTING_FINGERPRINT_MISMATCH",
            "S2 listing does not reference the governed record",
        )
    dimensions = tuple(dict.fromkeys((
        *config.route_dimensions,
        *config.descriptor_dimensions,
        *config.adoption_dimensions,
    )))
    policies = tuple(profile.source_policy(dimension) for dimension in dimensions)
    return tuple(
        _view(semantics[asin], policies=policies, profile=profile)
        for asin in sorted(records)
    )


__all__ = ("build_semantic_route_feature_views",)
