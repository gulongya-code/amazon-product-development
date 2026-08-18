"""Immutable contracts for XLSX Operator Delivery Foundation V0.1."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import MISSING, dataclass, fields, is_dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from types import MappingProxyType
import types
from typing import Any, Mapping, Self, Union, get_args, get_origin, get_type_hints

from .errors import (
    XlsxDeliverySerializationError,
    XlsxDeliveryValidationError,
)


XLSX_DELIVERY_RULESET_VERSION = "xlsx-delivery-v0.1"
_EXPORT_RULESET_VERSION = "operator-export-v0.1"
_WORKBOOK_FILENAME = "amazon_product_analysis.xlsx"
_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DANGEROUS_CELL_PREFIXES = ("=", "+", "-", "@")
_FORBIDDEN_KEYS = {
    "api_credential", "api_credentials", "api_key", "api_secret",
    "authorization", "credential", "credentials", "hidden_metadata",
    "hidden_internal_metadata", "internal_metadata", "password", "private_key",
    "raw_payload", "raw_provider_payload", "secret", "token",
}
_FORBIDDEN_KEY_SUFFIXES = (
    "_credential", "_credentials", "_password", "_secret", "_token",
)
_EXPORT_LAYOUT = (
    (
        "product", "product_rows", "01_产品数据",
        (
            "ASIN", "Marketplace", "Title", "Product Facts", "Metrics",
            "Variation", "Reviews", "Quality Indicators", "Source Reference",
        ),
    ),
    (
        "keyword", "keyword_rows", "02_关键词需求",
        (
            "Keyword", "Metrics", "Query Status", "Related Products",
            "Channels", "Providers", "Limitations",
        ),
    ),
    (
        "competition", "competition_rows", "03_竞争证据",
        (
            "Product Endpoint", "Keyword Relationship", "Channel", "Provider",
            "Evidence Count", "Variation Evidence", "Limitations",
        ),
    ),
    (
        "opportunity", "opportunity_rows", "04_机会分析",
        (
            "Product", "Signals", "Missing Evidence", "Risk Evidence",
            "Score References", "Explanation References",
        ),
    ),
    (
        "recommendation", "recommendation_rows", "05_建议与复核",
        (
            "Recommendation Type", "Rule Reference", "Explanation",
            "Evidence References", "Limitations",
        ),
    ),
)
_DELIVERY_LAYOUT = (
    (
        "product", "01_产品数据", "产品数据",
        _EXPORT_LAYOUT[0][3],
    ),
    (
        "keyword", "02_关键词需求", "关键词需求",
        _EXPORT_LAYOUT[1][3],
    ),
    (
        "competition", "03_竞争证据", "竞争证据",
        (
            "Product Endpoint", "Relationship Evidence", "Relationship Type",
            "Channel", "Provider", "Evidence Count", "Variation Evidence",
            "Limitations",
        ),
    ),
    (
        "opportunity", "04_机会分析", "机会分析",
        _EXPORT_LAYOUT[3][3],
    ),
    (
        "recommendation", "05_建议与复核", "建议与复核",
        _EXPORT_LAYOUT[4][3],
    ),
)
_EXPORT_SNAPSHOT_FIELDS = {
    "snapshot_id", "ruleset_version", "source_output_snapshot_id",
    "source_bundle_fingerprints", "table_definitions", "sheet_definitions",
    "rows", "workbook", "coverage", "diagnostics", "lineage_index",
}
_EXPORT_TABLE_FIELDS = {"table_id", "table_key", "columns", "source_view"}
_EXPORT_SHEET_FIELDS = {
    "sheet_id", "ordinal", "sheet_name", "table_id", "columns", "row_source",
    "lineage_reference_ids",
}
_EXPORT_ROW_FIELDS = {
    "export_row_id", "table_id", "sheet_id", "source_output_row_id", "values",
    "lineage_reference_ids",
}
_EXPORT_WORKBOOK_FIELDS = {
    "workbook_id", "filename", "sheet_ids", "metadata",
}
_EXPORT_COVERAGE_FIELDS = {
    "table_count", "sheet_count", "row_count", "lineage_reference_count",
    "diagnostic_count", "row_counts_by_table",
}
_EXPORT_DIAGNOSTIC_FIELDS = {
    "diagnostic_id", "code", "severity", "message",
    "source_output_snapshot_id",
}
_EXPORT_LINEAGE_FIELDS = {
    "export_lineage_id", "export_row_id", "table_id", "sheet_id",
    "source_output_snapshot_id", "source_output_row_id",
    "source_output_lineage_id", "source_snapshot_id", "source_record_id",
    "source_lineage_id", "canonical_reference_id", "canonical_reference_type",
    "semantic_observation_id", "transformation_run_id", "mapping_version",
    "raw_evidence_id", "collection_run_id", "provider", "source_tool",
    "source_field", "source_bundle_fingerprints",
}
_LINEAGE_COPY_FIELDS = tuple(sorted(
    _EXPORT_LINEAGE_FIELDS - {"export_lineage_id", "export_row_id"}
))


def _jsonable(value: Any, path: str = "value") -> Any:
    if isinstance(value, _XlsxModel):
        return {
            field.name: _jsonable(getattr(value, field.name), f"{path}.{field.name}")
            for field in fields(value)
        }
    if is_dataclass(value):
        raise XlsxDeliveryValidationError(f"{path} contains an unsupported dataclass")
    if isinstance(value, MappingABC):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise XlsxDeliveryValidationError(f"{path} keys must be strings")
            result[key] = _jsonable(item, f"{path}.{key}")
        return result
    if isinstance(value, (tuple, list)):
        return [_jsonable(item, f"{path}[{index}]") for index, item in enumerate(value)]
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise XlsxDeliveryValidationError(f"{path} must contain finite JSON data")


def canonical_json(value: Any) -> str:
    return json.dumps(
        _jsonable(value), allow_nan=False, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"),
    )


def deterministic_id(prefix: str, material: Any) -> str:
    _text(prefix, "prefix")
    digest = sha256(canonical_json(material).encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def _freeze_json(value: Any, path: str) -> Any:
    _jsonable(value, path)

    def freeze(item: Any) -> Any:
        if isinstance(item, MappingABC):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, (tuple, list)):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(value)


def _tuple(value: Any, path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise XlsxDeliveryValidationError(f"{path} must be an array")
    return tuple(value)


def _mapping(value: Any, path: str, *, allow_empty: bool = True) -> Mapping[str, Any]:
    frozen = _freeze_json(value, path)
    if not isinstance(frozen, MappingABC) or (not allow_empty and not frozen):
        raise XlsxDeliveryValidationError(f"{path} must be an object")
    return frozen


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise XlsxDeliveryValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _count(value: Any, path: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum:
        raise XlsxDeliveryValidationError(f"{path} must be an integer >= {minimum}")
    return value


def _number(value: Any, path: str, *, positive: bool = False) -> float:
    if type(value) not in {int, float} or isinstance(value, bool):
        raise XlsxDeliveryValidationError(f"{path} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise XlsxDeliveryValidationError(f"{path} must be a finite positive number")
    return result


def _unique_texts(
    value: Any, path: str, *, allow_empty: bool = True, sorted_values: bool = False
) -> tuple[str, ...]:
    result = _tuple(value, path)
    if not allow_empty and not result:
        raise XlsxDeliveryValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in result):
        raise XlsxDeliveryValidationError(f"{path} must contain non-empty text")
    if len(set(result)) != len(result):
        raise XlsxDeliveryValidationError(f"{path} must contain unique values")
    return tuple(sorted(result)) if sorted_values else result


def _exact(value: Any, expected: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC) or set(value) != expected:
        actual = set(value) if isinstance(value, MappingABC) else set()
        raise XlsxDeliveryValidationError(
            f"invalid {path} fields; missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    return value


def _records(
    snapshot: Mapping[str, Any], key: str, expected: set[str]
) -> tuple[Mapping[str, Any], ...]:
    values = _tuple(snapshot[key], f"operator export {key}")
    return tuple(
        _exact(item, expected, f"operator export {key}[{index}]")
        for index, item in enumerate(values)
    )


def _without_id(model: _XlsxModel, field_name: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field_name)
    return payload


def _normalized_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", key.strip().lower()).strip("_")


def _reject_forbidden(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, item in value.items():
            normalized = _normalized_key(key)
            if (
                normalized in _FORBIDDEN_KEYS
                or normalized.endswith(_FORBIDDEN_KEY_SUFFIXES)
            ):
                raise XlsxDeliveryValidationError(
                    f"{path} contains forbidden delivery field {key!r}"
                )
            _reject_forbidden(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _reject_forbidden(item, f"{path}[{index}]")
    elif type(value) is str:
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                decoded = json.loads(stripped)
            except (TypeError, ValueError):
                return
            if isinstance(decoded, (dict, list)):
                _reject_forbidden(decoded, f"{path}<json>")


def _decode(annotation: Any, value: Any, path: str) -> Any:
    if annotation is Any:
        return _freeze_json(value, path)
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in {types.UnionType, Union}:
        if value is None and type(None) in arguments:
            return None
        errors: list[str] = []
        for candidate in arguments:
            if candidate is type(None):
                continue
            try:
                return _decode(candidate, value, path)
            except XlsxDeliveryValidationError as exc:
                errors.append(str(exc))
        raise XlsxDeliveryValidationError(f"{path} does not match its union: {errors}")
    if origin is tuple:
        values = _tuple(value, path)
        item_type = arguments[0] if arguments else Any
        return tuple(
            _decode(item_type, item, f"{path}[{index}]")
            for index, item in enumerate(values)
        )
    if origin in {dict, Mapping, MappingABC}:
        if not isinstance(value, MappingABC):
            raise XlsxDeliveryValidationError(f"{path} must be an object")
        key_type, item_type = arguments or (str, Any)
        if key_type is not str:
            raise XlsxDeliveryValidationError(f"{path} must use string keys")
        if any(type(key) is not str for key in value):
            raise XlsxDeliveryValidationError(f"{path} keys must be strings")
        return MappingProxyType({
            key: _decode(item_type, item, f"{path}.{key}")
            for key, item in value.items()
        })
    if isinstance(annotation, type) and issubclass(annotation, _XlsxModel):
        return annotation.from_dict(value)
    if annotation is str:
        if type(value) is not str:
            raise XlsxDeliveryValidationError(f"{path} must be text")
        return value
    if annotation is bool:
        if type(value) is not bool:
            raise XlsxDeliveryValidationError(f"{path} must be boolean")
        return value
    if annotation is int:
        if type(value) is not int:
            raise XlsxDeliveryValidationError(f"{path} must be integer")
        return value
    if annotation is float:
        return _number(value, path)
    raise XlsxDeliveryValidationError(f"{path} has unsupported annotation {annotation!r}")


class _XlsxModel:
    def to_dict(self) -> dict[str, Any]:
        return _jsonable(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            if not isinstance(payload, MappingABC):
                raise XlsxDeliveryValidationError(f"{cls.__name__} must be an object")
            model_fields = {field.name: field for field in fields(cls)}
            _exact(payload, set(model_fields), cls.__name__)
            hints = get_type_hints(cls)
            values: dict[str, Any] = {}
            for name, field in model_fields.items():
                if name not in payload:
                    if field.default is MISSING and field.default_factory is MISSING:
                        raise XlsxDeliveryValidationError(
                            f"{cls.__name__}.{name} is required"
                        )
                    continue
                values[name] = _decode(
                    hints[name], payload[name], f"{cls.__name__}.{name}"
                )
            return cls(**values)
        except XlsxDeliverySerializationError:
            raise
        except (XlsxDeliveryValidationError, TypeError, ValueError) as exc:
            raise XlsxDeliverySerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


def _column_letter(index: int) -> str:
    _count(index, "column index", positive=True)
    result = ""
    current = index
    while current:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _unsafe_text(value: str) -> bool:
    return value.lstrip().startswith(_DANGEROUS_CELL_PREFIXES)


def _escape_formula(value: str) -> str:
    return f"'{value}" if _unsafe_text(value) else value


def _chunks(value: Any, max_chars: int) -> tuple[Any, ...]:
    if type(value) is not str:
        return (value,)
    raw = tuple(
        value[index:index + max_chars] for index in range(0, len(value), max_chars)
    ) or ("",)
    return tuple(_escape_formula(item) for item in raw)


def _delivery_values(
    table_key: str, values: Mapping[str, Any]
) -> tuple[tuple[str, ...], Mapping[str, Any]]:
    layout = next((item for item in _DELIVERY_LAYOUT if item[0] == table_key), None)
    if layout is None:
        raise XlsxDeliveryValidationError(f"unsupported delivery table {table_key!r}")
    columns = layout[3]
    if table_key != "competition":
        if set(values) != set(columns):
            raise XlsxDeliveryValidationError("export values do not match delivery columns")
        return columns, MappingProxyType({column: values[column] for column in columns})
    relationship_value = values.get("Keyword Relationship")
    if type(relationship_value) is not str:
        raise XlsxDeliveryValidationError("competition relationship must be JSON text")
    try:
        relationship = json.loads(relationship_value)
    except (TypeError, ValueError) as exc:
        raise XlsxDeliveryValidationError("competition relationship JSON is invalid") from exc
    _exact(
        relationship, {"relationship", "relationship_type"},
        "competition relationship",
    )
    rendered = {
        "Product Endpoint": values["Product Endpoint"],
        "Relationship Evidence": canonical_json(relationship["relationship"]),
        "Relationship Type": relationship["relationship_type"],
        "Channel": values["Channel"],
        "Provider": values["Provider"],
        "Evidence Count": values["Evidence Count"],
        "Variation Evidence": values["Variation Evidence"],
        "Limitations": values["Limitations"],
    }
    return columns, MappingProxyType(rendered)


def _chunked_delivery_values(
    columns: tuple[str, ...], values: Mapping[str, Any], max_chars: int
) -> tuple[tuple[Any, ...], ...]:
    by_column = {column: _chunks(values[column], max_chars) for column in columns}
    count = max(len(items) for items in by_column.values())
    return tuple(
        tuple(
            by_column[column][chunk_index]
            if chunk_index < len(by_column[column]) else None
            for column in columns
        )
        for chunk_index in range(count)
    )


def _validate_export_snapshot(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    _exact(payload, _EXPORT_SNAPSHOT_FIELDS, "operator export snapshot")
    snapshot = _freeze_json(payload, "operator export snapshot")
    if snapshot["ruleset_version"] != _EXPORT_RULESET_VERSION:
        raise XlsxDeliveryValidationError("unsupported operator export ruleset")
    _reject_forbidden(snapshot, "operator export snapshot")
    snapshot_id = _text(snapshot["snapshot_id"], "operator export snapshot_id")
    source_output_snapshot_id = _text(
        snapshot["source_output_snapshot_id"],
        "operator export source_output_snapshot_id",
    )
    fingerprints = _unique_texts(
        snapshot["source_bundle_fingerprints"],
        "operator export source_bundle_fingerprints",
        allow_empty=False,
        sorted_values=True,
    )
    if (
        tuple(snapshot["source_bundle_fingerprints"]) != fingerprints
        or any(_SHA256.fullmatch(item) is None for item in fingerprints)
    ):
        raise XlsxDeliveryValidationError("operator export fingerprints are invalid")

    tables = _records(snapshot, "table_definitions", _EXPORT_TABLE_FIELDS)
    if tuple(item["table_key"] for item in tables) != tuple(
        sorted(item[0] for item in _EXPORT_LAYOUT)
    ):
        raise XlsxDeliveryValidationError("operator export table order is invalid")
    table_by_id: dict[str, Mapping[str, Any]] = {}
    table_by_key: dict[str, Mapping[str, Any]] = {}
    for table in tables:
        table_id = _text(table["table_id"], "operator export table_id")
        content = dict(table)
        content.pop("table_id")
        if table_id != deterministic_id("operator-export-table", content):
            raise XlsxDeliveryValidationError("operator export table identity mismatch")
        table_by_id[table_id] = table
        table_by_key[table["table_key"]] = table
    if len(table_by_id) != 5 or len(table_by_key) != 5:
        raise XlsxDeliveryValidationError("operator export table IDs collide")

    sheets = _records(snapshot, "sheet_definitions", _EXPORT_SHEET_FIELDS)
    if tuple(item["ordinal"] for item in sheets) != (1, 2, 3, 4, 5):
        raise XlsxDeliveryValidationError("operator export sheet order is invalid")
    sheet_by_id: dict[str, Mapping[str, Any]] = {}
    for ordinal, (table_key, row_source, sheet_name, columns) in enumerate(
        _EXPORT_LAYOUT, start=1
    ):
        table = table_by_key.get(table_key)
        sheet = sheets[ordinal - 1]
        if table is None or (
            table["source_view"] != row_source
            or tuple(table["columns"]) != columns
            or sheet["ordinal"] != ordinal
            or sheet["sheet_name"] != sheet_name
            or sheet["table_id"] != table["table_id"]
            or tuple(sheet["columns"]) != columns
            or sheet["row_source"] != row_source
        ):
            raise XlsxDeliveryValidationError("operator export layout mismatch")
        sheet_id = _text(sheet["sheet_id"], "operator export sheet_id")
        content = dict(sheet)
        content.pop("sheet_id")
        content.pop("lineage_reference_ids")
        if sheet_id != deterministic_id("operator-export-sheet", content):
            raise XlsxDeliveryValidationError("operator export sheet identity mismatch")
        sheet_by_id[sheet_id] = sheet
    if len(sheet_by_id) != 5:
        raise XlsxDeliveryValidationError("operator export sheet IDs collide")

    rows = _records(snapshot, "rows", _EXPORT_ROW_FIELDS)
    if tuple(item["export_row_id"] for item in rows) != tuple(
        sorted(item["export_row_id"] for item in rows)
    ):
        raise XlsxDeliveryValidationError("operator export row order is invalid")
    row_by_id: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        row_id = _text(row["export_row_id"], "operator export row_id")
        table = table_by_id.get(row["table_id"])
        sheet = sheet_by_id.get(row["sheet_id"])
        if table is None or sheet is None or sheet["table_id"] != table["table_id"]:
            raise XlsxDeliveryValidationError("operator export row source is absent")
        values = row["values"]
        if not isinstance(values, MappingABC) or (
            set(values) != set(table["columns"])
            or any(
                value is not None and type(value) not in {str, bool, int, float}
                for value in values.values()
            )
        ):
            raise XlsxDeliveryValidationError("operator export row values are invalid")
        lineage_ids = _unique_texts(
            row["lineage_reference_ids"],
            "operator export row lineage_reference_ids",
            allow_empty=False,
            sorted_values=True,
        )
        if tuple(row["lineage_reference_ids"]) != lineage_ids:
            raise XlsxDeliveryValidationError("operator export row lineage order is invalid")
        content = dict(row)
        content.pop("export_row_id")
        content.pop("lineage_reference_ids")
        if row_id != deterministic_id("operator-export-row", content):
            raise XlsxDeliveryValidationError("operator export row identity mismatch")
        if row_id in row_by_id:
            raise XlsxDeliveryValidationError("operator export row IDs collide")
        row_by_id[row_id] = row

    lineages = _records(snapshot, "lineage_index", _EXPORT_LINEAGE_FIELDS)
    if tuple(item["export_lineage_id"] for item in lineages) != tuple(
        sorted(item["export_lineage_id"] for item in lineages)
    ):
        raise XlsxDeliveryValidationError("operator export lineage order is invalid")
    lineage_by_id: dict[str, Mapping[str, Any]] = {}
    source_output_lineage_ids: set[str] = set()
    for lineage in lineages:
        lineage_id = _text(lineage["export_lineage_id"], "operator export lineage_id")
        row = row_by_id.get(lineage["export_row_id"])
        if row is None or (
            lineage["table_id"] != row["table_id"]
            or lineage["sheet_id"] != row["sheet_id"]
            or lineage["source_output_row_id"] != row["source_output_row_id"]
            or lineage["source_output_snapshot_id"] != source_output_snapshot_id
            or lineage_id not in row["lineage_reference_ids"]
        ):
            raise XlsxDeliveryValidationError("operator export lineage chain is broken")
        lineage_fingerprints = _unique_texts(
            lineage["source_bundle_fingerprints"],
            "operator export lineage fingerprints",
            allow_empty=False,
            sorted_values=True,
        )
        if (
            tuple(lineage["source_bundle_fingerprints"]) != lineage_fingerprints
            or any(_SHA256.fullmatch(item) is None for item in lineage_fingerprints)
            or not set(lineage_fingerprints) <= set(fingerprints)
        ):
            raise XlsxDeliveryValidationError("operator export lineage fingerprint mismatch")
        for name in _LINEAGE_COPY_FIELDS:
            if name not in {"semantic_observation_id", "source_bundle_fingerprints"}:
                _text(lineage[name], f"operator export lineage.{name}")
        _optional_text(
            lineage["semantic_observation_id"],
            "operator export lineage.semantic_observation_id",
        )
        if lineage["canonical_reference_type"] not in {
            "OBSERVATION", "QUERY_EXECUTION",
        }:
            raise XlsxDeliveryValidationError("operator export reference type is invalid")
        content = dict(lineage)
        content.pop("export_lineage_id")
        if lineage_id != deterministic_id("operator-export-lineage", content):
            raise XlsxDeliveryValidationError("operator export lineage identity mismatch")
        if (
            lineage_id in lineage_by_id
            or lineage["source_output_lineage_id"] in source_output_lineage_ids
        ):
            raise XlsxDeliveryValidationError("operator export lineage IDs collide")
        lineage_by_id[lineage_id] = lineage
        source_output_lineage_ids.add(lineage["source_output_lineage_id"])
    expected_lineage_ids = {
        lineage_id for row in rows for lineage_id in row["lineage_reference_ids"]
    }
    if set(lineage_by_id) != expected_lineage_ids:
        raise XlsxDeliveryValidationError("operator export lineage inventory mismatch")
    for sheet in sheets:
        expected = {
            lineage_id
            for row in rows if row["sheet_id"] == sheet["sheet_id"]
            for lineage_id in row["lineage_reference_ids"]
        }
        if set(sheet["lineage_reference_ids"]) != expected:
            raise XlsxDeliveryValidationError("operator export sheet lineage mismatch")

    workbook = _exact(snapshot["workbook"], _EXPORT_WORKBOOK_FIELDS, "operator export workbook")
    workbook_id = _text(workbook["workbook_id"], "operator export workbook_id")
    if workbook["filename"] != _WORKBOOK_FILENAME or tuple(workbook["sheet_ids"]) != tuple(
        item["sheet_id"] for item in sheets
    ):
        raise XlsxDeliveryValidationError("operator export workbook layout mismatch")
    workbook_content = dict(workbook)
    workbook_content.pop("workbook_id")
    if workbook_id != deterministic_id("operator-export-workbook", workbook_content):
        raise XlsxDeliveryValidationError("operator export workbook identity mismatch")

    diagnostics = _records(snapshot, "diagnostics", _EXPORT_DIAGNOSTIC_FIELDS)
    for diagnostic in diagnostics:
        content = dict(diagnostic)
        diagnostic_id = content.pop("diagnostic_id")
        if diagnostic_id != deterministic_id("operator-export-diagnostic", content):
            raise XlsxDeliveryValidationError("operator export diagnostic identity mismatch")
    coverage = _exact(
        snapshot["coverage"], _EXPORT_COVERAGE_FIELDS, "operator export coverage"
    )
    expected_counts = {
        table["table_key"]: sum(row["table_id"] == table["table_id"] for row in rows)
        for table in tables
    }
    expected_coverage = {
        "table_count": 5,
        "sheet_count": 5,
        "row_count": len(rows),
        "lineage_reference_count": len(lineages),
        "diagnostic_count": len(diagnostics),
        "row_counts_by_table": {
            key: expected_counts[key] for key in sorted(expected_counts)
        },
    }
    if dict(coverage) != expected_coverage:
        raise XlsxDeliveryValidationError("operator export coverage mismatch")
    identity = dict(snapshot)
    identity.pop("snapshot_id")
    if snapshot_id != deterministic_id("operator-export-snapshot", identity):
        raise XlsxDeliveryValidationError("operator export snapshot identity mismatch")
    normalized = _jsonable(snapshot, "operator export snapshot")
    normalized_tables = {
        item["table_id"]: item for item in normalized["table_definitions"]
    }
    for row in normalized["rows"]:
        columns = normalized_tables[row["table_id"]]["columns"]
        row["values"] = {column: row["values"][column] for column in columns}
    return _freeze_json(normalized, "operator export snapshot")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookStyleDefinition(_XlsxModel):
    style_id: str
    font_name: str
    title_font_size: float
    header_font_size: float
    body_font_size: float
    title_fill: str
    header_fill: str
    title_font_color: str
    header_font_color: str
    body_font_color: str
    border_color: str
    wrap_text: bool
    max_cell_chars: int

    def __post_init__(self) -> None:
        _text(self.style_id, "WorkbookStyleDefinition.style_id")
        _text(self.font_name, "WorkbookStyleDefinition.font_name")
        for name in ("title_font_size", "header_font_size", "body_font_size"):
            _number(getattr(self, name), f"WorkbookStyleDefinition.{name}", positive=True)
        for name in (
            "title_fill", "header_fill", "title_font_color",
            "header_font_color", "body_font_color", "border_color",
        ):
            value = getattr(self, name)
            if type(value) is not str or re.fullmatch(r"[0-9A-F]{6}", value) is None:
                raise XlsxDeliveryValidationError(f"{name} must be six-digit uppercase RGB")
        if type(self.wrap_text) is not bool:
            raise XlsxDeliveryValidationError("wrap_text must be boolean")
        _count(self.max_cell_chars, "WorkbookStyleDefinition.max_cell_chars", positive=True)
        if self.max_cell_chars > 32766:
            raise XlsxDeliveryValidationError("max_cell_chars exceeds Excel cell safety limit")
        if self.style_id != deterministic_id(
            "xlsx-style", _without_id(self, "style_id")
        ):
            raise XlsxDeliveryValidationError("style_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorksheetRenderDefinition(_XlsxModel):
    worksheet_id: str
    ordinal: int
    sheet_name: str
    title: str
    source_table_id: str
    source_export_sheet_id: str
    columns: tuple[str, ...]
    column_widths: tuple[float, ...]
    title_row: int
    header_row: int
    data_start_row: int
    freeze_panes: str
    auto_filter_range: str
    source_export_row_ids: tuple[str, ...]
    delivery_row_ids: tuple[str, ...]
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "worksheet_id", "sheet_name", "title", "source_table_id",
            "source_export_sheet_id", "freeze_panes", "auto_filter_range",
        ):
            _text(getattr(self, name), f"WorksheetRenderDefinition.{name}")
        _count(self.ordinal, "WorksheetRenderDefinition.ordinal", positive=True)
        for name in ("title_row", "header_row", "data_start_row"):
            _count(getattr(self, name), f"WorksheetRenderDefinition.{name}", positive=True)
        if (self.title_row, self.header_row, self.data_start_row) != (1, 2, 3):
            raise XlsxDeliveryValidationError("worksheet row layout must be 1/2/3")
        if self.freeze_panes != "A2":
            raise XlsxDeliveryValidationError("V0.1 must freeze the first row")
        columns = _unique_texts(self.columns, "WorksheetRenderDefinition.columns", allow_empty=False)
        widths = tuple(
            _number(item, "WorksheetRenderDefinition.column_width", positive=True)
            for item in _tuple(self.column_widths, "WorksheetRenderDefinition.column_widths")
        )
        if len(columns) != len(widths):
            raise XlsxDeliveryValidationError("column widths do not match columns")
        object.__setattr__(self, "columns", columns)
        object.__setattr__(self, "column_widths", widths)
        object.__setattr__(
            self, "source_export_row_ids",
            _unique_texts(
                self.source_export_row_ids,
                "WorksheetRenderDefinition.source_export_row_ids",
            ),
        )
        object.__setattr__(
            self, "delivery_row_ids",
            _unique_texts(
                self.delivery_row_ids,
                "WorksheetRenderDefinition.delivery_row_ids",
            ),
        )
        object.__setattr__(
            self, "lineage_reference_ids",
            _unique_texts(
                self.lineage_reference_ids,
                "WorksheetRenderDefinition.lineage_reference_ids",
                sorted_values=True,
            ),
        )
        identity = self.to_dict()
        identity.pop("worksheet_id")
        identity.pop("source_export_row_ids")
        identity.pop("delivery_row_ids")
        identity.pop("lineage_reference_ids")
        if self.worksheet_id != deterministic_id("xlsx-worksheet", identity):
            raise XlsxDeliveryValidationError("worksheet_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CellRenderRecord(_XlsxModel):
    cell_id: str
    worksheet_id: str
    delivery_row_id: str
    source_export_row_id: str
    excel_row: int
    excel_column: int
    chunk_index: int
    coordinate: str
    column_name: str
    value: Any
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "cell_id", "worksheet_id", "delivery_row_id", "source_export_row_id",
            "coordinate", "column_name",
        ):
            _text(getattr(self, name), f"CellRenderRecord.{name}")
        _count(self.excel_row, "CellRenderRecord.excel_row", positive=True)
        _count(self.excel_column, "CellRenderRecord.excel_column", positive=True)
        _count(self.chunk_index, "CellRenderRecord.chunk_index")
        if self.excel_row < 3:
            raise XlsxDeliveryValidationError("data cells must start on row 3")
        if self.coordinate != f"{_column_letter(self.excel_column)}{self.excel_row}":
            raise XlsxDeliveryValidationError("cell coordinate does not match row/column")
        value = _freeze_json(self.value, "CellRenderRecord.value")
        if value is not None and type(value) not in {str, bool, int, float}:
            raise XlsxDeliveryValidationError("cell value must be a scalar")
        if type(value) is str and _unsafe_text(value):
            raise XlsxDeliveryValidationError("cell text has an unsafe formula prefix")
        object.__setattr__(self, "value", value)
        object.__setattr__(
            self, "lineage_reference_ids",
            _unique_texts(
                self.lineage_reference_ids,
                "CellRenderRecord.lineage_reference_ids",
                allow_empty=False,
                sorted_values=True,
            ),
        )
        identity = self.to_dict()
        identity.pop("cell_id")
        identity.pop("lineage_reference_ids")
        if self.cell_id != deterministic_id("xlsx-cell", identity):
            raise XlsxDeliveryValidationError("cell_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookDeliveryRecord(_XlsxModel):
    workbook_delivery_id: str
    filename: str
    media_type: str
    content_base64: str
    content_sha256: str
    size_bytes: int
    worksheet_ids: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.workbook_delivery_id, "WorkbookDeliveryRecord.workbook_delivery_id")
        if self.filename != _WORKBOOK_FILENAME or self.media_type != _MEDIA_TYPE:
            raise XlsxDeliveryValidationError("workbook filename or media type is invalid")
        _text(self.content_base64, "WorkbookDeliveryRecord.content_base64")
        if _SHA256.fullmatch(self.content_sha256) is None:
            raise XlsxDeliveryValidationError("content_sha256 is invalid")
        _count(self.size_bytes, "WorkbookDeliveryRecord.size_bytes", positive=True)
        object.__setattr__(
            self, "worksheet_ids",
            _unique_texts(
                self.worksheet_ids, "WorkbookDeliveryRecord.worksheet_ids",
                allow_empty=False,
            ),
        )
        object.__setattr__(
            self, "metadata",
            _mapping(self.metadata, "WorkbookDeliveryRecord.metadata", allow_empty=False),
        )
        try:
            content = base64.b64decode(self.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise XlsxDeliveryValidationError("content_base64 is invalid") from exc
        if (
            len(content) != self.size_bytes
            or sha256(content).hexdigest() != self.content_sha256
        ):
            raise XlsxDeliveryValidationError("workbook content digest or size mismatch")
        if self.workbook_delivery_id != deterministic_id(
            "xlsx-workbook", _without_id(self, "workbook_delivery_id")
        ):
            raise XlsxDeliveryValidationError("workbook_delivery_id does not match content")

    def to_xlsx_bytes(self) -> bytes:
        return base64.b64decode(self.content_base64, validate=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryCoverageSummary(_XlsxModel):
    worksheet_count: int
    source_export_row_count: int
    rendered_row_count: int
    cell_count: int
    lineage_reference_count: int
    diagnostic_count: int

    def __post_init__(self) -> None:
        for name in (
            "worksheet_count", "source_export_row_count", "rendered_row_count",
            "cell_count", "lineage_reference_count", "diagnostic_count",
        ):
            _count(getattr(self, name), f"DeliveryCoverageSummary.{name}")


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryLineageReference(_XlsxModel):
    delivery_lineage_id: str
    worksheet_id: str
    source_export_snapshot_id: str
    source_export_row_id: str
    source_export_lineage_id: str
    table_id: str
    sheet_id: str
    source_output_snapshot_id: str
    source_output_row_id: str
    source_output_lineage_id: str
    source_snapshot_id: str
    source_record_id: str
    source_lineage_id: str
    canonical_reference_id: str
    canonical_reference_type: str
    semantic_observation_id: str | None
    transformation_run_id: str
    mapping_version: str
    raw_evidence_id: str
    collection_run_id: str
    provider: str
    source_tool: str
    source_field: str
    source_bundle_fingerprints: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "delivery_lineage_id", "worksheet_id", "source_export_snapshot_id",
            "source_export_row_id", "source_export_lineage_id", "table_id",
            "sheet_id", "source_output_snapshot_id", "source_output_row_id",
            "source_output_lineage_id", "source_snapshot_id", "source_record_id",
            "source_lineage_id", "canonical_reference_id", "canonical_reference_type",
            "transformation_run_id", "mapping_version", "raw_evidence_id",
            "collection_run_id", "provider", "source_tool", "source_field",
        ):
            _text(getattr(self, name), f"DeliveryLineageReference.{name}")
        _optional_text(
            self.semantic_observation_id,
            "DeliveryLineageReference.semantic_observation_id",
        )
        if self.canonical_reference_type not in {"OBSERVATION", "QUERY_EXECUTION"}:
            raise XlsxDeliveryValidationError("canonical reference type is invalid")
        object.__setattr__(
            self, "source_bundle_fingerprints",
            _unique_texts(
                self.source_bundle_fingerprints,
                "DeliveryLineageReference.source_bundle_fingerprints",
                allow_empty=False,
                sorted_values=True,
            ),
        )
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise XlsxDeliveryValidationError("delivery lineage fingerprints are invalid")
        if self.delivery_lineage_id != deterministic_id(
            "xlsx-lineage", _without_id(self, "delivery_lineage_id")
        ):
            raise XlsxDeliveryValidationError("delivery_lineage_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryDiagnostic(_XlsxModel):
    diagnostic_id: str
    code: str
    severity: str
    message: str
    source_export_snapshot_id: str

    def __post_init__(self) -> None:
        for name in (
            "diagnostic_id", "code", "severity", "message",
            "source_export_snapshot_id",
        ):
            _text(getattr(self, name), f"DeliveryDiagnostic.{name}")
        if self.severity not in {"INFO", "WARNING", "MATERIAL", "BLOCKING"}:
            raise XlsxDeliveryValidationError("delivery diagnostic severity is invalid")
        if self.diagnostic_id != deterministic_id(
            "xlsx-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise XlsxDeliveryValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class XlsxDeliveryRequest(_XlsxModel):
    operator_export_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "operator_export_snapshot",
            _validate_export_snapshot(self.operator_export_snapshot),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class XlsxDeliverySnapshotV0_1(_XlsxModel):
    snapshot_id: str
    ruleset_version: str
    source_export_snapshot_id: str
    source_bundle_fingerprints: tuple[str, ...]
    style: WorkbookStyleDefinition
    worksheet_definitions: tuple[WorksheetRenderDefinition, ...]
    cells: tuple[CellRenderRecord, ...]
    workbook: WorkbookDeliveryRecord
    coverage: DeliveryCoverageSummary
    diagnostics: tuple[DeliveryDiagnostic, ...]
    lineage_index: tuple[DeliveryLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "XlsxDeliverySnapshotV0_1.snapshot_id")
        _text(
            self.source_export_snapshot_id,
            "XlsxDeliverySnapshotV0_1.source_export_snapshot_id",
        )
        if self.ruleset_version != XLSX_DELIVERY_RULESET_VERSION:
            raise XlsxDeliveryValidationError("unsupported XLSX delivery ruleset")
        object.__setattr__(
            self, "source_bundle_fingerprints",
            _unique_texts(
                self.source_bundle_fingerprints,
                "XlsxDeliverySnapshotV0_1.source_bundle_fingerprints",
                allow_empty=False,
                sorted_values=True,
            ),
        )
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise XlsxDeliveryValidationError("delivery source fingerprints are invalid")
        if not isinstance(self.style, WorkbookStyleDefinition):
            raise XlsxDeliveryValidationError("style must be WorkbookStyleDefinition")
        worksheets = tuple(sorted(
            _tuple(self.worksheet_definitions, "worksheet_definitions"),
            key=lambda item: item.ordinal,
        ))
        cells = tuple(sorted(
            _tuple(self.cells, "cells"), key=lambda item: item.cell_id,
        ))
        diagnostics = tuple(sorted(
            _tuple(self.diagnostics, "diagnostics"),
            key=lambda item: item.diagnostic_id,
        ))
        lineages = tuple(sorted(
            _tuple(self.lineage_index, "lineage_index"),
            key=lambda item: item.delivery_lineage_id,
        ))
        if any(not isinstance(item, WorksheetRenderDefinition) for item in worksheets):
            raise XlsxDeliveryValidationError("worksheet_definitions contains wrong type")
        if any(not isinstance(item, CellRenderRecord) for item in cells):
            raise XlsxDeliveryValidationError("cells contains wrong type")
        if any(not isinstance(item, DeliveryDiagnostic) for item in diagnostics):
            raise XlsxDeliveryValidationError("diagnostics contains wrong type")
        if any(not isinstance(item, DeliveryLineageReference) for item in lineages):
            raise XlsxDeliveryValidationError("lineage_index contains wrong type")
        object.__setattr__(self, "worksheet_definitions", worksheets)
        object.__setattr__(self, "cells", cells)
        object.__setattr__(self, "diagnostics", diagnostics)
        object.__setattr__(self, "lineage_index", lineages)
        if not isinstance(self.workbook, WorkbookDeliveryRecord):
            raise XlsxDeliveryValidationError("workbook has wrong type")
        if not isinstance(self.coverage, DeliveryCoverageSummary):
            raise XlsxDeliveryValidationError("coverage has wrong type")
        if len(worksheets) != 5 or tuple(item.ordinal for item in worksheets) != (
            1, 2, 3, 4, 5,
        ):
            raise XlsxDeliveryValidationError("V0.1 requires five ordered worksheets")
        worksheet_by_id = {item.worksheet_id: item for item in worksheets}
        if len(worksheet_by_id) != 5:
            raise XlsxDeliveryValidationError("worksheet IDs collide")
        for worksheet, layout in zip(worksheets, _DELIVERY_LAYOUT, strict=True):
            if worksheet.sheet_name != layout[1] or worksheet.title != layout[2] or worksheet.columns != layout[3]:
                raise XlsxDeliveryValidationError("delivery worksheet layout mismatch")
        if self.workbook.worksheet_ids != tuple(item.worksheet_id for item in worksheets):
            raise XlsxDeliveryValidationError("workbook worksheet order mismatch")
        lineage_by_id = {item.delivery_lineage_id: item for item in lineages}
        if len(lineage_by_id) != len(lineages):
            raise XlsxDeliveryValidationError("delivery lineage IDs collide")
        source_export_lineage_ids: set[str] = set()
        for lineage in lineages:
            if (
                lineage.source_export_snapshot_id != self.source_export_snapshot_id
                or not set(lineage.source_bundle_fingerprints) <= set(
                    self.source_bundle_fingerprints
                )
            ):
                raise XlsxDeliveryValidationError(
                    "delivery lineage source or fingerprint mismatch"
                )
            if lineage.source_export_lineage_id in source_export_lineage_ids:
                raise XlsxDeliveryValidationError(
                    "source export lineage delivered more than once"
                )
            source_export_lineage_ids.add(lineage.source_export_lineage_id)
        cell_by_coordinate: dict[tuple[str, str], CellRenderRecord] = {}
        referenced_lineages: set[str] = set()
        rows_by_worksheet: dict[str, dict[str, list[CellRenderRecord]]] = {
            item.worksheet_id: {} for item in worksheets
        }
        for cell in cells:
            worksheet = worksheet_by_id.get(cell.worksheet_id)
            if worksheet is None or cell.delivery_row_id not in worksheet.delivery_row_ids:
                raise XlsxDeliveryValidationError("cell worksheet or delivery row is absent")
            if cell.source_export_row_id not in worksheet.source_export_row_ids:
                raise XlsxDeliveryValidationError("cell source export row is absent")
            coordinate_key = (cell.worksheet_id, cell.coordinate)
            if coordinate_key in cell_by_coordinate:
                raise XlsxDeliveryValidationError("cell coordinates collide")
            cell_by_coordinate[coordinate_key] = cell
            row_cells = rows_by_worksheet[cell.worksheet_id].setdefault(
                cell.delivery_row_id, []
            )
            row_cells.append(cell)
            for lineage_id in cell.lineage_reference_ids:
                lineage = lineage_by_id.get(lineage_id)
                if lineage is None or (
                    lineage.worksheet_id != cell.worksheet_id
                    or lineage.source_export_row_id != cell.source_export_row_id
                    or lineage.source_export_snapshot_id != self.source_export_snapshot_id
                ):
                    raise XlsxDeliveryValidationError("cell lineage chain is broken")
                referenced_lineages.add(lineage_id)
        if referenced_lineages != set(lineage_by_id):
            raise XlsxDeliveryValidationError("delivery lineage inventory mismatch")
        for worksheet in worksheets:
            row_groups = rows_by_worksheet[worksheet.worksheet_id]
            if set(row_groups) != set(worksheet.delivery_row_ids):
                raise XlsxDeliveryValidationError("worksheet delivery row inventory mismatch")
            expected_rows = list(range(3, 3 + len(worksheet.delivery_row_ids)))
            actual_rows: list[int] = []
            for row_id in worksheet.delivery_row_ids:
                row_cells = row_groups[row_id]
                if len(row_cells) != len(worksheet.columns):
                    raise XlsxDeliveryValidationError("delivery row cell count mismatch")
                ordered = sorted(row_cells, key=lambda item: item.excel_column)
                if tuple(item.excel_column for item in ordered) != tuple(
                    range(1, len(worksheet.columns) + 1)
                ) or tuple(item.column_name for item in ordered) != worksheet.columns:
                    raise XlsxDeliveryValidationError("delivery row columns mismatch")
                if len({item.excel_row for item in ordered}) != 1:
                    raise XlsxDeliveryValidationError("delivery row spans multiple Excel rows")
                actual_rows.append(ordered[0].excel_row)
            if actual_rows != expected_rows:
                raise XlsxDeliveryValidationError("worksheet Excel row order mismatch")
            expected_sheet_lineages = {
                item.delivery_lineage_id
                for item in lineages if item.worksheet_id == worksheet.worksheet_id
            }
            if set(worksheet.lineage_reference_ids) != expected_sheet_lineages:
                raise XlsxDeliveryValidationError("worksheet lineage inventory mismatch")
            last_row = max(2, 2 + len(worksheet.delivery_row_ids))
            expected_filter = f"A2:{_column_letter(len(worksheet.columns))}{last_row}"
            if worksheet.auto_filter_range != expected_filter:
                raise XlsxDeliveryValidationError("worksheet auto filter range mismatch")
        expected_coverage = DeliveryCoverageSummary(
            worksheet_count=len(worksheets),
            source_export_row_count=sum(len(item.source_export_row_ids) for item in worksheets),
            rendered_row_count=sum(len(item.delivery_row_ids) for item in worksheets),
            cell_count=len(cells),
            lineage_reference_count=len(lineages),
            diagnostic_count=len(diagnostics),
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise XlsxDeliveryValidationError("delivery coverage mismatch")
        metadata = self.workbook.metadata
        expected_metadata = {
            "format": "XLSX",
            "media_type": _MEDIA_TYPE,
            "ruleset_version": XLSX_DELIVERY_RULESET_VERSION,
            "source_export_snapshot_id": self.source_export_snapshot_id,
            "renderer": "openpyxl",
            "renderer_version": metadata.get("renderer_version"),
            "formula_escape": "LEADING_APOSTROPHE",
            "max_cell_chars": self.style.max_cell_chars,
            "worksheet_count": len(worksheets),
            "source_export_row_count": self.coverage.source_export_row_count,
            "rendered_row_count": self.coverage.rendered_row_count,
            "cell_count": len(cells),
        }
        _text(metadata.get("renderer_version"), "workbook renderer_version")
        if dict(metadata) != expected_metadata:
            raise XlsxDeliveryValidationError("workbook metadata mismatch")
        expected_id = deterministic_id(
            "xlsx-delivery-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise XlsxDeliverySerializationError("snapshot_id does not match content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_export_snapshot(
        self, operator_export_snapshot: Mapping[str, Any]
    ) -> Self:
        source = _validate_export_snapshot(operator_export_snapshot)
        if source["snapshot_id"] != self.source_export_snapshot_id or tuple(
            source["source_bundle_fingerprints"]
        ) != self.source_bundle_fingerprints:
            raise XlsxDeliveryValidationError("source export snapshot mismatch")
        export_rows = {item["export_row_id"]: item for item in source["rows"]}
        export_lineages = {
            item["export_lineage_id"]: item for item in source["lineage_index"]
        }
        delivered_rows = {
            row_id
            for worksheet in self.worksheet_definitions
            for row_id in worksheet.source_export_row_ids
        }
        if delivered_rows != set(export_rows):
            raise XlsxDeliveryValidationError("source export row inventory mismatch")
        delivered_export_lineage_ids: set[str] = set()
        for lineage in self.lineage_index:
            source_lineage = export_lineages.get(lineage.source_export_lineage_id)
            source_row = export_rows.get(lineage.source_export_row_id)
            if source_lineage is None or source_row is None:
                raise XlsxDeliveryValidationError("delivery lineage source is absent")
            if source_lineage["export_row_id"] != source_row["export_row_id"]:
                raise XlsxDeliveryValidationError("delivery lineage source row mismatch")
            for field_name in _LINEAGE_COPY_FIELDS:
                if getattr(lineage, field_name) != source_lineage[field_name]:
                    raise XlsxDeliveryValidationError(
                        f"delivery lineage changed source field {field_name}"
                    )
            delivered_export_lineage_ids.add(lineage.source_export_lineage_id)
        if delivered_export_lineage_ids != set(export_lineages):
            raise XlsxDeliveryValidationError("source export lineage inventory mismatch")

        table_by_id = {item["table_id"]: item for item in source["table_definitions"]}
        cells_by_worksheet = {
            worksheet.worksheet_id: {
                (cell.excel_row, cell.excel_column): cell
                for cell in self.cells if cell.worksheet_id == worksheet.worksheet_id
            }
            for worksheet in self.worksheet_definitions
        }
        expected_cells: set[tuple[str, int, int]] = set()
        for worksheet in self.worksheet_definitions:
            table = table_by_id[worksheet.source_table_id]
            source_rows = sorted(
                (
                    row for row in source["rows"]
                    if row["table_id"] == worksheet.source_table_id
                    and row["sheet_id"] == worksheet.source_export_sheet_id
                ),
                key=lambda item: item["source_output_row_id"],
            )
            excel_row = 3
            expected_delivery_rows: list[str] = []
            for source_row in source_rows:
                columns, values = _delivery_values(table["table_key"], source_row["values"])
                chunk_rows = _chunked_delivery_values(
                    columns, values, self.style.max_cell_chars
                )
                source_lineage_ids = tuple(sorted(
                    item.delivery_lineage_id for item in self.lineage_index
                    if item.source_export_row_id == source_row["export_row_id"]
                ))
                for chunk_index, chunk_values in enumerate(chunk_rows):
                    row_content = {
                        "worksheet_id": worksheet.worksheet_id,
                        "source_export_row_id": source_row["export_row_id"],
                        "chunk_index": chunk_index,
                        "excel_row": excel_row,
                    }
                    delivery_row_id = deterministic_id("xlsx-row", row_content)
                    expected_delivery_rows.append(delivery_row_id)
                    for column_index, (column, expected_value) in enumerate(
                        zip(columns, chunk_values, strict=True), start=1
                    ):
                        cell = cells_by_worksheet[worksheet.worksheet_id].get(
                            (excel_row, column_index)
                        )
                        if cell is None or (
                            cell.delivery_row_id != delivery_row_id
                            or cell.source_export_row_id != source_row["export_row_id"]
                            or cell.chunk_index != chunk_index
                            or cell.column_name != column
                            or cell.value != expected_value
                            or cell.lineage_reference_ids != source_lineage_ids
                        ):
                            raise XlsxDeliveryValidationError(
                                "rendered cell does not reproduce export content"
                            )
                        expected_cells.add(
                            (worksheet.worksheet_id, excel_row, column_index)
                        )
                    excel_row += 1
            if worksheet.delivery_row_ids != tuple(expected_delivery_rows):
                raise XlsxDeliveryValidationError("rendered row identity mismatch")
        actual_cells = {
            (cell.worksheet_id, cell.excel_row, cell.excel_column)
            for cell in self.cells
        }
        if actual_cells != expected_cells:
            raise XlsxDeliveryValidationError("rendered cell inventory mismatch")
        return self

    def to_json(self) -> str:
        return canonical_json(self)

    def to_xlsx_bytes(self) -> bytes:
        return self.workbook.to_xlsx_bytes()

    def write_xlsx(self, destination: str | Path) -> Path:
        target = Path(destination)
        if target.name != self.workbook.filename:
            raise XlsxDeliveryValidationError(
                f"destination filename must be {self.workbook.filename!r}"
            )
        try:
            with target.open("xb") as stream:
                stream.write(self.to_xlsx_bytes())
        except (FileExistsError, FileNotFoundError, OSError) as exc:
            raise XlsxDeliveryValidationError(
                f"cannot create XLSX delivery at {target}: {exc}"
            ) from exc
        return target


def coverage_from_delivery(
    *,
    worksheets: Sequence[WorksheetRenderDefinition],
    cells: Sequence[CellRenderRecord],
    lineage: Sequence[DeliveryLineageReference],
    diagnostics: Sequence[DeliveryDiagnostic],
) -> DeliveryCoverageSummary:
    return DeliveryCoverageSummary(
        worksheet_count=len(worksheets),
        source_export_row_count=sum(len(item.source_export_row_ids) for item in worksheets),
        rendered_row_count=sum(len(item.delivery_row_ids) for item in worksheets),
        cell_count=len(cells),
        lineage_reference_count=len(lineage),
        diagnostic_count=len(diagnostics),
    )


__all__ = (
    "XLSX_DELIVERY_RULESET_VERSION",
    "XlsxDeliveryRequest",
    "XlsxDeliverySnapshotV0_1",
    "WorkbookStyleDefinition",
    "WorksheetRenderDefinition",
    "CellRenderRecord",
    "WorkbookDeliveryRecord",
    "DeliveryCoverageSummary",
    "DeliveryLineageReference",
    "DeliveryDiagnostic",
)
