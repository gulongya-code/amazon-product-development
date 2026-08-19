from __future__ import annotations

from collections import deque
import logging
import os
from unittest.mock import patch

import pytest

from amazon_product_intelligence.connectors import (
    BaseAPIClient,
    ProviderConnectorError,
    ProviderErrorCode,
    SorftimeClient,
    TransportResponse,
    XiyouClient,
)


TEST_KEY = "fixture-key-not-real"


class StubTransport:
    def __init__(self, *outcomes: object) -> None:
        self.outcomes = deque(outcomes)
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        outcome = self.outcomes.popleft()
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def base_client(transport: StubTransport, *, max_attempts: int = 3) -> BaseAPIClient:
    return BaseAPIClient(
        source="fixture",
        api_key_env="FIXTURE_API_KEY",
        base_url_env="FIXTURE_API_BASE_URL",
        credential_header="X-Api-Key",
        transport=transport,
        timeout_seconds=2.5,
        max_attempts=max_attempts,
    )


def test_base_client_standardizes_request_and_response_without_exposing_key(caplog) -> None:
    transport = StubTransport(
        TransportResponse(status_code=200, payload={"data": {"asin": "B0MOCK"}})
    )
    with patch.dict(os.environ, {"FIXTURE_API_KEY": TEST_KEY}, clear=True):
        client = base_client(transport)
        with caplog.at_level(logging.INFO):
            response = client.request(
                "POST",
                "/mock/products",
                operation="mock_product",
                parameters={"asin": "B0MOCK"},
            )

    assert response.source == "fixture"
    assert response.status_code == 200
    assert response.payload == {"data": {"asin": "B0MOCK"}}
    assert response.request_metadata == {
        "operation": "mock_product",
        "method": "POST",
        "endpoint": "/mock/products",
        "parameters": {"asin": "B0MOCK"},
        "timeout_seconds": 2.5,
        "attempt": 1,
        "status_code": 200,
    }
    assert transport.requests[0].timeout_seconds == 2.5
    assert TEST_KEY not in repr(transport.requests[0])
    assert TEST_KEY not in repr(response.request_metadata)
    assert TEST_KEY not in caplog.text


def test_base_client_retries_retryable_response_within_bound() -> None:
    transport = StubTransport(
        TransportResponse(status_code=503, payload={"error": "temporary"}),
        TransportResponse(status_code=200, payload={"ok": True}),
    )
    with patch.dict(os.environ, {"FIXTURE_API_KEY": TEST_KEY}, clear=True):
        response = base_client(transport, max_attempts=2).request(
            "GET",
            "/mock/health",
            operation="mock_health",
        )

    assert response.payload == {"ok": True}
    assert response.request_metadata["attempt"] == 2
    assert len(transport.requests) == 2


def test_base_client_normalizes_timeout_and_stops_at_max_attempts() -> None:
    transport = StubTransport(TimeoutError("first"), TimeoutError("second"))
    with patch.dict(os.environ, {"FIXTURE_API_KEY": TEST_KEY}, clear=True):
        with pytest.raises(ProviderConnectorError) as caught:
            base_client(transport, max_attempts=2).request(
                "GET",
                "/mock/timeout",
                operation="mock_timeout",
            )

    assert caught.value.code is ProviderErrorCode.TIMEOUT
    assert caught.value.retryable is True
    assert len(transport.requests) == 2


@pytest.mark.parametrize(
    ("client_type", "key_name", "expected_source"),
    (
        (XiyouClient, "XIYOU_API_KEY", "xiyou"),
        (SorftimeClient, "SORFTIME_API_KEY", "sorftime"),
    ),
)
def test_provider_clients_support_successful_mock_calls(
    client_type,
    key_name: str,
    expected_source: str,
) -> None:
    transport = StubTransport()
    payload = {"data": [{"value": 1}], "total": 1}
    with patch.dict(os.environ, {key_name: TEST_KEY}, clear=True):
        response = client_type(transport=transport).mock_call(
            payload,
            operation="fixture_success",
            request_metadata={"fixture": "success"},
        )

    assert response.source == expected_source
    assert response.payload is payload
    assert response.request_metadata["fixture"] == "success"
    assert transport.requests == []


def test_mock_error_response_uses_shared_error_model_and_does_not_use_network() -> None:
    transport = StubTransport()
    with patch.dict(os.environ, {"XIYOU_API_KEY": TEST_KEY}, clear=True):
        client = XiyouClient(transport=transport, max_attempts=1)
        with pytest.raises(ProviderConnectorError) as caught:
            client.mock_call({"error": "unauthorized"}, status_code=401)

    assert caught.value.code is ProviderErrorCode.AUTHENTICATION
    assert caught.value.details == {"status_code": 401}
    assert transport.requests == []


@pytest.mark.parametrize(
    ("client_type", "provider_id"),
    ((XiyouClient, "xiyou"), (SorftimeClient, "sorftime")),
)
def test_missing_api_key_fails_before_transport(client_type, provider_id: str) -> None:
    transport = StubTransport()
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ProviderConnectorError) as caught:
            client_type(transport=transport)

    assert caught.value.code is ProviderErrorCode.CONFIGURATION
    assert caught.value.provider_id == provider_id
    assert transport.requests == []


def test_credentials_are_rejected_from_request_parameters() -> None:
    transport = StubTransport()
    with patch.dict(os.environ, {"FIXTURE_API_KEY": TEST_KEY}, clear=True):
        client = base_client(transport)
        with pytest.raises(ProviderConnectorError) as caught:
            client.request(
                "POST",
                "/mock/unsafe",
                parameters={"nested": {"api_key": "must-not-enter"}},
            )

    assert caught.value.code is ProviderErrorCode.CONFIGURATION
    assert transport.requests == []


def test_real_transport_requires_environment_owned_base_url() -> None:
    with patch.dict(os.environ, {"FIXTURE_API_KEY": TEST_KEY}, clear=True):
        with pytest.raises(ProviderConnectorError) as caught:
            BaseAPIClient(
                source="fixture",
                api_key_env="FIXTURE_API_KEY",
                base_url_env="FIXTURE_API_BASE_URL",
                credential_header="X-Api-Key",
            )

    assert caught.value.code is ProviderErrorCode.CONFIGURATION
    assert caught.value.details == {"base_url_env": "FIXTURE_API_BASE_URL"}
