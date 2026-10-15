from __future__ import annotations

import pytest

from amazon_product_intelligence.product_route_opportunity.models import (
    MembershipStatus,
)
from amazon_product_intelligence.route_discovery_v2 import (
    build_route_discovery_v2,
    build_semantic_route_feature_views,
    load_route_discovery_v2_config,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    CohortEligibilityState,
    EvidenceRelationshipState,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from tests.test_route_discovery_v2 import CONFIGS, PROFILES, _dataset, _record


PORTABLE_INSTALLATION_RULE = "shower-install-none-title"
GENERIC_WALL_RULE = "shower-install-wall-generic-structured"
RECESSED_TITLE_RULE = "shower-install-recessed-title"


def _build(*records):
    dataset = _dataset(tuple(records))
    profile = load_category_semantic_profile(
        PROFILES / "shower_caddies.v1_1.json"
    )
    semantic = build_semantic_engine_v2_result(dataset, profile=profile)
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    route = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )
    return dataset, profile, semantic, config, route


def _facts(listing, dimension: str):
    return tuple(
        fact for fact in listing.facts if fact.dimension == dimension
    )


def _relationship(listing, dimension: str):
    return next(
        item for item in listing.relationships if item.dimension == dimension
    )


def test_portable_title_is_product_form_evidence_not_no_installation() -> None:
    _, _, semantic, _, route = _build(*(
        _record(
            index,
            title="Mesh Shower Caddy Portable Shower Bag",
            detail="Mounting Type: Hanging Mount",
        )
        for index in range(1, 4)
    ))

    for listing in semantic.listings:
        assert {
            fact.normalized_value
            for fact in _facts(listing, "installation_architecture")
        } == {"hanging_mount"}
        assert {
            fact.normalized_value for fact in _facts(listing, "product_form")
        } == {"portable"}
        assert any(
            evidence.profile_rule_id == PORTABLE_INSTALLATION_RULE
            for evidence in listing.evidence
        )
        assert (
            f"EVIDENCE_ONLY_UNRESOLVED:{PORTABLE_INSTALLATION_RULE}"
            in listing.limitations
        )

    assert all(
        membership.status is MembershipStatus.ASSIGNED
        for membership in route.memberships
    )


def test_explicit_structured_no_installation_remains_authoritative() -> None:
    _, _, semantic, _, _ = _build(_record(
        1,
        title="Portable Mesh Shower Caddy Bag",
        detail="Installation Type: No Installation Required",
    ))

    listing = semantic.listings[0]
    assert {
        fact.normalized_value
        for fact in _facts(listing, "installation_architecture")
    } == {"no_installation"}
    assert any(
        fact.rule_id == "shower-install-none-structured"
        for fact in _facts(listing, "installation_architecture")
    )


def test_explicit_recessed_title_resolves_unqualified_generic_wall_mount() -> None:
    dataset, profile, semantic, config, route = _build(*(
        _record(
            index,
            title="Recessed Shower Niche with Built-in Shower Shelf",
            detail="Mounting Type: Wall Mount",
        )
        for index in range(1, 4)
    ))

    for listing in semantic.listings:
        relationship = _relationship(listing, "installation_architecture")
        assert (
            relationship.state
            is EvidenceRelationshipState.RESOLVED_BY_GOVERNED_PRECEDENCE
        )
        assert set(relationship.profile_rule_ids) >= {
            GENERIC_WALL_RULE,
            RECESSED_TITLE_RULE,
        }
        assert set(relationship.reason_codes) >= {
            "PROFILE_GOVERNED_FACT_AUTHORITY_PRECEDENCE",
            RECESSED_TITLE_RULE,
        }
        assert listing.market_cohort_eligibility.state is (
            CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE
        )
        assert {
            fact.normalized_value
            for fact in _facts(listing, "installation_architecture")
        } == {"recessed_or_builtin", "wall_mount"}

    views = build_semantic_route_feature_views(
        dataset, semantic, profile=profile, config=config,
    )
    for view in views:
        feature = view.feature("installation_architecture")
        assert feature is not None
        assert set(feature.values) == {"recessed_or_builtin", "wall_mount"}
        assert feature.defining_values == ("recessed_or_builtin",)
        assert len(feature.fact_ids) == 2
        assert len(feature.evidence_ids) == 2

    assert all(
        membership.status is MembershipStatus.ASSIGNED
        for membership in route.memberships
    )


@pytest.mark.parametrize(
    "detail",
    (
        "Mounting Type: Wall Mount | Attachment Type: Adhesive",
        "Mounting Type: Wall Mount | Attachment Type: Suction Cup",
        "Mounting Type: Wall Mount | Attachment Type: Screw Mounted",
        "Mounting Type: Wall Mount, Hanging Mount",
        "Mounting Type: Wall Mount, Tension Mount",
        "Mounting Type: Wall Mount | Installation Method: Tabletop Mount",
    ),
)
def test_recessed_precedence_is_blocked_by_specific_conflicting_evidence(
    detail: str,
) -> None:
    _, _, semantic, _, route = _build(_record(
        1,
        title="Recessed Shower Niche",
        detail=detail,
    ))

    listing = semantic.listings[0]
    relationship = _relationship(listing, "installation_architecture")
    assert relationship.state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
    assert listing.market_cohort_eligibility.state is (
        CohortEligibilityState.REVIEW_REQUIRED
    )
    assert route.memberships[0].status is MembershipStatus.REVIEW_REQUIRED


@pytest.mark.parametrize(
    "title",
    (
        "Hanging Shower Caddy with Built-in Hooks",
        "Hanging Shower Caddy with Built-in Soap Dish",
        "Hanging Shower Caddy with Built-in Towel Bar",
        "Hanging Shower Caddy with Built-in Razor Hanger",
    ),
)
def test_built_in_component_language_does_not_author_recessed_architecture(
    title: str,
) -> None:
    _, _, semantic, _, _ = _build(_record(
        1,
        title=title,
        detail="Mounting Type: Hanging Mount",
    ))

    listing = semantic.listings[0]
    assert {
        fact.normalized_value
        for fact in _facts(listing, "installation_architecture")
    } == {"hanging_mount"}
    assert all(
        fact.rule_id != RECESSED_TITLE_RULE
        for fact in _facts(listing, "installation_architecture")
    )


def test_built_in_architectural_context_still_authors_recessed_architecture() -> None:
    _, _, semantic, _, _ = _build(_record(
        1,
        title="Built-in Shower Shelf and Shower Niche",
        detail="Mounting Type: Wall Mount",
    ))

    listing = semantic.listings[0]
    assert any(
        fact.rule_id == RECESSED_TITLE_RULE
        and fact.normalized_value == "recessed_or_builtin"
        for fact in _facts(listing, "installation_architecture")
    )
    assert _relationship(
        listing, "installation_architecture",
    ).state is EvidenceRelationshipState.RESOLVED_BY_GOVERNED_PRECEDENCE


def test_portable_special_feature_does_not_override_corner_shelf_form() -> None:
    _, _, semantic, _, route = _build(*(
        _record(
            index,
            title="Corner Shower Shelves Adhesive Shower Caddy",
            detail="Special Feature: Portable, Rust Resistant",
        )
        for index in range(1, 4)
    ))

    for listing in semantic.listings:
        assert {
            fact.normalized_value for fact in _facts(listing, "product_form")
        } == {"corner_shelf"}
        assert any(
            fact.dimension == "functional_feature"
            and "portable" in str(fact.normalized_value)
            for fact in listing.facts
        )
        assert _relationship(
            listing, "product_form",
        ).state is EvidenceRelationshipState.SOURCE_ONLY_TITLE

    assert all(
        membership.status is MembershipStatus.ASSIGNED
        for membership in route.memberships
    )


def test_explicit_structured_portable_product_form_remains_authoritative() -> None:
    _, _, semantic, _, _ = _build(_record(
        1,
        title="Shower Caddy Organizer",
        detail="Product Type: Portable",
    ))

    listing = semantic.listings[0]
    assert {
        fact.normalized_value for fact in _facts(listing, "product_form")
    } == {"portable"}
    assert any(
        fact.rule_id == "shower-form-portable-structured"
        for fact in _facts(listing, "product_form")
    )
