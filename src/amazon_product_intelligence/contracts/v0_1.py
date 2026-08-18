"""Canonical Data Contracts V0.1.

This module is dependency-free by design.  It implements the Level 2 design
contracts as immutable Python value objects and adds the cross-record checks
that JSON Schema cannot express on its own.
"""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import MISSING, dataclass, fields, is_dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
import json
import math
import re
import types
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Self, Sequence, Union, get_args, get_origin, get_type_hints


SCHEMA_VERSION = "0.1"
_ASIN = re.compile(r"^[A-Z0-9]{10}$")


class ContractValidationError(ValueError):
    """Raised when a contract or bundle violates V0.1 invariants."""

    def __init__(self, violations: str | Sequence[str]) -> None:
        self.violations = (violations,) if isinstance(violations, str) else tuple(violations)
        super().__init__("; ".join(self.violations))


class EvidenceType(StrEnum):
    OBSERVED = "OBSERVED"
    PROVIDER_ESTIMATE = "PROVIDER_ESTIMATE"
    RESOLVED = "RESOLVED"
    DERIVED = "DERIVED"


class PresenceStatus(StrEnum):
    PRESENT = "PRESENT"
    EXPLICIT_NULL = "EXPLICIT_NULL"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    QUERY_RETURNED_EMPTY = "QUERY_RETURNED_EMPTY"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class SemanticStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    SEMANTICS_UNCONFIRMED = "SEMANTICS_UNCONFIRMED"
    UNPARSED = "UNPARSED"
    INVALID = "INVALID"


class ResultStatus(StrEnum):
    POPULATED = "POPULATED"
    EMPTY_OBSERVATION = "EMPTY_OBSERVATION"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


class VersionStatus(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class ProviderSchemaSource(StrEnum):
    PROVIDER_DECLARED = "PROVIDER_DECLARED"
    MCP_TOOL_OR_SERVER = "MCP_TOOL_OR_SERVER"
    SCHEMA_FINGERPRINT = "SCHEMA_FINGERPRINT"
    LOCAL_CONTRACT = "LOCAL_CONTRACT"
    UNKNOWN = "UNKNOWN"


class CodeVersionScheme(StrEnum):
    GIT_COMMIT = "GIT_COMMIT"
    BUILD_VERSION = "BUILD_VERSION"
    PACKAGE_VERSION = "PACKAGE_VERSION"
    RULESET_VERSION = "RULESET_VERSION"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class TransformationStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class SubjectType(StrEnum):
    PRODUCT = "PRODUCT"
    KEYWORD = "KEYWORD"
    CATEGORY = "CATEGORY"
    BRAND = "BRAND"
    MARKETPLACE = "MARKETPLACE"
    PRODUCT_KEYWORD_RELATIONSHIP = "PRODUCT_KEYWORD_RELATIONSHIP"


class ScopeType(StrEnum):
    ASIN = "ASIN"
    PARENT_ASIN = "PARENT_ASIN"
    CHILD_ASIN = "CHILD_ASIN"
    KEYWORD = "KEYWORD"
    CATEGORY = "CATEGORY"
    BRAND = "BRAND"
    MARKETPLACE = "MARKETPLACE"


class ScopeStatus(StrEnum):
    CONFIRMED = "CONFIRMED"
    SCOPE_UNCONFIRMED = "SCOPE_UNCONFIRMED"


class ObservedAtStatus(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class PeriodType(StrEnum):
    INSTANT = "INSTANT"
    ROLLING_15_DAYS = "ROLLING_15_DAYS"
    ROLLING_30_DAYS = "ROLLING_30_DAYS"
    CALENDAR_DAY = "CALENDAR_DAY"
    CALENDAR_WEEK = "CALENDAR_WEEK"
    CALENDAR_MONTH = "CALENDAR_MONTH"
    CUSTOM = "CUSTOM"
    UNKNOWN = "UNKNOWN"


class ValueType(StrEnum):
    STRING = "STRING"
    NUMBER = "NUMBER"
    INTEGER = "INTEGER"
    BOOLEAN = "BOOLEAN"
    DATE = "DATE"
    DATETIME = "DATETIME"
    OBJECT = "OBJECT"
    LIST = "LIST"


class NormalizationStatus(StrEnum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    NORMALIZED = "NORMALIZED"
    FAILED = "FAILED"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ObservationKind(StrEnum):
    PRODUCT_FACT = "PRODUCT_FACT"
    METRIC = "METRIC"
    KEYWORD_METRIC = "KEYWORD_METRIC"
    PRODUCT_KEYWORD_RELATIONSHIP = "PRODUCT_KEYWORD_RELATIONSHIP"
    REVIEW = "REVIEW"


class FactGroup(StrEnum):
    IDENTITY_RELATED = "IDENTITY_RELATED"
    ATTRIBUTE = "ATTRIBUTE"
    TECHNICAL = "TECHNICAL"
    DESCRIPTION = "DESCRIPTION"
    VARIATION = "VARIATION"
    OTHER = "OTHER"


class EstimateMethodStatus(StrEnum):
    DOCUMENTED = "DOCUMENTED"
    PARTIALLY_DOCUMENTED = "PARTIALLY_DOCUMENTED"
    UNKNOWN = "UNKNOWN"


class RelationshipDirection(StrEnum):
    KEYWORD_TO_PRODUCT = "KEYWORD_TO_PRODUCT"
    PRODUCT_TO_KEYWORD = "PRODUCT_TO_KEYWORD"


class QueryExecutionOutcome(StrEnum):
    RESULTS_RETURNED = "RESULTS_RETURNED"
    EXPLICIT_EMPTY = "EXPLICIT_EMPTY"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"
    EXECUTION_FAILED = "EXECUTION_FAILED"


class RelationshipType(StrEnum):
    CANDIDATE_MEMBERSHIP = "CANDIDATE_MEMBERSHIP"
    RANK = "RANK"
    TRAFFIC = "TRAFFIC"
    CLICK_SHARE = "CLICK_SHARE"
    OTHER = "OTHER"


class Channel(StrEnum):
    ORGANIC = "ORGANIC"
    SPONSORED = "SPONSORED"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class Severity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    MATERIAL = "MATERIAL"
    BLOCKING = "BLOCKING"


class BlockingScope(StrEnum):
    NONE = "NONE"
    FIELD = "FIELD"
    SUBJECT = "SUBJECT"
    BUNDLE = "BUNDLE"


class OriginStage(StrEnum):
    RAW_EVIDENCE = "RAW_EVIDENCE"
    COLLECTION = "COLLECTION"
    MAPPING = "MAPPING"
    NORMALIZATION = "NORMALIZATION"
    VALIDATION = "VALIDATION"
    RESOLUTION = "RESOLUTION"
    UNKNOWN = "UNKNOWN"


class CheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConflictStatus(StrEnum):
    CONSISTENT = "CONSISTENT"
    MINOR_DIFFERENCE = "MINOR_DIFFERENCE"
    MATERIAL_DIFFERENCE = "MATERIAL_DIFFERENCE"
    SEMANTIC_CONFLICT = "SEMANTIC_CONFLICT"
    UNIT_CONFLICT = "UNIT_CONFLICT"
    DIRECTIONAL_CONFLICT = "DIRECTIONAL_CONFLICT"
    ONE_SOURCE_ONLY = "ONE_SOURCE_ONLY"
    NOT_DIRECTLY_COMPARABLE = "NOT_DIRECTLY_COMPARABLE"
    UNKNOWN = "UNKNOWN"


class ResolutionStatus(StrEnum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED_DETERMINISTIC = "RESOLVED_DETERMINISTIC"
    RESOLVED_BY_POLICY = "RESOLVED_BY_POLICY"
    NOT_REQUIRED = "NOT_REQUIRED"
    DEFERRED = "DEFERRED"
    REJECTED_INPUT = "REJECTED_INPUT"


def _require_text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{name} must be a non-empty string")


def _require_unique(name: str, values: Sequence[str]) -> None:
    for index, value in enumerate(values):
        _require_text(f"{name}[{index}]", value)
    if len(values) != len(set(values)):
        raise ContractValidationError(f"{name} must contain unique values")


def _require_datetime(name: str, value: str | None) -> None:
    if value is None:
        return
    _require_text(name, value)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ContractValidationError(f"{name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ContractValidationError(f"{name} must include a UTC offset or Z")


def _jsonable(value: Any, path: str = "$") -> Any:
    if isinstance(value, StrEnum):
        return value.value
    if is_dataclass(value):
        return {field.name: _jsonable(getattr(value, field.name), f"{path}.{field.name}") for field in fields(value)}
    if isinstance(value, MappingABC):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractValidationError(f"{path} mapping keys must be strings")
            result[key] = _jsonable(item, f"{path}.{key}")
        return result
    if isinstance(value, (tuple, list)):
        return [_jsonable(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ContractValidationError(f"{path} must not contain NaN or infinity")
        return value
    raise ContractValidationError(f"{path} contains unsupported non-JSON type {type(value).__name__}")


def _freeze_json_value(value: Any, path: str) -> Any:
    """Validate JSON data and detach it from caller-owned mutable containers."""

    normalized = _jsonable(value, path)

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


class JsonContract:
    def to_dict(self) -> dict[str, Any]:
        return _jsonable(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        """Strictly reconstruct a contract from its JSON-compatible mapping."""

        return _contract_from_dict(cls, payload)


def canonical_json(value: Any) -> str:
    """Return stable JSON used only as deterministic identity material."""

    return json.dumps(
        _jsonable(value),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _contract_from_dict(cls: type[Self], payload: Mapping[str, Any]) -> Self:
    if not isinstance(payload, MappingABC):
        raise ContractValidationError(f"{cls.__name__} payload must be an object")
    if cls is CanonicalObservation:
        kind_value = payload.get("observation_kind")
        try:
            kind = ObservationKind(kind_value)
        except (TypeError, ValueError) as exc:
            raise ContractValidationError("CanonicalObservation.observation_kind is missing or invalid") from exc
        cls = {
            ObservationKind.PRODUCT_FACT: ProductFactObservation,
            ObservationKind.METRIC: MetricObservation,
            ObservationKind.KEYWORD_METRIC: KeywordMetricObservation,
            ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP: ProductKeywordRelationshipObservation,
            ObservationKind.REVIEW: ReviewObservation,
        }[kind]
    if not is_dataclass(cls):
        raise ContractValidationError(f"{cls!r} is not a contract dataclass")

    contract_fields = {field.name: field for field in fields(cls)}
    extra = sorted(set(payload) - set(contract_fields))
    if extra:
        raise ContractValidationError(f"{cls.__name__} contains unknown fields: {', '.join(extra)}")
    hints = get_type_hints(cls)
    values: dict[str, Any] = {}
    for name, field in contract_fields.items():
        if name not in payload:
            if field.default is MISSING and field.default_factory is MISSING:
                raise ContractValidationError(f"{cls.__name__}.{name} is required")
            continue
        values[name] = _decode_value(hints[name], payload[name], f"{cls.__name__}.{name}")
    try:
        return cls(**values)
    except TypeError as exc:
        raise ContractValidationError(f"cannot construct {cls.__name__}: {exc}") from exc


def _decode_value(annotation: Any, value: Any, path: str) -> Any:
    if annotation is Any:
        return _freeze_json_value(value, path)
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in {types.UnionType, Union}:
        if value is None and type(None) in arguments:
            return None
        failures: list[str] = []
        for candidate in arguments:
            if candidate is type(None):
                continue
            try:
                return _decode_value(candidate, value, path)
            except ContractValidationError as exc:
                failures.extend(exc.violations)
        raise ContractValidationError(f"{path} does not match its declared union: {' | '.join(failures)}")
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ContractValidationError(f"{path} must be an array")
        item_type = arguments[0] if arguments else Any
        return tuple(_decode_value(item_type, item, f"{path}[{index}]") for index, item in enumerate(value))
    if origin in {dict, Mapping, MappingABC}:
        if not isinstance(value, MappingABC):
            raise ContractValidationError(f"{path} must be an object")
        key_type, item_type = arguments or (str, Any)
        if key_type is not str:
            raise ContractValidationError(f"{path} contract mappings must use string keys")
        decoded: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractValidationError(f"{path} mapping keys must be strings")
            decoded[key] = _decode_value(item_type, item, f"{path}.{key}")
        return MappingProxyType(decoded)
    if isinstance(annotation, type) and issubclass(annotation, StrEnum):
        if not isinstance(value, str):
            raise ContractValidationError(f"{path} must be a string enum value")
        try:
            return annotation(value)
        except ValueError as exc:
            raise ContractValidationError(f"{path} has invalid value {value!r}") from exc
    if isinstance(annotation, type) and is_dataclass(annotation):
        return _contract_from_dict(annotation, value)
    if annotation is str:
        if type(value) is not str:
            raise ContractValidationError(f"{path} must be a string")
        return value
    if annotation is bool:
        if type(value) is not bool:
            raise ContractValidationError(f"{path} must be a boolean")
        return value
    if annotation is int:
        if type(value) is not int:
            raise ContractValidationError(f"{path} must be an integer")
        return value
    if annotation is float:
        if type(value) not in {int, float} or isinstance(value, bool) or not math.isfinite(float(value)):
            raise ContractValidationError(f"{path} must be a finite number")
        return float(value)
    raise ContractValidationError(f"{path} uses unsupported annotation {annotation!r}")


def deterministic_id(prefix: str, material: Any) -> str:
    _require_text("prefix", prefix)
    digest = sha256(canonical_json(material).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def product_id(marketplace: str, asin: str) -> str:
    market = marketplace.strip().upper()
    normalized_asin = asin.strip().upper()
    if not _ASIN.fullmatch(normalized_asin):
        raise ContractValidationError("asin must be 10 uppercase alphanumeric characters")
    return f"product:{market}:{normalized_asin}"


def keyword_id(marketplace: str, locale: str, normalized_text: str) -> str:
    material = {
        "marketplace": marketplace.strip().upper(),
        "locale": locale.strip().lower(),
        "normalized_text": " ".join(normalized_text.split()).casefold(),
    }
    return deterministic_id("keyword", material)


def semantic_observation_id(
    *,
    provider: str,
    source_tool: str,
    subject: "SubjectRef",
    observation_kind: ObservationKind,
    dimension: str,
    source_record_identity: str,
    observed_at: str | None,
    period_identity: Mapping[str, Any],
    discriminator: str = "",
    relationship_identity: Mapping[str, Any] | None = None,
) -> str:
    material = {
        "provider": provider.strip().casefold(),
        "source_tool": source_tool.strip().casefold(),
        "subject": subject,
        "observation_kind": observation_kind,
        "dimension": dimension.strip().casefold(),
        "source_record_identity": source_record_identity.strip(),
        "observed_at": observed_at if observed_at is not None else "UNKNOWN",
        "period_identity": period_identity,
        "discriminator": discriminator,
        "relationship_identity": relationship_identity,
    }
    return deterministic_id("obss", material)


def observation_revision_id(semantic_id: str, canonical_semantic_content: Any) -> str:
    _require_text("semantic_observation_id", semantic_id)
    return deterministic_id("obs", {"semantic_observation_id": semantic_id, "content": canonical_semantic_content})


def raw_evidence_id(
    *,
    provider: str,
    source_tool: str,
    sanitized_request_fingerprint: str,
    retrieved_at: str,
    response_fingerprint: str,
) -> str:
    _require_datetime("retrieved_at", retrieved_at)
    return deterministic_id(
        "raw",
        {
            "provider": provider.strip().casefold(),
            "source_tool": source_tool.strip().casefold(),
            "sanitized_request_fingerprint": sanitized_request_fingerprint,
            "retrieved_at": retrieved_at,
            "response_fingerprint": response_fingerprint,
        },
    )


def relationship_observation_id(
    *,
    semantic_id: str,
    product: "ProductIdentity",
    keyword: "KeywordIdentity",
    direction: RelationshipDirection,
    relationship_type: RelationshipType,
    channel: Channel,
    canonical_content: Any,
) -> str:
    return deterministic_id(
        "rel",
        {
            "semantic_observation_id": semantic_id,
            "product_id": product.product_id,
            "keyword_id": keyword.keyword_id,
            "direction": direction,
            "relationship_type": relationship_type,
            "channel": channel,
            "canonical_content": canonical_content,
        },
    )


def query_execution_id(
    *,
    query_keyword: "KeywordIdentity | None",
    query_product: "ProductIdentity | None",
    direction: RelationshipDirection,
    outcome: QueryExecutionOutcome,
    related_relationship_observation_ids: Sequence[str],
    provenance: "Provenance",
    quality_issue_ids: Sequence[str],
    schema_version: str = SCHEMA_VERSION,
) -> str:
    related_ids = tuple(related_relationship_observation_ids)
    issue_ids = tuple(quality_issue_ids)
    _require_unique(
        "related_relationship_observation_ids",
        related_ids,
    )
    _require_unique("query_execution.quality_issue_ids", issue_ids)
    return deterministic_id(
        "qex",
        {
            "query_keyword": query_keyword,
            "query_product": query_product,
            "direction": direction,
            "outcome": outcome,
            "related_relationship_observation_ids": sorted(related_ids),
            "provenance": provenance,
            "quality_issue_ids": sorted(issue_ids),
            "schema_version": schema_version,
        },
    )


def conflict_record_id(
    *,
    subject: "SubjectRef",
    dimension: str,
    candidate_observation_ids: Sequence[str],
    conflict_status: ConflictStatus,
) -> str:
    return deterministic_id(
        "cfl",
        {
            "candidate_observation_ids": sorted(candidate_observation_ids),
            "subject": subject,
            "dimension": dimension,
            "conflict_status": conflict_status,
        },
    )


def resolution_record_id(
    *,
    subject: "SubjectRef",
    dimension: str,
    candidate_observation_ids: Sequence[str],
    resolution_policy: str | None,
) -> str:
    return deterministic_id(
        "res",
        {
            "candidate_observation_ids": sorted(candidate_observation_ids),
            "subject": subject,
            "dimension": dimension,
            "resolution_policy": resolution_policy,
        },
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderSchemaVersion(JsonContract):
    status: VersionStatus
    value: str | None
    source: ProviderSchemaSource

    def __post_init__(self) -> None:
        if self.status is VersionStatus.UNKNOWN:
            if self.value is not None or self.source is not ProviderSchemaSource.UNKNOWN:
                raise ContractValidationError("unknown provider schema version requires null value and UNKNOWN source")
        else:
            _require_text("provider_schema_version.value", self.value or "")
            if self.source is ProviderSchemaSource.UNKNOWN:
                raise ContractValidationError("known provider schema version requires a known source")


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformationCodeVersion(JsonContract):
    status: VersionStatus
    value: str | None
    scheme: CodeVersionScheme

    def __post_init__(self) -> None:
        if self.status is VersionStatus.UNKNOWN:
            if self.value is not None or self.scheme is not CodeVersionScheme.UNKNOWN:
                raise ContractValidationError("unknown code version requires null value and UNKNOWN scheme")
        else:
            _require_text("transformation_code_version.value", self.value or "")
            if self.scheme is CodeVersionScheme.UNKNOWN:
                raise ContractValidationError("known code version requires a known scheme")


@dataclass(frozen=True, slots=True, kw_only=True)
class SubjectRef(JsonContract):
    subject_type: SubjectType
    subject_id: str
    marketplace: str

    def __post_init__(self) -> None:
        _require_text("subject_id", self.subject_id)
        _require_text("marketplace", self.marketplace)
        if self.marketplace != self.marketplace.strip().upper():
            raise ContractValidationError("marketplace must be normalized uppercase text")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductIdentity(JsonContract):
    product_id: str
    marketplace: str
    asin: str
    parent_asin: str | None
    identity_status: str

    def __post_init__(self) -> None:
        if self.marketplace != self.marketplace.strip().upper():
            raise ContractValidationError("marketplace must be normalized uppercase text")
        if self.asin != self.asin.strip().upper():
            raise ContractValidationError("asin must already be normalized uppercase text")
        expected = product_id(self.marketplace, self.asin)
        if self.product_id != expected:
            raise ContractValidationError(f"product_id must equal {expected}")
        if self.parent_asin is not None:
            if self.parent_asin != self.parent_asin.strip().upper() or not _ASIN.fullmatch(self.parent_asin):
                raise ContractValidationError("parent_asin must be 10 uppercase alphanumeric characters")
        if self.identity_status not in {"CONFIRMED", "PARTIAL", "CONFLICTED", "UNKNOWN"}:
            raise ContractValidationError("invalid identity_status")


@dataclass(frozen=True, slots=True, kw_only=True)
class KeywordIdentity(JsonContract):
    keyword_id: str
    marketplace: str
    locale: str
    normalized_text: str
    raw_text: str

    def __post_init__(self) -> None:
        expected_marketplace = self.marketplace.strip().upper()
        expected_locale = self.locale.strip().lower()
        expected_text = " ".join(self.normalized_text.split()).casefold()
        if self.marketplace != expected_marketplace or self.locale != expected_locale or self.normalized_text != expected_text:
            raise ContractValidationError("keyword identity fields must already be normalized")
        expected = keyword_id(self.marketplace, self.locale, self.normalized_text)
        if self.keyword_id != expected:
            raise ContractValidationError(f"keyword_id must equal {expected}")
        _require_text("raw_text", self.raw_text)


@dataclass(frozen=True, slots=True, kw_only=True)
class Unit(JsonContract):
    dimension: str
    unit_code: str | None
    unit_system: str | None

    def __post_init__(self) -> None:
        _require_text("unit.dimension", self.dimension)


@dataclass(frozen=True, slots=True, kw_only=True)
class ValueEnvelope(JsonContract):
    presence_status: PresenceStatus
    raw_value: Any
    normalized_value: Any
    value_type: ValueType
    unit: Unit | None
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus

    def __post_init__(self) -> None:
        object.__setattr__(self, "raw_value", _freeze_json_value(self.raw_value, "value.raw_value"))
        object.__setattr__(self, "normalized_value", _freeze_json_value(self.normalized_value, "value.normalized_value"))
        absent = self.presence_status is not PresenceStatus.PRESENT
        if absent and (self.raw_value is not None or self.normalized_value is not None):
            raise ContractValidationError("non-present values must serialize raw_value and normalized_value as null")
        if self.presence_status is PresenceStatus.PRESENT and self.raw_value is None and self.normalized_value is None:
            raise ContractValidationError("PRESENT requires a raw or normalized value; numeric zero is valid")
        if absent and self.normalization_status is NormalizationStatus.NORMALIZED:
            raise ContractValidationError("non-present values cannot be NORMALIZED")


@dataclass(frozen=True, slots=True, kw_only=True)
class Scope(JsonContract):
    scope_type: ScopeType
    scope_status: ScopeStatus
    scope_subject_id: str | None

    def __post_init__(self) -> None:
        if self.scope_status is ScopeStatus.CONFIRMED:
            _require_text("scope_subject_id", self.scope_subject_id or "")


@dataclass(frozen=True, slots=True, kw_only=True)
class TimeWindow(JsonContract):
    observed_at: str | None
    observed_at_status: ObservedAtStatus
    retrieved_at: str
    period_start: str | None
    period_end: str | None
    period_type: PeriodType
    timezone: str | None

    def __post_init__(self) -> None:
        for name in ("observed_at", "retrieved_at", "period_start", "period_end"):
            _require_datetime(name, getattr(self, name))
        if self.observed_at_status is ObservedAtStatus.UNKNOWN and self.observed_at is not None:
            raise ContractValidationError("UNKNOWN observed_at_status requires observed_at=null")
        if self.observed_at_status is ObservedAtStatus.KNOWN and self.observed_at is None:
            raise ContractValidationError("KNOWN observed_at_status requires observed_at")
        if (self.period_start is None) != (self.period_end is None):
            raise ContractValidationError("period_start and period_end must be both present or both null")
        if self.period_start is not None and self.period_end is not None:
            start_text = self.period_start[:-1] + "+00:00" if self.period_start.endswith("Z") else self.period_start
            end_text = self.period_end[:-1] + "+00:00" if self.period_end.endswith("Z") else self.period_end
            if datetime.fromisoformat(start_text) > datetime.fromisoformat(end_text):
                raise ContractValidationError("period_start must not be after period_end")


@dataclass(frozen=True, slots=True, kw_only=True)
class RawEvidenceRecord(JsonContract):
    raw_evidence_id: str
    collection_run_id: str
    provider: str
    source_tool: str
    provider_schema_version: ProviderSchemaVersion
    sanitized_request: Mapping[str, Any]
    retrieved_at: str
    response_status: str
    media_type: str
    content_reference: str
    content_fingerprint: str
    pagination: Mapping[str, Any] | None = None
    error: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sanitized_request", _freeze_json_value(self.sanitized_request, "raw_evidence.sanitized_request"))
        if self.pagination is not None:
            object.__setattr__(self, "pagination", _freeze_json_value(self.pagination, "raw_evidence.pagination"))
        if self.error is not None:
            object.__setattr__(self, "error", _freeze_json_value(self.error, "raw_evidence.error"))
        for name in ("raw_evidence_id", "collection_run_id", "provider", "source_tool", "media_type", "content_reference", "content_fingerprint"):
            _require_text(name, getattr(self, name))
        _require_datetime("retrieved_at", self.retrieved_at)
        if self.response_status not in {"SUCCESS", "EMPTY", "PARTIAL", "FAILED"}:
            raise ContractValidationError("invalid raw response_status")


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformationProvenance(JsonContract):
    collection_run_id: str
    provider_schema_version: ProviderSchemaVersion
    mapping_version: str
    transformation_run_id: str
    transformation_code_version: TransformationCodeVersion
    raw_evidence_reference: str
    transformed_at: str
    transformation_status: TransformationStatus

    def __post_init__(self) -> None:
        for name in ("collection_run_id", "mapping_version", "transformation_run_id", "raw_evidence_reference"):
            _require_text(name, getattr(self, name))
        if self.mapping_version == "UNKNOWN":
            raise ContractValidationError("mapping_version cannot be UNKNOWN")
        _require_datetime("transformed_at", self.transformed_at)
        if self.transformation_status is TransformationStatus.FAILED:
            raise ContractValidationError("FAILED transformations cannot be embedded in emitted observations")


@dataclass(frozen=True, slots=True, kw_only=True)
class Provenance(JsonContract):
    provider: str
    source_tool: str
    source_field: str
    source_record_identity: str
    retrieved_at: str
    transformation: TransformationProvenance
    provider_semantic: str | None = None
    semantic_validation_status: SemanticStatus | None = None
    provider_method: str | None = None
    provider_documentation_reference: str | None = None

    def __post_init__(self) -> None:
        for name in ("provider", "source_tool", "source_field", "source_record_identity"):
            _require_text(name, getattr(self, name))
        _require_datetime("retrieved_at", self.retrieved_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalObservation(JsonContract):
    semantic_observation_id: str
    observation_id: str
    observation_kind: ObservationKind
    subject: SubjectRef
    evidence_type: EvidenceType
    value: ValueEnvelope
    scope: Scope
    time: TimeWindow
    provenance: Provenance
    quality_issue_ids: tuple[str, ...]
    result_status: ResultStatus
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_text("semantic_observation_id", self.semantic_observation_id)
        _require_text("observation_id", self.observation_id)
        if self.schema_version != SCHEMA_VERSION:
            raise ContractValidationError("schema_version must be 0.1")
        if self.evidence_type not in {EvidenceType.OBSERVED, EvidenceType.PROVIDER_ESTIMATE}:
            raise ContractValidationError("source observations must be OBSERVED or PROVIDER_ESTIMATE")
        _require_unique("quality_issue_ids", self.quality_issue_ids)
        if self.time.retrieved_at != self.provenance.retrieved_at:
            raise ContractValidationError("time.retrieved_at must match provenance.retrieved_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductFactObservation(CanonicalObservation):
    dimension: str
    fact_group: FactGroup
    provider_semantic: str | None = None

    def __post_init__(self) -> None:
        super(ProductFactObservation, self).__post_init__()
        if self.observation_kind is not ObservationKind.PRODUCT_FACT:
            raise ContractValidationError("ProductFactObservation requires PRODUCT_FACT kind")
        _require_text("dimension", self.dimension)


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricObservation(CanonicalObservation):
    metric: str
    measurement_type: EvidenceType
    metric_semantic: str | None
    currency: str | None = None
    rank_context: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        super(MetricObservation, self).__post_init__()
        if self.rank_context is not None:
            object.__setattr__(self, "rank_context", _freeze_json_value(self.rank_context, "metric.rank_context"))
        if self.observation_kind is not ObservationKind.METRIC:
            raise ContractValidationError("MetricObservation requires METRIC kind")
        _require_text("metric", self.metric)
        if self.measurement_type != self.evidence_type:
            raise ContractValidationError("measurement_type must equal evidence_type")


@dataclass(frozen=True, slots=True, kw_only=True)
class KeywordMetricObservation(CanonicalObservation):
    keyword: KeywordIdentity
    metric: str
    metric_semantic: str | None
    estimate_method_status: EstimateMethodStatus
    range: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        super(KeywordMetricObservation, self).__post_init__()
        if self.range is not None:
            object.__setattr__(self, "range", _freeze_json_value(self.range, "keyword_metric.range"))
        if self.observation_kind is not ObservationKind.KEYWORD_METRIC:
            raise ContractValidationError("KeywordMetricObservation requires KEYWORD_METRIC kind")
        _require_text("metric", self.metric)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductKeywordRelationshipObservation(CanonicalObservation):
    relationship_id: str
    product: ProductIdentity
    keyword: KeywordIdentity
    direction: RelationshipDirection
    relationship_type: RelationshipType
    channel: Channel
    query_result_status: ResultStatus
    rank: Mapping[str, Any] | None = None
    traffic: ValueEnvelope | None = None

    def __post_init__(self) -> None:
        super(ProductKeywordRelationshipObservation, self).__post_init__()
        if self.rank is not None:
            object.__setattr__(self, "rank", _freeze_json_value(self.rank, "relationship.rank"))
        if self.observation_kind is not ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP:
            raise ContractValidationError("relationship observation requires PRODUCT_KEYWORD_RELATIONSHIP kind")
        _require_text("relationship_id", self.relationship_id)
        if self.query_result_status is ResultStatus.EMPTY_OBSERVATION and self.value.presence_status is PresenceStatus.PRESENT:
            raise ContractValidationError("empty query result cannot carry a present relationship value")


@dataclass(frozen=True, slots=True, kw_only=True)
class DirectionalQueryExecutionRecord(JsonContract):
    """Provider-neutral evidence that one directional relationship query executed."""

    query_execution_id: str
    query_keyword: KeywordIdentity | None
    query_product: ProductIdentity | None
    direction: RelationshipDirection
    outcome: QueryExecutionOutcome
    related_relationship_observation_ids: tuple[str, ...]
    provenance: Provenance
    quality_issue_ids: tuple[str, ...]
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        related_ids = tuple(self.related_relationship_observation_ids)
        issue_ids = tuple(self.quality_issue_ids)
        _require_unique("related_relationship_observation_ids", related_ids)
        _require_unique("query_execution.quality_issue_ids", issue_ids)
        object.__setattr__(
            self,
            "related_relationship_observation_ids",
            tuple(sorted(related_ids)),
        )
        object.__setattr__(
            self,
            "quality_issue_ids",
            tuple(sorted(issue_ids)),
        )
        _require_text("query_execution_id", self.query_execution_id)
        if self.schema_version != SCHEMA_VERSION:
            raise ContractValidationError("query execution schema_version must be 0.1")
        if not isinstance(self.direction, RelationshipDirection):
            raise ContractValidationError("query execution direction must be RelationshipDirection")
        if not isinstance(self.outcome, QueryExecutionOutcome):
            raise ContractValidationError("query execution outcome must be QueryExecutionOutcome")
        if not isinstance(self.provenance, Provenance):
            raise ContractValidationError("query execution provenance must be Provenance")
        if self.direction is RelationshipDirection.KEYWORD_TO_PRODUCT:
            if not isinstance(self.query_keyword, KeywordIdentity) or self.query_product is not None:
                raise ContractValidationError("KEYWORD_TO_PRODUCT query requires only query_keyword")
        elif self.direction is RelationshipDirection.PRODUCT_TO_KEYWORD:
            if not isinstance(self.query_product, ProductIdentity) or self.query_keyword is not None:
                raise ContractValidationError("PRODUCT_TO_KEYWORD query requires only query_product")
        else:
            raise ContractValidationError("invalid query execution direction")
        if self.outcome is QueryExecutionOutcome.RESULTS_RETURNED:
            if not self.related_relationship_observation_ids:
                raise ContractValidationError("RESULTS_RETURNED requires relationship observations")
        elif self.related_relationship_observation_ids:
            raise ContractValidationError(
                f"{self.outcome.value} cannot reference relationship observations"
            )
        expected = query_execution_id(
            query_keyword=self.query_keyword,
            query_product=self.query_product,
            direction=self.direction,
            outcome=self.outcome,
            related_relationship_observation_ids=self.related_relationship_observation_ids,
            provenance=self.provenance,
            quality_issue_ids=self.quality_issue_ids,
            schema_version=self.schema_version,
        )
        if self.query_execution_id != expected:
            raise ContractValidationError(f"query_execution_id must equal {expected}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ReviewObservation(CanonicalObservation):
    review_observation_id: str
    product: ProductIdentity
    provider_review_identity: str | None
    rating: ValueEnvelope
    title: ValueEnvelope
    body: ValueEnvelope
    review_date: ValueEnvelope
    variant: ValueEnvelope
    helpful_votes: ValueEnvelope

    def __post_init__(self) -> None:
        super(ReviewObservation, self).__post_init__()
        if self.observation_kind is not ObservationKind.REVIEW:
            raise ContractValidationError("ReviewObservation requires REVIEW kind")
        _require_text("review_observation_id", self.review_observation_id)


@dataclass(frozen=True, slots=True, kw_only=True)
class TransformationRunRecord(JsonContract):
    provider: str
    collection_run_id: str
    provider_schema_version: ProviderSchemaVersion
    mapping_version: str
    transformation_run_id: str
    transformation_code_version: TransformationCodeVersion
    started_at: str
    completed_at: str | None
    status: TransformationStatus
    input_raw_evidence_references: tuple[str, ...]
    output_observation_ids: tuple[str, ...]
    quality_issue_ids: tuple[str, ...]
    output_query_execution_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "output_query_execution_ids",
            tuple(self.output_query_execution_ids),
        )
        for name in ("provider", "collection_run_id", "mapping_version", "transformation_run_id"):
            _require_text(name, getattr(self, name))
        if self.mapping_version == "UNKNOWN":
            raise ContractValidationError("mapping_version cannot be UNKNOWN")
        _require_datetime("started_at", self.started_at)
        _require_datetime("completed_at", self.completed_at)
        if not self.input_raw_evidence_references:
            raise ContractValidationError("transformation run requires at least one raw input")
        for name in (
            "input_raw_evidence_references",
            "output_observation_ids",
            "quality_issue_ids",
            "output_query_execution_ids",
        ):
            _require_unique(name, getattr(self, name))
        if (
            self.status is TransformationStatus.SUCCESS
            and not self.output_observation_ids
            and not self.output_query_execution_ids
        ):
            raise ContractValidationError("SUCCESS transformation requires an output")
        if self.status is TransformationStatus.FAILED and (
            self.output_observation_ids or self.output_query_execution_ids
        ):
            raise ContractValidationError("FAILED transformation cannot list outputs")


@dataclass(frozen=True, slots=True, kw_only=True)
class DataQualityIssue(JsonContract):
    issue_id: str
    issue_code: str
    severity: Severity
    subject: SubjectRef
    dimension: str | None
    message: str
    blocking: bool
    blocking_scope: BlockingScope
    source_references: tuple[str, ...]
    created_at: str
    origin_stage: OriginStage | None = None
    collection_run_id: str | None = None
    transformation_run_id: str | None = None
    mapping_version: str | None = None

    def __post_init__(self) -> None:
        for name in ("issue_id", "issue_code", "message"):
            _require_text(name, getattr(self, name))
        _require_datetime("created_at", self.created_at)
        _require_unique("source_references", self.source_references)
        if self.blocking != (self.blocking_scope is not BlockingScope.NONE):
            raise ContractValidationError("blocking must agree with blocking_scope")
        if self.origin_stage is OriginStage.COLLECTION:
            _require_text("collection_run_id", self.collection_run_id or "")
        if self.origin_stage in {OriginStage.MAPPING, OriginStage.NORMALIZATION}:
            for name in ("collection_run_id", "transformation_run_id", "mapping_version"):
                _require_text(name, getattr(self, name) or "")
            if self.mapping_version == "UNKNOWN":
                raise ContractValidationError("mapping-origin issue cannot use UNKNOWN mapping_version")


@dataclass(frozen=True, slots=True, kw_only=True)
class Comparability(JsonContract):
    identity: CheckStatus
    dimension: CheckStatus
    semantic: CheckStatus
    scope: CheckStatus
    period: CheckStatus
    unit: CheckStatus
    direction: CheckStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ConflictRecord(JsonContract):
    conflict_id: str
    subject: SubjectRef
    dimension: str
    candidate_observation_ids: tuple[str, ...]
    conflict_status: ConflictStatus
    comparability: Comparability
    difference: Mapping[str, Any] | None
    severity: Severity
    blocking: bool
    blocking_scope: BlockingScope
    resolution_status: ResolutionStatus
    explanation: str

    def __post_init__(self) -> None:
        if self.difference is not None:
            object.__setattr__(self, "difference", _freeze_json_value(self.difference, "conflict.difference"))
        for name in ("conflict_id", "dimension", "explanation"):
            _require_text(name, getattr(self, name))
        if not self.candidate_observation_ids:
            raise ContractValidationError("conflict requires at least one candidate")
        _require_unique("candidate_observation_ids", self.candidate_observation_ids)
        expected_id = conflict_record_id(
            subject=self.subject,
            dimension=self.dimension,
            candidate_observation_ids=self.candidate_observation_ids,
            conflict_status=self.conflict_status,
        )
        if self.conflict_id != expected_id:
            raise ContractValidationError(f"conflict_id must equal {expected_id}")
        if self.conflict_status is ConflictStatus.ONE_SOURCE_ONLY and len(self.candidate_observation_ids) != 1:
            raise ContractValidationError("ONE_SOURCE_ONLY requires exactly one candidate")
        if self.blocking != (self.blocking_scope is not BlockingScope.NONE):
            raise ContractValidationError("blocking must agree with blocking_scope")
        must_remain_unresolved = {
            ConflictStatus.MATERIAL_DIFFERENCE,
            ConflictStatus.SEMANTIC_CONFLICT,
            ConflictStatus.UNIT_CONFLICT,
            ConflictStatus.DIRECTIONAL_CONFLICT,
            ConflictStatus.UNKNOWN,
        }
        if self.conflict_status in must_remain_unresolved and self.resolution_status not in {
            ResolutionStatus.UNRESOLVED,
            ResolutionStatus.DEFERRED,
            ResolutionStatus.REJECTED_INPUT,
        }:
            raise ContractValidationError(f"{self.conflict_status.value} cannot be represented as resolved")
        if self.conflict_status is ConflictStatus.NOT_DIRECTLY_COMPARABLE and self.resolution_status not in {
            ResolutionStatus.UNRESOLVED,
            ResolutionStatus.NOT_REQUIRED,
            ResolutionStatus.DEFERRED,
        }:
            raise ContractValidationError("NOT_DIRECTLY_COMPARABLE cannot select a canonical value")


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolutionLineage(JsonContract):
    observation_ids: tuple[str, ...]
    raw_evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.observation_ids or not self.raw_evidence_ids:
            raise ContractValidationError("resolution lineage requires observation and raw evidence IDs")
        _require_unique("lineage.observation_ids", self.observation_ids)
        _require_unique("lineage.raw_evidence_ids", self.raw_evidence_ids)


@dataclass(frozen=True, slots=True, kw_only=True)
class ResolvedEvidence(JsonContract):
    resolution_id: str
    subject: SubjectRef
    dimension: str
    candidate_observation_ids: tuple[str, ...]
    conflict_id: str | None
    conflict_status: ConflictStatus
    resolution_status: ResolutionStatus
    value: ValueEnvelope
    resolution_method: str
    resolution_policy: str | None
    quality_issue_ids: tuple[str, ...]
    lineage: ResolutionLineage
    evidence_type: EvidenceType = EvidenceType.RESOLVED

    def __post_init__(self) -> None:
        for name in ("resolution_id", "dimension", "resolution_method"):
            _require_text(name, getattr(self, name))
        if self.evidence_type is not EvidenceType.RESOLVED:
            raise ContractValidationError("resolved evidence must use evidence_type=RESOLVED")
        if not self.candidate_observation_ids:
            raise ContractValidationError("resolution requires candidates")
        _require_unique("candidate_observation_ids", self.candidate_observation_ids)
        _require_unique("quality_issue_ids", self.quality_issue_ids)
        expected_id = resolution_record_id(
            subject=self.subject,
            dimension=self.dimension,
            candidate_observation_ids=self.candidate_observation_ids,
            resolution_policy=self.resolution_policy,
        )
        if self.resolution_id != expected_id:
            raise ContractValidationError(f"resolution_id must equal {expected_id}")
        if set(self.candidate_observation_ids) != set(self.lineage.observation_ids):
            raise ContractValidationError("resolution candidates must equal lineage observation IDs")
        if self.resolution_status is ResolutionStatus.RESOLVED_BY_POLICY:
            _require_text("resolution_policy", self.resolution_policy or "")
        if self.resolution_status in {ResolutionStatus.UNRESOLVED, ResolutionStatus.DEFERRED, ResolutionStatus.REJECTED_INPUT}:
            if self.value.presence_status is not PresenceStatus.UNKNOWN:
                raise ContractValidationError("unresolved/deferred/rejected evidence must have UNKNOWN value")
        if self.resolution_status is ResolutionStatus.NOT_REQUIRED and self.value.presence_status is not PresenceStatus.UNKNOWN:
            raise ContractValidationError("NOT_REQUIRED evidence must not publish a canonical value")
        if self.resolution_status in {ResolutionStatus.RESOLVED_DETERMINISTIC, ResolutionStatus.RESOLVED_BY_POLICY}:
            if self.value.presence_status not in {PresenceStatus.PRESENT, PresenceStatus.EXPLICIT_NULL}:
                raise ContractValidationError("resolved evidence must publish a PRESENT or EXPLICIT_NULL value")


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalEvidenceBundle(JsonContract):
    transformation_runs: tuple[TransformationRunRecord, ...]
    observations: tuple[CanonicalObservation, ...]
    conflicts: tuple[ConflictRecord, ...]
    resolutions: tuple[ResolvedEvidence, ...]
    quality_issues: tuple[DataQualityIssue, ...]
    raw_evidence_references: tuple[str, ...] = ()
    query_execution_records: tuple[DirectionalQueryExecutionRecord, ...] = ()
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "query_execution_records",
            tuple(self.query_execution_records),
        )
        if not all(
            isinstance(record, DirectionalQueryExecutionRecord)
            for record in self.query_execution_records
        ):
            raise ContractValidationError(
                "query_execution_records must contain DirectionalQueryExecutionRecord values"
            )
        if self.schema_version != SCHEMA_VERSION:
            raise ContractValidationError("bundle schema_version must be 0.1")
        self.validate()

    def validate(self) -> "CanonicalEvidenceBundle":
        errors: list[str] = []
        _collect_duplicate_ids(errors, "transformation_run_id", (run.transformation_run_id for run in self.transformation_runs))
        _collect_duplicate_ids(errors, "conflict_id", (item.conflict_id for item in self.conflicts))
        _collect_duplicate_ids(errors, "resolution_id", (item.resolution_id for item in self.resolutions))
        _collect_duplicate_ids(errors, "issue_id", (item.issue_id for item in self.quality_issues))
        _collect_duplicate_ids(
            errors,
            "query_execution_id",
            (item.query_execution_id for item in self.query_execution_records),
        )
        _require_unique("raw_evidence_references", self.raw_evidence_references)

        raw_ids = set(self.raw_evidence_references)
        runs = {run.transformation_run_id: run for run in self.transformation_runs}
        issue_ids = {issue.issue_id for issue in self.quality_issues}
        observation_ids = {item.observation_id for item in self.observations}
        query_execution_ids = {
            item.query_execution_id for item in self.query_execution_records
        }
        observations_by_id: dict[str, CanonicalObservation] = {}
        conflicts = {item.conflict_id: item for item in self.conflicts}
        resolution_ids = {item.resolution_id for item in self.resolutions}
        emissions: set[tuple[str, str]] = set()
        semantic_emissions: set[tuple[str, str]] = set()

        for run in self.transformation_runs:
            for raw_id in run.input_raw_evidence_references:
                if raw_id not in raw_ids:
                    errors.append(f"run {run.transformation_run_id} references unknown raw evidence {raw_id}")
            for output_id in run.output_observation_ids:
                if output_id not in observation_ids:
                    errors.append(f"run {run.transformation_run_id} references unknown observation {output_id}")
            for output_id in run.output_query_execution_ids:
                if output_id not in query_execution_ids:
                    errors.append(
                        f"run {run.transformation_run_id} references unknown query execution {output_id}"
                    )
            for issue_id in run.quality_issue_ids:
                if issue_id not in issue_ids:
                    errors.append(f"run {run.transformation_run_id} references unknown quality issue {issue_id}")

        for observation in self.observations:
            transform = observation.provenance.transformation
            emission = (transform.transformation_run_id, observation.observation_id)
            if emission in emissions:
                errors.append(f"duplicate materialized emission {emission}")
            emissions.add(emission)
            semantic_emission = (transform.transformation_run_id, observation.semantic_observation_id)
            if semantic_emission in semantic_emissions:
                errors.append(f"run {transform.transformation_run_id} emits duplicate semantic observation {observation.semantic_observation_id}")
            semantic_emissions.add(semantic_emission)
            prior_revision = observations_by_id.get(observation.observation_id)
            if prior_revision is not None and _observation_revision_content(prior_revision) != _observation_revision_content(observation):
                errors.append(f"observation_id {observation.observation_id} maps to conflicting canonical content")
            observations_by_id.setdefault(observation.observation_id, observation)
            run = runs.get(transform.transformation_run_id)
            if run is None:
                errors.append(f"observation {observation.observation_id} has no transformation run")
                continue
            expected_pairs = (
                ("provider", observation.provenance.provider, run.provider),
                ("collection_run_id", transform.collection_run_id, run.collection_run_id),
                ("mapping_version", transform.mapping_version, run.mapping_version),
                ("provider_schema_version", transform.provider_schema_version, run.provider_schema_version),
                ("transformation_code_version", transform.transformation_code_version, run.transformation_code_version),
            )
            for name, embedded, recorded in expected_pairs:
                if embedded != recorded:
                    errors.append(f"observation {observation.observation_id} has mismatched {name}")
            if observation.observation_id not in run.output_observation_ids:
                errors.append(f"run {run.transformation_run_id} does not list observation {observation.observation_id}")
            if transform.raw_evidence_reference not in run.input_raw_evidence_references:
                errors.append(f"observation {observation.observation_id} primary raw input is not listed by its run")
            for issue_id in observation.quality_issue_ids:
                if issue_id not in issue_ids:
                    errors.append(f"observation {observation.observation_id} references unknown quality issue {issue_id}")

        for query_execution in self.query_execution_records:
            transform = query_execution.provenance.transformation
            run = runs.get(transform.transformation_run_id)
            if run is None:
                errors.append(
                    f"query execution {query_execution.query_execution_id} has no transformation run"
                )
                continue
            expected_pairs = (
                ("provider", query_execution.provenance.provider, run.provider),
                ("collection_run_id", transform.collection_run_id, run.collection_run_id),
                ("mapping_version", transform.mapping_version, run.mapping_version),
                ("provider_schema_version", transform.provider_schema_version, run.provider_schema_version),
                (
                    "transformation_code_version",
                    transform.transformation_code_version,
                    run.transformation_code_version,
                ),
                ("transformation_status", transform.transformation_status, run.status),
            )
            for name, embedded, recorded in expected_pairs:
                if embedded != recorded:
                    errors.append(
                        f"query execution {query_execution.query_execution_id} has mismatched {name}"
                    )
            if query_execution.query_execution_id not in run.output_query_execution_ids:
                errors.append(
                    f"run {run.transformation_run_id} does not list query execution "
                    f"{query_execution.query_execution_id}"
                )
            if transform.raw_evidence_reference not in run.input_raw_evidence_references:
                errors.append(
                    f"query execution {query_execution.query_execution_id} primary raw input is not listed by its run"
                )
            for issue_id in query_execution.quality_issue_ids:
                if issue_id not in issue_ids:
                    errors.append(
                        f"query execution {query_execution.query_execution_id} references unknown quality issue {issue_id}"
                    )
            for observation_id in query_execution.related_relationship_observation_ids:
                observation = observations_by_id.get(observation_id)
                if observation is None:
                    errors.append(
                        f"query execution {query_execution.query_execution_id} references unknown relationship observation {observation_id}"
                    )
                    continue
                if not isinstance(observation, ProductKeywordRelationshipObservation):
                    errors.append(
                        f"query execution {query_execution.query_execution_id} references non-relationship observation {observation_id}"
                    )
                    continue
                if observation.direction is not query_execution.direction:
                    errors.append(
                        f"query execution {query_execution.query_execution_id} relationship direction mismatch"
                    )
                if (
                    query_execution.direction is RelationshipDirection.KEYWORD_TO_PRODUCT
                    and observation.keyword != query_execution.query_keyword
                ):
                    errors.append(
                        f"query execution {query_execution.query_execution_id} keyword subject mismatch"
                    )
                if (
                    query_execution.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
                    and observation.product != query_execution.query_product
                ):
                    errors.append(
                        f"query execution {query_execution.query_execution_id} product subject mismatch"
                    )
                if observation.provenance.transformation != transform:
                    errors.append(
                        f"query execution {query_execution.query_execution_id} relationship transformation mismatch"
                    )

        for conflict in self.conflicts:
            for observation_id in conflict.candidate_observation_ids:
                if observation_id not in observation_ids:
                    errors.append(f"conflict {conflict.conflict_id} references unknown observation {observation_id}")

        for resolution in self.resolutions:
            linked_conflict = conflicts.get(resolution.conflict_id) if resolution.conflict_id is not None else None
            if resolution.conflict_id is not None and linked_conflict is None:
                errors.append(f"resolution {resolution.resolution_id} references unknown conflict {resolution.conflict_id}")
            if linked_conflict is not None:
                if linked_conflict.subject != resolution.subject:
                    errors.append(f"resolution {resolution.resolution_id} subject does not match conflict {linked_conflict.conflict_id}")
                if linked_conflict.dimension != resolution.dimension:
                    errors.append(f"resolution {resolution.resolution_id} dimension does not match conflict {linked_conflict.conflict_id}")
                if set(linked_conflict.candidate_observation_ids) != set(resolution.candidate_observation_ids):
                    errors.append(f"resolution {resolution.resolution_id} candidates do not match conflict {linked_conflict.conflict_id}")
                if linked_conflict.conflict_status is not resolution.conflict_status:
                    errors.append(f"resolution {resolution.resolution_id} status does not match conflict {linked_conflict.conflict_id}")
                if linked_conflict.resolution_status is not resolution.resolution_status:
                    errors.append(f"resolution {resolution.resolution_id} outcome does not match conflict {linked_conflict.conflict_id}")
            for observation_id in resolution.candidate_observation_ids:
                if observation_id not in observation_ids:
                    errors.append(f"resolution {resolution.resolution_id} references unknown observation {observation_id}")
            candidate_raw_ids = {
                observations_by_id[observation_id].provenance.transformation.raw_evidence_reference
                for observation_id in resolution.candidate_observation_ids
                if observation_id in observations_by_id
            }
            if candidate_raw_ids and candidate_raw_ids != set(resolution.lineage.raw_evidence_ids):
                errors.append(f"resolution {resolution.resolution_id} raw lineage does not match its candidates")
            for raw_id in resolution.lineage.raw_evidence_ids:
                if raw_id not in raw_ids:
                    errors.append(f"resolution {resolution.resolution_id} references unknown raw evidence {raw_id}")
            for issue_id in resolution.quality_issue_ids:
                if issue_id not in issue_ids:
                    errors.append(f"resolution {resolution.resolution_id} references unknown quality issue {issue_id}")

        valid_source_references = (
            raw_ids
            | observation_ids
            | query_execution_ids
            | set(conflicts)
            | resolution_ids
            | set(runs)
        )
        collection_ids = {run.collection_run_id for run in self.transformation_runs}
        for issue in self.quality_issues:
            for source_reference in issue.source_references:
                if source_reference not in valid_source_references:
                    errors.append(f"quality issue {issue.issue_id} references unknown artifact {source_reference}")
            if issue.collection_run_id is not None and issue.collection_run_id not in collection_ids:
                errors.append(f"quality issue {issue.issue_id} references unknown collection run {issue.collection_run_id}")
            if issue.transformation_run_id is not None:
                issue_run = runs.get(issue.transformation_run_id)
                if issue_run is None:
                    errors.append(f"quality issue {issue.issue_id} references unknown transformation run {issue.transformation_run_id}")
                else:
                    if issue.collection_run_id is not None and issue.collection_run_id != issue_run.collection_run_id:
                        errors.append(f"quality issue {issue.issue_id} collection does not match its transformation run")
                    if issue.mapping_version is not None and issue.mapping_version != issue_run.mapping_version:
                        errors.append(f"quality issue {issue.issue_id} mapping version does not match its transformation run")

        if errors:
            raise ContractValidationError(errors)
        return self


def _collect_duplicate_ids(errors: list[str], name: str, values: Iterable[str]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            errors.append(f"duplicate {name}: {value}")
        seen.add(value)


def _observation_revision_content(observation: CanonicalObservation) -> dict[str, Any]:
    payload = observation.to_dict()
    for key in ("semantic_observation_id", "observation_id", "provenance", "quality_issue_ids", "result_status"):
        payload.pop(key, None)
    time_payload = payload.get("time")
    if isinstance(time_payload, dict):
        time_payload.pop("retrieved_at", None)
    return payload


__all__ = (
    "SCHEMA_VERSION",
    "ContractValidationError",
    "EvidenceType",
    "PresenceStatus",
    "SemanticStatus",
    "ResultStatus",
    "VersionStatus",
    "ProviderSchemaSource",
    "CodeVersionScheme",
    "TransformationStatus",
    "SubjectType",
    "ScopeType",
    "ScopeStatus",
    "ObservedAtStatus",
    "PeriodType",
    "ValueType",
    "NormalizationStatus",
    "ObservationKind",
    "FactGroup",
    "EstimateMethodStatus",
    "RelationshipDirection",
    "QueryExecutionOutcome",
    "RelationshipType",
    "Channel",
    "Severity",
    "BlockingScope",
    "OriginStage",
    "CheckStatus",
    "ConflictStatus",
    "ResolutionStatus",
    "JsonContract",
    "canonical_json",
    "deterministic_id",
    "product_id",
    "keyword_id",
    "semantic_observation_id",
    "observation_revision_id",
    "raw_evidence_id",
    "relationship_observation_id",
    "query_execution_id",
    "conflict_record_id",
    "resolution_record_id",
    "ProviderSchemaVersion",
    "TransformationCodeVersion",
    "SubjectRef",
    "ProductIdentity",
    "KeywordIdentity",
    "Unit",
    "ValueEnvelope",
    "Scope",
    "TimeWindow",
    "RawEvidenceRecord",
    "TransformationProvenance",
    "Provenance",
    "CanonicalObservation",
    "ProductFactObservation",
    "MetricObservation",
    "KeywordMetricObservation",
    "ProductKeywordRelationshipObservation",
    "DirectionalQueryExecutionRecord",
    "ReviewObservation",
    "TransformationRunRecord",
    "DataQualityIssue",
    "Comparability",
    "ConflictRecord",
    "ResolutionLineage",
    "ResolvedEvidence",
    "CanonicalEvidenceBundle",
)
