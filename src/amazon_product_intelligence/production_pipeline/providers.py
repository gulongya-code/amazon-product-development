"""Provider runtime adapters for live acquisition and zero-network fixture replay."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
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


XIYOU_REVERSE_KEYWORD_PAGE = 1
XIYOU_REVERSE_KEYWORD_PAGE_SIZE = 20
XIYOU_REVERSE_KEYWORD_PERIOD = "last7days"
XIYOU_REVERSE_KEYWORD_SORT_FIELD = "traffic"
XIYOU_REVERSE_KEYWORD_SORT_ORDER = "desc"

_SAFE_XIYOU_PROVIDER_REASONS = frozenset(
    {
        "APICredentialUnavailable",
        "APICredentialNotFound",
        "CreditBalanceInsufficient",
        "CreditAccountUnavailable",
        "CreditAccountNotFound",
    }
)


def xiyou_reverse_keyword_parameters(*, asin: str, marketplace: str) -> dict[str, Any]:
    """Return the frozen, cost-bounded reverse-keyword request used by SP-032."""

    return {
        "asin": asin,
        "country": marketplace,
        "page": XIYOU_REVERSE_KEYWORD_PAGE,
        "pageSize": XIYOU_REVERSE_KEYWORD_PAGE_SIZE,
        "period": XIYOU_REVERSE_KEYWORD_PERIOD,
        "sort": {
            "field": XIYOU_REVERSE_KEYWORD_SORT_FIELD,
            "order": XIYOU_REVERSE_KEYWORD_SORT_ORDER,
        },
    }


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
        if request.operation in {"ProductRequest", "ASINRequestKeyword"}:
            asin = request.parameters.get("ASIN")
            entries = operations.get(request.operation, {})
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
        self.confirmed_request_usage: list[tuple[int, int]] = []
        self.attempt_records: list[RecordedTransportAttempt] = []

    def execute(self, request: TransportRequest) -> TransportResponse:
        safe_request = request.to_safe_dict()
        self.safe_requests.append(safe_request)
        try:
            response = self.wrapped.execute(request)
        except ProviderConnectorError as exc:
            self.attempt_records.append(
                RecordedTransportAttempt(
                    safe_request=safe_request,
                    status="FAILED",
                    provider_error_code=exc.code.value,
                    credits=self._error_credit(exc),
                    response=None,
                )
            )
            if self.attempt_records[-1].credits is not None:
                self.credit_values.append(self.attempt_records[-1].credits)
            raise
        except TimeoutError:
            self.attempt_records.append(
                RecordedTransportAttempt(
                    safe_request=safe_request,
                    status="FAILED",
                    provider_error_code=ProviderErrorCode.TIMEOUT.value,
                    credits=None,
                    response=None,
                )
            )
            raise
        except OSError:
            self.attempt_records.append(
                RecordedTransportAttempt(
                    safe_request=safe_request,
                    status="FAILED",
                    provider_error_code=ProviderErrorCode.NETWORK.value,
                    credits=None,
                    response=None,
                )
            )
            raise
        credit = self._response_credit(response)
        error_code = self._response_error_code(response.status_code)
        self.attempt_records.append(
            RecordedTransportAttempt(
                safe_request=safe_request,
                status="SUCCEEDED" if error_code is None else "FAILED",
                provider_error_code=error_code,
                credits=credit,
                response=response,
            )
        )
        if credit is not None:
            self.credit_values.append(credit)
        return response

    @staticmethod
    def _response_credit(response: TransportResponse) -> float | None:
        credit = response.metadata.get("cost_credits")
        if credit is None and isinstance(response.payload, Mapping):
            credit = response.payload.get("cost_credits")
        if isinstance(credit, (int, float)) and not isinstance(credit, bool):
            return float(credit)
        elif isinstance(credit, str):
            try:
                return float(credit)
            except ValueError:
                return None
        return None

    @staticmethod
    def _error_credit(error: ProviderConnectorError) -> float | None:
        credit = error.details.get("cost_credits")
        if isinstance(credit, (int, float)) and not isinstance(credit, bool):
            return float(credit)
        if isinstance(credit, str):
            try:
                return float(credit)
            except ValueError:
                return None
        return None

    @staticmethod
    def _response_error_code(status_code: int) -> str | None:
        if 200 <= status_code <= 299:
            return None
        if status_code in {401, 403}:
            return ProviderErrorCode.AUTHENTICATION.value
        if status_code == 429:
            return ProviderErrorCode.RATE_LIMIT.value
        if status_code in {408, 504}:
            return ProviderErrorCode.TIMEOUT.value
        if status_code >= 500:
            return ProviderErrorCode.PROVIDER_UNAVAILABLE.value
        return ProviderErrorCode.BAD_RESPONSE.value

    @property
    def operation_count(self) -> int:
        return len(self.safe_requests)

    @property
    def operations(self) -> tuple[str, ...]:
        return tuple(str(item["operation"]) for item in self.safe_requests)

    @property
    def credits(self) -> float | None:
        return sum(self.credit_values) if self.credit_values else None

    def confirm_request_usage(self, response: TransportResponse) -> None:
        """Record counters only after the typed provider path accepted the response."""

        payload = response.payload
        if not isinstance(payload, Mapping):
            return
        consumed = payload.get("RequestConsumed")
        remaining = payload.get("RequestLeft")
        if (
            type(consumed) is int
            and consumed >= 0
            and type(remaining) is int
            and remaining >= 0
        ):
            self.confirmed_request_usage.append((consumed, remaining))


@dataclass(frozen=True, slots=True)
class RecordedTransportAttempt:
    """Internal response-bearing attempt record; public evidence is allowlisted later."""

    safe_request: Mapping[str, Any]
    status: str
    provider_error_code: str | None
    credits: float | None
    response: TransportResponse | None

    @property
    def request_sha256(self) -> str:
        material = json.dumps(
            self.safe_request,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return sha256(material).hexdigest()

    @property
    def http_status_code(self) -> int | None:
        return self.response.status_code if self.response is not None else None

    @property
    def provider_reason(self) -> str | None:
        if self.response is None or not isinstance(self.response.payload, Mapping):
            return None
        reason = self.response.payload.get("reason")
        return reason if reason in _SAFE_XIYOU_PROVIDER_REASONS else None

    @property
    def trace_id(self) -> str | None:
        if self.response is None:
            return None
        trace_id = self.response.metadata.get("trace_id")
        if not isinstance(trace_id, str):
            return None
        trace_id = trace_id.strip()
        if not trace_id or len(trace_id) > 128:
            return None
        if any(not (character.isalnum() or character in "._:-") for character in trace_id):
            return None
        return trace_id


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


__all__ = (
    "AcquiredReplayProvider",
    "FixtureTransport",
    "RecordingTransport",
    "RecordedTransportAttempt",
    "XIYOU_REVERSE_KEYWORD_PAGE",
    "XIYOU_REVERSE_KEYWORD_PAGE_SIZE",
    "XIYOU_REVERSE_KEYWORD_PERIOD",
    "XIYOU_REVERSE_KEYWORD_SORT_FIELD",
    "XIYOU_REVERSE_KEYWORD_SORT_ORDER",
    "xiyou_reverse_keyword_parameters",
)
