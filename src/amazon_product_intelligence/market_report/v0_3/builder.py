"""Business interpretation downstream of the unchanged, released Route result."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json

from amazon_product_intelligence.contracts import canonical_json

from .config import ReportProfile
from .metrics import aggregate, project_record, ratio, total
from .qualification import ReportEvidenceContext, qualify_records, restrict_aggregate

VERSION = "operator-market-report-v0.3"


@dataclass(frozen=True)
class OperatorMarketReport:
    """Canonical serialized storage prevents silent post-fingerprint mutation."""
    canonical_payload: str

    def __post_init__(self):
        data = json.loads(self.canonical_payload)
        if data.get("contract_version") != VERSION:
            raise ValueError("unsupported report contract")
        expected = data.pop("semantic_fingerprint", None)
        if expected != sha256(canonical_json(data).encode()).hexdigest():
            raise ValueError("report fingerprint mismatch")
        if any(r["human_verdict"] is not None or r["notes"] is not None for r in data["business_value_review"]):
            raise ValueError("human verdicts must be blank")
        if [r["question_id"] for r in data["business_value_review"]] != list(range(1, 12)):
            raise ValueError("eleven governed business questions required")
        counts = data["coverage_counts"]
        qualification = data.get("evidence_qualification")
        if qualification:
            eligible = qualification["time_qualified"] and qualification["sampling_scope_qualified"] and qualification["allocation_qualified"]
            if any(qualification[key] is not eligible for key in ("strong_research_allowed", "trend_allowed", "new_product_allowed")):
                raise ValueError("inconsistent evidence qualification flags")
            if qualification["allocation_qualified"] and (qualification["parent_metric_listing_count"] or qualification["scope_unconfirmed_listing_count"]):
                raise ValueError("unqualified measurement allocation")
            groups = [data["market"], data["assigned_market"], *data["routes"], *data["families"], *data["mechanism_groups"]]
            if not qualification["trend_allowed"] and any(group[key]["value"] is not None for group in groups for key in ("mom", "yoy")):
                raise ValueError("unqualified evidence cannot publish trends")
            if not qualification["new_product_allowed"] and any(item["products"] is not None for group in groups for item in group["new_products"]):
                raise ValueError("unqualified evidence cannot publish new-entrant counts")
            if not qualification["allocation_qualified"] and any(group["sales"]["value"] is not None for group in groups[1:]):
                raise ValueError("parent estimates cannot publish child-group sales")
        if qualification and not qualification["strong_research_allowed"]:
            if data["decision_readiness"]["strong_route_research_allowed"] or any(e["classification"] in {"PRIORITY_RESEARCH", "LOW_PRIORITY"} for e in data["opportunity_explanations"]):
                raise ValueError("unqualified evidence cannot authorize research directions")
        if counts["accepted"] != counts["assigned"] + counts["unclassified"] + counts["review_required"]:
            raise ValueError("coverage counts do not reconcile")
        routes = data["routes"]
        by_id = {r["route_id"]: r for r in routes}
        if len(by_id) != len(routes) or sum(r["products"] for r in routes) != counts["assigned"]:
            raise ValueError("route counts do not reconcile")
        child_ids = [r for f in data["families"] for r in f["route_ids"]]
        if len(child_ids) != len(set(child_ids)) or set(child_ids) != set(by_id):
            raise ValueError("families must partition the released Routes")
        for family in data["families"]:
            if family["products"] != sum(by_id[i]["products"] for i in family["route_ids"]):
                raise ValueError("family counts do not reconcile")
        mechanism_children = [r for g in data["mechanism_groups"] for r in g["route_ids"]]
        if sorted(mechanism_children) != sorted(by_id):
            raise ValueError("mechanism rollups must partition the same released Routes")
        for group in data["mechanism_groups"]:
            if group["products"] != sum(by_id[i]["products"] for i in group["route_ids"]):
                raise ValueError("mechanism rollup counts do not reconcile")
        for route in routes:
            for key in ("price_bands", "review_bands"):
                if sum(x["products"] for x in route[key]) != route["products"]:
                    raise ValueError("band counts do not reconcile")
        for explanation in data["opportunity_explanations"]:
            for fact in explanation["facts"]:
                if resolve(data, fact["path"]) != fact["value"]:
                    raise ValueError("explanation is not bound to report data")

    def to_dict(self):
        return json.loads(self.canonical_payload)

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    @property
    def semantic_fingerprint(self):
        return self.to_dict()["semantic_fingerprint"]


def resolve(data, path):
    for key in path.strip("/").split("/"):
        data = data[int(key)] if isinstance(data, list) else data[key]
    return data


def hierarchy(features, profile):
    tokens = {f["dimension"]: tuple(f["values"]) for f in features}
    family = None
    rule_used = None
    for i, rule in enumerate(profile.family_rules):
        if rule["value"] in tokens.get(rule["dimension"], ()):
            family, rule_used = rule["family"], i
            break
    if family is None:
        # A generic display grouping by the entire value tuple never splits a
        # compound observation or promotes a marketing descriptor into truth.
        dimension = next((d for d in ("installation_architecture", "product_form", "operation_mechanism") if tokens.get(d)), None)
        family = "other_structure" if dimension is None else dimension + ":" + "|".join(tokens[dimension])
    wall = "wall_mount" in tokens.get("installation_architecture", ())
    mechanisms = tokens.get("attachment_mechanism", ())
    specific = tuple(v for v in mechanisms if v not in {"wall", "wall_mount", "unspecified", "unknown"})
    fallback = wall and not specific
    return {"family_id": family, "mechanism_values": list(specific), "specificity": "EVIDENCE_LIMITED_FALLBACK" if fallback else "DEFINED_BY_GOVERNED_FEATURES", "fallback_label": "wall_mount_unspecified" if fallback else None, "profile_rule_index": rule_used, "compound_observation": any("," in v or "|" in v for f in features for v in f["values"])}


def _readiness(counts, assigned, market, profile, qualification=None):
    coverage = ratio(counts["assigned"], counts["accepted"]) or 0.0
    unresolved = ratio(counts["unclassified"] + counts["review_required"], counts["accepted"]) or 0.0
    sales_coverage = assigned["sales"]["coverage"]
    reasons = ["BUYER_NEED_DATA_MISSING"]
    if coverage < profile.minimum_route_coverage:
        reasons.append("LIMITED_ROUTE_COVERAGE")
    if sales_coverage < profile.minimum_sales_coverage or not assigned["sales"]["value"]:
        reasons.append("INSUFFICIENT_DEMAND_DATA")
    if unresolved > profile.high_unresolved_exposure:
        reasons.append("HIGH_UNRESOLVED_EXPOSURE")
    ready = not any(r in reasons for r in ("LIMITED_ROUTE_COVERAGE", "INSUFFICIENT_DEMAND_DATA", "HIGH_UNRESOLVED_EXPOSURE"))
    if qualification is not None:
        reasons.extend(qualification["reason_codes"])
        ready = ready and qualification["strong_research_allowed"]
    return {"technical_report_status": "GENERATED_VALIDATED", "business_decision_readiness": "READY_FOR_ROUTE_COMPARISON" if ready else "LIMITED_ROUTE_COMPARISON", "codes": reasons, "assigned_coverage": coverage, "unresolved_exposure": unresolved, "assigned_sales_observation_coverage": sales_coverage, "assigned_observed_sales_share_of_market": ratio(assigned["sales"]["value"], market["sales"]["value"]), "whole_category_recommendation_allowed": False, "strong_route_research_allowed": ready, "launch_decision_ready": False, "threshold_scope": "REPORT_WARNING_POLICY_ONLY_NOT_RELEASE_GATES"}


def _explanations(data):
    routes = data["routes"]
    sales = [r["sales_share"]["value"] for r in routes if r["sales_share"]["value"] is not None]
    largest = max(sales) if sales else None
    result = []
    for i, route in enumerate(routes):
        facts = []
        def add(code, key, role="context"):
            path = f"/routes/{i}/{key}"
            facts.append({"code": code, "path": path, "value": resolve(data, path), "role": role})
        add("ROUTE_SALES", "sales/value")
        add("ROUTE_SALES_SHARE", "sales_share/value")
        add("MEDIAN_PRICE", "median_price/value")
        add("MEDIAN_REVIEWS", "median_reviews/value")
        if largest is not None and route["sales_share"]["value"] == largest:
            add("LARGEST_SALES_SHARE", "sales_share/value", "support")
        for key in ("mom", "yoy"):
            val = route[key]["value"]
            if val is not None:
                supported = route[key]["coverage"] >= data["report_profile"]["minimum_sales_coverage"]
                add("POSITIVE_" + key.upper() if val > 0 else "NONPOSITIVE_" + key.upper(), key + "/value", "support" if val > 0 and supported else "concern" if val <= 0 else "context")
                add("GROWTH_COVERAGE_" + key.upper(), key + "/coverage")
        eff = route["demand_efficiency"]["value"]
        if eff is not None:
            add("DEMAND_ABOVE_PAR" if eff > 1 else "DEMAND_AT_OR_BELOW_PAR", "demand_efficiency/value", "support" if eff > 1 else "concern")
        add("LOW_REVIEW_DEMAND_SHARE", "low_review/sales_share/value")
        add("LOW_REVIEW_SELLING_PRODUCTS", "low_review/selling_products")
        add("BRAND_TOP1", "brands/sales_concentration/top_1")
        add("SELLER_TOP1", "sellers/sales_concentration/top_1")
        add("BRAND_IDENTITY_COVERAGE", "brands/identity_coverage")
        add("SELLER_IDENTITY_COVERAGE", "sellers/identity_coverage")
        new = route["new_products"][0]["demand_efficiency"]["value"]
        add("NEW_PRODUCT_EFFICIENCY", "new_products/0/demand_efficiency/value", "support" if new is not None and new > 1 else "concern")
        add("AGE_COVERAGE", "evidence_coverage/age")
        if route["hierarchy"]["specificity"] == "EVIDENCE_LIMITED_FALLBACK":
            add("UNSPECIFIED_MOUNT", "hierarchy/specificity", "concern")
        if route["hierarchy"]["compound_observation"]:
            add("COMPOUND_DEFINITION", "hierarchy/compound_observation", "concern")
        readiness = data["decision_readiness"]
        facts.append({"code": "CATEGORY_ROUTE_COVERAGE", "path": "/decision_readiness/assigned_coverage", "value": readiness["assigned_coverage"], "role": "concern"})
        classification = "WATCH"
        if not data.get("evidence_qualification", {"strong_research_allowed": True})["strong_research_allowed"]:
            classification = "EVIDENCE_QUALIFICATION_REQUIRED"
        elif eff is None or route["sales"]["coverage"] < data["report_profile"]["minimum_sales_coverage"]:
            classification = "INSUFFICIENT_EVIDENCE"
        elif not readiness["strong_route_research_allowed"]:
            classification = "LIMITED_COVERAGE_OBSERVATION"
        elif any(route[key].get("raw_value") is not None and not route[key].get("interpretation_allowed", True) for key in ("mom", "yoy")):
            classification = "GROWTH_QUALIFICATION_REQUIRED"
        elif eff > 1 and any(f["role"] == "support" and f["code"] in {"LARGEST_SALES_SHARE", "POSITIVE_MOM", "POSITIVE_YOY"} for f in facts):
            classification = "PRIORITY_RESEARCH"
        elif eff < 1 and not (new is not None and new > 1) and not any(f["code"] in {"POSITIVE_MOM", "POSITIVE_YOY"} for f in facts):
            classification = "LOW_PRIORITY"
        result.append({"route_id": route["route_id"], "route_number": route["route_number"], "classification": classification, "policy_id": "descriptive-research-triage-v0.3", "facts": facts, "reason_codes": [f["code"] for f in facts], "conclusion_code": classification, "limitations": ["NOT_A_LAUNCH_RECOMMENDATION", "BUYER_NEED_DATA_MISSING", "MARGIN_DATA_UNAVAILABLE", "UNASSIGNED_MEMBERSHIP_NOT_INFERRED"]})
    return result


def _summary(data):
    summaries = []
    def record(question, paths, entity=None):
        summaries.append({"question": question, "entity": entity, "facts": [{"path": p, "value": resolve(data, p)} for p in paths]})
    record("MARKET_SIZE", ["/coverage_counts/accepted", "/market/sales/value", "/market/revenue/value", "/market/sales/coverage"])
    record("ROUTE_COVERAGE", ["/coverage_counts/assigned", "/decision_readiness/assigned_coverage", "/decision_readiness/assigned_observed_sales_share_of_market"])
    for question, collection, key, choose in (
        ("LARGEST_ROUTE", "routes", "sales_share/value", max),
        ("LARGEST_FAMILY", "families", "sales_share/value", max),
        ("LOWEST_REVIEW_MEDIAN", "routes", "median_reviews/value", min),
        ("STRONGEST_LOW_REVIEW_DEMAND", "routes", "low_review/sales_share/value", max),
        ("STRONGEST_INCUMBENT", "routes", "brands/sales_concentration/top_1", max),
    ):
        available = [(i, r) for i, r in enumerate(data[collection]) if resolve(r, key) is not None]
        if available:
            i, r = choose(available, key=lambda t: (resolve(t[1], key), t[1].get("route_id", t[1].get("family_id"))))
            paths = [f"/{collection}/{i}/{key}", f"/{collection}/{i}/products", f"/{collection}/{i}/sales/value"]
            if question == "STRONGEST_INCUMBENT":
                paths.extend([f"/{collection}/{i}/brands/identity_coverage", f"/{collection}/{i}/brands/sales_coverage/coverage"])
            record(question, paths, r.get("route_number", r.get("family_id")))
        else:
            record(question, [])
    for period in ("yoy", "mom"):
        eligible = [(i, r) for i, r in enumerate(data["routes"]) if r[period]["value"] is not None and r[period].get("interpretation_allowed", True) and r[period]["coverage"] >= data["report_profile"]["minimum_sales_coverage"]]
        if eligible:
            i, r = max(eligible, key=lambda t: (t[1][period]["value"], t[1]["route_id"]))
            record("STRONGEST_" + period.upper(), [f"/routes/{i}/{period}/value", f"/routes/{i}/{period}/coverage", f"/routes/{i}/sales/value"], r["route_number"])
        else:
            record("STRONGEST_" + period.upper(), [])
    for cls, question in (("PRIORITY_RESEARCH", "RESEARCH_DIRECTION"), ("LOW_PRIORITY", "LOW_PRIORITY_DIRECTION")):
        found = [(i, r) for i, r in enumerate(data["routes"]) if data["opportunity_explanations"][i]["classification"] == cls]
        if found:
            i, r = max(found, key=lambda t: (t[1]["sales_share"]["value"] or 0, t[1]["route_id"]))
            record(question, [f"/routes/{i}/sales_share/value", f"/routes/{i}/demand_efficiency/value", f"/opportunity_explanations/{i}/classification"], r["route_number"])
        else:
            record(question, ["/decision_readiness/strong_route_research_allowed"])
    record("KEY_UNCERTAINTY", ["/coverage_counts/unclassified", "/coverage_counts/review_required", "/buyer_needs/availability"])
    record("DECISION_READY", ["/decision_readiness/business_decision_readiness", "/decision_readiness/launch_decision_ready"])
    return summaries


def build_operator_market_report(integrated, *, profile=None, evidence_context=None):
    profile = profile or ReportProfile()
    dataset = integrated.route_input.dataset
    if profile.category is not None and profile.category != dataset.category:
        raise ValueError("report profile category mismatch")
    base = integrated.market_report.to_dict()
    lineage = base["source_lineage"]
    bundles = getattr(integrated, "canonical_bundles", ())
    if bundles:
        from amazon_product_intelligence.competition_intelligence.models import bundle_fingerprint
        if sorted(bundle_fingerprint(b) for b in bundles) != sorted(lineage["canonical_bundle_fingerprints"]):
            raise ValueError("qualification Canonical source binding mismatch")
    for actual, expected in ((dataset.dataset_id, lineage["governed_dataset_id"]), (integrated.route_result.result_id, lineage["route_result_id"]), (integrated.semantic_result.result_id, lineage["semantic_result_id"]), (dataset.semantic_fingerprint, lineage["governed_dataset_fingerprint"]), (integrated.route_result.semantic_fingerprint, lineage["route_result_fingerprint"]), (integrated.semantic_result.semantic_fingerprint, lineage["semantic_result_fingerprint"])):
        if actual != expected:
            raise ValueError("integrated report upstream binding mismatch")
    records = {r.asin: project_record(r, observed_date=dataset.observed_date) for r in dataset.records}
    qualification = qualify_records(integrated, records, evidence_context or ReportEvidenceContext())
    def stats(rows, population, *, sample_total=False):
        return restrict_aggregate(aggregate(rows, population, profile), qualification, sample_total=sample_total)
    assigned_refs = [m.listing_reference for m in integrated.route_result.memberships if m.status.value == "ASSIGNED"]
    released = sorted(integrated.route_result.routes, key=lambda r: (-r.member_count, r.route_id))
    route_refs = [ref for r in released for ref in r.member_listing_references]
    if len(set(route_refs)) != len(route_refs) or sorted(route_refs) != sorted(assigned_refs):
        raise ValueError("released route membership must be a disjoint assigned partition")
    assigned = [records[x] for x in sorted(assigned_refs)]
    all_rows = list(records.values())
    family_records, family_routes = defaultdict(list), defaultdict(list)
    mechanism_records, mechanism_routes = defaultdict(list), defaultdict(list)
    routes = []
    candidates = {r.route_id: r.to_dict() for r in integrated.route_result.candidates}
    for i, route in enumerate(released):
        features = [{"dimension": f.dimension, "values": list(f.values)} for f in route.defining_features]
        h = hierarchy(features, profile)
        members = [records[x] for x in route.member_listing_references]
        routes.append({"route_number": f"R{i+1:02d}", "route_id": route.route_id, "features": features, "hierarchy": h, "released_candidate": candidates.get(route.route_id), "released_candidate_usage": "AUDIT_ONLY_NOT_QUALIFIED_REPORT_ADVICE", **stats(members, assigned)})
        family_records[h["family_id"]].extend(members)
        family_routes[h["family_id"]].append(route.route_id)
        mechanism = "|".join(h["mechanism_values"]) or h["fallback_label"] or "no_specific_mechanism"
        mechanism_records[(h["family_id"], mechanism)].extend(members)
        mechanism_routes[(h["family_id"], mechanism)].append(route.route_id)
    families = [{"family_id": key, "route_ids": sorted(family_routes[key]), **stats(rows, assigned)} for key, rows in sorted(family_records.items())]
    families.sort(key=lambda f: (-(f["sales"]["value"] or 0), f["family_id"]))
    mechanism_groups = [{"family_id": key[0], "mechanism_id": key[1], "route_ids": sorted(mechanism_routes[key]), **stats(members, family_records[key[0]])} for key, members in sorted(mechanism_records.items())]
    data = {
        "contract_version": VERSION, "generated_at": base["generated_at"], "category": base["category"], "marketplace": base["marketplace"],
        "source_lineage": {**lineage, "v0_2_report_fingerprint": integrated.market_report.semantic_fingerprint, "report_profile_fingerprint": profile.fingerprint},
        "report_profile": profile.to_dict(), "coverage_counts": base["market_overview"]["coverage_counts"],
        "evidence_qualification": qualification,
        "market": stats(all_rows, all_rows, sample_total=True), "assigned_market": stats(assigned, assigned),
        "routes": routes, "families": families, "mechanism_groups": mechanism_groups,
        "buyer_needs": {"availability": "UNAVAILABLE", "themes": [], "route_links": [], "reason": "NO_GOVERNED_REVIEW_OR_SEARCH_EVIDENCE"},
        "upstream_intelligence": {"usage": "AUDIT_ONLY_NOT_QUALIFIED_REPORT_ADVICE", "competition": base["competition"], "opportunity": base["opportunity"]},
        "business_value_review": [{"question_id": i, "human_verdict": None, "notes": None} for i in range(1, 12)],
        "limitations": ["OBSERVED_EXPORT_NOT_TOTAL_ADDRESSABLE_MARKET", "THIRD_PARTY_ESTIMATES", "MISSING_NOT_ZERO", "ASSIGNED_SUBSET_ONLY", "UNASSIGNED_MEMBERSHIP_NOT_INFERRED", "BUYER_NEED_DATA_MISSING", "MARGIN_DATA_UNAVAILABLE", "NO_GOVERNED_SUCCESS_DEFINITION", "NOT_A_LAUNCH_RECOMMENDATION"],
    }
    data["decision_readiness"] = _readiness(data["coverage_counts"], data["assigned_market"], data["market"], profile, qualification)
    data["opportunity_explanations"] = _explanations(data)
    data["executive_summary"] = _summary(data)
    data["semantic_fingerprint"] = sha256(canonical_json(data).encode()).hexdigest()
    return OperatorMarketReport(canonical_json(data))
