"""Low-level authenticated JSON API client shared by provider connectors."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from copy import deepcopy
import logging
import math
import os
import re
from typing import Any, Mapping
from urllib.parse import urlsplit

from amazon_product_intelligence.schemas import APIResponse

from .errors import ProviderConnectorError, ProviderErrorCode
from .transport import (
    HttpJsonTransport,
    ProviderCredential,
    ProviderTransport,
    TransportRequest,
    TransportResponse,
)


_SOURCE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_SENSITIVE_KEYS = {
    "api-key",
    "api_key",
    "apikey",
    "access-token",
    "access_token",
    "authorization",
    "cookie",
    "password",
    "proxy-authorization",
    "secret",
    "token",
    "x-api-key",
}


def _contains_sensitive_key(value: Any) -> str | None:
    if isinstance(value, MappingABC):
        for key, item in value.items():
            normalized = str(key).strip().casefold()
            if normalized in _SENSITIVE_KEYS:
                return str(key)
            nested = _contains_sensitive_key(item)
            if nested is not None:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _contains_sensitive_key(item)
            if nested is not None:
                return nested
    return None


class BaseAPIClient:
    """Authenticated, retry-bounded client with an injectable I/O boundary.

    Credential values are accepted only from the configured environment
    variable. A provider base URL is also environment-owned whenever the real
    HTTP transport is used. Tests inject a transport and therefore never touch
    the network.
    """

    def __init__(
        self,
        *,
        source: str,
        api_key_env: str,
        base_url_env: str,
        credential_header: str,
        transport: ProviderTransport | None = None,
        default_headers: Mapping[str, str] | None = None,
        timeout_seconds: float = 10.0,
        max_attempts: int = 3,
        logger: logging.Logger | None = None,
    ) -> None:
        if not isinstance(source, str) or not _SOURCE_ID.fullmatch(source):
            raise ValueError("source must be a lowercase machine-readable identifier")
        for name, value in (
            ("api_key_env", api_key_env),
            ("base_url_env", base_url_env),
            ("credential_header", credential_header),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        if not isinstance(timeout_seconds, (int, float)) or not math.isfinite(timeout_seconds):
            raise ValueError("timeout_seconds must be finite")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
            raise ValueError("max_attempts must be between 1 and 5")

        api_key = os.environ.get(api_key_env)
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                f"provider credential is not configured in {api_key_env}",
                provider_id=source,
                details={"credential_env": api_key_env},
            )

        headers = dict(default_headers or {})
        sensitive_header = _contains_sensitive_key(headers)
        if sensitive_header is not None:
            raise ValueError("default_headers must not contain authentication material")

        if transport is None:
            base_url = os.environ.get(base_url_env)
            if not isinstance(base_url, str) or not base_url.strip():
                raise ProviderConnectorError(
                    ProviderErrorCode.CONFIGURATION,
                    f"provider base URL is not configured in {base_url_env}",
                    provider_id=source,
                    details={"base_url_env": base_url_env},
                )
            transport = HttpJsonTransport({source: base_url.strip()})
        if not isinstance(transport, ProviderTransport):
            raise TypeError("transport must implement ProviderTransport")

        self.source = source
        self.api_key_env = api_key_env
        self.base_url_env = base_url_env
        self.timeout_seconds = float(timeout_seconds)
        self.max_attempts = max_attempts
        self._transport = transport
        self._default_headers = headers
        self._credential = ProviderCredential(
            environment_variable=api_key_env,
            injection_name=credential_header,
            value=api_key.strip(),
        )
        self._logger = logger or logging.getLogger(
            f"amazon_product_intelligence.connectors.{source}"
        )

    def request(
        self,
        method: str,
        endpoint: str,
        *,
        operation: str = "request",
        parameters: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> APIResponse:
        """Execute and standardize one request with bounded transient retries."""

        normalized_method = self._validate_request(method, endpoint, operation)
        safe_parameters = deepcopy(dict(parameters or {}))
        sensitive_parameter = _contains_sensitive_key(safe_parameters)
        if sensitive_parameter is not None:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                f"request parameters must not contain credential field {sensitive_parameter!r}",
                provider_id=self.source,
                operation=operation,
            )
        public_headers = {**self._default_headers, **dict(headers or {})}
        sensitive_header = _contains_sensitive_key(public_headers)
        if sensitive_header is not None:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "request headers must not contain authentication material",
                provider_id=self.source,
                operation=operation,
            )

        transport_request = TransportRequest(
            provider_id=self.source,
            operation=operation,
            method=normalized_method,
            endpoint=endpoint,
            parameters=safe_parameters,
            timeout_seconds=self.timeout_seconds,
            public_headers=public_headers,
            credential=self._credential,
        )
        attempt = 1
        while True:
            self._logger.info(
                "provider request started source=%s operation=%s attempt=%d",
                self.source,
                operation,
                attempt,
            )
            try:
                raw_response = self._transport.execute(transport_request)
                response = self._normalize_response(
                    raw_response,
                    operation=operation,
                    method=normalized_method,
                    endpoint=endpoint,
                    parameters=safe_parameters,
                    attempt=attempt,
                )
                self._raise_for_status(response)
            except ProviderConnectorError as exc:
                error = exc
            except (TimeoutError,) as exc:
                error = ProviderConnectorError(
                    ProviderErrorCode.TIMEOUT,
                    f"provider {self.source} request timed out",
                    provider_id=self.source,
                    operation=operation,
                    retryable=True,
                )
                error.__cause__ = exc
            except OSError as exc:
                error = ProviderConnectorError(
                    ProviderErrorCode.NETWORK,
                    f"provider {self.source} network request failed",
                    provider_id=self.source,
                    operation=operation,
                    retryable=True,
                    details={"exception_type": type(exc).__name__},
                )
                error.__cause__ = exc
            else:
                self._logger.info(
                    "provider request succeeded source=%s operation=%s status=%d attempt=%d",
                    self.source,
                    operation,
                    response.status_code,
                    attempt,
                )
                return response

            if not error.retryable or attempt >= self.max_attempts:
                self._logger.warning(
                    "provider request failed source=%s operation=%s code=%s attempt=%d",
                    self.source,
                    operation,
                    error.code.value,
                    attempt,
                )
                raise error
            self._logger.info(
                "provider request retrying source=%s operation=%s code=%s next_attempt=%d",
                self.source,
                operation,
                error.code.value,
                attempt + 1,
            )
            attempt += 1

    def mock_call(
        self,
        payload: Any,
        *,
        status_code: int = 200,
        operation: str = "mock",
        request_metadata: Mapping[str, Any] | None = None,
    ) -> APIResponse:
        """Standardize an in-memory response without executing a transport."""

        raw_response = TransportResponse(status_code=status_code, payload=payload)
        metadata = {
            "operation": operation,
            "method": "MOCK",
            "endpoint": "mock://local",
            "parameters": {},
            "timeout_seconds": self.timeout_seconds,
            "attempt": 1,
            "status_code": status_code,
            **dict(request_metadata or {}),
        }
        sensitive_key = _contains_sensitive_key(metadata)
        if sensitive_key is not None:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "mock request metadata must not contain authentication material",
                provider_id=self.source,
                operation=operation,
            )
        response = APIResponse(
            source=self.source,
            status_code=raw_response.status_code,
            request_metadata=metadata,
            payload=raw_response.payload,
        )
        self._raise_for_status(response)
        return response

    mock_request = mock_call

    @staticmethod
    def _validate_request(method: str, endpoint: str, operation: str) -> str:
        if not isinstance(method, str) or method.strip().upper() not in {"GET", "POST"}:
            raise ValueError("method must be GET or POST")
        if not isinstance(operation, str) or not operation.strip():
            raise ValueError("operation must be non-empty text")
        if not isinstance(endpoint, str) or not endpoint.strip():
            raise ValueError("endpoint must be non-empty text")
        parts = urlsplit(endpoint)
        if (
            not endpoint.startswith("/")
            or endpoint.startswith("//")
            or parts.scheme
            or parts.netloc
            or parts.query
            or parts.fragment
        ):
            raise ValueError("endpoint must be a relative absolute-path without query data")
        return method.strip().upper()

    def _normalize_response(
        self,
        response: TransportResponse,
        *,
        operation: str,
        method: str,
        endpoint: str,
        parameters: Mapping[str, Any],
        attempt: int,
    ) -> APIResponse:
        if not isinstance(response, TransportResponse):
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                f"provider {self.source} returned an invalid transport response",
                provider_id=self.source,
                operation=operation,
            )
        request_metadata = {
            "operation": operation,
            "method": method,
            "endpoint": endpoint,
            "parameters": deepcopy(dict(parameters)),
            "timeout_seconds": self.timeout_seconds,
            "attempt": attempt,
            "status_code": response.status_code,
        }
        try:
            return APIResponse(
                source=self.source,
                status_code=response.status_code,
                request_metadata=request_metadata,
                payload=response.payload,
            )
        except ValueError as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                f"provider {self.source} returned a non-JSON response",
                provider_id=self.source,
                operation=operation,
                details={"status_code": response.status_code},
            ) from exc

    def _raise_for_status(self, response: APIResponse) -> None:
        status = response.status_code
        if 200 <= status <= 299:
            return
        operation = str(response.request_metadata.get("operation", "request"))
        if status in {401, 403}:
            code = ProviderErrorCode.AUTHENTICATION
            retryable = False
        elif status == 429:
            code = ProviderErrorCode.RATE_LIMIT
            retryable = True
        elif status in {408, 504}:
            code = ProviderErrorCode.TIMEOUT
            retryable = True
        elif status >= 500:
            code = ProviderErrorCode.PROVIDER_UNAVAILABLE
            retryable = True
        else:
            code = ProviderErrorCode.BAD_RESPONSE
            retryable = False
        raise ProviderConnectorError(
            code,
            f"provider {self.source} returned status {status}",
            provider_id=self.source,
            operation=operation,
            retryable=retryable,
            details={"status_code": status},
        )


__all__ = ("BaseAPIClient",)
