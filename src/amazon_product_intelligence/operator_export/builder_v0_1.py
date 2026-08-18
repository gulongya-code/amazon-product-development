"""Deterministic Operator Export Foundation V0.1 builder."""

from __future__ import annotations

from typing import Any, Mapping

from amazon_product_intelligence.contracts import canonical_json, deterministic_id

from .errors import OperatorExportValidationError
from .models import (
    OPERATOR_EXPORT_RULESET_VERSION,
    ExportDiagnostic,
    ExportLineageReference,
    ExportRowRecord,
    ExportSheetDefinition,
    ExportTableDefinition,
    ExportWorkbookRecord,
    OperatorExportRequest,
    OperatorExportSnapshotV0_1,
    _EXPORT_LAYOUT,
    coverage_from_export,
)


_WORKBOOK_FILENAME = "amazon_product_analysis.xlsx"


def _scalar(value: Any) -> str | bool | int | float | None:
    if value is None or type(value) in {str, bool, int, float}:
        return value
    return canonical_json(value)


def _values(table_key: str, row: Mapping[str, Any]) -> dict[str, Any]:
    if table_key == "product":
        values = {
            "ASIN": row["asin"],
            "Marketplace": row["marketplace"],
            "Title": row["title"],
            "Product Facts": row["product_facts"],
            "Metrics": row["metrics"],
            "Variation": row["variation_information"],
            "Reviews": row["review_summary"],
            "Quality Indicators": row["data_quality_indicators"],
            "Source Reference": {
                "output_row_id": row["output_row_id"],
                "source_snapshot_id": row["source_snapshot_id"],
                "lineage_reference_ids": row["lineage_reference_ids"],
            },
        }
    elif table_key == "keyword":
        values = {
            "Keyword": row["keyword"],
            "Metrics": row["keyword_metrics"],
            "Query Status": row["query_status"],
            "Related Products": row["related_products"],
            "Channels": row["channels"],
            "Providers": row["providers"],
            "Limitations": row["limitations"],
        }
    elif table_key == "competition":
        values = {
            "Product Endpoint": row["product_endpoint"],
            "Keyword Relationship": {
                "relationship": row["keyword_relationship"],
                "relationship_type": row["relationship_type"],
            },
            "Channel": row["channel"],
            "Provider": row["provider"],
            "Evidence Count": row["evidence_count"],
            "Variation Evidence": row["variation_evidence"],
            "Limitations": row["limitations"],
        }
    elif table_key == "opportunity":
        values = {
            "Product": row["product"],
            "Signals": row["signals"],
            "Missing Evidence": row["missing_evidence"],
            "Risk Evidence": row["risk_evidence"],
            "Score References": row["score_references"],
            "Explanation References": row["explanation_references"],
        }
    elif table_key == "recommendation":
        values = {
            "Recommendation Type": row["recommendation_type"],
            "Rule Reference": row["rule_reference"],
            "Explanation": row["explanation"],
            "Evidence References": row["evidence_references"],
            "Limitations": row["limitations"],
        }
    else:
        raise OperatorExportValidationError(f"unsupported export table {table_key!r}")
    return {key: _scalar(value) for key, value in values.items()}


def _table_definition(
    table_key: str, row_source: str, columns: tuple[str, ...]
) -> ExportTableDefinition:
    content = {
        "table_key": table_key,
        "columns": columns,
        "source_view": row_source,
    }
    return ExportTableDefinition(
        table_id=deterministic_id("operator-export-table", content),
        **content,
    )


def _sheet_definition(
    *,
    ordinal: int,
    sheet_name: str,
    table: ExportTableDefinition,
    lineage_reference_ids: tuple[str, ...] = (),
) -> ExportSheetDefinition:
    identity = {
        "ordinal": ordinal,
        "sheet_name": sheet_name,
        "table_id": table.table_id,
        "columns": table.columns,
        "row_source": table.source_view,
    }
    return ExportSheetDefinition(
        sheet_id=deterministic_id("operator-export-sheet", identity),
        lineage_reference_ids=lineage_reference_ids,
        **identity,
    )


def _export_lineage(
    *,
    export_row_id: str,
    table_id: str,
    sheet_id: str,
    source_output_snapshot_id: str,
    source_output_lineage: Mapping[str, Any],
) -> ExportLineageReference:
    content = {
        "export_row_id": export_row_id,
        "table_id": table_id,
        "sheet_id": sheet_id,
        "source_output_snapshot_id": source_output_snapshot_id,
        "source_output_row_id": source_output_lineage["output_row_id"],
        "source_output_lineage_id": source_output_lineage["output_lineage_id"],
        "source_snapshot_id": source_output_lineage["source_snapshot_id"],
        "source_record_id": source_output_lineage["source_record_id"],
        "source_lineage_id": source_output_lineage["source_lineage_id"],
        "canonical_reference_id": source_output_lineage["canonical_reference_id"],
        "canonical_reference_type": source_output_lineage[
            "canonical_reference_type"
        ],
        "semantic_observation_id": source_output_lineage[
            "semantic_observation_id"
        ],
        "transformation_run_id": source_output_lineage["transformation_run_id"],
        "mapping_version": source_output_lineage["mapping_version"],
        "raw_evidence_id": source_output_lineage["raw_evidence_id"],
        "collection_run_id": source_output_lineage["collection_run_id"],
        "provider": source_output_lineage["provider"],
        "source_tool": source_output_lineage["source_tool"],
        "source_field": source_output_lineage["source_field"],
        "source_bundle_fingerprints": source_output_lineage[
            "source_bundle_fingerprints"
        ],
    }
    return ExportLineageReference(
        export_lineage_id=deterministic_id("operator-export-lineage", content),
        **content,
    )


class OperatorExportBuilderV0_1:
    """Project a serialized Operator Output snapshot into auditable exports."""

    def build(self, request: OperatorExportRequest) -> OperatorExportSnapshotV0_1:
        if not isinstance(request, OperatorExportRequest):
            raise OperatorExportValidationError(
                "request must be OperatorExportRequest"
            )
        source = request.operator_output_snapshot
        source_snapshot_id = source["snapshot_id"]
        source_lineage_by_id = {
            item["output_lineage_id"]: item for item in source["lineage_index"]
        }

        tables: list[ExportTableDefinition] = []
        provisional_sheets: list[ExportSheetDefinition] = []
        for ordinal, (table_key, row_source, sheet_name, columns) in enumerate(
            _EXPORT_LAYOUT, start=1
        ):
            table = _table_definition(table_key, row_source, columns)
            tables.append(table)
            provisional_sheets.append(
                _sheet_definition(
                    ordinal=ordinal,
                    sheet_name=sheet_name,
                    table=table,
                )
            )

        rows: list[ExportRowRecord] = []
        lineage: list[ExportLineageReference] = []
        for spec, table, sheet in zip(
            _EXPORT_LAYOUT, tables, provisional_sheets, strict=True
        ):
            table_key, row_source, _, _ = spec
            for source_row in sorted(
                source[row_source], key=lambda item: item["output_row_id"]
            ):
                values = _values(table_key, source_row)
                row_identity = {
                    "table_id": table.table_id,
                    "sheet_id": sheet.sheet_id,
                    "source_output_row_id": source_row["output_row_id"],
                    "values": values,
                }
                export_row_id = deterministic_id(
                    "operator-export-row", row_identity
                )
                row_lineage = tuple(
                    sorted(
                        (
                            _export_lineage(
                                export_row_id=export_row_id,
                                table_id=table.table_id,
                                sheet_id=sheet.sheet_id,
                                source_output_snapshot_id=source_snapshot_id,
                                source_output_lineage=source_lineage_by_id[lineage_id],
                            )
                            for lineage_id in source_row["lineage_reference_ids"]
                        ),
                        key=lambda item: item.export_lineage_id,
                    )
                )
                rows.append(
                    ExportRowRecord(
                        export_row_id=export_row_id,
                        lineage_reference_ids=tuple(
                            item.export_lineage_id for item in row_lineage
                        ),
                        **row_identity,
                    )
                )
                lineage.extend(row_lineage)

        rows_tuple = tuple(sorted(rows, key=lambda item: item.export_row_id))
        lineage_tuple = tuple(
            sorted(lineage, key=lambda item: item.export_lineage_id)
        )
        sheets = tuple(
            _sheet_definition(
                ordinal=sheet.ordinal,
                sheet_name=sheet.sheet_name,
                table=table,
                lineage_reference_ids=tuple(
                    item.export_lineage_id
                    for item in lineage_tuple
                    if item.sheet_id == sheet.sheet_id
                ),
            )
            for table, sheet in zip(tables, provisional_sheets, strict=True)
        )
        tables_tuple = tuple(sorted(tables, key=lambda item: item.table_key))
        metadata = {
            "encoding": "UTF-8",
            "format": "SHEET_ORIENTED_EXPORT_MODEL",
            "ruleset_version": OPERATOR_EXPORT_RULESET_VERSION,
            "source_output_snapshot_id": source_snapshot_id,
            "table_count": len(tables_tuple),
            "sheet_count": len(sheets),
            "row_count": len(rows_tuple),
        }
        workbook_content = {
            "filename": _WORKBOOK_FILENAME,
            "sheet_ids": tuple(item.sheet_id for item in sheets),
            "metadata": metadata,
        }
        workbook = ExportWorkbookRecord(
            workbook_id=deterministic_id(
                "operator-export-workbook", workbook_content
            ),
            **workbook_content,
        )
        diagnostic_content = {
            "code": "EXPORT_LAYER_PRESENTATION_ONLY",
            "severity": "INFO",
            "message": (
                "Tables serialize existing Operator Output rows; this layer performs "
                "no analysis, scoring, selection, or recommendation generation."
            ),
            "source_output_snapshot_id": source_snapshot_id,
        }
        diagnostics = (
            ExportDiagnostic(
                diagnostic_id=deterministic_id(
                    "operator-export-diagnostic", diagnostic_content
                ),
                **diagnostic_content,
            ),
        )
        coverage = coverage_from_export(
            tables=tables_tuple,
            sheets=sheets,
            rows=rows_tuple,
            lineage=lineage_tuple,
            diagnostics=diagnostics,
        )
        content = {
            "ruleset_version": OPERATOR_EXPORT_RULESET_VERSION,
            "source_output_snapshot_id": source_snapshot_id,
            "source_bundle_fingerprints": tuple(
                source["source_bundle_fingerprints"]
            ),
            "table_definitions": tables_tuple,
            "sheet_definitions": sheets,
            "rows": rows_tuple,
            "workbook": workbook,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": lineage_tuple,
        }
        snapshot = OperatorExportSnapshotV0_1(
            snapshot_id=deterministic_id("operator-export-snapshot", content),
            **content,
        )
        return snapshot.validate_against_bundles(request.canonical_bundles)


__all__ = ("OperatorExportBuilderV0_1",)
