"""Non-executable Opportunity Scoring Engine contracts V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    canonical_json,
)

from .errors import OpportunityScoringValidationError


ENGINE_ARCHITECTURE_VERSION = "opportunity-scoring-engine-architecture-v0.1"
BUSINESS_DECISION_REQUIRED = "BUSINESS_DECISION_REQUIRED"


class OpportunityDimension(StrEnum):
    DEMAND_POTENTIAL = "DEMAND_POTENTIAL"
    COMPETITION_ACCESSIBILITY = "COMPETITION_ACCESSIBILITY"
    PRODUCT_ECONOMICS_READINESS = "PRODUCT_ECONOMICS_READINESS"


class ScoringState(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICT = "CONFLICT"


class MetricInputStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"
    MISSING = "MISSING"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    UNKNOWN = "UNKNOWN"
    CONFLICT = "CONFLICT"


class ConfidenceLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class CompletenessLevel(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    PENDING = "PENDING"
    INSUFFICIENT = "INSUFFICIENT"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpportunityScoringValidationError(f"{path} must be non-empty text")
    return value


def _texts(value: Sequence[str], path: str) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OpportunityScoringValidationError(f"{path} must be a sequence")
    resolved = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in resolved):
        raise OpportunityScoringValidationError(f"{path} must contain non-empty text")
    if len(set(resolved)) != len(resolved):
        raise OpportunityScoringValidationError(f"{path} must contain unique values")
    return resolved


def _timestamp(value: str, path: str) -> str:
    _text(value, path)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise OpportunityScoringValidationError(f"{path} must use RFC 3339") from exc
    if parsed.tzinfo is None:
        raise OpportunityScoringValidationError(f"{path} must include a timezone")
    return value


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise OpportunityScoringValidationError(
            f"{path} must contain finite JSON data"
        ) from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


class _EngineContract(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OpportunityScoringValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise OpportunityScoringValidationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductIdentityInput(_EngineContract):
    product_id: str
    asin: str
    marketplace: str

    def __post_init__(self) -> None:
        _text(self.product_id, "ProductIdentityInput.product_id")
        asin = _text(self.asin, "ProductIdentityInput.asin").strip().upper()
        if len(asin) != 10 or not asin.isalnum():
            raise OpportunityScoringValidationError("product ASIN must be 10 alphanumeric characters")
        marketplace = _text(
            self.marketplace, "ProductIdentityInput.marketplace"
        ).strip().upper()
        object.__setattr__(self, "asin", asin)
        object.__setattr__(self, "marketplace", marketplace)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProvenanceReference(_EngineContract):
    provenance_id: str
    canonical_field: str
    source: str
    snapshot_id: str
    timestamp: str
    source_field: str
    raw_evidence_id: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "provenance_id",
            "canonical_field",
            "source",
            "snapshot_id",
            "source_field",
        ):
            _text(getattr(self, name), f"ProvenanceReference.{name}")
        _timestamp(self.timestamp, "ProvenanceReference.timestamp")
        if self.raw_evidence_id is not None:
            _text(self.raw_evidence_id, "ProvenanceReference.raw_evidence_id")


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricInput(_EngineContract):
    metric_id: str
    dimension: OpportunityDimension
    value: Any
    status: MetricInputStatus
    source: str
    snapshot_id: str
    timestamp: str
    confidence: ConfidenceLevel
    completeness: CompletenessLevel
    provenance_id: str
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("metric_id", "source", "snapshot_id", "provenance_id"):
            _text(getattr(self, name), f"MetricInput.{name}")
        _timestamp(self.timestamp, "MetricInput.timestamp")
        if not isinstance(self.dimension, OpportunityDimension):
            raise OpportunityScoringValidationError("MetricInput.dimension is invalid")
        if not isinstance(self.status, MetricInputStatus):
            raise OpportunityScoringValidationError("MetricInput.status is invalid")
        if not isinstance(self.confidence, ConfidenceLevel):
            raise OpportunityScoringValidationError("MetricInput.confidence is invalid")
        if not isinstance(self.completeness, CompletenessLevel):
            raise OpportunityScoringValidationError("MetricInput.completeness is invalid")
        object.__setattr__(
            self, "quality_flags", _texts(self.quality_flags, "MetricInput.quality_flags")
        )
        frozen = _freeze_json(self.value, "MetricInput.value")
        if self.status is MetricInputStatus.AVAILABLE and frozen is None:
            raise OpportunityScoringValidationError(
                "AVAILABLE metric input must contain a value"
            )
        if self.status in {
            MetricInputStatus.MISSING,
            MetricInputStatus.NOT_AVAILABLE,
            MetricInputStatus.UNKNOWN,
            MetricInputStatus.PENDING,
            MetricInputStatus.CONFLICT,
        } and frozen is not None:
            raise OpportunityScoringValidationError(
                f"{self.status.value} metric input must not contain a selected value"
            )
        object.__setattr__(self, "value", frozen)


@dataclass(frozen=True, slots=True, kw_only=True)
class InputQuality(_EngineContract):
    confidence: ConfidenceLevel
    completeness: CompletenessLevel
    missing_inputs: tuple[str, ...] = ()
    conflict_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.confidence, ConfidenceLevel):
            raise OpportunityScoringValidationError("InputQuality.confidence is invalid")
        if not isinstance(self.completeness, CompletenessLevel):
            raise OpportunityScoringValidationError("InputQuality.completeness is invalid")
        for name in ("missing_inputs", "conflict_ids", "limitations"):
            object.__setattr__(self, name, _texts(getattr(self, name), f"InputQuality.{name}"))
        if self.completeness is CompletenessLevel.CONFLICT and not self.conflict_ids:
            raise OpportunityScoringValidationError(
                "CONFLICT completeness requires conflict_ids"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoringEngineInput(_EngineContract):
    product_identity: ProductIdentityInput
    metrics: Mapping[str, MetricInput]
    provenance: tuple[ProvenanceReference, ...]
    quality: InputQuality

    def __post_init__(self) -> None:
        if not isinstance(self.product_identity, ProductIdentityInput):
            raise OpportunityScoringValidationError("product_identity is invalid")
        if not isinstance(self.metrics, MappingABC):
            raise OpportunityScoringValidationError("metrics must be a mapping")
        metrics = dict(self.metrics)
        if any(not isinstance(item, MetricInput) for item in metrics.values()):
            raise OpportunityScoringValidationError("metrics must contain MetricInput values")
        if any(key != item.metric_id for key, item in metrics.items()):
            raise OpportunityScoringValidationError("metric keys must match metric_id")
        provenance = tuple(self.provenance)
        if not provenance or any(not isinstance(item, ProvenanceReference) for item in provenance):
            raise OpportunityScoringValidationError(
                "provenance must contain ProvenanceReference records"
            )
        provenance_by_id = {item.provenance_id: item for item in provenance}
        if len(provenance_by_id) != len(provenance):
            raise OpportunityScoringValidationError("provenance IDs must be unique")
        for metric in metrics.values():
            reference = provenance_by_id.get(metric.provenance_id)
            if reference is None:
                raise OpportunityScoringValidationError(
                    f"metric {metric.metric_id} has no provenance reference"
                )
            if (
                reference.canonical_field != metric.metric_id
                or reference.source != metric.source
                or reference.snapshot_id != metric.snapshot_id
                or reference.timestamp != metric.timestamp
            ):
                raise OpportunityScoringValidationError(
                    f"metric {metric.metric_id} provenance does not match its source context"
                )
        if not isinstance(self.quality, InputQuality):
            raise OpportunityScoringValidationError("quality must be InputQuality")
        object.__setattr__(self, "metrics", MappingProxyType(metrics))
        object.__setattr__(self, "provenance", provenance)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceReference(_EngineContract):
    metric_id: str
    source: str
    snapshot_id: str
    timestamp: str
    provenance_id: str

    def __post_init__(self) -> None:
        for name in ("metric_id", "source", "snapshot_id", "provenance_id"):
            _text(getattr(self, name), f"EvidenceReference.{name}")
        _timestamp(self.timestamp, "EvidenceReference.timestamp")


@dataclass(frozen=True, slots=True, kw_only=True)
class RiskRecord(_EngineContract):
    risk_id: str
    code: str
    message: str
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        for name in ("risk_id", "code", "message"):
            _text(getattr(self, name), f"RiskRecord.{name}")
        evidence = tuple(self.evidence)
        if any(not isinstance(item, EvidenceReference) for item in evidence):
            raise OpportunityScoringValidationError(
                "RiskRecord.evidence must contain EvidenceReference records"
            )
        object.__setattr__(self, "evidence", evidence)


@dataclass(frozen=True, slots=True, kw_only=True)
class DimensionResult(_EngineContract):
    dimension: OpportunityDimension
    result_status: ScoringState
    evidence: tuple[EvidenceReference, ...]
    missing_inputs: tuple[str, ...]
    risks: tuple[RiskRecord, ...]
    conflict_ids: tuple[str, ...]
    score_value: Any = None
    business_parameters_status: str = BUSINESS_DECISION_REQUIRED

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, OpportunityDimension):
            raise OpportunityScoringValidationError("DimensionResult.dimension is invalid")
        if not isinstance(self.result_status, ScoringState):
            raise OpportunityScoringValidationError("DimensionResult.result_status is invalid")
        evidence = tuple(self.evidence)
        risks = tuple(self.risks)
        if any(not isinstance(item, EvidenceReference) for item in evidence):
            raise OpportunityScoringValidationError("dimension evidence is invalid")
        if any(not isinstance(item, RiskRecord) for item in risks):
            raise OpportunityScoringValidationError("dimension risks are invalid")
        missing = _texts(self.missing_inputs, "DimensionResult.missing_inputs")
        conflicts = _texts(self.conflict_ids, "DimensionResult.conflict_ids")
        if self.score_value is not None:
            raise OpportunityScoringValidationError(
                "business score values are not executable in architecture V0.1"
            )
        if self.business_parameters_status != BUSINESS_DECISION_REQUIRED:
            raise OpportunityScoringValidationError(
                "dimension business parameters must remain BUSINESS_DECISION_REQUIRED"
            )
        if self.result_status is ScoringState.READY and (not evidence or missing or conflicts):
            raise OpportunityScoringValidationError(
                "READY dimension requires evidence and no missing/conflict references"
            )
        if self.result_status is ScoringState.PARTIAL and (not evidence or not missing):
            raise OpportunityScoringValidationError(
                "PARTIAL dimension requires evidence and missing inputs"
            )
        if self.result_status in {ScoringState.PENDING, ScoringState.INSUFFICIENT_DATA} and not missing:
            raise OpportunityScoringValidationError(
                f"{self.result_status.value} dimension requires missing inputs"
            )
        if self.result_status is ScoringState.CONFLICT and not conflicts:
            raise OpportunityScoringValidationError(
                "CONFLICT dimension requires conflict_ids"
            )
        object.__setattr__(self, "evidence", evidence)
        object.__setattr__(self, "missing_inputs", missing)
        object.__setattr__(self, "risks", risks)
        object.__setattr__(self, "conflict_ids", conflicts)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfidenceResult(_EngineContract):
    level: ConfidenceLevel
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.level, ConfidenceLevel):
            raise OpportunityScoringValidationError("ConfidenceResult.level is invalid")
        reasons = _texts(self.reasons, "ConfidenceResult.reasons")
        if not reasons:
            raise OpportunityScoringValidationError("confidence requires a reason")
        object.__setattr__(self, "reasons", reasons)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompletenessResult(_EngineContract):
    level: CompletenessLevel
    available_inputs: tuple[str, ...]
    missing_inputs: tuple[str, ...]
    pending_inputs: tuple[str, ...]
    conflict_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.level, CompletenessLevel):
            raise OpportunityScoringValidationError("CompletenessResult.level is invalid")
        for name in ("available_inputs", "missing_inputs", "pending_inputs", "conflict_ids"):
            object.__setattr__(
                self, name, _texts(getattr(self, name), f"CompletenessResult.{name}")
            )
        if self.level is CompletenessLevel.COMPLETE and (
            self.missing_inputs or self.pending_inputs or self.conflict_ids
        ):
            raise OpportunityScoringValidationError(
                "COMPLETE result cannot contain missing, pending, or conflict references"
            )
        if self.level is CompletenessLevel.CONFLICT and not self.conflict_ids:
            raise OpportunityScoringValidationError(
                "CONFLICT completeness requires conflict_ids"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ExplanationRecord(_EngineContract):
    explanation_id: str
    dimension: OpportunityDimension
    summary: str
    evidence: tuple[EvidenceReference, ...]
    positive_factors: tuple[str, ...]
    negative_factors: tuple[str, ...]
    risks: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.explanation_id, "ExplanationRecord.explanation_id")
        _text(self.summary, "ExplanationRecord.summary")
        if not isinstance(self.dimension, OpportunityDimension):
            raise OpportunityScoringValidationError("ExplanationRecord.dimension is invalid")
        evidence = tuple(self.evidence)
        if any(not isinstance(item, EvidenceReference) for item in evidence):
            raise OpportunityScoringValidationError("explanation evidence is invalid")
        for name in ("positive_factors", "negative_factors", "risks"):
            object.__setattr__(
                self, name, _texts(getattr(self, name), f"ExplanationRecord.{name}")
            )
        if not evidence and not self.risks and not self.positive_factors and not self.negative_factors:
            raise OpportunityScoringValidationError(
                "explanation must reference evidence, factors, or risks"
            )
        object.__setattr__(self, "evidence", evidence)


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoringConfigurationStatus(_EngineContract):
    score_version: str = BUSINESS_DECISION_REQUIRED
    dimension_weights: str = BUSINESS_DECISION_REQUIRED
    thresholds: str = BUSINESS_DECISION_REQUIRED
    aggregation_formula: str = BUSINESS_DECISION_REQUIRED
    normalization_parameters: str = BUSINESS_DECISION_REQUIRED

    def __post_init__(self) -> None:
        for name in (
            "score_version",
            "dimension_weights",
            "thresholds",
            "aggregation_formula",
            "normalization_parameters",
        ):
            if getattr(self, name) != BUSINESS_DECISION_REQUIRED:
                raise OpportunityScoringValidationError(
                    f"{name} must remain BUSINESS_DECISION_REQUIRED"
                )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoringEngineResult(_EngineContract):
    result_status: ScoringState
    score_version: str
    dimension_results: tuple[DimensionResult, ...]
    confidence: ConfidenceResult
    completeness: CompletenessResult
    risks: tuple[RiskRecord, ...]
    missing_inputs: tuple[str, ...]
    provenance: tuple[ProvenanceReference, ...]
    explanations: tuple[ExplanationRecord, ...]
    configuration: ScoringConfigurationStatus
    score_value: Any = None
    architecture_version: str = ENGINE_ARCHITECTURE_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.result_status, ScoringState):
            raise OpportunityScoringValidationError("result_status is invalid")
        if self.score_version != BUSINESS_DECISION_REQUIRED:
            raise OpportunityScoringValidationError(
                "score_version must remain BUSINESS_DECISION_REQUIRED"
            )
        if self.architecture_version != ENGINE_ARCHITECTURE_VERSION:
            raise OpportunityScoringValidationError("architecture version is invalid")
        if self.score_value is not None:
            raise OpportunityScoringValidationError(
                "architecture V0.1 cannot contain a final score"
            )
        dimensions = tuple(self.dimension_results)
        expected_dimensions = set(OpportunityDimension)
        if any(not isinstance(item, DimensionResult) for item in dimensions):
            raise OpportunityScoringValidationError("dimension_results are invalid")
        if {item.dimension for item in dimensions} != expected_dimensions or len(dimensions) != 3:
            raise OpportunityScoringValidationError(
                "dimension_results must contain each required dimension exactly once"
            )
        explanations = tuple(self.explanations)
        if not explanations:
            raise OpportunityScoringValidationError(
                "scoring results are invalid without explanations"
            )
        if any(not isinstance(item, ExplanationRecord) for item in explanations):
            raise OpportunityScoringValidationError("explanations are invalid")
        if len(explanations) != 3 or {item.dimension for item in explanations} != expected_dimensions:
            raise OpportunityScoringValidationError(
                "explanations must cover each dimension exactly once"
            )
        risks = tuple(self.risks)
        provenance = tuple(self.provenance)
        if any(not isinstance(item, RiskRecord) for item in risks):
            raise OpportunityScoringValidationError("risks are invalid")
        if not provenance or any(not isinstance(item, ProvenanceReference) for item in provenance):
            raise OpportunityScoringValidationError("provenance must not be empty")
        provenance_by_id = {item.provenance_id: item for item in provenance}
        if len(provenance_by_id) != len(provenance):
            raise OpportunityScoringValidationError("provenance IDs must be unique")
        evidence_records = (
            *(evidence for item in dimensions for evidence in item.evidence),
            *(evidence for risk in risks for evidence in risk.evidence),
            *(evidence for item in explanations for evidence in item.evidence),
        )
        for evidence in evidence_records:
            reference = provenance_by_id.get(evidence.provenance_id)
            if reference is None:
                raise OpportunityScoringValidationError(
                    f"evidence {evidence.metric_id} has no output provenance reference"
                )
            if (
                reference.canonical_field != evidence.metric_id
                or reference.source != evidence.source
                or reference.snapshot_id != evidence.snapshot_id
                or reference.timestamp != evidence.timestamp
            ):
                raise OpportunityScoringValidationError(
                    f"evidence {evidence.metric_id} provenance context does not match"
                )
        missing = _texts(self.missing_inputs, "OpportunityScoringEngineResult.missing_inputs")
        if not isinstance(self.confidence, ConfidenceResult):
            raise OpportunityScoringValidationError("confidence is invalid")
        if not isinstance(self.completeness, CompletenessResult):
            raise OpportunityScoringValidationError("completeness is invalid")
        if not isinstance(self.configuration, ScoringConfigurationStatus):
            raise OpportunityScoringValidationError("configuration is invalid")
        if self.result_status is ScoringState.PENDING and not missing:
            raise OpportunityScoringValidationError("PENDING result requires missing inputs")
        if self.result_status is ScoringState.READY and (
            missing
            or self.completeness.level is not CompletenessLevel.COMPLETE
            or any(item.result_status is not ScoringState.READY for item in dimensions)
        ):
            raise OpportunityScoringValidationError(
                "READY result requires complete READY dimensions and no missing inputs"
            )
        if self.result_status is ScoringState.PARTIAL and (
            not missing
            or not any(item.result_status is ScoringState.PARTIAL for item in dimensions)
        ):
            raise OpportunityScoringValidationError(
                "PARTIAL result requires a partial dimension and missing inputs"
            )
        if self.result_status is ScoringState.INSUFFICIENT_DATA and (
            not missing
            or not any(
                item.result_status is ScoringState.INSUFFICIENT_DATA
                for item in dimensions
            )
        ):
            raise OpportunityScoringValidationError(
                "INSUFFICIENT_DATA result requires an insufficient dimension and missing inputs"
            )
        if self.result_status is ScoringState.CONFLICT and not any(
            item.result_status is ScoringState.CONFLICT for item in dimensions
        ):
            raise OpportunityScoringValidationError(
                "CONFLICT result requires a conflicting dimension"
            )
        object.__setattr__(self, "dimension_results", dimensions)
        object.__setattr__(self, "risks", risks)
        object.__setattr__(self, "missing_inputs", missing)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "explanations", explanations)


__all__ = (
    "BUSINESS_DECISION_REQUIRED",
    "ENGINE_ARCHITECTURE_VERSION",
    "CompletenessLevel",
    "CompletenessResult",
    "ConfidenceLevel",
    "ConfidenceResult",
    "DimensionResult",
    "EvidenceReference",
    "ExplanationRecord",
    "InputQuality",
    "MetricInput",
    "MetricInputStatus",
    "OpportunityDimension",
    "OpportunityScoringEngineInput",
    "OpportunityScoringEngineResult",
    "ProductIdentityInput",
    "ProvenanceReference",
    "RiskRecord",
    "ScoringConfigurationStatus",
    "ScoringState",
)
