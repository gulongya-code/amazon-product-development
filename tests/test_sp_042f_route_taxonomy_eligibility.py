from __future__ import annotations

from dataclasses import replace

import pytest

from amazon_product_intelligence.product_route_opportunity.models import MembershipStatus
from amazon_product_intelligence.route_discovery_v2 import (
    RouteDiscoveryV2Error,
    build_route_discovery_v2,
    load_route_discovery_v2_config,
    validate_route_v2_authority,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    CohortEligibilityState,
    EvidenceRelationshipState,
    RelationRole,
    UniversalSemanticRole,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from tests.test_route_discovery_v2 import (
    CONFIGS,
    PROFILES,
    _build,
    _dataset,
    _record,
)


def _definitions(result):
    return {
        tuple((key.dimension, key.values) for key in route.defining_features)
        for route in result.routes
    }


def _shower_semantic(records):
    dataset = _dataset(tuple(records))
    profile = load_category_semantic_profile(
        PROFILES / "shower_caddies.v1_1.json"
    )
    return dataset, profile, build_semantic_engine_v2_result(dataset, profile=profile)


def test_free_standing_surface_forms_share_one_canonical_route() -> None:
    records = tuple(
        _record(
            index,
            title="Freestanding Shower Caddy",
            detail=f"Mounting Type: {value}",
        )
        for index, value in enumerate(
            ("free standing", "freestanding", "floor standing") * 2,
            start=1,
        )
    )
    *_, result = _build(records)
    assert len(result.routes) == 1
    assert _definitions(result) == {
        (("installation_architecture", ("freestanding",)),)
    }


def test_tension_surface_forms_share_one_canonical_route() -> None:
    records = tuple(
        _record(
            index,
            title="Tension Pole Shower Caddy",
            detail=f"Mounting Type: {value}",
        )
        for index, value in enumerate(
            ("tension mount", "tension pole", "pole mount") * 2,
            start=1,
        )
    )
    *_, result = _build(records)
    assert len(result.routes) == 1
    assert _definitions(result) == {
        (("installation_architecture", ("tension_pole",)),)
    }


def test_portable_form_is_no_installation_not_freestanding() -> None:
    dataset, profile, semantic = _shower_semantic((
        _record(
            1,
            title="Portable Shower Caddy Basket with Handle",
            detail="Special Feature: Free Standing",
        ),
    ))
    listing = semantic.listings[0]
    installation_values = {
        fact.normalized_value
        for fact in listing.facts
        if fact.dimension == "installation_architecture"
    }
    form_values = {
        fact.normalized_value
        for fact in listing.facts
        if fact.dimension == "product_form"
    }
    assert installation_values == {"no_installation"}
    assert form_values == {"portable"}
    assert any(
        fact.dimension == "functional_feature"
        and fact.normalized_value == "free standing"
        for fact in listing.facts
    )
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    result = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )
    assert all(
        "freestanding" not in feature.defining_values
        for view in result.feature_views
        for feature in view.features
        if feature.dimension == "installation_architecture"
    )


def test_corner_shelf_and_recessed_niche_keep_distinct_product_forms() -> None:
    records = (
        *tuple(
            _record(
                index,
                title="Recessed Shower Niche Built In",
                detail="Mounting Type: Recessed",
            )
            for index in range(1, 4)
        ),
        *tuple(
            _record(
                index,
                title="Corner Shower Shelf Grout-In",
                detail="Mounting Type: Grout-In",
            )
            for index in range(4, 7)
        ),
    )
    *_, result = _build(records)
    assert len(result.routes) == 2
    assert _definitions(result) == {
        (("product_form", ("recessed_niche",)),),
        (("product_form", ("corner_shelf",)),),
    }


def test_missing_product_form_cannot_bridge_into_corner_shelf_route() -> None:
    records = (
        *tuple(
            _record(
                index,
                title="Corner Shower Shelf Grout-In",
                detail="Mounting Type: Grout-In",
            )
            for index in range(1, 4)
        ),
        _record(
            4,
            title="Shower Caddy",
            detail="Mounting Type: Wall Mount",
        ),
    )
    *_, result = _build(records)
    assert len(result.routes) == 1
    assert result.routes[0].member_count == 3
    generic = next(
        item for item in result.memberships
        if item.listing_reference == records[-1].asin
    )
    assert generic.status is MembershipStatus.UNCLASSIFIED
    assert generic.primary_route_id is None


@pytest.mark.parametrize(
    ("title", "expected_role"),
    (
        (
            "Replacement Basket Fits Corner Shower Caddy Only",
            RelationRole.REPLACEMENT,
        ),
        ("Snap-On Clip for Shower Shelf", RelationRole.ACCESSORY),
        (
            "Replacement Adhesive Pad Sticker for Shower Caddy",
            RelationRole.REPLACEMENT,
        ),
    ),
)
def test_components_are_not_primary_route_members(title, expected_role) -> None:
    *_, semantic, _, result = _build(tuple(
        _record(index, title=title, detail="Mounting Type: Wall Mount")
        for index in range(1, 4)
    ))
    assert all(
        listing.product_role.relation_role is expected_role
        for listing in semantic.listings
    )
    assert all(
        not listing.market_cohort_eligibility.eligible_for_primary_cohort
        and listing.market_cohort_eligibility.state in {
            CohortEligibilityState.NON_PRIMARY_EXCLUDED,
            CohortEligibilityState.OFF_TARGET_EXCLUDED,
        }
        for listing in semantic.listings
    )
    assert result.assigned_count == 0
    assert result.routes == ()
    assert all(
        membership.status is MembershipStatus.UNCLASSIFIED
        and membership.primary_route_id is None
        for membership in result.memberships
    )


@pytest.mark.parametrize(
    "feature",
    ("rust resistant", "durable", "waterproof", "lightweight"),
)
def test_non_attachment_special_features_cannot_enter_attachment_mechanism(
    feature: str,
) -> None:
    _, _, semantic = _shower_semantic((
        _record(
            1,
            title="Wall Mounted Shower Caddy",
            detail=f"Mounting Type: Wall Mount | Special Feature: {feature}",
        ),
    ))
    listing = semantic.listings[0]
    assert any(
        fact.dimension == "functional_feature"
        and fact.normalized_value == feature
        for fact in listing.facts
    )
    assert all(
        fact.normalized_value != feature
        for fact in listing.facts
        if fact.dimension == "attachment_mechanism"
    )


def test_expandable_remains_evidence_without_becoming_attachment() -> None:
    _, _, semantic = _shower_semantic((
        _record(
            1,
            title="Hanging Shower Caddy",
            detail="Mounting Type: Hanging Mount | Special Feature: Expandable",
        ),
    ))
    listing = semantic.listings[0]
    feature = next(
        fact for fact in listing.facts
        if fact.dimension == "functional_feature"
    )
    assert feature.normalized_value == "expandable"
    assert feature.evidence_ids
    assert all(
        fact.normalized_value != "expandable"
        for fact in listing.facts
        if fact.dimension == "attachment_mechanism"
    )


def test_secondary_features_do_not_fragment_portable_route() -> None:
    records = tuple(
        _record(
            index,
            title="Portable Mesh Shower Caddy Bag",
            detail=f"Special Feature: {feature}",
        )
        for index, feature in enumerate(
            ("quick dry", "foldable", "durable") * 2,
            start=1,
        )
    )
    *_, semantic, _, result = _build(records)
    assert len(result.routes) == 1
    assert result.routes[0].member_count == 6
    assert {
        key.dimension for key in result.routes[0].defining_features
    } == {"product_form"}
    assert {
        fact.normalized_value
        for listing in semantic.listings
        for fact in listing.facts
        if fact.dimension == "functional_feature"
    } == {"quick dry", "foldable", "durable"}


def test_marketing_phrase_cannot_author_installation_architecture() -> None:
    *_, semantic, _, result = _build(tuple(
        _record(index, title="Best Shower Caddy") for index in range(1, 4)
    ))
    assert all(
        not any(
            fact.dimension == "installation_architecture"
            for fact in listing.facts
        )
        for listing in semantic.listings
    )
    assert result.routes == ()
    assert result.unclassified_count == 3


def test_malformed_no_installation_fragment_fails_closed() -> None:
    *_, semantic, _, result = _build(tuple(
        _record(
            index,
            title="Shower Caddy",
            detail="Installation Type: No",
        )
        for index in range(1, 4)
    ))
    assert all(
        not any(
            fact.dimension == "installation_architecture"
            for fact in listing.facts
        )
        for listing in semantic.listings
    )
    assert result.routes == ()
    assert result.unclassified_count == 3


def test_conflicting_structured_and_title_architecture_remains_auditable() -> None:
    dataset, profile, semantic = _shower_semantic((
        _record(
            1,
            title="Hanging Shower Caddy over Shower Head",
            detail="Mounting Type: Wall Mount",
        ),
    ))
    listing = semantic.listings[0]
    relationship = next(
        item for item in listing.relationships
        if item.dimension == "installation_architecture"
    )
    facts = {
        fact.fact_id: fact
        for fact in listing.facts
        if fact.dimension == "installation_architecture"
    }
    assert relationship.state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
    assert {facts[fact_id].normalized_value for fact_id in relationship.fact_ids} == {
        "wall_mount", "hanging_mount",
    }
    assert len(relationship.evidence_ids) == 2
    assert set(relationship.evidence_ids) <= {
        evidence.evidence_id for evidence in listing.evidence
    }
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    result = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )
    assert result.memberships[0].status is MembershipStatus.REVIEW_REQUIRED
    assert result.memberships[0].primary_route_id is None


def test_route_authority_rejects_functional_feature_promotion() -> None:
    profile = load_category_semantic_profile(
        PROFILES / "shower_caddies.v1_1.json"
    )
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    invalid = replace(
        config,
        route_dimensions=("functional_feature",),
        promoted_secondary_dimensions=("functional_feature",),
        min_defining_dimensions=1,
    )
    with pytest.raises(RouteDiscoveryV2Error, match="cannot define a route"):
        validate_route_v2_authority(invalid, profile, "shower caddies")


def test_sp_042f_execution_is_deterministic() -> None:
    records = tuple(
        _record(
            index,
            title="Portable Mesh Shower Caddy Bag",
            detail="Special Feature: Quick Dry",
        )
        for index in range(1, 4)
    )
    dataset, profile, semantic, config, first = _build(records)
    replay_dataset = replace(
        dataset,
        imported_at="2035-01-01T00:00:00+00:00",
        records=tuple(reversed(dataset.records)),
    )
    replay_semantic = build_semantic_engine_v2_result(
        replay_dataset, profile=profile,
    )
    second = build_route_discovery_v2(
        replay_dataset, replay_semantic, profile=profile, config=config,
    )
    assert semantic.to_json() == replay_semantic.to_json()
    assert first.to_json() == second.to_json()


def test_all_category_authority_pairs_remain_isolated_and_valid() -> None:
    pairs = (
        ("air_fryers.v2.json", "air_fryer_accessories.v1_1.json"),
        ("dog_water_bottles.v2.json", "dog_water_bottles.v1_1.json"),
        ("food_storage_containers.v2.json", "food_storage_containers.v1_1.json"),
        ("shower_caddies.v2.json", "shower_caddies.v1_1.json"),
        ("vacuum_replacement_filters.v2.json", "vacuum_replacement_filters.v1_1.json"),
    )
    for config_name, profile_name in pairs:
        config = load_route_discovery_v2_config(CONFIGS / config_name)
        profile = load_category_semantic_profile(PROFILES / profile_name)
        validate_route_v2_authority(config, profile, config.category)
        assert all(
            other_name == config_name
            or not profile.supports_category(
                load_route_discovery_v2_config(CONFIGS / other_name).category
            )
            for other_name, _ in pairs
        )


def test_special_feature_evidence_preserves_provenance_without_raw_title_leak() -> None:
    _, _, semantic = _shower_semantic((
        _record(
            1,
            title="Synthetic Private-Like Shower Caddy Title",
            detail="Special Feature: Expandable",
        ),
    ))
    listing = semantic.listings[0]
    feature = next(
        fact for fact in listing.facts
        if fact.role is UniversalSemanticRole.FUNCTIONAL_FEATURE
    )
    evidence = next(
        item for item in listing.evidence
        if item.evidence_id in feature.evidence_ids
    )
    assert evidence.source_key == "special feature"
    assert evidence.source_content_fingerprint
    assert evidence.upstream_record_fingerprint == listing.upstream_record_fingerprint
    assert "synthetic private-like shower caddy title" not in semantic.to_json().casefold()
