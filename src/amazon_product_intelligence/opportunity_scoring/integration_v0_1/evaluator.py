"""Pure metric evaluator for declared Opportunity Score policy rules."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from amazon_product_intelligence.contracts import canonical_json, deterministic_id

from .models import (
    OpportunityMetricScoreTrace,
    OpportunityScoreMetricStatus,
    OpportunityScoringIntegrationValidationError,
    OpportunityScoringMetricInput,
)


class OpportunityScoreEvaluator:
    """Evaluate one adapted metric without using confidence as a multiplier."""

    def evaluate(
        self,
        metric: OpportunityScoringMetricInput,
        rule: Mapping[str, Any],
    ) -> OpportunityMetricScoreTrace:
        if not isinstance(metric, OpportunityScoringMetricInput):
            raise TypeError("metric must be OpportunityScoringMetricInput")
        if not isinstance(rule, Mapping):
            raise TypeError("rule must be a mapping")
        rule_type = rule["rule_type"]
        metric_weight = float(rule["metric_weight"])
        limitations = list(metric.limitations)
        normalized: float | None

        if (
            metric.status is OpportunityScoreMetricStatus.UNKNOWN
            or metric.value is None
        ):
            normalized = None
            limitations.append("UNKNOWN_EXCLUDED_NOT_ZERO")
        else:
            normalized = self._evaluate_value(metric.value, rule)
            if normalized is None:
                limitations.append("VALUE_NOT_ELIGIBLE_FOR_DECLARED_RULE")

        weighted = (
            None if normalized is None else normalized * metric_weight
        )
        material = {
            "metric_id": metric.metric_id,
            "dimension": metric.dimension,
            "raw_value": metric.value,
            "input_status": metric.status,
            "rule_type": rule_type,
            "rule_description": canonical_json(rule),
            "metric_weight": metric_weight,
            "normalized_score": normalized,
            "weighted_score": weighted,
            "source_evidence_ids": metric.source_evidence_ids,
            "source_reference_ids": metric.source_reference_ids,
            "limitations": tuple(sorted(set(limitations))),
        }
        return OpportunityMetricScoreTrace(
            trace_id=deterministic_id(
                "opportunity-score-metric-trace", material
            ),
            **material,
        )

    @staticmethod
    def _evaluate_value(
        value: str, rule: Mapping[str, Any]
    ) -> float | None:
        rule_type = rule["rule_type"]
        if rule_type == "PRESENCE":
            return float(rule["present_score"])
        if rule_type == "CATEGORY_MAP":
            selected = rule["scores"].get(value)
            if selected is None:
                selected = rule["scores"].get(value.upper())
            return None if selected is None else float(selected)
        if rule_type == "NUMERIC_RANGE":
            try:
                candidate = Decimal(value)
                minimum = Decimal(str(rule["minimum"]))
                maximum = Decimal(str(rule["maximum"]))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise OpportunityScoringIntegrationValidationError(
                    "numeric scoring input is not a finite decimal"
                ) from exc
            if not candidate.is_finite():
                raise OpportunityScoringIntegrationValidationError(
                    "numeric scoring input is not finite"
                )
            bounded = min(max(candidate, minimum), maximum)
            normalized = (bounded - minimum) / (maximum - minimum) * Decimal(100)
            if rule["direction"] == "LOWER_IS_FAVORABLE":
                normalized = Decimal(100) - normalized
            return float(normalized)
        raise OpportunityScoringIntegrationValidationError(
            f"unsupported rule_type {rule_type!r}"
        )


__all__ = ("OpportunityScoreEvaluator",)
