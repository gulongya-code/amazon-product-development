"""Shared P0 business normalization built on existing Canonical rules."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from amazon_product_intelligence.contracts import NormalizationStatus, Unit
from amazon_product_intelligence.schemas import (
    CanonicalEntity,
    CanonicalFieldStatus,
    CanonicalFieldValue,
    EntityType,
    MappedEntity,
    MappedField,
    MappingConfidence,
)

from .registry import RuleOutcome
from .rules import (
    normalize_asin,
    normalize_keyword,
    normalize_money,
    normalize_nonnegative_integer,
    normalize_rank,
    normalize_rating,
    normalize_text,
)


_COMPACT_NUMBER = re.compile(
    r"^(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(?P<suffix>[KkMm])?$"
)
_CONFIDENCE_ORDER = {
    MappingConfidence.LOW: 0,
    MappingConfidence.MEDIUM: 1,
    MappingConfidence.HIGH: 2,
}


def expand_compact_number(value: Any) -> Any:
    """Expand K/M count notation while leaving ordinary numeric values intact."""

    if not isinstance(value, str):
        return value
    candidate = value.strip().replace(",", "")
    match = _COMPACT_NUMBER.fullmatch(candidate)
    if match is None:
        return value
    try:
        number = Decimal(match.group("number"))
    except InvalidOperation:
        return value
    multiplier = {None: Decimal(1), "k": Decimal(1000), "m": Decimal(1_000_000)}[
        match.group("suffix").casefold() if match.group("suffix") else None
    ]
    expanded = number * multiplier
    return int(expanded) if expanded == expanded.to_integral_value() else expanded


def normalize_iso8601(value: Any) -> str:
    """Return an ISO-8601 date/datetime without silently adding a timezone."""

    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if not isinstance(value, str) or not value.strip():
        raise ValueError("date value must be non-empty text")
    text = value.strip()
    if re.fullmatch(r"\d{8}", text):
        return datetime.strptime(text, "%Y%m%d").date().isoformat()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return date.fromisoformat(text).isoformat()
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    parsed = datetime.fromisoformat(candidate)
    return parsed.isoformat().replace("+00:00", "Z")


def _currency_unit(currency: str | None) -> Unit | None:
    if currency is None:
        return None
    return Unit(dimension="CURRENCY", unit_code=currency, unit_system="ISO_4217")


def _issues(outcome: RuleOutcome) -> tuple[str, ...]:
    return tuple(issue.code.value for issue in outcome.issues)


def _numeric_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    return value


def _apply_rule(field: MappedField) -> tuple[Any, str | None, tuple[str, ...], CanonicalFieldStatus]:
    mapping = field.mapping
    if mapping is None:
        raise ValueError("present mapped field requires a mapping")
    raw_value = field.raw_value
    unit: Unit | None = None
    if mapping.transform_rule == "normalize_asin":
        outcome = normalize_asin(raw_value, None)
    elif mapping.transform_rule == "normalize_text":
        outcome = normalize_text(raw_value, None)
    elif mapping.transform_rule == "normalize_keyword":
        outcome = normalize_keyword(raw_value, None)
    elif mapping.transform_rule == "normalize_price":
        unit = _currency_unit(field.currency)
        outcome = normalize_money(raw_value, unit)
    elif mapping.transform_rule in {"normalize_compact_count", "normalize_monthly_sales"}:
        outcome = normalize_nonnegative_integer(expand_compact_number(raw_value), None)
    elif mapping.transform_rule == "normalize_rating":
        outcome = normalize_rating(raw_value, None)
    elif mapping.transform_rule == "normalize_rank":
        outcome = normalize_rank(raw_value, None)
    else:
        raise ValueError(f"unsupported business transform rule {mapping.transform_rule!r}")

    if outcome.normalization_status is NormalizationStatus.FAILED:
        status = CanonicalFieldStatus.PENDING
    elif outcome.normalization_status is NormalizationStatus.AMBIGUOUS:
        status = CanonicalFieldStatus.PENDING
    else:
        status = CanonicalFieldStatus.PRESENT
    currency = outcome.unit.unit_code if outcome.unit is not None else field.currency
    return _numeric_value(outcome.normalized_value), currency, _issues(outcome), status


class BusinessNormalizer:
    """Normalize mapped fields while preserving source quality metadata."""

    entity_type: EntityType

    def normalize(self, entity: MappedEntity) -> CanonicalEntity:
        if entity.entity_type is not self.entity_type:
            raise ValueError(
                f"{type(self).__name__} cannot normalize {entity.entity_type.value} entities"
            )
        normalized: dict[str, CanonicalFieldValue] = {}
        for canonical_field, field in entity.fields.items():
            normalized[canonical_field] = self._normalize_field(entity, field)
        identity_field = "product.asin" if self.entity_type is EntityType.PRODUCT else "keyword.text"
        identity_value = normalized[identity_field]
        identity = str(identity_value.value) if identity_value.status is CanonicalFieldStatus.PRESENT else None
        return CanonicalEntity(
            entity_type=self.entity_type,
            identity=identity,
            fields=normalized,
        )

    @staticmethod
    def _normalize_field(entity: MappedEntity, field: MappedField) -> CanonicalFieldValue:
        mapping = field.mapping
        confidence = mapping.confidence if mapping is not None else MappingConfidence.LOW
        source_field = mapping.source_field if mapping is not None else None
        transform_rule = mapping.transform_rule if mapping is not None else None
        quality: tuple[str, ...] = ()
        value = None
        currency = field.currency
        observed_at = field.observed_at
        status = field.status

        if status is CanonicalFieldStatus.PRESENT:
            value, currency, quality, status = _apply_rule(field)
        elif status is CanonicalFieldStatus.NOT_AVAILABLE:
            quality = ("SOURCE_FIELD_NOT_AVAILABLE",)
        elif status is CanonicalFieldStatus.UNKNOWN:
            quality = ("SOURCE_VALUE_UNKNOWN",)
        elif status is CanonicalFieldStatus.PENDING:
            quality = ("AWAITING_ADDITIONAL_INPUT",)
        if observed_at is not None:
            try:
                observed_at = normalize_iso8601(observed_at)
            except ValueError:
                quality += ("INVALID_OBSERVED_AT",)
                observed_at = None

        return CanonicalFieldValue(
            value=value,
            source=entity.source,
            snapshot_id=entity.snapshot_id,
            timestamp=normalize_iso8601(entity.timestamp),
            confidence=confidence,
            status=status,
            currency=currency,
            observed_at=observed_at,
            source_field=source_field,
            transform_rule=transform_rule,
            quality=quality,
        )


def merge_canonical_entities(*entities: CanonicalEntity) -> CanonicalEntity:
    """Merge one identity and mark differing present source values as CONFLICT."""

    if not entities:
        raise ValueError("at least one Canonical entity is required")
    entity_type = entities[0].entity_type
    identities = {entity.identity for entity in entities if entity.identity is not None}
    if any(entity.entity_type is not entity_type for entity in entities) or len(identities) > 1:
        raise ValueError("Canonical entities must describe one entity type and identity")
    field_names = tuple(dict.fromkeys(key for entity in entities for key in entity.fields))
    merged: dict[str, CanonicalFieldValue] = {}
    for field_name in field_names:
        candidates = [entity.fields[field_name] for entity in entities if field_name in entity.fields]
        present = [item for item in candidates if item.status is CanonicalFieldStatus.PRESENT]
        distinct = {repr(item.value) for item in present}
        if len(distinct) > 1:
            ordered = sorted(present, key=lambda item: (item.source, item.snapshot_id))
            merged[field_name] = CanonicalFieldValue(
                value=None,
                source="|".join(dict.fromkeys(item.source for item in ordered)),
                snapshot_id="|".join(dict.fromkeys(item.snapshot_id for item in ordered)),
                timestamp=max(item.timestamp for item in ordered),
                confidence=MappingConfidence.LOW,
                status=CanonicalFieldStatus.CONFLICT,
                transform_rule="detect_source_conflict",
                quality=tuple(
                    f"CONFLICT:{item.source}:{item.snapshot_id}:{item.value!r}" for item in ordered
                ),
            )
        elif present:
            merged[field_name] = max(
                present,
                key=lambda item: (_CONFIDENCE_ORDER[item.confidence], item.timestamp),
            )
        else:
            status_order = {
                CanonicalFieldStatus.CONFLICT: 4,
                CanonicalFieldStatus.PENDING: 3,
                CanonicalFieldStatus.UNKNOWN: 2,
                CanonicalFieldStatus.NOT_AVAILABLE: 1,
            }
            merged[field_name] = max(candidates, key=lambda item: status_order[item.status])
    return CanonicalEntity(
        entity_type=entity_type,
        identity=next(iter(identities), None),
        fields=merged,
    )


__all__ = (
    "BusinessNormalizer",
    "expand_compact_number",
    "merge_canonical_entities",
    "normalize_iso8601",
)
