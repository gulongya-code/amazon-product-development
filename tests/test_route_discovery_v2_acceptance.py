from __future__ import annotations

from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from amazon_product_intelligence.product_route_opportunity.models import MembershipStatus
from amazon_product_intelligence.route_discovery_v2 import (
    CandidateRouteV2,
    RouteDiscoveryV2Error,
    build_route_discovery_v2,
    load_route_discovery_v2_config,
    validate_route_v2_authority,
)
from amazon_product_intelligence.route_discovery_v2.models import (
    build_semantic_route_feature,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    SemanticEngineV2Error,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from amazon_product_intelligence.semantic_engine_v2.models import (
    RoleRelevance,
    UniversalSemanticRole,
)
from scripts import run_route_discovery_v2_private_replay as replay
from tests.test_route_discovery_v2 import (
    CONFIGS,
    DETAIL,
    PROFILES,
    ROOT,
    TITLE,
    _architecture_records,
    _build,
    _dataset,
    _record,
)


CONFIG_ACCEPTANCE = (
    (
        "air_fryers.v2.json",
        "air_fryer_accessories.v1_1.json",
        "65bf8f75e8130d0f4b46fa19d43f391647a0472f587ed9d13f4b2392d27c69bc",
        ("structural_form", "operation_mechanism"),
        ("consumable_unit_count",),
    ),
    (
        "dog_water_bottles.v2.json",
        "dog_water_bottles.v1_1.json",
        "7aea673fff8e1649cd2ac99d0b509c9d1aa61769dd196ad7d2b35c500c5ba620",
        ("operation_mechanism",),
        ("item_capacity", "package_count"),
    ),
    (
        "food_storage_containers.v2.json",
        "food_storage_containers.v1_1.json",
        "4a2dd049d3c0bd90c8cb223b08da82299a6ad382ef75929a4ac8a7bb5da1fea2",
        ("structural_form",),
        ("item_capacity", "structural_component_count"),
    ),
    (
        "shower_caddies.v2.json",
        "shower_caddies.v1_1.json",
        "cb863460d239978e461d4902906a5a7171e5069a820cb0305b09ad818de3edc3",
        ("installation_architecture", "attachment_mechanism"),
        ("package_count",),
    ),
    (
        "vacuum_replacement_filters.v2.json",
        "vacuum_replacement_filters.v1_1.json",
        "80a9b88f5822a3b22c1dcbac9de2abc4ce4be005a2b7e6b1f0714c9f7b82c2f1",
        ("compatibility",),
        ("material", "consumable_unit_count"),
    ),
)


def test_route_feature_rejects_unsupported_defining_claim_without_evidence() -> None:
    """A route-defining value must never exist without attributable S2 evidence."""

    with pytest.raises(RouteDiscoveryV2Error, match="defining values require facts and evidence"):
        build_semantic_route_feature(
            role=UniversalSemanticRole.INSTALLATION_ARCHITECTURE,
            dimension="installation_architecture",
            values=("adhesive",),
            defining_values=("adhesive",),
            profile_id="acceptance-profile",
            profile_version="1.0",
            profile_fingerprint="a" * 64,
            source_policy_id="acceptance-policy",
            relevance=RoleRelevance.CORE,
            route_critical=False,
            exact_specification=False,
            multi_value=True,
            fact_ids=(),
            defining_fact_ids=(),
            evidence_ids=(),
            relationship_ids=(),
            relationship_states=(),
            limitations=(),
        )

    with pytest.raises(RouteDiscoveryV2Error, match="must reference observed feature facts"):
        build_semantic_route_feature(
            role=UniversalSemanticRole.INSTALLATION_ARCHITECTURE,
            dimension="installation_architecture",
            values=("adhesive",),
            defining_values=("adhesive",),
            profile_id="acceptance-profile",
            profile_version="1.0",
            profile_fingerprint="a" * 64,
            source_policy_id="acceptance-policy",
            relevance=RoleRelevance.CORE,
            route_critical=False,
            exact_specification=False,
            multi_value=True,
            fact_ids=("semantic-fact:observed",),
            defining_fact_ids=("semantic-fact:unsupported",),
            evidence_ids=("semantic-evidence:observed",),
            relationship_ids=(),
            relationship_states=(),
            limitations=(),
        )


def test_all_and_only_current_category_configs_have_frozen_authority() -> None:
    assert {path.name for path in CONFIGS.glob("*.json")} == {
        item[0] for item in CONFIG_ACCEPTANCE
    }
    identities: set[str] = set()
    category_names: set[str] = set()
    for config_name, profile_name, fingerprint, route_dimensions, descriptors in (
        CONFIG_ACCEPTANCE
    ):
        config = load_route_discovery_v2_config(CONFIGS / config_name)
        profile = load_category_semantic_profile(PROFILES / profile_name)
        validate_route_v2_authority(config, profile, config.category)
        assert config.fingerprint == fingerprint
        assert config.route_dimensions == route_dimensions
        assert config.descriptor_dimensions == descriptors
        assert config.promoted_secondary_dimensions == ()
        assert set(config.adoption_dimensions) == {
            *config.route_dimensions,
            *config.descriptor_dimensions,
        }
        assert config.identity not in identities
        identities.add(config.identity)
        scoped_names = {config.category, *config.category_aliases}
        assert not category_names & scoped_names
        category_names.update(scoped_names)


def test_category_configs_are_isolated_from_every_other_current_category() -> None:
    configs = [
        load_route_discovery_v2_config(CONFIGS / item[0])
        for item in CONFIG_ACCEPTANCE
    ]
    profiles = [
        load_category_semantic_profile(PROFILES / item[1])
        for item in CONFIG_ACCEPTANCE
    ]
    for config, profile in zip(configs, profiles, strict=True):
        for other in configs:
            if other is config:
                continue
            with pytest.raises(RouteDiscoveryV2Error) as caught:
                validate_route_v2_authority(config, profile, other.category)
            assert caught.value.code == "ROUTE_V2_CATEGORY_MISMATCH"


def test_empty_and_single_product_inputs_do_not_manufacture_routes() -> None:
    *_, empty = _build(())
    assert empty.listing_count == 0
    assert empty.assigned_count == empty.unclassified_count == 0
    assert empty.review_required_count == 0
    assert empty.routes == empty.candidates == ()
    assert empty.candidate_selection_status.value == "INSUFFICIENT_EVIDENCE"

    *_, single = _build((
        _record(1, detail="Installation: Adhesive | Attachment: Wall"),
    ))
    assert single.listing_count == 1
    assert single.assigned_count == 0
    assert single.unclassified_count == 1
    assert single.routes == ()


def test_duplicate_product_and_duplicate_route_identities_fail_closed() -> None:
    record = _record(1, detail="Installation: Adhesive | Attachment: Wall")
    dataset = _dataset((record, record))
    profile = load_category_semantic_profile(PROFILES / "shower_caddies.v1_1.json")
    with pytest.raises(SemanticEngineV2Error, match="duplicate listing identities"):
        build_semantic_engine_v2_result(dataset, profile=profile)

    *_, result = _build(_architecture_records((("Adhesive", "Wall", 3),)))
    with pytest.raises(RouteDiscoveryV2Error, match="duplicate route"):
        replace(result, routes=(result.routes[0], result.routes[0]))


def test_missing_required_identity_is_not_admitted_to_a_route() -> None:
    record = _record(1, detail="Installation: Adhesive | Attachment: Wall")
    record = replace(
        record,
        fields=tuple(field for field in record.fields if field.header != TITLE),
    )
    dataset = _dataset((record,))
    profile = load_category_semantic_profile(PROFILES / "shower_caddies.v1_1.json")
    semantic = build_semantic_engine_v2_result(dataset, profile=profile)
    config = load_route_discovery_v2_config(CONFIGS / "shower_caddies.v2.json")
    result = build_route_discovery_v2(
        dataset, semantic, profile=profile, config=config,
    )

    assert semantic.listings[0].product_identity.normalized_identity is None
    assert result.assigned_count == 0
    assert result.memberships[0].status is not MembershipStatus.ASSIGNED
    assert result.memberships[0].primary_route_id is None


def test_missing_optional_market_signals_preserve_route_identity_without_imputation() -> None:
    records = []
    for index in range(1, 4):
        record = _record(
            index, detail="Installation: Adhesive | Attachment: Wall",
        )
        records.append(replace(
            record,
            fields=tuple(
                field for field in record.fields if field.header in {TITLE, DETAIL}
            ),
        ))
    *_, result = _build(tuple(records))

    assert result.assigned_count == 3
    assert len(result.routes) == 1
    route = result.routes[0]
    assert route.metric("route_sales_share").value is None
    assert route.metric("price_distribution").value is None


def test_malformed_observations_remain_explicitly_unclassified() -> None:
    records = tuple(
        _record(index, detail="malformed observation without a key value separator")
        for index in range(1, 4)
    )
    *_, result = _build(records)

    assert result.assigned_count == 0
    assert result.unclassified_count == 3
    assert result.routes == ()
    assert all(
        "INSUFFICIENT_PROFILE_AUTHORIZED_ROUTE_SEMANTICS"
        in membership.membership_reason_codes
        for membership in result.memberships
    )


def test_engine_output_claims_resolve_to_exact_s2_facts_and_evidence() -> None:
    records = tuple(
        _record(
            index,
            title="Shower Caddy No Drill",
            detail="Installation: Adhesive | Attachment: Wall",
        )
        for index in range(1, 4)
    )
    _, _, semantic, _, result = _build(records)
    semantic_by_listing = {
        listing.listing_reference: listing for listing in semantic.listings
    }
    view_by_listing = {
        view.listing_reference: view for view in result.feature_views
    }
    membership_by_id = {
        membership.membership_id: membership for membership in result.memberships
    }

    for view in result.feature_views:
        listing = semantic_by_listing[view.listing_reference]
        facts = {fact.fact_id: fact for fact in listing.facts}
        evidence_ids = {item.evidence_id for item in listing.evidence}
        for feature in view.features:
            assert set(feature.fact_ids) <= set(facts)
            assert set(feature.defining_fact_ids) <= set(feature.fact_ids)
            assert set(feature.evidence_ids) <= evidence_ids
            assert {
                json.dumps(facts[fact_id].normalized_value, sort_keys=True)
                for fact_id in feature.fact_ids
            } == {
                json.dumps(value, sort_keys=True) for value in feature.values
            }
            assert {
                json.dumps(facts[fact_id].normalized_value, sort_keys=True)
                for fact_id in feature.defining_fact_ids
            } == {
                json.dumps(value, sort_keys=True)
                for value in feature.defining_values
            }

    for membership in result.memberships:
        view = view_by_listing[membership.listing_reference]
        expected_evidence = {
            evidence_id
            for key in membership.assignment_features
            for evidence_id in view.feature(key.dimension).evidence_ids
        }
        assert set(membership.evidence_ids) == expected_evidence
    for route in result.routes:
        assert set(route.assignment_evidence_ids) == {
            evidence_id
            for membership_id in route.membership_ids
            for evidence_id in membership_by_id[membership_id].evidence_ids
        }


def test_unknown_route_references_are_rejected_by_result_contract() -> None:
    *_, result = _build(_architecture_records((("Adhesive", "Wall", 3),)))
    unknown = CandidateRouteV2(
        priority=1,
        route_id="product-route-v2:unknown",
        reason_codes=("ACCEPTANCE_PROBE",),
        minimum_semantic_distance_to_prior=None,
    )
    with pytest.raises(RouteDiscoveryV2Error, match="candidate references unknown route"):
        replace(result, candidates=(unknown,))


def test_hash_seed_process_independence_preserves_full_result() -> None:
    program = """
from tests.test_route_discovery_v2 import _architecture_records, _build
records = _architecture_records(((\"Adhesive\", \"Wall\", 3), (\"Hanging\", \"Hook\", 3)))
print(_build(records)[-1].to_json())
"""
    outputs = []
    for seed in ("7", "7001"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", program],
            cwd=ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1]


def test_private_replay_discloses_data_mode_and_disables_synthetic_fallback() -> None:
    assert replay.REPLAY_DISCLOSURE == {
        "execution_mode": "OFFLINE_PRIVATE_REPLAY",
        "input_data_classification": "CALLER_DECLARED_EXTERNAL_PRIVATE_CALIBRATION",
        "live_provider_access_enabled": False,
        "fixture_mode_enabled": False,
        "synthetic_fallback_enabled": False,
    }
    runner_source = Path(replay.__file__).read_text(encoding="utf-8")
    assert '"data_disclosure": dict(REPLAY_DISCLOSURE)' in runner_source


def test_private_replay_propagates_missing_input_without_synthetic_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest_rows = []
    profiles = {
        "CAL_AIR_FRYER_MIXED": "air_fryer_accessories.v1_1.json",
        "CAL_DOG_WATER_BOTTLE": "dog_water_bottles.v1_1.json",
        "CAL_FOOD_STORAGE_SET": "food_storage_containers.v1_1.json",
        "CAL_SHOWER_CADDY": "shower_caddies.v1_1.json",
        "CAL_VACUUM_FILTER": "vacuum_replacement_filters.v1_1.json",
    }
    configs = {
        "CAL_AIR_FRYER_MIXED": "air_fryers.v2.json",
        "CAL_DOG_WATER_BOTTLE": "dog_water_bottles.v2.json",
        "CAL_FOOD_STORAGE_SET": "food_storage_containers.v2.json",
        "CAL_SHOWER_CADDY": "shower_caddies.v2.json",
        "CAL_VACUUM_FILTER": "vacuum_replacement_filters.v2.json",
    }
    categories = {
        "CAL_AIR_FRYER_MIXED": "air fryers",
        "CAL_DOG_WATER_BOTTLE": "dog water bottles",
        "CAL_FOOD_STORAGE_SET": "food storage containers",
        "CAL_SHOWER_CADDY": "shower caddies",
        "CAL_VACUUM_FILTER": "vacuum replacement filters",
    }
    for calibration_id in replay.EXPECTED_COUNTS:
        manifest_rows.append({
            "calibration_id": calibration_id,
            "input": str(tmp_path / f"{calibration_id}.xlsx"),
            "profile": str(PROFILES / profiles[calibration_id]),
            "route_config": str(CONFIGS / configs[calibration_id]),
            "marketplace": "US",
            "category": categories[calibration_id],
            "observed_date": "2026-08-29",
            "sheet": None,
        })
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(manifest_rows), encoding="utf-8")
    original_manifest = manifest.read_bytes()
    calls = []

    def missing_input(path: str, **_: object) -> object:
        calls.append(path)
        raise FileNotFoundError(path)

    monkeypatch.setattr(replay, "import_sellersprite_file", missing_input)
    with pytest.raises(FileNotFoundError):
        replay.run_private_replay(manifest)

    assert len(calls) == 1
    assert manifest.read_bytes() == original_manifest


def test_private_replay_cli_never_overwrites_existing_aggregate_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "aggregate.json"
    output.write_text("preserve-me", encoding="utf-8")

    def must_not_run(*_: object, **__: object) -> object:
        raise AssertionError("replay must not start when output already exists")

    monkeypatch.setattr(replay, "run_private_replay", must_not_run)
    exit_code = replay.main([
        "--manifest", str(tmp_path / "not-read.json"),
        "--output", str(output),
    ])

    assert exit_code == 2
    assert output.read_text(encoding="utf-8") == "preserve-me"
    public_status = json.loads(capsys.readouterr().out)
    assert public_status == {
        "error": "ROUTE_V2_UNSAFE_OUTPUT",
        "status": "FAILED",
    }
