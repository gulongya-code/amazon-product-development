"""Dependency-injected orchestration skeleton for future business scoring."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .engine_contracts import (
    BUSINESS_DECISION_REQUIRED,
    CompletenessResult,
    ConfidenceResult,
    DimensionResult,
    ExplanationRecord,
    OpportunityDimension,
    OpportunityScoringEngineInput,
    OpportunityScoringEngineResult,
    RiskRecord,
    ScoringConfigurationStatus,
    ScoringState,
)


@runtime_checkable
class DimensionEvaluator(Protocol):
    """Evaluate one dimension's evidence state; no formula is supplied here."""

    def evaluate(
        self,
        request: OpportunityScoringEngineInput,
        dimension: OpportunityDimension,
    ) -> DimensionResult: ...


@runtime_checkable
class QualityEvaluator(Protocol):
    """Return qualitative confidence and completeness companions."""

    def evaluate(
        self,
        request: OpportunityScoringEngineInput,
        dimension_results: tuple[DimensionResult, ...],
    ) -> tuple[ConfidenceResult, CompletenessResult]: ...


@runtime_checkable
class RiskEvaluator(Protocol):
    """Expose risk evidence without numeric penalties or severity formulas."""

    def evaluate(
        self,
        request: OpportunityScoringEngineInput,
        dimension_results: tuple[DimensionResult, ...],
    ) -> tuple[RiskRecord, ...]: ...


@runtime_checkable
class ExplanationBuilder(Protocol):
    """Explain evidence, factors, and risks for every dimension."""

    def build(
        self,
        request: OpportunityScoringEngineInput,
        dimension_results: tuple[DimensionResult, ...],
        risks: tuple[RiskRecord, ...],
    ) -> tuple[ExplanationRecord, ...]: ...


class ScoringEngine:
    """Orchestrate injected evaluators while keeping business scoring disabled.

    The engine can assemble quality, risk, state, provenance, and explanations.
    V0.1 always keeps ``score_value`` null and configuration parameters at
    ``BUSINESS_DECISION_REQUIRED``.
    """

    def __init__(
        self,
        *,
        dimension_evaluator: DimensionEvaluator,
        quality_evaluator: QualityEvaluator,
        risk_evaluator: RiskEvaluator,
        explanation_builder: ExplanationBuilder,
    ) -> None:
        for name, value, contract in (
            ("dimension_evaluator", dimension_evaluator, DimensionEvaluator),
            ("quality_evaluator", quality_evaluator, QualityEvaluator),
            ("risk_evaluator", risk_evaluator, RiskEvaluator),
            ("explanation_builder", explanation_builder, ExplanationBuilder),
        ):
            if not isinstance(value, contract):
                raise TypeError(f"{name} does not implement its engine contract")
        self._dimension_evaluator = dimension_evaluator
        self._quality_evaluator = quality_evaluator
        self._risk_evaluator = risk_evaluator
        self._explanation_builder = explanation_builder

    def evaluate(
        self,
        request: OpportunityScoringEngineInput,
    ) -> OpportunityScoringEngineResult:
        if not isinstance(request, OpportunityScoringEngineInput):
            raise TypeError("request must be OpportunityScoringEngineInput")
        dimensions = tuple(
            self._dimension_evaluator.evaluate(request, dimension)
            for dimension in OpportunityDimension
        )
        confidence, completeness = self._quality_evaluator.evaluate(request, dimensions)
        evaluated_risks = self._risk_evaluator.evaluate(request, dimensions)
        risks_by_id = {
            risk.risk_id: risk
            for risk in (
                *evaluated_risks,
                *(risk for dimension in dimensions for risk in dimension.risks),
            )
        }
        risks = tuple(risks_by_id[key] for key in sorted(risks_by_id))
        explanations = self._explanation_builder.build(request, dimensions, risks)
        missing_inputs = tuple(
            dict.fromkeys(
                (
                    *request.quality.missing_inputs,
                    *completeness.missing_inputs,
                    *completeness.pending_inputs,
                    "SCORING_CONFIGURATION",
                )
            )
        )
        result_status = (
            ScoringState.CONFLICT
            if any(item.result_status is ScoringState.CONFLICT for item in dimensions)
            else ScoringState.PENDING
        )
        return OpportunityScoringEngineResult(
            result_status=result_status,
            score_version=BUSINESS_DECISION_REQUIRED,
            dimension_results=dimensions,
            confidence=confidence,
            completeness=completeness,
            risks=risks,
            missing_inputs=missing_inputs,
            provenance=request.provenance,
            explanations=explanations,
            configuration=ScoringConfigurationStatus(),
            score_value=None,
        )


__all__ = (
    "DimensionEvaluator",
    "ExplanationBuilder",
    "QualityEvaluator",
    "RiskEvaluator",
    "ScoringEngine",
)
