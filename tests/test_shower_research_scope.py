"""Synthetic subject/packaging counterexamples; no private acceptance rows."""
from dataclasses import replace
import json

import pytest

from amazon_product_intelligence.semantic_engine_v2 import (
    build_semantic_engine_v2_result, load_category_semantic_profile, SemanticEngineV2Error,
)
from amazon_product_intelligence.semantic_engine_v2.research_scope import build_research_scope_summary
from tests.test_semantic_engine_v2 import _dataset, _field, PROFILES


def run(*titles, detail=None, profile=None):
    records = tuple((f"SYN{i:07d}", (_field("商品标题", title),) +
                     (() if detail is None else (_field("详细参数", detail),)))
                    for i, title in enumerate(titles))
    return build_semantic_engine_v2_result(_dataset("shower caddies", records),
        profile=profile or load_category_semantic_profile(PROFILES / "shower_caddies.v1_1.json"))


@pytest.mark.parametrize("title", [
    "Synthetic Shower Caddy 3 Pack bundle with Adhesive Stickers 4 pack",
    "Synthetic Corner Shower Shelf bundle with Replacement Hardware Kit, Silver",
])
def test_explicit_whole_product_bundle_retains_role_and_evidence(title):
    item = run(title).listings[0]
    assert item.product_identity.is_target_identity
    assert item.product_role.relation_role.value == "BUNDLE"
    assert item.research_scope.group == "CORE_MAIN_PRODUCT_BUNDLE"
    assert item.market_cohort_eligibility.eligible_for_primary_cohort
    assert item.research_scope.packaging_status == "MAIN_PRODUCT_WITH_ANCILLARY_PARTS"
    assert set(item.research_scope.fact_ids) <= {f.fact_id for f in item.facts}
    evidence = {e.evidence_id: e for e in item.evidence}
    assert item.research_scope.evidence_ids
    assert {evidence[e].source_class.value for e in item.research_scope.evidence_ids} == {"LISTING_TITLE"}
    # A hardware kit does not prove how the shelf is installed.
    if "Hardware" in title:
        assert not any(f.dimension == "installation_architecture" for f in item.facts)


@pytest.mark.parametrize("title", [
    "Replacement Shower Caddy bundle with Replacement Hardware Kit",
    "Clips for Shower Caddy bundle with Replacement Hardware Kit",
    "Synthetic Shower Caddy bundle with another Shower Caddy",
    "Synthetic Shower Caddy bundle with Adhesive Stickers and Soap Dish",
    "Synthetic Shower Caddy bundle with Replacement Hardware Kit for Shower Caddy",
    "Adhesive Hooks for Shower Caddy bundle with Adhesive Stickers",
    "Soap Dish and Shower Caddy bundle with Adhesive Stickers",
    "Soap Dish & Shower Caddy bundle with Adhesive Stickers",
])
def test_bundle_word_never_blanket_admits_parts_or_other_products(title):
    item = run(title).listings[0]
    assert item.research_scope.group == "REVIEW_UNRESOLVED"
    assert not item.market_cohort_eligibility.eligible_for_primary_cohort
    assert item.research_scope.group != "CORE_MAIN_PRODUCT_BUNDLE"


def test_included_parts_are_not_an_explicit_bundle():
    item = run("Synthetic Shower Caddy with Adhesive Stickers").listings[0]
    assert item.product_role.relation_role.value == "PRIMARY_PRODUCT"
    assert item.research_scope.group == "CORE_STANDARD"
    assert item.research_scope.packaging_status == "NO_EXPLICIT_BUNDLE"


def test_explicit_accessory_role_precedes_broad_non_target_identity_group():
    item = run("Adhesive Strips Only").listings[0]
    assert item.product_role.relation_role.value == "ACCESSORY"
    assert item.research_scope.group == "ACCESSORY_OR_REPLACEMENT"
    assert not item.market_cohort_eligibility.eligible_for_primary_cohort


@pytest.mark.parametrize("title", [
    "Bath Toy Storage with quick dry Shower Caddy label",
    "Acrylic Bathroom Shelves", "Plastic Toilet Paper Basket with Shower Caddy handles",
    "Corner Bathroom Organizer Countertop Shelf and Vanity Tray",
])
def test_adjacent_main_objects_stay_outside_core(title):
    item = run(title).listings[0]
    assert item.research_scope.group == "ADJACENT"
    assert not item.market_cohort_eligibility.eligible_for_primary_cohort


def test_pocket_sum_abstains_without_inventing_bundle_or_portability():
    item = run("Synthetic Shower Caddy Organizer 4 Pockets + 7 Pockets Mesh Organizer",
               detail="Number of Items: 1 | Mounting Type: Insert Mount").listings[0]
    assert item.research_scope.group == "REVIEW_UNRESOLVED"
    assert item.research_scope.packaging_status == "UNRESOLVED"
    assert item.product_role.relation_role.value == "PRIMARY_PRODUCT"
    assert not item.market_cohort_eligibility.eligible_for_primary_cohort
    assert not any(f.dimension in {"product_form", "installation_architecture"} for f in item.facts)


def test_scope_does_not_clear_installation_conflict():
    item = run("Synthetic Tension Pole Shower Caddy bundle with Adhesive Stickers",
               detail="Mounting Type: Wall Mount").listings[0]
    assert item.research_scope.group == "CORE_MAIN_PRODUCT_BUNDLE"
    assert not item.market_cohort_eligibility.eligible_for_primary_cohort
    assert "ROUTE_CRITICAL_CONFLICT:installation_architecture" in item.review_reason_codes


def test_summary_is_disjoint_listing_grain_and_not_component_or_sales_allocation():
    result = run("Synthetic Shower Caddy 6 Pack bundle with Adhesive Stickers 12 pack",
                 "Synthetic Shower Caddy", "Bath Toy Storage", "Replacement Shower Caddy",
                 "Shower Caddy 4 Pockets + 7 Pockets")
    summary = build_research_scope_summary(result)
    assert summary["listing_count"] == 5
    assert summary["core_listing_count"] == 2
    assert all(g["listing_count"] == 1 for g in summary["groups"])
    assert sum(g["listing_count"] for g in summary["groups"]) == 5
    assert summary["semantic_result_fingerprint"] == result.semantic_fingerprint
    assert "sales" not in summary
    without_scope = replace(load_category_semantic_profile(PROFILES / "shower_caddies.v1_1.json"), research_scope_policy=None)
    legacy = run("Synthetic Shower Caddy", profile=without_scope)
    assert "research_scope" not in legacy.listings[0].to_dict()
    assert build_research_scope_summary(legacy) is None


@pytest.mark.parametrize("mutation", ["regex", "subject", "source", "missing_rule", "wrong_relation", "overlap"])
def test_scope_loader_rejects_unsafe_authority(tmp_path, mutation):
    payload = json.loads((PROFILES / "shower_caddies.v1_1.json").read_text())
    if mutation == "regex": payload["identity_rules"][0]["text_pattern"] = "["
    elif mutation == "subject": payload["identity_rules"][0]["text_pattern"] = "^bundle"
    elif mutation == "source": payload["identity_rules"][0]["sources"] = ["STRUCTURED_PARAMETERS"]
    elif mutation == "missing_rule": payload["research_scope_policy"]["bundle_identity_rule_ids"] = ["absent"]
    elif mutation == "wrong_relation": payload["relation_rules"][0]["result"] = "PRIMARY_PRODUCT"
    elif mutation == "overlap": payload["research_scope_policy"]["adjacent_identity_values"] += ["shower caddy"]
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(payload))
    with pytest.raises(SemanticEngineV2Error, match="PROFILE_SCHEMA_INVALID"):
        load_category_semantic_profile(path)


def test_report_consumes_bound_scope_and_rejects_rehashed_population_changes():
    from hashlib import sha256
    from amazon_product_intelligence.contracts import canonical_json
    from amazon_product_intelligence.market_report.v0_3 import build_operator_market_report, OperatorMarketReport
    from tests.test_sp_043a_final_market_intelligence_integration import _run
    integrated = _run()
    data = build_operator_market_report(integrated).to_dict()
    assert data["research_scope"] == build_research_scope_summary(integrated.semantic_result)
    assert not data["evidence_qualification"]["strong_research_allowed"]
    for change in ("core_count", "group", "source", "member"):
        tampered = json.loads(json.dumps(data))
        scope = tampered["research_scope"]
        if change == "core_count": scope["core_listing_count"] += 1
        elif change == "group": scope["groups"][0]["group"] = "ADJACENT"
        elif change == "source": scope["profile_fingerprint"] = "0" * 64
        elif change == "member": scope["groups"][0]["member_record_fingerprints"][0] = "unbound-member"
        tampered.pop("semantic_fingerprint")
        tampered["semantic_fingerprint"] = sha256(canonical_json(tampered).encode()).hexdigest()
        with pytest.raises(ValueError, match="research scope"):
            OperatorMarketReport(canonical_json(tampered))
