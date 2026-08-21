"""Versioned, explainable semantic normalization rules V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
from typing import Any

from amazon_product_intelligence.contracts import JsonContract, deterministic_id
from amazon_product_intelligence.normalization import normalize_keyword_text

from .errors import SemanticClusteringValidationError


SEMANTIC_NORMALIZATION_RULE_VERSION = "semantic-normalization-rules-v0.1"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise SemanticClusteringValidationError(f"{path} must be non-empty text")
    return value


def normalize_for_similarity(value: str) -> str:
    """Apply canonical text cleanup plus explainable punctuation/spacing cleanup."""

    normalized = normalize_keyword_text(value)
    tokens = re.sub(r"[^a-z0-9]+", " ", normalized).split()
    return " ".join(tokens)


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticNormalizationRule(JsonContract):
    rule_id: str
    canonical_key: str
    cluster_label: str
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.canonical_key, "SemanticNormalizationRule.canonical_key")
        _text(self.cluster_label, "SemanticNormalizationRule.cluster_label")
        if normalize_for_similarity(self.canonical_key) != self.canonical_key:
            raise SemanticClusteringValidationError(
                "normalization canonical_key must already be normalized"
            )
        if isinstance(self.aliases, (str, bytes)) or not isinstance(self.aliases, Sequence):
            raise SemanticClusteringValidationError("normalization aliases must be a sequence")
        aliases = tuple(self.aliases)
        if not aliases or any(type(item) is not str or not item.strip() for item in aliases):
            raise SemanticClusteringValidationError("normalization rule requires aliases")
        normalized_aliases = tuple(sorted({normalize_for_similarity(item) for item in aliases}))
        if len(normalized_aliases) != len(aliases):
            raise SemanticClusteringValidationError(
                "normalization aliases must remain unique after text normalization"
            )
        object.__setattr__(self, "aliases", normalized_aliases)
        payload = self.to_dict()
        payload.pop("rule_id")
        if self.rule_id != deterministic_id("semantic-normalization-rule", payload):
            raise SemanticClusteringValidationError(
                "normalization rule_id does not match rule content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticNormalizationResult(JsonContract):
    normalized_text: str
    canonical_key: str
    cluster_label: str | None
    rule_id: str | None

    def __post_init__(self) -> None:
        _text(self.normalized_text, "SemanticNormalizationResult.normalized_text")
        _text(self.canonical_key, "SemanticNormalizationResult.canonical_key")
        if self.cluster_label is not None:
            _text(self.cluster_label, "SemanticNormalizationResult.cluster_label")
        if self.rule_id is not None:
            _text(self.rule_id, "SemanticNormalizationResult.rule_id")
        if (self.cluster_label is None) != (self.rule_id is None):
            raise SemanticClusteringValidationError(
                "normalization cluster_label and rule_id must be known together"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticNormalizationRegistry(JsonContract):
    registry_id: str
    ruleset_version: str
    rules: tuple[SemanticNormalizationRule, ...]

    def __post_init__(self) -> None:
        _text(self.ruleset_version, "SemanticNormalizationRegistry.ruleset_version")
        if isinstance(self.rules, (str, bytes)) or not isinstance(self.rules, Sequence):
            raise SemanticClusteringValidationError("normalization rules must be a sequence")
        rules = tuple(self.rules)
        if not rules or any(not isinstance(item, SemanticNormalizationRule) for item in rules):
            raise SemanticClusteringValidationError("normalization registry requires rules")
        if len({item.rule_id for item in rules}) != len(rules):
            raise SemanticClusteringValidationError("normalization rule ids must be unique")
        aliases = [alias for item in rules for alias in item.aliases]
        if len(set(aliases)) != len(aliases):
            raise SemanticClusteringValidationError(
                "an alias cannot resolve to multiple normalization rules"
            )
        object.__setattr__(self, "rules", tuple(sorted(rules, key=lambda item: item.rule_id)))
        payload = self.to_dict()
        payload.pop("registry_id")
        if self.registry_id != deterministic_id("semantic-normalization-registry", payload):
            raise SemanticClusteringValidationError(
                "normalization registry_id does not match registry content"
            )

    def normalize(self, value: str) -> SemanticNormalizationResult:
        normalized = normalize_for_similarity(value)
        for rule in self.rules:
            if normalized in rule.aliases:
                return SemanticNormalizationResult(
                    normalized_text=normalized,
                    canonical_key=rule.canonical_key,
                    cluster_label=rule.cluster_label,
                    rule_id=rule.rule_id,
                )
        return SemanticNormalizationResult(
            normalized_text=normalized,
            canonical_key=normalized,
            cluster_label=None,
            rule_id=None,
        )


def _rule(
    canonical_key: str,
    cluster_label: str,
    aliases: tuple[str, ...],
) -> SemanticNormalizationRule:
    normalized_aliases = tuple(sorted(normalize_for_similarity(item) for item in aliases))
    payload = {
        "canonical_key": normalize_for_similarity(canonical_key),
        "cluster_label": cluster_label,
        "aliases": normalized_aliases,
    }
    return SemanticNormalizationRule(
        rule_id=deterministic_id("semantic-normalization-rule", payload),
        **payload,
    )


def build_semantic_normalization_registry_v0_1() -> SemanticNormalizationRegistry:
    rules = (
        _rule(
            "outdoor portability",
            "Outdoor Portability",
            (
                "portable",
                "easy to carry",
                "easy carry",
                "fits in backpack",
                "fit in backpack",
                "outdoor hiking",
                "hiking",
                "travel",
            ),
        ),
        _rule(
            "leak prevention",
            "Leak Prevention",
            (
                "leakproof",
                "leak proof",
                "prevent leaking",
                "doesn't leak",
                "does not leak",
            ),
        ),
        _rule(
            "large capacity",
            "Large Capacity",
            ("large capacity", "high capacity"),
        ),
        _rule("easy cleaning", "Easy Cleaning", ("easy cleaning", "easy to clean")),
        _rule("spill prevention", "Spill Prevention", ("avoid spills", "spillproof", "spill proof")),
        _rule("lightweight", "Lightweight", ("lightweight", "light weight")),
        _rule("durability", "Durability", ("durable", "durability")),
    )
    ordered = tuple(sorted(rules, key=lambda item: item.rule_id))
    payload = {
        "ruleset_version": SEMANTIC_NORMALIZATION_RULE_VERSION,
        "rules": ordered,
    }
    return SemanticNormalizationRegistry(
        registry_id=deterministic_id("semantic-normalization-registry", payload),
        **payload,
    )


SEMANTIC_NORMALIZATION_REGISTRY_V0_1 = build_semantic_normalization_registry_v0_1()


__all__ = (
    "SEMANTIC_NORMALIZATION_REGISTRY_V0_1",
    "SEMANTIC_NORMALIZATION_RULE_VERSION",
    "SemanticNormalizationRegistry",
    "SemanticNormalizationResult",
    "SemanticNormalizationRule",
    "build_semantic_normalization_registry_v0_1",
    "normalize_for_similarity",
)
