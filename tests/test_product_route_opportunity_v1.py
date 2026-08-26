from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import csv
import json
from pathlib import Path

import pytest

from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
)
from amazon_product_intelligence.listing_attribute_map import (
    build_product_attribute_map,
    load_category_rule_pack,
)
from amazon_product_intelligence.product_route_opportunity import (
    CandidateSelectionStatus,
    MembershipStatus,
    ProductRouteOpportunityError,
    build_product_route_opportunity,
    load_route_discovery_config,
)
from amazon_product_intelligence.sellersprite_import.models import (
    EvidenceSemantics,
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
    NormalizedField,
)
from scripts.build_product_route_opportunity import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
SHOWER_RULES = ROOT / "config/category_rule_packs/shower_caddies.v1.json"
SHOWER_ROUTES = ROOT / "config/route_discovery/shower_caddies.v1.json"
DOG_RULES = ROOT / "config/category_rule_packs/dog_water_bottle.v1.json"
DOG_ROUTES = ROOT / "config/route_discovery/dog_water_bottle.v1.json"


def _field(
    header: str,
    value,
    *,
    value_type: str = "TEXT",
    evidence: EvidenceSemantics = EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE,
) -> NormalizedField:
    return NormalizedField(
        header=header, requirement="OPTIONAL", value_type=value_type, value=value,
        import_status=ImportValueStatus.NORMALIZED,
        presence_status=PresenceStatus.PRESENT,
        normalization_status=NormalizationStatus.NORMALIZED,
        semantic_status=SemanticStatus.CONFIRMED,
        evidence_semantics=evidence,
    )


def _missing(header: str, *, value_type: str = "TEXT") -> NormalizedField:
    return NormalizedField(
        header=header, requirement="OPTIONAL", value_type=value_type, value=None,
        import_status=ImportValueStatus.BLANK,
        presence_status=PresenceStatus.MISSING,
        normalization_status=NormalizationStatus.NOT_ATTEMPTED,
        semantic_status=SemanticStatus.UNPARSED,
        evidence_semantics=EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE,
    )


def _record(
    index: int,
    parameters: str,
    *,
    sales: Decimal | None = None,
    growth: Decimal = Decimal("0.10"),
    color_title: str = "",
    age: int | None = 90,
) -> ListingRecordV1:
    asin = f"B{index:09d}"
    sales_value = sales if sales is not None else Decimal(80 + index * 10)
    fields = [
        _field("\u5546\u54c1\u6807\u9898", f"Governed synthetic item {color_title}"),
        _field("\u8be6\u7ec6\u53c2\u6570", parameters),
        _field("\u6708\u9500\u91cf", sales_value, value_type="NONNEGATIVE_INTEGER",
               evidence=EvidenceSemantics.THIRD_PARTY_ESTIMATE),
        _field("\u6708\u9500\u552e\u989d($)", sales_value * Decimal("20"),
               value_type="MONEY_USD", evidence=EvidenceSemantics.THIRD_PARTY_ESTIMATE),
        _field("\u4ef7\u683c($)", Decimal("19.99") + Decimal(index), value_type="MONEY_USD"),
        _field("\u8bc4\u5206", Decimal("4.4"), value_type="RATING"),
        _field("\u8bc4\u5206\u6570", 20 + index * 3, value_type="NONNEGATIVE_INTEGER"),
        _field("\u54c1\u724c", f"brand-{index % 3}"),
        _field("BuyBox\u5356\u5bb6", f"seller-{index % 2}"),
        _field("\u9500\u91cf\u73af\u6bd4\u589e\u957f\u7387", growth, value_type="PERCENTAGE"),
        _field("\u9500\u91cf\u540c\u6bd4\u589e\u957f\u7387", growth / 2, value_type="PERCENTAGE"),
        _field("\u5927\u7c7bBSR", {"rank": 100 + index, "category": "Synthetic"}, value_type="RANK"),
        _field("\u5c0f\u7c7bBSR", {"rank": 10 + index, "category": "Synthetic Sub"}, value_type="RANK"),
    ]
    fields.append(
        _missing("\u4e0a\u67b6\u5929\u6570", value_type="NONNEGATIVE_INTEGER")
        if age is None else _field("\u4e0a\u67b6\u5929\u6570", age, value_type="NONNEGATIVE_INTEGER")
    )
    return ListingRecordV1(
        asin=asin, parent_asin="P000000001", source_row=index + 1,
        fields=tuple(fields), record_fingerprint=f"record-fingerprint-{index:04d}",
    )


def _dataset(category: str, records: list[ListingRecordV1]) -> GovernedMarketDatasetV1:
    return GovernedMarketDatasetV1(
        dataset_id=f"gmdv1-{category.replace(' ', '-')}",
        semantic_fingerprint=f"dataset-fingerprint-{category.replace(' ', '-')}",
        source_type="CSV", source_basename="synthetic.csv", source_file_sha256="0" * 64,
        imported_at="2026-08-26T00:00:00+00:00", marketplace="US", category=category,
        observed_date="2026-08-26", observed_date_status="KNOWN", source_sheet=None,
        header_row=1, source_row_count=len(records), accepted_listing_count=len(records),
        unique_asin_count=len(records), duplicate_row_count=0, rejected_row_count=0,
        quarantined_row_count=0, missing_core_field_summary=(), unmapped_headers=(),
        out_of_scope_headers=(), records=tuple(records), row_outcomes=(),
    )


def _build(dataset, rule_path: Path, config_path: Path):
    attribute_map = build_product_attribute_map(
        dataset, rule_pack=load_category_rule_pack(rule_path)
    )
    return build_product_route_opportunity(
        dataset, attribute_map, config=load_route_discovery_config(config_path)
    )


def _shower_records() -> list[ListingRecordV1]:
    routes = [
        "Product Type: Shower Caddy | Mounting Type: Adhesive | Material: Stainless Steel | Number of Items: 2 | Special Feature: Rustproof",
        "Product Type: Shower Caddy | Mounting Type: Hanging | Material: Stainless Steel | Number of Items: 1 | Special Feature: Rustproof",
        "Product Type: Shower Caddy | Mounting Type: Tension Pole | Material: Stainless Steel | Number of Items: 1 | Special Feature: Adjustable",
        "Product Type: Shower Caddy | Mounting Type: Floor Standing | Material: Plastic | Number of Items: 1 | Special Feature: Drainable",
    ]
    records: list[ListingRecordV1] = []
    index = 1
    for route in routes:
        records.append(_record(index, route + " | Color: Black", color_title="black"))
        index += 1
        records.append(_record(index, route + " | Color: White", color_title="white"))
        index += 1
    return records


def _dog_records() -> list[ListingRecordV1]:
    routes = [
        "Product Type: Dog Water Bottle | Operation Mode: Push Button | Material: Plastic | Capacity: 12 fl oz | Special Feature: Leakproof",
        "Product Type: Dog Water Bottle | Operation Mode: Squeeze | Material: Plastic | Capacity: 20 fl oz | Special Feature: Leakproof",
        "Product Type: Dog Water Bottle | Operation Mode: Push Button | Material: Stainless Steel | Capacity: 16 fl oz | Special Feature: Filter",
    ]
    records: list[ListingRecordV1] = []
    index = 101
    for route in routes:
        records.append(_record(index, route + " | Color: Blue", color_title="blue"))
        index += 1
        records.append(_record(index, route + " | Color: Pink", color_title="pink"))
        index += 1
    return records


def test_shower_routes_join_listing_grain_ignore_color_and_select_candidates():
    result = _build(_dataset("Shower Caddies", _shower_records()), SHOWER_RULES, SHOWER_ROUTES)

    assert result.listing_count == 8
    assert result.assigned_count == 8
    assert result.unclassified_count == 0
    assert result.review_required_count == 0
    assert len(result.routes) == 4
    assert all(route.member_count == 2 for route in result.routes)
    assert all("color" not in dict(route.defining_attributes) for route in result.routes)
    assert all(item.status is MembershipStatus.ASSIGNED for item in result.memberships)
    assert all(item.primary_route_id is not None for item in result.memberships)
    assert result.candidate_selection_status is CandidateSelectionStatus.SELECTED
    assert 3 <= len(result.candidates) <= 5
    assert all(item.reason_codes for item in result.candidates)
    assert not any("representative" in key.casefold() for key in result.to_dict())


def test_dog_water_bottle_uses_same_generic_engine_without_category_fork():
    result = _build(_dataset("Dog Water Bottles", _dog_records()), DOG_RULES, DOG_ROUTES)

    assert len(result.routes) == 3
    assert result.assigned_count == 6
    assert result.candidate_selection_status is CandidateSelectionStatus.SELECTED
    assert len(result.candidates) == 3
    assert {route.discovery_method for route in result.routes} == {
        "EXACT_KNOWN_STRUCTURAL_ATTRIBUTE_SIGNATURE"
    }


def test_input_permutation_preserves_membership_route_ids_labels_and_fingerprint():
    records = _shower_records()
    first = _build(_dataset("Shower Caddies", records), SHOWER_RULES, SHOWER_ROUTES)
    second = _build(_dataset("Shower Caddies", list(reversed(records))), SHOWER_RULES, SHOWER_ROUTES)

    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert [(item.listing_reference, item.primary_route_id) for item in first.memberships] == [
        (item.listing_reference, item.primary_route_id) for item in second.memberships
    ]
    assert [(item.route_id, item.label, item.semantic_fingerprint) for item in first.routes] == [
        (item.route_id, item.label, item.semantic_fingerprint) for item in second.routes
    ]


def test_listing_and_available_sales_shares_sum_and_missing_sales_is_unknown():
    records = _shower_records()
    missing_sales_fields = tuple(
        _missing("\u6708\u9500\u91cf", value_type="NONNEGATIVE_INTEGER")
        if field.header == "\u6708\u9500\u91cf" else field
        for field in records[0].fields
    )
    records[0] = replace(records[0], fields=missing_sales_fields)
    result = _build(_dataset("Shower Caddies", records), SHOWER_RULES, SHOWER_ROUTES)

    assert sum(Decimal(str(route.metric("route_listing_share").value)) for route in result.routes) == 1
    assert sum(Decimal(str(route.metric("route_sales_share").value)) for route in result.routes) == 1
    assert all(route.metric("route_sales_share").sample_context.unknown_count == 1 for route in result.routes)
    assert all(route.metric("route_sales_share").coverage == pytest.approx(7 / 8) for route in result.routes)


def test_growth_reconstructs_prior_and_rejects_minus_one_without_averaging():
    records = _shower_records()
    target_parameters = records[0].fields[1].value
    records[0] = _record(1, target_parameters, sales=Decimal("100"), growth=Decimal("0.10"))
    records[1] = _record(2, target_parameters, sales=Decimal("200"), growth=Decimal("0.20"))
    result = _build(_dataset("Shower Caddies", records), SHOWER_RULES, SHOWER_ROUTES)
    route = next(route for route in result.routes if "adhesive" in route.label)
    actual = Decimal(str(route.metric("mom_aggregate_growth").value["aggregate_growth"]))
    expected = Decimal("300") / (Decimal("100") / Decimal("1.10") + Decimal("200") / Decimal("1.20")) - 1
    assert actual == pytest.approx(expected)
    assert actual != Decimal("0.15")

    records[1] = _record(2, target_parameters, sales=Decimal("200"), growth=Decimal("-1"))
    partial = _build(_dataset("Shower Caddies", records), SHOWER_RULES, SHOWER_ROUTES)
    route = next(route for route in partial.routes if "adhesive" in route.label)
    metric = route.metric("mom_aggregate_growth")
    assert metric.value["invalid_reconstruction_count"] == 1
    assert metric.coverage == 0.5
    assert "INVALID_GROWTH_AT_OR_BELOW_MINUS_100_EXCLUDED" in metric.limitations


def test_missing_age_is_not_old_and_distributions_concentration_and_adoption_are_covered():
    records = _shower_records()
    age_missing = tuple(
        _missing("\u4e0a\u67b6\u5929\u6570", value_type="NONNEGATIVE_INTEGER")
        if field.header == "\u4e0a\u67b6\u5929\u6570" else field
        for field in records[0].fields
    )
    brand_missing = tuple(
        _missing("\u54c1\u724c") if field.header == "\u54c1\u724c" else field
        for field in age_missing
    )
    records[0] = replace(records[0], fields=brand_missing)
    result = _build(_dataset("Shower Caddies", records), SHOWER_RULES, SHOWER_ROUTES)
    route = next(route for route in result.routes if "adhesive" in route.label)

    new_metric = route.metric("new_product_listing_share")
    assert new_metric.sample_context.unknown_count == 1
    assert "MISSING_AGE_EXCLUDED_NOT_CLASSIFIED_OLD" in new_metric.limitations
    assert route.metric("review_count_distribution").value["method"] == "NEAREST_RANK"
    assert route.metric("price_distribution").value["median"] is not None
    brand = route.metric("brand_listing_concentration")
    assert brand.value["unknown_listing_count"] == 1
    assert brand.coverage == 0.5
    adoption = route.metric("structural_feature_adoption")
    assert adoption.value["material_family"]["known_coverage"] == 1.0


def test_insufficient_missing_conflict_and_singleton_fail_closed():
    records = _shower_records()[:2]
    records.append(_record(
        50,
        "Color: Black",
        age=None,
    ))
    records.append(_record(
        51,
        "Product Type: Shower Caddy | Mounting Type: Hanging | Mounting Type: Adhesive | Material: Steel",
    ))
    records.append(_record(
        52,
        "Product Type: Shower Caddy | Mounting Type: Tension Pole | Material: Steel | Special Feature: Singleton",
    ))
    result = _build(_dataset("Shower Caddies", records), SHOWER_RULES, SHOWER_ROUTES)

    statuses = {item.listing_reference: item.status for item in result.memberships}
    assert statuses["B000000050"] is MembershipStatus.UNCLASSIFIED
    assert statuses["B000000051"] is MembershipStatus.REVIEW_REQUIRED
    assert statuses["B000000052"] is MembershipStatus.UNCLASSIFIED
    assert len(result.routes) == 1
    assert result.candidate_selection_status is CandidateSelectionStatus.INSUFFICIENT_EVIDENCE
    assert result.candidates == ()


def test_config_is_strict_and_forbids_cosmetic_primary_membership(tmp_path: Path):
    payload = json.loads(SHOWER_ROUTES.read_text(encoding="utf-8"))
    payload["core_dimensions"].append("color")
    candidate = tmp_path / "invalid.json"
    candidate.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ProductRouteOpportunityError, match="color cannot be a core dimension"):
        load_route_discovery_config(candidate)


def test_default_diagnostics_are_sanitized_and_source_has_no_network_ai_or_credentials():
    records = _shower_records()
    result = _build(_dataset("Shower Caddies", records), SHOWER_RULES, SHOWER_ROUTES)
    diagnostic_text = json.dumps(dict(result.diagnostics), ensure_ascii=False, sort_keys=True)
    for record in records:
        assert record.asin not in diagnostic_text
    assert "brand-" not in diagnostic_text
    assert "seller-" not in diagnostic_text
    assert "19.99" not in diagnostic_text
    assert dict(result.diagnostics)["private_values_in_diagnostics"] is False

    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "src/amazon_product_intelligence/product_route_opportunity").glob("*.py")
    ).casefold()
    assert "requests" not in source
    assert "http://" not in source and "https://" not in source
    assert "api_key" not in source and "credential" not in source
    assert "openai" not in source and "llm" not in source

def test_runtime_timestamp_change_does_not_change_semantic_output_and_parent_is_not_collapsed():
    dataset = _dataset("Shower Caddies", _shower_records())
    first = _build(dataset, SHOWER_RULES, SHOWER_ROUTES)
    second = _build(
        replace(dataset, imported_at="2030-01-01T12:34:56+00:00"),
        SHOWER_RULES,
        SHOWER_ROUTES,
    )

    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert len(first.product_map_records) == 8
    assert {item.parent_asin for item in first.product_map_records} == {"P000000001"}
    assert len({item.record_id for item in first.product_map_records}) == 8


def test_diversity_constraint_suppresses_near_duplicates_instead_of_forcing_three(tmp_path: Path):
    payload = json.loads(SHOWER_ROUTES.read_text(encoding="utf-8"))
    payload["candidate_min_structural_distance"] = "0.95"
    strict = tmp_path / "strict-diversity.json"
    strict.write_text(json.dumps(payload), encoding="utf-8")
    result = _build(_dataset("Shower Caddies", _shower_records()), SHOWER_RULES, strict)

    assert len(result.routes) == 4
    assert result.candidate_selection_status is CandidateSelectionStatus.INSUFFICIENT_EVIDENCE
    assert result.candidates == ()


def test_full_local_cli_chain_prints_sanitized_summary_only(tmp_path: Path, capsys):
    source = tmp_path / "private-realistic-synthetic.csv"
    headers = [
        "ASIN", "\u5546\u54c1\u6807\u9898", "\u8be6\u7ec6\u53c2\u6570", "\u6708\u9500\u91cf",
        "\u4ef7\u683c($)", "\u8bc4\u5206\u6570", "\u4e0a\u67b6\u5929\u6570", "\u54c1\u724c",
        "BuyBox\u5356\u5bb6", "\u9500\u91cf\u73af\u6bd4\u589e\u957f\u7387",
        "\u9500\u91cf\u540c\u6bd4\u589e\u957f\u7387",
    ]
    route_parameters = [
        "Product Type: Dog Water Bottle | Operation Mode: Push Button | Material: Plastic | Capacity: 12 fl oz | Special Feature: Leakproof",
        "Product Type: Dog Water Bottle | Operation Mode: Squeeze | Material: Plastic | Capacity: 20 fl oz | Special Feature: Leakproof",
        "Product Type: Dog Water Bottle | Operation Mode: Push Button | Material: Stainless Steel | Capacity: 16 fl oz | Special Feature: Filter",
    ]
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        for index, parameters in enumerate(route_parameters * 2, start=1):
            writer.writerow([
                f"B9{index:08d}", "PRIVATE SYNTHETIC TITLE", parameters,
                100 + index, "29.99", 10 + index, 60, "PRIVATE BRAND",
                "PRIVATE SELLER", "10%", "5%",
            ])

    code = cli_main([
        "--input", str(source), "--rule-pack", str(DOG_RULES),
        "--route-config", str(DOG_ROUTES), "--marketplace", "US",
        "--category", "Dog Water Bottles", "--observed-date", "2026-08-26",
        "--imported-at", "2026-08-26T00:00:00Z", "--sanitized-replay-only",
    ])
    output = capsys.readouterr().out
    summary = json.loads(output)

    assert code == 0
    assert summary["route_count"] == 3
    assert summary["candidate_count"] == 3
    assert summary["private_values_printed"] is False
    assert "B9" not in output
    assert "PRIVATE SYNTHETIC TITLE" not in output
    assert "PRIVATE BRAND" not in output
    assert "PRIVATE SELLER" not in output
    assert "29.99" not in output
    assert not list(tmp_path.glob("*.json"))
