"""Conservative field normalizers for SellerSprite export cells."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
    Unit,
)
from amazon_product_intelligence.normalization.rules import (
    normalize_asin,
    normalize_boolean,
    normalize_date,
    normalize_money,
    normalize_nonnegative_integer,
    normalize_rank,
    normalize_rating,
    normalize_text,
)

from .models import ImportValueStatus, NormalizedField
from .schema_v1 import FieldSpec


_NA_TOKENS = frozenset({"na", "n/a", "null", "none", "--", "-", "暂无", "无数据"})
_USD = Unit(dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217")


def _empty_field(spec: FieldSpec, status: ImportValueStatus) -> NormalizedField:
    presence = PresenceStatus.MISSING if status is ImportValueStatus.MISSING_HEADER else PresenceStatus.EXPLICIT_NULL
    if status is ImportValueStatus.NOT_AVAILABLE:
        presence = PresenceStatus.UNKNOWN
    return NormalizedField(
        header=spec.header,
        requirement=spec.requirement,
        value_type=spec.value_type,
        value=None,
        import_status=status,
        presence_status=presence,
        normalization_status=NormalizationStatus.NOT_ATTEMPTED,
        semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
        evidence_semantics=spec.evidence_semantics,
        issue_codes=(status.value,),
    )


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool):
        raise InvalidOperation
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, int):
        candidate = Decimal(value)
    elif isinstance(value, float):
        candidate = Decimal(str(value))
    elif isinstance(value, str):
        candidate = Decimal(value.strip().replace(",", ""))
    else:
        raise InvalidOperation
    if not candidate.is_finite():
        raise InvalidOperation
    return candidate


def _signed_integer(value: object) -> tuple[object | None, tuple[str, ...]]:
    try:
        candidate = _decimal(value)
    except (InvalidOperation, ValueError):
        return None, ("INVALID_FORMAT",)
    if candidate != candidate.to_integral_value():
        return None, ("INVALID_FORMAT",)
    return int(candidate), ()


def _percentage(value: object) -> tuple[object | None, tuple[str, ...]]:
    try:
        if isinstance(value, str) and value.strip().endswith("%"):
            candidate = _decimal(value.strip()[:-1]) / Decimal(100)
        else:
            candidate = _decimal(value)
    except (InvalidOperation, ValueError):
        return None, ("INVALID_FORMAT",)
    return candidate, ()


def _url(value: object) -> tuple[object | None, tuple[str, ...]]:
    outcome = normalize_text(value if isinstance(value, str) else str(value), None)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        return None, tuple(issue.code.value for issue in outcome.issues)
    parsed = urlsplit(outcome.normalized_value)
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        return None, ("INVALID_URL",)
    return outcome.normalized_value, ()


def _explicit_boolean(value: object) -> tuple[object | None, tuple[str, ...]]:
    if isinstance(value, str):
        translated = {"是": "true", "否": "false", "有": "true", "无": "false"}.get(value.strip(), value)
    else:
        translated = value
    outcome = normalize_boolean(translated, None)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        return None, tuple(issue.code.value for issue in outcome.issues)
    return outcome.normalized_value, ()


def normalize_field(spec: FieldSpec, value: object, *, header_present: bool) -> NormalizedField:
    if not header_present:
        return _empty_field(spec, ImportValueStatus.MISSING_HEADER)
    if value is None or (isinstance(value, str) and not value.strip()):
        return _empty_field(spec, ImportValueStatus.BLANK)
    if isinstance(value, str) and value.strip().casefold() in _NA_TOKENS:
        return _empty_field(spec, ImportValueStatus.NOT_AVAILABLE)

    issue_codes: tuple[str, ...]
    normalized: object | None
    if spec.value_type == "SIGNED_INTEGER":
        normalized, issue_codes = _signed_integer(value)
    elif spec.value_type == "PERCENTAGE":
        normalized, issue_codes = _percentage(value)
    elif spec.value_type == "URL":
        normalized, issue_codes = _url(value)
    elif spec.value_type == "BOOLEAN":
        normalized, issue_codes = _explicit_boolean(value)
    else:
        rule = {
            "ASIN": normalize_asin,
            "RANK": normalize_rank,
            "NONNEGATIVE_INTEGER": normalize_nonnegative_integer,
            "MONEY_USD": normalize_money,
            "RATING": normalize_rating,
            "DATE": normalize_date,
            "TEXT": normalize_text,
        }[spec.value_type]
        mapped_value = value
        if spec.value_type == "TEXT" and not isinstance(value, str):
            mapped_value = str(value)
        outcome = rule(mapped_value, _USD if spec.value_type == "MONEY_USD" else None)
        normalized = outcome.normalized_value
        issue_codes = tuple(issue.code.value for issue in outcome.issues)
        if outcome.normalization_status is not NormalizationStatus.FAILED:
            return NormalizedField(
                header=spec.header,
                requirement=spec.requirement,
                value_type=spec.value_type,
                value=normalized,
                import_status=ImportValueStatus.NORMALIZED,
                presence_status=PresenceStatus.PRESENT,
                normalization_status=outcome.normalization_status,
                semantic_status=outcome.semantic_status,
                evidence_semantics=spec.evidence_semantics,
                issue_codes=issue_codes,
            )

    failed = normalized is None
    return NormalizedField(
        header=spec.header,
        requirement=spec.requirement,
        value_type=spec.value_type,
        value=normalized,
        import_status=ImportValueStatus.PARSE_FAILED if failed else ImportValueStatus.NORMALIZED,
        presence_status=PresenceStatus.PRESENT,
        normalization_status=NormalizationStatus.FAILED if failed else NormalizationStatus.NORMALIZED,
        semantic_status=SemanticStatus.INVALID if failed else SemanticStatus.CONFIRMED,
        evidence_semantics=spec.evidence_semantics,
        issue_codes=issue_codes,
    )


__all__ = ("normalize_field",)
