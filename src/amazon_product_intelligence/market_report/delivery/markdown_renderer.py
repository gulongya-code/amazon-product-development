"""Deterministic operator-facing Markdown rendering for Market Report V0.1."""

from __future__ import annotations

import json

from amazon_product_intelligence.market_report.models import (
    CompetitionMetric,
    MarketReportSnapshot,
    ReportAvailability,
)


def _cell(value: object) -> str:
    if value is None:
        return "UNAVAILABLE"
    if isinstance(value, (dict, list, tuple)):
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    else:
        rendered = str(value)
    return rendered.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _percent(value: float | None) -> str:
    return "UNAVAILABLE" if value is None else f"{value:.1%}"


def _evidence(values: tuple[str, ...]) -> str:
    return ", ".join(values) if values else "UNAVAILABLE"


def _metric_value(metric: CompetitionMetric) -> str:
    if metric.availability is ReportAvailability.UNAVAILABLE:
        return "UNAVAILABLE"
    return _cell(metric.value)


def _metric_label(metric_name: str) -> str:
    return " ".join(
        part.upper() if part.casefold() == "asin" else part.title()
        for part in metric_name.split("_")
    )


class MarkdownReportRenderer:
    """Render a validated Market Report without adding analytical claims."""

    def render(self, report: MarketReportSnapshot) -> str:
        report.validate()
        lines = [
            "# Market Overview",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Category | {_cell(report.category.category_name)} |",
            f"| Marketplace | {_cell(report.category.marketplace)} |",
            f"| Category Scope | {_cell(report.category.scope)} |",
            f"| Sample Size | {report.sample.sample_size} |",
            f"| Unique ASIN Count | {report.sample.unique_asin_count} |",
            f"| ASIN Coverage | {_percent(report.sample.asin_coverage)} |",
            f"| Data Window | {_cell(report.data_window.period)} |",
            f"| Window Start | {_cell(report.data_window.start_at)} |",
            f"| Window End | {_cell(report.data_window.end_at)} |",
            f"| Report ID | `{report.report_id}` |",
            f"| Report Version | `{report.report_version}` |",
            f"| Pipeline Version | `{report.pipeline_version}` |",
            "",
            "# Buyer Need Analysis",
            "",
            "| Buyer Need | Share | Confidence | Validation Status | Evidence |",
            "|---|---:|---|---|---|",
        ]
        for need in report.buyer_needs.needs:
            lines.append(
                "| "
                + " | ".join(
                    (
                        _cell(need.need_label),
                        _percent(need.share),
                        _cell(need.confidence),
                        _cell(need.validation_status),
                        _cell(_evidence(need.evidence_ids)),
                    )
                )
                + " |"
            )

        lines.extend(
            (
                "",
                "# Competition Analysis",
                "",
                "| Indicator | Availability | Value | Evidence |",
                "|---|---|---|---|",
            )
        )
        for metric in self._competition_metrics(report):
            lines.append(
                "| "
                + " | ".join(
                    (
                        _cell(_metric_label(metric.metric_name)),
                        metric.availability.value,
                        _metric_value(metric),
                        _cell(_evidence(metric.evidence_ids)),
                    )
                )
                + " |"
            )

        opportunity = report.opportunity_score
        lines.extend(
            (
                "",
                "# Opportunity Assessment",
                "",
                "| Field | Value |",
                "|---|---|",
                f"| Opportunity Score | {_cell(opportunity.score_value)} |",
                f"| Confidence | {_cell(opportunity.confidence)} |",
                f"| Score Status | {_cell(opportunity.score_status)} |",
                f"| Policy | `{opportunity.policy_version}` |",
                f"| Policy Fingerprint | `{opportunity.policy_fingerprint}` |",
                "",
                "## Explanation",
                "",
                "| Dimension | Score | Contribution | Maximum | Explanation | Evidence |",
                "|---|---:|---:|---:|---|---|",
            )
        )
        for dimension in opportunity.dimensions:
            lines.append(
                "| "
                + " | ".join(
                    (
                        _cell(dimension.dimension.replace("_", " ").title()),
                        _cell(dimension.score_value),
                        _cell(dimension.contribution),
                        _cell(dimension.max_contribution),
                        _cell(dimension.explanation),
                        _cell(_evidence(dimension.evidence_ids)),
                    )
                )
                + " |"
            )
        lines.extend(("", "### Risks", ""))
        lines.extend(
            f"- {_cell(value)}" for value in (opportunity.risks or ("None recorded.",))
        )

        limitations = self._limitations(report)
        lines.extend(("", "# Data Limitations", ""))
        lines.extend(f"- {_cell(value)}" for value in limitations)
        lines.extend(
            (
                "",
                "## Evidence and Provenance",
                "",
                "| Source Module | Source Version | Source Record | Availability | Evidence | Limitations |",
                "|---|---|---|---|---|---|",
            )
        )
        for reference in report.provenance:
            lines.append(
                "| "
                + " | ".join(
                    (
                        _cell(reference.source_module),
                        _cell(reference.source_version),
                        _cell(reference.source_record_id),
                        reference.availability.value,
                        _cell(_evidence(reference.evidence_ids)),
                        _cell(", ".join(reference.limitations) or "None recorded."),
                    )
                )
                + " |"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def _competition_metrics(
        report: MarketReportSnapshot,
    ) -> tuple[CompetitionMetric, ...]:
        section = report.competition
        return (
            section.competition_level,
            section.asin_count,
            section.brand_count,
            section.price_distribution,
            section.rating_distribution,
            section.review_distribution,
            section.competition_concentration,
        )

    @staticmethod
    def _limitations(report: MarketReportSnapshot) -> tuple[str, ...]:
        values = {
            *report.limitations,
            *report.sample.limitations,
            *report.data_window.limitations,
            *report.buyer_needs.limitations,
            *report.competition.limitations,
            *report.opportunity_score.limitations,
            *(value for item in report.buyer_needs.needs for value in item.limitations),
            *(
                value
                for metric in MarkdownReportRenderer._competition_metrics(report)
                for value in metric.limitations
            ),
        }
        return tuple(sorted(values)) or ("No limitations recorded.",)


__all__ = ("MarkdownReportRenderer",)
