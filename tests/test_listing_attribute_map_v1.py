from __future__ import annotations

import json
import csv
from pathlib import Path

import pytest

from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
)
from amazon_product_intelligence.listing_attribute_map import (
    AttributeSlotStatus,
    build_product_attribute_map,
    load_category_rule_pack,
    parse_detailed_parameters,
)
from amazon_product_intelligence.listing_attribute_map.measurements import (
    parse_measurement,
)
from amazon_product_intelligence.listing_attribute_map.rule_pack import (
    MeasurementScope,
    QuantityKind,
)
from amazon_product_intelligence.sellersprite_import.models import (
    EvidenceSemantics,
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
    NormalizedField,
)

from scripts.build_product_attribute_map import main as cli_main


ROOT = Path(__file__).resolve().parents[1]
SHOWER_PACK = ROOT / "config/category_rule_packs/shower_caddies.v1.json"
DOG_PACK = ROOT / "config/category_rule_packs/dog_water_bottle.v1.json"


def _field(header: str, value: str) -> NormalizedField:
    return NormalizedField(
        header=header,
        requirement="OPTIONAL",
        value_type="TEXT",
        value=value,
        import_status=ImportValueStatus.NORMALIZED,
        presence_status=PresenceStatus.PRESENT,
        normalization_status=NormalizationStatus.NORMALIZED,
        semantic_status=SemanticStatus.CONFIRMED,
        evidence_semantics=EvidenceSemantics.PROVIDER_EXPORTED_EVIDENCE,
    )


def _dataset(
    category: str,
    fields: tuple[NormalizedField, ...],
    *,
    record_fingerprint: str = "record-fingerprint-001",
) -> GovernedMarketDatasetV1:
    record = ListingRecordV1(
        asin="B012345678",
        parent_asin=None,
        source_row=2,
        fields=fields,
        record_fingerprint=record_fingerprint,
    )
    return GovernedMarketDatasetV1(
        dataset_id="gmdv1-synthetic",
        semantic_fingerprint="upstream-semantic-fingerprint",
        source_type="CSV",
        source_basename="synthetic.csv",
        source_file_sha256="0" * 64,
        imported_at="2026-08-26T00:00:00+00:00",
        marketplace="US",
        category=category,
        observed_date="2026-08-26",
        observed_date_status="KNOWN",
        source_sheet=None,
        header_row=1,
        source_row_count=1,
        accepted_listing_count=1,
        unique_asin_count=1,
        duplicate_row_count=0,
        rejected_row_count=0,
        quarantined_row_count=0,
        missing_core_field_summary=(),
        unmapped_headers=(),
        out_of_scope_headers=(),
        records=(record,),
        row_outcomes=(),
    )


def _slot(product_map, dimension: str):
    return next(
        item for item in product_map.records[0].attributes
        if item.dimension == dimension
    )


def _values(slot):
    return tuple(item.value for item in slot.values)


def test_detailed_parameters_are_deduplicated_and_permutation_deterministic():
    first = parse_detailed_parameters(
        " Color : Black | Material: Stainless   Steel | Color: Black "
    )
    second = parse_detailed_parameters(
        "material: stainless steel|COLOR:black|color:black"
    )

    assert first.duplicate_pair_count == 1
    assert second.duplicate_pair_count == 1
    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert [
        (item.normalized_key, item.normalized_value)
        for item in first.parameters
    ] == [
        ("color", "black"),
        ("material", "stainless steel"),
    ]


def test_detailed_parameters_preserve_same_key_conflict_for_review():
    parsed = parse_detailed_parameters(
        "Color: Black | color: White | Color: Black"
    )

    assert parsed.duplicate_pair_count == 1
    assert parsed.conflicted_keys == frozenset({"color"})
    assert parsed.conflicts[0].normalized_values == ("black", "white")


@pytest.mark.parametrize(
    ("text", "kind", "expected_issue"),
    [
        ("8 pockets", QuantityKind.COUNT, "NON_PACK_COUNT_BOUNDARY"),
        ("8 tiers", QuantityKind.COUNT, "NON_PACK_COUNT_BOUNDARY"),
        ("8 shelves", QuantityKind.COUNT, "NON_PACK_COUNT_BOUNDARY"),
        ("8 layers", QuantityKind.COUNT, "NON_PACK_COUNT_BOUNDARY"),
        ("10 oz", QuantityKind.VOLUME, "AMBIGUOUS_OUNCE_UNIT"),
    ],
)
def test_measurement_negative_boundaries(text, kind, expected_issue):
    result = parse_measurement(
        text,
        quantity_kind=kind,
        scope=MeasurementScope.ITEM,
    )
    assert result.measurement is None
    assert result.issue_code == expected_issue


def test_decimal_measurements_preserve_original_and_canonical_values():
    dimensions = parse_measurement(
        "12 x 8 x 3 in",
        quantity_kind=QuantityKind.DIMENSIONS,
        scope=MeasurementScope.ITEM,
    ).measurement
    mass = parse_measurement(
        "2.5 lb",
        quantity_kind=QuantityKind.MASS,
        scope=MeasurementScope.PACKAGE,
    ).measurement
    volume = parse_measurement(
        "16 fl oz",
        quantity_kind=QuantityKind.VOLUME,
        scope=MeasurementScope.ITEM,
    ).measurement

    assert dimensions is not None
    assert dimensions.original_values == ("12", "8", "3")
    assert dimensions.canonical_values == ("30.48", "20.32", "7.62")
    assert mass is not None
    assert mass.canonical_values == ("1133.980925",)
    assert mass.scope is MeasurementScope.PACKAGE
    assert volume is not None
    assert volume.canonical_values == ("0.473176473",)


def test_shower_rule_pack_precedence_conflicts_and_negative_boundaries():
    product_map = build_product_attribute_map(
        _dataset(
            "Shower Caddies",
            (
                _field(
                    "\u8be6\u7ec6\u53c2\u6570",
                    "Product Type: Shower Caddy | Mounting Type: Hanging | "
                    "Material: Stainless Steel | Number of Items: 2 | "
                    "Color: Black | Special Feature: Rustproof",
                ),
                _field(
                    "\u5546\u54c1\u6807\u9898",
                    "Adhesive No Drilling Shower Caddy with 8 Pockets",
                ),
                _field("\u5546\u54c1\u5c3a\u5bf8", "12 x 8 x 3 in"),
                _field("\u5305\u88c5\u5c3a\u5bf8", "13 x 9 x 4 in"),
                _field("\u5546\u54c1\u91cd\u91cf", "2 lb"),
                _field("\u5305\u88c5\u91cd\u91cf", "2.5 lb"),
            ),
        ),
        rule_pack=load_category_rule_pack(SHOWER_PACK),
    )

    assert _values(_slot(product_map, "product_form")) == ("shower caddy",)
    mounting = _slot(product_map, "mounting_or_usage_mode")
    assert _values(mounting) == ("hanging",)
    assert any(
        "LOWER_PRIORITY_DISAGREEMENT" in item
        for item in mounting.limitations
    ) is False
    assert _values(_slot(product_map, "material_family")) == ("metal",)
    material_value = _slot(product_map, "material_family").values[0]
    material_evidence = next(
        item for item in product_map.records[0].evidence
        if item.evidence_id in material_value.evidence_ids
    )
    assert material_evidence.source_snippet == "stainless steel"
    assert _values(_slot(product_map, "pack_count"))[0][
        "canonical_values"
    ] == ["2"]
    assert _slot(product_map, "dimensions").status is AttributeSlotStatus.AVAILABLE
    assert {
        item.value["scope"]
        for item in _slot(product_map, "dimensions").values
    } == {"ITEM", "PACKAGE"}
    assert _slot(product_map, "weight").status is AttributeSlotStatus.AVAILABLE
    assert product_map.mapped_listing_count == 1
    assert product_map.upstream_dataset_id == "gmdv1-synthetic"


def test_no_drilling_wall_mounted_and_pockets_do_not_infer_forbidden_values():
    product_map = build_product_attribute_map(
        _dataset(
            "Shower Caddies",
            (
                _field(
                    "\u5546\u54c1\u6807\u9898",
                    "No Drilling Wall Mounted Shower Caddy with 8 Pockets",
                ),
            ),
        ),
        rule_pack=load_category_rule_pack(SHOWER_PACK),
    )

    assert _values(_slot(product_map, "mounting_or_usage_mode")) == (
        "wall mounted",
    )
    assert _slot(
        product_map, "pack_count"
    ).status is AttributeSlotStatus.UNAVAILABLE



def test_hanging_specificity_is_preserved():
    product_map = build_product_attribute_map(
        _dataset(
            "Shower Caddies",
            (
                _field(
                    "\u8be6\u7ec6\u53c2\u6570",
                    "Mounting Type: Over Shower Head",
                ),
            ),
        ),
        rule_pack=load_category_rule_pack(SHOWER_PACK),
    )

    assert _values(_slot(product_map, "mounting_or_usage_mode")) == (
        "over shower head",
    )
def test_structured_value_wins_over_title_and_conflicting_key_requires_review():
    product_map = build_product_attribute_map(
        _dataset(
            "Shower Caddies",
            (
                _field(
                    "\u8be6\u7ec6\u53c2\u6570",
                    "Mounting Type: Hanging | Color: Black | color: White",
                ),
                _field("\u5546\u54c1\u6807\u9898", "Adhesive Shower Caddy"),
            ),
        ),
        rule_pack=load_category_rule_pack(SHOWER_PACK),
    )

    mounting = _slot(product_map, "mounting_or_usage_mode")
    assert _values(mounting) == ("hanging",)
    assert any(
        "LOWER_PRIORITY_DISAGREEMENT" in item
        for item in mounting.limitations
    )
    color = _slot(product_map, "color")
    assert color.status is AttributeSlotStatus.REVIEW_REQUIRED
    assert not color.values
    assert {item.value for item in color.review_candidates} == {
        "black", "white"
    }
    assert color.conflicts[0].code == "STRUCTURED_SEMANTIC_KEY_CONFLICT"


def test_second_category_uses_same_engine_with_only_a_different_rule_pack():
    product_map = build_product_attribute_map(
        _dataset(
            "Dog Water Bottles",
            (
                _field(
                    "\u8be6\u7ec6\u53c2\u6570",
                    "Product Type: Dog Water Bottle | Capacity: 16 fl oz | "
                    "Material: PETG | Color: Blue | "
                    "Special Feature: Leakproof",
                ),
                _field(
                    "\u5546\u54c1\u6807\u9898",
                    "Portable Squeeze Dog Water Bottle with Filter",
                ),
                _field("\u5546\u54c1\u91cd\u91cf", "8 oz"),
            ),
        ),
        rule_pack=load_category_rule_pack(DOG_PACK),
    )

    assert _values(_slot(product_map, "product_form")) == (
        "dog water bottle",
    )
    assert _values(_slot(product_map, "operation_mode")) == ("squeeze",)
    assert _values(_slot(product_map, "material_family")) == ("plastic",)
    assert _values(_slot(product_map, "size_or_capacity"))[0][
        "canonical_values"
    ] == ["0.473176473"]
    assert set(_values(_slot(product_map, "special_features"))) == {
        "filter", "leakproof"
    }


def test_product_attribute_map_identity_is_stable_and_timestamp_free():
    dataset = _dataset(
        "Dog Water Bottles",
        (_field("\u8be6\u7ec6\u53c2\u6570", "Capacity: 500 ml | Color: Blue"),),
    )
    pack = load_category_rule_pack(DOG_PACK)

    first = build_product_attribute_map(dataset, rule_pack=pack)
    second = build_product_attribute_map(dataset, rule_pack=pack)

    assert first.semantic_fingerprint == second.semantic_fingerprint
    assert first.dataset_id == second.dataset_id
    serialized = first.to_json()
    assert "runtime_timestamp" not in serialized
    assert "imported_at" not in serialized


def test_rule_pack_loader_rejects_unknown_fields(tmp_path):
    payload = json.loads(SHOWER_PACK.read_text(encoding="utf-8"))

    payload["executable_expression"] = "never_allowed"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown"):
        load_category_rule_pack(path)


def test_cli_chains_sp041b_to_map_with_sanitized_exclusive_output(
    tmp_path, capsys
):
    source = tmp_path / "seller-export.csv"
    output = tmp_path / "attribute-map.json"
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "ASIN",
            "SKU",
            "\u8be6\u7ec6\u53c2\u6570",
            "\u5546\u54c1\u6807\u9898",
            "\u5546\u54c1\u5c3a\u5bf8",
        ])
        writer.writerow([
            "B012345678",
            "SC-2PK",
            "Product Type: Shower Caddy | Number of Items: 2",
            "Two Pack Shower Caddy",
            "12 x 8 x 3 in",
        ])
    arguments = [
        "--input", str(source),
        "--rule-pack", str(SHOWER_PACK),
        "--marketplace", "US",
        "--category", "Shower Caddies",
        "--imported-at", "2026-08-26T00:00:00Z",
        "--output", str(output),
    ]

    assert cli_main(arguments) == 0
    stdout = capsys.readouterr().out
    assert str(tmp_path) not in stdout
    summary = json.loads(stdout)
    assert summary["status"] == "SUCCEEDED"
    assert summary["private_real_listing_replay"] == "NOT_RUN"
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["counts"]["listings"] == 1
    assert payload["rule_pack"]["id"] == "shower-caddies"

    assert cli_main(arguments) == 2
    failure = json.loads(capsys.readouterr().out)
    assert failure["status"] == "FAILED"

    assert failure["error"].startswith("OUTPUT_ALREADY_EXISTS")


def test_unmapped_structured_parse_problems_are_record_level_review_items():
    product_map = build_product_attribute_map(
        _dataset(
            "Shower Caddies",
            (
                _field(
                    "\u8be6\u7ec6\u53c2\u6570",
                    "Bad Segment | Unknown: A | unknown: B",
                ),
            ),
        ),
        rule_pack=load_category_rule_pack(SHOWER_PACK),
    )

    record = product_map.records[0]
    assert record.record_limitations == (
        "STRUCTURED_PARAMETERS:MISSING_KEY_VALUE_DELIMITER",
        "STRUCTURED_PARAMETERS:UNMAPPED_CONFLICT:unknown",
    )
    assert record.review_required_count == 2
    assert record.conflict_count == 1
    assert product_map.review_required_count == 2
    assert product_map.conflict_count == 1
