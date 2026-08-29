"""Deterministic Route Discovery V2 over accepted Semantic Engine V2 facts."""

from .config import (
    ROUTE_V2_CONFIG_SCHEMA_VERSION,
    ROUTE_V2_ENGINE_VERSION,
    ROUTE_V2_METHOD,
    RouteDiscoveryV2Config,
    load_route_discovery_v2_config,
    validate_route_v2_authority,
)
from .engine import build_route_discovery_v2
from .errors import RouteDiscoveryV2Error
from .models import (
    CandidateRouteV2,
    ProductRouteV2,
    RouteDescriptor,
    RouteDiscoveryV2Result,
    RouteSemanticKey,
    RouteV2Membership,
    SemanticRouteFeature,
    SemanticRouteFeatureView,
)
from .projection import build_semantic_route_feature_views

__all__ = (
    "CandidateRouteV2", "ProductRouteV2", "ROUTE_V2_CONFIG_SCHEMA_VERSION",
    "ROUTE_V2_ENGINE_VERSION", "ROUTE_V2_METHOD", "RouteDescriptor",
    "RouteDiscoveryV2Config", "RouteDiscoveryV2Error", "RouteDiscoveryV2Result",
    "RouteSemanticKey", "RouteV2Membership", "SemanticRouteFeature",
    "SemanticRouteFeatureView", "build_route_discovery_v2",
    "build_semantic_route_feature_views", "load_route_discovery_v2_config",
    "validate_route_v2_authority",
)
