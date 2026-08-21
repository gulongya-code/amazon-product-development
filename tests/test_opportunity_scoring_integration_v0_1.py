from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.opportunity_intelligence.integration_v0_1 import (
    OpportunityConfidence,
)
from amazon_product_intelligence.opportunity_scoring.integration_v0_1 import (
    EvidenceBasedOpportunityScore,
    EvidenceBasedOpportunityScorerV0_1,
    OpportunityScoreDimension,
    OpportunityScoreDimensionStatus,
    OpportunityScoreInputAdapter,
    OpportunityScoreMetricStatus,
    OpportunityScorePolicyLoader,
    OpportunityScoreStatus,
    OpportunityScoringIntegrationInput,
    OpportunityScoringIntegrationV0_1,
    calculate_policy_fingerprint,
)
from amazon_product_intelligence.opportunity_scoring.scoring import (
    ScoreCalculator,
    ScoreStatus,
)

from tests.test_configuration_driven_scoring_engine_v0_1 import (
    load_configuration,
    opportunity_result,
)
from tests.test_opportunity_candidate_v0_1 import OpportunityCandidateFixtureCase


POLICY_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "opportunity_scoring"
    / "opportunity_score_policy_integration_v0_1.json"
)
ADAPTER_SOURCE = (
    Path(__file__).parents[1]
    / "src"
    / "amazon_product_intelligence"
    / "opportunity_scoring"
    / "integration_v0_1"
    / "adapter.py"
)


def policy():
    return OpportunityScorePolicyLoader().load(
        POLICY_FIXTURE,
        policy_version="opportunity-score-policy-v0.1",
    )


def rebuilt_input(
    source: OpportunityScoringIntegrationInput,
    *,
    values: dict[str, str | None] | None = None,
    statuses: dict[str, OpportunityScoreMetricStatus] | None = None,
    confidence: OpportunityConfidence | None = None,
) -> OpportunityScoringIntegrationInput:
    values = values or {}
    statuses = statuses or {}
    metrics = []
    for metric in source.metrics:
        value = values.get(metric.metric_id, metric.value)
        status = statuses.get(metric.metric_id, metric.status)
        if status is OpportunityScoreMetricStatus.AVAILABLE:
            limitations = ()
        elif status is OpportunityScoreMetricStatus.UNKNOWN:
            value = None
            limitations = (f"TEST_UNKNOWN:{metric.metric_id}",)
        else:
            limitations = (f"TEST_PARTIAL:{metric.metric_id}",)
        metrics.append(
            replace(
                metric,
                value=value,
                status=status,
                limitations=limitations,
            )
        )
    material = {
        "candidate_id": source.candidate_id,
        "category_scope": source.category_scope,
        "candidate_confidence": confidence or source.candidate_confidence,
        "metrics": tuple(sorted(metrics, key=lambda item: item.metric_id)),
        "evidence_ids": source.evidence_ids,
        "source_references": source.source_references,
        "limitations": source.limitations,
        "integration_version": source.integration_version,
    }
    return OpportunityScoringIntegrationInput(
        input_id=deterministic_id("opportunity-score-input", material),
        **material,
    )


def complete_scenario(
    source: OpportunityScoringIntegrationInput,
    *,
    competition: str,
    confidence: OpportunityConfidence = OpportunityConfidence.LOW,
) -> OpportunityScoringIntegrationInput:
    values = {
        "demand.search_demand_share": "0.80",
        "demand.review_mention_share": "0.70",
        "demand.confidence": "HIGH",
        "supply_gap.gap_type": "HIGH_DEMAND_LOW_SUPPLY",
        "supply_gap.gap_strength": "HIGH",
        "competition.market_concentration": competition,
        "competition.brand_concentration": competition,
        "competition.review_barrier": competition,
        "competition.price_competition": competition,
        "economic.price_band": "20_TO_30_USD",
        "economic.sales_availability": "0.60",
        "economic.revenue_availability": "0.55",
        "evidence_confidence.demand": "AVAILABLE",
        "evidence_confidence.supply": "AVAILABLE",
        "evidence_confidence.gap": "AVAILABLE",
        "evidence_confidence.competition": "AVAILABLE",
        "evidence_confidence.economic": "AVAILABLE",
    }
    statuses = {
        metric_id: OpportunityScoreMetricStatus.AVAILABLE
        for metric_id in values
    }
    return rebuilt_input(
        source,
        values=values,
        statuses=statuses,
        confidence=confidence,
    )


def dimension(result: EvidenceBasedOpportunityScore, name: OpportunityScoreDimension):
    return next(
        item
        for item in result.explanation.dimension_breakdown
        if item.dimension is name
    )


class OpportunityScoringIntegrationTests(OpportunityCandidateFixtureCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.candidate = cls.builder.build(
            OpportunityCandidateFixtureCase.request_for(
                cls, cls.high_demand_low_supply_gap
            )
        )
        cls.adapter = OpportunityScoreInputAdapter()
        cls.base_input = cls.adapter.adapt(cls.candidate)
        cls.policy = policy()
        cls.scorer = EvidenceBasedOpportunityScorerV0_1()

    def test_high_demand_low_supply_and_low_competition_scores_high_dimensions(self) -> None:
        source = complete_scenario(self.base_input, competition="LOW")
        result = self.scorer.score(source, self.policy)

        self.assertIs(result.score_status, OpportunityScoreStatus.CALCULATED)
        self.assertGreater(
            dimension(result, OpportunityScoreDimension.DEMAND_STRENGTH).contribution,
            20.0,
        )
        self.assertGreater(
            dimension(result, OpportunityScoreDimension.SUPPLY_GAP).contribution,
            20.0,
        )
        self.assertEqual(
            dimension(
                result, OpportunityScoreDimension.COMPETITION_FAVORABILITY
            ).contribution,
            20.0,
        )

    def test_high_competition_reduces_competition_contribution(self) -> None:
        low = self.scorer.score(
            complete_scenario(self.base_input, competition="LOW"), self.policy
        )
        high = self.scorer.score(
            complete_scenario(self.base_input, competition="HIGH"), self.policy
        )

        low_competition = dimension(
            low, OpportunityScoreDimension.COMPETITION_FAVORABILITY
        )
        high_competition = dimension(
            high, OpportunityScoreDimension.COMPETITION_FAVORABILITY
        )
        self.assertGreater(low_competition.contribution, high_competition.contribution)
        self.assertGreater(low.score_value, high.score_value)
        self.assertIn(
            "HIGH_COMPETITION_SIGNAL:competition.market_concentration",
            high.explanation.risks,
        )

    def test_missing_economic_evidence_is_unknown_and_not_zero(self) -> None:
        complete = complete_scenario(self.base_input, competition="LOW")
        economic_metrics = {
            "economic.price_band",
            "economic.sales_availability",
            "economic.revenue_availability",
            "evidence_confidence.economic",
        }
        source = rebuilt_input(
            complete,
            statuses={
                metric_id: OpportunityScoreMetricStatus.UNKNOWN
                for metric_id in economic_metrics
            },
        )
        result = self.scorer.score(source, self.policy)
        economic = dimension(result, OpportunityScoreDimension.ECONOMIC_EVIDENCE)

        self.assertIs(
            economic.status, OpportunityScoreDimensionStatus.UNKNOWN
        )
        self.assertIsNone(economic.score_value)
        self.assertIsNone(economic.contribution)
        self.assertIsNotNone(result.score_value)
        self.assertIs(
            result.score_status, OpportunityScoreStatus.CALCULATED_PARTIAL
        )
        self.assertTrue(
            all(item.normalized_score is None for item in economic.metric_traces)
        )

    def test_confidence_and_score_are_separate(self) -> None:
        low_input = complete_scenario(
            self.base_input,
            competition="LOW",
            confidence=OpportunityConfidence.LOW,
        )
        high_input = rebuilt_input(
            low_input, confidence=OpportunityConfidence.HIGH
        )
        low = self.scorer.score(low_input, self.policy)
        high = self.scorer.score(high_input, self.policy)

        self.assertEqual(low.score_value, high.score_value)
        self.assertIs(low.confidence, OpportunityConfidence.LOW)
        self.assertIs(high.confidence, OpportunityConfidence.HIGH)
        self.assertGreater(low.score_value, 85.0)

    def test_explanation_is_complete_and_source_bound(self) -> None:
        source = complete_scenario(self.base_input, competition="LOW")
        result = self.scorer.score(source, self.policy)
        explanation = result.explanation

        self.assertEqual(explanation.final_score, result.score_value)
        self.assertEqual(explanation.policy_version, self.policy.policy_version)
        self.assertEqual(
            {item.dimension for item in explanation.dimension_breakdown},
            set(OpportunityScoreDimension),
        )
        self.assertEqual(len(explanation.metric_traces), 17)
        self.assertEqual(
            {item.reference_id for item in explanation.evidence_references},
            {item.reference_id for item in source.source_references},
        )
        for item in explanation.dimension_breakdown:
            self.assertTrue(item.calculation_rule)
            self.assertTrue(item.explanation)
            self.assertTrue(item.metric_traces)
            self.assertTrue(item.source_evidence_ids)
            self.assertTrue(item.source_reference_ids)

    def test_policy_version_and_weight_change_produce_a_different_result(self) -> None:
        source = complete_scenario(self.base_input, competition="LOW")
        original = self.scorer.score(source, self.policy)
        payload = json.loads(POLICY_FIXTURE.read_text(encoding="utf-8"))
        payload["policy_version"] = "opportunity-score-policy-v0.2-test"
        payload["dimension_weights"]["DEMAND_STRENGTH"] = 35.0
        payload["dimension_weights"]["ECONOMIC_EVIDENCE"] = 10.0
        payload["policy_fingerprint"] = calculate_policy_fingerprint(payload)
        changed_policy = OpportunityScorePolicyLoader().load_mapping(payload)
        changed = self.scorer.score(source, changed_policy)

        self.assertNotEqual(original.score_value, changed.score_value)
        self.assertNotEqual(original.score_id, changed.score_id)
        self.assertNotEqual(original.policy_version, changed.policy_version)

    def test_legacy_scoring_entrypoint_remains_compatible(self) -> None:
        legacy = ScoreCalculator(allow_test_config=True).calculate(
            opportunity_result(), load_configuration()
        )

        self.assertIs(legacy.score_status, ScoreStatus.CALCULATED)
        self.assertEqual(legacy.score_value, 80.0)

    def test_score_id_and_serialization_are_deterministic(self) -> None:
        source = complete_scenario(self.base_input, competition="LOW")
        first = self.scorer.score(source, self.policy)
        second = self.scorer.score(source, self.policy)
        restored_input = OpportunityScoringIntegrationInput.from_dict(
            source.to_dict()
        )
        restored = EvidenceBasedOpportunityScore.from_dict(first.to_dict())

        self.assertEqual(restored_input, source)
        self.assertEqual(first.score_id, second.score_id)
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(restored, first)

    def test_evidence_lineage_reaches_candidate_sources(self) -> None:
        source = complete_scenario(self.base_input, competition="LOW")
        result = self.scorer.score(source, self.policy)
        source_evidence_ids = set(source.evidence_ids)
        source_reference_ids = {
            item.reference_id for item in source.source_references
        }

        self.assertEqual(result.candidate_id, self.candidate.candidate_id)
        for trace in result.explanation.metric_traces:
            self.assertLessEqual(
                set(trace.source_evidence_ids), source_evidence_ids
            )
            self.assertLessEqual(
                set(trace.source_reference_ids), source_reference_ids
            )

    def test_adapter_consumes_candidate_contract_only(self) -> None:
        source = ADAPTER_SOURCE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module or ""
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        forbidden = (
            "review",
            "search_term",
            "product_attribute",
            "raw_evidence",
            "canonicalization",
        )

        self.assertFalse(
            any(
                token in module
                for module in imported_modules
                for token in forbidden
            )
        )
        self.assertEqual(self.base_input.candidate_id, self.candidate.candidate_id)
        self.assertEqual(
            canonical_json(self.base_input.category_scope),
            canonical_json(self.candidate.category_scope),
        )
        self.assertTrue(self.base_input.evidence_ids)
        self.assertEqual(
            {item.reference_id for item in self.base_input.source_references},
            {
                item.reference_id
                for item in self.candidate.evidence.source_references
            },
        )

    def test_validation_contract_is_ready_for_real_data_validation(self) -> None:
        result = OpportunityScoringIntegrationV0_1().score_candidate(
            self.candidate, self.policy
        )
        validation = result.validation

        self.assertEqual(validation.candidate_count, 1)
        self.assertEqual(
            canonical_json(validation.category_scope),
            canonical_json(self.candidate.category_scope),
        )
        self.assertEqual(
            set(validation.evidence_coverage),
            {item.value for item in OpportunityScoreDimension},
        )
        self.assertEqual(
            set(validation.metric_availability),
            {item.metric_id for item in self.base_input.metrics},
        )


if __name__ == "__main__":
    unittest.main()
