from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest import mock
import zipfile

from amazon_product_intelligence.market_report import (
    MarketReportBuildRequest,
    MarketReportBuilderV0_1,
    validate_market_report_payload,
)
from amazon_product_intelligence.market_report.delivery import (
    OPERATOR_MARKDOWN_FILENAME,
    OPERATOR_XLSX_FILENAME,
    ExcelReportRenderer,
    MarkdownReportRenderer,
    OperatorReportDelivery,
    OperatorReportExcelError,
)
from amazon_product_intelligence.operator_workflow import (
    OperatorWorkflowBuilderV0_1,
    OperatorWorkflowRequest,
)


ROOT = Path(__file__).parents[1]
EXAMPLE = ROOT / "docs" / "examples" / "market_report.json"
INPUT_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "market_report"
    / "market_report_input_v0_1.json"
)
R7_WORKFLOW_FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "market_report"
    / "r7_partial_live_shape.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _xlsx_xml(path: Path) -> str:
    with zipfile.ZipFile(path, "r") as package:
        return "\n".join(
            package.read(name).decode("utf-8-sig")
            for name in package.namelist()
            if name.endswith(".xml")
        )


class OperatorReportDeliveryV01Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.report = validate_market_report_payload(
            json.loads(EXAMPLE.read_text(encoding="utf-8"))
        )

    def _excel_renderer(self) -> ExcelReportRenderer:
        node = os.environ.get("MARKET_REPORT_NODE_EXECUTABLE")
        modules = os.environ.get("MARKET_REPORT_NODE_MODULES")
        renderer = ExcelReportRenderer(
            node_executable=node,
            node_modules_path=modules,
        )
        try:
            renderer._resolve_node()
            renderer._resolve_node_modules()
        except OperatorReportExcelError as exc:
            self.skipTest(f"artifact-tool runtime is unavailable: {exc}")
        return renderer

    def test_bundled_runtime_is_discovered_without_environment_configuration(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            runtime = Path(directory) / "node"
            executable = (
                runtime / "bin" / ("node.exe" if os.name == "nt" else "node")
            )
            package = (
                runtime
                / "node_modules"
                / "@oai"
                / "artifact-tool"
                / "package.json"
            )
            executable.parent.mkdir(parents=True)
            executable.touch()
            package.parent.mkdir(parents=True)
            package.write_text("{}", encoding="utf-8")
            renderer = ExcelReportRenderer()
            with mock.patch.object(
                renderer, "_bundled_runtime_roots", return_value=(runtime,)
            ):
                self.assertEqual(renderer._resolve_node(), executable.resolve())
                self.assertEqual(
                    renderer._resolve_node_modules(),
                    (runtime / "node_modules").resolve(),
                )

    def test_explicit_incomplete_node_modules_remain_a_hard_failure(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            node = root / "node.exe"
            modules = root / "node_modules"
            node.touch()
            modules.mkdir()
            renderer = ExcelReportRenderer(
                node_executable=node,
                node_modules_path=modules,
            )
            with self.assertRaisesRegex(
                OperatorReportExcelError, "artifact-tool node_modules"
            ):
                renderer._resolve_node_modules()

    def _report_with_missing_competition_data(self):
        payload = json.loads(INPUT_FIXTURE.read_text(encoding="utf-8"))
        request_payload = deepcopy(payload)
        request_payload["competition_output"].pop("brand_count")
        request_payload["competition_output"].pop("rating_summary")
        return MarketReportBuilderV0_1().build(
            MarketReportBuildRequest(**request_payload)
        )

    def test_schema_compatibility_and_required_output_names(self) -> None:
        loaded = OperatorReportDelivery.load_report(EXAMPLE)

        self.assertEqual(self.report, loaded)
        self.assertEqual("operator_market_report.xlsx", OPERATOR_XLSX_FILENAME)
        self.assertEqual("operator_market_report.md", OPERATOR_MARKDOWN_FILENAME)

    def test_markdown_generation_is_operator_readable_and_traceable(self) -> None:
        rendered = MarkdownReportRenderer().render(self.report)

        for heading in (
            "# Market Overview",
            "# Buyer Need Analysis",
            "# Competition Analysis",
            "# Opportunity Assessment",
            "# Data Limitations",
        ):
            self.assertIn(heading, rendered)
        self.assertIn(self.report.report_id, rendered)
        self.assertIn("buyer-need:portable-001", rendered)
        self.assertIn("opportunity-score-policy-v0.1", rendered)

    def test_xlsx_generation_has_four_required_worksheets(self) -> None:
        with TemporaryDirectory() as directory:
            target = Path(directory) / OPERATOR_XLSX_FILENAME
            self._excel_renderer().render(self.report, target)
            package_text = _xlsx_xml(target)

            self.assertTrue(target.read_bytes().startswith(b"PK"))
            for sheet_name in (
                "Market Overview",
                "Buyer Need Analysis",
                "Competition Analysis",
                "Opportunity Analysis",
            ):
                self.assertIn(f'name="{sheet_name}"', package_text)
            self.assertIn(self.report.report_id, package_text)
            self.assertIn("Outdoor Portability", package_text)

    def test_missing_data_is_explicitly_unavailable_in_both_formats(self) -> None:
        report = self._report_with_missing_competition_data()
        markdown = MarkdownReportRenderer().render(report)
        self.assertIn(
            "| Brand Count | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |",
            markdown,
        )
        self.assertIn(
            "| Rating Distribution | UNAVAILABLE | UNAVAILABLE | UNAVAILABLE |",
            markdown,
        )

        with TemporaryDirectory() as directory:
            target = Path(directory) / OPERATOR_XLSX_FILENAME
            self._excel_renderer().render(report, target)
            package_text = _xlsx_xml(target)
            self.assertIn("Brand Count", package_text)
            self.assertIn("Rating Distribution", package_text)
            self.assertIn("UNAVAILABLE", package_text)

    def test_r7_provider_neutral_partial_report_delivery_fixture(self) -> None:
        report = self._report_with_missing_competition_data()
        fixture = json.loads(R7_WORKFLOW_FIXTURE.read_text(encoding="utf-8"))
        workflow = OperatorWorkflowBuilderV0_1().build(
            OperatorWorkflowRequest(
                report=report,
                run_id=fixture["run_id"],
                run_status=fixture["run_status"],
                provider_summary=fixture["provider_summary"],
                recovery=fixture["recovery"],
            )
        )
        with TemporaryDirectory() as directory:
            delivered = OperatorReportDelivery(
                excel_renderer=self._excel_renderer()
            ).deliver(report, directory, operator_workflow=workflow)
            package_text = _xlsx_xml(delivered.xlsx_path)

            self.assertTrue(delivered.xlsx_path.read_bytes().startswith(b"PK"))
            self.assertIn('name="Operator Summary"', package_text)
            self.assertIn("UNAVAILABLE", package_text)
            self.assertEqual(workflow.run_health.executed_operation_count, 2)
            self.assertEqual(workflow.run_health.replayed_operation_count, 0)

    def test_delivery_output_is_byte_deterministic(self) -> None:
        renderer = self._excel_renderer()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first" / OPERATOR_XLSX_FILENAME
            second = root / "second" / OPERATOR_XLSX_FILENAME
            first.parent.mkdir()
            second.parent.mkdir()
            renderer.render(self.report, first)
            renderer.render(self.report, second)

            self.assertEqual(_sha256(first), _sha256(second))
            markdown = MarkdownReportRenderer()
            self.assertEqual(markdown.render(self.report), markdown.render(self.report))


if __name__ == "__main__":
    unittest.main()
