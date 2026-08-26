from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from amazon_product_intelligence.adapters import AdaptationContext
from amazon_product_intelligence.adapters.sorftime_dto_mapper_v0_1 import (
    ASIN_REQUEST_KEYWORD_PAYLOAD_KIND,
    SorftimeDtoMapperV0_1,
    sorftime_sanitized_mapping_request,
)
from amazon_product_intelligence.connectors import (
    ProviderConfig,
    ProviderConnectorError,
    SorftimeAsinRequestKeywordRequest,
    SorftimeAsinRequestKeywordWireCapture,
    SorftimeClient,
    TransportResponse,
    diagnose_asin_request_keyword_wire_structure,
    parse_asin_request_keyword_response,
    parse_asin_request_keyword_wire_response,
)


FIXTURES = Path(__file__).parent / "fixtures" / "sorftime_dtos" / "v0_1"
ASIN = "B09265WXY5"
PROVEN_NUMBER_FIELDS = (
    "ClickConversionRateD90",
    "ClickOf90D",
    "ProductCount",
    "Rank",
    "RankChangeOfWeekly",
    "SalesVolumeOf90D",
    "SearchConversionRate",
    "SearchConversionRateD90",
    "ShareClickRate",
    "ShareConversionRate",
    "WordCount",
)
PROVEN_ARRAY_FIELDS = (
    "Images",
    "ImagesFromAsin",
    "SearchRankTrend",
    "SearchVolumeGrowthRateTrend",
    "SearchVolumeTrend",
    "Top3Brand",
    "Top3Category",
    "Top3asin",
)
PROVEN_STRING_FIELDS = ("KeywordCNName", "Season", "Update")


def fixture() -> dict[str, object]:
    return json.loads(
        (FIXTURES / "asin_request_keyword_success.json").read_text(encoding="utf-8")
    )


def request() -> SorftimeAsinRequestKeywordRequest:
    return SorftimeAsinRequestKeywordRequest(ASIN=ASIN, PageIndex=1, PageSize=20)


def live_shape(seed: int = 1) -> dict[str, object]:
    payload = fixture()
    for index, row in enumerate(payload["Data"]):  # type: ignore[index]
        nested = row["Keyword"]
        for offset, name in enumerate(PROVEN_NUMBER_FIELDS):
            nested[name] = seed + index + offset
        for name in PROVEN_ARRAY_FIELDS:
            nested[name] = [seed, index]
        for name in PROVEN_STRING_FIELDS:
            nested[name] = f"synthetic-{seed}-{index}"
        nested["Department"] = None
    return payload


def context() -> AdaptationContext:
    typed_request = request()
    return AdaptationContext(
        provider="sorftime",
        payload_kind=ASIN_REQUEST_KEYWORD_PAYLOAD_KIND,
        source_tool="ASINRequestKeyword",
        marketplace="US",
        locale="en-us",
        retrieved_at="2026-08-26T08:00:00Z",
        transformed_at="2026-08-26T08:01:00Z",
        collection_run_id="collection:sp040f-r5:offline",
        sanitized_request=sorftime_sanitized_mapping_request(typed_request),
        currency="USD",
    )


def map_payload(payload: dict[str, object]):
    response = parse_asin_request_keyword_response(payload, request())
    return SorftimeDtoMapperV0_1().map_asin_request_keyword(
        request(), response, context()
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


def test_proven_live_nested_shape_projects_into_strict_semantic_dto() -> None:
    capture = parse_asin_request_keyword_wire_response(live_shape(), request())
    assert isinstance(capture, SorftimeAsinRequestKeywordWireCapture)
    assert len(capture.semantic_response.Data) == 20
    assert len(capture.nested_keyword_extensions) == 20
    assert set(capture.nested_keyword_extensions[0]) == {
        *PROVEN_NUMBER_FIELDS,
        *PROVEN_ARRAY_FIELDS,
        *PROVEN_STRING_FIELDS,
        "Department",
    }
    assert not hasattr(capture.semantic_response.Data[0].Keyword, "Rank")
    diagnostic = diagnose_asin_request_keyword_wire_structure(live_shape(), request())
    assert diagnostic.parser_failure_kind == "NESTED_KEYWORD_EXTRA_FIELDS"
    assert diagnostic.parser_accepted is True


def test_safe_inventory_has_frequency_type_and_status_without_values() -> None:
    capture = parse_asin_request_keyword_wire_response(live_shape(), request())
    inventory = {item.field_name: item for item in capture.nested_keyword_inventory}
    assert inventory["Keyword"].status == "SEMANTIC_EXACT"
    assert inventory["Rank"].status == "CAPTURED_UNVERIFIED"
    assert inventory["Rank"].json_types == ("NUMBER",)
    assert inventory["Rank"].present_count == 20
    safe = json.dumps(capture.to_safe_dict(), sort_keys=True)
    assert "synthetic-1-0" not in safe
    assert '"nested_keyword_extensions"' not in safe


def test_capture_only_values_do_not_change_canonical_ids_or_fingerprints() -> None:
    first = map_payload(live_shape(seed=1))
    second = map_payload(live_shape(seed=999))
    assert tuple(item.observation_id for item in first.bundle.observations) == tuple(
        item.observation_id for item in second.bundle.observations
    )
    assert first.raw_evidence is not None
    assert second.raw_evidence is not None
    assert first.raw_evidence.content_fingerprint == second.raw_evidence.content_fingerprint
    assert first.raw_snapshot == second.raw_snapshot


def test_client_exposes_keyword_wire_sidecar_without_changing_typed_response() -> None:
    transport = RecordingTransport(live_shape())
    result = SorftimeClient(
        transport=transport,
        environment={"SORFTIME_API_KEY": "offline-test-only"},
    ).asin_request_keyword(request(), configuration())
    assert len(transport.requests) == 1
    assert len(result.response.Data) == 20
    assert isinstance(result.wire_capture, SorftimeAsinRequestKeywordWireCapture)
    assert result.to_safe_dict()["wire_capture"]["source_operation"] == "ASINRequestKeyword"


def test_unknown_nested_extra_remains_strictly_rejected() -> None:
    payload = live_shape()
    payload["Data"][0]["Keyword"]["UnprovenFuture"] = 1  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="strict DTO validation"):
        parse_asin_request_keyword_wire_response(payload, request())


@pytest.mark.parametrize("field_name", ["Rank", "KeywordCNName", "Images", "Department"])
def test_proven_extension_type_drift_fails_closed(field_name: str) -> None:
    payload = live_shape()
    payload["Data"][0]["Keyword"][field_name] = {"wrong": "shape"}  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="extension type"):
        parse_asin_request_keyword_wire_response(payload, request())


@pytest.mark.parametrize(
    ("exact_name", "drifted_name"),
    [("Keyword", "keyword"), ("SearchVolume", "searchvolume"), ("Rank", "rank")],
)
def test_unproven_nested_casing_variants_fail(
    exact_name: str,
    drifted_name: str,
) -> None:
    payload = live_shape()
    nested = payload["Data"][0]["Keyword"]  # type: ignore[index]
    nested[drifted_name] = nested.pop(exact_name)
    with pytest.raises(ProviderConnectorError, match="casing"):
        parse_asin_request_keyword_wire_response(payload, request())


def test_duplicate_alias_and_canonical_field_fails() -> None:
    payload = live_shape()
    payload["Data"][0]["Keyword"]["rank"] = 2  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="casing"):
        parse_asin_request_keyword_wire_response(payload, request())


def test_row_extra_fields_remain_strictly_rejected() -> None:
    payload = live_shape()
    payload["Data"][0]["FutureRowField"] = None  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="strict DTO validation"):
        parse_asin_request_keyword_wire_response(payload, request())


def test_secret_like_nested_extension_is_ignored_without_value_capture() -> None:
    payload = live_shape()
    payload["Data"][0]["Keyword"]["Authorization"] = "forbidden-value"  # type: ignore[index]
    capture = parse_asin_request_keyword_wire_response(payload, request())
    assert "Authorization" not in capture.nested_keyword_extensions[0]
    safe = json.dumps(capture.to_safe_dict(), sort_keys=True)
    assert "Authorization" not in safe
    assert "forbidden-value" not in safe


def test_missing_semantic_keyword_field_remains_rejected() -> None:
    payload = live_shape()
    payload["Data"][0]["Keyword"].pop("SearchVolume")  # type: ignore[index]
    with pytest.raises(ProviderConnectorError, match="strict DTO validation"):
        parse_asin_request_keyword_wire_response(payload, request())


def test_sponsored_fields_remain_unavailable_and_unmapped() -> None:
    result = map_payload(live_shape())
    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert '"channel": "SPONSORED"' not in serialized
    assert "SPONSORED_PLACEMENT_UNAVAILABLE" in serialized


def test_extension_order_is_deterministic() -> None:
    first = live_shape()
    second = deepcopy(first)
    for row in second["Data"]:  # type: ignore[index]
        nested = row["Keyword"]
        row["Keyword"] = dict(reversed(tuple(nested.items())))
    assert parse_asin_request_keyword_wire_response(
        first, request()
    ).to_safe_dict() == parse_asin_request_keyword_wire_response(
        second, request()
    ).to_safe_dict()
