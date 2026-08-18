"""Strict immutable contracts for Operator Workbook Product V0.2."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass, fields
from hashlib import sha256
import json
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any, Mapping, Self
from zipfile import BadZipFile, ZipFile

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    ContractValidationError,
    JsonContract,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.evidence_evaluation import (
    EvidenceEvaluationSnapshotV0_1,
)
from amazon_product_intelligence.operator_export import OperatorExportSnapshotV0_1
from amazon_product_intelligence.operator_output import (
    OperatorOutputRequest,
    OperatorOutputSnapshotV0_1,
)

from .errors import (
    OperatorWorkbookSerializationError,
    OperatorWorkbookValidationError,
)
from .schema_v0_2 import EXPECTED_FIELD_COUNT, EXPECTED_SHEET_NAMES


OPERATOR_WORKBOOK_RULESET_VERSION = "operator-workbook-v0.2"
WORKBOOK_FILENAME = "amazon_product_analysis_v0.2.xlsx"
WORKBOOK_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SOURCE_KEYS = (
    "competition_intelligence",
    "demand_intelligence",
    "evidence_evaluation",
    "operator_export",
    "operator_output",
    "opportunity_intelligence",
    "opportunity_scoring",
    "product_intelligence",
    "recommendation_framework",
)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OperatorWorkbookValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _count(value: Any, path: str, *, positive: bool = False) -> int:
    minimum = 1 if positive else 0
    if type(value) is not int or value < minimum:
        raise OperatorWorkbookValidationError(
            f"{path} must be an integer >= {minimum}"
        )
    return value


def _unique_texts(
    value: Any, path: str, *, allow_empty: bool = True, ordered: bool = True
) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OperatorWorkbookValidationError(f"{path} must be an array")
    result = tuple(value)
    if not allow_empty and not result:
        raise OperatorWorkbookValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in result):
        raise OperatorWorkbookValidationError(
            f"{path} must contain non-empty text"
        )
    if len(result) != len(set(result)):
        raise OperatorWorkbookValidationError(f"{path} must be unique")
    return result if ordered else tuple(sorted(result))


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise OperatorWorkbookValidationError(
            f"{path} must contain finite JSON data"
        ) from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _mapping(value: Any, path: str, *, allow_empty: bool = True) -> Mapping[str, Any]:
    frozen = _freeze_json(value, path)
    if not isinstance(frozen, MappingABC) or (not allow_empty and not frozen):
        raise OperatorWorkbookValidationError(f"{path} must be an object")
    return frozen


def _ordered_export_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    """Restore the field order required by the strict Operator Export contract."""
    payload = json.loads(canonical_json(value))
    columns_by_table = {
        item["table_id"]: tuple(item["columns"])
        for item in payload["table_definitions"]
    }
    for row in payload["rows"]:
        columns = columns_by_table[row["table_id"]]
        row["values"] = {column: row["values"][column] for column in columns}
    return payload


def _bundle_fingerprint(bundle: CanonicalEvidenceBundle) -> str:
    payload = bundle.to_dict()
    for key, value in tuple(payload.items()):
        if isinstance(value, list):
            payload[key] = sorted(value, key=canonical_json)
    return sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _without_id(value: JsonContract, field_name: str) -> dict[str, Any]:
    payload = value.to_dict()
    payload.pop(field_name)
    return payload


class _WorkbookModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OperatorWorkbookSerializationError:
            raise
        except (
            ContractValidationError,
            OperatorWorkbookValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise OperatorWorkbookSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookFieldDefinition(_WorkbookModel):
    field_id: str
    sheet_key: str
    ordinal: int
    chinese_name: str
    english_name: str
    data_type: str
    source: str
    visible: bool
    default_hidden: bool
    operator_use: str
    column_width: float

    def __post_init__(self) -> None:
        for name in (
            "field_id", "sheet_key", "chinese_name", "english_name",
            "data_type", "source", "operator_use",
        ):
            _text(getattr(self, name), f"WorkbookFieldDefinition.{name}")
        _count(self.ordinal, "WorkbookFieldDefinition.ordinal", positive=True)
        if type(self.visible) is not bool or type(self.default_hidden) is not bool:
            raise OperatorWorkbookValidationError("field visibility must be boolean")
        if type(self.column_width) not in {int, float} or not 8 <= float(self.column_width) <= 60:
            raise OperatorWorkbookValidationError("field column_width must be 8..60")
        if self.visible == self.default_hidden:
            raise OperatorWorkbookValidationError(
                "field visible must be the inverse of default_hidden"
            )
        if self.field_id != deterministic_id(
            "operator-workbook-field", _without_id(self, "field_id")
        ):
            raise OperatorWorkbookValidationError("field identity mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookSheetDefinition(_WorkbookModel):
    sheet_id: str
    ordinal: int
    sheet_key: str
    sheet_name: str
    purpose: str
    warning: str
    row_grain: str
    hidden: bool
    field_ids: tuple[str, ...]
    row_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "sheet_id", "sheet_key", "sheet_name", "purpose", "warning", "row_grain"
        ):
            _text(getattr(self, name), f"WorkbookSheetDefinition.{name}")
        _count(self.ordinal, "WorkbookSheetDefinition.ordinal", positive=True)
        if type(self.hidden) is not bool:
            raise OperatorWorkbookValidationError("sheet hidden must be boolean")
        object.__setattr__(
            self, "field_ids", _unique_texts(self.field_ids, "sheet.field_ids", allow_empty=False)
        )
        object.__setattr__(
            self, "row_ids", _unique_texts(self.row_ids, "sheet.row_ids")
        )
        identity = _without_id(self, "sheet_id")
        identity.pop("row_ids")
        if self.sheet_id != deterministic_id("operator-workbook-sheet", identity):
            raise OperatorWorkbookValidationError("sheet identity mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookRowRecord(_WorkbookModel):
    row_id: str
    sheet_id: str
    row_key: str
    values: Mapping[str, Any]
    source_output_row_ids: tuple[str, ...]
    source_snapshot_ids: tuple[str, ...]
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("row_id", "sheet_id", "row_key"):
            _text(getattr(self, name), f"WorkbookRowRecord.{name}")
        object.__setattr__(self, "values", _mapping(self.values, "row.values", allow_empty=False))
        for name, allow_empty in (
            ("source_output_row_ids", False),
            ("source_snapshot_ids", False),
            ("lineage_reference_ids", False),
        ):
            object.__setattr__(
                self, name, _unique_texts(getattr(self, name), f"row.{name}", allow_empty=allow_empty)
            )
        identity = _without_id(self, "row_id")
        identity.pop("lineage_reference_ids")
        if self.row_id != deterministic_id("operator-workbook-row", identity):
            raise OperatorWorkbookValidationError("row identity mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookLineageReference(_WorkbookModel):
    workbook_lineage_id: str
    row_id: str
    sheet_id: str
    source_export_snapshot_id: str
    source_export_row_id: str
    source_export_lineage_id: str
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
        for field in fields(self):
            if field.name in {"semantic_observation_id", "source_bundle_fingerprints"}:
                continue
            _text(getattr(self, field.name), f"WorkbookLineageReference.{field.name}")
        _optional_text(self.semantic_observation_id, "lineage.semantic_observation_id")
        object.__setattr__(
            self,
            "source_bundle_fingerprints",
            _unique_texts(
                self.source_bundle_fingerprints,
                "lineage.source_bundle_fingerprints",
                allow_empty=False,
                ordered=False,
            ),
        )
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise OperatorWorkbookValidationError("lineage fingerprints must be SHA-256")
        if self.canonical_reference_type not in {"OBSERVATION", "QUERY_EXECUTION"}:
            raise OperatorWorkbookValidationError("unsupported canonical reference type")
        if self.workbook_lineage_id != deterministic_id(
            "operator-workbook-lineage", _without_id(self, "workbook_lineage_id")
        ):
            raise OperatorWorkbookValidationError("lineage identity mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookFileRecord(_WorkbookModel):
    workbook_id: str
    filename: str
    media_type: str
    content_base64: str
    content_sha256: str
    size_bytes: int
    sheet_ids: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        for name in (
            "workbook_id", "filename", "media_type", "content_base64", "content_sha256"
        ):
            _text(getattr(self, name), f"WorkbookFileRecord.{name}")
        if self.filename != WORKBOOK_FILENAME or self.media_type != WORKBOOK_MEDIA_TYPE:
            raise OperatorWorkbookValidationError("workbook filename or media type mismatch")
        if _SHA256.fullmatch(self.content_sha256) is None:
            raise OperatorWorkbookValidationError("workbook SHA-256 is invalid")
        _count(self.size_bytes, "workbook.size_bytes", positive=True)
        object.__setattr__(self, "sheet_ids", _unique_texts(self.sheet_ids, "workbook.sheet_ids", allow_empty=False))
        object.__setattr__(self, "metadata", _mapping(self.metadata, "workbook.metadata", allow_empty=False))
        try:
            content = base64.b64decode(self.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise OperatorWorkbookValidationError("workbook content is not valid base64") from exc
        if len(content) != self.size_bytes or sha256(content).hexdigest() != self.content_sha256:
            raise OperatorWorkbookValidationError("workbook content size or hash mismatch")
        try:
            with ZipFile(__import__("io").BytesIO(content), "r") as archive:
                if "[Content_Types].xml" not in archive.namelist():
                    raise OperatorWorkbookValidationError("workbook ZIP is not an XLSX package")
        except BadZipFile as exc:
            raise OperatorWorkbookValidationError("workbook content is not a ZIP package") from exc
        if self.workbook_id != deterministic_id(
            "operator-workbook-file", _without_id(self, "workbook_id")
        ):
            raise OperatorWorkbookValidationError("workbook identity mismatch")

    def to_bytes(self) -> bytes:
        return base64.b64decode(self.content_base64, validate=True)


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookCoverageSummary(_WorkbookModel):
    sheet_count: int
    field_count: int
    display_row_count: int
    audit_row_count: int
    lineage_reference_count: int
    diagnostic_count: int
    row_counts_by_sheet: Mapping[str, int]

    def __post_init__(self) -> None:
        for name in (
            "sheet_count", "field_count", "display_row_count", "audit_row_count",
            "lineage_reference_count", "diagnostic_count",
        ):
            _count(getattr(self, name), f"WorkbookCoverageSummary.{name}")
        counts = _mapping(self.row_counts_by_sheet, "coverage.row_counts_by_sheet", allow_empty=False)
        if any(type(value) is not int or value < 0 for value in counts.values()):
            raise OperatorWorkbookValidationError("coverage row counts must be non-negative integers")
        object.__setattr__(self, "row_counts_by_sheet", counts)


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookDiagnostic(_WorkbookModel):
    diagnostic_id: str
    code: str
    severity: str
    message: str
    source_snapshot_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("diagnostic_id", "code", "severity", "message"):
            _text(getattr(self, name), f"WorkbookDiagnostic.{name}")
        if self.severity not in {"INFO", "WARNING", "MATERIAL", "BLOCKING"}:
            raise OperatorWorkbookValidationError("invalid diagnostic severity")
        object.__setattr__(
            self, "source_snapshot_ids", _unique_texts(self.source_snapshot_ids, "diagnostic.source_snapshot_ids", allow_empty=False)
        )
        if self.diagnostic_id != deterministic_id(
            "operator-workbook-diagnostic", _without_id(self, "diagnostic_id")
        ):
            raise OperatorWorkbookValidationError("diagnostic identity mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorWorkbookRequest(_WorkbookModel):
    canonical_bundles: tuple[CanonicalEvidenceBundle, ...]
    product_intelligence_snapshot: Mapping[str, Any]
    demand_intelligence_snapshot: Mapping[str, Any]
    competition_intelligence_snapshot: Mapping[str, Any]
    opportunity_intelligence_snapshot: Mapping[str, Any]
    evidence_evaluation_snapshot: Mapping[str, Any]
    opportunity_scoring_snapshot: Mapping[str, Any]
    recommendation_framework_snapshot: Mapping[str, Any]
    operator_export_snapshot: Mapping[str, Any]
    operator_output_snapshot: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not self.canonical_bundles or any(
            not isinstance(item, CanonicalEvidenceBundle) for item in self.canonical_bundles
        ):
            raise OperatorWorkbookValidationError("canonical_bundles must contain canonical bundles")
        for bundle in self.canonical_bundles:
            bundle.validate()
        ordered = tuple(sorted(self.canonical_bundles, key=_bundle_fingerprint))
        fingerprints = tuple(_bundle_fingerprint(item) for item in ordered)
        if len(fingerprints) != len(set(fingerprints)):
            raise OperatorWorkbookValidationError("canonical bundle content is duplicated")
        object.__setattr__(self, "canonical_bundles", ordered)
        snapshot_names = tuple(
            key for key in _SOURCE_KEYS
            if key not in {"operator_export", "operator_output"}
        )
        for name in snapshot_names:
            object.__setattr__(self, f"{name}_snapshot", _mapping(
                getattr(self, f"{name}_snapshot"), f"request.{name}_snapshot", allow_empty=False
            ))
        object.__setattr__(self, "operator_output_snapshot", _mapping(
            self.operator_output_snapshot, "request.operator_output_snapshot", allow_empty=False
        ))
        object.__setattr__(self, "operator_export_snapshot", _mapping(
            self.operator_export_snapshot, "request.operator_export_snapshot", allow_empty=False
        ))
        try:
            evaluation_fingerprints = set(
                self.evidence_evaluation_snapshot["source_bundle_fingerprints"]
            )
            evaluation_bundles = tuple(
                item for item in ordered
                if _bundle_fingerprint(item) in evaluation_fingerprints
            )
            evaluation = EvidenceEvaluationSnapshotV0_1.from_dict(
                self.evidence_evaluation_snapshot
            ).validate_against_bundles(evaluation_bundles)
            source_request = OperatorOutputRequest(
                canonical_bundles=ordered,
                product_intelligence_snapshot=self.product_intelligence_snapshot,
                demand_intelligence_snapshot=self.demand_intelligence_snapshot,
                competition_intelligence_snapshot=self.competition_intelligence_snapshot,
                opportunity_intelligence_snapshot=self.opportunity_intelligence_snapshot,
                opportunity_scoring_snapshot=self.opportunity_scoring_snapshot,
                recommendation_framework_snapshot=self.recommendation_framework_snapshot,
            )
            output = OperatorOutputSnapshotV0_1.from_dict(
                self.operator_output_snapshot
            ).validate_against_bundles(ordered)
            export = OperatorExportSnapshotV0_1.from_dict(
                _ordered_export_payload(self.operator_export_snapshot)
            ).validate_against_bundles(ordered)
        except Exception as exc:
            raise OperatorWorkbookValidationError(
                f"upstream source validation failed: {exc}"
            ) from exc
        expected_ids = {
            "product_intelligence": self.product_intelligence_snapshot["snapshot_id"],
            "demand_intelligence": self.demand_intelligence_snapshot["snapshot_id"],
            "competition_intelligence": self.competition_intelligence_snapshot["snapshot_id"],
            "opportunity_intelligence": self.opportunity_intelligence_snapshot["snapshot_id"],
            "opportunity_scoring": self.opportunity_scoring_snapshot["snapshot_id"],
            "recommendation_framework": self.recommendation_framework_snapshot["snapshot_id"],
        }
        if dict(output.source_snapshot_ids) != expected_ids:
            raise OperatorWorkbookValidationError("operator output source snapshot IDs mismatch")
        if export.source_output_snapshot_id != output.snapshot_id:
            raise OperatorWorkbookValidationError("operator export source output mismatch")
        output_lineage = {
            item.output_lineage_id: item.to_dict() for item in output.lineage_index
        }
        exported_output_lineage_ids: set[str] = set()
        for export_lineage in export.lineage_index:
            source = output_lineage.get(export_lineage.source_output_lineage_id)
            if source is None:
                raise OperatorWorkbookValidationError(
                    "operator export references missing output lineage"
                )
            comparable_fields = (
                "source_snapshot_id", "source_record_id", "source_lineage_id",
                "canonical_reference_id", "canonical_reference_type",
                "semantic_observation_id", "transformation_run_id", "mapping_version",
                "raw_evidence_id", "collection_run_id", "provider", "source_tool",
                "source_field", "source_bundle_fingerprints",
            )
            if (
                export_lineage.source_output_row_id != source["output_row_id"]
                or any(
                    getattr(export_lineage, name)
                    != (
                        tuple(source[name])
                        if name == "source_bundle_fingerprints"
                        else source[name]
                    )
                    for name in comparable_fields
                )
            ):
                raise OperatorWorkbookValidationError(
                    "operator export lineage does not match operator output"
                )
            exported_output_lineage_ids.add(export_lineage.source_output_lineage_id)
        if exported_output_lineage_ids != set(output_lineage):
            raise OperatorWorkbookValidationError(
                "operator export output-lineage inventory mismatch"
            )
        if self.opportunity_scoring_snapshot["source_evaluation_snapshot_id"] != evaluation.snapshot_id:
            raise OperatorWorkbookValidationError("scoring evaluation source mismatch")
        if self.recommendation_framework_snapshot["source_evaluation_snapshot_id"] != evaluation.snapshot_id:
            raise OperatorWorkbookValidationError("recommendation evaluation source mismatch")
        del source_request


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorWorkbookSnapshotV0_2(_WorkbookModel):
    snapshot_id: str
    ruleset_version: str
    source_bundle_fingerprints: tuple[str, ...]
    source_snapshot_ids: Mapping[str, str]
    fields: tuple[WorkbookFieldDefinition, ...]
    sheets: tuple[WorkbookSheetDefinition, ...]
    rows: tuple[WorkbookRowRecord, ...]
    workbook: WorkbookFileRecord
    coverage: WorkbookCoverageSummary
    diagnostics: tuple[WorkbookDiagnostic, ...]
    lineage_index: tuple[WorkbookLineageReference, ...]

    def __post_init__(self) -> None:
        _text(self.snapshot_id, "OperatorWorkbookSnapshotV0_2.snapshot_id")
        if self.ruleset_version != OPERATOR_WORKBOOK_RULESET_VERSION:
            raise OperatorWorkbookValidationError("unsupported workbook ruleset")
        object.__setattr__(self, "source_bundle_fingerprints", _unique_texts(
            self.source_bundle_fingerprints, "workbook.source_bundle_fingerprints", allow_empty=False, ordered=False
        ))
        if any(_SHA256.fullmatch(item) is None for item in self.source_bundle_fingerprints):
            raise OperatorWorkbookValidationError("workbook fingerprints must be SHA-256")
        source_ids = _mapping(self.source_snapshot_ids, "workbook.source_snapshot_ids", allow_empty=False)
        if set(source_ids) != set(_SOURCE_KEYS):
            raise OperatorWorkbookValidationError("workbook source snapshot keys mismatch")
        object.__setattr__(self, "source_snapshot_ids", source_ids)
        typed = (
            ("fields", WorkbookFieldDefinition, "field_id"),
            ("sheets", WorkbookSheetDefinition, "sheet_id"),
            ("rows", WorkbookRowRecord, "row_id"),
            ("diagnostics", WorkbookDiagnostic, "diagnostic_id"),
            ("lineage_index", WorkbookLineageReference, "workbook_lineage_id"),
        )
        for name, expected_type, id_name in typed:
            value = tuple(getattr(self, name))
            if any(not isinstance(item, expected_type) for item in value):
                raise OperatorWorkbookValidationError(f"{name} contains wrong type")
            ids = tuple(getattr(item, id_name) for item in value)
            if len(ids) != len(set(ids)):
                raise OperatorWorkbookValidationError(f"{name} contains duplicate identities")
            object.__setattr__(self, name, value)
        if len(self.fields) != EXPECTED_FIELD_COUNT:
            raise OperatorWorkbookValidationError("workbook must define exactly 157 fields")
        if tuple(sheet.sheet_name for sheet in self.sheets) != EXPECTED_SHEET_NAMES:
            raise OperatorWorkbookValidationError("workbook sheet order mismatch")
        if tuple(sheet.ordinal for sheet in self.sheets) != tuple(range(1, 10)):
            raise OperatorWorkbookValidationError("workbook sheet ordinals mismatch")
        if not self.sheets[-1].hidden or any(item.hidden for item in self.sheets[:-1]):
            raise OperatorWorkbookValidationError("only data audit sheet may be hidden")
        field_by_id = {item.field_id: item for item in self.fields}
        row_by_id = {item.row_id: item for item in self.rows}
        lineage_by_id = {item.workbook_lineage_id: item for item in self.lineage_index}
        referenced_rows: set[str] = set()
        referenced_lineage: set[str] = set()
        for sheet in self.sheets:
            if any(field_id not in field_by_id for field_id in sheet.field_ids):
                raise OperatorWorkbookValidationError("sheet references missing field")
            if any(field_by_id[field_id].sheet_key != sheet.sheet_key for field_id in sheet.field_ids):
                raise OperatorWorkbookValidationError("sheet references another sheet's field")
            for row_id in sheet.row_ids:
                row = row_by_id.get(row_id)
                if row is None or row.sheet_id != sheet.sheet_id:
                    raise OperatorWorkbookValidationError("sheet row reference is broken")
                if set(row.values) != set(sheet.field_ids):
                    raise OperatorWorkbookValidationError("row values do not match sheet fields")
                for lineage_id in row.lineage_reference_ids:
                    lineage = lineage_by_id.get(lineage_id)
                    if lineage is None or lineage.row_id != row.row_id or lineage.sheet_id != sheet.sheet_id:
                        raise OperatorWorkbookValidationError("row lineage reference is broken")
                    if lineage.source_output_row_id not in row.source_output_row_ids:
                        raise OperatorWorkbookValidationError("row lineage output reference mismatch")
                    if (
                        lineage.source_output_snapshot_id
                        != source_ids["operator_output"]
                        or lineage.source_export_snapshot_id
                        != source_ids["operator_export"]
                    ):
                        raise OperatorWorkbookValidationError(
                            "row lineage source snapshot reference mismatch"
                        )
                    referenced_lineage.add(lineage_id)
                referenced_rows.add(row_id)
        if referenced_rows != set(row_by_id):
            raise OperatorWorkbookValidationError("workbook rows must be referenced exactly once")
        display_rows = tuple(row for row in self.rows if row.sheet_id != self.sheets[-1].sheet_id)
        if referenced_lineage != set(lineage_by_id):
            raise OperatorWorkbookValidationError("workbook lineage must be referenced exactly once")
        if any(not row.lineage_reference_ids for row in display_rows):
            raise OperatorWorkbookValidationError("each display row requires canonical lineage")
        if self.workbook.sheet_ids != tuple(item.sheet_id for item in self.sheets):
            raise OperatorWorkbookValidationError("workbook file sheet IDs mismatch")
        expected_counts = {sheet.sheet_name: len(sheet.row_ids) for sheet in self.sheets}
        expected_coverage = WorkbookCoverageSummary(
            sheet_count=len(self.sheets),
            field_count=len(self.fields),
            display_row_count=len(display_rows),
            audit_row_count=len(self.sheets[-1].row_ids),
            lineage_reference_count=len(self.lineage_index),
            diagnostic_count=len(self.diagnostics),
            row_counts_by_sheet=expected_counts,
        )
        if canonical_json(expected_coverage) != canonical_json(self.coverage):
            raise OperatorWorkbookValidationError("workbook coverage mismatch")
        expected_id = deterministic_id(
            "operator-workbook-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_id:
            raise OperatorWorkbookSerializationError("snapshot identity mismatch")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def validate_against_bundles(
        self, bundles: Sequence[CanonicalEvidenceBundle]
    ) -> Self:
        if isinstance(bundles, (str, bytes)) or not isinstance(bundles, Sequence) or not bundles:
            raise OperatorWorkbookValidationError("bundles must be a non-empty sequence")
        fingerprints = {_bundle_fingerprint(item) for item in bundles}
        if fingerprints != set(self.source_bundle_fingerprints):
            raise OperatorWorkbookValidationError("validation bundle fingerprints mismatch")
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        emissions: dict[tuple[str, str], tuple[str, set[str]]] = {}
        for bundle in bundles:
            if not isinstance(bundle, CanonicalEvidenceBundle):
                raise OperatorWorkbookValidationError("validation input contains wrong type")
            bundle.validate()
            fingerprint = _bundle_fingerprint(bundle)
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                runs[run.transformation_run_id] = run
            for record, kind in tuple((item, "OBSERVATION") for item in bundle.observations) + tuple(
                (item, "QUERY_EXECUTION") for item in bundle.query_execution_records
            ):
                reference_id = getattr(record, "observation_id", None) or record.query_execution_id
                run_id = record.provenance.transformation.transformation_run_id
                key = (reference_id, run_id)
                if key not in emissions:
                    emissions[key] = (kind, {fingerprint})
                else:
                    emissions[key][1].add(fingerprint)
        for lineage in self.lineage_index:
            emission = emissions.get((lineage.canonical_reference_id, lineage.transformation_run_id))
            if emission is None or emission[0] != lineage.canonical_reference_type:
                raise OperatorWorkbookValidationError("canonical lineage reference is absent")
            run = runs.get(lineage.transformation_run_id)
            if run is None or run.mapping_version != lineage.mapping_version:
                raise OperatorWorkbookValidationError("lineage transformation is absent or changed")
            if lineage.raw_evidence_id not in raw_ids:
                raise OperatorWorkbookValidationError("lineage raw evidence reference is absent")
            if not set(lineage.source_bundle_fingerprints) <= emission[1]:
                raise OperatorWorkbookValidationError("lineage fingerprint does not own emission")
        return self

    def to_json(self) -> str:
        return canonical_json(self)

    def to_xlsx_bytes(self) -> bytes:
        return self.workbook.to_bytes()

    def write_xlsx(self, destination: str | Path) -> Path:
        target = Path(destination)
        if target.name != WORKBOOK_FILENAME:
            raise OperatorWorkbookValidationError(
                f"destination filename must be {WORKBOOK_FILENAME}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise OperatorWorkbookValidationError("destination already exists")
        target.write_bytes(self.to_xlsx_bytes())
        return target


__all__ = (
    "OPERATOR_WORKBOOK_RULESET_VERSION",
    "WORKBOOK_FILENAME",
    "OperatorWorkbookRequest",
    "OperatorWorkbookSnapshotV0_2",
    "WorkbookCoverageSummary",
    "WorkbookDiagnostic",
    "WorkbookFieldDefinition",
    "WorkbookFileRecord",
    "WorkbookLineageReference",
    "WorkbookRowRecord",
    "WorkbookSheetDefinition",
)
