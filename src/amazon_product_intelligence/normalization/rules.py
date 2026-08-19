"""Conservative, field-aware Canonical normalization rules."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
import unicodedata
from typing import Any

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    NormalizationStatus,
    SemanticStatus,
    Severity,
    Unit,
    product_id,
)

from .models import NormalizationIssueCode
from .registry import IssueSpec, NormalizationRule, NormalizerRegistry, RuleOutcome


RULE_VERSION = "0.1"
_MONEY = re.compile(
    r"^(?:(?P<prefix>USD|US\$|\$)\s*)?(?P<amount>[+-]?(?:\d+(?:\.\d*)?|\.\d+))(?:(?:\s*)(?P<suffix>USD))?$",
    re.IGNORECASE,
)
_RANK = re.compile(r"^#?\s*(\d[\d,]*)$")


def _success(value: Any, unit: Unit | None, *steps: str, issues: tuple[IssueSpec, ...] = ()) -> RuleOutcome:
    status = NormalizationStatus.AMBIGUOUS if issues and any(item.blocking for item in issues) else NormalizationStatus.NORMALIZED
    semantic = SemanticStatus.SEMANTICS_UNCONFIRMED if status is NormalizationStatus.AMBIGUOUS else SemanticStatus.CONFIRMED
    return RuleOutcome(
        normalized_value=value,
        normalization_status=status,
        semantic_status=semantic,
        unit=unit,
        transformations=tuple(steps),
        issues=issues,
    )


def _failure(code: NormalizationIssueCode, message: str, unit: Unit | None) -> RuleOutcome:
    return RuleOutcome(
        normalized_value=None,
        normalization_status=NormalizationStatus.FAILED,
        semantic_status=SemanticStatus.INVALID,
        unit=unit,
        transformations=(),
        issues=(IssueSpec(code=code, severity=Severity.MATERIAL, message=message),),
    )


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise InvalidOperation
    if isinstance(value, Decimal):
        candidate = value
    elif isinstance(value, int):
        candidate = Decimal(value)
    elif isinstance(value, float):
        candidate = Decimal(str(value))
    elif isinstance(value, str):
        text = value.strip().replace(",", "")
        if not text:
            raise InvalidOperation
        candidate = Decimal(text)
    else:
        raise InvalidOperation
    if not candidate.is_finite():
        raise InvalidOperation
    return candidate


def normalize_decimal(value: Any, unit: Unit | None) -> RuleOutcome:
    try:
        return _success(_decimal(value), unit, "parse_decimal")
    except (InvalidOperation, ValueError):
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "value is not a finite decimal", unit)


def normalize_nonnegative_integer(value: Any, unit: Unit | None) -> RuleOutcome:
    try:
        candidate = _decimal(value)
    except (InvalidOperation, ValueError):
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "value is not an integer", unit)
    integral = candidate.to_integral_value()
    if candidate != integral:
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "count must be an integer", unit)
    if integral < 0:
        return _failure(NormalizationIssueCode.OUT_OF_RANGE, "count cannot be negative", unit)
    return _success(int(integral), unit, "parse_nonnegative_integer")


def normalize_money(value: Any, unit: Unit | None) -> RuleOutcome:
    if unit is not None and unit.dimension != "CURRENCY":
        return _failure(
            NormalizationIssueCode.UNSUPPORTED_UNIT,
            "money normalization requires a CURRENCY unit when a unit is supplied",
            unit,
        )
    explicit_currency: str | None = None
    try:
        if isinstance(value, str):
            text = value.strip().replace(",", "")
            match = _MONEY.fullmatch(text)
            if match is None:
                raise InvalidOperation
            marker = (match.group("prefix") or match.group("suffix") or "").upper()
            explicit_currency = "USD" if marker in {"USD", "US$"} else None
            amount = Decimal(match.group("amount"))
            ambiguous_symbol = marker == "$"
        else:
            amount = _decimal(value)
            ambiguous_symbol = False
    except (InvalidOperation, ValueError):
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "money value has an unsupported format", unit)
    if amount < 0:
        return _failure(NormalizationIssueCode.OUT_OF_RANGE, "money value cannot be negative", unit)

    context_currency = unit.unit_code.upper() if unit is not None and unit.unit_code else None
    if explicit_currency and context_currency and explicit_currency != context_currency:
        issue = IssueSpec(
            code=NormalizationIssueCode.CURRENCY_CONFLICT,
            severity=Severity.MATERIAL,
            message="explicit currency conflicts with the Canonical unit",
        )
        return _success(amount, unit, "parse_money", issues=(issue,))
    currency = context_currency or explicit_currency
    output_unit = unit
    if output_unit is None and currency:
        output_unit = Unit(dimension="CURRENCY", unit_code=currency, unit_system="ISO_4217")
    if currency is None or (ambiguous_symbol and context_currency is None):
        issue = IssueSpec(
            code=NormalizationIssueCode.AMBIGUOUS_CURRENCY,
            severity=Severity.WARNING,
            message="amount parsed but currency cannot be established without trustworthy context",
        )
        return _success(amount, output_unit, "parse_money", issues=(issue,))
    return _success(amount, output_unit, "parse_money", "validate_currency")


def normalize_ratio(value: Any, unit: Unit | None) -> RuleOutcome:
    try:
        if isinstance(value, str) and value.strip().endswith("%"):
            candidate = _decimal(value.strip()[:-1]) / Decimal(100)
            step = "parse_explicit_percentage"
        else:
            candidate = _decimal(value)
            step = "parse_ratio"
    except (InvalidOperation, ValueError):
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "ratio has an unsupported format", unit)
    if candidate < 0 or candidate > 1:
        return _failure(
            NormalizationIssueCode.OUT_OF_RANGE,
            "ratio must be between 0 and 1; bare numbers are never divided by 100",
            unit,
        )
    return _success(candidate, unit, step, "validate_ratio_range")


def normalize_rank(value: Any, unit: Unit | None) -> RuleOutcome:
    if isinstance(value, bool):
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "rank must be an integer", unit)
    if isinstance(value, int):
        rank = value
    elif isinstance(value, Decimal) and value == value.to_integral_value():
        rank = int(value)
    elif isinstance(value, str):
        match = _RANK.fullmatch(value.strip())
        if match is None:
            return _failure(NormalizationIssueCode.INVALID_FORMAT, "rank has an unsupported format", unit)
        rank = int(match.group(1).replace(",", ""))
    else:
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "rank must be an integer", unit)
    if rank <= 0:
        return _failure(NormalizationIssueCode.OUT_OF_RANGE, "rank must be greater than zero", unit)
    return _success(rank, unit, "parse_positive_rank")


def normalize_rating(value: Any, unit: Unit | None) -> RuleOutcome:
    outcome = normalize_decimal(value, unit)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        return outcome
    if outcome.normalized_value < 0 or outcome.normalized_value > 5:
        return _failure(NormalizationIssueCode.OUT_OF_RANGE, "rating must be between 0 and 5", unit)
    return _success(outcome.normalized_value, unit, "parse_decimal", "validate_rating_range")


def normalize_boolean(value: Any, unit: Unit | None) -> RuleOutcome:
    if isinstance(value, bool):
        return _success(value, unit, "validate_boolean")
    if type(value) is int and value in {0, 1}:
        return _success(bool(value), unit, "parse_explicit_boolean")
    if isinstance(value, str):
        mapping = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False}
        normalized = value.strip().casefold()
        if normalized in mapping:
            return _success(mapping[normalized], unit, "parse_explicit_boolean")
    return _failure(NormalizationIssueCode.INVALID_FORMAT, "value is not an explicit boolean", unit)


def _clean_text(value: Any) -> tuple[str, bool]:
    if not isinstance(value, str):
        raise ValueError
    normalized = unicodedata.normalize("NFC", value)
    removed_control = any(unicodedata.category(char) == "Cc" for char in normalized)
    if removed_control:
        normalized = "".join(" " if unicodedata.category(char) == "Cc" else char for char in normalized)
    return " ".join(normalized.split()), removed_control


def normalize_text(value: Any, unit: Unit | None) -> RuleOutcome:
    try:
        normalized, removed_control = _clean_text(value)
    except ValueError:
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "text value must be a string", unit)
    if not normalized:
        return _failure(NormalizationIssueCode.EMPTY_VALUE, "text value is empty after conservative cleaning", unit)
    issues = ()
    if removed_control:
        issues = (
            IssueSpec(
                code=NormalizationIssueCode.CONTROL_CHARACTER_REMOVED,
                severity=Severity.WARNING,
                message="control characters were replaced with spaces",
                blocking=False,
            ),
        )
    return _success(normalized, unit, "unicode_nfc", "collapse_whitespace", issues=issues)


def normalize_keyword(value: Any, unit: Unit | None) -> RuleOutcome:
    outcome = normalize_text(value, unit)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        return outcome
    return _success(
        outcome.normalized_value.casefold(),
        unit,
        *outcome.transformations,
        "casefold_for_keyword_identity",
        issues=outcome.issues,
    )


def _normalized_asin(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError
    candidate = value.strip().upper()
    try:
        product_id("CANONICAL", candidate)
    except ContractValidationError as exc:
        raise ValueError from exc
    return candidate


def normalize_asin(value: Any, unit: Unit | None) -> RuleOutcome:
    try:
        candidate = _normalized_asin(value)
    except ValueError:
        return _failure(
            NormalizationIssueCode.INVALID_IDENTIFIER,
            "ASIN must be 10 alphanumeric characters",
            unit,
        )
    return _success(candidate, unit, "trim", "uppercase", "validate_canonical_asin")


def normalize_date(value: Any, unit: Unit | None) -> RuleOutcome:
    try:
        if isinstance(value, datetime):
            candidate = value.date()
        elif isinstance(value, date):
            candidate = value
        elif isinstance(value, str):
            candidate = date.fromisoformat(value.strip())
        else:
            raise ValueError
    except ValueError:
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "date must use ISO YYYY-MM-DD format", unit)
    return _success(candidate, unit, "parse_iso_date")


def normalize_datetime(value: Any, unit: Unit | None) -> RuleOutcome:
    try:
        if isinstance(value, datetime):
            candidate = value
        elif isinstance(value, str):
            text = value.strip()
            candidate = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        else:
            raise ValueError
    except ValueError:
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "datetime must use RFC 3339 format", unit)
    if candidate.tzinfo is None:
        return RuleOutcome(
            normalized_value=candidate,
            normalization_status=NormalizationStatus.AMBIGUOUS,
            semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
            unit=unit,
            transformations=("parse_iso_datetime",),
            issues=(
                IssueSpec(
                    code=NormalizationIssueCode.TIMEZONE_MISSING,
                    severity=Severity.MATERIAL,
                    message="datetime has no timezone; UTC was not assumed",
                ),
            ),
        )
    return _success(candidate, unit, "parse_rfc3339_datetime", "preserve_timezone")


def normalize_asin_collection(value: Any, unit: Unit | None) -> RuleOutcome:
    if not isinstance(value, (list, tuple)):
        return _failure(NormalizationIssueCode.INVALID_FORMAT, "ASIN collection must be a list", unit)
    valid: set[str] = set()
    invalid = 0
    duplicates = 0
    for member in value:
        try:
            candidate = _normalized_asin(member)
        except ValueError:
            invalid += 1
            continue
        if candidate in valid:
            duplicates += 1
        valid.add(candidate)
    issues: list[IssueSpec] = []
    if invalid:
        issues.append(
            IssueSpec(
                code=NormalizationIssueCode.INVALID_MEMBER,
                severity=Severity.MATERIAL,
                message=f"{invalid} invalid ASIN collection member(s) retained only in raw evidence",
            )
        )
    if duplicates:
        issues.append(
            IssueSpec(
                code=NormalizationIssueCode.DUPLICATE_MEMBER,
                severity=Severity.WARNING,
                message=f"{duplicates} duplicate ASIN collection member(s) removed by canonical identity",
                blocking=False,
            )
        )
    status = NormalizationStatus.AMBIGUOUS if invalid else NormalizationStatus.NORMALIZED
    semantic = SemanticStatus.SEMANTICS_UNCONFIRMED if invalid else SemanticStatus.CONFIRMED
    return RuleOutcome(
        normalized_value=tuple(sorted(valid)),
        normalization_status=status,
        semantic_status=semantic,
        unit=unit,
        transformations=("normalize_asin_members", "deduplicate_by_asin", "sort_by_asin"),
        issues=tuple(issues),
    )


def build_default_registry() -> NormalizerRegistry:
    registry = NormalizerRegistry()
    definitions = (
        NormalizationRule(
            rule_id="canonical.text",
            rule_version=RULE_VERSION,
            canonical_fields=(
                "product.title",
                "product.brand",
                "product.category",
                "product.fulfillment",
                "product.seller",
                "keyword.channel",
            ),
            normalize=normalize_text,
        ),
        NormalizationRule(
            rule_id="canonical.keyword",
            rule_version=RULE_VERSION,
            canonical_fields=("keyword.text",),
            normalize=normalize_keyword,
        ),
        NormalizationRule(
            rule_id="canonical.asin",
            rule_version=RULE_VERSION,
            canonical_fields=("product.asin", "product.parent_asin", "product.variation"),
            normalize=normalize_asin,
        ),
        NormalizationRule(
            rule_id="canonical.decimal",
            rule_version=RULE_VERSION,
            canonical_fields=("keyword.difficulty",),
            normalize=normalize_decimal,
        ),
        NormalizationRule(
            rule_id="canonical.nonnegative_integer",
            rule_version=RULE_VERSION,
            canonical_fields=(
                "metric.review_count",
                "metric.orders",
                "metric.estimated_monthly_sales",
                "metric.estimated_variation_sales",
                "keyword.search_volume",
                "product.child_count",
                "keyword.related_product_count",
            ),
            normalize=normalize_nonnegative_integer,
        ),
        NormalizationRule(
            rule_id="canonical.money",
            rule_version=RULE_VERSION,
            canonical_fields=("metric.price", "keyword.cpc"),
            normalize=normalize_money,
        ),
        NormalizationRule(
            rule_id="canonical.ratio",
            rule_version=RULE_VERSION,
            canonical_fields=("keyword.click_conversion_rate", "metric.traffic_ratio"),
            normalize=normalize_ratio,
        ),
        NormalizationRule(
            rule_id="canonical.rank",
            rule_version=RULE_VERSION,
            canonical_fields=("metric.bsr", "keyword.aba_rank", "relationship.rank"),
            normalize=normalize_rank,
        ),
        NormalizationRule(
            rule_id="canonical.rating",
            rule_version=RULE_VERSION,
            canonical_fields=("metric.rating",),
            normalize=normalize_rating,
        ),
        NormalizationRule(
            rule_id="canonical.boolean",
            rule_version=RULE_VERSION,
            canonical_fields=(
                "product.a_plus",
                "relationship.keyword_to_product",
                "relationship.product_to_keyword",
            ),
            normalize=normalize_boolean,
        ),
        NormalizationRule(
            rule_id="canonical.date",
            rule_version=RULE_VERSION,
            canonical_fields=("product.first_available_date",),
            normalize=normalize_date,
        ),
        NormalizationRule(
            rule_id="canonical.datetime",
            rule_version=RULE_VERSION,
            canonical_fields=("observation.observed_at",),
            normalize=normalize_datetime,
        ),
        NormalizationRule(
            rule_id="canonical.asin_collection",
            rule_version=RULE_VERSION,
            canonical_fields=("keyword.related_product_asins", "product.child_asins"),
            normalize=normalize_asin_collection,
        ),
    )
    for definition in definitions:
        registry.register(definition)
    return registry


__all__ = ("RULE_VERSION", "build_default_registry")
