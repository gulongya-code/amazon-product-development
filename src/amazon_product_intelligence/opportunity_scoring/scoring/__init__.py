"""Configuration-driven opportunity scoring components V0.1."""

from .config_loader import (
    ConfigurationLoadError,
    ConfigurationLoader,
    ScoringConfigurationLoader,
)
from .config_validator import (
    SUPPORTED_CONFIGURATION_SCHEMA_VERSION,
    AggregationFormula,
    BusinessScoringConfiguration,
    ComparisonOperator,
    ConfigLifecycleStatus,
    ConfigurationAudit,
    ConfigurationValidationError,
    ConfigurationValidator,
    DimensionScoringConfiguration,
    MissingDataPolicy,
    RoundingMode,
    ScoreAggregationConfiguration,
    ScoreRuleConfiguration,
)
from .result_builder import (
    ConfigurationReference,
    DimensionScoreTrace,
    MetricRuleTrace,
    OpportunityScoreResult,
    OpportunityScoreResultBuilder,
    ScoreResultBuilder,
    ScoreStatus,
)
from .score_calculator import ScoreCalculationError, ScoreCalculator


__all__ = (
    "SUPPORTED_CONFIGURATION_SCHEMA_VERSION",
    "AggregationFormula",
    "BusinessScoringConfiguration",
    "ComparisonOperator",
    "ConfigLifecycleStatus",
    "ConfigurationAudit",
    "ConfigurationLoadError",
    "ConfigurationLoader",
    "ConfigurationReference",
    "ConfigurationValidationError",
    "ConfigurationValidator",
    "DimensionScoreTrace",
    "DimensionScoringConfiguration",
    "MetricRuleTrace",
    "MissingDataPolicy",
    "OpportunityScoreResult",
    "OpportunityScoreResultBuilder",
    "RoundingMode",
    "ScoreAggregationConfiguration",
    "ScoreCalculationError",
    "ScoreCalculator",
    "ScoreRuleConfiguration",
    "ScoreResultBuilder",
    "ScoreStatus",
    "ScoringConfigurationLoader",
)
