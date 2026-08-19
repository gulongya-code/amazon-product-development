"""Product-focused business normalization facade."""

from __future__ import annotations

from typing import Any

from amazon_product_intelligence.contracts import NormalizationStatus
from amazon_product_intelligence.schemas import EntityType

from .business_base import BusinessNormalizer, expand_compact_number
from .rules import normalize_money, normalize_nonnegative_integer, normalize_text


def normalize_price(value: Any, *, currency: str | None = None) -> float | int:
    unit = None
    if currency is not None:
        from amazon_product_intelligence.contracts import Unit

        unit = Unit(
            dimension="CURRENCY",
            unit_code=currency.strip().upper(),
            unit_system="ISO_4217",
        )
    outcome = normalize_money(value, unit)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        raise ValueError("price cannot be normalized")
    normalized = outcome.normalized_value
    return int(normalized) if normalized == normalized.to_integral_value() else float(normalized)


def normalize_review_count(value: Any) -> int:
    outcome = normalize_nonnegative_integer(expand_compact_number(value), None)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        raise ValueError("review count cannot be normalized")
    return int(outcome.normalized_value)


def normalize_monthly_sales(value: Any) -> int:
    outcome = normalize_nonnegative_integer(expand_compact_number(value), None)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        raise ValueError("monthly sales cannot be normalized")
    return int(outcome.normalized_value)


def normalize_product_text(value: Any) -> str:
    outcome = normalize_text(value, None)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        raise ValueError("product text cannot be normalized")
    return str(outcome.normalized_value)


class ProductNormalizer(BusinessNormalizer):
    entity_type = EntityType.PRODUCT


__all__ = (
    "ProductNormalizer",
    "normalize_monthly_sales",
    "normalize_price",
    "normalize_product_text",
    "normalize_review_count",
)
