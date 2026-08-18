"""Immutable public data models for Opportunity Intelligence V0.1."""

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
    ContractValidationError,
    DirectionalQueryExecutionRecord,
    JsonContract,
    KeywordMetricObservation,
    MetricObservation,
    ObservationKind,
    ProductFactObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    ReviewObservation,
    Severity,
    KeywordIdentity,
    canonical_json,
    deterministic_id,
)

from .errors import OpportunitySerializationError, OpportunityValidationError


OPPORTUNITY_INTELLIGENCE_RULESET_VERSION = "opportunity-intelligence-v0.1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class OpportunitySignalClassification(StrEnum):
    """Closed classification namespace with no score or conclusion state."""

    OBSERVED_SIGNAL = "OBSERVED_SIGNAL"
    DERIVED_SIGNAL = "DERIVED_SIGNAL"
    MISSING_EVIDENCE_SIGNAL = "MISSING_EVIDENCE_SIGNAL"
    RISK_EVIDENCE = "RISK_EVIDENCE"


class OpportunitySignalType(StrEnum):
    """Evidence-existence signal types; none expresses quality or desirability."""

    PRODUCT_FACT_OBSERVED = "PRODUCT_FACT_OBSERVED"
    PRODUCT_METRIC_OBSERVED = "PRODUCT_METRIC_OBSERVED"
    KEYWORD_METRIC_OBSERVED = "KEYWORD_METRIC_OBSERVED"
    KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED = "KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED"
    QUERY_EXECUTION_OBSERVED = "QUERY_EXECUTION_OBSERVED"
    REVIEW_OBSERVED = "REVIEW_OBSERVED"
    VARIATION_RELATIONSHIP_OBSERVED = "VARIATION_RELATIONSHIP_OBSERVED"
    PRODUCT_EVIDENCE_PRESENT = "PRODUCT_EVIDENCE_PRESENT"
    KEYWORD_EVIDENCE_PRESENT = "KEYWORD_EVIDENCE_PRESENT"
    RELATIONSHIP_EVIDENCE_PRESENT = "RELATIONSHIP_EVIDENCE_PRESENT"
    CONFIRMED_VARIATION_EVIDENCE_PRESENT = "CONFIRMED_VARIATION_EVIDENCE_PRESENT"


class OpportunitySourceRecordType(StrEnum):
    """Canonical source-record roles used for strict lineage replay."""

    PRODUCT_FACT = "PRODUCT_FACT"
    PRODUCT_METRIC = "PRODUCT_METRIC"
    KEYWORD_METRIC = "KEYWORD_METRIC"
    KEYWORD_PRODUCT_RELATIONSHIP = "KEYWORD_PRODUCT_RELATIONSHIP"
    QUERY_EXECUTION = "QUERY_EXECUTION"
    REVIEW = "REVIEW"


class OpportunityMissingEvidenceKind(StrEnum):
    """Explicit categories evaluated for presence without negative interpretation."""

    PRODUCT_FACT_EVIDENCE = "PRODUCT_FACT_EVIDENCE"
    PRODUCT_METRIC_EVIDENCE = "PRODUCT_METRIC_EVIDENCE"
    KEYWORD_EVIDENCE = "KEYWORD_EVIDENCE"
    KEYWORD_PRODUCT_RELATIONSHIP_EVIDENCE = "KEYWORD_PRODUCT_RELATIONSHIP_EVIDENCE"
    QUERY_EXECUTION_EVIDENCE = "QUERY_EXECUTION_EVIDENCE"
    COMPETITION_RELATED_EVIDENCE = "COMPETITION_RELATED_EVIDENCE"
    VARIATION_EVIDENCE = "VARIATION_EVIDENCE"
    REVIEW_EVIDENCE = "REVIEW_EVIDENCE"
    PRICE_EVIDENCE = "PRICE_EVIDENCE"


class OpportunityRiskType(StrEnum):
    """Evidence limitations, never a risk score or investment conclusion."""

    UNKNOWN_PERIOD = "UNKNOWN_PERIOD"
    UNKNOWN_OBSERVATION_TIME = "UNKNOWN_OBSERVATION_TIME"
    PROVIDER_METHOD_UNDECLARED = "PROVIDER_METHOD_UNDECLARED"
    SINGLE_PROVIDER_EVIDENCE = "SINGLE_PROVIDER_EVIDENCE"
    QUERY_OUTCOME_LIMITATION = "QUERY_OUTCOME_LIMITATION"
    REVIEW_EVIDENCE_ABSENT = "REVIEW_EVIDENCE_ABSENT"


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise OpportunityValidationError(f"{path} must contain finite JSON data: {exc}") from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OpportunityValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OpportunityValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise OpportunityValidationError(f"{path} must be a non-negative integer")
    return value


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise OpportunityValidationError(f"{path} must be {expected.__name__}")


def _mapping(value: Mapping[str, Any], path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise OpportunityValidationError(f"{path} must be an object")
    if any(type(key) is not str for key in value):
        raise OpportunityValidationError(f"{path} keys must be strings")
    return _freeze_json(value, path)


def _unique_texts(value: Sequence[str], path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise OpportunityValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item for item in values):
        raise OpportunityValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise OpportunityValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(value: Sequence[Any], expected: type, path: str, key) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise OpportunityValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise OpportunityValidationError(f"{path} contains duplicates")
    return ordered


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


class _OpportunityModel(JsonContract):
    """Strictly decode public models and translate contract errors."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OpportunitySerializationError:
            raise
        except (OpportunityValidationError, ContractValidationError, TypeError, ValueError) as exc:
            raise OpportunitySerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityLineageReference(_OpportunityModel):
    """Replayable canonical observation/query-to-collection lineage."""

    source_record_id: str
    source_record_type: OpportunitySourceRecordType
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
            "source_record_id", "transformation_run_id", "mapping_version",
            "raw_evidence_id", "collection_run_id", "provider", "source_tool", "source_field",
        ):
            _text(getattr(self, name), f"OpportunityLineageReference.{name}")
        _instance(self.source_record_type, OpportunitySourceRecordType, "lineage source_record_type")
        if self.source_record_type is OpportunitySourceRecordType.QUERY_EXECUTION:
            if self.semantic_observation_id is not None or self.observation_kind is not None:
                raise OpportunityValidationError("query lineage cannot claim observation identity")
        else:
            _text(self.semantic_observation_id, "lineage semantic_observation_id")
            _instance(self.observation_kind, ObservationKind, "lineage observation_kind")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints,
            "lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise OpportunityValidationError("lineage fingerprints must be lowercase SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)


_OBSERVED_SIGNAL_TYPES = {
    OpportunitySignalType.PRODUCT_FACT_OBSERVED,
    OpportunitySignalType.PRODUCT_METRIC_OBSERVED,
    OpportunitySignalType.KEYWORD_METRIC_OBSERVED,
    OpportunitySignalType.KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED,
    OpportunitySignalType.QUERY_EXECUTION_OBSERVED,
    OpportunitySignalType.REVIEW_OBSERVED,
    OpportunitySignalType.VARIATION_RELATIONSHIP_OBSERVED,
}
_DERIVED_SIGNAL_TYPES = {
    OpportunitySignalType.PRODUCT_EVIDENCE_PRESENT,
    OpportunitySignalType.KEYWORD_EVIDENCE_PRESENT,
    OpportunitySignalType.RELATIONSHIP_EVIDENCE_PRESENT,
    OpportunitySignalType.CONFIRMED_VARIATION_EVIDENCE_PRESENT,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunitySignalEvidence(_OpportunityModel):
    """One observed or mechanically derived evidence-existence signal."""

    signal_id: str
    classification: OpportunitySignalClassification
    signal_type: OpportunitySignalType
    product_identities: tuple[ProductIdentity, ...]
    keyword_identities: tuple[KeywordIdentity, ...]
    source_record_ids: tuple[str, ...]
    supporting_signal_ids: tuple[str, ...]
    providers: tuple[str, ...]
    source_tools: tuple[str, ...]
    evidence_attributes: Mapping[str, Any]
    lineage_references: tuple[OpportunityLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.signal_id, "signal_id")
        _instance(self.classification, OpportunitySignalClassification, "signal classification")
        _instance(self.signal_type, OpportunitySignalType, "signal type")
        if self.classification is OpportunitySignalClassification.OBSERVED_SIGNAL:
            if self.signal_type not in _OBSERVED_SIGNAL_TYPES:
                raise OpportunityValidationError("observed signal uses a derived signal type")
        elif self.classification is OpportunitySignalClassification.DERIVED_SIGNAL:
            if self.signal_type not in _DERIVED_SIGNAL_TYPES:
                raise OpportunityValidationError("derived signal uses an observed signal type")
        else:
            raise OpportunityValidationError("OpportunitySignalEvidence must be observed or derived")
        products = _typed_unique(
            self.product_identities, ProductIdentity, "signal product_identities", canonical_json
        )
        keywords = _typed_unique(
            self.keyword_identities, KeywordIdentity, "signal keyword_identities", canonical_json
        )
        source_ids = _unique_texts(self.source_record_ids, "signal source_record_ids", allow_empty=False)
        supporting_ids = _unique_texts(self.supporting_signal_ids, "signal supporting_signal_ids")
        if self.classification is OpportunitySignalClassification.OBSERVED_SIGNAL:
            if len(source_ids) != 1 or supporting_ids:
                raise OpportunityValidationError("observed signal requires one source and no supporting signals")
        elif not supporting_ids:
            raise OpportunityValidationError("derived signal requires supporting observed signals")
        lineages = _typed_unique(
            self.lineage_references, OpportunityLineageReference,
            "signal lineage_references", canonical_json,
        )
        if not lineages or {item.source_record_id for item in lineages} != set(source_ids):
            raise OpportunityValidationError("signal lineage does not match source records")
        providers = _unique_texts(self.providers, "signal providers", allow_empty=False)
        source_tools = _unique_texts(self.source_tools, "signal source_tools", allow_empty=False)
        if set(providers) != {item.provider for item in lineages}:
            raise OpportunityValidationError("signal providers do not match lineage")
        if set(source_tools) != {item.source_tool for item in lineages}:
            raise OpportunityValidationError("signal source tools do not match lineage")
        object.__setattr__(self, "product_identities", products)
        object.__setattr__(self, "keyword_identities", keywords)
        object.__setattr__(self, "source_record_ids", source_ids)
        object.__setattr__(self, "supporting_signal_ids", supporting_ids)
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "source_tools", source_tools)
        object.__setattr__(self, "evidence_attributes", _mapping(
            self.evidence_attributes, "signal evidence_attributes"
        ))
        object.__setattr__(self, "lineage_references", lineages)
        if self.signal_id != deterministic_id("opportunity-signal", _without_id(self, "signal_id")):
            raise OpportunityValidationError("signal_id does not match signal content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityMissingEvidence(_OpportunityModel):
    """One evaluated evidence category absent from the supplied bundles."""

    missing_evidence_id: str
    classification: OpportunitySignalClassification
    evidence_kind: OpportunityMissingEvidenceKind
    basis: str
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.missing_evidence_id, "missing_evidence_id")
        if self.classification is not OpportunitySignalClassification.MISSING_EVIDENCE_SIGNAL:
            raise OpportunityValidationError("missing evidence must use MISSING_EVIDENCE_SIGNAL")
        _instance(self.evidence_kind, OpportunityMissingEvidenceKind, "missing evidence kind")
        _text(self.basis, "missing evidence basis")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints, "missing evidence fingerprints", allow_empty=False
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise OpportunityValidationError("missing evidence fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        if self.missing_evidence_id != deterministic_id(
            "opportunity-missing-evidence", _without_id(self, "missing_evidence_id")
        ):
            raise OpportunityValidationError("missing_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class MissingEvidenceInventory(_OpportunityModel):
    """Complete evaluated category inventory; absence is never negative evidence."""

    evaluated_evidence_kinds: tuple[OpportunityMissingEvidenceKind, ...]
    items: tuple[OpportunityMissingEvidence, ...]
    interpretation: str

    def __post_init__(self) -> None:
        kinds = _typed_unique(
            self.evaluated_evidence_kinds, OpportunityMissingEvidenceKind,
            "evaluated evidence kinds", lambda item: item.value,
        )
        if set(kinds) != set(OpportunityMissingEvidenceKind):
            raise OpportunityValidationError("missing evidence inventory must evaluate every V0.1 category")
        items = _typed_unique(
            self.items, OpportunityMissingEvidence,
            "missing evidence items", lambda item: item.missing_evidence_id,
        )
        if len({item.evidence_kind for item in items}) != len(items):
            raise OpportunityValidationError("missing evidence kinds must be unique")
        if self.interpretation != "MISSING_EVIDENCE_IS_NOT_NEGATIVE_EVIDENCE":
            raise OpportunityValidationError("missing evidence interpretation is fixed in V0.1")
        object.__setattr__(self, "evaluated_evidence_kinds", kinds)
        object.__setattr__(self, "items", items)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityRiskEvidence(_OpportunityModel):
    """Evidence limitation with no severity, probability, or risk score."""

    risk_evidence_id: str
    classification: OpportunitySignalClassification
    risk_type: OpportunityRiskType
    source_record_ids: tuple[str, ...]
    missing_evidence_ids: tuple[str, ...]
    providers: tuple[str, ...]
    source_tools: tuple[str, ...]
    message: str
    lineage_references: tuple[OpportunityLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.risk_evidence_id, "risk_evidence_id")
        if self.classification is not OpportunitySignalClassification.RISK_EVIDENCE:
            raise OpportunityValidationError("risk evidence must use RISK_EVIDENCE")
        _instance(self.risk_type, OpportunityRiskType, "risk type")
        source_ids = _unique_texts(self.source_record_ids, "risk source_record_ids")
        missing_ids = _unique_texts(self.missing_evidence_ids, "risk missing_evidence_ids")
        if not source_ids and not missing_ids:
            raise OpportunityValidationError("risk evidence requires source or missing evidence IDs")
        lineages = _typed_unique(
            self.lineage_references, OpportunityLineageReference,
            "risk lineage_references", canonical_json,
        )
        if {item.source_record_id for item in lineages} != set(source_ids):
            raise OpportunityValidationError("risk lineage does not match source records")
        providers = _unique_texts(self.providers, "risk providers")
        source_tools = _unique_texts(self.source_tools, "risk source_tools")
        if set(providers) != {item.provider for item in lineages}:
            raise OpportunityValidationError("risk providers do not match lineage")
        if set(source_tools) != {item.source_tool for item in lineages}:
            raise OpportunityValidationError("risk source tools do not match lineage")
        _text(self.message, "risk message")
        object.__setattr__(self, "source_record_ids", source_ids)
        object.__setattr__(self, "missing_evidence_ids", missing_ids)
        object.__setattr__(self, "providers", providers)
        object.__setattr__(self, "source_tools", source_tools)
        object.__setattr__(self, "lineage_references", lineages)
        if self.risk_evidence_id != deterministic_id(
            "opportunity-risk-evidence", _without_id(self, "risk_evidence_id")
        ):
            raise OpportunityValidationError("risk_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityQualityIssueReference(_OpportunityModel):
    """Stable inventory reference for one supplied canonical quality issue."""

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
            raise OpportunityValidationError("quality issue fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityDiagnostic(_OpportunityModel):
    """Non-concluding diagnostic about evidence organization."""

    diagnostic_id: str
    code: str
    severity: Severity
    related_source_record_ids: tuple[str, ...]
    related_evidence_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "diagnostic id")
        _text(self.code, "diagnostic code")
        _instance(self.severity, Severity, "diagnostic severity")
        object.__setattr__(self, "related_source_record_ids", _unique_texts(
            self.related_source_record_ids, "diagnostic source record ids"
        ))
        object.__setattr__(self, "related_evidence_ids", _unique_texts(
            self.related_evidence_ids, "diagnostic evidence ids"
        ))
        _text(self.message, "diagnostic message")
        if self.diagnostic_id != deterministic_id(
            "opportunity-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise OpportunityValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityCoverageSummary(_OpportunityModel):
    """Descriptive evidence counts; never completeness, confidence, or score."""

    source_bundle_count: int
    raw_evidence_reference_count: int
    transformation_run_count: int
    observed_signal_count: int
    derived_signal_count: int
    missing_evidence_count: int
    risk_evidence_count: int
    product_identity_count: int
    keyword_identity_count: int
    product_fact_observation_count: int
    product_metric_observation_count: int
    keyword_metric_observation_count: int
    relationship_observation_count: int
    query_execution_record_count: int
    review_observation_count: int
    confirmed_variation_observation_count: int
    competition_related_evidence_count: int
    provider_count: int
    source_tool_count: int
    signal_type_counts: Mapping[str, int]
    query_outcome_counts: Mapping[str, int]
    quality_issue_count: int
    diagnostic_count: int

    def __post_init__(self) -> None:
        for name in (
            "source_bundle_count", "raw_evidence_reference_count", "transformation_run_count",
            "observed_signal_count", "derived_signal_count", "missing_evidence_count",
            "risk_evidence_count", "product_identity_count", "keyword_identity_count",
            "product_fact_observation_count", "product_metric_observation_count",
            "keyword_metric_observation_count", "relationship_observation_count",
            "query_execution_record_count", "review_observation_count",
            "confirmed_variation_observation_count", "competition_related_evidence_count",
            "provider_count", "source_tool_count", "quality_issue_count", "diagnostic_count",
        ):
            _count(getattr(self, name), f"OpportunityCoverageSummary.{name}")
        for name in ("signal_type_counts", "query_outcome_counts"):
            value = _mapping(getattr(self, name), f"OpportunityCoverageSummary.{name}")
            if any(type(item) is not int or item < 0 for item in value.values()):
                raise OpportunityValidationError(f"{name} values must be non-negative integers")
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
class OpportunityIntelligenceRequest(_OpportunityModel):
    """Strict immutable request containing canonical bundles only."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "request canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise OpportunityValidationError(
                "canonical_bundles must contain one or more CanonicalEvidenceBundle values"
            )
        fingerprinted: list[tuple[str, CanonicalEvidenceBundle]] = []
        for bundle in bundles:
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise OpportunityValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprinted.append((bundle_fingerprint(bundle), bundle))
        if len({item[0] for item in fingerprinted}) != len(fingerprinted):
            raise OpportunityValidationError("duplicate canonical bundle fingerprint")
        object.__setattr__(
            self, "canonical_bundles",
            tuple(bundle for _, bundle in sorted(fingerprinted, key=lambda item: item[0])),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityIntelligenceSnapshotV0_1(_OpportunityModel):
    """Deterministic auditable view of opportunity-related evidence availability."""

    snapshot_id: str
    ruleset_version: str
    source_bundle_fingerprints: tuple[str, ...]
    observed_signals: tuple[OpportunitySignalEvidence, ...]
    derived_signals: tuple[OpportunitySignalEvidence, ...]
    missing_evidence: MissingEvidenceInventory
    risk_evidence: tuple[OpportunityRiskEvidence, ...]
    coverage: OpportunityCoverageSummary
    quality_issue_references: tuple[OpportunityQualityIssueReference, ...]
    diagnostics: tuple[OpportunityDiagnostic, ...]
    lineage_index: tuple[OpportunityLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "snapshot id")
        if self.ruleset_version != OPPORTUNITY_INTELLIGENCE_RULESET_VERSION:
            raise OpportunityValidationError("invalid Opportunity Intelligence ruleset version")
        fingerprints = _unique_texts(
            self.source_bundle_fingerprints, "snapshot source fingerprints", allow_empty=False
        )
        if any(_SHA256.fullmatch(item) is None for item in fingerprints):
            raise OpportunityValidationError("snapshot fingerprints must be SHA-256 hex")
        object.__setattr__(self, "source_bundle_fingerprints", fingerprints)
        sequences = (
            ("observed_signals", OpportunitySignalEvidence, lambda item: item.signal_id),
            ("derived_signals", OpportunitySignalEvidence, lambda item: item.signal_id),
            ("risk_evidence", OpportunityRiskEvidence, lambda item: item.risk_evidence_id),
            ("quality_issue_references", OpportunityQualityIssueReference, lambda item: item.issue_id),
            ("diagnostics", OpportunityDiagnostic, lambda item: item.diagnostic_id),
            ("lineage_index", OpportunityLineageReference, canonical_json),
        )
        for name, expected, key in sequences:
            object.__setattr__(self, name, _typed_unique(
                getattr(self, name), expected, f"snapshot {name}", key
            ))
        if any(
            item.classification is not OpportunitySignalClassification.OBSERVED_SIGNAL
            for item in self.observed_signals
        ):
            raise OpportunityValidationError("observed_signals contains a non-observed signal")
        if any(
            item.classification is not OpportunitySignalClassification.DERIVED_SIGNAL
            for item in self.derived_signals
        ):
            raise OpportunityValidationError("derived_signals contains a non-derived signal")
        _instance(self.missing_evidence, MissingEvidenceInventory, "snapshot missing_evidence")
        _instance(self.coverage, OpportunityCoverageSummary, "snapshot coverage")
        observed_ids = {item.signal_id for item in self.observed_signals}
        for item in self.derived_signals:
            if not set(item.supporting_signal_ids) <= observed_ids:
                raise OpportunityValidationError("derived signal references an absent observed signal")
        missing_ids = {item.missing_evidence_id for item in self.missing_evidence.items}
        for item in self.risk_evidence:
            if not set(item.missing_evidence_ids) <= missing_ids:
                raise OpportunityValidationError("risk evidence references absent missing evidence")
        required_source_ids = {
            source_id
            for item in self.observed_signals + self.derived_signals
            for source_id in item.source_record_ids
        } | {
            source_id for item in self.risk_evidence for source_id in item.source_record_ids
        }
        lineage_ids = {item.source_record_id for item in self.lineage_index}
        if not required_source_ids <= lineage_ids:
            raise OpportunityValidationError("snapshot evidence is missing lineage")
        checks = (
            (self.coverage.observed_signal_count, len(self.observed_signals), "observed signal"),
            (self.coverage.derived_signal_count, len(self.derived_signals), "derived signal"),
            (self.coverage.missing_evidence_count, len(self.missing_evidence.items), "missing evidence"),
            (self.coverage.risk_evidence_count, len(self.risk_evidence), "risk evidence"),
            (self.coverage.quality_issue_count, len(self.quality_issue_references), "quality issue"),
            (self.coverage.diagnostic_count, len(self.diagnostics), "diagnostic"),
        )
        mismatch = next((label for left, right, label in checks if left != right), None)
        if mismatch is not None:
            raise OpportunityValidationError(f"coverage {mismatch} count mismatch")
        expected_id = deterministic_id("opportunity-snapshot", _without_id(self, "snapshot_id"))
        if self.snapshot_id != expected_id:
            raise OpportunitySerializationError("snapshot_id does not match snapshot content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    @staticmethod
    def _source_type(record: CanonicalObservation | DirectionalQueryExecutionRecord) -> OpportunitySourceRecordType:
        if isinstance(record, ProductFactObservation):
            return OpportunitySourceRecordType.PRODUCT_FACT
        if isinstance(record, MetricObservation):
            return OpportunitySourceRecordType.PRODUCT_METRIC
        if isinstance(record, KeywordMetricObservation):
            return OpportunitySourceRecordType.KEYWORD_METRIC
        if isinstance(record, ProductKeywordRelationshipObservation):
            return OpportunitySourceRecordType.KEYWORD_PRODUCT_RELATIONSHIP
        if isinstance(record, ReviewObservation):
            return OpportunitySourceRecordType.REVIEW
        if isinstance(record, DirectionalQueryExecutionRecord):
            return OpportunitySourceRecordType.QUERY_EXECUTION
        raise OpportunityValidationError(f"unsupported canonical source type: {type(record).__name__}")

    def validate_against_bundles(self, bundles: Sequence[CanonicalEvidenceBundle]) -> Self:
        """Replay all public lineage and quality references against source bundles."""

        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise OpportunityValidationError("bundles must be a non-empty sequence")
        fingerprints: dict[str, CanonicalEvidenceBundle] = {}
        observations: dict[tuple[str, str], tuple[CanonicalObservation, set[str]]] = {}
        queries: dict[tuple[str, str], tuple[DirectionalQueryExecutionRecord, set[str]]] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, tuple[Any, set[str]]] = {}
        issues: dict[str, tuple[Any, set[str]]] = {}
        raw_ids: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise OpportunityValidationError("against-bundles input contains a wrong type")
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise OpportunityValidationError(f"invalid canonical bundle: {exc}") from exc
            fingerprint = bundle_fingerprint(bundle)
            if fingerprint in fingerprints:
                raise OpportunityValidationError("duplicate canonical bundle fingerprint")
            fingerprints[fingerprint] = bundle
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current and canonical_json(current[0]) != canonical_json(run):
                    raise OpportunityValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    runs[run.transformation_run_id] = (run, {fingerprint})
            for observation in bundle.observations:
                content = canonical_json(observation_revision_content(observation))
                if observation.observation_id in revisions and revisions[observation.observation_id] != content:
                    raise OpportunityValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = content
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                current = observations.get(key)
                if current and canonical_json(current[0]) != canonical_json(observation):
                    raise OpportunityValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    observations[key] = (observation, {fingerprint})
            for query in bundle.query_execution_records:
                run_id = query.provenance.transformation.transformation_run_id
                key = (query.query_execution_id, run_id)
                current = queries.get(key)
                if current and canonical_json(current[0]) != canonical_json(query):
                    raise OpportunityValidationError(
                        f"query execution identity collision: {query.query_execution_id}"
                    )
                if current:
                    current[1].add(fingerprint)
                else:
                    queries[key] = (query, {fingerprint})
            for issue in bundle.quality_issues:
                current = issues.get(issue.issue_id)
                if current and canonical_json(current[0]) != canonical_json(issue):
                    raise OpportunityValidationError(f"quality issue identity collision: {issue.issue_id}")
                if current:
                    current[1].add(fingerprint)
                else:
                    issues[issue.issue_id] = (issue, {fingerprint})
        if set(fingerprints) != set(self.source_bundle_fingerprints):
            raise OpportunityValidationError(
                "snapshot source bundle fingerprints do not match supplied bundles"
            )
        for reference in self.lineage_index:
            key = (reference.source_record_id, reference.transformation_run_id)
            if reference.source_record_type is OpportunitySourceRecordType.QUERY_EXECUTION:
                entry = queries.get(key)
            else:
                entry = observations.get(key)
            if entry is None:
                raise OpportunityValidationError(
                    f"orphan canonical lineage: {reference.source_record_id}"
                )
            record, source_fingerprints = entry
            expected_type = self._source_type(record)
            if reference.source_record_type is not expected_type:
                raise OpportunityValidationError(
                    f"wrong lineage source type: {reference.source_record_id}"
                )
            if isinstance(record, DirectionalQueryExecutionRecord):
                semantic_id = None
                observation_kind = None
            else:
                semantic_id = record.semantic_observation_id
                observation_kind = record.observation_kind
            transformation = record.provenance.transformation
            run_entry = runs.get(reference.transformation_run_id)
            if run_entry is None:
                raise OpportunityValidationError(
                    f"orphan transformation lineage: {reference.transformation_run_id}"
                )
            run = run_entry[0]
            checks = (
                (reference.semantic_observation_id, semantic_id, "semantic observation"),
                (reference.observation_kind, observation_kind, "observation kind"),
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
                raise OpportunityValidationError(
                    f"lineage {mismatch} mismatch for {reference.source_record_id}"
                )
            if (
                reference.raw_evidence_id not in raw_ids
                or reference.raw_evidence_id not in run.input_raw_evidence_references
            ):
                raise OpportunityValidationError(
                    f"orphan raw evidence lineage: {reference.raw_evidence_id}"
                )
            if (
                run.collection_run_id != reference.collection_run_id
                or run.mapping_version != reference.mapping_version
            ):
                raise OpportunityValidationError(
                    f"run lineage mismatch for {reference.source_record_id}"
                )
            outputs = (
                run.output_query_execution_ids
                if isinstance(record, DirectionalQueryExecutionRecord)
                else run.output_observation_ids
            )
            if reference.source_record_id not in outputs:
                raise OpportunityValidationError(
                    f"transformation output mismatch: {reference.source_record_id}"
                )
        referenced = {
            canonical_json(lineage)
            for item in self.observed_signals + self.derived_signals
            for lineage in item.lineage_references
        } | {
            canonical_json(lineage)
            for item in self.risk_evidence
            for lineage in item.lineage_references
        }
        indexed = {canonical_json(item) for item in self.lineage_index}
        if indexed != referenced:
            raise OpportunityValidationError(
                "snapshot lineage_index does not exactly match evidence lineage"
            )
        if {item.issue_id for item in self.quality_issue_references} != set(issues):
            raise OpportunityValidationError("quality issue reference inventory mismatch")
        for reference in self.quality_issue_references:
            issue, source_fingerprints = issues[reference.issue_id]
            checks = (
                (reference.issue_code, issue.issue_code),
                (reference.severity, issue.severity),
                (set(reference.source_references), set(issue.source_references)),
                (set(reference.source_bundle_fingerprints), source_fingerprints),
            )
            if any(left != right for left, right in checks):
                raise OpportunityValidationError(
                    f"quality issue reference mismatch: {reference.issue_id}"
                )
        return self.validate()


__all__ = (
    "OPPORTUNITY_INTELLIGENCE_RULESET_VERSION",
    "OpportunitySignalClassification",
    "OpportunitySignalType",
    "OpportunitySourceRecordType",
    "OpportunityMissingEvidenceKind",
    "OpportunityRiskType",
    "OpportunityLineageReference",
    "OpportunitySignalEvidence",
    "OpportunityMissingEvidence",
    "MissingEvidenceInventory",
    "OpportunityRiskEvidence",
    "OpportunityQualityIssueReference",
    "OpportunityDiagnostic",
    "OpportunityCoverageSummary",
    "OpportunityIntelligenceRequest",
    "OpportunityIntelligenceSnapshotV0_1",
)
