from __future__ import annotations

import ast
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.opportunity_scoring as opportunity_scoring
from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.opportunity_scoring import (
    OPPORTUNITY_SCORING_RULESET_VERSION,
    OpportunityScoringBuilderV0_1,
    OpportunityScoringRequest,
    OpportunityScoringSerializationError,
    OpportunityScoringSnapshotV0_1,
    OpportunityScoringValidationError,
    ScoreCalculationRecord,
)
from tests.test_conflict_resolution_v0_1 import (
    adapt,
    build_evaluation,
    build_resolution,
    reordered,
    synthetic_bundles,
)
from tests.test_decision_framework_v0_1 import build_decision
from tests.test_evidence_policy_v0_1 import build_policy


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_score(bundles, evaluation, conflict, policy, decision):
    return OpportunityScoringBuilderV0_1().build(OpportunityScoringRequest(
        canonical_bundles=tuple(bundles),
        evidence_evaluation_snapshot=evaluation.to_dict(),
        conflict_resolution_snapshot=conflict.to_dict(),
        evidence_policy_snapshot=policy.to_dict(),
        decision_framework_snapshot=decision.to_dict(),
    ))


def recalculate_snapshot_id(payload: dict[str, object], prefix: str) -> None:
    content = dict(payload)
    content.pop("snapshot_id")
    payload["snapshot_id"] = deterministic_id(prefix, content)


class OpportunityScoringFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundles = synthetic_bundles()
        cls.evaluation = build_evaluation(*cls.bundles)
        cls.conflict = build_resolution(cls.bundles, cls.evaluation)
        cls.policy = build_policy(cls.bundles, cls.evaluation, cls.conflict)
        cls.decision = build_decision(
            cls.bundles, cls.evaluation, cls.conflict, cls.policy
        )
        cls.snapshot = build_score(
            cls.bundles,
            cls.evaluation,
            cls.conflict,
            cls.policy,
            cls.decision,
        )
        cls.factors_by_condition = {
            item.input_requirements["decision_condition_type"]: item
            for item in cls.snapshot.score_factors
        }
        cls.components_by_condition = {
            cls.condition_for_factor(item.factor_id): item
            for item in cls.snapshot.components
        }
        cls.calculations_by_condition = {
            cls.condition_for_factor(item.factor_id): item
            for item in cls.snapshot.calculations
        }

    @classmethod
    def condition_for_factor(cls, factor_id):
        return next(
            item.input_requirements["decision_condition_type"]
            for item in cls.snapshot.score_factors
            if item.factor_id == factor_id
        )

    def test_public_api_is_explicit_and_closed(self) -> None:
        expected = {
            "OPPORTUNITY_SCORING_RULESET_VERSION",
            "OpportunityScoringRequest",
            "OpportunityScoringSnapshotV0_1",
            "OpportunityScoringBuilderV0_1",
            "OpportunityScoringError",
            "OpportunityScoringValidationError",
            "OpportunityScoringSerializationError",
            "ScoreFactorDefinition",
            "ScoreComponentRecord",
            "ScoreCalculationRecord",
            "ScoreExplanationRecord",
            "ScoreCoverageSummary",
            "ScoreLineageReference",
            "ScoreDiagnostic",
        }
        self.assertEqual(set(opportunity_scoring.__all__), expected)
        self.assertEqual(len(opportunity_scoring.__all__), 14)
        self.assertEqual(
            OPPORTUNITY_SCORING_RULESET_VERSION,
            "opportunity-scoring-v0.1",
        )
        self.assertTrue(expected <= set(vars(opportunity_scoring)))

    def test_production_dependency_boundary_is_contracts_only(self) -> None:
        production = (
            REPOSITORY_ROOT
            / "src"
            / "amazon_product_intelligence"
            / "opportunity_scoring"
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
            "decision_framework",
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

    def test_factor_definitions_are_fixed_declarative_and_versioned(self) -> None:
        self.assertEqual(set(self.factors_by_condition), {
            "EVIDENCE_INVENTORY",
            "CONFLICT_FREE_EVIDENCE",
            "KEYWORD_EVIDENCE",
            "CONFLICT_CONTEXT",
        })
        for factor in self.snapshot.score_factors:
            self.assertEqual(factor.factor_version, "0.1")
            self.assertIsInstance(factor.input_requirements, Mapping)
            self.assertEqual(
                factor.explanation_template,
                "Explain the factor rule, evidence references, calculation method, "
                "version, process status, and bounded interpretation.",
            )
            self.assertEqual(
                factor.calculation_rule,
                {
                    "calculation_method": "FIXED_PROCESS_RULE_RESULT_V0_1",
                    "conflict_behavior": "PRESERVE_AND_MARK_VISIBLE",
                    "missing_evidence_behavior": "EXCLUDE_WITHOUT_NUMERIC_RESULT",
                    "policy_block_behavior": "UNAVAILABLE_WITHOUT_NUMERIC_RESULT",
                },
            )
            self.assertEqual(
                factor.factor_id,
                deterministic_id(
                    "score-factor",
                    {
                        key: value
                        for key, value in factor.to_dict().items()
                        if key != "factor_id"
                    },
                ),
            )

    def test_real_integration_emits_audited_component_states(self) -> None:
        self.assertEqual(
            {
                condition: item.result_status
                for condition, item in self.calculations_by_condition.items()
            },
            {
                "EVIDENCE_INVENTORY": "CALCULATED_WITH_CONFLICT_VISIBLE",
                "CONFLICT_FREE_EVIDENCE": "BLOCKED_BY_POLICY",
                "KEYWORD_EVIDENCE": "EXCLUDED_MISSING_EVIDENCE",
                "CONFLICT_CONTEXT": "CALCULATED_WITH_CONFLICT_VISIBLE",
            },
        )
        self.assertEqual(self.snapshot.coverage.factor_definition_count, 4)
        self.assertEqual(self.snapshot.coverage.component_count, 4)
        self.assertEqual(self.snapshot.coverage.calculation_count, 4)
        self.assertEqual(self.snapshot.coverage.input_evidence_count, 15)
        self.assertEqual(self.snapshot.coverage.conflict_reference_count, 4)
        self.assertEqual(self.snapshot.coverage.lineage_reference_count, 120)
        self.assertTrue(all(
            item.component_explanation for item in self.snapshot.components
        ))

    def test_numeric_results_exist_only_in_calculation_records(self) -> None:
        payload = self.snapshot.to_dict()

        def result_value_paths(value, path=""):
            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{path}.{key}" if path else key
                    if key == "result_value":
                        yield child_path
                    yield from result_value_paths(child, child_path)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    yield from result_value_paths(child, f"{path}[{index}]")

        paths = tuple(result_value_paths(payload))
        self.assertEqual(len(paths), 4)
        self.assertTrue(all(path.startswith("calculations[") for path in paths))
        values = [item.result_value for item in self.snapshot.calculations]
        self.assertEqual(values.count(25), 2)
        self.assertEqual(values.count(None), 2)
        self.assertTrue(all(
            item.decision_lineage_ids for item in self.snapshot.calculations
        ))
        self.assertFalse(hasattr(self.snapshot, "total_score"))

    def test_missing_evidence_is_excluded_and_never_silent_zero(self) -> None:
        calculation = self.calculations_by_condition["KEYWORD_EVIDENCE"]
        component = self.components_by_condition["KEYWORD_EVIDENCE"]
        self.assertEqual(calculation.result_status, "EXCLUDED_MISSING_EVIDENCE")
        self.assertIsNone(calculation.result_value)
        self.assertIn("MISSING_EVIDENCE_EXCLUDED_NOT_ZERO", component.reason_codes)
        explanation = next(
            item
            for item in self.snapshot.explanations
            if item.calculation_id == calculation.calculation_id
        )
        self.assertIn("not treated as zero", explanation.result_interpretation)

    def test_policy_block_makes_component_unavailable_not_product_rejected(self) -> None:
        calculation = self.calculations_by_condition["CONFLICT_FREE_EVIDENCE"]
        self.assertEqual(calculation.result_status, "BLOCKED_BY_POLICY")
        self.assertIsNone(calculation.result_value)
        self.assertTrue(any(
            item.code == "SCORE_COMPONENT_BLOCKED_BY_POLICY"
            and calculation.calculation_id in item.related_calculation_ids
            for item in self.snapshot.diagnostics
        ))
        explanation = next(
            item
            for item in self.snapshot.explanations
            if item.calculation_id == calculation.calculation_id
        )
        self.assertIn("no product or market was rejected", explanation.result_interpretation)

    def test_conflict_is_visible_without_candidate_selection(self) -> None:
        calculation = self.calculations_by_condition["CONFLICT_CONTEXT"]
        self.assertEqual(
            calculation.result_status, "CALCULATED_WITH_CONFLICT_VISIBLE"
        )
        self.assertEqual(calculation.result_value, 25)
        self.assertEqual(
            set(calculation.conflict_ids),
            {item.conflict_record_id for item in self.evaluation.conflict_records},
        )
        payload = self.snapshot.to_dict()
        keys = {
            key.casefold()
            for calculation_payload in payload["calculations"]
            for key in calculation_payload
        }
        self.assertFalse({
            "winner",
            "selected_candidate_id",
            "produced_candidate_id",
            "selected_provider",
        } & keys)

    def test_no_conflict_scenario_calculates_available_rules(self) -> None:
        bundle = adapt("xiyou_info")
        evaluation = build_evaluation(bundle)
        conflict = build_resolution((bundle,), evaluation)
        policy = build_policy((bundle,), evaluation, conflict)
        decision = build_decision((bundle,), evaluation, conflict, policy)
        snapshot = build_score(
            (bundle,), evaluation, conflict, policy, decision
        )
        calculations = {
            next(
                factor.input_requirements["decision_condition_type"]
                for factor in snapshot.score_factors
                if factor.factor_id == item.factor_id
            ): item
            for item in snapshot.calculations
        }
        self.assertEqual(
            calculations["EVIDENCE_INVENTORY"].result_status, "CALCULATED"
        )
        self.assertEqual(
            calculations["CONFLICT_FREE_EVIDENCE"].result_status, "CALCULATED"
        )
        self.assertEqual(
            calculations["CONFLICT_CONTEXT"].result_status, "NOT_APPLICABLE"
        )
        self.assertIsNone(calculations["CONFLICT_CONTEXT"].result_value)

    def test_every_calculation_has_complete_explanation(self) -> None:
        explanations = {
            item.calculation_id: item for item in self.snapshot.explanations
        }
        for calculation in self.snapshot.calculations:
            explanation = explanations[calculation.calculation_id]
            self.assertTrue(explanation.factor_explanation)
            self.assertEqual(
                explanation.calculation_rule, calculation.calculation_method
            )
            self.assertEqual(explanation.version, calculation.version)
            self.assertEqual(explanation.evidence_ids, calculation.evidence_ids)
            self.assertEqual(
                explanation.decision_evaluation_ids,
                calculation.decision_evaluation_ids,
            )
            self.assertEqual(
                explanation.policy_evaluation_ids,
                calculation.policy_evaluation_ids,
            )

    def test_snapshot_has_no_ranking_recommendation_or_business_decision_fields(self) -> None:
        forbidden = {
            "winner",
            "recommendation",
            "ranking",
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
            "selected_candidate_id",
            "selected_provider",
            "total_score",
            "overall_score",
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

    def test_serialized_source_boundaries_are_strict_and_source_bound(self) -> None:
        with self.assertRaises(OpportunityScoringValidationError):
            OpportunityScoringRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation,  # type: ignore[arg-type]
                conflict_resolution_snapshot=self.conflict.to_dict(),
                evidence_policy_snapshot=self.policy.to_dict(),
                decision_framework_snapshot=self.decision.to_dict(),
            )
        decision_payload = self.decision.to_dict()
        decision_payload["unexpected"] = True
        with self.assertRaises(OpportunityScoringValidationError):
            OpportunityScoringRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation.to_dict(),
                conflict_resolution_snapshot=self.conflict.to_dict(),
                evidence_policy_snapshot=self.policy.to_dict(),
                decision_framework_snapshot=decision_payload,
            )
        policy_payload = self.policy.to_dict()
        policy_payload["snapshot_id"] = "evidence-policy-snapshot:tampered"
        with self.assertRaises(OpportunityScoringValidationError):
            OpportunityScoringRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation.to_dict(),
                conflict_resolution_snapshot=self.conflict.to_dict(),
                evidence_policy_snapshot=policy_payload,
                decision_framework_snapshot=self.decision.to_dict(),
            )

    def test_tampered_decision_lineage_fails_closed(self) -> None:
        payload = self.decision.to_dict()
        lineage = payload["lineage_index"][0]
        lineage["support_record_id"] = "evidence-support:orphan"
        content = dict(lineage)
        content.pop("decision_lineage_id")
        lineage["decision_lineage_id"] = deterministic_id(
            "decision-lineage", content
        )
        payload["lineage_index"] = sorted(
            payload["lineage_index"], key=lambda item: item["decision_lineage_id"]
        )
        recalculate_snapshot_id(payload, "decision-framework-snapshot")
        request = OpportunityScoringRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=self.conflict.to_dict(),
            evidence_policy_snapshot=self.policy.to_dict(),
            decision_framework_snapshot=payload,
        )
        with self.assertRaises(OpportunityScoringValidationError):
            OpportunityScoringBuilderV0_1().build(request)

    def test_models_are_deeply_immutable_and_detached(self) -> None:
        factor = self.snapshot.score_factors[0]
        with self.assertRaises(FrozenInstanceError):
            factor.description = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            factor.calculation_rule["changed"] = True  # type: ignore[index]
        decision_payload = self.decision.to_dict()
        request = OpportunityScoringRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=self.conflict.to_dict(),
            evidence_policy_snapshot=self.policy.to_dict(),
            decision_framework_snapshot=decision_payload,
        )
        decision_payload["decision_evaluations"][0]["evaluation_result"] = "TAMPERED"
        self.assertNotEqual(
            request.decision_framework_snapshot["decision_evaluations"][0][
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
            deterministic_id("opportunity-scoring-snapshot", identity_content),
        )
        restored = OpportunityScoringSnapshotV0_1.from_dict(payload)
        self.assertEqual(restored, self.snapshot)
        self.assertEqual(canonical_json(restored), canonical_json(self.snapshot))
        payload["unexpected"] = True
        with self.assertRaises(OpportunityScoringSerializationError):
            OpportunityScoringSnapshotV0_1.from_dict(payload)
        identity_payload = self.snapshot.to_dict()
        identity_payload["snapshot_id"] = "opportunity-scoring-snapshot:tampered"
        with self.assertRaises(OpportunityScoringSerializationError):
            OpportunityScoringSnapshotV0_1.from_dict(identity_payload)
        missing_factor = self.snapshot.to_dict()
        removed_factor_id = missing_factor["score_factors"][0]["factor_id"]
        missing_factor["score_factors"] = missing_factor["score_factors"][1:]
        recalculate_snapshot_id(missing_factor, "opportunity-scoring-snapshot")
        with self.assertRaises(OpportunityScoringSerializationError):
            OpportunityScoringSnapshotV0_1.from_dict(missing_factor)
        unexplained = self.snapshot.to_dict()
        unexplained["explanations"] = [
            item
            for item in unexplained["explanations"]
            if item["factor_id"] != removed_factor_id
        ]
        recalculate_snapshot_id(unexplained, "opportunity-scoring-snapshot")
        with self.assertRaises(OpportunityScoringSerializationError):
            OpportunityScoringSnapshotV0_1.from_dict(unexplained)

    def test_unavailable_calculation_rejects_numeric_result(self) -> None:
        original = self.calculations_by_condition["KEYWORD_EVIDENCE"]
        payload = original.to_dict()
        payload["result_value"] = 0
        content = dict(payload)
        content.pop("calculation_id")
        payload["calculation_id"] = deterministic_id(
            "score-calculation", content
        )
        with self.assertRaises(OpportunityScoringSerializationError):
            ScoreCalculationRecord.from_dict(payload)

    def test_determinism_ignores_bundle_and_record_order(self) -> None:
        built = build_score(
            tuple(reversed(tuple(reordered(item) for item in self.bundles))),
            self.evaluation,
            self.conflict,
            self.policy,
            self.decision,
        )
        again = build_score(
            self.bundles,
            self.evaluation,
            self.conflict,
            self.policy,
            self.decision,
        )
        self.assertEqual(built.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(canonical_json(built), canonical_json(self.snapshot))
        self.assertEqual(canonical_json(again), canonical_json(self.snapshot))

    def test_determinism_is_stable_across_processes(self) -> None:
        script = (
            "from tests.test_opportunity_scoring_v0_1 import build_score; "
            "from tests.test_conflict_resolution_v0_1 import synthetic_bundles,"
            "build_evaluation,build_resolution; "
            "from tests.test_evidence_policy_v0_1 import build_policy; "
            "from tests.test_decision_framework_v0_1 import build_decision; "
            "b=synthetic_bundles(); e=build_evaluation(*b); c=build_resolution(b,e); "
            "p=build_policy(b,e,c); d=build_decision(b,e,c,p); "
            "print(build_score(b,e,c,p,d).snapshot_id)"
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
            item
            for item in self.snapshot.lineage_index
            if item.conflict_record_id is not None
        )
        self.assertTrue(lineage.calculation_id)
        self.assertTrue(lineage.decision_evaluation_id)
        self.assertTrue(lineage.decision_lineage_id)
        calculation = next(
            item
            for item in self.snapshot.calculations
            if item.calculation_id == lineage.calculation_id
        )
        self.assertIn(lineage.decision_lineage_id, calculation.decision_lineage_ids)
        self.assertTrue(lineage.policy_evaluation_id)
        self.assertTrue(lineage.conflict_analysis_id)
        self.assertTrue(lineage.conflict_candidate_id)
        self.assertTrue(lineage.resolution_attempt_ids)
        self.assertTrue(lineage.support_record_id)
        self.assertTrue(lineage.transformation_run_id)
        self.assertTrue(lineage.mapping_version)
        self.assertTrue(lineage.raw_evidence_id)
        self.assertTrue(lineage.collection_run_id)
        with self.assertRaises(OpportunityScoringValidationError):
            self.snapshot.validate_against_bundles((self.bundles[0],))

    def test_orphan_score_lineage_is_rejected_on_bundle_replay(self) -> None:
        payload = self.snapshot.to_dict()
        lineage = payload["lineage_index"][0]
        lineage["observation_id"] = "observation:orphan"
        content = dict(lineage)
        content.pop("score_lineage_id")
        lineage["score_lineage_id"] = deterministic_id(
            "score-lineage", content
        )
        payload["lineage_index"] = sorted(
            payload["lineage_index"], key=lambda item: item["score_lineage_id"]
        )
        recalculate_snapshot_id(payload, "opportunity-scoring-snapshot")
        restored = OpportunityScoringSnapshotV0_1.from_dict(payload)
        with self.assertRaises(OpportunityScoringValidationError):
            restored.validate_against_bundles(self.bundles)

    def test_builder_does_not_mutate_upstream_snapshots(self) -> None:
        evaluation = self.evaluation.to_dict()
        conflict = self.conflict.to_dict()
        policy = self.policy.to_dict()
        decision = self.decision.to_dict()
        expected = tuple(canonical_json(item) for item in (
            evaluation, conflict, policy, decision
        ))
        request = OpportunityScoringRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=evaluation,
            conflict_resolution_snapshot=conflict,
            evidence_policy_snapshot=policy,
            decision_framework_snapshot=decision,
        )
        OpportunityScoringBuilderV0_1().build(request)
        self.assertEqual(
            expected,
            tuple(canonical_json(item) for item in (
                evaluation, conflict, policy, decision
            )),
        )


if __name__ == "__main__":
    unittest.main()
