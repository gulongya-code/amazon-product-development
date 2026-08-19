"""Injected transport and bounded retry extension points for providers."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import json
import re
import socket
from types import MappingProxyType
from typing import Any, Mapping, Protocol, runtime_checkable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .errors import ProviderConnectorError, ProviderErrorCode


_SECRET_HEADER_NAMES = {
    "api-key",
    "authorization",
    "cookie",
    "proxy-authorization",
    "x-api-key",
}
_HTTP_HEADER_NAME = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


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
        if not _HTTP_HEADER_NAME.fullmatch(self.injection_name):
            raise ValueError("injection_name must be a valid HTTP-style header name")
        if "\r" in self.value or "\n" in self.value:
            raise ValueError("credential value must not contain header control characters")

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
        if any(
            not _HTTP_HEADER_NAME.fullmatch(key) or "\r" in value or "\n" in value
            for key, value in headers.items()
        ):
            raise ValueError("public headers must be valid and contain no control characters")
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


class BoundedTransientRetryPolicy:
    """Retry only transient failures and never exceed provider configuration."""

    _RETRYABLE_CODES = {
        ProviderErrorCode.NETWORK,
        ProviderErrorCode.TIMEOUT,
        ProviderErrorCode.PROVIDER_UNAVAILABLE,
    }

    def should_retry(
        self,
        error: ProviderConnectorError,
        *,
        attempt: int,
        max_attempts: int,
    ) -> bool:
        return (
            attempt < max_attempts
            and error.retryable
            and error.code in self._RETRYABLE_CODES
        )


def _json_ready(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, MappingABC):
        return {str(key): _json_ready(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    raise TypeError(f"unsupported request value type {type(value).__name__}")


class HttpJsonTransport:
    """Small production JSON/HTTPS boundary with secret-safe failures.

    Retry decisions intentionally remain in ``AdapterBackedProvider`` so the
    transport performs exactly one network attempt per call and stays injectable.
    """

    def __init__(
        self,
        base_urls: Mapping[str, str],
        *,
        opener: Any = urlopen,
        max_response_bytes: int = 2_000_000,
    ) -> None:
        if not isinstance(max_response_bytes, int) or max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be a positive integer")
        normalized: dict[str, str] = {}
        for provider_id, raw_url in base_urls.items():
            parts = urlsplit(raw_url)
            if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
                raise ValueError("provider base URLs must be credential-free HTTPS origins")
            if parts.path not in {"", "/"} or parts.query or parts.fragment:
                raise ValueError("provider base URLs must be origins without path, query, or fragment data")
            normalized[provider_id] = raw_url.rstrip("/") + "/"
        self._base_urls = MappingProxyType(normalized)
        self._opener = opener
        self._max_response_bytes = max_response_bytes

    def execute(self, request: TransportRequest) -> TransportResponse:
        if request.method not in {"GET", "POST"}:
            raise ProviderConnectorError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "provider operation has no verified HTTP transport contract",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        base_url = self._base_urls.get(request.provider_id)
        if base_url is None:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "provider HTTP base URL is not configured",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        endpoint_parts = urlsplit(request.endpoint)
        if (
            not request.endpoint.startswith("/")
            or request.endpoint.startswith("//")
            or endpoint_parts.scheme
            or endpoint_parts.netloc
            or endpoint_parts.query
            or endpoint_parts.fragment
        ):
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "provider endpoint must be a relative absolute-path reference",
                provider_id=request.provider_id,
                operation=request.operation,
            )

        headers = {"Accept": "application/json", **dict(request.public_headers)}
        data: bytes | None = None
        if request.method == "POST":
            headers["Content-Type"] = "application/json"
            try:
                data = json.dumps(
                    _json_ready(request.parameters),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            except (TypeError, ValueError) as exc:
                raise ProviderConnectorError(
                    ProviderErrorCode.CONFIGURATION,
                    "provider request parameters are not JSON serializable",
                    provider_id=request.provider_id,
                    operation=request.operation,
                ) from exc
        if request.credential is not None:
            headers[request.credential.injection_name] = request.credential.value

        http_request = Request(
            urljoin(base_url, request.endpoint.lstrip("/")),
            data=data,
            headers=headers,
            method=request.method,
        )
        try:
            response = self._opener(http_request, timeout=request.timeout_seconds)
            with response as stream:
                return self._response(
                    status_code=int(getattr(stream, "status", 200)),
                    headers=getattr(stream, "headers", {}),
                    body=self._read_bounded(stream, request),
                    request=request,
                    strict_json=True,
                )
        except HTTPError as exc:
            body = self._read_bounded(exc, request)
            return self._response(
                status_code=exc.code,
                headers=exc.headers or {},
                body=body,
                request=request,
                strict_json=False,
            )
        except (socket.timeout, TimeoutError) as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.TIMEOUT,
                "provider request timed out",
                provider_id=request.provider_id,
                operation=request.operation,
                retryable=True,
            ) from exc
        except (URLError, OSError) as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.NETWORK,
                "provider network request failed",
                provider_id=request.provider_id,
                operation=request.operation,
                retryable=True,
                details={"exception_type": type(exc).__name__},
            ) from exc

    def _read_bounded(self, stream: Any, request: TransportRequest) -> bytes:
        body = stream.read(self._max_response_bytes + 1)
        if len(body) > self._max_response_bytes:
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                "provider response exceeded the configured size limit",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        return body

    @staticmethod
    def _response(
        *,
        status_code: int,
        headers: Any,
        body: bytes,
        request: TransportRequest,
        strict_json: bool,
    ) -> TransportResponse:
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            if strict_json:
                raise ProviderConnectorError(
                    ProviderErrorCode.BAD_RESPONSE,
                    "provider returned an invalid JSON response",
                    provider_id=request.provider_id,
                    operation=request.operation,
                    details={"status_code": status_code},
                ) from exc
            payload = {}
        metadata: dict[str, Any] = {}
        retry_after = headers.get("Retry-After") if hasattr(headers, "get") else None
        if isinstance(retry_after, str) and retry_after.strip().isdigit():
            metadata["retry_after_seconds"] = int(retry_after.strip())
        for header, key in (("X-Trace-Id", "trace_id"), ("X-Cost-Credits", "cost_credits")):
            value = headers.get(header) if hasattr(headers, "get") else None
            if isinstance(value, str) and value.strip():
                metadata[key] = value.strip()
        return TransportResponse(status_code=status_code, payload=payload, metadata=metadata)


__all__ = (
    "BoundedTransientRetryPolicy",
    "HttpJsonTransport",
    "NoRetryPolicy",
    "ProviderCredential",
    "ProviderOperation",
    "ProviderTransport",
    "RetryPolicy",
    "TransportRequest",
    "TransportResponse",
)
