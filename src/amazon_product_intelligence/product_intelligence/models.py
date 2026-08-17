"""Immutable public data models for Product Intelligence V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from enum import StrEnum
import json
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    ContractValidationError,
    EvidenceType,
    FactGroup,
    JsonContract,
    NormalizationStatus,
    ObservationKind,
    ObservedAtStatus,
    PeriodType,
    PresenceStatus,
    ProductIdentity,
    ResultStatus,
    Scope,
    SemanticStatus,
    Severity,
    SubjectRef,
    TimeWindow,
    Unit,
    ValueType,
    canonical_json,
    deterministic_id,
)

from .errors import ProductIntelligenceValidationError, SnapshotSerializationError


PRODUCT_INTELLIGENCE_RULESET_VERSION = "product-intelligence-v0.1"


class ProductScope(StrEnum):
    """Supported product boundaries."""

    EXACT_PRODUCT = "EXACT_PRODUCT"
    EXPLICIT_VARIATION_FAMILY = "EXPLICIT_VARIATION_FAMILY"


class FactCandidateState(StrEnum):
    """Structural state of an unresolved fact candidate set."""

    NO_PRESENT_CANDIDATE = "NO_PRESENT_CANDIDATE"
    ONE_DISTINCT_PRESENT_VALUE = "ONE_DISTINCT_PRESENT_VALUE"
    MULTIPLE_DISTINCT_PRESENT_VALUES = "MULTIPLE_DISTINCT_PRESENT_VALUES"


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ProductIntelligenceValidationError(f"{path} must contain finite JSON data: {exc}") from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ProductIntelligenceValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise ProductIntelligenceValidationError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ProductIntelligenceValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise ProductIntelligenceValidationError(f"{path} must be {expected.__name__}")


def _mapping(value: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise ProductIntelligenceValidationError(f"{path} must be an object")
    if any(type(key) is not str for key in value):
        raise ProductIntelligenceValidationError(f"{path} keys must be strings")
    return _freeze_json(value, path)


def _identity(prefix: str, payload: Mapping[str, Any]) -> str:
    return deterministic_id(prefix, payload)


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


class _ProductModel(JsonContract):
    """Strictly decode public models while translating contract errors."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except ProductIntelligenceValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise SnapshotSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class LineageReference(_ProductModel):
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
            _text(getattr(self, name), f"LineageReference.{name}")
        _instance(self.observation_kind, ObservationKind, "LineageReference.observation_kind")
        fingerprints = _tuple(self.source_bundle_fingerprints, "LineageReference.source_bundle_fingerprints")
        if not fingerprints or any(type(item) is not str or len(item) != 64 for item in fingerprints):
            raise ProductIntelligenceValidationError("lineage source bundle fingerprints must be SHA-256 hex strings")
        if len(set(fingerprints)) != len(fingerprints):
            raise ProductIntelligenceValidationError("lineage source bundle fingerprints must be unique")
        object.__setattr__(self, "source_bundle_fingerprints", tuple(sorted(fingerprints)))


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceCandidate(_ProductModel):
    """One unresolved canonical evidence candidate."""

    observation_id: str
    semantic_observation_id: str
    observation_kind: ObservationKind
    presence_status: PresenceStatus
    raw_value: Any
    normalized_value: Any
    value_type: ValueType
    unit: Unit | None
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    evidence_type: EvidenceType
    result_status: ResultStatus
    scope: Scope
    time: TimeWindow
    provider: str
    source_tool: str
    lineage_references: tuple[LineageReference, ...]

    def __post_init__(self) -> None:
        for name in ("observation_id", "semantic_observation_id", "provider", "source_tool"):
            _text(getattr(self, name), f"EvidenceCandidate.{name}")
        for name, expected in (
            ("observation_kind", ObservationKind),
            ("presence_status", PresenceStatus),
            ("value_type", ValueType),
            ("normalization_status", NormalizationStatus),
            ("semantic_status", SemanticStatus),
            ("evidence_type", EvidenceType),
            ("result_status", ResultStatus),
            ("scope", Scope),
            ("time", TimeWindow),
        ):
            _instance(getattr(self, name), expected, f"EvidenceCandidate.{name}")
        if self.unit is not None:
            _instance(self.unit, Unit, "EvidenceCandidate.unit")
        object.__setattr__(self, "raw_value", _freeze_json(self.raw_value, "EvidenceCandidate.raw_value"))
        object.__setattr__(self, "normalized_value", _freeze_json(self.normalized_value, "EvidenceCandidate.normalized_value"))
        lineages = _tuple(self.lineage_references, "EvidenceCandidate.lineage_references")
        if not lineages or any(not isinstance(item, LineageReference) for item in lineages):
            raise ProductIntelligenceValidationError("each evidence candidate requires lineage references")
        if any(item.observation_id != self.observation_id for item in lineages):
            raise ProductIntelligenceValidationError("candidate lineage observation mismatch")
        if any(
            item.semantic_observation_id != self.semantic_observation_id
            or item.observation_kind is not self.observation_kind
            or item.provider != self.provider
            or item.source_tool != self.source_tool
            for item in lineages
        ):
            raise ProductIntelligenceValidationError("candidate lineage semantics mismatch")
        absent = self.presence_status is not PresenceStatus.PRESENT
        if absent and (self.raw_value is not None or self.normalized_value is not None):
            raise ProductIntelligenceValidationError("non-present candidates require null values")
        if self.presence_status is PresenceStatus.PRESENT and self.raw_value is None and self.normalized_value is None:
            raise ProductIntelligenceValidationError("present candidates require a raw or normalized value")
        if absent and self.normalization_status is NormalizationStatus.NORMALIZED:
            raise ProductIntelligenceValidationError("non-present candidates cannot be normalized")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductFactEvidenceSet(_ProductModel):
    """Unresolved fact candidates sharing the same semantic boundary."""

    fact_set_id: str
    subject_product_identity: ProductIdentity
    dimension: str
    fact_group: FactGroup
    scope: Scope
    unit: Unit | None
    provider_semantic: str | None
    candidate_state: FactCandidateState
    distinct_present_value_count: int
    candidates: tuple[EvidenceCandidate, ...]

    def __post_init__(self) -> None:
        _instance(self.subject_product_identity, ProductIdentity, "ProductFactEvidenceSet.subject_product_identity")
        _text(self.dimension, "ProductFactEvidenceSet.dimension")
        _instance(self.fact_group, FactGroup, "ProductFactEvidenceSet.fact_group")
        _instance(self.scope, Scope, "ProductFactEvidenceSet.scope")
        _instance(self.candidate_state, FactCandidateState, "ProductFactEvidenceSet.candidate_state")
        _count(self.distinct_present_value_count, "ProductFactEvidenceSet.distinct_present_value_count")
        if self.unit is not None:
            _instance(self.unit, Unit, "ProductFactEvidenceSet.unit")
        candidates = _tuple(self.candidates, "ProductFactEvidenceSet.candidates")
        if not candidates or any(not isinstance(item, EvidenceCandidate) for item in candidates):
            raise ProductIntelligenceValidationError("fact evidence sets require candidates")
        if any(item.observation_kind is not ObservationKind.PRODUCT_FACT for item in candidates):
            raise ProductIntelligenceValidationError("fact evidence set contains a non-fact candidate")
        if any(item.scope != self.scope or item.unit != self.unit for item in candidates):
            raise ProductIntelligenceValidationError("fact candidate scope or unit mismatch")
        present_values = {
            canonical_json({"value": item.normalized_value, "unit": item.unit})
            for item in candidates
            if item.presence_status is PresenceStatus.PRESENT
        }
        expected_state = (
            FactCandidateState.NO_PRESENT_CANDIDATE
            if not present_values
            else FactCandidateState.ONE_DISTINCT_PRESENT_VALUE
            if len(present_values) == 1
            else FactCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES
        )
        if self.distinct_present_value_count != len(present_values) or self.candidate_state is not expected_state:
            raise ProductIntelligenceValidationError("fact candidate state does not match candidates")
        object.__setattr__(self, "candidates", tuple(sorted(candidates, key=lambda item: item.observation_id)))
        if self.fact_set_id != _identity("fact-set", _without_id(self, "fact_set_id")):
            raise ProductIntelligenceValidationError("fact_set_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductMetricSeries(_ProductModel):
    """Unresolved metric candidates sharing complete canonical semantics."""

    metric_series_id: str
    subject_product_identity: ProductIdentity
    metric: str
    measurement_type: EvidenceType
    evidence_type: EvidenceType
    unit: Unit | None
    scope: Scope
    period_type: PeriodType
    period_start: str | None
    period_end: str | None
    observed_at_status: ObservedAtStatus
    timezone: str | None
    currency: str | None
    rank_context: Mapping[str, Any] | None
    metric_semantic: str | None
    candidate_count: int
    presence_counts: Mapping[str, int]
    candidates: tuple[EvidenceCandidate, ...]

    def __post_init__(self) -> None:
        _instance(self.subject_product_identity, ProductIdentity, "ProductMetricSeries.subject_product_identity")
        _text(self.metric, "ProductMetricSeries.metric")
        _instance(self.measurement_type, EvidenceType, "ProductMetricSeries.measurement_type")
        _instance(self.evidence_type, EvidenceType, "ProductMetricSeries.evidence_type")
        _instance(self.scope, Scope, "ProductMetricSeries.scope")
        _instance(self.period_type, PeriodType, "ProductMetricSeries.period_type")
        _instance(self.observed_at_status, ObservedAtStatus, "ProductMetricSeries.observed_at_status")
        if self.unit is not None:
            _instance(self.unit, Unit, "ProductMetricSeries.unit")
        if self.rank_context is not None:
            object.__setattr__(self, "rank_context", _mapping(self.rank_context, "ProductMetricSeries.rank_context"))
        object.__setattr__(self, "presence_counts", _mapping(self.presence_counts, "ProductMetricSeries.presence_counts"))
        _count(self.candidate_count, "ProductMetricSeries.candidate_count")
        if any(type(value) is not int or value < 0 for value in self.presence_counts.values()):
            raise ProductIntelligenceValidationError("metric presence counts must be non-negative integers")
        candidates = _tuple(self.candidates, "ProductMetricSeries.candidates")
        if len(candidates) != self.candidate_count or not candidates:
            raise ProductIntelligenceValidationError("metric candidate_count does not match candidates")
        if any(not isinstance(item, EvidenceCandidate) or item.observation_kind is not ObservationKind.METRIC for item in candidates):
            raise ProductIntelligenceValidationError("metric series contains a non-metric candidate")
        if any(
            item.scope != self.scope
            or item.unit != self.unit
            or item.evidence_type is not self.evidence_type
            or item.time.period_type is not self.period_type
            or item.time.period_start != self.period_start
            or item.time.period_end != self.period_end
            or item.time.observed_at_status is not self.observed_at_status
            or item.time.timezone != self.timezone
            for item in candidates
        ):
            raise ProductIntelligenceValidationError("metric candidate semantic boundary mismatch")
        expected_counts = {
            status.value: sum(item.presence_status is status for item in candidates)
            for status in PresenceStatus
            if any(item.presence_status is status for item in candidates)
        }
        if dict(self.presence_counts) != expected_counts:
            raise ProductIntelligenceValidationError("metric presence counts do not match candidates")
        ordered = tuple(sorted(candidates, key=lambda item: (
            item.time.observed_at or "",
            item.time.period_start or "",
            item.time.period_end or "",
            item.observation_id,
        )))
        object.__setattr__(self, "candidates", ordered)
        if self.metric_series_id != _identity("metric-series", _without_id(self, "metric_series_id")):
            raise ProductIntelligenceValidationError("metric_series_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductIntelligenceDiagnostic(_ProductModel):
    """Stable, non-resolving Product Intelligence diagnostic."""

    diagnostic_id: str
    code: str
    severity: Severity
    subject: SubjectRef | None
    related_observation_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.code, "ProductIntelligenceDiagnostic.code")
        _instance(self.severity, Severity, "ProductIntelligenceDiagnostic.severity")
        if self.subject is not None:
            _instance(self.subject, SubjectRef, "ProductIntelligenceDiagnostic.subject")
        _text(self.message, "ProductIntelligenceDiagnostic.message")
        references = _tuple(self.related_observation_ids, "ProductIntelligenceDiagnostic.related_observation_ids")
        if any(type(item) is not str or not item for item in references) or len(set(references)) != len(references):
            raise ProductIntelligenceValidationError("diagnostic observation references must be unique text")
        object.__setattr__(self, "related_observation_ids", tuple(sorted(references)))
        if self.diagnostic_id != _identity("pi-diagnostic", _without_id(self, "diagnostic_id")):
            raise ProductIntelligenceValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class VariationEdge(_ProductModel):
    """A confirmed parent-to-child edge with all supporting evidence."""

    variation_edge_id: str
    parent_product_identity: ProductIdentity
    child_product_identity: ProductIdentity
    evidence_observation_ids: tuple[str, ...]
    evidence_dimensions: tuple[str, ...]
    providers: tuple[str, ...]
    source_tools: tuple[str, ...]
    evidence_count: int
    lineage_references: tuple[LineageReference, ...]

    def __post_init__(self) -> None:
        _instance(self.parent_product_identity, ProductIdentity, "VariationEdge.parent_product_identity")
        _instance(self.child_product_identity, ProductIdentity, "VariationEdge.child_product_identity")
        if self.parent_product_identity.product_id == self.child_product_identity.product_id:
            raise ProductIntelligenceValidationError("variation edge cannot be a self-loop")
        if self.parent_product_identity.marketplace != self.child_product_identity.marketplace:
            raise ProductIntelligenceValidationError("variation edge marketplaces must match")
        for name in ("evidence_observation_ids", "evidence_dimensions", "providers", "source_tools"):
            values = _tuple(getattr(self, name), f"VariationEdge.{name}")
            if not values or any(type(item) is not str or not item for item in values):
                raise ProductIntelligenceValidationError(f"VariationEdge.{name} requires text values")
            object.__setattr__(self, name, tuple(sorted(set(values))))
        _count(self.evidence_count, "VariationEdge.evidence_count")
        if self.evidence_count != len(self.evidence_observation_ids):
            raise ProductIntelligenceValidationError("variation edge evidence count mismatch")
        lineages = _tuple(self.lineage_references, "VariationEdge.lineage_references")
        if not lineages or any(not isinstance(item, LineageReference) for item in lineages):
            raise ProductIntelligenceValidationError("variation edge requires lineage")
        if {item.observation_id for item in lineages} != set(self.evidence_observation_ids):
            raise ProductIntelligenceValidationError("variation edge evidence and lineage mismatch")
        if {item.provider for item in lineages} != set(self.providers):
            raise ProductIntelligenceValidationError("variation edge provider inventory mismatch")
        if {item.source_tool for item in lineages} != set(self.source_tools):
            raise ProductIntelligenceValidationError("variation edge source tool inventory mismatch")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))
        if self.variation_edge_id != _identity("variation-edge", _without_id(self, "variation_edge_id")):
            raise ProductIntelligenceValidationError("variation_edge_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class VariationTopology(_ProductModel):
    """Validated explicit variation topology for the requested scope."""

    target_product_identity: ProductIdentity
    scope: ProductScope
    nodes: tuple[ProductIdentity, ...]
    edges: tuple[VariationEdge, ...]
    family_root: ProductIdentity | None
    diagnostic_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _instance(self.target_product_identity, ProductIdentity, "VariationTopology.target_product_identity")
        _instance(self.scope, ProductScope, "VariationTopology.scope")
        nodes = _tuple(self.nodes, "VariationTopology.nodes")
        edges = _tuple(self.edges, "VariationTopology.edges")
        if any(not isinstance(item, ProductIdentity) for item in nodes):
            raise ProductIntelligenceValidationError("topology nodes must be ProductIdentity values")
        if any(not isinstance(item, VariationEdge) for item in edges):
            raise ProductIntelligenceValidationError("topology edges must be VariationEdge values")
        node_ids = {item.product_id for item in nodes}
        if len(node_ids) != len(nodes):
            raise ProductIntelligenceValidationError("topology nodes must be unique")
        if self.target_product_identity.product_id not in node_ids:
            raise ProductIntelligenceValidationError("topology must contain target")
        if any(edge.parent_product_identity.product_id not in node_ids or edge.child_product_identity.product_id not in node_ids for edge in edges):
            raise ProductIntelligenceValidationError("topology edge endpoint is absent from nodes")
        if self.family_root is not None and self.family_root.product_id not in node_ids:
            raise ProductIntelligenceValidationError("family_root must be a topology node")
        edge_pairs = {
            (edge.parent_product_identity.product_id, edge.child_product_identity.product_id)
            for edge in edges
        }
        if len(edge_pairs) != len(edges):
            raise ProductIntelligenceValidationError("topology edges must be unique")
        parents_by_child: dict[str, set[str]] = {}
        directed: dict[str, set[str]] = {}
        adjacent: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
        for parent_id, child_id in edge_pairs:
            parents_by_child.setdefault(child_id, set()).add(parent_id)
            directed.setdefault(parent_id, set()).add(child_id)
            adjacent[parent_id].add(child_id)
            adjacent[child_id].add(parent_id)
        if any(len(parents) > 1 for parents in parents_by_child.values()):
            raise ProductIntelligenceValidationError("topology child has multiple parents")
        seen: set[str] = set()
        active: set[str] = set()

        def visit(node_id: str) -> None:
            if node_id in active:
                raise ProductIntelligenceValidationError("topology contains a directed cycle")
            if node_id in seen:
                return
            active.add(node_id)
            for child_id in directed.get(node_id, ()):
                visit(child_id)
            active.remove(node_id)
            seen.add(node_id)

        for node_id in node_ids:
            visit(node_id)
        connected = {self.target_product_identity.product_id}
        pending = list(connected)
        while pending:
            for neighbour in adjacent[pending.pop()]:
                if neighbour not in connected:
                    connected.add(neighbour)
                    pending.append(neighbour)
        if connected != node_ids:
            raise ProductIntelligenceValidationError("topology nodes must be target-connected")
        roots = node_ids - set(parents_by_child)
        expected_root = next(iter(roots)) if len(roots) == 1 else None
        actual_root = self.family_root.product_id if self.family_root is not None else None
        if actual_root != expected_root:
            raise ProductIntelligenceValidationError("family_root does not match topology")
        object.__setattr__(self, "nodes", tuple(sorted(nodes, key=lambda item: item.product_id)))
        object.__setattr__(self, "edges", tuple(sorted(edges, key=lambda item: item.variation_edge_id)))
        diagnostics = _tuple(self.diagnostic_ids, "VariationTopology.diagnostic_ids")
        object.__setattr__(self, "diagnostic_ids", tuple(sorted(set(diagnostics))))


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewEvidenceSummary(_ProductModel):
    """Descriptive counts for the supplied review evidence sample."""

    sample_basis: str
    review_observation_count: int
    exact_unique_review_identity_count: int
    providers: tuple[str, ...]
    source_tools: tuple[str, ...]
    rating_presence_counts: Mapping[str, int]
    present_rating_histogram: Mapping[str, int]
    known_date_count: int
    unknown_date_count: int
    helpful_votes_missing_count: int
    helpful_votes_zero_count: int
    helpful_votes_positive_count: int
    variant_known_count: int
    variant_unknown_count: int
    review_observation_ids: tuple[str, ...]
    lineage_references: tuple[LineageReference, ...]

    def __post_init__(self) -> None:
        if self.sample_basis != "SUPPLIED_EVIDENCE_SAMPLE":
            raise ProductIntelligenceValidationError("review summary sample_basis is invalid")
        for name in (
            "review_observation_count", "exact_unique_review_identity_count", "known_date_count", "unknown_date_count",
            "helpful_votes_missing_count", "helpful_votes_zero_count", "helpful_votes_positive_count",
            "variant_known_count", "variant_unknown_count",
        ):
            _count(getattr(self, name), f"ReviewEvidenceSummary.{name}")
        for name in ("providers", "source_tools", "review_observation_ids"):
            values = _tuple(getattr(self, name), f"ReviewEvidenceSummary.{name}")
            object.__setattr__(self, name, tuple(sorted(set(values))))
        if self.review_observation_count != len(self.review_observation_ids):
            raise ProductIntelligenceValidationError("review observation count mismatch")
        for name in ("rating_presence_counts", "present_rating_histogram"):
            frozen = _mapping(getattr(self, name), f"ReviewEvidenceSummary.{name}")
            if any(type(value) is not int or value < 0 for value in frozen.values()):
                raise ProductIntelligenceValidationError(f"{name} values must be non-negative integers")
            object.__setattr__(self, name, frozen)
        if sum(self.rating_presence_counts.values()) != self.review_observation_count:
            raise ProductIntelligenceValidationError("review rating presence counts do not match sample")
        if sum(self.present_rating_histogram.values()) != self.rating_presence_counts.get(PresenceStatus.PRESENT.value, 0):
            raise ProductIntelligenceValidationError("review rating histogram does not match present ratings")
        if self.known_date_count + self.unknown_date_count != self.review_observation_count:
            raise ProductIntelligenceValidationError("review date counts do not match sample")
        if self.variant_known_count + self.variant_unknown_count != self.review_observation_count:
            raise ProductIntelligenceValidationError("review variant counts do not match sample")
        lineages = _tuple(self.lineage_references, "ReviewEvidenceSummary.lineage_references")
        if any(not isinstance(item, LineageReference) for item in lineages):
            raise ProductIntelligenceValidationError("review summary lineage is invalid")
        if not set(self.review_observation_ids) <= {item.observation_id for item in lineages}:
            raise ProductIntelligenceValidationError("review summary lineage omits a representative review")
        if {item.provider for item in lineages} != set(self.providers):
            raise ProductIntelligenceValidationError("review provider inventory mismatch")
        if {item.source_tool for item in lineages} != set(self.source_tools):
            raise ProductIntelligenceValidationError("review source tool inventory mismatch")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class QualityIssueReference(_ProductModel):
    """Auditable reference to an input canonical quality issue."""

    issue_id: str
    issue_code: str
    severity: Severity
    source_references: tuple[str, ...]
    collection_run_id: str | None
    transformation_run_id: str | None
    mapping_version: str | None
    raw_evidence_ids: tuple[str, ...]
    collection_run_ids: tuple[str, ...]
    transformation_run_ids: tuple[str, ...]
    mapping_versions: tuple[str, ...]
    providers: tuple[str, ...]
    source_tools: tuple[str, ...]
    observation_lineage_references: tuple[LineageReference, ...]
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.issue_id, "QualityIssueReference.issue_id")
        _text(self.issue_code, "QualityIssueReference.issue_code")
        _instance(self.severity, Severity, "QualityIssueReference.severity")
        for name in (
            "source_references", "raw_evidence_ids", "collection_run_ids", "transformation_run_ids",
            "mapping_versions", "providers", "source_tools", "source_bundle_fingerprints",
        ):
            values = _tuple(getattr(self, name), f"QualityIssueReference.{name}")
            object.__setattr__(self, name, tuple(sorted(set(values))))
        lineages = _tuple(
            self.observation_lineage_references,
            "QualityIssueReference.observation_lineage_references",
        )
        if any(not isinstance(item, LineageReference) for item in lineages):
            raise ProductIntelligenceValidationError("quality issue observation lineage is invalid")
        object.__setattr__(
            self, "observation_lineage_references", tuple(sorted(lineages, key=canonical_json))
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OutOfScopeObservationReference(_ProductModel):
    """Explicit reference to supplied evidence not consumed as product evidence."""

    observation_id: str
    observation_kind: ObservationKind
    reason_code: str
    lineage_references: tuple[LineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.observation_id, "OutOfScopeObservationReference.observation_id")
        _instance(self.observation_kind, ObservationKind, "OutOfScopeObservationReference.observation_kind")
        _text(self.reason_code, "OutOfScopeObservationReference.reason_code")
        lineages = _tuple(self.lineage_references, "OutOfScopeObservationReference.lineage_references")
        if not lineages or any(not isinstance(item, LineageReference) for item in lineages):
            raise ProductIntelligenceValidationError("out-of-scope observation requires lineage")
        if any(item.observation_id != self.observation_id for item in lineages):
            raise ProductIntelligenceValidationError("out-of-scope lineage observation mismatch")
        object.__setattr__(self, "lineage_references", tuple(sorted(lineages, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceCoverageSummary(_ProductModel):
    """Inventory counts for supplied evidence; never a score or percentage."""

    source_bundle_count: int
    collection_count: int
    raw_evidence_record_count: int
    mapping_count: int
    transformation_run_count: int
    observation_counts_by_type: Mapping[str, int]
    included_observation_count: int
    excluded_observation_count: int
    out_of_scope_keyword_observation_count: int
    provider_count: int
    source_tool_count: int
    payload_kind_count: int
    evidence_type_counts: Mapping[str, int]
    presence_state_counts: Mapping[str, int]
    fact_dimension_count: int
    metric_type_count: int
    review_evidence_count: int
    variation_edge_count: int
    quality_issue_count: int
    product_intelligence_diagnostic_count: int

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count", "collection_count", "raw_evidence_record_count", "mapping_count",
            "transformation_run_count", "included_observation_count", "excluded_observation_count",
            "out_of_scope_keyword_observation_count", "provider_count", "source_tool_count", "payload_kind_count",
            "fact_dimension_count", "metric_type_count", "review_evidence_count", "variation_edge_count",
            "quality_issue_count", "product_intelligence_diagnostic_count",
        ):
            _count(getattr(self, name), f"EvidenceCoverageSummary.{name}")
        for name in ("observation_counts_by_type", "evidence_type_counts", "presence_state_counts"):
            frozen = _mapping(getattr(self, name), f"EvidenceCoverageSummary.{name}")
            if any(type(value) is not int or value < 0 for value in frozen.values()):
                raise ProductIntelligenceValidationError(f"{name} values must be non-negative integers")
            object.__setattr__(self, name, frozen)


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    """Return the stable SHA-256 identity of a strict canonical bundle."""

    import hashlib

    payload = bundle.to_dict()
    # Bundle members are canonical record sets. Sorting their strict serialized
    # forms makes the fingerprint independent of caller-controlled tuple order.
    for key, value in tuple(payload.items()):
        if isinstance(value, list):
            payload[key] = sorted(value, key=canonical_json)
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def observation_revision_content(observation: CanonicalObservation) -> dict[str, Any]:
    """Mirror the public contract's documented revision-content boundary."""

    payload = observation.to_dict()
    for key in ("semantic_observation_id", "observation_id", "provenance", "quality_issue_ids", "result_status"):
        payload.pop(key, None)
    time_payload = payload.get("time")
    if isinstance(time_payload, dict):
        time_payload.pop("retrieved_at", None)
    return payload


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductIntelligenceRequest(_ProductModel):
    """Strict immutable request for a product evidence snapshot."""

    target_product_identity: ProductIdentity
    scope: ProductScope
    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]

    def __post_init__(self) -> None:
        _instance(self.target_product_identity, ProductIdentity, "ProductIntelligenceRequest.target_product_identity")
        _instance(self.scope, ProductScope, "ProductIntelligenceRequest.scope")
        bundles = _tuple(self.canonical_bundles, "ProductIntelligenceRequest.canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise ProductIntelligenceValidationError("canonical_bundles must contain one or more CanonicalEvidenceBundle values")
        fingerprints: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise ProductIntelligenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprints.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprints}) != len(fingerprints):
            raise ProductIntelligenceValidationError("duplicate canonical bundle fingerprint")
        object.__setattr__(self, "canonical_bundles", tuple(bundle for _, bundle in sorted(fingerprints, key=lambda item: item[0])))


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductIntelligenceSnapshotV0_1(_ProductModel):
    """Deterministic, auditable and unresolved Product Intelligence snapshot."""

    snapshot_id: str
    ruleset_version: str
    target_product_identity: ProductIdentity
    scope: ProductScope
    included_product_identities: tuple[ProductIdentity, ...]
    source_bundle_fingerprints: tuple[str, ...]
    variation_topology: VariationTopology
    product_fact_evidence_sets: tuple[ProductFactEvidenceSet, ...]
    product_metric_series: tuple[ProductMetricSeries, ...]
    review_evidence_summary: ReviewEvidenceSummary
    evidence_coverage_summary: EvidenceCoverageSummary
    quality_issue_references: tuple[QualityIssueReference, ...]
    out_of_scope_observation_references: tuple[OutOfScopeObservationReference, ...]
    lineage_index: tuple[LineageReference, ...]
    diagnostics: tuple[ProductIntelligenceDiagnostic, ...]

    def __post_init__(self) -> None:
        if self.ruleset_version != PRODUCT_INTELLIGENCE_RULESET_VERSION:
            raise ProductIntelligenceValidationError("invalid Product Intelligence ruleset version")
        _instance(self.target_product_identity, ProductIdentity, "snapshot target")
        _instance(self.scope, ProductScope, "snapshot scope")
        typed_sequences = (
            ("included_product_identities", ProductIdentity, lambda item: item.product_id),
            ("product_fact_evidence_sets", ProductFactEvidenceSet, lambda item: item.fact_set_id),
            ("product_metric_series", ProductMetricSeries, lambda item: item.metric_series_id),
            ("quality_issue_references", QualityIssueReference, lambda item: item.issue_id),
            ("out_of_scope_observation_references", OutOfScopeObservationReference, lambda item: item.observation_id),
            ("lineage_index", LineageReference, canonical_json),
            ("diagnostics", ProductIntelligenceDiagnostic, lambda item: item.diagnostic_id),
        )
        for name, expected, key in typed_sequences:
            values = _tuple(getattr(self, name), f"snapshot.{name}")
            if any(not isinstance(item, expected) for item in values):
                raise ProductIntelligenceValidationError(f"snapshot.{name} contains an invalid value")
            object.__setattr__(self, name, tuple(sorted(values, key=key)))
        fingerprints = _tuple(self.source_bundle_fingerprints, "snapshot.source_bundle_fingerprints")
        if not fingerprints or len(set(fingerprints)) != len(fingerprints):
            raise ProductIntelligenceValidationError("snapshot source bundle fingerprints must be non-empty and unique")
        object.__setattr__(self, "source_bundle_fingerprints", tuple(sorted(fingerprints)))
        _instance(self.variation_topology, VariationTopology, "snapshot.variation_topology")
        _instance(self.review_evidence_summary, ReviewEvidenceSummary, "snapshot.review_evidence_summary")
        _instance(self.evidence_coverage_summary, EvidenceCoverageSummary, "snapshot.evidence_coverage_summary")
        included_ids = {item.product_id for item in self.included_product_identities}
        if len(included_ids) != len(self.included_product_identities):
            raise ProductIntelligenceValidationError("included products must be unique")
        if self.target_product_identity.product_id not in included_ids:
            raise ProductIntelligenceValidationError("included products must contain target")
        if self.scope is ProductScope.EXACT_PRODUCT and included_ids != {self.target_product_identity.product_id}:
            raise ProductIntelligenceValidationError("exact scope can include only the target product")
        if (
            self.variation_topology.target_product_identity != self.target_product_identity
            or self.variation_topology.scope is not self.scope
        ):
            raise ProductIntelligenceValidationError("snapshot topology target or scope mismatch")
        topology_ids = {item.product_id for item in self.variation_topology.nodes}
        if self.scope is ProductScope.EXPLICIT_VARIATION_FAMILY and topology_ids != included_ids:
            raise ProductIntelligenceValidationError("family scope topology must match included products")
        diagnostic_ids = {item.diagnostic_id for item in self.diagnostics}
        if not set(self.variation_topology.diagnostic_ids) <= diagnostic_ids:
            raise ProductIntelligenceValidationError("topology references an absent diagnostic")
        lineage_keys = [canonical_json(item) for item in self.lineage_index]
        if len(set(lineage_keys)) != len(lineage_keys):
            raise ProductIntelligenceValidationError("snapshot lineage index contains duplicates")
        expected_id = _identity("snapshot", _without_id(self, "snapshot_id"))
        if self.snapshot_id != expected_id:
            raise SnapshotSerializationError("snapshot_id does not match snapshot content")

    def validate(self) -> Self:
        """Re-run internal invariant checks and return this snapshot."""

        self.__post_init__()
        return self

    def validate_against_bundles(self, bundles: Sequence[CanonicalEvidenceBundle]) -> Self:
        """Replay every public lineage and issue reference against source bundles."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise ProductIntelligenceValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[tuple[str, str], tuple[CanonicalObservation, set[str]]] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, tuple[Any, set[str]]] = {}
        issues: dict[str, tuple[Any, set[str]]] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise ProductIntelligenceValidationError("against-bundles input contains a wrong type")
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise ProductIntelligenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise ProductIntelligenceValidationError("duplicate canonical bundle fingerprint")
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current and canonical_json(current[0]) != canonical_json(run):
                    raise ProductIntelligenceValidationError(f"transformation run identity collision: {run.transformation_run_id}")
                if current:
                    current[1].add(fingerprint)
                else:
                    runs[run.transformation_run_id] = (run, {fingerprint})
            for observation in bundle.observations:
                content = canonical_json(observation_revision_content(observation))
                if observation.observation_id in revisions and revisions[observation.observation_id] != content:
                    raise ProductIntelligenceValidationError(f"observation identity collision: {observation.observation_id}")
                revisions[observation.observation_id] = content
                key = (observation.observation_id, observation.provenance.transformation.transformation_run_id)
                current = observations.get(key)
                if current and canonical_json(current[0]) != canonical_json(observation):
                    raise ProductIntelligenceValidationError(f"observation emission collision: {observation.observation_id}")
                if current:
                    current[1].add(fingerprint)
                else:
                    observations[key] = (observation, {fingerprint})
            for issue in bundle.quality_issues:
                current = issues.get(issue.issue_id)
                if current and canonical_json(current[0]) != canonical_json(issue):
                    raise ProductIntelligenceValidationError(f"quality issue identity collision: {issue.issue_id}")
                if current:
                    current[1].add(fingerprint)
                else:
                    issues[issue.issue_id] = (issue, {fingerprint})
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise ProductIntelligenceValidationError("snapshot source bundle fingerprints do not match supplied bundles")
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            emission = observations.get(key)
            if emission is None:
                raise ProductIntelligenceValidationError(f"orphan observation lineage: {reference.observation_id}")
            observation, source_fingerprints = emission
            run_entry = runs.get(reference.transformation_run_id)
            if run_entry is None:
                raise ProductIntelligenceValidationError(f"orphan transformation lineage: {reference.transformation_run_id}")
            run = run_entry[0]
            transformation = observation.provenance.transformation
            checks = (
                (reference.semantic_observation_id, observation.semantic_observation_id, "semantic observation"),
                (reference.observation_kind, observation.observation_kind, "observation kind"),
                (reference.mapping_version, transformation.mapping_version, "mapping"),
                (reference.raw_evidence_id, transformation.raw_evidence_reference, "raw evidence"),
                (reference.collection_run_id, transformation.collection_run_id, "collection"),
                (reference.provider, observation.provenance.provider, "provider"),
                (reference.source_tool, observation.provenance.source_tool, "source tool"),
                (reference.source_field, observation.provenance.source_field, "source field"),
            )
            if any(left != right for left, right, _ in checks):
                mismatch = next(label for left, right, label in checks if left != right)
                raise ProductIntelligenceValidationError(f"lineage {mismatch} mismatch for {reference.observation_id}")
            if reference.raw_evidence_id not in raw_ids or reference.raw_evidence_id not in run.input_raw_evidence_references:
                raise ProductIntelligenceValidationError(f"orphan raw evidence lineage: {reference.raw_evidence_id}")
            if reference.collection_run_id != run.collection_run_id or reference.mapping_version != run.mapping_version:
                raise ProductIntelligenceValidationError(f"orphan collection or mapping lineage: {reference.observation_id}")
            if set(reference.source_bundle_fingerprints) != source_fingerprints:
                raise ProductIntelligenceValidationError(f"lineage bundle fingerprint mismatch: {reference.observation_id}")
        indexed = {canonical_json(item) for item in self.lineage_index}
        referenced: list[LineageReference] = []
        for fact_set in self.product_fact_evidence_sets:
            for candidate in fact_set.candidates:
                referenced.extend(candidate.lineage_references)
        for series in self.product_metric_series:
            for candidate in series.candidates:
                referenced.extend(candidate.lineage_references)
        referenced.extend(self.review_evidence_summary.lineage_references)
        for edge in self.variation_topology.edges:
            referenced.extend(edge.lineage_references)
        for item in self.out_of_scope_observation_references:
            referenced.extend(item.lineage_references)
        for item in self.quality_issue_references:
            referenced.extend(item.observation_lineage_references)
        referenced_keys = {canonical_json(item) for item in referenced}
        if indexed != referenced_keys:
            raise ProductIntelligenceValidationError("snapshot lineage_index does not exactly match item lineage")
        for reference in self.quality_issue_references:
            entry = issues.get(reference.issue_id)
            if entry is None:
                raise ProductIntelligenceValidationError(f"orphan quality issue: {reference.issue_id}")
            issue, source_fingerprints = entry
            source_observation_ids = {
                item for item in issue.source_references if item.startswith("obs:")
            }
            source_raw_ids = {
                item for item in issue.source_references if item.startswith("raw:")
            }
            if len(source_observation_ids) + len(source_raw_ids) != len(issue.source_references):
                raise ProductIntelligenceValidationError(
                    f"quality issue has unsupported source reference: {reference.issue_id}"
                )
            if any(not any(key[0] == item for key in observations) for item in source_observation_ids):
                raise ProductIntelligenceValidationError(f"quality issue observation orphan: {reference.issue_id}")
            if not source_raw_ids <= raw_ids:
                raise ProductIntelligenceValidationError(f"quality issue raw evidence orphan: {reference.issue_id}")
            expected_lineages = tuple(sorted(
                (
                    lineage
                    for lineage in self.lineage_index
                    if lineage.observation_id in source_observation_ids
                ),
                key=canonical_json,
            ))
            expected_raw_ids = source_raw_ids | {item.raw_evidence_id for item in expected_lineages}
            related_runs = {
                run_id: run_entry[0]
                for run_id, run_entry in runs.items()
                if expected_raw_ids.intersection(run_entry[0].input_raw_evidence_references)
                or run_id == issue.transformation_run_id
            }
            expected_collections = {item.collection_run_id for item in related_runs.values()}
            if issue.collection_run_id is not None:
                expected_collections.add(issue.collection_run_id)
            expected_mappings = {item.mapping_version for item in related_runs.values()}
            if issue.mapping_version is not None:
                expected_mappings.add(issue.mapping_version)
            expected_providers = {item.provider for item in related_runs.values()}
            expected_source_tools = {
                observation.provenance.source_tool
                for (observation_id, run_id), (observation, _) in observations.items()
                if run_id in related_runs or observation_id in source_observation_ids
            }
            if (
                reference.issue_code != issue.issue_code
                or reference.severity != issue.severity
                or reference.source_references != tuple(sorted(set(issue.source_references)))
                or reference.collection_run_id != issue.collection_run_id
                or reference.transformation_run_id != issue.transformation_run_id
                or reference.mapping_version != issue.mapping_version
                or set(reference.raw_evidence_ids) != expected_raw_ids
                or set(reference.collection_run_ids) != expected_collections
                or set(reference.transformation_run_ids) != set(related_runs)
                or set(reference.mapping_versions) != expected_mappings
                or set(reference.providers) != expected_providers
                or set(reference.source_tools) != expected_source_tools
                or reference.observation_lineage_references != expected_lineages
                or set(reference.source_bundle_fingerprints) != source_fingerprints
            ):
                raise ProductIntelligenceValidationError(f"quality issue lineage mismatch: {reference.issue_id}")
        included = {item.product_id for item in self.included_product_identities}
        for fact_set in self.product_fact_evidence_sets:
            if fact_set.subject_product_identity.product_id not in included:
                raise ProductIntelligenceValidationError("scope-external fact set")
        for series in self.product_metric_series:
            if series.subject_product_identity.product_id not in included:
                raise ProductIntelligenceValidationError("scope-external metric series")
        # Lineage replay proves every reference exists. Deterministic source replay
        # additionally proves that no derived value, count, grouping, topology, or
        # diagnostic was altered while retaining valid source references.
        from .builder_v0_1 import ProductIntelligenceBuilderV0_1

        expected = ProductIntelligenceBuilderV0_1()._build_snapshot(
            ProductIntelligenceRequest(
                target_product_identity=self.target_product_identity,
                scope=self.scope,
                canonical_bundles=tuple(bundles),
            )
        )
        if self.to_dict() != expected.to_dict():
            raise ProductIntelligenceValidationError(
                "snapshot content does not match deterministic replay from supplied bundles"
            )
        return self


__all__ = (
    "PRODUCT_INTELLIGENCE_RULESET_VERSION",
    "ProductScope",
    "FactCandidateState",
    "LineageReference",
    "EvidenceCandidate",
    "ProductFactEvidenceSet",
    "ProductMetricSeries",
    "ProductIntelligenceDiagnostic",
    "VariationEdge",
    "VariationTopology",
    "ReviewEvidenceSummary",
    "QualityIssueReference",
    "OutOfScopeObservationReference",
    "EvidenceCoverageSummary",
    "ProductIntelligenceRequest",
    "ProductIntelligenceSnapshotV0_1",
)
