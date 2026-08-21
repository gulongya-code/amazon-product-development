"""Policy-driven scorer for adapted Opportunity Candidate evidence."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.opportunity_intelligence.integration_v0_1 import (
    OpportunityCandidateSnapshot,
)

from .adapter import OpportunityScoreInputAdapter
from .evaluator import OpportunityScoreEvaluator
from .models import (
    EvidenceBasedOpportunityScore,
    OpportunityDimensionScore,
    OpportunityMetricScoreTrace,
    OpportunityScoreDimension,
    OpportunityScoreDimensionStatus,
    OpportunityScoreExplanation,
    OpportunityScoreMetricStatus,
    OpportunityScoreMissingDataPolicy,
    OpportunityScorePolicy,
    OpportunityScoreRoundingMode,
    OpportunityScoreStatus,
    OpportunityScoringIntegrationInput,
    OpportunityScoringIntegrationValidationError,
)
from .policy import EXPECTED_METRICS, OpportunityScorePolicyValidator
from .validation import OpportunityScoreValidationBuilder


_ROUNDING = {
    OpportunityScoreRoundingMode.HALF_UP: ROUND_HALF_UP,
    OpportunityScoreRoundingMode.HALF_EVEN: ROUND_HALF_EVEN,
    OpportunityScoreRoundingMode.DOWN: ROUND_DOWN,
}


class EvidenceBasedOpportunityScorerV0_1:
    """Aggregate Candidate evidence according to one explicit versioned policy."""

    def __init__(
        self,
        *,
        evaluator: OpportunityScoreEvaluator | None = None,
        policy_validator: OpportunityScorePolicyValidator | None = None,
        validation_builder: OpportunityScoreValidationBuilder | None = None,
    ) -> None:
        self._evaluator = evaluator or OpportunityScoreEvaluator()
        self._policy_validator = (
            policy_validator or OpportunityScorePolicyValidator()
        )
        self._validation_builder = (
            validation_builder or OpportunityScoreValidationBuilder()
        )

    def score(
        self,
        scoring_input: OpportunityScoringIntegrationInput,
        policy: OpportunityScorePolicy,
    ) -> EvidenceBasedOpportunityScore:
        if not isinstance(scoring_input, OpportunityScoringIntegrationInput):
            raise TypeError(
                "scoring_input must be OpportunityScoringIntegrationInput"
            )
        self._policy_validator.validate(policy)
        self._validate_metric_catalogue(scoring_input)

        traces = tuple(sorted((
            self._evaluator.evaluate(
                metric, policy.thresholds[metric.metric_id]
            )
            for metric in scoring_input.metrics
        ), key=lambda item: item.trace_id))
        dimensions = tuple(sorted((
            self._dimension_score(
                dimension=dimension,
                traces=tuple(
                    item for item in traces if item.dimension is dimension
                ),
                maximum=float(policy.dimension_weights[dimension.value]),
                policy=policy,
            )
            for dimension in OpportunityScoreDimension
        ), key=lambda item: item.dimension_score_id))
        available_dimensions = tuple(
            item
            for item in dimensions
            if item.status is not OpportunityScoreDimensionStatus.UNKNOWN
        )
        unknown_dimensions = tuple(
            item
            for item in dimensions
            if item.status is OpportunityScoreDimensionStatus.UNKNOWN
        )

        if (
            unknown_dimensions
            and policy.missing_data_policy is OpportunityScoreMissingDataPolicy.BLOCK
        ) or not available_dimensions:
            final_score = None
            score_status = OpportunityScoreStatus.PENDING_DATA
        else:
            included_weight = sum(
                item.max_contribution for item in available_dimensions
            )
            contribution = sum(
                item.contribution or 0.0 for item in available_dimensions
            )
            final_score = self._round(
                contribution / included_weight * 100.0, policy
            )
            score_status = (
                OpportunityScoreStatus.CALCULATED_PARTIAL
                if unknown_dimensions
                or any(
                    item.status is OpportunityScoreDimensionStatus.PARTIAL
                    for item in dimensions
                )
                else OpportunityScoreStatus.CALCULATED
            )

        risks = self._risks(traces, dimensions)
        limitations = tuple(
            sorted(
                {
                    *scoring_input.limitations,
                    *(
                        value
                        for trace in traces
                        for value in trace.limitations
                    ),
                    *(
                        ("MISSING_DIMENSIONS_EXCLUDED_AND_WEIGHTS_RENORMALIZED",)
                        if unknown_dimensions
                        and policy.missing_data_policy
                        is OpportunityScoreMissingDataPolicy.SKIP_RENORMALIZE
                        else ()
                    ),
                }
            )
        )
        explanation_material = {
            "final_score": final_score,
            "dimension_breakdown": dimensions,
            "metric_traces": traces,
            "evidence_references": scoring_input.source_references,
            "policy_version": policy.policy_version,
            "risks": risks,
            "limitations": limitations,
        }
        explanation = OpportunityScoreExplanation(
            explanation_id=deterministic_id(
                "opportunity-score-explanation", explanation_material
            ),
            **explanation_material,
        )
        validation = self._validation_builder.build(scoring_input)
        score_material = {
            "candidate_id": scoring_input.candidate_id,
            "score_status": score_status,
            "score_value": final_score,
            "confidence": scoring_input.candidate_confidence,
            "policy_version": policy.policy_version,
            "policy_fingerprint": policy.policy_fingerprint,
            "explanation": explanation,
            "validation": validation,
            "integration_version": scoring_input.integration_version,
        }
        return EvidenceBasedOpportunityScore(
            score_id=deterministic_id(
                "evidence-based-opportunity-score", score_material
            ),
            **score_material,
        )

    @staticmethod
    def _validate_metric_catalogue(
        scoring_input: OpportunityScoringIntegrationInput,
    ) -> None:
        expected = {
            metric_id: dimension
            for dimension, metric_ids in EXPECTED_METRICS.items()
            for metric_id in metric_ids
        }
        supplied = {item.metric_id: item.dimension for item in scoring_input.metrics}
        if supplied != expected:
            raise OpportunityScoringIntegrationValidationError(
                "integration input does not match the V0.1 metric catalogue"
            )

    def _dimension_score(
        self,
        *,
        dimension: OpportunityScoreDimension,
        traces: tuple[OpportunityMetricScoreTrace, ...],
        maximum: float,
        policy: OpportunityScorePolicy,
    ) -> OpportunityDimensionScore:
        traces = tuple(sorted(traces, key=lambda item: item.trace_id))
        eligible = tuple(
            item
            for item in traces
            if item.normalized_score is not None and item.metric_weight > 0
        )
        if not eligible:
            status = OpportunityScoreDimensionStatus.UNKNOWN
            score_value = None
            contribution = None
            explanation = (
                f"{dimension.value} is UNKNOWN; unavailable metrics were excluded "
                "without numeric zero."
            )
        else:
            weighted_total = sum(item.weighted_score or 0.0 for item in eligible)
            weight_total = sum(item.metric_weight for item in eligible)
            score_value = self._round(weighted_total / weight_total, policy)
            contribution = self._round(score_value / 100.0 * maximum, policy)
            is_partial = len(eligible) != len(traces) or any(
                item.input_status is not OpportunityScoreMetricStatus.AVAILABLE
                for item in eligible
            )
            status = (
                OpportunityScoreDimensionStatus.PARTIAL
                if is_partial
                else OpportunityScoreDimensionStatus.SCORED
            )
            explanation = (
                f"{dimension.value} used policy-declared weighted aggregation; "
                f"contribution is {contribution} of {maximum}."
            )
        source_evidence_ids = tuple(
            sorted(
                {
                    value
                    for item in traces
                    for value in item.source_evidence_ids
                }
            )
        )
        source_reference_ids = tuple(
            sorted(
                {
                    value
                    for item in traces
                    for value in item.source_reference_ids
                }
            )
        )
        material = {
            "dimension": dimension,
            "status": status,
            "score_value": score_value,
            "contribution": contribution,
            "max_contribution": maximum,
            "metric_traces": traces,
            "source_evidence_ids": source_evidence_ids,
            "source_reference_ids": source_reference_ids,
            "calculation_rule": (
                "POLICY_WEIGHTED_AVERAGE_WITH_EXPLICIT_MISSING_DATA_POLICY"
            ),
            "explanation": explanation,
        }
        return OpportunityDimensionScore(
            dimension_score_id=deterministic_id(
                "opportunity-dimension-score", material
            ),
            **material,
        )

    @staticmethod
    def _risks(
        traces: tuple[OpportunityMetricScoreTrace, ...],
        dimensions: tuple[OpportunityDimensionScore, ...],
    ) -> tuple[str, ...]:
        risks: set[str] = set()
        for trace in traces:
            if trace.input_status is OpportunityScoreMetricStatus.PARTIAL:
                risks.add(f"PARTIAL_EVIDENCE:{trace.metric_id}")
            if trace.normalized_score is None:
                risks.add(f"UNKNOWN_EVIDENCE:{trace.metric_id}")
            if (
                trace.dimension
                is OpportunityScoreDimension.COMPETITION_FAVORABILITY
                and trace.raw_value == "HIGH"
            ):
                risks.add(f"HIGH_COMPETITION_SIGNAL:{trace.metric_id}")
        for dimension in dimensions:
            if dimension.status is OpportunityScoreDimensionStatus.UNKNOWN:
                risks.add(f"UNKNOWN_DIMENSION:{dimension.dimension.value}")
        return tuple(sorted(risks))

    @staticmethod
    def _round(value: float, policy: OpportunityScorePolicy) -> float:
        quantum = Decimal(1).scaleb(-policy.rounding_policy.decimal_places)
        resolved = Decimal(str(value)).quantize(
            quantum,
            rounding=_ROUNDING[policy.rounding_policy.mode],
        )
        return float(resolved)


class OpportunityScoringIntegrationV0_1:
    """Candidate entrypoint; the legacy Opportunity Scoring entrypoints stay separate."""

    def __init__(
        self,
        *,
        adapter: OpportunityScoreInputAdapter | None = None,
        scorer: EvidenceBasedOpportunityScorerV0_1 | None = None,
    ) -> None:
        self._adapter = adapter or OpportunityScoreInputAdapter()
        self._scorer = scorer or EvidenceBasedOpportunityScorerV0_1()

    def score_candidate(
        self,
        candidate: OpportunityCandidateSnapshot,
        policy: OpportunityScorePolicy,
    ) -> EvidenceBasedOpportunityScore:
        return self._scorer.score(self._adapter.adapt(candidate), policy)


__all__ = (
    "EvidenceBasedOpportunityScorerV0_1",
    "OpportunityScoringIntegrationV0_1",
)
