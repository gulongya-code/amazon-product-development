"""Opportunity result aggregation without executable business scoring."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TypeVar

from amazon_product_intelligence.contracts import canonical_json

from .engine_contracts import (
    BUSINESS_DECISION_REQUIRED,
    CompletenessLevel,
    CompletenessResult,
    ConfidenceLevel,
    ConfidenceResult,
    OpportunityDimension,
    OpportunityScoringEngineResult,
    ScoringConfigurationStatus,
    ScoringState,
)
from .errors import OpportunityScoringValidationError
from .evaluators import (
    DimensionEvaluationResult,
    DimensionExplanation,
    DimensionRiskRecord,
)


_CONFIDENCE_ORDER = {
    ConfidenceLevel.UNKNOWN: 0,
    ConfidenceLevel.LOW: 1,
    ConfidenceLevel.MEDIUM: 2,
    ConfidenceLevel.HIGH: 3,
}
_COMPLETENESS_BY_STATE = {
    ScoringState.READY: CompletenessLevel.COMPLETE,
    ScoringState.PARTIAL: CompletenessLevel.PARTIAL,
    ScoringState.PENDING: CompletenessLevel.PENDING,
    ScoringState.INSUFFICIENT_DATA: CompletenessLevel.INSUFFICIENT,
    ScoringState.CONFLICT: CompletenessLevel.CONFLICT,
}
_RecordT = TypeVar("_RecordT")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityResult(OpportunityScoringEngineResult):
    """Aggregated, source-preserving opportunity analysis result V0.1."""

    dimension_results: tuple[DimensionEvaluationResult, ...]
    risks: tuple[DimensionRiskRecord, ...]
    explanations: tuple[DimensionExplanation, ...]

    def __post_init__(self) -> None:
        OpportunityScoringEngineResult.__post_init__(self)
        dimensions = tuple(self.dimension_results)
        risks = tuple(self.risks)
        explanations = tuple(self.explanations)
        if any(not isinstance(item, DimensionEvaluationResult) for item in dimensions):
            raise OpportunityScoringValidationError(
                "OpportunityResult requires DimensionEvaluationResult inputs"
            )
        if any(not isinstance(item, DimensionRiskRecord) for item in risks):
            raise OpportunityScoringValidationError(
                "OpportunityResult risks must be DimensionRiskRecord values"
            )
        if any(not isinstance(item, DimensionExplanation) for item in explanations):
            raise OpportunityScoringValidationError(
                "OpportunityResult explanations must be DimensionExplanation values"
            )
        expected_order = tuple(OpportunityDimension)
        if tuple(item.dimension for item in dimensions) != expected_order:
            raise OpportunityScoringValidationError(
                "OpportunityResult dimensions must use canonical dimension order"
            )
        if explanations != tuple(item.explanation for item in dimensions):
            raise OpportunityScoringValidationError(
                "OpportunityResult must aggregate dimension explanations unchanged"
            )
        final_provenance = {
            item.provenance_id: item for item in self.provenance
        }
        for dimension in dimensions:
            for reference in dimension.provenance:
                if final_provenance.get(reference.provenance_id) != reference:
                    raise OpportunityScoringValidationError(
                        "OpportunityResult must preserve all dimension provenance"
                    )


class OpportunityResultAggregator:
    """Combine exactly three dimension results; never calculate a score."""

    def aggregate(
        self,
        dimension_results: Sequence[DimensionEvaluationResult]
        | DimensionEvaluationResult,
        *additional_results: DimensionEvaluationResult,
    ) -> OpportunityResult:
        if additional_results:
            supplied = (dimension_results, *additional_results)
        elif isinstance(dimension_results, DimensionEvaluationResult):
            supplied = (dimension_results,)
        elif isinstance(dimension_results, (str, bytes)) or not isinstance(
            dimension_results, Sequence
        ):
            raise TypeError("dimension_results must be a sequence or dimension result")
        else:
            supplied = tuple(dimension_results)
        if len(supplied) != len(OpportunityDimension) or any(
            not isinstance(item, DimensionEvaluationResult) for item in supplied
        ):
            raise OpportunityScoringValidationError(
                "aggregation requires exactly three DimensionEvaluationResult values"
            )
        by_dimension = {item.dimension: item for item in supplied}
        if len(by_dimension) != len(OpportunityDimension) or set(by_dimension) != set(
            OpportunityDimension
        ):
            raise OpportunityScoringValidationError(
                "aggregation requires each opportunity dimension exactly once"
            )
        dimensions = tuple(by_dimension[dimension] for dimension in OpportunityDimension)

        result_status = _aggregate_status(
            tuple(item.result_status for item in dimensions)
        )
        risks = _merge_records(
            (risk for item in dimensions for risk in item.risks),
            identifier="risk_id",
            label="risk",
        )
        provenance = _merge_records(
            (reference for item in dimensions for reference in item.provenance),
            identifier="provenance_id",
            label="provenance",
        )
        if not provenance:
            raise OpportunityScoringValidationError(
                "an OpportunityResult requires source provenance"
            )
        missing_inputs = _unique(
            item
            for dimension in dimensions
            for item in dimension.missing_inputs
        )
        confidence = ConfidenceResult(
            level=min(
                (item.confidence.level for item in dimensions),
                key=_CONFIDENCE_ORDER.__getitem__,
            ),
            reasons=_unique(
                f"{dimension.dimension.value}: {reason}"
                for dimension in dimensions
                for reason in dimension.confidence.reasons
            ),
        )
        completeness = CompletenessResult(
            level=_COMPLETENESS_BY_STATE[result_status],
            available_inputs=_unique(
                value
                for dimension in dimensions
                for value in dimension.completeness.available_inputs
            ),
            missing_inputs=_unique(
                value
                for dimension in dimensions
                for value in dimension.completeness.missing_inputs
            ),
            pending_inputs=_unique(
                value
                for dimension in dimensions
                for value in dimension.completeness.pending_inputs
            ),
            conflict_ids=_unique(
                value
                for dimension in dimensions
                for value in dimension.completeness.conflict_ids
            ),
        )
        return OpportunityResult(
            result_status=result_status,
            score_value=None,
            score_version=BUSINESS_DECISION_REQUIRED,
            dimension_results=dimensions,
            confidence=confidence,
            completeness=completeness,
            risks=risks,
            missing_inputs=missing_inputs,
            provenance=provenance,
            explanations=tuple(item.explanation for item in dimensions),
            configuration=ScoringConfigurationStatus(),
        )


def _aggregate_status(states: tuple[ScoringState, ...]) -> ScoringState:
    """Aggregate readiness states without weights, thresholds, or value comparison."""

    state_set = set(states)
    if ScoringState.CONFLICT in state_set:
        return ScoringState.CONFLICT
    if state_set == {ScoringState.READY}:
        return ScoringState.READY
    # PARTIAL remains the aggregate state when another dimension is insufficient,
    # while that insufficient state and all of its missing inputs remain visible.
    if ScoringState.PARTIAL in state_set:
        return ScoringState.PARTIAL
    if ScoringState.INSUFFICIENT_DATA in state_set:
        return ScoringState.INSUFFICIENT_DATA
    if ScoringState.PENDING in state_set:
        return ScoringState.PENDING
    raise OpportunityScoringValidationError("unsupported dimension state combination")


def _merge_records(
    records: Iterable[_RecordT],
    *,
    identifier: str,
    label: str,
) -> tuple[_RecordT, ...]:
    merged: dict[str, _RecordT] = {}
    fingerprints: dict[str, str] = {}
    for record in records:
        record_id = getattr(record, identifier)
        fingerprint = canonical_json(record)
        if record_id in merged and fingerprints[record_id] != fingerprint:
            raise OpportunityScoringValidationError(
                f"duplicate {label} ID {record_id!r} has conflicting records"
            )
        if record_id not in merged:
            merged[record_id] = record
            fingerprints[record_id] = fingerprint
    return tuple(merged.values())


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


__all__ = (
    "OpportunityResult",
    "OpportunityResultAggregator",
)
