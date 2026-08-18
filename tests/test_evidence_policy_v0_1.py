from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.evidence_policy as evidence_policy
from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.evidence_policy import (
    EVIDENCE_POLICY_RULESET_VERSION,
    EvidencePolicyBuilderV0_1,
    EvidencePolicyRequest,
    EvidencePolicySnapshotV0_1,
    EvidencePolicySerializationError,
    EvidencePolicyValidationError,
    PolicyEvaluationRecord,
)
from tests.test_conflict_resolution_v0_1 import (
    adapt,
    build_evaluation,
    build_resolution,
    make_attempt,
    price_analysis,
    reordered,
    synthetic_bundles,
)


SYNTHETIC_CANONICAL_TEST_INPUT = "SYNTHETIC_CANONICAL_TEST_INPUT"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_policy(bundles, evaluation, conflict):
    return EvidencePolicyBuilderV0_1().build(EvidencePolicyRequest(
        canonical_bundles=tuple(bundles),
        evidence_evaluation_snapshot=evaluation.to_dict(),
        conflict_resolution_snapshot=conflict.to_dict(),
    ))


def recalculate_snapshot_id(payload: dict[str, object], prefix: str) -> None:
    content = dict(payload)
    content.pop("snapshot_id")
    payload["snapshot_id"] = deterministic_id(prefix, content)


def recalculate_attempt_and_conflict_snapshot(
    payload: dict[str, object],
    attempt: dict[str, object],
    old_attempt_id: str,
) -> None:
    content = dict(attempt)
    content.pop("resolution_attempt_id")
    attempt["resolution_attempt_id"] = deterministic_id("resolution-attempt", content)
    new_attempt_id = attempt["resolution_attempt_id"]
    for diagnostic in payload["diagnostics"]:
        related_ids = diagnostic["related_resolution_attempt_ids"]
        if old_attempt_id in related_ids:
            diagnostic["related_resolution_attempt_ids"] = sorted(
                new_attempt_id if item == old_attempt_id else item
                for item in related_ids
            )
            diagnostic_content = dict(diagnostic)
            diagnostic_content.pop("diagnostic_id")
            diagnostic["diagnostic_id"] = deterministic_id(
                "conflict-diagnostic", diagnostic_content
            )
    payload["diagnostics"] = sorted(
        payload["diagnostics"], key=lambda item: item["diagnostic_id"]
    )
    payload["coverage"]["attempt_status_counts"] = dict(sorted(Counter(
        item["result_status"] for item in payload["resolution_attempts"]
    ).items()))
    recalculate_snapshot_id(payload, "conflict-resolution-snapshot")


class EvidencePolicyFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundles = synthetic_bundles()
        cls.evaluation = build_evaluation(*cls.bundles)
        cls.conflict = build_resolution(cls.bundles, cls.evaluation)
        cls.snapshot = build_policy(cls.bundles, cls.evaluation, cls.conflict)
        cls.definitions = {
            item.conditions["condition_type"]: item
            for item in cls.snapshot.policy_definitions
        }
        cls.evaluations = {
            cls.definitions_by_id(cls.snapshot)[item.policy_id]: item
            for item in cls.snapshot.policy_evaluations
        }

    @staticmethod
    def definitions_by_id(snapshot):
        return {item.policy_id: item.conditions["condition_type"] for item in snapshot.policy_definitions}

    def test_public_api_is_explicit_and_closed(self) -> None:
        expected = {
            "EVIDENCE_POLICY_RULESET_VERSION",
            "EvidencePolicyRequest",
            "EvidencePolicySnapshotV0_1",
            "EvidencePolicyBuilderV0_1",
            "EvidencePolicyError",
            "EvidencePolicyValidationError",
            "EvidencePolicySerializationError",
            "PolicyDefinition",
            "PolicyApplicabilityRecord",
            "PolicyEvaluationRecord",
            "PolicyAuditRecord",
            "PolicyCoverageSummary",
            "PolicyLineageReference",
            "PolicyDiagnostic",
        }
        self.assertEqual(set(evidence_policy.__all__), expected)
        self.assertEqual(len(evidence_policy.__all__), 14)
        self.assertEqual(EVIDENCE_POLICY_RULESET_VERSION, "evidence-policy-v0.1")
        self.assertTrue(expected <= set(vars(evidence_policy)))

    def test_production_dependency_boundary_is_contracts_only(self) -> None:
        production = REPOSITORY_ROOT / "src" / "amazon_product_intelligence" / "evidence_policy"
        forbidden = {
            "adapters",
            "product_intelligence",
            "demand_intelligence",
            "competition_intelligence",
            "opportunity_intelligence",
            "evidence_evaluation",
            "conflict_resolution",
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

    def test_policy_definitions_are_declarative_and_versioned(self) -> None:
        self.assertEqual(set(self.definitions), {
            "MINIMUM_PROVIDER_COUNT",
            "LINEAGE_COMPLETENESS_REQUIRED",
            "CONFLICT_PRESENT",
        })
        for definition in self.snapshot.policy_definitions:
            self.assertEqual(definition.policy_version, "0.1")
            self.assertTrue(definition.description)
            self.assertTrue(definition.applicable_evidence_types)
            self.assertIsInstance(definition.conditions, Mapping)
            self.assertNotIn("callable", definition.conditions)
            self.assertEqual(
                definition.policy_id,
                deterministic_id(
                    "evidence-policy",
                    {
                        key: value
                        for key, value in definition.to_dict().items()
                        if key != "policy_id"
                    },
                ),
            )

    def test_integration_emits_process_policy_outcomes_only(self) -> None:
        self.assertEqual(
            {key: value.evaluation_result for key, value in self.evaluations.items()},
            {
                "MINIMUM_PROVIDER_COUNT": "APPLICABLE_NO_ACTION",
                "LINEAGE_COMPLETENESS_REQUIRED": "ACTION_ALLOWED",
                "CONFLICT_PRESENT": "ACTION_BLOCKED",
            },
        )
        self.assertEqual(self.snapshot.coverage.policy_definition_count, 3)
        self.assertEqual(self.snapshot.coverage.policy_evaluation_count, 3)
        self.assertEqual(self.snapshot.coverage.conflict_count, 4)
        self.assertEqual(self.snapshot.coverage.source_bundle_count, 2)

    def test_action_allowed_never_claims_truth(self) -> None:
        allowed = self.evaluations["LINEAGE_COMPLETENESS_REQUIRED"]
        self.assertEqual(allowed.evaluation_result, "ACTION_ALLOWED")
        self.assertEqual(
            allowed.audit_metadata["process_interpretation"],
            "POLICY_RESULT_IS_PROCESS_PERMISSION_ONLY",
        )
        self.assertTrue(any(
            item.code == "PROCESS_ALLOWED_IS_NOT_TRUTH"
            and allowed.policy_evaluation_id in item.related_policy_evaluation_ids
            for item in self.snapshot.diagnostics
        ))

    def test_output_contains_no_hidden_resolution_or_decision_fields(self) -> None:
        forbidden = {
            "winner",
            "selected_value",
            "selected_provider",
            "preferred_provider",
            "truth_value",
            "score",
            "weight",
            "confidence",
            "trust",
            "recommendation",
            "ranking",
            "opportunity_score",
            "product_score",
            "market_decision",
            "provider_priority",
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
        self.assertEqual(
            self.conflict.to_dict(),
            build_resolution(self.bundles, self.evaluation).to_dict(),
        )

    def test_resolution_produced_remains_process_evidence_not_policy_truth(self) -> None:
        analysis = price_analysis(self.conflict)
        attempt = make_attempt(
            analysis,
            "RESOLUTION_PRODUCED",
            method="EXPLICIT_SYNTHETIC_RULE",
            produced_candidate_id=analysis.candidate_ids[0],
        )
        conflict = build_resolution(self.bundles, self.evaluation, attempt)
        built = build_policy(self.bundles, self.evaluation, conflict)
        definitions = self.definitions_by_id(built)
        policy_result = next(
            item
            for item in built.policy_evaluations
            if definitions[item.policy_id] == "CONFLICT_PRESENT"
        )
        self.assertEqual(policy_result.evaluation_result, "ACTION_BLOCKED")
        self.assertTrue(any(
            attempt.resolution_attempt_id in item.resolution_attempt_ids
            for item in built.lineage_index
            if item.conflict_record_id is not None
        ))

    def test_serialized_source_boundaries_are_strict(self) -> None:
        with self.assertRaises(EvidencePolicyValidationError):
            EvidencePolicyRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation,  # type: ignore[arg-type]
                conflict_resolution_snapshot=self.conflict.to_dict(),
            )
        evaluation_payload = self.evaluation.to_dict()
        evaluation_payload["snapshot_id"] = "evidence-evaluation-snapshot:tampered"
        with self.assertRaises(EvidencePolicyValidationError):
            EvidencePolicyRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=evaluation_payload,
                conflict_resolution_snapshot=self.conflict.to_dict(),
            )
        conflict_payload = self.conflict.to_dict()
        conflict_payload["unexpected"] = True
        with self.assertRaises(EvidencePolicyValidationError):
            EvidencePolicyRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation.to_dict(),
                conflict_resolution_snapshot=conflict_payload,
            )

    def test_tampered_evaluation_semantics_fail_closed(self) -> None:
        payload = self.evaluation.to_dict()
        support = payload["support_records"][0]
        support["provider_count"] += 1
        support_content = dict(support)
        support_content.pop("support_record_id")
        support["support_record_id"] = deterministic_id(
            "evidence-support", support_content
        )
        recalculate_snapshot_id(payload, "evidence-evaluation-snapshot")
        conflict_payload = self.conflict.to_dict()
        conflict_payload["source_evaluation_snapshot_id"] = payload["snapshot_id"]
        recalculate_snapshot_id(conflict_payload, "conflict-resolution-snapshot")
        request = EvidencePolicyRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=payload,
            conflict_resolution_snapshot=conflict_payload,
        )
        with self.assertRaises(EvidencePolicyValidationError):
            EvidencePolicyBuilderV0_1().build(request)

    def test_tampered_conflict_coverage_fails_closed(self) -> None:
        payload = self.conflict.to_dict()
        payload["coverage"]["candidate_count"] += 1
        recalculate_snapshot_id(payload, "conflict-resolution-snapshot")
        request = EvidencePolicyRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=payload,
        )
        with self.assertRaises(EvidencePolicyValidationError):
            EvidencePolicyBuilderV0_1().build(request)

    def test_tampered_resolution_preference_evidence_fails_closed(self) -> None:
        cases = (
            {
                "attempted_method": "PROVIDER_PRIORITY",
                "result_status": "AMBIGUOUS",
            },
            {
                "process_evidence": {
                    "nested_context": {"preferred_provider": "SYNTHETIC_PROVIDER"}
                },
            },
        )
        for changes in cases:
            with self.subTest(changes=changes):
                payload = self.conflict.to_dict()
                attempt = payload["resolution_attempts"][0]
                old_attempt_id = attempt["resolution_attempt_id"]
                attempt.update(changes)
                recalculate_attempt_and_conflict_snapshot(
                    payload, attempt, old_attempt_id
                )
                request = EvidencePolicyRequest(
                    canonical_bundles=self.bundles,
                    evidence_evaluation_snapshot=self.evaluation.to_dict(),
                    conflict_resolution_snapshot=payload,
                )
                with self.assertRaises(EvidencePolicyValidationError):
                    EvidencePolicyBuilderV0_1().build(request)

    def test_models_are_deeply_immutable_and_detached(self) -> None:
        definition = self.snapshot.policy_definitions[0]
        with self.assertRaises(FrozenInstanceError):
            definition.description = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            definition.conditions["changed"] = True  # type: ignore[index]
        evaluation = self.snapshot.policy_evaluations[0]
        with self.assertRaises(TypeError):
            evaluation.audit_metadata["changed"] = True  # type: ignore[index]
        source_payload = self.evaluation.to_dict()
        request = EvidencePolicyRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=source_payload,
            conflict_resolution_snapshot=self.conflict.to_dict(),
        )
        source_payload["support_records"][0]["provider_count"] = 999
        self.assertNotEqual(
            request.evidence_evaluation_snapshot["support_records"][0]["provider_count"],
            999,
        )

    def test_strict_serialization_round_trip_and_tamper_rejection(self) -> None:
        payload = self.snapshot.to_dict()
        restored = EvidencePolicySnapshotV0_1.from_dict(payload)
        self.assertEqual(restored, self.snapshot)
        self.assertEqual(canonical_json(restored), canonical_json(self.snapshot))
        payload["unexpected"] = True
        with self.assertRaises(EvidencePolicySerializationError):
            EvidencePolicySnapshotV0_1.from_dict(payload)
        identity_payload = self.snapshot.to_dict()
        identity_payload["snapshot_id"] = "evidence-policy-snapshot:tampered"
        with self.assertRaises(EvidencePolicySerializationError):
            EvidencePolicySnapshotV0_1.from_dict(identity_payload)
        coverage_payload = self.snapshot.to_dict()
        coverage_payload["coverage"]["conflict_count"] += 1
        recalculate_snapshot_id(coverage_payload, "evidence-policy-snapshot")
        with self.assertRaises(EvidencePolicySerializationError):
            EvidencePolicySnapshotV0_1.from_dict(coverage_payload)

    def test_determinism_ignores_bundle_and_record_order(self) -> None:
        built = build_policy(
            tuple(reversed(tuple(reordered(item) for item in self.bundles))),
            self.evaluation,
            self.conflict,
        )
        again = build_policy(self.bundles, self.evaluation, self.conflict)
        self.assertEqual(built.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(canonical_json(built), canonical_json(self.snapshot))
        self.assertEqual(canonical_json(again), canonical_json(self.snapshot))

    def test_determinism_is_stable_across_processes(self) -> None:
        script = (
            "from tests.test_evidence_policy_v0_1 import build_policy; "
            "from tests.test_conflict_resolution_v0_1 import synthetic_bundles,"
            "build_evaluation,build_resolution; "
            "b=synthetic_bundles(); e=build_evaluation(*b); c=build_resolution(b,e); "
            "print(build_policy(b,e,c).snapshot_id)"
        )
        first = subprocess.check_output(
            [sys.executable, "-c", script], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        second = subprocess.check_output(
            [sys.executable, "-c", script], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        self.assertEqual(first, self.snapshot.snapshot_id)
        self.assertEqual(second, first)

    def test_lineage_replays_every_required_layer(self) -> None:
        self.assertIs(
            self.snapshot.validate_against_bundles(self.bundles), self.snapshot
        )
        self.assertTrue(self.snapshot.lineage_index)
        conflict_lineage = next(
            item for item in self.snapshot.lineage_index
            if item.conflict_record_id is not None
        )
        self.assertTrue(conflict_lineage.support_record_id)
        self.assertTrue(conflict_lineage.conflict_analysis_id)
        self.assertTrue(conflict_lineage.conflict_candidate_id)
        self.assertTrue(conflict_lineage.resolution_attempt_ids)
        self.assertTrue(conflict_lineage.mapping_version)
        self.assertTrue(conflict_lineage.raw_evidence_id)
        self.assertTrue(conflict_lineage.collection_run_id)
        with self.assertRaises(EvidencePolicyValidationError):
            self.snapshot.validate_against_bundles((self.bundles[0],))
        with self.assertRaises(EvidencePolicyValidationError):
            self.snapshot.validate_against_bundles(({},))  # type: ignore[arg-type]

    def test_orphan_policy_lineage_is_rejected(self) -> None:
        payload = self.snapshot.to_dict()
        lineage = payload["lineage_index"][0]
        lineage["observation_id"] = "observation:orphan"
        lineage_content = dict(lineage)
        lineage_content.pop("policy_lineage_id")
        lineage["policy_lineage_id"] = deterministic_id(
            "policy-lineage", lineage_content
        )
        payload["lineage_index"] = sorted(
            payload["lineage_index"], key=lambda item: item["policy_lineage_id"]
        )
        recalculate_snapshot_id(payload, "evidence-policy-snapshot")
        restored = EvidencePolicySnapshotV0_1.from_dict(payload)
        with self.assertRaises(EvidencePolicyValidationError):
            restored.validate_against_bundles(self.bundles)

    def test_no_conflict_input_makes_conflict_policy_not_applicable(self) -> None:
        bundle = adapt("xiyou_info")
        evaluation = build_evaluation(bundle)
        conflict = build_resolution((bundle,), evaluation)
        built = build_policy((bundle,), evaluation, conflict)
        definitions = self.definitions_by_id(built)
        results = {definitions[item.policy_id]: item for item in built.policy_evaluations}
        self.assertEqual(
            results["CONFLICT_PRESENT"].evaluation_result, "NOT_APPLICABLE"
        )
        self.assertFalse(results["CONFLICT_PRESENT"].conflict_ids)
        self.assertEqual(built.coverage.conflict_count, 0)

    def test_all_allowed_outcomes_are_representable_without_truth(self) -> None:
        bundle = adapt("xiyou_info")
        evaluation = build_evaluation(bundle)
        conflict = build_resolution((bundle,), evaluation)
        no_conflict = build_policy((bundle,), evaluation, conflict)
        outcomes = {item.evaluation_result for item in self.snapshot.policy_evaluations}
        outcomes.update(item.evaluation_result for item in no_conflict.policy_evaluations)
        self.assertEqual(outcomes, {
            "NOT_APPLICABLE",
            "APPLICABLE_NO_ACTION",
            "ACTION_ALLOWED",
            "ACTION_BLOCKED",
        })

    def test_audit_trail_is_one_to_one_and_source_bound(self) -> None:
        self.assertEqual(len(self.snapshot.audit_records), 3)
        by_policy = {item.policy_id: item for item in self.snapshot.policy_evaluations}
        applicability = {
            item.policy_id: item for item in self.snapshot.policy_applicability_records
        }
        for audit in self.snapshot.audit_records:
            evaluation = by_policy[audit.policy_id]
            self.assertEqual(audit.policy_evaluation_id, evaluation.policy_evaluation_id)
            self.assertEqual(
                audit.policy_applicability_id,
                applicability[audit.policy_id].policy_applicability_id,
            )
            self.assertEqual(
                audit.source_evaluation_snapshot_id, self.evaluation.snapshot_id
            )
            self.assertEqual(
                audit.source_conflict_resolution_snapshot_id,
                self.conflict.snapshot_id,
            )

    def test_audit_metadata_rejects_conclusion_fields_recursively(self) -> None:
        original = self.snapshot.policy_evaluations[0]
        for field in (
            "winner",
            "score",
            "weight",
            "confidence",
            "trust",
            "recommendation",
            "ranking",
            "market_decision",
            "truth_value",
            "provider_priority",
        ):
            with self.subTest(field=field):
                payload = original.to_dict()
                payload["audit_metadata"] = {
                    "nested_context": {field: SYNTHETIC_CANONICAL_TEST_INPUT}
                }
                content = dict(payload)
                content.pop("policy_evaluation_id")
                payload["policy_evaluation_id"] = deterministic_id(
                    "policy-evaluation", content
                )
                with self.assertRaises(EvidencePolicySerializationError):
                    PolicyEvaluationRecord.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
