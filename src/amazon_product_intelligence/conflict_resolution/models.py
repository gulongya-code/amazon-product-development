"""Immutable public data models for Conflict Resolution V0.1."""

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
    JsonContract,
    KeywordMetricObservation,
    MetricObservation,
    ObservationKind,
    PresenceStatus,
    ProductFactObservation,
    ProductKeywordRelationshipObservation,
    ReviewObservation,
    Severity,
    SubjectRef,
    ValueEnvelope,
    canonical_json,
    deterministic_id,
)

from .errors import ConflictSerializationError, ConflictValidationError


CONFLICT_RESOLUTION_RULESET_VERSION = "conflict-resolution-v0.1"
_EVALUATION_RULESET_VERSION = "evidence-evaluation-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ATTEMPT_STATUSES = {
    "NOT_ATTEMPTED",
    "INSUFFICIENT_EVIDENCE",
    "AMBIGUOUS",
    "RESOLUTION_PRODUCED",
}
_FORBIDDEN_METHOD_TOKENS = {
    "PROVIDER_PRIORITY",
    "LATEST",
    "HIGHEST",
    "LOWEST",
    "AVERAGE",
    "MEDIAN",
    "MAJORITY",
    "CONFIDENCE",
    "TRUST",
    "SCORE",
    "RANKING",
    "WEIGHT",
    "PROBABILITY",
    "RECOMMENDATION",
    "PROVIDER",
    "PREFERRED",
    "WINNER",
    "WINS",
}
_FORBIDDEN_PROCESS_FIELD_TOKENS = {
    "WINNER",
    "SCORE",
    "CONFIDENCE",
    "TRUST",
    "RECOMMENDATION",
    "RANKING",
    "WEIGHT",
    "PROBABILITY",
    "PREFERRED",
    "PRIORITY",
    "TRUTH",
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


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ConflictValidationError(f"{path} must contain finite JSON data: {exc}") from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ConflictValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise ConflictValidationError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ConflictValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise ConflictValidationError(f"{path} must be {expected.__name__}")


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise ConflictValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise ConflictValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise ConflictValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, key
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise ConflictValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise ConflictValidationError(f"{path} contains duplicates")
    return ordered


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def _observed_value_identity(value: ValueEnvelope) -> str:
    selected = value.normalized_value
    if selected is None:
        selected = value.raw_value
    return canonical_json({"value_type": value.value_type, "value": selected})


def _reject_forbidden_process_fields(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, child in value.items():
            normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")
            tokens = set(normalized.split("_"))
            if tokens & _FORBIDDEN_PROCESS_FIELD_TOKENS:
                raise ConflictValidationError(
                    f"{path}.{key} uses a forbidden conclusion field"
                )
            _reject_forbidden_process_fields(child, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, child in enumerate(value):
            _reject_forbidden_process_fields(child, f"{path}[{index}]")


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    """Return the evaluation-compatible order-insensitive bundle fingerprint."""

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


def observation_dimension(observation: CanonicalObservation) -> str:
    if isinstance(observation, ProductFactObservation):
        return observation.dimension
    if isinstance(observation, MetricObservation):
        return observation.metric
    if isinstance(observation, KeywordMetricObservation):
        return observation.metric
    if isinstance(observation, ProductKeywordRelationshipObservation):
        return ":".join((
            "relationship",
            observation.direction.value,
            observation.relationship_type.value,
            observation.channel.value,
        ))
    if isinstance(observation, ReviewObservation):
        return "review"
    raise ConflictValidationError(
        f"unsupported canonical observation type: {type(observation).__name__}"
    )


def semantic_field_material(observation: CanonicalObservation) -> dict[str, Any]:
    """Return the Evaluation-compatible comparability key for an observation."""

    material: dict[str, Any] = {
        "subject": observation.subject,
        "observation_kind": observation.observation_kind,
        "dimension": observation_dimension(observation),
        "scope": observation.scope,
        "time_context": {
            "observed_at": observation.time.observed_at,
            "observed_at_status": observation.time.observed_at_status,
            "period_start": observation.time.period_start,
            "period_end": observation.time.period_end,
            "period_type": observation.time.period_type,
            "timezone": observation.time.timezone,
        },
        "evidence_type": observation.evidence_type,
        "unit": observation.value.unit,
    }
    if isinstance(observation, MetricObservation):
        material.update({
            "currency": observation.currency,
            "rank_context": observation.rank_context,
        })
    elif isinstance(observation, KeywordMetricObservation):
        material["keyword"] = observation.keyword
    elif isinstance(observation, ProductKeywordRelationshipObservation):
        material.update({
            "product": observation.product,
            "keyword": observation.keyword,
            "direction": observation.direction,
            "relationship_type": observation.relationship_type,
            "channel": observation.channel,
        })
    elif isinstance(observation, ReviewObservation):
        material.update({
            "product": observation.product,
            "review_identity": observation.provider_review_identity
            or observation.semantic_observation_id,
        })
    elif (
        isinstance(observation, ProductFactObservation)
        and observation.dimension == "child_product_relationship"
    ):
        material["relationship_value"] = observation.value.normalized_value
    return material


def validate_evaluation_snapshot_payload(
    payload: Mapping[str, Any], fingerprints: Sequence[str]
) -> Mapping[str, Any]:
    """Validate the strict serialized Evidence Evaluation handoff."""

    if not isinstance(payload, MappingABC):
        raise ConflictValidationError("evidence_evaluation_snapshot must be an object")
    if set(payload) != _EVALUATION_SNAPSHOT_FIELDS:
        missing = sorted(_EVALUATION_SNAPSHOT_FIELDS - set(payload))
        extra = sorted(set(payload) - _EVALUATION_SNAPSHOT_FIELDS)
        raise ConflictValidationError(
            f"invalid evaluation snapshot fields; missing={missing}, extra={extra}"
        )
    frozen = _freeze_json(payload, "evidence_evaluation_snapshot")
    if frozen["ruleset_version"] != _EVALUATION_RULESET_VERSION:
        raise ConflictValidationError("unsupported Evidence Evaluation ruleset version")
    snapshot_id = frozen["snapshot_id"]
    _text(snapshot_id, "evaluation snapshot_id")
    source_fingerprints = _unique_texts(
        frozen["source_bundle_fingerprints"],
        "evaluation source_bundle_fingerprints",
        allow_empty=False,
    )
    if any(_SHA256.fullmatch(item) is None for item in source_fingerprints):
        raise ConflictValidationError("evaluation fingerprints must be SHA-256 hex")
    if set(source_fingerprints) != set(fingerprints):
        raise ConflictValidationError("evaluation fingerprints do not match canonical bundles")
    identity_payload = dict(frozen)
    identity_payload.pop("snapshot_id")
    if snapshot_id != deterministic_id("evidence-evaluation-snapshot", identity_payload):
        raise ConflictValidationError("evaluation snapshot identity mismatch")
    for name in (
        "evidence_quality_profiles",
        "support_records",
        "conflict_records",
        "diagnostics",
        "lineage_index",
    ):
        values = frozen[name]
        if not isinstance(values, tuple):
            raise ConflictValidationError(f"evaluation {name} must be an array")
    if not isinstance(frozen["coverage"], MappingABC):
        raise ConflictValidationError("evaluation coverage must be an object")
    return frozen


class _ConflictModel(JsonContract):
    """Strictly decode public models and translate contract errors."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except ConflictSerializationError:
            raise
        except (ConflictValidationError, ContractValidationError, TypeError, ValueError) as exc:
            raise ConflictSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictLineageReference(_ConflictModel):
    """Replayable canonical observation-to-collection lineage."""

    observation_id: str
    semantic_observation_id: str
    observation_kind: ObservationKind
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
            _text(getattr(self, name), f"ConflictLineageReference.{name}")
        _instance(self.observation_kind, ObservationKind, "lineage observation_kind")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise ConflictValidationError("lineage fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictCandidate(_ConflictModel):
    """One preserved present candidate from an Evaluation conflict."""

    candidate_id: str
    source_evaluation_conflict_id: str
    observation_id: str
    value: ValueEnvelope
    provider: str
    source: str
    lineage_references: tuple[ConflictLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "candidate_id",
            "source_evaluation_conflict_id",
            "observation_id",
            "provider",
            "source",
        ):
            _text(getattr(self, name), f"ConflictCandidate.{name}")
        _instance(self.value, ValueEnvelope, "candidate value")
        if self.value.presence_status is not PresenceStatus.PRESENT:
            raise ConflictValidationError("resolution candidates must have PRESENT values")
        lineages = _typed_unique(
            self.lineage_references,
            ConflictLineageReference,
            "candidate lineage_references",
            canonical_json,
        )
        if not lineages or {item.observation_id for item in lineages} != {self.observation_id}:
            raise ConflictValidationError("candidate lineage does not match observation")
        if {item.provider for item in lineages} != {self.provider}:
            raise ConflictValidationError("candidate provider does not match lineage")
        if {f"{item.provider}::{item.source_tool}" for item in lineages} != {self.source}:
            raise ConflictValidationError("candidate source does not match lineage")
        object.__setattr__(self, "lineage_references", lineages)
        if self.candidate_id != deterministic_id(
            "conflict-candidate", _without_id(self, "candidate_id")
        ):
            raise ConflictValidationError("candidate_id does not match candidate content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictAnalysisRecord(_ConflictModel):
    """Candidate-preserving analysis of one Evaluation conflict."""

    conflict_analysis_id: str
    source_evaluation_conflict_id: str
    semantic_field_id: str
    subject: SubjectRef
    observation_kind: ObservationKind
    dimension: str
    candidate_ids: tuple[str, ...]
    candidates: tuple[ConflictCandidate, ...]
    analysis_status: str
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "conflict_analysis_id",
            "source_evaluation_conflict_id",
            "semantic_field_id",
            "dimension",
        ):
            _text(getattr(self, name), f"ConflictAnalysisRecord.{name}")
        _instance(self.subject, SubjectRef, "analysis subject")
        _instance(self.observation_kind, ObservationKind, "analysis observation_kind")
        candidate_ids = _unique_texts(
            self.candidate_ids, "analysis candidate_ids", allow_empty=False
        )
        if len(candidate_ids) < 2:
            raise ConflictValidationError("conflict analysis requires at least two candidates")
        candidates = _typed_unique(
            self.candidates,
            ConflictCandidate,
            "analysis candidates",
            lambda item: item.candidate_id,
        )
        if {item.candidate_id for item in candidates} != set(candidate_ids):
            raise ConflictValidationError("analysis candidate IDs do not match candidates")
        if {item.source_evaluation_conflict_id for item in candidates} != {
            self.source_evaluation_conflict_id
        }:
            raise ConflictValidationError("analysis candidates cross Evaluation conflicts")
        if len({item.observation_id for item in candidates}) != len(candidates):
            raise ConflictValidationError("analysis candidates must reference unique observations")
        if len({_observed_value_identity(item.value) for item in candidates}) < 2:
            raise ConflictValidationError("analysis candidates must contain different values")
        if self.analysis_status != "CONFLICT_PRESENT":
            raise ConflictValidationError("analysis_status must be CONFLICT_PRESENT")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "analysis source_bundle_fingerprints",
            allow_empty=False,
        )
        candidate_fingerprints = {
            fingerprint
            for candidate in candidates
            for lineage in candidate.lineage_references
            for fingerprint in lineage.source_bundle_fingerprints
        }
        if set(fingerprints) != candidate_fingerprints:
            raise ConflictValidationError("analysis fingerprints do not match candidate lineage")
        object.__setattr__(self, "candidate_ids", candidate_ids)
        object.__setattr__(self, "candidates", candidates)
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        if self.conflict_analysis_id != deterministic_id(
            "conflict-analysis", _without_id(self, "conflict_analysis_id")
        ):
            raise ConflictValidationError("conflict_analysis_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolutionAttemptRecord(_ConflictModel):
    """Evidence that an explicit method was or was not applied to a conflict."""

    resolution_attempt_id: str
    conflict_analysis_id: str
    attempted_method: str
    candidate_ids: tuple[str, ...]
    available_evidence_candidate_ids: tuple[str, ...]
    result_status: str
    produced_candidate_id: str | None
    process_evidence: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "resolution_attempt_id",
            "conflict_analysis_id",
            "attempted_method",
            "result_status",
        ):
            _text(getattr(self, name), f"ResolutionAttemptRecord.{name}")
        candidate_ids = _unique_texts(
            self.candidate_ids, "attempt candidate_ids", allow_empty=False
        )
        available_ids = _unique_texts(
            self.available_evidence_candidate_ids,
            "attempt available_evidence_candidate_ids",
        )
        if not set(available_ids) <= set(candidate_ids):
            raise ConflictValidationError(
                "available evidence must contain present conflict candidates only"
            )
        if self.result_status not in _ATTEMPT_STATUSES:
            raise ConflictValidationError("invalid resolution attempt result_status")
        normalized_method = re.sub(r"[^A-Z0-9]+", "_", self.attempted_method.upper()).strip("_")
        if self.result_status == "NOT_ATTEMPTED":
            if normalized_method != "NOT_ATTEMPTED":
                raise ConflictValidationError("NOT_ATTEMPTED requires attempted_method=NOT_ATTEMPTED")
        else:
            if normalized_method == "NOT_ATTEMPTED":
                raise ConflictValidationError("an attempted status requires an explicit method")
            if any(token in normalized_method for token in _FORBIDDEN_METHOD_TOKENS):
                raise ConflictValidationError("attempted_method uses a forbidden preference rule")
        if self.result_status == "RESOLUTION_PRODUCED":
            _text(self.produced_candidate_id, "produced_candidate_id")
            if self.produced_candidate_id not in candidate_ids:
                raise ConflictValidationError("produced candidate must be in the preserved set")
            if self.produced_candidate_id not in available_ids:
                raise ConflictValidationError("produced candidate must be available evidence")
        elif self.produced_candidate_id is not None:
            raise ConflictValidationError(
                "only RESOLUTION_PRODUCED may reference a produced candidate"
            )
        process_evidence = _freeze_json(self.process_evidence, "attempt process_evidence")
        if not isinstance(process_evidence, MappingABC):
            raise ConflictValidationError("attempt process_evidence must be an object")
        _reject_forbidden_process_fields(process_evidence, "attempt process_evidence")
        if self.result_status == "RESOLUTION_PRODUCED" and not process_evidence:
            raise ConflictValidationError("produced resolution requires process evidence")
        object.__setattr__(self, "candidate_ids", candidate_ids)
        object.__setattr__(self, "available_evidence_candidate_ids", available_ids)
        object.__setattr__(self, "process_evidence", process_evidence)
        if self.resolution_attempt_id != deterministic_id(
            "resolution-attempt", _without_id(self, "resolution_attempt_id")
        ):
            raise ConflictValidationError("resolution_attempt_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictDiagnostic(_ConflictModel):
    """Non-conclusive explanation of conflict-resolution process state."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_conflict_analysis_ids: tuple[str, ...]
    related_resolution_attempt_ids: tuple[str, ...]
    related_candidate_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "diagnostic id")
        _text(self.code, "diagnostic code")
        _instance(self.severity, Severity, "diagnostic severity")
        object.__setattr__(self, "related_conflict_analysis_ids", _unique_texts(
            self.related_conflict_analysis_ids, "diagnostic analysis IDs"
        ))
        object.__setattr__(self, "related_resolution_attempt_ids", _unique_texts(
            self.related_resolution_attempt_ids, "diagnostic attempt IDs"
        ))
        object.__setattr__(self, "related_candidate_ids", _unique_texts(
            self.related_candidate_ids, "diagnostic candidate IDs"
        ))
        _text(self.message, "diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "conflict-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise ConflictValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictCoverageSummary(_ConflictModel):
    """Descriptive process counts without confidence, truth, or preference."""

    source_bundle_count: int
    source_evaluation_conflict_count: int
    conflict_analysis_count: int
    candidate_count: int
    resolution_attempt_count: int
    provider_count: int
    source_count: int
    diagnostic_count: int
    attempt_status_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count",
            "source_evaluation_conflict_count",
            "conflict_analysis_count",
            "candidate_count",
            "resolution_attempt_count",
            "provider_count",
            "source_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"ConflictCoverageSummary.{name}")
        if not isinstance(self.attempt_status_counts, MappingABC):
            raise ConflictValidationError("attempt_status_counts must be an object")
        counts = dict(sorted(self.attempt_status_counts.items()))
        if set(counts) - _ATTEMPT_STATUSES:
            raise ConflictValidationError("attempt_status_counts contains an invalid status")
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise ConflictValidationError("attempt_status_counts values must be counts")
        object.__setattr__(self, "attempt_status_counts", MappingProxyType(counts))


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictResolutionRequest(_ConflictModel):
    """Strict canonical/evaluation handoff plus optional explicit attempts."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    evidence_evaluation_snapshot: Mapping[str, Any]
    resolution_attempts: tuple[ResolutionAttemptRecord, ...] = ()

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "request canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise ConflictValidationError(
                "canonical_bundles must contain one or more CanonicalEvidenceBundle values"
            )
        fingerprinted: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise ConflictValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprinted.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprinted}) != len(fingerprinted):
            raise ConflictValidationError("duplicate canonical bundle fingerprint")
        ordered_bundles = tuple(
            bundle for _, bundle in sorted(fingerprinted, key=lambda item: item[0])
        )
        fingerprints = tuple(item[0] for item in sorted(fingerprinted, key=lambda item: item[0]))
        evaluation_snapshot = validate_evaluation_snapshot_payload(
            self.evidence_evaluation_snapshot, fingerprints
        )
        attempts = _typed_unique(
            self.resolution_attempts,
            ResolutionAttemptRecord,
            "request resolution_attempts",
            lambda item: item.resolution_attempt_id,
        )
        object.__setattr__(self, "canonical_bundles", ordered_bundles)
        object.__setattr__(self, "evidence_evaluation_snapshot", evaluation_snapshot)
        object.__setattr__(self, "resolution_attempts", attempts)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictResolutionSnapshotV0_1(_ConflictModel):
    """Auditable conflict analysis and explicit resolution-process evidence."""

    snapshot_id: str
    ruleset_version: str
    source_evaluation_snapshot_id: str
    source_bundle_fingerprints: tuple[str, ...]
    conflict_analyses: tuple[ConflictAnalysisRecord, ...]
    resolution_attempts: tuple[ResolutionAttemptRecord, ...]
    coverage: ConflictCoverageSummary
    diagnostics: tuple[ConflictDiagnostic, ...]
    lineage_index: tuple[ConflictLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot id")
        _text(self.source_evaluation_snapshot_id, "source evaluation snapshot id")
        if self.ruleset_version != CONFLICT_RESOLUTION_RULESET_VERSION:
            raise ConflictValidationError("invalid Conflict Resolution ruleset version")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "snapshot source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise ConflictValidationError("snapshot fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        sequences = (
            (
                "conflict_analyses",
                ConflictAnalysisRecord,
                lambda item: item.conflict_analysis_id,
            ),
            (
                "resolution_attempts",
                ResolutionAttemptRecord,
                lambda item: item.resolution_attempt_id,
            ),
            ("diagnostics", ConflictDiagnostic, lambda item: item.diagnostic_id),
            ("lineage_index", ConflictLineageReference, canonical_json),
        )
        for name, expected, key in sequences:
            object.__setattr__(self, name, _typed_unique(
                getattr(self, name), expected, f"snapshot {name}", key
            ))
        _instance(self.coverage, ConflictCoverageSummary, "snapshot coverage")
        analyses = {item.conflict_analysis_id: item for item in self.conflict_analyses}
        if len({item.source_evaluation_conflict_id for item in self.conflict_analyses}) != len(
            self.conflict_analyses
        ):
            raise ConflictValidationError("duplicate source Evaluation conflict")
        attempts_by_analysis: dict[str, list[ResolutionAttemptRecord]] = {}
        for attempt in self.resolution_attempts:
            analysis = analyses.get(attempt.conflict_analysis_id)
            if analysis is None:
                raise ConflictValidationError("attempt references an absent conflict analysis")
            if set(attempt.candidate_ids) != set(analysis.candidate_ids):
                raise ConflictValidationError("attempt candidate set does not preserve analysis")
            attempts_by_analysis.setdefault(attempt.conflict_analysis_id, []).append(attempt)
        if set(attempts_by_analysis) != set(analyses):
            raise ConflictValidationError("every conflict analysis requires process evidence")
        candidate_ids = {
            candidate.candidate_id
            for analysis in self.conflict_analyses
            for candidate in analysis.candidates
        }
        observation_ids = {
            candidate.observation_id
            for analysis in self.conflict_analyses
            for candidate in analysis.candidates
        }
        if {item.observation_id for item in self.lineage_index} != observation_ids:
            raise ConflictValidationError("snapshot lineage does not cover all candidates")
        analysis_ids = set(analyses)
        attempt_ids = {item.resolution_attempt_id for item in self.resolution_attempts}
        for diagnostic in self.diagnostics:
            if not set(diagnostic.related_conflict_analysis_ids) <= analysis_ids:
                raise ConflictValidationError("diagnostic references an absent analysis")
            if not set(diagnostic.related_resolution_attempt_ids) <= attempt_ids:
                raise ConflictValidationError("diagnostic references an absent attempt")
            if not set(diagnostic.related_candidate_ids) <= candidate_ids:
                raise ConflictValidationError("diagnostic references an absent candidate")
        checks = (
            (self.coverage.source_bundle_count, len(fingerprints), "source bundle"),
            (
                self.coverage.source_evaluation_conflict_count,
                len(self.conflict_analyses),
                "source conflict",
            ),
            (self.coverage.conflict_analysis_count, len(self.conflict_analyses), "analysis"),
            (self.coverage.candidate_count, len(candidate_ids), "candidate"),
            (
                self.coverage.resolution_attempt_count,
                len(self.resolution_attempts),
                "attempt",
            ),
            (
                self.coverage.provider_count,
                len({
                    candidate.provider
                    for analysis in self.conflict_analyses
                    for candidate in analysis.candidates
                }),
                "provider",
            ),
            (
                self.coverage.source_count,
                len({
                    candidate.source
                    for analysis in self.conflict_analyses
                    for candidate in analysis.candidates
                }),
                "source",
            ),
            (self.coverage.diagnostic_count, len(self.diagnostics), "diagnostic"),
        )
        mismatch = next((label for left, right, label in checks if left != right), None)
        if mismatch is not None:
            raise ConflictValidationError(f"coverage {mismatch} count mismatch")
        expected_status_counts = dict(sorted(Counter(
            item.result_status for item in self.resolution_attempts
        ).items()))
        if dict(self.coverage.attempt_status_counts) != expected_status_counts:
            raise ConflictValidationError("coverage attempt status counts mismatch")
        expected_id = deterministic_id(
            "conflict-resolution-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise ConflictSerializationError("snapshot_id does not match snapshot content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        """Replay candidate lineage through canonical transformation evidence."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise ConflictValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[tuple[str, str], tuple[CanonicalObservation, set[str]]] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, Any] = {}
        issues: dict[str, str] = {}
        generic: dict[tuple[str, str], str] = {}
        namespaces: dict[str, str] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise ConflictValidationError("against-bundles input contains a wrong type")
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise ConflictValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise ConflictValidationError("duplicate canonical bundle fingerprint")
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise ConflictValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                namespace = namespaces.get(observation.observation_id)
                if namespace is not None and namespace != "observation":
                    raise ConflictValidationError(
                        f"canonical source identity crosses namespaces: {observation.observation_id}"
                    )
                namespaces[observation.observation_id] = "observation"
                content = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != content:
                    raise ConflictValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = content
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                current = observations.get(key)
                if current is not None and canonical_json(current[0]) != canonical_json(observation):
                    raise ConflictValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current is None:
                    observations[key] = (observation, {fingerprint})
                else:
                    current[1].add(fingerprint)
            for query in bundle.query_execution_records:
                namespace = namespaces.get(query.query_execution_id)
                if namespace is not None and namespace != "query execution":
                    raise ConflictValidationError(
                        f"canonical source identity crosses namespaces: {query.query_execution_id}"
                    )
                namespaces[query.query_execution_id] = "query execution"
                key = ("query execution", query.query_execution_id)
                content = canonical_json(query)
                if key in generic and generic[key] != content:
                    raise ConflictValidationError(
                        f"query execution identity collision: {query.query_execution_id}"
                    )
                generic[key] = content
            for issue in bundle.quality_issues:
                content = canonical_json(issue)
                if issue.issue_id in issues and issues[issue.issue_id] != content:
                    raise ConflictValidationError(
                        f"quality issue identity collision: {issue.issue_id}"
                    )
                issues[issue.issue_id] = content
            for kind, records, field in (
                ("conflict", bundle.conflicts, "conflict_id"),
                ("resolution", bundle.resolutions, "resolution_id"),
            ):
                for record in records:
                    identity = getattr(record, field)
                    content = canonical_json(record)
                    key = (kind, identity)
                    if key in generic and generic[key] != content:
                        raise ConflictValidationError(f"{kind} identity collision: {identity}")
                    generic[key] = content
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise ConflictValidationError(
                "snapshot source bundle fingerprints do not match supplied bundles"
            )
        expected_candidate_observation_ids = {
            candidate.observation_id
            for analysis in self.conflict_analyses
            for candidate in analysis.candidates
        }
        expected_lineage_keys = {
            key for key in observations if key[0] in expected_candidate_observation_ids
        }
        actual_lineage_keys = {
            (item.observation_id, item.transformation_run_id) for item in self.lineage_index
        }
        if actual_lineage_keys != expected_lineage_keys:
            raise ConflictValidationError("lineage index does not match candidate emissions")
        lineages_by_observation: dict[str, list[ConflictLineageReference]] = {}
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            entry = observations.get(key)
            if entry is None:
                raise ConflictValidationError(
                    f"orphan candidate observation: {reference.observation_id}"
                )
            observation, source_fingerprints = entry
            transformation = observation.provenance.transformation
            run = runs.get(reference.transformation_run_id)
            if run is None:
                raise ConflictValidationError(
                    f"orphan transformation run: {reference.transformation_run_id}"
                )
            expected = (
                (reference.semantic_observation_id, observation.semantic_observation_id),
                (reference.observation_kind, observation.observation_kind),
                (reference.mapping_version, transformation.mapping_version),
                (reference.raw_evidence_id, transformation.raw_evidence_reference),
                (reference.collection_run_id, transformation.collection_run_id),
                (reference.provider, observation.provenance.provider),
                (reference.source_tool, observation.provenance.source_tool),
                (reference.source_field, observation.provenance.source_field),
                (set(reference.source_bundle_fingerprints), source_fingerprints),
            )
            if any(left != right for left, right in expected):
                raise ConflictValidationError(
                    f"candidate lineage content mismatch: {reference.observation_id}"
                )
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or reference.raw_evidence_id not in raw_ids
                or reference.raw_evidence_id not in run.input_raw_evidence_references
                or reference.observation_id not in run.output_observation_ids
            ):
                raise ConflictValidationError(
                    f"broken candidate transformation lineage: {reference.observation_id}"
                )
            lineages_by_observation.setdefault(reference.observation_id, []).append(reference)
        representatives: dict[str, CanonicalObservation] = {}
        for (observation_id, _), (observation, _) in sorted(observations.items()):
            representatives.setdefault(observation_id, observation)
        for analysis in self.conflict_analyses:
            for candidate in analysis.candidates:
                observation = representatives.get(candidate.observation_id)
                if observation is None:
                    raise ConflictValidationError(
                        f"orphan candidate observation: {candidate.observation_id}"
                    )
                if canonical_json(candidate.value) != canonical_json(observation.value):
                    raise ConflictValidationError("candidate value replay mismatch")
                if (
                    candidate.provider != observation.provenance.provider
                    or candidate.source
                    != f"{observation.provenance.provider}::{observation.provenance.source_tool}"
                ):
                    raise ConflictValidationError("candidate source replay mismatch")
                if (
                    analysis.subject != observation.subject
                    or analysis.observation_kind is not observation.observation_kind
                    or analysis.dimension != observation_dimension(observation)
                ):
                    raise ConflictValidationError("candidate semantic field replay mismatch")
                expected_lineages = lineages_by_observation[candidate.observation_id]
                if {canonical_json(item) for item in expected_lineages} != {
                    canonical_json(item) for item in candidate.lineage_references
                }:
                    raise ConflictValidationError("candidate lineage replay mismatch")
        expected_coverage = coverage_from_records(
            bundle_count=len(fingerprints),
            analyses=self.conflict_analyses,
            attempts=self.resolution_attempts,
            diagnostics=self.diagnostics,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise ConflictValidationError("coverage replay mismatch")
        return self


def coverage_from_records(
    *,
    bundle_count: int,
    analyses: Sequence[ConflictAnalysisRecord],
    attempts: Sequence[ResolutionAttemptRecord],
    diagnostics: Sequence[ConflictDiagnostic],
) -> ConflictCoverageSummary:
    candidates = tuple(candidate for analysis in analyses for candidate in analysis.candidates)
    return ConflictCoverageSummary(
        source_bundle_count=bundle_count,
        source_evaluation_conflict_count=len(analyses),
        conflict_analysis_count=len(analyses),
        candidate_count=len(candidates),
        resolution_attempt_count=len(attempts),
        provider_count=len({item.provider for item in candidates}),
        source_count=len({item.source for item in candidates}),
        diagnostic_count=len(diagnostics),
        attempt_status_counts=dict(sorted(Counter(
            item.result_status for item in attempts
        ).items())),
    )


__all__ = (
    "CONFLICT_RESOLUTION_RULESET_VERSION",
    "ConflictResolutionRequest",
    "ConflictResolutionSnapshotV0_1",
    "ConflictCandidate",
    "ConflictAnalysisRecord",
    "ResolutionAttemptRecord",
    "ConflictCoverageSummary",
    "ConflictLineageReference",
    "ConflictDiagnostic",
)
