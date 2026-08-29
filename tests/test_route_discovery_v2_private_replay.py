from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from scripts.run_route_discovery_v2_private_replay import (
    BLOCKED_VERDICT,
    EXPECTED_COUNTS,
    FROZEN_METRIC_KEYS,
    PASS_VERDICT,
    CategoryReplay,
    _acceptance_verdict,
    _candidate_quality,
    _external_new_json,
    _manifest,
    _metric_contract_ok,
    _privacy_safe,
    _review_metrics,
    _review_sample,
    _shower_comparison,
)


def _manifest_rows() -> list[dict[str, object]]:
    return [
        {
            "calibration_id": calibration_id,
            "input": f"private-{index}.xlsx",
            "profile": f"profile-{index}.json",
            "route_config": f"route-{index}.json",
            "marketplace": "US",
            "category": f"synthetic-category-{index}",
            "observed_date": "2026-08-29",
            "sheet": None,
        }
        for index, calibration_id in enumerate(reversed(tuple(EXPECTED_COUNTS)))
    ]


def test_manifest_is_strict_complete_and_canonical(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(_manifest_rows()), encoding="utf-8")

    loaded = _manifest(path)

    assert [item["calibration_id"] for item in loaded] == sorted(EXPECTED_COUNTS)
    malformed = _manifest_rows()
    malformed[0].pop("route_config")
    path.write_text(json.dumps(malformed), encoding="utf-8")
    with pytest.raises(ValueError, match="schema mismatch"):
        _manifest(path)


def _route(
    route_id: str,
    members: int,
    tokens: frozenset[tuple[str, str]],
    *,
    facet: str,
) -> SimpleNamespace:
    descriptor = SimpleNamespace(
        role=SimpleNamespace(value="QUANTITY"), dimension="package_count", value=facet,
    )
    by_dimension: dict[str, list[str]] = {}
    for dimension, value in sorted(tokens):
        by_dimension.setdefault(dimension, []).append(json.loads(value))
    defining_features = tuple(
        SimpleNamespace(dimension=dimension, values=tuple(values))
        for dimension, values in sorted(by_dimension.items())
    )
    return SimpleNamespace(
        route_id=route_id, member_count=members, semantic_tokens=tokens,
        defining_features=defining_features,
        secondary_descriptors=(), facet_descriptors=(descriptor,),
    )


def test_candidate_quality_uses_route_semantics_and_aggregate_coverage() -> None:
    routes = (
        _route("r1", 30, frozenset({("installation", '"adhesive"')}), facet="1"),
        _route("r2", 20, frozenset({("installation", '"hanging"')}), facet="2"),
        _route("r3", 10, frozenset({("installation", '"pole"')}), facet="3"),
    )
    result = SimpleNamespace(
        routes=routes,
        candidates=tuple(SimpleNamespace(route_id=item.route_id) for item in routes),
        assigned_count=100,
        listing_count=200,
        candidate_selection_status=SimpleNamespace(value="SELECTED"),
    )

    summary = _candidate_quality(result)

    assert summary["candidate_count"] == 3
    assert summary["candidate_member_count"] == 60
    assert summary["coverage_of_assigned"] == pytest.approx(0.6)
    assert summary["coverage_of_accepted"] == pytest.approx(0.3)
    assert summary["candidate_pairs_without_route_eligible_difference"] == 0
    assert summary["facet_only_distinct_candidate_pair_count"] == 0
    assert summary["three_to_five_or_insufficient_evidence"]


def test_candidate_quality_detects_facet_only_distinct_pair() -> None:
    shared = frozenset({("installation", '"adhesive"')})
    routes = (
        _route("r1", 30, shared, facet="1"),
        _route("r2", 20, shared, facet="9"),
        _route("r3", 10, frozenset({("installation", '"pole"')}), facet="3"),
    )
    result = SimpleNamespace(
        routes=routes,
        candidates=tuple(SimpleNamespace(route_id=item.route_id) for item in routes),
        assigned_count=100,
        listing_count=200,
        candidate_selection_status=SimpleNamespace(value="SELECTED"),
    )

    summary = _candidate_quality(result)

    assert summary["candidate_pairs_without_route_eligible_difference"] == 1
    assert summary["facet_only_distinct_candidate_pair_count"] == 1


def test_candidate_quality_rejects_broad_vs_specific_as_materially_distinct() -> None:
    routes = (
        _route("r1", 30, frozenset({("installation", '"adhesive"')}), facet="1"),
        _route("r2", 20, frozenset({
            ("installation", '"adhesive"'), ("attachment", '"wall"'),
        }), facet="1"),
        _route("r3", 10, frozenset({("installation", '"pole"')}), facet="1"),
    )
    result = SimpleNamespace(
        routes=routes,
        candidates=tuple(SimpleNamespace(route_id=item.route_id) for item in routes),
        assigned_count=100,
        listing_count=200,
        candidate_selection_status=SimpleNamespace(value="SELECTED"),
    )

    summary = _candidate_quality(result)

    assert summary["candidate_pairs_without_route_eligible_difference"] == 1
    assert summary["facet_only_distinct_candidate_pair_count"] == 0


def test_frozen_shower_thresholds_are_exact() -> None:
    summary = {
        "accepted_listing_count": 998,
        "assigned_count": 594,
        "assigned_rate": 0.595190,
        "unclassified_count": 281,
        "unclassified_rate": 0.281563,
        "review_required_count": 69,
        "review_required_rate": 0.069640,
        "size_2_route_count": 5,
        "size_2_route_share": 0.281250,
        "route_count": 20,
        "route_deterministic_match": True,
        "candidate": {
            "candidate_count": 3,
            "candidate_member_count": 100,
            "coverage_of_assigned": 0.276094,
            "coverage_of_accepted": 0.082164,
        },
    }

    comparison = _shower_comparison(summary)

    assert comparison["all_frozen_quantitative_gates_passed"]
    failed = _shower_comparison({**summary, "assigned_rate": 0.595189})
    assert not failed["frozen_quantitative_gates"]["assigned_rate"]["passed"]


def test_frozen_metric_contract_accepts_immutable_mapping_values() -> None:
    metrics = []
    for name in sorted(FROZEN_METRIC_KEYS):
        value = None
        if name in {"mom_aggregate_growth", "yoy_aggregate_growth"}:
            value = MappingProxyType({
                "aggregation": "SUM_CURRENT_DIV_SUM_RECONSTRUCTED_PRIOR_MINUS_ONE",
            })
        elif name in {"review_count_distribution", "price_distribution"}:
            value = MappingProxyType({"method": "NEAREST_RANK"})
        metrics.append((name, SimpleNamespace(value=value)))
    result = SimpleNamespace(routes=(SimpleNamespace(metrics=tuple(metrics)),))

    assert _metric_contract_ok(result)


def _sample_replays() -> dict[str, CategoryReplay]:
    definition = SimpleNamespace(
        to_dict=lambda: {
            "role": "INSTALLATION_ARCHITECTURE",
            "dimension": "installation_architecture",
            "values": ["synthetic-anchor"],
        },
    )
    route = SimpleNamespace(
        route_id="synthetic-route", member_listing_references=("SYNTHETIC-001",),
        defining_features=(definition,), member_count=1,
        feature_coverage=(("installation_architecture", 0.5),),
        secondary_descriptors=(), facet_descriptors=(),
    )
    membership = SimpleNamespace(
        listing_reference="SYNTHETIC-001", assignment_features=(definition,),
    )
    route_result = SimpleNamespace(
        routes=(route,), candidates=(SimpleNamespace(
            route_id="synthetic-route", reason_codes=("DEMAND_EFFICIENCY",),
        ),),
        memberships=(membership,),
        assigned_count=1, listing_count=1,
    )
    field = SimpleNamespace(header="\u5546\u54c1\u6807\u9898", value="Synthetic item")
    dataset = SimpleNamespace(
        records=(SimpleNamespace(asin="SYNTHETIC-001", fields=(field,)),),
    )
    semantic_listing = SimpleNamespace(
        listing_reference="SYNTHETIC-001",
        product_identity=SimpleNamespace(normalized_identity="synthetic identity"),
        product_role=SimpleNamespace(
            relation_role=SimpleNamespace(value="PRIMARY_PRODUCT"),
        ),
        market_cohort_eligibility=SimpleNamespace(
            state=SimpleNamespace(value="PRIMARY_COHORT_ELIGIBLE"),
        ),
    )
    semantic_result = SimpleNamespace(listings=(semantic_listing,))
    replay = CategoryReplay(
        calibration_id="CAL_SHOWER_CADDY", dataset=dataset,
        semantic_result=semantic_result, route_result=route_result,
        profile=None, route_config=SimpleNamespace(min_route_size=1),
        semantic_deterministic=True,
        route_deterministic=True, runtime_seconds={},
    )
    return {"CAL_SHOWER_CADDY": replay}


def test_private_review_sample_has_blank_human_decisions_and_validates_explicit_work(
    tmp_path: Path,
) -> None:
    sample = _review_sample(_sample_replays())

    assert sample["sampling"]["row_count"] == 1
    assert sample["sampling"]["sampled_route_count"] == 1
    assert set(sample["rows"][0]["review_strata"]) == {
        "CANDIDATE_ROUTE", "LARGEST_ROUTE", "BOUNDARY_MIN_SIZE_ROUTE",
        "SPARSE_ROUTE",
    }
    review = sample["rows"][0]["human_review"]
    assert all(value is None for key, value in review.items() if key != "notes")
    assert review["notes"] == ""

    completed = json.loads(json.dumps(sample))
    for key in completed["rows"][0]["human_review"]:
        if key != "notes":
            completed["rows"][0]["human_review"][key] = True
    path = tmp_path / "completed.json"
    path.write_text(json.dumps(completed), encoding="utf-8")

    metrics = _review_metrics(path, sample)

    assert metrics["completed_review_supplied"]
    assert metrics["intra_route_consistency_rate"] == 1.0
    assert metrics["candidate_minimum_business_sense_passed"]
    assert metrics["all_reviewed_route_safety_checks_passed"]

    completed["rows"][0]["human_review"]["coherent_product_identity"] = False
    unsafe_path = tmp_path / "unsafe.json"
    unsafe_path.write_text(json.dumps(completed), encoding="utf-8")
    unsafe = _review_metrics(unsafe_path, sample)
    assert not unsafe["all_reviewed_route_safety_checks_passed"]


def test_missing_or_blank_human_review_cannot_pass(tmp_path: Path) -> None:
    sample = _review_sample(_sample_replays())

    missing = _review_metrics(None, sample)

    assert missing["intra_route_consistency_rate"] is None
    assert not missing["candidate_minimum_business_sense_passed"]
    assert _acceptance_verdict({"quantitative": True, "human_review": False}) == (
        BLOCKED_VERDICT
    )

    path = tmp_path / "blank.json"
    path.write_text(json.dumps(sample), encoding="utf-8")
    with pytest.raises(ValueError, match="explicit booleans"):
        _review_metrics(path, sample)


def test_review_basis_cannot_be_modified(tmp_path: Path) -> None:
    sample = _review_sample(_sample_replays())
    completed = json.loads(json.dumps(sample))
    completed["rows"][0]["listing_reference"] = "CHANGED"
    for key in completed["rows"][0]["human_review"]:
        completed["rows"][0]["human_review"][key] = (
            "" if key == "notes" else True
        )
    path = tmp_path / "changed.json"
    path.write_text(json.dumps(completed), encoding="utf-8")

    with pytest.raises(ValueError, match="basis was modified"):
        _review_metrics(path, sample)


def test_private_review_output_is_forced_outside_repository(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    with pytest.raises(ValueError, match="outside the repository"):
        _external_new_json(
            repo_root / "synthetic-private-review.json", repo_root=repo_root,
        )

    external = tmp_path / "synthetic-private-review.json"
    _external_new_json(external, repo_root=repo_root)


def test_aggregate_privacy_scan_and_verdict_are_fail_closed() -> None:
    assert _privacy_safe({"categories": {"CAL_SHOWER_CADDY": {"count": 998}}})
    assert not _privacy_safe({"listing_reference": "B012345678"})
    assert not _privacy_safe({"detail": "C:\\private\\asset.xlsx"})
    assert not _privacy_safe({"brand": "private brand"})
    assert not _privacy_safe({"api_key": "not-a-real-secret"})
    assert _acceptance_verdict({"a": True, "b": True}) == PASS_VERDICT
    assert _acceptance_verdict({}) == BLOCKED_VERDICT
