from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from amazon_product_intelligence.connectors import (
    SorftimeProductRequest,
    diagnose_product_request_wire_structure,
)


FIXTURES = Path(__file__).parent / "fixtures" / "sorftime_dtos" / "v0_1"
ASIN = "B09265WXY5"


def fixture(name: str = "product_request_success.json") -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def request() -> SorftimeProductRequest:
    return SorftimeProductRequest(ASIN=ASIN, Trend=2)


def diagnostic(payload: object):
    return diagnose_product_request_wire_structure(payload, request(), http_status=200)


def lowercase_payload() -> dict[str, object]:
    payload = fixture()
    data = payload["Data"]
    payload["Data"] = {name.casefold(): value for name, value in data.items()}  # type: ignore[union-attr]
    return payload


def test_current_minimal_payload_is_accepted_without_title() -> None:
    result = diagnostic(fixture())
    assert result.parser_accepted is True
    assert result.parser_failure_kind is None
    assert result.missing_semantic_fields == ("Title",)
    assert result.request_consumed == 1


def test_proven_live_shape_is_accepted_without_promoting_array_drift() -> None:
    payload = fixture()
    data = payload["Data"]
    del data["ListingSalesVolumeOfDaily"]  # type: ignore[index]
    del data["ListingSalesOfDaily"]  # type: ignore[index]
    data["BsrRankTrend"] = []  # type: ignore[index]
    data["DealTrend"] = []  # type: ignore[index]
    data["ListingSalesVolumeOfDailyTrend"] = None  # type: ignore[index]
    data["ListingSalesOfDailyTrend"] = None  # type: ignore[index]

    result = diagnostic(payload)

    assert result.parser_accepted is True
    assert result.parser_failure_kind is None
    assert result.missing_semantic_fields == (
        "ListingSalesOfDaily",
        "ListingSalesVolumeOfDaily",
        "Title",
    )
    status = {item.field_name: item.status for item in result.data_fields}
    assert status["BsrRankTrend"] == "CAPTURED_PROVEN_ARRAY_DRIFT"
    assert status["DealTrend"] == "CAPTURED_PROVEN_ARRAY_DRIFT"
    assert status["ListingSalesOfDailyTrend"] == "CAPTURED_UNVERIFIED"
    assert status["ListingSalesVolumeOfDailyTrend"] == "CAPTURED_UNVERIFIED"


def test_lowercase_shape_reports_names_types_and_casing_only() -> None:
    result = diagnostic(lowercase_payload())
    assert result.parser_accepted is False
    assert result.parser_failure_kind == "WIRE_FIELD_CASING"
    assert result.parser_failure_path == "Data.asin"
    assert "asin->Asin" in result.casing_aliases
    assert "parentasin->ParentAsin" in result.casing_aliases
    assert all(item.status == "CASING_ALIAS_CANDIDATE" for item in result.data_fields)


def test_structure_counts_do_not_retain_variation_or_attribute_values() -> None:
    result = diagnostic(fixture())
    assert result.variation_asin_count == 10
    assert result.attribute_row_count == 2
    assert result.attribute_row_json_types == ("ARRAY", "ARRAY")
    assert result.attribute_row_lengths == (5, 5)
    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert "B09TSGDJLD" not in serialized
    assert "Pink" not in serialized


def test_capture_only_scalar_values_never_enter_diagnostic() -> None:
    payload = fixture("product_request_rich_wire.json")
    result = diagnostic(payload)
    serialized = json.dumps(result.to_dict(), sort_keys=True)
    for forbidden in (
        "Synthetic Insulated Water Bottle",
        "CAPTURE ONLY",
        "1999",
        "4.8",
        "500",
        "https://example.invalid/synthetic.jpg",
    ):
        assert forbidden not in serialized
    assert {item.field_name for item in result.data_fields}.issuperset(
        {"Title", "Price", "Brand", "Rating", "Sales", "Image"}
    )


def test_diagnostic_ordering_is_deterministic() -> None:
    first = fixture("product_request_rich_wire.json")
    second = deepcopy(first)
    data = second["Data"]
    second["Data"] = {name: data[name] for name in reversed(tuple(data))}  # type: ignore[index]
    assert diagnostic(first).to_dict() == diagnostic(second).to_dict()


def test_invalid_title_type_reports_exact_type_path_without_value() -> None:
    payload = fixture()
    payload["Data"]["Title"] = 987654321  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "SEMANTIC_FIELD_TYPE"
    assert result.parser_failure_path == "Data.Title"
    assert "987654321" not in json.dumps(result.to_dict(), sort_keys=True)


def test_missing_required_field_reports_deterministic_path() -> None:
    payload = fixture()
    del payload["Data"]["VariationASINCount"]  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "SEMANTIC_FIELD_MISSING"
    assert result.parser_failure_path == "Data.VariationASINCount"


def test_envelope_shape_remains_strict() -> None:
    payload = fixture()
    payload["trace"] = "not-retained"
    result = diagnostic(payload)
    assert result.parser_failure_kind == "ENVELOPE_SHAPE"
    assert result.parser_failure_path == "$"
    assert "not-retained" not in json.dumps(result.to_dict(), sort_keys=True)


def test_secret_like_root_and_nested_fields_are_redacted() -> None:
    payload = fixture()
    payload["Data"]["Authorization"] = "forbidden-value"  # type: ignore[index]
    payload["Data"]["Metadata"] = {"api_key": "another-forbidden-value"}  # type: ignore[index]
    result = diagnostic(payload)
    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert result.unsafe_field_count == 2
    assert "Authorization" not in serialized
    assert "api_key" not in serialized
    assert "forbidden-value" not in serialized
    assert "another-forbidden-value" not in serialized


def test_non_object_payload_emits_only_safe_envelope_failure() -> None:
    result = diagnostic("arbitrary-business-value")
    assert result.envelope_keys == ()
    assert result.data_fields == ()
    assert result.parser_failure_kind == "ENVELOPE_SHAPE"
    assert "arbitrary-business-value" not in json.dumps(result.to_dict(), sort_keys=True)


def test_committed_census_fixture_contains_structure_only() -> None:
    census = fixture("product_request_r3_structural_census.json")
    groups = census["field_groups"]
    field_count = sum(len(group["field_names"]) for group in groups)  # type: ignore[arg-type,index]
    missing_count = sum(
        len(group["field_names"])
        for group in groups  # type: ignore[union-attr]
        if group["json_type"] == "MISSING"
    )

    assert field_count == census["data_root_field_count"] + missing_count
    assert census["data_root_field_count"] == 65
    assert missing_count == 2
    assert census["casing_aliases"] == []
    assert census["pre_repair_failure"] == {
        "kind": "SEMANTIC_FIELD_MISSING",
        "path": "Data.ListingSalesOfDaily",
    }
    serialized = json.dumps(census, sort_keys=True)
    assert ASIN not in serialized
    for forbidden_key in ("value", "raw", "authorization", "credential", "secret", "token"):
        assert forbidden_key not in serialized.casefold()
