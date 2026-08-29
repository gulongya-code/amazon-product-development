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
    SemanticEngineV2Result,
)
from amazon_product_intelligence.semantic_engine_v2.profile import (
    CategorySemanticProfileV1_1,
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
    primary = tuple(
        item for item in facts if set(item.source_classes) & set(policy.primary_sources)
    )
    fallback = tuple(
        item for item in facts if set(item.source_classes) & set(policy.fallback_sources)
    )
    # Corroborating-only signals remain visible but cannot manufacture an
    # architecture value.  A governed fallback is used only when primary facts
    # are genuinely absent.
    defining = primary or fallback
    limitations = {
        limitation for item in facts for limitation in item.limitations
    }
    if not defining:
        limitations.add("CORROBORATING_ONLY_NOT_ROUTE_DEFINING")
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


def _view(
    listing: ListingSemanticResult,
    *,
    policies: tuple[SourcePolicy, ...],
    profile: CategorySemanticProfileV1_1,
) -> SemanticRouteFeatureView:
    features = tuple(sorted((
        feature for policy in policies
        if (feature := _feature(listing, policy=policy, profile=profile)) is not None
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
