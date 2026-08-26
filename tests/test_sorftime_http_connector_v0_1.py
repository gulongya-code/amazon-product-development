from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket
from unittest.mock import patch

import pytest

from amazon_product_intelligence.connectors import (
    BoundedTransientRetryPolicy,
    HttpJsonTransport,
    ProviderConfig,
    ProviderConnectorError,
    ProviderCredential,
    ProviderErrorCode,
    ProviderFetchStatus,
    ProviderRequest,
    SorftimeAsinRequestKeywordRequest,
    SorftimeClient,
    SorftimeProductRequest,
    SorftimeProductVariationsRequest,
    SorftimeProvider,
    TransportRequest,
    TransportResponse,
)
from amazon_product_intelligence.connectors.sorftime_client import (
    SORFTIME_CONTENT_TYPE,
    SORFTIME_HTTP_OPERATIONS,
    SORFTIME_ORIGIN,
)
from amazon_product_intelligence.connectors.sorftime_legacy import (
    LegacySorftimeFixtureProvider,
)
from amazon_product_intelligence.contracts import (
    MetricObservation,
    PresenceStatus,
    QueryExecutionOutcome,
    canonical_json,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "sorftime_dtos" / "v0_1"
TEST_SECRET = "fixture-account-sk-not-real"
ASIN = "B09265WXY5"
NOW = "2026-08-26T08:00:00Z"


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: object, *, status: int = 200) -> None:
        self.status = status
        self.headers: dict[str, str] = {}
        self._body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def read(self, size: int = -1) -> bytes:
        return self._body if size < 0 else self._body[:size]

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None


class SequenceOpener:
    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[object] = []

    def __call__(self, request: object, *, timeout: float) -> object:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class RecordingTransport:
    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.requests: list[TransportRequest] = []

    def execute(self, request: TransportRequest) -> TransportResponse:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, TransportResponse):
            return outcome
        return TransportResponse(status_code=200, payload=deepcopy(outcome))


def configuration(*, attempts: int = 1) -> ProviderConfig:
    return ProviderConfig(
        provider_id="sorftime",
        enabled=True,
        priority=1,
        credential_env="SORFTIME_API_KEY",
        timeout_seconds=2,
        max_attempts=attempts,
    )


def provider_request(field: str, parameters: dict[str, object]) -> ProviderRequest:
    return ProviderRequest(
        canonical_field=field,
        parameters=parameters,
        marketplace="US",
        locale="en-us",
        retrieved_at=NOW,
        transformed_at=NOW,
        collection_run_id=f"collection:sp040d:{field}",
        currency="USD",
    )


def product_request() -> SorftimeProductRequest:
    return SorftimeProductRequest(ASIN=ASIN, Trend=2)


def variation_request() -> SorftimeProductVariationsRequest:
    return SorftimeProductVariationsRequest(Asin=ASIN, PageIndex=1)


def keyword_request() -> SorftimeAsinRequestKeywordRequest:
    return SorftimeAsinRequestKeywordRequest(ASIN=ASIN, PageIndex=1, PageSize=20)


def direct_client(opener: SequenceOpener, *, retry_policy=None) -> SorftimeClient:
    return SorftimeClient(
        opener=opener,
        environment={"SORFTIME_API_KEY": TEST_SECRET},
        retry_policy=retry_policy,
    )


@pytest.mark.parametrize(
    ("method", "dto_request", "fixture_name", "expected_url"),
    (
        (
            "product_request",
            product_request(),
            "product_request_success.json",
            f"{SORFTIME_ORIGIN}/api/ProductRequest?domain=1",
        ),
        (
            "product_variations",
            variation_request(),
            "product_variations_success.json",
            f"{SORFTIME_ORIGIN}/api/ProductVariations?domain=1",
        ),
        (
            "asin_request_keyword",
            keyword_request(),
            "asin_request_keyword_success.json",
            f"{SORFTIME_ORIGIN}/api/ASINRequestKeyword?domain=1",
        ),
    ),
)
def test_exact_three_http_contracts(method, dto_request, fixture_name: str, expected_url: str) -> None:
    opener = SequenceOpener(FakeResponse(fixture(fixture_name)))
    result = getattr(direct_client(opener), method)(dto_request, configuration())
    sent = opener.requests[0]
    headers = {key.casefold(): value for key, value in sent.header_items()}
    body = json.loads(sent.data.decode("utf-8"))
    assert sent.full_url == expected_url
    assert sent.method == "POST"
    assert headers["content-type"] == SORFTIME_CONTENT_TYPE
    assert headers["authorization"] == f"BasicAuth {TEST_SECRET}"
    assert body == dto_request.to_provider_body()
    assert "domain" not in body
    assert result.response.Code == 0


def test_operations_are_exact_and_contain_no_provider_tool_placeholders() -> None:
    assert [item.operation for item in SORFTIME_HTTP_OPERATIONS] == [
        "ProductRequest",
        "ProductVariations",
        "ASINRequestKeyword",
    ]
    assert all(item.method == "POST" for item in SORFTIME_HTTP_OPERATIONS)
    assert all(item.query_parameters == {"domain": 1} for item in SORFTIME_HTTP_OPERATIONS)
    assert not any("provider-tool" in item.endpoint for item in SORFTIME_HTTP_OPERATIONS)


def test_safe_transport_identity_redacts_basic_auth_secret() -> None:
    transport = RecordingTransport(fixture("product_request_success.json"))
    result = SorftimeClient(
        transport=transport,
        environment={"SORFTIME_API_KEY": TEST_SECRET},
    ).product_request(product_request(), configuration())
    safe = transport.requests[0].to_safe_dict()
    assert safe["credential"]["value"] == "<redacted>"
    assert safe["query_parameters"] == {"domain": 1}
    for value in (repr(transport.requests[0]), repr(safe), repr(result), repr(result.to_safe_dict())):
        assert TEST_SECRET not in value
        assert f"BasicAuth {TEST_SECRET}" not in value


def test_public_headers_and_query_cannot_carry_credentials() -> None:
    with pytest.raises(ValueError, match="ProviderCredential"):
        TransportRequest(
            provider_id="sorftime",
            operation="ProductRequest",
            method="POST",
            endpoint="/api/ProductRequest",
            parameters={"ASIN": ASIN, "Trend": 2},
            timeout_seconds=2,
            public_headers={"Authorization": "forbidden"},
        )
    with pytest.raises(ValueError, match="credential"):
        TransportRequest(
            provider_id="sorftime",
            operation="ProductRequest",
            method="POST",
            endpoint="/api/ProductRequest",
            parameters={"ASIN": ASIN, "Trend": 2},
            timeout_seconds=2,
            public_headers={},
            query_parameters={"authorization": "forbidden"},
        )
    with pytest.raises(ValueError, match="credential values"):
        TransportRequest(
            provider_id="sorftime",
            operation="ProductRequest",
            method="POST",
            endpoint="/api/ProductRequest",
            parameters={"ASIN": ASIN, "Trend": 2},
            timeout_seconds=2,
            public_headers={},
            query_parameters={"opaque": TEST_SECRET},
            credential=ProviderCredential(
                environment_variable="SORFTIME_API_KEY",
                injection_name="Authorization",
                value=TEST_SECRET,
                value_prefix="BasicAuth ",
            ),
        )


def test_missing_and_control_character_credentials_fail_before_io() -> None:
    for environment in ({}, {"SORFTIME_API_KEY": "bad\r\nInjected: yes"}):
        opener = SequenceOpener(FakeResponse(fixture("product_request_success.json")))
        with pytest.raises(ProviderConnectorError) as caught:
            SorftimeClient(opener=opener, environment=environment).product_request(
                product_request(), configuration()
            )
        assert caught.value.code is ProviderErrorCode.CONFIGURATION
        assert opener.requests == []
        assert "Injected" not in str(caught.value.to_dict())


@pytest.mark.parametrize(
    "origin",
    (
        "http://standardapi.sorftime.com",
        "https://evil.invalid",
        "https://standardapi.sorftime.com/",
        "https://user@standardapi.sorftime.com",
        "https://standardapi.sorftime.com:443",
        "https://standardapi.sorftime.com?x=1",
        "https://standardapi.sorftime.com#x",
        " https://standardapi.sorftime.com",
        "https://standardapi.sorftime.com.evil.invalid",
    ),
)
def test_invalid_origin_is_rejected_before_environment_or_io(origin: str) -> None:
    opener = SequenceOpener(FakeResponse(fixture("product_request_success.json")))
    with pytest.raises(ProviderConnectorError) as caught:
        SorftimeClient(
            base_origin=origin,
            opener=opener,
            environment={"SORFTIME_API_KEY": TEST_SECRET},
        )
    assert caught.value.code is ProviderErrorCode.CONFIGURATION
    assert opener.requests == []
    assert TEST_SECRET not in str(caught.value.to_dict())


def test_injected_http_transport_cannot_redirect_account_key() -> None:
    opener = SequenceOpener(FakeResponse(fixture("product_request_success.json")))
    transport = HttpJsonTransport({"sorftime": "https://evil.invalid"}, opener=opener)
    with pytest.raises(ProviderConnectorError) as caught:
        SorftimeClient(
            transport=transport,
            environment={"SORFTIME_API_KEY": TEST_SECRET},
        )
    assert caught.value.code is ProviderErrorCode.CONFIGURATION
    assert opener.requests == []


def test_client_rejects_raw_dict_and_variations_do_not_enable_sales() -> None:
    transport = RecordingTransport(fixture("product_variations_success.json"))
    client = SorftimeClient(
        transport=transport,
        environment={"SORFTIME_API_KEY": TEST_SECRET},
    )
    with pytest.raises(TypeError, match="exact SP-040B"):
        client.product_variations({"Asin": ASIN}, configuration())  # type: ignore[arg-type]
    client.product_variations(variation_request(), configuration())
    assert transport.requests[0].parameters == {"Asin": ASIN, "PageIndex": 1}
    assert "IsSalesVolume" not in transport.requests[0].parameters


def test_keyword_request_is_one_page_without_hidden_pagination() -> None:
    opener = SequenceOpener(FakeResponse(fixture("asin_request_keyword_success.json")))
    direct_client(opener).asin_request_keyword(keyword_request(), configuration())
    assert len(opener.requests) == 1
    assert json.loads(opener.requests[0].data) == {
        "ASIN": ASIN,
        "PageIndex": 1,
        "PageSize": 20,
    }


def test_client_returns_exact_typed_response_and_runtime_usage_only() -> None:
    opener = SequenceOpener(FakeResponse(fixture("product_request_success.json")))
    result = direct_client(opener).product_request(product_request(), configuration())
    assert type(result.response).__name__ == "SorftimeProductRequestResponse"
    assert result.usage.request_consumed == result.response.RequestConsumed
    assert result.usage.request_left == result.response.RequestLeft
    assert result.to_safe_dict()["usage"] == result.usage.to_safe_dict()


def test_provider_runs_dto_first_mapper_deterministically() -> None:
    body = fixture("product_request_success.json")
    request = provider_request("product.asin", {"ASIN": ASIN, "Trend": 2})
    first = SorftimeProvider(
        RecordingTransport(body), environment={"SORFTIME_API_KEY": TEST_SECRET}
    ).fetch(request, configuration())
    second = SorftimeProvider(
        RecordingTransport(body), environment={"SORFTIME_API_KEY": TEST_SECRET}
    ).fetch(request, configuration())
    assert first.status is ProviderFetchStatus.RETURNED
    assert canonical_json(first.adaptation.to_dict()) == canonical_json(second.adaptation.to_dict())
    serialized = canonical_json(first.adaptation.to_dict())
    assert "RequestConsumed" not in serialized
    assert "RequestLeft" not in serialized
    assert TEST_SECRET not in serialized


@pytest.mark.parametrize("status", (401, 403))
def test_authentication_status_is_nonretryable_and_one_attempt(status: int) -> None:
    opener = SequenceOpener(FakeResponse(b"not-json", status=status), FakeResponse({}))
    client = direct_client(opener, retry_policy=BoundedTransientRetryPolicy())
    with pytest.raises(ProviderConnectorError) as caught:
        client.product_request(product_request(), configuration(attempts=2))
    assert caught.value.code is ProviderErrorCode.AUTHENTICATION
    assert caught.value.retryable is False
    assert len(opener.requests) == 1


def test_rate_limit_default_is_one_attempt() -> None:
    opener = SequenceOpener(FakeResponse({}, status=429), FakeResponse({}))
    with pytest.raises(ProviderConnectorError) as caught:
        direct_client(opener).product_request(product_request(), configuration(attempts=5))
    assert caught.value.code is ProviderErrorCode.RATE_LIMIT
    assert len(opener.requests) == 1


@pytest.mark.parametrize("first", (408, 500, 503, 504))
def test_explicit_transient_retry_is_bounded(first: int) -> None:
    opener = SequenceOpener(
        FakeResponse({}, status=first),
        FakeResponse(fixture("product_request_success.json")),
    )
    result = direct_client(opener, retry_policy=BoundedTransientRetryPolicy()).product_request(
        product_request(), configuration(attempts=2)
    )
    assert result.response.Code == 0
    assert len(opener.requests) == 2


def test_timeout_retry_stops_at_configured_bound() -> None:
    opener = SequenceOpener(socket.timeout(), socket.timeout(), socket.timeout())
    with pytest.raises(ProviderConnectorError) as caught:
        direct_client(opener, retry_policy=BoundedTransientRetryPolicy()).product_request(
            product_request(), configuration(attempts=2)
        )
    assert caught.value.code is ProviderErrorCode.TIMEOUT
    assert len(opener.requests) == 2


def test_business_and_schema_failures_never_retry_or_reach_mapper() -> None:
    business = fixture("product_request_success.json")
    business["Code"] = 7
    malformed = fixture("product_request_success.json")
    malformed["Unexpected"] = True
    for payload, code in (
        (business, ProviderErrorCode.BAD_RESPONSE),
        (malformed, ProviderErrorCode.SCHEMA_MISMATCH),
    ):
        transport = RecordingTransport(payload, fixture("product_request_success.json"))
        provider = SorftimeProvider(
            transport,
            environment={"SORFTIME_API_KEY": TEST_SECRET},
            retry_policy=BoundedTransientRetryPolicy(),
        )
        provider._mapper = object()  # parser must fail before mapper dispatch
        with pytest.raises(ProviderConnectorError) as caught:
            provider.fetch(
                provider_request("product.asin", {"ASIN": ASIN, "Trend": 2}),
                configuration(attempts=2),
            )
        assert caught.value.code is code
        assert len(transport.requests) == 1


def test_non_json_2xx_fails_closed() -> None:
    opener = SequenceOpener(FakeResponse(b"not-json"))
    with pytest.raises(ProviderConnectorError) as caught:
        direct_client(opener).product_request(product_request(), configuration())
    assert caught.value.code is ProviderErrorCode.BAD_RESPONSE


def test_network_failure_is_sanitized_even_if_lower_layer_mentions_secret() -> None:
    opener = SequenceOpener(OSError(f"unsafe lower-layer detail {TEST_SECRET}"))
    with pytest.raises(ProviderConnectorError) as caught:
        direct_client(opener).product_request(product_request(), configuration())
    assert caught.value.code is ProviderErrorCode.NETWORK
    assert TEST_SECRET not in str(caught.value)
    assert TEST_SECRET not in repr(caught.value.to_dict())
    assert caught.value.__suppress_context__ is True


def test_empty_keyword_page_is_empty_not_zero_demand() -> None:
    body = fixture("asin_request_keyword_success.json")
    body["Data"] = []
    result = SorftimeProvider(
        RecordingTransport(body), environment={"SORFTIME_API_KEY": TEST_SECRET}
    ).fetch(
        provider_request(
            "relationship.product_to_keyword",
            {"ASIN": ASIN, "PageIndex": 1, "PageSize": 20},
        ),
        configuration(),
    )
    assert result.status is ProviderFetchStatus.EMPTY
    assert result.adaptation.bundle.query_execution_records[0].outcome is QueryExecutionOutcome.EXPLICIT_EMPTY
    assert not result.observations


def test_sales_minus_one_remains_unknown_end_to_end() -> None:
    result = SorftimeProvider(
        RecordingTransport(fixture("product_variations_success.json")),
        environment={"SORFTIME_API_KEY": TEST_SECRET},
    ).fetch(
        provider_request("metric.estimated_variation_sales", {"Asin": ASIN, "PageIndex": 1}),
        configuration(),
    )
    sales = tuple(item for item in result.observations if isinstance(item, MetricObservation))
    assert sales
    assert all(item.value.presence_status is PresenceStatus.UNKNOWN for item in sales)
    assert all(item.value.raw_value is None and item.value.normalized_value is None for item in sales)


def test_capabilities_are_only_dto_first_proven_slice() -> None:
    fields = {item.canonical_field for item in SorftimeProvider(RecordingTransport({})).capabilities}
    assert fields == {
        "product.asin",
        "product.parent_asin",
        "product.attributes",
        "product.variation",
        "metric.estimated_variation_sales",
        "relationship.product_to_keyword",
        "keyword.channel",
        "keyword.search_volume",
        "keyword.cpc",
    }
    assert not fields & {"review.raw", "metric.price", "product.brand", "product.category"}


def test_legacy_raw_adapter_requires_explicit_fixture_only_opt_in() -> None:
    with pytest.raises(ValueError, match="offline fixtures"):
        LegacySorftimeFixtureProvider(RecordingTransport({}))


def test_fake_opener_path_constructs_no_socket_and_persists_no_secret() -> None:
    opener = SequenceOpener(FakeResponse(fixture("product_request_success.json")))
    with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
        result = direct_client(opener).product_request(product_request(), configuration())
    assert result.response.Code == 0
    fixture_text = "".join(path.read_text(encoding="utf-8") for path in FIXTURES.glob("*.json"))
    assert TEST_SECRET not in fixture_text
    assert "BasicAuth" not in fixture_text
