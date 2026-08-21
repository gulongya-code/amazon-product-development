from __future__ import annotations

from functools import lru_cache
import hashlib
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedCandidateBuilder,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.buyer_need_map import (
    BuyerNeedMapBuilderV0_1,
    BuyerNeedMapEvidenceType,
    BuyerNeedMapRequest,
    DemandMetricConfidence,
    DemandMetricConfidenceLevel,
    DemandMetricResult,
    DemandMetricStatus,
    DemandMetricType,
    EvidencePopulationStatus,
)
from amazon_product_intelligence.category_product_map import (
    CategoryMapSourceEvidence,
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
from amazon_product_intelligence.supply_demand_gap import (
    GapClassifier,
    GapConfidenceLevel,
    GapSignalStatus,
    GapStrength,
    GapType,
    SupplyDemandGapBuilderV0_1,
    SupplyDemandGapRequest,
    SupplyDemandGapSnapshot,
    SupplyMetricType,
)


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


def keyword_for(text: str) -> KeywordIdentity:
    normalized = normalize_keyword_text(text)
    return KeywordIdentity(
        keyword_id=keyword_id("US", "en-us", normalized),
        marketplace="US",
        locale="en-us",
        normalized_text=normalized,
        raw_text=text,
    )


@lru_cache(maxsize=1)
def portable_need_and_cluster():
    keyword = keyword_for("portable")
    need = BuyerNeedCandidateBuilder().build(build_search_term_text_evidence(keyword))[0]
    cluster = SemanticClusterBuilder().build((need,)).clusters[0]
    return keyword, need, cluster


def search_metric(keyword: KeywordIdentity, value: int, *, seed: str) -> KeywordMetricEvidenceSet:
    observation_id = f"obs:supply-demand-gap:{seed}"
    semantic_id = f"obss:supply-demand-gap:{seed}"
    fingerprint = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    lineage = DemandLineageReference(
        source_record_id=observation_id,
        source_record_type=DemandSourceRecordType.KEYWORD_METRIC_OBSERVATION,
        semantic_observation_id=semantic_id,
        observation_kind=ObservationKind.KEYWORD_METRIC,
        transformation_run_id=f"transform:{seed}",
        mapping_version="supply-demand-gap-test-v0.1",
        raw_evidence_id=f"raw:{seed}",
        collection_run_id=f"collection:{seed}",
        provider="synthetic-gap-test-provider",
        source_tool="keyword_info",
        source_field="search_volume",
        source_bundle_fingerprints=(fingerprint,),
    )
    unit = Unit(dimension="search_volume", unit_code="searches", unit_system=None)
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
        provider="synthetic-gap-test-provider",
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


def category_scope():
    return build_category_scope(
        scope_type=CategoryScopeType.INPUT_COHORT,
        scope_value="supply-demand-gap-test",
        inclusion_rule="All ten supplied evidence-backed category members.",
    )


@lru_cache(maxsize=None)
def profile_for(index: int, title: str):
    payload = json.loads(
        (FIXTURES / "sorftime_product_detail.json").read_text(encoding="utf-8")
    )
    asin = f"B{index:09d}"
    payload["data"]["asin"] = asin
    payload["data"]["title"] = title
    payload["data"]["attributes"] = "{}"
    payload["data"]["description"] = "Evidence-backed bottle description."
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
            collection_run_id=f"collection:supply-demand-gap-product:{index}:{title}",
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


@lru_cache(maxsize=None)
def profiles_for(portable_count: int):
    return tuple(
        profile_for(
            index,
            "Portable travel bottle" if index <= portable_count else "Leakproof bottle",
        )
        for index in range(1, 11)
    )


@lru_cache(maxsize=None)
def product_map_for(portable_count: int):
    profiles = profiles_for(portable_count)
    return CategoryProductMapBuilderV0_1().build(
        CategoryProductMapRequest(
            category_scope=category_scope(),
            marketplace="US",
            analysis_window=unknown_analysis_window(),
            product_grain=ProductGrain.CHILD_ASIN,
            product_profiles=profiles,
            combination_dimensions=(),
        )
    )


def buyer_need_map_for(
    *,
    demand_value: int | None,
    portable_count: int,
    population_status: EvidencePopulationStatus = EvidencePopulationStatus.COMPLETE,
):
    keyword, need, cluster = portable_need_and_cluster()
    search_sets = ()
    search_status = EvidencePopulationStatus.UNKNOWN
    if demand_value is not None:
        search_sets = (
            search_metric(keyword, demand_value, seed=f"portable-{demand_value}-{population_status.value}"),
            search_metric(
                keyword_for("other category demand"),
                100 - demand_value,
                seed=f"other-{demand_value}-{population_status.value}",
            ),
        )
        search_status = population_status
    category_map = product_map_for(portable_count)
    snapshot = BuyerNeedMapBuilderV0_1().build(
        BuyerNeedMapRequest(
            category_scope=category_scope(),
            marketplace="US",
            analysis_window=unknown_analysis_window(),
            buyer_need_evidence=(need,),
            semantic_clusters=(cluster,),
            search_metric_evidence_sets=search_sets,
            category_product_map=category_map,
            search_population_status=search_status,
            review_population_status=EvidencePopulationStatus.UNKNOWN,
        )
    )
    return snapshot, category_map, cluster.cluster_id, profiles_for(portable_count)


def gap_for(
    demand_percent: int | None,
    supply_count: int,
    *,
    population_status: EvidencePopulationStatus = EvidencePopulationStatus.COMPLETE,
):
    buyer_map, category_map, cluster_id, profiles = buyer_need_map_for(
        demand_value=demand_percent,
        portable_count=supply_count,
        population_status=population_status,
    )
    return SupplyDemandGapBuilderV0_1().build(
        SupplyDemandGapRequest(
            buyer_need_map=buyer_map,
            category_product_map=category_map,
            need_cluster_id=cluster_id,
            product_attribute_profiles=profiles,
        )
    )


def supply_metric(snapshot, metric_type: SupplyMetricType):
    return next(item for item in snapshot.supply_metrics if item.metric_type is metric_type)


class SupplyDemandGapV01Tests(unittest.TestCase):
    def test_high_demand_low_supply(self) -> None:
        result = gap_for(30, 1)

        self.assertIs(GapType.HIGH_DEMAND_LOW_SUPPLY, result.gap_type)
        coverage = supply_metric(result, SupplyMetricType.PRODUCT_COVERAGE_SHARE)
        self.assertEqual("0.1", coverage.value)
        search = next(
            item
            for item in result.demand_metrics
            if item.metric_type is DemandMetricType.SEARCH_DEMAND_SHARE
        )
        self.assertEqual("0.3", search.share)

    def test_high_demand_high_supply(self) -> None:
        result = gap_for(30, 3)
        self.assertIs(GapType.HIGH_DEMAND_HIGH_SUPPLY, result.gap_type)

    def test_low_demand_high_supply(self) -> None:
        result = gap_for(10, 3)
        self.assertIs(GapType.LOW_DEMAND_HIGH_SUPPLY, result.gap_type)

    def test_low_demand_low_supply(self) -> None:
        result = gap_for(10, 1)
        self.assertIs(GapType.LOW_DEMAND_LOW_SUPPLY, result.gap_type)

    def test_missing_demand_is_insufficient_evidence_not_zero(self) -> None:
        result = gap_for(None, 3)

        self.assertIs(GapType.INSUFFICIENT_EVIDENCE, result.gap_type)
        self.assertIs(GapStrength.UNKNOWN, result.gap_strength)
        self.assertIs(GapConfidenceLevel.UNKNOWN, result.confidence.level)

    def test_demand_confidence_changes_gap_strength(self) -> None:
        complete = gap_for(30, 1, population_status=EvidencePopulationStatus.COMPLETE)
        search = next(
            item
            for item in complete.demand_metrics
            if item.metric_type is DemandMetricType.SEARCH_DEMAND_SHARE
        )
        lowered_confidence = DemandMetricConfidence(
            level=DemandMetricConfidenceLevel.MEDIUM,
            evidence_coverage=search.confidence.evidence_coverage,
            basis=tuple(sorted({*search.confidence.basis, "test_partial_population"})),
        )
        partial_payload = {
            "metric_id": search.metric_id,
            "metric_type": search.metric_type,
            "cluster_id": search.cluster_id,
            "status": DemandMetricStatus.PARTIAL,
            "numerator_value": search.numerator_value,
            "denominator_id": search.denominator_id,
            "share": search.share,
            "confidence": lowered_confidence,
            "evidence_reference_ids": search.evidence_reference_ids,
            "limitations": ("DECLARED_SEARCH_POPULATION_PARTIAL",),
        }
        partial_search = DemandMetricResult(
            metric_result_id=deterministic_id("demand-metric-result", partial_payload),
            **partial_payload,
        )
        partial_demand = tuple(
            partial_search
            if item.metric_type is DemandMetricType.SEARCH_DEMAND_SHARE
            else item
            for item in complete.demand_metrics
        )
        classifier = GapClassifier()
        partial_type = classifier.classify(partial_demand, complete.supply_metrics)
        partial_confidence = classifier.confidence(
            partial_demand,
            complete.supply_metrics,
            evidence_completeness="1",
        )
        partial_strength = classifier.strength(
            partial_type,
            partial_demand,
            complete.supply_metrics,
            partial_confidence,
        )

        self.assertIs(GapType.HIGH_DEMAND_LOW_SUPPLY, complete.gap_type)
        self.assertIs(GapType.HIGH_DEMAND_LOW_SUPPLY, partial_type)
        self.assertIs(GapStrength.MEDIUM, complete.gap_strength)
        self.assertIs(GapStrength.LOW, partial_strength)
        self.assertNotEqual(complete.confidence.level, partial_confidence.level)

    def test_supply_evidence_preserves_asin_profile_and_attribute_lineage(self) -> None:
        result = gap_for(30, 1)

        self.assertEqual(10, len(result.evidence.product_identities))
        self.assertTrue(all(item.asin for item in result.evidence.product_identities))
        self.assertEqual(10, len(result.evidence.profile_ids))
        category_refs = {
            item.evidence_reference_id: item
            for item in result.evidence.category_product_map.source_evidence
        }
        referenced = set(result.evidence.supply_source_evidence_reference_ids) - {
            result.evidence.category_product_map.map_id
        }
        self.assertTrue(referenced)
        source = category_refs[next(iter(referenced))]
        self.assertIsInstance(source, CategoryMapSourceEvidence)
        self.assertTrue(source.assertion.raw_value)
        self.assertTrue(source.source_evidence[0].lineage_reference.raw_evidence_id)

    def test_demand_evidence_preserves_cluster_search_term_and_lineage(self) -> None:
        result = gap_for(30, 1)
        source_by_id = {
            item.evidence_reference_id: item
            for item in result.evidence.buyer_need_map.source_evidence
        }
        sources = [
            source_by_id[item]
            for item in result.evidence.demand_source_evidence_reference_ids
        ]

        self.assertIn(
            BuyerNeedMapEvidenceType.SEMANTIC_CLUSTER,
            {item.evidence_type for item in sources},
        )
        search = next(
            item.source_record
            for item in sources
            if item.evidence_type is BuyerNeedMapEvidenceType.SEARCH_METRIC
            and item.source_record.keyword_identity.raw_text == "portable"
        )
        self.assertEqual("synthetic-gap-test-provider", search.candidates[0].provider)
        self.assertTrue(search.candidates[0].lineage_references)

    def test_deterministic_id_and_json_round_trip(self) -> None:
        first = gap_for(30, 1)
        second = gap_for(30, 1)

        self.assertEqual(first.gap_id, second.gap_id)
        self.assertEqual(canonical_json(first), canonical_json(second))
        restored = SupplyDemandGapSnapshot.from_dict(
            json.loads(json.dumps(first.to_dict()))
        )
        self.assertEqual(first, restored)

    def test_unknown_context_is_retained_and_no_opportunity_output_exists(self) -> None:
        result = gap_for(30, 1)
        competition = supply_metric(result, SupplyMetricType.COMPETITION_EVIDENCE)

        self.assertIs(GapSignalStatus.UNKNOWN, competition.status)
        self.assertIsNone(competition.value)
        self.assertFalse(hasattr(result, "opportunity_score"))
        self.assertFalse(hasattr(result, "recommendation"))


if __name__ == "__main__":
    unittest.main()
