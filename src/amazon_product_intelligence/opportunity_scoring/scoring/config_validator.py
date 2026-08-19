"""Contracts and validation for explicit business scoring configuration."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math
from types import MappingProxyType
from typing import Any, Mapping

from amazon_product_intelligence.contracts import JsonContract, canonical_json

from ..engine_contracts import (
    BUSINESS_DECISION_REQUIRED,
    OpportunityDimension,
    ScoringState,
)
from ..evaluators import (
    CompetitionAccessibilityEvaluator,
    DemandPotentialEvaluator,
    EconomicsReadinessEvaluator,
)


SUPPORTED_CONFIGURATION_SCHEMA_VERSION = (
    "business-scoring-configuration-schema-v0.1"
)


class ConfigLifecycleStatus(StrEnum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    RETIRED = "RETIRED"


class ComparisonOperator(StrEnum):
    GREATER_THAN = "GT"
    GREATER_THAN_OR_EQUAL = "GTE"
    LESS_THAN = "LT"
    LESS_THAN_OR_EQUAL = "LTE"
    EQUAL = "EQ"


class MissingDataPolicy(StrEnum):
    BLOCK = "BLOCK"
    SKIP_RENORMALIZE = "SKIP_RENORMALIZE"


class AggregationFormula(StrEnum):
    WEIGHTED_AVERAGE = "WEIGHTED_AVERAGE"


class RoundingMode(StrEnum):
    HALF_UP = "HALF_UP"
    HALF_EVEN = "HALF_EVEN"
    DOWN = "DOWN"


class ConfigurationValidationError(ValueError):
    """Raised when a configuration cannot be used for calculation."""


def _text(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationValidationError(f"{path} must be non-empty text")
    return value


def _finite_number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationValidationError(f"{path} must be a finite number")
    resolved = float(value)
    if not math.isfinite(resolved):
        raise ConfigurationValidationError(f"{path} must be a finite number")
    return resolved


def _timestamp(value: str, path: str) -> str:
    _text(value, path)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ConfigurationValidationError(f"{path} must use RFC 3339") from exc
    if parsed.tzinfo is None:
        raise ConfigurationValidationError(f"{path} must include a timezone")
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreRuleConfiguration(JsonContract):
    rule_id: str
    metric_id: str
    weight: float
    operator: ComparisonOperator
    threshold: float
    score_if_true: float
    score_if_false: float

    def __post_init__(self) -> None:
        _text(self.rule_id, "ScoreRuleConfiguration.rule_id")
        _text(self.metric_id, "ScoreRuleConfiguration.metric_id")
        object.__setattr__(
            self, "weight", _finite_number(self.weight, "ScoreRuleConfiguration.weight")
        )
        object.__setattr__(
            self,
            "threshold",
            _finite_number(self.threshold, "ScoreRuleConfiguration.threshold"),
        )
        object.__setattr__(
            self,
            "score_if_true",
            _finite_number(
                self.score_if_true, "ScoreRuleConfiguration.score_if_true"
            ),
        )
        object.__setattr__(
            self,
            "score_if_false",
            _finite_number(
                self.score_if_false, "ScoreRuleConfiguration.score_if_false"
            ),
        )
        if not isinstance(self.operator, ComparisonOperator):
            raise ConfigurationValidationError(
                "ScoreRuleConfiguration.operator is invalid"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DimensionScoringConfiguration(JsonContract):
    weight: float
    formula: AggregationFormula
    eligible_states: tuple[ScoringState, ...]
    missing_data_policy: MissingDataPolicy
    rules: tuple[ScoreRuleConfiguration, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "weight",
            _finite_number(self.weight, "DimensionScoringConfiguration.weight"),
        )
        if not isinstance(self.formula, AggregationFormula):
            raise ConfigurationValidationError(
                "DimensionScoringConfiguration.formula is invalid"
            )
        states = tuple(self.eligible_states)
        if not states or any(not isinstance(item, ScoringState) for item in states):
            raise ConfigurationValidationError(
                "DimensionScoringConfiguration.eligible_states is invalid"
            )
        if len(set(states)) != len(states):
            raise ConfigurationValidationError(
                "DimensionScoringConfiguration.eligible_states must be unique"
            )
        if not isinstance(self.missing_data_policy, MissingDataPolicy):
            raise ConfigurationValidationError(
                "DimensionScoringConfiguration.missing_data_policy is invalid"
            )
        rules = tuple(self.rules)
        if not rules or any(not isinstance(item, ScoreRuleConfiguration) for item in rules):
            raise ConfigurationValidationError(
                "DimensionScoringConfiguration.rules must not be empty"
            )
        if len({item.rule_id for item in rules}) != len(rules):
            raise ConfigurationValidationError(
                "DimensionScoringConfiguration.rule IDs must be unique"
            )
        object.__setattr__(self, "eligible_states", states)
        object.__setattr__(self, "rules", rules)


@dataclass(frozen=True, slots=True, kw_only=True)
class ScoreAggregationConfiguration(JsonContract):
    formula: AggregationFormula
    missing_dimension_policy: MissingDataPolicy
    score_min: float
    score_max: float
    rounding_mode: RoundingMode
    decimal_places: int

    def __post_init__(self) -> None:
        if not isinstance(self.formula, AggregationFormula):
            raise ConfigurationValidationError(
                "ScoreAggregationConfiguration.formula is invalid"
            )
        if not isinstance(self.missing_dimension_policy, MissingDataPolicy):
            raise ConfigurationValidationError(
                "ScoreAggregationConfiguration.missing_dimension_policy is invalid"
            )
        object.__setattr__(
            self,
            "score_min",
            _finite_number(self.score_min, "ScoreAggregationConfiguration.score_min"),
        )
        object.__setattr__(
            self,
            "score_max",
            _finite_number(self.score_max, "ScoreAggregationConfiguration.score_max"),
        )
        if not isinstance(self.rounding_mode, RoundingMode):
            raise ConfigurationValidationError(
                "ScoreAggregationConfiguration.rounding_mode is invalid"
            )
        if isinstance(self.decimal_places, bool) or not isinstance(
            self.decimal_places, int
        ):
            raise ConfigurationValidationError(
                "ScoreAggregationConfiguration.decimal_places must be an integer"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfigurationAudit(JsonContract):
    business_owner: str
    decision_reference: str
    approved_by: str
    approved_at: str
    configuration_fingerprint: str

    def __post_init__(self) -> None:
        for name in (
            "business_owner",
            "decision_reference",
            "approved_by",
            "configuration_fingerprint",
        ):
            _text(getattr(self, name), f"ConfigurationAudit.{name}")
        _timestamp(self.approved_at, "ConfigurationAudit.approved_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class BusinessScoringConfiguration(JsonContract):
    schema_version: str
    configuration_id: str
    score_version: str
    lifecycle_status: ConfigLifecycleStatus
    test_only: bool
    dimensions: Mapping[str, DimensionScoringConfiguration]
    aggregation: ScoreAggregationConfiguration
    audit: ConfigurationAudit

    def __post_init__(self) -> None:
        for name in ("schema_version", "configuration_id", "score_version"):
            _text(getattr(self, name), f"BusinessScoringConfiguration.{name}")
        if not isinstance(self.lifecycle_status, ConfigLifecycleStatus):
            raise ConfigurationValidationError(
                "BusinessScoringConfiguration.lifecycle_status is invalid"
            )
        if not isinstance(self.test_only, bool):
            raise ConfigurationValidationError(
                "BusinessScoringConfiguration.test_only must be boolean"
            )
        if not isinstance(self.dimensions, MappingABC):
            raise ConfigurationValidationError(
                "BusinessScoringConfiguration.dimensions must be a mapping"
            )
        dimensions = dict(self.dimensions)
        if any(
            not isinstance(item, DimensionScoringConfiguration)
            for item in dimensions.values()
        ):
            raise ConfigurationValidationError(
                "BusinessScoringConfiguration dimensions are invalid"
            )
        if not isinstance(self.aggregation, ScoreAggregationConfiguration):
            raise ConfigurationValidationError(
                "BusinessScoringConfiguration.aggregation is invalid"
            )
        if not isinstance(self.audit, ConfigurationAudit):
            raise ConfigurationValidationError(
                "BusinessScoringConfiguration.audit is invalid"
            )
        object.__setattr__(self, "dimensions", MappingProxyType(dimensions))


_EVALUATOR_BY_DIMENSION = {
    OpportunityDimension.DEMAND_POTENTIAL: DemandPotentialEvaluator,
    OpportunityDimension.COMPETITION_ACCESSIBILITY: CompetitionAccessibilityEvaluator,
    OpportunityDimension.PRODUCT_ECONOMICS_READINESS: EconomicsReadinessEvaluator,
}


def metric_alias_group(
    dimension: OpportunityDimension,
    metric_id: str,
) -> tuple[str, ...]:
    evaluator = _EVALUATOR_BY_DIMENSION[dimension]
    for logical_metric, aliases in evaluator.metric_aliases.items():
        if metric_id == logical_metric or metric_id in aliases:
            return aliases
    return ()


class ConfigurationValidator:
    """Validate an explicit configuration; never supply missing business values."""

    def validate(
        self,
        configuration: BusinessScoringConfiguration,
        *,
        allow_test_config: bool = False,
    ) -> None:
        if not isinstance(configuration, BusinessScoringConfiguration):
            raise TypeError("configuration must be BusinessScoringConfiguration")
        if configuration.schema_version != SUPPORTED_CONFIGURATION_SCHEMA_VERSION:
            raise ConfigurationValidationError(
                f"unsupported schema_version {configuration.schema_version!r}"
            )
        for name in ("configuration_id", "score_version"):
            value = getattr(configuration, name)
            if value == BUSINESS_DECISION_REQUIRED:
                raise ConfigurationValidationError(
                    f"{name} remains BUSINESS_DECISION_REQUIRED"
                )
            if value.casefold() == "latest":
                raise ConfigurationValidationError(
                    f"{name} must be explicit; latest is prohibited"
                )
        if configuration.lifecycle_status not in {
            ConfigLifecycleStatus.APPROVED,
            ConfigLifecycleStatus.ACTIVE,
        }:
            raise ConfigurationValidationError(
                "configuration must be APPROVED or ACTIVE for calculation"
            )
        if configuration.test_only and not allow_test_config:
            raise ConfigurationValidationError(
                "test-only configuration is prohibited for production calculation"
            )
        if BUSINESS_DECISION_REQUIRED in canonical_json(configuration):
            raise ConfigurationValidationError(
                "approved configuration contains BUSINESS_DECISION_REQUIRED"
            )

        expected_dimensions = {item.value for item in OpportunityDimension}
        if set(configuration.dimensions) != expected_dimensions:
            raise ConfigurationValidationError(
                "configuration must contain each opportunity dimension exactly once"
            )
        if configuration.aggregation.score_min >= configuration.aggregation.score_max:
            raise ConfigurationValidationError(
                "aggregation score_min must be less than score_max"
            )
        if configuration.aggregation.decimal_places < 0:
            raise ConfigurationValidationError(
                "aggregation decimal_places must not be negative"
            )

        dimension_weights: list[float] = []
        for dimension in OpportunityDimension:
            dimension_config = configuration.dimensions[dimension.value]
            if dimension_config.weight < 0:
                raise ConfigurationValidationError(
                    f"{dimension.value} weight must not be negative"
                )
            dimension_weights.append(dimension_config.weight)
            rule_weights: list[float] = []
            for rule in dimension_config.rules:
                if not metric_alias_group(dimension, rule.metric_id):
                    raise ConfigurationValidationError(
                        f"unknown metric {rule.metric_id!r} for {dimension.value}"
                    )
                if rule.weight < 0:
                    raise ConfigurationValidationError(
                        f"rule {rule.rule_id} weight must not be negative"
                    )
                rule_weights.append(rule.weight)
                for name in ("score_if_true", "score_if_false"):
                    score = getattr(rule, name)
                    if not (
                        configuration.aggregation.score_min
                        <= score
                        <= configuration.aggregation.score_max
                    ):
                        raise ConfigurationValidationError(
                            f"rule {rule.rule_id} {name} is outside configured score range"
                        )
            if not any(weight > 0 for weight in rule_weights):
                raise ConfigurationValidationError(
                    f"{dimension.value} must contain a positive rule weight"
                )
        if not any(weight > 0 for weight in dimension_weights):
            raise ConfigurationValidationError(
                "configuration must contain a positive dimension weight"
            )


__all__ = (
    "SUPPORTED_CONFIGURATION_SCHEMA_VERSION",
    "AggregationFormula",
    "BusinessScoringConfiguration",
    "ComparisonOperator",
    "ConfigLifecycleStatus",
    "ConfigurationAudit",
    "ConfigurationValidationError",
    "ConfigurationValidator",
    "DimensionScoringConfiguration",
    "MissingDataPolicy",
    "RoundingMode",
    "ScoreAggregationConfiguration",
    "ScoreRuleConfiguration",
    "metric_alias_group",
)
