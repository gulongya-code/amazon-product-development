"""Shared, non-scoring behavior for opportunity dimension evaluators."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar

from amazon_product_intelligence.contracts import canonical_json

from ..engine_contracts import (
    CompletenessLevel,
    CompletenessResult,
    ConfidenceLevel,
    ConfidenceResult,
    DimensionResult,
    EvidenceReference,
    ExplanationRecord,
    MetricInput,
    MetricInputStatus,
    OpportunityDimension,
    OpportunityScoringEngineInput,
    ProvenanceReference,
    RiskRecord,
    ScoringState,
)
from ..errors import OpportunityScoringValidationError


_EVIDENCE_STATUSES = frozenset(
    {MetricInputStatus.AVAILABLE, MetricInputStatus.PARTIAL}
)
_CONFIDENCE_ORDER = {
    ConfidenceLevel.UNKNOWN: 0,
    ConfidenceLevel.LOW: 1,
    ConfidenceLevel.MEDIUM: 2,
    ConfidenceLevel.HIGH: 3,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricEvidence(EvidenceReference):
    """A source-backed metric value used by a dimension evaluator."""

    value: Any
    confidence: ConfidenceLevel
    status: MetricInputStatus
    completeness: CompletenessLevel

    def __post_init__(self) -> None:
        EvidenceReference.__post_init__(self)
        if not isinstance(self.confidence, ConfidenceLevel):
            raise OpportunityScoringValidationError(
                "MetricEvidence.confidence is invalid"
            )
        if not isinstance(self.status, MetricInputStatus):
            raise OpportunityScoringValidationError("MetricEvidence.status is invalid")
        if not isinstance(self.completeness, CompletenessLevel):
            raise OpportunityScoringValidationError(
                "MetricEvidence.completeness is invalid"
            )
        if self.status in _EVIDENCE_STATUSES and self.value is None:
            raise OpportunityScoringValidationError(
                "selected evaluator evidence must contain a value"
            )
        if self.status is MetricInputStatus.CONFLICT and self.value is not None:
            raise OpportunityScoringValidationError(
                "conflicting evaluator evidence cannot contain a selected value"
            )

    @property
    def metric(self) -> str:
        """Return the contract's metric name using task terminology."""

        return self.metric_id


@dataclass(frozen=True, slots=True, kw_only=True)
class DimensionRiskRecord(RiskRecord):
    """Risk record retaining the complete metric evidence shape."""

    evidence: tuple[MetricEvidence, ...] = ()

    def __post_init__(self) -> None:
        RiskRecord.__post_init__(self)


@dataclass(frozen=True, slots=True, kw_only=True)
class DimensionExplanation(ExplanationRecord):
    """Explanation record with explicit evaluator-section aliases."""

    evidence: tuple[MetricEvidence, ...]

    def __post_init__(self) -> None:
        ExplanationRecord.__post_init__(self)

    @property
    def positive_evidence(self) -> tuple[str, ...]:
        return self.positive_factors

    @property
    def missing_evidence(self) -> tuple[str, ...]:
        return self.negative_factors

    @property
    def risk(self) -> tuple[str, ...]:
        return self.risks


@dataclass(frozen=True, slots=True, kw_only=True)
class DimensionEvaluationResult(DimensionResult):
    """Evaluator result extending the architecture contract with audit companions.

    It remains a ``DimensionResult`` so the existing orchestration protocol can
    consume it.  No score field is introduced; the inherited ``score_value`` is
    required to remain null by the architecture contract.
    """

    evidence: tuple[MetricEvidence, ...]
    risks: tuple[DimensionRiskRecord, ...]
    confidence: ConfidenceResult
    completeness: CompletenessResult
    provenance: tuple[ProvenanceReference, ...]
    explanation: DimensionExplanation

    def __post_init__(self) -> None:
        DimensionResult.__post_init__(self)
        if not isinstance(self.confidence, ConfidenceResult):
            raise OpportunityScoringValidationError(
                "dimension confidence must be ConfidenceResult"
            )
        if not isinstance(self.completeness, CompletenessResult):
            raise OpportunityScoringValidationError(
                "dimension completeness must be CompletenessResult"
            )
        provenance = tuple(self.provenance)
        if any(not isinstance(item, ProvenanceReference) for item in provenance):
            raise OpportunityScoringValidationError(
                "dimension provenance must contain ProvenanceReference records"
            )
        provenance_ids = {item.provenance_id for item in provenance}
        if len(provenance_ids) != len(provenance):
            raise OpportunityScoringValidationError(
                "dimension provenance IDs must be unique"
            )
        if any(item.provenance_id not in provenance_ids for item in self.evidence):
            raise OpportunityScoringValidationError(
                "dimension evidence must retain its provenance reference"
            )
        if not isinstance(self.explanation, DimensionExplanation):
            raise OpportunityScoringValidationError(
                "dimension explanation must be DimensionExplanation"
            )
        if self.explanation.dimension is not self.dimension:
            raise OpportunityScoringValidationError(
                "dimension explanation must match its dimension"
            )
        if self.explanation.evidence != self.evidence:
            raise OpportunityScoringValidationError(
                "dimension explanation must preserve evaluated evidence"
            )
        object.__setattr__(self, "provenance", provenance)

    @property
    def dimension_name(self) -> OpportunityDimension:
        return self.dimension

    @property
    def status(self) -> ScoringState:
        return self.result_status


@dataclass(frozen=True, slots=True)
class _ResolvedInputs:
    evidence: tuple[MetricEvidence, ...]
    available: tuple[str, ...]
    missing: tuple[str, ...]
    pending: tuple[str, ...]
    incomplete: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    conflict_metrics: tuple[str, ...]
    provenance: tuple[ProvenanceReference, ...]


class BaseOpportunityDimensionEvaluator:
    """Resolve evidence state without comparing metric values to business limits."""

    dimension: ClassVar[OpportunityDimension]
    metric_aliases: ClassVar[Mapping[str, tuple[str, ...]]]
    insufficient_inputs: ClassVar[frozenset[str]] = frozenset()
    summaries: ClassVar[Mapping[ScoringState, str]]

    def evaluate(
        self,
        request: OpportunityScoringEngineInput,
        dimension: OpportunityDimension | None = None,
    ) -> DimensionEvaluationResult:
        """Evaluate one dimension's evidence readiness.

        ``dimension`` is optional for direct use and accepted for compatibility
        with the architecture's dependency-injected ``DimensionEvaluator``
        protocol.  A mismatched dimension is rejected instead of being routed or
        silently interpreted.
        """

        if not isinstance(request, OpportunityScoringEngineInput):
            raise TypeError("request must be OpportunityScoringEngineInput")
        if dimension is not None and dimension is not self.dimension:
            raise OpportunityScoringValidationError(
                f"{type(self).__name__} only evaluates {self.dimension.value}"
            )

        resolved = self._resolve(request)
        status = self._result_status(resolved)
        missing_inputs = _unique(
            (*resolved.missing, *resolved.pending, *resolved.incomplete)
        )
        risks = self._build_risks(request, resolved)
        confidence = self._build_confidence(request, resolved, status)
        completeness = CompletenessResult(
            level=_completeness_level(status),
            available_inputs=resolved.available,
            missing_inputs=_unique((*resolved.missing, *resolved.incomplete)),
            pending_inputs=resolved.pending,
            conflict_ids=resolved.conflict_ids,
        )
        explanation = self._build_explanation(
            status=status,
            evidence=resolved.evidence,
            missing_inputs=missing_inputs,
            risks=risks,
        )
        return DimensionEvaluationResult(
            dimension=self.dimension,
            result_status=status,
            evidence=resolved.evidence,
            missing_inputs=missing_inputs,
            risks=risks,
            conflict_ids=resolved.conflict_ids,
            confidence=confidence,
            completeness=completeness,
            provenance=resolved.provenance,
            explanation=explanation,
            score_value=None,
        )

    @property
    def supported_metrics(self) -> tuple[str, ...]:
        return tuple(self.metric_aliases)

    def _resolve(self, request: OpportunityScoringEngineInput) -> _ResolvedInputs:
        provenance_by_id = {
            item.provenance_id: item for item in request.provenance
        }
        evidence: list[MetricEvidence] = []
        available: list[str] = []
        missing: list[str] = []
        pending: list[str] = []
        incomplete: list[str] = []
        conflict_ids: list[str] = []
        conflict_metrics: list[str] = []
        used_provenance_ids: list[str] = []

        for logical_metric, aliases in self.metric_aliases.items():
            candidates = tuple(
                request.metrics[metric_id]
                for metric_id in aliases
                if metric_id in request.metrics
            )
            for candidate in candidates:
                if candidate.dimension is not self.dimension:
                    raise OpportunityScoringValidationError(
                        f"metric {candidate.metric_id} is assigned to "
                        f"{candidate.dimension.value}, not {self.dimension.value}"
                    )
                used_provenance_ids.append(candidate.provenance_id)

            value_candidates = tuple(
                item
                for item in candidates
                if item.status in _EVIDENCE_STATUSES and item.value is not None
            )
            explicit_conflicts = tuple(
                item for item in candidates if item.status is MetricInputStatus.CONFLICT
            )
            has_value_conflict = len(
                {canonical_json(item.value) for item in value_candidates}
            ) > 1
            is_conflict = bool(explicit_conflicts or has_value_conflict)

            if is_conflict:
                conflict_metrics.append(logical_metric)
                ids = tuple(
                    flag
                    for item in candidates
                    for flag in item.quality_flags
                    if "conflict" in flag.casefold()
                )
                conflict_ids.extend(ids)
                if request.quality.conflict_ids:
                    conflict_ids.extend(request.quality.conflict_ids)
                if not ids and not request.quality.conflict_ids:
                    conflict_ids.append(
                        f"conflict:{self.dimension.value.lower()}:{logical_metric}"
                    )
                evidence.extend(
                    self._evidence(item)
                    for item in (*value_candidates, *explicit_conflicts)
                )
                continue

            if value_candidates:
                available.append(logical_metric)
                evidence.extend(self._evidence(item) for item in value_candidates)
                if any(
                    item.status is MetricInputStatus.PARTIAL
                    or item.completeness is not CompletenessLevel.COMPLETE
                    or item.quality_flags
                    for item in value_candidates
                ):
                    incomplete.append(logical_metric)
                continue

            if any(item.status is MetricInputStatus.PENDING for item in candidates):
                pending.append(logical_metric)
            else:
                missing.append(logical_metric)

        provenance = tuple(
            provenance_by_id[provenance_id]
            for provenance_id in _unique(used_provenance_ids)
        )
        return _ResolvedInputs(
            evidence=tuple(evidence),
            available=tuple(available),
            missing=tuple(missing),
            pending=tuple(pending),
            incomplete=tuple(incomplete),
            conflict_ids=_unique(conflict_ids),
            conflict_metrics=tuple(conflict_metrics),
            provenance=provenance,
        )

    def _result_status(self, resolved: _ResolvedInputs) -> ScoringState:
        if resolved.conflict_ids:
            return ScoringState.CONFLICT
        unresolved = set(
            (*resolved.missing, *resolved.pending, *resolved.incomplete)
        )
        blocking = self.insufficient_inputs & unresolved
        if blocking:
            if blocking <= set(resolved.pending) and not (
                self.insufficient_inputs & set(resolved.missing)
            ):
                return ScoringState.PENDING
            return ScoringState.INSUFFICIENT_DATA
        if resolved.evidence and not unresolved:
            return ScoringState.READY
        if resolved.evidence:
            return ScoringState.PARTIAL
        if resolved.pending:
            return ScoringState.PENDING
        return ScoringState.INSUFFICIENT_DATA

    def _evidence(self, metric: MetricInput) -> MetricEvidence:
        return MetricEvidence(
            metric_id=metric.metric_id,
            value=metric.value,
            source=metric.source,
            snapshot_id=metric.snapshot_id,
            timestamp=metric.timestamp,
            confidence=metric.confidence,
            status=metric.status,
            completeness=metric.completeness,
            provenance_id=metric.provenance_id,
        )

    def _build_confidence(
        self,
        request: OpportunityScoringEngineInput,
        resolved: _ResolvedInputs,
        status: ScoringState,
    ) -> ConfidenceResult:
        if status in {ScoringState.CONFLICT, ScoringState.INSUFFICIENT_DATA}:
            level = ConfidenceLevel.UNKNOWN
        else:
            levels = [request.quality.confidence]
            levels.extend(item.confidence for item in resolved.evidence)
            level = min(levels, key=_CONFIDENCE_ORDER.__getitem__)
        if not resolved.evidence:
            reason = "No selected metric value is available for this dimension."
        elif status is ScoringState.CONFLICT:
            reason = "Unresolved source candidates prevent a selected evidence value."
        else:
            reason = (
                "The lowest declared evidence/input quality confidence was preserved "
                "without numeric weighting."
            )
        return ConfidenceResult(level=level, reasons=(reason,))

    def _build_risks(
        self,
        request: OpportunityScoringEngineInput,
        resolved: _ResolvedInputs,
    ) -> tuple[DimensionRiskRecord, ...]:
        records: list[DimensionRiskRecord] = []
        evidence_by_logical = self._evidence_by_logical(resolved.evidence)
        if resolved.conflict_metrics:
            conflict_evidence = tuple(
                item
                for metric in resolved.conflict_metrics
                for item in evidence_by_logical.get(metric, ())
            )
            records.append(
                self._risk(
                    "SOURCE_CONFLICT",
                    "Multiple source candidates conflict; no value was selected.",
                    conflict_evidence,
                )
            )
        if resolved.missing:
            records.append(
                self._risk(
                    "MISSING_INPUTS",
                    f"Missing evidence: {', '.join(resolved.missing)}.",
                )
            )
        if resolved.pending:
            records.append(
                self._risk(
                    "PENDING_INPUTS",
                    f"Evidence is pending: {', '.join(resolved.pending)}.",
                )
            )
        if resolved.incomplete:
            incomplete_evidence = tuple(
                item
                for metric in resolved.incomplete
                for item in evidence_by_logical.get(metric, ())
            )
            records.append(
                self._risk(
                    "INCOMPLETE_EVIDENCE",
                    f"Evidence is present but incomplete: {', '.join(resolved.incomplete)}.",
                    incomplete_evidence,
                )
            )
        if request.quality.limitations:
            records.append(
                self._risk(
                    "INPUT_QUALITY_LIMITATIONS",
                    "Input quality limitations: "
                    + "; ".join(request.quality.limitations),
                )
            )
        return tuple(records)

    def _risk(
        self,
        code: str,
        message: str,
        evidence: Sequence[EvidenceReference] = (),
    ) -> DimensionRiskRecord:
        return DimensionRiskRecord(
            risk_id=f"risk:{self.dimension.value.lower()}:{code.lower()}",
            code=code,
            message=message,
            evidence=tuple(evidence),
        )

    def _evidence_by_logical(
        self,
        evidence: Sequence[MetricEvidence],
    ) -> Mapping[str, tuple[MetricEvidence, ...]]:
        alias_to_logical = {
            alias: logical
            for logical, aliases in self.metric_aliases.items()
            for alias in aliases
        }
        grouped: dict[str, list[MetricEvidence]] = {}
        for item in evidence:
            grouped.setdefault(alias_to_logical[item.metric_id], []).append(item)
        return MappingProxyType(
            {key: tuple(values) for key, values in grouped.items()}
        )

    def _build_explanation(
        self,
        *,
        status: ScoringState,
        evidence: tuple[MetricEvidence, ...],
        missing_inputs: tuple[str, ...],
        risks: tuple[DimensionRiskRecord, ...],
    ) -> DimensionExplanation:
        positive = tuple(
            f"Evidence available: {item.metric_id}; no desirability direction was inferred."
            for item in evidence
            if item.value is not None
        )
        missing = tuple(
            f"Missing or incomplete evidence: {metric_id}."
            for metric_id in missing_inputs
        )
        risk_messages = tuple(item.message for item in risks)
        return DimensionExplanation(
            explanation_id=f"explanation:{self.dimension.value.lower()}:v0.1",
            dimension=self.dimension,
            summary=self.summaries[status],
            evidence=evidence,
            positive_factors=positive,
            negative_factors=missing,
            risks=risk_messages,
        )


def _unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _completeness_level(status: ScoringState) -> CompletenessLevel:
    return {
        ScoringState.READY: CompletenessLevel.COMPLETE,
        ScoringState.PARTIAL: CompletenessLevel.PARTIAL,
        ScoringState.PENDING: CompletenessLevel.PENDING,
        ScoringState.INSUFFICIENT_DATA: CompletenessLevel.INSUFFICIENT,
        ScoringState.CONFLICT: CompletenessLevel.CONFLICT,
    }[status]


__all__ = (
    "BaseOpportunityDimensionEvaluator",
    "DimensionEvaluationResult",
    "DimensionExplanation",
    "DimensionRiskRecord",
    "MetricEvidence",
)
