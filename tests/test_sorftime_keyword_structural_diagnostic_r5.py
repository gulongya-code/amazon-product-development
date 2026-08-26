from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from amazon_product_intelligence.connectors import (
    SorftimeAsinRequestKeywordRequest,
    diagnose_asin_request_keyword_wire_structure,
)


FIXTURES = Path(__file__).parent / "fixtures" / "sorftime_dtos" / "v0_1"
ASIN = "B09265WXY5"


def fixture() -> dict[str, object]:
    return json.loads(
        (FIXTURES / "asin_request_keyword_success.json").read_text(encoding="utf-8")
    )


def request() -> SorftimeAsinRequestKeywordRequest:
    return SorftimeAsinRequestKeywordRequest(ASIN=ASIN, PageIndex=1, PageSize=20)


def diagnostic(payload: object):
    return diagnose_asin_request_keyword_wire_structure(payload, request())


def serialized(payload: object) -> str:
    return json.dumps(diagnostic(payload).to_dict(), ensure_ascii=False, sort_keys=True)


def test_existing_keyword_fixture_is_accepted_and_scalar_free() -> None:
    result = diagnostic(fixture())
    assert result.parser_accepted is True
    assert result.parser_failure_kind is None
    assert result.data_json_type == "ARRAY"
    assert result.row_count == 20
    assert result.position_type_container_types == ("ARRAY",)
    assert result.position_type_element_classes == ("ELEMENT_TYPES:STRING",)
    assert result.position_type_cardinality_classes == ("LEN_1",)
    assert result.ad_position_presence_classes == ("NULL",)
    assert result.search_position_format_classes == ("CHINESE_PAGE_1_3",)
    assert result.search_position_date_format_classes == (
        "LOCAL_MINUTE_TIMEZONE_UNKNOWN",
    )
    assert result.cpc_range_length_classes == ("LEN_2",)
    safe = serialized(fixture())
    for forbidden in (
        "fixture keyword 01",
        "第1页，第1/48位",
        "2026-08-26 00:01",
        "1001",
        "0.41",
    ):
        assert forbidden not in safe


def test_row_extra_field_is_classified_without_its_value() -> None:
    payload = fixture()
    payload["Data"][0]["FutureOrganicSignal"] = "never-retain-this"  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "ROW_EXTRA_FIELDS"
    assert result.parser_failure_path == "Data[].FutureOrganicSignal"
    assert "never-retain-this" not in serialized(payload)


def test_nested_keyword_extra_field_is_classified_without_its_value() -> None:
    payload = fixture()
    payload["Data"][0]["Keyword"]["FutureMetric"] = 987654321  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "NESTED_KEYWORD_EXTRA_FIELDS"
    assert result.parser_failure_path == "Data[].Keyword.FutureMetric"
    assert "987654321" not in serialized(payload)


def test_casing_alias_is_diagnostic_only_and_not_accepted() -> None:
    payload = fixture()
    row = payload["Data"][0]  # type: ignore[index]
    row["showtype"] = row.pop("ShowType")
    result = diagnostic(payload)
    assert result.parser_failure_kind == "WIRE_FIELD_CASING"
    assert result.parser_failure_path == "Data[].showtype"
    assert "Data[].showtype->ShowType" in result.casing_aliases


def test_missing_semantic_field_has_exact_safe_path() -> None:
    payload = fixture()
    payload["Data"][0].pop("SearchPosition")  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "SEMANTIC_FIELD_MISSING"
    assert result.parser_failure_path == "Data[].SearchPosition"


def test_position_type_shape_uses_only_type_and_cardinality_classes() -> None:
    payload = fixture()
    payload["Data"][0]["PositionType"] = []  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "POSITION_TYPE_SHAPE"
    assert result.parser_failure_path == "Data[].PositionType"
    assert result.position_type_cardinality_classes == ("LEN_0", "LEN_1")


def test_sponsored_presence_is_classified_but_not_promoted() -> None:
    payload = fixture()
    payload["Data"][0]["AdPosition"] = "do-not-retain-position"  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "SPONSORED_FIELD_PRESENCE"
    assert result.ad_position_presence_classes == ("NONEMPTY_STRING", "NULL")
    assert "do-not-retain-position" not in serialized(payload)


def test_position_date_and_cpc_range_classes_are_narrow() -> None:
    position = fixture()
    position["Data"][0]["SearchPosition"] = "page 1 rank 2"  # type: ignore[index]
    assert diagnostic(position).parser_failure_kind == "SEARCH_POSITION_FORMAT"

    timestamp = fixture()
    timestamp["Data"][0]["SearchPositionDate"] = "2026-08-26T00:01:00Z"  # type: ignore[index]
    assert diagnostic(timestamp).parser_failure_kind == "SEARCH_POSITION_DATE_FORMAT"

    cpc_range = fixture()
    cpc_range["Data"][0]["Keyword"]["CpcRange"] = [1, 2, 3]  # type: ignore[index]
    result = diagnostic(cpc_range)
    assert result.parser_failure_kind == "CPC_RANGE_SHAPE"
    assert result.cpc_range_length_classes == ("LEN_2", "LEN_NOT_2")


def test_diagnostic_ordering_is_deterministic() -> None:
    first = fixture()
    second = deepcopy(first)
    second["Data"] = [dict(reversed(tuple(row.items()))) for row in second["Data"]]  # type: ignore[index]
    assert diagnostic(first).to_dict() == diagnostic(second).to_dict()


def test_secret_like_nested_field_is_redacted_as_structure() -> None:
    payload = fixture()
    payload["Data"][0]["Keyword"]["Authorization"] = "forbidden-secret"  # type: ignore[index]
    result = diagnostic(payload)
    safe = serialized(payload)
    assert result.unsafe_field_count == 1
    assert result.parser_failure_kind == "NESTED_KEYWORD_EXTRA_FIELDS"
    assert result.parser_failure_path == "Data[].Keyword.[REDACTED_UNSAFE]"
    assert "Authorization" not in safe
    assert "forbidden-secret" not in safe


def test_non_array_data_and_non_object_rows_fail_safely() -> None:
    payload = fixture()
    payload["Data"] = {"not": "rows"}
    assert diagnostic(payload).parser_failure_kind == "ENVELOPE_OR_DATA_SHAPE"

    payload = fixture()
    payload["Data"][0] = "never-retain-row"  # type: ignore[index]
    result = diagnostic(payload)
    assert result.parser_failure_kind == "ENVELOPE_OR_DATA_SHAPE"
    assert "never-retain-row" not in serialized(payload)


def test_committed_census_fixture_contains_structure_only() -> None:
    census = json.loads(
        (FIXTURES / "asin_request_keyword_r5_structural_census.json").read_text(
            encoding="utf-8"
        )
    )
    capture_only_count = sum(
        len(names)
        for names in census["nested_capture_only_fields"].values()
    )
    assert capture_only_count == 23
    assert census["row_count"] == 20
    assert census["raw_response_persisted"] is False
    assert census["pre_repair_failure"] == {
        "kind": "NESTED_KEYWORD_EXTRA_FIELDS",
        "path": "Data[].Keyword.ClickConversionRateD90",
    }
    safe = json.dumps(census, sort_keys=True)
    assert ASIN not in safe
    for forbidden in (
        "fixture keyword",
        "authorization",
        "account-sk",
        "basicauth",
        "2026-08-26 00:01",
    ):
        assert forbidden not in safe.casefold()
