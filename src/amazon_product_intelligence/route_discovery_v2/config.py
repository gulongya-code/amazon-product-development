"""Strict, profile-authorized configuration for Route Discovery V2."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.semantic_engine_v2.models import (
    RoleRelevance,
    UniversalSemanticRole,
)
from amazon_product_intelligence.semantic_engine_v2.profile import (
    CategorySemanticProfileV1_1,
)

from .errors import RouteDiscoveryV2Error


ROUTE_V2_CONFIG_SCHEMA_VERSION = "route-discovery-v2-config-v1.0"
ROUTE_V2_ENGINE_VERSION = "route-discovery-v2.0"
ROUTE_V2_RESULT_CONTRACT_VERSION = "route-discovery-v2-result-v1.0"
ROUTE_V2_MEMBERSHIP_CONTRACT_VERSION = "route-membership-v2.0"
ROUTE_V2_METHOD = "PROFILE_AUTHORIZED_HIERARCHICAL_SPARSE_SEMANTIC_CONSENSUS"

_ROUTE_ROLES = frozenset((
    UniversalSemanticRole.STRUCTURAL_FORM,
    UniversalSemanticRole.USAGE_ARCHITECTURE,
    UniversalSemanticRole.INSTALLATION_ARCHITECTURE,
    UniversalSemanticRole.ATTACHMENT_MECHANISM,
    UniversalSemanticRole.OPERATION_MECHANISM,
    UniversalSemanticRole.POWER_MODE,
    UniversalSemanticRole.COMPATIBILITY,
    UniversalSemanticRole.SIZE_CAPACITY,
))
_NON_DESCRIPTOR_ROLES = frozenset((
    UniversalSemanticRole.PRODUCT_IDENTITY,
    UniversalSemanticRole.PRODUCT_ROLE,
))
_TOP_KEYS = frozenset((
    "schema_version", "config_id", "version", "category", "category_aliases",
    "route_dimensions", "promoted_secondary_dimensions", "descriptor_dimensions",
    "adoption_dimensions", "min_defining_dimensions", "min_route_size",
    "singleton_policy",
    "new_product_max_age_days", "new_product_threshold_source", "percentile_method",
    "candidate_min_count", "candidate_max_count", "candidate_min_reason_count",
    "candidate_min_semantic_distance",
))


@dataclass(frozen=True, slots=True)
class RouteDiscoveryV2Config:
    config_id: str
    version: str
    category: str
    category_aliases: tuple[str, ...]
    route_dimensions: tuple[str, ...]
    promoted_secondary_dimensions: tuple[str, ...]
    descriptor_dimensions: tuple[str, ...]
    adoption_dimensions: tuple[str, ...]
    min_defining_dimensions: int
    min_route_size: int
    singleton_policy: str
    new_product_max_age_days: int
    new_product_threshold_source: str
    percentile_method: str
    candidate_min_count: int
    candidate_max_count: int
    candidate_min_reason_count: int
    candidate_min_semantic_distance: Decimal
    fingerprint: str
    schema_version: str = ROUTE_V2_CONFIG_SCHEMA_VERSION

    @property
    def identity(self) -> str:
        return f"{self.config_id}@{self.version}"


def _object(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise RouteDiscoveryV2Error("ROUTE_V2_CONFIG_INVALID", "config must be an object")
    unknown = sorted(set(value) - _TOP_KEYS)
    missing = sorted(_TOP_KEYS - set(value))
    if unknown or missing:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", f"unknown={unknown} missing={missing}",
        )
    return value


def _text(value: Any, name: str, *, normalize: bool = False) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RouteDiscoveryV2Error("ROUTE_V2_CONFIG_INVALID", f"{name} must be text")
    result = " ".join(value.split())
    return result.casefold() if normalize else result


def _texts(value: Any, name: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise RouteDiscoveryV2Error("ROUTE_V2_CONFIG_INVALID", f"{name} must be a list")
    result = tuple(_text(item, f"{name}[]", normalize=True) for item in value)
    if len(result) != len(set(result)):
        raise RouteDiscoveryV2Error("ROUTE_V2_CONFIG_INVALID", f"{name} has duplicates")
    return result


def _integer(value: Any, name: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", f"{name} must be an integer >= {minimum}",
        )
    return value


def _decimal(value: Any, name: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", f"{name} must be decimal",
        ) from exc
    if not result.is_finite() or not Decimal("0") <= result <= Decimal("1"):
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", f"{name} must be between zero and one",
        )
    return result


def load_route_discovery_v2_config(path: str | Path) -> RouteDiscoveryV2Config:
    candidate = Path(path)
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_READ_FAILED", "config must be readable UTF-8 JSON",
        ) from exc
    top = _object(payload)
    if top["schema_version"] != ROUTE_V2_CONFIG_SCHEMA_VERSION:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", "unsupported schema_version",
        )
    route_dimensions = _texts(top["route_dimensions"], "route_dimensions")
    promotions = _texts(
        top["promoted_secondary_dimensions"],
        "promoted_secondary_dimensions", allow_empty=True,
    )
    descriptors = _texts(
        top["descriptor_dimensions"], "descriptor_dimensions", allow_empty=True,
    )
    adoption = _texts(
        top["adoption_dimensions"], "adoption_dimensions", allow_empty=True,
    )
    if set(promotions) - set(route_dimensions):
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID",
            "promoted secondary dimensions must also be route dimensions",
        )
    min_dimensions = _integer(
        top["min_defining_dimensions"], "min_defining_dimensions", minimum=1,
    )
    if min_dimensions > len(route_dimensions):
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", "min_defining_dimensions exceeds route dimensions",
        )
    if min_dimensions != 1:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID",
            "compatible sparse consensus requires min_defining_dimensions=1",
        )
    min_candidates = _integer(
        top["candidate_min_count"], "candidate_min_count", minimum=3,
    )
    max_candidates = _integer(
        top["candidate_max_count"], "candidate_max_count", minimum=3,
    )
    if min_candidates > max_candidates or max_candidates > 5:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", "candidate bounds must satisfy 3 <= min <= max <= 5",
        )
    singleton = _text(top["singleton_policy"], "singleton_policy").upper()
    if singleton != "MERGE_COMPATIBLE_ELSE_UNCLASSIFIED":
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", "unsupported singleton policy",
        )
    percentile = _text(top["percentile_method"], "percentile_method").upper()
    if percentile != "NEAREST_RANK":
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CONFIG_INVALID", "percentile method must retain NEAREST_RANK",
        )
    return RouteDiscoveryV2Config(
        config_id=_text(top["config_id"], "config_id"),
        version=_text(top["version"], "version"),
        category=_text(top["category"], "category", normalize=True),
        category_aliases=_texts(
            top["category_aliases"], "category_aliases", allow_empty=True,
        ),
        route_dimensions=route_dimensions,
        promoted_secondary_dimensions=promotions,
        descriptor_dimensions=descriptors,
        adoption_dimensions=adoption,
        min_defining_dimensions=min_dimensions,
        min_route_size=_integer(top["min_route_size"], "min_route_size", minimum=2),
        singleton_policy=singleton,
        new_product_max_age_days=_integer(
            top["new_product_max_age_days"], "new_product_max_age_days", minimum=1,
        ),
        new_product_threshold_source=_text(
            top["new_product_threshold_source"], "new_product_threshold_source",
        ),
        percentile_method=percentile,
        candidate_min_count=min_candidates,
        candidate_max_count=max_candidates,
        candidate_min_reason_count=_integer(
            top["candidate_min_reason_count"], "candidate_min_reason_count", minimum=1,
        ),
        candidate_min_semantic_distance=_decimal(
            top["candidate_min_semantic_distance"], "candidate_min_semantic_distance",
        ),
        fingerprint=sha256(canonical_json(payload).encode("utf-8")).hexdigest(),
    )


def validate_route_v2_authority(
    config: RouteDiscoveryV2Config,
    profile: CategorySemanticProfileV1_1,
    category: str,
) -> None:
    """Reject config that exceeds accepted profile relevance/role authority."""

    normalized = " ".join(category.split()).casefold()
    if normalized not in {config.category, *config.category_aliases}:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_CATEGORY_MISMATCH", "dataset category is not covered by config",
        )
    if not profile.supports_category(category):
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_PROFILE_MISMATCH", "semantic profile does not cover dataset category",
        )
    policies = {item.dimension: item for item in profile.source_policies}
    configured = {
        *config.route_dimensions, *config.descriptor_dimensions,
        *config.adoption_dimensions,
    }
    missing = sorted(configured - set(policies))
    if missing:
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_PROFILE_AUTHORITY_INVALID", f"dimensions lack profile policy: {missing}",
        )
    for dimension in config.route_dimensions:
        policy = policies[dimension]
        if policy.role not in _ROUTE_ROLES:
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_PROFILE_AUTHORITY_INVALID",
                f"role cannot define a route: {policy.role.value}",
            )
        if policy.relevance is RoleRelevance.CORE:
            if dimension in config.promoted_secondary_dimensions:
                raise RouteDiscoveryV2Error(
                    "ROUTE_V2_PROFILE_AUTHORITY_INVALID",
                    f"CORE dimension cannot be marked as secondary promotion: {dimension}",
                )
            continue
        if (
            policy.relevance is RoleRelevance.SECONDARY
            and dimension in config.promoted_secondary_dimensions
        ):
            continue
        raise RouteDiscoveryV2Error(
            "ROUTE_V2_PROFILE_AUTHORITY_INVALID",
            f"dimension is not profile-promoted for route identity: {dimension}",
        )
    for dimension in config.descriptor_dimensions:
        if policies[dimension].role in _NON_DESCRIPTOR_ROLES:
            raise RouteDiscoveryV2Error(
                "ROUTE_V2_PROFILE_AUTHORITY_INVALID",
                f"identity/role boundary is not a route descriptor: {dimension}",
            )


__all__ = (
    "ROUTE_V2_CONFIG_SCHEMA_VERSION", "ROUTE_V2_ENGINE_VERSION",
    "ROUTE_V2_MEMBERSHIP_CONTRACT_VERSION", "ROUTE_V2_METHOD",
    "ROUTE_V2_RESULT_CONTRACT_VERSION", "RouteDiscoveryV2Config",
    "load_route_discovery_v2_config", "validate_route_v2_authority",
)
