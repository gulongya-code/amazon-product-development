"""Immutable contracts for evidence-based Opportunity Scoring Integration V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import math
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.opportunity_intelligence.integration_v0_1 import (
    OpportunityConfidence,
)


OPPORTUNITY_SCORING_INTEGRATION_VERSION = (
    "opportunity-scoring-integration-v0.1"
)


class OpportunityScoringIntegrationError(ValueError):
    """Base error for the isolated Candidate scoring path."""


class OpportunityScoringIntegrationValidationError(
    OpportunityScoringIntegrationError
):
    """Raised when an integration contract or policy is invalid."""


class OpportunityScoringIntegrationSerializationError(
    OpportunityScoringIntegrationValidationError
):
    """Raised when strict integration deserialization fails."""


class OpportunityScoreDimension(StrEnum):
    DEMAND_STRENGTH = "DEMAND_STRENGTH"
    SUPPLY_GAP = "SUPPLY_GAP"
    COMPETITION_FAVORABILITY = "COMPETITION_FAVORABILITY"
    ECONOMIC_EVIDENCE = "ECONOMIC_EVIDENCE"
    EVIDENCE_CONFIDENCE = "EVIDENCE_CONFIDENCE"


class OpportunityScoreMetricStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class OpportunityScoreDimensionStatus(StrEnum):
    SCORED = "SCORED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class OpportunityScoreStatus(StrEnum):
    CALCULATED = "CALCULATED"
    CALCULATED_PARTIAL = "CALCULATED_PARTIAL"
    PENDING_DATA = "PENDING_DATA"


class OpportunityScoreMissingDataPolicy(StrEnum):
    SKIP_RENORMALIZE = "SKIP_RENORMALIZE"
    BLOCK = "BLOCK"


class OpportunityScoreRoundingMode(StrEnum):
    HALF_UP = "HALF_UP"
    HALF_EVEN = "HALF_EVEN"
    DOWN = "DOWN"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must be non-empty text"
        )
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must be a sequence"
        )
    resolved = tuple(value)
    if not allow_empty and not resolved:
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must not be empty"
        )
    if any(type(item) is not str or not item.strip() for item in resolved):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must contain non-empty text"
        )
    if len(set(resolved)) != len(resolved):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must contain unique values"
        )
    return tuple(sorted(resolved))


def _finite(value: Any, path: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must be a finite number"
        )
    resolved = float(value)
    if not math.isfinite(resolved) or (
        minimum is not None and resolved < minimum
    ):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must be a finite number"
        )
    return resolved


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must contain finite JSON data"
        ) from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType(
                {key: freeze(child) for key, child in item.items()}
            )
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _frozen_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must be an object"
        )
    frozen = _freeze_json(value, path)
    assert isinstance(frozen, MappingABC)
    return frozen


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, identifier: str
) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} must be a sequence"
        )
    resolved = tuple(value)
    if any(not isinstance(item, expected) for item in resolved):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} contains an invalid record"
        )
    ordered = tuple(sorted(resolved, key=lambda item: getattr(item, identifier)))
    identities = tuple(getattr(item, identifier) for item in ordered)
    if len(set(identities)) != len(identities):
        raise OpportunityScoringIntegrationValidationError(
            f"{path} contains duplicate identities"
        )
    return ordered


def _identity(prefix: str, model: JsonContract, field: str) -> str:
    payload = model.to_dict()
    payload.pop(field)
    return deterministic_id(prefix, payload)


class _IntegrationModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OpportunityScoringIntegrationSerializationError:
            raise
        except (
            OpportunityScoringIntegrationValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise OpportunityScoringIntegrationSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoreEvidenceReference(_IntegrationModel):
    reference_id: str
    source: str
    source_id: str
    record_ids: tuple[str, ...]
    missing: bool
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("reference_id", "source", "source_id"):
            _text(getattr(self, name), f"OpportunityScoreEvidenceReference.{name}")
        object.__setattr__(
            self, "record_ids", _texts(self.record_ids, "reference record_ids")
        )
        limitations = _texts(self.limitations, "reference limitations")
        if not isinstance(self.missing, bool):
            raise OpportunityScoringIntegrationValidationError(
                "reference missing must be boolean"
            )
        if self.missing and not limitations:
            raise OpportunityScoringIntegrationValidationError(
                "missing reference requires a limitation"
            )
        object.__setattr__(self, "limitations", limitations)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoringMetricInput(_IntegrationModel):
    metric_id: str
    dimension: OpportunityScoreDimension
    value: str | None
    status: OpportunityScoreMetricStatus
    source_evidence_ids: tuple[str, ...]
    source_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.metric_id, "OpportunityScoringMetricInput.metric_id")
        if not isinstance(self.dimension, OpportunityScoreDimension):
            raise OpportunityScoringIntegrationValidationError(
                "metric dimension is invalid"
            )
        if not isinstance(self.status, OpportunityScoreMetricStatus):
            raise OpportunityScoringIntegrationValidationError(
                "metric status is invalid"
            )
        _optional_text(self.value, "OpportunityScoringMetricInput.value")
        evidence_ids = _texts(
            self.source_evidence_ids,
            "metric source_evidence_ids",
            allow_empty=False,
        )
        reference_ids = _texts(
            self.source_reference_ids,
            "metric source_reference_ids",
            allow_empty=False,
        )
        limitations = _texts(self.limitations, "metric limitations")
        if self.status is OpportunityScoreMetricStatus.AVAILABLE:
            if self.value is None or limitations:
                raise OpportunityScoringIntegrationValidationError(
                    "AVAILABLE scoring metric requires a value and no limitation"
                )
        elif self.status is OpportunityScoreMetricStatus.UNKNOWN:
            if self.value is not None or not limitations:
                raise OpportunityScoringIntegrationValidationError(
                    "UNKNOWN scoring metric requires null value and limitations"
                )
        elif not limitations:
            raise OpportunityScoringIntegrationValidationError(
                "PARTIAL scoring metric requires a limitation"
            )
        object.__setattr__(self, "source_evidence_ids", evidence_ids)
        object.__setattr__(self, "source_reference_ids", reference_ids)
        object.__setattr__(self, "limitations", limitations)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoringIntegrationInput(_IntegrationModel):
    input_id: str
    candidate_id: str
    category_scope: Mapping[str, Any]
    candidate_confidence: OpportunityConfidence
    metrics: tuple[OpportunityScoringMetricInput, ...]
    evidence_ids: tuple[str, ...]
    source_references: tuple[OpportunityScoreEvidenceReference, ...]
    limitations: tuple[str, ...]
    integration_version: str = OPPORTUNITY_SCORING_INTEGRATION_VERSION

    def __post_init__(self) -> None:
        for name in ("input_id", "candidate_id"):
            _text(getattr(self, name), f"OpportunityScoringIntegrationInput.{name}")
        if self.integration_version != OPPORTUNITY_SCORING_INTEGRATION_VERSION:
            raise OpportunityScoringIntegrationValidationError(
                "unsupported scoring integration version"
            )
        if not isinstance(self.candidate_confidence, OpportunityConfidence):
            raise OpportunityScoringIntegrationValidationError(
                "candidate confidence is invalid"
            )
        category_scope = _frozen_mapping(self.category_scope, "category_scope")
        if not category_scope:
            raise OpportunityScoringIntegrationValidationError(
                "category_scope must not be empty"
            )
        metrics = _typed_unique(
            self.metrics,
            OpportunityScoringMetricInput,
            "integration metrics",
            "metric_id",
        )
        if not metrics:
            raise OpportunityScoringIntegrationValidationError(
                "integration input requires metrics"
            )
        references = _typed_unique(
            self.source_references,
            OpportunityScoreEvidenceReference,
            "integration source_references",
            "reference_id",
        )
        if not references:
            raise OpportunityScoringIntegrationValidationError(
                "integration input requires source references"
            )
        evidence_ids = _texts(
            self.evidence_ids, "integration evidence_ids", allow_empty=False
        )
        reference_ids = {item.reference_id for item in references}
        for metric in metrics:
            if not set(metric.source_evidence_ids) <= set(evidence_ids):
                raise OpportunityScoringIntegrationValidationError(
                    f"metric {metric.metric_id} references absent evidence"
                )
            if not set(metric.source_reference_ids) <= reference_ids:
                raise OpportunityScoringIntegrationValidationError(
                    f"metric {metric.metric_id} references absent source"
                )
        object.__setattr__(self, "category_scope", category_scope)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "evidence_ids", evidence_ids)
        object.__setattr__(self, "source_references", references)
        object.__setattr__(
            self, "limitations", _texts(self.limitations, "input limitations")
        )
        if self.input_id != _identity(
            "opportunity-score-input", self, "input_id"
        ):
            raise OpportunityScoringIntegrationValidationError(
                "input_id does not match input content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoreRoundingPolicy(_IntegrationModel):
    mode: OpportunityScoreRoundingMode
    decimal_places: int

    def __post_init__(self) -> None:
        if not isinstance(self.mode, OpportunityScoreRoundingMode):
            raise OpportunityScoringIntegrationValidationError(
                "rounding mode is invalid"
            )
        if (
            isinstance(self.decimal_places, bool)
            or not isinstance(self.decimal_places, int)
            or not 0 <= self.decimal_places <= 6
        ):
            raise OpportunityScoringIntegrationValidationError(
                "decimal_places must be an integer from 0 through 6"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScorePolicy(_IntegrationModel):
    policy_version: str
    dimension_weights: Mapping[str, float]
    thresholds: Mapping[str, Any]
    missing_data_policy: OpportunityScoreMissingDataPolicy
    rounding_policy: OpportunityScoreRoundingPolicy
    confidence_rules: Mapping[str, Any]
    policy_fingerprint: str

    def __post_init__(self) -> None:
        _text(self.policy_version, "OpportunityScorePolicy.policy_version")
        if not isinstance(
            self.missing_data_policy, OpportunityScoreMissingDataPolicy
        ):
            raise OpportunityScoringIntegrationValidationError(
                "missing_data_policy is invalid"
            )
        if not isinstance(self.rounding_policy, OpportunityScoreRoundingPolicy):
            raise OpportunityScoringIntegrationValidationError(
                "rounding_policy is invalid"
            )
        weights = _frozen_mapping(self.dimension_weights, "dimension_weights")
        thresholds = _frozen_mapping(self.thresholds, "thresholds")
        confidence_rules = _frozen_mapping(
            self.confidence_rules, "confidence_rules"
        )
        normalized_weights: dict[str, float] = {}
        for key, value in weights.items():
            _text(key, "dimension weight key")
            normalized_weights[key] = _finite(
                value, f"dimension_weights.{key}", minimum=0.0
            )
        object.__setattr__(
            self,
            "dimension_weights",
            MappingProxyType(dict(sorted(normalized_weights.items()))),
        )
        object.__setattr__(self, "thresholds", thresholds)
        object.__setattr__(self, "confidence_rules", confidence_rules)
        expected_fingerprint = self.fingerprint_for_content()
        if self.policy_fingerprint != expected_fingerprint:
            raise OpportunityScoringIntegrationValidationError(
                "policy_fingerprint does not match policy content"
            )

    def fingerprint_for_content(self) -> str:
        payload = self.to_dict()
        payload.pop("policy_fingerprint")
        digest = sha256(canonical_json(payload).encode("utf-8")).hexdigest()
        return f"sha256:{digest}"


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityMetricScoreTrace(_IntegrationModel):
    trace_id: str
    metric_id: str
    dimension: OpportunityScoreDimension
    raw_value: str | None
    input_status: OpportunityScoreMetricStatus
    rule_type: str
    rule_description: str
    metric_weight: float
    normalized_score: float | None
    weighted_score: float | None
    source_evidence_ids: tuple[str, ...]
    source_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("trace_id", "metric_id", "rule_type", "rule_description"):
            _text(getattr(self, name), f"OpportunityMetricScoreTrace.{name}")
        if not isinstance(self.dimension, OpportunityScoreDimension):
            raise OpportunityScoringIntegrationValidationError(
                "trace dimension is invalid"
            )
        if not isinstance(self.input_status, OpportunityScoreMetricStatus):
            raise OpportunityScoringIntegrationValidationError(
                "trace input status is invalid"
            )
        _optional_text(self.raw_value, "OpportunityMetricScoreTrace.raw_value")
        object.__setattr__(
            self,
            "metric_weight",
            _finite(self.metric_weight, "trace metric_weight", minimum=0.0),
        )
        for name in ("normalized_score", "weighted_score"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self, name, _finite(value, f"trace {name}", minimum=0.0)
                )
        if (self.normalized_score is None) != (self.weighted_score is None):
            raise OpportunityScoringIntegrationValidationError(
                "trace normalized and weighted scores must be present together"
            )
        if self.input_status is OpportunityScoreMetricStatus.UNKNOWN and (
            self.normalized_score is not None or self.raw_value is not None
        ):
            raise OpportunityScoringIntegrationValidationError(
                "UNKNOWN trace cannot contain a value or numeric score"
            )
        object.__setattr__(
            self,
            "source_evidence_ids",
            _texts(
                self.source_evidence_ids,
                "trace source_evidence_ids",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "source_reference_ids",
            _texts(
                self.source_reference_ids,
                "trace source_reference_ids",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self, "limitations", _texts(self.limitations, "trace limitations")
        )
        if self.trace_id != _identity(
            "opportunity-score-metric-trace", self, "trace_id"
        ):
            raise OpportunityScoringIntegrationValidationError(
                "trace_id does not match trace content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityDimensionScore(_IntegrationModel):
    dimension_score_id: str
    dimension: OpportunityScoreDimension
    status: OpportunityScoreDimensionStatus
    score_value: float | None
    contribution: float | None
    max_contribution: float
    metric_traces: tuple[OpportunityMetricScoreTrace, ...]
    source_evidence_ids: tuple[str, ...]
    source_reference_ids: tuple[str, ...]
    calculation_rule: str
    explanation: str

    def __post_init__(self) -> None:
        for name in (
            "dimension_score_id",
            "calculation_rule",
            "explanation",
        ):
            _text(getattr(self, name), f"OpportunityDimensionScore.{name}")
        if not isinstance(self.dimension, OpportunityScoreDimension):
            raise OpportunityScoringIntegrationValidationError(
                "dimension score dimension is invalid"
            )
        if not isinstance(self.status, OpportunityScoreDimensionStatus):
            raise OpportunityScoringIntegrationValidationError(
                "dimension score status is invalid"
            )
        object.__setattr__(
            self,
            "max_contribution",
            _finite(
                self.max_contribution,
                "dimension max_contribution",
                minimum=0.0,
            ),
        )
        for name in ("score_value", "contribution"):
            value = getattr(self, name)
            if value is not None:
                object.__setattr__(
                    self,
                    name,
                    _finite(value, f"dimension {name}", minimum=0.0),
                )
        if self.status is OpportunityScoreDimensionStatus.UNKNOWN:
            if self.score_value is not None or self.contribution is not None:
                raise OpportunityScoringIntegrationValidationError(
                    "UNKNOWN dimension cannot contain a numeric score"
                )
        elif self.score_value is None or self.contribution is None:
            raise OpportunityScoringIntegrationValidationError(
                "scored dimension requires score and contribution"
            )
        traces = _typed_unique(
            self.metric_traces,
            OpportunityMetricScoreTrace,
            "dimension metric_traces",
            "trace_id",
        )
        if not traces or any(item.dimension is not self.dimension for item in traces):
            raise OpportunityScoringIntegrationValidationError(
                "dimension requires matching metric traces"
            )
        evidence_ids = _texts(
            self.source_evidence_ids,
            "dimension source_evidence_ids",
            allow_empty=False,
        )
        reference_ids = _texts(
            self.source_reference_ids,
            "dimension source_reference_ids",
            allow_empty=False,
        )
        if not {
            value for item in traces for value in item.source_evidence_ids
        } <= set(evidence_ids):
            raise OpportunityScoringIntegrationValidationError(
                "dimension omits trace evidence lineage"
            )
        if not {
            value for item in traces for value in item.source_reference_ids
        } <= set(reference_ids):
            raise OpportunityScoringIntegrationValidationError(
                "dimension omits trace source lineage"
            )
        object.__setattr__(self, "metric_traces", traces)
        object.__setattr__(self, "source_evidence_ids", evidence_ids)
        object.__setattr__(self, "source_reference_ids", reference_ids)
        if self.dimension_score_id != _identity(
            "opportunity-dimension-score", self, "dimension_score_id"
        ):
            raise OpportunityScoringIntegrationValidationError(
                "dimension_score_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoreValidationContract(_IntegrationModel):
    validation_contract_id: str
    category_scope: Mapping[str, Any]
    candidate_count: int
    evidence_coverage: Mapping[str, str]
    metric_availability: Mapping[str, str]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(
            self.validation_contract_id,
            "OpportunityScoreValidationContract.validation_contract_id",
        )
        if (
            isinstance(self.candidate_count, bool)
            or not isinstance(self.candidate_count, int)
            or self.candidate_count < 1
        ):
            raise OpportunityScoringIntegrationValidationError(
                "candidate_count must be a positive integer"
            )
        object.__setattr__(
            self,
            "category_scope",
            _frozen_mapping(self.category_scope, "validation category_scope"),
        )
        object.__setattr__(
            self,
            "evidence_coverage",
            _frozen_mapping(self.evidence_coverage, "evidence_coverage"),
        )
        object.__setattr__(
            self,
            "metric_availability",
            _frozen_mapping(self.metric_availability, "metric_availability"),
        )
        object.__setattr__(
            self,
            "limitations",
            _texts(self.limitations, "validation limitations"),
        )
        if self.validation_contract_id != _identity(
            "opportunity-score-validation", self, "validation_contract_id"
        ):
            raise OpportunityScoringIntegrationValidationError(
                "validation_contract_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoreExplanation(_IntegrationModel):
    explanation_id: str
    final_score: float | None
    dimension_breakdown: tuple[OpportunityDimensionScore, ...]
    metric_traces: tuple[OpportunityMetricScoreTrace, ...]
    evidence_references: tuple[OpportunityScoreEvidenceReference, ...]
    policy_version: str
    risks: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("explanation_id", "policy_version"):
            _text(getattr(self, name), f"OpportunityScoreExplanation.{name}")
        if self.final_score is not None:
            object.__setattr__(
                self,
                "final_score",
                _finite(self.final_score, "explanation final_score", minimum=0.0),
            )
        dimensions = _typed_unique(
            self.dimension_breakdown,
            OpportunityDimensionScore,
            "explanation dimension_breakdown",
            "dimension_score_id",
        )
        if {item.dimension for item in dimensions} != set(
            OpportunityScoreDimension
        ):
            raise OpportunityScoringIntegrationValidationError(
                "explanation must contain all five dimensions"
            )
        traces = _typed_unique(
            self.metric_traces,
            OpportunityMetricScoreTrace,
            "explanation metric_traces",
            "trace_id",
        )
        expected_trace_ids = {
            item.trace_id
            for dimension in dimensions
            for item in dimension.metric_traces
        }
        if {item.trace_id for item in traces} != expected_trace_ids:
            raise OpportunityScoringIntegrationValidationError(
                "explanation metric traces do not match dimension breakdown"
            )
        references = _typed_unique(
            self.evidence_references,
            OpportunityScoreEvidenceReference,
            "explanation evidence_references",
            "reference_id",
        )
        if not references:
            raise OpportunityScoringIntegrationValidationError(
                "explanation requires evidence references"
            )
        object.__setattr__(self, "dimension_breakdown", dimensions)
        object.__setattr__(self, "metric_traces", traces)
        object.__setattr__(self, "evidence_references", references)
        object.__setattr__(self, "risks", _texts(self.risks, "score risks"))
        object.__setattr__(
            self, "limitations", _texts(self.limitations, "score limitations")
        )
        if self.explanation_id != _identity(
            "opportunity-score-explanation", self, "explanation_id"
        ):
            raise OpportunityScoringIntegrationValidationError(
                "explanation_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceBasedOpportunityScore(_IntegrationModel):
    score_id: str
    candidate_id: str
    score_status: OpportunityScoreStatus
    score_value: float | None
    confidence: OpportunityConfidence
    policy_version: str
    policy_fingerprint: str
    explanation: OpportunityScoreExplanation
    validation: OpportunityScoreValidationContract
    integration_version: str = OPPORTUNITY_SCORING_INTEGRATION_VERSION

    def __post_init__(self) -> None:
        for name in (
            "score_id",
            "candidate_id",
            "policy_version",
            "policy_fingerprint",
        ):
            _text(getattr(self, name), f"EvidenceBasedOpportunityScore.{name}")
        if self.integration_version != OPPORTUNITY_SCORING_INTEGRATION_VERSION:
            raise OpportunityScoringIntegrationValidationError(
                "unsupported score integration version"
            )
        if not isinstance(self.score_status, OpportunityScoreStatus):
            raise OpportunityScoringIntegrationValidationError(
                "score_status is invalid"
            )
        if not isinstance(self.confidence, OpportunityConfidence):
            raise OpportunityScoringIntegrationValidationError(
                "score confidence is invalid"
            )
        if self.score_value is not None:
            object.__setattr__(
                self,
                "score_value",
                _finite(self.score_value, "score_value", minimum=0.0),
            )
        if self.score_status is OpportunityScoreStatus.PENDING_DATA:
            if self.score_value is not None:
                raise OpportunityScoringIntegrationValidationError(
                    "PENDING_DATA score must not contain a numeric value"
                )
        elif self.score_value is None:
            raise OpportunityScoringIntegrationValidationError(
                "calculated score requires a numeric value"
            )
        if not isinstance(self.explanation, OpportunityScoreExplanation):
            raise OpportunityScoringIntegrationValidationError(
                "score explanation is invalid"
            )
        if not isinstance(self.validation, OpportunityScoreValidationContract):
            raise OpportunityScoringIntegrationValidationError(
                "score validation contract is invalid"
            )
        if (
            self.explanation.final_score != self.score_value
            or self.explanation.policy_version != self.policy_version
        ):
            raise OpportunityScoringIntegrationValidationError(
                "score and explanation do not match"
            )
        if self.score_id != _identity(
            "evidence-based-opportunity-score", self, "score_id"
        ):
            raise OpportunityScoringIntegrationValidationError(
                "score_id does not match score content"
            )


__all__ = (
    "OPPORTUNITY_SCORING_INTEGRATION_VERSION",
    "EvidenceBasedOpportunityScore",
    "OpportunityDimensionScore",
    "OpportunityMetricScoreTrace",
    "OpportunityScoreDimension",
    "OpportunityScoreDimensionStatus",
    "OpportunityScoreEvidenceReference",
    "OpportunityScoreExplanation",
    "OpportunityScoreMetricStatus",
    "OpportunityScoreMissingDataPolicy",
    "OpportunityScorePolicy",
    "OpportunityScoreRoundingMode",
    "OpportunityScoreRoundingPolicy",
    "OpportunityScoreStatus",
    "OpportunityScoreValidationContract",
    "OpportunityScoringIntegrationError",
    "OpportunityScoringIntegrationInput",
    "OpportunityScoringIntegrationSerializationError",
    "OpportunityScoringIntegrationValidationError",
    "OpportunityScoringMetricInput",
)
