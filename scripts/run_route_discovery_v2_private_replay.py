"""Run the privacy-safe five-category TASK-SP-041R2 acceptance replay.

Private listing workbooks and human-review rows stay outside the repository.
The primary output contains aggregate statistics only.  An optional, explicitly
external JSON review sample may contain listing-grain material for a human
operator; every human decision in that sample is left blank.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, replace
from hashlib import sha256
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.route_discovery_v2 import (
    RouteDiscoveryV2Error,
    build_route_discovery_v2,
    load_route_discovery_v2_config,
)
from amazon_product_intelligence.semantic_engine_v2 import (
    SemanticEngineV2Error,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from amazon_product_intelligence.sellersprite_import import (
    ImportContext,
    import_sellersprite_file,
)


EXPECTED_COUNTS = {
    "CAL_SHOWER_CADDY": 998,
    "CAL_DOG_WATER_BOTTLE": 400,
    "CAL_VACUUM_FILTER": 300,
    "CAL_FOOD_STORAGE_SET": 150,
    "CAL_AIR_FRYER_MIXED": 300,
}
EXPECTED_PRIMARY_COHORT_COUNTS = {
    "CAL_SHOWER_CADDY": 868,
    "CAL_DOG_WATER_BOTTLE": 280,
    "CAL_VACUUM_FILTER": 0,
    "CAL_FOOD_STORAGE_SET": 99,
    "CAL_AIR_FRYER_MIXED": 162,
}
EXPECTED_PROFILE_FINGERPRINTS = {
    "CAL_SHOWER_CADDY": "d08a2a441d0746767dd0e0f0a35bd26675256c82f26cda1821a488b039ca9aa1",
    "CAL_DOG_WATER_BOTTLE": "3bfa600c6659721fe133d27c866efdb8ed3ea0ac5d4623ed3055f16213c30173",
    "CAL_VACUUM_FILTER": "bfeb66f3c065394acba8c3bd55672b8c349ebe58289eff203105310061320764",
    "CAL_FOOD_STORAGE_SET": "097097108b11b88af72b3f0d1d81fb743dc3f8895176d0ec086980b87464339c",
    "CAL_AIR_FRYER_MIXED": "d3a4e29090ce5e50872f2b53087d7423b6bc0295cf74e43e6b5d8549f2c8fe76",
}
EXPECTED_ROUTE_CONFIG_FINGERPRINTS = {
    "CAL_SHOWER_CADDY": "cb863460d239978e461d4902906a5a7171e5069a820cb0305b09ad818de3edc3",
    "CAL_DOG_WATER_BOTTLE": "7aea673fff8e1649cd2ac99d0b509c9d1aa61769dd196ad7d2b35c500c5ba620",
    "CAL_VACUUM_FILTER": "80a9b88f5822a3b22c1dcbac9de2abc4ce4be005a2b7e6b1f0714c9f7b82c2f1",
    "CAL_FOOD_STORAGE_SET": "4a2dd049d3c0bd90c8cb223b08da82299a6ad382ef75929a4ac8a7bb5da1fea2",
    "CAL_AIR_FRYER_MIXED": "65bf8f75e8130d0f4b46fa19d43f391647a0472f587ed9d13f4b2392d27c69bc",
}
SHOWER_CALIBRATION_ID = "CAL_SHOWER_CADDY"
MANIFEST_KEYS = frozenset((
    "calibration_id", "input", "profile", "route_config", "marketplace",
    "category", "observed_date", "sheet",
))
FROZEN_METRIC_KEYS = frozenset((
    "route_listing_share", "route_sales_share", "demand_efficiency",
    "mom_aggregate_growth", "yoy_aggregate_growth",
    "new_product_listing_share", "new_product_sales_share",
    "new_product_demand_efficiency", "review_count_distribution",
    "price_distribution", "brand_listing_concentration",
    "brand_sales_concentration", "seller_listing_concentration",
    "seller_sales_concentration", "product_sales_concentration",
    "structural_feature_adoption",
))
GENERIC_CATEGORY_LITERALS = (
    "shower caddy", "dog water bottle", "vacuum filter",
    "food storage", "air fryer",
)
REVIEW_CONTRACT = "route-v2-human-review-sample-v1.0"
REVIEW_SAMPLE_PER_ROUTE = 3
REVIEW_MAX_ROWS = 209
REVIEW_DECISION_KEYS = (
    "coherent_product_identity",
    "coherent_relation_role_cohort",
    "route_eligible_structural_distinction",
    "accessory_off_target_leakage_absent",
    "facet_only_route_identity_absent",
    "intra_route_consistent",
)
TITLE_HEADER = "\u5546\u54c1\u6807\u9898"
BLOCKED_VERDICT = "BLOCKED \u2014 ROUTE_V2_ACCEPTANCE_GATE_FAILED"
PASS_VERDICT = "PASS \u2014 ROUTE_DISCOVERY_V2"
REPLAY_DISCLOSURE = {
    "execution_mode": "OFFLINE_PRIVATE_REPLAY",
    "input_data_classification": "CALLER_DECLARED_EXTERNAL_PRIVATE_CALIBRATION",
    "live_provider_access_enabled": False,
    "fixture_mode_enabled": False,
    "synthetic_fallback_enabled": False,
}

SHOWER_V1 = {
    "accepted_listing_count": 998,
    "assigned_count": 297,
    "assigned_rate": 0.297595,
    "unclassified_count": 562,
    "unclassified_rate": 0.563126,
    "review_required_count": 139,
    "review_required_rate": 0.139279,
    "route_count": 80,
    "size_2_route_count": 45,
    "size_2_route_share": 0.5625,
    "candidate_member_count": 41,
    "candidate_coverage_of_assigned": 0.138047,
    "candidate_coverage_of_accepted": 0.041082,
    "bounded_structural_sample_count": 209,
    "bounded_structural_sample_mismatch_count": 0,
    "repeated_route_fingerprint_mismatch_count": 0,
}
SHOWER_FLOORS = {
    "assigned_rate": (">=", 0.595190),
    "unclassified_rate": ("<=", 0.281563),
    "review_required_rate": ("<=", 0.069640),
    "size_2_route_share": ("<=", 0.281250),
    "candidate_coverage_of_assigned": (">=", 0.276094),
    "candidate_coverage_of_accepted": (">=", 0.082164),
}


@dataclass(frozen=True, slots=True)
class CategoryReplay:
    calibration_id: str
    dataset: Any
    semantic_result: Any
    route_result: Any
    profile: Any
    route_config: Any
    semantic_deterministic: bool
    route_deterministic: bool
    runtime_seconds: Mapping[str, float]


def _error(code: str, detail: str) -> RouteDiscoveryV2Error:
    return RouteDiscoveryV2Error(code, detail)


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise _error("ROUTE_V2_PRIVATE_INPUT_INVALID", "private JSON is unreadable") from exc


def _manifest(path: Path) -> tuple[dict[str, Any], ...]:
    payload = _load_json(path)
    if not isinstance(payload, list) or len(payload) != len(EXPECTED_COUNTS):
        raise _error(
            "ROUTE_V2_PRIVATE_INPUT_INVALID", "manifest must contain five entries",
        )
    entries: list[dict[str, Any]] = []
    for raw in payload:
        if not isinstance(raw, dict) or set(raw) != MANIFEST_KEYS:
            raise _error("ROUTE_V2_PRIVATE_INPUT_INVALID", "manifest schema mismatch")
        if raw["calibration_id"] not in EXPECTED_COUNTS:
            raise _error("ROUTE_V2_PRIVATE_INPUT_INVALID", "unknown calibration ID")
        for key in ("input", "profile", "route_config", "marketplace", "category"):
            if not isinstance(raw[key], str) or not raw[key].strip():
                raise _error("ROUTE_V2_PRIVATE_INPUT_INVALID", "manifest text is blank")
        if raw["observed_date"] is not None and not isinstance(raw["observed_date"], str):
            raise _error("ROUTE_V2_PRIVATE_INPUT_INVALID", "observed_date is invalid")
        if raw["sheet"] is not None and not isinstance(raw["sheet"], str):
            raise _error("ROUTE_V2_PRIVATE_INPUT_INVALID", "sheet is invalid")
        entries.append(raw)
    identities = [item["calibration_id"] for item in entries]
    if len(identities) != len(set(identities)) or set(identities) != set(EXPECTED_COUNTS):
        raise _error(
            "ROUTE_V2_PRIVATE_INPUT_INVALID", "calibration IDs must be unique and complete",
        )
    return tuple(sorted(entries, key=lambda item: item["calibration_id"]))


def _rate(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _route_size_histogram(routes: tuple[Any, ...]) -> list[dict[str, int]]:
    counts = Counter(route.member_count for route in routes)
    return [
        {"member_count": size, "route_count": count}
        for size, count in sorted(counts.items())
    ]


def _descriptor_tokens(route: Any) -> frozenset[str]:
    descriptors = (*route.secondary_descriptors, *route.facet_descriptors)
    return frozenset(
        canonical_json({
            "role": item.role.value, "dimension": item.dimension, "value": item.value,
        })
        for item in descriptors
    )


def _definition_value_sets(route: Any) -> dict[str, frozenset[str]]:
    return {
        item.dimension: frozenset(canonical_json(value) for value in item.values)
        for item in route.defining_features
    }


def _materially_distinct(left: Any, right: Any) -> bool:
    """Require an explicit incompatible value on a shared route dimension."""

    left_values = _definition_value_sets(left)
    right_values = _definition_value_sets(right)
    return any(
        left_values[dimension].isdisjoint(right_values[dimension])
        for dimension in sorted(set(left_values) & set(right_values))
    )


def _candidate_quality(result: Any) -> dict[str, Any]:
    routes = {route.route_id: route for route in result.routes}
    candidate_routes = [routes[item.route_id] for item in result.candidates]
    no_eligible_difference = 0
    facet_only_pairs = 0
    pair_count = 0
    for index, left in enumerate(candidate_routes):
        for right in candidate_routes[index + 1:]:
            pair_count += 1
            if _materially_distinct(left, right):
                continue
            no_eligible_difference += 1
            if _descriptor_tokens(left) != _descriptor_tokens(right):
                facet_only_pairs += 1
    candidate_member_count = sum(route.member_count for route in candidate_routes)
    candidate_count_valid = (
        3 <= len(candidate_routes) <= 5
        if candidate_routes
        else result.candidate_selection_status.value == "INSUFFICIENT_EVIDENCE"
    )
    return {
        "selection_status": result.candidate_selection_status.value,
        "candidate_count": len(candidate_routes),
        "candidate_member_count": candidate_member_count,
        "coverage_of_assigned": _rate(candidate_member_count, result.assigned_count),
        "coverage_of_accepted": _rate(candidate_member_count, result.listing_count),
        "candidate_pair_count": pair_count,
        "candidate_pairs_without_route_eligible_difference": no_eligible_difference,
        "facet_only_distinct_candidate_pair_count": facet_only_pairs,
        "three_to_five_or_insufficient_evidence": candidate_count_valid,
    }


def _metric_contract_ok(result: Any) -> bool:
    for route in result.routes:
        metrics = dict(route.metrics)
        if set(metrics) != FROZEN_METRIC_KEYS:
            return False
        for key in ("mom_aggregate_growth", "yoy_aggregate_growth"):
            value = metrics[key].value
            if value is not None and (
                not isinstance(value, Mapping)
                or value.get("aggregation")
                != "SUM_CURRENT_DIV_SUM_RECONSTRUCTED_PRIOR_MINUS_ONE"
            ):
                return False
        for key in ("review_count_distribution", "price_distribution"):
            value = metrics[key].value
            if value is not None and (
                not isinstance(value, Mapping) or value.get("method") != "NEAREST_RANK"
            ):
                return False
    return True


def _category_summary(replay: CategoryReplay) -> dict[str, Any]:
    result = replay.route_result
    routes = result.routes
    candidate = _candidate_quality(result)
    views = {item.listing_reference: item for item in result.feature_views}
    nonprimary_assigned = sum(
        membership.status.value == "ASSIGNED"
        and not views[membership.listing_reference].eligible_for_primary_cohort
        for membership in result.memberships
    )
    invalid_route_dimensions = sum(
        key.dimension not in replay.route_config.route_dimensions
        for route in routes for key in route.defining_features
    )
    dimensions = {}
    for dimension in replay.route_config.route_dimensions:
        eligible = [view for view in result.feature_views if view.eligible_for_primary_cohort]
        defining = sum(
            (feature := view.feature(dimension)) is not None
            and bool(feature.defining_values)
            for view in eligible
        )
        dimensions[dimension] = {
            "eligible_listing_count": len(eligible),
            "defining_fact_listing_count": defining,
            "defining_fact_coverage": _rate(defining, len(eligible)),
        }
    defining_roles: Counter[str] = Counter()
    defining_role_members: Counter[str] = Counter()
    defining_dimensions: Counter[str] = Counter()
    defining_dimension_members: Counter[str] = Counter()
    for route in routes:
        for role in {item.role.value for item in route.defining_features}:
            defining_roles[role] += 1
            defining_role_members[role] += route.member_count
        for dimension in {item.dimension for item in route.defining_features}:
            defining_dimensions[dimension] += 1
            defining_dimension_members[dimension] += route.member_count
    diagnostics = dict(result.diagnostics)
    semantic_primary_count = sum(
        listing.market_cohort_eligibility.eligible_for_primary_cohort
        for listing in replay.semantic_result.listings
    )
    s2_authority_match = (
        result.upstream_semantic_result_id == replay.semantic_result.result_id
        and result.upstream_semantic_fingerprint
        == replay.semantic_result.semantic_fingerprint
        and result.semantic_profile_id == replay.semantic_result.profile_id
        and result.semantic_profile_version == replay.semantic_result.profile_version
        and result.semantic_profile_fingerprint
        == replay.semantic_result.profile_fingerprint
        and result.primary_cohort_eligible_count == semantic_primary_count
    )
    calibrated_authority_match = (
        replay.profile.fingerprint
        == EXPECTED_PROFILE_FINGERPRINTS[replay.calibration_id]
        and replay.route_config.fingerprint
        == EXPECTED_ROUTE_CONFIG_FINGERPRINTS[replay.calibration_id]
        and result.primary_cohort_eligible_count
        == EXPECTED_PRIMARY_COHORT_COUNTS[replay.calibration_id]
    )
    candidate_reason_codes = Counter(
        reason for candidate_item in result.candidates
        for reason in candidate_item.reason_codes
    )
    return {
        "accepted_listing_count": result.listing_count,
        "primary_cohort_eligible_count": result.primary_cohort_eligible_count,
        "assigned_count": result.assigned_count,
        "assigned_rate": _rate(result.assigned_count, result.listing_count),
        "unclassified_count": result.unclassified_count,
        "unclassified_rate": _rate(result.unclassified_count, result.listing_count),
        "review_required_count": result.review_required_count,
        "review_required_rate": _rate(result.review_required_count, result.listing_count),
        "route_count": len(routes),
        "route_size_distribution": _route_size_histogram(routes),
        "size_2_route_count": sum(route.member_count == 2 for route in routes),
        "size_2_route_share": _rate(
            sum(route.member_count == 2 for route in routes), len(routes),
        ),
        "candidate": candidate,
        "candidate_reason_code_histogram": dict(sorted(candidate_reason_codes.items())),
        "route_ids": [route.route_id for route in routes],
        "route_fingerprints": [route.semantic_fingerprint for route in routes],
        "route_dimension_coverage": dimensions,
        "route_defining_role_distribution": {
            role: {
                "route_count": defining_roles[role],
                "assigned_member_count": defining_role_members[role],
            }
            for role in sorted(defining_roles)
        },
        "route_defining_dimension_distribution": {
            dimension: {
                "route_count": defining_dimensions[dimension],
                "assigned_member_count": defining_dimension_members[dimension],
            }
            for dimension in sorted(defining_dimensions)
        },
        "accepted_s2_authority_match": s2_authority_match,
        "accepted_calibrated_authority_match": calibrated_authority_match,
        "semantic_result_fingerprint": replay.semantic_result.semantic_fingerprint,
        "route_result_fingerprint": result.semantic_fingerprint,
        "semantic_deterministic_match": replay.semantic_deterministic,
        "route_deterministic_match": replay.route_deterministic,
        "nonprimary_assigned_count": nonprimary_assigned,
        "invalid_route_identity_dimension_count": invalid_route_dimensions,
        "frozen_metric_contract_match": _metric_contract_ok(result),
        "network_calls": diagnostics.get("network_calls"),
        "provider_calls": diagnostics.get("provider_calls"),
        "credential_accesses": diagnostics.get("credential_accesses"),
        "llm_authoritative_decisions": diagnostics.get(
            "llm_authoritative_decisions",
        ),
        "category_specific_generic_branches": diagnostics.get(
            "category_specific_generic_branches",
        ),
        "downstream_representation_selection_count": diagnostics.get(
            "downstream_representation_selection_count",
        ),
        "runtime_seconds": dict(sorted(replay.runtime_seconds.items())),
    }


def _threshold_result(actual: float, operator: str, floor: float) -> dict[str, Any]:
    passed = actual >= floor if operator == ">=" else actual <= floor
    return {"operator": operator, "threshold": floor, "actual": actual, "passed": passed}


def _shower_comparison(summary: dict[str, Any]) -> dict[str, Any]:
    actuals = {
        "assigned_rate": summary["assigned_rate"],
        "unclassified_rate": summary["unclassified_rate"],
        "review_required_rate": summary["review_required_rate"],
        "size_2_route_share": summary["size_2_route_share"],
        "candidate_coverage_of_assigned": summary["candidate"]["coverage_of_assigned"],
        "candidate_coverage_of_accepted": summary["candidate"]["coverage_of_accepted"],
    }
    gates = {
        name: _threshold_result(actuals[name], operator, threshold)
        for name, (operator, threshold) in SHOWER_FLOORS.items()
    }
    return {
        "v1_rejected_baseline": SHOWER_V1,
        "v2": {
            **actuals,
            "accepted_listing_count": summary["accepted_listing_count"],
            "assigned_count": summary["assigned_count"],
            "unclassified_count": summary["unclassified_count"],
            "review_required_count": summary["review_required_count"],
            "route_count": summary["route_count"],
            "size_2_route_count": summary["size_2_route_count"],
            "candidate_count": summary["candidate"]["candidate_count"],
            "candidate_member_count": summary["candidate"]["candidate_member_count"],
            "route_deterministic_match": summary["route_deterministic_match"],
        },
        "frozen_quantitative_gates": gates,
        "all_frozen_quantitative_gates_passed": all(
            item["passed"] for item in gates.values()
        ),
    }


def _record_title(record: Any) -> str | None:
    for field in record.fields:
        if field.header == TITLE_HEADER and isinstance(field.value, str):
            value = " ".join(field.value.split())
            return value or None
    return None


def _blank_human_review() -> dict[str, Any]:
    return {**{key: None for key in REVIEW_DECISION_KEYS}, "notes": ""}


def _review_sample(replays: Mapping[str, CategoryReplay]) -> dict[str, Any]:
    replay = replays[SHOWER_CALIBRATION_ID]
    route_result = replay.route_result
    semantic = {
        item.listing_reference: item for item in replay.semantic_result.listings
    }
    records = {item.asin: item for item in replay.dataset.records}
    candidate_ids = {item.route_id for item in route_result.candidates}
    candidates = {item.route_id: item for item in route_result.candidates}
    membership_by_listing = {
        item.listing_reference: item for item in route_result.memberships
    }
    largest_ids = {
        item.route_id for item in sorted(
            route_result.routes, key=lambda route: (-route.member_count, route.route_id),
        )[:min(5, len(route_result.routes))]
    }

    def route_strata(route: Any) -> tuple[str, ...]:
        strata: list[str] = []
        if route.route_id in candidate_ids:
            strata.append("CANDIDATE_ROUTE")
        if route.route_id in largest_ids:
            strata.append("LARGEST_ROUTE")
        if route.member_count <= replay.route_config.min_route_size:
            strata.append("BOUNDARY_MIN_SIZE_ROUTE")
        if any(coverage < 1.0 for _, coverage in route.feature_coverage):
            strata.append("SPARSE_ROUTE")
        signature_count = len({
            canonical_json([
                item.to_dict()
                for item in membership_by_listing[reference].assignment_features
            ])
            for reference in route.member_listing_references
        })
        if (
            signature_count > 1
            or bool(route.secondary_descriptors)
            or bool(route.facet_descriptors)
        ):
            strata.append("FORMER_V1_FRAGMENTATION_RISK")
        return tuple(strata or ("GENERAL_ROUTE",))

    strata_by_route = {
        route.route_id: route_strata(route) for route in route_result.routes
    }
    rows: list[dict[str, Any]] = []
    ordered_routes = sorted(
        route_result.routes,
        key=lambda item: (
            item.route_id not in candidate_ids,
            item.route_id not in largest_ids,
            "BOUNDARY_MIN_SIZE_ROUTE" not in strata_by_route[item.route_id]
            and "SPARSE_ROUTE" not in strata_by_route[item.route_id],
            "FORMER_V1_FRAGMENTATION_RISK" not in strata_by_route[item.route_id],
            -item.member_count,
            item.route_id,
        ),
    )
    for route in ordered_routes:
        if len(rows) >= REVIEW_MAX_ROWS:
            break
        references = sorted(
            route.member_listing_references,
            key=lambda reference: sha256(
                f"{route.route_id}:{reference}".encode("utf-8")
            ).hexdigest(),
        )[:min(REVIEW_SAMPLE_PER_ROUTE, REVIEW_MAX_ROWS - len(rows))]
        for reference in references:
            listing = semantic[reference]
            rows.append({
                "calibration_id": SHOWER_CALIBRATION_ID,
                "route_reference": route.route_id,
                "candidate_route": route.route_id in candidate_ids,
                "candidate_reason_codes": list(
                    candidates[route.route_id].reason_codes
                    if route.route_id in candidates else ()
                ),
                "review_strata": list(strata_by_route[route.route_id]),
                "listing_reference": reference,
                "listing_title": _record_title(records[reference]),
                "semantic_product_identity": listing.product_identity.normalized_identity,
                "semantic_relation_role": listing.product_role.relation_role.value,
                "semantic_cohort_state": listing.market_cohort_eligibility.state.value,
                "route_eligible_definition": [
                    item.to_dict() for item in route.defining_features
                ],
                "human_review": _blank_human_review(),
            })
    identity = [{
        "calibration_id": row["calibration_id"],
        "route_reference": row["route_reference"],
        "candidate_route": row["candidate_route"],
        "candidate_reason_codes": row["candidate_reason_codes"],
        "review_strata": row["review_strata"],
        "listing_reference": row["listing_reference"],
        "route_eligible_definition": row["route_eligible_definition"],
    } for row in rows]
    sample_id = sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    sampled_route_ids = {row["route_reference"] for row in rows}
    strata_names = sorted({
        stratum for strata in strata_by_route.values() for stratum in strata
    })
    return {
        "contract_version": REVIEW_CONTRACT,
        "review_sample_id": sample_id,
        "calibration_id": SHOWER_CALIBRATION_ID,
        "sampling": {
            "method": (
                "DETERMINISTIC_STRATIFIED_ROUTE_PRIORITY_AND_HASHED_MEMBER_ORDER"
            ),
            "maximum_rows_per_route": REVIEW_SAMPLE_PER_ROUTE,
            "maximum_total_rows": REVIEW_MAX_ROWS,
            "route_count": len(route_result.routes),
            "sampled_route_count": len(sampled_route_ids),
            "row_count": len(rows),
            "candidate_route_count": len(candidate_ids),
            "candidate_member_count": sum(
                route.member_count for route in route_result.routes
                if route.route_id in candidate_ids
            ),
            "candidate_coverage_of_assigned": _rate(
                sum(
                    route.member_count for route in route_result.routes
                    if route.route_id in candidate_ids
                ),
                route_result.assigned_count,
            ),
            "candidate_coverage_of_accepted": _rate(
                sum(
                    route.member_count for route in route_result.routes
                    if route.route_id in candidate_ids
                ),
                route_result.listing_count,
            ),
            "strata_coverage": {
                stratum: {
                    "available_route_count": sum(
                        stratum in strata for strata in strata_by_route.values()
                    ),
                    "sampled_route_count": sum(
                        route_id in sampled_route_ids and stratum in strata
                        for route_id, strata in strata_by_route.items()
                    ),
                }
                for stratum in strata_names
            },
        },
        "instructions": {
            "authority": "HUMAN_OPERATOR_ONLY",
            "blank_decisions_must_not_be_inferred": True,
            "accepted_decision_values": [True, False],
        },
        "rows": rows,
    }


def _external_new_json(path: Path, *, repo_root: Path) -> None:
    if path.suffix.casefold() != ".json" or path.exists():
        raise _error("ROUTE_V2_UNSAFE_PRIVATE_OUTPUT", "private output must be a new JSON file")
    resolved = path.resolve(strict=False)
    if resolved.is_relative_to(repo_root.resolve()):
        raise _error(
            "ROUTE_V2_UNSAFE_PRIVATE_OUTPUT",
            "private review sample must be outside the repository",
        )


def _review_metrics(
    completed_path: Path | None,
    expected: dict[str, Any],
) -> dict[str, Any]:
    empty = {
        "completed_review_supplied": False,
        "review_sample_id_match": False,
        "reviewed_row_count": 0,
        "consistent_row_count": 0,
        "intra_route_consistency_rate": None,
        "candidate_route_count": sum(
            row["candidate_route"] for row in expected["rows"]
        ),
        "candidate_route_reviewed_count": 0,
        "candidate_minimum_business_sense_passed": False,
        "decision_true_counts": {key: 0 for key in REVIEW_DECISION_KEYS},
        "decision_true_rates": {key: None for key in REVIEW_DECISION_KEYS},
        "all_reviewed_route_safety_checks_passed": False,
    }
    # Candidate count above intentionally counts sample rows only temporarily;
    # normalize it to distinct route references before returning.
    candidate_routes = {
        row["route_reference"] for row in expected["rows"] if row["candidate_route"]
    }
    empty["candidate_route_count"] = len(candidate_routes)
    if completed_path is None:
        return empty
    payload = _load_json(completed_path)
    if not isinstance(payload, dict) or set(payload) != set(expected):
        raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review document schema mismatch")
    if payload["contract_version"] != REVIEW_CONTRACT:
        raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review contract mismatch")
    if payload["review_sample_id"] != expected["review_sample_id"]:
        raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review sample ID mismatch")
    for key in ("calibration_id", "sampling", "instructions"):
        if payload[key] != expected[key]:
            raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review basis was modified")
    rows = payload["rows"]
    if not isinstance(rows, list) or len(rows) != len(expected["rows"]):
        raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review row set mismatch")
    immutable_keys = set(expected["rows"][0]) - {"human_review"} if rows else set()
    consistent = 0
    decision_true_counts = Counter({key: 0 for key in REVIEW_DECISION_KEYS})
    candidate_reviewed: set[str] = set()
    candidate_business_sense = True
    for supplied, basis in zip(rows, expected["rows"], strict=True):
        if not isinstance(supplied, dict) or set(supplied) != set(basis):
            raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review row schema mismatch")
        if any(supplied[key] != basis[key] for key in immutable_keys):
            raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review row basis was modified")
        decision = supplied["human_review"]
        if not isinstance(decision, dict) or set(decision) != {
            *REVIEW_DECISION_KEYS, "notes",
        }:
            raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "human decision schema mismatch")
        if any(type(decision[key]) is not bool for key in REVIEW_DECISION_KEYS):
            raise _error(
                "ROUTE_V2_OPERATOR_REVIEW_INVALID",
                "completed human decisions must be explicit booleans",
            )
        if not isinstance(decision["notes"], str):
            raise _error("ROUTE_V2_OPERATOR_REVIEW_INVALID", "review notes must be text")
        consistent += int(decision["intra_route_consistent"])
        for key in REVIEW_DECISION_KEYS:
            decision_true_counts[key] += int(decision[key])
        if basis["candidate_route"]:
            candidate_reviewed.add(basis["route_reference"])
            candidate_business_sense = candidate_business_sense and all(
                decision[key] for key in REVIEW_DECISION_KEYS
            )
    rate = _rate(consistent, len(rows)) if rows else None
    return {
        "completed_review_supplied": True,
        "review_sample_id_match": True,
        "reviewed_row_count": len(rows),
        "consistent_row_count": consistent,
        "intra_route_consistency_rate": rate,
        "candidate_route_count": len(candidate_routes),
        "candidate_route_reviewed_count": len(candidate_reviewed),
        "candidate_minimum_business_sense_passed": (
            candidate_reviewed == candidate_routes and candidate_business_sense
        ),
        "decision_true_counts": {
            key: decision_true_counts[key] for key in REVIEW_DECISION_KEYS
        },
        "decision_true_rates": {
            key: _rate(decision_true_counts[key], len(rows))
            for key in REVIEW_DECISION_KEYS
        },
        "all_reviewed_route_safety_checks_passed": all(
            decision_true_counts[key] == len(rows)
            for key in REVIEW_DECISION_KEYS
            if key != "intra_route_consistent"
        ),
    }


def _generic_source_checks(repo_root: Path) -> dict[str, int]:
    source_root = repo_root / "src/amazon_product_intelligence/route_discovery_v2"
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(source_root.glob("*.py"))
    ).casefold()
    return {
        "category_literal_patch_count": sum(
            source.count(value) for value in GENERIC_CATEGORY_LITERALS
        ),
        "representative_asin_capability_count": source.count("representative_asin"),
        "direct_competitor_capability_count": source.count("direct_competitor"),
        "procurement_ceiling_capability_count": source.count("procurement_ceiling"),
        "network_client_import_count": len(re.findall(
            r"(?m)^\s*(?:from|import)\s+(?:aiohttp|httpx|requests|socket|urllib)\b",
            source,
        )),
        "provider_client_reference_count": len(re.findall(
            r"\b(?:sorftime|xiyou|sellercentral|selling_partner_api)\b", source,
        )),
        "credential_read_count": len(re.findall(
            r"\b(?:getenv|os\.environ|environ\[|keyring\.)", source,
        )),
        "llm_client_import_count": len(re.findall(
            r"(?m)^\s*(?:from|import)\s+(?:anthropic|openai|transformers)\b",
            source,
        )),
    }


def _privacy_safe(report: dict[str, Any]) -> bool:
    encoded = json.dumps(report, ensure_ascii=False, sort_keys=True)
    patterns = (
        r"\bB0[A-Z0-9]{8}\b", r"[A-Za-z]:\\", r"/(?:Users|home)/",
        r'"listing_reference"', r'"listing_title"', TITLE_HEADER,
        r'"(?:brand|seller|price|raw_row|source_row)"\s*:',
        r'"(?:api[_-]?key|access[_-]?token|secret|password|credential)"\s*:',
        r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    )
    return not any(re.search(pattern, encoded) for pattern in patterns)


def _require_external_private_input(path: Path, *, repo_root: Path) -> None:
    resolved = path.resolve(strict=False)
    if resolved.is_relative_to(repo_root.resolve()):
        raise _error(
            "ROUTE_V2_UNSAFE_PRIVATE_INPUT",
            "private replay inputs and review documents must remain outside the repository",
        )


def _acceptance_verdict(gates: Mapping[str, bool]) -> str:
    return PASS_VERDICT if gates and all(gates.values()) else BLOCKED_VERDICT


def run_private_replay(
    manifest_path: Path,
    completed_review_path: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.perf_counter()
    replays: dict[str, CategoryReplay] = {}
    repo_root = Path(__file__).resolve().parents[1]
    _require_external_private_input(manifest_path, repo_root=repo_root)
    if completed_review_path is not None:
        _require_external_private_input(completed_review_path, repo_root=repo_root)
    manifest_entries = _manifest(manifest_path)
    for entry in manifest_entries:
        _require_external_private_input(Path(entry["input"]), repo_root=repo_root)
        import_started = time.perf_counter()
        dataset = import_sellersprite_file(
            entry["input"],
            context=ImportContext(
                marketplace=entry["marketplace"], category=entry["category"],
                imported_at="2026-08-29T00:00:00+00:00",
                observed_date=entry["observed_date"], sheet_name=entry["sheet"],
            ),
        )
        import_seconds = time.perf_counter() - import_started
        profile = load_category_semantic_profile(entry["profile"])
        route_config = load_route_discovery_v2_config(entry["route_config"])
        semantic_started = time.perf_counter()
        semantic_result = build_semantic_engine_v2_result(dataset, profile=profile)
        semantic_seconds = time.perf_counter() - semantic_started
        route_started = time.perf_counter()
        route_result = build_route_discovery_v2(
            dataset, semantic_result, profile=profile, config=route_config,
        )
        route_seconds = time.perf_counter() - route_started
        replay_dataset = replace(
            dataset, imported_at="2030-01-01T00:00:00+00:00",
            records=tuple(reversed(dataset.records)),
        )
        determinism_started = time.perf_counter()
        replay_semantic = build_semantic_engine_v2_result(
            replay_dataset, profile=profile,
        )
        replay_route = build_route_discovery_v2(
            replay_dataset, replay_semantic, profile=profile, config=route_config,
        )
        determinism_seconds = time.perf_counter() - determinism_started
        replays[entry["calibration_id"]] = CategoryReplay(
            calibration_id=entry["calibration_id"], dataset=dataset,
            semantic_result=semantic_result, route_result=route_result,
            profile=profile, route_config=route_config,
            semantic_deterministic=semantic_result.to_json() == replay_semantic.to_json(),
            route_deterministic=route_result.to_json() == replay_route.to_json(),
            runtime_seconds={
                "governed_import": round(import_seconds, 6),
                "semantic_engine_v2": round(semantic_seconds, 6),
                "route_discovery_v2": round(route_seconds, 6),
                "reversed_timestamp_determinism": round(determinism_seconds, 6),
            },
        )

    summaries = {
        key: _category_summary(value) for key, value in sorted(replays.items())
    }
    expected_review = _review_sample(replays)
    operator = _review_metrics(completed_review_path, expected_review)
    shower = _shower_comparison(summaries[SHOWER_CALIBRATION_ID])
    source_checks = _generic_source_checks(Path(__file__).resolve().parents[1])
    exact_counts = all(
        summaries[key]["accepted_listing_count"] == count
        for key, count in EXPECTED_COUNTS.items()
    )
    result_diagnostics_zero = all(
        summaries[key][name] == 0
        for key in summaries
        for name in (
            "network_calls", "provider_calls", "credential_accesses",
            "llm_authoritative_decisions", "category_specific_generic_branches",
        )
    )
    gates = {
        "exact_corpus_counts": exact_counts,
        "shower_frozen_quantitative_gates": shower[
            "all_frozen_quantitative_gates_passed"
        ],
        "bounded_human_intra_route_consistency": (
            operator["intra_route_consistency_rate"] is not None
            and operator["intra_route_consistency_rate"] >= 0.95
        ),
        "candidate_minimum_business_sense": operator[
            "candidate_minimum_business_sense_passed"
        ],
        "operator_route_safety_checks": operator[
            "all_reviewed_route_safety_checks_passed"
        ],
        "candidate_material_distinctness": all(
            summary["candidate"][
                "candidate_pairs_without_route_eligible_difference"
            ] == 0
            for summary in summaries.values()
        ),
        "facet_only_distinct_candidate_pairs_zero": all(
            summary["candidate"]["facet_only_distinct_candidate_pair_count"] == 0
            for summary in summaries.values()
        ),
        "candidate_count_policy": all(
            summary["candidate"]["three_to_five_or_insufficient_evidence"]
            for summary in summaries.values()
        ),
        "nonprimary_leakage_zero": all(
            summary["nonprimary_assigned_count"] == 0
            for summary in summaries.values()
        ),
        "route_identity_uses_only_authorized_dimensions": all(
            summary["invalid_route_identity_dimension_count"] == 0
            for summary in summaries.values()
        ),
        "frozen_metric_contract_match": all(
            summary["frozen_metric_contract_match"] for summary in summaries.values()
        ),
        "accepted_s2_authority_match": all(
            summary["accepted_s2_authority_match"] for summary in summaries.values()
        ),
        "accepted_calibrated_authority_match": all(
            summary["accepted_calibrated_authority_match"]
            for summary in summaries.values()
        ),
        "semantic_determinism_100_percent": all(
            summary["semantic_deterministic_match"] for summary in summaries.values()
        ),
        "route_determinism_100_percent": all(
            summary["route_deterministic_match"] for summary in summaries.values()
        ),
        "generic_engine_category_patches_zero": (
            source_checks["category_literal_patch_count"] == 0
        ),
        "forbidden_downstream_capabilities_zero": all(
            value == 0 for key, value in source_checks.items()
            if key not in {
                "category_literal_patch_count", "network_client_import_count",
                "provider_client_reference_count", "credential_read_count",
                "llm_client_import_count",
            }
        ),
        "static_network_provider_credential_llm_references_zero": all(
            source_checks[key] == 0 for key in (
                "network_client_import_count", "provider_client_reference_count",
                "credential_read_count", "llm_client_import_count",
            )
        ),
        "network_provider_credential_llm_zero": result_diagnostics_zero,
    }
    report = {
        "contract_version": "route-discovery-v2-private-replay-summary-v1.0",
        "data_disclosure": dict(REPLAY_DISCLOSURE),
        "calibration_category_count": len(replays),
        "total_listing_count": sum(
            summary["accepted_listing_count"] for summary in summaries.values()
        ),
        "categories": summaries,
        "shower_caddy_v1_v2_comparison": shower,
        "bounded_operator_review": operator,
        "generic_engine_checks": source_checks,
        "runtime_seconds": {
            "total_replay_wall_clock": round(time.perf_counter() - started, 6),
        },
        "gates": gates,
    }
    privacy_safe = _privacy_safe(report)
    report["privacy_leak_count"] = 0 if privacy_safe else 1
    report["gates"]["aggregate_output_privacy_safe"] = privacy_safe
    report["verdict"] = _acceptance_verdict(report["gates"])
    return report, expected_review


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest", required=True,
        help="private external five-category JSON manifest",
    )
    parser.add_argument(
        "--completed-review",
        help="private completed JSON produced from the generated review sample",
    )
    parser.add_argument(
        "--review-sample-output",
        help="new private JSON path outside the repository; decisions remain blank",
    )
    parser.add_argument("--output", required=True, help="new aggregate-only JSON output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = Path(args.output)
        if output.suffix.casefold() != ".json" or output.exists():
            raise _error("ROUTE_V2_UNSAFE_OUTPUT", "aggregate output must be a new JSON file")
        report, review_sample = run_private_replay(
            Path(args.manifest),
            None if args.completed_review is None else Path(args.completed_review),
        )
        if args.review_sample_output is not None:
            sample_output = Path(args.review_sample_output)
            if sample_output.resolve(strict=False) == output.resolve(strict=False):
                raise _error(
                    "ROUTE_V2_UNSAFE_PRIVATE_OUTPUT",
                    "aggregate and private review outputs must differ",
                )
            _external_new_json(
                sample_output, repo_root=Path(__file__).resolve().parents[1],
            )
            with sample_output.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(review_sample, handle, ensure_ascii=False, sort_keys=True, indent=2)
                handle.write("\n")
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
        print(json.dumps({
            "status": "SUCCEEDED", "verdict": report["verdict"],
            "total_listing_count": report["total_listing_count"],
            "privacy_leak_count": report["privacy_leak_count"],
        }, ensure_ascii=False, sort_keys=True))
        return 0 if report["verdict"] == PASS_VERDICT else 3
    except (OSError, ValueError, SemanticEngineV2Error, RouteDiscoveryV2Error) as exc:
        public_error = getattr(exc, "code", "ROUTE_V2_PRIVATE_REPLAY_FAILED")
        print(json.dumps({
            "status": "FAILED", "error": public_error,
        }, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
