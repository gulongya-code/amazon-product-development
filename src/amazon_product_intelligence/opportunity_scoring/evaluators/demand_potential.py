"""Demand-potential evidence evaluator V0.1."""

from ..engine_contracts import OpportunityDimension, ScoringState
from .base import BaseOpportunityDimensionEvaluator


class DemandPotentialEvaluator(BaseOpportunityDimensionEvaluator):
    """Report demand evidence readiness without inferring demand direction."""

    dimension = OpportunityDimension.DEMAND_POTENTIAL
    metric_aliases = {
        "keyword_volume": (
            "keyword_volume",
            "keyword.search_volume",
            "market_analysis.keyword_search_volume",
        ),
        "keyword_trend": (
            "keyword_trend",
            "keyword.trend",
            "keyword_trend_observations",
        ),
        "sales_trend": (
            "sales_trend",
            "sales_trend_observations",
        ),
        "category_growth": ("category_growth",),
        "market_size": ("market_size", "total_market_size"),
        "seasonality": ("seasonality",),
    }
    summaries = {
        ScoringState.READY: (
            "All required demand evidence is present; this state does not infer growth."
        ),
        ScoringState.PARTIAL: (
            "Demand evidence is present, but demand or trend evidence is incomplete."
        ),
        ScoringState.PENDING: (
            "Demand evaluation is waiting for evidence or business confirmation."
        ),
        ScoringState.INSUFFICIENT_DATA: (
            "Available evidence is insufficient for a demand-dimension assessment."
        ),
        ScoringState.CONFLICT: (
            "Demand evidence contains unresolved source conflicts; no value was selected."
        ),
    }


__all__ = ("DemandPotentialEvaluator",)
