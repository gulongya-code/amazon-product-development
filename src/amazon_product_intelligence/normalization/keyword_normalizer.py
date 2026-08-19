"""Keyword-focused business normalization facade."""

from __future__ import annotations

from typing import Any

from amazon_product_intelligence.contracts import NormalizationStatus
from amazon_product_intelligence.schemas import EntityType

from .business_base import BusinessNormalizer, expand_compact_number
from .rules import normalize_keyword, normalize_nonnegative_integer


def normalize_keyword_text(value: Any) -> str:
    outcome = normalize_keyword(value, None)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        raise ValueError("keyword cannot be normalized")
    return str(outcome.normalized_value)


def normalize_search_volume(value: Any) -> int:
    outcome = normalize_nonnegative_integer(expand_compact_number(value), None)
    if outcome.normalization_status is NormalizationStatus.FAILED:
        raise ValueError("search volume cannot be normalized")
    return int(outcome.normalized_value)


class KeywordNormalizer(BusinessNormalizer):
    entity_type = EntityType.KEYWORD


__all__ = ("KeywordNormalizer", "normalize_keyword_text", "normalize_search_volume")
