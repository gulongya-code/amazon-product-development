from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedCandidateBuilder,
    BuyerNeedEvidence,
    build_review_text_evidence,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.buyer_need_map import (
    BuyerNeedMapBuilderV0_1,
    BuyerNeedMapEvidenceType,
    BuyerNeedMapRequest,
    BuyerNeedMapSnapshot,
    DemandMetricConfidenceLevel,
    DemandMetricStatus,
    DemandMetricType,
    EvidencePopulationStatus,
)
from amazon_product_intelligence.category_product_map import (
    CategoryProductMapBuilderV0_1,
    CategoryProductMapRequest,
    CategoryScopeType,
    build_category_scope,
    unknown_analysis_window,
)
from amazon_product_intelligence.contracts import (
    EstimateMethodStatus,
    EvidenceType,
    KeywordIdentity,
    NormalizationStatus,
    ObservationKind,
    ObservedAtStatus,
    PeriodType,
    PresenceStatus,
    ProductIdentity,
    ResultStatus,
    Scope,
    ScopeStatus,
    ScopeType,
    SemanticStatus,
    TimeWindow,
    Unit,
    ValueEnvelope,
    ValueType,
    canonical_json,
    deterministic_id,
    keyword_id,
    product_id,
)
from amazon_product_intelligence.demand_intelligence import (
    DemandLineageReference,
    DemandSourceRecordType,
    KeywordMetricCandidate,
    KeywordMetricEvidenceSet,
    MetricCandidateState,
)
from amazon_product_intelligence.normalization import normalize_keyword_text
from amazon_product_intelligence.product_attribute_extraction import (
    AttributeExtractionPipeline,
    ProductGrain,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)
from amazon_product_intelligence.semantic_clustering import SemanticClusterBuilder


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"
REVIEW_ASIN = "B0G2VV4RBW"


def keyword_for(text: str) -> KeywordIdentity:
    normalized = normalize_keyword_text(text)
    return KeywordIdentity(
        keyword_id=keyword_id("US", "en-us", normalized),
        marketplace="US",
        locale="en-us",
        normalized_text=normalized,
        raw_text=text,
    )


def search_need(text: str) -> tuple[BuyerNeedEvidence, KeywordIdentity]:
    keyword = keyword_for(text)
    candidates = BuyerNeedCandidateBuilder().build(
        build_search_term_text_evidence(keyword)
    )
    if len(candidates) != 1:
        raise AssertionError(f"expected one Buyer Need for {text!r}")
    return candidates[0], keyword


def search_metric(
    keyword: KeywordIdentity,
    value: int,
    *,
    seed: str,
) -> KeywordMetricEvidenceSet:
    observation_id = f"obs:buyer-need-map:{seed}"
    semantic_id = f"obss:buyer-need-map:{seed}"
    fingerprint = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    lineage = DemandLineageReference(
        source_record_id=observation_id,
        source_record_type=DemandSourceRecordType.KEYWORD_METRIC_OBSERVATION,
        semantic_observation_id=semantic_id,
        observation_kind=ObservationKind.KEYWORD_METRIC,
        transformation_run_id=f"transform:{seed}",
        mapping_version="buyer-need-map-test-v0.1",
        raw_evidence_id=f"raw:{seed}",
        collection_run_id=f"collection:{seed}",
        provider="synthetic-test-provider",
        source_tool="keyword_info",
        source_field="search_volume",
        source_bundle_fingerprints=(fingerprint,),
    )
    unit = Unit(
        dimension="search_volume",
        unit_code="searches",
        unit_system=None,
    )
    time = TimeWindow(
        observed_at=None,
        observed_at_status=ObservedAtStatus.UNKNOWN,
        retrieved_at=RETRIEVED_AT,
        period_start="2026-08-01T00:00:00Z",
        period_end="2026-08-31T23:59:59Z",
        period_type=PeriodType.CALENDAR_MONTH,
        timezone="UTC",
    )
    scope = Scope(
        scope_type=ScopeType.KEYWORD,
        scope_status=ScopeStatus.CONFIRMED,
        scope_subject_id=keyword.keyword_id,
    )
    candidate = KeywordMetricCandidate(
        observation_id=observation_id,
        semantic_observation_id=semantic_id,
        keyword_identity=keyword,
        metric="search_volume",
        metric_semantic="monthly_search_volume",
        estimate_method_status=EstimateMethodStatus.DOCUMENTED,
        range=None,
        evidence_type=EvidenceType.PROVIDER_ESTIMATE,
        value=ValueEnvelope(
            presence_status=PresenceStatus.PRESENT,
            raw_value=value,
            normalized_value=value,
            value_type=ValueType.INTEGER,
            unit=unit,
            normalization_status=NormalizationStatus.NORMALIZED,
            semantic_status=SemanticStatus.CONFIRMED,
        ),
        scope=scope,
        time=time,
        provider_semantic="monthlySearchVolume",
        result_status=ResultStatus.POPULATED,
        provider="synthetic-test-provider",
        source_tool="keyword_info",
        lineage_references=(lineage,),
    )
    payload = {
        "keyword_identity": keyword,
        "metric": "search_volume",
        "metric_semantic": "monthly_search_volume",
        "unit": unit,
        "period_type": time.period_type,
        "period_start": time.period_start,
        "period_end": time.period_end,
        "observed_at_status": time.observed_at_status,
        "timezone": time.timezone,
        "scope": scope,
        "evidence_type": EvidenceType.PROVIDER_ESTIMATE,
        "provider_semantic": "monthlySearchVolume",
        "candidate_state": MetricCandidateState.ONE_DISTINCT_PRESENT_VALUE,
        "distinct_present_value_count": 1,
        "candidate_count": 1,
        "presence_counts": {PresenceStatus.PRESENT.value: 1},
        "candidates": (candidate,),
    }
    return KeywordMetricEvidenceSet(
        metric_evidence_set_id=deterministic_id("demand-metric-set", payload),
        **payload,
    )


def category_scope(label: str = "buyer-need-map-test"):
    return build_category_scope(
        scope_type=CategoryScopeType.INPUT_COHORT,
        scope_value=label,
        inclusion_rule="All supplied evidence-backed category members.",
    )


def request_for(
    clusters,
    *,
    needs=None,
    search_sets=(),
    scope=None,
    category_map=None,
    search_status=EvidencePopulationStatus.UNKNOWN,
    review_status=EvidencePopulationStatus.UNKNOWN,
):
    source_needs = (
        tuple(needs)
        if needs is not None
        else tuple(need for cluster in clusters for need in cluster.source_needs)
    )
    return BuyerNeedMapRequest(
        category_scope=scope or category_scope(),
        marketplace="US",
        analysis_window=unknown_analysis_window(),
        buyer_need_evidence=source_needs,
        semantic_clusters=tuple(clusters),
        search_metric_evidence_sets=tuple(search_sets),
        category_product_map=category_map,
        search_population_status=search_status,
        review_population_status=review_status,
    )


def metric(snapshot, cluster_id: str, metric_type: DemandMetricType):
    return next(
        item
        for item in snapshot.demand_metrics
        if item.cluster_id == cluster_id and item.metric_type is metric_type
    )


@lru_cache(maxsize=1)
def review_population_fixture():
    payload_template = json.loads(
        (FIXTURES / "sorftime_product_reviews.json").read_text(encoding="utf-8")
    )
    needs: list[BuyerNeedEvidence] = []
    leak_needs: list[BuyerNeedEvidence] = []
    for index in range(1000):
        raw_text = (
            f"leakproof review mention {index:04d}"
            if index < 100
            else f"easy to clean review mention {index:04d}"
        )
        payload = json.loads(json.dumps(payload_template))
        payload["data"][0]["content"] = raw_text
        bundle = SorftimeAdapterV0_1().adapt(
            payload,
            AdaptationContext(
                provider="sorftime",
                payload_kind="product_reviews",
                source_tool="product_reviews",
                marketplace="US",
                locale="en-us",
                retrieved_at=RETRIEVED_AT,
                transformed_at=TRANSFORMED_AT,
                collection_run_id=f"collection:buyer-need-map-review:{index}",
                sanitized_request={"asin": REVIEW_ASIN},
                currency="USD",
            ),
        ).bundle.validate()
        observation = next(
            item
            for item in bundle.observations
            if item.observation_kind is ObservationKind.REVIEW
        )
        need = BuyerNeedCandidateBuilder().build(
            build_review_text_evidence(observation)
        )[0]
        needs.append(need)
        if index < 100:
            leak_needs.append(need)
    cluster = SemanticClusterBuilder().build(tuple(leak_needs)).clusters[0]
    return tuple(needs), cluster


@lru_cache(maxsize=None)
def profile_for(index: int, title: str):
    payload = json.loads(
        (FIXTURES / "sorftime_product_detail.json").read_text(encoding="utf-8")
    )
    asin = f"B{index:09d}"
    payload["data"]["asin"] = asin
    payload["data"]["title"] = title
    payload["data"]["attributes"] = "{}"
    payload["data"]["description"] = "Generic product description."
    payload["data"].pop("parent_asin", None)
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
            collection_run_id=f"collection:buyer-need-map-product:{index}",
            sanitized_request={"asin": asin},
            currency="USD",
        ),
    ).bundle.validate()
    identity = ProductIdentity(
        product_id=product_id("US", asin),
        marketplace="US",
        asin=asin,
        parent_asin=None,
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


@lru_cache(maxsize=1)
def product_map_fixture():
    scope = category_scope("buyer-need-map-product-coverage")
    profiles = tuple(
        profile_for(
            index,
            "Leakproof bottle" if index <= 30 else "Generic bottle",
        )
        for index in range(1, 101)
    )
    snapshot = CategoryProductMapBuilderV0_1().build(
        CategoryProductMapRequest(
            category_scope=scope,
            marketplace="US",
            analysis_window=unknown_analysis_window(),
            product_grain=ProductGrain.CHILD_ASIN,
            product_profiles=profiles,
            combination_dimensions=(),
        )
    )
    return scope, snapshot


class BuyerNeedMapV01Tests(unittest.TestCase):
    def test_search_demand_share_is_ten_percent(self) -> None:
        need, keyword = search_need("portable")
        other_keyword = keyword_for("unclustered category search")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]
        result = BuyerNeedMapBuilderV0_1().build(
            request_for(
                (cluster,),
                search_sets=(
                    search_metric(keyword, 100, seed="portable-100"),
                    search_metric(other_keyword, 900, seed="other-900"),
                ),
                search_status=EvidencePopulationStatus.COMPLETE,
            )
        )

        measured = metric(result, cluster.cluster_id, DemandMetricType.SEARCH_DEMAND_SHARE)
        self.assertIs(DemandMetricStatus.AVAILABLE, measured.status)
        self.assertEqual("100", measured.numerator_value)
        self.assertEqual("0.1", measured.share)
        denominator = next(
            item for item in result.denominator_registry if item.denominator_id == measured.denominator_id
        )
        self.assertEqual("1000", denominator.value)
        self.assertEqual(2, len(denominator.eligible_ids))

    def test_review_mention_share_is_one_hundred_of_one_thousand(self) -> None:
        needs, cluster = review_population_fixture()
        result = BuyerNeedMapBuilderV0_1().build(
            request_for(
                (cluster,),
                needs=needs,
                review_status=EvidencePopulationStatus.COMPLETE,
            )
        )

        measured = metric(result, cluster.cluster_id, DemandMetricType.REVIEW_MENTION_SHARE)
        self.assertEqual("100", measured.numerator_value)
        self.assertEqual("0.1", measured.share)
        denominator = next(
            item for item in result.denominator_registry if item.denominator_id == measured.denominator_id
        )
        self.assertEqual("1000", denominator.value)
        review_source = cluster.source_needs[0].source_evidence[0].source_reference
        self.assertEqual(REVIEW_ASIN, review_source.product_identity.asin)
        self.assertEqual("sorftime", review_source.provenance.provider)

    def test_product_coverage_is_thirty_of_one_hundred_not_demand(self) -> None:
        need, _ = search_need("leakproof")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]
        scope, category_map = product_map_fixture()
        result = BuyerNeedMapBuilderV0_1().build(
            request_for(
                (cluster,),
                scope=scope,
                category_map=category_map,
            )
        )

        measured = metric(result, cluster.cluster_id, DemandMetricType.PRODUCT_COVERAGE_SHARE)
        self.assertEqual("30", measured.numerator_value)
        self.assertEqual("0.3", measured.share)
        self.assertIn("product_coverage_is_not_demand_share", measured.confidence.basis)
        summary = result.need_clusters[0]
        self.assertEqual(30, len(summary.related_products))
        self.assertEqual("leakproof", summary.related_attributes[0].canonical_value.value)

    def test_missing_search_data_returns_unknown_not_zero(self) -> None:
        need, _ = search_need("portable")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]

        result = BuyerNeedMapBuilderV0_1().build(request_for((cluster,)))
        measured = metric(result, cluster.cluster_id, DemandMetricType.SEARCH_DEMAND_SHARE)

        self.assertIs(DemandMetricStatus.UNKNOWN, measured.status)
        self.assertIsNone(measured.numerator_value)
        self.assertIsNone(measured.share)
        self.assertIs(DemandMetricConfidenceLevel.UNKNOWN, measured.confidence.level)

    def test_every_metric_has_registered_definition_and_denominator(self) -> None:
        need, _ = search_need("portable")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]
        result = BuyerNeedMapBuilderV0_1().build(request_for((cluster,)))

        definitions = {item.metric_id for item in result.metric_registry.definitions}
        denominators = {item.denominator_id for item in result.denominator_registry}
        self.assertEqual(set(DemandMetricType), {item.metric_type for item in result.metric_registry.definitions})
        self.assertTrue(all(item.metric_id in definitions for item in result.demand_metrics))
        self.assertTrue(all(item.denominator_id in denominators for item in result.demand_metrics))

    def test_confidence_and_demand_size_are_separate_fields(self) -> None:
        need, keyword = search_need("portable")
        other = keyword_for("other category demand")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]
        result = BuyerNeedMapBuilderV0_1().build(
            request_for(
                (cluster,),
                search_sets=(
                    search_metric(keyword, 100, seed="confidence-100"),
                    search_metric(other, 900, seed="confidence-900"),
                ),
                search_status=EvidencePopulationStatus.COMPLETE,
            )
        )
        measured = metric(result, cluster.cluster_id, DemandMetricType.SEARCH_DEMAND_SHARE)

        self.assertEqual("0.1", measured.share)
        self.assertIs(DemandMetricConfidenceLevel.HIGH, measured.confidence.level)
        self.assertEqual("1", measured.confidence.evidence_coverage)
        self.assertNotEqual(measured.share, measured.confidence.evidence_coverage)

    def test_cluster_and_search_evidence_lineage_are_embedded(self) -> None:
        need, keyword = search_need("portable")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]
        search = search_metric(keyword, 100, seed="lineage")
        result = BuyerNeedMapBuilderV0_1().build(
            request_for(
                (cluster,),
                search_sets=(search,),
                search_status=EvidencePopulationStatus.COMPLETE,
            )
        )

        by_type = {item.evidence_type for item in result.source_evidence}
        self.assertIn(BuyerNeedMapEvidenceType.SEMANTIC_CLUSTER, by_type)
        self.assertIn(BuyerNeedMapEvidenceType.BUYER_NEED, by_type)
        self.assertIn(BuyerNeedMapEvidenceType.SEARCH_METRIC, by_type)
        embedded_search = next(
            item.source_record
            for item in result.source_evidence
            if item.evidence_type is BuyerNeedMapEvidenceType.SEARCH_METRIC
        )
        self.assertEqual(keyword, embedded_search.keyword_identity)
        self.assertEqual("synthetic-test-provider", embedded_search.candidates[0].provider)
        self.assertTrue(embedded_search.candidates[0].lineage_references)

    def test_deterministic_id_and_json_round_trip(self) -> None:
        need, keyword = search_need("portable")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]
        request = request_for(
            (cluster,),
            search_sets=(search_metric(keyword, 100, seed="deterministic"),),
            search_status=EvidencePopulationStatus.COMPLETE,
        )
        builder = BuyerNeedMapBuilderV0_1()

        first = builder.build(request)
        second = builder.build(request)
        self.assertEqual(first.map_id, second.map_id)
        self.assertEqual(canonical_json(first), canonical_json(second))
        restored = BuyerNeedMapSnapshot.from_dict(json.loads(json.dumps(first.to_dict())))
        self.assertEqual(first, restored)

    def test_multiple_metrics_coexist_without_becoming_opportunity_score(self) -> None:
        need, keyword = search_need("portable")
        cluster = SemanticClusterBuilder().build((need,)).clusters[0]
        result = BuyerNeedMapBuilderV0_1().build(
            request_for(
                (cluster,),
                search_sets=(search_metric(keyword, 100, seed="coexist"),),
                search_status=EvidencePopulationStatus.COMPLETE,
            )
        )

        cluster_metrics = [item for item in result.demand_metrics if item.cluster_id == cluster.cluster_id]
        self.assertEqual(set(DemandMetricType), {item.metric_type for item in cluster_metrics})
        self.assertEqual(5, len(cluster_metrics))
        self.assertFalse(hasattr(result, "opportunity_score"))
        self.assertFalse(hasattr(result.need_clusters[0], "recommendation"))


if __name__ == "__main__":
    unittest.main()
