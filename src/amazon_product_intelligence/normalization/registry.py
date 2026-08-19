"""Small schema-driven registry for Canonical normalization rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from amazon_product_intelligence.contracts import NormalizationStatus, SemanticStatus, Severity, Unit

from .models import NormalizationIssueCode


@dataclass(frozen=True, slots=True, kw_only=True)
class IssueSpec:
    code: NormalizationIssueCode
    severity: Severity
    message: str
    blocking: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.code, NormalizationIssueCode):
            raise TypeError("issue code must be NormalizationIssueCode")
        if not isinstance(self.severity, Severity):
            raise TypeError("issue severity must be Canonical Severity")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("issue message must be non-empty text")
        if not isinstance(self.blocking, bool):
            raise TypeError("issue blocking must be bool")


@dataclass(frozen=True, slots=True, kw_only=True)
class RuleOutcome:
    normalized_value: Any
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    unit: Unit | None
    transformations: tuple[str, ...]
    issues: tuple[IssueSpec, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "transformations", tuple(self.transformations))
        object.__setattr__(self, "issues", tuple(self.issues))
        if not isinstance(self.normalization_status, NormalizationStatus):
            raise TypeError("normalization_status must be Canonical NormalizationStatus")
        if not isinstance(self.semantic_status, SemanticStatus):
            raise TypeError("semantic_status must be Canonical SemanticStatus")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise TypeError("unit must be Canonical Unit or None")
        if any(not isinstance(item, str) or not item.strip() for item in self.transformations):
            raise ValueError("transformations must contain non-empty text")
        if any(not isinstance(item, IssueSpec) for item in self.issues):
            raise TypeError("issues must contain IssueSpec values")


Normalizer = Callable[[Any, Unit | None], RuleOutcome]


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizationRule:
    rule_id: str
    rule_version: str
    canonical_fields: tuple[str, ...]
    normalize: Normalizer

    def __post_init__(self) -> None:
        object.__setattr__(self, "canonical_fields", tuple(self.canonical_fields))
        if not self.rule_id.strip() or not self.rule_version.strip():
            raise ValueError("rule identity and version must be non-empty")
        if not self.canonical_fields or any(not field.strip() for field in self.canonical_fields):
            raise ValueError("rule must declare Canonical fields")
        if len(set(self.canonical_fields)) != len(self.canonical_fields):
            raise ValueError("rule Canonical fields must be unique")
        if not callable(self.normalize):
            raise TypeError("normalize must be callable")


class NormalizerRegistry:
    """One immutable-by-convention rule lookup built once per pipeline."""

    def __init__(self) -> None:
        self._rules: dict[str, NormalizationRule] = {}

    def register(self, rule: NormalizationRule) -> None:
        collisions = set(rule.canonical_fields) & self._rules.keys()
        if collisions:
            raise ValueError(f"normalization rule already registered for {sorted(collisions)!r}")
        for canonical_field in rule.canonical_fields:
            self._rules[canonical_field] = rule

    def get(self, canonical_field: str) -> NormalizationRule | None:
        return self._rules.get(canonical_field)

    @property
    def fields(self) -> tuple[str, ...]:
        return tuple(sorted(self._rules))


__all__ = ("IssueSpec", "NormalizationRule", "NormalizerRegistry", "RuleOutcome")
