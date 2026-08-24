"""Conservative composition of validated report evidence into operator workflow V0.1."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.decision_framework import DECISION_FRAMEWORK_RULESET_VERSION
from amazon_product_intelligence.market_report.models import (
    CompetitionMetric,
    MarketReportSnapshot,
    ReportAvailability,
)
from amazon_product_intelligence.operator_output import OPERATOR_OUTPUT_RULESET_VERSION
from amazon_product_intelligence.operator_workbook import OPERATOR_WORKBOOK_RULESET_VERSION
from amazon_product_intelligence.recommendation_framework import (
    RECOMMENDATION_FRAMEWORK_RULESET_VERSION,
)

from .models import (
    OPERATOR_WORKFLOW_RULESET_VERSION,
    OperatorActionType,
    OperatorClaim,
    OperatorNextAction,
    OperatorRunHealth,
    OperatorWorkflowRequest,
    OperatorWorkflowSnapshotV0_1,
)


_ADAPTER_GAP = (
    "Production Pipeline does not currently expose the complete Demand, Evidence "
    "Evaluation, Conflict Resolution, Evidence Policy, Decision, Scoring, and "
    "Recommendation snapshot chain required by the public builders. Inputs were "
    "not reconstructed or fabricated."
)


def _claim(
    *,
    label: str,
    value: Any,
    status: str,
    reason: str,
    evidence_ids: Iterable[str] = (),
    provenance_reference_ids: Iterable[str],
) -> OperatorClaim:
    content = {
        "label": label,
        "value": value,
        "status": status,
        "reason": reason,
        "evidence_ids": tuple(sorted(set(evidence_ids))),
        "provenance_reference_ids": tuple(sorted(set(provenance_reference_ids))),
    }
    return OperatorClaim(
        claim_id=deterministic_id("operator-workflow-claim", content),
        **content,
    )


def _next_action(
    *,
    priority: int = 3,
    action: str,
    reason: str,
    trigger_status: str,
    evidence_ids: Iterable[str] = (),
    provenance_reference_ids: Iterable[str],
) -> OperatorNextAction:
    content = {
        "priority": priority,
        "action": action,
        "reason": reason,
        "trigger_status": trigger_status,
        "evidence_ids": tuple(sorted(set(evidence_ids))),
        "provenance_reference_ids": tuple(sorted(set(provenance_reference_ids))),
    }
    return OperatorNextAction(
        action_id=deterministic_id("operator-workflow-next-action", content),
        **content,
    )


def _competition_metrics(report: MarketReportSnapshot) -> tuple[CompetitionMetric, ...]:
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


def _metric_label(name: str) -> str:
    return " ".join(part.upper() if part == "asin" else part.title() for part in name.split("_"))


def _provider_value(summary: Mapping[str, Any] | None, key: str, default: Any) -> Any:
    return default if summary is None else summary.get(key, default)


def _run_health(request: OperatorWorkflowRequest) -> OperatorRunHealth:
    summary = request.provider_summary
    recovery = request.recovery or {}
    executed = int(_provider_value(summary, "executed_operation_count", 0))
    attempts = int(_provider_value(summary, "transport_attempt_count", 0))
    resume_source = recovery.get("resume_source_run_id")
    return OperatorRunHealth(
        status=request.run_status,
        retried=attempts > executed,
        resumed=resume_source is not None,
        provider_id=str(_provider_value(summary, "provider_id", "NOT_RECORDED")),
        logical_operation_count=int(_provider_value(summary, "operation_count", 0)),
        transport_attempt_count=attempts,
        executed_operation_count=executed,
        replayed_operation_count=int(_provider_value(summary, "replayed_operation_count", 0)),
        credits=_provider_value(summary, "credits", None),
        credit_semantics=str(_provider_value(summary, "credit_semantics", "NOT_RECORDED")),
        resume_source_run_id=str(resume_source) if resume_source is not None else None,
    )


class OperatorWorkflowBuilderV0_1:
    """Build an operator triage snapshot without creating new intelligence."""

    def build(self, request: OperatorWorkflowRequest) -> OperatorWorkflowSnapshotV0_1:
        if not isinstance(request, OperatorWorkflowRequest):
            raise TypeError("build requires OperatorWorkflowRequest")
        report = request.report.validate()
        report_refs = tuple(item.reference_id for item in report.provenance)
        supporting: list[OperatorClaim] = []
        missing: list[OperatorClaim] = []
        next_actions: list[OperatorNextAction] = []

        buyer_themes = tuple(
            _claim(
                label=item.need_label,
                value={"share": item.share, "share_basis": item.share_basis},
                status=item.availability.value,
                reason=(
                    f"Buyer Need theme has {item.evidence_count} governed evidence reference(s)."
                ),
                evidence_ids=item.evidence_ids,
                provenance_reference_ids=item.provenance_reference_ids,
            )
            for item in report.buyer_needs.needs[:3]
        )
        supporting.extend(buyer_themes)
        for item in report.buyer_needs.needs:
            if item.availability is not ReportAvailability.AVAILABLE or item.limitations:
                next_actions.append(
                    _next_action(
                        priority=3,
                        action=f"Validate buyer-need theme '{item.need_label}' with review or bullet evidence.",
                        reason=(
                            f"Theme status is {item.availability.value}; its limitations require "
                            "human evidence review before using it as a product requirement."
                        ),
                        trigger_status=item.availability.value,
                        evidence_ids=item.evidence_ids,
                        provenance_reference_ids=item.provenance_reference_ids,
                    )
                )

        competition_claims: list[OperatorClaim] = []
        for metric in _competition_metrics(report):
            item = _claim(
                label=_metric_label(metric.metric_name),
                value=metric.value,
                status=metric.availability.value,
                reason=(
                    "Metric copied from validated Competition output; unavailable values remain null."
                ),
                evidence_ids=metric.evidence_ids,
                provenance_reference_ids=metric.provenance_reference_ids,
            )
            competition_claims.append(item)
            if metric.availability is ReportAvailability.AVAILABLE:
                supporting.append(item)
            else:
                missing.append(item)
                next_actions.append(
                    _next_action(
                        priority=1,
                        action=f"Collect evidence required for competition metric '{_metric_label(metric.metric_name)}'.",
                        reason=(
                            f"The validated Competition metric is {metric.availability.value}; "
                            "it must not be interpreted as numeric zero."
                        ),
                        trigger_status=metric.availability.value,
                        provenance_reference_ids=metric.provenance_reference_ids,
                    )
                )

        opportunity = report.opportunity_score
        opportunity_claims = [
            _claim(
                label="Opportunity Score",
                value=opportunity.score_value,
                status=opportunity.score_status,
                reason="Value and status are copied from the governed Opportunity scoring output.",
                evidence_ids=opportunity.evidence_ids,
                provenance_reference_ids=opportunity.provenance_reference_ids,
            )
        ]
        for dimension in opportunity.dimensions:
            opportunity_claims.append(
                _claim(
                    label=f"Opportunity Dimension: {_metric_label(dimension.dimension)}",
                    value={
                        "score_value": dimension.score_value,
                        "contribution": dimension.contribution,
                        "max_contribution": dimension.max_contribution,
                    },
                    status=dimension.status,
                    reason=dimension.explanation,
                    evidence_ids=dimension.evidence_ids,
                    provenance_reference_ids=dimension.provenance_reference_ids,
                )
            )
            if dimension.status == "UNKNOWN":
                next_actions.append(
                    _next_action(
                        priority=2,
                        action=(
                            f"Collect the demand/economic/competition inputs required by "
                            f"opportunity dimension '{_metric_label(dimension.dimension)}'."
                        ),
                        reason=(
                            "This governed dimension is UNKNOWN with null score and contribution."
                        ),
                        trigger_status="UNKNOWN",
                        evidence_ids=dimension.evidence_ids,
                        provenance_reference_ids=dimension.provenance_reference_ids,
                    )
                )
        if opportunity.score_status == "PENDING_DATA" or opportunity.score_value is None:
            missing.extend(opportunity_claims)
        else:
            supporting.extend(opportunity_claims)

        incomplete_attributes = sorted(
            (
                attribute
                for attribute in report.product_attributes
                if attribute.availability is not ReportAvailability.AVAILABLE
                or attribute.unknown_count
            ),
            key=lambda item: (-item.unknown_rate, item.dimension),
        )
        for attribute in incomplete_attributes[:3]:
            next_actions.append(
                _next_action(
                    priority=2,
                    action=(
                        f"Inspect product attribute segment '{attribute.dimension}' "
                        "and resolve unknown values."
                    ),
                    reason=(
                        f"Attribute coverage is {attribute.attribute_coverage:.1%} with "
                        f"{attribute.unknown_count} unknown product value(s)."
                    ),
                    trigger_status=attribute.availability.value,
                    evidence_ids=attribute.evidence_ids,
                    provenance_reference_ids=attribute.provenance_reference_ids,
                )
            )

        if report.data_window.availability is not ReportAvailability.AVAILABLE:
            window_claim = _claim(
                label="Data Window",
                value={
                    "period": report.data_window.period,
                    "start_at": report.data_window.start_at,
                    "end_at": report.data_window.end_at,
                },
                status=report.data_window.availability.value,
                reason="A comparable observation window is required before time-based conclusions.",
                provenance_reference_ids=report.data_window.provenance_reference_ids,
            )
            missing.append(window_claim)
            next_actions.append(
                _next_action(
                    priority=2,
                    action="Collect a comparable dated demand and competition observation window.",
                    reason="The current data window is not fully available.",
                    trigger_status=report.data_window.availability.value,
                    provenance_reference_ids=report.data_window.provenance_reference_ids,
                )
            )

        limitation_values = sorted(
            {
                *report.limitations,
                *report.sample.limitations,
                *report.data_window.limitations,
                *report.buyer_needs.limitations,
                *report.competition.limitations,
                *report.opportunity_score.limitations,
                *report.opportunity_score.risks,
            }
        )
        risks = tuple(
            _claim(
                label="Risk / Limitation",
                value=value,
                status="REVIEW_REQUIRED",
                reason="Limitation copied from validated report evidence.",
                provenance_reference_ids=report_refs,
            )
            for value in limitation_values
        )

        if missing:
            action = OperatorActionType.COLLECT_EVIDENCE
            recommendation_type = "EVIDENCE_COLLECTION_RECOMMENDED"
            recommendation_applicability = "INSUFFICIENT_EVIDENCE"
            readiness = "INCOMPLETE"
            reason = (
                "Material Competition, Opportunity, or time-window evidence is missing. "
                "Collect the named inputs before advancing product validation; missing evidence is not zero."
            )
        else:
            action = OperatorActionType.FURTHER_REVIEW
            recommendation_type = "FURTHER_REVIEW_RECOMMENDED"
            recommendation_applicability = "UNAVAILABLE_ADAPTER_GAP"
            readiness = "REVIEW_REQUIRED"
            reason = (
                "The validated report is complete enough for review, but the full governed Decision/"
                "Recommendation input chain is not available in Production Pipeline. Human review is required."
            )

        framework = {
            "decision_framework_ruleset_version": DECISION_FRAMEWORK_RULESET_VERSION,
            "decision_framework_execution_status": "UNAVAILABLE_ADAPTER_GAP",
            "recommendation_framework_ruleset_version": RECOMMENDATION_FRAMEWORK_RULESET_VERSION,
            "recommendation_framework_execution_status": "GOVERNED_SEMANTIC_MAPPING_ONLY",
            "recommendation_applicability": recommendation_applicability,
            "recommendation_type": recommendation_type,
            "operator_output_ruleset_version": OPERATOR_OUTPUT_RULESET_VERSION,
            "operator_output_execution_status": "UNAVAILABLE_ADAPTER_GAP",
            "operator_workbook_ruleset_version": OPERATOR_WORKBOOK_RULESET_VERSION,
            "operator_workbook_execution_status": "DESIGN_AND_STYLE_REUSED",
            "adapter_gap": _ADAPTER_GAP,
        }
        lineages = {
            *report_refs,
            *(value for item in supporting for value in (*item.evidence_ids, *item.provenance_reference_ids)),
            *(value for item in missing for value in (*item.evidence_ids, *item.provenance_reference_ids)),
            *(value for item in next_actions for value in (*item.evidence_ids, *item.provenance_reference_ids)),
        }
        run_health = _run_health(request)
        supporting_tuple = tuple(sorted(supporting, key=lambda item: item.claim_id))
        missing_tuple = tuple(sorted(missing, key=lambda item: item.claim_id))
        buyer_tuple = tuple(sorted(buyer_themes, key=lambda item: item.claim_id))
        competition_tuple = tuple(sorted(competition_claims, key=lambda item: item.claim_id))
        opportunity_tuple = tuple(sorted(opportunity_claims, key=lambda item: item.claim_id))
        risks_tuple = tuple(sorted(risks, key=lambda item: item.claim_id))
        actions_tuple = tuple(
            sorted(
                {item.action_id: item for item in next_actions}.values(),
                key=lambda item: (item.priority, item.action_id),
            )
        )
        content = {
            "semantic_fingerprint": "pending",
            "ruleset_version": OPERATOR_WORKFLOW_RULESET_VERSION,
            "run_id": request.run_id,
            "market_report_id": report.report_id,
            "market_report_version": report.report_version,
            "operator_action": action,
            "recommendation_type": recommendation_type,
            "action_reason": reason,
            "evidence_readiness": readiness,
            "framework_integration": framework,
            "supporting_evidence": supporting_tuple,
            "missing_evidence": missing_tuple,
            "top_buyer_need_themes": buyer_tuple,
            "competition_summary": competition_tuple,
            "opportunity_summary": opportunity_tuple,
            "risks_and_limitations": risks_tuple,
            "next_actions": actions_tuple,
            "run_health": run_health,
            "lineage_reference_ids": tuple(sorted(lineages)),
        }
        semantic = {
            key: value
            for key, value in content.items()
            if key not in {"semantic_fingerprint", "run_id", "run_health"}
        }
        content["semantic_fingerprint"] = deterministic_id(
            "operator-workflow-semantic", semantic
        )
        snapshot_content = dict(content)
        return OperatorWorkflowSnapshotV0_1(
            snapshot_id=deterministic_id("operator-workflow-snapshot", snapshot_content),
            **content,
        )


def build_standalone_operator_workflow(
    report: MarketReportSnapshot,
) -> OperatorWorkflowSnapshotV0_1:
    """Build a report-only workflow when runtime metadata is unavailable."""

    return OperatorWorkflowBuilderV0_1().build(
        OperatorWorkflowRequest(
            report=report,
            run_id=f"standalone:{report.report_id}",
            run_status="NOT_RECORDED",
        )
    )


__all__ = (
    "OperatorWorkflowBuilderV0_1",
    "build_standalone_operator_workflow",
)
