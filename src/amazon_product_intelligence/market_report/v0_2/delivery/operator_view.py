"""Pure operator-facing projection of one validated V0.2 snapshot."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from ..models import MarketReportSnapshotV0_2


OPERATOR_VIEW_VERSION = "operator-market-report-v0.2-view-v1"


def _state(value: Any, availability: str) -> Any:
    return availability if value is None else value


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorReportViewV0_2:
    view_version: str
    report_id: str
    report_version: str
    payload: Mapping[str, Any]
    parity: Mapping[str, Any]


def compose_operator_view(report: MarketReportSnapshotV0_2) -> OperatorReportViewV0_2:
    """Project only validated fields; no analytical calculation is performed."""

    report.validate()
    payload = report.to_dict()
    market = payload["market_size"]
    competitors = payload["true_competitor_set"]
    directions = payload["product_directions"]
    shortlist = payload["competitor_shortlist"]
    opportunity = payload["opportunity_score"]
    score = opportunity["source_section"]
    parity = {
        "report_id": payload["metadata"]["report_id"],
        "report_version": payload["metadata"]["report_version"],
        "category_name": payload["category"]["category_name"],
        "marketplace": payload["category"]["marketplace"],
        "scope_product_grain": payload["scope_context"]["product_grain"],
        "sample_size": payload["sample"]["sample_size"],
        "market_availability": market["availability"],
        "monthly_sales": _state(market["monthly_sales"]["value"], market["monthly_sales"]["availability"]),
        "monthly_revenue": _state(market["monthly_revenue"]["value"], market["monthly_revenue"]["availability"]),
        "true_competitor_availability": competitors["availability"],
        "true_competitor_included_count": competitors["included_count"],
        "true_competitor_review_required_count": competitors["review_required_count"],
        "buyer_need_availability": payload["buyer_needs"]["availability"],
        "product_direction_availability": directions["availability"],
        "product_direction_semantics": "HYPOTHESIS",
        "competitor_shortlist_availability": shortlist["availability"],
        "competitor_shortlist_semantics": "REVIEW_ORDER_NOT_RANK",
        "opportunity_availability": opportunity["availability"],
        "opportunity_status": score["score_status"],
        "opportunity_score": _state(score["score_value"], score["score_status"]),
        "keyword_intelligence_state": payload["external_integrations"]["state"],
    }
    return OperatorReportViewV0_2(
        view_version=OPERATOR_VIEW_VERSION,
        report_id=payload["metadata"]["report_id"],
        report_version=payload["metadata"]["report_version"],
        payload=MappingProxyType(payload),
        parity=MappingProxyType(parity),
    )


__all__ = ("OPERATOR_VIEW_VERSION", "OperatorReportViewV0_2", "compose_operator_view")
