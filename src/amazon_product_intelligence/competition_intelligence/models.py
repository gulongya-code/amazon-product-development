"""Immutable public data models for Competition Intelligence V0.1."""

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
    EvidenceType,
    JsonContract,
    KeywordIdentity,
    ObservationKind,
    PresenceStatus,
    ProductFactObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    RelationshipDirection,
    RelationshipType,
    ResultStatus,
    Scope,
    SemanticStatus,
    Severity,
    TimeWindow,
    ValueEnvelope,
    canonical_json,
    deterministic_id,
)

from .errors import CompetitionIntelligenceValidationError, CompetitionSerializationError


COMPETITION_INTELLIGENCE_RULESET_VERSION = "competition-intelligence-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class EvidenceClassification(StrEnum):
    """Separate canonical evidence from organizational derivations."""

    DIRECT_EVIDENCE = "DIRECT_EVIDENCE"
    DERIVED_EVIDENCE = "DERIVED_EVIDENCE"


class EvidenceGraphEdgeType(StrEnum):
    """Closed graph edge namespace; it intentionally has no competitor edge."""

    KEYWORD_OBSERVED_RELATIONSHIP = "keyword_observed_relationship"
    VARIATION_RELATIONSHIP = "variation_relationship"


class CompetitionSourceRecordType(StrEnum):
    """Canonical observation roles used by replayable lineage."""

    PRODUCT_OBSERVATION = "PRODUCT_OBSERVATION"
    KEYWORD_PRODUCT_RELATIONSHIP = "KEYWORD_PRODUCT_RELATIONSHIP"
    VARIATION_RELATIONSHIP = "VARIATION_RELATIONSHIP"


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise CompetitionIntelligenceValidationError(
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
        raise CompetitionIntelligenceValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise CompetitionIntelligenceValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise CompetitionIntelligenceValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise CompetitionIntelligenceValidationError(f"{path} must be {expected.__name__}")


def _mapping(value: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise CompetitionIntelligenceValidationError(f"{path} must be an object")
    if any(type(key) is not str for key in value):
        raise CompetitionIntelligenceValidationError(f"{path} keys must be strings")
    return _freeze_json(value, path)


def _unique_texts(value: Sequence[str], path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise CompetitionIntelligenceValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item for item in values):
        raise CompetitionIntelligenceValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise CompetitionIntelligenceValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(value: Sequence[Any], expected: type, path: str, key) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise CompetitionIntelligenceValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise CompetitionIntelligenceValidationError(f"{path} contains duplicates")
    return ordered


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


class _CompetitionModel(JsonContract):
    """Strictly decode public models while translating contract errors."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except CompetitionSerializationError:
            raise
        except (CompetitionIntelligenceValidationError, ContractValidationError, TypeError, ValueError) as exc:
            raise CompetitionSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionLineageReference(_CompetitionModel):
    """Replayable canonical observation-to-collection lineage."""

    observation_id: str
    semantic_observation_id: str
    observation_kind: ObservationKind
    source_record_type: CompetitionSourceRecordType
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
            "observation_id", "semantic_observation_id", "transformation_run_id",
            "mapping_version", "raw_evidence_id", "collection_run_id", "provider",
            "source_tool", "source_field",
        ):
            _text(getattr(self, name), f"CompetitionLineageReference.{name}")
        _instance(self.observation_kind, ObservationKind, "lineage observation_kind")
        _instance(self.source_record_type, CompetitionSourceRecordType, "lineage source_record_type")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise CompetitionIntelligenceValidationError("lineage fingerprints must be lowercase SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionRelationshipEvidence(_CompetitionModel):
    """One direct canonical keyword-product relationship observation."""

    observation_id: str
    semantic_observation_id: str
    classification: EvidenceClassification
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
    lineage_references: tuple[CompetitionLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "observation_id", "semantic_observation_id", "relationship_id", "provider", "source_tool"
        ):
            _text(getattr(self, name), f"CompetitionRelationshipEvidence.{name}")
        if self.classification is not EvidenceClassification.DIRECT_EVIDENCE:
            raise CompetitionIntelligenceValidationError("canonical relationship must be DIRECT_EVIDENCE")
        for value, expected, path in (
            (self.product_identity, ProductIdentity, "relationship product_identity"),
            (self.keyword_identity, KeywordIdentity, "relationship keyword_identity"),
            (self.direction, RelationshipDirection, "relationship direction"),
            (self.relationship_type, RelationshipType, "relationship relationship_type"),
            (self.channel, Channel, "relationship channel"),
            (self.query_result_status, ResultStatus, "relationship query_result_status"),
            (self.evidence_type, EvidenceType, "relationship evidence_type"),
            (self.value, ValueEnvelope, "relationship value"),
            (self.scope, Scope, "relationship scope"),
            (self.time, TimeWindow, "relationship time"),
            (self.result_status, ResultStatus, "relationship result_status"),
        ):
            _instance(value, expected, path)
        _optional_text(self.provider_semantic, "relationship provider_semantic")
        if self.rank is not None:
            object.__setattr__(self, "rank", _mapping(self.rank, "relationship rank"))
        if self.traffic is not None:
            _instance(self.traffic, ValueEnvelope, "relationship traffic")
        lineages = _typed_unique(
            self.lineage_references, CompetitionLineageReference,
            "relationship lineage_references", canonical_json,
        )
        if not lineages or any(
            item.observation_id != self.observation_id
            or item.semantic_observation_id != self.semantic_observation_id
            or item.observation_kind is not ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP
            or item.source_record_type is not CompetitionSourceRecordType.KEYWORD_PRODUCT_RELATIONSHIP
            for item in lineages
        ):
            raise CompetitionIntelligenceValidationError("relationship lineage mismatch")
        object.__setattr__(self, "lineage_references", lineages)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionVariationEvidence(_CompetitionModel):
    """One direct confirmed canonical variation relationship observation."""

    variation_evidence_id: str
    observation_id: str
    semantic_observation_id: str
    classification: EvidenceClassification
    parent_product_identity: ProductIdentity
    child_product_identity: ProductIdentity
    source_dimension: str
    evidence_type: EvidenceType
    value: ValueEnvelope
    scope: Scope
    time: TimeWindow
    result_status: ResultStatus
    provider_semantic: str | None
    provider: str
    source_tool: str
    lineage_references: tuple[CompetitionLineageReference, ...]

    def __post_init__(self) -> None:
        for name in (
            "variation_evidence_id", "observation_id", "semantic_observation_id",
            "source_dimension", "provider", "source_tool",
        ):
            _text(getattr(self, name), f"CompetitionVariationEvidence.{name}")
        if self.classification is not EvidenceClassification.DIRECT_EVIDENCE:
            raise CompetitionIntelligenceValidationError("canonical variation must be DIRECT_EVIDENCE")
        if self.source_dimension not in {"child_product_relationship", "parent_product_relationship"}:
            raise CompetitionIntelligenceValidationError("unsupported variation source dimension")
        for value, expected, path in (
            (self.parent_product_identity, ProductIdentity, "variation parent"),
            (self.child_product_identity, ProductIdentity, "variation child"),
            (self.evidence_type, EvidenceType, "variation evidence_type"),
            (self.value, ValueEnvelope, "variation value"),
            (self.scope, Scope, "variation scope"),
            (self.time, TimeWindow, "variation time"),
            (self.result_status, ResultStatus, "variation result_status"),
        ):
            _instance(value, expected, path)
        if self.parent_product_identity.marketplace != self.child_product_identity.marketplace:
            raise CompetitionIntelligenceValidationError("variation endpoints must share marketplace")
        if self.parent_product_identity.product_id == self.child_product_identity.product_id:
            raise CompetitionIntelligenceValidationError("variation evidence cannot be a self-loop")
        _optional_text(self.provider_semantic, "variation provider_semantic")
        lineages = _typed_unique(
            self.lineage_references, CompetitionLineageReference,
            "variation lineage_references", canonical_json,
        )
        if not lineages or any(
            item.observation_id != self.observation_id
            or item.semantic_observation_id != self.semantic_observation_id
            or item.observation_kind is not ObservationKind.PRODUCT_FACT
            or item.source_record_type is not CompetitionSourceRecordType.VARIATION_RELATIONSHIP
            for item in lineages
        ):
            raise CompetitionIntelligenceValidationError("variation lineage mismatch")
        object.__setattr__(self, "lineage_references", lineages)
        if self.variation_evidence_id != deterministic_id(
            "competition-variation", _without_id(self, "variation_evidence_id")
        ):
            raise CompetitionIntelligenceValidationError("variation_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionProductEvidence(_CompetitionModel):
    """Derived inventory entry for one product observed in supplied evidence."""

    product_evidence_id: str
    classification: EvidenceClassification
    product_identity: ProductIdentity
    source_observation_ids: tuple[str, ...]
    keywords: tuple[KeywordIdentity, ...]
    directions: tuple[RelationshipDirection, ...]
    channels: tuple[Channel, ...]
    providers: tuple[str, ...]
    source_tools: tuple[str, ...]
    lineage_references: tuple[CompetitionLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.product_evidence_id, "product evidence id")
        if self.classification is not EvidenceClassification.DERIVED_EVIDENCE:
            raise CompetitionIntelligenceValidationError("product inventory must be DERIVED_EVIDENCE")
        _instance(self.product_identity, ProductIdentity, "product evidence identity")
        source_ids = _unique_texts(
            self.source_observation_ids, "product source_observation_ids", allow_empty=False
        )
        keywords = _typed_unique(self.keywords, KeywordIdentity, "product keywords", canonical_json)
        directions = _typed_unique(
            self.directions, RelationshipDirection, "product directions", lambda item: item.value
        )
        channels = _typed_unique(self.channels, Channel, "product channels", lambda item: item.value)
        providers = _unique_texts(self.providers, "product providers", allow_empty=False)
        source_tools = _unique_texts(self.source_tools, "product source_tools", allow_empty=False)
        lineages = _typed_unique(
            self.lineage_references, CompetitionLineageReference,
            "product lineage_references", canonical_json,
        )
        if not lineages or {item.observation_id for item in lineages} != set(source_ids):
            raise CompetitionIntelligenceValidationError("product evidence lineage mismatch")
        object.__setattr__(self, "source_observation_ids", source_ids)
        object.__setattr__(self, "keywords", keywords)
        object.__setattr__(self, "directions", directions)
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "source_tools", source_tools)
        object.__setattr__(self, "lineage_references", lineages)
        if self.product_evidence_id != deterministic_id(
            "competition-product-evidence", _without_id(self, "product_evidence_id")
        ):
            raise CompetitionIntelligenceValidationError("product_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionKeywordEvidence(_CompetitionModel):
    """Derived keyword view referencing direct relationship observations."""

    keyword_evidence_id: str
    classification: EvidenceClassification
    keyword_identity: KeywordIdentity
    product_identities: tuple[ProductIdentity, ...]
    relationship_observation_ids: tuple[str, ...]
    directions: tuple[RelationshipDirection, ...]
    channels: tuple[Channel, ...]
    providers: tuple[str, ...]
    lineage_references: tuple[CompetitionLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.keyword_evidence_id, "keyword evidence id")
        if self.classification is not EvidenceClassification.DERIVED_EVIDENCE:
            raise CompetitionIntelligenceValidationError("keyword view must be DERIVED_EVIDENCE")
        _instance(self.keyword_identity, KeywordIdentity, "keyword evidence identity")
        products = _typed_unique(
            self.product_identities, ProductIdentity, "keyword product_identities",
            lambda item: item.product_id,
        )
        if not products:
            raise CompetitionIntelligenceValidationError("keyword evidence requires observed products")
        ids = _unique_texts(
            self.relationship_observation_ids,
            "keyword relationship_observation_ids",
            allow_empty=False,
        )
        directions = _typed_unique(
            self.directions, RelationshipDirection, "keyword directions", lambda item: item.value
        )
        channels = _typed_unique(self.channels, Channel, "keyword channels", lambda item: item.value)
        providers = _unique_texts(self.providers, "keyword providers", allow_empty=False)
        lineages = _typed_unique(
            self.lineage_references, CompetitionLineageReference,
            "keyword lineage_references", canonical_json,
        )
        if {item.observation_id for item in lineages} != set(ids):
            raise CompetitionIntelligenceValidationError("keyword evidence lineage mismatch")
        object.__setattr__(self, "product_identities", products)
        object.__setattr__(self, "relationship_observation_ids", ids)
        object.__setattr__(self, "directions", directions)
        object.__setattr__(self, "channels", channels)
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "lineage_references", lineages)
        if self.keyword_evidence_id != deterministic_id(
            "competition-keyword-evidence", _without_id(self, "keyword_evidence_id")
        ):
            raise CompetitionIntelligenceValidationError("keyword_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionEvidenceGraphNode(_CompetitionModel):
    """Derived graph node for one observed product identity."""

    graph_node_id: str
    classification: EvidenceClassification
    product_identity: ProductIdentity
    source_observation_ids: tuple[str, ...]
    lineage_references: tuple[CompetitionLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.graph_node_id, "graph node id")
        if self.classification is not EvidenceClassification.DERIVED_EVIDENCE:
            raise CompetitionIntelligenceValidationError("graph node must be DERIVED_EVIDENCE")
        _instance(self.product_identity, ProductIdentity, "graph node product_identity")
        ids = _unique_texts(self.source_observation_ids, "graph node source ids", allow_empty=False)
        lineages = _typed_unique(
            self.lineage_references, CompetitionLineageReference,
            "graph node lineages", canonical_json,
        )
        if {item.observation_id for item in lineages} != set(ids):
            raise CompetitionIntelligenceValidationError("graph node lineage mismatch")
        object.__setattr__(self, "source_observation_ids", ids)
        object.__setattr__(self, "lineage_references", lineages)
        if self.graph_node_id != deterministic_id(
            "competition-graph-node", _without_id(self, "graph_node_id")
        ):
            raise CompetitionIntelligenceValidationError("graph_node_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionEvidenceGraphEdge(_CompetitionModel):
    """Derived evidence-backed incidence edge; never a competitor edge."""

    graph_edge_id: str
    classification: EvidenceClassification
    edge_type: EvidenceGraphEdgeType
    endpoint_product_identities: tuple[ProductIdentity, ...]
    keyword_identity: KeywordIdentity | None
    variation_parent_product_identity: ProductIdentity | None
    variation_child_product_identity: ProductIdentity | None
    source_observation_ids: tuple[str, ...]
    providers: tuple[str, ...]
    lineage_references: tuple[CompetitionLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.graph_edge_id, "graph edge id")
        if self.classification is not EvidenceClassification.DERIVED_EVIDENCE:
            raise CompetitionIntelligenceValidationError("graph edge must be DERIVED_EVIDENCE")
        _instance(self.edge_type, EvidenceGraphEdgeType, "graph edge type")
        endpoints = _typed_unique(
            self.endpoint_product_identities, ProductIdentity,
            "graph edge endpoint_product_identities", lambda item: item.product_id,
        )
        if self.edge_type is EvidenceGraphEdgeType.KEYWORD_OBSERVED_RELATIONSHIP:
            if len(endpoints) != 1 or not isinstance(self.keyword_identity, KeywordIdentity):
                raise CompetitionIntelligenceValidationError(
                    "keyword graph edge requires one product endpoint and a keyword"
                )
            if self.variation_parent_product_identity is not None or self.variation_child_product_identity is not None:
                raise CompetitionIntelligenceValidationError(
                    "keyword graph edge cannot claim variation direction"
                )
        elif self.edge_type is EvidenceGraphEdgeType.VARIATION_RELATIONSHIP:
            if len(endpoints) != 2 or self.keyword_identity is not None:
                raise CompetitionIntelligenceValidationError(
                    "variation graph edge requires two product endpoints and no keyword"
                )
            if not isinstance(self.variation_parent_product_identity, ProductIdentity) or not isinstance(
                self.variation_child_product_identity, ProductIdentity
            ):
                raise CompetitionIntelligenceValidationError(
                    "variation graph edge requires explicit parent and child identities"
                )
            if {
                self.variation_parent_product_identity.product_id,
                self.variation_child_product_identity.product_id,
            } != {item.product_id for item in endpoints}:
                raise CompetitionIntelligenceValidationError(
                    "variation graph direction must match endpoint identities"
                )
            if self.variation_parent_product_identity.product_id == self.variation_child_product_identity.product_id:
                raise CompetitionIntelligenceValidationError("variation graph direction cannot be a self-loop")
            if endpoints[0].marketplace != endpoints[1].marketplace:
                raise CompetitionIntelligenceValidationError("variation graph endpoints must share marketplace")
        ids = _unique_texts(self.source_observation_ids, "graph edge source ids", allow_empty=False)
        providers = _unique_texts(self.providers, "graph edge providers", allow_empty=False)
        lineages = _typed_unique(
            self.lineage_references, CompetitionLineageReference,
            "graph edge lineages", canonical_json,
        )
        if {item.observation_id for item in lineages} != set(ids):
            raise CompetitionIntelligenceValidationError("graph edge lineage mismatch")
        object.__setattr__(self, "endpoint_product_identities", endpoints)
        object.__setattr__(self, "source_observation_ids", ids)
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "lineage_references", lineages)
        if self.graph_edge_id != deterministic_id(
            "competition-graph-edge", _without_id(self, "graph_edge_id")
        ):
            raise CompetitionIntelligenceValidationError("graph_edge_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionEvidenceGraph(_CompetitionModel):
    """Product-node evidence graph with unary keyword and binary variation edges."""

    nodes: tuple[CompetitionEvidenceGraphNode, ...]
    edges: tuple[CompetitionEvidenceGraphEdge, ...]

    def __post_init__(self) -> None:
        nodes = _typed_unique(
            self.nodes, CompetitionEvidenceGraphNode, "graph nodes", lambda item: item.graph_node_id
        )
        edges = _typed_unique(
            self.edges, CompetitionEvidenceGraphEdge, "graph edges", lambda item: item.graph_edge_id
        )
        node_products = {item.product_identity.product_id for item in nodes}
        endpoint_products = {
            product.product_id for edge in edges for product in edge.endpoint_product_identities
        }
        if not endpoint_products <= node_products:
            raise CompetitionIntelligenceValidationError("graph edge has an absent product node")
        object.__setattr__(self, "nodes", nodes)
        object.__setattr__(self, "edges", edges)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionQualityIssueReference(_CompetitionModel):
    """Stable inventory entry for a supplied canonical quality issue."""

    issue_id: str
    issue_code: str
    severity: Severity
    source_references: tuple[str, ...]
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.issue_id, "quality issue id")
        _text(self.issue_code, "quality issue code")
        _instance(self.severity, Severity, "quality issue severity")
        object.__setattr__(
            self, "source_references", _unique_texts(self.source_references, "quality issue sources")
        )
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints, "quality issue fingerprints", allow_empty=False
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise CompetitionIntelligenceValidationError("quality issue fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionDiagnostic(_CompetitionModel):
    """Stable non-concluding diagnostic about supplied competition-related evidence."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_observation_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "diagnostic id")
        _text(self.code, "diagnostic code")
        _instance(self.severity, Severity, "diagnostic severity")
        object.__setattr__(
            self, "related_observation_ids",
            _unique_texts(self.related_observation_ids, "diagnostic related observation ids"),
        )
        _text(self.message, "diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "competition-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise CompetitionIntelligenceValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionCoverageSummary(_CompetitionModel):
    """Evidence inventory counts; never a score, percentage, or ranking."""

    source_bundle_count: int
    raw_evidence_reference_count: int
    transformation_run_count: int
    observed_product_identity_count: int
    observed_keyword_identity_count: int
    relationship_observation_count: int
    variation_observation_count: int
    keyword_graph_edge_count: int
    variation_graph_edge_count: int
    provider_count: int
    source_tool_count: int
    channel_counts: Mapping[str, int]
    direction_counts: Mapping[str, int]
    quality_issue_count: int
    diagnostic_count: int

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count", "raw_evidence_reference_count", "transformation_run_count",
            "observed_product_identity_count", "observed_keyword_identity_count",
            "relationship_observation_count", "variation_observation_count",
            "keyword_graph_edge_count", "variation_graph_edge_count", "provider_count",
            "source_tool_count", "quality_issue_count", "diagnostic_count",
        ):
            _count(getattr(self, name), f"CompetitionCoverageSummary.{name}")
        for name in ("channel_counts", "direction_counts"):
            value = _mapping(getattr(self, name), f"CompetitionCoverageSummary.{name}")
            if any(type(item) is not int or item < 0 for item in value.values()):
                raise CompetitionIntelligenceValidationError(f"{name} values must be non-negative integers")
            object.__setattr__(self, name, value)


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
        "semantic_observation_id", "observation_id", "provenance", "quality_issue_ids", "result_status",
    ):
        payload.pop(key, None)
    time_payload = payload.get("time")
    if isinstance(time_payload, dict):
        time_payload.pop("retrieved_at", None)
    return payload


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionIntelligenceRequest(_CompetitionModel):
    """Strict immutable request containing canonical bundles only."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "request canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise CompetitionIntelligenceValidationError(
                "canonical_bundles must contain one or more CanonicalEvidenceBundle values"
            )
        fingerprinted: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise CompetitionIntelligenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprinted.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprinted}) != len(fingerprinted):
            raise CompetitionIntelligenceValidationError("duplicate canonical bundle fingerprint")
        object.__setattr__(
            self, "canonical_bundles",
            tuple(bundle for _, bundle in sorted(fingerprinted, key=lambda item: item[0])),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionIntelligenceSnapshotV0_1(_CompetitionModel):
    """Deterministic auditable inventory of competition-related evidence."""

    snapshot_id: str
    ruleset_version: str
    source_bundle_fingerprints: tuple[str, ...]
    observed_product_inventory: tuple[CompetitionProductEvidence, ...]
    relationship_evidence_graph: CompetitionEvidenceGraph
    variation_evidence: tuple[CompetitionVariationEvidence, ...]
    keyword_relationship_evidence: tuple[CompetitionRelationshipEvidence, ...]
    keyword_evidence: tuple[CompetitionKeywordEvidence, ...]
    coverage: CompetitionCoverageSummary
    quality_issue_references: tuple[CompetitionQualityIssueReference, ...]
    diagnostics: tuple[CompetitionDiagnostic, ...]
    lineage_index: tuple[CompetitionLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot id")
        if self.ruleset_version != COMPETITION_INTELLIGENCE_RULESET_VERSION:
            raise CompetitionIntelligenceValidationError("invalid Competition Intelligence ruleset version")
        sequences = (
            ("observed_product_inventory", CompetitionProductEvidence, lambda item: item.product_evidence_id),
            ("variation_evidence", CompetitionVariationEvidence, lambda item: item.variation_evidence_id),
            ("keyword_relationship_evidence", CompetitionRelationshipEvidence, lambda item: item.observation_id),
            ("keyword_evidence", CompetitionKeywordEvidence, lambda item: item.keyword_evidence_id),
            ("quality_issue_references", CompetitionQualityIssueReference, lambda item: item.issue_id),
            ("diagnostics", CompetitionDiagnostic, lambda item: item.diagnostic_id),
            ("lineage_index", CompetitionLineageReference, canonical_json),
        )
        for name, expected, key in sequences:
            object.__setattr__(self, name, _typed_unique(getattr(self, name), expected, f"snapshot {name}", key))
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints, "snapshot source_bundle_fingerprints", allow_empty=False
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise CompetitionIntelligenceValidationError("snapshot fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        _instance(self.relationship_evidence_graph, CompetitionEvidenceGraph, "snapshot relationship_evidence_graph")
        _instance(self.coverage, CompetitionCoverageSummary, "snapshot coverage")
        inventory = {item.product_identity.product_id: item.product_identity for item in self.observed_product_inventory}
        if len(inventory) != len(self.observed_product_inventory):
            raise CompetitionIntelligenceValidationError("observed product inventory contains duplicate products")
        node_products = {
            item.product_identity.product_id for item in self.relationship_evidence_graph.nodes
        }
        if node_products != set(inventory):
            raise CompetitionIntelligenceValidationError("graph nodes must exactly match product inventory")
        direct_relationship_ids = {item.observation_id for item in self.keyword_relationship_evidence}
        direct_variation_ids = {item.observation_id for item in self.variation_evidence}
        for edge in self.relationship_evidence_graph.edges:
            if edge.edge_type is EvidenceGraphEdgeType.KEYWORD_OBSERVED_RELATIONSHIP:
                if not set(edge.source_observation_ids) <= direct_relationship_ids:
                    raise CompetitionIntelligenceValidationError("keyword graph edge source is not direct evidence")
            elif not set(edge.source_observation_ids) <= direct_variation_ids:
                raise CompetitionIntelligenceValidationError("variation graph edge source is not direct evidence")
        for item in self.keyword_evidence:
            if not set(item.relationship_observation_ids) <= direct_relationship_ids:
                raise CompetitionIntelligenceValidationError("keyword view references absent direct evidence")
        lineage_ids = {item.observation_id for item in self.lineage_index}
        required_ids = direct_relationship_ids | direct_variation_ids | {
            observation_id
            for item in self.observed_product_inventory
            for observation_id in item.source_observation_ids
        }
        if not required_ids <= lineage_ids:
            raise CompetitionIntelligenceValidationError("snapshot evidence is missing lineage")
        expected_id = deterministic_id("competition-snapshot", _without_id(self, "snapshot_id"))
        if self.snapshot_id != expected_id:
            raise CompetitionSerializationError("snapshot_id does not match snapshot content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(self, bundles: Sequence[CanonicalEvidenceBundle]) -> Self:
        """Replay all lineage and bundle fingerprints against canonical source bundles."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise CompetitionIntelligenceValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[tuple[str, str], tuple[CanonicalObservation, set[str]]] = {}
        runs: dict[str, tuple[Any, set[str]]] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise CompetitionIntelligenceValidationError("against-bundles input contains a wrong type")
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise CompetitionIntelligenceValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise CompetitionIntelligenceValidationError("duplicate canonical bundle fingerprint")
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current and canonical_json(current[0]) != canonical_json(run):
                    raise CompetitionIntelligenceValidationError(
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
                    raise CompetitionIntelligenceValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    observations[key] = (observation, {fingerprint})
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise CompetitionIntelligenceValidationError(
                "snapshot source bundle fingerprints do not match supplied bundles"
            )
        for reference in self.lineage_index:
            key = (reference.observation_id, reference.transformation_run_id)
            entry = observations.get(key)
            if entry is None:
                raise CompetitionIntelligenceValidationError(
                    f"orphan observation lineage: {reference.observation_id}"
                )
            observation, source_fingerprints = entry
            if (
                reference.source_record_type
                is CompetitionSourceRecordType.KEYWORD_PRODUCT_RELATIONSHIP
                and not isinstance(observation, ProductKeywordRelationshipObservation)
            ):
                raise CompetitionIntelligenceValidationError(
                    f"wrong keyword relationship lineage type: {reference.observation_id}"
                )
            if reference.source_record_type is CompetitionSourceRecordType.VARIATION_RELATIONSHIP:
                if (
                    not isinstance(observation, ProductFactObservation)
                    or observation.dimension not in {
                        "child_product_relationship",
                        "parent_product_relationship",
                    }
                    or observation.value.presence_status is not PresenceStatus.PRESENT
                    or observation.value.semantic_status is not SemanticStatus.CONFIRMED
                ):
                    raise CompetitionIntelligenceValidationError(
                        f"wrong variation lineage type: {reference.observation_id}"
                    )
            if (
                reference.source_record_type is CompetitionSourceRecordType.PRODUCT_OBSERVATION
                and isinstance(observation, ProductKeywordRelationshipObservation)
            ):
                raise CompetitionIntelligenceValidationError(
                    f"wrong product observation lineage type: {reference.observation_id}"
                )
            transformation = observation.provenance.transformation
            run_entry = runs.get(reference.transformation_run_id)
            if run_entry is None:
                raise CompetitionIntelligenceValidationError(
                    f"orphan transformation lineage: {reference.transformation_run_id}"
                )
            run = run_entry[0]
            checks = (
                (reference.semantic_observation_id, observation.semantic_observation_id, "semantic observation"),
                (reference.observation_kind, observation.observation_kind, "observation kind"),
                (reference.transformation_run_id, transformation.transformation_run_id, "transformation run"),
                (reference.mapping_version, transformation.mapping_version, "mapping"),
                (reference.raw_evidence_id, transformation.raw_evidence_reference, "raw evidence"),
                (reference.collection_run_id, transformation.collection_run_id, "collection"),
                (reference.provider, observation.provenance.provider, "provider"),
                (reference.source_tool, observation.provenance.source_tool, "source tool"),
                (reference.source_field, observation.provenance.source_field, "source field"),
                (set(reference.source_bundle_fingerprints), source_fingerprints, "bundle fingerprint"),
            )
            mismatch = next((label for left, right, label in checks if left != right), None)
            if mismatch is not None:
                raise CompetitionIntelligenceValidationError(
                    f"lineage {mismatch} mismatch for {reference.observation_id}"
                )
            if reference.raw_evidence_id not in raw_ids or reference.raw_evidence_id not in run.input_raw_evidence_references:
                raise CompetitionIntelligenceValidationError(
                    f"orphan raw evidence lineage: {reference.raw_evidence_id}"
                )
            if run.collection_run_id != reference.collection_run_id or run.mapping_version != reference.mapping_version:
                raise CompetitionIntelligenceValidationError(
                    f"run lineage mismatch for {reference.observation_id}"
                )
        return self.validate()


__all__ = (
    "COMPETITION_INTELLIGENCE_RULESET_VERSION",
    "EvidenceClassification",
    "EvidenceGraphEdgeType",
    "CompetitionSourceRecordType",
    "CompetitionLineageReference",
    "CompetitionRelationshipEvidence",
    "CompetitionVariationEvidence",
    "CompetitionProductEvidence",
    "CompetitionKeywordEvidence",
    "CompetitionEvidenceGraphNode",
    "CompetitionEvidenceGraphEdge",
    "CompetitionEvidenceGraph",
    "CompetitionQualityIssueReference",
    "CompetitionDiagnostic",
    "CompetitionCoverageSummary",
    "CompetitionIntelligenceRequest",
    "CompetitionIntelligenceSnapshotV0_1",
)
