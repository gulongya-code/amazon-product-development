from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
    canonical_json,
)
from amazon_product_intelligence.product_route_opportunity.models import MembershipStatus
from amazon_product_intelligence.route_discovery_v2 import (
    RouteDiscoveryV2Error,
    build_route_discovery_v2,
    build_semantic_route_feature_views,
    load_route_discovery_v2_config,
    validate_route_v2_authority,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    CohortEligibilityState,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from amazon_product_intelligence.sellersprite_import.models import (
    EvidenceSemantics,
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
    NormalizedField,
)


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "config/category_semantic_profiles"
CONFIGS = ROOT / "config/route_discovery_v2"
TITLE = "\u5546\u54c1\u6807\u9898"
DETAIL = "\u8be6\u7ec6\u53c2\u6570"
MONTHLY_SALES = "\u6708\u9500\u91cf"
PRICE = "\u4ef7\u683c($)"
REVIEW_COUNT = "\u8bc4\u5206\u6570"
AGE_DAYS = "\u4e0a\u67b6\u5929\u6570"
BRAND = "\u54c1\u724c"
SELLER = "BuyBox\u5356\u5bb6"
MOM = "\u9500\u91cf\u73af\u6bd4\u589e\u957f\u7387"
YOY = "\u9500\u91cf\u540c\u6bd4\u589e\u957f\u7387"


def _field(header: str, value: str) -> NormalizedField:
    return NormalizedField(
        header=header, requirement="OPTIONAL", value_type="TEXT", value=value,
        import_status=ImportValueStatus.NORMALIZED,
        presence_status=PresenceStatus.PRESENT,
        normalization_status=NormalizationStatus.NORMALIZED,
        semantic_status=SemanticStatus.CONFIRMED,
        evidence_semantics=EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE,
    )


def _record(
    index: int,
    *,
    title: str = "Shower Caddy",
    detail: str | None = None,
    sales: int = 100,
    pack_count: int | None = None,
) -> ListingRecordV1:
    asin = f"SYN{index:07d}"
    fields = [
        _field(TITLE, title), _field(MONTHLY_SALES, str(sales)),
        _field(PRICE, "19.99"), _field(REVIEW_COUNT, "25"),
        _field(AGE_DAYS, "60"), _field(BRAND, f"brand-{index % 3}"),
        _field(SELLER, f"seller-{index % 2}"), _field(MOM, "0.10"),
        _field(YOY, "0.20"),
    ]
    parameters = [] if detail is None else [detail]
    if pack_count is not None:
        parameters.append(f"Number of Items: {pack_count}")
    if parameters:
        fields.append(_field(DETAIL, " | ".join(parameters)))
    return ListingRecordV1(
        asin=asin, parent_asin=None, source_row=index + 2,
        fields=tuple(fields), record_fingerprint=f"record-fingerprint-{asin}",
    )


def _dataset(
    records: tuple[ListingRecordV1, ...],
    *,
    category: str = "shower caddies",
    imported_at: str = "2026-08-29T00:00:00+00:00",
) -> GovernedMarketDatasetV1:
    return GovernedMarketDatasetV1(
        dataset_id="route-v2-synthetic-dataset",
        semantic_fingerprint="a" * 64, source_type="CSV",
        source_basename="synthetic.csv", source_file_sha256="b" * 64,
        imported_at=imported_at, marketplace="US", category=category,
        observed_date="2026-08-29", observed_date_status="KNOWN",
        source_sheet=None, header_row=1, source_row_count=len(records),
        accepted_listing_count=len(records), unique_asin_count=len(records),
        duplicate_row_count=0, rejected_row_count=0, quarantined_row_count=0,
        missing_core_field_summary=(), unmapped_headers=(), out_of_scope_headers=(),
        records=records, row_outcomes=(),
    )


def _build(records: tuple[ListingRecordV1, ...]):
    dataset = _dataset(records)
    profile = load_category_semantic_profile(PROFILES / "shower_caddies.v1_1.json")
    semantic = build_semantic_engine_v2_result(dataset, profile=profile)
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    return dataset, profile, semantic, config, build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )


def _architecture_records(
    architectures: tuple[tuple[str, str, int], ...],
) -> tuple[ListingRecordV1, ...]:
    result = []
    index = 1
    for installation, attachment, count in architectures:
        for _ in range(count):
            result.append(_record(
                index,
                detail=f"Installation: {installation} | Attachment: {attachment}",
                sales=100 + index,
            ))
            index += 1
    return tuple(result)


def test_s2_projection_preserves_authoritative_lineage_and_primary_source_values() -> None:
    records = (_record(
        1, title="Shower Caddy No Drill",
        detail="Installation: Adhesive | Attachment: Wall",
    ),)
    dataset = _dataset(records)
    profile = load_category_semantic_profile(PROFILES / "shower_caddies.v1_1.json")
    semantic = build_semantic_engine_v2_result(dataset, profile=profile)
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    views = build_semantic_route_feature_views(
        dataset, semantic, profile=profile, config=config,
    )
    assert len(views) == 1
    view = views[0]
    assert view.semantic_listing_result_id == semantic.listings[0].listing_result_id
    assert view.cohort_state is CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE
    installation = view.feature("installation_architecture")
    assert installation is not None
    assert installation.profile_fingerprint == profile.fingerprint
    assert "adhesive" in installation.defining_values
    assert "title_installation_signal" in installation.values
    assert "title_installation_signal" not in installation.defining_values


def test_primary_only_gate_and_exactly_one_membership_state_per_listing() -> None:
    records = (
        _record(1, detail="Installation: Adhesive | Attachment: Wall"),
        _record(2, detail="Installation: Adhesive | Attachment: Wall"),
        _record(3, detail="Installation: Adhesive | Attachment: Wall"),
        _record(4, title="Replacement Adhesive for Shower Caddy", detail="Installation: Adhesive"),
        _record(5, title="Squeegee for Bathroom", detail="Installation: Adhesive"),
    )
    *_, result = _build(records)
    assert len(result.memberships) == len(records)
    assert len({item.listing_reference for item in result.memberships}) == len(records)
    assert result.assigned_count == 3
    assert result.unclassified_count == 2
    assert all(
        (item.status is MembershipStatus.ASSIGNED) == (item.primary_route_id is not None)
        for item in result.memberships
    )
    assigned = {item.listing_reference for item in result.memberships if item.primary_route_id}
    assert assigned == {item.asin for item in records[:3]}


def test_missing_semantics_are_unclassified_not_an_equality_signal() -> None:
    records = (
        _record(1, detail="Installation: Adhesive | Attachment: Wall"),
        _record(2, detail="Installation: Adhesive | Attachment: Wall"),
        _record(3, detail="Installation: Adhesive | Attachment: Wall"),
        _record(4), _record(5), _record(6),
    )
    *_, result = _build(records)
    assert result.assigned_count == 3
    assert result.unclassified_count == 3
    assert len(result.routes) == 1
    missing = result.memberships[3:]
    assert all(item.primary_route_id is None for item in missing)
    assert all(
        "INSUFFICIENT_PROFILE_AUTHORIZED_ROUTE_SEMANTICS"
        in item.membership_reason_codes for item in missing
    )


def test_facet_only_package_count_cannot_split_route_identity() -> None:
    records = tuple(
        _record(
            index, detail="Installation: Adhesive | Attachment: Wall",
            pack_count=1 if index <= 3 else 9,
        )
        for index in range(1, 7)
    )
    *_, result = _build(records)
    assert result.assigned_count == 6
    assert len(result.routes) == 1
    assert {
        key.dimension for key in result.routes[0].defining_features
    } == {"installation_architecture"}
    assert all(
        descriptor.dimension == "package_count"
        for descriptor in result.routes[0].facet_descriptors
    )


def test_profile_secondary_promotion_is_explicit_and_facet_promotion_is_rejected() -> None:
    profile = load_category_semantic_profile(PROFILES / "dog_water_bottles.v1_1.json")
    base = load_route_discovery_v2_config(CONFIGS / "dog_water_bottles.v2.json")
    promoted = replace(
        base, route_dimensions=("item_capacity",),
        promoted_secondary_dimensions=("item_capacity",),
        min_defining_dimensions=1,
    )
    validate_route_v2_authority(promoted, profile, "dog water bottles")
    with pytest.raises(RouteDiscoveryV2Error, match="not profile-promoted"):
        validate_route_v2_authority(
            replace(promoted, promoted_secondary_dimensions=()),
            profile, "dog water bottles",
        )
    with pytest.raises(RouteDiscoveryV2Error, match="cannot define a route"):
        validate_route_v2_authority(
            replace(
                base, route_dimensions=("package_count",),
                promoted_secondary_dimensions=("package_count",),
            ),
            profile, "dog water bottles",
        )


def test_compatible_multi_value_and_sparse_signatures_merge_deterministically() -> None:
    records = (
        _record(1, detail="Installation: Adhesive | Attachment: Wall"),
        _record(2, detail="Installation: Adhesive | Attachment: Wall"),
        _record(3, detail="Installation: Adhesive | Attachment: Wall"),
        _record(4, detail="Installation: Adhesive | Installation: Hanging"),
        _record(5, detail="Installation: Adhesive"),
        _record(6, detail="Installation: Adhesive"),
    )
    *_, result = _build(records)
    assert result.assigned_count == 6
    assert len(result.routes) == 1
    assert result.routes[0].member_count == 6
    assert all(
        "HIERARCHICAL_SPARSE_SEMANTIC_CONSENSUS"
        in item.membership_reason_codes
        for item in result.memberships
    )
    assert len(result.routes[0].defining_features) == 1
    assert result.routes[0].defining_features[0].dimension == (
        "installation_architecture"
    )
    assert result.routes[0].defining_features[0].values == ("adhesive",)


def test_single_viable_child_with_sparse_remainder_stays_broad_parent() -> None:
    records = (
        *tuple(
            _record(
                index,
                detail="Installation: Adhesive | Attachment: Wall",
            )
            for index in range(1, 4)
        ),
        _record(4, detail="Installation: Adhesive"),
        _record(5, detail="Installation: Adhesive"),
    )
    *_, result = _build(records)
    assert result.assigned_count == 5
    assert result.unclassified_count == 0
    assert result.review_required_count == 0
    assert len(result.routes) == 1
    assert tuple(
        (item.dimension, item.values)
        for item in result.routes[0].defining_features
    ) == (("installation_architecture", ("adhesive",)),)
    assert all(
        "HIERARCHICAL_BASE_OR_BROAD_PARENT_ROUTE"
        in item.membership_reason_codes
        for item in result.memberships
    )


def test_tiny_incompatible_route_is_governedly_unclassified() -> None:
    records = _architecture_records((
        ("Adhesive", "Wall", 3), ("Tension Pole", "Pole", 1),
    ))
    *_, result = _build(records)
    assert result.assigned_count == 3
    assert result.unclassified_count == 1
    assert len(result.routes) == 1
    assert "HIERARCHICAL_SEMANTIC_GROUP_NOT_VIABLE" in (
        result.memberships[-1].membership_reason_codes
    )


def test_same_first_dimension_with_incompatible_second_dimension_stays_separate() -> None:
    records = _architecture_records((
        ("Adhesive", "Wall", 3), ("Adhesive", "Hook", 3),
    ))
    *_, result = _build(records)
    assert result.assigned_count == 6
    assert len(result.routes) == 2
    definitions = {
        tuple((item.dimension, item.values) for item in route.defining_features)
        for route in result.routes
    }
    assert definitions == {
        (
            ("installation_architecture", ("adhesive",)),
            ("attachment_mechanism", ("wall",)),
        ),
        (
            ("installation_architecture", ("adhesive",)),
            ("attachment_mechanism", ("hook",)),
        ),
    }


def test_cross_level_sparse_signature_does_not_merge_into_a_different_base() -> None:
    records = (
        *tuple(
            _record(
                index,
                detail="Installation: Adhesive | Attachment: Wall",
            )
            for index in range(1, 4)
        ),
        _record(4, detail="Attachment: Wall"),
        _record(5, detail="Attachment: Wall"),
    )
    *_, result = _build(records)
    assert result.assigned_count == 3
    assert result.unclassified_count == 2
    assert len(result.routes) == 1
    sparse = result.memberships[-2:]
    assert all(
        "HIERARCHICAL_SEMANTIC_GROUP_NOT_VIABLE"
        in item.membership_reason_codes
        for item in sparse
    )
    assert all(
        "NO_COMPATIBLE_VIABLE_ROUTE" in item.membership_reason_codes
        for item in sparse
    )
    assert all(item.status is MembershipStatus.UNCLASSIFIED for item in sparse)


def test_cross_level_sparse_signature_attaches_to_one_compatible_route() -> None:
    records = (
        *_architecture_records((
            ("Adhesive", "Wall", 3), ("Adhesive", "Hook", 3),
        )),
        _record(7, detail="Attachment: Wall"),
        _record(8, detail="Attachment: Wall"),
    )
    dataset, profile, _, config, result = _build(records)
    assert result.assigned_count == 8
    assert result.unclassified_count == 0
    assert result.review_required_count == 0
    assert len(result.routes) == 2
    wall_route = next(
        route for route in result.routes
        if any(
            item.dimension == "attachment_mechanism"
            and item.values == ("wall",)
            for item in route.defining_features
        )
    )
    assert wall_route.member_count == 5
    sparse = result.memberships[-2:]
    assert all(item.primary_route_id == wall_route.route_id for item in sparse)
    assert all(
        "UNIQUE_COMPATIBLE_VIABLE_ROUTE_ATTACHMENT"
        in item.membership_reason_codes
        for item in sparse
    )
    assert all(
        "ROUTE_DEFINITION_UNCHANGED_BY_COMPATIBLE_ATTACHMENT"
        in item.limitations
        for item in sparse
    )
    assert all(
        tuple((key.dimension, key.values) for key in item.assignment_features)
        == (("attachment_mechanism", ("wall",)),)
        for item in sparse
    )
    replay_dataset = replace(
        dataset,
        imported_at="2032-01-01T00:00:00+00:00",
        records=tuple(reversed(dataset.records)),
    )
    replay_semantic = build_semantic_engine_v2_result(
        replay_dataset, profile=profile,
    )
    replay = build_route_discovery_v2(
        replay_dataset, replay_semantic, profile=profile, config=config,
    )
    assert result.to_json() == replay.to_json()


def test_ambiguous_sparse_bridge_does_not_merge_incompatible_routes() -> None:
    records = (
        *_architecture_records((
            ("Adhesive", "Wall", 3), ("Adhesive", "Hook", 3),
        )),
        _record(7, detail="Installation: Adhesive"),
        _record(8, detail="Installation: Adhesive"),
    )
    dataset, profile, _, config, result = _build(records)
    assert result.assigned_count == 6
    assert result.unclassified_count == 0
    assert result.review_required_count == 2
    assert len(result.routes) == 2
    assert all(
        item.primary_route_id is None for item in result.memberships[-2:]
    )
    assert all(
        "AMBIGUOUS_HIERARCHICAL_ROUTE_MEMBERSHIP"
        in item.membership_reason_codes
        for item in result.memberships[-2:]
    )
    assert all(
        "AMBIGUOUS_MULTIPLE_COMPATIBLE_VIABLE_ROUTES"
        in item.membership_reason_codes
        for item in result.memberships[-2:]
    )
    assert all(
        item.status is MembershipStatus.REVIEW_REQUIRED
        for item in result.memberships[-2:]
    )
    replay_dataset = replace(
        dataset,
        imported_at="2032-01-01T00:00:00+00:00",
        records=tuple(reversed(dataset.records)),
    )
    replay_semantic = build_semantic_engine_v2_result(
        replay_dataset, profile=profile,
    )
    replay = build_route_discovery_v2(
        replay_dataset, replay_semantic, profile=profile, config=config,
    )
    assert result.to_json() == replay.to_json()


def test_overlapping_multi_values_merge_only_on_common_defining_value() -> None:
    records = (
        _record(1, detail="Installation: Adhesive | Installation: Hanging"),
        _record(2, detail="Installation: Adhesive | Installation: Hanging"),
        _record(3, detail="Installation: Hanging"),
        _record(4, detail="Installation: Hanging"),
        _record(5, detail="Installation: Hanging"),
    )
    *_, result = _build(records)
    assert result.assigned_count == 5
    assert len(result.routes) == 1
    assert result.routes[0].defining_features[0].values == ("hanging",)
    first_membership = next(
        item for item in result.memberships if item.listing_reference == records[0].asin
    )
    assert first_membership.assignment_features[0].values == (
        "adhesive", "hanging",
    )


def test_corroborating_only_fact_without_profile_fallback_cannot_define_route() -> None:
    records = tuple(
        _record(index, title="Shower Caddy No Drill")
        for index in range(1, 4)
    )
    *_, result = _build(records)
    assert result.assigned_count == 0
    assert result.unclassified_count == 3
    assert all(
        item.primary_route_id is None for item in result.memberships
    )


def test_missing_only_difference_cannot_make_candidate_routes_materially_distinct() -> None:
    records = (
        *_architecture_records((
            ("Adhesive", "Wall", 3), ("Adhesive", "Hook", 3),
        )),
        _record(7, detail="Installation: Adhesive"),
        _record(8, detail="Installation: Adhesive"),
        _record(9, detail="Installation: Adhesive"),
    )
    *_, result = _build(records)
    assert len(result.routes) == 3
    assert result.candidates == ()
    assert result.candidate_selection_status.value == "INSUFFICIENT_EVIDENCE"


def test_candidate_search_does_not_let_large_broad_route_hide_valid_distinct_set() -> None:
    records = (
        *tuple(
            _record(index, detail="Installation: Adhesive")
            for index in range(1, 11)
        ),
        *tuple(
            _record(
                index,
                detail="Installation: Adhesive | Attachment: Wall",
            )
            for index in range(11, 14)
        ),
        *tuple(
            _record(
                index,
                detail="Installation: Adhesive | Attachment: Hook",
            )
            for index in range(14, 17)
        ),
        *tuple(
            _record(
                index,
                detail="Installation: Adhesive | Attachment: Pole",
            )
            for index in range(17, 20)
        ),
    )
    *_, result = _build(records)
    assert len(result.routes) == 4
    assert len(result.candidates) == 3
    routes = {item.route_id: item for item in result.routes}
    selected = tuple(routes[item.route_id] for item in result.candidates)
    assert all(
        {item.dimension for item in route.defining_features}
        == {"installation_architecture", "attachment_mechanism"}
        for route in selected
    )


def test_route_membership_ids_and_fingerprint_are_permutation_and_timestamp_stable() -> None:
    records = _architecture_records((
        ("Adhesive", "Wall", 3), ("Hanging", "Hook", 3),
    ))
    dataset, profile, semantic, config, first = _build(records)
    replay_dataset = replace(
        dataset, imported_at="2030-01-01T00:00:00+00:00",
        records=tuple(reversed(dataset.records)),
    )
    replay_semantic = build_semantic_engine_v2_result(replay_dataset, profile=profile)
    second = build_route_discovery_v2(
        replay_dataset, replay_semantic, profile=profile, config=config,
    )
    assert first.to_json() == second.to_json()
    assert [item.membership_id for item in first.memberships] == [
        item.membership_id for item in second.memberships
    ]


def test_route_contract_rejects_tampered_id_and_fingerprint() -> None:
    records = _architecture_records((("Adhesive", "Wall", 3),))
    *_, result = _build(records)
    route = result.routes[0]
    with pytest.raises(RouteDiscoveryV2Error, match="route ID mismatch"):
        replace(route, route_id="product-route-v2:tampered")
    with pytest.raises(RouteDiscoveryV2Error, match="route fingerprint mismatch"):
        replace(route, semantic_fingerprint="0" * 64)


def test_result_contract_rejects_declared_status_count_tampering() -> None:
    records = _architecture_records((("Adhesive", "Wall", 3),))
    *_, result = _build(records)
    with pytest.raises(
        RouteDiscoveryV2Error, match="declared membership status counts mismatch",
    ):
        replace(
            result,
            assigned_count=result.assigned_count - 1,
            unclassified_count=result.unclassified_count + 1,
        )


def test_result_contract_rejects_route_member_mapping_tampering() -> None:
    records = _architecture_records((
        ("Adhesive", "Wall", 3), ("Hanging", "Hook", 3),
    ))
    *_, result = _build(records)
    first, second = result.routes
    logical = first.logical_dict()
    logical["member_listing_references"] = list(
        second.member_listing_references
    )
    logical["membership_ids"] = list(second.membership_ids)
    tampered = replace(
        first,
        member_listing_references=second.member_listing_references,
        membership_ids=second.membership_ids,
        semantic_fingerprint=sha256(
            canonical_json(logical).encode("utf-8")
        ).hexdigest(),
    )
    with pytest.raises(
        RouteDiscoveryV2Error,
        match="assigned membership/route member mapping mismatch",
    ):
        replace(result, routes=(tampered, *result.routes[1:]))


def test_conflict_is_preserved_as_review_required(tmp_path: Path) -> None:
    payload = json.loads(
        (PROFILES / "shower_caddies.v1_1.json").read_text(encoding="utf-8")
    )
    for policy in payload["source_policies"]:
        if policy["dimension"] == "installation_architecture":
            policy["route_critical"] = True
    payload["route_critical_conflict_rules"].append({
        "rule_id": "test-installation-conflict",
        "dimension": "installation_architecture",
        "values": ["adhesive", "hanging"],
    })
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(payload), encoding="utf-8")
    profile = load_category_semantic_profile(profile_path)
    dataset = _dataset((_record(
        1,
        detail="Installation: Adhesive | Installation: Hanging | Attachment: Wall",
    ),))
    semantic = build_semantic_engine_v2_result(dataset, profile=profile)
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    result = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )
    assert result.review_required_count == 1
    assert result.memberships[0].status is MembershipStatus.REVIEW_REQUIRED
    assert result.memberships[0].primary_route_id is None


def test_candidate_selection_uses_semantic_diversity_and_respects_three_to_five() -> None:
    records = _architecture_records((
        ("Adhesive", "Wall", 3), ("Hanging", "Hook", 3),
        ("Tension Pole", "Pole", 3), ("Floor", "Standing", 3),
    ))
    *_, result = _build(records)
    assert len(result.routes) == 4
    assert 3 <= len(result.candidates) <= 5
    selected = [
        next(route for route in result.routes if route.route_id == candidate.route_id)
        for candidate in result.candidates
    ]
    for index, left in enumerate(selected):
        for right in selected[index + 1:]:
            assert left.semantic_tokens != right.semantic_tokens
            assert left.semantic_tokens ^ right.semantic_tokens
    assert all(
        key.dimension != "package_count"
        for route in selected for key in route.defining_features
    )


def test_candidate_selection_does_not_force_minimum() -> None:
    records = _architecture_records((
        ("Adhesive", "Wall", 3), ("Hanging", "Hook", 3),
    ))
    *_, result = _build(records)
    assert len(result.routes) == 2
    assert result.candidates == ()
    assert result.candidate_selection_status.value == "INSUFFICIENT_EVIDENCE"


def test_retained_metric_invariants_growth_and_diagnostics_safety() -> None:
    records = _architecture_records((
        ("Adhesive", "Wall", 3), ("Hanging", "Hook", 3),
        ("Tension Pole", "Pole", 3),
    ))
    *_, result = _build(records)
    assert sum(route.metric("route_listing_share").value for route in result.routes) == pytest.approx(1)
    assert sum(route.metric("route_sales_share").value for route in result.routes) == pytest.approx(1)
    for route in result.routes:
        assert route.metric("mom_aggregate_growth").value["aggregation"] == (
            "SUM_CURRENT_DIV_SUM_RECONSTRUCTED_PRIOR_MINUS_ONE"
        )
        assert route.metric("review_count_distribution").value["method"] == "NEAREST_RANK"
    diagnostics = dict(result.diagnostics)
    assert diagnostics["network_calls"] == 0
    assert diagnostics["provider_calls"] == 0
    assert diagnostics["credential_accesses"] == 0
    assert diagnostics["llm_authoritative_decisions"] == 0
    assert diagnostics["downstream_representation_selection_count"] == 0
    encoded = json.dumps(diagnostics, sort_keys=True)
    assert not any(item.asin in encoded for item in records)
    assert "Shower Caddy" not in encoded


def test_same_generic_engine_and_configs_cover_all_five_profiles_without_category_literals() -> None:
    pairs = (
        ("shower_caddies.v2.json", "shower_caddies.v1_1.json"),
        ("dog_water_bottles.v2.json", "dog_water_bottles.v1_1.json"),
        ("vacuum_replacement_filters.v2.json", "vacuum_replacement_filters.v1_1.json"),
        ("food_storage_containers.v2.json", "food_storage_containers.v1_1.json"),
        ("air_fryers.v2.json", "air_fryer_accessories.v1_1.json"),
    )
    for config_name, profile_name in pairs:
        config = load_route_discovery_v2_config(CONFIGS / config_name)
        profile = load_category_semantic_profile(PROFILES / profile_name)
        validate_route_v2_authority(config, profile, config.category)
    generic = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src/amazon_product_intelligence/route_discovery_v2").glob("*.py"))
    ).casefold()
    assert all(term not in generic for term in (
        "shower caddy", "dog water bottle", "vacuum filter",
        "food storage", "air fryer",
    ))
    assert "representative_" + "asin" not in generic


def test_strict_config_rejects_unknown_key(tmp_path: Path) -> None:
    payload = json.loads((CONFIGS / "shower_caddies.v2.json").read_text(encoding="utf-8"))
    payload["category_branch"] = "forbidden"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(RouteDiscoveryV2Error, match="unknown"):
        load_route_discovery_v2_config(path)
