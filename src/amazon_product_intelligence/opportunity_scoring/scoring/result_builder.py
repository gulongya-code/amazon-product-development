"""Serializable opportunity score result and builder V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Any

from amazon_product_intelligence.contracts import JsonContract

from ..engine_contracts import (
    BUSINESS_DECISION_REQUIRED,
    CompletenessLevel,
    CompletenessResult,
    ConfidenceResult,
    OpportunityDimension,
    ProvenanceReference,
)
from ..errors import OpportunityScoringValidationError
from ..evaluators import (
    DimensionEvaluationResult,
    DimensionExplanation,
    DimensionRiskRecord,
)
from ..result_aggregator import OpportunityResult
from .config_validator import (
    AggregationFormula,
    BusinessScoringConfiguration,
    ComparisonOperator,
    ConfigLifecycleStatus,
)


class ScoreStatus(StrEnum):
    CALCULATED = "CALCULATED"
    PENDING_CONFIGURATION = "PENDING_CONFIGURATION"
    PENDING_DATA = "PENDING_DATA"


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigurationReference(JsonContract):
    schema_version: str
    configuration_id: str
    score_version: str
    lifecycle_status: ConfigLifecycleStatus
    configuration_fingerprint: str
    decision_reference: str
    approved_by: str
    approved_at: str
    test_only: bool

    def __post_init__(self) -> None:
        for name in (
            "schema_version",
            "configuration_id",
            "score_version",
            "configuration_fingerprint",
            "decision_reference",
            "approved_by",
            "approved_at",
        ):
            if not isinstance(getattr(self, name), str) or not getattr(
                self, name
            ).strip():
                raise OpportunityScoringValidationError(
                    f"ConfigurationReference.{name} is required"
                )
        if not isinstance(self.lifecycle_status, ConfigLifecycleStatus):
            raise OpportunityScoringValidationError(
                "ConfigurationReference.lifecycle_status is invalid"
            )
        if not isinstance(self.test_only, bool):
            raise OpportunityScoringValidationError(
                "ConfigurationReference.test_only must be boolean"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricRuleTrace(JsonContract):
    rule_id: str
    metric_id: str
    metric_value: Any
    operator: ComparisonOperator
    threshold: float
    matched: bool
    rule_score: float
    rule_weight: float
    evidence_provenance_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("rule_id", "metric_id"):
            if not isinstance(getattr(self, name), str) or not getattr(
                self, name
            ).strip():
                raise OpportunityScoringValidationError(
                    f"MetricRuleTrace.{name} is required"
                )
        if not isinstance(self.operator, ComparisonOperator):
            raise OpportunityScoringValidationError(
                "MetricRuleTrace.operator is invalid"
            )
        if not isinstance(self.matched, bool):
            raise OpportunityScoringValidationError(
                "MetricRuleTrace.matched must be boolean"
            )
        for name in ("threshold", "rule_score", "rule_weight"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise OpportunityScoringValidationError(
                    f"MetricRuleTrace.{name} must be finite"
                )
        provenance_ids = tuple(self.evidence_provenance_ids)
        if (
            not provenance_ids
            or len(set(provenance_ids)) != len(provenance_ids)
            or any(not isinstance(item, str) or not item.strip() for item in provenance_ids)
        ):
            raise OpportunityScoringValidationError(
                "MetricRuleTrace evidence provenance is invalid"
            )
        object.__setattr__(self, "evidence_provenance_ids", provenance_ids)


@dataclass(frozen=True, slots=True, kw_only=True)
class DimensionScoreTrace(JsonContract):
    dimension: OpportunityDimension
    formula: AggregationFormula
    dimension_weight: float
    score_value: float
    rule_traces: tuple[MetricRuleTrace, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, OpportunityDimension):
            raise OpportunityScoringValidationError(
                "DimensionScoreTrace.dimension is invalid"
            )
        if not isinstance(self.formula, AggregationFormula):
            raise OpportunityScoringValidationError(
                "DimensionScoreTrace.formula is invalid"
            )
        for name in ("dimension_weight", "score_value"):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                raise OpportunityScoringValidationError(
                    f"DimensionScoreTrace.{name} must be finite"
                )
        rules = tuple(self.rule_traces)
        if not rules or any(not isinstance(item, MetricRuleTrace) for item in rules):
            raise OpportunityScoringValidationError(
                "DimensionScoreTrace.rule_traces must not be empty"
            )
        object.__setattr__(self, "rule_traces", rules)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoreResult(JsonContract):
    score_value: float | None
    score_status: ScoreStatus
    score_version: str
    configuration_id: str
    dimension_results: tuple[DimensionEvaluationResult, ...]
    confidence: ConfidenceResult
    completeness: CompletenessResult
    risks: tuple[DimensionRiskRecord, ...]
    missing_inputs: tuple[str, ...]
    provenance: tuple[ProvenanceReference, ...]
    explanations: tuple[DimensionExplanation, ...]
    configuration: ConfigurationReference | None
    calculation_trace: tuple[DimensionScoreTrace, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.score_status, ScoreStatus):
            raise OpportunityScoringValidationError("score_status is invalid")
        if self.score_value is not None and (
            isinstance(self.score_value, bool)
            or not isinstance(self.score_value, (int, float))
            or not math.isfinite(float(self.score_value))
        ):
            raise OpportunityScoringValidationError(
                "score_value must be null or a finite number"
            )
        if not isinstance(self.score_version, str) or not self.score_version.strip():
            raise OpportunityScoringValidationError("score_version is required")
        if not isinstance(self.configuration_id, str) or not self.configuration_id.strip():
            raise OpportunityScoringValidationError("configuration_id is required")
        dimensions = tuple(self.dimension_results)
        if (
            len(dimensions) != len(OpportunityDimension)
            or tuple(item.dimension for item in dimensions)
            != tuple(OpportunityDimension)
            or any(not isinstance(item, DimensionEvaluationResult) for item in dimensions)
        ):
            raise OpportunityScoringValidationError(
                "dimension_results must contain three evaluated dimensions in canonical order"
            )
        if not isinstance(self.confidence, ConfidenceResult):
            raise OpportunityScoringValidationError("confidence is invalid")
        if not isinstance(self.completeness, CompletenessResult):
            raise OpportunityScoringValidationError("completeness is invalid")
        risks = tuple(self.risks)
        if any(not isinstance(item, DimensionRiskRecord) for item in risks):
            raise OpportunityScoringValidationError("risks are invalid")
        provenance = tuple(self.provenance)
        if not provenance or any(
            not isinstance(item, ProvenanceReference) for item in provenance
        ):
            raise OpportunityScoringValidationError("provenance must not be empty")
        explanations = tuple(self.explanations)
        if explanations != tuple(item.explanation for item in dimensions):
            raise OpportunityScoringValidationError(
                "dimension explanations must be preserved unchanged"
            )
        missing = tuple(dict.fromkeys(self.missing_inputs))
        if any(not isinstance(item, str) or not item.strip() for item in missing):
            raise OpportunityScoringValidationError("missing_inputs are invalid")
        trace = tuple(self.calculation_trace)
        if any(not isinstance(item, DimensionScoreTrace) for item in trace):
            raise OpportunityScoringValidationError("calculation_trace is invalid")
        if len({item.dimension for item in trace}) != len(trace):
            raise OpportunityScoringValidationError(
                "calculation_trace dimensions must be unique"
            )
        if any(item.dimension not in set(OpportunityDimension) for item in trace):
            raise OpportunityScoringValidationError(
                "calculation_trace contains an unknown dimension"
            )
        provenance_ids = {item.provenance_id for item in provenance}
        if any(
            provenance_id not in provenance_ids
            for dimension_trace in trace
            for rule_trace in dimension_trace.rule_traces
            for provenance_id in rule_trace.evidence_provenance_ids
        ):
            raise OpportunityScoringValidationError(
                "calculation_trace must reference final result provenance"
            )
        if self.score_status is ScoreStatus.CALCULATED:
            if self.score_value is None or self.configuration is None or not trace:
                raise OpportunityScoringValidationError(
                    "CALCULATED result requires score, configuration, and trace"
                )
            if (
                self.score_version == BUSINESS_DECISION_REQUIRED
                or self.configuration_id == BUSINESS_DECISION_REQUIRED
            ):
                raise OpportunityScoringValidationError(
                    "CALCULATED result requires approved versioned configuration"
                )
            if (
                self.configuration.configuration_id != self.configuration_id
                or self.configuration.score_version != self.score_version
            ):
                raise OpportunityScoringValidationError(
                    "score result configuration reference does not match result identity"
                )
        elif self.score_value is not None:
            raise OpportunityScoringValidationError(
                "non-calculated result must keep score_value null"
            )
        object.__setattr__(self, "dimension_results", dimensions)
        object.__setattr__(self, "risks", risks)
        object.__setattr__(self, "missing_inputs", missing)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "explanations", explanations)
        object.__setattr__(self, "calculation_trace", trace)


class OpportunityScoreResultBuilder:
    """Build score results while preserving the source Opportunity Result."""

    def pending_configuration(
        self,
        opportunity: OpportunityResult,
    ) -> OpportunityScoreResult:
        return OpportunityScoreResult(
            score_value=None,
            score_status=ScoreStatus.PENDING_CONFIGURATION,
            score_version=BUSINESS_DECISION_REQUIRED,
            configuration_id=BUSINESS_DECISION_REQUIRED,
            dimension_results=opportunity.dimension_results,
            confidence=opportunity.confidence,
            completeness=_pending_completeness(
                opportunity, pending=("SCORING_CONFIGURATION",)
            ),
            risks=opportunity.risks,
            missing_inputs=_unique(
                (*opportunity.missing_inputs, "SCORING_CONFIGURATION")
            ),
            provenance=opportunity.provenance,
            explanations=opportunity.explanations,
            configuration=None,
            calculation_trace=(),
        )

    def pending_data(
        self,
        opportunity: OpportunityResult,
        configuration: BusinessScoringConfiguration,
        *,
        missing_inputs: tuple[str, ...],
        calculation_trace: tuple[DimensionScoreTrace, ...] = (),
    ) -> OpportunityScoreResult:
        return OpportunityScoreResult(
            score_value=None,
            score_status=ScoreStatus.PENDING_DATA,
            score_version=configuration.score_version,
            configuration_id=configuration.configuration_id,
            dimension_results=opportunity.dimension_results,
            confidence=opportunity.confidence,
            completeness=_pending_completeness(
                opportunity, missing=missing_inputs
            ),
            risks=opportunity.risks,
            missing_inputs=_unique((*opportunity.missing_inputs, *missing_inputs)),
            provenance=opportunity.provenance,
            explanations=opportunity.explanations,
            configuration=_configuration_reference(configuration),
            calculation_trace=calculation_trace,
        )

    def calculated(
        self,
        opportunity: OpportunityResult,
        configuration: BusinessScoringConfiguration,
        *,
        score_value: float,
        calculation_trace: tuple[DimensionScoreTrace, ...],
        missing_inputs: tuple[str, ...] = (),
    ) -> OpportunityScoreResult:
        return OpportunityScoreResult(
            score_value=score_value,
            score_status=ScoreStatus.CALCULATED,
            score_version=configuration.score_version,
            configuration_id=configuration.configuration_id,
            dimension_results=opportunity.dimension_results,
            confidence=opportunity.confidence,
            completeness=_calculated_completeness(opportunity, missing_inputs),
            risks=opportunity.risks,
            missing_inputs=_unique((*opportunity.missing_inputs, *missing_inputs)),
            provenance=opportunity.provenance,
            explanations=opportunity.explanations,
            configuration=_configuration_reference(configuration),
            calculation_trace=calculation_trace,
        )


def _configuration_reference(
    configuration: BusinessScoringConfiguration,
) -> ConfigurationReference:
    return ConfigurationReference(
        schema_version=configuration.schema_version,
        configuration_id=configuration.configuration_id,
        score_version=configuration.score_version,
        lifecycle_status=configuration.lifecycle_status,
        configuration_fingerprint=configuration.audit.configuration_fingerprint,
        decision_reference=configuration.audit.decision_reference,
        approved_by=configuration.audit.approved_by,
        approved_at=configuration.audit.approved_at,
        test_only=configuration.test_only,
    )


def _pending_completeness(
    opportunity: OpportunityResult,
    *,
    missing: tuple[str, ...] = (),
    pending: tuple[str, ...] = (),
) -> CompletenessResult:
    return CompletenessResult(
        level=CompletenessLevel.PENDING,
        available_inputs=opportunity.completeness.available_inputs,
        missing_inputs=_unique((*opportunity.completeness.missing_inputs, *missing)),
        pending_inputs=_unique((*opportunity.completeness.pending_inputs, *pending)),
        conflict_ids=opportunity.completeness.conflict_ids,
    )


def _calculated_completeness(
    opportunity: OpportunityResult,
    missing: tuple[str, ...],
) -> CompletenessResult:
    if not missing:
        return opportunity.completeness
    return CompletenessResult(
        level=CompletenessLevel.PARTIAL,
        available_inputs=opportunity.completeness.available_inputs,
        missing_inputs=_unique((*opportunity.completeness.missing_inputs, *missing)),
        pending_inputs=opportunity.completeness.pending_inputs,
        conflict_ids=opportunity.completeness.conflict_ids,
    )


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


ScoreResultBuilder = OpportunityScoreResultBuilder


__all__ = (
    "ConfigurationReference",
    "DimensionScoreTrace",
    "MetricRuleTrace",
    "OpportunityScoreResult",
    "OpportunityScoreResultBuilder",
    "ScoreResultBuilder",
    "ScoreStatus",
)
