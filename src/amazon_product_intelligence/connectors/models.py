"""Immutable provider configuration, capability, request, and result models."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
import math
import os
import re
from types import MappingProxyType
from typing import Any, Mapping

from amazon_product_intelligence.adapters import AdaptationResult
from amazon_product_intelligence.contracts import CanonicalObservation, ObservationKind, Provenance


_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_CANONICAL_FIELD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "access_token",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
}


def _require_text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _validate_datetime(name: str, value: str) -> None:
    _require_text(name, value)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")


def _freeze_json(value: Any, path: str) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must not contain NaN or infinity")
        return value
    if isinstance(value, MappingABC):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be strings")
            if key.strip().casefold() in _SENSITIVE_KEYS:
                raise ValueError(f"{path} must not contain credential field {key!r}")
            frozen[key] = _freeze_json(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(item, f"{path}[]") for item in value)
    raise ValueError(f"{path} contains unsupported JSON type {type(value).__name__}")


def _parse_bool(name: str, value: str) -> bool:
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


class CapabilityStatus(StrEnum):
    """Provider API capability; CALCULATED intentionally does not exist."""

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


class ProviderFetchStatus(StrEnum):
    """Outcome of one provider attempt for one Canonical field."""

    RETURNED = "RETURNED"
    EMPTY = "EMPTY"
    FIELD_MISSING = "FIELD_MISSING"


@dataclass(frozen=True, slots=True, kw_only=True)
class CanonicalSelector:
    """Provider-neutral view used to index an existing Canonical bundle."""

    observation_kind: ObservationKind | None
    canonical_names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        names = tuple(self.canonical_names)
        if any(not isinstance(name, str) or not name.strip() for name in names):
            raise ValueError("canonical selector names must be non-empty text")
        object.__setattr__(self, "canonical_names", names)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderCapability:
    """Runtime description of one provider-to-Canonical field path."""

    provider_id: str
    canonical_field: str
    capability_status: CapabilityStatus
    source_field: str | None
    endpoint: str | None
    operation: str | None
    payload_kind: str | None
    selector: CanonicalSelector | None
    priority: int | None = None
    notes: str = ""
    accepts_empty_query: bool = False

    def __post_init__(self) -> None:
        if not _PROVIDER_ID.fullmatch(self.provider_id):
            raise ValueError("provider_id must be stable lowercase machine-readable text")
        if not _CANONICAL_FIELD.fullmatch(self.canonical_field):
            raise ValueError("canonical_field must be a dotted lowercase identifier")
        if not isinstance(self.capability_status, CapabilityStatus):
            raise TypeError("capability_status must be CapabilityStatus")
        if self.priority is not None and (not isinstance(self.priority, int) or self.priority < 0):
            raise ValueError("capability priority must be a non-negative integer")
        if self.capability_status in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}:
            for name in ("source_field", "endpoint", "operation", "payload_kind"):
                _require_text(name, getattr(self, name))
            if self.selector is None:
                raise ValueError("available/partial capability requires a Canonical selector")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderConfig:
    """Provider enablement and runtime policy without storing credential values."""

    provider_id: str
    enabled: bool
    priority: int
    credential_env: str | None
    timeout_seconds: float = 10.0
    max_attempts: int = 1
    field_priorities: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _PROVIDER_ID.fullmatch(self.provider_id):
            raise ValueError("provider_id must be stable lowercase machine-readable text")
        if not isinstance(self.enabled, bool):
            raise TypeError("enabled must be bool")
        if not isinstance(self.priority, int) or self.priority < 0:
            raise ValueError("priority must be a non-negative integer")
        if self.credential_env is not None:
            _require_text("credential_env", self.credential_env)
        if not isinstance(self.timeout_seconds, (int, float)) or not math.isfinite(self.timeout_seconds):
            raise ValueError("timeout_seconds must be finite")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(self.max_attempts, int) or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")
        frozen_priorities: dict[str, int] = {}
        for canonical_field, priority in self.field_priorities.items():
            if not _CANONICAL_FIELD.fullmatch(canonical_field):
                raise ValueError("field priority keys must be dotted Canonical fields")
            if not isinstance(priority, int) or priority < 0:
                raise ValueError("field priorities must be non-negative integers")
            frozen_priorities[canonical_field] = priority
        object.__setattr__(self, "field_priorities", MappingProxyType(frozen_priorities))

    @classmethod
    def from_environment(
        cls,
        *,
        provider_id: str,
        credential_env: str | None,
        environ: Mapping[str, str] | None = None,
        default_enabled: bool = False,
        default_priority: int = 100,
        default_timeout_seconds: float = 10.0,
        default_max_attempts: int = 1,
    ) -> "ProviderConfig":
        source = os.environ if environ is None else environ
        prefix = f"API_PROVIDER_{provider_id.upper()}_"
        enabled = (
            _parse_bool(prefix + "ENABLED", source[prefix + "ENABLED"])
            if prefix + "ENABLED" in source
            else default_enabled
        )
        priority = int(source.get(prefix + "PRIORITY", str(default_priority)))
        timeout = float(source.get(prefix + "TIMEOUT_SECONDS", str(default_timeout_seconds)))
        attempts = int(source.get(prefix + "MAX_ATTEMPTS", str(default_max_attempts)))
        return cls(
            provider_id=provider_id,
            enabled=enabled,
            priority=priority,
            credential_env=credential_env,
            timeout_seconds=timeout,
            max_attempts=attempts,
        )

    def with_enabled(self, enabled: bool) -> "ProviderConfig":
        return replace(self, enabled=enabled)

    def with_priority(self, priority: int) -> "ProviderConfig":
        return replace(self, priority=priority)

    def priority_for(self, capability: ProviderCapability) -> int:
        if capability.canonical_field in self.field_priorities:
            return self.field_priorities[capability.canonical_field]
        if capability.priority is not None:
            return capability.priority
        return self.priority


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderRequest:
    """Credential-free request context shared by every provider."""

    canonical_field: str
    parameters: Mapping[str, Any]
    marketplace: str
    locale: str
    retrieved_at: str
    transformed_at: str
    collection_run_id: str
    currency: str | None = None

    def __post_init__(self) -> None:
        if not _CANONICAL_FIELD.fullmatch(self.canonical_field):
            raise ValueError("canonical_field must be a dotted lowercase identifier")
        if self.marketplace != self.marketplace.strip().upper():
            raise ValueError("marketplace must be normalized uppercase text")
        if self.locale != self.locale.strip().lower():
            raise ValueError("locale must be normalized lowercase text")
        _require_text("collection_run_id", self.collection_run_id)
        _validate_datetime("retrieved_at", self.retrieved_at)
        _validate_datetime("transformed_at", self.transformed_at)
        if self.currency is not None and (
            self.currency != self.currency.strip().upper() or len(self.currency) != 3
        ):
            raise ValueError("currency must be a normalized three-letter code")
        frozen = _freeze_json(self.parameters, "parameters")
        if not isinstance(frozen, MappingABC):
            raise ValueError("parameters must be a mapping")
        object.__setattr__(self, "parameters", frozen)


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderFetchResult:
    """Canonical-compatible output plus an indexed field-level view."""

    provider_id: str
    canonical_field: str
    capability: ProviderCapability
    status: ProviderFetchStatus
    adaptation: AdaptationResult
    observations: tuple[CanonicalObservation, ...]

    def __post_init__(self) -> None:
        observations = tuple(self.observations)
        if self.provider_id != self.capability.provider_id:
            raise ValueError("result provider must match capability provider")
        if self.canonical_field != self.capability.canonical_field:
            raise ValueError("result field must match capability field")
        if self.adaptation.provider != self.provider_id:
            raise ValueError("adaptation provider must match connector provider")
        if any(item.provenance.provider != self.provider_id for item in observations):
            raise ValueError("indexed observations must retain connector provider provenance")
        object.__setattr__(self, "observations", observations)

    @property
    def provenance(self) -> tuple[Provenance, ...]:
        """Existing Canonical provenance objects; no parallel evidence model."""

        return tuple(item.provenance for item in self.observations)


__all__ = (
    "CanonicalSelector",
    "CapabilityStatus",
    "ProviderCapability",
    "ProviderConfig",
    "ProviderFetchResult",
    "ProviderFetchStatus",
    "ProviderRequest",
)
