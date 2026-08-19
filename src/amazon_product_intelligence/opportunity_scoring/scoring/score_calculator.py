"""Configuration-driven opportunity score calculation V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, ROUND_HALF_UP
import math
from typing import Any

from ..evaluators import DimensionEvaluationResult
from ..result_aggregator import OpportunityResult, OpportunityResultAggregator
from .config_validator import (
    AggregationFormula,
    BusinessScoringConfiguration,
    ComparisonOperator,
    ConfigurationValidator,
    MissingDataPolicy,
    RoundingMode,
    metric_alias_group,
)
from .result_builder import (
    DimensionScoreTrace,
    MetricRuleTrace,
    OpportunityScoreResult,
    OpportunityScoreResultBuilder,
)


class ScoreCalculationError(ValueError):
    """Raised when approved configuration cannot be executed safely."""


_ROUNDING_MODES = {
    RoundingMode.HALF_UP: ROUND_HALF_UP,
    RoundingMode.HALF_EVEN: ROUND_HALF_EVEN,
    RoundingMode.DOWN: ROUND_DOWN,
}


class ScoreCalculator:
    """Execute only rules supplied by one explicit approved configuration."""

    def __init__(
        self,
        *,
        validator: ConfigurationValidator | None = None,
        result_builder: OpportunityScoreResultBuilder | None = None,
        allow_test_config: bool = False,
    ) -> None:
        self._validator = validator or ConfigurationValidator()
        self._result_builder = result_builder or OpportunityScoreResultBuilder()
        self._allow_test_config = allow_test_config

    def calculate(
        self,
        dimension_results: OpportunityResult
        | Sequence[DimensionEvaluationResult],
        configuration: BusinessScoringConfiguration | None,
    ) -> OpportunityScoreResult:
        opportunity = (
            dimension_results
            if isinstance(dimension_results, OpportunityResult)
            else OpportunityResultAggregator().aggregate(dimension_results)
        )
        if configuration is None:
            return self._result_builder.pending_configuration(opportunity)
        self._validator.validate(
            configuration, allow_test_config=self._allow_test_config
        )
        return self._calculate(opportunity, configuration)

    def _calculate(
        self,
        opportunity: OpportunityResult,
        configuration: BusinessScoringConfiguration,
    ) -> OpportunityScoreResult:
        dimension_traces: list[DimensionScoreTrace] = []
        missing_inputs: list[str] = []

        for dimension_result in opportunity.dimension_results:
            dimension_config = configuration.dimensions[
                dimension_result.dimension.value
            ]
            if dimension_result.result_status not in dimension_config.eligible_states:
                missing_inputs.append(
                    f"{dimension_result.dimension.value}:INELIGIBLE_STATE:"
                    f"{dimension_result.result_status.value}"
                )
                if (
                    configuration.aggregation.missing_dimension_policy
                    is MissingDataPolicy.SKIP_RENORMALIZE
                ):
                    continue
                return self._result_builder.pending_data(
                    opportunity,
                    configuration,
                    missing_inputs=tuple(missing_inputs),
                )

            rule_traces: list[MetricRuleTrace] = []
            for rule in dimension_config.rules:
                aliases = set(
                    metric_alias_group(dimension_result.dimension, rule.metric_id)
                )
                evidence = tuple(
                    item
                    for item in dimension_result.evidence
                    if item.metric_id in aliases and item.value is not None
                )
                numeric_values = tuple(
                    _numeric(item.value) for item in evidence
                )
                if not evidence or any(item is None for item in numeric_values):
                    missing_inputs.append(
                        f"{dimension_result.dimension.value}:METRIC:{rule.metric_id}"
                    )
                    if (
                        dimension_config.missing_data_policy
                        is MissingDataPolicy.SKIP_RENORMALIZE
                    ):
                        continue
                    return self._result_builder.pending_data(
                        opportunity,
                        configuration,
                        missing_inputs=tuple(missing_inputs),
                        calculation_trace=tuple(dimension_traces),
                    )
                distinct_values = set(numeric_values)
                if len(distinct_values) != 1:
                    missing_inputs.append(
                        f"{dimension_result.dimension.value}:CONFLICT:{rule.metric_id}"
                    )
                    return self._result_builder.pending_data(
                        opportunity,
                        configuration,
                        missing_inputs=tuple(missing_inputs),
                        calculation_trace=tuple(dimension_traces),
                    )
                metric_value = numeric_values[0]
                assert metric_value is not None
                matched = _compare(
                    metric_value,
                    Decimal(str(rule.threshold)),
                    rule.operator,
                )
                rule_score = (
                    rule.score_if_true if matched else rule.score_if_false
                )
                rule_traces.append(
                    MetricRuleTrace(
                        rule_id=rule.rule_id,
                        metric_id=rule.metric_id,
                        metric_value=evidence[0].value,
                        operator=rule.operator,
                        threshold=rule.threshold,
                        matched=matched,
                        rule_score=rule_score,
                        rule_weight=rule.weight,
                        evidence_provenance_ids=tuple(
                            item.provenance_id for item in evidence
                        ),
                    )
                )

            if not rule_traces:
                missing_inputs.append(
                    f"{dimension_result.dimension.value}:NO_ELIGIBLE_RULES"
                )
                if (
                    configuration.aggregation.missing_dimension_policy
                    is MissingDataPolicy.SKIP_RENORMALIZE
                ):
                    continue
                return self._result_builder.pending_data(
                    opportunity,
                    configuration,
                    missing_inputs=tuple(missing_inputs),
                    calculation_trace=tuple(dimension_traces),
                )
            dimension_score = _aggregate(
                tuple((trace.rule_score, trace.rule_weight) for trace in rule_traces),
                dimension_config.formula,
            )
            dimension_traces.append(
                DimensionScoreTrace(
                    dimension=dimension_result.dimension,
                    formula=dimension_config.formula,
                    dimension_weight=dimension_config.weight,
                    score_value=_round(
                        dimension_score,
                        configuration.aggregation.decimal_places,
                        configuration.aggregation.rounding_mode,
                    ),
                    rule_traces=tuple(rule_traces),
                )
            )

        if not dimension_traces:
            return self._result_builder.pending_data(
                opportunity,
                configuration,
                missing_inputs=tuple(missing_inputs),
            )
        total_score = _aggregate(
            tuple((trace.score_value, trace.dimension_weight) for trace in dimension_traces),
            configuration.aggregation.formula,
        )
        resolved_score = _round(
            total_score,
            configuration.aggregation.decimal_places,
            configuration.aggregation.rounding_mode,
        )
        return self._result_builder.calculated(
            opportunity,
            configuration,
            score_value=resolved_score,
            calculation_trace=tuple(dimension_traces),
            missing_inputs=tuple(missing_inputs),
        )


def _numeric(value: Any) -> Decimal | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(float(value)):
        return None
    return Decimal(str(value))


def _compare(
    value: Decimal,
    threshold: Decimal,
    operator: ComparisonOperator,
) -> bool:
    if operator is ComparisonOperator.GREATER_THAN:
        return value > threshold
    if operator is ComparisonOperator.GREATER_THAN_OR_EQUAL:
        return value >= threshold
    if operator is ComparisonOperator.LESS_THAN:
        return value < threshold
    if operator is ComparisonOperator.LESS_THAN_OR_EQUAL:
        return value <= threshold
    if operator is ComparisonOperator.EQUAL:
        return value == threshold
    raise ScoreCalculationError(f"unsupported comparison operator {operator}")


def _aggregate(
    values: tuple[tuple[float, float], ...],
    formula: AggregationFormula,
) -> Decimal:
    if formula is not AggregationFormula.WEIGHTED_AVERAGE:
        raise ScoreCalculationError(f"unsupported aggregation formula {formula}")
    weighted_total = sum(
        (Decimal(str(value)) * Decimal(str(weight)) for value, weight in values),
        Decimal(0),
    )
    total_weight = sum(
        (Decimal(str(weight)) for _, weight in values),
        Decimal(0),
    )
    if total_weight <= 0:
        raise ScoreCalculationError("configured aggregate has no positive weight")
    return weighted_total / total_weight


def _round(value: Decimal, decimal_places: int, mode: RoundingMode) -> float:
    quantum = Decimal(1).scaleb(-decimal_places)
    return float(value.quantize(quantum, rounding=_ROUNDING_MODES[mode]))


__all__ = (
    "ScoreCalculationError",
    "ScoreCalculator",
)
