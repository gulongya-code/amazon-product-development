from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.conflict_resolution as conflict_resolution
from amazon_product_intelligence.adapters import (
    AdaptationContext,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.conflict_resolution import (
    CONFLICT_RESOLUTION_RULESET_VERSION,
    ConflictResolutionBuilderV0_1,
    ConflictResolutionRequest,
    ConflictResolutionSnapshotV0_1,
    ConflictSerializationError,
    ConflictValidationError,
    ResolutionAttemptRecord,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    ContractValidationError,
    PresenceStatus,
    canonical_json,
    deterministic_id,
    observation_revision_id,
)
from amazon_product_intelligence.evidence_evaluation import (
    EvidenceEvaluationBuilderV0_1,
    EvidenceEvaluationRequest,
)


SYNTHETIC_CANONICAL_TEST_INPUT = "SYNTHETIC_CANONICAL_TEST_INPUT"
FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"
TARGET_ASIN = "B0G2VV4RBW"

CASES = {
    "xiyou_info": (
        "xiyou",
        "xiyou_asin_info.json",
        "asin_info",
        "get_asin_info",
        {},
    ),
    "detail": (
        "sorftime",
        "sorftime_product_detail.json",
        "product_detail",
        "product_detail",
        {"asin": TARGET_ASIN},
    ),
}


def adapt(case: str) -> CanonicalEvidenceBundle:
    provider, fixture, payload_kind, source_tool, request = CASES[case]
    payload = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    context = AdaptationContext(
        provider=provider,
        payload_kind=payload_kind,
        source_tool=source_tool,
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:{provider}:{payload_kind}:conflict-resolution-test",
        sanitized_request=request,
        currency="USD",
    )
    adapter = XiYouAdapterV0_1() if provider == "xiyou" else SorftimeAdapterV0_1()
    result = adapter.adapt(payload, context)
    if not result.succeeded:
        raise AssertionError(result.errors)
    return result.bundle.validate()


def revision_content(observation) -> dict[str, object]:
    payload = observation.to_dict()
    for key in (
        "semantic_observation_id",
        "observation_id",
        "provenance",
        "quality_issue_ids",
        "result_status",
    ):
        payload.pop(key, None)
    payload["time"].pop("retrieved_at", None)
    return payload


def synthetic_bundles() -> tuple[CanonicalEvidenceBundle, CanonicalEvidenceBundle]:
    xiyou = adapt("xiyou_info")
    detail = adapt("detail")
    old = next(item for item in detail.observations if getattr(item, "metric", None) == "price")
    changed_value = replace(old.value, raw_value=12.0, normalized_value=12.0)
    provisional = replace(old, value=changed_value)
    changed_id = observation_revision_id(
        provisional.semantic_observation_id, revision_content(provisional)
    )
    changed = replace(provisional, observation_id=changed_id)
    runs = tuple(
        replace(
            run,
            output_observation_ids=tuple(
                changed_id if item == old.observation_id else item
                for item in run.output_observation_ids
            ),
        )
        if old.observation_id in run.output_observation_ids
        else run
        for run in detail.transformation_runs
    )
    observations = tuple(
        changed if item.observation_id == old.observation_id else item
        for item in detail.observations
    )
    synthetic_detail = CanonicalEvidenceBundle(
        transformation_runs=runs,
        observations=observations,
        conflicts=detail.conflicts,
        resolutions=detail.resolutions,
        quality_issues=detail.quality_issues,
        raw_evidence_references=detail.raw_evidence_references,
        query_execution_records=detail.query_execution_records,
    )
    return xiyou, synthetic_detail


def build_evaluation(*bundles: CanonicalEvidenceBundle):
    return EvidenceEvaluationBuilderV0_1().build(
        EvidenceEvaluationRequest(canonical_bundles=tuple(bundles))
    )


def build_resolution(
    bundles: tuple[CanonicalEvidenceBundle, ...],
    evaluation,
    *attempts: ResolutionAttemptRecord,
) -> ConflictResolutionSnapshotV0_1:
    return ConflictResolutionBuilderV0_1().build(ConflictResolutionRequest(
        canonical_bundles=bundles,
        evidence_evaluation_snapshot=evaluation.to_dict(),
        resolution_attempts=attempts,
    ))


def price_analysis(snapshot: ConflictResolutionSnapshotV0_1):
    return next(item for item in snapshot.conflict_analyses if item.dimension == "price")


def make_attempt(
    analysis,
    status: str,
    *,
    method: str,
    produced_candidate_id: str | None = None,
    candidate_ids: tuple[str, ...] | None = None,
    available_ids: tuple[str, ...] | None = None,
) -> ResolutionAttemptRecord:
    ids = candidate_ids or analysis.candidate_ids
    available = available_ids if available_ids is not None else ids
    payload = {
        "conflict_analysis_id": analysis.conflict_analysis_id,
        "attempted_method": method,
        "candidate_ids": ids,
        "available_evidence_candidate_ids": available,
        "result_status": status,
        "produced_candidate_id": produced_candidate_id,
        "process_evidence": {
            "input_classification": SYNTHETIC_CANONICAL_TEST_INPUT,
            "interpretation": "PROCESS_OUTPUT_IS_NOT_CANONICAL_TRUTH",
        },
    }
    return ResolutionAttemptRecord(
        resolution_attempt_id=deterministic_id("resolution-attempt", payload), **payload
    )


def reordered(bundle: CanonicalEvidenceBundle) -> CanonicalEvidenceBundle:
    return CanonicalEvidenceBundle(
        transformation_runs=tuple(reversed(bundle.transformation_runs)),
        observations=tuple(reversed(bundle.observations)),
        conflicts=tuple(reversed(bundle.conflicts)),
        resolutions=tuple(reversed(bundle.resolutions)),
        quality_issues=tuple(reversed(bundle.quality_issues)),
        raw_evidence_references=tuple(reversed(bundle.raw_evidence_references)),
        query_execution_records=tuple(reversed(bundle.query_execution_records)),
    )


class ConflictResolutionFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundles = synthetic_bundles()
        cls.evaluation = build_evaluation(*cls.bundles)
        cls.snapshot = build_resolution(cls.bundles, cls.evaluation)
        cls.price = price_analysis(cls.snapshot)

    def test_public_api_is_explicit_and_closed(self) -> None:
        expected = {
            "CONFLICT_RESOLUTION_RULESET_VERSION",
            "ConflictResolutionRequest",
            "ConflictResolutionSnapshotV0_1",
            "ConflictResolutionBuilderV0_1",
            "ConflictResolutionError",
            "ConflictValidationError",
            "ConflictSerializationError",
            "ConflictCandidate",
            "ConflictAnalysisRecord",
            "ResolutionAttemptRecord",
            "ConflictCoverageSummary",
            "ConflictLineageReference",
            "ConflictDiagnostic",
        }
        self.assertEqual(set(conflict_resolution.__all__), expected)
        self.assertEqual(CONFLICT_RESOLUTION_RULESET_VERSION, "conflict-resolution-v0.1")
        self.assertTrue(expected <= set(vars(conflict_resolution)))

    def test_production_dependency_boundary_is_contracts_only(self) -> None:
        production = REPOSITORY_ROOT / "src" / "amazon_product_intelligence" / "conflict_resolution"
        forbidden = {
            "adapters",
            "product_intelligence",
            "demand_intelligence",
            "competition_intelligence",
            "opportunity_intelligence",
            "evidence_evaluation",
        }
        for path in production.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            self.assertFalse(
                any(part in forbidden for name in imported for part in name.split(".")),
                path.name,
            )

    def test_serialized_evaluation_boundary_is_strict(self) -> None:
        request = ConflictResolutionRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
        )
        self.assertEqual(
            request.evidence_evaluation_snapshot["snapshot_id"], self.evaluation.snapshot_id
        )
        with self.assertRaises(ConflictValidationError):
            ConflictResolutionRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation,  # type: ignore[arg-type]
            )
        tampered = self.evaluation.to_dict()
        tampered["snapshot_id"] = "evidence-evaluation-snapshot:tampered"
        with self.assertRaises(ConflictValidationError):
            ConflictResolutionRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=tampered,
            )
        duplicated = self.evaluation.to_dict()
        conflict = duplicated["conflict_records"][0]
        conflict["providers"].append(conflict["providers"][0])
        conflict_content = dict(conflict)
        conflict_content.pop("conflict_record_id")
        conflict["conflict_record_id"] = deterministic_id(
            "evidence-conflict", conflict_content
        )
        snapshot_content = dict(duplicated)
        snapshot_content.pop("snapshot_id")
        duplicated["snapshot_id"] = deterministic_id(
            "evidence-evaluation-snapshot", snapshot_content
        )
        duplicate_request = ConflictResolutionRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=duplicated,
        )
        with self.assertRaises(ConflictValidationError):
            ConflictResolutionBuilderV0_1().build(duplicate_request)

    def test_synthetic_price_conflict_preserves_every_candidate(self) -> None:
        source_conflict = next(
            item for item in self.evaluation.conflict_records if item.dimension == "price"
        )
        self.assertEqual(
            {item.observation_id for item in self.price.candidates},
            set(source_conflict.candidate_observation_ids),
        )
        self.assertEqual(
            {item.value.normalized_value for item in self.price.candidates},
            {12.0, 18.99},
        )
        self.assertEqual({item.provider for item in self.price.candidates}, {"xiyou", "sorftime"})
        self.assertEqual(len(self.price.candidate_ids), 2)
        self.assertTrue(all(item.lineage_references for item in self.price.candidates))

    def test_default_builder_never_selects_a_candidate(self) -> None:
        self.assertEqual(
            {item.result_status for item in self.snapshot.resolution_attempts},
            {"NOT_ATTEMPTED"},
        )
        self.assertTrue(all(
            item.produced_candidate_id is None for item in self.snapshot.resolution_attempts
        ))
        self.assertTrue(all(
            set(item.candidate_ids)
            == set(next(
                analysis.candidate_ids
                for analysis in self.snapshot.conflict_analyses
                if analysis.conflict_analysis_id == item.conflict_analysis_id
            ))
            for item in self.snapshot.resolution_attempts
        ))

    def test_all_attempt_statuses_are_recordable_without_automatic_truth(self) -> None:
        cases = (
            ("NOT_ATTEMPTED", "NOT_ATTEMPTED", None),
            ("INSUFFICIENT_EVIDENCE", "EVIDENCE_SUFFICIENCY_REVIEW", None),
            ("AMBIGUOUS", "EXPLICIT_CONSISTENCY_REVIEW", None),
            (
                "RESOLUTION_PRODUCED",
                "EXPLICIT_SYNTHETIC_RULE",
                self.price.candidate_ids[0],
            ),
        )
        for status, method, produced in cases:
            with self.subTest(status=status):
                attempt = make_attempt(
                    self.price,
                    status,
                    method=method,
                    produced_candidate_id=produced,
                )
                built = build_resolution(self.bundles, self.evaluation, attempt)
                recorded = next(
                    item
                    for item in built.resolution_attempts
                    if item.conflict_analysis_id == self.price.conflict_analysis_id
                )
                self.assertEqual(recorded.result_status, status)
                self.assertEqual(recorded.produced_candidate_id, produced)
                self.assertEqual(set(recorded.candidate_ids), set(self.price.candidate_ids))
                if status == "RESOLUTION_PRODUCED":
                    self.assertTrue(any(
                        item.code == "PRODUCED_CANDIDATE_IS_RULE_OUTPUT_NOT_TRUTH"
                        for item in built.diagnostics
                    ))

    def test_forbidden_preference_methods_and_invalid_selection_fail_closed(self) -> None:
        for method in (
            "PROVIDER_PRIORITY",
            "LATEST_VALUE",
            "HIGHEST_VALUE",
            "LOWEST_PRICE",
            "AVERAGE_VALUE",
            "MEDIAN_VALUE",
            "MAJORITY_VOTE",
            "CONFIDENCE_SCORE",
            "PROVIDER_A_ALWAYS_WINS",
            "PREFERRED_PROVIDER",
        ):
            with self.subTest(method=method), self.assertRaises(ConflictValidationError):
                make_attempt(
                    self.price,
                    "AMBIGUOUS",
                    method=method,
                )
        with self.assertRaises(ConflictValidationError):
            make_attempt(
                self.price,
                "RESOLUTION_PRODUCED",
                method="EXPLICIT_SYNTHETIC_RULE",
                produced_candidate_id="conflict-candidate:not-in-set",
            )

    def test_attempt_cannot_delete_candidates_or_use_missing_evidence(self) -> None:
        reduced = make_attempt(
            self.price,
            "AMBIGUOUS",
            method="EXPLICIT_CONSISTENCY_REVIEW",
            candidate_ids=(self.price.candidate_ids[0],),
        )
        with self.assertRaises(ConflictValidationError):
            build_resolution(self.bundles, self.evaluation, reduced)
        with self.assertRaises(ConflictValidationError):
            make_attempt(
                self.price,
                "INSUFFICIENT_EVIDENCE",
                method="EVIDENCE_SUFFICIENCY_REVIEW",
                available_ids=("missing-evidence:not-a-candidate",),
            )
        self.assertTrue(all(
            candidate.value.presence_status is PresenceStatus.PRESENT
            for analysis in self.snapshot.conflict_analyses
            for candidate in analysis.candidates
        ))

    def test_no_evaluation_conflict_produces_empty_analysis_inventory(self) -> None:
        bundle = adapt("xiyou_info")
        evaluation = build_evaluation(bundle)
        built = build_resolution((bundle,), evaluation)
        self.assertFalse(built.conflict_analyses)
        self.assertFalse(built.resolution_attempts)
        self.assertEqual(built.coverage.candidate_count, 0)
        self.assertEqual({item.code for item in built.diagnostics}, {"NO_EVALUATION_CONFLICTS"})

    def test_models_are_deeply_immutable(self) -> None:
        candidate = self.price.candidates[0]
        with self.assertRaises(FrozenInstanceError):
            candidate.provider = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            self.snapshot.coverage.attempt_status_counts["NOT_ATTEMPTED"] = 0  # type: ignore[index]
        attempt = self.snapshot.resolution_attempts[0]
        with self.assertRaises(TypeError):
            attempt.process_evidence["changed"] = True  # type: ignore[index]
        caller_context = {"context": {"signals": [{"label": "original"}]}}
        payload = {
            "conflict_analysis_id": self.price.conflict_analysis_id,
            "attempted_method": "EXPLICIT_CONSISTENCY_REVIEW",
            "candidate_ids": self.price.candidate_ids,
            "available_evidence_candidate_ids": self.price.candidate_ids,
            "result_status": "AMBIGUOUS",
            "produced_candidate_id": None,
            "process_evidence": caller_context,
        }
        nested_attempt = ResolutionAttemptRecord(
            resolution_attempt_id=deterministic_id("resolution-attempt", payload),
            **payload,
        )
        caller_context["context"]["signals"][0]["label"] = "caller mutation"
        self.assertEqual(
            nested_attempt.process_evidence["context"]["signals"][0]["label"],
            "original",
        )
        with self.assertRaises(TypeError):
            nested_attempt.process_evidence["context"]["signals"][0]["label"] = (
                "model mutation"
            )

    def test_strict_serialization_round_trip_and_identity_rejection(self) -> None:
        payload = self.snapshot.to_dict()
        restored = ConflictResolutionSnapshotV0_1.from_dict(payload)
        self.assertEqual(restored, self.snapshot)
        self.assertEqual(canonical_json(restored), canonical_json(self.snapshot))
        payload["unexpected"] = True
        with self.assertRaises(ConflictSerializationError):
            ConflictResolutionSnapshotV0_1.from_dict(payload)
        identity_payload = self.snapshot.to_dict()
        identity_payload["snapshot_id"] = "conflict-resolution-snapshot:tampered"
        with self.assertRaises(ConflictSerializationError):
            ConflictResolutionSnapshotV0_1.from_dict(identity_payload)
        coverage_payload = self.snapshot.to_dict()
        coverage_payload["coverage"]["provider_count"] += 1
        content = dict(coverage_payload)
        content.pop("snapshot_id")
        coverage_payload["snapshot_id"] = deterministic_id(
            "conflict-resolution-snapshot", content
        )
        with self.assertRaises(ConflictSerializationError):
            ConflictResolutionSnapshotV0_1.from_dict(coverage_payload)

    def test_determinism_ignores_bundle_and_record_order(self) -> None:
        built = build_resolution(
            tuple(reversed(tuple(reordered(item) for item in self.bundles))),
            self.evaluation,
        )
        self.assertEqual(built.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(canonical_json(built), canonical_json(self.snapshot))

    def test_determinism_is_stable_across_processes(self) -> None:
        script = (
            "from tests.test_conflict_resolution_v0_1 import synthetic_bundles, "
            "build_evaluation, build_resolution; "
            "b=synthetic_bundles(); e=build_evaluation(*b); "
            "print(build_resolution(b,e).snapshot_id)"
        )
        first = subprocess.check_output(
            [sys.executable, "-c", script], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        second = subprocess.check_output(
            [sys.executable, "-c", script], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        self.assertEqual(first, self.snapshot.snapshot_id)
        self.assertEqual(second, first)

    def test_lineage_replays_to_mapping_raw_collection_and_fingerprint(self) -> None:
        self.assertIs(self.snapshot.validate_against_bundles(self.bundles), self.snapshot)
        self.assertEqual(
            {item.observation_id for item in self.snapshot.lineage_index},
            {
                candidate.observation_id
                for analysis in self.snapshot.conflict_analyses
                for candidate in analysis.candidates
            },
        )
        self.assertTrue(all(item.mapping_version for item in self.snapshot.lineage_index))
        self.assertTrue(all(item.raw_evidence_id for item in self.snapshot.lineage_index))
        with self.assertRaises(ConflictValidationError):
            self.snapshot.validate_against_bundles((self.bundles[0],))
        with self.assertRaises(ConflictValidationError):
            self.snapshot.validate_against_bundles(({},))  # type: ignore[arg-type]

    def test_evaluation_candidate_mismatch_is_rejected(self) -> None:
        payload = self.evaluation.to_dict()
        conflict = next(item for item in payload["conflict_records"] if item["dimension"] == "price")
        observation_id = conflict["candidate_observation_ids"][0]
        conflict["candidate_values"][observation_id]["raw_value"] = 999
        conflict["candidate_values"][observation_id]["normalized_value"] = 999
        conflict_payload = dict(conflict)
        conflict_payload.pop("conflict_record_id")
        conflict["conflict_record_id"] = deterministic_id("evidence-conflict", conflict_payload)
        payload_without_id = dict(payload)
        payload_without_id.pop("snapshot_id")
        payload["snapshot_id"] = deterministic_id(
            "evidence-evaluation-snapshot", payload_without_id
        )
        request = ConflictResolutionRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=payload,
        )
        with self.assertRaises(ConflictValidationError):
            ConflictResolutionBuilderV0_1().build(request)
        semantic_payload = self.evaluation.to_dict()
        semantic_conflict = semantic_payload["conflict_records"][0]
        semantic_conflict["semantic_field_id"] = "evidence-field:" + "0" * 64
        conflict_content = dict(semantic_conflict)
        conflict_content.pop("conflict_record_id")
        semantic_conflict["conflict_record_id"] = deterministic_id(
            "evidence-conflict", conflict_content
        )
        snapshot_content = dict(semantic_payload)
        snapshot_content.pop("snapshot_id")
        semantic_payload["snapshot_id"] = deterministic_id(
            "evidence-evaluation-snapshot", snapshot_content
        )
        semantic_request = ConflictResolutionRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=semantic_payload,
        )
        with self.assertRaises(ConflictValidationError):
            ConflictResolutionBuilderV0_1().build(semantic_request)

    def test_output_contains_no_score_preference_or_recommendation_fields(self) -> None:
        forbidden = {
            "score",
            "weight",
            "confidence",
            "trust",
            "probability",
            "winner",
            "preferred_provider",
            "provider_priority",
            "recommendation",
            "ranking",
            "truth_value",
        }

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key.casefold()
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertFalse(forbidden & set(keys(self.snapshot.to_dict())))
        for field in forbidden:
            with self.subTest(process_evidence_field=field):
                payload = {
                    "conflict_analysis_id": self.price.conflict_analysis_id,
                    "attempted_method": "EXPLICIT_SYNTHETIC_RULE",
                    "candidate_ids": self.price.candidate_ids,
                    "available_evidence_candidate_ids": self.price.candidate_ids,
                    "result_status": "RESOLUTION_PRODUCED",
                    "produced_candidate_id": self.price.candidate_ids[0],
                    "process_evidence": {
                        "nested_context": {field: "forbidden conclusion"}
                    },
                }
                with self.assertRaises(ConflictValidationError):
                    ResolutionAttemptRecord(
                        resolution_attempt_id=deterministic_id(
                            "resolution-attempt", payload
                        ),
                        **payload,
                    )


if __name__ == "__main__":
    unittest.main()
