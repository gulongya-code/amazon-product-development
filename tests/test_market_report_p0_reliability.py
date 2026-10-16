"""Behavioral regression cases for the three authorized P0 defects."""
from dataclasses import replace
from decimal import Decimal as D
import json

import pytest

from amazon_product_intelligence.contracts import Scope, ScopeType, ScopeStatus
from amazon_product_intelligence.market_report.integrated import run_final_market_intelligence
from amazon_product_intelligence.market_report.v0_3 import ReportEvidenceContext, build_operator_market_report
from amazon_product_intelligence.market_report.v0_3.metrics import growth
from amazon_product_intelligence.market_report.v0_3.presentation import markdown, workbook_spec
from tests.test_sp_043a_final_market_intelligence_integration import _canonical_bundles, _run
from tests.test_sp_043b_operator_market_report_v03 import row


COMPLETE = ReportEvidenceContext(research_query="fixture", sampling_description="complete synthetic sample", period_start="2026-07-28", period_end="2026-08-26")


@pytest.fixture(scope="module")
def integrated():
    return _run()


def parent_evidence(integrated, *, missing_parent=False, identical=False, mixed=False):
    original = _canonical_bundles()[0]
    observations = []
    for observation in original.observations:
        if getattr(observation, "metric", None) in {"estimated_monthly_sales", "estimated_monthly_revenue", "sales_mom_growth", "sales_yoy_growth"} and not (mixed and observation.subject.subject_id.endswith("009")):
            ref = observation.subject.subject_id
            parent = "product:US:B0PAREN001" if ref.endswith(("001", "002")) else ref
            scope = Scope(scope_type=ScopeType.PARENT_ASIN, scope_status=ScopeStatus.SCOPE_UNCONFIRMED if missing_parent else ScopeStatus.CONFIRMED, scope_subject_id=None if missing_parent else parent)
            observation = replace(observation, scope=scope)
            if identical and observation.metric == "estimated_monthly_sales" and ref.endswith(("001", "002")):
                observation = replace(observation, value=replace(observation.value, raw_value=120, normalized_value=120))
        observations.append(observation)
    bundle = replace(original, observations=tuple(observations))
    from amazon_product_intelligence.route_discovery_input import RouteDiscoveryInputContext
    from amazon_product_intelligence.route_discovery_v2 import load_route_discovery_v2_config
    from amazon_product_intelligence.semantic_engine_v2 import load_category_semantic_profile
    from tests.test_sp_043a_final_market_intelligence_integration import ROOT
    return run_final_market_intelligence(canonical_bundles=(bundle,), input_context=RouteDiscoveryInputContext(marketplace="US", category="shower caddies", imported_at="2026-08-26T00:00:00Z", normalized_at="2026-08-26T00:00:00Z", normalization_run_id="p0-fixture", observed_date="2026-08-26"), semantic_profile=load_category_semantic_profile(ROOT / "config/category_semantic_profiles/shower_caddies.v1_1.json"), route_config=load_route_discovery_v2_config(ROOT / "config/route_discovery_v2/shower_caddies.v2.json"), generated_at="2026-08-26T00:00:00Z")


@pytest.mark.parametrize("identical", [False, True])
def test_repeated_parents_are_not_summed_or_arbitrarily_selected(integrated, identical):
    result = build_operator_market_report(parent_evidence(integrated, identical=identical), evidence_context=COMPLETE).to_dict()
    q = result["evidence_qualification"]
    assert q["duplicate_parent_group_count"] == 1
    assert q["duplicate_parent_listing_count"] == 2
    assert result["market"]["sales"]["included_count"] == 7
    assert result["market"]["sales"]["value"] == q["raw_source_row_sums_audit_only"]["sales"] - q["duplicate_parent_excluded_sums"]["sales"]
    assert sum(r["products"] for r in result["routes"]) == 9  # no semantic migration


def test_parent_estimates_never_leak_to_child_facets_or_seller_shares(integrated):
    result = build_operator_market_report(parent_evidence(integrated), evidence_context=COMPLETE).to_dict()
    for aggregate in [result["market"], result["assigned_market"], *result["routes"], *result["families"], *result["mechanism_groups"]]:
        for band in aggregate["price_bands"] + aggregate["review_bands"]:
            assert band["sales"]["value"] is None and band["sales_share"]["value"] is None
        assert aggregate["low_review"]["selling_products"] is None
        for name in ["brands", "sellers"]:
            assert aggregate[name]["sales_concentration"]["top_1"] is None
            assert all(x["sales"]["value"] is None for x in aggregate[name]["top_entities"])
    assert all(x["sales"]["value"] is None for x in result["routes"])
    assert all(x["median_price"]["value"] is not None for x in result["routes"])
    assert result["market"]["sales"]["value"] > 0
    assert not result["decision_readiness"]["strong_route_research_allowed"]


def test_unknown_metric_scope_is_not_promoted_to_listing_scope(integrated):
    result = build_operator_market_report(parent_evidence(integrated, missing_parent=True), evidence_context=COMPLETE).to_dict()
    assert result["market"]["sales"]["value"] is None
    assert result["evidence_qualification"]["scope_unconfirmed_listing_count"] == 9
    assert not result["evidence_qualification"]["allocation_qualified"]


def test_parent_and_child_estimates_cannot_be_combined_into_a_total(integrated):
    report = build_operator_market_report(parent_evidence(integrated, mixed=True), evidence_context=COMPLETE)
    result = report.to_dict()
    assert result["evidence_qualification"]["metric_grain"] == "MIXED"
    assert result["market"]["sales"]["value"] is None
    assert "MIXED_METRIC_SCOPES_WITHHELD" in result["evidence_qualification"]["reason_codes"]
    assert "混合粒度" in markdown(report)


def test_scope_sources_must_match_bound_input_fingerprint(integrated):
    parent = parent_evidence(integrated)
    forged = replace(integrated, canonical_bundles=parent.canonical_bundles)
    with pytest.raises(ValueError, match="source binding"):
        build_operator_market_report(forged, evidence_context=COMPLETE)


@pytest.mark.parametrize("context", [ReportEvidenceContext(), replace(COMPLETE, sampling_description=None), replace(COMPLETE, period_start=None, period_end=None)])
def test_missing_time_or_scope_blocks_json_and_both_localized_views(integrated, context):
    report = build_operator_market_report(integrated, evidence_context=context)
    data = report.to_dict()
    assert not data["decision_readiness"]["strong_route_research_allowed"]
    assert all(e["classification"] == "EVIDENCE_QUALIFICATION_REQUIRED" for e in data["opportunity_explanations"])
    assert all(r["mom"]["value"] is None and r["yoy"]["value"] is None for r in data["routes"])
    assert all(n["products"] is None and n["demand_efficiency"]["value"] is None for r in data["routes"] for n in r["new_products"])
    for locale in ("zh-CN", "en-US"):
        spec = workbook_spec(report, locale)
        assert len(spec["sheets"]) == 15
        assert all(s["note"] for s in spec["sheets"])
        text = markdown(report, locale)
        assert "优先研究：" not in text and "Priority research:" not in text


def test_complete_listing_evidence_retains_normal_analyses(integrated):
    data = build_operator_market_report(integrated, evidence_context=COMPLETE).to_dict()
    assert data["evidence_qualification"]["allocation_qualified"]
    assert data["evidence_qualification"]["time_qualified"]
    assert data["decision_readiness"]["strong_route_research_allowed"]
    assert all(r["sales"]["value"] > 0 for r in data["routes"])


@pytest.mark.parametrize("kwargs", [{"period_start":"2026-08-26"}, {"period_start":"2026-08-26", "period_end":"2026-08-01"}, {"period_start":"invalid", "period_end":"2026-08-26"}])
def test_invalid_or_partial_statistical_window_rejected(kwargs):
    with pytest.raises(ValueError):
        ReportEvidenceContext(**kwargs)


def test_window_after_observation_rejected(integrated):
    with pytest.raises(ValueError, match="after observation"):
        build_operator_market_report(integrated, evidence_context=replace(COMPLETE, period_end="2026-09-01"))


def test_normal_growth_remains_available():
    rows = [row(i, sales=110, mom=.1) for i in range(10)]
    result = growth(rows, "mom")
    assert result["value"] == pytest.approx(.1)
    assert result["interpretation_allowed"] and not result["qualification_reasons"]
    assert result["maximum_leave_one_out_delta"] == pytest.approx(0)


def test_near_total_decline_preserved_but_cannot_become_trend():
    rows = [row(i, sales=100, mom=0) for i in range(10)] + [row(11, sales=30000, mom=-.9994)]
    result = growth(rows, "mom")
    assert result["value"] is None and result["raw_value"] < -.99
    assert result["near_total_decline_count"] == 1
    assert result["largest_prior_contribution_share"] > .99
    assert result["leave_one_out_value_audit_only"] == 0
    assert {"NEAR_TOTAL_DECLINE_IN_SOURCE", "DOMINANT_PRIOR_RECONSTRUCTION", "LEAVE_ONE_OUT_SENSITIVE"} <= set(result["qualification_reasons"])
    assert result == growth(list(reversed(rows)), "mom")


def test_positive_outlier_also_withheld_and_invalid_pairs_counted():
    rows = [row(i, sales=10, mom=0) for i in range(5)] + [row(6, sales=10000, mom=99), row(7, sales=3, mom=-1)]
    result = growth(rows, "mom")
    assert result["value"] is None and result["raw_value"] > 1
    assert result["invalid_reconstruction_count"] == 1
    assert "LEAVE_ONE_OUT_SENSITIVE" in result["qualification_reasons"]


@pytest.mark.parametrize("parent", ["PARENT0001", ""])
def test_export_adapter_declares_parent_and_child_measurement_scopes(tmp_path, parent):
    from amazon_product_intelligence.sellersprite_import import ImportContext, import_sellersprite_file, build_sellersprite_canonical_evidence
    from tests.test_sellersprite_import_governed_dataset_v1 import write_csv
    path = tmp_path / "synthetic.csv"
    write_csv(path, ["ASIN", "父ASIN", "商品标题", "月销量", "子体销量", "月销售额($)", "价格($)"], [["SYNTH00001", parent, "Synthetic product", 100, 30, 2000, 20]])
    dataset = import_sellersprite_file(path, context=ImportContext(marketplace="US", category="fixture", imported_at="2026-08-26T00:00:00Z"))
    bundle = build_sellersprite_canonical_evidence(dataset)
    monthly = next(o for o in bundle.observations if getattr(o, "metric", None) == "estimated_monthly_sales")
    child = next(o for o in bundle.observations if getattr(o, "metric", None) == "estimated_variation_sales")
    assert monthly.scope.scope_type is ScopeType.PARENT_ASIN
    assert monthly.scope.scope_status is (ScopeStatus.CONFIRMED if parent else ScopeStatus.SCOPE_UNCONFIRMED)
    assert monthly.scope.scope_subject_id == (f"product:US:{parent}" if parent else None)
    assert child.scope.scope_type is ScopeType.CHILD_ASIN
    assert child.scope.scope_subject_id == "product:US:SYNTH00001"


def test_missing_canonical_sources_fail_closed_instead_of_trusting_old_labels(integrated):
    data = build_operator_market_report(replace(integrated, canonical_bundles=()), evidence_context=COMPLETE).to_dict()
    assert data["market"]["sales"]["value"] is None
    assert not data["evidence_qualification"]["strong_research_allowed"]


def test_qualification_enters_fingerprint_and_no_listing_id_is_exposed(integrated):
    first = build_operator_market_report(integrated, evidence_context=COMPLETE)
    second = build_operator_market_report(integrated, evidence_context=replace(COMPLETE, sampling_description="another explicitly documented sampling scope"))
    assert first.semantic_fingerprint != second.semantic_fingerprint
    for record in integrated.route_input.dataset.records:
        assert record.asin not in first.to_json()


def test_contradictory_canonical_window_is_rejected(integrated):
    from amazon_product_intelligence.market_report.v0_3.qualification import qualify_records
    original = integrated.canonical_bundles[0]
    observations = tuple(replace(o, time=replace(o.time, period_start="2026-07-01T00:00:00Z", period_end="2026-07-30T00:00:00Z")) if getattr(o, "metric", None) == "estimated_monthly_sales" else o for o in original.observations)
    altered = replace(integrated, canonical_bundles=(replace(original, observations=observations),))
    with pytest.raises(ValueError, match="contradicts Canonical"):
        qualify_records(altered, {r.asin: row(i) for i, r in enumerate(integrated.route_input.dataset.records)}, COMPLETE)


def test_unstable_growth_is_not_mistaken_for_absence_of_positive_growth(integrated):
    from amazon_product_intelligence.market_report.v0_3.builder import _explanations
    data = build_operator_market_report(integrated, evidence_context=COMPLETE).to_dict()
    route = data["routes"][0]
    route["demand_efficiency"]["value"] = .5
    route["mom"]["value"] = None
    route["mom"]["raw_value"] = -.999
    route["mom"]["interpretation_allowed"] = False
    result = next(x for x in _explanations(data) if x["route_id"] == route["route_id"])
    assert result["classification"] == "GROWTH_QUALIFICATION_REQUIRED"


def test_legacy_report_can_be_read_but_cannot_be_reissued_without_qualification(integrated):
    from hashlib import sha256
    from amazon_product_intelligence.contracts import canonical_json
    from amazon_product_intelligence.market_report.v0_3 import OperatorMarketReport
    data = build_operator_market_report(integrated, evidence_context=COMPLETE).to_dict()
    data.pop("evidence_qualification")
    data.pop("semantic_fingerprint")
    data["semantic_fingerprint"] = sha256(canonical_json(data).encode()).hexdigest()
    legacy = OperatorMarketReport(canonical_json(data))
    with pytest.raises(ValueError, match="legacy report"):
        workbook_spec(legacy)


@pytest.mark.parametrize("tamper", ["permission", "trend", "new"])
def test_serialized_output_cannot_bypass_evidence_restrictions(integrated, tamper):
    from hashlib import sha256
    from amazon_product_intelligence.contracts import canonical_json
    from amazon_product_intelligence.market_report.v0_3 import OperatorMarketReport
    data = build_operator_market_report(integrated).to_dict()
    if tamper == "permission":
        data["evidence_qualification"]["strong_research_allowed"] = True
    elif tamper == "trend":
        data["routes"][0]["mom"]["value"] = .1
    else:
        data["routes"][0]["new_products"][0]["products"] = 1
    data.pop("semantic_fingerprint")
    data["semantic_fingerprint"] = sha256(canonical_json(data).encode()).hexdigest()
    with pytest.raises(ValueError, match="qualification|unqualified"):
        OperatorMarketReport(canonical_json(data))
