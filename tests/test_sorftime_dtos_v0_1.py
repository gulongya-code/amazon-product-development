from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, is_dataclass
from decimal import Decimal
import json
from pathlib import Path
import socket
from typing import get_args, get_origin, get_type_hints
from unittest.mock import patch

import pytest

from amazon_product_intelligence.connectors import (
    SORFTIME_AMAZON_US,
    ProviderConnectorError,
    ProviderErrorCode,
    SorftimeAsinRequestKeywordRequest,
    SorftimeAsinRequestKeywordResponse,
    SorftimeDomainContext,
    SorftimePageState,
    SorftimeProductRequest,
    SorftimeProductRequestResponse,
    SorftimeWireFieldStatus,
    SorftimeProductVariationsRequest,
    SorftimeProductVariationsResponse,
    SorftimeSalesState,
    parse_asin_request_keyword_response,
    parse_product_request_response,
    parse_product_request_wire_response,
    parse_product_variations_response,
    resolve_sorftime_domain,
    sorftime_dto_json,
)
from amazon_product_intelligence.contracts import ContractValidationError, canonical_json


FIXTURES = Path(__file__).parent / "fixtures" / "sorftime_dtos" / "v0_1"
PRODUCT_ASIN = "B09265WXY5"


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def product_request() -> SorftimeProductRequest:
    return SorftimeProductRequest(ASIN=PRODUCT_ASIN, Trend=2)


def variations_request(*, sales: bool | None = None) -> SorftimeProductVariationsRequest:
    return SorftimeProductVariationsRequest(
        Asin=PRODUCT_ASIN,
        PageIndex=1,
        IsSalesVolume=sales,
    )


def keyword_request(*, page_size: int = 20) -> SorftimeAsinRequestKeywordRequest:
    return SorftimeAsinRequestKeywordRequest(
        ASIN=PRODUCT_ASIN,
        PageIndex=1,
        PageSize=page_size,
    )


def assert_schema_mismatch(callable_) -> ProviderConnectorError:
    with pytest.raises(ProviderConnectorError) as caught:
        callable_()
    assert caught.value.code is ProviderErrorCode.SCHEMA_MISMATCH
    return caught.value


class TestStrictRequestDtos:
    def test_product_request_exact_casing_defaults_and_identity(self) -> None:
        request = SorftimeProductRequest(ASIN=PRODUCT_ASIN, Trend=2)
        assert request.to_provider_body() == {"ASIN": PRODUCT_ASIN, "Trend": 2}
        assert request.request_id() == SorftimeProductRequest(
            ASIN=PRODUCT_ASIN,
            Trend=2,
        ).request_id()
        with pytest.raises(ContractValidationError, match="unknown fields"):
            SorftimeProductRequest.from_dict({"asin": PRODUCT_ASIN, "Trend": 2})

    @pytest.mark.parametrize("asin", ["b09265wxy5", " B09265WXY5", "B09265WXY", True])
    def test_all_request_dtos_reject_non_normalized_asin(self, asin: object) -> None:
        with pytest.raises(ContractValidationError, match="ASIN"):
            SorftimeProductRequest(ASIN=asin, Trend=2)  # type: ignore[arg-type]

    def test_product_request_trend_and_date_rules_are_fail_closed(self) -> None:
        with pytest.raises(ContractValidationError, match="Trend"):
            SorftimeProductRequest(ASIN=PRODUCT_ASIN, Trend=3)
        with pytest.raises(ContractValidationError, match="valid only"):
            SorftimeProductRequest(
                ASIN=PRODUCT_ASIN,
                Trend=2,
                QueryTrendStartDt="2026-08-01",
            )
        with pytest.raises(ContractValidationError, match="requires"):
            SorftimeProductRequest(
                ASIN=PRODUCT_ASIN,
                Trend=1,
                QueryTrendEndDt="2026-08-20",
            )
        with pytest.raises(ContractValidationError, match="precede"):
            SorftimeProductRequest(
                ASIN=PRODUCT_ASIN,
                Trend=1,
                QueryTrendStartDt="2026-08-20",
                QueryTrendEndDt="2026-08-01",
            )
        valid = SorftimeProductRequest(
            ASIN=PRODUCT_ASIN,
            Trend=1,
            QueryTrendStartDt="2026-08-01",
            QueryTrendEndDt="2026-08-20",
        )
        assert valid.to_provider_body()["QueryTrendEndDt"] == "2026-08-20"

    def test_product_variations_omission_never_enables_sales(self) -> None:
        omitted = SorftimeProductVariationsRequest(Asin=PRODUCT_ASIN)
        explicit_false = SorftimeProductVariationsRequest(
            Asin=PRODUCT_ASIN,
            IsSalesVolume=False,
        )
        assert omitted.to_provider_body() == {"Asin": PRODUCT_ASIN, "PageIndex": 1}
        assert omitted.sales_requested is False
        assert explicit_false.sales_requested is False
        assert explicit_false.to_provider_body()["IsSalesVolume"] is False
        with pytest.raises(ContractValidationError, match="PageIndex"):
            SorftimeProductVariationsRequest(Asin=PRODUCT_ASIN, PageIndex=0)
        with pytest.raises(ContractValidationError, match="unknown fields"):
            SorftimeProductVariationsRequest.from_dict({"ASIN": PRODUCT_ASIN})

    @pytest.mark.parametrize("page_size", [19, 201, 20.0, True])
    def test_asin_keyword_page_size_bounds_are_exact(self, page_size: object) -> None:
        with pytest.raises(ContractValidationError, match="PageSize"):
            SorftimeAsinRequestKeywordRequest(
                ASIN=PRODUCT_ASIN,
                PageSize=page_size,  # type: ignore[arg-type]
            )
        assert SorftimeAsinRequestKeywordRequest(ASIN=PRODUCT_ASIN).to_provider_body() == {
            "ASIN": PRODUCT_ASIN,
            "PageIndex": 1,
            "PageSize": 20,
        }

    def test_requests_reject_auth_and_secret_like_fields(self) -> None:
        for forbidden in ("Authorization", "api_key", "token", "password"):
            payload = {"ASIN": PRODUCT_ASIN, "Trend": 2, forbidden: "not-a-real-secret"}
            with pytest.raises(ContractValidationError, match="unknown fields"):
                SorftimeProductRequest.from_dict(payload)

    def test_only_us_domain_one_is_frozen(self) -> None:
        assert resolve_sorftime_domain(1) is SORFTIME_AMAZON_US
        assert SORFTIME_AMAZON_US.to_dict() == {
            "domain": 1,
            "marketplace": "US",
            "currency": "USD",
            "minor_unit_exponent": 2,
        }
        with pytest.raises(ProviderConnectorError) as caught:
            resolve_sorftime_domain(2)
        assert caught.value.code is ProviderErrorCode.CONFIGURATION
        with pytest.raises(ContractValidationError, match="only Sorftime Amazon US"):
            SorftimeDomainContext(
                domain=2,
                marketplace="GB",
                currency="GBP",
                minor_unit_exponent=2,
            )


class TestEnvelopeAndProductRequestDto:
    def test_product_request_success_envelope_and_bounded_structure(self) -> None:
        response = parse_product_request_response(
            load_fixture("product_request_success.json"),
            product_request(),
        )
        assert isinstance(response, SorftimeProductRequestResponse)
        assert response.Code == 0
        assert response.Data.Asin == PRODUCT_ASIN
        assert response.Data.ParentAsin == "B0GS2MHR8Z"
        assert response.Data.has_distinct_parent is True
        assert len(response.Data.VariationASIN or ()) == 10
        assert {(item.Name, item.Value) for item in response.Data.attributes} == {
            ("Color", "Pink"),
            ("Size", "12oz"),
            ("Color", "Blue"),
        }
        assert SorftimeProductRequestResponse.from_dict(response.to_dict()) == response

    @pytest.mark.parametrize(
        ("mutation", "state"),
        [
            (lambda payload: payload.pop("Data"), "MISSING"),
            (lambda payload: payload.__setitem__("Data", None), "EXPLICIT_NULL"),
        ],
    )
    def test_missing_and_null_data_are_distinct(self, mutation, state: str) -> None:
        payload = load_fixture("product_request_success.json")
        mutation(payload)
        error = assert_schema_mismatch(
            lambda: parse_product_request_response(payload, product_request())
        )
        assert error.details["data_state"] == state

    def test_nonzero_business_code_is_not_success(self) -> None:
        payload = load_fixture("product_request_success.json")
        payload.update({"Code": 10, "Message": "invalid parameters", "Data": None})
        with pytest.raises(ProviderConnectorError) as caught:
            parse_product_request_response(payload, product_request())
        assert caught.value.code is ProviderErrorCode.BAD_RESPONSE
        assert caught.value.details["business_code"] == 10
        assert caught.value.details["http_status"] == 200

    def test_http_failure_is_not_a_provider_success_envelope(self) -> None:
        payload = load_fixture("product_request_success.json")
        with pytest.raises(ProviderConnectorError) as caught:
            parse_product_request_response(payload, product_request(), http_status=401)
        assert caught.value.code is ProviderErrorCode.AUTHENTICATION
        assert caught.value.details["http_status"] == 401
        assert caught.value.details["provider_envelope_accepted"] is False

    def test_unknown_envelope_is_rejected_but_safe_data_root_extension_is_captured(self) -> None:
        payload = load_fixture("product_request_success.json")
        payload["Unexpected"] = "value"
        error = assert_schema_mismatch(
            lambda: parse_product_request_response(payload, product_request())
        )
        assert error.details["data_state"] == "PRESENT"

        payload = load_fixture("product_request_success.json")
        payload["Data"]["Unexpected"] = "value"  # type: ignore[index]
        capture = parse_product_request_wire_response(payload, product_request())
        assert capture.extensions == {"Unexpected": "value"}
        assert next(
            item for item in capture.field_inventory if item.field_name == "Unexpected"
        ).status is SorftimeWireFieldStatus.CAPTURED_UNVERIFIED

    def test_variation_count_mismatch_and_malformed_attribute_fail(self) -> None:
        payload = load_fixture("product_request_success.json")
        payload["Data"]["VariationASINCount"] = 9  # type: ignore[index]
        assert_schema_mismatch(lambda: parse_product_request_response(payload, product_request()))

        payload = load_fixture("product_request_success.json")
        payload["Data"]["Attribute"][0] = [PRODUCT_ASIN, "Color"]  # type: ignore[index]
        assert_schema_mismatch(lambda: parse_product_request_response(payload, product_request()))

    def test_request_response_identity_mismatch_is_explicit(self) -> None:
        payload = load_fixture("product_request_success.json")
        payload["Data"]["Asin"] = "B09TSGDJLD"  # type: ignore[index]
        error = assert_schema_mismatch(
            lambda: parse_product_request_response(payload, product_request())
        )
        assert error.details["mismatch"] == "REQUEST_RESPONSE"

    def test_self_parent_is_retained_without_becoming_an_edge(self) -> None:
        payload = load_fixture("product_request_success.json")
        payload["Data"]["ParentAsin"] = PRODUCT_ASIN  # type: ignore[index]
        response = parse_product_request_response(payload, product_request())
        assert response.Data.ParentAsin == PRODUCT_ASIN
        assert response.Data.has_distinct_parent is False

    def test_trend_payload_is_unavailable_not_guessed(self) -> None:
        payload = load_fixture("product_request_success.json")
        payload["Data"]["PriceTrend"] = [20260801, 1999]  # type: ignore[index]
        assert_schema_mismatch(lambda: parse_product_request_response(payload, product_request()))
        with pytest.raises(ProviderConnectorError) as caught:
            parse_product_request_response(
                load_fixture("product_request_success.json"),
                SorftimeProductRequest(ASIN=PRODUCT_ASIN, Trend=1),
            )
        assert caught.value.code is ProviderErrorCode.SCHEMA_MISMATCH


class TestProductVariationsDto:
    def test_valid_ten_row_page_preserves_properties_and_pagination(self) -> None:
        response = parse_product_variations_response(
            load_fixture("product_variations_success.json"),
            variations_request(),
        )
        assert isinstance(response, SorftimeProductVariationsResponse)
        assert len(response.Data) == 10
        assert response.page_state is SorftimePageState.RETURNED
        assert response.provider_total == 10
        assert response.Data[0].properties == (("Color", "Pink"), ("Size", "12oz"))

    def test_minus_one_is_first_class_unknown_never_numeric_sales(self) -> None:
        response = parse_product_variations_response(
            load_fixture("product_variations_success.json"),
            variations_request(),
        )
        assert {row.sales_state for row in response.Data} == {SorftimeSalesState.UNKNOWN}
        assert all(row.sales_value is None for row in response.Data)
        assert all(row.sales_value != -1 and row.sales_value != 0 for row in response.Data)

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda payload: payload["Data"][0].pop("Asin"),
            lambda payload: payload["Data"][1].__setitem__("Asin", PRODUCT_ASIN),
            lambda payload: payload["Data"][0].__setitem__("Property", "Color:Pink,Size"),
            lambda payload: payload["Data"][1].__setitem__("ItemTotal", 11),
            lambda payload: payload["Data"].__setitem__(0, None),
            lambda payload: payload["Data"][0].__setitem__("SalesAmount", -2),
            lambda payload: payload.__setitem__("PageCount", 1),
        ],
    )
    def test_negative_variation_shapes_fail_closed(self, mutation) -> None:
        payload = load_fixture("product_variations_success.json")
        mutation(payload)
        assert_schema_mismatch(
            lambda: parse_product_variations_response(payload, variations_request())
        )

    def test_numeric_sales_require_explicit_sales_request(self) -> None:
        payload = load_fixture("product_variations_success.json")
        payload["Data"][0]["SalesAmount"] = 100  # type: ignore[index]
        error = assert_schema_mismatch(
            lambda: parse_product_variations_response(payload, variations_request())
        )
        assert error.details["mismatch"] == "REQUEST_RESPONSE"
        response = parse_product_variations_response(
            payload,
            variations_request(sales=True),
        )
        assert response.Data[0].sales_state is SorftimeSalesState.AVAILABLE
        assert response.Data[0].sales_value == 100

    def test_empty_page_is_not_zero_sales_or_unfetched_page(self) -> None:
        payload = load_fixture("product_variations_success.json")
        payload["Data"] = []
        response = parse_product_variations_response(payload, variations_request())
        assert response.page_state is SorftimePageState.EMPTY
        assert response.provider_total is None
        assert response.Data == ()


class TestAsinRequestKeywordDto:
    def test_valid_twenty_row_page_retains_boundedness_and_cpc_source_unit(self) -> None:
        response = parse_asin_request_keyword_response(
            load_fixture("asin_request_keyword_success.json"),
            keyword_request(),
        )
        assert isinstance(response, SorftimeAsinRequestKeywordResponse)
        assert len(response.Data) == 20
        assert response.page_state is SorftimePageState.RETURNED
        assert response.relationship_window_days == 30
        assert response.search_result_page_bound == 3
        assert response.provider_total is None
        assert response.complete_keyword_universe is False
        first = response.Data[0]
        assert first.organic_position.page == 1
        assert first.organic_position.timezone is None
        assert first.Keyword.search_volume_period_days == 30
        assert first.Keyword.search_volume_estimate_method is None
        cpc = first.cpc_evidence()
        assert cpc.source_value == 51
        assert cpc.unit_semantics == "LOCAL_MINOR_UNIT"
        assert cpc.major_value == Decimal("0.51")
        assert tuple(item.major_value for item in first.cpc_range_evidence()) == (
            Decimal("0.41"),
            Decimal("0.61"),
        )

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda payload: payload["Data"][0]["Keyword"].pop("Keyword"),
            lambda payload: payload["Data"][0].__setitem__("SearchPosition", "page 1 position 1"),
            lambda payload: payload["Data"][0].__setitem__("SearchPosition", "第4页，第1/48位"),
            lambda payload: payload["Data"][0].__setitem__("ShowShare", 100.01),
            lambda payload: payload["Data"][0]["Keyword"].__setitem__("CpcRange", [60, 40]),
            lambda payload: payload["Data"][0].__setitem__("AdPosition", "sponsored top"),
        ],
    )
    def test_negative_keyword_shapes_fail_closed(self, mutation) -> None:
        payload = load_fixture("asin_request_keyword_success.json")
        mutation(payload)
        assert_schema_mismatch(
            lambda: parse_asin_request_keyword_response(payload, keyword_request())
        )

    def test_zero_cpc_boundary_remains_zero_minor_units(self) -> None:
        payload = load_fixture("asin_request_keyword_success.json")
        payload["Data"][0]["Keyword"].update({"Cpc": 0, "CpcRange": [0, 0]})  # type: ignore[index]
        response = parse_asin_request_keyword_response(payload, keyword_request())
        assert response.Data[0].cpc_evidence().source_value == 0
        assert response.Data[0].cpc_evidence().major_value == Decimal("0.00")

    def test_missing_sponsored_data_is_explicitly_unavailable(self) -> None:
        response = parse_asin_request_keyword_response(
            load_fixture("asin_request_keyword_success.json"),
            keyword_request(),
        )
        assert all(row.AdPosition is None for row in response.Data)
        assert all(row.sponsored_available is False for row in response.Data)

    def test_returned_rows_cannot_exceed_requested_page_size(self) -> None:
        payload = load_fixture("asin_request_keyword_success.json")
        extra = deepcopy(payload["Data"][-1])  # type: ignore[index]
        extra["Keyword"]["Keyword"] = "fixture keyword 21"
        extra["SearchPosition"] = "第3页，第7/48位"
        payload["Data"].append(extra)  # type: ignore[union-attr]
        error = assert_schema_mismatch(
            lambda: parse_asin_request_keyword_response(payload, keyword_request())
        )
        assert error.details["mismatch"] == "REQUEST_RESPONSE"

    def test_empty_keyword_page_is_not_zero_demand_or_complete_universe(self) -> None:
        payload = load_fixture("asin_request_keyword_success.json")
        payload["Data"] = []
        response = parse_asin_request_keyword_response(payload, keyword_request())
        assert response.page_state is SorftimePageState.EMPTY
        assert response.provider_total is None
        assert response.complete_keyword_universe is False
        assert response.Data == ()


class TestDeterminismAndOfflineSafety:
    def test_all_fixtures_are_minimal_valid_json_without_secret_markers(self) -> None:
        markers = {
            "authorization",
            "api_key",
            "apikey",
            "access_token",
            "cookie",
            "password",
            "secret",
            "token",
        }
        files = sorted(FIXTURES.glob("*.json"))
        assert {path.name for path in files} == {
            "asin_request_keyword_success.json",
            "product_request_rich_wire.json",
            "product_request_success.json",
            "product_variations_success.json",
        }
        for path in files:
            payload = json.loads(path.read_text(encoding="utf-8"))
            assert isinstance(payload, dict)
            folded = canonical_json(payload).casefold()
            assert not {marker for marker in markers if marker in folded}

    def test_round_trip_and_mapping_order_are_deterministic(self) -> None:
        cases = (
            (
                SorftimeProductRequestResponse,
                "product_request_success.json",
                lambda payload: parse_product_request_response(payload, product_request()),
            ),
            (
                SorftimeProductVariationsResponse,
                "product_variations_success.json",
                lambda payload: parse_product_variations_response(payload, variations_request()),
            ),
            (
                SorftimeAsinRequestKeywordResponse,
                "asin_request_keyword_success.json",
                lambda payload: parse_asin_request_keyword_response(payload, keyword_request()),
            ),
        )
        for response_type, fixture_name, parser in cases:
            payload = load_fixture(fixture_name)
            reversed_payload = dict(reversed(list(payload.items())))
            first = parser(payload)
            second = parser(reversed_payload)
            assert sorftime_dto_json(first) == sorftime_dto_json(second)
            assert response_type.from_dict(first.to_dict()) == first
            assert sorftime_dto_json(first) == canonical_json(first)

    def test_secret_like_nested_header_field_is_not_representable(self) -> None:
        payload = load_fixture("asin_request_keyword_success.json")
        payload["Data"][0]["Authorization"] = "BasicAuth not-a-real-secret"  # type: ignore[index]
        assert_schema_mismatch(
            lambda: parse_asin_request_keyword_response(payload, keyword_request())
        )

    def test_dto_graph_has_no_credential_or_header_fields(self) -> None:
        forbidden = {
            "authorization",
            "api_key",
            "apikey",
            "credential",
            "cookie",
            "password",
            "secret",
            "token",
        }
        seen: set[type[object]] = set()

        def visit(model: type[object]) -> None:
            if model in seen or not is_dataclass(model):
                return
            seen.add(model)
            assert not {field.name.casefold() for field in fields(model)} & forbidden
            for annotation in get_type_hints(model).values():
                candidates = (annotation, *get_args(annotation))
                for candidate in candidates:
                    origin = get_origin(candidate)
                    target = get_args(candidate)[0] if origin is tuple and get_args(candidate) else candidate
                    if isinstance(target, type) and is_dataclass(target):
                        visit(target)

        for root in (
            SorftimeProductRequest,
            SorftimeProductVariationsRequest,
            SorftimeAsinRequestKeywordRequest,
            SorftimeProductRequestResponse,
            SorftimeProductVariationsResponse,
            SorftimeAsinRequestKeywordResponse,
        ):
            visit(root)

    def test_parsing_constructs_no_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def denied(*args, **kwargs):
            raise AssertionError("network construction is forbidden in SP-040B")

        monkeypatch.setattr(socket, "create_connection", denied)
        with patch("urllib.request.urlopen", side_effect=denied):
            parse_product_request_response(
                load_fixture("product_request_success.json"),
                product_request(),
            )
            parse_product_variations_response(
                load_fixture("product_variations_success.json"),
                variations_request(),
            )
            parse_asin_request_keyword_response(
                load_fixture("asin_request_keyword_success.json"),
                keyword_request(),
            )
