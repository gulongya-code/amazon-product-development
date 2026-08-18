"""Immutable public models for Operator Export Foundation V0.1."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping as MappingABC, Sequence
import csv
from dataclasses import dataclass
from hashlib import sha256
import io
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    ContractValidationError,
    JsonContract,
    canonical_json,
    deterministic_id,
)

from .errors import (
    OperatorExportSerializationError,
    OperatorExportValidationError,
)


OPERATOR_EXPORT_RULESET_VERSION = "operator-export-v0.1"
_OUTPUT_RULESET_VERSION = "operator-output-v0.1"
_WORKBOOK_FILENAME = "amazon_product_analysis.xlsx"
_EXPORT_LAYOUT = (
    (
        "product",
        "product_rows",
        "01_产品数据",
        (
            "ASIN", "Marketplace", "Title", "Product Facts", "Metrics",
            "Variation", "Reviews", "Quality Indicators", "Source Reference",
        ),
    ),
    (
        "keyword",
        "keyword_rows",
        "02_关键词需求",
        (
            "Keyword", "Metrics", "Query Status", "Related Products",
            "Channels", "Providers", "Limitations",
        ),
    ),
    (
        "competition",
        "competition_rows",
        "03_竞争证据",
        (
            "Product Endpoint", "Keyword Relationship", "Channel", "Provider",
            "Evidence Count", "Variation Evidence", "Limitations",
        ),
    ),
    (
        "opportunity",
        "opportunity_rows",
        "04_机会分析",
        (
            "Product", "Signals", "Missing Evidence", "Risk Evidence",
            "Score References", "Explanation References",
        ),
    ),
    (
        "recommendation",
        "recommendation_rows",
        "05_建议与复核",
        (
            "Recommendation Type", "Rule Reference", "Explanation",
            "Evidence References", "Limitations",
        ),
    ),
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_SNAPSHOT_KEYS = {
    "product_intelligence", "demand_intelligence", "competition_intelligence",
    "opportunity_intelligence", "opportunity_scoring", "recommendation_framework",
}
_OUTPUT_SNAPSHOT_FIELDS = {
    "snapshot_id", "ruleset_version", "source_bundle_fingerprints",
    "source_snapshot_ids", "product_rows", "keyword_rows", "competition_rows",
    "opportunity_rows", "recommendation_rows", "coverage", "diagnostics",
    "lineage_index",
}
_PRODUCT_ROW_FIELDS = {
    "output_row_id", "asin", "marketplace", "title", "product_facts", "metrics",
    "variation_information", "review_summary", "data_quality_indicators",
    "source_snapshot_id", "lineage_reference_ids",
}
_KEYWORD_ROW_FIELDS = {
    "output_row_id", "keyword", "keyword_metrics", "query_status",
    "related_products", "channels", "providers", "limitations",
    "source_snapshot_id", "lineage_reference_ids",
}
_COMPETITION_ROW_FIELDS = {
    "output_row_id", "product_endpoint", "keyword_relationship", "relationship_type",
    "channel", "provider", "evidence_count", "variation_evidence", "limitations",
    "source_snapshot_id", "lineage_reference_ids",
}
_OPPORTUNITY_ROW_FIELDS = {
    "output_row_id", "product", "signals", "missing_evidence", "risk_evidence",
    "score_references", "explanation_references", "source_snapshot_ids",
    "lineage_reference_ids",
}
_RECOMMENDATION_ROW_FIELDS = {
    "output_row_id", "recommendation_type", "rule_reference", "explanation",
    "evidence_references", "limitations", "source_record_id", "source_snapshot_id",
    "lineage_reference_ids",
}
_OUTPUT_LINEAGE_FIELDS = {
    "output_lineage_id", "output_row_id", "output_view", "source_snapshot_id",
    "source_record_id", "source_lineage_id", "canonical_reference_id",
    "canonical_reference_type", "semantic_observation_id", "transformation_run_id",
    "mapping_version", "raw_evidence_id", "collection_run_id", "provider",
    "source_tool", "source_field", "source_bundle_fingerprints",
}
_OUTPUT_DIAGNOSTIC_FIELDS = {
    "diagnostic_id", "code", "severity", "message", "source_snapshot_ids",
}
_OUTPUT_COVERAGE_FIELDS = {
    "product_row_count", "keyword_row_count", "competition_row_count",
    "opportunity_row_count", "recommendation_row_count", "source_snapshot_count",
    "lineage_reference_count", "diagnostic_count",
}
_ROW_SPECS = {
    "product_rows": (_PRODUCT_ROW_FIELDS, "operator-product-row", "PRODUCT"),
    "keyword_rows": (_KEYWORD_ROW_FIELDS, "operator-keyword-row", "KEYWORD"),
    "competition_rows": (
        _COMPETITION_ROW_FIELDS, "operator-competition-row", "COMPETITION_EVIDENCE",
    ),
    "opportunity_rows": (
        _OPPORTUNITY_ROW_FIELDS, "operator-opportunity-row", "OPPORTUNITY",
    ),
    "recommendation_rows": (
        _RECOMMENDATION_ROW_FIELDS, "operator-recommendation-row", "RECOMMENDATION",
    ),
}
_FORBIDDEN_EXPORT_KEYS = {
    "api_credential", "api_credentials", "api_key", "api_secret", "authorization",
    "credential", "credentials", "hidden_metadata", "password", "raw_payload",
    "raw_provider_payload", "secret", "token", "internal_metadata",
    "hidden_internal_metadata", "private_key",
}
_FORBIDDEN_EXPORT_KEY_SUFFIXES = (
    "_credential", "_credentials", "_password", "_secret", "_token",
)


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise OperatorExportValidationError(
            f"{path} must contain finite JSON data: {exc}"
        ) from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OperatorExportValidationError(f"{path} must be a sequence")
    return tuple(value)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OperatorExportValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _count(value: Any, path: str, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0):
        qualifier = "positive" if positive else "non-negative"
        raise OperatorExportValidationError(f"{path} must be a {qualifier} integer")
    return value


def _mapping(value: Any, path: str, *, allow_empty: bool = True) -> Mapping[str, Any]:
    frozen = _freeze_json(value, path)
    if not isinstance(frozen, MappingABC) or (not allow_empty and not frozen):
        raise OperatorExportValidationError(f"{path} must be an object")
    return frozen


def _unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise OperatorExportValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise OperatorExportValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise OperatorExportValidationError(f"{path} must contain unique values")
    return tuple(values)


def _sorted_unique_texts(
    value: Sequence[str], path: str, *, allow_empty: bool = True
) -> tuple[str, ...]:
    return tuple(sorted(_unique_texts(value, path, allow_empty=allow_empty)))


def _typed_unique(value: Sequence[Any], expected: type, path: str, key) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise OperatorExportValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({canonical_json(item) for item in ordered}) != len(ordered):
        raise OperatorExportValidationError(f"{path} contains duplicates")
    return ordered


def _without_id(model: JsonContract, field: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field)
    return payload


def _row_identity(model: JsonContract) -> str:
    payload = model.to_dict()
    payload.pop("export_row_id")
    payload.pop("lineage_reference_ids")
    return deterministic_id("operator-export-row", payload)


def _sheet_identity(model: JsonContract) -> str:
    payload = model.to_dict()
    payload.pop("sheet_id")
    payload.pop("lineage_reference_ids")
    return deterministic_id("operator-export-sheet", payload)


def _reject_forbidden_keys(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, item in value.items():
            normalized_key = re.sub(
                r"[^a-z0-9]+", "_", key.strip().lower()
            ).strip("_")
            if (
                normalized_key in _FORBIDDEN_EXPORT_KEYS
                or normalized_key.endswith(_FORBIDDEN_EXPORT_KEY_SUFFIXES)
            ):
                raise OperatorExportValidationError(
                    f"{path} contains forbidden export field {key!r}"
                )
            _reject_forbidden_keys(item, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, item in enumerate(value):
            _reject_forbidden_keys(item, f"{path}[{index}]")


def _identifier_values(value: Any, key: str = "") -> set[str]:
    result: set[str] = set()
    if isinstance(value, MappingABC):
        for child_key, child in value.items():
            result.update(_identifier_values(child, child_key))
    elif isinstance(value, tuple):
        if key.endswith("_ids"):
            result.update(item for item in value if type(item) is str and item.strip())
        for child in value:
            result.update(_identifier_values(child, key))
    elif key.endswith("_id") and type(value) is str and value.strip():
        result.add(value)
    return result


def bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    payload = bundle.to_dict()
    for key, value in tuple(payload.items()):
        if isinstance(value, list):
            payload[key] = sorted(value, key=canonical_json)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _exact(value: Any, fields: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC) or set(value) != fields:
        actual = set(value) if isinstance(value, MappingABC) else set()
        raise OperatorExportValidationError(
            f"invalid {path} fields; missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)}"
        )
    return value


def _source_records(
    snapshot: Mapping[str, Any], key: str, fields: set[str]
) -> tuple[Mapping[str, Any], ...]:
    values = snapshot[key]
    if not isinstance(values, tuple):
        raise OperatorExportValidationError(f"operator output {key} must be an array")
    return tuple(
        _exact(item, fields, f"operator output {key}[{index}]")
        for index, item in enumerate(values)
    )


def _validate_source_output_snapshot(
    payload: Mapping[str, Any], fingerprints: set[str]
) -> Mapping[str, Any]:
    _exact(payload, _OUTPUT_SNAPSHOT_FIELDS, "operator output snapshot")
    snapshot = _freeze_json(payload, "operator output snapshot")
    if snapshot["ruleset_version"] != _OUTPUT_RULESET_VERSION:
        raise OperatorExportValidationError("unsupported operator output ruleset")
    source_fingerprints = _sorted_unique_texts(
        snapshot["source_bundle_fingerprints"],
        "operator output source_bundle_fingerprints",
        allow_empty=False,
    )
    if (
        any(_SHA256.fullmatch(item) is None for item in source_fingerprints)
        or set(source_fingerprints) != fingerprints
        or tuple(snapshot["source_bundle_fingerprints"]) != source_fingerprints
    ):
        raise OperatorExportValidationError("operator output bundle fingerprints mismatch")
    source_ids = _exact(
        snapshot["source_snapshot_ids"], _SOURCE_SNAPSHOT_KEYS,
        "operator output source_snapshot_ids",
    )
    if any(type(value) is not str or not value.strip() for value in source_ids.values()):
        raise OperatorExportValidationError("operator output source snapshot ID is invalid")
    if len(set(source_ids.values())) != len(source_ids):
        raise OperatorExportValidationError("operator output source snapshot IDs collide")

    rows_by_id: dict[str, tuple[Mapping[str, Any], str]] = {}
    expected_counts: dict[str, int] = {}
    for key, (fields, prefix, view) in _ROW_SPECS.items():
        rows = _source_records(snapshot, key, fields)
        expected_counts[key] = len(rows)
        for row in rows:
            row_id = _text(row["output_row_id"], f"operator output {key}.output_row_id")
            content = dict(row)
            content.pop("output_row_id")
            content.pop("lineage_reference_ids")
            if row_id != deterministic_id(prefix, content):
                raise OperatorExportValidationError("operator output row identity mismatch")
            lineage_ids = _sorted_unique_texts(
                row["lineage_reference_ids"],
                f"operator output {key}.lineage_reference_ids",
                allow_empty=False,
            )
            if row_id in rows_by_id:
                raise OperatorExportValidationError("operator output row ID collision")
            rows_by_id[row_id] = (row, view)
            if tuple(lineage_ids) != tuple(row["lineage_reference_ids"]):
                raise OperatorExportValidationError("operator output row lineage order mismatch")

    lineages = _source_records(snapshot, "lineage_index", _OUTPUT_LINEAGE_FIELDS)
    lineage_by_id: dict[str, Mapping[str, Any]] = {}
    referenced: set[str] = set()
    for lineage in lineages:
        lineage_id = _text(lineage["output_lineage_id"], "operator output lineage ID")
        content = dict(lineage)
        content.pop("output_lineage_id")
        if lineage_id != deterministic_id("operator-output-lineage", content):
            raise OperatorExportValidationError("operator output lineage identity mismatch")
        row_entry = rows_by_id.get(lineage["output_row_id"])
        if row_entry is None or lineage["output_view"] != row_entry[1]:
            raise OperatorExportValidationError("operator output lineage row or view mismatch")
        row, _ = row_entry
        if lineage_id not in row["lineage_reference_ids"]:
            raise OperatorExportValidationError("operator output lineage is not referenced")
        source_ids_in_row = _identifier_values(row)
        source_ids_in_row.discard(row["output_row_id"])
        source_ids_in_row.difference_update(row["lineage_reference_ids"])
        if (
            lineage["source_record_id"] not in source_ids_in_row
            or lineage["source_snapshot_id"] not in source_ids_in_row
        ):
            raise OperatorExportValidationError("operator output source is absent")
        lineage_fingerprints = _sorted_unique_texts(
            lineage["source_bundle_fingerprints"],
            "operator output lineage source_bundle_fingerprints",
            allow_empty=False,
        )
        if (
            any(_SHA256.fullmatch(item) is None for item in lineage_fingerprints)
            or tuple(lineage["source_bundle_fingerprints"]) != lineage_fingerprints
            or not set(lineage_fingerprints) <= fingerprints
        ):
            raise OperatorExportValidationError("operator output lineage fingerprint mismatch")
        if lineage_id in lineage_by_id:
            raise OperatorExportValidationError("operator output lineage ID collision")
        lineage_by_id[lineage_id] = lineage
        referenced.add(lineage_id)
    expected_lineage_ids = {
        lineage_id
        for row, _ in rows_by_id.values()
        for lineage_id in row["lineage_reference_ids"]
    }
    if referenced != expected_lineage_ids:
        raise OperatorExportValidationError("operator output lineage inventory mismatch")

    diagnostics = _source_records(snapshot, "diagnostics", _OUTPUT_DIAGNOSTIC_FIELDS)
    for diagnostic in diagnostics:
        content = dict(diagnostic)
        diagnostic_id = content.pop("diagnostic_id")
        if diagnostic_id != deterministic_id("operator-output-diagnostic", content):
            raise OperatorExportValidationError("operator output diagnostic identity mismatch")
    coverage = _exact(snapshot["coverage"], _OUTPUT_COVERAGE_FIELDS, "operator output coverage")
    expected_coverage = {
        "product_row_count": expected_counts["product_rows"],
        "keyword_row_count": expected_counts["keyword_rows"],
        "competition_row_count": expected_counts["competition_rows"],
        "opportunity_row_count": expected_counts["opportunity_rows"],
        "recommendation_row_count": expected_counts["recommendation_rows"],
        "source_snapshot_count": len(source_ids),
        "lineage_reference_count": len(lineages),
        "diagnostic_count": len(diagnostics),
    }
    if dict(coverage) != expected_coverage:
        raise OperatorExportValidationError("operator output coverage mismatch")
    snapshot_id = _text(snapshot["snapshot_id"], "operator output snapshot_id")
    identity = dict(snapshot)
    identity.pop("snapshot_id")
    if snapshot_id != deterministic_id("operator-output-snapshot", identity):
        raise OperatorExportValidationError("operator output snapshot identity mismatch")
    _reject_forbidden_keys(snapshot, "operator output snapshot")
    return snapshot


class _OperatorExportModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OperatorExportSerializationError:
            raise
        except (
            OperatorExportValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise OperatorExportSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportTableDefinition(_OperatorExportModel):
    """Fixed column schema for one exported operator table."""

    table_id: str
    table_key: str
    columns: tuple[str, ...]
    source_view: str

    def __post_init__(self) -> None:
        for name in ("table_id", "table_key", "source_view"):
            _text(getattr(self, name), f"ExportTableDefinition.{name}")
        object.__setattr__(
            self, "columns", _unique_texts(self.columns, "ExportTableDefinition.columns", allow_empty=False)
        )
        if self.table_id != deterministic_id(
            "operator-export-table", _without_id(self, "table_id")
        ):
            raise OperatorExportValidationError("table_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportSheetDefinition(_OperatorExportModel):
    """One deterministic workbook sheet and its lineage inventory."""

    sheet_id: str
    ordinal: int
    sheet_name: str
    table_id: str
    columns: tuple[str, ...]
    row_source: str
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _count(self.ordinal, "ExportSheetDefinition.ordinal", positive=True)
        for name in ("sheet_id", "sheet_name", "table_id", "row_source"):
            _text(getattr(self, name), f"ExportSheetDefinition.{name}")
        object.__setattr__(
            self, "columns", _unique_texts(self.columns, "ExportSheetDefinition.columns", allow_empty=False)
        )
        object.__setattr__(
            self,
            "lineage_reference_ids",
            _sorted_unique_texts(
                self.lineage_reference_ids, "ExportSheetDefinition.lineage_reference_ids"
            ),
        )
        if self.sheet_id != _sheet_identity(self):
            raise OperatorExportValidationError("sheet_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportRowRecord(_OperatorExportModel):
    """One CSV-ready row copied from one Operator Output row."""

    export_row_id: str
    table_id: str
    sheet_id: str
    source_output_row_id: str
    values: Mapping[str, Any]
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("export_row_id", "table_id", "sheet_id", "source_output_row_id"):
            _text(getattr(self, name), f"ExportRowRecord.{name}")
        if not isinstance(self.values, MappingABC) or not self.values:
            raise OperatorExportValidationError(
                "ExportRowRecord.values must be a non-empty object"
            )
        values = dict(self.values)
        _freeze_json(values, "ExportRowRecord.values")
        if any(
            value is not None and type(value) not in {str, bool, int, float}
            for value in values.values()
        ):
            raise OperatorExportValidationError("export row values must be CSV-safe scalars")
        object.__setattr__(self, "values", MappingProxyType(values))
        object.__setattr__(
            self,
            "lineage_reference_ids",
            _sorted_unique_texts(
                self.lineage_reference_ids,
                "ExportRowRecord.lineage_reference_ids",
                allow_empty=False,
            ),
        )
        if self.export_row_id != _row_identity(self):
            raise OperatorExportValidationError("export_row_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportWorkbookRecord(_OperatorExportModel):
    """Workbook representation without binary XLSX generation."""

    workbook_id: str
    filename: str
    sheet_ids: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        _text(self.workbook_id, "ExportWorkbookRecord.workbook_id")
        if self.filename != _WORKBOOK_FILENAME:
            raise OperatorExportValidationError("unsupported workbook filename")
        object.__setattr__(
            self, "sheet_ids", _unique_texts(self.sheet_ids, "ExportWorkbookRecord.sheet_ids", allow_empty=False)
        )
        object.__setattr__(
            self, "metadata", _mapping(self.metadata, "ExportWorkbookRecord.metadata", allow_empty=False)
        )
        if self.workbook_id != deterministic_id(
            "operator-export-workbook", _without_id(self, "workbook_id")
        ):
            raise OperatorExportValidationError("workbook_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportLineageReference(_OperatorExportModel):
    """Export-row link through Operator Output to one canonical emission."""

    export_lineage_id: str
    export_row_id: str
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
            "export_lineage_id", "export_row_id", "table_id", "sheet_id",
            "source_output_snapshot_id", "source_output_row_id",
            "source_output_lineage_id", "source_snapshot_id", "source_record_id",
            "source_lineage_id", "canonical_reference_id",
            "canonical_reference_type",
            "transformation_run_id", "mapping_version", "raw_evidence_id",
            "collection_run_id", "provider", "source_tool", "source_field",
        ):
            _text(getattr(self, name), f"ExportLineageReference.{name}")
        _optional_text(self.semantic_observation_id, "ExportLineageReference.semantic_observation_id")
        if self.canonical_reference_type not in {"OBSERVATION", "QUERY_EXECUTION"}:
            raise OperatorExportValidationError("unsupported canonical reference type")
        if self.canonical_reference_type == "OBSERVATION" and self.semantic_observation_id is None:
            raise OperatorExportValidationError("observation export lineage requires semantic ID")
        object.__setattr__(
            self,
            "source_bundle_fingerprints",
            _sorted_unique_texts(
                self.source_bundle_fingerprints,
                "ExportLineageReference.source_bundle_fingerprints",
                allow_empty=False,
            ),
        )
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise OperatorExportValidationError("export lineage fingerprints must be SHA-256 hex")
        if self.export_lineage_id != deterministic_id(
            "operator-export-lineage", _without_id(self, "export_lineage_id")
        ):
            raise OperatorExportValidationError("export_lineage_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportDiagnostic(_OperatorExportModel):
    """Deterministic export-boundary diagnostic."""

    diagnostic_id: str
    code: str
    severity: str
    message: str
    source_output_snapshot_id: str

    def __post_init__(self) -> None:
        for name in (
            "diagnostic_id", "code", "severity", "message", "source_output_snapshot_id",
        ):
            _text(getattr(self, name), f"ExportDiagnostic.{name}")
        if self.severity not in {"INFO", "WARNING", "MATERIAL", "BLOCKING"}:
            raise OperatorExportValidationError("invalid export diagnostic severity")
        if self.diagnostic_id != deterministic_id(
            "operator-export-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise OperatorExportValidationError("export diagnostic ID mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExportCoverageSummary(_OperatorExportModel):
    """Mechanical export inventory counts."""

    table_count: int
    sheet_count: int
    row_count: int
    lineage_reference_count: int
    diagnostic_count: int
    row_counts_by_table: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "table_count", "sheet_count", "row_count", "lineage_reference_count",
            "diagnostic_count",
        ):
            _count(getattr(self, name), f"ExportCoverageSummary.{name}")
        counts = _mapping(self.row_counts_by_table, "ExportCoverageSummary.row_counts_by_table")
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise OperatorExportValidationError("row_counts_by_table values are invalid")
        object.__setattr__(self, "row_counts_by_table", counts)


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorExportRequest(_OperatorExportModel):
    """Canonical bundles and one serialized Operator Output snapshot."""

    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    operator_output_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        bundles = _tuple(self.canonical_bundles, "canonical_bundles")
        if not bundles or any(not isinstance(item, CanonicalEvidenceBundle) for item in bundles):
            raise OperatorExportValidationError(
                "canonical_bundles must contain CanonicalEvidenceBundle values"
            )
        for bundle in bundles:
            bundle.validate()
        ordered = tuple(sorted(bundles, key=bundle_fingerprint))
        fingerprints = tuple(bundle_fingerprint(item) for item in ordered)
        if len(set(fingerprints)) != len(fingerprints):
            raise OperatorExportValidationError("canonical_bundles contain duplicate content")
        object.__setattr__(self, "canonical_bundles", ordered)
        object.__setattr__(
            self,
            "operator_output_snapshot",
            _validate_source_output_snapshot(
                self.operator_output_snapshot, set(fingerprints)
            ),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorExportSnapshotV0_1(_OperatorExportModel):
    """Deterministic workbook and CSV-ready export snapshot."""

    snapshot_id: str
    ruleset_version: str
    source_output_snapshot_id: str
    source_bundle_fingerprints: tuple[str, ...]
    table_definitions: tuple[ExportTableDefinition, ...]
    sheet_definitions: tuple[ExportSheetDefinition, ...]
    rows: tuple[ExportRowRecord, ...]
    workbook: ExportWorkbookRecord
    coverage: ExportCoverageSummary
    diagnostics: tuple[ExportDiagnostic, ...]
    lineage_index: tuple[ExportLineageReference, ...]

    def __post_init__(self) -> None:
        for name in ("snapshot_id", "source_output_snapshot_id"):
            _text(getattr(self, name), f"OperatorExportSnapshotV0_1.{name}")
        if self.ruleset_version != OPERATOR_EXPORT_RULESET_VERSION:
            raise OperatorExportValidationError("unsupported operator export ruleset")
        object.__setattr__(
            self,
            "source_bundle_fingerprints",
            _sorted_unique_texts(
                self.source_bundle_fingerprints,
                "operator export source_bundle_fingerprints",
                allow_empty=False,
            ),
        )
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise OperatorExportValidationError("operator export fingerprints are invalid")
        object.__setattr__(
            self,
            "table_definitions",
            _typed_unique(
                self.table_definitions, ExportTableDefinition,
                "operator export table_definitions", lambda item: item.table_key,
            ),
        )
        sheets = _typed_unique(
            self.sheet_definitions, ExportSheetDefinition,
            "operator export sheet_definitions", lambda item: item.ordinal,
        )
        object.__setattr__(self, "sheet_definitions", sheets)
        object.__setattr__(
            self,
            "rows",
            _typed_unique(
                self.rows, ExportRowRecord, "operator export rows",
                lambda item: item.export_row_id,
            ),
        )
        object.__setattr__(
            self,
            "diagnostics",
            _typed_unique(
                self.diagnostics, ExportDiagnostic, "operator export diagnostics",
                lambda item: item.diagnostic_id,
            ),
        )
        object.__setattr__(
            self,
            "lineage_index",
            _typed_unique(
                self.lineage_index, ExportLineageReference,
                "operator export lineage_index", lambda item: item.export_lineage_id,
            ),
        )
        if not isinstance(self.workbook, ExportWorkbookRecord):
            raise OperatorExportValidationError("workbook must be ExportWorkbookRecord")
        if not isinstance(self.coverage, ExportCoverageSummary):
            raise OperatorExportValidationError("coverage must be ExportCoverageSummary")
        if len(self.table_definitions) != 5 or len(sheets) != 5:
            raise OperatorExportValidationError("V0.1 requires exactly five tables and sheets")
        if tuple(item.ordinal for item in sheets) != (1, 2, 3, 4, 5):
            raise OperatorExportValidationError("sheet ordinals must be 1 through 5")
        table_by_id = {item.table_id: item for item in self.table_definitions}
        table_by_key = {item.table_key: item for item in self.table_definitions}
        sheet_by_id = {item.sheet_id: item for item in sheets}
        if (
            len(table_by_id) != 5
            or len(table_by_key) != 5
            or len(sheet_by_id) != 5
        ):
            raise OperatorExportValidationError("table or sheet IDs collide")
        if set(table_by_key) != {item[0] for item in _EXPORT_LAYOUT}:
            raise OperatorExportValidationError("V0.1 table inventory mismatch")
        for ordinal, (table_key, row_source, sheet_name, columns) in enumerate(
            _EXPORT_LAYOUT, start=1
        ):
            table = table_by_key[table_key]
            sheet = sheets[ordinal - 1]
            if (
                table.source_view != row_source
                or table.columns != columns
                or sheet.sheet_name != sheet_name
                or sheet.table_id != table.table_id
                or sheet.columns != columns
                or sheet.row_source != row_source
            ):
                raise OperatorExportValidationError("V0.1 export layout mismatch")
        if set(self.workbook.sheet_ids) != set(sheet_by_id):
            raise OperatorExportValidationError("workbook sheet inventory mismatch")
        if tuple(self.workbook.sheet_ids) != tuple(item.sheet_id for item in sheets):
            raise OperatorExportValidationError("workbook sheet order mismatch")
        rows_by_id = {item.export_row_id: item for item in self.rows}
        if len(rows_by_id) != len(self.rows):
            raise OperatorExportValidationError("export row IDs collide")
        for row in self.rows:
            table = table_by_id.get(row.table_id)
            sheet = sheet_by_id.get(row.sheet_id)
            if table is None or sheet is None or sheet.table_id != table.table_id:
                raise OperatorExportValidationError("export row table or sheet is absent")
            if set(row.values) != set(table.columns) or tuple(row.values) != table.columns:
                raise OperatorExportValidationError("export row columns mismatch")
            if sheet.columns != table.columns or sheet.row_source != table.source_view:
                raise OperatorExportValidationError("sheet and table definitions mismatch")
        lineage_by_id = {item.export_lineage_id: item for item in self.lineage_index}
        referenced: set[str] = set()
        source_output_lineage_ids: set[str] = set()
        for row in self.rows:
            for lineage_id in row.lineage_reference_ids:
                lineage = lineage_by_id.get(lineage_id)
                if (
                    lineage is None
                    or lineage.export_row_id != row.export_row_id
                    or lineage.table_id != row.table_id
                    or lineage.sheet_id != row.sheet_id
                    or lineage.source_output_row_id != row.source_output_row_id
                    or lineage.source_output_snapshot_id != self.source_output_snapshot_id
                ):
                    raise OperatorExportValidationError("export row lineage chain is broken")
                if not set(lineage.source_bundle_fingerprints) <= set(
                    self.source_bundle_fingerprints
                ):
                    raise OperatorExportValidationError("export lineage fingerprint mismatch")
                if lineage.source_output_lineage_id in source_output_lineage_ids:
                    raise OperatorExportValidationError("source output lineage exported twice")
                source_output_lineage_ids.add(lineage.source_output_lineage_id)
                referenced.add(lineage_id)
        if referenced != set(lineage_by_id):
            raise OperatorExportValidationError("export lineage inventory mismatch")
        for sheet in sheets:
            expected = {
                lineage_id
                for row in self.rows
                if row.sheet_id == sheet.sheet_id
                for lineage_id in row.lineage_reference_ids
            }
            if set(sheet.lineage_reference_ids) != expected:
                raise OperatorExportValidationError("sheet lineage inventory mismatch")
        expected_metadata = {
            "encoding": "UTF-8",
            "format": "SHEET_ORIENTED_EXPORT_MODEL",
            "ruleset_version": OPERATOR_EXPORT_RULESET_VERSION,
            "source_output_snapshot_id": self.source_output_snapshot_id,
            "table_count": len(self.table_definitions),
            "sheet_count": len(sheets),
            "row_count": len(self.rows),
        }
        if dict(self.workbook.metadata) != expected_metadata:
            raise OperatorExportValidationError("workbook metadata mismatch")
        expected_coverage = coverage_from_export(
            tables=self.table_definitions,
            sheets=sheets,
            rows=self.rows,
            lineage=self.lineage_index,
            diagnostics=self.diagnostics,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise OperatorExportValidationError("operator export coverage mismatch")
        expected_id = deterministic_id(
            "operator-export-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise OperatorExportSerializationError(
                "snapshot_id does not match operator export content"
            )

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        values = _tuple(bundles, "bundles")
        if not values or any(not isinstance(item, CanonicalEvidenceBundle) for item in values):
            raise OperatorExportValidationError("bundles must contain canonical bundles")
        for bundle in values:
            bundle.validate()
        fingerprints = {bundle_fingerprint(item) for item in values}
        if fingerprints != set(self.source_bundle_fingerprints):
            raise OperatorExportValidationError("validation bundle fingerprints mismatch")
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        emissions: dict[tuple[str, str], tuple[Any, set[str], str]] = {}
        for bundle in values:
            fingerprint = bundle_fingerprint(bundle)
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                prior = runs.get(run.transformation_run_id)
                if prior is not None and canonical_json(prior) != canonical_json(run):
                    raise OperatorExportValidationError("transformation run identity collision")
                runs[run.transformation_run_id] = run
            records = tuple((item, "OBSERVATION") for item in bundle.observations) + tuple(
                (item, "QUERY_EXECUTION") for item in bundle.query_execution_records
            )
            for record, reference_type in records:
                reference_id = (
                    record.observation_id if reference_type == "OBSERVATION"
                    else record.query_execution_id
                )
                run_id = record.provenance.transformation.transformation_run_id
                key = (reference_id, run_id)
                prior = emissions.get(key)
                if prior is not None and canonical_json(prior[0]) != canonical_json(record):
                    raise OperatorExportValidationError("canonical emission identity collision")
                if prior is None:
                    emissions[key] = (record, {fingerprint}, reference_type)
                else:
                    prior[1].add(fingerprint)
        for lineage in self.lineage_index:
            key = (lineage.canonical_reference_id, lineage.transformation_run_id)
            emission = emissions.get(key)
            if emission is None or emission[2] != lineage.canonical_reference_type:
                raise OperatorExportValidationError("export canonical reference is absent")
            record, emission_fingerprints, reference_type = emission
            provenance = record.provenance
            transformation = provenance.transformation
            run = runs.get(lineage.transformation_run_id)
            expected_ids = (
                run.output_observation_ids if reference_type == "OBSERVATION"
                else run.output_query_execution_ids
            ) if run is not None else ()
            if (
                run is None
                or lineage.canonical_reference_id not in expected_ids
                or lineage.raw_evidence_id not in raw_ids
                or lineage.raw_evidence_id not in run.input_raw_evidence_references
                or transformation.raw_evidence_reference != lineage.raw_evidence_id
                or transformation.mapping_version != lineage.mapping_version
                or transformation.collection_run_id != lineage.collection_run_id
                or provenance.provider != lineage.provider
                or provenance.source_tool != lineage.source_tool
                or provenance.source_field != lineage.source_field
                or getattr(record, "semantic_observation_id", None)
                != lineage.semantic_observation_id
                or not set(lineage.source_bundle_fingerprints) <= emission_fingerprints
            ):
                raise OperatorExportValidationError(
                    "export lineage does not replay against canonical bundles"
                )
        return self

    def to_json(self) -> str:
        return canonical_json(self)

    def to_csv(self, table_key: str) -> str:
        table = next(
            (item for item in self.table_definitions if item.table_key == table_key),
            None,
        )
        if table is None:
            raise OperatorExportValidationError(f"unknown export table {table_key!r}")
        buffer = io.StringIO(newline="")
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(table.columns)
        for row in sorted(
            (item for item in self.rows if item.table_id == table.table_id),
            key=lambda item: item.source_output_row_id,
        ):
            writer.writerow(
                "" if row.values[column] is None else row.values[column]
                for column in table.columns
            )
        return buffer.getvalue()

    def to_csv_bytes(self, table_key: str) -> bytes:
        return self.to_csv(table_key).encode("utf-8")

    def to_csv_files(self) -> dict[str, bytes]:
        table_by_id = {item.table_id: item for item in self.table_definitions}
        return {
            f"{sheet.sheet_name}.csv": self.to_csv_bytes(
                table_by_id[sheet.table_id].table_key
            )
            for sheet in self.sheet_definitions
        }

    def to_workbook_dict(self) -> dict[str, Any]:
        table_by_id = {item.table_id: item for item in self.table_definitions}
        return {
            "filename": self.workbook.filename,
            "metadata": dict(self.workbook.metadata),
            "sheets": [
                {
                    "sheet_name": sheet.sheet_name,
                    "columns": list(sheet.columns),
                    "row_source": sheet.row_source,
                    "rows": [
                        dict(row.values)
                        for row in sorted(
                            (item for item in self.rows if item.sheet_id == sheet.sheet_id),
                            key=lambda item: item.source_output_row_id,
                        )
                    ],
                    "lineage_reference_ids": list(sheet.lineage_reference_ids),
                    "table_key": table_by_id[sheet.table_id].table_key,
                }
                for sheet in self.sheet_definitions
            ],
        }


def coverage_from_export(
    *,
    tables: Sequence[ExportTableDefinition],
    sheets: Sequence[ExportSheetDefinition],
    rows: Sequence[ExportRowRecord],
    lineage: Sequence[ExportLineageReference],
    diagnostics: Sequence[ExportDiagnostic],
) -> ExportCoverageSummary:
    table_key_by_id = {item.table_id: item.table_key for item in tables}
    counts = Counter(table_key_by_id[item.table_id] for item in rows)
    return ExportCoverageSummary(
        table_count=len(tables),
        sheet_count=len(sheets),
        row_count=len(rows),
        lineage_reference_count=len(lineage),
        diagnostic_count=len(diagnostics),
        row_counts_by_table={
            item.table_key: counts.get(item.table_key, 0)
            for item in sorted(tables, key=lambda value: value.table_key)
        },
    )


__all__ = (
    "OPERATOR_EXPORT_RULESET_VERSION",
    "OperatorExportRequest",
    "OperatorExportSnapshotV0_1",
    "ExportTableDefinition",
    "ExportSheetDefinition",
    "ExportRowRecord",
    "ExportWorkbookRecord",
    "ExportCoverageSummary",
    "ExportLineageReference",
    "ExportDiagnostic",
)
