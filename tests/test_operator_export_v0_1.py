from __future__ import annotations

import ast
import csv
from dataclasses import FrozenInstanceError
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
import amazon_product_intelligence.operator_export as operator_export
from amazon_product_intelligence.operator_export import (
    OPERATOR_EXPORT_RULESET_VERSION,
    OperatorExportBuilderV0_1,
    OperatorExportRequest,
    OperatorExportSerializationError,
    OperatorExportSnapshotV0_1,
    OperatorExportValidationError,
)
from tests.test_operator_output_v0_1 import (
    build_fixture as build_operator_output_fixture,
)


EXPECTED_API = {
    "OPERATOR_EXPORT_RULESET_VERSION",
    "OperatorExportRequest",
    "OperatorExportSnapshotV0_1",
    "OperatorExportBuilderV0_1",
    "OperatorExportError",
    "OperatorExportValidationError",
    "OperatorExportSerializationError",
    "ExportTableDefinition",
    "ExportSheetDefinition",
    "ExportRowRecord",
    "ExportWorkbookRecord",
    "ExportCoverageSummary",
    "ExportLineageReference",
    "ExportDiagnostic",
}
EXPECTED_SHEETS = (
    "01_产品数据",
    "02_关键词需求",
    "03_竞争证据",
    "04_机会分析",
    "05_建议与复核",
)
EXPECTED_COLUMNS = {
    "product": (
        "ASIN",
        "Marketplace",
        "Title",
        "Product Facts",
        "Metrics",
        "Variation",
        "Reviews",
        "Quality Indicators",
        "Source Reference",
    ),
    "keyword": (
        "Keyword",
        "Metrics",
        "Query Status",
        "Related Products",
        "Channels",
        "Providers",
        "Limitations",
    ),
    "competition": (
        "Product Endpoint",
        "Keyword Relationship",
        "Channel",
        "Provider",
        "Evidence Count",
        "Variation Evidence",
        "Limitations",
    ),
    "opportunity": (
        "Product",
        "Signals",
        "Missing Evidence",
        "Risk Evidence",
        "Score References",
        "Explanation References",
    ),
    "recommendation": (
        "Recommendation Type",
        "Rule Reference",
        "Explanation",
        "Evidence References",
        "Limitations",
    ),
}
ROW_COUNTS = {
    "competition": 10,
    "keyword": 1,
    "opportunity": 1,
    "product": 1,
    "recommendation": 4,
}


def build_export():
    bundles, _, _, output_snapshot = build_operator_output_fixture()
    request = OperatorExportRequest(
        canonical_bundles=bundles,
        operator_output_snapshot=output_snapshot.to_dict(),
    )
    snapshot = OperatorExportBuilderV0_1().build(request)
    return bundles, output_snapshot, request, snapshot


def reverse_mapping_keys(value):
    if isinstance(value, dict):
        return {
            key: reverse_mapping_keys(value[key])
            for key in reversed(tuple(value))
        }
    if isinstance(value, list):
        return [reverse_mapping_keys(item) for item in value]
    return value


def replace_export_lineage(payload, index, **changes):
    lineage = payload["lineage_index"][index]
    old_id = lineage["export_lineage_id"]
    lineage.update(changes)
    content = dict(lineage)
    content.pop("export_lineage_id")
    new_id = deterministic_id("operator-export-lineage", content)
    lineage["export_lineage_id"] = new_id
    for row in payload["rows"]:
        if old_id in row["lineage_reference_ids"]:
            row["lineage_reference_ids"] = sorted(
                new_id if item == old_id else item
                for item in row["lineage_reference_ids"]
            )
    return old_id, new_id


class OperatorExportV01Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        (
            cls.bundles,
            cls.output_snapshot,
            cls.request,
            cls.snapshot,
        ) = build_export()

    def table(self, key):
        return next(
            item for item in self.snapshot.table_definitions
            if item.table_key == key
        )

    def rows(self, key):
        table_id = self.table(key).table_id
        return tuple(
            sorted(
                (item for item in self.snapshot.rows if item.table_id == table_id),
                key=lambda item: item.source_output_row_id,
            )
        )

    def test_public_api_is_exact(self):
        self.assertEqual(set(operator_export.__all__), EXPECTED_API)
        self.assertEqual(len(operator_export.__all__), 14)
        for name in EXPECTED_API:
            self.assertIsNotNone(getattr(operator_export, name))

    def test_ruleset_and_fixed_workbook_filename(self):
        self.assertEqual(OPERATOR_EXPORT_RULESET_VERSION, "operator-export-v0.1")
        self.assertEqual(self.snapshot.ruleset_version, OPERATOR_EXPORT_RULESET_VERSION)
        self.assertEqual(
            self.snapshot.workbook.filename, "amazon_product_analysis.xlsx"
        )
        identity = self.snapshot.to_dict()
        snapshot_id = identity.pop("snapshot_id")
        self.assertEqual(
            snapshot_id, deterministic_id("operator-export-snapshot", identity)
        )

    def test_fixed_sheet_names_and_ordinals(self):
        self.assertEqual(
            tuple(item.sheet_name for item in self.snapshot.sheet_definitions),
            EXPECTED_SHEETS,
        )
        self.assertEqual(
            tuple(item.ordinal for item in self.snapshot.sheet_definitions),
            (1, 2, 3, 4, 5),
        )

    def test_exact_columns_and_row_sources(self):
        for table in self.snapshot.table_definitions:
            self.assertEqual(table.columns, EXPECTED_COLUMNS[table.table_key])
            self.assertEqual(table.source_view, f"{table.table_key}_rows")
        for sheet in self.snapshot.sheet_definitions:
            table = next(
                item for item in self.snapshot.table_definitions
                if item.table_id == sheet.table_id
            )
            self.assertEqual(sheet.columns, table.columns)
            self.assertEqual(sheet.row_source, table.source_view)

    def test_snapshot_rejects_a_reidentified_noncanonical_table_layout(self):
        payload = self.snapshot.to_dict()
        table = payload["table_definitions"][0]
        table["table_key"] = "competition-v2"
        content = dict(table)
        content.pop("table_id")
        table["table_id"] = deterministic_id("operator-export-table", content)
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportSnapshotV0_1.from_dict(payload)

    def test_coverage_is_a_mechanical_inventory(self):
        self.assertEqual(self.snapshot.coverage.table_count, 5)
        self.assertEqual(self.snapshot.coverage.sheet_count, 5)
        self.assertEqual(self.snapshot.coverage.row_count, 17)
        self.assertEqual(self.snapshot.coverage.lineage_reference_count, 332)
        self.assertEqual(self.snapshot.coverage.diagnostic_count, 1)
        self.assertEqual(dict(self.snapshot.coverage.row_counts_by_table), ROW_COUNTS)

    def test_product_row_reproduces_operator_output(self):
        source = self.output_snapshot.product_rows[0]
        exported = self.rows("product")[0]
        self.assertEqual(exported.values["ASIN"], source.asin)
        self.assertEqual(exported.values["Marketplace"], source.marketplace)
        self.assertEqual(json.loads(exported.values["Title"]), source.to_dict()["title"])
        source_reference = json.loads(exported.values["Source Reference"])
        self.assertEqual(source_reference["output_row_id"], source.output_row_id)
        self.assertEqual(
            source_reference["lineage_reference_ids"],
            list(source.lineage_reference_ids),
        )

    def test_keyword_row_preserves_query_status_channels_and_limitations(self):
        source = self.output_snapshot.keyword_rows[0]
        exported = self.rows("keyword")[0]
        self.assertEqual(json.loads(exported.values["Keyword"]), source.to_dict()["keyword"])
        self.assertEqual(
            json.loads(exported.values["Query Status"]),
            source.to_dict()["query_status"],
        )
        self.assertEqual(json.loads(exported.values["Channels"]), list(source.channels))
        self.assertEqual(
            json.loads(exported.values["Limitations"]), list(source.limitations)
        )

    def test_competition_export_preserves_relationship_type_without_new_column(self):
        source_by_id = {
            item.output_row_id: item
            for item in self.output_snapshot.competition_rows
        }
        for exported in self.rows("competition"):
            source = source_by_id[exported.source_output_row_id]
            relationship = json.loads(exported.values["Keyword Relationship"])
            self.assertEqual(
                relationship["relationship"],
                source.to_dict()["keyword_relationship"],
            )
            self.assertEqual(
                relationship["relationship_type"], source.relationship_type
            )
            self.assertNotIn("Competitor Ranking", exported.values)
            self.assertNotIn("Competitor Score", exported.values)

    def test_opportunity_and_recommendation_rows_are_existing_references(self):
        opportunity = self.rows("opportunity")[0]
        source_opportunity = self.output_snapshot.opportunity_rows[0]
        self.assertEqual(
            json.loads(opportunity.values["Score References"]),
            source_opportunity.to_dict()["score_references"],
        )
        source_recommendations = {
            item.output_row_id: item
            for item in self.output_snapshot.recommendation_rows
        }
        for exported in self.rows("recommendation"):
            source = source_recommendations[exported.source_output_row_id]
            self.assertEqual(
                exported.values["Recommendation Type"],
                source.recommendation_type,
            )
            self.assertEqual(
                json.loads(exported.values["Rule Reference"]),
                source.to_dict()["rule_reference"],
            )

    def test_csv_has_exact_headers_deterministic_rows_and_safe_escaping(self):
        original_limit = csv.field_size_limit()
        try:
            csv.field_size_limit(10_000_000)
            for table_key, columns in EXPECTED_COLUMNS.items():
                text = self.snapshot.to_csv(table_key)
                parsed = list(csv.reader(io.StringIO(text)))
                self.assertEqual(tuple(parsed[0]), columns)
                self.assertEqual(len(parsed) - 1, ROW_COUNTS[table_key])
                expected_rows = self.rows(table_key)
                self.assertEqual(
                    parsed[1:],
                    [
                        [
                            "" if row.values[column] is None
                            else str(row.values[column])
                            for column in columns
                        ]
                        for row in expected_rows
                    ],
                )
                self.assertNotIn("\r\n", text)
                self.assertEqual(
                    self.snapshot.to_csv_bytes(table_key), text.encode("utf-8")
                )
        finally:
            csv.field_size_limit(original_limit)

    def test_csv_file_inventory_uses_utf8_chinese_sheet_names(self):
        files = self.snapshot.to_csv_files()
        self.assertEqual(
            tuple(files), tuple(f"{name}.csv" for name in EXPECTED_SHEETS)
        )
        for name, content in files.items():
            self.assertTrue(name.endswith(".csv"))
            self.assertEqual(content.decode("utf-8").encode("utf-8"), content)

    def test_workbook_model_contains_headers_rows_metadata_and_no_binary_writer(self):
        workbook = self.snapshot.to_workbook_dict()
        self.assertEqual(workbook["filename"], "amazon_product_analysis.xlsx")
        self.assertEqual(workbook["metadata"]["encoding"], "UTF-8")
        self.assertEqual(len(workbook["sheets"]), 5)
        self.assertEqual(
            tuple(item["sheet_name"] for item in workbook["sheets"]),
            EXPECTED_SHEETS,
        )
        self.assertEqual(
            sum(len(item["rows"]) for item in workbook["sheets"]), 17
        )
        json.dumps(workbook, ensure_ascii=False, allow_nan=False)
        self.assertFalse(hasattr(self.snapshot, "to_xlsx"))

    def test_every_output_lineage_is_exported_exactly_once(self):
        source_lineage_ids = {
            item.output_lineage_id for item in self.output_snapshot.lineage_index
        }
        source_by_id = {
            item.output_lineage_id: item
            for item in self.output_snapshot.lineage_index
        }
        exported_source_ids = {
            item.source_output_lineage_id for item in self.snapshot.lineage_index
        }
        self.assertEqual(exported_source_ids, source_lineage_ids)
        self.assertEqual(len(self.snapshot.lineage_index), len(source_lineage_ids))
        export_rows = {item.export_row_id: item for item in self.snapshot.rows}
        for lineage in self.snapshot.lineage_index:
            row = export_rows[lineage.export_row_id]
            self.assertEqual(lineage.source_output_row_id, row.source_output_row_id)
            self.assertEqual(
                lineage.source_output_snapshot_id,
                self.output_snapshot.snapshot_id,
            )
            self.assertEqual(
                lineage.source_lineage_id,
                source_by_id[lineage.source_output_lineage_id].source_lineage_id,
            )

    def test_lineage_replays_against_canonical_bundles(self):
        self.assertIs(
            self.snapshot.validate_against_bundles(self.bundles), self.snapshot
        )
        with self.assertRaises(OperatorExportValidationError):
            self.snapshot.validate_against_bundles(self.bundles[:-1])

    def test_orphan_export_lineage_is_rejected(self):
        payload = self.snapshot.to_dict()
        row = next(item for item in payload["rows"] if len(item["lineage_reference_ids"]) > 1)
        row["lineage_reference_ids"] = row["lineage_reference_ids"][1:]
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportSnapshotV0_1.from_dict(payload)

    def test_wrong_sheet_lineage_is_rejected(self):
        payload = self.snapshot.to_dict()
        current = payload["lineage_index"][0]["sheet_id"]
        wrong = next(
            item["sheet_id"] for item in payload["sheet_definitions"]
            if item["sheet_id"] != current
        )
        replace_export_lineage(payload, 0, sheet_id=wrong)
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportSnapshotV0_1.from_dict(payload)

    def test_missing_output_source_is_rejected(self):
        payload = self.snapshot.to_dict()
        replace_export_lineage(
            payload, 0, source_output_row_id="operator-row:missing"
        )
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportSnapshotV0_1.from_dict(payload)

    def test_fingerprint_mismatch_is_rejected(self):
        payload = self.snapshot.to_dict()
        replace_export_lineage(
            payload, 0, source_bundle_fingerprints=["0" * 64]
        )
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportSnapshotV0_1.from_dict(payload)

    def test_export_identity_mismatch_is_rejected(self):
        payload = self.snapshot.to_dict()
        first_column = next(iter(payload["rows"][0]["values"]))
        payload["rows"][0]["values"][first_column] = "tampered"
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportSnapshotV0_1.from_dict(payload)

    def test_strict_serialization_round_trip_and_unknown_field_rejection(self):
        restored = OperatorExportSnapshotV0_1.from_dict(self.snapshot.to_dict())
        self.assertEqual(restored.to_dict(), self.snapshot.to_dict())
        self.assertEqual(restored.to_json(), canonical_json(self.snapshot))
        payload = self.snapshot.to_dict()
        payload["unknown"] = True
        with self.assertRaises(OperatorExportSerializationError):
            OperatorExportSnapshotV0_1.from_dict(payload)

    def test_serialized_operator_output_is_validated_fail_closed(self):
        payload = self.output_snapshot.to_dict()
        payload["product_rows"][0]["unknown"] = True
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportRequest(
                canonical_bundles=self.bundles,
                operator_output_snapshot=payload,
            )
        for forbidden_key in (
            "raw_payload",
            "raw_provider_payload",
            "access_token",
            "client_secret",
            "internal_metadata",
        ):
            payload = self.output_snapshot.to_dict()
            diagnostic = payload["diagnostics"][0]
            diagnostic["message"] = {forbidden_key: "must-not-export"}
            diagnostic_content = dict(diagnostic)
            diagnostic_content.pop("diagnostic_id")
            diagnostic["diagnostic_id"] = deterministic_id(
                "operator-output-diagnostic", diagnostic_content
            )
            snapshot_content = dict(payload)
            snapshot_content.pop("snapshot_id")
            payload["snapshot_id"] = deterministic_id(
                "operator-output-snapshot", snapshot_content
            )
            with self.subTest(forbidden_key=forbidden_key):
                with self.assertRaises(OperatorExportValidationError):
                    OperatorExportRequest(
                        canonical_bundles=self.bundles,
                        operator_output_snapshot=payload,
                    )

    def test_request_and_snapshot_are_deeply_immutable(self):
        with self.assertRaises(TypeError):
            self.request.operator_output_snapshot["snapshot_id"] = "changed"
        nested = self.request.operator_output_snapshot[
            "product_rows"
        ][0]["product_facts"][0]
        with self.assertRaises(TypeError):
            nested[next(iter(nested))] = "changed"
        with self.assertRaises(TypeError):
            self.snapshot.rows[0].values[next(iter(self.snapshot.rows[0].values))] = "changed"
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.snapshot_id = "changed"

    def test_build_is_deterministic_under_bundle_and_mapping_order_changes(self):
        reordered_request = OperatorExportRequest(
            canonical_bundles=tuple(reversed(self.bundles)),
            operator_output_snapshot=reverse_mapping_keys(
                self.output_snapshot.to_dict()
            ),
        )
        rebuilt = OperatorExportBuilderV0_1().build(reordered_request)
        self.assertEqual(rebuilt.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(rebuilt.to_json(), self.snapshot.to_json())
        self.assertEqual(rebuilt.to_csv_files(), self.snapshot.to_csv_files())

    def test_build_is_deterministic_across_processes(self):
        script = (
            "from tests.test_operator_output_v0_1 import build_fixture;"
            "from amazon_product_intelligence.operator_export import "
            "OperatorExportRequest,OperatorExportBuilderV0_1;"
            "b,_,_,o=build_fixture();"
            "r=OperatorExportRequest(canonical_bundles=b,"
            "operator_output_snapshot=o.to_dict());"
            "print(OperatorExportBuilderV0_1().build(r).snapshot_id)"
        )
        environment = dict(os.environ)
        environment["PYTHONPATH"] = "src"
        actual = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            text=True,
            encoding="utf-8",
        ).strip()
        self.assertEqual(actual, self.snapshot.snapshot_id)

    def test_builder_does_not_mutate_source_snapshot(self):
        payload = self.output_snapshot.to_dict()
        before = canonical_json(payload)
        request = OperatorExportRequest(
            canonical_bundles=self.bundles,
            operator_output_snapshot=payload,
        )
        OperatorExportBuilderV0_1().build(request)
        self.assertEqual(canonical_json(payload), before)

    def test_builder_rejects_wrong_request_type(self):
        with self.assertRaises(OperatorExportValidationError):
            OperatorExportBuilderV0_1().build(self.output_snapshot)

    def test_production_dependency_and_safety_boundary(self):
        root = Path(__file__).resolve().parents[1]
        production = root / "src" / "amazon_product_intelligence" / "operator_export"
        allowed_absolute = {
            "__future__",
            "collections",
            "collections.abc",
            "csv",
            "dataclasses",
            "hashlib",
            "io",
            "json",
            "re",
            "types",
            "typing",
            "amazon_product_intelligence.contracts",
        }
        forbidden_calls = {
            "eval", "exec", "hash", "repr", "compile", "open",
        }
        forbidden_import_parts = {
            "adapters",
            "competition_intelligence",
            "conflict_resolution",
            "decision_framework",
            "demand_intelligence",
            "evidence_evaluation",
            "evidence_policy",
            "network",
            "operator_output",
            "opportunity_intelligence",
            "opportunity_scoring",
            "pickle",
            "product_intelligence",
            "random",
            "recommendation_framework",
            "socket",
            "time",
            "urllib",
            "uuid",
        }
        for path in sorted(production.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(alias.name, allowed_absolute)
                        self.assertTrue(
                            forbidden_import_parts.isdisjoint(alias.name.split("."))
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.level == 0:
                        self.assertIn(node.module, allowed_absolute)
                        self.assertTrue(
                            forbidden_import_parts.isdisjoint(node.module.split("."))
                        )
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, forbidden_calls)


if __name__ == "__main__":
    unittest.main()
