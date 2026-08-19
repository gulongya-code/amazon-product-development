"""Public Canonical normalization and cleaning surface V0.1."""

from .models import (
    NORMALIZATION_RULESET_VERSION,
    NormalizationContext,
    NormalizationInput,
    NormalizationIssueCode,
    NormalizationResult,
    NormalizationRuleApplication,
)
from .pipeline import CanonicalNormalizationPipeline
from .registry import NormalizationRule, NormalizerRegistry, RuleOutcome
from .rules import build_default_registry


__all__ = (
    "NORMALIZATION_RULESET_VERSION",
    "CanonicalNormalizationPipeline",
    "NormalizationContext",
    "NormalizationInput",
    "NormalizationIssueCode",
    "NormalizationResult",
    "NormalizationRule",
    "NormalizationRuleApplication",
    "NormalizerRegistry",
    "RuleOutcome",
    "build_default_registry",
)
