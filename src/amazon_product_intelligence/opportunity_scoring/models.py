"""Immutable public data models for Opportunity Scoring Framework V0.1."""

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
    OpportunityScoringSerializationError,
    OpportunityScoringValidationError,
)


OPPORTUNITY_SCORING_RULESET_VERSION = "opportunity-scoring-v0.1"
_EVALUATION_RULESET_VERSION = "evidence-evaluation-v0.1"
_CONFLICT_RULESET_VERSION = "conflict-resolution-v0.1"
_POLICY_RULESET_VERSION = "evidence-policy-v0.1"
_DECISION_RULESET_VERSION = "decision-framework-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")

_CONDITION_TYPES = {
    "EVIDENCE_INVENTORY",
    "CONFLICT_FREE_EVIDENCE",
    "KEYWORD_EVIDENCE",
    "CONFLICT_CONTEXT",
}
_DECISION_RESULTS = {
    "RULE_NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE",
    "RULE_ANALYSIS_RECORDED",
    "RULE_ANALYSIS_BLOCKED_BY_POLICY",
}
_CALCULATION_STATUSES = {
    "CALCULATED",
    "CALCULATED_WITH_CONFLICT_VISIBLE",
    "BLOCKED_BY_POLICY",
    "EXCLUDED_MISSING_EVIDENCE",
    "NOT_APPLICABLE",
}
_NUMERIC_STATUSES = {"CALCULATED", "CALCULATED_WITH_CONFLICT_VISIBLE"}
_METHOD_BY_STATUS = {
    "CALCULATED": "FIXED_PROCESS_RULE_RESULT_V0_1",
    "CALCULATED_WITH_CONFLICT_VISIBLE": (
        "FIXED_PROCESS_RULE_RESULT_WITH_CONFLICT_VISIBLE_V0_1"
    ),
    "BLOCKED_BY_POLICY": "NO_NUMERIC_RESULT_POLICY_BLOCKED_V0_1",
    "EXCLUDED_MISSING_EVIDENCE": (
        "NO_NUMERIC_RESULT_MISSING_EVIDENCE_V0_1"
    ),
    "NOT_APPLICABLE": "NO_NUMERIC_RESULT_NOT_APPLICABLE_V0_1",
}
_COMPONENT_EXPLANATION_BY_STATUS = {
    "CALCULATED": (
        "Upstream decision rule analysis is available for a versioned process calculation."
    ),
    "CALCULATED_WITH_CONFLICT_VISIBLE": (
        "Upstream decision rule analysis is available; unresolved conflicts remain visible."
    ),
    "BLOCKED_BY_POLICY": (
        "Upstream policy makes this component unavailable without rejecting a product."
    ),
    "EXCLUDED_MISSING_EVIDENCE": (
        "Required evidence is missing; this component is excluded without a numeric zero."
    ),
    "NOT_APPLICABLE": (
        "The upstream decision rule is not applicable; this component has no numeric result."
    ),
}
_EXPLANATION_TEMPLATE = (
    "Explain the factor rule, evidence references, calculation method, version, "
    "process status, and bounded interpretation."
)
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


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise OpportunityScoringValidationError(
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
        raise OpportunityScoringValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OpportunityScoringValidationError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise OpportunityScoringValidationError(
            f"{path} must be a non-negative integer"
        )
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise OpportunityScoringValidationError(
            f"{path} must be {expected.__name__}"
        )


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise OpportunityScoringValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise OpportunityScoringValidationError(
            f"{path} must contain non-empty text"
        )
    if len(set(values)) != len(values):
        raise OpportunityScoringValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, key
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise OpportunityScoringValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise OpportunityScoringValidationError(f"{path} contains duplicates")
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
        raise OpportunityScoringValidationError(f"{path} must be an object")
    if set(payload) != fields:
        missing = sorted(fields - set(payload))
        extra = sorted(set(payload) - fields)
        raise OpportunityScoringValidationError(
            f"invalid {path} fields; missing={missing}, extra={extra}"
        )
    frozen = _freeze_json(payload, path)
    if frozen["ruleset_version"] != ruleset:
        raise OpportunityScoringValidationError(f"unsupported {path} ruleset version")
    snapshot_id = _text(frozen["snapshot_id"], f"{path} snapshot_id")
    source_fingerprints = _unique_texts(
        frozen["source_bundle_fingerprints"],
        f"{path} source_bundle_fingerprints",
        allow_empty=False,
    )
    if any(_SHA256.fullmatch(item) is None for item in source_fingerprints):
        raise OpportunityScoringValidationError(
            f"{path} fingerprints must be SHA-256 hex"
        )
    if set(source_fingerprints) != set(fingerprints):
        raise OpportunityScoringValidationError(
            f"{path} fingerprints do not match canonical bundles"
        )
    identity_payload = dict(frozen)
    identity_payload.pop("snapshot_id")
    if snapshot_id != deterministic_id(identity_prefix, identity_payload):
        raise OpportunityScoringValidationError(f"{path} snapshot identity mismatch")
    for name in array_fields:
        if not isinstance(frozen[name], tuple):
            raise OpportunityScoringValidationError(f"{path}.{name} must be an array")
    if not isinstance(frozen["coverage"], MappingABC):
        raise OpportunityScoringValidationError(f"{path}.coverage must be an object")
    return frozen


class _ScoringModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OpportunityScoringSerializationError:
            raise
        except (
            OpportunityScoringValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise OpportunityScoringSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreFactorDefinition(_ScoringModel):
    """One versioned process-evidence factor without a business conclusion."""

    factor_id: str
    factor_version: str
    name: str
    description: str
    input_requirements: Mapping[str, Any]
    calculation_rule: Mapping[str, Any]
    explanation_template: str
    expected_behavior: str

    def __post_init__(self) -> None:
        for name in (
            "factor_id",
            "factor_version",
            "name",
            "description",
            "explanation_template",
            "expected_behavior",
        ):
            _text(getattr(self, name), f"ScoreFactorDefinition.{name}")
        if self.factor_version != "0.1":
            raise OpportunityScoringValidationError(
                "unsupported score factor version"
            )
        requirements = _freeze_json(
            self.input_requirements, "score factor input_requirements"
        )
        rule = _freeze_json(self.calculation_rule, "score factor calculation_rule")
        if not isinstance(requirements, MappingABC) or set(requirements) != {
            "decision_condition_type",
            "source_record_type",
        }:
            raise OpportunityScoringValidationError(
                "score factor input requirement fields do not match V0.1"
            )
        condition = requirements["decision_condition_type"]
        if (
            condition not in _CONDITION_TYPES
            or requirements["source_record_type"] != "DECISION_EVALUATION"
        ):
            raise OpportunityScoringValidationError(
                "unsupported score factor input requirement"
            )
        if not isinstance(rule, MappingABC) or set(rule) != {
            "calculation_method",
            "conflict_behavior",
            "missing_evidence_behavior",
            "policy_block_behavior",
        }:
            raise OpportunityScoringValidationError(
                "score factor calculation rule fields do not match V0.1"
            )
        expected_rule = {
            "calculation_method": "FIXED_PROCESS_RULE_RESULT_V0_1",
            "conflict_behavior": "PRESERVE_AND_MARK_VISIBLE",
            "missing_evidence_behavior": "EXCLUDE_WITHOUT_NUMERIC_RESULT",
            "policy_block_behavior": "UNAVAILABLE_WITHOUT_NUMERIC_RESULT",
        }
        if dict(rule) != expected_rule:
            raise OpportunityScoringValidationError(
                "score factor calculation rule is not the V0.1 audited rule"
            )
        if self.expected_behavior != "NUMERIC_PROCESS_RESULT_ONLY_NO_RECOMMENDATION":
            raise OpportunityScoringValidationError(
                "score factor expected behavior exceeds V0.1 boundary"
            )
        if self.explanation_template != _EXPLANATION_TEMPLATE:
            raise OpportunityScoringValidationError(
                "score factor explanation template is not the V0.1 audited template"
            )
        object.__setattr__(self, "input_requirements", requirements)
        object.__setattr__(self, "calculation_rule", rule)
        if self.factor_id != deterministic_id(
            "score-factor", _without_id(self, "factor_id")
        ):
            raise OpportunityScoringValidationError(
                "factor_id does not match factor content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreComponentRecord(_ScoringModel):
    """One factor input component; numeric results live only in its calculation."""

    component_id: str
    factor_id: str
    decision_evaluation_id: str
    input_evidence_ids: tuple[str, ...]
    policy_evaluation_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    component_status: str
    component_explanation: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "component_id",
            "factor_id",
            "decision_evaluation_id",
            "component_status",
            "component_explanation",
        ):
            _text(getattr(self, name), f"ScoreComponentRecord.{name}")
        if self.component_status not in _CALCULATION_STATUSES:
            raise OpportunityScoringValidationError("invalid score component status")
        if (
            self.component_explanation
            != _COMPONENT_EXPLANATION_BY_STATUS[self.component_status]
        ):
            raise OpportunityScoringValidationError(
                "score component explanation does not match component status"
            )
        object.__setattr__(
            self,
            "input_evidence_ids",
            _unique_texts(
                self.input_evidence_ids,
                "score component input_evidence_ids",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "policy_evaluation_ids",
            _unique_texts(
                self.policy_evaluation_ids,
                "score component policy_evaluation_ids",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self,
            "conflict_ids",
            _unique_texts(self.conflict_ids, "score component conflict_ids"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _unique_texts(
                self.reason_codes,
                "score component reason_codes",
                allow_empty=False,
            ),
        )
        if self.component_id != deterministic_id(
            "score-component", _without_id(self, "component_id")
        ):
            raise OpportunityScoringValidationError(
                "component_id does not match component content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreCalculationRecord(_ScoringModel):
    """The only public record that may contain a numeric score result."""

    calculation_id: str
    factor_id: str
    component_id: str
    calculation_method: str
    input_components: tuple[str, ...]
    result_value: int | None
    result_status: str
    version: str
    decision_evaluation_ids: tuple[str, ...]
    decision_lineage_ids: tuple[str, ...]
    policy_evaluation_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    process_interpretation: str

    def __post_init__(self) -> None:
        for name in (
            "calculation_id",
            "factor_id",
            "component_id",
            "calculation_method",
            "result_status",
            "version",
            "process_interpretation",
        ):
            _text(getattr(self, name), f"ScoreCalculationRecord.{name}")
        if self.result_status not in _CALCULATION_STATUSES:
            raise OpportunityScoringValidationError("invalid calculation result status")
        if self.calculation_method != _METHOD_BY_STATUS[self.result_status]:
            raise OpportunityScoringValidationError(
                "calculation method does not match result status"
            )
        if self.version != "0.1":
            raise OpportunityScoringValidationError(
                "unsupported score calculation version"
            )
        if self.result_status in _NUMERIC_STATUSES:
            if type(self.result_value) is not int or not 0 <= self.result_value <= 100:
                raise OpportunityScoringValidationError(
                    "calculated result_value must be an integer from 0 through 100"
                )
        elif self.result_value is not None:
            raise OpportunityScoringValidationError(
                "unavailable calculation must not contain a numeric result"
            )
        inputs = _unique_texts(
            self.input_components,
            "score calculation input_components",
            allow_empty=False,
        )
        if inputs != (self.component_id,):
            raise OpportunityScoringValidationError(
                "V0.1 calculation must reference its single component"
            )
        object.__setattr__(self, "input_components", inputs)
        for name, allow_empty in (
            ("decision_evaluation_ids", False),
            ("decision_lineage_ids", False),
            ("policy_evaluation_ids", False),
            ("conflict_ids", True),
            ("evidence_ids", False),
        ):
            object.__setattr__(
                self,
                name,
                _unique_texts(
                    getattr(self, name),
                    f"score calculation {name}",
                    allow_empty=allow_empty,
                ),
            )
        if self.process_interpretation != (
            "RULE_NUMERIC_RESULT_ONLY_NO_RECOMMENDATION_OR_DECISION"
        ):
            raise OpportunityScoringValidationError(
                "score calculation interpretation exceeds V0.1 boundary"
            )
        if self.calculation_id != deterministic_id(
            "score-calculation", _without_id(self, "calculation_id")
        ):
            raise OpportunityScoringValidationError(
                "calculation_id does not match calculation content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreExplanationRecord(_ScoringModel):
    """Human-auditable explanation and complete source references for a calculation."""

    explanation_id: str
    factor_id: str
    component_id: str
    calculation_id: str
    factor_explanation: str
    calculation_rule: str
    version: str
    evidence_ids: tuple[str, ...]
    decision_evaluation_ids: tuple[str, ...]
    policy_evaluation_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    result_interpretation: str

    def __post_init__(self) -> None:
        for name in (
            "explanation_id",
            "factor_id",
            "component_id",
            "calculation_id",
            "factor_explanation",
            "calculation_rule",
            "version",
            "result_interpretation",
        ):
            _text(getattr(self, name), f"ScoreExplanationRecord.{name}")
        if self.version != "0.1":
            raise OpportunityScoringValidationError(
                "unsupported score explanation version"
            )
        for name, allow_empty in (
            ("evidence_ids", False),
            ("decision_evaluation_ids", False),
            ("policy_evaluation_ids", False),
            ("conflict_ids", True),
        ):
            object.__setattr__(
                self,
                name,
                _unique_texts(
                    getattr(self, name),
                    f"score explanation {name}",
                    allow_empty=allow_empty,
                ),
            )
        if self.explanation_id != deterministic_id(
            "score-explanation", _without_id(self, "explanation_id")
        ):
            raise OpportunityScoringValidationError(
                "explanation_id does not match explanation content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreLineageReference(_ScoringModel):
    """Score-to-decision-to-policy-to-canonical replay reference."""

    score_lineage_id: str
    factor_id: str
    component_id: str
    calculation_id: str
    rule_id: str
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
            "score_lineage_id",
            "factor_id",
            "component_id",
            "calculation_id",
            "rule_id",
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
            _text(getattr(self, name), f"ScoreLineageReference.{name}")
        _instance(
            self.observation_kind,
            ObservationKind,
            "score lineage observation_kind",
        )
        _instance(self.evidence_type, EvidenceType, "score lineage evidence_type")
        conflict_values = (
            self.conflict_record_id,
            self.conflict_analysis_id,
            self.conflict_candidate_id,
        )
        if any(item is None for item in conflict_values) != all(
            item is None for item in conflict_values
        ):
            raise OpportunityScoringValidationError(
                "score conflict lineage identities must be supplied together"
            )
        for index, value in enumerate(item for item in conflict_values if item is not None):
            _text(value, f"score lineage conflict identity {index}")
        attempts = _unique_texts(
            self.resolution_attempt_ids, "score lineage resolution_attempt_ids"
        )
        if all(item is None for item in conflict_values) and attempts:
            raise OpportunityScoringValidationError(
                "non-conflict score lineage cannot reference resolution attempts"
            )
        if self.conflict_record_id is not None and not attempts:
            raise OpportunityScoringValidationError(
                "conflict score lineage requires resolution process evidence"
            )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "score lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise OpportunityScoringValidationError(
                "score lineage fingerprints must be SHA-256 hex"
            )
        object.__setattr__(self, "resolution_attempt_ids", attempts)
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        if self.score_lineage_id != deterministic_id(
            "score-lineage", _without_id(self, "score_lineage_id")
        ):
            raise OpportunityScoringValidationError(
                "score_lineage_id does not match lineage content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreDiagnostic(_ScoringModel):
    """Non-conclusive explanation of score calculation process state."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_factor_ids: tuple[str, ...]
    related_component_ids: tuple[str, ...]
    related_calculation_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "score diagnostic_id")
        _text(self.code, "score diagnostic code")
        _instance(self.severity, Severity, "score diagnostic severity")
        for name in (
            "related_factor_ids",
            "related_component_ids",
            "related_calculation_ids",
        ):
            object.__setattr__(
                self,
                name,
                _unique_texts(getattr(self, name), f"score diagnostic {name}"),
            )
        _text(self.message, "score diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "score-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise OpportunityScoringValidationError(
                "diagnostic_id does not match diagnostic content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreCoverageSummary(_ScoringModel):
    """Descriptive score-process counts; this is not a numeric score."""

    source_bundle_count: int
    factor_definition_count: int
    component_count: int
    calculation_count: int
    explanation_count: int
    input_evidence_count: int
    decision_evaluation_reference_count: int
    policy_evaluation_reference_count: int
    conflict_reference_count: int
    lineage_reference_count: int
    diagnostic_count: int
    calculation_status_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count",
            "factor_definition_count",
            "component_count",
            "calculation_count",
            "explanation_count",
            "input_evidence_count",
            "decision_evaluation_reference_count",
            "policy_evaluation_reference_count",
            "conflict_reference_count",
            "lineage_reference_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"ScoreCoverageSummary.{name}")
        if not isinstance(self.calculation_status_counts, MappingABC):
            raise OpportunityScoringValidationError(
                "calculation_status_counts must be an object"
            )
        counts = dict(sorted(self.calculation_status_counts.items()))
        if set(counts) - _CALCULATION_STATUSES or any(
            type(value) is not int or value < 0 for value in counts.values()
        ):
            raise OpportunityScoringValidationError(
                "calculation_status_counts contains invalid counts"
            )
        object.__setattr__(
            self, "calculation_status_counts", MappingProxyType(counts)
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoringRequest(_ScoringModel):
    """Strict canonical and four-snapshot serialized handoff."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    evidence_evaluation_snapshot: Mapping[str, Any]
    conflict_resolution_snapshot: Mapping[str, Any]
    evidence_policy_snapshot: Mapping[str, Any]
    decision_framework_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "canonical_bundles")
        if not bundles:
            raise OpportunityScoringValidationError(
                "canonical_bundles must not be empty"
            )
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise OpportunityScoringValidationError(
                    "canonical_bundles contains a wrong type"
                )
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise OpportunityScoringValidationError(
                    f"invalid canonical bundle: {exc}"
                ) from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise OpportunityScoringValidationError(
                    "duplicate canonical bundle fingerprint"
                )
            fingerprints[fingerprint] = bundle
        ordered_bundles = tuple(
            fingerprints[key] for key in sorted(fingerprints)
        )
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
        if conflict["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]:
            raise OpportunityScoringValidationError(
                "Conflict Resolution source snapshot continuity mismatch"
            )
        if (
            policy["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]
            or policy["source_conflict_resolution_snapshot_id"]
            != conflict["snapshot_id"]
        ):
            raise OpportunityScoringValidationError(
                "Evidence Policy source snapshot continuity mismatch"
            )
        if (
            decision["source_evaluation_snapshot_id"] != evaluation["snapshot_id"]
            or decision["source_conflict_resolution_snapshot_id"]
            != conflict["snapshot_id"]
            or decision["source_policy_snapshot_id"] != policy["snapshot_id"]
        ):
            raise OpportunityScoringValidationError(
                "Decision Framework source snapshot continuity mismatch"
            )
        object.__setattr__(self, "canonical_bundles", ordered_bundles)
        object.__setattr__(self, "evidence_evaluation_snapshot", evaluation)
        object.__setattr__(self, "conflict_resolution_snapshot", conflict)
        object.__setattr__(self, "evidence_policy_snapshot", policy)
        object.__setattr__(self, "decision_framework_snapshot", decision)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityScoringSnapshotV0_1(_ScoringModel):
    """Auditable rule-numeric results without a recommendation or ranking."""

    snapshot_id: str
    ruleset_version: str
    source_evaluation_snapshot_id: str
    source_conflict_resolution_snapshot_id: str
    source_policy_snapshot_id: str
    source_decision_snapshot_id: str
    source_bundle_fingerprints: tuple[str, ...]
    score_factors: tuple[ScoreFactorDefinition, ...]
    components: tuple[ScoreComponentRecord, ...]
    calculations: tuple[ScoreCalculationRecord, ...]
    explanations: tuple[ScoreExplanationRecord, ...]
    coverage: ScoreCoverageSummary
    diagnostics: tuple[ScoreDiagnostic, ...]
    lineage_index: tuple[ScoreLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "source_evaluation_snapshot_id",
            "source_conflict_resolution_snapshot_id",
            "source_policy_snapshot_id",
            "source_decision_snapshot_id",
        ):
            _text(getattr(self, name), f"OpportunityScoringSnapshotV0_1.{name}")
        if self.ruleset_version != OPPORTUNITY_SCORING_RULESET_VERSION:
            raise OpportunityScoringValidationError(
                "invalid Opportunity Scoring ruleset version"
            )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "score snapshot source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise OpportunityScoringValidationError(
                "score snapshot fingerprints must be SHA-256 hex"
            )
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        sequences = (
            ("score_factors", ScoreFactorDefinition, lambda item: item.factor_id),
            ("components", ScoreComponentRecord, lambda item: item.component_id),
            (
                "calculations",
                ScoreCalculationRecord,
                lambda item: item.calculation_id,
            ),
            (
                "explanations",
                ScoreExplanationRecord,
                lambda item: item.explanation_id,
            ),
            ("diagnostics", ScoreDiagnostic, lambda item: item.diagnostic_id),
            (
                "lineage_index",
                ScoreLineageReference,
                lambda item: item.score_lineage_id,
            ),
        )
        for name, expected, key in sequences:
            object.__setattr__(
                self,
                name,
                _typed_unique(getattr(self, name), expected, f"snapshot {name}", key),
            )
        _instance(self.coverage, ScoreCoverageSummary, "score snapshot coverage")
        factors = {item.factor_id: item for item in self.score_factors}
        components = {item.factor_id: item for item in self.components}
        calculations = {item.factor_id: item for item in self.calculations}
        explanations = {item.factor_id: item for item in self.explanations}
        if not factors or set(factors) != set(components) or set(factors) != set(
            calculations
        ) or set(factors) != set(explanations):
            raise OpportunityScoringValidationError(
                "every factor requires exactly one component, calculation, and explanation"
            )
        conditions = {
            item.input_requirements["decision_condition_type"]
            for item in self.score_factors
        }
        if conditions != _CONDITION_TYPES or len(self.score_factors) != 4:
            raise OpportunityScoringValidationError(
                "V0.1 requires one score factor for each fixed decision condition"
            )
        calculation_ids = {
            item.calculation_id: item for item in self.calculations
        }
        component_ids = {item.component_id: item for item in self.components}
        decision_ids: set[str] = set()
        policy_ids: set[str] = set()
        conflict_ids: set[str] = set()
        evidence_ids: set[str] = set()
        for factor_id, component in components.items():
            calculation = calculations[factor_id]
            explanation = explanations[factor_id]
            decision_ids.add(component.decision_evaluation_id)
            policy_ids.update(component.policy_evaluation_ids)
            conflict_ids.update(component.conflict_ids)
            evidence_ids.update(component.input_evidence_ids)
            if (
                component.component_id != calculation.component_id
                or component.component_id != explanation.component_id
                or calculation.calculation_id != explanation.calculation_id
                or component.component_status != calculation.result_status
                or calculation.decision_evaluation_ids
                != (component.decision_evaluation_id,)
                or calculation.policy_evaluation_ids
                != component.policy_evaluation_ids
                or calculation.conflict_ids != component.conflict_ids
                or calculation.evidence_ids != component.input_evidence_ids
                or explanation.decision_evaluation_ids
                != calculation.decision_evaluation_ids
                or explanation.policy_evaluation_ids
                != calculation.policy_evaluation_ids
                or explanation.conflict_ids != calculation.conflict_ids
                or explanation.evidence_ids != calculation.evidence_ids
                or explanation.calculation_rule != calculation.calculation_method
            ):
                raise OpportunityScoringValidationError(
                    "score factor component, calculation, and explanation mismatch"
                )
        lineages_by_calculation: dict[str, list[ScoreLineageReference]] = {}
        for lineage in self.lineage_index:
            calculation = calculation_ids.get(lineage.calculation_id)
            component = component_ids.get(lineage.component_id)
            if (
                calculation is None
                or component is None
                or lineage.factor_id != calculation.factor_id
                or lineage.factor_id != component.factor_id
                or lineage.decision_evaluation_id
                not in calculation.decision_evaluation_ids
                or lineage.policy_evaluation_id
                not in calculation.policy_evaluation_ids
                or lineage.support_record_id not in calculation.evidence_ids
            ):
                raise OpportunityScoringValidationError(
                    "score lineage contains an orphan reference"
                )
            if (
                lineage.conflict_record_id is not None
                and lineage.conflict_record_id not in calculation.conflict_ids
            ):
                raise OpportunityScoringValidationError(
                    "score lineage references an unrelated conflict"
                )
            lineages_by_calculation.setdefault(lineage.calculation_id, []).append(
                lineage
            )
        for calculation in self.calculations:
            lineages = lineages_by_calculation.get(calculation.calculation_id, [])
            if not lineages:
                raise OpportunityScoringValidationError(
                    "every score calculation requires complete lineage"
                )
            if {item.policy_evaluation_id for item in lineages} != set(
                calculation.policy_evaluation_ids
            ) or {item.support_record_id for item in lineages} != set(
                calculation.evidence_ids
            ) or {item.decision_lineage_id for item in lineages} != set(
                calculation.decision_lineage_ids
            ) or {
                item.conflict_record_id
                for item in lineages
                if item.conflict_record_id is not None
            } != set(calculation.conflict_ids):
                raise OpportunityScoringValidationError(
                    "score lineage does not cover calculation inputs"
                )
        factor_ids = set(factors)
        for diagnostic in self.diagnostics:
            if (
                not set(diagnostic.related_factor_ids) <= factor_ids
                or not set(diagnostic.related_component_ids) <= set(component_ids)
                or not set(diagnostic.related_calculation_ids)
                <= set(calculation_ids)
            ):
                raise OpportunityScoringValidationError(
                    "score diagnostic contains an orphan reference"
                )
        expected_coverage = coverage_from_records(
            bundle_count=len(fingerprints),
            factors=self.score_factors,
            components=self.components,
            calculations=self.calculations,
            explanations=self.explanations,
            diagnostics=self.diagnostics,
            lineage=self.lineage_index,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise OpportunityScoringValidationError("score coverage mismatch")
        expected_id = deterministic_id(
            "opportunity-scoring-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise OpportunityScoringSerializationError(
                "snapshot_id does not match snapshot content"
            )

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        """Replay score lineage through canonical transformation evidence."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence):
            raise OpportunityScoringValidationError(
                "bundles must be a non-empty sequence"
            )
        if not bundles:
            raise OpportunityScoringValidationError(
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
                raise OpportunityScoringValidationError(
                    "against-bundles input contains a wrong type"
                )
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise OpportunityScoringValidationError(
                    f"invalid canonical bundle: {exc}"
                ) from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise OpportunityScoringValidationError(
                    "duplicate canonical bundle fingerprint"
                )
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise OpportunityScoringValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                content = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != content:
                    raise OpportunityScoringValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = content
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                current = observations.get(key)
                if current is not None and canonical_json(current[0]) != canonical_json(
                    observation
                ):
                    raise OpportunityScoringValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current is None:
                    observations[key] = (observation, {fingerprint})
                else:
                    current[1].add(fingerprint)
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise OpportunityScoringValidationError(
                "score snapshot fingerprints do not match supplied bundles"
            )
        grouped_runs: dict[tuple[str, str, str], set[str]] = {}
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            entry = observations.get(key)
            if entry is None:
                raise OpportunityScoringValidationError(
                    f"orphan score observation: {reference.observation_id}"
                )
            observation, source_fingerprints = entry
            transformation = observation.provenance.transformation
            run = runs.get(reference.transformation_run_id)
            if run is None:
                raise OpportunityScoringValidationError(
                    f"orphan score transformation: {reference.transformation_run_id}"
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
                raise OpportunityScoringValidationError(
                    f"score lineage content mismatch: {reference.observation_id}"
                )
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or reference.raw_evidence_id not in raw_ids
                or reference.raw_evidence_id not in run.input_raw_evidence_references
                or reference.observation_id not in run.output_observation_ids
            ):
                raise OpportunityScoringValidationError(
                    f"broken score transformation lineage: {reference.observation_id}"
                )
            group = (
                reference.calculation_id,
                reference.policy_evaluation_id,
                reference.observation_id,
            )
            grouped_runs.setdefault(group, set()).add(
                reference.transformation_run_id
            )
        for (_, _, observation_id), actual_runs in grouped_runs.items():
            expected_runs = {key[1] for key in observations if key[0] == observation_id}
            if actual_runs != expected_runs:
                raise OpportunityScoringValidationError(
                    f"score lineage omits an observation emission: {observation_id}"
                )
        return self


def coverage_from_records(
    *,
    bundle_count: int,
    factors: Sequence[ScoreFactorDefinition],
    components: Sequence[ScoreComponentRecord],
    calculations: Sequence[ScoreCalculationRecord],
    explanations: Sequence[ScoreExplanationRecord],
    diagnostics: Sequence[ScoreDiagnostic],
    lineage: Sequence[ScoreLineageReference],
) -> ScoreCoverageSummary:
    return ScoreCoverageSummary(
        source_bundle_count=bundle_count,
        factor_definition_count=len(factors),
        component_count=len(components),
        calculation_count=len(calculations),
        explanation_count=len(explanations),
        input_evidence_count=len({
            evidence_id
            for calculation in calculations
            for evidence_id in calculation.evidence_ids
        }),
        decision_evaluation_reference_count=len({
            decision_id
            for calculation in calculations
            for decision_id in calculation.decision_evaluation_ids
        }),
        policy_evaluation_reference_count=len({
            policy_id
            for calculation in calculations
            for policy_id in calculation.policy_evaluation_ids
        }),
        conflict_reference_count=len({
            conflict_id
            for calculation in calculations
            for conflict_id in calculation.conflict_ids
        }),
        lineage_reference_count=len(lineage),
        diagnostic_count=len(diagnostics),
        calculation_status_counts=dict(sorted(Counter(
            item.result_status for item in calculations
        ).items())),
    )


__all__ = (
    "OPPORTUNITY_SCORING_RULESET_VERSION",
    "OpportunityScoringRequest",
    "OpportunityScoringSnapshotV0_1",
    "ScoreFactorDefinition",
    "ScoreComponentRecord",
    "ScoreCalculationRecord",
    "ScoreExplanationRecord",
    "ScoreCoverageSummary",
    "ScoreLineageReference",
    "ScoreDiagnostic",
)
