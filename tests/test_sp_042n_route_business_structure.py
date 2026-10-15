from __future__ import annotations

import re

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
    RelationRole,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from tests.test_route_discovery_v2 import CONFIGS, PROFILES, _dataset, _record


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


def _definition(route):
    return {
        item.dimension: tuple(item.values) for item in route.defining_features
    }


def test_wall_parent_is_not_published_when_specific_children_explain_members() -> None:
    _, _, _, _, route = _build(*(
        *(
            _record(
                index,
                title="Adhesive Shower Caddy",
                detail="Mounting Type: Wall Mount | Attachment Type: Adhesive",
            )
            for index in range(1, 4)
        ),
        *(
            _record(
                index,
                title="Suction Cup Shower Caddy",
                detail="Mounting Type: Wall Mount | Attachment Type: Suction Cup",
            )
            for index in range(4, 7)
        ),
    ))

    assert len(route.routes) == 2
    assert all("attachment_mechanism" in _definition(item) for item in route.routes)
    assert not any(
        _definition(item) == {"installation_architecture": ("wall_mount",)}
        for item in route.routes
    )
    member_sets = [set(item.member_listing_references) for item in route.routes]
    assert not member_sets[0] & member_sets[1]
    assert sum(item.member_count for item in route.routes) == route.assigned_count


def test_residual_wall_route_is_explicitly_labeled_unspecified() -> None:
    _, _, _, _, route = _build(*(
        _record(
            index,
            title="Shower Caddy Organizer",
            detail="Mounting Type: Wall Mount",
        )
        for index in range(1, 4)
    ))

    assert len(route.routes) == 1
    result = route.routes[0]
    assert _definition(result) == {
        "installation_architecture": ("wall_mount",),
    }
    assert "wall_mount_unspecified" in result.label
    assert "attachment_mechanism" not in result.label


def test_recessed_architecture_remains_independent_from_wall_hierarchy() -> None:
    _, _, semantic, _, route = _build(*(
        *(
            _record(
                index,
                title="Recessed Shower Niche with Built-in Shower Shelf",
                detail="Mounting Type: Wall Mount",
            )
            for index in range(1, 4)
        ),
        *(
            _record(
                index,
                title="Adhesive Shower Caddy",
                detail="Mounting Type: Wall Mount | Attachment Type: Adhesive",
            )
            for index in range(4, 7)
        ),
    ))

    definitions = tuple(_definition(item) for item in route.routes)
    assert any(
        item.get("installation_architecture") == ("recessed_or_builtin",)
        or item.get("product_form") == ("recessed_niche",)
        for item in definitions
    )
    assert any(
        fact.dimension == "attachment_mechanism"
        and fact.normalized_value == "adhesive"
        for listing in semantic.listings
        for fact in listing.facts
    )
    assert sum(item.member_count for item in route.routes) == route.assigned_count


def test_confirmed_accessory_phrase_class_isolated_before_primary_assignment() -> None:
    title = "Shower Caddy Adhesive, Strong Adhesive Hooks Set"
    _, _, semantic, _, route = _build(_record(
        1,
        title=title,
        detail="Mounting Type: Wall Mount",
    ))

    listing = semantic.listings[0]
    assert listing.product_identity.normalized_identity == "shower caddy component"
    assert listing.product_identity.is_target_identity is False
    assert listing.product_role.relation_role is RelationRole.ACCESSORY
    assert listing.market_cohort_eligibility.state is (
        CohortEligibilityState.OFF_TARGET_EXCLUDED
    )
    assert route.memberships[0].status is MembershipStatus.UNCLASSIFIED
    assert route.memberships[0].primary_route_id is None
    assert {
        fact.rule_id for fact in listing.facts
        if fact.dimension in {"product_identity", "relation_role"}
    } >= {"shower-identity-component", "shower-relation-accessory"}
    assert {
        evidence.profile_rule_id for evidence in listing.evidence
    } >= {"shower-identity-component", "shower-relation-accessory"}


def test_accessory_correction_is_generic_and_preserves_real_primary_caddies() -> None:
    _, _, semantic, _, route = _build(
        _record(
            1,
            title="Shower Caddy Adhesive Strong Adhesive Hooks, 8 Pack",
            detail="Mounting Type: Wall Mount",
        ),
        *(
            _record(
                index,
                title="Adhesive Shower Caddy with Soap Holder and Hooks",
                detail="Mounting Type: Wall Mount | Attachment Type: Adhesive",
            )
            for index in range(2, 5)
        ),
    )

    accessory, *primaries = semantic.listings
    assert accessory.product_role.relation_role is RelationRole.ACCESSORY
    assert all(
        item.product_role.relation_role is RelationRole.PRIMARY_PRODUCT
        and item.market_cohort_eligibility.eligible_for_primary_cohort
        for item in primaries
    )
    memberships = {
        item.listing_reference: item for item in route.memberships
    }
    assert memberships[accessory.listing_reference].status is (
        MembershipStatus.UNCLASSIFIED
    )
    assert all(
        memberships[item.listing_reference].status is MembershipStatus.ASSIGNED
        for item in primaries
    )


def test_portable_identity_consolidates_incidental_installation_route_splits() -> None:
    records = (
        *(
            _record(
                index,
                title="Portable Shower Caddy Tote Basket",
                detail="Mounting Type: Hanging Mount",
            )
            for index in range(1, 4)
        ),
        *(
            _record(
                index,
                title="Portable Shower Caddy Basket",
                detail="Mounting Type: Wall Mount",
            )
            for index in range(4, 7)
        ),
        *(
            _record(index, title="Portable Shower Caddy Tote")
            for index in range(7, 10)
        ),
    )
    dataset, profile, semantic, config, route = _build(*records)

    assert len(route.routes) == 1
    assert _definition(route.routes[0]) == {"product_form": ("portable",)}
    assert route.routes[0].member_count == 9
    assert all(
        item.status is MembershipStatus.ASSIGNED for item in route.memberships
    )

    views = build_semantic_route_feature_views(
        dataset, semantic, profile=profile, config=config,
    )
    incidental = tuple(
        view for view in views
        if view.feature("installation_architecture") is not None
    )
    assert len(incidental) == 6
    for view in incidental:
        installation = view.feature("installation_architecture")
        assert installation is not None
        assert installation.values
        assert installation.defining_values == ()
        assert any(
            item.startswith("PROFILE_GOVERNED_ROUTE_DIMENSION_PRECEDENCE:")
            for item in installation.limitations
        )


def test_portable_precedence_does_not_collapse_true_hanging_or_wall_products() -> None:
    _, _, semantic, _, route = _build(*(
        *(
            _record(
                index,
                title="Hanging Shower Caddy over Shower Head",
                detail="Mounting Type: Hanging Mount",
            )
            for index in range(1, 4)
        ),
        *(
            _record(
                index,
                title="Adhesive Wall Mounted Shower Shelf",
                detail="Mounting Type: Wall Mount | Attachment Type: Adhesive",
            )
            for index in range(4, 7)
        ),
    ))

    assert all(
        item.product_identity.normalized_identity != "portable shower caddy"
        for item in semantic.listings
    )
    definitions = tuple(_definition(item) for item in route.routes)
    assert any(
        item.get("installation_architecture") == ("hanging_mount",)
        for item in definitions
    )
    assert any(
        item.get("installation_architecture") == ("wall_mount",)
        for item in definitions
    )
    wall_listings = tuple(
        item for item in semantic.listings
        if any(
            fact.dimension == "installation_architecture"
            and fact.normalized_value == "wall_mount"
            for fact in item.facts
        )
    )
    assert all(
        any(
            fact.dimension == "attachment_mechanism"
            and fact.normalized_value == "adhesive"
            for fact in item.facts
        )
        for item in wall_listings
    )


def test_governed_structural_portable_variants_can_remain_route_defining() -> None:
    _, _, _, _, route = _build(*(
        *(
            _record(
                index,
                title="Portable Shower Caddy Basket",
                detail=(
                    "Mounting Type: Tension Pole | Attachment Type: Tension"
                ),
            )
            for index in range(1, 4)
        ),
        *(
            _record(
                index,
                title="Portable Shower Caddy Basket",
                detail="Mounting Type: Floor Standing",
            )
            for index in range(4, 7)
        ),
        *(
            _record(index, title="Portable Shower Caddy Basket")
            for index in range(7, 10)
        ),
    ))

    definitions = tuple(_definition(item) for item in route.routes)
    assert len(route.routes) == 3
    assert {item.get("installation_architecture") for item in definitions} == {
        None,
        ("freestanding",),
        ("tension_pole",),
    }
    assert all(
        item.get("product_form") == ("portable",) for item in definitions
    )


def test_route_business_projection_is_deterministic() -> None:
    records = tuple(
        _record(
            index,
            title="Portable Shower Caddy Tote",
            detail=(
                "Mounting Type: Hanging Mount"
                if index % 2 else "Mounting Type: Wall Mount"
            ),
            sales=100 + index,
        )
        for index in range(1, 7)
    )
    *_, first = _build(*records)
    *_, second = _build(*reversed(records))

    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.to_json() == second.to_json()


def test_generic_shared_engine_contains_no_shower_or_asin_special_case() -> None:
    projection = (
        PROFILES.parents[1]
        / "src/amazon_product_intelligence/route_discovery_v2/projection.py"
    ).read_text(encoding="utf-8").casefold()
    assert "shower caddy" not in projection
    assert re.search(r"\bb0[a-z0-9]{8}\b", projection) is None
