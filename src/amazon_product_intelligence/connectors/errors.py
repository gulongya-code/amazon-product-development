"""Provider-neutral connector error model."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ProviderErrorCode(StrEnum):
    """Stable error categories exposed above provider transports."""

    CONFIGURATION = "CONFIGURATION"
    AUTHENTICATION = "AUTHENTICATION"
    RATE_LIMIT = "RATE_LIMIT"
    TIMEOUT = "TIMEOUT"
    NETWORK = "NETWORK"
    BAD_RESPONSE = "BAD_RESPONSE"
    SCHEMA_MISMATCH = "SCHEMA_MISMATCH"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    FIELD_UNAVAILABLE = "FIELD_UNAVAILABLE"
    DUPLICATE_PROVIDER = "DUPLICATE_PROVIDER"
    PROVIDER_NOT_REGISTERED = "PROVIDER_NOT_REGISTERED"
    RESOLUTION_EXHAUSTED = "RESOLUTION_EXHAUSTED"


class ProviderConnectorError(RuntimeError):
    """Sanitized connector failure independent of third-party exceptions."""

    def __init__(
        self,
        code: ProviderErrorCode,
        message: str,
        *,
        provider_id: str | None = None,
        operation: str | None = None,
        retryable: bool = False,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        if not isinstance(code, ProviderErrorCode):
            raise TypeError("code must be ProviderErrorCode")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message must be non-empty text")
        super().__init__(message)
        self.code = code
        self.provider_id = provider_id
        self.operation = operation
        self.retryable = retryable
        self.details = MappingProxyType(dict(details or {}))

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": str(self),
            "provider_id": self.provider_id,
            "operation": self.operation,
            "retryable": self.retryable,
            "details": dict(self.details),
        }


__all__ = ("ProviderConnectorError", "ProviderErrorCode")
