"""Bounded adapters for the isolated Market Report V0.2 foundation."""

from .competitor_structure_adapter import CompetitorStructureAdapter
from .competitor_detail_adapter import (
    CompetitorDetailAdapter,
    MetricCompatibilityBoundary,
)
from .distribution_adapter import (
    DistributionAdapter,
    GovernedDistributionSegmentInput,
)
from .market_size_adapter import MarketSizeAdapter
from .scope_context_adapter import ScopeContextAdapter
from .true_competitor_adapter import (
    GovernedDispositionInput,
    TrueCompetitorSetAdapter,
)

__all__ = (
    "CompetitorStructureAdapter",
    "CompetitorDetailAdapter",
    "DistributionAdapter",
    "GovernedDispositionInput",
    "GovernedDistributionSegmentInput",
    "MarketSizeAdapter",
    "MetricCompatibilityBoundary",
    "ScopeContextAdapter",
    "TrueCompetitorSetAdapter",
)
