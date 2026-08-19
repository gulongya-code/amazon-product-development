"""Product-economics data-readiness evaluator V0.1."""

from ..engine_contracts import OpportunityDimension, ScoringState
from .base import BaseOpportunityDimensionEvaluator


class EconomicsReadinessEvaluator(BaseOpportunityDimensionEvaluator):
    """Report economics input readiness without calculating profit or margin."""

    dimension = OpportunityDimension.PRODUCT_ECONOMICS_READINESS
    metric_aliases = {
        "selling_price": (
            "selling_price",
            "price",
            "market_analysis.observed_product_price",
        ),
        "revenue_estimate": ("revenue_estimate", "estimated_revenue"),
        "product_cost": (
            "product_cost",
            "cost_input_availability",
            "landed_unit_cost",
        ),
        "logistics_cost": (
            "logistics_cost",
            "fulfillment_logistics_cost",
        ),
        "fee_input": ("fee_input", "amazon_fee"),
        "margin_readiness": (
            "margin_readiness",
            "margin_calculation_readiness",
        ),
    }
    insufficient_inputs = frozenset({"product_cost", "logistics_cost"})
    summaries = {
        ScoringState.READY: (
            "All required economics inputs are present; no profit or margin was calculated."
        ),
        ScoringState.PARTIAL: (
            "Economics inputs are present, but part of the readiness evidence is incomplete."
        ),
        ScoringState.PENDING: (
            "Economics readiness is waiting for cost evidence or business confirmation."
        ),
        ScoringState.INSUFFICIENT_DATA: (
            "Economics readiness cannot be assessed without required cost evidence."
        ),
        ScoringState.CONFLICT: (
            "Economics evidence contains unresolved source conflicts; no value was selected."
        ),
    }


__all__ = ("EconomicsReadinessEvaluator",)
