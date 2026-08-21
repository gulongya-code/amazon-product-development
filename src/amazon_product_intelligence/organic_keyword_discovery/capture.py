"""Explicit-live XiYou capture boundary reused by the organic discovery pilot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from amazon_product_intelligence.adapters import AdaptationContext, XiYouAdapterV0_1
from amazon_product_intelligence.connectors import (
    HttpJsonTransport,
    ProviderConfig,
    ProviderConnectorError,
    ProviderCredential,
    ProviderErrorCode,
    ProviderRequest,
    ProviderTransport,
    TransportRequest,
    TransportResponse,
    XIYOU_OPERATIONS,
    XiYouProvider,
)
from amazon_product_intelligence.contracts import CanonicalEvidenceBundle, deterministic_id


class _CapturedPayloadTransport:
    def __init__(self, operation: str, payload: Mapping[str, Any]) -> None:
        self.operation = operation
        self.payload = dict(payload)

    def execute(self, request: TransportRequest) -> TransportResponse:
        if request.operation != self.operation:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                "captured payload does not cover this operation",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        return TransportResponse(status_code=200, payload=self.payload)


@dataclass(frozen=True, slots=True)
class CapturedXiYouOperation:
    operation: str
    parameters: Mapping[str, Any]
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any]
    bundle: CanonicalEvidenceBundle
    request_ref: str
    response_ref: str

    @property
    def cost_credits(self) -> int | None:
        value = self.metadata.get("cost_credits")
        if value is None:
            value = self.payload.get("cost_credits")
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    @property
    def x_cost_credits(self) -> str | None:
        value = self.metadata.get("cost_credits")
        return str(value) if value is not None else None

    @property
    def data(self) -> Mapping[str, Any]:
        nested = self.payload.get("data")
        return nested if isinstance(nested, Mapping) else self.payload


class XiYouLiveCaptureClient:
    """Perform only explicitly requested XiYou calls and adapt captured payloads."""

    def __init__(
        self,
        *,
        environment: Mapping[str, str],
        transport: ProviderTransport | None = None,
        retrieved_at: str | None = None,
    ) -> None:
        self.environment = environment
        self.retrieved_at = retrieved_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self._operations = {item.operation: item for item in XIYOU_OPERATIONS}
        self._transport = transport or HttpJsonTransport(
            {"xiyou": environment.get("XIYOU_API_BASE_URL", "https://openapi.xydc.com")}
        )

    def capture(
        self,
        *,
        operation: str,
        canonical_field: str,
        parameters: Mapping[str, Any],
    ) -> CapturedXiYouOperation:
        api_key = self.environment.get("XIYOU_API_KEY")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "XIYOU_API_KEY is required for an explicit live organic discovery run",
                provider_id="xiyou",
                operation=operation,
            )
        contract = self._operations.get(operation)
        if contract is None:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "requested XiYou operation is not registered",
                provider_id="xiyou",
                operation=operation,
            )
        collection_run_id = deterministic_id(
            "collection",
            {
                "provider": "xiyou",
                "operation": operation,
                "parameters": parameters,
                "retrieved_at": self.retrieved_at,
            },
        )
        response = self._transport.execute(
            TransportRequest(
                provider_id="xiyou",
                operation=operation,
                method=contract.method,
                endpoint=contract.endpoint,
                parameters=parameters,
                timeout_seconds=30.0,
                public_headers=contract.public_headers,
                credential=ProviderCredential(
                    environment_variable="XIYOU_API_KEY",
                    injection_name="X-Api-Key",
                    value=api_key,
                ),
            )
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                f"provider returned HTTP {response.status_code}",
                provider_id="xiyou",
                operation=operation,
            )
        if not isinstance(response.payload, Mapping):
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                "provider response root is not an object",
                provider_id="xiyou",
                operation=operation,
            )
        payload = dict(response.payload)
        if operation.endswith("_monthly"):
            adaptation = XiYouAdapterV0_1().adapt(
                payload,
                AdaptationContext(
                    provider="xiyou",
                    payload_kind=contract.payload_kind,
                    source_tool=contract.source_tool,
                    marketplace=str(parameters.get("country", "US")),
                    locale="en-us",
                    retrieved_at=self.retrieved_at,
                    transformed_at=self.retrieved_at,
                    collection_run_id=collection_run_id,
                    sanitized_request=parameters,
                    currency="USD",
                ),
            )
            if not adaptation.succeeded:
                raise ProviderConnectorError(
                    ProviderErrorCode.SCHEMA_MISMATCH,
                    "monthly provider response failed audited adapter validation",
                    provider_id="xiyou",
                    operation=operation,
                    details={
                        "adapter_error_codes": tuple(
                            item.code for item in adaptation.errors
                        )
                    },
                )
            bundle = adaptation.bundle.validate()
        else:
            provider = XiYouProvider(
                _CapturedPayloadTransport(operation, payload),
                environment={"XIYOU_API_KEY": "captured-payload-only"},
            )
            configuration = ProviderConfig(
                provider_id="xiyou",
                enabled=True,
                priority=1,
                credential_env="XIYOU_API_KEY",
                timeout_seconds=1.0,
                max_attempts=1,
            )
            fetched = provider.fetch(
                ProviderRequest(
                    canonical_field=canonical_field,
                    parameters=parameters,
                    marketplace=str(parameters.get("country", "US")),
                    locale="en-us",
                    retrieved_at=self.retrieved_at,
                    transformed_at=self.retrieved_at,
                    collection_run_id=collection_run_id,
                    currency="USD",
                ),
                configuration,
            )
            bundle = fetched.adaptation.bundle.validate()
        response_ref = next(iter(bundle.raw_evidence_references), "")
        if not response_ref:
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                "adapted provider response has no raw evidence reference",
                provider_id="xiyou",
                operation=operation,
            )
        query_refs = tuple(item.query_execution_id for item in bundle.query_execution_records)
        request_ref = query_refs[0] if len(query_refs) == 1 else collection_run_id
        return CapturedXiYouOperation(
            operation=operation,
            parameters=dict(parameters),
            payload=payload,
            metadata=dict(response.metadata),
            bundle=bundle,
            request_ref=request_ref,
            response_ref=response_ref,
        )


__all__ = ("CapturedXiYouOperation", "XiYouLiveCaptureClient")
