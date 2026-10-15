from __future__ import annotations

from amazon_product_intelligence.product_route_opportunity.models import (
    MembershipStatus,
)
from amazon_product_intelligence.route_discovery_v2 import (
    build_route_discovery_v2,
    load_route_discovery_v2_config,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from tests.test_route_discovery_v2 import CONFIGS, PROFILES, _dataset, _record


TABLETOP_RULE = "shower-install-tabletop-mount-ambiguous-structured"


def _semantic(*records):
    dataset = _dataset(tuple(records))
    profile = load_category_semantic_profile(
        PROFILES / "shower_caddies.v1_1.json"
    )
    result = build_semantic_engine_v2_result(dataset, profile=profile)
    return dataset, profile, result


def _installation_values(listing) -> set[str]:
    return {
        fact.normalized_value
        for fact in listing.facts
        if fact.dimension == "installation_architecture"
    }


def test_tabletop_mount_alone_is_evidence_only_and_cannot_author_route() -> None:
    dataset, profile, semantic = _semantic(_record(
        1,
        title="Stainless Steel Shower Shelves",
        detail="Mounting Type: Tabletop Mount",
    ))
    listing = semantic.listings[0]

    assert _installation_values(listing) == set()
    assert any(
        evidence.profile_rule_id == TABLETOP_RULE
        and evidence.source_key == "installation"
        for evidence in listing.evidence
    )
    assert f"EVIDENCE_ONLY_UNRESOLVED:{TABLETOP_RULE}" in listing.limitations

    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    route_result = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )
    membership = route_result.memberships[0]
    assert membership.status is MembershipStatus.UNCLASSIFIED
    assert membership.primary_route_id is None


def test_tabletop_observation_does_not_block_authoritative_wall_evidence() -> None:
    records = tuple(
        _record(
            index,
            title="Adhesive Shower Caddy Shelves",
            detail=(
                "Mounting Type: Tabletop Mount | "
                "Attachment Type: Adhesive"
            ),
        )
        for index in range(1, 4)
    )
    dataset, profile, semantic = _semantic(*records)

    assert all(
        _installation_values(listing) == {"wall_mount"}
        for listing in semantic.listings
    )
    assert all(
        any(evidence.profile_rule_id == TABLETOP_RULE for evidence in listing.evidence)
        for listing in semantic.listings
    )

    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    route_result = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )
    assert all(
        membership.status is MembershipStatus.ASSIGNED
        for membership in route_result.memberships
    )
    assert all(
        any(
            feature.dimension == "installation_architecture"
            and feature.values == ("wall_mount",)
            for feature in membership.assignment_features
        )
        for membership in route_result.memberships
    )


def test_explicit_no_installation_required_remains_authoritative() -> None:
    _, _, semantic = _semantic(_record(
        1,
        title="Portable Mesh Shower Caddy Bag",
        detail="Installation Type: No Installation Required",
    ))
    listing = semantic.listings[0]

    assert _installation_values(listing) == {"no_installation"}
    assert any(
        evidence.profile_rule_id == "shower-install-none-structured"
        for evidence in listing.evidence
    )
