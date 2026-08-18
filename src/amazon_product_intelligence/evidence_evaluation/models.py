"""Immutable public data models for Evidence Evaluation V0.1."""

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
    ObservedAtStatus,
    ObservationKind,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    ProductKeywordRelationshipObservation,
    ReviewObservation,
    SemanticStatus,
    Severity,
    SubjectRef,
    ValueEnvelope,
    canonical_json,
    deterministic_id,
)

from .errors import EvidenceSerializationError, EvidenceValidationError


EVIDENCE_EVALUATION_RULESET_VERSION = "evidence-evaluation-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_LINEAGE_COMPLETE = "COMPLETE_LINEAGE"
_CONFLICT_PRESENT = "CONFLICT_PRESENT"


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise EvidenceValidationError(f"{path} must contain finite JSON data: {exc}") from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise EvidenceValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise EvidenceValidationError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise EvidenceValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise EvidenceValidationError(f"{path} must be {expected.__name__}")


def _mapping(value: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise EvidenceValidationError(f"{path} must be an object")
    if any(type(key) is not str for key in value):
        raise EvidenceValidationError(f"{path} keys must be strings")
    return _freeze_json(value, path)


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise EvidenceValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise EvidenceValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise EvidenceValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(
    value: Sequence[Any], expected: type, path: str, key
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise EvidenceValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise EvidenceValidationError(f"{path} contains duplicates")
    return ordered


def _enum_values(
    value: Sequence[Any], expected: type, path: str, *, allow_empty: bool = False
) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise EvidenceValidationError(f"{path} must not be empty")
    if any(not isinstance(item, expected) for item in values):
        raise EvidenceValidationError(f"{path} contains a wrong enum type")
    if len(set(values)) != len(values):
        raise EvidenceValidationError(f"{path} must contain unique values")
    return tuple(sorted(values, key=lambda item: item.value))


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def observed_value_identity(value: ValueEnvelope) -> str:
    """Return the comparable observed value without treating metadata as the value."""

    selected = value.normalized_value
    if selected is None:
        selected = value.raw_value
    return canonical_json({"value_type": value.value_type, "value": selected})


def qualitative_dimensions(
    records: Sequence[CanonicalObservation],
) -> dict[str, str]:
    """Evaluate the closed V0.1 qualitative dimensions for comparable records."""

    values = _tuple(records, "qualitative records")
    if not values or any(not isinstance(item, CanonicalObservation) for item in values):
        raise EvidenceValidationError("qualitative records must contain canonical observations")
    provider_count = len({item.provenance.provider for item in values})
    source_diversity = (
        "MULTI_PROVIDER_SUPPORT" if provider_count > 1 else "SINGLE_PROVIDER"
    )
    known_times = sum(
        item.time.observed_at_status is ObservedAtStatus.KNOWN for item in values
    )
    if known_times == len(values):
        observation_recency = "KNOWN_OBSERVATION_TIME"
    elif known_times == 0:
        observation_recency = "UNKNOWN_OBSERVATION_TIME"
    else:
        observation_recency = "MIXED_OBSERVATION_TIME"
    known_periods = sum(item.time.period_type is not PeriodType.UNKNOWN for item in values)
    if known_periods == len(values):
        period_status = "KNOWN_PERIOD"
    elif known_periods == 0:
        period_status = "UNKNOWN_PERIOD"
    else:
        period_status = "MIXED_PERIOD"
    present = tuple(
        item for item in values if item.value.presence_status is PresenceStatus.PRESENT
    )
    if len(present) == len(values):
        completeness = "ALL_VALUES_PRESENT"
    elif not present:
        completeness = "NO_PRESENT_VALUE"
    else:
        completeness = "MIXED_VALUE_PRESENCE"
    distinct_values = {observed_value_identity(item.value) for item in present}
    if not present:
        consistency = "NO_PRESENT_VALUE"
    elif len(distinct_values) > 1:
        consistency = _CONFLICT_PRESENT
    elif len(present) > 1:
        consistency = "SAME_VALUE"
    else:
        consistency = "SINGLE_VALUE"
    return {
        "source_diversity": source_diversity,
        "observation_recency": observation_recency,
        "period_status": period_status,
        "completeness": completeness,
        "lineage_completeness": _LINEAGE_COMPLETE,
        "consistency": consistency,
    }


class _EvidenceModel(JsonContract):
    """Strictly decode public models and translate contract errors."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except EvidenceSerializationError:
            raise
        except (EvidenceValidationError, ContractValidationError, TypeError, ValueError) as exc:
            raise EvidenceSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceLineageReference(_EvidenceModel):
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
            _text(getattr(self, name), f"EvidenceLineageReference.{name}")
        _instance(self.observation_kind, ObservationKind, "lineage observation_kind")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise EvidenceValidationError("lineage fingerprints must be lowercase SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceSupportRecord(_EvidenceModel):
    """Qualitative support inventory for one comparable semantic field."""

    support_record_id: str
    semantic_field_id: str
    subject: SubjectRef
    observation_kind: ObservationKind
    dimension: str
    supporting_observation_ids: tuple[str, ...]
    providers: tuple[str, ...]
    sources: tuple[str, ...]
    provider_count: int
    source_count: int
    lineage_completeness: str
    semantic_statuses: tuple[SemanticStatus, ...]
    presence_statuses: tuple[PresenceStatus, ...]
    lineage_references: tuple[EvidenceLineageReference, ...]

    def __post_init__(self) -> None:
        for name in ("support_record_id", "semantic_field_id", "dimension"):
            _text(getattr(self, name), f"EvidenceSupportRecord.{name}")
        _instance(self.subject, SubjectRef, "support subject")
        _instance(self.observation_kind, ObservationKind, "support observation_kind")
        observation_ids = _unique_texts(
            self.supporting_observation_ids,
            "support supporting_observation_ids",
            allow_empty=False,
        )
        providers = _unique_texts(self.providers, "support providers", allow_empty=False)
        sources = _unique_texts(self.sources, "support sources", allow_empty=False)
        _count(self.provider_count, "support provider_count")
        _count(self.source_count, "support source_count")
        if self.provider_count != len(providers) or self.source_count != len(sources):
            raise EvidenceValidationError("support provider/source counts do not match inventories")
        if self.lineage_completeness != _LINEAGE_COMPLETE:
            raise EvidenceValidationError("V0.1 support records require COMPLETE_LINEAGE")
        semantic_statuses = _enum_values(
            self.semantic_statuses, SemanticStatus, "support semantic_statuses"
        )
        presence_statuses = _enum_values(
            self.presence_statuses, PresenceStatus, "support presence_statuses"
        )
        lineages = _typed_unique(
            self.lineage_references,
            EvidenceLineageReference,
            "support lineage_references",
            canonical_json,
        )
        if not lineages or {item.observation_id for item in lineages} != set(observation_ids):
            raise EvidenceValidationError("support lineage does not match supporting observations")
        if {item.provider for item in lineages} != set(providers):
            raise EvidenceValidationError("support providers do not match lineage")
        expected_sources = {f"{item.provider}::{item.source_tool}" for item in lineages}
        if expected_sources != set(sources):
            raise EvidenceValidationError("support sources do not match lineage")
        object.__setattr__(self, "supporting_observation_ids", observation_ids)
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "semantic_statuses", semantic_statuses)
        object.__setattr__(self, "presence_statuses", presence_statuses)
        object.__setattr__(self, "lineage_references", lineages)
        if self.support_record_id != deterministic_id(
            "evidence-support", _without_id(self, "support_record_id")
        ):
            raise EvidenceValidationError("support_record_id does not match support content")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceConflictRecord(_EvidenceModel):
    """Unresolved disagreement between present values for one semantic field."""

    conflict_record_id: str
    support_record_id: str
    semantic_field_id: str
    subject: SubjectRef
    observation_kind: ObservationKind
    dimension: str
    candidate_observation_ids: tuple[str, ...]
    candidate_values: Mapping[str, ValueEnvelope]
    providers: tuple[str, ...]
    sources: tuple[str, ...]
    conflict_status: str
    lineage_references: tuple[EvidenceLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "conflict_record_id",
            "support_record_id",
            "semantic_field_id",
            "dimension",
        ):
            _text(getattr(self, name), f"EvidenceConflictRecord.{name}")
        _instance(self.subject, SubjectRef, "conflict subject")
        _instance(self.observation_kind, ObservationKind, "conflict observation_kind")
        candidate_ids = _unique_texts(
            self.candidate_observation_ids,
            "conflict candidate_observation_ids",
            allow_empty=False,
        )
        if len(candidate_ids) < 2:
            raise EvidenceValidationError("conflict requires at least two candidates")
        if not isinstance(self.candidate_values, MappingABC):
            raise EvidenceValidationError("conflict candidate_values must be an object")
        if set(self.candidate_values) != set(candidate_ids):
            raise EvidenceValidationError("conflict values do not match candidate observations")
        values: dict[str, ValueEnvelope] = {}
        for observation_id in sorted(self.candidate_values):
            value = self.candidate_values[observation_id]
            _instance(value, ValueEnvelope, "conflict candidate value")
            if value.presence_status is not PresenceStatus.PRESENT:
                raise EvidenceValidationError("conflict candidates must be PRESENT values")
            values[observation_id] = value
        if len({observed_value_identity(item) for item in values.values()}) < 2:
            raise EvidenceValidationError("conflict candidates must contain different observed values")
        providers = _unique_texts(self.providers, "conflict providers", allow_empty=False)
        sources = _unique_texts(self.sources, "conflict sources", allow_empty=False)
        if self.conflict_status != _CONFLICT_PRESENT:
            raise EvidenceValidationError("conflict_status must be CONFLICT_PRESENT")
        lineages = _typed_unique(
            self.lineage_references,
            EvidenceLineageReference,
            "conflict lineage_references",
            canonical_json,
        )
        if {item.observation_id for item in lineages} != set(candidate_ids):
            raise EvidenceValidationError("conflict lineage does not match candidates")
        if {item.provider for item in lineages} != set(providers):
            raise EvidenceValidationError("conflict providers do not match lineage")
        expected_sources = {f"{item.provider}::{item.source_tool}" for item in lineages}
        if expected_sources != set(sources):
            raise EvidenceValidationError("conflict sources do not match lineage")
        object.__setattr__(self, "candidate_observation_ids", candidate_ids)
        object.__setattr__(self, "candidate_values", MappingProxyType(values))
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "sources", sources)
        object.__setattr__(self, "lineage_references", lineages)
        if self.conflict_record_id != deterministic_id(
            "evidence-conflict", _without_id(self, "conflict_record_id")
        ):
            raise EvidenceValidationError("conflict_record_id does not match conflict content")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceQualityProfile(_EvidenceModel):
    """Closed qualitative attributes for one evidence support record."""

    profile_id: str
    support_record_id: str
    semantic_field_id: str
    source_diversity: str
    observation_recency: str
    period_status: str
    completeness: str
    lineage_completeness: str
    consistency: str
    qualitative_attributes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "profile_id",
            "support_record_id",
            "semantic_field_id",
            "source_diversity",
            "observation_recency",
            "period_status",
            "completeness",
            "lineage_completeness",
            "consistency",
        ):
            _text(getattr(self, name), f"EvidenceQualityProfile.{name}")
        allowed = {
            "source_diversity": {"SINGLE_PROVIDER", "MULTI_PROVIDER_SUPPORT"},
            "observation_recency": {
                "KNOWN_OBSERVATION_TIME",
                "UNKNOWN_OBSERVATION_TIME",
                "MIXED_OBSERVATION_TIME",
            },
            "period_status": {"KNOWN_PERIOD", "UNKNOWN_PERIOD", "MIXED_PERIOD"},
            "completeness": {
                "ALL_VALUES_PRESENT",
                "NO_PRESENT_VALUE",
                "MIXED_VALUE_PRESENCE",
            },
            "lineage_completeness": {_LINEAGE_COMPLETE},
            "consistency": {
                "SINGLE_VALUE",
                "SAME_VALUE",
                _CONFLICT_PRESENT,
                "NO_PRESENT_VALUE",
            },
        }
        for name, choices in allowed.items():
            if getattr(self, name) not in choices:
                raise EvidenceValidationError(f"invalid qualitative {name}")
        attributes = _unique_texts(
            self.qualitative_attributes,
            "quality profile qualitative_attributes",
            allow_empty=False,
        )
        expected = {
            self.source_diversity,
            self.observation_recency,
            self.period_status,
            self.completeness,
            self.lineage_completeness,
            self.consistency,
        }
        if set(attributes) != expected:
            raise EvidenceValidationError("qualitative_attributes do not match profile dimensions")
        object.__setattr__(self, "qualitative_attributes", attributes)
        if self.profile_id != deterministic_id(
            "evidence-quality-profile", _without_id(self, "profile_id")
        ):
            raise EvidenceValidationError("profile_id does not match profile content")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceDiagnostic(_EvidenceModel):
    """Deterministic non-conclusive explanation of evaluation state."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_support_record_ids: tuple[str, ...]
    related_conflict_record_ids: tuple[str, ...]
    related_observation_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "diagnostic id")
        _text(self.code, "diagnostic code")
        _instance(self.severity, Severity, "diagnostic severity")
        object.__setattr__(self, "related_support_record_ids", _unique_texts(
            self.related_support_record_ids, "diagnostic related support IDs"
        ))
        object.__setattr__(self, "related_conflict_record_ids", _unique_texts(
            self.related_conflict_record_ids, "diagnostic related conflict IDs"
        ))
        object.__setattr__(self, "related_observation_ids", _unique_texts(
            self.related_observation_ids, "diagnostic related observation IDs"
        ))
        _text(self.message, "diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "evidence-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise EvidenceValidationError("diagnostic_id does not match diagnostic content")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceCoverageSummary(_EvidenceModel):
    """Descriptive counts only; no quality weight, confidence, or conclusion."""

    source_bundle_count: int
    canonical_observation_count: int
    support_record_count: int
    conflict_record_count: int
    quality_profile_count: int
    provider_count: int
    source_count: int
    complete_lineage_record_count: int
    single_provider_support_count: int
    multi_provider_support_count: int
    known_observation_time_profile_count: int
    unknown_observation_time_profile_count: int
    unknown_period_profile_count: int
    conflict_profile_count: int
    present_observation_count: int
    non_present_observation_count: int
    quality_issue_count: int
    diagnostic_count: int
    observation_kind_counts: Mapping[str, int]
    semantic_status_counts: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count",
            "canonical_observation_count",
            "support_record_count",
            "conflict_record_count",
            "quality_profile_count",
            "provider_count",
            "source_count",
            "complete_lineage_record_count",
            "single_provider_support_count",
            "multi_provider_support_count",
            "known_observation_time_profile_count",
            "unknown_observation_time_profile_count",
            "unknown_period_profile_count",
            "conflict_profile_count",
            "present_observation_count",
            "non_present_observation_count",
            "quality_issue_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"EvidenceCoverageSummary.{name}")
        for name in ("observation_kind_counts", "semantic_status_counts"):
            value = _mapping(getattr(self, name), f"EvidenceCoverageSummary.{name}")
            if any(type(item) is not int or item < 0 for item in value.values()):
                raise EvidenceValidationError(f"{name} values must be non-negative integers")
            object.__setattr__(self, name, value)


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    """Return an order-insensitive stable SHA-256 identity for a canonical bundle."""

    payload = bundle.to_dict()
    for key, value in tuple(payload.items()):
        if isinstance(value, list):
            payload[key] = sorted(value, key=canonical_json)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def observation_revision_content(observation: CanonicalObservation) -> dict[str, Any]:
    """Return observation content excluding revision and emission metadata."""

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
    """Return the provider-neutral field name used by V0.1 evaluation."""

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
    raise EvidenceValidationError(
        f"unsupported canonical observation type: {type(observation).__name__}"
    )


def semantic_field_material(observation: CanonicalObservation) -> dict[str, Any]:
    """Return the conservative comparability key for one canonical observation."""

    dimension = observation_dimension(observation)
    time_context = {
        "observed_at": observation.time.observed_at,
        "observed_at_status": observation.time.observed_at_status,
        "period_start": observation.time.period_start,
        "period_end": observation.time.period_end,
        "period_type": observation.time.period_type,
        "timezone": observation.time.timezone,
    }
    material: dict[str, Any] = {
        "subject": observation.subject,
        "observation_kind": observation.observation_kind,
        "dimension": dimension,
        "scope": observation.scope,
        "time_context": time_context,
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
        # A parent may have many children.  A different child is another fact,
        # not a competing truth value for a single-valued field.
        material["relationship_value"] = observation.value.normalized_value
    return material


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceEvaluationRequest(_EvidenceModel):
    """Strict immutable request containing canonical bundles only."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "request canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise EvidenceValidationError(
                "canonical_bundles must contain one or more CanonicalEvidenceBundle values"
            )
        fingerprinted: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise EvidenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprinted.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprinted}) != len(fingerprinted):
            raise EvidenceValidationError("duplicate canonical bundle fingerprint")
        object.__setattr__(
            self,
            "canonical_bundles",
            tuple(bundle for _, bundle in sorted(fingerprinted, key=lambda item: item[0])),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceEvaluationSnapshotV0_1(_EvidenceModel):
    """Deterministic qualitative evaluation of canonical evidence properties."""

    snapshot_id: str
    ruleset_version: str
    source_bundle_fingerprints: tuple[str, ...]
    evidence_quality_profiles: tuple[EvidenceQualityProfile, ...]
    support_records: tuple[EvidenceSupportRecord, ...]
    conflict_records: tuple[EvidenceConflictRecord, ...]
    coverage: EvidenceCoverageSummary
    diagnostics: tuple[EvidenceDiagnostic, ...]
    lineage_index: tuple[EvidenceLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot id")
        if self.ruleset_version != EVIDENCE_EVALUATION_RULESET_VERSION:
            raise EvidenceValidationError("invalid Evidence Evaluation ruleset version")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "snapshot source fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise EvidenceValidationError("snapshot fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        sequences = (
            (
                "evidence_quality_profiles",
                EvidenceQualityProfile,
                lambda item: item.profile_id,
            ),
            ("support_records", EvidenceSupportRecord, lambda item: item.support_record_id),
            (
                "conflict_records",
                EvidenceConflictRecord,
                lambda item: item.conflict_record_id,
            ),
            ("diagnostics", EvidenceDiagnostic, lambda item: item.diagnostic_id),
            ("lineage_index", EvidenceLineageReference, canonical_json),
        )
        for name, expected, key in sequences:
            object.__setattr__(self, name, _typed_unique(
                getattr(self, name), expected, f"snapshot {name}", key
            ))
        _instance(self.coverage, EvidenceCoverageSummary, "snapshot coverage")
        support_by_id = {item.support_record_id: item for item in self.support_records}
        if len({item.semantic_field_id for item in self.support_records}) != len(self.support_records):
            raise EvidenceValidationError("snapshot contains duplicate semantic fields")
        if {item.support_record_id for item in self.evidence_quality_profiles} != set(support_by_id):
            raise EvidenceValidationError("quality profiles must cover every support record once")
        for profile in self.evidence_quality_profiles:
            support = support_by_id[profile.support_record_id]
            if profile.semantic_field_id != support.semantic_field_id:
                raise EvidenceValidationError("quality profile semantic field mismatch")
        conflict_support_ids: set[str] = set()
        for conflict in self.conflict_records:
            support = support_by_id.get(conflict.support_record_id)
            if support is None:
                raise EvidenceValidationError("conflict references an absent support record")
            if conflict.support_record_id in conflict_support_ids:
                raise EvidenceValidationError("support record has duplicate conflict records")
            conflict_support_ids.add(conflict.support_record_id)
            if (
                conflict.semantic_field_id != support.semantic_field_id
                or conflict.subject != support.subject
                or conflict.observation_kind is not support.observation_kind
                or conflict.dimension != support.dimension
            ):
                raise EvidenceValidationError("conflict semantic field does not match support")
            if not set(conflict.candidate_observation_ids) <= set(
                support.supporting_observation_ids
            ):
                raise EvidenceValidationError("conflict candidates are absent from support")
        conflict_profiles = {
            item.support_record_id
            for item in self.evidence_quality_profiles
            if item.consistency == _CONFLICT_PRESENT
        }
        if conflict_profiles != conflict_support_ids:
            raise EvidenceValidationError("conflict profiles and conflict records do not match")
        lineage_ids = {item.observation_id for item in self.lineage_index}
        required_ids = {
            observation_id
            for support in self.support_records
            for observation_id in support.supporting_observation_ids
        }
        if lineage_ids != required_ids:
            raise EvidenceValidationError("snapshot lineage must cover all evaluated observations")
        profile_by_support = {
            item.support_record_id: item for item in self.evidence_quality_profiles
        }
        support_ids = set(support_by_id)
        conflict_ids = {item.conflict_record_id for item in self.conflict_records}
        for diagnostic in self.diagnostics:
            if not set(diagnostic.related_support_record_ids) <= support_ids:
                raise EvidenceValidationError("diagnostic references an absent support record")
            if not set(diagnostic.related_conflict_record_ids) <= conflict_ids:
                raise EvidenceValidationError("diagnostic references an absent conflict record")
            if not set(diagnostic.related_observation_ids) <= required_ids:
                raise EvidenceValidationError("diagnostic references an absent observation")
        checks = (
            (
                self.coverage.source_bundle_count,
                len(self.source_bundle_fingerprints),
                "source bundle",
            ),
            (self.coverage.canonical_observation_count, len(required_ids), "observation"),
            (self.coverage.support_record_count, len(self.support_records), "support record"),
            (self.coverage.conflict_record_count, len(self.conflict_records), "conflict record"),
            (
                self.coverage.quality_profile_count,
                len(self.evidence_quality_profiles),
                "quality profile",
            ),
            (
                self.coverage.complete_lineage_record_count,
                len(self.support_records),
                "complete lineage",
            ),
            (
                self.coverage.provider_count,
                len({item.provider for item in self.lineage_index}),
                "provider",
            ),
            (
                self.coverage.source_count,
                len({f"{item.provider}::{item.source_tool}" for item in self.lineage_index}),
                "source",
            ),
            (
                self.coverage.single_provider_support_count,
                sum(
                    item.source_diversity == "SINGLE_PROVIDER"
                    for item in profile_by_support.values()
                ),
                "single provider support",
            ),
            (
                self.coverage.multi_provider_support_count,
                sum(
                    item.source_diversity == "MULTI_PROVIDER_SUPPORT"
                    for item in profile_by_support.values()
                ),
                "multi provider support",
            ),
            (
                self.coverage.known_observation_time_profile_count,
                sum(
                    item.observation_recency == "KNOWN_OBSERVATION_TIME"
                    for item in profile_by_support.values()
                ),
                "known observation time",
            ),
            (
                self.coverage.unknown_observation_time_profile_count,
                sum(
                    item.observation_recency == "UNKNOWN_OBSERVATION_TIME"
                    for item in profile_by_support.values()
                ),
                "unknown observation time",
            ),
            (
                self.coverage.unknown_period_profile_count,
                sum(
                    item.period_status == "UNKNOWN_PERIOD"
                    for item in profile_by_support.values()
                ),
                "unknown period",
            ),
            (
                self.coverage.conflict_profile_count,
                len(conflict_profiles),
                "conflict profile",
            ),
            (self.coverage.diagnostic_count, len(self.diagnostics), "diagnostic"),
        )
        mismatch = next((label for left, right, label in checks if left != right), None)
        if mismatch is not None:
            raise EvidenceValidationError(f"coverage {mismatch} count mismatch")
        expected_id = deterministic_id("evidence-evaluation-snapshot", _without_id(
            self, "snapshot_id"
        ))
        if self.snapshot_id != expected_id:
            raise EvidenceSerializationError("snapshot_id does not match snapshot content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        """Replay evaluation records through canonical transformation lineage."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise EvidenceValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[tuple[str, str], tuple[CanonicalObservation, set[str]]] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, tuple[Any, set[str]]] = {}
        issues: dict[str, str] = {}
        generic: dict[tuple[str, str], str] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise EvidenceValidationError("against-bundles input contains a wrong type")
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise EvidenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise EvidenceValidationError("duplicate canonical bundle fingerprint")
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current and canonical_json(current[0]) != canonical_json(run):
                    raise EvidenceValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    runs[run.transformation_run_id] = (run, {fingerprint})
            for observation in bundle.observations:
                content = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != content:
                    raise EvidenceValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = content
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                current = observations.get(key)
                if current and canonical_json(current[0]) != canonical_json(observation):
                    raise EvidenceValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    observations[key] = (observation, {fingerprint})
            for issue in bundle.quality_issues:
                content = canonical_json(issue)
                if issue.issue_id in issues and issues[issue.issue_id] != content:
                    raise EvidenceValidationError(
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
                        raise EvidenceValidationError(f"{kind} identity collision: {identity}")
                    generic[key] = content
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise EvidenceValidationError(
                "snapshot source bundle fingerprints do not match supplied bundles"
            )
        expected_lineage_keys = set(observations)
        actual_lineage_keys = {
            (item.observation_id, item.transformation_run_id) for item in self.lineage_index
        }
        if expected_lineage_keys != actual_lineage_keys:
            raise EvidenceValidationError("lineage index does not match canonical observation emissions")
        lineage_by_observation: dict[str, list[EvidenceLineageReference]] = {}
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            entry = observations.get(key)
            if entry is None:
                raise EvidenceValidationError(f"orphan canonical lineage: {reference.observation_id}")
            observation, source_fingerprints = entry
            transformation = observation.provenance.transformation
            run_entry = runs.get(reference.transformation_run_id)
            if run_entry is None:
                raise EvidenceValidationError(
                    f"orphan transformation run: {reference.transformation_run_id}"
                )
            run = run_entry[0]
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
                raise EvidenceValidationError(
                    f"lineage content mismatch: {reference.observation_id}"
                )
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or reference.raw_evidence_id not in raw_ids
                or reference.raw_evidence_id not in run.input_raw_evidence_references
                or reference.observation_id not in run.output_observation_ids
            ):
                raise EvidenceValidationError(
                    f"broken transformation lineage: {reference.observation_id}"
                )
            lineage_by_observation.setdefault(reference.observation_id, []).append(reference)
        representatives: dict[str, CanonicalObservation] = {}
        for (observation_id, _), (observation, _) in sorted(observations.items()):
            representatives.setdefault(observation_id, observation)
        profiles = {item.support_record_id: item for item in self.evidence_quality_profiles}
        conflict_by_support = {item.support_record_id: item for item in self.conflict_records}
        for support in self.support_records:
            records: list[CanonicalObservation] = []
            expected_lineages: list[EvidenceLineageReference] = []
            for observation_id in support.supporting_observation_ids:
                observation = representatives.get(observation_id)
                if observation is None:
                    raise EvidenceValidationError(f"orphan support observation: {observation_id}")
                records.append(observation)
                expected_lineages.extend(lineage_by_observation[observation_id])
            field_materials = {canonical_json(semantic_field_material(item)) for item in records}
            if len(field_materials) != 1:
                raise EvidenceValidationError("support combines non-comparable semantic fields")
            expected_field_id = deterministic_id("evidence-field", semantic_field_material(records[0]))
            if (
                support.semantic_field_id != expected_field_id
                or support.subject != records[0].subject
                or support.observation_kind is not records[0].observation_kind
                or support.dimension != observation_dimension(records[0])
            ):
                raise EvidenceValidationError("support semantic field replay mismatch")
            if {canonical_json(item) for item in support.lineage_references} != {
                canonical_json(item) for item in expected_lineages
            }:
                raise EvidenceValidationError("support lineage replay mismatch")
            if {item.provenance.provider for item in records} != set(support.providers):
                raise EvidenceValidationError("support provider replay mismatch")
            if {item.value.semantic_status for item in records} != set(
                support.semantic_statuses
            ):
                raise EvidenceValidationError("support semantic status replay mismatch")
            if {item.value.presence_status for item in records} != set(
                support.presence_statuses
            ):
                raise EvidenceValidationError("support presence status replay mismatch")
            profile = profiles[support.support_record_id]
            conflict = conflict_by_support.get(support.support_record_id)
            present_records = [
                item for item in records if item.value.presence_status is PresenceStatus.PRESENT
            ]
            value_count = len({observed_value_identity(item.value) for item in present_records})
            if (profile.consistency == _CONFLICT_PRESENT) != (value_count > 1):
                raise EvidenceValidationError("quality consistency replay mismatch")
            expected_dimensions = qualitative_dimensions(records)
            if any(
                getattr(profile, name) != value
                for name, value in expected_dimensions.items()
            ):
                raise EvidenceValidationError("quality profile replay mismatch")
            if conflict is not None:
                if set(conflict.candidate_observation_ids) != {
                    item.observation_id for item in present_records
                }:
                    raise EvidenceValidationError("conflict candidate replay mismatch")
                for observation_id, value in conflict.candidate_values.items():
                    if canonical_json(value) != canonical_json(representatives[observation_id].value):
                        raise EvidenceValidationError("conflict value replay mismatch")
        expected_coverage = coverage_from_records(
            bundle_count=len(fingerprints),
            observations=tuple(representatives.values()),
            profiles=self.evidence_quality_profiles,
            supports=self.support_records,
            conflicts=self.conflict_records,
            quality_issue_count=len(issues),
            diagnostics=self.diagnostics,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise EvidenceValidationError("coverage replay mismatch")
        return self


def coverage_from_records(
    *,
    bundle_count: int,
    observations: Sequence[CanonicalObservation],
    profiles: Sequence[EvidenceQualityProfile],
    supports: Sequence[EvidenceSupportRecord],
    conflicts: Sequence[EvidenceConflictRecord],
    quality_issue_count: int,
    diagnostics: Sequence[EvidenceDiagnostic],
) -> EvidenceCoverageSummary:
    """Build the deterministic descriptive coverage inventory."""

    return EvidenceCoverageSummary(
        source_bundle_count=bundle_count,
        canonical_observation_count=len(observations),
        support_record_count=len(supports),
        conflict_record_count=len(conflicts),
        quality_profile_count=len(profiles),
        provider_count=len({item.provenance.provider for item in observations}),
        source_count=len({
            f"{item.provenance.provider}::{item.provenance.source_tool}"
            for item in observations
        }),
        complete_lineage_record_count=sum(
            item.lineage_completeness == _LINEAGE_COMPLETE for item in supports
        ),
        single_provider_support_count=sum(
            item.source_diversity == "SINGLE_PROVIDER" for item in profiles
        ),
        multi_provider_support_count=sum(
            item.source_diversity == "MULTI_PROVIDER_SUPPORT" for item in profiles
        ),
        known_observation_time_profile_count=sum(
            item.observation_recency == "KNOWN_OBSERVATION_TIME" for item in profiles
        ),
        unknown_observation_time_profile_count=sum(
            item.observation_recency == "UNKNOWN_OBSERVATION_TIME" for item in profiles
        ),
        unknown_period_profile_count=sum(
            item.period_status == "UNKNOWN_PERIOD" for item in profiles
        ),
        conflict_profile_count=sum(
            item.consistency == _CONFLICT_PRESENT for item in profiles
        ),
        present_observation_count=sum(
            item.value.presence_status is PresenceStatus.PRESENT for item in observations
        ),
        non_present_observation_count=sum(
            item.value.presence_status is not PresenceStatus.PRESENT for item in observations
        ),
        quality_issue_count=quality_issue_count,
        diagnostic_count=len(diagnostics),
        observation_kind_counts=dict(sorted(Counter(
            item.observation_kind.value for item in observations
        ).items())),
        semantic_status_counts=dict(sorted(Counter(
            item.value.semantic_status.value for item in observations
        ).items())),
    )


__all__ = (
    "EVIDENCE_EVALUATION_RULESET_VERSION",
    "EvidenceEvaluationRequest",
    "EvidenceEvaluationSnapshotV0_1",
    "EvidenceQualityProfile",
    "EvidenceSupportRecord",
    "EvidenceConflictRecord",
    "EvidenceCoverageSummary",
    "EvidenceLineageReference",
    "EvidenceDiagnostic",
)
