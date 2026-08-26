from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import socket
from unittest.mock import patch

import pytest

from amazon_product_intelligence.connectors import (
    ProviderConfig,
    ProviderConnectorError,
    ProviderRequest,
    SorftimeClient,
    SorftimeProductRequest,
    SorftimeProductRequestWireCapture,
    SorftimeWireFieldStatus,
    TransportResponse,
    parse_product_request_response,
    parse_product_request_wire_response,
)
from amazon_product_intelligence.adapters import AdaptationContext
from amazon_product_intelligence.adapters.sorftime_dto_mapper_v0_1 import (
    PRODUCT_REQUEST_PAYLOAD_KIND,
    SorftimeDtoMapperV0_1,
    sorftime_sanitized_mapping_request,
)
from amazon_product_intelligence.contracts import ProductFactObservation
from amazon_product_intelligence.production_pipeline import orchestrator
from amazon_product_intelligence.production_pipeline.recovery import CheckpointStore


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "sorftime_dtos" / "v0_1"
ASIN = "B09265WXY5"
TITLE = "Synthetic Insulated Water Bottle"


def fixture(name: str = "product_request_rich_wire.json") -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def request() -> SorftimeProductRequest:
    return SorftimeProductRequest(ASIN=ASIN, Trend=2)


def context() -> AdaptationContext:
    typed_request = request()
    return AdaptationContext(
        provider="sorftime",
        payload_kind=PRODUCT_REQUEST_PAYLOAD_KIND,
        source_tool="ProductRequest",
        marketplace="US",
        locale="en-us",
        retrieved_at="2026-08-26T08:00:00Z",
        transformed_at="2026-08-26T08:01:00Z",
        collection_run_id="collection:sp040f-r1:offline",
        sanitized_request=sorftime_sanitized_mapping_request(typed_request),
        currency="USD",
    )


def map_payload(payload: dict[str, object]):
    response = parse_product_request_response(payload, request())
    return SorftimeDtoMapperV0_1().map_product_request(request(), response, context())


def facts(result, dimension: str) -> tuple[ProductFactObservation, ...]:
    return tuple(
        item
        for item in result.bundle.observations
        if isinstance(item, ProductFactObservation) and item.dimension == dimension
    )


class RecordingTransport:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests: list[object] = []

    def execute(self, transport_request):
        self.requests.append(transport_request)
        return TransportResponse(status_code=200, payload=deepcopy(self.payload))


def configuration() -> ProviderConfig:
    return ProviderConfig(
        provider_id="sorftime",
        enabled=True,
        priority=1,
        credential_env="SORFTIME_API_KEY",
        timeout_seconds=2,
        max_attempts=1,
    )


def test_rich_wire_payload_promotes_only_exact_title() -> None:
    capture = parse_product_request_wire_response(fixture(), request())
    assert capture.semantic_response.Data.Title == TITLE
    assert set(capture.extensions) == {"Brand", "Image", "Price", "Rating", "Sales"}
    assert not hasattr(capture.semantic_response.Data, "Brand")


def test_inventory_is_lightweight_deterministic_and_statused() -> None:
    capture = parse_product_request_wire_response(fixture(), request())
    inventory = {item.field_name: item for item in capture.field_inventory}
    assert tuple(inventory) == tuple(sorted(inventory))
    assert inventory["Title"].status is SorftimeWireFieldStatus.PROMOTED
    assert inventory["Title"].json_type == "STRING"
    assert inventory["Price"].status is SorftimeWireFieldStatus.CAPTURED_UNVERIFIED
    assert inventory["Sales"].json_type == "OBJECT"
    assert inventory["Price"].source_operation == "ProductRequest"


@pytest.mark.parametrize("title", [None, "Synthetic Title"])
def test_title_null_or_nonempty_string_is_accepted(title: str | None) -> None:
    payload = fixture()
    payload["Data"]["Title"] = title  # type: ignore[index]
    response = parse_product_request_response(payload, request())
    assert response.Data.Title == title


def test_missing_title_is_explicitly_unavailable() -> None:
    payload = fixture()
    del payload["Data"]["Title"]  # type: ignore[index]
    assert parse_product_request_response(payload, request()).Data.Title is None


@pytest.mark.parametrize("title", ["", "   ", 7, True, ["synthetic"]])
def test_invalid_title_type_or_blank_is_rejected(title: object) -> None:
    payload = fixture()
    payload["Data"]["Title"] = title  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="strict DTO validation"):
        parse_product_request_response(payload, request())


@pytest.mark.parametrize("drifted", ["title", "TITLE", "tItLe"])
def test_title_casing_drift_is_not_captured_as_an_extension(drifted: str) -> None:
    payload = fixture()
    payload["Data"][drifted] = payload["Data"].pop("Title")  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="casing") as caught:
        parse_product_request_wire_response(payload, request())
    assert caught.value.details["field_path"].startswith(f"Data.{drifted}")


def test_unknown_top_level_envelope_field_remains_strict() -> None:
    payload = fixture()
    payload["Trace"] = "synthetic"
    with pytest.raises(ProviderConnectorError, match="strict DTO validation"):
        parse_product_request_wire_response(payload, request())


def test_unknown_nested_shape_inside_approved_attribute_remains_strict() -> None:
    payload = fixture()
    payload["Data"]["Attribute"] = [[ASIN, "Material", "Steel"]]  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="strict DTO validation"):
        parse_product_request_wire_response(payload, request())


def test_safe_extension_nested_json_is_captured_and_detached() -> None:
    payload = fixture()
    payload["Data"]["Future"] = {"Nested": [1, {"Known": True}]}  # type: ignore[index]
    capture = parse_product_request_wire_response(payload, request())
    payload["Data"]["Future"]["Nested"][1]["Known"] = False  # type: ignore[index]
    assert capture.extensions["Future"]["Nested"][1]["Known"] is True


@pytest.mark.parametrize("unsafe_name", ["Authorization", "api_key", "AccessToken", "password"])
def test_unsafe_root_extension_is_sanitized_from_capture(unsafe_name: str) -> None:
    payload = fixture()
    payload["Data"][unsafe_name] = "test-only-value"  # type: ignore[index]
    capture = parse_product_request_wire_response(payload, request())
    assert unsafe_name not in capture.extensions
    item = next(item for item in capture.field_inventory if item.field_name == unsafe_name)
    assert item.status is SorftimeWireFieldStatus.IGNORED_UNSAFE


def test_nested_unsafe_extension_is_sanitized_as_a_whole() -> None:
    payload = fixture()
    payload["Data"]["Metadata"] = {"Authorization": "test-only-value"}  # type: ignore[index]
    capture = parse_product_request_wire_response(payload, request())
    assert "Metadata" not in capture.extensions
    safe = json.dumps(capture.to_safe_dict(), sort_keys=True)
    assert "test-only-value" not in safe


def test_non_json_extension_fails_closed() -> None:
    payload = fixture()
    payload["Data"]["FutureScore"] = float("nan")  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="JSON-safe"):
        parse_product_request_wire_response(payload, request())


def test_capture_only_values_do_not_enter_semantic_response_or_fingerprint() -> None:
    first = fixture()
    second = fixture()
    second["Data"]["Price"] = 999999  # type: ignore[index]
    first_result = map_payload(first)
    second_result = map_payload(second)
    assert first_result.raw_evidence is not None
    assert second_result.raw_evidence is not None
    assert first_result.raw_evidence.content_fingerprint == second_result.raw_evidence.content_fingerprint
    assert first_result.raw_snapshot == second_result.raw_snapshot


def test_extension_order_does_not_change_promoted_canonical_ids() -> None:
    first = fixture()
    second = fixture()
    data = second["Data"]  # type: ignore[index]
    reordered = {name: data[name] for name in reversed(tuple(data))}  # type: ignore[index]
    second["Data"] = reordered
    first_ids = tuple(item.observation_id for item in map_payload(first).bundle.observations)
    second_ids = tuple(item.observation_id for item in map_payload(second).bundle.observations)
    assert first_ids == second_ids


def test_rich_and_minimal_payloads_preserve_prior_semantics_except_title() -> None:
    rich = map_payload(fixture())
    minimal = map_payload(fixture("product_request_success.json"))

    def prior_facts(result):
        return tuple(
            sorted(
                (
                    item.dimension,
                    item.subject.subject_id,
                    json.dumps(item.value.to_dict(), sort_keys=True),
                )
                for item in result.bundle.observations
                if isinstance(item, ProductFactObservation) and item.dimension != "title"
            )
        )

    assert prior_facts(rich) == prior_facts(minimal)
    assert len(facts(rich, "title")) == 1
    assert facts(minimal, "title") == ()


def test_title_is_in_semantic_fingerprint() -> None:
    first = fixture()
    second = fixture()
    second["Data"]["Title"] = "A Different Synthetic Title"  # type: ignore[index]
    first_result = map_payload(first)
    second_result = map_payload(second)
    assert first_result.raw_evidence is not None
    assert second_result.raw_evidence is not None
    assert first_result.raw_evidence.content_fingerprint != second_result.raw_evidence.content_fingerprint


def test_mapper_emits_exact_requested_asin_title_only() -> None:
    result = map_payload(fixture())
    title_facts = facts(result, "title")
    assert len(title_facts) == 1
    assert title_facts[0].provenance.source_record_identity == f"US:{ASIN}:ProductRequest"
    assert title_facts[0].value.raw_value == TITLE
    assert title_facts[0].provenance.source_field == "Data.Title"


def test_mapper_does_not_promote_capture_only_commercial_fields() -> None:
    result = map_payload(fixture())
    dimensions = {
        item.dimension
        for item in result.bundle.observations
        if isinstance(item, ProductFactObservation)
    }
    assert not dimensions.intersection({"brand", "price", "rating", "sales", "profit"})


def test_null_title_emits_no_title_fact() -> None:
    payload = fixture()
    payload["Data"]["Title"] = None  # type: ignore[index]
    assert facts(map_payload(payload), "title") == ()


def test_client_exposes_runtime_capture_without_logging_extension_values() -> None:
    transport = RecordingTransport(fixture())
    client = SorftimeClient(
        transport=transport,
        environment={"SORFTIME_API_KEY": "test-only-credential"},
    )
    result = client.product_request(request(), configuration())
    assert isinstance(result.wire_capture, SorftimeProductRequestWireCapture)
    assert result.response.Data.Title == TITLE
    assert len(transport.requests) == 1
    safe = json.dumps(result.to_safe_dict(), sort_keys=True)
    assert TITLE not in safe
    assert "CAPTURE ONLY" not in safe
    assert "test-only-credential" not in safe


def test_success_checkpoint_retains_safe_wire_payload_without_credentials(tmp_path: Path) -> None:
    payload = fixture()
    store = CheckpointStore(
        tmp_path,
        run_id="run:sp040f-r1:offline",
        request_fingerprint="sha256:v1:offline-fixture",
        provider_id="sorftime",
    )
    provider_request = ProviderRequest(
        canonical_field="product.asin",
        parameters={"ASIN": ASIN, "Trend": 2},
        marketplace="US",
        locale="en-us",
        retrieved_at="2026-08-26T08:00:00Z",
        transformed_at="2026-08-26T08:01:00Z",
        collection_run_id="collection:sp040f-r1:offline",
        currency="USD",
    )
    checkpoint = store.write_success(
        operation="ProductRequest",
        request=provider_request,
        response=TransportResponse(status_code=200, payload=payload),
        provenance_id="raw-evidence:sp040f-r1:offline",
    )
    saved = checkpoint.payload["provider_response"]["payload"]
    assert saved["Data"]["Title"] == TITLE
    assert saved["Data"]["Price"] == 1999
    serialized = json.dumps(checkpoint.payload, sort_keys=True)
    assert "SORFTIME_API_KEY" not in serialized
    assert "Authorization" not in serialized


def test_offline_forensic_path_never_opens_a_socket() -> None:
    with patch.object(socket, "create_connection", side_effect=AssertionError) as connect:
        capture = parse_product_request_wire_response(fixture(), request())
    assert capture.semantic_response.Data.Title == TITLE
    connect.assert_not_called()


def test_sorftime_live_gate_remains_disabled() -> None:
    assert orchestrator._SORFTIME_V0_1_LIVE_RELEASE_ENABLED is False
