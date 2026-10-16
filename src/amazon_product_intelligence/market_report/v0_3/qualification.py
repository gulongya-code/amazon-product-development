"""Report-owned evidence qualification; no collection or semantic classification."""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
import re

from .metrics import total


@dataclass(frozen=True)
class ReportEvidenceContext:
    research_query: str | None = None
    sampling_description: str | None = None
    period_start: str | None = None
    period_end: str | None = None

    def __post_init__(self):
        for key in ("research_query", "sampling_description"):
            value = getattr(self, key)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{key} must be nonblank or unknown")
        for key in ("period_start", "period_end"):
            value = getattr(self, key)
            if value is not None:
                date.fromisoformat(value)
        if bool(self.period_start) != bool(self.period_end):
            raise ValueError("both statistical window boundaries are required")
        if self.period_start and self.period_start > self.period_end:
            raise ValueError("statistical window is reversed")


METRICS = {"sales": "estimated_monthly_sales", "revenue": "estimated_monthly_revenue", "mom": "sales_mom_growth", "yoy": "sales_yoy_growth"}


def qualify_records(integrated, records, context):
    """Exclude unresolved repeated parent estimates without selecting a value.

    A parent estimate remains usable only as a sample-level parent estimate.
    It cannot establish the sales of the representative child's facets/Route.
    """
    # Scope is also useful for an unavailable value (e.g. a missing estimate in
    # a repeated parent group). Numeric eligibility still comes from project_record.
    accepted = {x.observation_id for x in integrated.route_input.field_lineage}
    scopes = defaultdict(list)
    for bundle in getattr(integrated, "canonical_bundles", ()):
        for observation in bundle.observations:
            name = getattr(observation, "metric", None)
            if observation.observation_id in accepted and name in METRICS.values():
                for key in ("period_start", "period_end"):
                    source_date = getattr(observation.time, key)
                    supplied_date = getattr(context, key)
                    if source_date and supplied_date and source_date[:10] != supplied_date:
                        raise ValueError("statistical window contradicts Canonical evidence")
                scopes[(observation.subject.subject_id, name)].append(observation.scope)
    parent_groups = defaultdict(list)
    unknown = set()
    parent_rows = set()
    listing_scope_present = False
    raw_sums = {key: total(list(records.values()), key)["value"] for key in ("sales", "revenue")}
    for ref, row in records.items():
        subject = f"product:{integrated.route_input.dataset.marketplace}:{ref}"
        row_scopes = {}
        for key, name in METRICS.items():
            values = scopes[(subject, name)]
            identities = {(s.scope_type.value, s.scope_status.value, s.scope_subject_id) for s in values}
            identity = next(iter(identities)) if len(identities) == 1 else None
            valid = identity is not None and identity[1] == "CONFIRMED" and identity[2] is not None
            if valid and identity[0] in {"ASIN", "CHILD_ASIN"}:
                valid = identity[2] == subject
            elif valid:
                valid = identity[0] == "PARENT_ASIN" and re.fullmatch(r"product:" + re.escape(integrated.route_input.dataset.marketplace) + r":[A-Z0-9]{10}", identity[2]) is not None
            if not valid:
                if row[key] is not None:
                    unknown.add(ref)
                row[key] = None
            else:
                row_scopes[key] = identity
        sales_scope = row_scopes.get("sales")
        if sales_scope is None:
            unknown.add(ref)
        # Growth/revenue may only accompany exactly the same measurement subject.
        for key in ("revenue", "mom", "yoy"):
            if row_scopes.get(key) != sales_scope:
                row[key] = None
        if sales_scope and sales_scope[0] == "PARENT_ASIN":
            parent_groups[sales_scope[2]].append(ref)
            parent_rows.add(ref)
        elif sales_scope:
            listing_scope_present = True
    duplicates = [refs for refs in parent_groups.values() if len(refs) > 1]
    duplicate_refs = {ref for refs in duplicates for ref in refs}
    excluded_sums = {key: total([records[ref] for ref in sorted(duplicate_refs)], key)["value"] for key in ("sales", "revenue")}
    for ref in duplicate_refs:
        for key in METRICS:
            records[ref][key] = None
    mixed_scope = bool(parent_rows) and listing_scope_present
    if mixed_scope:
        # A parent estimate and a child estimate may overlap. There is no safe
        # combined total without an explicit allocation/reconciliation contract.
        for row in records.values():
            for key in METRICS:
                row[key] = None
    dataset = integrated.route_input.dataset
    observed = dataset.observed_date
    generated_date = integrated.market_report.to_dict()["generated_at"][:10]
    time_known = bool(observed and context.period_start and context.period_end)
    if observed and observed > generated_date:
        raise ValueError("observation date is after report generation")
    if observed and context.period_end and context.period_end > observed:
        raise ValueError("statistical window ends after observation date")
    allocation = not parent_rows and not unknown and bool(scopes)
    scope_known = bool(context.research_query and context.sampling_description)
    reasons = []
    if not time_known:
        reasons.append("TIME_WINDOW_UNCONFIRMED")
    if not scope_known:
        reasons.append("SAMPLING_SCOPE_UNCONFIRMED")
    if parent_rows:
        reasons.append("PARENT_ESTIMATES_NOT_ALLOCATED_TO_CHILD_FACETS")
    if unknown or not scopes:
        reasons.append("METRIC_SCOPE_UNCONFIRMED")
    if duplicates:
        reasons.append("DUPLICATE_PARENT_ESTIMATES_WITHHELD")
    if mixed_scope:
        reasons.append("MIXED_METRIC_SCOPES_WITHHELD")
    return {
        "policy_version": "report-evidence-qualification-v1.0", **asdict(context),
        "observed_date": observed, "time_qualified": time_known,
        "sampling_scope_qualified": scope_known, "allocation_qualified": allocation,
        "trend_allowed": time_known and scope_known and allocation,
        "new_product_allowed": time_known and scope_known and allocation,
        "strong_research_allowed": time_known and scope_known and allocation,
        "metric_grain": "MIXED" if mixed_scope else "PARENT_ASIN" if parent_rows else "ASIN" if allocation else "UNCONFIRMED",
        "parent_metric_listing_count": len(parent_rows), "parent_group_count": len(parent_groups),
        "duplicate_parent_group_count": len(duplicates), "duplicate_parent_listing_count": len(duplicate_refs),
        "duplicate_parent_excluded_sums": excluded_sums, "scope_unconfirmed_listing_count": len(unknown),
        "raw_source_row_sums_audit_only": raw_sums, "reason_codes": reasons,
        "seller_attribution": "CURRENT_IDENTITY_LINKED_LISTINGS_NOT_ACTUAL_SELLER_SALES",
        "duplicate_policy": "WITHHOLD_ALL_REPEATED_PARENT_GROUPS_PENDING_SOURCE_RESOLUTION",
        "whole_market_generalization_allowed": False,
    }


def withhold(value, reason):
    if isinstance(value, dict) and "value" in value:
        value.setdefault("raw_value", value["value"])
        value.setdefault("source_coverage", value.get("coverage"))
        value.update(value=None, availability="UNAVAILABLE", interpretation_allowed=False)
        value["qualification_reasons"] = sorted({*value.get("qualification_reasons", []), reason})


def restrict_aggregate(data, qualification, *, sample_total=False):
    """Restrict derived uses while preserving unqualified calculations for audit."""
    if not qualification["allocation_qualified"]:
        reason = "PARENT_OR_UNKNOWN_SCOPE_NOT_ALLOCATABLE"
        keys = ("sales_share", "revenue_share", "demand_efficiency") if sample_total else ("sales", "sales_share", "revenue", "revenue_share", "demand_efficiency", "mom", "yoy")
        for key in keys:
            withhold(data[key], reason)
        for band in (*data["price_bands"], *data["review_bands"]):
            for key in ("sales", "sales_share", "demand_efficiency"):
                withhold(band[key], reason)
        low = data["low_review"]
        low["selling_products"] = None
        for key in ("sales", "sales_share", "demand_efficiency", "median_sales"):
            withhold(low[key], reason)
        for key in ("brands", "sellers"):
            competition = data[key]
            withhold(competition["sales_coverage"], reason)
            competition["ranking_basis"] = "LISTING_COUNT_DESC_THEN_NAME_NO_SALES_ATTRIBUTION"
            competition["sales_concentration"] = {k: None for k in competition["sales_concentration"]}
            # No sales ranking is retained when its attribution is unqualified.
            competition["top_entities"] = sorted(competition["all_entities"], key=lambda x: (-x["products"], x["name"].casefold(), x["name"]))[:competition["top_n"]]
            for entity in competition["top_entities"]:
                for field in ("sales", "sales_share"):
                    withhold(entity[field], reason)
    for key in ("mom", "yoy"):
        if not qualification["trend_allowed"]:
            withhold(data[key], "TIME_OR_SCOPE_NOT_QUALIFIED")
    for item in data["new_products"]:
        if not qualification["new_product_allowed"]:
            item["raw_products_audit_only"] = item["products"]
            item["products"] = None
            item["listing_share_known_age"] = None
            for key in ("sales", "sales_share_route", "sales_share_known_age", "median_sales", "median_reviews", "demand_efficiency"):
                withhold(item[key], "NEW_PRODUCT_TIME_OR_SCOPE_NOT_QUALIFIED")
    # Internal complete entity sets must not become a second exposed ranking.
    for key in ("brands", "sellers"):
        data[key].pop("all_entities", None)
        data[key].pop("top_n", None)
    return data
