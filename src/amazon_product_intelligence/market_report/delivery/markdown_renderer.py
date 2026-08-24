"""Deterministic operator-facing Markdown rendering for Market Report V0.1."""

from __future__ import annotations

import json

from amazon_product_intelligence.market_report.models import (
    CompetitionMetric,
    MarketReportSnapshot,
    ReportAvailability,
)
from amazon_product_intelligence.operator_workflow import (
    OperatorWorkflowSnapshotV0_1,
    build_standalone_operator_workflow,
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

    def render(
        self,
        report: MarketReportSnapshot,
        *,
        operator_workflow: OperatorWorkflowSnapshotV0_1 | None = None,
    ) -> str:
        report.validate()
        workflow = operator_workflow or build_standalone_operator_workflow(report)
        lines = self._executive_lines(workflow)
        lines.extend((
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
        ))
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
    def _executive_lines(workflow: OperatorWorkflowSnapshotV0_1) -> list[str]:
        health = workflow.run_health
        credit_note = (
            "fixture reference credits; not billed"
            if health.credit_semantics == "FIXTURE_REFERENCE"
            else "live provider-reported credits"
            if health.credit_semantics == "LIVE_PROVIDER_REPORTED"
            else "billing semantics not recorded"
        )
        provider_usage = (
            f"provider={health.provider_id}; logical operations={health.logical_operation_count}; "
            f"transport attempts={health.transport_attempt_count}; executed={health.executed_operation_count}; "
            f"replayed={health.replayed_operation_count}; credits={_cell(health.credits)}; "
            f"credit semantics={health.credit_semantics}; {credit_note}"
        )
        recovery = (
            f"RESUMED from {health.resume_source_run_id}"
            if health.resumed
            else "UNINTERRUPTED / no resume lineage"
        )
        lines = [
            "# Operator Brief",
            "",
            "| Field | Operator view |",
            "|---|---|",
            f"| Operator action | **{workflow.operator_action.value}** |",
            f"| Recommendation semantic | `{workflow.recommendation_type}` |",
            f"| Why this action | {_cell(workflow.action_reason)} |",
            f"| Evidence readiness | **{workflow.evidence_readiness}** |",
            f"| Run health | {_cell(health.status)}; retried={str(health.retried).lower()}; {_cell(recovery)} |",
            f"| Provider usage | {_cell(provider_usage)} |",
            f"| Workflow contract | `{workflow.ruleset_version}` |",
            f"| Workflow audit ID | `{workflow.snapshot_id}` |",
            "",
            "## What We Know",
            "",
        ]
        lines.extend(
            f"- **{_cell(item.label)}** — `{item.status}` — {_cell(item.value)} "
            f"(Evidence: {_cell(_evidence(item.evidence_ids or item.provenance_reference_ids))})"
            for item in workflow.supporting_evidence
        )
        if not workflow.supporting_evidence:
            lines.append("- No supporting evidence is currently available.")
        lines.extend(("", "## What We Do Not Know", ""))
        lines.extend(
            f"- **{_cell(item.label)}** — `{item.status}` — {_cell(item.reason)} "
            f"(Audit: {_cell(_evidence(item.provenance_reference_ids))})"
            for item in workflow.missing_evidence
        )
        if not workflow.missing_evidence:
            lines.append("- No material evidence gap is recorded in the validated report.")
        lines.extend(("", "## Top Opportunity Themes", ""))
        lines.extend(
            f"- **{_cell(item.label)}** — {_cell(item.value)} — `{item.status}`"
            for item in workflow.top_buyer_need_themes
        )
        lines.extend(("", "## Top Risks / Blockers", ""))
        lines.extend(f"- {_cell(item.value)}" for item in workflow.risks_and_limitations)
        if not workflow.risks_and_limitations:
            lines.append("- No explicit risk record is available; framework adapter review is still required.")
        lines.extend(("", "## Recommended Next Checks", ""))
        lines.extend(
            f"{index}. **[P{item.priority}] {_cell(item.action)}** Trigger: `{item.trigger_status}`. "
            f"Why: {_cell(item.reason)} Audit: {_cell(_evidence(item.provenance_reference_ids))}."
            for index, item in enumerate(workflow.next_actions, start=1)
        )
        if not workflow.next_actions:
            lines.append(
                "1. Perform human review before advancing; automatic market-entry decisions are out of scope."
            )
        lines.extend(
            (
                "",
                "## Run Health / Provider Usage",
                "",
                f"- Status: `{health.status}`",
                f"- Retry observed: `{str(health.retried).lower()}`",
                f"- Recovery: {_cell(recovery)}",
                f"- Provider usage: {_cell(provider_usage)}",
                "",
                "## Semantic Boundary",
                "",
                f"- Decision Framework: `{workflow.framework_integration['decision_framework_execution_status']}`.",
                f"- Recommendation Framework: `{workflow.framework_integration['recommendation_framework_execution_status']}`.",
                f"- Adapter gap: {_cell(workflow.framework_integration['adapter_gap'])}",
                "- This workflow does not claim profitability, guaranteed success, purchase advice, or an automatic market-entry decision.",
                "",
            )
        )
        return lines

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
