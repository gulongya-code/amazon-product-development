"""Snapshot-to-Canonical business mapping contracts for the P0 API slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import re
from types import MappingProxyType
from typing import Any, Mapping


_CANONICAL_FIELD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class EntityType(StrEnum):
    PRODUCT = "PRODUCT"
    KEYWORD = "KEYWORD"


class MappingConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CanonicalFieldStatus(StrEnum):
    PRESENT = "PRESENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    UNKNOWN = "UNKNOWN"
    PENDING = "PENDING"
    CONFLICT = "CONFLICT"


P0_PRODUCT_FIELDS = (
    "product.asin",
    "product.title",
    "product.category",
    "product.brand",
    "metric.price",
    "metric.review_count",
    "metric.rating",
    "metric.bsr",
    "metric.estimated_monthly_sales",
    "metric.orders",
)
P0_KEYWORD_FIELDS = (
    "keyword.text",
    "keyword.search_volume",
    "keyword.trend",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalFieldMapping:
    """One explicit source field mapping with auditable semantics."""

    source: str
    source_field: str
    canonical_field: str
    transform_rule: str
    confidence: MappingConfidence
    notes: str
    operations: tuple[str, ...]
    entity_type: EntityType
    record_field: str

    def __post_init__(self) -> None:
        for name in ("source", "source_field", "transform_rule", "notes", "record_field"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not _CANONICAL_FIELD.fullmatch(self.canonical_field):
            raise ValueError("canonical_field must be a dotted lowercase identifier")
        if not isinstance(self.confidence, MappingConfidence):
            raise TypeError("confidence must be MappingConfidence")
        if not isinstance(self.entity_type, EntityType):
            raise TypeError("entity_type must be EntityType")
        operations = tuple(self.operations)
        if not operations or any(not isinstance(item, str) or not item.strip() for item in operations):
            raise ValueError("operations must contain non-empty operation names")
        object.__setattr__(self, "operations", operations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "source_field": self.source_field,
            "canonical_field": self.canonical_field,
            "transform_rule": self.transform_rule,
            "confidence": self.confidence.value,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class MappedField:
    canonical_field: str
    raw_value: Any
    status: CanonicalFieldStatus
    mapping: CanonicalFieldMapping | None
    currency: str | None = None
    observed_at: str | None = None

    def __post_init__(self) -> None:
        if not _CANONICAL_FIELD.fullmatch(self.canonical_field):
            raise ValueError("canonical_field must be a dotted lowercase identifier")
        if not isinstance(self.status, CanonicalFieldStatus):
            raise TypeError("status must be CanonicalFieldStatus")
        if self.mapping is not None and self.mapping.canonical_field != self.canonical_field:
            raise ValueError("mapping canonical field does not match mapped field")
        if self.currency is not None:
            normalized = self.currency.strip().upper()
            if len(normalized) != 3 or not normalized.isalpha():
                raise ValueError("currency must be an ISO-style three-letter code")
            object.__setattr__(self, "currency", normalized)


@dataclass(frozen=True, slots=True, kw_only=True)
class MappedEntity:
    source: str
    snapshot_id: str
    timestamp: str
    entity_type: EntityType
    identity_hint: str | None
    fields: Mapping[str, MappedField]

    def __post_init__(self) -> None:
        for name in ("source", "snapshot_id", "timestamp"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        fields = dict(self.fields)
        if any(key != value.canonical_field for key, value in fields.items()):
            raise ValueError("field keys must match MappedField canonical fields")
        object.__setattr__(self, "fields", MappingProxyType(fields))


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_json_value(item) for item in value]
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalFieldValue:
    value: Any
    source: str
    snapshot_id: str
    timestamp: str
    confidence: MappingConfidence
    status: CanonicalFieldStatus
    currency: str | None = None
    observed_at: str | None = None
    source_field: str | None = None
    transform_rule: str | None = None
    quality: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("source", "snapshot_id", "timestamp"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(self.confidence, MappingConfidence):
            raise TypeError("confidence must be MappingConfidence")
        if not isinstance(self.status, CanonicalFieldStatus):
            raise TypeError("status must be CanonicalFieldStatus")
        quality = tuple(self.quality)
        if any(not isinstance(item, str) or not item.strip() for item in quality):
            raise ValueError("quality entries must be non-empty text")
        object.__setattr__(self, "quality", quality)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": _json_value(self.value),
            "source": self.source,
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "confidence": self.confidence.value,
            "status": self.status.value,
            "currency": self.currency,
            "observed_at": self.observed_at,
            "source_field": self.source_field,
            "transform_rule": self.transform_rule,
            "quality": list(self.quality),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalEntity:
    entity_type: EntityType
    identity: str | None
    fields: Mapping[str, CanonicalFieldValue] = field(default_factory=dict)

    def __post_init__(self) -> None:
        fields = dict(self.fields)
        if any(not _CANONICAL_FIELD.fullmatch(key) for key in fields):
            raise ValueError("Canonical entity fields must use dotted identifiers")
        object.__setattr__(self, "fields", MappingProxyType(fields))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type.value,
            "identity": self.identity,
            "fields": {key: value.to_dict() for key, value in self.fields.items()},
        }


def _mapping(
    source: str,
    source_field: str,
    canonical_field: str,
    transform_rule: str,
    confidence: MappingConfidence,
    notes: str,
    operations: tuple[str, ...],
    entity_type: EntityType,
    record_field: str,
) -> CanonicalFieldMapping:
    return CanonicalFieldMapping(
        source=source,
        source_field=source_field,
        canonical_field=canonical_field,
        transform_rule=transform_rule,
        confidence=confidence,
        notes=notes,
        operations=operations,
        entity_type=entity_type,
        record_field=record_field,
    )


_SORFTIME_DETAIL = ("product_detail",)
_XIYOU_INFO = ("asin_info", "asin_info_http_v2")
_XIYOU_BSR = ("asin_bsr_trends", "asin_bsr_trends_http_v2")
_XIYOU_ORDERS = ("asin_orders_last_30_days",)
_XIYOU_KEYWORD = ("keyword_info", "keyword_info_http_v2")


P0_FIELD_MAPPINGS = (
    _mapping("sorftime", "data.asin", "product.asin", "normalize_asin", MappingConfidence.HIGH, "Direct product identifier.", _SORFTIME_DETAIL, EntityType.PRODUCT, "asin"),
    _mapping("sorftime", "data.title", "product.title", "normalize_text", MappingConfidence.HIGH, "Direct listing title.", _SORFTIME_DETAIL, EntityType.PRODUCT, "title"),
    _mapping("sorftime", "data.category", "product.category", "normalize_text", MappingConfidence.HIGH, "Direct provider category label.", _SORFTIME_DETAIL, EntityType.PRODUCT, "category"),
    _mapping("sorftime", "data.brand", "product.brand", "normalize_text", MappingConfidence.HIGH, "Direct provider brand field.", _SORFTIME_DETAIL, EntityType.PRODUCT, "brand"),
    _mapping("sorftime", "data.price", "metric.price", "normalize_price", MappingConfidence.HIGH, "Direct selling price; currency remains explicit context.", _SORFTIME_DETAIL, EntityType.PRODUCT, "price"),
    _mapping("sorftime", "data.review_count", "metric.review_count", "normalize_compact_count", MappingConfidence.HIGH, "Displayed review count.", _SORFTIME_DETAIL, EntityType.PRODUCT, "review_count"),
    _mapping("sorftime", "data.star_rating", "metric.rating", "normalize_rating", MappingConfidence.HIGH, "Displayed rating on a five-point scale.", _SORFTIME_DETAIL, EntityType.PRODUCT, "star_rating"),
    _mapping("sorftime", "data.monthly_sales_volume", "metric.estimated_monthly_sales", "normalize_monthly_sales", MappingConfidence.MEDIUM, "Provider monthly sales estimate; estimation method remains provider-defined.", _SORFTIME_DETAIL, EntityType.PRODUCT, "monthly_sales_volume"),
    _mapping("sorftime", "data.estimated_sales", "metric.estimated_monthly_sales", "normalize_monthly_sales", MappingConfidence.MEDIUM, "Supported monthly-sales alias; period semantics must be supplied by the source contract.", _SORFTIME_DETAIL, EntityType.PRODUCT, "estimated_sales"),
    _mapping("sorftime", "data.sales", "metric.estimated_monthly_sales", "normalize_monthly_sales", MappingConfidence.LOW, "Legacy sales alias; retained at low mapping confidence.", _SORFTIME_DETAIL, EntityType.PRODUCT, "sales"),
    _mapping("sorftime", "data.sale_num", "metric.estimated_monthly_sales", "normalize_monthly_sales", MappingConfidence.MEDIUM, "Supported monthly-sales count alias.", _SORFTIME_DETAIL, EntityType.PRODUCT, "sale_num"),
    _mapping("xiyou", "data.entities[].asin", "product.asin", "normalize_asin", MappingConfidence.HIGH, "Direct ASIN from product facts.", _XIYOU_INFO, EntityType.PRODUCT, "asin"),
    _mapping("xiyou", "data.entities[].title", "product.title", "normalize_text", MappingConfidence.HIGH, "Direct listing title.", _XIYOU_INFO, EntityType.PRODUCT, "title"),
    _mapping("xiyou", "data.entities[].price", "metric.price", "normalize_price", MappingConfidence.HIGH, "Direct price with record currency when supplied.", _XIYOU_INFO, EntityType.PRODUCT, "price"),
    _mapping("xiyou", "data.entities[].ratings", "metric.review_count", "normalize_compact_count", MappingConfidence.HIGH, "Displayed ratings/review count.", _XIYOU_INFO, EntityType.PRODUCT, "ratings"),
    _mapping("xiyou", "data.entities[].stars", "metric.rating", "normalize_rating", MappingConfidence.HIGH, "Displayed rating on a five-point scale.", _XIYOU_INFO, EntityType.PRODUCT, "stars"),
    _mapping("xiyou", "data.asin", "product.asin", "normalize_asin", MappingConfidence.HIGH, "Direct ASIN from BSR response.", _XIYOU_BSR, EntityType.PRODUCT, "asin"),
    _mapping("xiyou", "data.categoryTree[].name", "product.category", "normalize_text", MappingConfidence.MEDIUM, "Deepest returned non-root category label.", _XIYOU_BSR, EntityType.PRODUCT, "category"),
    _mapping("xiyou", "data.trends[].values[].rank", "metric.bsr", "normalize_rank", MappingConfidence.HIGH, "Latest dated rank for the selected category context.", _XIYOU_BSR, EntityType.PRODUCT, "bsr"),
    _mapping("xiyou", "data.entities[].asin", "product.asin", "normalize_asin", MappingConfidence.HIGH, "Direct ASIN from recent-order response.", _XIYOU_ORDERS, EntityType.PRODUCT, "asin"),
    _mapping("xiyou", "data.entities[].orders", "metric.orders", "normalize_compact_count", MappingConfidence.HIGH, "Recent order evidence remains distinct from monthly sales estimates.", _XIYOU_ORDERS, EntityType.PRODUCT, "orders"),
    _mapping("xiyou", "data.list[].searchTerm", "keyword.text", "normalize_keyword", MappingConfidence.HIGH, "Direct provider search term.", _XIYOU_KEYWORD, EntityType.KEYWORD, "searchTerm"),
    _mapping("xiyou", "data.list[].abaReport.weeklySearchVolume", "keyword.search_volume", "normalize_compact_count", MappingConfidence.MEDIUM, "Weekly provider search-volume estimate with report period.", _XIYOU_KEYWORD, EntityType.KEYWORD, "weeklySearchVolume"),
    _mapping("xiyou", "data.list[].abaReport", "keyword.trend", "defer_trend_analysis", MappingConfidence.LOW, "A single dated report is retained as evidence; trend direction requires a governed series.", _XIYOU_KEYWORD, EntityType.KEYWORD, "abaReport"),
)


EXPLICITLY_UNAVAILABLE_FIELDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "xiyou": frozenset({"product.brand", "metric.estimated_monthly_sales"}),
        "sorftime": frozenset(
            {
                "metric.bsr",
                "metric.orders",
                "keyword.text",
                "keyword.search_volume",
                "keyword.trend",
            }
        ),
    }
)


def mappings_for(
    source: str,
    operation: str | None = None,
    entity_type: EntityType | None = None,
) -> tuple[CanonicalFieldMapping, ...]:
    return tuple(
        mapping
        for mapping in P0_FIELD_MAPPINGS
        if mapping.source == source
        and (operation is None or operation in mapping.operations)
        and (entity_type is None or mapping.entity_type is entity_type)
    )


__all__ = (
    "CanonicalEntity",
    "CanonicalFieldMapping",
    "CanonicalFieldStatus",
    "CanonicalFieldValue",
    "EntityType",
    "EXPLICITLY_UNAVAILABLE_FIELDS",
    "MappedEntity",
    "MappedField",
    "MappingConfidence",
    "P0_FIELD_MAPPINGS",
    "P0_KEYWORD_FIELDS",
    "P0_PRODUCT_FIELDS",
    "mappings_for",
)
