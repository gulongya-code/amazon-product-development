"""Injected transport and bounded retry extension points for providers."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable

from .errors import ProviderConnectorError


_SECRET_HEADER_NAMES = {
    "api-key",
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderCredential:
    """Ephemeral credential value excluded from repr and safe serialization."""

    environment_variable: str
    injection_name: str
    value: str = field(repr=False)

    def __post_init__(self) -> None:
        for name in ("environment_variable", "injection_name", "value"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")

    def safe_summary(self) -> dict[str, str]:
        return {
            "environment_variable": self.environment_variable,
            "injection_name": self.injection_name,
            "value": "<redacted>",
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderOperation:
    operation: str
    payload_kind: str
    source_tool: str
    method: str
    endpoint: str
    requires_credential: bool
    credential_injection_name: str | None = None
    public_headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("operation", "payload_kind", "source_tool", "method", "endpoint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if self.requires_credential:
            if not isinstance(self.credential_injection_name, str) or not self.credential_injection_name.strip():
                raise ValueError("credential injection name is required")
        headers = dict(self.public_headers)
        if any(not isinstance(key, str) or not isinstance(value, str) for key, value in headers.items()):
            raise ValueError("public headers must contain text keys and values")
        forbidden = sorted(key for key in headers if key.strip().casefold() in _SECRET_HEADER_NAMES)
        if forbidden:
            raise ValueError("credential headers must use ProviderCredential, not public_headers")
        object.__setattr__(self, "public_headers", MappingProxyType(headers))


@dataclass(frozen=True, slots=True, kw_only=True)
class TransportRequest:
    provider_id: str
    operation: str
    method: str
    endpoint: str
    parameters: Mapping[str, Any]
    timeout_seconds: float
    public_headers: Mapping[str, str]
    credential: ProviderCredential | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, "public_headers", MappingProxyType(dict(self.public_headers)))

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "operation": self.operation,
            "method": self.method,
            "endpoint": self.endpoint,
            "parameters": dict(self.parameters),
            "timeout_seconds": self.timeout_seconds,
            "public_headers": dict(self.public_headers),
            "credential": self.credential.safe_summary() if self.credential is not None else None,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class TransportResponse:
    status_code: int
    payload: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.status_code, int) or not 100 <= self.status_code <= 599:
            raise ValueError("status_code must be a valid HTTP-style status")
        if not isinstance(self.metadata, MappingABC):
            raise ValueError("metadata must be a mapping")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@runtime_checkable
class ProviderTransport(Protocol):
    """Side-effect boundary; production HTTP/tool clients are injected here."""

    def execute(self, request: TransportRequest) -> TransportResponse:
        """Execute one request or raise a provider-neutral connector error."""


@runtime_checkable
class RetryPolicy(Protocol):
    """Optional bounded retry decision; no sleeping or infinite loop is implied."""

    def should_retry(
        self,
        error: ProviderConnectorError,
        *,
        attempt: int,
        max_attempts: int,
    ) -> bool:
        """Return whether the transport attempt should be repeated."""


class NoRetryPolicy:
    """Safe default: one attempt, with retry behavior injected explicitly."""

    def should_retry(
        self,
        error: ProviderConnectorError,
        *,
        attempt: int,
        max_attempts: int,
    ) -> bool:
        return False


__all__ = (
    "NoRetryPolicy",
    "ProviderCredential",
    "ProviderOperation",
    "ProviderTransport",
    "RetryPolicy",
    "TransportRequest",
    "TransportResponse",
)
