"""Compact, versioned Buyer Need taxonomy registry V0.1."""

from __future__ import annotations

from amazon_product_intelligence.contracts import deterministic_id

from .models import (
    BUYER_NEED_TAXONOMY_VERSION,
    BuyerNeedEvidenceRequirement,
    BuyerNeedLabelStrategy,
    BuyerNeedMatchStrength,
    BuyerNeedTaxonomyEntry,
    BuyerNeedTaxonomyRegistry,
    BuyerNeedTextSourceType,
    BuyerNeedType,
)


_ALL_TEXT_SOURCES = tuple(BuyerNeedTextSourceType)
_BUYER_EXPRESSION_SOURCES = (
    BuyerNeedTextSourceType.SEARCH_TERM,
    BuyerNeedTextSourceType.REVIEW,
)


def _entry(
    *,
    need_type: BuyerNeedType,
    canonical_label: str,
    definition: str,
    patterns: tuple[str, ...],
    sources: tuple[BuyerNeedTextSourceType, ...] = _ALL_TEXT_SOURCES,
    strength: BuyerNeedMatchStrength = BuyerNeedMatchStrength.EXPLICIT,
    label_strategy: BuyerNeedLabelStrategy = BuyerNeedLabelStrategy.CANONICAL,
) -> BuyerNeedTaxonomyEntry:
    normalized_patterns = tuple(sorted(patterns))
    normalized_sources = tuple(sorted(sources, key=lambda item: item.value))
    payload = {
        "need_type": need_type,
        "canonical_label": canonical_label,
        "definition": definition,
        "regex_patterns": normalized_patterns,
        "applicable_source_types": normalized_sources,
        "match_strength": strength,
        "label_strategy": label_strategy,
        "evidence_requirement": BuyerNeedEvidenceRequirement.EXPLICIT_TEXT_SPAN,
    }
    return BuyerNeedTaxonomyEntry(
        taxonomy_need_id=deterministic_id("buyer-need-taxonomy-entry", payload),
        **payload,
    )


def build_buyer_need_taxonomy_v0_1() -> BuyerNeedTaxonomyRegistry:
    """Build a deliberately small registry; future versions can add entries without builder changes."""

    entries = (
        _entry(
            need_type=BuyerNeedType.USE_CASE,
            canonical_label="outdoor hiking",
            definition="The product is intended for hiking or a hiking-related outdoor scenario.",
            patterns=(r"\bhik(?:e|es|ed|ing)\b",),
        ),
        _entry(
            need_type=BuyerNeedType.USE_CASE,
            canonical_label="travel",
            definition="The product is intended for travel.",
            patterns=(r"\btravel(?:s|ed|ing|led|ling)?\b",),
        ),
        _entry(
            need_type=BuyerNeedType.USE_CASE,
            canonical_label="walking",
            definition="The product is intended for walking.",
            patterns=(r"\bwalk(?:s|ed|ing)?\b",),
        ),
        _entry(
            need_type=BuyerNeedType.AUDIENCE,
            canonical_label="large dogs",
            definition="The intended user group includes large dogs.",
            patterns=(r"\b(?:for\s+)?large\s+dogs?\b",),
        ),
        _entry(
            need_type=BuyerNeedType.AUDIENCE,
            canonical_label="small dogs",
            definition="The intended user group includes small dogs.",
            patterns=(r"\b(?:for\s+)?small\s+dogs?\b",),
        ),
        _entry(
            need_type=BuyerNeedType.AUDIENCE,
            canonical_label="kids",
            definition="The intended user group includes children.",
            patterns=(r"\b(?:for\s+)?(?:kids?|children)\b",),
        ),
        _entry(
            need_type=BuyerNeedType.PROBLEM_SOLUTION,
            canonical_label="prevent leaking",
            definition="The product is expected to prevent leaking.",
            patterns=(
                r"\bdoes(?:n['’]?t|\s+not)\s+leak\b",
                r"\bleak[ -]?proof\b",
                r"\b(?:prevent|stop|avoid)(?:s|ed|ing)?\s+(?:leaks?|leaking)\b",
            ),
        ),
        _entry(
            need_type=BuyerNeedType.PROBLEM_SOLUTION,
            canonical_label="easy cleaning",
            definition="The product is expected to reduce cleaning effort.",
            patterns=(r"\beasy(?:\s+to)?\s+clean(?:ing)?\b",),
        ),
        _entry(
            need_type=BuyerNeedType.PROBLEM_SOLUTION,
            canonical_label="avoid spills",
            definition="The product is expected to prevent or reduce spills.",
            patterns=(
                r"\b(?:avoid|prevent|stop)(?:s|ed|ing)?\s+spills?\b",
                r"\bspill[ -]?proof\b",
            ),
        ),
        _entry(
            need_type=BuyerNeedType.ATTRIBUTE_NEED,
            canonical_label="large capacity",
            definition="The buyer explicitly needs a larger carrying capacity.",
            patterns=(r"\b(?:large|high)\s+capacity\b",),
        ),
        _entry(
            need_type=BuyerNeedType.ATTRIBUTE_NEED,
            canonical_label="portable",
            definition="The buyer explicitly needs a product that is portable.",
            patterns=(r"\bportable\b",),
        ),
        _entry(
            need_type=BuyerNeedType.ATTRIBUTE_NEED,
            canonical_label="easy to carry",
            definition="The buyer explicitly needs a product that is easy to carry.",
            patterns=(r"\beasy\s+to\s+carry\b",),
        ),
        _entry(
            need_type=BuyerNeedType.ATTRIBUTE_NEED,
            canonical_label="fits in backpack",
            definition="The buyer explicitly needs a product that fits in a backpack.",
            patterns=(r"\bfits?\s+in\s+(?:a\s+)?backpack\b",),
        ),
        _entry(
            need_type=BuyerNeedType.ATTRIBUTE_NEED,
            canonical_label="lightweight",
            definition="The buyer explicitly needs low product weight.",
            patterns=(r"\blight[ -]?weight\b",),
        ),
        _entry(
            need_type=BuyerNeedType.ATTRIBUTE_NEED,
            canonical_label="durable",
            definition="The buyer explicitly needs durability or long service life.",
            patterns=(r"\bdurab(?:le|ility)\b",),
        ),
        _entry(
            need_type=BuyerNeedType.SPECIFICATION_PREFERENCE,
            canonical_label="quantity specification preference",
            definition=(
                "An explicit measurable size or capacity specification candidate; this remains a "
                "preference candidate rather than a general Buyer Need."
            ),
            patterns=(
                r"(?<![a-z0-9])\d+(?:\.\d+)?\s?(?:fl\s?oz|oz|ml|l|liters?|inches?|cm|mm)(?![a-z0-9])",
            ),
            label_strategy=BuyerNeedLabelStrategy.MATCH_NORMALIZED,
        ),
        _entry(
            need_type=BuyerNeedType.SPECIFICATION_PREFERENCE,
            canonical_label="stainless steel",
            definition=(
                "A stainless-steel specification explicitly expressed by a buyer; listing material "
                "alone is supply evidence and is intentionally excluded."
            ),
            patterns=(r"\bstainless[ -]+steel\b",),
            sources=_BUYER_EXPRESSION_SOURCES,
            strength=BuyerNeedMatchStrength.WEAK,
        ),
        _entry(
            need_type=BuyerNeedType.SPECIFICATION_PREFERENCE,
            canonical_label="compact size",
            definition="The buyer explicitly prefers a compact size.",
            patterns=(r"\bcompact\s+size\b",),
            sources=_BUYER_EXPRESSION_SOURCES,
        ),
        _entry(
            need_type=BuyerNeedType.COMPATIBILITY,
            canonical_label="compatibility requirement",
            definition="The product must work with an explicitly named model or device.",
            patterns=(
                r"\bcompatible\s+with\s+[a-z0-9][a-z0-9 -]{1,40}",
                r"\bworks?\s+with\s+[a-z0-9][a-z0-9 -]{1,40}",
                r"\bfits?\s+(?:the\s+)?[a-z0-9][a-z0-9 -]{1,40}",
            ),
            label_strategy=BuyerNeedLabelStrategy.MATCH_NORMALIZED,
        ),
    )
    ordered_entries = tuple(sorted(entries, key=lambda item: item.taxonomy_need_id))
    payload = {
        "taxonomy_version": BUYER_NEED_TAXONOMY_VERSION,
        "entries": ordered_entries,
    }
    return BuyerNeedTaxonomyRegistry(
        registry_id=deterministic_id("buyer-need-taxonomy", payload),
        **payload,
    )


BUYER_NEED_TAXONOMY_V0_1 = build_buyer_need_taxonomy_v0_1()


__all__ = (
    "BUYER_NEED_TAXONOMY_V0_1",
    "build_buyer_need_taxonomy_v0_1",
)
