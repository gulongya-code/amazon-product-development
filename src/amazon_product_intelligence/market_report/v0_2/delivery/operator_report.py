"""Atomic XLSX and Markdown delivery from one validated V0.2 snapshot."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from amazon_product_intelligence.xlsx_delivery.package_fingerprint import ooxml_package_content_sha256

from ..models import MarketReportSnapshotV0_2, MarketReportV0_2ValidationError
from ..validation import market_report_v0_2_from_dict
from .excel_renderer import ExcelReportRendererV0_2
from .markdown_renderer import MarkdownReportRendererV0_2


OPERATOR_REPORT_DELIVERY_V0_2_VERSION = "operator-market-report-delivery-v0.2"
OPERATOR_XLSX_FILENAME = "operator_market_report.xlsx"
OPERATOR_MARKDOWN_FILENAME = "operator_market_report.md"


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorReportDeliveryResultV0_2:
    source_report_id: str
    delivery_version: str
    xlsx_path: Path
    markdown_path: Path
    xlsx_sha256: str
    xlsx_package_content_sha256: str
    markdown_sha256: str


class OperatorReportDeliveryV0_2:
    def __init__(self) -> None:
        self._excel = ExcelReportRendererV0_2()
        self._markdown = MarkdownReportRendererV0_2()

    def deliver(
        self,
        source: MarketReportSnapshotV0_2 | Mapping[str, Any] | Path,
        output_directory: Path,
    ) -> OperatorReportDeliveryResultV0_2:
        report = self.load_report(source)
        output_directory.mkdir(parents=True, exist_ok=True)
        xlsx = output_directory / OPERATOR_XLSX_FILENAME
        markdown = output_directory / OPERATOR_MARKDOWN_FILENAME
        temporary = markdown.with_name(f".{markdown.name}.tmp")
        temporary.write_text(self._markdown.render(report), encoding="utf-8", newline="\n")
        temporary.replace(markdown)
        self._excel.render(report, xlsx)
        xlsx_bytes = xlsx.read_bytes()
        return OperatorReportDeliveryResultV0_2(
            source_report_id=report.metadata.report_id,
            delivery_version=OPERATOR_REPORT_DELIVERY_V0_2_VERSION,
            xlsx_path=xlsx,
            markdown_path=markdown,
            xlsx_sha256=sha256(xlsx_bytes).hexdigest(),
            xlsx_package_content_sha256=ooxml_package_content_sha256(xlsx_bytes),
            markdown_sha256=sha256(markdown.read_bytes()).hexdigest(),
        )

    @staticmethod
    def load_report(source: MarketReportSnapshotV0_2 | Mapping[str, Any] | Path) -> MarketReportSnapshotV0_2:
        if isinstance(source, MarketReportSnapshotV0_2):
            return source.validate()
        if isinstance(source, Mapping):
            return market_report_v0_2_from_dict(source)
        if not source.is_file():
            raise MarketReportV0_2ValidationError(f"Market Report file does not exist: {source}")
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MarketReportV0_2ValidationError(f"cannot read Market Report V0.2 JSON: {exc}") from exc
        return market_report_v0_2_from_dict(payload)


__all__ = (
    "OPERATOR_MARKDOWN_FILENAME", "OPERATOR_REPORT_DELIVERY_V0_2_VERSION",
    "OPERATOR_XLSX_FILENAME", "OperatorReportDeliveryResultV0_2", "OperatorReportDeliveryV0_2",
)
