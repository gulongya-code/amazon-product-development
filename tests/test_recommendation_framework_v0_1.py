from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Mapping
from dataclasses import FrozenInstanceError
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.recommendation_framework as recommendation
from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.recommendation_framework import (
    RECOMMENDATION_FRAMEWORK_RULESET_VERSION,
    RecommendationFrameworkBuilderV0_1,
    RecommendationFrameworkRequest,
    RecommendationFrameworkSerializationError,
    RecommendationFrameworkSnapshotV0_1,
    RecommendationFrameworkValidationError,
    RecommendationRuleDefinition,
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
from tests.test_opportunity_scoring_v0_1 import build_score


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_recommendation(bundles, evaluation, conflict, policy, decision, scoring):
    return RecommendationFrameworkBuilderV0_1().build(
        RecommendationFrameworkRequest(
            canonical_bundles=tuple(bundles),
            evidence_evaluation_snapshot=evaluation.to_dict(),
            conflict_resolution_snapshot=conflict.to_dict(),
            evidence_policy_snapshot=policy.to_dict(),
            decision_framework_snapshot=decision.to_dict(),
            opportunity_scoring_snapshot=scoring.to_dict(),
        )
    )


def recalculate_snapshot_id(payload: dict[str, object], prefix: str) -> None:
    content = dict(payload)
    content.pop("snapshot_id")
    payload["snapshot_id"] = deterministic_id(prefix, content)


class RecommendationFrameworkFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundles = synthetic_bundles()
        cls.evaluation = build_evaluation(*cls.bundles)
        cls.conflict = build_resolution(cls.bundles, cls.evaluation)
        cls.policy = build_policy(cls.bundles, cls.evaluation, cls.conflict)
        cls.decision = build_decision(
            cls.bundles, cls.evaluation, cls.conflict, cls.policy
        )
        cls.scoring = build_score(
            cls.bundles,
            cls.evaluation,
            cls.conflict,
            cls.policy,
            cls.decision,
        )
        cls.snapshot = build_recommendation(
            cls.bundles,
            cls.evaluation,
            cls.conflict,
            cls.policy,
            cls.decision,
            cls.scoring,
        )
        cls.rules_by_condition = {
            item.input_requirements["decision_condition_type"]: item
            for item in cls.snapshot.recommendation_rules
        }
        cls.generations_by_condition = {
            cls.condition_for_rule(item.rule_id): item
            for item in cls.snapshot.generation_records
        }
        cls.applicability_by_condition = {
            cls.condition_for_rule(item.rule_id): item
            for item in cls.snapshot.applicability_records
        }

    @classmethod
    def condition_for_rule(cls, rule_id):
        return next(
            item.input_requirements["decision_condition_type"]
            for item in cls.snapshot.recommendation_rules
            if item.rule_id == rule_id
        )

    def test_public_api_is_explicit_and_closed(self) -> None:
        expected = {
            "RECOMMENDATION_FRAMEWORK_RULESET_VERSION",
            "RecommendationFrameworkRequest",
            "RecommendationFrameworkSnapshotV0_1",
            "RecommendationFrameworkBuilderV0_1",
            "RecommendationFrameworkError",
            "RecommendationFrameworkValidationError",
            "RecommendationFrameworkSerializationError",
            "RecommendationRuleDefinition",
            "RecommendationApplicabilityRecord",
            "RecommendationGenerationRecord",
            "RecommendationExplanationRecord",
            "RecommendationCoverageSummary",
            "RecommendationLineageReference",
            "RecommendationDiagnostic",
        }
        self.assertEqual(set(recommendation.__all__), expected)
        self.assertEqual(len(recommendation.__all__), 14)
        self.assertEqual(
            RECOMMENDATION_FRAMEWORK_RULESET_VERSION,
            "recommendation-framework-v0.1",
        )
        self.assertTrue(expected <= set(vars(recommendation)))

    def test_production_dependency_boundary_is_contracts_only(self) -> None:
        production = (
            REPOSITORY_ROOT
            / "src"
            / "amazon_product_intelligence"
            / "recommendation_framework"
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
            "opportunity_scoring",
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

    def test_rule_definitions_are_fixed_declarative_and_versioned(self) -> None:
        self.assertEqual(set(self.rules_by_condition), {
            "EVIDENCE_INVENTORY",
            "CONFLICT_FREE_EVIDENCE",
            "KEYWORD_EVIDENCE",
            "CONFLICT_CONTEXT",
        })
        expected_conditions = {
            "calculated_behavior": "RULE_CONDITIONS_SATISFIED",
            "conflict_visible_behavior": "FURTHER_REVIEW_RECOMMENDED",
            "missing_evidence_behavior": "EVIDENCE_COLLECTION_RECOMMENDED",
            "policy_blocked_behavior": "RECOMMENDATION_BLOCKED_BY_POLICY",
            "not_applicable_behavior": "RULE_NOT_APPLICABLE",
        }
        for rule in self.snapshot.recommendation_rules:
            self.assertEqual(rule.rule_version, "0.1")
            self.assertIsInstance(rule.input_requirements, Mapping)
            self.assertEqual(rule.conditions, expected_conditions)
            self.assertNotIn("callable", rule.conditions)
            self.assertEqual(
                rule.rule_id,
                deterministic_id(
                    "recommendation-rule",
                    {
                        key: value
                        for key, value in rule.to_dict().items()
                        if key != "rule_id"
                    },
                ),
            )

    def test_real_integration_generates_bounded_advisory_records(self) -> None:
        self.assertEqual(
            Counter(
                item.recommendation_type
                for item in self.snapshot.generation_records
            ),
            {
                "FURTHER_REVIEW_RECOMMENDED": 2,
                "RECOMMENDATION_BLOCKED_BY_POLICY": 2,
            },
        )
        self.assertEqual(self.snapshot.coverage.rule_definition_count, 4)
        self.assertEqual(self.snapshot.coverage.generation_record_count, 4)
        self.assertEqual(self.snapshot.coverage.score_calculation_reference_count, 4)
        self.assertEqual(self.snapshot.coverage.input_evidence_count, 15)
        self.assertEqual(self.snapshot.coverage.conflict_reference_count, 4)
        self.assertEqual(self.snapshot.coverage.lineage_reference_count, 120)

    def test_generation_preserves_score_decision_policy_and_evidence_references(self) -> None:
        calculations = {
            item.calculation_id: item for item in self.scoring.calculations
        }
        for generation in self.snapshot.generation_records:
            self.assertEqual(len(generation.score_calculation_ids), 1)
            calculation = calculations[generation.score_calculation_ids[0]]
            self.assertEqual(
                generation.decision_evaluation_ids,
                calculation.decision_evaluation_ids,
            )
            self.assertEqual(
                generation.policy_evaluation_ids,
                calculation.policy_evaluation_ids,
            )
            self.assertEqual(generation.conflict_ids, calculation.conflict_ids)
            self.assertEqual(generation.input_evidence_ids, calculation.evidence_ids)
            self.assertEqual(
                generation.process_interpretation,
                "RULE_GENERATED_ADVISORY_RECORD_NOT_FACTUAL_TRUTH_OR_FINAL_DECISION",
            )

    def test_policy_block_blocks_recommendation_not_product(self) -> None:
        for condition in ("CONFLICT_FREE_EVIDENCE", "KEYWORD_EVIDENCE"):
            applies = self.applicability_by_condition[condition]
            generation = self.generations_by_condition[condition]
            self.assertEqual(applies.policy_status, "POLICY_BLOCKED")
            self.assertEqual(applies.applicability_result, "BLOCKED_BY_POLICY")
            self.assertEqual(
                generation.recommendation_type,
                "RECOMMENDATION_BLOCKED_BY_POLICY",
            )
        blocked = [
            item
            for item in self.snapshot.diagnostics
            if item.code == "RECOMMENDATION_BLOCKED_BY_POLICY"
        ]
        self.assertEqual(len(blocked), 2)
        self.assertTrue(all(
            "without rejecting a product or market" in item.message
            for item in blocked
        ))

    def test_missing_evidence_without_policy_block_recommends_collection(self) -> None:
        bundle = adapt("xiyou_info")
        evaluation = build_evaluation(bundle)
        conflict = build_resolution((bundle,), evaluation)
        policy = build_policy((bundle,), evaluation, conflict)
        decision = build_decision((bundle,), evaluation, conflict, policy)
        scoring = build_score((bundle,), evaluation, conflict, policy, decision)
        snapshot = build_recommendation(
            (bundle,), evaluation, conflict, policy, decision, scoring
        )
        rules = {
            item.rule_id: item.input_requirements["decision_condition_type"]
            for item in snapshot.recommendation_rules
        }
        generations = {
            rules[item.rule_id]: item for item in snapshot.generation_records
        }
        applicability = {
            rules[item.rule_id]: item for item in snapshot.applicability_records
        }
        self.assertEqual(
            generations["KEYWORD_EVIDENCE"].recommendation_type,
            "EVIDENCE_COLLECTION_RECOMMENDED",
        )
        self.assertEqual(
            applicability["KEYWORD_EVIDENCE"].applicability_result,
            "INSUFFICIENT_EVIDENCE",
        )
        self.assertEqual(
            applicability["KEYWORD_EVIDENCE"].missing_evidence_requirements,
            ("UPSTREAM_SCORE_EXCLUDED_MISSING_EVIDENCE",),
        )

    def test_no_conflict_scenario_records_rule_conditions_not_success_claim(self) -> None:
        bundle = adapt("xiyou_info")
        evaluation = build_evaluation(bundle)
        conflict = build_resolution((bundle,), evaluation)
        policy = build_policy((bundle,), evaluation, conflict)
        decision = build_decision((bundle,), evaluation, conflict, policy)
        scoring = build_score((bundle,), evaluation, conflict, policy, decision)
        snapshot = build_recommendation(
            (bundle,), evaluation, conflict, policy, decision, scoring
        )
        rules = {
            item.rule_id: item.input_requirements["decision_condition_type"]
            for item in snapshot.recommendation_rules
        }
        generations = {
            rules[item.rule_id]: item for item in snapshot.generation_records
        }
        self.assertEqual(
            generations["EVIDENCE_INVENTORY"].recommendation_type,
            "RULE_CONDITIONS_SATISFIED",
        )
        self.assertEqual(
            generations["CONFLICT_FREE_EVIDENCE"].recommendation_type,
            "RULE_CONDITIONS_SATISFIED",
        )
        self.assertEqual(
            generations["CONFLICT_CONTEXT"].recommendation_type,
            "RULE_NOT_APPLICABLE",
        )

    def test_conflict_remains_visible_and_requires_further_review(self) -> None:
        generation = self.generations_by_condition["CONFLICT_CONTEXT"]
        self.assertEqual(
            generation.recommendation_type, "FURTHER_REVIEW_RECOMMENDED"
        )
        self.assertEqual(
            set(generation.conflict_ids),
            {item.conflict_record_id for item in self.evaluation.conflict_records},
        )
        lineage = next(
            item
            for item in self.snapshot.lineage_index
            if item.recommendation_generation_id
            == generation.recommendation_generation_id
            and item.conflict_record_id is not None
        )
        self.assertTrue(lineage.conflict_analysis_id)
        self.assertTrue(lineage.conflict_candidate_id)
        self.assertTrue(lineage.resolution_attempt_ids)

    def test_every_recommendation_has_complete_explanation_and_limitations(self) -> None:
        explanations = {
            item.explanation_id: item for item in self.snapshot.explanations
        }
        required_limitations = {
            "CURRENT_RULE_AND_EVIDENCE_ONLY",
            "NO_AUTOMATIC_SELECTION",
            "NO_FACTUAL_TRUTH_CLAIM",
            "NO_GUARANTEE_OR_FORECAST",
            "NO_MARKET_OR_INVESTMENT_DECISION",
        }
        for generation in self.snapshot.generation_records:
            explanation = explanations[generation.explanation_id]
            self.assertTrue(explanation.rule_explanation)
            self.assertEqual(explanation.evidence_ids, generation.input_evidence_ids)
            self.assertEqual(
                explanation.score_calculation_ids,
                generation.score_calculation_ids,
            )
            self.assertEqual(
                explanation.policy_evaluation_ids,
                generation.policy_evaluation_ids,
            )
            self.assertEqual(explanation.conflict_ids, generation.conflict_ids)
            self.assertEqual(set(explanation.limitations), required_limitations)

    def test_recommendation_snapshot_copies_no_numeric_score(self) -> None:
        payload = self.snapshot.to_dict()

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertNotIn("result_value", set(keys(payload)))
        self.assertNotIn("total_score", set(keys(payload)))
        self.assertNotIn("overall_score", set(keys(payload)))

    def test_no_guarantee_winner_ranking_or_selection_output(self) -> None:
        forbidden_types = {
            "BUY_THIS_PRODUCT",
            "PRODUCT_WILL_SUCCEED",
            "MARKET_IS_PROFITABLE",
            "BEST_PRODUCT",
            "GUARANTEED_OPPORTUNITY",
        }
        self.assertFalse(
            forbidden_types
            & {item.recommendation_type for item in self.snapshot.generation_records}
        )
        forbidden_keys = {
            "winner",
            "ranking",
            "selected_product",
            "selected_candidate_id",
            "selected_provider",
            "market_entry_decision",
            "investment_advice",
            "roi_guarantee",
            "profit_prediction",
            "revenue_prediction",
        }

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key.casefold()
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertFalse(forbidden_keys & set(keys(self.snapshot.to_dict())))
        unsafe_rule = self.snapshot.recommendation_rules[0].to_dict()
        unsafe_rule["description"] = "Buy this product"
        content = dict(unsafe_rule)
        content.pop("rule_id")
        unsafe_rule["rule_id"] = deterministic_id(
            "recommendation-rule", content
        )
        with self.assertRaises(RecommendationFrameworkSerializationError):
            RecommendationRuleDefinition.from_dict(unsafe_rule)

    def test_serialized_source_boundaries_are_strict(self) -> None:
        with self.assertRaises(RecommendationFrameworkValidationError):
            RecommendationFrameworkRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation.to_dict(),
                conflict_resolution_snapshot=self.conflict.to_dict(),
                evidence_policy_snapshot=self.policy.to_dict(),
                decision_framework_snapshot=self.decision.to_dict(),
                opportunity_scoring_snapshot=self.scoring,  # type: ignore[arg-type]
            )
        scoring = self.scoring.to_dict()
        scoring["unexpected"] = True
        with self.assertRaises(RecommendationFrameworkValidationError):
            RecommendationFrameworkRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=self.evaluation.to_dict(),
                conflict_resolution_snapshot=self.conflict.to_dict(),
                evidence_policy_snapshot=self.policy.to_dict(),
                decision_framework_snapshot=self.decision.to_dict(),
                opportunity_scoring_snapshot=scoring,
            )

    def test_tampered_score_lineage_fails_closed(self) -> None:
        scoring = self.scoring.to_dict()
        lineage = scoring["lineage_index"][0]
        lineage["support_record_id"] = "evidence-support:orphan"
        content = dict(lineage)
        content.pop("score_lineage_id")
        lineage["score_lineage_id"] = deterministic_id("score-lineage", content)
        scoring["lineage_index"] = sorted(
            scoring["lineage_index"], key=lambda item: item["score_lineage_id"]
        )
        recalculate_snapshot_id(scoring, "opportunity-scoring-snapshot")
        request = RecommendationFrameworkRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=self.conflict.to_dict(),
            evidence_policy_snapshot=self.policy.to_dict(),
            decision_framework_snapshot=self.decision.to_dict(),
            opportunity_scoring_snapshot=scoring,
        )
        with self.assertRaises(RecommendationFrameworkValidationError):
            RecommendationFrameworkBuilderV0_1().build(request)

    def test_models_are_deeply_immutable_and_detached(self) -> None:
        rule = self.snapshot.recommendation_rules[0]
        with self.assertRaises(FrozenInstanceError):
            rule.description = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            rule.conditions["changed"] = True  # type: ignore[index]
        scoring = self.scoring.to_dict()
        request = RecommendationFrameworkRequest(
            canonical_bundles=self.bundles,
            evidence_evaluation_snapshot=self.evaluation.to_dict(),
            conflict_resolution_snapshot=self.conflict.to_dict(),
            evidence_policy_snapshot=self.policy.to_dict(),
            decision_framework_snapshot=self.decision.to_dict(),
            opportunity_scoring_snapshot=scoring,
        )
        scoring["calculations"][0]["result_status"] = "TAMPERED"
        self.assertNotEqual(
            request.opportunity_scoring_snapshot["calculations"][0][
                "result_status"
            ],
            "TAMPERED",
        )

    def test_strict_serialization_round_trip_and_tamper_rejection(self) -> None:
        payload = self.snapshot.to_dict()
        identity_content = dict(payload)
        identity_content.pop("snapshot_id")
        self.assertEqual(
            self.snapshot.snapshot_id,
            deterministic_id("recommendation-framework-snapshot", identity_content),
        )
        restored = RecommendationFrameworkSnapshotV0_1.from_dict(payload)
        self.assertEqual(restored, self.snapshot)
        self.assertEqual(canonical_json(restored), canonical_json(self.snapshot))
        payload["unexpected"] = True
        with self.assertRaises(RecommendationFrameworkSerializationError):
            RecommendationFrameworkSnapshotV0_1.from_dict(payload)
        missing_rule = self.snapshot.to_dict()
        missing_rule["recommendation_rules"] = missing_rule[
            "recommendation_rules"
        ][1:]
        recalculate_snapshot_id(
            missing_rule, "recommendation-framework-snapshot"
        )
        with self.assertRaises(RecommendationFrameworkSerializationError):
            RecommendationFrameworkSnapshotV0_1.from_dict(missing_rule)
        unexplained = self.snapshot.to_dict()
        unexplained["explanations"] = unexplained["explanations"][1:]
        recalculate_snapshot_id(
            unexplained, "recommendation-framework-snapshot"
        )
        with self.assertRaises(RecommendationFrameworkSerializationError):
            RecommendationFrameworkSnapshotV0_1.from_dict(unexplained)

    def test_determinism_ignores_bundle_and_record_order(self) -> None:
        built = build_recommendation(
            tuple(reversed(tuple(reordered(item) for item in self.bundles))),
            self.evaluation,
            self.conflict,
            self.policy,
            self.decision,
            self.scoring,
        )
        again = build_recommendation(
            self.bundles,
            self.evaluation,
            self.conflict,
            self.policy,
            self.decision,
            self.scoring,
        )
        self.assertEqual(built.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(canonical_json(built), canonical_json(self.snapshot))
        self.assertEqual(canonical_json(again), canonical_json(self.snapshot))

    def test_determinism_is_stable_across_processes(self) -> None:
        script = (
            "from tests.test_recommendation_framework_v0_1 import build_recommendation; "
            "from tests.test_conflict_resolution_v0_1 import synthetic_bundles,"
            "build_evaluation,build_resolution; "
            "from tests.test_evidence_policy_v0_1 import build_policy; "
            "from tests.test_decision_framework_v0_1 import build_decision; "
            "from tests.test_opportunity_scoring_v0_1 import build_score; "
            "b=synthetic_bundles(); e=build_evaluation(*b); c=build_resolution(b,e); "
            "p=build_policy(b,e,c); d=build_decision(b,e,c,p); s=build_score(b,e,c,p,d); "
            "print(build_recommendation(b,e,c,p,d,s).snapshot_id)"
        )
        first = subprocess.check_output(
            [sys.executable, "-c", script], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        second = subprocess.check_output(
            [sys.executable, "-c", script], cwd=REPOSITORY_ROOT, text=True
        ).strip()
        self.assertEqual(first, self.snapshot.snapshot_id)
        self.assertEqual(second, first)

    def test_lineage_replays_recommendation_score_decision_and_canonical_layers(self) -> None:
        self.assertIs(
            self.snapshot.validate_against_bundles(self.bundles), self.snapshot
        )
        lineage = next(
            item
            for item in self.snapshot.lineage_index
            if item.conflict_record_id is not None
        )
        self.assertTrue(lineage.recommendation_generation_id)
        self.assertTrue(lineage.score_calculation_id)
        self.assertTrue(lineage.score_lineage_id)
        self.assertTrue(lineage.decision_evaluation_id)
        self.assertTrue(lineage.decision_lineage_id)
        self.assertTrue(lineage.policy_evaluation_id)
        self.assertTrue(lineage.conflict_analysis_id)
        self.assertTrue(lineage.support_record_id)
        self.assertTrue(lineage.transformation_run_id)
        self.assertTrue(lineage.mapping_version)
        self.assertTrue(lineage.raw_evidence_id)
        self.assertTrue(lineage.collection_run_id)
        with self.assertRaises(RecommendationFrameworkValidationError):
            self.snapshot.validate_against_bundles((self.bundles[0],))

    def test_orphan_recommendation_lineage_is_rejected_on_replay(self) -> None:
        payload = self.snapshot.to_dict()
        lineage = payload["lineage_index"][0]
        lineage["observation_id"] = "observation:orphan"
        content = dict(lineage)
        content.pop("recommendation_lineage_id")
        lineage["recommendation_lineage_id"] = deterministic_id(
            "recommendation-lineage", content
        )
        payload["lineage_index"] = sorted(
            payload["lineage_index"],
            key=lambda item: item["recommendation_lineage_id"],
        )
        recalculate_snapshot_id(payload, "recommendation-framework-snapshot")
        restored = RecommendationFrameworkSnapshotV0_1.from_dict(payload)
        with self.assertRaises(RecommendationFrameworkValidationError):
            restored.validate_against_bundles(self.bundles)

    def test_builder_does_not_mutate_upstream_snapshots(self) -> None:
        values = (
            self.evaluation.to_dict(),
            self.conflict.to_dict(),
            self.policy.to_dict(),
            self.decision.to_dict(),
            self.scoring.to_dict(),
        )
        expected = tuple(canonical_json(item) for item in values)
        RecommendationFrameworkBuilderV0_1().build(
            RecommendationFrameworkRequest(
                canonical_bundles=self.bundles,
                evidence_evaluation_snapshot=values[0],
                conflict_resolution_snapshot=values[1],
                evidence_policy_snapshot=values[2],
                decision_framework_snapshot=values[3],
                opportunity_scoring_snapshot=values[4],
            )
        )
        self.assertEqual(expected, tuple(canonical_json(item) for item in values))


if __name__ == "__main__":
    unittest.main()
