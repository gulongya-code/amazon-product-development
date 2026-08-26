"""Strict ordinary-HTTP Sorftime client for the SP-040B DTO boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from typing import Any, Generic, Mapping, TypeVar
from urllib.parse import urlsplit

from .errors import ProviderConnectorError, ProviderErrorCode
from .models import ProviderConfig
from .sorftime_dtos_v0_1 import (
    SorftimeAsinRequestKeywordRequest,
    SorftimeAsinRequestKeywordResponse,
    SorftimeProductRequest,
    SorftimeProductRequestResponse,
    SorftimeProductVariationsRequest,
    SorftimeProductVariationsResponse,
    parse_asin_request_keyword_response,
    parse_product_request_response,
    parse_product_variations_response,
)
from .transport import (
    HttpJsonTransport,
    NoRetryPolicy,
    ProviderCredential,
    ProviderOperation,
    ProviderTransport,
    RetryPolicy,
    TransportRequest,
)


SORFTIME_ORIGIN = "https://standardapi.sorftime.com"
SORFTIME_CREDENTIAL_ENV = "SORFTIME_API_KEY"
SORFTIME_CONTENT_TYPE = "application/json;charset=UTF-8"


def validate_sorftime_origin(origin: str) -> str:
    """Accept only the exact credential-safe first-party Sorftime origin."""

    if not isinstance(origin, str) or origin != SORFTIME_ORIGIN:
        raise ProviderConnectorError(
            ProviderErrorCode.CONFIGURATION,
            "Sorftime HTTP origin must match the pinned first-party origin",
            provider_id="sorftime",
            details={"origin_status": "REJECTED"},
        )
    parts = urlsplit(origin)
    if (
        parts.scheme != "https"
        or parts.hostname != "standardapi.sorftime.com"
        or parts.netloc != "standardapi.sorftime.com"
        or parts.path
        or parts.query
        or parts.fragment
        or parts.username
        or parts.password
        or parts.port is not None
        or any(ord(character) < 33 or ord(character) == 127 for character in origin)
    ):
        raise ProviderConnectorError(
            ProviderErrorCode.CONFIGURATION,
            "Sorftime HTTP origin failed pinned-origin validation",
            provider_id="sorftime",
            details={"origin_status": "REJECTED"},
        )
    return origin


def _operation(operation: str, payload_kind: str, endpoint: str) -> ProviderOperation:
    return ProviderOperation(
        operation=operation,
        payload_kind=payload_kind,
        source_tool=operation,
        method="POST",
        endpoint=endpoint,
        requires_credential=True,
        credential_injection_name="Authorization",
        credential_value_prefix="BasicAuth ",
        public_headers={"Content-Type": SORFTIME_CONTENT_TYPE},
        query_parameters={"domain": 1},
    )


PRODUCT_REQUEST_OPERATION = _operation(
    "ProductRequest", "sorftime_product_request_dto", "/api/ProductRequest"
)
PRODUCT_VARIATIONS_OPERATION = _operation(
    "ProductVariations", "sorftime_product_variations_dto", "/api/ProductVariations"
)
ASIN_REQUEST_KEYWORD_OPERATION = _operation(
    "ASINRequestKeyword",
    "sorftime_asin_request_keyword_dto",
    "/api/ASINRequestKeyword",
)
SORFTIME_HTTP_OPERATIONS = (
    PRODUCT_REQUEST_OPERATION,
    PRODUCT_VARIATIONS_OPERATION,
    ASIN_REQUEST_KEYWORD_OPERATION,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeUsageEvidence:
    """Credential-free runtime counters; never Canonical business evidence."""

    request_consumed: int | None
    request_left: int | None

    def to_safe_dict(self) -> dict[str, int | None]:
        return {
            "request_consumed": self.request_consumed,
            "request_left": self.request_left,
        }


_ResponseT = TypeVar(
    "_ResponseT",
    SorftimeProductRequestResponse,
    SorftimeProductVariationsResponse,
    SorftimeAsinRequestKeywordResponse,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SorftimeOperationResult(Generic[_ResponseT]):
    """Typed success plus runtime-only usage evidence."""

    operation: str
    response: _ResponseT = field(repr=False)
    usage: SorftimeUsageEvidence

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "operation": self.operation,
            "response_type": type(self.response).__name__,
            "usage": self.usage.to_safe_dict(),
        }


class SorftimeClient:
    """Narrow client exposing only the three accepted typed operations.

    The old arbitrary endpoint/base-URL/X-Api-Key API is intentionally absent.
    Each call performs one attempt unless an explicit provider-neutral retry
    policy is injected.
    """

    source = "sorftime"

    def __init__(
        self,
        *,
        transport: ProviderTransport | None = None,
        environment: Mapping[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
        base_origin: str = SORFTIME_ORIGIN,
        opener: Any | None = None,
    ) -> None:
        origin = validate_sorftime_origin(base_origin)
        if transport is None:
            options = {} if opener is None else {"opener": opener}
            transport = HttpJsonTransport({"sorftime": origin}, **options)
        elif isinstance(transport, HttpJsonTransport):
            validate_sorftime_origin(transport.base_origin("sorftime") or "")
        if not isinstance(transport, ProviderTransport):
            raise TypeError("transport must implement ProviderTransport")
        if retry_policy is not None and not isinstance(retry_policy, RetryPolicy):
            raise TypeError("retry_policy must implement RetryPolicy")
        self._transport = transport
        self._environment = os.environ if environment is None else environment
        self._retry_policy = retry_policy or NoRetryPolicy()

    def product_request(
        self,
        request: SorftimeProductRequest,
        configuration: ProviderConfig,
    ) -> SorftimeOperationResult[SorftimeProductRequestResponse]:
        if type(request) is not SorftimeProductRequest:
            raise TypeError("ProductRequest requires the exact SP-040B request DTO")
        return self._execute(request, PRODUCT_REQUEST_OPERATION, configuration)

    def product_variations(
        self,
        request: SorftimeProductVariationsRequest,
        configuration: ProviderConfig,
    ) -> SorftimeOperationResult[SorftimeProductVariationsResponse]:
        if type(request) is not SorftimeProductVariationsRequest:
            raise TypeError("ProductVariations requires the exact SP-040B request DTO")
        return self._execute(request, PRODUCT_VARIATIONS_OPERATION, configuration)

    def asin_request_keyword(
        self,
        request: SorftimeAsinRequestKeywordRequest,
        configuration: ProviderConfig,
    ) -> SorftimeOperationResult[SorftimeAsinRequestKeywordResponse]:
        if type(request) is not SorftimeAsinRequestKeywordRequest:
            raise TypeError("ASINRequestKeyword requires the exact SP-040B request DTO")
        return self._execute(request, ASIN_REQUEST_KEYWORD_OPERATION, configuration)

    def _execute(self, request: Any, operation: ProviderOperation, configuration: ProviderConfig) -> Any:
        credential = self._credential(configuration, operation)
        transport_request = TransportRequest(
            provider_id="sorftime",
            operation=operation.operation,
            method=operation.method,
            endpoint=operation.endpoint,
            parameters=request.to_provider_body(),
            timeout_seconds=configuration.timeout_seconds,
            public_headers=operation.public_headers,
            query_parameters=operation.query_parameters,
            credential=credential,
        )
        attempt = 1
        while True:
            try:
                raw = self._transport.execute(transport_request)
                response = self._parse(operation.operation, request, raw.payload, raw.status_code)
            except ProviderConnectorError as exc:
                error = exc
            except TimeoutError:
                error = ProviderConnectorError(
                    ProviderErrorCode.TIMEOUT,
                    "Sorftime HTTP request timed out",
                    provider_id="sorftime",
                    operation=operation.operation,
                    retryable=True,
                )
            except OSError as exc:
                error = ProviderConnectorError(
                    ProviderErrorCode.NETWORK,
                    "Sorftime HTTP network request failed",
                    provider_id="sorftime",
                    operation=operation.operation,
                    retryable=True,
                    details={"exception_type": type(exc).__name__},
                )
            else:
                return SorftimeOperationResult(
                    operation=operation.operation,
                    response=response,
                    usage=SorftimeUsageEvidence(
                        request_consumed=response.RequestConsumed,
                        request_left=response.RequestLeft,
                    ),
                )
            if not self._retry_policy.should_retry(
                error, attempt=attempt, max_attempts=configuration.max_attempts
            ):
                raise error from None
            attempt += 1
            if attempt > configuration.max_attempts:
                raise error from None

    def _credential(
        self, configuration: ProviderConfig, operation: ProviderOperation
    ) -> ProviderCredential:
        if configuration.provider_id != "sorftime":
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "provider configuration ID does not match Sorftime client",
                provider_id="sorftime",
                operation=operation.operation,
            )
        if not configuration.enabled:
            raise ProviderConnectorError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                "Sorftime provider is disabled",
                provider_id="sorftime",
                operation=operation.operation,
            )
        if configuration.credential_env != SORFTIME_CREDENTIAL_ENV:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "Sorftime credential environment reference must be SORFTIME_API_KEY",
                provider_id="sorftime",
                operation=operation.operation,
                details={"credential_env_status": "REJECTED"},
            )
        value = self._environment.get(SORFTIME_CREDENTIAL_ENV)
        if not isinstance(value, str) or not value or value != value.strip():
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "Sorftime credential is missing or malformed",
                provider_id="sorftime",
                operation=operation.operation,
                details={"credential_env": SORFTIME_CREDENTIAL_ENV},
            )
        try:
            return ProviderCredential(
                environment_variable=SORFTIME_CREDENTIAL_ENV,
                injection_name=operation.credential_injection_name or "Authorization",
                value=value,
                value_prefix=operation.credential_value_prefix,
            )
        except ValueError as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "Sorftime credential is missing or malformed",
                provider_id="sorftime",
                operation=operation.operation,
                details={"credential_env": SORFTIME_CREDENTIAL_ENV},
            ) from exc

    @staticmethod
    def _parse(operation: str, request: Any, payload: Any, status_code: int) -> Any:
        if operation == "ProductRequest":
            return parse_product_request_response(payload, request, http_status=status_code)
        if operation == "ProductVariations":
            return parse_product_variations_response(payload, request, http_status=status_code)
        if operation == "ASINRequestKeyword":
            return parse_asin_request_keyword_response(payload, request, http_status=status_code)
        raise ProviderConnectorError(
            ProviderErrorCode.CONFIGURATION,
            "Sorftime operation is not part of the accepted HTTP contract",
            provider_id="sorftime",
        )


__all__ = (
    "ASIN_REQUEST_KEYWORD_OPERATION",
    "PRODUCT_REQUEST_OPERATION",
    "PRODUCT_VARIATIONS_OPERATION",
    "SORFTIME_CONTENT_TYPE",
    "SORFTIME_CREDENTIAL_ENV",
    "SORFTIME_HTTP_OPERATIONS",
    "SORFTIME_ORIGIN",
    "SorftimeClient",
    "SorftimeOperationResult",
    "SorftimeUsageEvidence",
    "validate_sorftime_origin",
)
