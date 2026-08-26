"""Product Map, deterministic route discovery, and opportunity evidence V1.0."""

from .config import (
    ROUTE_ENGINE_VERSION,
    RouteDiscoveryConfig,
    load_route_discovery_config,
)
from .engine import build_product_route_opportunity
from .errors import ProductRouteOpportunityError
from .models import (
    CandidateRoute,
    CandidateSelectionStatus,
    MembershipStatus,
    ProductMapRecord,
    ProductRoute,
    ProductRouteOpportunityResult,
    RouteMembership,
)
from .product_map import build_product_map_records

__all__ = (
    "CandidateRoute", "CandidateSelectionStatus", "MembershipStatus",
    "ProductMapRecord", "ProductRoute", "ProductRouteOpportunityError",
    "ProductRouteOpportunityResult", "ROUTE_ENGINE_VERSION",
    "RouteDiscoveryConfig", "RouteMembership", "build_product_map_records",
    "build_product_route_opportunity", "load_route_discovery_config",
)
