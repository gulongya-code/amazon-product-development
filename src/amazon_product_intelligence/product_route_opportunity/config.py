"""Strict versioned configuration for generic product-route discovery."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.listing_attribute_map.rule_pack import DIMENSIONS

from .errors import ProductRouteOpportunityError


ROUTE_CONFIG_SCHEMA_VERSION = "product-route-config-v1.0"
ROUTE_ENGINE_VERSION = "product-route-engine-v1.0"
ROUTE_METRIC_POLICY_ID = "product-route-metrics"
ROUTE_METRIC_POLICY_VERSION = "1.0"

_TOP_KEYS = {
    "schema_version", "config_id", "version", "category", "category_aliases",
    "core_dimensions", "secondary_dimensions", "cosmetic_dimensions",
    "adoption_dimensions", "min_known_core_dimensions", "min_route_size",
    "singleton_policy", "new_product_max_age_days",
    "new_product_threshold_source", "percentile_method",
    "candidate_min_count", "candidate_max_count", "candidate_min_reason_count",
    "candidate_min_structural_distance",
}


@dataclass(frozen=True, slots=True)
class RouteDiscoveryConfig:
    config_id: str
    version: str
    category: str
    category_aliases: tuple[str, ...]
    core_dimensions: tuple[str, ...]
    secondary_dimensions: tuple[str, ...]
    cosmetic_dimensions: tuple[str, ...]
    adoption_dimensions: tuple[str, ...]
    min_known_core_dimensions: int
    min_route_size: int
    singleton_policy: str
    new_product_max_age_days: int
    new_product_threshold_source: str
    percentile_method: str
    candidate_min_count: int
    candidate_max_count: int
    candidate_min_reason_count: int
    candidate_min_structural_distance: Decimal
    fingerprint: str
    schema_version: str = ROUTE_CONFIG_SCHEMA_VERSION

    @property
    def identity(self) -> str:
        return f"{self.config_id}@{self.version}"


def _object(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise ProductRouteOpportunityError("ROUTE_CONFIG_INVALID", "config must be an object")
    unknown = sorted(set(value) - _TOP_KEYS)
    missing = sorted(_TOP_KEYS - set(value))
    if unknown or missing:
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", f"unknown={unknown} missing={missing}"
        )
    return value


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProductRouteOpportunityError("ROUTE_CONFIG_INVALID", f"{name} must be text")
    return " ".join(value.split())


def _texts(value: Any, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ProductRouteOpportunityError("ROUTE_CONFIG_INVALID", f"{name} must be a list")
    result = tuple(_text(item, f"{name}[]").casefold() for item in value)
    if len(result) != len(set(result)):
        raise ProductRouteOpportunityError("ROUTE_CONFIG_INVALID", f"{name} has duplicates")
    return result


def _integer(value: Any, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", f"{name} must be an integer >= {minimum}"
        )
    return value


def load_route_discovery_config(path: str | Path) -> RouteDiscoveryConfig:
    candidate = Path(path)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_READ_FAILED", "config must be readable UTF-8 JSON"
        ) from exc
    top = _object(payload)
    if top["schema_version"] != ROUTE_CONFIG_SCHEMA_VERSION:
        raise ProductRouteOpportunityError("ROUTE_CONFIG_INVALID", "unsupported schema_version")

    core = _texts(top["core_dimensions"], "core_dimensions")
    secondary = _texts(top["secondary_dimensions"], "secondary_dimensions", allow_empty=True)
    cosmetic = _texts(top["cosmetic_dimensions"], "cosmetic_dimensions", allow_empty=True)
    adoption = _texts(top["adoption_dimensions"], "adoption_dimensions", allow_empty=True)
    for name, values in (
        ("core_dimensions", core), ("secondary_dimensions", secondary),
        ("cosmetic_dimensions", cosmetic), ("adoption_dimensions", adoption),
    ):
        unsupported = sorted(set(values) - set(DIMENSIONS))
        if unsupported:
            raise ProductRouteOpportunityError(
                "ROUTE_CONFIG_INVALID", f"{name} unsupported={unsupported}"
            )
    if "color" in core:
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "color cannot be a core dimension in V1"
        )
    if set(core) & set(cosmetic):
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "cosmetic dimensions cannot define primary routes"
        )
    min_known = _integer(top["min_known_core_dimensions"], "min_known_core_dimensions", minimum=1)
    if min_known > len(core):
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "min_known_core_dimensions exceeds configured core dimensions"
        )
    min_candidates = _integer(top["candidate_min_count"], "candidate_min_count", minimum=3)
    max_candidates = _integer(top["candidate_max_count"], "candidate_max_count", minimum=3)
    if max_candidates > 5 or min_candidates > max_candidates:
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "candidate bounds must satisfy 3 <= min <= max <= 5"
        )
    try:
        distance = Decimal(str(top["candidate_min_structural_distance"]))
    except (InvalidOperation, ValueError) as exc:
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "candidate distance must be decimal"
        ) from exc
    if not Decimal("0") <= distance <= Decimal("1"):
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "candidate distance must be between zero and one"
        )
    singleton_policy = _text(top["singleton_policy"], "singleton_policy").upper()
    if singleton_policy != "UNCLASSIFIED":
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "V1 singleton_policy must be UNCLASSIFIED"
        )
    percentile_method = _text(top["percentile_method"], "percentile_method").upper()
    if percentile_method != "NEAREST_RANK":
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_INVALID", "V1 percentile_method must be NEAREST_RANK"
        )

    return RouteDiscoveryConfig(
        config_id=_text(top["config_id"], "config_id"),
        version=_text(top["version"], "version"),
        category=_text(top["category"], "category").casefold(),
        category_aliases=_texts(top["category_aliases"], "category_aliases", allow_empty=True),
        core_dimensions=core,
        secondary_dimensions=secondary,
        cosmetic_dimensions=cosmetic,
        adoption_dimensions=adoption,
        min_known_core_dimensions=min_known,
        min_route_size=_integer(top["min_route_size"], "min_route_size", minimum=2),
        singleton_policy=singleton_policy,
        new_product_max_age_days=_integer(
            top["new_product_max_age_days"], "new_product_max_age_days", minimum=1
        ),
        new_product_threshold_source=_text(
            top["new_product_threshold_source"], "new_product_threshold_source"
        ),
        percentile_method=percentile_method,
        candidate_min_count=min_candidates,
        candidate_max_count=max_candidates,
        candidate_min_reason_count=_integer(
            top["candidate_min_reason_count"], "candidate_min_reason_count", minimum=1
        ),
        candidate_min_structural_distance=distance,
        fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
    )


def validate_category(config: RouteDiscoveryConfig, category: str) -> None:
    normalized = " ".join(category.split()).casefold()
    if normalized not in {config.category, *config.category_aliases}:
        raise ProductRouteOpportunityError(
            "ROUTE_CONFIG_CATEGORY_MISMATCH",
            "dataset category is not covered by the route config",
        )


__all__ = (
    "ROUTE_CONFIG_SCHEMA_VERSION", "ROUTE_ENGINE_VERSION",
    "ROUTE_METRIC_POLICY_ID", "ROUTE_METRIC_POLICY_VERSION",
    "RouteDiscoveryConfig", "load_route_discovery_config", "validate_category",
)
