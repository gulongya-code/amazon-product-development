"""Markdown renderer for the pure Market Report V0.2 operator view."""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping

from ..models import MarketReportSnapshotV0_2
from .operator_view import compose_operator_view


def _text(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value).replace("|", "\\|").replace("\n", " ")


def _table(rows: Iterable[tuple[Any, Any]]) -> list[str]:
    result = ["| Field | Value |", "|---|---|"]
    result.extend(f"| {_text(key)} | {_text(value)} |" for key, value in rows)
    return result


class MarkdownReportRendererV0_2:
    def render(self, report: MarketReportSnapshotV0_2) -> str:
        view = compose_operator_view(report)
        p = view.payload
        lines = [
            "# Operator Market Report V0.2", "",
            "This report is decision support. Product Directions are hypotheses; Competitor Shortlist order is for human review and is not a rank.",
            "", "## Cross-artifact parity", "", *_table(view.parity.items()),
        ]
        sections: tuple[tuple[str, Mapping[str, Any]], ...] = (
            ("Executive Summary", p["executive_summary"]),
            ("Market Overview", {"category": p["category"], "sample": p["sample"], "data_window": p["data_window"], "scope_context": p["scope_context"]}),
            ("Market Size", p["market_size"]),
            ("Competition", {"true_competitor_set": p["true_competitor_set"], "competitor_structure": p["competitor_structure"]}),
            ("Distributions", {"items": p["distributions"]}),
            ("Competitor Details", {"items": p["competitor_details"]}),
            ("Buyer Needs", p["buyer_needs"]),
            ("Product Directions", p["product_directions"]),
            ("Competitor Shortlist", p["competitor_shortlist"]),
            ("Opportunity", p["opportunity_score"]),
            ("Evidence Gaps", {"report_limitations": p["limitations"], "sanitized_appendix": p["sanitized_appendix"], "external_integrations": p["external_integrations"]}),
            ("Audit / Provenance", {"metadata": p["metadata"], "provenance": p["provenance"], "evidence_registry": p["evidence_registry"]}),
        )
        for title, section in sections:
            lines.extend(("", f"## {title}", "", *_table(section.items())))
        lines.append("")
        return "\n".join(lines)


__all__ = ("MarkdownReportRendererV0_2",)
