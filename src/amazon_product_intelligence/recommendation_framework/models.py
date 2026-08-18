"""Immutable public data models for Recommendation Framework V0.1."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    ContractValidationError,
    EvidenceType,
    JsonContract,
    ObservationKind,
    Severity,
    canonical_json,
    deterministic_id,
)

from .errors import (
    RecommendationFrameworkSerializationError,
    RecommendationFrameworkValidationError,
)


RECOMMENDATION_FRAMEWORK_RULESET_VERSION = "recommendation-framework-v0.1"
_EVALUATION_RULESET_VERSION = "evidence-evaluation-v0.1"
_CONFLICT_RULESET_VERSION = "conflict-resolution-v0.1"
_POLICY_RULESET_VERSION = "evidence-policy-v0.1"
_DECISION_RULESET_VERSION = "decision-framework-v0.1"
_SCORING_RULESET_VERSION = "opportunity-scoring-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_CONDITION_TYPES = {
    "EVIDENCE_INVENTORY",
    "CONFLICT_FREE_EVIDENCE",
    "KEYWORD_EVIDENCE",
    "CONFLICT_CONTEXT",
}
_APPLICABILITY_RESULTS = {
    "NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE",
    "APPLICABLE",
    "BLOCKED_BY_POLICY",
}
_RECOMMENDATION_TYPES = {
    "FURTHER_REVIEW_RECOMMENDED",
    "EVIDENCE_COLLECTION_RECOMMENDED",
    "RULE_CONDITIONS_SATISFIED",
    "RECOMMENDATION_BLOCKED_BY_POLICY",
    "RULE_NOT_APPLICABLE",
}
_RECOMMENDATION_BY_APPLICABILITY = {
    "NOT_APPLICABLE": "RULE_NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE": "EVIDENCE_COLLECTION_RECOMMENDED",
    "BLOCKED_BY_POLICY": "RECOMMENDATION_BLOCKED_BY_POLICY",
}
_POLICY_STATUSES = {"POLICY_ALLOWED", "POLICY_BLOCKED", "POLICY_NOT_APPLICABLE"}
_CONFLICT_STATUSES = {"NO_CONFLICT", "CONFLICT_PRESENT"}
_RULE_CONDITIONS = {
    "calculated_behavior": "RULE_CONDITIONS_SATISFIED",
    "conflict_visible_behavior": "FURTHER_REVIEW_RECOMMENDED",
    "missing_evidence_behavior": "EVIDENCE_COLLECTION_RECOMMENDED",
    "policy_blocked_behavior": "RECOMMENDATION_BLOCKED_BY_POLICY",
    "not_applicable_behavior": "RULE_NOT_APPLICABLE",
}
_LIMITATIONS = (
    "CURRENT_RULE_AND_EVIDENCE_ONLY",
    "NO_AUTOMATIC_SELECTION",
    "NO_FACTUAL_TRUTH_CLAIM",
    "NO_GUARANTEE_OR_FORECAST",
    "NO_MARKET_OR_INVESTMENT_DECISION",
)
_FORBIDDEN_RECOMMENDATION_PHRASES = {
    "BEST MARKET",
    "BEST PRODUCT",
    "BUY THIS PRODUCT",
    "GUARANTEED OPPORTUNITY",
    "GUARANTEED SUCCESS",
    "THIS MARKET IS PROFITABLE",
    "THIS PRODUCT WILL SUCCEED",
}
_EVALUATION_SNAPSHOT_FIELDS = {
    "snapshot_id",
    "ruleset_version",
    "source_bundle_fingerprints",
    "evidence_quality_profiles",
    "support_records",
    "conflict_records",
    "coverage",
    "diagnostics",
    "lineage_index",
}
_CONFLICT_SNAPSHOT_FIELDS = {
    "snapshot_id",
    "ruleset_version",
    "source_evaluation_snapshot_id",
    "source_bundle_fingerprints",
    "conflict_analyses",
    "resolution_attempts",
    "coverage",
    "diagnostics",
    "lineage_index",
}
_POLICY_SNAPSHOT_FIELDS = {
    "snapshot_id",
    "ruleset_version",
    "source_evaluation_snapshot_id",
    "source_conflict_resolution_snapshot_id",
    "source_bundle_fingerprints",
    "policy_definitions",
    "policy_applicability_records",
    "policy_evaluations",
    "audit_records",
    "coverage",
    "diagnostics",
    "lineage_index",
}
_DECISION_SNAPSHOT_FIELDS = {
    "snapshot_id",
    "ruleset_version",
    "source_evaluation_snapshot_id",
    "source_conflict_resolution_snapshot_id",
    "source_policy_snapshot_id",
    "source_bundle_fingerprints",
    "rule_definitions",
    "applicability_records",
    "decision_evaluations",
    "audit_records",
    "coverage",
    "diagnostics",
    "lineage_index",
}
_SCORING_SNAPSHOT_FIELDS = {
    "snapshot_id",
    "ruleset_version",
    "source_evaluation_snapshot_id",
    "source_conflict_resolution_snapshot_id",
    "source_policy_snapshot_id",
    "source_decision_snapshot_id",
    "source_bundle_fingerprints",
    "score_factors",
    "components",
    "calculations",
    "explanations",
    "coverage",
    "diagnostics",
    "lineage_index",
}


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise RecommendationFrameworkValidationError(
            f"{path} must contain finite JSON data: {exc}"
        ) from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise RecommendationFrameworkValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise RecommendationFrameworkValidationError(
            f"{path} must be non-empty text"
        )
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise RecommendationFrameworkValidationError(
            f"{path} must be a non-negative integer"
        )
    return value


def _reject_unsafe_recommendation_language(value: str, path: str) -> None:
    normalized = re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()
    if any(phrase in normalized for phrase in _FORBIDDEN_RECOMMENDATION_PHRASES):
        raise RecommendationFrameworkValidationError(
            f"{path} contains forbidden guarantee or selection language"
        )


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise RecommendationFrameworkValidationError(
            f"{path} must be {expected.__name__}"
        )


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise RecommendationFrameworkValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise RecommendationFrameworkValidationError(
            f"{path} must contain non-empty text"
        )
    if len(set(values)) != len(values):
        raise RecommendationFrameworkValidationError(
            f"{path} must contain unique values"
        )
    return tuple(sorted(values))


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, key
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise RecommendationFrameworkValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise RecommendationFrameworkValidationError(f"{path} contains duplicates")
    return ordered


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    payload = bundle.to_dict()
    for key, value in tuple(payload.items()):
        if isinstance(value, list):
            payload[key] = sorted(value, key=canonical_json)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def observation_revision_content(observation: CanonicalObservation) -> dict[str, Any]:
    payload = observation.to_dict()
    for key in (
        "semantic_observation_id",
        "observation_id",
        "provenance",
        "quality_issue_ids",
        "result_status",
    ):
        payload.pop(key, None)
    time_payload = payload.get("time")
    if isinstance(time_payload, dict):
        time_payload.pop("retrieved_at", None)
    return payload


def _validate_source_snapshot(
    payload: Mapping[str, Any],
    *,
    path: str,
    fields: set[str],
    ruleset: str,
    identity_prefix: str,
    fingerprints: Sequence[str],
    array_fields: Sequence[str],
) -> Mapping[str, Any]:
    if not isinstance(payload, MappingABC):
        raise RecommendationFrameworkValidationError(f"{path} must be an object")
    if set(payload) != fields:
        missing = sorted(fields - set(payload))
        extra = sorted(set(payload) - fields)
        raise RecommendationFrameworkValidationError(
            f"invalid {path} fields; missing={missing}, extra={extra}"
        )
    frozen = _freeze_json(payload, path)
    if frozen["ruleset_version"] != ruleset:
        raise RecommendationFrameworkValidationError(
            f"unsupported {path} ruleset version"
        )
    snapshot_id = _text(frozen["snapshot_id"], f"{path} snapshot_id")
    source_fingerprints = _unique_texts(
        frozen["source_bundle_fingerprints"],
        f"{path} source_bundle_fingerprints",
        allow_empty=False,
    )
    if any(_SHA256.fullmatch(item) is None for item in source_fingerprints):
        raise RecommendationFrameworkValidationError(
            f"{path} fingerprints must be SHA-256 hex"
        )
    if set(source_fingerprints) != set(fingerprints):
        raise RecommendationFrameworkValidationError(
            f"{path} fingerprints do not match canonical bundles"
        )
    identity_payload = dict(frozen)
    identity_payload.pop("snapshot_id")
    if snapshot_id != deterministic_id(identity_prefix, identity_payload):
        raise RecommendationFrameworkValidationError(
            f"{path} snapshot identity mismatch"
        )
    for name in array_fields:
        if not isinstance(frozen[name], tuple):
            raise RecommendationFrameworkValidationError(
                f"{path}.{name} must be an array"
            )
    if not isinstance(frozen["coverage"], MappingABC):
        raise RecommendationFrameworkValidationError(
            f"{path}.coverage must be an object"
        )
    return frozen


class _RecommendationModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except RecommendationFrameworkSerializationError:
            raise
        except (
            RecommendationFrameworkValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise RecommendationFrameworkSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationRuleDefinition(_RecommendationModel):
    """One declarative recommendation rule without automatic selection."""

    rule_id: str
    rule_version: str
    description: str
    input_requirements: Mapping[str, Any]
    conditions: Mapping[str, Any]
    expected_recommendation_behavior: str

    def __post_init__(self) -> None:
        for name in (
            "rule_id",
            "rule_version",
            "description",
            "expected_recommendation_behavior",
        ):
            _text(getattr(self, name), f"RecommendationRuleDefinition.{name}")
        if self.rule_version != "0.1":
            raise RecommendationFrameworkValidationError(
                "unsupported recommendation rule version"
            )
        _reject_unsafe_recommendation_language(
            self.description, "recommendation rule description"
        )
        requirements = _freeze_json(
            self.input_requirements, "recommendation rule input_requirements"
        )
        conditions = _freeze_json(self.conditions, "recommendation rule conditions")
        if not isinstance(requirements, MappingABC) or set(requirements) != {
            "decision_condition_type",
            "required_source_records",
        }:
            raise RecommendationFrameworkValidationError(
                "recommendation input requirement fields do not match V0.1"
            )
        if requirements["decision_condition_type"] not in _CONDITION_TYPES:
            raise RecommendationFrameworkValidationError(
                "unsupported recommendation decision condition"
            )
        sources = _unique_texts(
            requirements["required_source_records"],
            "recommendation required_source_records",
            allow_empty=False,
        )
        if sources != ("DECISION_EVALUATION", "SCORE_CALCULATION"):
            raise RecommendationFrameworkValidationError(
                "recommendation source record requirements mismatch"
            )
        if not isinstance(conditions, MappingABC) or dict(conditions) != _RULE_CONDITIONS:
            raise RecommendationFrameworkValidationError(
                "recommendation rule conditions are not the V0.1 audited mapping"
            )
        if self.expected_recommendation_behavior != (
            "AUDITABLE_RULE_OUTPUT_NO_AUTOMATIC_SELECTION"
        ):
            raise RecommendationFrameworkValidationError(
                "recommendation behavior exceeds V0.1 boundary"
            )
        object.__setattr__(self, "input_requirements", requirements)
        object.__setattr__(self, "conditions", conditions)
        if self.rule_id != deterministic_id(
            "recommendation-rule", _without_id(self, "rule_id")
        ):
            raise RecommendationFrameworkValidationError(
                "rule_id does not match recommendation rule content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationApplicabilityRecord(_RecommendationModel):
    """Availability and upstream process state for one recommendation rule."""

    recommendation_applicability_id: str
    rule_id: str
    available_evidence_ids: tuple[str, ...]
    missing_evidence_requirements: tuple[str, ...]
    score_component_ids: tuple[str, ...]
    score_calculation_ids: tuple[str, ...]
    policy_status: str
    conflict_status: str
    applicability_result: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "recommendation_applicability_id",
            "rule_id",
            "policy_status",
            "conflict_status",
            "applicability_result",
        ):
            _text(getattr(self, name), f"RecommendationApplicabilityRecord.{name}")
        for name, allow_empty in (
            ("available_evidence_ids", False),
            ("missing_evidence_requirements", True),
            ("score_component_ids", False),
            ("score_calculation_ids", False),
            ("reason_codes", False),
        ):
            object.__setattr__(
                self,
                name,
                _unique_texts(
                    getattr(self, name),
                    f"recommendation applicability {name}",
                    allow_empty=allow_empty,
                ),
            )
        if self.policy_status not in _POLICY_STATUSES:
            raise RecommendationFrameworkValidationError(
                "invalid recommendation policy status"
            )
        if self.conflict_status not in _CONFLICT_STATUSES:
            raise RecommendationFrameworkValidationError(
                "invalid recommendation conflict status"
            )
        if self.applicability_result not in _APPLICABILITY_RESULTS:
            raise RecommendationFrameworkValidationError(
                "invalid recommendation applicability result"
            )
        if (
            self.applicability_result == "BLOCKED_BY_POLICY"
            and self.policy_status != "POLICY_BLOCKED"
        ):
            raise RecommendationFrameworkValidationError(
                "policy-blocked recommendation requires blocked policy status"
            )
        if self.policy_status == "POLICY_BLOCKED" and self.applicability_result != (
            "BLOCKED_BY_POLICY"
        ):
            raise RecommendationFrameworkValidationError(
                "blocked policy must block recommendation generation"
            )
        if (
            self.applicability_result == "INSUFFICIENT_EVIDENCE"
            and not self.missing_evidence_requirements
        ):
            raise RecommendationFrameworkValidationError(
                "insufficient evidence requires explicit missing requirements"
            )
        if (
            self.missing_evidence_requirements
            and self.applicability_result
            not in {"INSUFFICIENT_EVIDENCE", "BLOCKED_BY_POLICY"}
        ):
            raise RecommendationFrameworkValidationError(
                "missing requirements require insufficient or policy-blocked state"
            )
        if self.recommendation_applicability_id != deterministic_id(
            "recommendation-applicability",
            _without_id(self, "recommendation_applicability_id"),
        ):
            raise RecommendationFrameworkValidationError(
                "recommendation_applicability_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationExplanationRecord(_RecommendationModel):
    """Complete, bounded explanation for one generated recommendation record."""

    explanation_id: str
    rule_id: str
    recommendation_type: str
    rule_explanation: str
    evidence_ids: tuple[str, ...]
    decision_evaluation_ids: tuple[str, ...]
    score_component_ids: tuple[str, ...]
    score_calculation_ids: tuple[str, ...]
    policy_evaluation_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "explanation_id",
            "rule_id",
            "recommendation_type",
            "rule_explanation",
        ):
            _text(getattr(self, name), f"RecommendationExplanationRecord.{name}")
        if self.recommendation_type not in _RECOMMENDATION_TYPES:
            raise RecommendationFrameworkValidationError(
                "invalid explanation recommendation type"
            )
        _reject_unsafe_recommendation_language(
            self.rule_explanation, "recommendation rule explanation"
        )
        for name, allow_empty in (
            ("evidence_ids", False),
            ("decision_evaluation_ids", False),
            ("score_component_ids", False),
            ("score_calculation_ids", False),
            ("policy_evaluation_ids", False),
            ("conflict_ids", True),
            ("limitations", False),
        ):
            object.__setattr__(
                self,
                name,
                _unique_texts(
                    getattr(self, name),
                    f"recommendation explanation {name}",
                    allow_empty=allow_empty,
                ),
            )
        if self.limitations != tuple(sorted(_LIMITATIONS)):
            raise RecommendationFrameworkValidationError(
                "recommendation explanation limitations mismatch"
            )
        if self.explanation_id != deterministic_id(
            "recommendation-explanation", _without_id(self, "explanation_id")
        ):
            raise RecommendationFrameworkValidationError(
                "explanation_id does not match explanation content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationGenerationRecord(_RecommendationModel):
    """One rule-generated advisory record, never factual truth or final decision."""

    recommendation_generation_id: str
    rule_id: str
    recommendation_applicability_id: str
    input_evidence_ids: tuple[str, ...]
    decision_evaluation_ids: tuple[str, ...]
    score_component_ids: tuple[str, ...]
    score_calculation_ids: tuple[str, ...]
    policy_evaluation_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    recommendation_type: str
    explanation_id: str
    process_interpretation: str

    def __post_init__(self) -> None:
        for name in (
            "recommendation_generation_id",
            "rule_id",
            "recommendation_applicability_id",
            "recommendation_type",
            "explanation_id",
            "process_interpretation",
        ):
            _text(getattr(self, name), f"RecommendationGenerationRecord.{name}")
        if self.recommendation_type not in _RECOMMENDATION_TYPES:
            raise RecommendationFrameworkValidationError(
                "invalid generated recommendation type"
            )
        for name, allow_empty in (
            ("input_evidence_ids", False),
            ("decision_evaluation_ids", False),
            ("score_component_ids", False),
            ("score_calculation_ids", False),
            ("policy_evaluation_ids", False),
            ("conflict_ids", True),
        ):
            object.__setattr__(
                self,
                name,
                _unique_texts(
                    getattr(self, name),
                    f"recommendation generation {name}",
                    allow_empty=allow_empty,
                ),
            )
        if self.process_interpretation != (
            "RULE_GENERATED_ADVISORY_RECORD_NOT_FACTUAL_TRUTH_OR_FINAL_DECISION"
        ):
            raise RecommendationFrameworkValidationError(
                "recommendation interpretation exceeds V0.1 boundary"
            )
        if self.recommendation_generation_id != deterministic_id(
            "recommendation-generation",
            _without_id(self, "recommendation_generation_id"),
        ):
            raise RecommendationFrameworkValidationError(
                "recommendation_generation_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationLineageReference(_RecommendationModel):
    """Recommendation-to-score-to-canonical replay reference."""

    recommendation_lineage_id: str
    recommendation_rule_id: str
    recommendation_applicability_id: str
    recommendation_generation_id: str
    explanation_id: str
    score_factor_id: str
    score_component_id: str
    score_calculation_id: str
    score_lineage_id: str
    decision_rule_id: str
    decision_evaluation_id: str
    decision_lineage_id: str
    policy_id: str
    policy_evaluation_id: str
    support_record_id: str
    conflict_record_id: str | None
    conflict_analysis_id: str | None
    conflict_candidate_id: str | None
    resolution_attempt_ids: tuple[str, ...]
    observation_id: str
    semantic_observation_id: str
    observation_kind: ObservationKind
    evidence_type: EvidenceType
    transformation_run_id: str
    mapping_version: str
    raw_evidence_id: str
    collection_run_id: str
    provider: str
    source_tool: str
    source_field: str
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "recommendation_lineage_id",
            "recommendation_rule_id",
            "recommendation_applicability_id",
            "recommendation_generation_id",
            "explanation_id",
            "score_factor_id",
            "score_component_id",
            "score_calculation_id",
            "score_lineage_id",
            "decision_rule_id",
            "decision_evaluation_id",
            "decision_lineage_id",
            "policy_id",
            "policy_evaluation_id",
            "support_record_id",
            "observation_id",
            "semantic_observation_id",
            "transformation_run_id",
            "mapping_version",
            "raw_evidence_id",
            "collection_run_id",
            "provider",
            "source_tool",
            "source_field",
        ):
            _text(getattr(self, name), f"RecommendationLineageReference.{name}")
        _instance(
            self.observation_kind,
            ObservationKind,
            "recommendation lineage observation_kind",
        )
        _instance(
            self.evidence_type,
            EvidenceType,
            "recommendation lineage evidence_type",
        )
        conflict_values = (
            self.conflict_record_id,
            self.conflict_analysis_id,
            self.conflict_candidate_id,
        )
        if any(item is None for item in conflict_values) != all(
            item is None for item in conflict_values
        ):
            raise RecommendationFrameworkValidationError(
                "recommendation conflict lineage identities must be supplied together"
            )
        for index, value in enumerate(item for item in conflict_values if item is not None):
            _text(value, f"recommendation conflict lineage identity {index}")
        attempts = _unique_texts(
            self.resolution_attempt_ids,
            "recommendation lineage resolution_attempt_ids",
        )
        if all(item is None for item in conflict_values) and attempts:
            raise RecommendationFrameworkValidationError(
                "non-conflict recommendation lineage cannot reference attempts"
            )
        if self.conflict_record_id is not None and not attempts:
            raise RecommendationFrameworkValidationError(
                "conflict recommendation lineage requires process evidence"
            )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "recommendation lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise RecommendationFrameworkValidationError(
                "recommendation lineage fingerprints must be SHA-256 hex"
            )
        object.__setattr__(self, "resolution_attempt_ids", attempts)
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        if self.recommendation_lineage_id != deterministic_id(
            "recommendation-lineage", _without_id(self, "recommendation_lineage_id")
        ):
            raise RecommendationFrameworkValidationError(
                "recommendation_lineage_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationDiagnostic(_RecommendationModel):
    """Non-conclusive recommendation process diagnostic."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_rule_ids: tuple[str, ...]
    related_recommendation_generation_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "recommendation diagnostic_id")
        _text(self.code, "recommendation diagnostic code")
        _instance(self.severity, Severity, "recommendation diagnostic severity")
        object.__setattr__(
            self,
            "related_rule_ids",
            _unique_texts(self.related_rule_ids, "recommendation diagnostic rule IDs"),
        )
        object.__setattr__(
            self,
            "related_recommendation_generation_ids",
            _unique_texts(
                self.related_recommendation_generation_ids,
                "recommendation diagnostic generation IDs",
            ),
        )
        _text(self.message, "recommendation diagnostic message")
        _reject_unsafe_recommendation_language(
            self.message, "recommendation diagnostic message"
        )
        if self.diagnostic_id != deterministic_id(
            "recommendation-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise RecommendationFrameworkValidationError(
                "diagnostic_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationCoverageSummary(_RecommendationModel):
    """Descriptive recommendation-process counts without rankings."""

    source_bundle_count: int
    rule_definition_count: int
    applicability_record_count: int
    generation_record_count: int
    explanation_record_count: int
    input_evidence_count: int
    decision_evaluation_reference_count: int
    score_calculation_reference_count: int
    policy_evaluation_reference_count: int
    conflict_reference_count: int
    lineage_reference_count: int
    diagnostic_count: int
    applicability_result_counts: Mapping[str, int]
    recommendation_type_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count",
            "rule_definition_count",
            "applicability_record_count",
            "generation_record_count",
            "explanation_record_count",
            "input_evidence_count",
            "decision_evaluation_reference_count",
            "score_calculation_reference_count",
            "policy_evaluation_reference_count",
            "conflict_reference_count",
            "lineage_reference_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"RecommendationCoverageSummary.{name}")
        for name, allowed in (
            ("applicability_result_counts", _APPLICABILITY_RESULTS),
            ("recommendation_type_counts", _RECOMMENDATION_TYPES),
        ):
            value = getattr(self, name)
            if not isinstance(value, MappingABC):
                raise RecommendationFrameworkValidationError(
                    f"{name} must be an object"
                )
            counts = dict(sorted(value.items()))
            if set(counts) - allowed or any(
                type(item) is not int or item < 0 for item in counts.values()
            ):
                raise RecommendationFrameworkValidationError(
                    f"{name} contains invalid counts"
                )
            object.__setattr__(self, name, MappingProxyType(counts))


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationFrameworkRequest(_RecommendationModel):
    """Strict canonical and five-snapshot serialized handoff."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    evidence_evaluation_snapshot: Mapping[str, Any]
    conflict_resolution_snapshot: Mapping[str, Any]
    evidence_policy_snapshot: Mapping[str, Any]
    decision_framework_snapshot: Mapping[str, Any]
    opportunity_scoring_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "canonical_bundles")
        if not bundles:
            raise RecommendationFrameworkValidationError(
                "canonical_bundles must not be empty"
            )
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise RecommendationFrameworkValidationError(
                    "canonical_bundles contains a wrong type"
                )
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise RecommendationFrameworkValidationError(
                    f"invalid canonical bundle: {exc}"
                ) from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise RecommendationFrameworkValidationError(
                    "duplicate canonical bundle fingerprint"
                )
            fingerprints[fingerprint] = bundle
        ordered_bundles = tuple(fingerprints[key] for key in sorted(fingerprints))
        ordered_fingerprints = tuple(sorted(fingerprints))
        evaluation = _validate_source_snapshot(
            self.evidence_evaluation_snapshot,
            path="evidence_evaluation_snapshot",
            fields=_EVALUATION_SNAPSHOT_FIELDS,
            ruleset=_EVALUATION_RULESET_VERSION,
            identity_prefix="evidence-evaluation-snapshot",
            fingerprints=ordered_fingerprints,
            array_fields=(
                "evidence_quality_profiles",
                "support_records",
                "conflict_records",
                "diagnostics",
                "lineage_index",
            ),
        )
        conflict = _validate_source_snapshot(
            self.conflict_resolution_snapshot,
            path="conflict_resolution_snapshot",
            fields=_CONFLICT_SNAPSHOT_FIELDS,
            ruleset=_CONFLICT_RULESET_VERSION,
            identity_prefix="conflict-resolution-snapshot",
            fingerprints=ordered_fingerprints,
            array_fields=(
                "conflict_analyses",
                "resolution_attempts",
                "diagnostics",
                "lineage_index",
            ),
        )
        policy = _validate_source_snapshot(
            self.evidence_policy_snapshot,
            path="evidence_policy_snapshot",
            fields=_POLICY_SNAPSHOT_FIELDS,
            ruleset=_POLICY_RULESET_VERSION,
            identity_prefix="evidence-policy-snapshot",
            fingerprints=ordered_fingerprints,
            array_fields=(
                "policy_definitions",
                "policy_applicability_records",
                "policy_evaluations",
                "audit_records",
                "diagnostics",
                "lineage_index",
            ),
        )
        decision = _validate_source_snapshot(
            self.decision_framework_snapshot,
            path="decision_framework_snapshot",
            fields=_DECISION_SNAPSHOT_FIELDS,
            ruleset=_DECISION_RULESET_VERSION,
            identity_prefix="decision-framework-snapshot",
            fingerprints=ordered_fingerprints,
            array_fields=(
                "rule_definitions",
                "applicability_records",
                "decision_evaluations",
                "audit_records",
                "diagnostics",
                "lineage_index",
            ),
        )
        scoring = _validate_source_snapshot(
            self.opportunity_scoring_snapshot,
            path="opportunity_scoring_snapshot",
            fields=_SCORING_SNAPSHOT_FIELDS,
            ruleset=_SCORING_RULESET_VERSION,
            identity_prefix="opportunity-scoring-snapshot",
            fingerprints=ordered_fingerprints,
            array_fields=(
                "score_factors",
                "components",
                "calculations",
                "explanations",
                "diagnostics",
                "lineage_index",
            ),
        )
        if conflict["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]:
            raise RecommendationFrameworkValidationError(
                "Conflict Resolution source snapshot continuity mismatch"
            )
        if (
            policy["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]
            or policy["source_conflict_resolution_snapshot_id"]
            != conflict["snapshot_id"]
        ):
            raise RecommendationFrameworkValidationError(
                "Evidence Policy source snapshot continuity mismatch"
            )
        if (
            decision["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]
            or decision["source_conflict_resolution_snapshot_id"]
            != conflict["snapshot_id"]
            or decision["source_policy_snapshot_id"] != policy["snapshot_id"]
        ):
            raise RecommendationFrameworkValidationError(
                "Decision Framework source snapshot continuity mismatch"
            )
        if (
            scoring["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]
            or scoring["source_conflict_resolution_snapshot_id"]
            != conflict["snapshot_id"]
            or scoring["source_policy_snapshot_id"] != policy["snapshot_id"]
            or scoring["source_decision_snapshot_id"] != decision["snapshot_id"]
        ):
            raise RecommendationFrameworkValidationError(
                "Opportunity Scoring source snapshot continuity mismatch"
            )
        object.__setattr__(self, "canonical_bundles", ordered_bundles)
        object.__setattr__(self, "evidence_evaluation_snapshot", evaluation)
        object.__setattr__(self, "conflict_resolution_snapshot", conflict)
        object.__setattr__(self, "evidence_policy_snapshot", policy)
        object.__setattr__(self, "decision_framework_snapshot", decision)
        object.__setattr__(self, "opportunity_scoring_snapshot", scoring)


@dataclass(frozen=True, slots=True, kw_only=True)
class RecommendationFrameworkSnapshotV0_1(_RecommendationModel):
    """Auditable rule-generated advisory records without automatic selection."""

    snapshot_id: str
    ruleset_version: str
    source_evaluation_snapshot_id: str
    source_conflict_resolution_snapshot_id: str
    source_policy_snapshot_id: str
    source_decision_snapshot_id: str
    source_scoring_snapshot_id: str
    source_bundle_fingerprints: tuple[str, ...]
    recommendation_rules: tuple[RecommendationRuleDefinition, ...]
    applicability_records: tuple[RecommendationApplicabilityRecord, ...]
    generation_records: tuple[RecommendationGenerationRecord, ...]
    explanations: tuple[RecommendationExplanationRecord, ...]
    coverage: RecommendationCoverageSummary
    diagnostics: tuple[RecommendationDiagnostic, ...]
    lineage_index: tuple[RecommendationLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id",
            "source_policy_snapshot_id",
            "source_decision_snapshot_id",
            "source_scoring_snapshot_id",
        ):
            _text(getattr(self, name), f"RecommendationFrameworkSnapshotV0_1.{name}")
        if self.ruleset_version != RECOMMENDATION_FRAMEWORK_RULESET_VERSION:
            raise RecommendationFrameworkValidationError(
                "invalid Recommendation Framework ruleset version"
            )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "recommendation snapshot source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise RecommendationFrameworkValidationError(
                "recommendation snapshot fingerprints must be SHA-256 hex"
            )
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        sequences = (
            (
                "recommendation_rules",
                RecommendationRuleDefinition,
                lambda item: item.rule_id,
            ),
            (
                "applicability_records",
                RecommendationApplicabilityRecord,
                lambda item: item.recommendation_applicability_id,
            ),
            (
                "generation_records",
                RecommendationGenerationRecord,
                lambda item: item.recommendation_generation_id,
            ),
            (
                "explanations",
                RecommendationExplanationRecord,
                lambda item: item.explanation_id,
            ),
            ("diagnostics", RecommendationDiagnostic, lambda item: item.diagnostic_id),
            (
                "lineage_index",
                RecommendationLineageReference,
                lambda item: item.recommendation_lineage_id,
            ),
        )
        for name, expected, key in sequences:
            object.__setattr__(
                self,
                name,
                _typed_unique(getattr(self, name), expected, f"snapshot {name}", key),
            )
        _instance(
            self.coverage,
            RecommendationCoverageSummary,
            "recommendation snapshot coverage",
        )
        rules = {item.rule_id: item for item in self.recommendation_rules}
        applicability = {item.rule_id: item for item in self.applicability_records}
        generations = {item.rule_id: item for item in self.generation_records}
        explanations = {item.rule_id: item for item in self.explanations}
        if (
            len(rules) != 4
            or set(rules) != set(applicability)
            or set(rules) != set(generations)
            or set(rules) != set(explanations)
            or {
                item.input_requirements["decision_condition_type"]
                for item in self.recommendation_rules
            }
            != _CONDITION_TYPES
        ):
            raise RecommendationFrameworkValidationError(
                "V0.1 requires one applicability, generation, and explanation per fixed rule"
            )
        generation_ids = {
            item.recommendation_generation_id: item
            for item in self.generation_records
        }
        for rule_id, generation in generations.items():
            applies = applicability[rule_id]
            explanation = explanations[rule_id]
            expected_type = _RECOMMENDATION_BY_APPLICABILITY.get(
                applies.applicability_result
            )
            if applies.applicability_result == "APPLICABLE":
                expected_type = (
                    "FURTHER_REVIEW_RECOMMENDED"
                    if applies.conflict_status == "CONFLICT_PRESENT"
                    else "RULE_CONDITIONS_SATISFIED"
                )
            if (
                generation.recommendation_applicability_id
                != applies.recommendation_applicability_id
                or generation.recommendation_type != expected_type
                or generation.explanation_id != explanation.explanation_id
                or explanation.rule_explanation != rules[rule_id].description
                or generation.input_evidence_ids != applies.available_evidence_ids
                or generation.score_component_ids != applies.score_component_ids
                or generation.score_calculation_ids != applies.score_calculation_ids
                or explanation.recommendation_type != generation.recommendation_type
                or explanation.evidence_ids != generation.input_evidence_ids
                or explanation.decision_evaluation_ids
                != generation.decision_evaluation_ids
                or explanation.score_component_ids != generation.score_component_ids
                or explanation.score_calculation_ids
                != generation.score_calculation_ids
                or explanation.policy_evaluation_ids
                != generation.policy_evaluation_ids
                or explanation.conflict_ids != generation.conflict_ids
            ):
                raise RecommendationFrameworkValidationError(
                    "recommendation applicability, generation, or explanation mismatch"
                )
        lineages_by_generation: dict[
            str, list[RecommendationLineageReference]
        ] = {}
        for lineage in self.lineage_index:
            generation = generation_ids.get(lineage.recommendation_generation_id)
            if (
                generation is None
                or generation.rule_id != lineage.recommendation_rule_id
                or generation.recommendation_applicability_id
                != lineage.recommendation_applicability_id
                or generation.explanation_id != lineage.explanation_id
                or lineage.score_component_id not in generation.score_component_ids
                or lineage.score_calculation_id not in generation.score_calculation_ids
                or lineage.decision_evaluation_id
                not in generation.decision_evaluation_ids
                or lineage.policy_evaluation_id
                not in generation.policy_evaluation_ids
                or lineage.support_record_id not in generation.input_evidence_ids
            ):
                raise RecommendationFrameworkValidationError(
                    "recommendation lineage contains an orphan reference"
                )
            if (
                lineage.conflict_record_id is not None
                and lineage.conflict_record_id not in generation.conflict_ids
            ):
                raise RecommendationFrameworkValidationError(
                    "recommendation lineage references an unrelated conflict"
                )
            lineages_by_generation.setdefault(
                lineage.recommendation_generation_id, []
            ).append(lineage)
        for generation in self.generation_records:
            lineages = lineages_by_generation.get(
                generation.recommendation_generation_id, []
            )
            if not lineages or {
                item.score_calculation_id for item in lineages
            } != set(generation.score_calculation_ids) or {
                item.decision_evaluation_id for item in lineages
            } != set(generation.decision_evaluation_ids) or {
                item.policy_evaluation_id for item in lineages
            } != set(generation.policy_evaluation_ids) or {
                item.support_record_id for item in lineages
            } != set(generation.input_evidence_ids) or {
                item.conflict_record_id
                for item in lineages
                if item.conflict_record_id is not None
            } != set(generation.conflict_ids):
                raise RecommendationFrameworkValidationError(
                    "recommendation lineage does not cover generation inputs"
                )
        rule_ids = set(rules)
        for diagnostic in self.diagnostics:
            if not set(diagnostic.related_rule_ids) <= rule_ids or not set(
                diagnostic.related_recommendation_generation_ids
            ) <= set(generation_ids):
                raise RecommendationFrameworkValidationError(
                    "recommendation diagnostic contains an orphan reference"
                )
        expected_coverage = coverage_from_records(
            bundle_count=len(fingerprints),
            rules=self.recommendation_rules,
            applicability=self.applicability_records,
            generations=self.generation_records,
            explanations=self.explanations,
            diagnostics=self.diagnostics,
            lineage=self.lineage_index,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise RecommendationFrameworkValidationError(
                "recommendation coverage mismatch"
            )
        expected_id = deterministic_id(
            "recommendation-framework-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise RecommendationFrameworkSerializationError(
                "snapshot_id does not match snapshot content"
            )

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        """Replay recommendation lineage through canonical transformation evidence."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence):
            raise RecommendationFrameworkValidationError(
                "bundles must be a non-empty sequence"
            )
        if not bundles:
            raise RecommendationFrameworkValidationError(
                "bundles must be a non-empty sequence"
            )
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[
            tuple[str, str], tuple[CanonicalObservation, set[str]]
        ] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise RecommendationFrameworkValidationError(
                    "against-bundles input contains a wrong type"
                )
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise RecommendationFrameworkValidationError(
                    f"invalid canonical bundle: {exc}"
                ) from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise RecommendationFrameworkValidationError(
                    "duplicate canonical bundle fingerprint"
                )
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise RecommendationFrameworkValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                content = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != content:
                    raise RecommendationFrameworkValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = content
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                current = observations.get(key)
                if current is not None and canonical_json(current[0]) != canonical_json(
                    observation
                ):
                    raise RecommendationFrameworkValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current is None:
                    observations[key] = (observation, {fingerprint})
                else:
                    current[1].add(fingerprint)
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise RecommendationFrameworkValidationError(
                "recommendation snapshot fingerprints do not match supplied bundles"
            )
        grouped_runs: dict[tuple[str, str, str], set[str]] = {}
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            entry = observations.get(key)
            if entry is None:
                raise RecommendationFrameworkValidationError(
                    f"orphan recommendation observation: {reference.observation_id}"
                )
            observation, source_fingerprints = entry
            transformation = observation.provenance.transformation
            run = runs.get(reference.transformation_run_id)
            if run is None:
                raise RecommendationFrameworkValidationError(
                    f"orphan recommendation transformation: {reference.transformation_run_id}"
                )
            expected = (
                (reference.semantic_observation_id, observation.semantic_observation_id),
                (reference.observation_kind, observation.observation_kind),
                (reference.evidence_type, observation.evidence_type),
                (reference.mapping_version, transformation.mapping_version),
                (reference.raw_evidence_id, transformation.raw_evidence_reference),
                (reference.collection_run_id, transformation.collection_run_id),
                (reference.provider, observation.provenance.provider),
                (reference.source_tool, observation.provenance.source_tool),
                (reference.source_field, observation.provenance.source_field),
                (set(reference.source_bundle_fingerprints), source_fingerprints),
            )
            if any(left != right for left, right in expected):
                raise RecommendationFrameworkValidationError(
                    f"recommendation lineage content mismatch: {reference.observation_id}"
                )
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or reference.raw_evidence_id not in raw_ids
                or reference.raw_evidence_id not in run.input_raw_evidence_references
                or reference.observation_id not in run.output_observation_ids
            ):
                raise RecommendationFrameworkValidationError(
                    f"broken recommendation transformation lineage: {reference.observation_id}"
                )
            group = (
                reference.recommendation_generation_id,
                reference.policy_evaluation_id,
                reference.observation_id,
            )
            grouped_runs.setdefault(group, set()).add(
                reference.transformation_run_id
            )
        for (_, _, observation_id), actual_runs in grouped_runs.items():
            expected_runs = {key[1] for key in observations if key[0] == observation_id}
            if actual_runs != expected_runs:
                raise RecommendationFrameworkValidationError(
                    f"recommendation lineage omits an observation emission: {observation_id}"
                )
        return self


def coverage_from_records(
    *,
    bundle_count: int,
    rules: Sequence[RecommendationRuleDefinition],
    applicability: Sequence[RecommendationApplicabilityRecord],
    generations: Sequence[RecommendationGenerationRecord],
    explanations: Sequence[RecommendationExplanationRecord],
    diagnostics: Sequence[RecommendationDiagnostic],
    lineage: Sequence[RecommendationLineageReference],
) -> RecommendationCoverageSummary:
    return RecommendationCoverageSummary(
        source_bundle_count=bundle_count,
        rule_definition_count=len(rules),
        applicability_record_count=len(applicability),
        generation_record_count=len(generations),
        explanation_record_count=len(explanations),
        input_evidence_count=len({
            evidence_id
            for generation in generations
            for evidence_id in generation.input_evidence_ids
        }),
        decision_evaluation_reference_count=len({
            decision_id
            for generation in generations
            for decision_id in generation.decision_evaluation_ids
        }),
        score_calculation_reference_count=len({
            score_id
            for generation in generations
            for score_id in generation.score_calculation_ids
        }),
        policy_evaluation_reference_count=len({
            policy_id
            for generation in generations
            for policy_id in generation.policy_evaluation_ids
        }),
        conflict_reference_count=len({
            conflict_id
            for generation in generations
            for conflict_id in generation.conflict_ids
        }),
        lineage_reference_count=len(lineage),
        diagnostic_count=len(diagnostics),
        applicability_result_counts=dict(sorted(Counter(
            item.applicability_result for item in applicability
        ).items())),
        recommendation_type_counts=dict(sorted(Counter(
            item.recommendation_type for item in generations
        ).items())),
    )


__all__ = (
    "RECOMMENDATION_FRAMEWORK_RULESET_VERSION",
    "RecommendationFrameworkRequest",
    "RecommendationFrameworkSnapshotV0_1",
    "RecommendationRuleDefinition",
    "RecommendationApplicabilityRecord",
    "RecommendationGenerationRecord",
    "RecommendationExplanationRecord",
    "RecommendationCoverageSummary",
    "RecommendationLineageReference",
    "RecommendationDiagnostic",
)
