"""Provider runtime adapters for live acquisition and zero-network fixture replay."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any, Mapping

from amazon_product_intelligence.connectors import (
    CapabilityStatus,
    DataProvider,
    ProviderConfig,
    ProviderConnectorError,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderFetchStatus,
    ProviderRequest,
    ProviderTransport,
    TransportRequest,
    TransportResponse,
)


class FixtureTransport:
    """Serve a sanitized package fixture without importing any network client."""

    def __init__(self, fixture: Mapping[str, Any]) -> None:
        self.fixture = deepcopy(dict(fixture))
        self.execute_count = 0
        self.network_call_count = 0

    @classmethod
    def from_path(cls, path: str | Path) -> "FixtureTransport":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def execute(self, request: TransportRequest) -> TransportResponse:
        self.execute_count += 1
        operations = self.fixture.get("operations", {})
        if request.operation == "asin_info":
            entry = deepcopy(operations.get("asin_info"))
            if not isinstance(entry, dict):
                raise self._missing(request)
            requested = {
                item.get("asin")
                for item in request.parameters.get("entities", ())
                if isinstance(item, Mapping)
            }
            payload = entry.get("payload", {})
            entities = payload.get("entities", ()) if isinstance(payload, Mapping) else ()
            entry["payload"] = {
                "entities": [item for item in entities if item.get("asin") in requested]
            }
            return self._response(entry)
        if request.operation == "asin_keywords":
            asin = request.parameters.get("asin")
            entries = operations.get("asin_keywords", {})
            entry = deepcopy(entries.get(asin)) if isinstance(entries, Mapping) else None
            if not isinstance(entry, dict):
                raise self._missing(request)
            return self._response(entry)
        raise self._missing(request)

    @staticmethod
    def _response(entry: Mapping[str, Any]) -> TransportResponse:
        return TransportResponse(
            status_code=int(entry.get("status_code", 200)),
            payload=deepcopy(entry.get("payload", {})),
            metadata=deepcopy(entry.get("metadata", {})),
        )

    @staticmethod
    def _missing(request: TransportRequest) -> ProviderConnectorError:
        return ProviderConnectorError(
            ProviderErrorCode.FIELD_UNAVAILABLE,
            "offline fixture does not cover the requested provider operation",
            provider_id=request.provider_id,
            operation=request.operation,
        )


class RecordingTransport:
    """Record only safe operation/credit evidence around an injected transport."""

    def __init__(self, wrapped: ProviderTransport) -> None:
        if not isinstance(wrapped, ProviderTransport):
            raise TypeError("wrapped must implement ProviderTransport")
        self.wrapped = wrapped
        self.safe_requests: list[dict[str, Any]] = []
        self.credit_values: list[float] = []

    def execute(self, request: TransportRequest) -> TransportResponse:
        self.safe_requests.append(request.to_safe_dict())
        response = self.wrapped.execute(request)
        credit = response.metadata.get("cost_credits")
        if credit is None and isinstance(response.payload, Mapping):
            credit = response.payload.get("cost_credits")
        if isinstance(credit, (int, float)) and not isinstance(credit, bool):
            self.credit_values.append(float(credit))
        elif isinstance(credit, str):
            try:
                self.credit_values.append(float(credit))
            except ValueError:
                pass
        return response

    @property
    def operation_count(self) -> int:
        return len(self.safe_requests)

    @property
    def operations(self) -> tuple[str, ...]:
        return tuple(str(item["operation"]) for item in self.safe_requests)

    @property
    def credits(self) -> float | None:
        return sum(self.credit_values) if self.credit_values else None


class AcquiredReplayProvider:
    """Replay one acquired adaptation into DataCleaningService without another call."""

    def __init__(self, source: DataProvider, acquired: ProviderFetchResult) -> None:
        if source.provider_id != acquired.provider_id:
            raise ValueError("source provider and acquired result must match")
        self.provider_id = source.provider_id
        self.display_name = f"{source.display_name} acquired replay"
        operation = acquired.capability.operation
        self.capabilities = tuple(
            item for item in source.capabilities if item.operation == operation
        )
        self._capabilities = {item.canonical_field: item for item in self.capabilities}
        self._adaptation = acquired.adaptation

    def capability(self, canonical_field: str):
        return self._capabilities.get(canonical_field)

    def fetch(
        self,
        request: ProviderRequest,
        configuration: ProviderConfig,
    ) -> ProviderFetchResult:
        if configuration.provider_id != self.provider_id or not configuration.enabled:
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "acquired replay provider is not enabled",
                provider_id=self.provider_id,
            )
        capability = self.capability(request.canonical_field)
        if capability is None or capability.capability_status not in {
            CapabilityStatus.AVAILABLE,
            CapabilityStatus.PARTIAL,
        }:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                "acquired replay does not contain the requested capability",
                provider_id=self.provider_id,
            )
        selector = capability.selector
        observations = tuple(
            item
            for item in self._adaptation.bundle.observations
            if selector is not None and selector.matches(item)
        )
        return ProviderFetchResult(
            provider_id=self.provider_id,
            canonical_field=request.canonical_field,
            capability=capability,
            status=(
                ProviderFetchStatus.RETURNED
                if observations
                else ProviderFetchStatus.FIELD_MISSING
            ),
            adaptation=self._adaptation,
            observations=observations,
        )


__all__ = ("AcquiredReplayProvider", "FixtureTransport", "RecordingTransport")
