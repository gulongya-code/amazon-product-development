"""Operator-facing delivery orchestration for a validated Market Report."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from amazon_product_intelligence.market_report.models import (
    MarketReportSnapshot,
    MarketReportValidationError,
    validate_market_report_payload,
)

from .excel_renderer import ExcelReportRenderer
from .markdown_renderer import MarkdownReportRenderer


OPERATOR_REPORT_DELIVERY_VERSION = "operator-market-report-delivery-v0.1"
OPERATOR_XLSX_FILENAME = "operator_market_report.xlsx"
OPERATOR_MARKDOWN_FILENAME = "operator_market_report.md"


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorReportDeliveryResult:
    source_report_id: str
    delivery_version: str
    xlsx_path: Path
    markdown_path: Path
    xlsx_sha256: str
    markdown_sha256: str


class OperatorReportDelivery:
    """Validate once, then render the same report to XLSX and Markdown."""

    def __init__(
        self,
        *,
        excel_renderer: ExcelReportRenderer | None = None,
        markdown_renderer: MarkdownReportRenderer | None = None,
    ) -> None:
        self._excel_renderer = excel_renderer or ExcelReportRenderer()
        self._markdown_renderer = markdown_renderer or MarkdownReportRenderer()

    def deliver(
        self,
        source: MarketReportSnapshot | Mapping[str, Any] | str | Path,
        output_directory: str | Path,
        *,
        preview_directory: str | Path | None = None,
    ) -> OperatorReportDeliveryResult:
        report = self.load_report(source)
        destination = Path(output_directory)
        destination.mkdir(parents=True, exist_ok=True)
        markdown_path = destination / OPERATOR_MARKDOWN_FILENAME
        xlsx_path = destination / OPERATOR_XLSX_FILENAME

        markdown = self._markdown_renderer.render(report)
        temporary_markdown = destination / f".{OPERATOR_MARKDOWN_FILENAME}.tmp"
        temporary_markdown.write_text(markdown, encoding="utf-8", newline="\n")
        temporary_markdown.replace(markdown_path)
        self._excel_renderer.render(
            report,
            xlsx_path,
            preview_directory=preview_directory,
        )
        return OperatorReportDeliveryResult(
            source_report_id=report.report_id,
            delivery_version=OPERATOR_REPORT_DELIVERY_VERSION,
            xlsx_path=xlsx_path,
            markdown_path=markdown_path,
            xlsx_sha256=self._sha256(xlsx_path),
            markdown_sha256=self._sha256(markdown_path),
        )

    @staticmethod
    def load_report(
        source: MarketReportSnapshot | Mapping[str, Any] | str | Path,
    ) -> MarketReportSnapshot:
        if isinstance(source, MarketReportSnapshot):
            return source.validate()
        if isinstance(source, Mapping):
            return validate_market_report_payload(source)
        path = Path(source)
        if not path.is_file():
            raise MarketReportValidationError(f"Market Report file does not exist: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MarketReportValidationError(
                f"cannot read Market Report JSON: {exc}"
            ) from exc
        return validate_market_report_payload(payload)

    @staticmethod
    def _sha256(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()


__all__ = (
    "OPERATOR_MARKDOWN_FILENAME",
    "OPERATOR_REPORT_DELIVERY_VERSION",
    "OPERATOR_XLSX_FILENAME",
    "OperatorReportDelivery",
    "OperatorReportDeliveryResult",
)
