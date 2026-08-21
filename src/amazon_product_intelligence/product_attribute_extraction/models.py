"""Evidence-grounded Product Attribute Extraction contracts V0.1.

This module defines contracts only.  It does not extract, infer, normalize, or
resolve attributes.  Canonical observation lineage remains authoritative.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    ContractValidationError,
    JsonContract,
    ProductIdentity,
    RawEvidenceRecord,
    Severity,
    SubjectType,
    Unit,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.product_intelligence import (
    LineageReference,
    ProductIntelligenceSnapshotV0_1,
    ProductIntelligenceValidationError,
)

from .errors import (
    AttributeEvidenceValidationError,
    AttributeTaxonomyValidationError,
    ProductAttributeContractError,
    ProductAttributeSerializationError,
)


ATTRIBUTE_CONTRACT_VERSION = "0.1"
ATTRIBUTE_EXTRACTION_RULESET_VERSION = "product-attribute-contract-v0.1"


class AttributeDimension(StrEnum):
    PRODUCT_TYPE = "product_type"
    MATERIAL = "material"
    COLOR = "color"
    CAPACITY = "capacity"
    DIMENSION = "dimension"
    SIZE = "size"
    STRUCTURE = "structure"
    FEATURE = "feature"
    OPERATION_METHOD = "operation_method"
    COMPATIBILITY = "compatibility"
    PACKAGE_QUANTITY = "package_quantity"
    AUDIENCE = "audience"
    USE_CASE = "use_case"
    PROBLEM_SOLVED = "problem_solved"
    PRICE_BAND = "price_band"


class ProductGrain(StrEnum):
    CHILD_ASIN = "CHILD_ASIN"
    PARENT_ASIN = "PARENT_ASIN"
    PRODUCT_FAMILY = "PRODUCT_FAMILY"


class AttributeProfileStatus(StrEnum):
    READY = "READY"
    PARTIAL = "PARTIAL"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class AttributeState(StrEnum):
    PRESENT = "PRESENT"
    UNKNOWN = "UNKNOWN"
    AMBIGUOUS = "AMBIGUOUS"
    CONFLICTED = "CONFLICTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AttributeResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"
    BLOCKED_BY_CONFLICT = "BLOCKED_BY_CONFLICT"
    NOT_REQUIRED = "NOT_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class AttributeExtractionMethod(StrEnum):
    EXPLICIT_STRUCTURED = "EXPLICIT_STRUCTURED"
    EXPLICIT_TEXT = "EXPLICIT_TEXT"
    RULE_DERIVED = "RULE_DERIVED"
    AI_INFERRED = "AI_INFERRED"


class AttributeAssertionStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class AttributeConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class AttributeValueType(StrEnum):
    TEXT = "TEXT"
    NUMBER = "NUMBER"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    RANGE = "RANGE"
    LIST = "LIST"
    OBJECT = "OBJECT"


class AttributeEvidenceSource(StrEnum):
    CANONICAL_EVIDENCE_BUNDLE = "CANONICAL_EVIDENCE_BUNDLE"
    PRODUCT_INTELLIGENCE_SNAPSHOT = "PRODUCT_INTELLIGENCE_SNAPSHOT"


class AttributeCardinality(StrEnum):
    SINGLE = "SINGLE"
    MULTI = "MULTI"


class AttributeNormalizationRuleType(StrEnum):
    EXACT = "EXACT"
    CASEFOLD = "CASEFOLD"
    ALIAS = "ALIAS"
    REGEX = "REGEX"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise ProductAttributeContractError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ProductAttributeContractError(f"{path} must be a non-negative integer")
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ProductAttributeContractError(f"{path} must be a sequence")
    return tuple(value)


def _instance(value: Any, expected: type, path: str) -> None:
    if not isinstance(value, expected):
        raise ProductAttributeContractError(f"{path} must be {expected.__name__}")


def _datetime(value: str | None, path: str) -> None:
    if value is None:
        return
    _text(value, path)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ProductAttributeContractError(f"{path} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ProductAttributeContractError(f"{path} must include a UTC offset or Z")


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise ProductAttributeContractError(f"{path} must contain finite JSON data: {exc}") from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _without_id(model: JsonContract, field_name: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field_name)
    return payload


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    return deterministic_id(prefix, _without_id(model, field_name))


class _AttributeModel(JsonContract):
    """Strictly decode attribute models and keep one public error boundary."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except ProductAttributeContractError:
            raise
        except (ContractValidationError, ProductIntelligenceValidationError, TypeError, ValueError) as exc:
            raise ProductAttributeSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeConfidence(_AttributeModel):
    level: AttributeConfidenceLevel
    basis: tuple[str, ...]
    calibration_version: str | None = None

    def __post_init__(self) -> None:
        _instance(self.level, AttributeConfidenceLevel, "AttributeConfidence.level")
        basis = _tuple(self.basis, "AttributeConfidence.basis")
        if any(type(item) is not str or not item.strip() for item in basis):
            raise ProductAttributeContractError("confidence basis must contain non-empty text")
        if len(set(basis)) != len(basis):
            raise ProductAttributeContractError("confidence basis must be unique")
        if self.level is AttributeConfidenceLevel.UNKNOWN and (basis or self.calibration_version is not None):
            raise ProductAttributeContractError("UNKNOWN confidence cannot claim a basis or calibration")
        if self.level is not AttributeConfidenceLevel.UNKNOWN and not basis:
            raise ProductAttributeContractError("known confidence requires an explicit basis")
        if self.calibration_version is not None:
            _text(self.calibration_version, "AttributeConfidence.calibration_version")
        object.__setattr__(self, "basis", tuple(sorted(basis)))


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalAttributeValue(_AttributeModel):
    value_id: str
    dimension: AttributeDimension
    value_type: AttributeValueType
    value: Any
    display_value: str
    taxonomy_version: str
    taxonomy_value_id: str | None
    unit: Unit | None

    def __post_init__(self) -> None:
        _instance(self.dimension, AttributeDimension, "CanonicalAttributeValue.dimension")
        _instance(self.value_type, AttributeValueType, "CanonicalAttributeValue.value_type")
        _text(self.display_value, "CanonicalAttributeValue.display_value")
        _text(self.taxonomy_version, "CanonicalAttributeValue.taxonomy_version")
        if self.taxonomy_value_id is not None:
            _text(self.taxonomy_value_id, "CanonicalAttributeValue.taxonomy_value_id")
        if self.unit is not None:
            _instance(self.unit, Unit, "CanonicalAttributeValue.unit")
        frozen = _freeze_json(self.value, "CanonicalAttributeValue.value")
        if frozen is None:
            raise ProductAttributeContractError("canonical attribute values cannot be null; use UNKNOWN state")
        if self.value_type is AttributeValueType.TEXT and (type(frozen) is not str or not frozen.strip()):
            raise ProductAttributeContractError("TEXT canonical value requires non-empty text")
        if self.value_type is AttributeValueType.NUMBER and (
            type(frozen) not in {int, float} or isinstance(frozen, bool)
        ):
            raise ProductAttributeContractError("NUMBER canonical value requires a JSON number")
        if self.value_type is AttributeValueType.INTEGER and type(frozen) is not int:
            raise ProductAttributeContractError("INTEGER canonical value requires an integer")
        if self.value_type is AttributeValueType.BOOLEAN and type(frozen) is not bool:
            raise ProductAttributeContractError("BOOLEAN canonical value requires a boolean")
        if self.value_type is AttributeValueType.LIST and not isinstance(frozen, tuple):
            raise ProductAttributeContractError("LIST canonical value requires an array")
        if self.value_type in {AttributeValueType.OBJECT, AttributeValueType.RANGE} and not isinstance(
            frozen, MappingABC
        ):
            raise ProductAttributeContractError(f"{self.value_type.value} canonical value requires an object")
        if self.unit is not None and self.value_type not in {
            AttributeValueType.NUMBER,
            AttributeValueType.INTEGER,
            AttributeValueType.RANGE,
            AttributeValueType.OBJECT,
        }:
            raise ProductAttributeContractError("units require a numeric, range, or structured canonical value")
        object.__setattr__(self, "value", frozen)
        if self.value_id != _identity("attribute-value", self, "value_id"):
            raise ProductAttributeContractError("value_id does not match canonical value content")


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeSourceEvidence(_AttributeModel):
    source_evidence_id: str
    source_type: AttributeEvidenceSource
    source_artifact_ids: tuple[str, ...]
    product_identity: ProductIdentity
    lineage_reference: LineageReference
    source_raw_value: Any
    source_normalized_value: Any
    source_unit: Unit | None
    observed_at: str | None
    retrieved_at: str

    def __post_init__(self) -> None:
        _instance(self.source_type, AttributeEvidenceSource, "AttributeSourceEvidence.source_type")
        _instance(self.product_identity, ProductIdentity, "AttributeSourceEvidence.product_identity")
        _instance(self.lineage_reference, LineageReference, "AttributeSourceEvidence.lineage_reference")
        if self.source_unit is not None:
            _instance(self.source_unit, Unit, "AttributeSourceEvidence.source_unit")
        artifacts = _tuple(self.source_artifact_ids, "AttributeSourceEvidence.source_artifact_ids")
        if not artifacts or any(type(item) is not str or not item.strip() for item in artifacts):
            raise ProductAttributeContractError("source evidence requires source artifact identifiers")
        if len(set(artifacts)) != len(artifacts):
            raise ProductAttributeContractError("source artifact identifiers must be unique")
        if self.source_type is AttributeEvidenceSource.CANONICAL_EVIDENCE_BUNDLE:
            if set(artifacts) != set(self.lineage_reference.source_bundle_fingerprints):
                raise ProductAttributeContractError(
                    "bundle source artifact identifiers must equal lineage bundle fingerprints"
                )
        elif len(artifacts) != 1:
            raise ProductAttributeContractError("snapshot source evidence requires exactly one snapshot id")
        raw = _freeze_json(self.source_raw_value, "AttributeSourceEvidence.source_raw_value")
        normalized = _freeze_json(
            self.source_normalized_value, "AttributeSourceEvidence.source_normalized_value"
        )
        if raw is None and normalized is None:
            raise ProductAttributeContractError("source evidence must preserve a raw or normalized value")
        _datetime(self.observed_at, "AttributeSourceEvidence.observed_at")
        _datetime(self.retrieved_at, "AttributeSourceEvidence.retrieved_at")
        object.__setattr__(self, "source_artifact_ids", tuple(sorted(artifacts)))
        object.__setattr__(self, "source_raw_value", raw)
        object.__setattr__(self, "source_normalized_value", normalized)
        if self.source_evidence_id != _identity("attribute-source", self, "source_evidence_id"):
            raise ProductAttributeContractError("source_evidence_id does not match evidence content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalAttributeAssertion(_AttributeModel):
    assertion_id: str
    raw_value: Any
    normalized_value: Any
    canonical_value: CanonicalAttributeValue | None
    unit: Unit | None
    source_evidence: tuple[AttributeSourceEvidence, ...]
    extraction_method: AttributeExtractionMethod
    extractor_version: str
    confidence: AttributeConfidence
    status: AttributeAssertionStatus

    def __post_init__(self) -> None:
        _instance(self.extraction_method, AttributeExtractionMethod, "assertion extraction_method")
        _instance(self.confidence, AttributeConfidence, "assertion confidence")
        _instance(self.status, AttributeAssertionStatus, "assertion status")
        _text(self.extractor_version, "assertion extractor_version")
        if self.unit is not None:
            _instance(self.unit, Unit, "assertion unit")
        raw = _freeze_json(self.raw_value, "assertion raw_value")
        normalized = _freeze_json(self.normalized_value, "assertion normalized_value")
        if raw is None:
            raise ProductAttributeContractError("attribute assertions must preserve a non-null raw value")
        evidence = _tuple(self.source_evidence, "assertion source_evidence")
        if not evidence or any(not isinstance(item, AttributeSourceEvidence) for item in evidence):
            raise ProductAttributeContractError("every attribute assertion requires source evidence")
        evidence_ids = [item.source_evidence_id for item in evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ProductAttributeContractError("assertion source evidence must be unique")
        if self.canonical_value is not None:
            _instance(self.canonical_value, CanonicalAttributeValue, "assertion canonical_value")
            if self.unit != self.canonical_value.unit:
                raise ProductAttributeContractError("assertion unit must match canonical value unit")
        elif self.unit is not None:
            raise ProductAttributeContractError("assertion without a canonical value cannot claim a unit")
        if self.status is AttributeAssertionStatus.CONFIRMED and (
            normalized is None or self.canonical_value is None
        ):
            raise ProductAttributeContractError("confirmed assertions require normalized and canonical values")
        if self.status is AttributeAssertionStatus.REJECTED and self.canonical_value is not None:
            raise ProductAttributeContractError("rejected assertions cannot publish a canonical value")
        if (
            self.extraction_method is AttributeExtractionMethod.AI_INFERRED
            and self.status is not AttributeAssertionStatus.CANDIDATE
        ):
            raise ProductAttributeContractError("AI_INFERRED assertions must remain unconfirmed candidates")
        object.__setattr__(self, "raw_value", raw)
        object.__setattr__(self, "normalized_value", normalized)
        object.__setattr__(self, "source_evidence", tuple(sorted(evidence, key=lambda item: item.source_evidence_id)))
        if self.assertion_id != _identity("attribute-assertion", self, "assertion_id"):
            raise ProductAttributeContractError("assertion_id does not match assertion content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalAttributeConflict(_AttributeModel):
    conflict_id: str
    assertion_ids: tuple[str, ...]
    reason_code: str
    description: str

    def __post_init__(self) -> None:
        assertions = _tuple(self.assertion_ids, "conflict assertion_ids")
        if len(assertions) < 2 or any(type(item) is not str or not item.strip() for item in assertions):
            raise ProductAttributeContractError("attribute conflicts require at least two assertion ids")
        if len(set(assertions)) != len(assertions):
            raise ProductAttributeContractError("conflict assertion ids must be unique")
        _text(self.reason_code, "conflict reason_code")
        _text(self.description, "conflict description")
        object.__setattr__(self, "assertion_ids", tuple(sorted(assertions)))
        if self.conflict_id != _identity("attribute-conflict", self, "conflict_id"):
            raise ProductAttributeContractError("conflict_id does not match conflict content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalAttributeSlot(_AttributeModel):
    dimension: AttributeDimension
    state: AttributeState
    resolved_value: tuple[CanonicalAttributeValue, ...]
    assertions: tuple[CanonicalAttributeAssertion, ...]
    conflicts: tuple[CanonicalAttributeConflict, ...]
    resolution_status: AttributeResolutionStatus

    def __post_init__(self) -> None:
        _instance(self.dimension, AttributeDimension, "attribute slot dimension")
        _instance(self.state, AttributeState, "attribute slot state")
        _instance(self.resolution_status, AttributeResolutionStatus, "attribute slot resolution_status")
        resolved = _tuple(self.resolved_value, "attribute slot resolved_value")
        assertions = _tuple(self.assertions, "attribute slot assertions")
        conflicts = _tuple(self.conflicts, "attribute slot conflicts")
        if any(not isinstance(item, CanonicalAttributeValue) for item in resolved):
            raise ProductAttributeContractError("resolved values contain a wrong type")
        if any(not isinstance(item, CanonicalAttributeAssertion) for item in assertions):
            raise ProductAttributeContractError("assertions contain a wrong type")
        if any(not isinstance(item, CanonicalAttributeConflict) for item in conflicts):
            raise ProductAttributeContractError("conflicts contain a wrong type")
        if any(item.dimension is not self.dimension for item in resolved):
            raise ProductAttributeContractError("resolved value dimension does not match its slot")
        if any(
            item.canonical_value is not None and item.canonical_value.dimension is not self.dimension
            for item in assertions
        ):
            raise ProductAttributeContractError("assertion canonical value dimension does not match its slot")
        for name, values, key in (
            ("resolved values", resolved, lambda item: item.value_id),
            ("assertions", assertions, lambda item: item.assertion_id),
            ("conflicts", conflicts, lambda item: item.conflict_id),
        ):
            keys = [key(item) for item in values]
            if len(set(keys)) != len(keys):
                raise ProductAttributeContractError(f"attribute slot {name} must be unique")
        assertion_ids = {item.assertion_id for item in assertions}
        if any(not set(item.assertion_ids) <= assertion_ids for item in conflicts):
            raise ProductAttributeContractError("attribute conflict references an absent assertion")
        if self.state is AttributeState.PRESENT:
            if not resolved or not assertions or conflicts:
                raise ProductAttributeContractError("PRESENT requires resolved values and assertions without conflicts")
            if self.resolution_status is not AttributeResolutionStatus.RESOLVED:
                raise ProductAttributeContractError("PRESENT requires RESOLVED resolution status")
            confirmed = {
                item.canonical_value.value_id
                for item in assertions
                if item.status is AttributeAssertionStatus.CONFIRMED and item.canonical_value is not None
            }
            if not {item.value_id for item in resolved} <= confirmed:
                raise ProductAttributeContractError("each resolved value requires a confirmed non-AI assertion")
        elif self.state is AttributeState.UNKNOWN:
            if resolved or assertions or conflicts or self.resolution_status is not AttributeResolutionStatus.NOT_REQUIRED:
                raise ProductAttributeContractError("UNKNOWN must not invent values, assertions, or conflicts")
        elif self.state is AttributeState.AMBIGUOUS:
            if resolved or not assertions or conflicts or self.resolution_status is not AttributeResolutionStatus.UNRESOLVED:
                raise ProductAttributeContractError("AMBIGUOUS requires unresolved assertions without a value")
        elif self.state is AttributeState.CONFLICTED:
            if resolved or len(assertions) < 2 or not conflicts:
                raise ProductAttributeContractError("CONFLICTED requires assertions and explicit conflicts")
            if self.resolution_status is not AttributeResolutionStatus.BLOCKED_BY_CONFLICT:
                raise ProductAttributeContractError("CONFLICTED requires BLOCKED_BY_CONFLICT")
        elif self.state is AttributeState.NOT_APPLICABLE:
            if resolved or assertions or conflicts or self.resolution_status is not AttributeResolutionStatus.NOT_APPLICABLE:
                raise ProductAttributeContractError("NOT_APPLICABLE cannot carry attribute evidence")
        object.__setattr__(self, "resolved_value", tuple(sorted(resolved, key=lambda item: item.value_id)))
        object.__setattr__(self, "assertions", tuple(sorted(assertions, key=lambda item: item.assertion_id)))
        object.__setattr__(self, "conflicts", tuple(sorted(conflicts, key=lambda item: item.conflict_id)))


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeExtractionRun(_AttributeModel):
    extraction_run_id: str
    extractor_name: str
    extractor_version: str
    taxonomy_version: str
    started_at: str | None
    completed_at: str | None
    source_types: tuple[AttributeEvidenceSource, ...]

    def __post_init__(self) -> None:
        for name in ("extractor_name", "extractor_version", "taxonomy_version"):
            _text(getattr(self, name), f"AttributeExtractionRun.{name}")
        _datetime(self.started_at, "AttributeExtractionRun.started_at")
        _datetime(self.completed_at, "AttributeExtractionRun.completed_at")
        if (self.started_at is None) != (self.completed_at is None):
            raise ProductAttributeContractError("extraction run times must both be known or both be null")
        if self.started_at is not None and self.completed_at is not None:
            start = datetime.fromisoformat(
                self.started_at[:-1] + "+00:00" if self.started_at.endswith("Z") else self.started_at
            )
            end = datetime.fromisoformat(
                self.completed_at[:-1] + "+00:00" if self.completed_at.endswith("Z") else self.completed_at
            )
            if start > end:
                raise ProductAttributeContractError("extraction run cannot complete before it starts")
        sources = _tuple(self.source_types, "AttributeExtractionRun.source_types")
        if not sources or any(not isinstance(item, AttributeEvidenceSource) for item in sources):
            raise ProductAttributeContractError("extraction run requires declared source types")
        if len(set(sources)) != len(sources):
            raise ProductAttributeContractError("extraction run source types must be unique")
        object.__setattr__(self, "source_types", tuple(sorted(sources, key=lambda item: item.value)))
        if self.extraction_run_id != _identity("attribute-extraction-run", self, "extraction_run_id"):
            raise ProductAttributeContractError("extraction_run_id does not match run content")


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeCoverage(_AttributeModel):
    total_dimension_count: int
    present_dimension_count: int
    unknown_dimension_count: int
    ambiguous_dimension_count: int
    conflicted_dimension_count: int
    not_applicable_dimension_count: int
    assertion_count: int
    source_evidence_count: int

    def __post_init__(self) -> None:
        for name in (
            "total_dimension_count",
            "present_dimension_count",
            "unknown_dimension_count",
            "ambiguous_dimension_count",
            "conflicted_dimension_count",
            "not_applicable_dimension_count",
            "assertion_count",
            "source_evidence_count",
        ):
            _count(getattr(self, name), f"AttributeCoverage.{name}")
        state_total = (
            self.present_dimension_count
            + self.unknown_dimension_count
            + self.ambiguous_dimension_count
            + self.conflicted_dimension_count
            + self.not_applicable_dimension_count
        )
        if state_total != self.total_dimension_count:
            raise ProductAttributeContractError("attribute coverage state counts must equal total dimensions")


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeDiagnostic(_AttributeModel):
    diagnostic_id: str
    code: str
    severity: Severity
    dimension: AttributeDimension | None
    related_assertion_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.code, "AttributeDiagnostic.code")
        _instance(self.severity, Severity, "AttributeDiagnostic.severity")
        if self.dimension is not None:
            _instance(self.dimension, AttributeDimension, "AttributeDiagnostic.dimension")
        references = _tuple(self.related_assertion_ids, "AttributeDiagnostic.related_assertion_ids")
        if any(type(item) is not str or not item.strip() for item in references):
            raise ProductAttributeContractError("diagnostic assertion references must contain text")
        if len(set(references)) != len(references):
            raise ProductAttributeContractError("diagnostic assertion references must be unique")
        _text(self.message, "AttributeDiagnostic.message")
        object.__setattr__(self, "related_assertion_ids", tuple(sorted(references)))
        if self.diagnostic_id != _identity("attribute-diagnostic", self, "diagnostic_id"):
            raise ProductAttributeContractError("diagnostic_id does not match diagnostic content")


@dataclass(frozen=True, slots=True, kw_only=True)
class AllowedAttributeValue(_AttributeModel):
    value_id: str
    display_value: str
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.value_id, "AllowedAttributeValue.value_id")
        _text(self.display_value, "AllowedAttributeValue.display_value")
        aliases = _tuple(self.aliases, "AllowedAttributeValue.aliases")
        if any(type(item) is not str or not item.strip() for item in aliases):
            raise ProductAttributeContractError("allowed value aliases must contain text")
        folded = [item.casefold() for item in aliases]
        if len(set(folded)) != len(folded):
            raise ProductAttributeContractError("allowed value aliases must be case-insensitively unique")
        object.__setattr__(self, "aliases", tuple(sorted(aliases, key=str.casefold)))


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeValueNormalizationRule(_AttributeModel):
    rule_id: str
    rule_type: AttributeNormalizationRuleType
    source_values: tuple[str, ...]
    target_value_id: str

    def __post_init__(self) -> None:
        _text(self.rule_id, "AttributeValueNormalizationRule.rule_id")
        _instance(self.rule_type, AttributeNormalizationRuleType, "normalization rule type")
        values = _tuple(self.source_values, "normalization rule source_values")
        if not values or any(type(item) is not str or not item.strip() for item in values):
            raise ProductAttributeContractError("normalization rules require source values")
        if len({item.casefold() for item in values}) != len(values):
            raise ProductAttributeContractError("normalization rule source values must be unique")
        _text(self.target_value_id, "AttributeValueNormalizationRule.target_value_id")
        object.__setattr__(self, "source_values", tuple(sorted(values, key=str.casefold)))


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeUnitRule(_AttributeModel):
    quantity_dimension: str
    canonical_unit: Unit
    accepted_units: tuple[Unit, ...]

    def __post_init__(self) -> None:
        _text(self.quantity_dimension, "AttributeUnitRule.quantity_dimension")
        _instance(self.canonical_unit, Unit, "AttributeUnitRule.canonical_unit")
        units = _tuple(self.accepted_units, "AttributeUnitRule.accepted_units")
        if not units or any(not isinstance(item, Unit) for item in units):
            raise ProductAttributeContractError("unit rules require accepted units")
        keys = [canonical_json(item) for item in units]
        if len(set(keys)) != len(keys):
            raise ProductAttributeContractError("accepted units must be unique")
        if canonical_json(self.canonical_unit) not in set(keys):
            raise ProductAttributeContractError("canonical unit must be included in accepted units")
        if any(item.dimension != self.canonical_unit.dimension for item in units):
            raise ProductAttributeContractError("all accepted units must share the canonical dimension")
        object.__setattr__(self, "accepted_units", tuple(sorted(units, key=canonical_json)))


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeDimensionDefinition(_AttributeModel):
    dimension: AttributeDimension
    definition: str
    cardinality: AttributeCardinality
    open_value_set: bool
    allowed_values: tuple[AllowedAttributeValue, ...]
    value_normalization_rules: tuple[AttributeValueNormalizationRule, ...]
    unit_rules: tuple[AttributeUnitRule, ...]

    def __post_init__(self) -> None:
        _instance(self.dimension, AttributeDimension, "dimension definition dimension")
        _text(self.definition, "dimension definition")
        _instance(self.cardinality, AttributeCardinality, "dimension cardinality")
        if type(self.open_value_set) is not bool:
            raise ProductAttributeContractError("open_value_set must be a boolean")
        allowed = _tuple(self.allowed_values, "dimension allowed_values")
        rules = _tuple(self.value_normalization_rules, "dimension value_normalization_rules")
        units = _tuple(self.unit_rules, "dimension unit_rules")
        if any(not isinstance(item, AllowedAttributeValue) for item in allowed):
            raise ProductAttributeContractError("allowed_values contains a wrong type")
        if any(not isinstance(item, AttributeValueNormalizationRule) for item in rules):
            raise ProductAttributeContractError("value_normalization_rules contains a wrong type")
        if any(not isinstance(item, AttributeUnitRule) for item in units):
            raise ProductAttributeContractError("unit_rules contains a wrong type")
        allowed_ids = [item.value_id for item in allowed]
        rule_ids = [item.rule_id for item in rules]
        if len(set(allowed_ids)) != len(allowed_ids) or len(set(rule_ids)) != len(rule_ids):
            raise ProductAttributeContractError("dimension registry identifiers must be unique")
        if any(item.target_value_id not in set(allowed_ids) for item in rules):
            raise ProductAttributeContractError("normalization rule target is absent from allowed values")
        quantity_dimensions = [item.quantity_dimension for item in units]
        if len(set(quantity_dimensions)) != len(quantity_dimensions):
            raise ProductAttributeContractError("unit rules must use unique quantity dimensions")
        object.__setattr__(self, "allowed_values", tuple(sorted(allowed, key=lambda item: item.value_id)))
        object.__setattr__(self, "value_normalization_rules", tuple(sorted(rules, key=lambda item: item.rule_id)))
        object.__setattr__(self, "unit_rules", tuple(sorted(units, key=lambda item: item.quantity_dimension)))


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeDimensionRegistry(_AttributeModel):
    registry_id: str
    taxonomy_version: str
    dimensions: tuple[AttributeDimensionDefinition, ...]

    def __post_init__(self) -> None:
        _text(self.taxonomy_version, "AttributeDimensionRegistry.taxonomy_version")
        dimensions = _tuple(self.dimensions, "AttributeDimensionRegistry.dimensions")
        if not dimensions or any(not isinstance(item, AttributeDimensionDefinition) for item in dimensions):
            raise ProductAttributeContractError("registry requires dimension definitions")
        keys = [item.dimension for item in dimensions]
        if len(set(keys)) != len(keys):
            raise ProductAttributeContractError("registry dimensions must be unique")
        object.__setattr__(self, "dimensions", tuple(sorted(dimensions, key=lambda item: item.dimension.value)))
        if self.registry_id != _identity("attribute-registry", self, "registry_id"):
            raise ProductAttributeContractError("registry_id does not match registry content")

    def definition_for(self, dimension: AttributeDimension) -> AttributeDimensionDefinition:
        _instance(dimension, AttributeDimension, "registry lookup dimension")
        for definition in self.dimensions:
            if definition.dimension is dimension:
                return definition
        raise AttributeTaxonomyValidationError(f"dimension {dimension.value} is absent from registry")

    def validate_profile(self, profile: CanonicalProductAttributeProfile) -> CanonicalProductAttributeProfile:
        _instance(profile, CanonicalProductAttributeProfile, "registry profile")
        if profile.extraction_run.taxonomy_version != self.taxonomy_version:
            raise AttributeTaxonomyValidationError("profile taxonomy version does not match registry")
        profile_dimensions = {item.dimension for item in profile.attributes}
        registry_dimensions = {item.dimension for item in self.dimensions}
        if profile_dimensions != registry_dimensions:
            raise AttributeTaxonomyValidationError("profile dimensions must exactly match its registry version")
        for slot in profile.attributes:
            definition = self.definition_for(slot.dimension)
            if definition.cardinality is AttributeCardinality.SINGLE and len(slot.resolved_value) > 1:
                raise AttributeTaxonomyValidationError(f"{slot.dimension.value} allows only one resolved value")
            values = list(slot.resolved_value) + [
                assertion.canonical_value
                for assertion in slot.assertions
                if assertion.canonical_value is not None
            ]
            allowed_ids = {item.value_id for item in definition.allowed_values}
            accepted_units = {
                canonical_json(unit)
                for rule in definition.unit_rules
                for unit in rule.accepted_units
            }
            for value in values:
                if value.taxonomy_version != self.taxonomy_version:
                    raise AttributeTaxonomyValidationError("canonical value taxonomy version mismatch")
                if value.taxonomy_value_id is not None and value.taxonomy_value_id not in allowed_ids:
                    raise AttributeTaxonomyValidationError("canonical value is absent from allowed values")
                if value.taxonomy_value_id is None and not definition.open_value_set:
                    raise AttributeTaxonomyValidationError("closed dimension requires an allowed taxonomy value")
                if value.unit is not None and canonical_json(value.unit) not in accepted_units:
                    raise AttributeTaxonomyValidationError("canonical value unit is not allowed by the registry")
        return profile


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalProductAttributeProfile(_AttributeModel):
    profile_id: str
    product_identity: ProductIdentity
    product_grain: ProductGrain
    status: AttributeProfileStatus
    attributes: tuple[CanonicalAttributeSlot, ...]
    extraction_run: AttributeExtractionRun
    source_evidence: tuple[AttributeSourceEvidence, ...]
    coverage: AttributeCoverage
    diagnostics: tuple[AttributeDiagnostic, ...]

    def __post_init__(self) -> None:
        _instance(self.product_identity, ProductIdentity, "profile product_identity")
        _instance(self.product_grain, ProductGrain, "profile product_grain")
        _instance(self.status, AttributeProfileStatus, "profile status")
        _instance(self.extraction_run, AttributeExtractionRun, "profile extraction_run")
        _instance(self.coverage, AttributeCoverage, "profile coverage")
        attributes = _tuple(self.attributes, "profile attributes")
        evidence = _tuple(self.source_evidence, "profile source_evidence")
        diagnostics = _tuple(self.diagnostics, "profile diagnostics")
        if not attributes or any(not isinstance(item, CanonicalAttributeSlot) for item in attributes):
            raise ProductAttributeContractError("profile requires attribute slots")
        if any(not isinstance(item, AttributeSourceEvidence) for item in evidence):
            raise ProductAttributeContractError("profile source_evidence contains a wrong type")
        if any(not isinstance(item, AttributeDiagnostic) for item in diagnostics):
            raise ProductAttributeContractError("profile diagnostics contains a wrong type")
        dimensions = [item.dimension for item in attributes]
        evidence_ids = [item.source_evidence_id for item in evidence]
        diagnostic_ids = [item.diagnostic_id for item in diagnostics]
        if len(set(dimensions)) != len(dimensions):
            raise ProductAttributeContractError("profile attribute dimensions must be unique")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ProductAttributeContractError("profile source evidence must be unique")
        if len(set(diagnostic_ids)) != len(diagnostic_ids):
            raise ProductAttributeContractError("profile diagnostics must be unique")
        used_evidence = {
            item.source_evidence_id
            for slot in attributes
            for assertion in slot.assertions
            for item in assertion.source_evidence
        }
        if used_evidence != set(evidence_ids):
            raise ProductAttributeContractError("profile source evidence must exactly index assertion evidence")
        used_source_types = {item.source_type for item in evidence}
        if not used_source_types <= set(self.extraction_run.source_types):
            raise ProductAttributeContractError("profile evidence uses an undeclared extraction source type")
        assertion_ids = {assertion.assertion_id for slot in attributes for assertion in slot.assertions}
        if any(not set(item.related_assertion_ids) <= assertion_ids for item in diagnostics):
            raise ProductAttributeContractError("diagnostic references an absent assertion")
        if any(item.product_identity.marketplace != self.product_identity.marketplace for item in evidence):
            raise ProductAttributeContractError("attribute evidence marketplace must match profile")
        if self.product_grain is ProductGrain.CHILD_ASIN and any(
            item.product_identity.product_id != self.product_identity.product_id for item in evidence
        ):
            raise ProductAttributeContractError("CHILD_ASIN profile evidence must belong to the exact product")
        expected_coverage = AttributeCoverage(
            total_dimension_count=len(attributes),
            present_dimension_count=sum(item.state is AttributeState.PRESENT for item in attributes),
            unknown_dimension_count=sum(item.state is AttributeState.UNKNOWN for item in attributes),
            ambiguous_dimension_count=sum(item.state is AttributeState.AMBIGUOUS for item in attributes),
            conflicted_dimension_count=sum(item.state is AttributeState.CONFLICTED for item in attributes),
            not_applicable_dimension_count=sum(item.state is AttributeState.NOT_APPLICABLE for item in attributes),
            assertion_count=sum(len(item.assertions) for item in attributes),
            source_evidence_count=len(evidence),
        )
        if self.coverage != expected_coverage:
            raise ProductAttributeContractError("profile coverage does not match attribute contents")
        expected_status = (
            AttributeProfileStatus.CONFLICTED
            if any(item.state is AttributeState.CONFLICTED for item in attributes)
            else AttributeProfileStatus.UNKNOWN
            if all(item.state in {AttributeState.UNKNOWN, AttributeState.NOT_APPLICABLE} for item in attributes)
            else AttributeProfileStatus.PARTIAL
            if any(item.state in {AttributeState.UNKNOWN, AttributeState.AMBIGUOUS} for item in attributes)
            else AttributeProfileStatus.READY
        )
        if self.status is not expected_status:
            raise ProductAttributeContractError("profile status does not match attribute states")
        object.__setattr__(self, "attributes", tuple(sorted(attributes, key=lambda item: item.dimension.value)))
        object.__setattr__(self, "source_evidence", tuple(sorted(evidence, key=lambda item: item.source_evidence_id)))
        object.__setattr__(self, "diagnostics", tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)))
        if self.profile_id != _identity("attribute-profile", self, "profile_id"):
            raise ProductAttributeContractError("profile_id does not match profile content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_registry(self, registry: AttributeDimensionRegistry) -> Self:
        _instance(registry, AttributeDimensionRegistry, "profile registry")
        registry.validate_profile(self)
        return self

    def validate_against_product_intelligence_snapshot(
        self, snapshot: ProductIntelligenceSnapshotV0_1
    ) -> Self:
        _instance(snapshot, ProductIntelligenceSnapshotV0_1, "profile source snapshot")
        snapshot.validate()
        if snapshot.target_product_identity != self.product_identity:
            raise AttributeEvidenceValidationError("profile product does not match source snapshot target")
        included = {item.product_id for item in snapshot.included_product_identities}
        lineage_index = {canonical_json(item) for item in snapshot.lineage_index}
        candidates: dict[str, tuple[ProductIdentity, Any]] = {}
        for evidence_set in snapshot.product_fact_evidence_sets:
            for candidate in evidence_set.candidates:
                candidates[candidate.observation_id] = (evidence_set.subject_product_identity, candidate)
        for series in snapshot.product_metric_series:
            for candidate in series.candidates:
                candidates[candidate.observation_id] = (series.subject_product_identity, candidate)
        for reference in self.source_evidence:
            if reference.product_identity.product_id not in included:
                raise AttributeEvidenceValidationError("attribute evidence product is absent from snapshot")
            if canonical_json(reference.lineage_reference) not in lineage_index:
                raise AttributeEvidenceValidationError("attribute lineage is absent from snapshot")
            if reference.source_type is AttributeEvidenceSource.PRODUCT_INTELLIGENCE_SNAPSHOT:
                if reference.source_artifact_ids != (snapshot.snapshot_id,):
                    raise AttributeEvidenceValidationError("attribute source snapshot id mismatch")
            elif not set(reference.source_artifact_ids) <= set(snapshot.source_bundle_fingerprints):
                raise AttributeEvidenceValidationError("attribute source bundle is absent from snapshot")
            candidate_entry = candidates.get(reference.lineage_reference.observation_id)
            if candidate_entry is None:
                raise AttributeEvidenceValidationError("attribute lineage has no source candidate")
            source_product, candidate = candidate_entry
            if source_product != reference.product_identity:
                raise AttributeEvidenceValidationError("attribute source product identity mismatch")
            if canonical_json(reference.lineage_reference) not in {
                canonical_json(item) for item in candidate.lineage_references
            }:
                raise AttributeEvidenceValidationError("attribute lineage does not belong to its source candidate")
            checks = (
                (reference.source_raw_value, candidate.raw_value, "raw value"),
                (reference.source_normalized_value, candidate.normalized_value, "normalized value"),
                (reference.source_unit, candidate.unit, "unit"),
                (reference.observed_at, candidate.time.observed_at, "observed_at"),
                (reference.retrieved_at, candidate.time.retrieved_at, "retrieved_at"),
            )
            if any(canonical_json(left) != canonical_json(right) for left, right, _ in checks):
                mismatch = next(
                    label for left, right, label in checks if canonical_json(left) != canonical_json(right)
                )
                raise AttributeEvidenceValidationError(f"attribute source {mismatch} mismatch")
        return self

    def validate_against_canonical_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise AttributeEvidenceValidationError("canonical bundle validation requires a non-empty sequence")
        from amazon_product_intelligence.product_intelligence.models import bundle_fingerprint

        observations: dict[tuple[str, str], Any] = {}
        fingerprints: set[str] = set()
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise AttributeEvidenceValidationError("canonical source contains a wrong bundle type")
            try:
                bundle.validate()
            except ContractValidationError as exc:
                raise AttributeEvidenceValidationError(f"invalid canonical source bundle: {exc}") from exc
            fingerprint = bundle_fingerprint(bundle)
            fingerprints.add(fingerprint)
            for observation in bundle.observations:
                key = (
                    observation.observation_id,
                    observation.provenance.transformation.transformation_run_id,
                )
                current = observations.get(key)
                if current is not None and canonical_json(current) != canonical_json(observation):
                    raise AttributeEvidenceValidationError(
                        f"canonical observation emission collision: {observation.observation_id}"
                    )
                observations[key] = observation
        for reference in self.source_evidence:
            lineage = reference.lineage_reference
            if not set(lineage.source_bundle_fingerprints) <= fingerprints:
                raise AttributeEvidenceValidationError("attribute lineage bundle fingerprint is absent")
            observation = observations.get((lineage.observation_id, lineage.transformation_run_id))
            if observation is None:
                raise AttributeEvidenceValidationError("attribute lineage observation is absent")
            provenance = observation.provenance
            transformation = provenance.transformation
            checks = (
                (lineage.semantic_observation_id, observation.semantic_observation_id, "semantic observation"),
                (lineage.observation_kind, observation.observation_kind, "observation kind"),
                (lineage.mapping_version, transformation.mapping_version, "mapping version"),
                (lineage.raw_evidence_id, transformation.raw_evidence_reference, "raw evidence"),
                (lineage.collection_run_id, transformation.collection_run_id, "collection run"),
                (lineage.provider, provenance.provider, "provider"),
                (lineage.source_tool, provenance.source_tool, "source tool"),
                (lineage.source_field, provenance.source_field, "source field"),
                (reference.source_raw_value, observation.value.raw_value, "raw value"),
                (reference.source_normalized_value, observation.value.normalized_value, "normalized value"),
                (reference.source_unit, observation.value.unit, "unit"),
                (reference.observed_at, observation.time.observed_at, "observed_at"),
                (reference.retrieved_at, observation.time.retrieved_at, "retrieved_at"),
                (reference.product_identity.product_id, observation.subject.subject_id, "product identity"),
                (reference.product_identity.marketplace, observation.subject.marketplace, "marketplace"),
            )
            if observation.subject.subject_type is not SubjectType.PRODUCT:
                raise AttributeEvidenceValidationError("attribute evidence must use a product subject")
            if any(canonical_json(left) != canonical_json(right) for left, right, _ in checks):
                mismatch = next(
                    label for left, right, label in checks if canonical_json(left) != canonical_json(right)
                )
                raise AttributeEvidenceValidationError(f"attribute canonical {mismatch} mismatch")
        return self

    def validate_against_raw_evidence_records(
        self, records: Sequence[RawEvidenceRecord]
    ) -> Self:
        """Replay the terminal lineage hop without copying the Raw Evidence model."""

        if isinstance(records, (str, bytes)) or not isinstance(records, Sequence) or not records:
            raise AttributeEvidenceValidationError("raw evidence validation requires a non-empty sequence")
        indexed: dict[str, RawEvidenceRecord] = {}
        for record in records:
            if not isinstance(record, RawEvidenceRecord):
                raise AttributeEvidenceValidationError("raw evidence source contains a wrong record type")
            current = indexed.get(record.raw_evidence_id)
            if current is not None and canonical_json(current) != canonical_json(record):
                raise AttributeEvidenceValidationError(
                    f"raw evidence identity collision: {record.raw_evidence_id}"
                )
            indexed[record.raw_evidence_id] = record
        for reference in self.source_evidence:
            lineage = reference.lineage_reference
            raw = indexed.get(lineage.raw_evidence_id)
            if raw is None:
                raise AttributeEvidenceValidationError("attribute lineage raw evidence is absent")
            checks = (
                (lineage.collection_run_id, raw.collection_run_id, "collection run"),
                (lineage.provider, raw.provider, "provider"),
                (lineage.source_tool, raw.source_tool, "source tool"),
                (reference.retrieved_at, raw.retrieved_at, "retrieved_at"),
            )
            if any(left != right for left, right, _ in checks):
                mismatch = next(label for left, right, label in checks if left != right)
                raise AttributeEvidenceValidationError(f"attribute raw evidence {mismatch} mismatch")
        return self


__all__ = (
    "ATTRIBUTE_CONTRACT_VERSION",
    "ATTRIBUTE_EXTRACTION_RULESET_VERSION",
    "AttributeDimension",
    "ProductGrain",
    "AttributeProfileStatus",
    "AttributeState",
    "AttributeResolutionStatus",
    "AttributeExtractionMethod",
    "AttributeAssertionStatus",
    "AttributeConfidenceLevel",
    "AttributeValueType",
    "AttributeEvidenceSource",
    "AttributeCardinality",
    "AttributeNormalizationRuleType",
    "AttributeConfidence",
    "CanonicalAttributeValue",
    "AttributeSourceEvidence",
    "CanonicalAttributeAssertion",
    "CanonicalAttributeConflict",
    "CanonicalAttributeSlot",
    "AttributeExtractionRun",
    "AttributeCoverage",
    "AttributeDiagnostic",
    "AllowedAttributeValue",
    "AttributeValueNormalizationRule",
    "AttributeUnitRule",
    "AttributeDimensionDefinition",
    "AttributeDimensionRegistry",
    "CanonicalProductAttributeProfile",
)
