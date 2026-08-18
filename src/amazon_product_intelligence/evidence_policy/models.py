"""Immutable public data models for Evidence Policy V0.1."""

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

from .errors import EvidencePolicySerializationError, EvidencePolicyValidationError


EVIDENCE_POLICY_RULESET_VERSION = "evidence-policy-v0.1"
_EVALUATION_RULESET_VERSION = "evidence-evaluation-v0.1"
_CONFLICT_RULESET_VERSION = "conflict-resolution-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_APPLICABILITY_STATUSES = {"APPLICABLE", "NOT_APPLICABLE"}
_EVALUATION_RESULTS = {
    "NOT_APPLICABLE",
    "APPLICABLE_NO_ACTION",
    "ACTION_ALLOWED",
    "ACTION_BLOCKED",
}
_CONDITION_BEHAVIORS = {
    "MINIMUM_PROVIDER_COUNT": "RECORD_SUPPORT_CONTEXT_WITHOUT_ACTION",
    "LINEAGE_COMPLETENESS_REQUIRED": "ALLOW_PROCESS_ONLY_WITH_COMPLETE_LINEAGE",
    "CONFLICT_PRESENT": "BLOCK_AUTOMATIC_INTERPRETATION_AND_REQUIRE_REVIEW",
}
_FORBIDDEN_OUTPUT_KEY_TOKENS = {
    "WINNER",
    "SCORE",
    "CONFIDENCE",
    "TRUST",
    "WEIGHT",
    "RECOMMENDATION",
    "RANKING",
    "DECISION",
    "TRUTH",
    "PREFERRED",
    "PRIORITY",
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


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise EvidencePolicyValidationError(
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
        raise EvidencePolicyValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise EvidencePolicyValidationError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise EvidencePolicyValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise EvidencePolicyValidationError(f"{path} must be {expected.__name__}")


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise EvidencePolicyValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise EvidencePolicyValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise EvidencePolicyValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, key
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise EvidencePolicyValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise EvidencePolicyValidationError(f"{path} contains duplicates")
    return ordered


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def _reject_forbidden_keys(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, child in value.items():
            normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")
            if set(normalized.split("_")) & _FORBIDDEN_OUTPUT_KEY_TOKENS:
                raise EvidencePolicyValidationError(
                    f"{path}.{key} uses a forbidden conclusion field"
                )
            _reject_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, child in enumerate(value):
            _reject_forbidden_keys(child, f"{path}[{index}]")


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    """Return the established order-insensitive canonical bundle fingerprint."""

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
        raise EvidencePolicyValidationError(f"{path} must be an object")
    if set(payload) != fields:
        missing = sorted(fields - set(payload))
        extra = sorted(set(payload) - fields)
        raise EvidencePolicyValidationError(
            f"invalid {path} fields; missing={missing}, extra={extra}"
        )
    frozen = _freeze_json(payload, path)
    if frozen["ruleset_version"] != ruleset:
        raise EvidencePolicyValidationError(f"unsupported {path} ruleset version")
    snapshot_id = _text(frozen["snapshot_id"], f"{path} snapshot_id")
    source_fingerprints = _unique_texts(
        frozen["source_bundle_fingerprints"],
        f"{path} source_bundle_fingerprints",
        allow_empty=False,
    )
    if any(_SHA256.fullmatch(item) is None for item in source_fingerprints):
        raise EvidencePolicyValidationError(f"{path} fingerprints must be SHA-256 hex")
    if set(source_fingerprints) != set(fingerprints):
        raise EvidencePolicyValidationError(
            f"{path} fingerprints do not match canonical bundles"
        )
    identity_payload = dict(frozen)
    identity_payload.pop("snapshot_id")
    if snapshot_id != deterministic_id(identity_prefix, identity_payload):
        raise EvidencePolicyValidationError(f"{path} snapshot identity mismatch")
    for name in array_fields:
        if not isinstance(frozen[name], tuple):
            raise EvidencePolicyValidationError(f"{path}.{name} must be an array")
    if not isinstance(frozen["coverage"], MappingABC):
        raise EvidencePolicyValidationError(f"{path}.coverage must be an object")
    return frozen


class _PolicyModel(JsonContract):
    """Strictly decode public models and translate contract errors."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except EvidencePolicySerializationError:
            raise
        except (
            EvidencePolicyValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise EvidencePolicySerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyDefinition(_PolicyModel):
    """One declarative, versioned evidence-interpretation policy."""

    policy_id: str
    policy_version: str
    description: str
    applicable_evidence_types: tuple[EvidenceType, ...]
    conditions: Mapping[str, Any]
    expected_behavior: str

    def __post_init__(self) -> None:
        for name in ("policy_id", "policy_version", "description", "expected_behavior"):
            _text(getattr(self, name), f"PolicyDefinition.{name}")
        evidence_types = _tuple(
            self.applicable_evidence_types, "policy applicable_evidence_types"
        )
        if not evidence_types or any(
            not isinstance(item, EvidenceType) for item in evidence_types
        ):
            raise EvidencePolicyValidationError(
                "applicable_evidence_types must contain EvidenceType values"
            )
        evidence_types = tuple(sorted(set(evidence_types), key=lambda item: item.value))
        conditions = _freeze_json(self.conditions, "policy conditions")
        if not isinstance(conditions, MappingABC):
            raise EvidencePolicyValidationError("policy conditions must be an object")
        condition_type = conditions.get("condition_type")
        if condition_type not in _CONDITION_BEHAVIORS:
            raise EvidencePolicyValidationError("unsupported declarative policy condition")
        expected_fields = {
            "MINIMUM_PROVIDER_COUNT": {"condition_type", "minimum_provider_count"},
            "LINEAGE_COMPLETENESS_REQUIRED": {
                "condition_type",
                "required_status",
            },
            "CONFLICT_PRESENT": {"condition_type"},
        }[condition_type]
        if set(conditions) != expected_fields:
            raise EvidencePolicyValidationError("policy condition fields do not match V0.1")
        if condition_type == "MINIMUM_PROVIDER_COUNT":
            minimum = conditions["minimum_provider_count"]
            if type(minimum) is not int or minimum < 2:
                raise EvidencePolicyValidationError(
                    "minimum_provider_count must be an integer of at least two"
                )
        if (
            condition_type == "LINEAGE_COMPLETENESS_REQUIRED"
            and conditions["required_status"] != "COMPLETE_LINEAGE"
        ):
            raise EvidencePolicyValidationError(
                "V0.1 lineage policy requires COMPLETE_LINEAGE"
            )
        if self.expected_behavior != _CONDITION_BEHAVIORS[condition_type]:
            raise EvidencePolicyValidationError(
                "expected_behavior does not match the declarative condition"
            )
        object.__setattr__(self, "applicable_evidence_types", evidence_types)
        object.__setattr__(self, "conditions", conditions)
        if self.policy_id != deterministic_id(
            "evidence-policy", _without_id(self, "policy_id")
        ):
            raise EvidencePolicyValidationError("policy_id does not match policy content")


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyApplicabilityRecord(_PolicyModel):
    """Evidence showing whether one declarative policy applies."""

    policy_applicability_id: str
    policy_id: str
    applicability_status: str
    matched_evidence_ids: tuple[str, ...]
    matched_conflict_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("policy_applicability_id", "policy_id", "applicability_status"):
            _text(getattr(self, name), f"PolicyApplicabilityRecord.{name}")
        if self.applicability_status not in _APPLICABILITY_STATUSES:
            raise EvidencePolicyValidationError("invalid policy applicability status")
        evidence_ids = _unique_texts(
            self.matched_evidence_ids, "applicability matched_evidence_ids"
        )
        conflict_ids = _unique_texts(
            self.matched_conflict_ids, "applicability matched_conflict_ids"
        )
        reason_codes = _unique_texts(
            self.reason_codes, "applicability reason_codes", allow_empty=False
        )
        if self.applicability_status == "APPLICABLE" and not (
            evidence_ids or conflict_ids
        ):
            raise EvidencePolicyValidationError(
                "an applicable policy requires matched evidence"
            )
        if self.applicability_status == "NOT_APPLICABLE" and (
            evidence_ids or conflict_ids
        ):
            raise EvidencePolicyValidationError(
                "a non-applicable policy cannot claim matched evidence"
            )
        object.__setattr__(self, "matched_evidence_ids", evidence_ids)
        object.__setattr__(self, "matched_conflict_ids", conflict_ids)
        object.__setattr__(self, "reason_codes", reason_codes)
        if self.policy_applicability_id != deterministic_id(
            "policy-applicability",
            _without_id(self, "policy_applicability_id"),
        ):
            raise EvidencePolicyValidationError(
                "policy_applicability_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyEvaluationRecord(_PolicyModel):
    """Process-permission outcome without a truth or business decision."""

    policy_evaluation_id: str
    policy_id: str
    policy_applicability_id: str
    input_evidence_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    evaluation_result: str
    expected_behavior: str
    audit_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "policy_evaluation_id",
            "policy_id",
            "policy_applicability_id",
            "evaluation_result",
            "expected_behavior",
        ):
            _text(getattr(self, name), f"PolicyEvaluationRecord.{name}")
        if self.evaluation_result not in _EVALUATION_RESULTS:
            raise EvidencePolicyValidationError("invalid policy evaluation result")
        evidence_ids = _unique_texts(
            self.input_evidence_ids, "evaluation input_evidence_ids"
        )
        conflict_ids = _unique_texts(self.conflict_ids, "evaluation conflict_ids")
        metadata = _freeze_json(self.audit_metadata, "evaluation audit_metadata")
        if not isinstance(metadata, MappingABC) or not metadata:
            raise EvidencePolicyValidationError(
                "evaluation audit_metadata must be a non-empty object"
            )
        _reject_forbidden_keys(metadata, "evaluation audit_metadata")
        object.__setattr__(self, "input_evidence_ids", evidence_ids)
        object.__setattr__(self, "conflict_ids", conflict_ids)
        object.__setattr__(self, "audit_metadata", metadata)
        if self.policy_evaluation_id != deterministic_id(
            "policy-evaluation", _without_id(self, "policy_evaluation_id")
        ):
            raise EvidencePolicyValidationError(
                "policy_evaluation_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyAuditRecord(_PolicyModel):
    """Deterministic audit trail for one policy evaluation."""

    policy_audit_id: str
    policy_id: str
    policy_version: str
    policy_applicability_id: str
    policy_evaluation_id: str
    condition_type: str
    condition_observations: Mapping[str, Any]
    evaluation_result: str
    source_evaluation_snapshot_id: str
    source_conflict_resolution_snapshot_id: str

    def __post_init__(self) -> None:
        for name in (
            "policy_audit_id",
            "policy_id",
            "policy_version",
            "policy_applicability_id",
            "policy_evaluation_id",
            "condition_type",
            "evaluation_result",
            "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id",
        ):
            _text(getattr(self, name), f"PolicyAuditRecord.{name}")
        if self.condition_type not in _CONDITION_BEHAVIORS:
            raise EvidencePolicyValidationError("invalid audit condition_type")
        if self.evaluation_result not in _EVALUATION_RESULTS:
            raise EvidencePolicyValidationError("invalid audit evaluation_result")
        observations = _freeze_json(
            self.condition_observations, "audit condition_observations"
        )
        if not isinstance(observations, MappingABC) or not observations:
            raise EvidencePolicyValidationError(
                "audit condition_observations must be a non-empty object"
            )
        _reject_forbidden_keys(observations, "audit condition_observations")
        expected_observation_fields = {
            "considered_evidence_count",
            "matched_evidence_count",
            "related_conflict_count",
            "incomplete_lineage_count",
        }
        if set(observations) != expected_observation_fields:
            raise EvidencePolicyValidationError(
                "audit condition observation fields do not match V0.1"
            )
        for name in expected_observation_fields:
            _count(observations[name], f"audit condition_observations.{name}")
        if observations["matched_evidence_count"] > observations[
            "considered_evidence_count"
        ] or observations["incomplete_lineage_count"] > observations[
            "considered_evidence_count"
        ]:
            raise EvidencePolicyValidationError(
                "audit condition observation counts are inconsistent"
            )
        object.__setattr__(self, "condition_observations", observations)
        if self.policy_audit_id != deterministic_id(
            "policy-audit", _without_id(self, "policy_audit_id")
        ):
            raise EvidencePolicyValidationError("policy_audit_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyLineageReference(_PolicyModel):
    """Policy-to-canonical replay reference using existing source identities."""

    policy_lineage_id: str
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
            "policy_lineage_id",
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
            _text(getattr(self, name), f"PolicyLineageReference.{name}")
        _instance(self.observation_kind, ObservationKind, "lineage observation_kind")
        _instance(self.evidence_type, EvidenceType, "lineage evidence_type")
        conflict_values = (
            self.conflict_record_id,
            self.conflict_analysis_id,
            self.conflict_candidate_id,
        )
        if any(item is None for item in conflict_values) != all(
            item is None for item in conflict_values
        ):
            raise EvidencePolicyValidationError(
                "conflict lineage identities must be supplied together"
            )
        if all(item is None for item in conflict_values):
            if self.resolution_attempt_ids:
                raise EvidencePolicyValidationError(
                    "non-conflict lineage cannot reference resolution attempts"
                )
        else:
            for index, value in enumerate(conflict_values):
                _text(value, f"lineage conflict identity {index}")
        attempts = _unique_texts(
            self.resolution_attempt_ids, "lineage resolution_attempt_ids"
        )
        if self.conflict_record_id is not None and not attempts:
            raise EvidencePolicyValidationError(
                "conflict lineage requires resolution process evidence"
            )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise EvidencePolicyValidationError("lineage fingerprints must be SHA-256 hex")
        object.__setattr__(self, "resolution_attempt_ids", attempts)
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        if self.policy_lineage_id != deterministic_id(
            "policy-lineage", _without_id(self, "policy_lineage_id")
        ):
            raise EvidencePolicyValidationError("policy_lineage_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyDiagnostic(_PolicyModel):
    """Non-conclusive explanation of policy process state."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_policy_ids: tuple[str, ...]
    related_policy_evaluation_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "policy diagnostic_id")
        _text(self.code, "policy diagnostic code")
        _instance(self.severity, Severity, "policy diagnostic severity")
        object.__setattr__(
            self,
            "related_policy_ids",
            _unique_texts(self.related_policy_ids, "diagnostic policy IDs"),
        )
        object.__setattr__(
            self,
            "related_policy_evaluation_ids",
            _unique_texts(
                self.related_policy_evaluation_ids,
                "diagnostic evaluation IDs",
            ),
        )
        _text(self.message, "policy diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "policy-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise EvidencePolicyValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class PolicyCoverageSummary(_PolicyModel):
    """Descriptive policy process counts without scores or recommendations."""

    source_bundle_count: int
    policy_definition_count: int
    applicability_record_count: int
    policy_evaluation_count: int
    audit_record_count: int
    input_evidence_count: int
    conflict_count: int
    lineage_reference_count: int
    diagnostic_count: int
    evaluation_result_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count",
            "policy_definition_count",
            "applicability_record_count",
            "policy_evaluation_count",
            "audit_record_count",
            "input_evidence_count",
            "conflict_count",
            "lineage_reference_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"PolicyCoverageSummary.{name}")
        if not isinstance(self.evaluation_result_counts, MappingABC):
            raise EvidencePolicyValidationError(
                "evaluation_result_counts must be an object"
            )
        counts = dict(sorted(self.evaluation_result_counts.items()))
        if set(counts) - _EVALUATION_RESULTS:
            raise EvidencePolicyValidationError(
                "evaluation_result_counts contains an invalid result"
            )
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise EvidencePolicyValidationError(
                "evaluation_result_counts values must be counts"
            )
        object.__setattr__(self, "evaluation_result_counts", MappingProxyType(counts))


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidencePolicyRequest(_PolicyModel):
    """Strict canonical, Evaluation, and Conflict Resolution handoff."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    evidence_evaluation_snapshot: Mapping[str, Any]
    conflict_resolution_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "request canonical_bundles")
        if not bundles or any(
            not isinstance(item, CanonicalEvidenceBundle) for item in bundles
        ):
            raise EvidencePolicyValidationError(
                "canonical_bundles must contain one or more CanonicalEvidenceBundle values"
            )
        fingerprinted: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise EvidencePolicyValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprinted.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprinted}) != len(fingerprinted):
            raise EvidencePolicyValidationError("duplicate canonical bundle fingerprint")
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
        if conflict["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]:
            raise EvidencePolicyValidationError(
                "Conflict Resolution source Evaluation snapshot mismatch"
            )
        object.__setattr__(self, "canonical_bundles", ordered_bundles)
        object.__setattr__(self, "evidence_evaluation_snapshot", evaluation)
        object.__setattr__(self, "conflict_resolution_snapshot", conflict)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidencePolicySnapshotV0_1(_PolicyModel):
    """Auditable declarative policy interpretation without a decision."""

    snapshot_id: str
    ruleset_version: str
    source_evaluation_snapshot_id: str
    source_conflict_resolution_snapshot_id: str
    source_bundle_fingerprints: tuple[str, ...]
    policy_definitions: tuple[PolicyDefinition, ...]
    policy_applicability_records: tuple[PolicyApplicabilityRecord, ...]
    policy_evaluations: tuple[PolicyEvaluationRecord, ...]
    audit_records: tuple[PolicyAuditRecord, ...]
    coverage: PolicyCoverageSummary
    diagnostics: tuple[PolicyDiagnostic, ...]
    lineage_index: tuple[PolicyLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id",
        ):
            _text(getattr(self, name), f"EvidencePolicySnapshotV0_1.{name}")
        if self.ruleset_version != EVIDENCE_POLICY_RULESET_VERSION:
            raise EvidencePolicyValidationError("invalid Evidence Policy ruleset version")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "policy snapshot source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise EvidencePolicyValidationError("snapshot fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        sequences = (
            ("policy_definitions", PolicyDefinition, lambda item: item.policy_id),
            (
                "policy_applicability_records",
                PolicyApplicabilityRecord,
                lambda item: item.policy_applicability_id,
            ),
            (
                "policy_evaluations",
                PolicyEvaluationRecord,
                lambda item: item.policy_evaluation_id,
            ),
            ("audit_records", PolicyAuditRecord, lambda item: item.policy_audit_id),
            ("diagnostics", PolicyDiagnostic, lambda item: item.diagnostic_id),
            ("lineage_index", PolicyLineageReference, lambda item: item.policy_lineage_id),
        )
        for name, expected, key in sequences:
            object.__setattr__(
                self,
                name,
                _typed_unique(getattr(self, name), expected, f"snapshot {name}", key),
            )
        _instance(self.coverage, PolicyCoverageSummary, "policy snapshot coverage")
        policies = {item.policy_id: item for item in self.policy_definitions}
        applicability = {
            item.policy_id: item for item in self.policy_applicability_records
        }
        evaluations = {item.policy_id: item for item in self.policy_evaluations}
        audits = {item.policy_id: item for item in self.audit_records}
        if not policies or any(
            len(values) != len(policies)
            for values in (applicability, evaluations, audits)
        ) or not (
            set(policies) == set(applicability) == set(evaluations) == set(audits)
        ):
            raise EvidencePolicyValidationError(
                "every policy requires exactly one applicability, evaluation, and audit record"
            )
        evaluation_ids = {
            item.policy_evaluation_id: item for item in self.policy_evaluations
        }
        for policy_id, evaluation in evaluations.items():
            policy = policies[policy_id]
            applicable = applicability[policy_id]
            audit = audits[policy_id]
            if evaluation.policy_applicability_id != applicable.policy_applicability_id:
                raise EvidencePolicyValidationError(
                    "evaluation references the wrong applicability record"
                )
            if evaluation.expected_behavior != policy.expected_behavior:
                raise EvidencePolicyValidationError(
                    "evaluation expected behavior does not match policy"
                )
            if not set(applicable.matched_evidence_ids) <= set(
                evaluation.input_evidence_ids
            ) or not set(applicable.matched_conflict_ids) <= set(
                evaluation.conflict_ids
            ):
                raise EvidencePolicyValidationError(
                    "applicability matches are absent from evaluation inputs"
                )
            if applicable.applicability_status == "NOT_APPLICABLE":
                if evaluation.evaluation_result != "NOT_APPLICABLE":
                    raise EvidencePolicyValidationError(
                        "non-applicable policy must evaluate NOT_APPLICABLE"
                    )
            elif evaluation.evaluation_result == "NOT_APPLICABLE":
                raise EvidencePolicyValidationError(
                    "applicable policy cannot evaluate NOT_APPLICABLE"
                )
            if (
                audit.policy_version != policy.policy_version
                or audit.policy_applicability_id != applicable.policy_applicability_id
                or audit.policy_evaluation_id != evaluation.policy_evaluation_id
                or audit.condition_type != policy.conditions["condition_type"]
                or audit.evaluation_result != evaluation.evaluation_result
                or audit.source_evaluation_snapshot_id
                != self.source_evaluation_snapshot_id
                or audit.source_conflict_resolution_snapshot_id
                != self.source_conflict_resolution_snapshot_id
            ):
                raise EvidencePolicyValidationError("policy audit trail mismatch")
            observed = audit.condition_observations
            if (
                observed["considered_evidence_count"]
                != len(evaluation.input_evidence_ids)
                or observed["matched_evidence_count"]
                != len(applicable.matched_evidence_ids)
                or observed["related_conflict_count"] != len(evaluation.conflict_ids)
            ):
                raise EvidencePolicyValidationError(
                    "policy audit counts do not match evaluation evidence"
                )
            condition_type = policy.conditions["condition_type"]
            if applicable.applicability_status == "NOT_APPLICABLE":
                expected_result = "NOT_APPLICABLE"
            elif condition_type == "MINIMUM_PROVIDER_COUNT":
                expected_result = "APPLICABLE_NO_ACTION"
            elif condition_type == "CONFLICT_PRESENT":
                expected_result = "ACTION_BLOCKED"
            else:
                expected_result = (
                    "ACTION_ALLOWED"
                    if observed["incomplete_lineage_count"] == 0
                    else "ACTION_BLOCKED"
                )
            if evaluation.evaluation_result != expected_result:
                raise EvidencePolicyValidationError(
                    "policy evaluation result does not follow its declarative condition"
                )
        lineages_by_evaluation: dict[str, list[PolicyLineageReference]] = {}
        for lineage in self.lineage_index:
            evaluation = evaluation_ids.get(lineage.policy_evaluation_id)
            if evaluation is None or evaluation.policy_id != lineage.policy_id:
                raise EvidencePolicyValidationError(
                    "lineage references an unknown policy evaluation"
                )
            lineages_by_evaluation.setdefault(lineage.policy_evaluation_id, []).append(
                lineage
            )
        for evaluation in self.policy_evaluations:
            lineages = lineages_by_evaluation.get(evaluation.policy_evaluation_id, [])
            if {item.support_record_id for item in lineages} != set(
                evaluation.input_evidence_ids
            ):
                raise EvidencePolicyValidationError(
                    "policy lineage does not cover evaluation evidence inputs"
                )
            if {
                item.conflict_record_id
                for item in lineages
                if item.conflict_record_id is not None
            } != set(evaluation.conflict_ids):
                raise EvidencePolicyValidationError(
                    "policy lineage does not cover evaluation conflicts"
                )
        policy_ids = set(policies)
        for diagnostic in self.diagnostics:
            if not set(diagnostic.related_policy_ids) <= policy_ids:
                raise EvidencePolicyValidationError(
                    "diagnostic references an unknown policy"
                )
            if not set(diagnostic.related_policy_evaluation_ids) <= set(
                evaluation_ids
            ):
                raise EvidencePolicyValidationError(
                    "diagnostic references an unknown policy evaluation"
                )
        expected_coverage = coverage_from_records(
            bundle_count=len(fingerprints),
            definitions=self.policy_definitions,
            applicability=self.policy_applicability_records,
            evaluations=self.policy_evaluations,
            audits=self.audit_records,
            diagnostics=self.diagnostics,
            lineage=self.lineage_index,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise EvidencePolicyValidationError("policy coverage mismatch")
        expected_id = deterministic_id(
            "evidence-policy-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise EvidencePolicySerializationError(
                "snapshot_id does not match snapshot content"
            )

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        """Replay every policy lineage reference through canonical bundles."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence):
            raise EvidencePolicyValidationError("bundles must be a non-empty sequence")
        if not bundles:
            raise EvidencePolicyValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[
            tuple[str, str], tuple[CanonicalObservation, set[str]]
        ] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise EvidencePolicyValidationError(
                    "against-bundles input contains a wrong type"
                )
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise EvidencePolicyValidationError(
                    f"invalid canonical bundle: {exc}"
                ) from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise EvidencePolicyValidationError("duplicate canonical bundle fingerprint")
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise EvidencePolicyValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                content = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != content:
                    raise EvidencePolicyValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = content
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                current = observations.get(key)
                if current is not None and canonical_json(current[0]) != canonical_json(
                    observation
                ):
                    raise EvidencePolicyValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current is None:
                    observations[key] = (observation, {fingerprint})
                else:
                    current[1].add(fingerprint)
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise EvidencePolicyValidationError(
                "snapshot source bundle fingerprints do not match supplied bundles"
            )
        grouped_runs: dict[tuple[str, str, str], set[str]] = {}
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            entry = observations.get(key)
            if entry is None:
                raise EvidencePolicyValidationError(
                    f"orphan policy observation: {reference.observation_id}"
                )
            observation, source_fingerprints = entry
            transformation = observation.provenance.transformation
            run = runs.get(reference.transformation_run_id)
            if run is None:
                raise EvidencePolicyValidationError(
                    f"orphan policy transformation: {reference.transformation_run_id}"
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
                raise EvidencePolicyValidationError(
                    f"policy lineage content mismatch: {reference.observation_id}"
                )
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or reference.raw_evidence_id not in raw_ids
                or reference.raw_evidence_id not in run.input_raw_evidence_references
                or reference.observation_id not in run.output_observation_ids
            ):
                raise EvidencePolicyValidationError(
                    f"broken policy transformation lineage: {reference.observation_id}"
                )
            group = (
                reference.policy_evaluation_id,
                reference.support_record_id,
                reference.observation_id,
            )
            grouped_runs.setdefault(group, set()).add(reference.transformation_run_id)
        for (_, _, observation_id), actual_runs in grouped_runs.items():
            expected_runs = {key[1] for key in observations if key[0] == observation_id}
            if actual_runs != expected_runs:
                raise EvidencePolicyValidationError(
                    f"policy lineage omits an observation emission: {observation_id}"
                )
        return self


def coverage_from_records(
    *,
    bundle_count: int,
    definitions: Sequence[PolicyDefinition],
    applicability: Sequence[PolicyApplicabilityRecord],
    evaluations: Sequence[PolicyEvaluationRecord],
    audits: Sequence[PolicyAuditRecord],
    diagnostics: Sequence[PolicyDiagnostic],
    lineage: Sequence[PolicyLineageReference],
) -> PolicyCoverageSummary:
    return PolicyCoverageSummary(
        source_bundle_count=bundle_count,
        policy_definition_count=len(definitions),
        applicability_record_count=len(applicability),
        policy_evaluation_count=len(evaluations),
        audit_record_count=len(audits),
        input_evidence_count=len({
            evidence_id
            for evaluation in evaluations
            for evidence_id in evaluation.input_evidence_ids
        }),
        conflict_count=len({
            conflict_id
            for evaluation in evaluations
            for conflict_id in evaluation.conflict_ids
        }),
        lineage_reference_count=len(lineage),
        diagnostic_count=len(diagnostics),
        evaluation_result_counts=dict(sorted(Counter(
            item.evaluation_result for item in evaluations
        ).items())),
    )


__all__ = (
    "EVIDENCE_POLICY_RULESET_VERSION",
    "EvidencePolicyRequest",
    "EvidencePolicySnapshotV0_1",
    "PolicyDefinition",
    "PolicyApplicabilityRecord",
    "PolicyEvaluationRecord",
    "PolicyAuditRecord",
    "PolicyCoverageSummary",
    "PolicyLineageReference",
    "PolicyDiagnostic",
)
