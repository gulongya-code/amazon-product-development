"""Immutable public data models for Demand Intelligence V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    Channel,
    ContractValidationError,
    DirectionalQueryExecutionRecord,
    EstimateMethodStatus,
    EvidenceType,
    JsonContract,
    KeywordIdentity,
    NormalizationStatus,
    ObservationKind,
    ObservedAtStatus,
    PeriodType,
    PresenceStatus,
    ProductIdentity,
    Provenance,
    QueryExecutionOutcome,
    RelationshipDirection,
    RelationshipType,
    ResultStatus,
    Scope,
    SemanticStatus,
    Severity,
    TimeWindow,
    Unit,
    ValueEnvelope,
    canonical_json,
    deterministic_id,
)

from .errors import DemandIntelligenceValidationError, DemandSerializationError


DEMAND_INTELLIGENCE_RULESET_VERSION = "demand-intelligence-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MetricCandidateState(StrEnum):
    """Structural state of an unresolved keyword-metric candidate set."""

    NO_PRESENT_CANDIDATE = "NO_PRESENT_CANDIDATE"
    ONE_DISTINCT_PRESENT_VALUE = "ONE_DISTINCT_PRESENT_VALUE"
    MULTIPLE_DISTINCT_PRESENT_VALUES = "MULTIPLE_DISTINCT_PRESENT_VALUES"


class DemandSourceRecordType(StrEnum):
    """Canonical record kinds that can anchor replayable demand lineage."""

    KEYWORD_METRIC_OBSERVATION = "KEYWORD_METRIC_OBSERVATION"
    PRODUCT_KEYWORD_RELATIONSHIP_OBSERVATION = "PRODUCT_KEYWORD_RELATIONSHIP_OBSERVATION"
    DIRECTIONAL_QUERY_EXECUTION_RECORD = "DIRECTIONAL_QUERY_EXECUTION_RECORD"
    OUT_OF_SCOPE_OBSERVATION = "OUT_OF_SCOPE_OBSERVATION"


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise DemandIntelligenceValidationError(
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
        raise DemandIntelligenceValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise DemandIntelligenceValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise DemandIntelligenceValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise DemandIntelligenceValidationError(f"{path} must be {expected.__name__}")


def _mapping(value: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise DemandIntelligenceValidationError(f"{path} must be an object")
    if any(type(key) is not str for key in value):
        raise DemandIntelligenceValidationError(f"{path} keys must be strings")
    return _freeze_json(value, path)


def _unique_texts(value: Sequence[str], path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise DemandIntelligenceValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item for item in values):
        raise DemandIntelligenceValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise DemandIntelligenceValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def _present_material(candidate: "KeywordMetricCandidate") -> str | None:
    if candidate.value.presence_status is not PresenceStatus.PRESENT:
        return None
    return canonical_json(
        {
            "raw_value": candidate.value.raw_value,
            "normalized_value": candidate.value.normalized_value,
            "unit": candidate.value.unit,
            "range": candidate.range,
        }
    )


class _DemandModel(JsonContract):
    """Strictly decode public models while translating contract errors."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except DemandSerializationError:
            raise
        except (DemandIntelligenceValidationError, ContractValidationError, TypeError, ValueError) as exc:
            raise DemandSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandLineageReference(_DemandModel):
    """Replayable canonical record-to-collection lineage."""

    source_record_id: str
    source_record_type: DemandSourceRecordType
    semantic_observation_id: str | None
    observation_kind: ObservationKind | None
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
            "source_record_id",
            "transformation_run_id",
            "mapping_version",
            "raw_evidence_id",
            "collection_run_id",
            "provider",
            "source_tool",
            "source_field",
        ):
            _text(getattr(self, name), f"DemandLineageReference.{name}")
        _instance(self.source_record_type, DemandSourceRecordType, "lineage source_record_type")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "DemandLineageReference.source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise DemandIntelligenceValidationError("lineage fingerprints must be lowercase SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        if self.source_record_type is DemandSourceRecordType.DIRECTIONAL_QUERY_EXECUTION_RECORD:
            if self.semantic_observation_id is not None or self.observation_kind is not None:
                raise DemandIntelligenceValidationError(
                    "query execution lineage cannot claim observation semantics"
                )
        else:
            _text(self.semantic_observation_id, "lineage semantic_observation_id")
            _instance(self.observation_kind, ObservationKind, "lineage observation_kind")


@dataclass(frozen=True, slots=True, kw_only=True)
class KeywordMetricCandidate(_DemandModel):
    """One unresolved canonical keyword-metric candidate."""

    observation_id: str
    semantic_observation_id: str
    keyword_identity: KeywordIdentity
    metric: str
    metric_semantic: str | None
    estimate_method_status: EstimateMethodStatus
    range: Mapping[str, Any] | None
    evidence_type: EvidenceType
    value: ValueEnvelope
    scope: Scope
    time: TimeWindow
    provider_semantic: str | None
    result_status: ResultStatus
    provider: str
    source_tool: str
    lineage_references: tuple[DemandLineageReference, ...]

    def __post_init__(self) -> None:
        for name in ("observation_id", "semantic_observation_id", "metric", "provider", "source_tool"):
            _text(getattr(self, name), f"KeywordMetricCandidate.{name}")
        _instance(self.keyword_identity, KeywordIdentity, "candidate keyword_identity")
        _instance(self.estimate_method_status, EstimateMethodStatus, "candidate estimate_method_status")
        _instance(self.evidence_type, EvidenceType, "candidate evidence_type")
        _instance(self.value, ValueEnvelope, "candidate value")
        _instance(self.scope, Scope, "candidate scope")
        _instance(self.time, TimeWindow, "candidate time")
        _instance(self.result_status, ResultStatus, "candidate result_status")
        _optional_text(self.metric_semantic, "candidate metric_semantic")
        _optional_text(self.provider_semantic, "candidate provider_semantic")
        if self.range is not None:
            object.__setattr__(self, "range", _mapping(self.range, "candidate range"))
        lineages = _tuple(self.lineage_references, "candidate lineage_references")
        if not lineages or any(not isinstance(item, DemandLineageReference) for item in lineages):
            raise DemandIntelligenceValidationError("keyword metric candidate requires lineage")
        if any(
            item.source_record_id != self.observation_id
            or item.source_record_type is not DemandSourceRecordType.KEYWORD_METRIC_OBSERVATION
            or item.semantic_observation_id != self.semantic_observation_id
            or item.observation_kind is not ObservationKind.KEYWORD_METRIC
            or item.provider != self.provider
            or item.source_tool != self.source_tool
            for item in lineages
        ):
            raise DemandIntelligenceValidationError("keyword metric candidate lineage mismatch")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class KeywordMetricEvidenceSet(_DemandModel):
    """Candidates sharing the complete non-resolving metric boundary."""

    metric_evidence_set_id: str
    keyword_identity: KeywordIdentity
    metric: str
    metric_semantic: str | None
    unit: Unit | None
    period_type: PeriodType
    period_start: str | None
    period_end: str | None
    observed_at_status: ObservedAtStatus
    timezone: str | None
    scope: Scope
    evidence_type: EvidenceType
    provider_semantic: str | None
    candidate_state: MetricCandidateState
    distinct_present_value_count: int
    candidate_count: int
    presence_counts: Mapping[str, int]
    candidates: tuple[KeywordMetricCandidate, ...]

    def __post_init__(self) -> None:
        _text(self.metric_evidence_set_id, "metric evidence set id")
        _instance(self.keyword_identity, KeywordIdentity, "metric set keyword_identity")
        _text(self.metric, "metric set metric")
        _optional_text(self.metric_semantic, "metric set metric_semantic")
        if self.unit is not None:
            _instance(self.unit, Unit, "metric set unit")
        _instance(self.period_type, PeriodType, "metric set period_type")
        _instance(self.observed_at_status, ObservedAtStatus, "metric set observed_at_status")
        _instance(self.scope, Scope, "metric set scope")
        _instance(self.evidence_type, EvidenceType, "metric set evidence_type")
        _optional_text(self.provider_semantic, "metric set provider_semantic")
        _instance(self.candidate_state, MetricCandidateState, "metric set candidate_state")
        _count(self.distinct_present_value_count, "metric set distinct_present_value_count")
        _count(self.candidate_count, "metric set candidate_count")
        counts = _mapping(self.presence_counts, "metric set presence_counts")
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise DemandIntelligenceValidationError("metric presence counts must be non-negative integers")
        object.__setattr__(self, "presence_counts", counts)
        candidates = _tuple(self.candidates, "metric set candidates")
        if not candidates or len(candidates) != self.candidate_count:
            raise DemandIntelligenceValidationError("metric candidate_count does not match candidates")
        if any(not isinstance(item, KeywordMetricCandidate) for item in candidates):
            raise DemandIntelligenceValidationError("metric set contains a wrong candidate type")
        boundary = (
            "keyword_identity", "metric", "metric_semantic", "scope", "evidence_type", "provider_semantic"
        )
        if any(any(getattr(item, name) != getattr(self, name) for name in boundary) for item in candidates):
            raise DemandIntelligenceValidationError("metric candidate semantic boundary mismatch")
        if any(
            item.value.unit != self.unit
            or item.time.period_type is not self.period_type
            or item.time.period_start != self.period_start
            or item.time.period_end != self.period_end
            or item.time.observed_at_status is not self.observed_at_status
            or item.time.timezone != self.timezone
            for item in candidates
        ):
            raise DemandIntelligenceValidationError("metric candidate unit or period boundary mismatch")
        expected_counts = {
            status.value: sum(item.value.presence_status is status for item in candidates)
            for status in PresenceStatus
            if any(item.value.presence_status is status for item in candidates)
        }
        present_values = {material for item in candidates if (material := _present_material(item)) is not None}
        expected_state = (
            MetricCandidateState.NO_PRESENT_CANDIDATE
            if not present_values
            else MetricCandidateState.ONE_DISTINCT_PRESENT_VALUE
            if len(present_values) == 1
            else MetricCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES
        )
        if dict(counts) != expected_counts:
            raise DemandIntelligenceValidationError("metric presence counts do not match candidates")
        if self.distinct_present_value_count != len(present_values) or self.candidate_state is not expected_state:
            raise DemandIntelligenceValidationError("metric candidate state does not match candidates")
        object.__setattr__(self, "candidates", tuple(sorted(candidates, key=lambda item: item.observation_id)))
        if self.metric_evidence_set_id != deterministic_id(
            "demand-metric-set", _without_id(self, "metric_evidence_set_id")
        ):
            raise DemandIntelligenceValidationError("metric_evidence_set_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationshipEvidenceItem(_DemandModel):
    """One canonical directional, channel-specific product-keyword relationship."""

    observation_id: str
    semantic_observation_id: str
    relationship_id: str
    product_identity: ProductIdentity
    keyword_identity: KeywordIdentity
    direction: RelationshipDirection
    relationship_type: RelationshipType
    channel: Channel
    query_result_status: ResultStatus
    rank: Mapping[str, Any] | None
    traffic: ValueEnvelope | None
    evidence_type: EvidenceType
    value: ValueEnvelope
    scope: Scope
    time: TimeWindow
    result_status: ResultStatus
    provider_semantic: str | None
    provider: str
    source_tool: str
    lineage_references: tuple[DemandLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "observation_id", "semantic_observation_id", "relationship_id", "provider", "source_tool"
        ):
            _text(getattr(self, name), f"RelationshipEvidenceItem.{name}")
        _instance(self.product_identity, ProductIdentity, "relationship product_identity")
        _instance(self.keyword_identity, KeywordIdentity, "relationship keyword_identity")
        _instance(self.direction, RelationshipDirection, "relationship direction")
        _instance(self.relationship_type, RelationshipType, "relationship relationship_type")
        _instance(self.channel, Channel, "relationship channel")
        _instance(self.query_result_status, ResultStatus, "relationship query_result_status")
        _instance(self.evidence_type, EvidenceType, "relationship evidence_type")
        _instance(self.value, ValueEnvelope, "relationship value")
        _instance(self.scope, Scope, "relationship scope")
        _instance(self.time, TimeWindow, "relationship time")
        _instance(self.result_status, ResultStatus, "relationship result_status")
        _optional_text(self.provider_semantic, "relationship provider_semantic")
        if self.rank is not None:
            object.__setattr__(self, "rank", _mapping(self.rank, "relationship rank"))
        if self.traffic is not None:
            _instance(self.traffic, ValueEnvelope, "relationship traffic")
        lineages = _tuple(self.lineage_references, "relationship lineage_references")
        if not lineages or any(not isinstance(item, DemandLineageReference) for item in lineages):
            raise DemandIntelligenceValidationError("relationship evidence requires lineage")
        if any(
            item.source_record_id != self.observation_id
            or item.source_record_type
            is not DemandSourceRecordType.PRODUCT_KEYWORD_RELATIONSHIP_OBSERVATION
            or item.semantic_observation_id != self.semantic_observation_id
            or item.observation_kind is not ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP
            or item.provider != self.provider
            or item.source_tool != self.source_tool
            for item in lineages
        ):
            raise DemandIntelligenceValidationError("relationship evidence lineage mismatch")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class RelationshipEvidenceGroup(_DemandModel):
    """Relationship records separated by direction and channel without aggregation."""

    relationship_group_id: str
    keyword_identity: KeywordIdentity
    direction: RelationshipDirection
    channel: Channel
    records: tuple[RelationshipEvidenceItem, ...]

    def __post_init__(self) -> None:
        _text(self.relationship_group_id, "relationship group id")
        _instance(self.keyword_identity, KeywordIdentity, "relationship group keyword_identity")
        _instance(self.direction, RelationshipDirection, "relationship group direction")
        _instance(self.channel, Channel, "relationship group channel")
        records = _tuple(self.records, "relationship group records")
        if not records or any(not isinstance(item, RelationshipEvidenceItem) for item in records):
            raise DemandIntelligenceValidationError("relationship group requires evidence records")
        if any(
            item.keyword_identity != self.keyword_identity
            or item.direction is not self.direction
            or item.channel is not self.channel
            for item in records
        ):
            raise DemandIntelligenceValidationError("relationship group boundary mismatch")
        if len({item.observation_id for item in records}) != len(records):
            raise DemandIntelligenceValidationError("relationship group contains duplicate observations")
        object.__setattr__(self, "records", tuple(sorted(records, key=lambda item: item.observation_id)))
        if self.relationship_group_id != deterministic_id(
            "demand-relationship-group", _without_id(self, "relationship_group_id")
        ):
            raise DemandIntelligenceValidationError("relationship_group_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class QueryExecutionEvidenceItem(_DemandModel):
    """One consumed canonical directional query execution record."""

    query_execution_id: str
    query_keyword: KeywordIdentity | None
    query_product: ProductIdentity | None
    direction: RelationshipDirection
    outcome: QueryExecutionOutcome
    related_relationship_observation_ids: tuple[str, ...]
    target_related_relationship_observation_ids: tuple[str, ...]
    provenance: Provenance
    quality_issue_ids: tuple[str, ...]
    lineage_references: tuple[DemandLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.query_execution_id, "query execution id")
        _instance(self.direction, RelationshipDirection, "query execution direction")
        _instance(self.outcome, QueryExecutionOutcome, "query execution outcome")
        _instance(self.provenance, Provenance, "query execution provenance")
        related = _unique_texts(
            self.related_relationship_observation_ids, "query related relationship ids"
        )
        target_related = _unique_texts(
            self.target_related_relationship_observation_ids, "query target relationship ids"
        )
        issues = _unique_texts(self.quality_issue_ids, "query quality issue ids")
        if self.direction is RelationshipDirection.KEYWORD_TO_PRODUCT:
            _instance(self.query_keyword, KeywordIdentity, "forward query keyword")
            if self.query_product is not None:
                raise DemandIntelligenceValidationError("forward query cannot contain query_product")
        else:
            _instance(self.query_product, ProductIdentity, "reverse query product")
            if self.query_keyword is not None:
                raise DemandIntelligenceValidationError("reverse query cannot contain query_keyword")
            if not target_related:
                raise DemandIntelligenceValidationError(
                    "reverse query evidence requires an observed product-to-target association"
                )
        if self.outcome is QueryExecutionOutcome.RESULTS_RETURNED:
            if not related:
                raise DemandIntelligenceValidationError("RESULTS_RETURNED requires relationship observations")
        elif related:
            raise DemandIntelligenceValidationError(f"{self.outcome.value} cannot contain relationship results")
        object.__setattr__(self, "related_relationship_observation_ids", related)
        object.__setattr__(self, "target_related_relationship_observation_ids", target_related)
        object.__setattr__(self, "quality_issue_ids", issues)
        lineages = _tuple(self.lineage_references, "query lineage_references")
        if not lineages or any(not isinstance(item, DemandLineageReference) for item in lineages):
            raise DemandIntelligenceValidationError("query execution evidence requires lineage")
        if any(
            item.source_record_id != self.query_execution_id
            or item.source_record_type is not DemandSourceRecordType.DIRECTIONAL_QUERY_EXECUTION_RECORD
            or item.provider != self.provenance.provider
            or item.source_tool != self.provenance.source_tool
            for item in lineages
        ):
            raise DemandIntelligenceValidationError("query execution lineage mismatch")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class RelatedProductEvidence(_DemandModel):
    """Observed product endpoint inventory; this is not a competitor set."""

    inventory_item_id: str
    product_identity: ProductIdentity
    relationship_observation_ids: tuple[str, ...]
    directions: tuple[RelationshipDirection, ...]
    channels: tuple[Channel, ...]
    providers: tuple[str, ...]
    lineage_references: tuple[DemandLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.inventory_item_id, "related product inventory item id")
        _instance(self.product_identity, ProductIdentity, "related product identity")
        ids = _unique_texts(
            self.relationship_observation_ids,
            "related product relationship ids",
            allow_empty=False,
        )
        directions = _tuple(self.directions, "related product directions")
        channels = _tuple(self.channels, "related product channels")
        if not directions or any(not isinstance(item, RelationshipDirection) for item in directions):
            raise DemandIntelligenceValidationError("related product directions are invalid")
        if not channels or any(not isinstance(item, Channel) for item in channels):
            raise DemandIntelligenceValidationError("related product channels are invalid")
        if len(set(directions)) != len(directions) or len(set(channels)) != len(channels):
            raise DemandIntelligenceValidationError("related product directions and channels must be unique")
        providers = _unique_texts(self.providers, "related product providers", allow_empty=False)
        lineages = _tuple(self.lineage_references, "related product lineage_references")
        if not lineages or any(not isinstance(item, DemandLineageReference) for item in lineages):
            raise DemandIntelligenceValidationError("related product evidence requires lineage")
        if {item.source_record_id for item in lineages} != set(ids):
            raise DemandIntelligenceValidationError("related product lineage does not match relationship evidence")
        object.__setattr__(self, "relationship_observation_ids", ids)
        object.__setattr__(self, "directions", tuple(sorted(directions, key=lambda item: item.value)))
        object.__setattr__(self, "channels", tuple(sorted(channels, key=lambda item: item.value)))
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))
        if self.inventory_item_id != deterministic_id(
            "related-product-evidence", _without_id(self, "inventory_item_id")
        ):
            raise DemandIntelligenceValidationError("inventory_item_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OutOfScopeEvidenceReference(_DemandModel):
    """Audited reference to supplied canonical evidence excluded from demand organization."""

    source_record_id: str
    source_record_type: DemandSourceRecordType
    observation_kind: ObservationKind | None
    reason_code: str
    lineage_references: tuple[DemandLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.source_record_id, "out-of-scope source_record_id")
        _instance(self.source_record_type, DemandSourceRecordType, "out-of-scope source_record_type")
        _text(self.reason_code, "out-of-scope reason_code")
        if self.source_record_type is DemandSourceRecordType.DIRECTIONAL_QUERY_EXECUTION_RECORD:
            if self.observation_kind is not None:
                raise DemandIntelligenceValidationError("out-of-scope query cannot claim observation kind")
        else:
            _instance(self.observation_kind, ObservationKind, "out-of-scope observation_kind")
        lineages = _tuple(self.lineage_references, "out-of-scope lineage_references")
        if not lineages or any(not isinstance(item, DemandLineageReference) for item in lineages):
            raise DemandIntelligenceValidationError("out-of-scope evidence requires lineage")
        if any(item.source_record_id != self.source_record_id for item in lineages):
            raise DemandIntelligenceValidationError("out-of-scope lineage source mismatch")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandQualityIssueReference(_DemandModel):
    """Stable inventory entry for one supplied canonical quality issue."""

    issue_id: str
    issue_code: str
    severity: Severity
    source_references: tuple[str, ...]
    collection_run_id: str | None
    transformation_run_id: str | None
    mapping_version: str | None
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.issue_id, "quality issue id")
        _text(self.issue_code, "quality issue code")
        _instance(self.severity, Severity, "quality issue severity")
        object.__setattr__(
            self, "source_references", _unique_texts(self.source_references, "quality issue source_references")
        )
        _optional_text(self.collection_run_id, "quality issue collection_run_id")
        _optional_text(self.transformation_run_id, "quality issue transformation_run_id")
        _optional_text(self.mapping_version, "quality issue mapping_version")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "quality issue source bundle fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise DemandIntelligenceValidationError("quality issue fingerprints must be lowercase SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandIntelligenceDiagnostic(_DemandModel):
    """Stable diagnostic that documents organization without demand inference."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_record_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "diagnostic id")
        _text(self.code, "diagnostic code")
        _instance(self.severity, Severity, "diagnostic severity")
        object.__setattr__(
            self, "related_record_ids", _unique_texts(self.related_record_ids, "diagnostic related_record_ids")
        )
        _text(self.message, "diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "demand-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise DemandIntelligenceValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandEvidenceCoverage(_DemandModel):
    """Inventory counts for supplied evidence; never a score or confidence measure."""

    source_bundle_count: int
    raw_evidence_reference_count: int
    transformation_run_count: int
    keyword_metric_observation_count: int
    relationship_observation_count: int
    query_execution_record_count: int
    included_keyword_metric_count: int
    included_relationship_count: int
    included_query_execution_count: int
    out_of_scope_record_count: int
    relationship_direction_counts: Mapping[str, int]
    query_direction_counts: Mapping[str, int]
    channel_counts: Mapping[str, int]
    query_outcome_counts: Mapping[str, int]
    providers: tuple[str, ...]
    provider_record_counts: Mapping[str, int]
    quality_issue_count: int
    diagnostic_count: int

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count",
            "raw_evidence_reference_count",
            "transformation_run_count",
            "keyword_metric_observation_count",
            "relationship_observation_count",
            "query_execution_record_count",
            "included_keyword_metric_count",
            "included_relationship_count",
            "included_query_execution_count",
            "out_of_scope_record_count",
            "quality_issue_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"DemandEvidenceCoverage.{name}")
        for name in (
            "relationship_direction_counts",
            "query_direction_counts",
            "channel_counts",
            "query_outcome_counts",
            "provider_record_counts",
        ):
            value = _mapping(getattr(self, name), f"DemandEvidenceCoverage.{name}")
            if any(type(item) is not int or item < 0 for item in value.values()):
                raise DemandIntelligenceValidationError(f"{name} values must be non-negative integers")
            object.__setattr__(self, name, value)
        providers = _unique_texts(self.providers, "DemandEvidenceCoverage.providers")
        if set(providers) != set(self.provider_record_counts):
            raise DemandIntelligenceValidationError("coverage providers do not match provider record counts")
        object.__setattr__(self, "providers", providers)


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    """Return an order-insensitive stable SHA-256 identity for a canonical bundle."""

    payload = bundle.to_dict()
    for key, value in tuple(payload.items()):
        if isinstance(value, list):
            payload[key] = sorted(value, key=canonical_json)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def observation_revision_content(observation: CanonicalObservation) -> dict[str, Any]:
    """Return canonical observation content excluding revision and emission metadata."""

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


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandIntelligenceRequest(_DemandModel):
    """Strict immutable request for an exact canonical keyword evidence snapshot."""

    target_keyword_identity: KeywordIdentity
    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]

    def __post_init__(self) -> None:
        _instance(self.target_keyword_identity, KeywordIdentity, "request target_keyword_identity")
        bundles = _tuple(self.canonical_bundles, "request canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise DemandIntelligenceValidationError(
                "canonical_bundles must contain one or more CanonicalEvidenceBundle values"
            )
        fingerprinted: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise DemandIntelligenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprinted.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprinted}) != len(fingerprinted):
            raise DemandIntelligenceValidationError("duplicate canonical bundle fingerprint")
        object.__setattr__(
            self,
            "canonical_bundles",
            tuple(bundle for _, bundle in sorted(fingerprinted, key=lambda item: item[0])),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandIntelligenceSnapshotV0_1(_DemandModel):
    """Deterministic, auditable and unresolved Demand Intelligence snapshot."""

    snapshot_id: str
    ruleset_version: str
    target_keyword_identity: KeywordIdentity
    source_bundle_fingerprints: tuple[str, ...]
    keyword_metric_evidence_sets: tuple[KeywordMetricEvidenceSet, ...]
    relationship_evidence_groups: tuple[RelationshipEvidenceGroup, ...]
    query_execution_evidence: tuple[QueryExecutionEvidenceItem, ...]
    related_product_evidence_inventory: tuple[RelatedProductEvidence, ...]
    evidence_coverage: DemandEvidenceCoverage
    quality_issue_references: tuple[DemandQualityIssueReference, ...]
    out_of_scope_evidence_references: tuple[OutOfScopeEvidenceReference, ...]
    diagnostics: tuple[DemandIntelligenceDiagnostic, ...]
    lineage_index: tuple[DemandLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot id")
        if self.ruleset_version != DEMAND_INTELLIGENCE_RULESET_VERSION:
            raise DemandIntelligenceValidationError("invalid Demand Intelligence ruleset version")
        _instance(self.target_keyword_identity, KeywordIdentity, "snapshot target_keyword_identity")
        typed_sequences = (
            ("keyword_metric_evidence_sets", KeywordMetricEvidenceSet, lambda item: item.metric_evidence_set_id),
            ("relationship_evidence_groups", RelationshipEvidenceGroup, lambda item: item.relationship_group_id),
            ("query_execution_evidence", QueryExecutionEvidenceItem, lambda item: item.query_execution_id),
            ("related_product_evidence_inventory", RelatedProductEvidence, lambda item: item.inventory_item_id),
            ("quality_issue_references", DemandQualityIssueReference, lambda item: item.issue_id),
            ("out_of_scope_evidence_references", OutOfScopeEvidenceReference, lambda item: (item.source_record_type.value, item.source_record_id)),
            ("diagnostics", DemandIntelligenceDiagnostic, lambda item: item.diagnostic_id),
            ("lineage_index", DemandLineageReference, canonical_json),
        )
        for name, expected, key in typed_sequences:
            values = _tuple(getattr(self, name), f"snapshot.{name}")
            if any(not isinstance(item, expected) for item in values):
                raise DemandIntelligenceValidationError(f"snapshot.{name} contains a wrong type")
            ordered = tuple(sorted(values, key=key))
            if len({canonical_json(item) for item in ordered}) != len(ordered):
                raise DemandIntelligenceValidationError(f"snapshot.{name} contains duplicates")
            object.__setattr__(self, name, ordered)
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "snapshot source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise DemandIntelligenceValidationError("snapshot fingerprints must be lowercase SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        _instance(self.evidence_coverage, DemandEvidenceCoverage, "snapshot evidence_coverage")
        if any(item.keyword_identity != self.target_keyword_identity for item in self.keyword_metric_evidence_sets):
            raise DemandIntelligenceValidationError("snapshot metric evidence keyword mismatch")
        relationship_items = tuple(
            record for group in self.relationship_evidence_groups for record in group.records
        )
        if any(group.keyword_identity != self.target_keyword_identity for group in self.relationship_evidence_groups):
            raise DemandIntelligenceValidationError("snapshot relationship keyword mismatch")
        relationship_ids = {item.observation_id for item in relationship_items}
        if len(relationship_ids) != len(relationship_items):
            raise DemandIntelligenceValidationError("relationship observations occur in multiple groups")
        for query in self.query_execution_evidence:
            if query.direction is RelationshipDirection.KEYWORD_TO_PRODUCT:
                if query.query_keyword != self.target_keyword_identity:
                    raise DemandIntelligenceValidationError("forward query target keyword mismatch")
            elif not set(query.target_related_relationship_observation_ids) <= relationship_ids:
                raise DemandIntelligenceValidationError("reverse query target associations are absent")
        product_by_id = {item.product_identity.product_id: item.product_identity for item in relationship_items}
        inventory_ids: set[str] = set()
        for item in self.related_product_evidence_inventory:
            expected_product = product_by_id.get(item.product_identity.product_id)
            if expected_product != item.product_identity:
                raise DemandIntelligenceValidationError("related product inventory identity mismatch")
            if not set(item.relationship_observation_ids) <= relationship_ids:
                raise DemandIntelligenceValidationError("related product inventory references unknown relationship")
            if item.product_identity.product_id in inventory_ids:
                raise DemandIntelligenceValidationError("related product inventory contains duplicate endpoint")
            inventory_ids.add(item.product_identity.product_id)
        lineage_ids = {item.source_record_id for item in self.lineage_index}
        included_ids = {
            candidate.observation_id
            for evidence_set in self.keyword_metric_evidence_sets
            for candidate in evidence_set.candidates
        } | relationship_ids | {item.query_execution_id for item in self.query_execution_evidence}
        out_ids = {item.source_record_id for item in self.out_of_scope_evidence_references}
        if not included_ids | out_ids <= lineage_ids:
            raise DemandIntelligenceValidationError("snapshot item is missing from lineage index")
        if included_ids & out_ids:
            raise DemandIntelligenceValidationError("source record cannot be both included and out of scope")
        expected_id = deterministic_id("demand-snapshot", _without_id(self, "snapshot_id"))
        if self.snapshot_id != expected_id:
            raise DemandSerializationError("snapshot_id does not match snapshot content")

    def validate(self) -> Self:
        """Re-run internal invariant checks and return this snapshot."""

        self.__post_init__()
        return self

    def validate_against_bundles(self, bundles: Sequence[CanonicalEvidenceBundle]) -> Self:
        """Replay all public lineage and fingerprints against source bundles."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise DemandIntelligenceValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[tuple[str, str], tuple[CanonicalObservation, set[str]]] = {}
        queries: dict[str, tuple[DirectionalQueryExecutionRecord, set[str]]] = {}
        runs: dict[str, tuple[Any, set[str]]] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise DemandIntelligenceValidationError("against-bundles input contains a wrong type")
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise DemandIntelligenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise DemandIntelligenceValidationError("duplicate canonical bundle fingerprint")
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current and canonical_json(current[0]) != canonical_json(run):
                    raise DemandIntelligenceValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    runs[run.transformation_run_id] = (run, {fingerprint})
            for observation in bundle.observations:
                key = (
                    observation.observation_id,
                    observation.provenance.transformation.transformation_run_id,
                )
                current = observations.get(key)
                if current and canonical_json(current[0]) != canonical_json(observation):
                    raise DemandIntelligenceValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    observations[key] = (observation, {fingerprint})
            for query in bundle.query_execution_records:
                current = queries.get(query.query_execution_id)
                if current and canonical_json(current[0]) != canonical_json(query):
                    raise DemandIntelligenceValidationError(
                        f"query execution identity collision: {query.query_execution_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    queries[query.query_execution_id] = (query, {fingerprint})
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise DemandIntelligenceValidationError(
                "snapshot source bundle fingerprints do not match supplied bundles"
            )
        for reference in self.lineage_index:
            if reference.source_record_type is DemandSourceRecordType.DIRECTIONAL_QUERY_EXECUTION_RECORD:
                entry = queries.get(reference.source_record_id)
                if entry is None:
                    raise DemandIntelligenceValidationError(
                        f"orphan query execution lineage: {reference.source_record_id}"
                    )
                record, source_fingerprints = entry
                semantic_id = None
                observation_kind = None
            else:
                matching = [
                    value for (record_id, _), value in observations.items() if record_id == reference.source_record_id
                ]
                matching = [
                    value
                    for value in matching
                    if value[0].provenance.transformation.transformation_run_id
                    == reference.transformation_run_id
                ]
                if len(matching) != 1:
                    raise DemandIntelligenceValidationError(
                        f"orphan observation lineage: {reference.source_record_id}"
                    )
                record, source_fingerprints = matching[0]
                semantic_id = record.semantic_observation_id
                observation_kind = record.observation_kind
            transformation = record.provenance.transformation
            run_entry = runs.get(reference.transformation_run_id)
            if run_entry is None:
                raise DemandIntelligenceValidationError(
                    f"orphan transformation lineage: {reference.transformation_run_id}"
                )
            run = run_entry[0]
            checks = (
                (reference.semantic_observation_id, semantic_id, "semantic observation"),
                (reference.observation_kind, observation_kind, "observation kind"),
                (
                    reference.transformation_run_id,
                    transformation.transformation_run_id,
                    "transformation run",
                ),
                (reference.mapping_version, transformation.mapping_version, "mapping"),
                (reference.raw_evidence_id, transformation.raw_evidence_reference, "raw evidence"),
                (reference.collection_run_id, transformation.collection_run_id, "collection"),
                (reference.provider, record.provenance.provider, "provider"),
                (reference.source_tool, record.provenance.source_tool, "source tool"),
                (reference.source_field, record.provenance.source_field, "source field"),
                (set(reference.source_bundle_fingerprints), source_fingerprints, "bundle fingerprint"),
            )
            mismatch = next((label for left, right, label in checks if left != right), None)
            if mismatch is not None:
                raise DemandIntelligenceValidationError(
                    f"lineage {mismatch} mismatch for {reference.source_record_id}"
                )
            if reference.raw_evidence_id not in raw_ids or reference.raw_evidence_id not in run.input_raw_evidence_references:
                raise DemandIntelligenceValidationError(
                    f"orphan raw evidence lineage: {reference.raw_evidence_id}"
                )
            if (
                run.collection_run_id != reference.collection_run_id
                or run.mapping_version != reference.mapping_version
            ):
                raise DemandIntelligenceValidationError(
                    f"run lineage mismatch for {reference.source_record_id}"
                )
        return self.validate()


__all__ = (
    "DEMAND_INTELLIGENCE_RULESET_VERSION",
    "MetricCandidateState",
    "DemandSourceRecordType",
    "DemandLineageReference",
    "KeywordMetricCandidate",
    "KeywordMetricEvidenceSet",
    "RelationshipEvidenceItem",
    "RelationshipEvidenceGroup",
    "QueryExecutionEvidenceItem",
    "RelatedProductEvidence",
    "OutOfScopeEvidenceReference",
    "DemandQualityIssueReference",
    "DemandIntelligenceDiagnostic",
    "DemandEvidenceCoverage",
    "DemandIntelligenceRequest",
    "DemandIntelligenceSnapshotV0_1",
)
