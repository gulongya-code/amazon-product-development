from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.decision_framework as decision_framework
from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.decision_framework import (
    DECISION_FRAMEWORK_RULESET_VERSION,
    DecisionEvaluationRecord,
    DecisionFrameworkBuilderV0_1,
    DecisionFrameworkRequest,
    DecisionFrameworkSerializationError,
    DecisionFrameworkSnapshotV0_1,
    DecisionFrameworkValidationError,
)
from tests.test_conflict_resolution_v0_1 import (
    adapt,
    build_evaluation,
    build_resolution,
    reordered,
    synthetic_bundles,
)
from tests.test_evidence_policy_v0_1 import build_policy


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_decision(bundles, evaluation, conflict, policy):
    return DecisionFrameworkBuilderV0_1().build(DecisionFrameworkRequest(
        canonical_bundles=tuple(bundles),
        evidence_evaluation_snapshot=evaluation.to_dict(),
        conflict_resolution_snapshot=conflict.to_dict(),
        evidence_policy_snapshot=policy.to_dict(),
    ))


def recalculate_snapshot_id(payload: dict[str, object], prefix: str) -> None:
    content = dict(payload)
    content.pop("snapshot_id")
    payload["snapshot_id"] = deterministic_id(prefix, content)


def recalculate_policy_evaluation_and_snapshot(
    payload: dict[str, object], evaluation: dict[str, object]
) -> None:
    old_evaluation_id = evaluation["policy_evaluation_id"]
    content = dict(evaluation)
    content.pop("policy_evaluation_id")
    evaluation["policy_evaluation_id"] = deterministic_id(
        "policy-evaluation", content
    )
    new_evaluation_id = evaluation["policy_evaluation_id"]
    for audit in payload["audit_records"]:
        if audit["policy_evaluation_id"] == old_evaluation_id:
            audit["policy_evaluation_id"] = new_evaluation_id
            audit["evaluation_result"] = evaluation["evaluation_result"]
            audit_content = dict(audit)
            audit_content.pop("policy_audit_id")
            audit["policy_audit_id"] = deterministic_id(
                "policy-audit", audit_content
            )
    for lineage in payload["lineage_index"]:
        if lineage["policy_evaluation_id"] == old_evaluation_id:
            lineage["policy_evaluation_id"] = new_evaluation_id
            lineage_content = dict(lineage)
            lineage_content.pop("policy_lineage_id")
            lineage["policy_lineage_id"] = deterministic_id(
                "policy-lineage", lineage_content
            )
    for diagnostic in payload["diagnostics"]:
        if old_evaluation_id in diagnostic["related_policy_evaluation_ids"]:
            diagnostic["related_policy_evaluation_ids"] = sorted(
                new_evaluation_id if item == old_evaluation_id else item
                for item in diagnostic["related_policy_evaluation_ids"]
            )
            diagnostic_content = dict(diagnostic)
            diagnostic_content.pop("diagnostic_id")
            diagnostic["diagnostic_id"] = deterministic_id(
                "policy-diagnostic", diagnostic_content
            )
    for name, key in (
        ("policy_evaluations", "policy_evaluation_id"),
        ("audit_records", "policy_audit_id"),
        ("lineage_index", "policy_lineage_id"),
        ("diagnostics", "diagnostic_id"),
    ):
        payload[name] = sorted(payload[name], key=lambda item: item[key])
    payload["coverage"]["evaluation_result_counts"] = dict(sorted(Counter(
        item["evaluation_result"] for item in payload["policy_evaluations"]
    ).items()))
    recalculate_snapshot_id(payload, "evidence-policy-snapshot")


class DecisionFrameworkFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundles = synthetic_bundles()
        cls.evaluation = build_evaluation(*cls.bundles)
        cls.conflict = build_resolution(cls.bundles, cls.evaluation)
        cls.policy = build_policy(cls.bundles, cls.evaluation, cls.conflict)
        cls.snapshot = build_decision(
            cls.bundles, cls.evaluation, cls.conflict, cls.policy
        )
        cls.definitions = {
            item.conditions["condition_type"]: item
            for item in cls.snapshot.rule_definitions
        }
        cls.results = {
            cls.definition_type(cls.snapshot, item.rule_id): item
            for item in cls.snapshot.decision_evaluations
        }
        cls.applicability = {
            cls.definition_type(cls.snapshot, item.rule_id): item
            for item in cls.snapshot.applicability_records
        }

    @staticmethod
    def definition_type(snapshot, rule_id):
        return next(
            item.conditions["condition_type"]
            for item in snapshot.rule_definitions
            if item.rule_id == rule_id
        )

    def test_public_api_is_explicit_and_closed(self) -> None:
        expected = {
            "DECISION_FRAMEWORK_RULESET_VERSION",
            "DecisionFrameworkRequest",
            "DecisionFrameworkSnapshotV0_1",
            "DecisionFrameworkBuilderV0_1",
            "DecisionFrameworkError",
            "DecisionFrameworkValidationError",
            "DecisionFrameworkSerializationError",
            "DecisionRuleDefinition",
            "DecisionApplicabilityRecord",
            "DecisionEvaluationRecord",
            "DecisionAuditRecord",
            "DecisionCoverageSummary",
            "DecisionLineageReference",
            "DecisionDiagnostic",
        }
        self.assertEqual(set(decision_framework.__all__), expected)
        self.assertEqual(len(decision_framework.__all__), 14)
        self.assertEqual(
            DECISION_FRAMEWORK_RULESET_VERSION, "decision-framework-v0.1"
        )
        self.assertTrue(expected <= set(vars(decision_framework)))

    def test_production_dependency_boundary_is_contracts_only(self) -> None:
        production = (
            REPOSITORY_ROOT
            / "src"
            / "amazon_product_intelligence"
            / "decision_framework"
        )
        forbidden = {
            "adapters",
            "product_intelligence",
            "demand_intelligence",
            "competition_intelligence",
            "opportunity_intelligence",
            "evidence_evaluation",
            "conflict_resolution",
            "evidence_policy",
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

    def test_rule_definitions_are_declarative_versioned_and_fixed(self) -> None:
        self.assertEqual(set(self.definitions), {
            "EVIDENCE_INVENTORY",
            "CONFLICT_FREE_EVIDENCE",
            "KEYWORD_EVIDENCE",
            "CONFLICT_CONTEXT",
        })
        for definition in self.snapshot.rule_definitions:
            self.assertEqual(definition.rule_version, "0.1")
            self.assertTrue(definition.description)
            self.assertIsInstance(definition.input_evidence_requirements, Mapping)
            self.assertIsInstance(definition.conditions, Mapping)
            self.assertNotIn("callable", definition.conditions)
            self.assertEqual(
                definition.rule_id,
                deterministic_id(
                    "decision-rule",
                    {
                        key: value
                        for key, value in definition.to_dict().items()
                        if key != "rule_id"
                    },
                ),
            )

    def test_real_integration_emits_rule_analysis_records_only(self) -> None:
        self.assertEqual(
            {
                condition: item.evaluation_result
                for condition, item in self.results.items()
            },
            {
                "EVIDENCE_INVENTORY": "RULE_ANALYSIS_RECORDED",
                "CONFLICT_FREE_EVIDENCE": "RULE_ANALYSIS_BLOCKED_BY_POLICY",
                "KEYWORD_EVIDENCE": "INSUFFICIENT_EVIDENCE",
                "CONFLICT_CONTEXT": "RULE_ANALYSIS_RECORDED",
            },
        )
        self.assertEqual(self.snapshot.coverage.rule_definition_count, 4)
        self.assertEqual(self.snapshot.coverage.input_evidence_count, 15)
        self.assertEqual(self.snapshot.coverage.conflict_count, 4)
        self.assertEqual(self.snapshot.coverage.lineage_reference_count, 120)

    def test_conflict_policy_blocks_rule_not_product(self) -> None:
        applies = self.applicability["CONFLICT_FREE_EVIDENCE"]
        result = self.results["CONFLICT_FREE_EVIDENCE"]
        self.assertEqual(applies.applicability_result, "BLOCKED_BY_POLICY")
        self.assertEqual(applies.policy_status, "POLICY_BLOCKED")
        self.assertEqual(result.evaluation_result, "RULE_ANALYSIS_BLOCKED_BY_POLICY")
        self.assertEqual(
            result.analysis_output["process_interpretation"],
            "ANALYSIS_RECORD_ONLY_NO_BUSINESS_CONCLUSION",
        )

    def test_conflict_context_preserves_conflict_without_resolution(self) -> None:
        result = self.results["CONFLICT_CONTEXT"]
        self.assertEqual(result.evaluation_result, "RULE_ANALYSIS_RECORDED")
        self.assertEqual(set(result.conflict_ids), {
            item.conflict_record_id for item in self.evaluation.conflict_records
        })
        self.assertFalse({
            "selected_candidate_id",
            "produced_candidate_id",
            "winner",
            "selected_provider",
        } & set(result.analysis_output))

    def test_missing_keyword_evidence_is_not_negative_evidence(self) -> None:
        applies = self.applicability["KEYWORD_EVIDENCE"]
        result = self.results["KEYWORD_EVIDENCE"]
        self.assertEqual(applies.applicability_result, "INSUFFICIENT_EVIDENCE")
        self.assertEqual(
            applies.missing_evidence_requirements,
            ("REQUIRED_EVIDENCE_KIND_MISSING",),
        )
        self.assertEqual(result.evaluation_result, "INSUFFICIENT_EVIDENCE")
        self.assertTrue(any(
            diagnostic.code == "MISSING_EVIDENCE_IS_NOT_NEGATIVE_CONCLUSION"
            and result.decision_evaluation_id
            in diagnostic.related_decision_evaluation_ids
            for diagnostic in self.snapshot.diagnostics
        ))

    def test_no_conflict_scenario_allows_conflict_free_rule(self) -> None:
        bundle = adapt("xiyou_info")
        evaluation = build_evaluation(bundle)
        conflict = build_resolution((bundle,), evaluation)
        policy = build_policy((bundle,), evaluation, conflict)
        snapshot = build_decision((bundle,), evaluation, conflict, policy)
        results = {
            self.definition_type(snapshot, item.rule_id): item
            for item in snapshot.decision_evaluations
        }
        applicability = {
            self.definition_type(snapshot, item.rule_id): item
            for item in snapshot.applicability_records
        }
        self.assertEqual(
            results["CONFLICT_FREE_EVIDENCE"].evaluation_result,
            "RULE_ANALYSIS_RECORDED",
        )
        self.assertEqual(
            applicability["CONFLICT_CONTEXT"].applicability_result,
            "NOT_APPLICABLE",
        )
        self.assertFalse(results["CONFLICT_FREE_EVIDENCE"].conflict_ids)

    def test_snapshot_contains_no_recommendation_score_rank_or_winner(self) -> None:
        forbidden = {
            "winner",
            "recommendation",
            "ranking",
            "score",
            "priority",
            "best_product",
            "best_keyword",
            "market_entry",
            "investment_decision",
            "business_conclusion",
            "product_selection",
            "roi",
            "profit_prediction",
            "revenue_prediction",
            "confidence_score",
            "trust_score",
            "selected_candidate_id",
            "selected_provider",
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

    def test_serialized_source_boundaries_are_strict(self) -> None:
        with self.assertRaises(DecisionFrameworkValidationError):
            DecisionFrameworkRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation,  # type: ignore[arg-type]
                conflict_resolution_snapshot=self.conflict.to_dict(),
                evidence_policy_snapshot=self.policy.to_dict(),
            )
        policy_payload = self.policy.to_dict()
        policy_payload["unexpected"] = True
        with self.assertRaises(DecisionFrameworkValidationError):
            DecisionFrameworkRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation.to_dict(),
                conflict_resolution_snapshot=self.conflict.to_dict(),
                evidence_policy_snapshot=policy_payload,
            )
        conflict_payload = self.conflict.to_dict()
        conflict_payload["snapshot_id"] = "conflict-resolution-snapshot:tampered"
        with self.assertRaises(DecisionFrameworkValidationError):
            DecisionFrameworkRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation.to_dict(),
                conflict_resolution_snapshot=conflict_payload,
                evidence_policy_snapshot=self.policy.to_dict(),
            )

    def test_tampered_policy_lineage_fails_closed(self) -> None:
        payload = self.policy.to_dict()
        lineage = payload["lineage_index"][0]
        lineage["support_record_id"] = "evidence-support:orphan"
        content = dict(lineage)
        content.pop("policy_lineage_id")
        lineage["policy_lineage_id"] = deterministic_id("policy-lineage", content)
        payload["lineage_index"] = sorted(
            payload["lineage_index"], key=lambda item: item["policy_lineage_id"]
        )
        recalculate_snapshot_id(payload, "evidence-policy-snapshot")
        request = DecisionFrameworkRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=self.conflict.to_dict(),
            evidence_policy_snapshot=payload,
        )
        with self.assertRaises(DecisionFrameworkValidationError):
            DecisionFrameworkBuilderV0_1().build(request)

    def test_tampered_policy_result_is_independently_replayed(self) -> None:
        payload = self.policy.to_dict()
        definitions = {
            item["policy_id"]: item["conditions"]["condition_type"]
            for item in payload["policy_definitions"]
        }
        evaluation = next(
            item
            for item in payload["policy_evaluations"]
            if definitions[item["policy_id"]] == "CONFLICT_PRESENT"
        )
        evaluation["evaluation_result"] = "ACTION_ALLOWED"
        recalculate_policy_evaluation_and_snapshot(payload, evaluation)
        request = DecisionFrameworkRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=self.conflict.to_dict(),
            evidence_policy_snapshot=payload,
        )
        with self.assertRaises(DecisionFrameworkValidationError):
            DecisionFrameworkBuilderV0_1().build(request)

    def test_models_are_deeply_immutable_and_detached(self) -> None:
        definition = self.snapshot.rule_definitions[0]
        with self.assertRaises(FrozenInstanceError):
            definition.description = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            definition.conditions["changed"] = True  # type: ignore[index]
        result = self.snapshot.decision_evaluations[0]
        with self.assertRaises(TypeError):
            result.analysis_output["changed"] = True  # type: ignore[index]
        source_payload = self.policy.to_dict()
        request = DecisionFrameworkRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=self.conflict.to_dict(),
            evidence_policy_snapshot=source_payload,
        )
        source_payload["policy_evaluations"][0]["evaluation_result"] = "TAMPERED"
        self.assertNotEqual(
            request.evidence_policy_snapshot["policy_evaluations"][0][
                "evaluation_result"
            ],
            "TAMPERED",
        )

    def test_strict_serialization_round_trip_and_tamper_rejection(self) -> None:
        payload = self.snapshot.to_dict()
        identity_content = dict(payload)
        identity_content.pop("snapshot_id")
        self.assertEqual(
            self.snapshot.snapshot_id,
            deterministic_id("decision-framework-snapshot", identity_content),
        )
        restored = DecisionFrameworkSnapshotV0_1.from_dict(payload)
        self.assertEqual(restored, self.snapshot)
        self.assertEqual(canonical_json(restored), canonical_json(self.snapshot))
        payload["unexpected"] = True
        with self.assertRaises(DecisionFrameworkSerializationError):
            DecisionFrameworkSnapshotV0_1.from_dict(payload)
        identity_payload = self.snapshot.to_dict()
        identity_payload["snapshot_id"] = "decision-framework-snapshot:tampered"
        with self.assertRaises(DecisionFrameworkSerializationError):
            DecisionFrameworkSnapshotV0_1.from_dict(identity_payload)
        coverage_payload = self.snapshot.to_dict()
        coverage_payload["coverage"]["conflict_count"] += 1
        recalculate_snapshot_id(coverage_payload, "decision-framework-snapshot")
        with self.assertRaises(DecisionFrameworkSerializationError):
            DecisionFrameworkSnapshotV0_1.from_dict(coverage_payload)

    def test_determinism_ignores_bundle_and_record_order(self) -> None:
        built = build_decision(
            tuple(reversed(tuple(reordered(item) for item in self.bundles))),
            self.evaluation,
            self.conflict,
            self.policy,
        )
        again = build_decision(
            self.bundles, self.evaluation, self.conflict, self.policy
        )
        self.assertEqual(built.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(canonical_json(built), canonical_json(self.snapshot))
        self.assertEqual(canonical_json(again), canonical_json(self.snapshot))

    def test_determinism_is_stable_across_processes(self) -> None:
        script = (
            "from tests.test_decision_framework_v0_1 import build_decision; "
            "from tests.test_conflict_resolution_v0_1 import synthetic_bundles,"
            "build_evaluation,build_resolution; "
            "from tests.test_evidence_policy_v0_1 import build_policy; "
            "b=synthetic_bundles(); e=build_evaluation(*b); c=build_resolution(b,e); "
            "p=build_policy(b,e,c); print(build_decision(b,e,c,p).snapshot_id)"
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
        lineage = next(
            item for item in self.snapshot.lineage_index
            if item.conflict_record_id is not None
        )
        self.assertTrue(lineage.policy_evaluation_id)
        self.assertTrue(lineage.conflict_analysis_id)
        self.assertTrue(lineage.conflict_candidate_id)
        self.assertTrue(lineage.resolution_attempt_ids)
        self.assertTrue(lineage.transformation_run_id)
        self.assertTrue(lineage.mapping_version)
        self.assertTrue(lineage.raw_evidence_id)
        self.assertTrue(lineage.collection_run_id)
        with self.assertRaises(DecisionFrameworkValidationError):
            self.snapshot.validate_against_bundles((self.bundles[0],))

    def test_orphan_decision_lineage_is_rejected(self) -> None:
        payload = self.snapshot.to_dict()
        lineage = payload["lineage_index"][0]
        lineage["observation_id"] = "observation:orphan"
        content = dict(lineage)
        content.pop("decision_lineage_id")
        lineage["decision_lineage_id"] = deterministic_id(
            "decision-lineage", content
        )
        payload["lineage_index"] = sorted(
            payload["lineage_index"], key=lambda item: item["decision_lineage_id"]
        )
        recalculate_snapshot_id(payload, "decision-framework-snapshot")
        restored = DecisionFrameworkSnapshotV0_1.from_dict(payload)
        with self.assertRaises(DecisionFrameworkValidationError):
            restored.validate_against_bundles(self.bundles)

    def test_audit_trail_is_one_to_one_and_source_bound(self) -> None:
        self.assertEqual(len(self.snapshot.audit_records), 4)
        evaluations = {
            item.rule_id: item for item in self.snapshot.decision_evaluations
        }
        applicability = {
            item.rule_id: item for item in self.snapshot.applicability_records
        }
        for audit in self.snapshot.audit_records:
            evaluation = evaluations[audit.rule_id]
            definition = next(
                item
                for item in self.snapshot.rule_definitions
                if item.rule_id == audit.rule_id
            )
            self.assertEqual(
                audit.decision_evaluation_id,
                evaluation.decision_evaluation_id,
            )
            self.assertEqual(
                audit.decision_applicability_id,
                applicability[audit.rule_id].decision_applicability_id,
            )
            self.assertEqual(
                audit.source_evaluation_snapshot_id, self.evaluation.snapshot_id
            )
            self.assertEqual(
                audit.source_conflict_resolution_snapshot_id,
                self.conflict.snapshot_id,
            )
            self.assertEqual(
                audit.source_policy_snapshot_id, self.policy.snapshot_id
            )
            self.assertEqual(
                evaluation.audit_metadata,
                {
                    "condition_type": definition.conditions["condition_type"],
                    "source_evaluation_snapshot_id": self.evaluation.snapshot_id,
                    "source_conflict_resolution_snapshot_id": self.conflict.snapshot_id,
                    "source_policy_snapshot_id": self.policy.snapshot_id,
                },
            )

    def test_analysis_output_rejects_conclusion_fields(self) -> None:
        original = self.snapshot.decision_evaluations[0]
        payload = original.to_dict()
        payload["analysis_output"]["best_product"] = "SYNTHETIC_PRODUCT"
        content = dict(payload)
        content.pop("decision_evaluation_id")
        payload["decision_evaluation_id"] = deterministic_id(
            "decision-evaluation", content
        )
        with self.assertRaises(DecisionFrameworkSerializationError):
            DecisionEvaluationRecord.from_dict(payload)

    def test_builder_does_not_mutate_upstream_snapshots(self) -> None:
        evaluation = self.evaluation.to_dict()
        conflict = self.conflict.to_dict()
        policy = self.policy.to_dict()
        expected = (
            canonical_json(evaluation),
            canonical_json(conflict),
            canonical_json(policy),
        )
        request = DecisionFrameworkRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=evaluation,
            conflict_resolution_snapshot=conflict,
            evidence_policy_snapshot=policy,
        )
        DecisionFrameworkBuilderV0_1().build(request)
        self.assertEqual(
            expected,
            (
                canonical_json(evaluation),
                canonical_json(conflict),
                canonical_json(policy),
            ),
        )


if __name__ == "__main__":
    unittest.main()
