"""Competition-accessibility evidence evaluator V0.1."""

from ..engine_contracts import OpportunityDimension, ScoringState
from .base import BaseOpportunityDimensionEvaluator


class CompetitionAccessibilityEvaluator(BaseOpportunityDimensionEvaluator):
    """Report competition evidence state without classifying competition level."""

    dimension = OpportunityDimension.COMPETITION_ACCESSIBILITY
    metric_aliases = {
        "top_asin_review": (
            "top_asin_review",
            "review_count",
            "metric.review_count",
        ),
        "top_asin_rating": (
            "top_asin_rating",
            "rating",
            "metric.rating",
        ),
        "brand_concentration": ("brand_concentration",),
        "seller_information": (
            "seller_information",
            "seller_count",
            "seller_concentration",
        ),
        "price_competition": (
            "price_competition",
            "comparable_price_pressure",
        ),
        "bsr_distribution": (
            "bsr_distribution",
            "competition_analysis.contextual_bsr",
        ),
    }
    summaries = {
        ScoringState.READY: (
            "All required competition evidence is present; no high/low classification was made."
        ),
        ScoringState.PARTIAL: (
            "Competition evidence is present, but part of the required context is missing."
        ),
        ScoringState.PENDING: (
            "Competition evaluation is waiting for evidence or business confirmation."
        ),
        ScoringState.INSUFFICIENT_DATA: (
            "Available evidence is insufficient for a competition-dimension assessment."
        ),
        ScoringState.CONFLICT: (
            "Competition evidence contains unresolved source conflicts; no value was selected."
        ),
    }


__all__ = ("CompetitionAccessibilityEvaluator",)
