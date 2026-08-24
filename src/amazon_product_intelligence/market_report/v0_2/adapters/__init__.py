"""Bounded adapters for the isolated Market Report V0.2 foundation."""

from .competitor_structure_adapter import CompetitorStructureAdapter
from .market_size_adapter import MarketSizeAdapter
from .scope_context_adapter import ScopeContextAdapter
from .true_competitor_adapter import (
    GovernedDispositionInput,
    TrueCompetitorSetAdapter,
)

__all__ = (
    "CompetitorStructureAdapter",
    "GovernedDispositionInput",
    "MarketSizeAdapter",
    "ScopeContextAdapter",
    "TrueCompetitorSetAdapter",
)
