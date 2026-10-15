from __future__ import annotations

from dataclasses import replace
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report.v0_3 import OperatorMarketReport, ReportProfile, build_operator_market_report, load_report_profile
from amazon_product_intelligence.market_report.v0_3.builder import _explanations, _readiness, hierarchy, resolve
from amazon_product_intelligence.market_report.v0_3.delivery import deliver, validate_workbook
from amazon_product_intelligence.market_report.v0_3.i18n import QUESTIONS, label
from amazon_product_intelligence.market_report.v0_3.metrics import aggregate, bands, competition, efficiency, entrants, growth, median, project_record, total
from amazon_product_intelligence.market_report.v0_3.presentation import markdown, workbook_spec
from scripts.run_sp_043b_private_market_reports import outside
from tests.test_sp_043a_final_market_intelligence_integration import _run

ROOT = Path(__file__).resolve().parents[1]


def row(index=0, **kwargs):
    result = {k: D(str(v)) if v is not None else None for k, v in {"sales": 10, "revenue": 200, "price": 20, "reviews": 20, "rating": 4, "age": 30, "mom": 0.1, "yoy": 0.2}.items()}
    result.update(reference=f"synthetic-{index}", brand="Fixture brand", seller="Fixture seller", title="Synthetic product", structured=True)
    for k, v in kwargs.items():
        result[k] = D(str(v)) if v is not None and k in {"sales", "revenue", "price", "reviews", "rating", "age", "mom", "yoy"} else v
    return result


@pytest.fixture(scope="module")
def integrated():
    return _run()


@pytest.fixture(scope="module")
def report(integrated):
    return build_operator_market_report(integrated, profile=load_report_profile(ROOT / "config/market_report/shower_caddies.v0_3.json"))


@pytest.mark.parametrize("field,boundaries,values,expected", [
    ("price", (10, 20, 40), (0, 9.99, 10, 19.99, 20, 39.99, 40, None), (2, 2, 2, 1, 1)),
    ("reviews", (51, 201, 1001), (0, 50, 51, 200, 201, 1000, 1001, None), (2, 2, 2, 1, 1)),
])
def test_exact_band_boundaries_unknown_partition(field, boundaries, values, expected):
    rows = [row(i, **{field: v}) for i, v in enumerate(values)]
    result = bands(rows, field, boundaries)
    assert tuple(r["products"] for r in result) == expected
    assert sum(r["sales"]["value"] for r in result) == total(rows, "sales")["value"]
    assert sum(r["sales_share"]["value"] for r in result) == pytest.approx(1)


def test_missing_is_not_zero_and_empty_set_is_explicit():
    result = total([row(sales=None)], "sales")
    assert result["value"] is None and result["availability"] == "UNAVAILABLE"
    assert result["unknown_count"] == 1
    assert total([row(sales=0)], "sales")["value"] == 0
    assert total([], "sales") == {"value": 0.0, "availability": "AVAILABLE", "included_count": 0, "population_count": 0, "unknown_count": 0, "coverage": 0.0, "method": "EMPTY_SET_ZERO", "field": "sales"}


def test_efficiency_uses_paired_sales_known_denominator():
    rows = [row(1, sales=40), row(2, sales=10), row(3, sales=None)]
    result = efficiency(rows[:1], rows)
    assert result["value"] == pytest.approx(1.6)
    assert result["listing_share"] == .5
    assert result["coverage"] == pytest.approx(2/3)


def test_zero_demand_has_no_efficiency():
    assert efficiency([row(sales=0)], [row(sales=0)])["value"] is None


@pytest.mark.parametrize("days,expected", [(180, 2), (365, 4)])
def test_nested_new_product_windows_preserve_unknown_age(days, expected):
    rows = [row(i, age=age) for i, age in enumerate((0, 180, 181, 365, 366, None))]
    result = entrants(rows, days)
    assert result["products"] == expected
    assert result["age_unknown"] == 1
    assert result["age_known"] == 5
    assert result["sales_share_known_age"]["value"] == pytest.approx(expected/5)
    assert result["sales_share_route"]["value"] == pytest.approx(expected/6)
    assert result["demand_efficiency"]["value"] == 1
    assert result["success_count"] is None and result["success_share"] is None


def test_no_age_does_not_invent_old_or_successful_products():
    result = entrants([row(age=None)], 180)
    assert result["age_known"] == 0 and result["products"] == 0
    assert result["listing_share_known_age"] is None
    assert result["demand_efficiency"]["value"] is None
    assert result["sales_share_route"]["availability"] == "PARTIAL"


@pytest.mark.parametrize("first,observed,expected", [("2026-01-01", "2026-01-31", 30), ("2027-01-01", "2026-01-31", None), ("invalid", "2026-01-31", None)])
def test_first_available_date_only_uses_governed_observed_date(first, observed, expected):
    record = SimpleNamespace(asin="synthetic", fields=[SimpleNamespace(header="上架时间", import_status=SimpleNamespace(value="NORMALIZED"), value=first)])
    assert project_record(record, observed_date=observed)["age"] == expected
    assert project_record(record)["age"] is None


def test_growth_reconstructs_prior_sales_not_mean_percentages():
    rows = [row(1, sales=200, mom=1), row(2, sales=100, mom=0), row(3, sales=50, mom=-1), row(4, sales=None, mom=0)]
    result = growth(rows, "mom")
    assert result["value"] == .5
    assert result["reconstructed_prior_sales"] == 200
    assert result["coverage"] == .5
    assert result["invalid_reconstruction_count"] == 1


def test_family_median_uses_members_not_mean_of_child_medians():
    rows = [row(i, price=p) for i, p in enumerate((1, 2, 3, 100))]
    family = aggregate(rows, rows, ReportProfile())
    assert family["median_price"]["value"] == 2
    assert family["products"] == 4


def test_competition_top_n_concentration_and_private_names():
    rows = [row(i, brand=f"Synthetic {i}", sales=i+1) for i in range(6)] + [row(7, brand=None, sales=500)]
    result = competition(rows, "brand", 5)
    assert result["top_entities"][0]["name"] == "Synthetic 5"
    assert result["sales_concentration"]["top_1"] == pytest.approx(6/21)
    assert result["sales_concentration"]["top_3"] == pytest.approx(15/21)
    assert result["sales_concentration"]["top_5"] == pytest.approx(20/21)
    assert result["sales_concentration"]["long_tail"] == pytest.approx(1/21)
    assert result["unknown_identity"] == 1 and result["identity_coverage"] == pytest.approx(6/7)


def test_identity_canonicalization_is_only_whitespace_case_and_deterministic():
    rows = [row(1, brand="ACME"), row(2, brand=" acme "), row(3, brand="acme inc")]
    a = competition(rows, "brand", 5)
    assert a == competition(list(reversed(rows)), "brand", 5)
    assert a["entity_count"] == 2


def test_unknown_sales_cannot_create_concentration():
    result = competition([row(brand="Synthetic", sales=None)], "brand", 5)
    assert result["sales_concentration"]["top_1"] is None
    assert result["listing_concentration"]["top_1"] == 1


@pytest.mark.parametrize("form,architecture,mechanism,family,fallback", [
    (None, "wall_mount", "adhesive", "wall_mounted", False),
    (None, "wall_mount", "suction_cup", "wall_mounted", False),
    (None, "wall_mount", "screw_fixed", "wall_mounted", False),
    (None, "wall_mount", None, "wall_mounted", True),
    ("recessed_niche", None, None, "recessed_or_builtin", False),
    ("corner_shelf", "recessed_or_builtin", None, "recessed_or_builtin", False),
    ("portable", None, None, "portable", False),
    (None, "hanging_mount", None, "hanging_mount", False),
])
def test_governed_display_hierarchy(form, architecture, mechanism, family, fallback):
    profile = load_report_profile(ROOT / "config/market_report/shower_caddies.v0_3.json")
    features = [{"dimension": d, "values": [v]} for d, v in (("product_form", form), ("installation_architecture", architecture), ("attachment_mechanism", mechanism)) if v]
    h = hierarchy(features, profile)
    assert h["family_id"] == family
    assert bool(h["fallback_label"]) == fallback


def test_generic_compound_observations_are_never_split_into_routes():
    value = "programmable, temperature control, timer"
    h = hierarchy([{"dimension": "operation_mechanism", "values": [value]}], ReportProfile())
    assert h["family_id"] == "operation_mechanism:" + value
    assert h["compound_observation"]


@pytest.mark.parametrize("kwargs", [{"price_boundaries": (10, 10)}, {"review_boundaries": (100, 50)}, {"price_boundaries": (float('nan'),)}, {"minimum_route_coverage": 1.1}, {"top_n": 2}, {"review_boundaries": (5.1,)}, {"currency": "EUR"}])
def test_invalid_report_policy_rejected(kwargs):
    with pytest.raises(ValueError):
        ReportProfile(**kwargs)


def test_profile_category_isolation(integrated):
    with pytest.raises(ValueError, match="category"):
        build_operator_market_report(integrated, profile=ReportProfile(category="unrelated fixture category"))


def test_upstream_binding_and_released_result_unchanged(integrated, report):
    before = integrated.route_result.semantic_fingerprint
    again = build_operator_market_report(integrated)
    assert before == integrated.route_result.semantic_fingerprint
    assert report.to_dict()["source_lineage"]["route_result_fingerprint"] == before
    tampered = SimpleNamespace(**{k:getattr(integrated,k) for k in ("route_input", "route_result", "semantic_result", "market_report")})
    tampered.semantic_result = SimpleNamespace(result_id="mismatched", semantic_fingerprint="mismatched")
    with pytest.raises(ValueError, match="binding"):
        build_operator_market_report(tampered)


def test_partition_totals_definition_identity_no_listing_grain(report, integrated):
    data = report.to_dict()
    assert sum(f["products"] for f in data["families"]) == data["coverage_counts"]["assigned"]
    assert sum(r["products"] for r in data["routes"]) == data["coverage_counts"]["assigned"]
    assert sum(g["products"] for g in data["mechanism_groups"]) == data["coverage_counts"]["assigned"]
    for f in data["families"]:
        groups = [g for g in data["mechanism_groups"] if g["family_id"] == f["family_id"]]
        assert sum(g["products"] for g in groups) == f["products"]
        assert sum(g["sales_share"]["value"] for g in groups) == pytest.approx(1)
    assert set(r["route_id"] for r in data["routes"]) == set(r.route_id for r in integrated.route_result.routes)
    for listing in integrated.route_input.dataset.records:
        assert listing.asin not in report.to_json()
    for r in data["routes"]:
        assert r["unresolved_exposure"]["value"] is None


def test_low_coverage_blocks_strong_recommendations_without_engine_change(integrated):
    report = build_operator_market_report(integrated, profile=ReportProfile(minimum_sales_coverage=1))
    counts = {"accepted":300, "assigned":64, "unclassified":233, "review_required":3}
    data = report.to_dict()
    result = _readiness(counts, data["assigned_market"], data["market"], ReportProfile())
    assert result["assigned_coverage"] == pytest.approx(64/300)
    assert not result["strong_route_research_allowed"]
    assert {"LIMITED_ROUTE_COVERAGE", "HIGH_UNRESOLVED_EXPOSURE", "BUYER_NEED_DATA_MISSING"} <= set(result["codes"])
    assert not result["whole_category_recommendation_allowed"]
    data["decision_readiness"] = result
    assert all(e["classification"] == "LIMITED_COVERAGE_OBSERVATION" for e in _explanations(data))


def test_all_explanations_are_exact_metric_bound_facts(report):
    data = report.to_dict()
    for item in data["opportunity_explanations"]:
        for fact in item["facts"]:
            assert fact["value"] == resolve(data, fact["path"])
    assert not data["buyer_needs"]["themes"]
    assert data["buyer_needs"]["availability"] == "UNAVAILABLE"


def test_thin_growth_evidence_cannot_trigger_priority_research(report):
    data = report.to_dict()
    route = min(data["routes"], key=lambda r:r["sales_share"]["value"])
    route["demand_efficiency"]["value"] = 1.2
    route["mom"]["value"] = 1.0
    route["mom"]["coverage"] = .1
    route["yoy"]["value"] = None
    explanation = next(e for e in _explanations(data) if e["route_id"] == route["route_id"])
    assert explanation["classification"] == "WATCH"
    assert next(f for f in explanation["facts"] if f["code"] == "POSITIVE_MOM")["role"] == "context"


def test_serialized_report_rejects_migrated_human_values(report):
    data = report.to_dict()
    data["business_value_review"][0]["human_verdict"] = True
    data.pop("semantic_fingerprint")
    data["semantic_fingerprint"] = sha256(canonical_json(data).encode()).hexdigest()
    with pytest.raises(ValueError, match="human"):
        OperatorMarketReport(canonical_json(data))


def test_report_cannot_mutate_behind_its_fingerprint(report):
    copy = report.to_dict()
    copy["routes"][0]["products"] = 999
    assert report.to_dict()["routes"][0]["products"] != 999


@pytest.mark.parametrize("locale", ["zh-CN", "en-US"])
def test_localized_shared_views_and_blank_human_review(report, locale):
    spec = workbook_spec(report, locale)
    assert len(spec["sheets"]) == 15
    human = spec["sheets"][13]["tables"][0]["rows"]
    assert len(human) == 11 and all(r[1:] == ["", ""] for r in human)
    assert spec == workbook_spec(report, locale)
    assert markdown(report, locale) == markdown(report, locale)
    if locale == "zh-CN":
        assert all(any('\u4e00' <= c <= '\u9fff' for c in s["name"]) for s in spec["sheets"])
        assert all(q[0] in markdown(report, locale) for q in QUESTIONS)
        assert "900.00%" not in markdown(report, locale)  # counts are not ratios
        assert "未翻译的受治理结构值" not in markdown(report, locale)


def test_locale_unknown_rejected(report):
    with pytest.raises(ValueError, match="locale"):
        workbook_spec(report, "unsupported")


def test_private_boundary_rejects_repository_and_symlink_resolved_paths(tmp_path):
    with pytest.raises(ValueError, match="outside"):
        outside(ROOT / "outputs/private", ROOT)
    assert outside(tmp_path, ROOT) == tmp_path.resolve()


def test_report_core_has_no_provider_or_category_logic():
    for path in (ROOT / "src/amazon_product_intelligence/market_report/v0_3").glob("*.py"):
        if path.name == "i18n.py":
            continue
        body = path.read_text(encoding="utf-8").casefold()
        assert not any(term in body for term in ("sellersprite", "sorftime", "shower caddies", "air fryers"))


@pytest.mark.skipif(not os.environ.get("SP043B_NODE") or not os.environ.get("SP043B_RUNTIME"), reason="Artifact Tool runtime supplied by host for XLSX integration")
def test_artifact_workbook_roundtrip_determinism_and_formula_injection(report, tmp_path):
    data = report.to_dict()
    data["routes"][0]["brands"]["top_entities"][0]["name"] = '=HYPERLINK("https://example.invalid","not executable")'
    data.pop("semantic_fingerprint")
    data["semantic_fingerprint"] = sha256(canonical_json(data).encode()).hexdigest()
    report = OperatorMarketReport(canonical_json(data))
    args = dict(node_executable=os.environ["SP043B_NODE"], renderer_runtime=os.environ["SP043B_RUNTIME"])
    first = deliver(report, tmp_path / "first", **args)
    second = deliver(report, tmp_path / "second", **args)
    assert first["workbook_content_sha256"] == second["workbook_content_sha256"]
    assert first["checks"]["blank_human_cells"] == 22
    assert first["checks"]["all_table_cells_match"]
