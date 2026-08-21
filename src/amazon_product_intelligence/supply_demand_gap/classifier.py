"""Explainable threshold classifier for Supply/Demand Gap Analysis V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from amazon_product_intelligence.buyer_need_map import (
    DemandMetricConfidenceLevel,
    DemandMetricResult,
    DemandMetricStatus,
    DemandMetricType,
)

from .errors import SupplyDemandGapValidationError
from .models import (
    GapClassificationPolicy,
    GapConfidence,
    GapConfidenceLevel,
    GapSignalBand,
    GapSignalStatus,
    GapStrength,
    GapSupplyMetric,
    GapType,
    GapTypeRegistry,
    SupplyMetricType,
)
from .registry import GAP_CLASSIFICATION_POLICY_V0_1, GAP_TYPE_REGISTRY_V0_1


_DEMAND_TYPES = frozenset(
    {
        DemandMetricType.SEARCH_DEMAND_SHARE,
        DemandMetricType.REVIEW_MENTION_SHARE,
        DemandMetricType.SALES_ASSOCIATED_SHARE,
        DemandMetricType.REVENUE_ASSOCIATED_SHARE,
    }
)
_LEVEL_RANK = {
    GapConfidenceLevel.UNKNOWN: 0,
    GapConfidenceLevel.LOW: 1,
    GapConfidenceLevel.MEDIUM: 2,
    GapConfidenceLevel.HIGH: 3,
}
_RANK_LEVEL = {value: key for key, value in _LEVEL_RANK.items()}


def _ratio(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0"
    rendered = format(Decimal(numerator) / Decimal(denominator), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _demand_level(level: DemandMetricConfidenceLevel) -> GapConfidenceLevel:
    return GapConfidenceLevel(level.value)


class GapClassifier:
    """Classify existing metrics without recalculating their source populations."""

    def __init__(
        self,
        *,
        type_registry: GapTypeRegistry = GAP_TYPE_REGISTRY_V0_1,
        classification_policy: GapClassificationPolicy = GAP_CLASSIFICATION_POLICY_V0_1,
    ) -> None:
        if not isinstance(type_registry, GapTypeRegistry):
            raise SupplyDemandGapValidationError("classifier requires GapTypeRegistry")
        if not isinstance(classification_policy, GapClassificationPolicy):
            raise SupplyDemandGapValidationError("classifier requires GapClassificationPolicy")
        self.type_registry = type_registry
        self.classification_policy = classification_policy

    @staticmethod
    def _demand_values(demand_metrics: Sequence[DemandMetricResult]) -> tuple[Decimal, ...]:
        return tuple(
            Decimal(item.share)
            for item in demand_metrics
            if item.metric_type in _DEMAND_TYPES
            and item.status is not DemandMetricStatus.UNKNOWN
            and item.share is not None
        )

    @staticmethod
    def _product_coverage(supply_metrics: Sequence[GapSupplyMetric]) -> GapSupplyMetric | None:
        candidates = tuple(
            item
            for item in supply_metrics
            if item.metric_type is SupplyMetricType.PRODUCT_COVERAGE_SHARE
        )
        if len(candidates) != 1:
            raise SupplyDemandGapValidationError(
                "classifier requires exactly one Product Coverage supply metric"
            )
        metric = candidates[0]
        if metric.status is GapSignalStatus.UNKNOWN or metric.value is None:
            return None
        if type(metric.value) is not str:
            raise SupplyDemandGapValidationError("Product Coverage supply metric must use decimal text")
        return metric

    def classify(
        self,
        demand_metrics: Sequence[DemandMetricResult],
        supply_metrics: Sequence[GapSupplyMetric],
    ) -> GapType:
        values = self._demand_values(demand_metrics)
        product_coverage = self._product_coverage(supply_metrics)
        if not values or product_coverage is None:
            return GapType.INSUFFICIENT_EVIDENCE
        demand_band = (
            GapSignalBand.HIGH
            if max(values) >= Decimal(self.classification_policy.high_demand_threshold)
            else GapSignalBand.LOW
        )
        supply_band = (
            GapSignalBand.HIGH
            if Decimal(product_coverage.value)
            >= Decimal(self.classification_policy.high_supply_threshold)
            else GapSignalBand.LOW
        )
        return self.type_registry.for_bands(demand_band, supply_band)

    def confidence(
        self,
        demand_metrics: Sequence[DemandMetricResult],
        supply_metrics: Sequence[GapSupplyMetric],
        *,
        evidence_completeness: str,
    ) -> GapConfidence:
        available_demand = tuple(
            item
            for item in demand_metrics
            if item.metric_type in _DEMAND_TYPES
            and item.status is not DemandMetricStatus.UNKNOWN
            and item.share is not None
        )
        product_coverage = self._product_coverage(supply_metrics)
        demand_confidence = (
            min(
                (_demand_level(item.confidence.level) for item in available_demand),
                key=lambda item: _LEVEL_RANK[item],
            )
            if available_demand
            else GapConfidenceLevel.UNKNOWN
        )
        supply_confidence = (
            product_coverage.confidence.level
            if product_coverage is not None
            else GapConfidenceLevel.UNKNOWN
        )
        available_supply_types = {
            item.metric_type
            for item in supply_metrics
            if item.status is not GapSignalStatus.UNKNOWN
        }
        demand_coverage = _ratio(len({item.metric_type for item in available_demand}), len(_DEMAND_TYPES))
        supply_coverage = _ratio(len(available_supply_types), len(SupplyMetricType))
        if GapConfidenceLevel.UNKNOWN in {demand_confidence, supply_confidence}:
            overall = GapConfidenceLevel.UNKNOWN
        else:
            rank = min(_LEVEL_RANK[demand_confidence], _LEVEL_RANK[supply_confidence])
            if Decimal(evidence_completeness) < Decimal("1"):
                rank = min(rank, 1)
            if Decimal(demand_coverage) < Decimal("0.5") or Decimal(supply_coverage) < Decimal("0.5"):
                rank = max(1, rank - 1)
            overall = _RANK_LEVEL[rank]
        return GapConfidence(
            level=overall,
            demand_confidence=demand_confidence,
            supply_confidence=supply_confidence,
            demand_metric_coverage=demand_coverage,
            supply_metric_coverage=supply_coverage,
            evidence_completeness=evidence_completeness,
            basis=(
                "confidence_is_separate_from_demand_and_supply_values",
                "conservative_side_confidence",
                "metric_type_coverage",
                "embedded_snapshot_evidence_completeness",
            ),
        )

    def strength(
        self,
        gap_type: GapType,
        demand_metrics: Sequence[DemandMetricResult],
        supply_metrics: Sequence[GapSupplyMetric],
        confidence: GapConfidence,
    ) -> GapStrength:
        if gap_type is GapType.INSUFFICIENT_EVIDENCE:
            return GapStrength.UNKNOWN
        if gap_type in {GapType.HIGH_DEMAND_HIGH_SUPPLY, GapType.LOW_DEMAND_LOW_SUPPLY}:
            return GapStrength.LOW
        values = self._demand_values(demand_metrics)
        product_coverage = self._product_coverage(supply_metrics)
        if not values or product_coverage is None:
            return GapStrength.UNKNOWN
        margin = abs(max(values) - Decimal(product_coverage.value))
        if margin >= Decimal(self.classification_policy.high_gap_margin):
            strength = GapStrength.HIGH
        elif margin >= Decimal(self.classification_policy.medium_gap_margin):
            strength = GapStrength.MEDIUM
        else:
            strength = GapStrength.LOW
        confidence_cap = {
            GapConfidenceLevel.HIGH: GapStrength.HIGH,
            GapConfidenceLevel.MEDIUM: GapStrength.MEDIUM,
            GapConfidenceLevel.LOW: GapStrength.LOW,
            GapConfidenceLevel.UNKNOWN: GapStrength.UNKNOWN,
        }[confidence.level]
        if confidence_cap is GapStrength.UNKNOWN:
            return GapStrength.UNKNOWN
        rank = {GapStrength.LOW: 1, GapStrength.MEDIUM: 2, GapStrength.HIGH: 3}
        return min((strength, confidence_cap), key=lambda item: rank[item])


__all__ = ("GapClassifier",)
