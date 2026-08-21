from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.category_product_map import (
    CategoryProductMapBuilderV0_1,
    CategoryProductMapRequest,
    CategoryProductMapSnapshot,
    CategoryScopeType,
    DenominatorType,
    EvidenceAwareMetricStatus,
    build_category_scope,
    unknown_analysis_window,
)
from amazon_product_intelligence.contracts import ProductIdentity, canonical_json, product_id
from amazon_product_intelligence.product_attribute_extraction import (
    AttributeDimension,
    AttributeExtractionPipeline,
    ProductGrain,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "provider_adapters"
    / "v0_1"
    / "sorftime_product_detail.json"
)
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


@lru_cache(maxsize=None)
def profile_for(
    asin: str,
    title: str,
    parent_asin: str | None = None,
):
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    payload["data"]["asin"] = asin
    payload["data"]["title"] = title
    payload["data"]["attributes"] = "{}"
    payload["data"]["description"] = "Generic product description."
    if parent_asin is None:
        payload["data"].pop("parent_asin", None)
    else:
        payload["data"]["parent_asin"] = parent_asin
    bundle = SorftimeAdapterV0_1().adapt(
        payload,
        AdaptationContext(
            provider="sorftime",
            payload_kind="product_detail",
            source_tool="product_detail",
            marketplace="US",
            locale="en-us",
            retrieved_at=RETRIEVED_AT,
            transformed_at=TRANSFORMED_AT,
            collection_run_id=f"collection:category-product-map-test:{asin}",
            sanitized_request={"asin": asin},
            currency="USD",
        ),
    ).bundle.validate()
    identity = ProductIdentity(
        product_id=product_id("US", asin),
        marketplace="US",
        asin=asin,
        parent_asin=parent_asin,
        identity_status="CONFIRMED",
    )
    snapshot = ProductIntelligenceBuilderV0_1().build(
        ProductIntelligenceRequest(
            target_product_identity=identity,
            scope=ProductScope.EXACT_PRODUCT,
            canonical_bundles=(bundle,),
        )
    )
    return AttributeExtractionPipeline().extract(snapshot)


def make_profiles(*titles: str):
    return tuple(
        profile_for(f"B{index:09d}", title)
        for index, title in enumerate(titles, start=1)
    )


def request_for(
    profiles,
    *,
    grain: ProductGrain = ProductGrain.CHILD_ASIN,
    combinations: tuple[tuple[AttributeDimension, ...], ...] = (),
):
    return CategoryProductMapRequest(
        category_scope=build_category_scope(
            scope_type=CategoryScopeType.INPUT_COHORT,
            scope_value="category-map-v0.1-test-cohort",
            inclusion_rule="All supplied marketplace-matching attribute profiles.",
        ),
        marketplace="US",
        analysis_window=unknown_analysis_window(),
        product_grain=grain,
        product_profiles=tuple(profiles),
        combination_dimensions=combinations,
    )


def distribution(snapshot, dimension: AttributeDimension):
    return next(
        item for item in snapshot.attribute_distributions if item.dimension is dimension
    )


def value_metric(target_distribution, value):
    return next(
        item
        for item in target_distribution.values
        if item.canonical_value.value == value
    )


class CategoryProductMapV01Tests(unittest.TestCase):
    def test_material_distribution_is_60_40_among_known_products(self) -> None:
        profiles = make_profiles(
            *("Plastic bottle" for _ in range(6)),
            *("Stainless steel bottle" for _ in range(4)),
        )
        snapshot = CategoryProductMapBuilderV0_1().build(request_for(profiles))
        material = distribution(snapshot, AttributeDimension.MATERIAL)

        self.assertEqual(10, material.total_product_count)
        self.assertEqual(10, material.known_value_count)
        self.assertEqual(0, material.unknown_count)
        self.assertEqual("1", material.attribute_coverage)
        self.assertEqual("0.6", value_metric(material, "plastic").asin_share)
        self.assertEqual("0.4", value_metric(material, "stainless_steel").asin_share)

        denominator = next(
            item
            for item in snapshot.denominator_registry
            if item.denominator_id == material.known_value_denominator_id
        )
        self.assertIs(DenominatorType.KNOWN_ATTRIBUTE_PRODUCTS, denominator.denominator_type)
        self.assertEqual(10, denominator.eligible_product_count)
        self.assertEqual(10, len(denominator.eligible_grain_product_ids))

    def test_unknown_material_is_excluded_from_value_share_denominator(self) -> None:
        profiles = make_profiles(
            "Plastic bottle",
            "Plastic container",
            "Stainless steel bottle",
            "Silicone bottle",
            "Generic item",
        )
        snapshot = CategoryProductMapBuilderV0_1().build(request_for(profiles))
        material = distribution(snapshot, AttributeDimension.MATERIAL)

        self.assertEqual(5, material.total_product_count)
        self.assertEqual(4, material.known_value_count)
        self.assertEqual(1, material.unknown_count)
        self.assertEqual("0.8", material.attribute_coverage)
        self.assertEqual("0.2", material.unknown_rate)
        denominator = next(
            item
            for item in snapshot.denominator_registry
            if item.denominator_id == material.known_value_denominator_id
        )
        self.assertEqual(4, denominator.eligible_product_count)
        self.assertEqual(1, denominator.unknown_count)

    def test_multi_value_feature_memberships_can_sum_above_one(self) -> None:
        profiles = make_profiles(
            "Leakproof portable bottle",
            "Portable bottle",
        )
        snapshot = CategoryProductMapBuilderV0_1().build(request_for(profiles))
        feature = distribution(snapshot, AttributeDimension.FEATURE)

        portable = value_metric(feature, "portable")
        leakproof = value_metric(feature, "leakproof")
        self.assertEqual("1", portable.asin_share)
        self.assertEqual("0.5", leakproof.asin_share)
        self.assertGreater(
            sum(float(item.asin_share) for item in feature.values),
            1.0,
        )
        self.assertEqual(2, feature.known_value_count)

    def test_combination_frequency_has_explicit_denominators_and_unknown_metrics(self) -> None:
        profiles = make_profiles(
            "600ml Plastic bottle",
            "600ml Plastic container",
            "20oz Stainless steel bottle",
            "Generic item",
        )
        dimensions = (AttributeDimension.CAPACITY, AttributeDimension.MATERIAL)
        snapshot = CategoryProductMapBuilderV0_1().build(
            request_for(profiles, combinations=(dimensions,))
        )

        plastic_segment = next(
            item
            for item in snapshot.combination_segments
            if {value.value for value in item.canonical_values} == {0.6, "plastic"}
        )
        self.assertEqual(2, plastic_segment.asin_count)
        self.assertEqual("0.6666666666666666666666666667", plastic_segment.asin_share)
        self.assertEqual("0.75", plastic_segment.coverage)
        share_denominator = next(
            item
            for item in snapshot.denominator_registry
            if item.denominator_id == plastic_segment.share_denominator_id
        )
        self.assertEqual(3, share_denominator.eligible_product_count)
        self.assertIs(
            DenominatorType.COMPLETE_COMBINATION_PRODUCTS,
            share_denominator.denominator_type,
        )
        for metric in (
            plastic_segment.sales_metrics,
            plastic_segment.revenue_metrics,
            plastic_segment.review_metrics,
            plastic_segment.competition_metrics,
        ):
            self.assertIs(EvidenceAwareMetricStatus.UNKNOWN, metric.status)
            self.assertIsNone(metric.value)
            self.assertTrue(metric.limitations)
            self.assertEqual((), metric.evidence_ids)

    def test_child_parent_and_family_grain_produce_explicitly_different_counts(self) -> None:
        parent_asin = "P000000001"
        profiles = (
            profile_for("C000000001", "600ml Plastic bottle", parent_asin),
            profile_for("C000000002", "600ml Plastic bottle", parent_asin),
        )
        builder = CategoryProductMapBuilderV0_1()
        child = builder.build(request_for(profiles, grain=ProductGrain.CHILD_ASIN))
        parent = builder.build(request_for(profiles, grain=ProductGrain.PARENT_ASIN))
        family = builder.build(request_for(profiles, grain=ProductGrain.PRODUCT_FAMILY))

        self.assertEqual(2, child.coverage.included_product_count)
        self.assertEqual(1, parent.coverage.included_product_count)
        self.assertEqual(1, family.coverage.included_product_count)
        self.assertEqual(
            2,
            value_metric(distribution(child, AttributeDimension.MATERIAL), "plastic").asin_count,
        )
        self.assertEqual(
            1,
            value_metric(distribution(parent, AttributeDimension.MATERIAL), "plastic").asin_count,
        )
        self.assertIs(ProductGrain.PARENT_ASIN, parent.product_grain)
        self.assertIs(ProductGrain.PRODUCT_FAMILY, family.product_grain)

    def test_evidence_lineage_reaches_profile_assertion_and_raw_source(self) -> None:
        profile = profile_for("E000000001", "600ml Plastic bottle")
        snapshot = CategoryProductMapBuilderV0_1().build(request_for((profile,)))
        material = distribution(snapshot, AttributeDimension.MATERIAL)
        metric = value_metric(material, "plastic")
        evidence = next(
            item
            for item in snapshot.source_evidence
            if item.evidence_reference_id in metric.evidence_reference_ids
        )

        self.assertEqual(profile.profile_id, evidence.profile_id)
        self.assertEqual(profile.product_identity, evidence.product_identity)
        self.assertEqual("Plastic", evidence.assertion.raw_value)
        self.assertEqual("plastic", evidence.assertion.normalized_value)
        self.assertEqual("US", evidence.source_evidence[0].product_identity.marketplace)
        self.assertEqual("E000000001", evidence.source_evidence[0].product_identity.asin)
        self.assertEqual(RETRIEVED_AT, evidence.source_evidence[0].retrieved_at)
        self.assertEqual(
            "600ml Plastic bottle",
            evidence.source_evidence[0].source_raw_value,
        )

    def test_serialization_is_json_safe_and_strict_round_trip(self) -> None:
        profiles = make_profiles("600ml Plastic bottle", "Generic item")
        snapshot = CategoryProductMapBuilderV0_1().build(request_for(profiles))

        encoded = json.dumps(snapshot.to_dict(), sort_keys=True)
        restored = CategoryProductMapSnapshot.from_dict(json.loads(encoded))
        self.assertEqual(snapshot.map_id, restored.map_id)
        self.assertEqual(canonical_json(snapshot), canonical_json(restored))

    def test_map_id_is_deterministic_and_input_order_independent(self) -> None:
        profiles = make_profiles(
            "600ml Plastic portable bottle",
            "20oz Stainless steel leakproof bottle",
            "Generic item",
        )
        dimensions = (
            (AttributeDimension.CAPACITY, AttributeDimension.MATERIAL),
            (AttributeDimension.FEATURE, AttributeDimension.MATERIAL),
        )
        builder = CategoryProductMapBuilderV0_1()
        first = builder.build(request_for(profiles, combinations=dimensions))
        second = builder.build(
            request_for(tuple(reversed(profiles)), combinations=tuple(reversed(dimensions)))
        )

        self.assertEqual(first.map_id, second.map_id)
        self.assertEqual(canonical_json(first), canonical_json(second))


if __name__ == "__main__":
    unittest.main()
