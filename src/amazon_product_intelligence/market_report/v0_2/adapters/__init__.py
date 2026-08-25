"""Bounded adapters for the isolated Market Report V0.2 foundation."""

from .buyer_need_adapter import BuyerNeedProjectionAdapter
from .buyer_need_link_adapter import (
    BuyerNeedLinkAdapter,
    GovernedBuyerNeedLinkInput,
)
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
from .product_direction_adapter import (
    GovernedProductDirectionInput,
    ProductDirectionAdapter,
    ProductDirectionMetricBoundary,
)
from .competitor_shortlist_adapter import (
    CompetitorShortlistAdapter,
    GovernedCompetitorShortlistInput,
)
from .executive_summary_adapter import (
    ExecutiveSummaryAdapter,
    GovernedExecutiveClaimInput,
    ValidatedExecutiveSource,
)
from .opportunity_adapter import OpportunityProjectionAdapter
from .report_context_adapter import ReportContextAdapter

__all__ = (
    "BuyerNeedLinkAdapter",
    "BuyerNeedProjectionAdapter",
    "CompetitorShortlistAdapter",
    "CompetitorStructureAdapter",
    "CompetitorDetailAdapter",
    "DistributionAdapter",
    "GovernedDispositionInput",
    "GovernedBuyerNeedLinkInput",
    "GovernedCompetitorShortlistInput",
    "GovernedDistributionSegmentInput",
    "GovernedProductDirectionInput",
    "MarketSizeAdapter",
    "MetricCompatibilityBoundary",
    "ProductDirectionAdapter",
    "ProductDirectionMetricBoundary",
    "ScopeContextAdapter",
    "TrueCompetitorSetAdapter",
    "ExecutiveSummaryAdapter",
    "GovernedExecutiveClaimInput",
    "OpportunityProjectionAdapter",
    "ReportContextAdapter",
    "ValidatedExecutiveSource",
)
