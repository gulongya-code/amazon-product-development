from __future__ import annotations

from dataclasses import replace

import pytest

from amazon_product_intelligence.product_route_opportunity.models import MembershipStatus
from amazon_product_intelligence.route_discovery_v2 import (
    build_route_discovery_v2,
    load_route_discovery_v2_config,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    CohortEligibilityState,
    RelationRole,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from tests.test_route_discovery_v2 import CONFIGS, PROFILES, _build, _dataset, _record


def _semantic(*records):
    dataset = _dataset(tuple(records))
    profile = load_category_semantic_profile(
        PROFILES / "shower_caddies.v1_1.json"
    )
    result = build_semantic_engine_v2_result(dataset, profile=profile)
    return dataset, profile, result


def _values(listing, dimension: str) -> set[str]:
    return {
        fact.normalized_value
        for fact in listing.facts
        if fact.dimension == dimension
    }


@pytest.mark.parametrize(
    "title",
    (
        "Portable Storage Shower Caddy Tote Basket with Handle",
        "Plastic Shower Caddy Portable Basket with Handle",
    ),
)
def test_portable_basket_with_handle_is_not_freestanding(title: str) -> None:
    _, _, semantic = _semantic(_record(
        1,
        title=title,
        detail=(
            "Mounting Type: Freestanding | Special Feature: Portable, Quick Dry"
        ),
    ))
    listing = semantic.listings[0]

    assert _values(listing, "product_form") == {"portable"}
    assert _values(listing, "installation_architecture") == {"no_installation"}
    assert "freestanding" not in _values(listing, "installation_architecture")
    assert any(
        evidence.profile_rule_id
        == "shower-install-freestanding-ambiguous-structured"
        for evidence in listing.evidence
    )


def test_true_floor_standing_organizer_remains_freestanding() -> None:
    _, _, semantic = _semantic(_record(
        1,
        title="Floor Standing Shower Organizer with Four Tiers",
        detail="Mounting Type: Floor Standing",
    ))
    listing = semantic.listings[0]

    assert _values(listing, "installation_architecture") == {"freestanding"}
    assert "portable" not in _values(listing, "product_form")


def test_no_installation_does_not_imply_freestanding() -> None:
    _, _, semantic = _semantic(_record(
        1,
        title="Portable Mesh Shower Caddy Bag",
        detail="Installation Type: No Installation Required",
    ))
    installation = _values(semantic.listings[0], "installation_architecture")

    assert installation == {"no_installation"}
    assert "freestanding" not in installation


def test_structured_portable_form_is_visible_but_not_route_authority() -> None:
    dataset, profile, semantic = _semantic(_record(
        1,
        title="Bath Storage Shower Organizer for Dorm and Gym",
        detail="Mounting Type: Freestanding | Special Feature: Portable",
    ))
    listing = semantic.listings[0]

    assert _values(listing, "product_form") == {"portable"}
    assert _values(listing, "installation_architecture") == set()
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    route_result = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )
    form = route_result.feature_views[0].feature("product_form")
    assert form is not None
    assert form.values == ("portable",)
    assert form.defining_values == ()
    assert route_result.memberships[0].status is MembershipStatus.UNCLASSIFIED


@pytest.mark.parametrize(
    "installation",
    ("Recessed", "Built-In", "Grout-In"),
)
def test_explicit_recessed_evidence_supports_canonical_installation(
    installation: str,
) -> None:
    _, _, semantic = _semantic(_record(
        1,
        title="Corner Shower Shelf",
        detail=f"Mounting Type: {installation}",
    ))

    assert _values(
        semantic.listings[0], "installation_architecture"
    ) == {"recessed_or_builtin"}


def test_tiled_wall_and_insert_mount_cannot_establish_recessed_route() -> None:
    records = (
        *tuple(
            _record(
                index,
                title="Recessed Corner Shower Shelf Grout-In",
                detail="Mounting Type: Recessed",
            )
            for index in range(1, 4)
        ),
        *tuple(
            _record(
                index,
                title="Wall Mounted Corner Shower Shelf",
                detail="Mounting Type: Wall Mount",
            )
            for index in range(4, 7)
        ),
        _record(
            7,
            title="Corner Shower Shelf for Tiled Wall",
            detail="Mounting Type: Insert Mount",
        ),
    )
    *_, semantic, _, route_result = _build(records)
    ambiguous_listing = next(
        item for item in semantic.listings
        if item.listing_reference == records[-1].asin
    )
    ambiguous_membership = next(
        item for item in route_result.memberships
        if item.listing_reference == records[-1].asin
    )

    assert _values(ambiguous_listing, "product_form") == {"corner_shelf"}
    assert _values(ambiguous_listing, "installation_architecture") == set()
    assert ambiguous_membership.status is MembershipStatus.UNCLASSIFIED
    assert ambiguous_membership.primary_route_id is None
    assert all(
        ambiguous_listing.listing_reference not in route.member_listing_references
        for route in route_result.routes
        if any(
            key.dimension == "installation_architecture"
            and key.values == ("recessed_or_builtin",)
            for key in route.defining_features
        )
    )


def test_ambiguous_installation_evidence_is_preserved_and_fails_closed() -> None:
    _, _, semantic = _semantic(_record(
        1,
        title="Corner Shower Shelf for Tiled Wall",
        detail="Mounting Type: Insert Mount",
    ))
    listing = semantic.listings[0]

    assert _values(listing, "installation_architecture") == set()
    assert any(
        evidence.profile_rule_id
        == "shower-install-insert-mount-ambiguous-structured"
        and evidence.source_key == "installation"
        for evidence in listing.evidence
    )
    assert (
        "EVIDENCE_ONLY_UNRESOLVED:"
        "shower-install-insert-mount-ambiguous-structured"
    ) in listing.limitations


@pytest.mark.parametrize(
    ("title", "detail", "dimension", "expected"),
    (
        (
            "Wall Mounted Shower Caddy",
            "Mounting Type: Wall Mount",
            "installation_architecture",
            "wall_mount",
        ),
        (
            "Hanging Shower Caddy over Showerhead",
            "Mounting Type: Hanging Mount",
            "installation_architecture",
            "hanging_mount",
        ),
        (
            "Tension Pole Shower Caddy",
            "Mounting Type: Pole Mount",
            "installation_architecture",
            "tension_pole",
        ),
        (
            "Suction Cup Shower Caddy",
            "Mounting Type: Wall Mount | Attachment Type: Suction Cup",
            "attachment_mechanism",
            "suction_cup",
        ),
        (
            "Adhesive Shower Caddy",
            "Mounting Type: Wall Mount | Attachment Type: Adhesive",
            "attachment_mechanism",
            "adhesive",
        ),
        (
            "Portable Shower Caddy Basket",
            "Special Feature: Portable",
            "product_form",
            "portable",
        ),
    ),
)
def test_sp_042f_canonicalization_remains_intact(
    title: str, detail: str, dimension: str, expected: str,
) -> None:
    _, _, semantic = _semantic(_record(1, title=title, detail=detail))

    assert expected in _values(semantic.listings[0], dimension)


def test_accessory_isolation_remains_intact() -> None:
    *_, semantic, _, route_result = _build(tuple(
        _record(
            index,
            title="Replacement Adhesive Pad for Shower Caddy",
            detail="Attachment Type: Adhesive",
        )
        for index in range(1, 4)
    ))

    assert all(
        item.product_role.relation_role is RelationRole.REPLACEMENT
        and item.market_cohort_eligibility.state
        in {
            CohortEligibilityState.NON_PRIMARY_EXCLUDED,
            CohortEligibilityState.OFF_TARGET_EXCLUDED,
        }
        for item in semantic.listings
    )
    assert route_result.routes == ()
    assert route_result.assigned_count == 0


def test_sp_042g_repeated_and_reversed_execution_is_deterministic() -> None:
    records = (
        *tuple(
            _record(
                index,
                title="Portable Shower Caddy Basket with Handle",
                detail="Mounting Type: Freestanding | Special Feature: Portable",
            )
            for index in range(1, 4)
        ),
        *tuple(
            _record(
                index,
                title="Floor Standing Shower Organizer",
                detail="Mounting Type: Floor Standing",
            )
            for index in range(4, 7)
        ),
        *tuple(
            _record(
                index,
                title="Recessed Corner Shower Shelf Grout-In",
                detail="Mounting Type: Recessed",
            )
            for index in range(7, 10)
        ),
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
