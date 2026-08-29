from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    CohortEligibilityState,
    ConsumptionLifecycle,
    EvidenceRelationshipState,
    QuantitySubtype,
    RelationRole,
    SemanticDecisionStatus,
    SemanticEngineV2Error,
    SemanticScope,
    SemanticSourceClass,
    UniversalSemanticRole,
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
from scripts.build_semantic_engine_v2 import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
PROFILES = ROOT / "config/category_semantic_profiles"


def _field(header: str, value: str) -> NormalizedField:
    return NormalizedField(
        header=header,
        requirement="OPTIONAL",
        value_type="TEXT",
        value=value,
        import_status=ImportValueStatus.NORMALIZED,
        presence_status=PresenceStatus.PRESENT,
        normalization_status=NormalizationStatus.NORMALIZED,
        semantic_status=SemanticStatus.CONFIRMED,
        evidence_semantics=EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE,
    )


def _dataset(
    category: str,
    records: tuple[tuple[str, tuple[NormalizedField, ...]], ...],
    *,
    imported_at: str = "2026-08-29T00:00:00+00:00",
) -> GovernedMarketDatasetV1:
    listing_records = tuple(
        ListingRecordV1(
            asin=asin,
            parent_asin=None,
            source_row=index + 2,
            fields=fields,
            record_fingerprint=f"record-fingerprint-{asin}",
        )
        for index, (asin, fields) in enumerate(records)
    )
    return GovernedMarketDatasetV1(
        dataset_id="gmdv1-semantic-synthetic",
        semantic_fingerprint="upstream-semantic-fingerprint",
        source_type="CSV",
        source_basename="synthetic.csv",
        source_file_sha256="0" * 64,
        imported_at=imported_at,
        marketplace="US",
        category=category,
        observed_date="2026-08-29",
        observed_date_status="KNOWN",
        source_sheet=None,
        header_row=1,
        source_row_count=len(listing_records),
        accepted_listing_count=len(listing_records),
        unique_asin_count=len(listing_records),
        duplicate_row_count=0,
        rejected_row_count=0,
        quarantined_row_count=0,
        missing_core_field_summary=(),
        unmapped_headers=(),
        out_of_scope_headers=(),
        records=listing_records,
        row_outcomes=(),
    )


def _profile(name: str):
    return load_category_semantic_profile(PROFILES / name)


def test_all_five_profiles_are_strict_and_fingerprinted() -> None:
    files = sorted(PROFILES.glob("*.json"))
    assert len(files) == 5
    profiles = [_profile(item.name) for item in files]
    assert len({item.fingerprint for item in profiles}) == 5
    assert all(len(item.fingerprint) == 64 for item in profiles)
    assert all(SemanticSourceClass.LLM_DERIVED_CANDIDATE not in item.source_authorization for item in profiles)
    assert all(item.normalization_version == "semantic-normalization-v2.0" for item in profiles)


def test_profile_loader_rejects_unknown_keys_and_category_mismatch(tmp_path: Path) -> None:
    source = PROFILES / "shower_caddies.v1_1.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["category_branch"] = "forbidden"
    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SemanticEngineV2Error, match="PROFILE_SCHEMA_INVALID"):
        load_category_semantic_profile(invalid)
    with pytest.raises(SemanticEngineV2Error, match="PROFILE_CATEGORY_MISMATCH"):
        build_semantic_engine_v2_result(
            _dataset("wrong category", (("B000000001", (_field("商品标题", "Shower Caddy"),)),)),
            profile=_profile("shower_caddies.v1_1.json"),
        )


def test_frozen_relationship_and_role_vocabularies_are_exact() -> None:
    assert {item.value for item in EvidenceRelationshipState} == {
        "AGREES", "COMPLEMENTARY", "COMPATIBLE_MULTI_VALUE",
        "SOURCE_ONLY_TITLE", "SOURCE_ONLY_STRUCTURED", "UNAVAILABLE",
        "TRUE_CONFLICT", "ROUTE_CRITICAL_CONFLICT",
    }
    assert {item.value for item in UniversalSemanticRole} == {
        "PRODUCT_IDENTITY", "PRODUCT_ROLE", "STRUCTURAL_FORM",
        "USAGE_ARCHITECTURE", "INSTALLATION_ARCHITECTURE",
        "ATTACHMENT_MECHANISM", "OPERATION_MECHANISM", "POWER_MODE",
        "COMPATIBILITY", "MATERIAL", "SIZE_CAPACITY", "QUANTITY",
        "FUNCTIONAL_FEATURE", "COSMETIC",
    }


def test_generic_engine_contains_no_five_category_vocabulary() -> None:
    generic = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src/amazon_product_intelligence/semantic_engine_v2").glob("*.py"))
    ).casefold()
    for literal in (
        "shower caddy", "dog water bottle", "vacuum filter",
        "food storage", "air fryer",
    ):
        assert literal not in generic


def test_shower_facts_relationships_role_cohort_and_no_raw_title() -> None:
    result = build_semantic_engine_v2_result(
        _dataset("shower caddies", (("B000000001", (
            _field("商品标题", "Rustproof Shower Caddy No Drill"),
            _field("详细参数", "Installation Type: Adhesive | Number of Items: 2"),
        )),)),
        profile=_profile("shower_caddies.v1_1.json"),
    )
    listing = result.listings[0]
    assert listing.product_identity.status is SemanticDecisionStatus.GOVERNED
    assert listing.product_identity.normalized_identity == "shower caddy"
    assert listing.product_role.relation_role is RelationRole.PRIMARY_PRODUCT
    assert listing.market_cohort_eligibility.state is CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE
    assert any(item.role is UniversalSemanticRole.INSTALLATION_ARCHITECTURE for item in listing.facts)
    assert any(item.quantity_subtype is QuantitySubtype.PACKAGE_COUNT for item in listing.facts)
    assert any(item.state is EvidenceRelationshipState.COMPATIBLE_MULTI_VALUE for item in listing.relationships)
    encoded = result.to_json().casefold()
    assert "rustproof shower caddy no drill" not in encoded
    assert '"network_calls":0' in encoded
    assert '"llm_authoritative_decisions":0' in encoded


def test_agreement_source_only_unavailable_and_true_conflict_are_distinct() -> None:
    agreed = build_semantic_engine_v2_result(
        _dataset("shower caddies", (("B000000001", (
            _field("商品标题", "Reusable Shower Caddy No Drill"),
            _field("详细参数", "Installation Type: title_installation_signal"),
        )),)),
        profile=_profile("shower_caddies.v1_1.json"),
    ).listings[0]
    states = {item.dimension: item.state for item in agreed.relationships}
    assert states["installation_architecture"] is EvidenceRelationshipState.AGREES
    assert states["attachment_mechanism"] is EvidenceRelationshipState.UNAVAILABLE
    assert states["product_identity"] is EvidenceRelationshipState.SOURCE_ONLY_TITLE

    conflict = build_semantic_engine_v2_result(
        _dataset("shower caddies", (("B000000001", (
            _field("商品标题", "Reusable Replacement Adhesive Shower Caddy"),
        )),)),
        profile=_profile("shower_caddies.v1_1.json"),
    ).listings[0]
    lifecycle = next(
        item for item in conflict.relationships
        if item.dimension == "consumption_lifecycle"
    )
    assert lifecycle.state is EvidenceRelationshipState.TRUE_CONFLICT
    assert conflict.product_role.lifecycle_status is SemanticDecisionStatus.GOVERNED


def test_equal_priority_route_critical_relation_conflict_requires_review(tmp_path: Path) -> None:
    payload = json.loads((PROFILES / "shower_caddies.v1_1.json").read_text(encoding="utf-8"))
    payload["relation_rules"].append({
        "rule_id": "shower-relation-equal-priority-conflict",
        "sources": ["LISTING_TITLE"],
        "phrases": ["shower caddy"],
        "exclusions": [],
        "result": "ACCESSORY",
        "priority": 20,
    })
    profile_path = tmp_path / "critical.json"
    profile_path.write_text(json.dumps(payload), encoding="utf-8")
    listing = build_semantic_engine_v2_result(
        _dataset("shower caddies", (("B000000001", (
            _field("商品标题", "Shower Caddy"),
        )),)),
        profile=load_category_semantic_profile(profile_path),
    ).listings[0]
    relation = next(item for item in listing.relationships if item.dimension == "relation_role")
    assert relation.state is EvidenceRelationshipState.ROUTE_CRITICAL_CONFLICT
    assert listing.product_role.relation_status is SemanticDecisionStatus.REVIEW_REQUIRED
    assert listing.market_cohort_eligibility.state is CohortEligibilityState.REVIEW_REQUIRED


def test_result_contract_rejects_fingerprint_tampering() -> None:
    result = build_semantic_engine_v2_result(
        _dataset("dog water bottles", (("B000000001", (
            _field("商品标题", "Dog Water Bottle"),
        )),)),
        profile=_profile("dog_water_bottles.v1_1.json"),
    )
    with pytest.raises(SemanticEngineV2Error, match="result fingerprint mismatch"):
        replace(result, semantic_fingerprint="0" * 64)


@pytest.mark.parametrize(
    ("profile_name", "category", "target_title", "other_title"),
    [
        ("shower_caddies.v1_1.json", "shower caddies", "Shower Caddy", "Replacement Adhesive Strips Only for Shower Caddy"),
        ("dog_water_bottles.v1_1.json", "dog water bottles", "Portable Dog Water Bottle", "Replacement Filter for Dog Water Bottle"),
        ("vacuum_replacement_filters.v1_1.json", "vacuum replacement filters", "HEPA Vacuum Filter", "Filter Cleaning Brush for Vacuum Filter"),
        ("food_storage_containers.v1_1.json", "food storage containers", "Food Storage Container", "Replacement Lid for Food Storage Container"),
        ("air_fryer_accessories.v1_1.json", "air fryer accessories", "6 Quart Air Fryer with Digital Controls", "Air Fryer Cookbook with Recipes"),
    ],
)
def test_nonprimary_and_obvious_other_never_leak_into_primary_cohort(
    profile_name: str, category: str, target_title: str, other_title: str,
) -> None:
    result = build_semantic_engine_v2_result(
        _dataset(category, (
            ("B000000001", (_field("商品标题", target_title),)),
            ("B000000002", (_field("商品标题", other_title),)),
        )),
        profile=_profile(profile_name),
    )
    other = next(item for item in result.listings if item.listing_reference == "B000000002")
    assert not other.market_cohort_eligibility.eligible_for_primary_cohort
    assert other.market_cohort_eligibility.state in {
        CohortEligibilityState.NON_PRIMARY_EXCLUDED,
        CohortEligibilityState.OFF_TARGET_EXCLUDED,
    }


def test_air_fryer_use_case_mention_alone_does_not_establish_identity() -> None:
    listing = build_semantic_engine_v2_result(
        _dataset("air fryer accessories", (("B000000001", (
            _field("商品标题", "Kitchen Cleaning Tool Works Great with Air Fryer"),
        )),)),
        profile=_profile("air_fryer_accessories.v1_1.json"),
    ).listings[0]
    assert listing.product_identity.status is SemanticDecisionStatus.UNKNOWN
    assert not listing.market_cohort_eligibility.eligible_for_primary_cohort


def test_air_fryer_accessory_and_consumable_are_excluded_from_primary_cohort() -> None:
    result = build_semantic_engine_v2_result(
        _dataset("air fryer accessories", (
            ("B000000001", (_field("商品标题", "Air Fryer Rack for 6 Quart Air Fryer"),)),
            ("B000000002", (_field("商品标题", "Disposable Air Fryer Paper Liners"),)),
        )),
        profile=_profile("air_fryer_accessories.v1_1.json"),
    )
    assert all(not item.market_cohort_eligibility.eligible_for_primary_cohort for item in result.listings)
    assert {item.product_role.relation_role for item in result.listings} == {
        RelationRole.ACCESSORY,
    }
    paper = next(
        item for item in result.listings
        if item.product_role.consumption_lifecycle is ConsumptionLifecycle.CONSUMABLE
    )
    assert paper.product_role.relation_role is RelationRole.ACCESSORY


def test_relation_role_and_lifecycle_cover_frozen_orthogonal_examples() -> None:
    vacuum = build_semantic_engine_v2_result(
        _dataset("vacuum replacement filters", (
            ("B000000001", (_field("商品标题", "Disposable Vacuum Filter Bags"),)),
            ("B000000002", (_field("商品标题", "Replacement Vacuum Filter"),)),
        )),
        profile=_profile("vacuum_replacement_filters.v1_1.json"),
    )
    roles = {
        (item.product_role.relation_role, item.product_role.consumption_lifecycle)
        for item in vacuum.listings
    }
    assert (RelationRole.REFILL, ConsumptionLifecycle.CONSUMABLE) in roles
    assert (
        RelationRole.REPLACEMENT,
        ConsumptionLifecycle.PERIODIC_REPLACEMENT,
    ) in roles

    shower = build_semantic_engine_v2_result(
        _dataset("shower caddies", (("B000000001", (
            _field("商品标题", "Shower Caddy Adhesive Hooks Replacement"),
        )),)),
        profile=_profile("shower_caddies.v1_1.json"),
    ).listings[0]
    assert shower.product_role.relation_role is RelationRole.REPLACEMENT
    assert (
        shower.product_role.consumption_lifecycle
        is ConsumptionLifecycle.REUSABLE_DURABLE
    )


def test_primary_product_with_included_accessories_stays_primary() -> None:
    listing = build_semantic_engine_v2_result(
        _dataset("shower caddies", (("B000000001", (
            _field("商品标题", "Shower Caddy with Soap Dish and Hooks"),
        )),)),
        profile=_profile("shower_caddies.v1_1.json"),
    ).listings[0]
    assert listing.product_role.relation_role is RelationRole.PRIMARY_PRODUCT
    assert listing.market_cohort_eligibility.eligible_for_primary_cohort


def test_provider_category_context_does_not_overwrite_title_identity() -> None:
    listing = build_semantic_engine_v2_result(
        _dataset("dog water bottles", (("B000000001", (
            _field("商品标题", "Portable Dog Water Bottle"),
            _field("类目路径", "Unrelated Provider Placement"),
        )),)),
        profile=_profile("dog_water_bottles.v1_1.json"),
    ).listings[0]
    assert listing.product_identity.normalized_identity == "dog water bottle"
    assert listing.product_identity.is_target_identity is True


def test_quantity_scope_acceptance_and_rejection_are_explicit() -> None:
    listing = build_semantic_engine_v2_result(
        _dataset("food storage containers", (("B000000001", (
            _field("商品标题", "Reusable Food Storage Container"),
            _field("详细参数", "Capacity: 32 fl oz | Number of Pieces: unknown units"),
        )),)),
        profile=_profile("food_storage_containers.v1_1.json"),
    ).listings[0]
    capacity = next(item for item in listing.facts if item.role is UniversalSemanticRole.SIZE_CAPACITY)
    assert capacity.semantic_scope is SemanticScope.ITEM
    assert capacity.quantity_kind == "VOLUME"
    assert not any(item.role is UniversalSemanticRole.QUANTITY for item in listing.facts)
    assert any(item.startswith("MEASUREMENT_REJECTED:food-component-count") for item in listing.limitations)
    assert listing.product_role.relation_role is RelationRole.PRIMARY_PRODUCT
    assert listing.product_role.relation_role is not RelationRole.BUNDLE


def test_host_capacity_is_not_assigned_to_air_fryer_accessory() -> None:
    listing = build_semantic_engine_v2_result(
        _dataset("air fryer accessories", (("B000000001", (
            _field("商品标题", "Air Fryer Rack for 6 Quart Air Fryer"),
            _field("详细参数", "Capacity: 6 qt | Number of Items: 2"),
        )),)),
        profile=_profile("air_fryer_accessories.v1_1.json"),
    ).listings[0]
    assert not any(item.role is UniversalSemanticRole.SIZE_CAPACITY for item in listing.facts)


def test_input_record_field_order_and_import_timestamp_do_not_change_result() -> None:
    fields = (
        _field("商品标题", "Portable Dog Water Bottle One Hand Leak Proof"),
        _field("详细参数", "Capacity: 19 oz | Operation Mode: One Key Lock"),
    )
    first = build_semantic_engine_v2_result(
        _dataset("dog water bottles", (("B000000001", fields),), imported_at="2026-08-29T00:00:00+00:00"),
        profile=_profile("dog_water_bottles.v1_1.json"),
    )
    second = build_semantic_engine_v2_result(
        _dataset("dog water bottles", (("B000000001", tuple(reversed(fields))),), imported_at="2030-01-01T00:00:00+00:00"),
        profile=_profile("dog_water_bottles.v1_1.json"),
    )
    assert first.to_json() == second.to_json()
    assert first.semantic_fingerprint == second.semantic_fingerprint


def test_missing_noncritical_lifecycle_remains_unknown_without_whole_listing_review() -> None:
    listing = build_semantic_engine_v2_result(
        _dataset("dog water bottles", (("B000000001", (
            _field("商品标题", "Portable Dog Water Bottle"),
        )),)),
        profile=_profile("dog_water_bottles.v1_1.json"),
    ).listings[0]
    assert listing.product_role.lifecycle_status is SemanticDecisionStatus.UNKNOWN
    assert listing.product_role.relation_status is SemanticDecisionStatus.GOVERNED
    assert listing.review_reason_codes == ()


def test_malformed_detail_segment_is_a_limitation_not_a_runtime_failure() -> None:
    listing = build_semantic_engine_v2_result(
        _dataset("dog water bottles", (("B000000001", (
            _field("商品标题", "Portable Dog Water Bottle"),
            _field("详细参数", "Capacity: 19 fl oz | malformed segment"),
        )),)),
        profile=_profile("dog_water_bottles.v1_1.json"),
    ).listings[0]
    assert "DETAIL_PARSE_ISSUE:MISSING_KEY_VALUE_DELIMITER" in listing.limitations
    assert any(item.role is UniversalSemanticRole.SIZE_CAPACITY for item in listing.facts)
    assert listing.product_role.relation_status is SemanticDecisionStatus.GOVERNED


def test_cli_fails_closed_on_existing_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "input.csv"
    source.write_text("ASIN,商品标题\nB000000001,Shower Caddy\n", encoding="utf-8-sig")
    output = tmp_path / "result.json"
    output.write_text("reserved", encoding="utf-8")
    exit_code = cli_main([
        "--input", str(source), "--profile", str(PROFILES / "shower_caddies.v1_1.json"),
        "--marketplace", "US", "--category", "shower caddies",
        "--imported-at", "2026-08-29T00:00:00+00:00", "--output", str(output),
    ])
    assert exit_code == 2
    assert "OUTPUT_ALREADY_EXISTS" in capsys.readouterr().out


def test_cli_builds_isolated_deterministic_result(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    source = tmp_path / "input.csv"
    source.write_text(
        "ASIN,商品标题,价格($),月销量,评分,详细参数\n"
        "B000000001,Shower Caddy No Drill,19.99,100,4.5,Installation Type: Adhesive\n",
        encoding="utf-8-sig",
    )
    output = tmp_path / "result.json"
    exit_code = cli_main([
        "--input", str(source), "--profile", str(PROFILES / "shower_caddies.v1_1.json"),
        "--marketplace", "US", "--category", "shower caddies",
        "--imported-at", "2026-08-29T00:00:00+00:00", "--output", str(output),
    ])
    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == "SUCCEEDED"
    assert summary["network_calls"] == 0
    assert summary["llm_authoritative_decisions"] == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["listing_count"] == 1
    assert "Shower Caddy No Drill" not in output.read_text(encoding="utf-8")
