from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.contracts import (
    FactGroup,
    ObservationKind,
    ProductFactObservation,
    ProductIdentity,
    canonical_json,
    observation_revision_id,
    product_id,
    semantic_observation_id,
)
from amazon_product_intelligence.product_attribute_extraction import (
    ATTRIBUTE_DIMENSION_REGISTRY_V0_1,
    ATTRIBUTE_RULES_ENGINE_VERSION,
    AttributeAssertionStatus,
    AttributeConfidenceLevel,
    AttributeDimension,
    AttributeExtractionMethod,
    AttributeExtractionPipeline,
    AttributeProfileStatus,
    AttributeState,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)


FIXTURE = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1" / "sorftime_product_detail.json"
TARGET_ASIN = "B0G2VV4RBW"
PARENT_ASIN = "B0G2VVX3ML"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


def target() -> ProductIdentity:
    return ProductIdentity(
        product_id=product_id("US", TARGET_ASIN),
        marketplace="US",
        asin=TARGET_ASIN,
        parent_asin=PARENT_ASIN,
        identity_status="CONFIRMED",
    )


def build_bundle(
    *,
    title: str,
    attributes: dict[str, str] | None = None,
    description: str = "Generic product description.",
):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["data"]["title"] = title
    payload["data"]["attributes"] = json.dumps(attributes or {}, separators=(",", ":"))
    payload["data"]["description"] = description
    return SorftimeAdapterV0_1().adapt(
        payload,
        AdaptationContext(
            provider="sorftime",
            payload_kind="product_detail",
            source_tool="product_detail",
            marketplace="US",
            locale="en-us",
            retrieved_at=RETRIEVED_AT,
            transformed_at=TRANSFORMED_AT,
            collection_run_id="collection:sorftime:product-detail:attribute-rules-test",
            sanitized_request={"asin": TARGET_ASIN},
            currency="USD",
        ),
    ).bundle.validate()


def add_bullet(bundle, bullet: str):
    title = next(
        item
        for item in bundle.observations
        if isinstance(item, ProductFactObservation) and item.dimension == "title"
    )
    dimension = "bullet_points"
    provider_semantic = "Synthetic canonical bullet point evidence for rules-engine tests"
    source_field = "data.bullet_points[0]"
    semantic_id = semantic_observation_id(
        provider=title.provenance.provider,
        source_tool=title.provenance.source_tool,
        subject=title.subject,
        observation_kind=ObservationKind.PRODUCT_FACT,
        dimension=dimension,
        source_record_identity=title.provenance.source_record_identity,
        observed_at=title.time.observed_at,
        period_identity={
            "period_type": title.time.period_type.value,
            "start": title.time.period_start,
            "end": title.time.period_end,
        },
        discriminator=source_field,
    )
    value = replace(title.value, raw_value=bullet, normalized_value=bullet)
    revision_id = observation_revision_id(
        semantic_id,
        {
            "kind": ObservationKind.PRODUCT_FACT,
            "dimension": dimension,
            "fact_group": FactGroup.DESCRIPTION,
            "evidence_type": title.evidence_type,
            "value": value,
            "scope": title.scope,
            "observed_at": title.time.observed_at,
            "period_type": title.time.period_type,
            "provider_semantic": provider_semantic,
        },
    )
    bullet_observation = replace(
        title,
        semantic_observation_id=semantic_id,
        observation_id=revision_id,
        value=value,
        provenance=replace(
            title.provenance,
            source_field=source_field,
            provider_semantic=provider_semantic,
        ),
        dimension=dimension,
        fact_group=FactGroup.DESCRIPTION,
        provider_semantic=provider_semantic,
    )
    run_id = title.provenance.transformation.transformation_run_id
    runs = tuple(
        replace(
            run,
            output_observation_ids=run.output_observation_ids + (revision_id,),
        )
        if run.transformation_run_id == run_id
        else run
        for run in bundle.transformation_runs
    )
    return replace(
        bundle,
        observations=bundle.observations + (bullet_observation,),
        transformation_runs=runs,
    ).validate()


def build_snapshot(bundle):
    return ProductIntelligenceBuilderV0_1().build(ProductIntelligenceRequest(
        target_product_identity=target(),
        scope=ProductScope.EXACT_PRODUCT,
        canonical_bundles=(bundle,),
    ))


def extract(
    *,
    title: str,
    attributes: dict[str, str] | None = None,
    description: str = "Generic product description.",
):
    snapshot = build_snapshot(build_bundle(
        title=title,
        attributes=attributes,
        description=description,
    ))
    return snapshot, AttributeExtractionPipeline().extract(snapshot)


def slot(profile, dimension: AttributeDimension):
    return next(item for item in profile.attributes if item.dimension is dimension)


class AttributeExtractionRulesEngineV01Tests(unittest.TestCase):
    def test_title_extracts_capacity_and_material(self) -> None:
        _, profile = extract(title="20oz stainless steel bottle")
        capacity = slot(profile, AttributeDimension.CAPACITY)
        material = slot(profile, AttributeDimension.MATERIAL)
        self.assertIs(AttributeState.PRESENT, capacity.state)
        self.assertEqual("L", capacity.resolved_value[0].unit.unit_code)
        self.assertEqual("20oz", capacity.assertions[0].raw_value)
        self.assertIs(AttributeState.PRESENT, material.state)
        self.assertEqual("stainless_steel", material.resolved_value[0].value)
        self.assertIs(AttributeExtractionMethod.EXPLICIT_TEXT, material.assertions[0].extraction_method)
        self.assertIs(AttributeConfidenceLevel.MEDIUM, material.assertions[0].confidence.level)

    def test_unit_normalization_converts_600ml_to_point_6_liters(self) -> None:
        _, profile = extract(title="600ml bottle")
        capacity = slot(profile, AttributeDimension.CAPACITY)
        value = capacity.resolved_value[0]
        self.assertEqual(0.6, value.value)
        self.assertEqual("L", value.unit.unit_code)
        normalized = capacity.assertions[0].normalized_value
        self.assertEqual("600", normalized["original_magnitude"])
        self.assertEqual("ml", normalized["original_unit"])
        self.assertEqual("0.6", normalized["canonical_magnitude_text"])

    def test_material_patterns_include_plastic_and_silicone(self) -> None:
        _, profile = extract(title="Portable silicone and plastic container")
        material = slot(profile, AttributeDimension.MATERIAL)
        self.assertEqual(
            {"plastic", "silicone"},
            {item.value for item in material.resolved_value},
        )

    def test_feature_patterns_are_multi_value(self) -> None:
        _, profile = extract(title="Leakproof portable foldable bottle")
        feature = slot(profile, AttributeDimension.FEATURE)
        self.assertIs(AttributeState.PRESENT, feature.state)
        self.assertEqual(
            {"leakproof", "portable", "foldable"},
            {item.value for item in feature.resolved_value},
        )

    def test_package_quantity_supports_both_requested_patterns(self) -> None:
        _, two_pack = extract(title="2 pack reusable bottle")
        _, pack_of_three = extract(title="Pack of 3 reusable bottles")
        self.assertEqual(2, slot(two_pack, AttributeDimension.PACKAGE_QUANTITY).resolved_value[0].value)
        self.assertEqual(3, slot(pack_of_three, AttributeDimension.PACKAGE_QUANTITY).resolved_value[0].value)

    def test_structured_material_and_title_disagreement_is_conflicted(self) -> None:
        _, profile = extract(
            title="Stainless steel bottle",
            attributes={"Material": "Plastic"},
        )
        material = slot(profile, AttributeDimension.MATERIAL)
        self.assertIs(AttributeState.CONFLICTED, material.state)
        self.assertEqual((), material.resolved_value)
        self.assertEqual(2, len(material.assertions))
        self.assertEqual(
            {AttributeExtractionMethod.EXPLICIT_STRUCTURED, AttributeExtractionMethod.EXPLICIT_TEXT},
            {item.extraction_method for item in material.assertions},
        )
        self.assertEqual(
            {AttributeConfidenceLevel.HIGH, AttributeConfidenceLevel.MEDIUM},
            {item.confidence.level for item in material.assertions},
        )

    def test_unknown_handling_does_not_invent_values(self) -> None:
        _, profile = extract(title="Generic Item")
        self.assertIs(AttributeProfileStatus.UNKNOWN, profile.status)
        self.assertTrue(all(item.state is AttributeState.UNKNOWN for item in profile.attributes))
        self.assertEqual(0, profile.coverage.assertion_count)
        self.assertNotIn('"resolved_value":[0]', canonical_json(profile))

    def test_evidence_lineage_retains_source_raw_timestamp_marketplace_and_asin(self) -> None:
        snapshot, profile = extract(title="600ml stainless steel bottle")
        assertion = slot(profile, AttributeDimension.CAPACITY).assertions[0]
        source = assertion.source_evidence[0]
        self.assertEqual("600ml stainless steel bottle", source.source_raw_value)
        self.assertEqual(RETRIEVED_AT, source.retrieved_at)
        self.assertEqual("US", source.product_identity.marketplace)
        self.assertEqual(TARGET_ASIN, source.product_identity.asin)
        self.assertIs(profile, profile.validate_against_product_intelligence_snapshot(snapshot))

    def test_structured_color_size_quantity_and_dimension(self) -> None:
        _, profile = extract(
            title="Generic Item",
            attributes={
                "Color": "Ocean Blue",
                "Size": "Large",
                "Number of Pieces": "2",
                "Item dimensions L x W x H": "12 inch",
            },
        )
        self.assertEqual("ocean blue", slot(profile, AttributeDimension.COLOR).resolved_value[0].value)
        self.assertEqual("large", slot(profile, AttributeDimension.SIZE).resolved_value[0].value)
        self.assertEqual(2, slot(profile, AttributeDimension.PACKAGE_QUANTITY).resolved_value[0].value)
        dimension = slot(profile, AttributeDimension.DIMENSION).resolved_value[0]
        self.assertEqual(30.48, dimension.value)
        self.assertEqual("cm", dimension.unit.unit_code)

    def test_bullet_extracts_attributes_and_keeps_use_case_candidate(self) -> None:
        bundle = build_bundle(title="Generic Bottle")
        bundle = add_bullet(
            bundle,
            "Made with BPA-free stainless steel. Large 600ml capacity. Perfect for hiking and travel.",
        )
        snapshot = build_snapshot(bundle)
        profile = AttributeExtractionPipeline().extract(snapshot)
        self.assertIs(AttributeState.PRESENT, slot(profile, AttributeDimension.MATERIAL).state)
        self.assertEqual(0.6, slot(profile, AttributeDimension.CAPACITY).resolved_value[0].value)
        use_case = slot(profile, AttributeDimension.USE_CASE)
        self.assertIs(AttributeState.AMBIGUOUS, use_case.state)
        self.assertEqual(2, len(use_case.assertions))
        self.assertTrue(all(
            item.status is AttributeAssertionStatus.CANDIDATE for item in use_case.assertions
        ))

    def test_description_patterns_are_low_confidence_and_evidence_backed(self) -> None:
        _, profile = extract(
            title="Generic Bottle",
            description="A foldable silicone container with 0.6L capacity.",
        )
        material = slot(profile, AttributeDimension.MATERIAL)
        feature = slot(profile, AttributeDimension.FEATURE)
        capacity = slot(profile, AttributeDimension.CAPACITY)
        self.assertEqual("silicone", material.resolved_value[0].value)
        self.assertEqual("foldable", feature.resolved_value[0].value)
        self.assertEqual(0.6, capacity.resolved_value[0].value)
        self.assertTrue(all(
            item.confidence.level is AttributeConfidenceLevel.LOW
            for target_slot in (material, feature, capacity)
            for item in target_slot.assertions
        ))
        self.assertTrue(all(item.source_evidence for item in capacity.assertions))

    def test_output_is_deterministic_for_equivalent_inputs(self) -> None:
        first_snapshot, first = extract(title="600ml leakproof stainless steel bottle")
        second_snapshot, second = extract(title="600ml leakproof stainless steel bottle")
        self.assertEqual(first_snapshot.snapshot_id, second_snapshot.snapshot_id)
        self.assertEqual(first.profile_id, second.profile_id)
        self.assertEqual(canonical_json(first), canonical_json(second))

    def test_repeated_execution_produces_same_result(self) -> None:
        snapshot = build_snapshot(build_bundle(title="20 oz portable plastic bottle"))
        pipeline = AttributeExtractionPipeline()
        first = pipeline.extract(snapshot)
        second = pipeline.extract(snapshot)
        self.assertEqual(ATTRIBUTE_RULES_ENGINE_VERSION, first.extraction_run.extractor_version)
        self.assertEqual(first.profile_id, second.profile_id)
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertIs(first, first.validate_against_registry(ATTRIBUTE_DIMENSION_REGISTRY_V0_1))


if __name__ == "__main__":
    unittest.main()
