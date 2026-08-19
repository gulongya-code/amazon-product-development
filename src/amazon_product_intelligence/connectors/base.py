"""Provider-neutral connector contract and adapter-backed implementation."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
import os
from typing import Any, Mapping, Protocol, runtime_checkable

from amazon_product_intelligence.adapters import (
    AdaptationContext,
    AdapterError,
    ProviderAdapter,
)
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    ObservationKind,
    QueryExecutionOutcome,
)

from .errors import ProviderConnectorError, ProviderErrorCode
from .models import (
    CapabilityStatus,
    ProviderCapability,
    ProviderConfig,
    ProviderFetchResult,
    ProviderFetchStatus,
    ProviderRequest,
)
from .transport import (
    NoRetryPolicy,
    ProviderCredential,
    ProviderOperation,
    ProviderTransport,
    RetryPolicy,
    TransportRequest,
    TransportResponse,
)


@runtime_checkable
class DataProvider(Protocol):
    """Minimal replaceable provider interface used by the registry/resolver."""

    provider_id: str
    display_name: str
    capabilities: tuple[ProviderCapability, ...]

    def capability(self, canonical_field: str) -> ProviderCapability | None:
        """Return the provider's declared capability for a Canonical field."""

    def fetch(
        self,
        request: ProviderRequest,
        configuration: ProviderConfig,
    ) -> ProviderFetchResult:
        """Fetch and adapt one field request into existing Canonical contracts."""


class AdapterBackedProvider:
    """Shared connector flow with provider-specific operations supplied as data."""

    def __init__(
        self,
        *,
        provider_id: str,
        display_name: str,
        adapter: ProviderAdapter,
        capabilities: tuple[ProviderCapability, ...],
        operations: tuple[ProviderOperation, ...],
        transport: ProviderTransport,
        environment: Mapping[str, str] | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if adapter.provider != provider_id:
            raise ValueError("adapter provider must match connector provider_id")
        if not isinstance(transport, ProviderTransport):
            raise TypeError("transport must implement ProviderTransport")
        if retry_policy is not None and not isinstance(retry_policy, RetryPolicy):
            raise TypeError("retry_policy must implement RetryPolicy")
        capability_index: dict[str, ProviderCapability] = {}
        for capability in capabilities:
            if capability.provider_id != provider_id:
                raise ValueError("capability provider must match connector provider_id")
            if capability.canonical_field in capability_index:
                raise ValueError(f"duplicate capability {capability.canonical_field}")
            capability_index[capability.canonical_field] = capability
        operation_index: dict[str, ProviderOperation] = {}
        for operation in operations:
            if operation.operation in operation_index:
                raise ValueError(f"duplicate provider operation {operation.operation}")
            if operation.payload_kind not in adapter.supported_payload_kinds:
                raise ValueError(f"operation payload kind {operation.payload_kind} is not supported by adapter")
            operation_index[operation.operation] = operation
        for capability in capabilities:
            if capability.operation is None:
                continue
            operation = operation_index.get(capability.operation)
            if operation is None or operation.payload_kind != capability.payload_kind:
                raise ValueError(f"capability {capability.canonical_field} references an invalid operation")
        self.provider_id = provider_id
        self.display_name = display_name
        self.capabilities = tuple(capabilities)
        self._adapter = adapter
        self._capability_index = capability_index
        self._operations = operation_index
        self._transport = transport
        self._environment = os.environ if environment is None else environment
        self._retry_policy = retry_policy or NoRetryPolicy()

    def capability(self, canonical_field: str) -> ProviderCapability | None:
        return self._capability_index.get(canonical_field)

    def fetch(
        self,
        request: ProviderRequest,
        configuration: ProviderConfig,
    ) -> ProviderFetchResult:
        self._validate_configuration(configuration)
        capability = self.capability(request.canonical_field)
        if capability is None:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                f"provider {self.provider_id} does not declare {request.canonical_field}",
                provider_id=self.provider_id,
            )
        if capability.capability_status not in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                (
                    f"provider {self.provider_id} capability for {request.canonical_field} "
                    f"is {capability.capability_status.value}"
                ),
                provider_id=self.provider_id,
                details={"capability_status": capability.capability_status.value},
            )
        operation = self._operations[capability.operation or ""]
        credential = self._credential(operation, configuration)
        transport_request = TransportRequest(
            provider_id=self.provider_id,
            operation=operation.operation,
            method=operation.method,
            endpoint=operation.endpoint,
            parameters=request.parameters,
            timeout_seconds=configuration.timeout_seconds,
            public_headers=operation.public_headers,
            credential=credential,
        )
        response = self._execute_transport(
            transport_request,
            operation=operation,
            configuration=configuration,
        )
        try:
            context = AdaptationContext(
                provider=self.provider_id,
                payload_kind=operation.payload_kind,
                source_tool=operation.source_tool,
                marketplace=request.marketplace,
                locale=request.locale,
                retrieved_at=request.retrieved_at,
                transformed_at=request.transformed_at,
                collection_run_id=request.collection_run_id,
                sanitized_request=request.parameters,
                currency=request.currency,
            )
            adaptation = self._adapter.adapt(response.payload, context)
        except (AdapterError, ContractValidationError, ValueError) as exc:
            raise ProviderConnectorError(
                ProviderErrorCode.SCHEMA_MISMATCH,
                f"provider {self.provider_id} response could not be adapted",
                provider_id=self.provider_id,
                operation=operation.operation,
                details={"exception_type": type(exc).__name__},
            ) from exc
        if not adaptation.succeeded:
            raise ProviderConnectorError(
                ProviderErrorCode.SCHEMA_MISMATCH,
                f"provider {self.provider_id} response failed audited adapter validation",
                provider_id=self.provider_id,
                operation=operation.operation,
                details={"adapter_error_codes": tuple(item.code for item in adaptation.errors)},
            )
        observations = self._matching_observations(capability, adaptation.bundle.observations)
        if observations:
            status = ProviderFetchStatus.RETURNED
        elif capability.accepts_empty_query and any(
            item.outcome is QueryExecutionOutcome.EXPLICIT_EMPTY
            for item in adaptation.bundle.query_execution_records
        ):
            status = ProviderFetchStatus.EMPTY
        elif adaptation.raw_evidence is not None and adaptation.raw_evidence.response_status == "EMPTY":
            status = ProviderFetchStatus.EMPTY
        else:
            status = ProviderFetchStatus.FIELD_MISSING
        return ProviderFetchResult(
            provider_id=self.provider_id,
            canonical_field=request.canonical_field,
            capability=capability,
            status=status,
            adaptation=adaptation,
            observations=observations,
        )

    def _validate_configuration(self, configuration: ProviderConfig) -> None:
        if configuration.provider_id != self.provider_id:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "provider configuration ID does not match connector",
                provider_id=self.provider_id,
            )
        if not configuration.enabled:
            raise ProviderConnectorError(
                ProviderErrorCode.PROVIDER_UNAVAILABLE,
                f"provider {self.provider_id} is disabled",
                provider_id=self.provider_id,
            )

    def _credential(
        self,
        operation: ProviderOperation,
        configuration: ProviderConfig,
    ) -> ProviderCredential | None:
        if not operation.requires_credential:
            return None
        if configuration.credential_env is None:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                f"provider {self.provider_id} has no credential environment reference",
                provider_id=self.provider_id,
                operation=operation.operation,
            )
        value = self._environment.get(configuration.credential_env)
        if not isinstance(value, str) or not value.strip():
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                f"provider credential is not configured in {configuration.credential_env}",
                provider_id=self.provider_id,
                operation=operation.operation,
                details={"credential_env": configuration.credential_env},
            )
        return ProviderCredential(
            environment_variable=configuration.credential_env,
            injection_name=operation.credential_injection_name or "provider_credential",
            value=value,
        )

    def _execute_transport(
        self,
        request: TransportRequest,
        *,
        operation: ProviderOperation,
        configuration: ProviderConfig,
    ) -> TransportResponse:
        attempt = 1
        while True:
            try:
                response = self._transport.execute(request)
                self._raise_for_response(response, operation.operation)
                return response
            except ProviderConnectorError as exc:
                error = exc
            except TimeoutError as exc:
                error = ProviderConnectorError(
                    ProviderErrorCode.TIMEOUT,
                    f"provider {self.provider_id} request timed out",
                    provider_id=self.provider_id,
                    operation=operation.operation,
                    retryable=True,
                )
                error.__cause__ = exc
            except OSError as exc:
                error = ProviderConnectorError(
                    ProviderErrorCode.NETWORK,
                    f"provider {self.provider_id} network request failed",
                    provider_id=self.provider_id,
                    operation=operation.operation,
                    retryable=True,
                    details={"exception_type": type(exc).__name__},
                )
                error.__cause__ = exc
            if not self._retry_policy.should_retry(
                error,
                attempt=attempt,
                max_attempts=configuration.max_attempts,
            ):
                raise error
            attempt += 1
            if attempt > configuration.max_attempts:
                raise error

    def _raise_for_response(self, response: TransportResponse, operation: str) -> None:
        status = response.status_code
        if 200 <= status <= 299:
            return
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
        safe_details: dict[str, Any] = {"status_code": status}
        if "retry_after_seconds" in response.metadata:
            safe_details["retry_after_seconds"] = response.metadata["retry_after_seconds"]
        raise ProviderConnectorError(
            code,
            f"provider {self.provider_id} returned status {status}",
            provider_id=self.provider_id,
            operation=operation,
            retryable=retryable,
            details=safe_details,
        )

    @staticmethod
    def _matching_observations(
        capability: ProviderCapability,
        observations: tuple[Any, ...],
    ) -> tuple[Any, ...]:
        selector = capability.selector
        if selector is None:
            return ()
        matches: list[Any] = []
        for observation in observations:
            if selector.observation_kind is not None and observation.observation_kind is not selector.observation_kind:
                continue
            if not selector.canonical_names:
                matches.append(observation)
                continue
            if observation.observation_kind is ObservationKind.PRODUCT_FACT:
                canonical_name = getattr(observation, "dimension", None)
            elif observation.observation_kind in {ObservationKind.METRIC, ObservationKind.KEYWORD_METRIC}:
                canonical_name = getattr(observation, "metric", None)
            else:
                canonical_name = None
            if canonical_name in selector.canonical_names:
                matches.append(observation)
        return tuple(matches)


__all__ = ("AdapterBackedProvider", "DataProvider")
