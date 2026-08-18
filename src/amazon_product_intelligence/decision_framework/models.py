"""Immutable public data models for Decision Framework V0.1."""

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
    DecisionFrameworkSerializationError,
    DecisionFrameworkValidationError,
)


DECISION_FRAMEWORK_RULESET_VERSION = "decision-framework-v0.1"
_EVALUATION_RULESET_VERSION = "evidence-evaluation-v0.1"
_CONFLICT_RULESET_VERSION = "conflict-resolution-v0.1"
_POLICY_RULESET_VERSION = "evidence-policy-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_APPLICABILITY_RESULTS = {
    "NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE",
    "APPLICABLE",
    "BLOCKED_BY_POLICY",
}
_EVALUATION_RESULTS = {
    "RULE_NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE",
    "RULE_ANALYSIS_RECORDED",
    "RULE_ANALYSIS_BLOCKED_BY_POLICY",
}
_RESULT_BY_APPLICABILITY = {
    "NOT_APPLICABLE": "RULE_NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
    "APPLICABLE": "RULE_ANALYSIS_RECORDED",
    "BLOCKED_BY_POLICY": "RULE_ANALYSIS_BLOCKED_BY_POLICY",
}
_POLICY_STATUSES = {"POLICY_ALLOWED", "POLICY_BLOCKED", "POLICY_NOT_APPLICABLE"}
_CONFLICT_STATUSES = {"NO_CONFLICT", "CONFLICT_PRESENT"}
_CONDITION_BEHAVIORS = {
    "EVIDENCE_INVENTORY": "RECORD_EVIDENCE_AVAILABILITY_WITHOUT_CONCLUSION",
    "CONFLICT_FREE_EVIDENCE": "RECORD_ANALYSIS_ONLY_WHEN_CONFLICT_POLICY_ALLOWS",
    "KEYWORD_EVIDENCE": "RECORD_KEYWORD_EVIDENCE_AVAILABILITY_WITHOUT_RECOMMENDATION",
    "CONFLICT_CONTEXT": "RECORD_CONFLICT_CONTEXT_WITHOUT_RESOLUTION",
}
_CONDITION_CONFLICT_REQUIREMENTS = {
    "EVIDENCE_INVENTORY": "ANY",
    "CONFLICT_FREE_EVIDENCE": "ABSENT",
    "KEYWORD_EVIDENCE": "ABSENT",
    "CONFLICT_CONTEXT": "PRESENT",
}
_CONDITION_REQUIRED_POLICIES = {
    "EVIDENCE_INVENTORY": ("LINEAGE_COMPLETENESS_REQUIRED",),
    "CONFLICT_FREE_EVIDENCE": (
        "CONFLICT_PRESENT",
        "LINEAGE_COMPLETENESS_REQUIRED",
    ),
    "KEYWORD_EVIDENCE": (
        "CONFLICT_PRESENT",
        "LINEAGE_COMPLETENESS_REQUIRED",
    ),
    "CONFLICT_CONTEXT": ("LINEAGE_COMPLETENESS_REQUIRED",),
}
_KEYWORD_KINDS = (
    ObservationKind.KEYWORD_METRIC.value,
    ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP.value,
)
_FORBIDDEN_OUTPUT_KEY_TOKENS = {
    "BEST",
    "CONFIDENCE",
    "INVESTMENT",
    "MARKET_ENTRY",
    "PREFERRED",
    "PRIORITY",
    "PROFIT",
    "RANKING",
    "RECOMMENDATION",
    "REVENUE",
    "ROI",
    "SCORE",
    "SELECTED",
    "SELECTION",
    "TRUST",
    "TRUTH",
    "WEIGHT",
    "WINNER",
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


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise DecisionFrameworkValidationError(
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
        raise DecisionFrameworkValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise DecisionFrameworkValidationError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise DecisionFrameworkValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise DecisionFrameworkValidationError(f"{path} must be {expected.__name__}")


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise DecisionFrameworkValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise DecisionFrameworkValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise DecisionFrameworkValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, key
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise DecisionFrameworkValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise DecisionFrameworkValidationError(f"{path} contains duplicates")
    return ordered


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def _reject_forbidden_keys(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, child in value.items():
            normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")
            words = set(normalized.split("_"))
            if words & _FORBIDDEN_OUTPUT_KEY_TOKENS or normalized in _FORBIDDEN_OUTPUT_KEY_TOKENS:
                raise DecisionFrameworkValidationError(
                    f"{path}.{key} uses a forbidden conclusion field"
                )
            _reject_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}[{index}]")


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
        raise DecisionFrameworkValidationError(f"{path} must be an object")
    if set(payload) != fields:
        missing = sorted(fields - set(payload))
        extra = sorted(set(payload) - fields)
        raise DecisionFrameworkValidationError(
            f"invalid {path} fields; missing={missing}, extra={extra}"
        )
    frozen = _freeze_json(payload, path)
    if frozen["ruleset_version"] != ruleset:
        raise DecisionFrameworkValidationError(f"unsupported {path} ruleset version")
    snapshot_id = _text(frozen["snapshot_id"], f"{path} snapshot_id")
    source_fingerprints = _unique_texts(
        frozen["source_bundle_fingerprints"],
        f"{path} source_bundle_fingerprints",
        allow_empty=False,
    )
    if any(_SHA256.fullmatch(item) is None for item in source_fingerprints):
        raise DecisionFrameworkValidationError(f"{path} fingerprints must be SHA-256 hex")
    if set(source_fingerprints) != set(fingerprints):
        raise DecisionFrameworkValidationError(
            f"{path} fingerprints do not match canonical bundles"
        )
    identity_payload = dict(frozen)
    identity_payload.pop("snapshot_id")
    if snapshot_id != deterministic_id(identity_prefix, identity_payload):
        raise DecisionFrameworkValidationError(f"{path} snapshot identity mismatch")
    for name in array_fields:
        if not isinstance(frozen[name], tuple):
            raise DecisionFrameworkValidationError(f"{path}.{name} must be an array")
    if not isinstance(frozen["coverage"], MappingABC):
        raise DecisionFrameworkValidationError(f"{path}.coverage must be an object")
    return frozen


class _DecisionModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except DecisionFrameworkSerializationError:
            raise
        except (
            DecisionFrameworkValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise DecisionFrameworkSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionRuleDefinition(_DecisionModel):
    """One declarative decision-analysis rule without a recommendation."""

    rule_id: str
    rule_version: str
    description: str
    input_evidence_requirements: Mapping[str, Any]
    conditions: Mapping[str, Any]
    expected_behavior: str

    def __post_init__(self) -> None:
        for name in ("rule_id", "rule_version", "description", "expected_behavior"):
            _text(getattr(self, name), f"DecisionRuleDefinition.{name}")
        if self.rule_version != "0.1":
            raise DecisionFrameworkValidationError("unsupported decision rule version")
        requirements = _freeze_json(
            self.input_evidence_requirements, "rule input_evidence_requirements"
        )
        conditions = _freeze_json(self.conditions, "rule conditions")
        if not isinstance(requirements, MappingABC) or set(requirements) != {
            "minimum_support_record_count",
            "required_observation_kinds",
        }:
            raise DecisionFrameworkValidationError(
                "rule evidence requirement fields do not match V0.1"
            )
        minimum = requirements["minimum_support_record_count"]
        if type(minimum) is not int or minimum < 1:
            raise DecisionFrameworkValidationError(
                "minimum_support_record_count must be a positive integer"
            )
        kinds = _unique_texts(
            requirements["required_observation_kinds"],
            "rule required_observation_kinds",
        )
        try:
            tuple(ObservationKind(item) for item in kinds)
        except ValueError as exc:
            raise DecisionFrameworkValidationError(
                "rule contains an invalid observation kind"
            ) from exc
        if not isinstance(conditions, MappingABC) or set(conditions) != {
            "condition_type",
            "conflict_requirement",
            "required_lineage_status",
            "required_policy_condition_types",
        }:
            raise DecisionFrameworkValidationError("rule condition fields do not match V0.1")
        condition_type = conditions["condition_type"]
        if condition_type not in _CONDITION_BEHAVIORS:
            raise DecisionFrameworkValidationError("unsupported declarative decision condition")
        policy_types = _unique_texts(
            conditions["required_policy_condition_types"],
            "rule required policy conditions",
            allow_empty=False,
        )
        if conditions["conflict_requirement"] != _CONDITION_CONFLICT_REQUIREMENTS[
            condition_type
        ]:
            raise DecisionFrameworkValidationError("rule conflict requirement mismatch")
        if conditions["required_lineage_status"] != "COMPLETE_LINEAGE":
            raise DecisionFrameworkValidationError("V0.1 rules require complete lineage")
        if policy_types != tuple(sorted(_CONDITION_REQUIRED_POLICIES[condition_type])):
            raise DecisionFrameworkValidationError("rule policy requirements mismatch")
        expected_kinds = _KEYWORD_KINDS if condition_type == "KEYWORD_EVIDENCE" else ()
        if kinds != tuple(sorted(expected_kinds)):
            raise DecisionFrameworkValidationError("rule evidence kind requirements mismatch")
        if self.expected_behavior != _CONDITION_BEHAVIORS[condition_type]:
            raise DecisionFrameworkValidationError("rule expected behavior mismatch")
        object.__setattr__(self, "input_evidence_requirements", requirements)
        object.__setattr__(self, "conditions", conditions)
        if self.rule_id != deterministic_id("decision-rule", _without_id(self, "rule_id")):
            raise DecisionFrameworkValidationError("rule_id does not match rule content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionApplicabilityRecord(_DecisionModel):
    """Evidence availability and upstream process state for one rule."""

    decision_applicability_id: str
    rule_id: str
    available_evidence_ids: tuple[str, ...]
    missing_evidence_requirements: tuple[str, ...]
    conflict_status: str
    policy_status: str
    policy_evaluation_ids: tuple[str, ...]
    applicability_result: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "decision_applicability_id",
            "rule_id",
            "conflict_status",
            "policy_status",
            "applicability_result",
        ):
            _text(getattr(self, name), f"DecisionApplicabilityRecord.{name}")
        available = _unique_texts(
            self.available_evidence_ids, "applicability available_evidence_ids"
        )
        missing = _unique_texts(
            self.missing_evidence_requirements,
            "applicability missing_evidence_requirements",
        )
        policies = _unique_texts(
            self.policy_evaluation_ids,
            "applicability policy_evaluation_ids",
            allow_empty=False,
        )
        reasons = _unique_texts(
            self.reason_codes, "applicability reason_codes", allow_empty=False
        )
        if self.conflict_status not in _CONFLICT_STATUSES:
            raise DecisionFrameworkValidationError("invalid decision conflict status")
        if self.policy_status not in _POLICY_STATUSES:
            raise DecisionFrameworkValidationError("invalid decision policy status")
        if self.applicability_result not in _APPLICABILITY_RESULTS:
            raise DecisionFrameworkValidationError("invalid decision applicability result")
        if self.applicability_result == "INSUFFICIENT_EVIDENCE" and not missing:
            raise DecisionFrameworkValidationError(
                "insufficient evidence requires missing requirements"
            )
        if self.applicability_result != "INSUFFICIENT_EVIDENCE" and missing:
            raise DecisionFrameworkValidationError(
                "only insufficient evidence may report missing requirements"
            )
        if self.applicability_result == "APPLICABLE" and not available:
            raise DecisionFrameworkValidationError("applicable rule requires evidence")
        if (
            self.applicability_result == "BLOCKED_BY_POLICY"
            and self.policy_status != "POLICY_BLOCKED"
        ):
            raise DecisionFrameworkValidationError(
                "policy-blocked applicability requires blocked policy status"
            )
        if (
            self.policy_status == "POLICY_BLOCKED"
            and self.applicability_result
            not in {"BLOCKED_BY_POLICY", "INSUFFICIENT_EVIDENCE"}
        ):
            raise DecisionFrameworkValidationError(
                "blocked policy status must block a rule with sufficient evidence"
            )
        object.__setattr__(self, "available_evidence_ids", available)
        object.__setattr__(self, "missing_evidence_requirements", missing)
        object.__setattr__(self, "policy_evaluation_ids", policies)
        object.__setattr__(self, "reason_codes", reasons)
        if self.decision_applicability_id != deterministic_id(
            "decision-applicability", _without_id(self, "decision_applicability_id")
        ):
            raise DecisionFrameworkValidationError(
                "decision_applicability_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionEvaluationRecord(_DecisionModel):
    """A rule-analysis record that never contains a business conclusion."""

    decision_evaluation_id: str
    rule_id: str
    decision_applicability_id: str
    input_evidence_ids: tuple[str, ...]
    policy_evaluation_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    evaluation_result: str
    analysis_output: Mapping[str, Any]
    audit_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "decision_evaluation_id",
            "rule_id",
            "decision_applicability_id",
            "evaluation_result",
        ):
            _text(getattr(self, name), f"DecisionEvaluationRecord.{name}")
        evidence = _unique_texts(
            self.input_evidence_ids, "decision input_evidence_ids", allow_empty=False
        )
        policies = _unique_texts(
            self.policy_evaluation_ids,
            "decision policy_evaluation_ids",
            allow_empty=False,
        )
        conflicts = _unique_texts(self.conflict_ids, "decision conflict_ids")
        if self.evaluation_result not in _EVALUATION_RESULTS:
            raise DecisionFrameworkValidationError("invalid decision evaluation result")
        analysis = _freeze_json(self.analysis_output, "decision analysis_output")
        metadata = _freeze_json(self.audit_metadata, "decision audit_metadata")
        expected_analysis_fields = {
            "record_type",
            "applicability_result",
            "process_interpretation",
        }
        if not isinstance(analysis, MappingABC) or set(analysis) != expected_analysis_fields:
            raise DecisionFrameworkValidationError(
                "decision analysis output fields do not match V0.1"
            )
        if (
            analysis["record_type"] != "DECISION_RULE_ANALYSIS"
            or analysis["applicability_result"] not in _APPLICABILITY_RESULTS
            or analysis["process_interpretation"]
            != "ANALYSIS_RECORD_ONLY_NO_BUSINESS_CONCLUSION"
        ):
            raise DecisionFrameworkValidationError("invalid decision analysis output")
        expected_metadata_fields = {
            "condition_type",
            "source_conflict_resolution_snapshot_id",
            "source_evaluation_snapshot_id",
            "source_policy_snapshot_id",
        }
        if not isinstance(metadata, MappingABC) or set(metadata) != expected_metadata_fields:
            raise DecisionFrameworkValidationError(
                "decision audit metadata fields do not match V0.1"
            )
        _reject_forbidden_keys(analysis, "decision analysis_output")
        _reject_forbidden_keys(metadata, "decision audit_metadata")
        object.__setattr__(self, "input_evidence_ids", evidence)
        object.__setattr__(self, "policy_evaluation_ids", policies)
        object.__setattr__(self, "conflict_ids", conflicts)
        object.__setattr__(self, "analysis_output", analysis)
        object.__setattr__(self, "audit_metadata", metadata)
        if self.decision_evaluation_id != deterministic_id(
            "decision-evaluation", _without_id(self, "decision_evaluation_id")
        ):
            raise DecisionFrameworkValidationError(
                "decision_evaluation_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionAuditRecord(_DecisionModel):
    """Deterministic audit trail for one decision-rule evaluation."""

    decision_audit_id: str
    rule_id: str
    rule_version: str
    decision_applicability_id: str
    decision_evaluation_id: str
    condition_type: str
    condition_observations: Mapping[str, Any]
    applicability_result: str
    evaluation_result: str
    source_evaluation_snapshot_id: str
    source_conflict_resolution_snapshot_id: str
    source_policy_snapshot_id: str

    def __post_init__(self) -> None:
        for name in (
            "decision_audit_id",
            "rule_id",
            "rule_version",
            "decision_applicability_id",
            "decision_evaluation_id",
            "condition_type",
            "applicability_result",
            "evaluation_result",
            "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id",
            "source_policy_snapshot_id",
        ):
            _text(getattr(self, name), f"DecisionAuditRecord.{name}")
        if self.rule_version != "0.1" or self.condition_type not in _CONDITION_BEHAVIORS:
            raise DecisionFrameworkValidationError("invalid decision audit rule metadata")
        if self.applicability_result not in _APPLICABILITY_RESULTS:
            raise DecisionFrameworkValidationError("invalid audit applicability result")
        if self.evaluation_result not in _EVALUATION_RESULTS:
            raise DecisionFrameworkValidationError("invalid audit evaluation result")
        observations = _freeze_json(
            self.condition_observations, "decision audit condition_observations"
        )
        expected = {
            "available_evidence_count",
            "blocking_policy_count",
            "conflict_count",
            "considered_evidence_count",
            "missing_requirement_count",
        }
        if not isinstance(observations, MappingABC) or set(observations) != expected:
            raise DecisionFrameworkValidationError(
                "decision audit observation fields do not match V0.1"
            )
        for name in expected:
            _count(observations[name], f"decision audit observations.{name}")
        if observations["available_evidence_count"] > observations[
            "considered_evidence_count"
        ]:
            raise DecisionFrameworkValidationError("decision audit counts are inconsistent")
        _reject_forbidden_keys(observations, "decision audit observations")
        object.__setattr__(self, "condition_observations", observations)
        if self.decision_audit_id != deterministic_id(
            "decision-audit", _without_id(self, "decision_audit_id")
        ):
            raise DecisionFrameworkValidationError("decision_audit_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionLineageReference(_DecisionModel):
    """Decision-to-policy-to-canonical replay reference using existing identities."""

    decision_lineage_id: str
    rule_id: str
    decision_evaluation_id: str
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
            "decision_lineage_id",
            "rule_id",
            "decision_evaluation_id",
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
            _text(getattr(self, name), f"DecisionLineageReference.{name}")
        _instance(self.observation_kind, ObservationKind, "decision lineage observation_kind")
        _instance(self.evidence_type, EvidenceType, "decision lineage evidence_type")
        conflict_values = (
            self.conflict_record_id,
            self.conflict_analysis_id,
            self.conflict_candidate_id,
        )
        if any(item is None for item in conflict_values) != all(
            item is None for item in conflict_values
        ):
            raise DecisionFrameworkValidationError(
                "decision conflict lineage identities must be supplied together"
            )
        if all(item is None for item in conflict_values) and self.resolution_attempt_ids:
            raise DecisionFrameworkValidationError(
                "non-conflict decision lineage cannot reference resolution attempts"
            )
        for index, value in enumerate(item for item in conflict_values if item is not None):
            _text(value, f"decision lineage conflict identity {index}")
        attempts = _unique_texts(
            self.resolution_attempt_ids, "decision lineage resolution_attempt_ids"
        )
        if self.conflict_record_id is not None and not attempts:
            raise DecisionFrameworkValidationError(
                "conflict decision lineage requires resolution process evidence"
            )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "decision lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise DecisionFrameworkValidationError(
                "decision lineage fingerprints must be SHA-256 hex"
            )
        object.__setattr__(self, "resolution_attempt_ids", attempts)
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        if self.decision_lineage_id != deterministic_id(
            "decision-lineage", _without_id(self, "decision_lineage_id")
        ):
            raise DecisionFrameworkValidationError(
                "decision_lineage_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionDiagnostic(_DecisionModel):
    """Non-conclusive explanation of decision-rule process state."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_rule_ids: tuple[str, ...]
    related_decision_evaluation_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "decision diagnostic_id")
        _text(self.code, "decision diagnostic code")
        _instance(self.severity, Severity, "decision diagnostic severity")
        object.__setattr__(
            self,
            "related_rule_ids",
            _unique_texts(self.related_rule_ids, "diagnostic rule IDs"),
        )
        object.__setattr__(
            self,
            "related_decision_evaluation_ids",
            _unique_texts(
                self.related_decision_evaluation_ids,
                "diagnostic decision evaluation IDs",
            ),
        )
        _text(self.message, "decision diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "decision-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise DecisionFrameworkValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionCoverageSummary(_DecisionModel):
    """Descriptive decision-process counts without scores or rankings."""

    source_bundle_count: int
    rule_definition_count: int
    applicability_record_count: int
    decision_evaluation_count: int
    audit_record_count: int
    input_evidence_count: int
    policy_evaluation_reference_count: int
    conflict_count: int
    lineage_reference_count: int
    diagnostic_count: int
    applicability_result_counts: Mapping[str, int]
    evaluation_result_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count",
            "rule_definition_count",
            "applicability_record_count",
            "decision_evaluation_count",
            "audit_record_count",
            "input_evidence_count",
            "policy_evaluation_reference_count",
            "conflict_count",
            "lineage_reference_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"DecisionCoverageSummary.{name}")
        for name, allowed in (
            ("applicability_result_counts", _APPLICABILITY_RESULTS),
            ("evaluation_result_counts", _EVALUATION_RESULTS),
        ):
            value = getattr(self, name)
            if not isinstance(value, MappingABC):
                raise DecisionFrameworkValidationError(f"{name} must be an object")
            counts = dict(sorted(value.items()))
            if set(counts) - allowed or any(
                type(item) is not int or item < 0 for item in counts.values()
            ):
                raise DecisionFrameworkValidationError(f"{name} contains invalid counts")
            object.__setattr__(self, name, MappingProxyType(counts))


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionFrameworkRequest(_DecisionModel):
    """Strict canonical and three-snapshot serialized handoff."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    evidence_evaluation_snapshot: Mapping[str, Any]
    conflict_resolution_snapshot: Mapping[str, Any]
    evidence_policy_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "request canonical_bundles")
        if not bundles or any(
            not isinstance(item, CanonicalEvidenceBundle) for item in bundles
        ):
            raise DecisionFrameworkValidationError(
                "canonical_bundles must contain one or more CanonicalEvidenceBundle values"
            )
        fingerprinted: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise DecisionFrameworkValidationError(
                    f"invalid canonical bundle: {exc}"
                ) from exc
            fingerprinted.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprinted}) != len(fingerprinted):
            raise DecisionFrameworkValidationError("duplicate canonical bundle fingerprint")
        fingerprinted.sort(key=lambda item: item[0])
        ordered_bundles = tuple(item[1] for item in fingerprinted)
        fingerprints = tuple(item[0] for item in fingerprinted)
        evaluation = _validate_source_snapshot(
            self.evidence_evaluation_snapshot,
            path="evidence_evaluation_snapshot",
            fields=_EVALUATION_SNAPSHOT_FIELDS,
            ruleset=_EVALUATION_RULESET_VERSION,
            identity_prefix="evidence-evaluation-snapshot",
            fingerprints=fingerprints,
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
            fingerprints=fingerprints,
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
            fingerprints=fingerprints,
            array_fields=(
                "policy_definitions",
                "policy_applicability_records",
                "policy_evaluations",
                "audit_records",
                "diagnostics",
                "lineage_index",
            ),
        )
        if conflict["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]:
            raise DecisionFrameworkValidationError(
                "Conflict Resolution source Evaluation snapshot mismatch"
            )
        if (
            policy["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]
            or policy["source_conflict_resolution_snapshot_id"] != conflict["snapshot_id"]
        ):
            raise DecisionFrameworkValidationError(
                "Evidence Policy source snapshot continuity mismatch"
            )
        object.__setattr__(self, "canonical_bundles", ordered_bundles)
        object.__setattr__(self, "evidence_evaluation_snapshot", evaluation)
        object.__setattr__(self, "conflict_resolution_snapshot", conflict)
        object.__setattr__(self, "evidence_policy_snapshot", policy)


@dataclass(frozen=True, slots=True, kw_only=True)
class DecisionFrameworkSnapshotV0_1(_DecisionModel):
    """Auditable decision-rule analysis without a business decision."""

    snapshot_id: str
    ruleset_version: str
    source_evaluation_snapshot_id: str
    source_conflict_resolution_snapshot_id: str
    source_policy_snapshot_id: str
    source_bundle_fingerprints: tuple[str, ...]
    rule_definitions: tuple[DecisionRuleDefinition, ...]
    applicability_records: tuple[DecisionApplicabilityRecord, ...]
    decision_evaluations: tuple[DecisionEvaluationRecord, ...]
    audit_records: tuple[DecisionAuditRecord, ...]
    coverage: DecisionCoverageSummary
    diagnostics: tuple[DecisionDiagnostic, ...]
    lineage_index: tuple[DecisionLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id",
            "source_policy_snapshot_id",
        ):
            _text(getattr(self, name), f"DecisionFrameworkSnapshotV0_1.{name}")
        if self.ruleset_version != DECISION_FRAMEWORK_RULESET_VERSION:
            raise DecisionFrameworkValidationError(
                "invalid Decision Framework ruleset version"
            )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "decision snapshot source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise DecisionFrameworkValidationError(
                "decision snapshot fingerprints must be SHA-256 hex"
            )
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        sequences = (
            ("rule_definitions", DecisionRuleDefinition, lambda item: item.rule_id),
            (
                "applicability_records",
                DecisionApplicabilityRecord,
                lambda item: item.decision_applicability_id,
            ),
            (
                "decision_evaluations",
                DecisionEvaluationRecord,
                lambda item: item.decision_evaluation_id,
            ),
            ("audit_records", DecisionAuditRecord, lambda item: item.decision_audit_id),
            ("diagnostics", DecisionDiagnostic, lambda item: item.diagnostic_id),
            (
                "lineage_index",
                DecisionLineageReference,
                lambda item: item.decision_lineage_id,
            ),
        )
        for name, expected, key in sequences:
            object.__setattr__(
                self,
                name,
                _typed_unique(getattr(self, name), expected, f"snapshot {name}", key),
            )
        _instance(self.coverage, DecisionCoverageSummary, "decision snapshot coverage")
        rules = {item.rule_id: item for item in self.rule_definitions}
        applicability = {item.rule_id: item for item in self.applicability_records}
        evaluations = {item.rule_id: item for item in self.decision_evaluations}
        audits = {item.rule_id: item for item in self.audit_records}
        if not rules or any(
            len(values) != len(rules)
            for values in (applicability, evaluations, audits)
        ) or not (
            set(rules) == set(applicability) == set(evaluations) == set(audits)
        ):
            raise DecisionFrameworkValidationError(
                "every rule requires exactly one applicability, evaluation, and audit record"
            )
        evaluation_ids = {
            item.decision_evaluation_id: item for item in self.decision_evaluations
        }
        for rule_id, evaluation in evaluations.items():
            rule = rules[rule_id]
            applies = applicability[rule_id]
            audit = audits[rule_id]
            if (
                evaluation.decision_applicability_id
                != applies.decision_applicability_id
                or evaluation.policy_evaluation_ids != applies.policy_evaluation_ids
                or evaluation.evaluation_result
                != _RESULT_BY_APPLICABILITY[applies.applicability_result]
                or evaluation.analysis_output["applicability_result"]
                != applies.applicability_result
            ):
                raise DecisionFrameworkValidationError(
                    "decision evaluation does not match applicability"
                )
            if not set(applies.available_evidence_ids) <= set(
                evaluation.input_evidence_ids
            ):
                raise DecisionFrameworkValidationError(
                    "available evidence is absent from decision inputs"
                )
            if (
                audit.rule_version != rule.rule_version
                or audit.decision_applicability_id != applies.decision_applicability_id
                or audit.decision_evaluation_id != evaluation.decision_evaluation_id
                or audit.condition_type != rule.conditions["condition_type"]
                or audit.applicability_result != applies.applicability_result
                or audit.evaluation_result != evaluation.evaluation_result
                or audit.source_evaluation_snapshot_id
                != self.source_evaluation_snapshot_id
                or audit.source_conflict_resolution_snapshot_id
                != self.source_conflict_resolution_snapshot_id
                or audit.source_policy_snapshot_id != self.source_policy_snapshot_id
            ):
                raise DecisionFrameworkValidationError("decision audit trail mismatch")
            observed = audit.condition_observations
            if (
                observed["considered_evidence_count"]
                != len(evaluation.input_evidence_ids)
                or observed["available_evidence_count"]
                != len(applies.available_evidence_ids)
                or observed["missing_requirement_count"]
                != len(applies.missing_evidence_requirements)
                or observed["conflict_count"] != len(evaluation.conflict_ids)
                or observed["blocking_policy_count"]
                != (1 if applies.policy_status == "POLICY_BLOCKED" else 0)
            ):
                raise DecisionFrameworkValidationError(
                    "decision audit counts do not match evaluation evidence"
                )
        lineages_by_evaluation: dict[str, list[DecisionLineageReference]] = {}
        for lineage in self.lineage_index:
            evaluation = evaluation_ids.get(lineage.decision_evaluation_id)
            if evaluation is None or evaluation.rule_id != lineage.rule_id:
                raise DecisionFrameworkValidationError(
                    "decision lineage references an unknown evaluation"
                )
            lineages_by_evaluation.setdefault(
                lineage.decision_evaluation_id, []
            ).append(lineage)
        for evaluation in self.decision_evaluations:
            lineages = lineages_by_evaluation.get(evaluation.decision_evaluation_id, [])
            if {item.policy_evaluation_id for item in lineages} != set(
                evaluation.policy_evaluation_ids
            ):
                raise DecisionFrameworkValidationError(
                    "decision lineage does not cover policy references"
                )
            if {item.support_record_id for item in lineages} != set(
                evaluation.input_evidence_ids
            ):
                raise DecisionFrameworkValidationError(
                    "decision lineage does not cover input evidence"
                )
            if {
                item.conflict_record_id
                for item in lineages
                if item.conflict_record_id is not None
            } != set(evaluation.conflict_ids):
                raise DecisionFrameworkValidationError(
                    "decision lineage does not cover conflict references"
                )
        rule_ids = set(rules)
        for diagnostic in self.diagnostics:
            if not set(diagnostic.related_rule_ids) <= rule_ids or not set(
                diagnostic.related_decision_evaluation_ids
            ) <= set(evaluation_ids):
                raise DecisionFrameworkValidationError(
                    "decision diagnostic contains an orphan reference"
                )
        expected_coverage = coverage_from_records(
            bundle_count=len(fingerprints),
            definitions=self.rule_definitions,
            applicability=self.applicability_records,
            evaluations=self.decision_evaluations,
            audits=self.audit_records,
            diagnostics=self.diagnostics,
            lineage=self.lineage_index,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise DecisionFrameworkValidationError("decision coverage mismatch")
        expected_id = deterministic_id(
            "decision-framework-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise DecisionFrameworkSerializationError(
                "snapshot_id does not match snapshot content"
            )

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        """Replay decision lineage through canonical transformation evidence."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence):
            raise DecisionFrameworkValidationError("bundles must be a non-empty sequence")
        if not bundles:
            raise DecisionFrameworkValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[
            tuple[str, str], tuple[CanonicalObservation, set[str]]
        ] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise DecisionFrameworkValidationError(
                    "against-bundles input contains a wrong type"
                )
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise DecisionFrameworkValidationError(
                    f"invalid canonical bundle: {exc}"
                ) from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise DecisionFrameworkValidationError(
                    "duplicate canonical bundle fingerprint"
                )
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise DecisionFrameworkValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                content = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != content:
                    raise DecisionFrameworkValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = content
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                current = observations.get(key)
                if current is not None and canonical_json(current[0]) != canonical_json(
                    observation
                ):
                    raise DecisionFrameworkValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current is None:
                    observations[key] = (observation, {fingerprint})
                else:
                    current[1].add(fingerprint)
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise DecisionFrameworkValidationError(
                "decision snapshot fingerprints do not match supplied bundles"
            )
        grouped_runs: dict[tuple[str, str, str], set[str]] = {}
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            entry = observations.get(key)
            if entry is None:
                raise DecisionFrameworkValidationError(
                    f"orphan decision observation: {reference.observation_id}"
                )
            observation, source_fingerprints = entry
            transformation = observation.provenance.transformation
            run = runs.get(reference.transformation_run_id)
            if run is None:
                raise DecisionFrameworkValidationError(
                    f"orphan decision transformation: {reference.transformation_run_id}"
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
                raise DecisionFrameworkValidationError(
                    f"decision lineage content mismatch: {reference.observation_id}"
                )
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or reference.raw_evidence_id not in raw_ids
                or reference.raw_evidence_id not in run.input_raw_evidence_references
                or reference.observation_id not in run.output_observation_ids
            ):
                raise DecisionFrameworkValidationError(
                    f"broken decision transformation lineage: {reference.observation_id}"
                )
            group = (
                reference.decision_evaluation_id,
                reference.policy_evaluation_id,
                reference.observation_id,
            )
            grouped_runs.setdefault(group, set()).add(reference.transformation_run_id)
        for (_, _, observation_id), actual_runs in grouped_runs.items():
            expected_runs = {key[1] for key in observations if key[0] == observation_id}
            if actual_runs != expected_runs:
                raise DecisionFrameworkValidationError(
                    f"decision lineage omits an observation emission: {observation_id}"
                )
        return self


def coverage_from_records(
    *,
    bundle_count: int,
    definitions: Sequence[DecisionRuleDefinition],
    applicability: Sequence[DecisionApplicabilityRecord],
    evaluations: Sequence[DecisionEvaluationRecord],
    audits: Sequence[DecisionAuditRecord],
    diagnostics: Sequence[DecisionDiagnostic],
    lineage: Sequence[DecisionLineageReference],
) -> DecisionCoverageSummary:
    return DecisionCoverageSummary(
        source_bundle_count=bundle_count,
        rule_definition_count=len(definitions),
        applicability_record_count=len(applicability),
        decision_evaluation_count=len(evaluations),
        audit_record_count=len(audits),
        input_evidence_count=len({
            evidence_id
            for evaluation in evaluations
            for evidence_id in evaluation.input_evidence_ids
        }),
        policy_evaluation_reference_count=len({
            policy_id
            for evaluation in evaluations
            for policy_id in evaluation.policy_evaluation_ids
        }),
        conflict_count=len({
            conflict_id
            for evaluation in evaluations
            for conflict_id in evaluation.conflict_ids
        }),
        lineage_reference_count=len(lineage),
        diagnostic_count=len(diagnostics),
        applicability_result_counts=dict(sorted(Counter(
            item.applicability_result for item in applicability
        ).items())),
        evaluation_result_counts=dict(sorted(Counter(
            item.evaluation_result for item in evaluations
        ).items())),
    )


__all__ = (
    "DECISION_FRAMEWORK_RULESET_VERSION",
    "DecisionFrameworkRequest",
    "DecisionFrameworkSnapshotV0_1",
    "DecisionRuleDefinition",
    "DecisionApplicabilityRecord",
    "DecisionEvaluationRecord",
    "DecisionAuditRecord",
    "DecisionCoverageSummary",
    "DecisionLineageReference",
    "DecisionDiagnostic",
)
