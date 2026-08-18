from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.demand_intelligence as demand
from amazon_product_intelligence.adapters import AdaptationContext, XiYouAdapterV0_1
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    Channel,
    KeywordIdentity,
    KeywordMetricObservation,
    NormalizationStatus,
    PresenceStatus,
    ProductKeywordRelationshipObservation,
    QueryExecutionOutcome,
    RelationshipDirection,
    ResultStatus,
    SemanticStatus,
    ValueEnvelope,
    canonical_json,
    deterministic_id,
    keyword_id,
    query_execution_id,
)
from amazon_product_intelligence.demand_intelligence import (
    DEMAND_INTELLIGENCE_RULESET_VERSION,
    DemandIdentityCollisionError,
    DemandIntelligenceBuilderV0_1,
    DemandIntelligenceRequest,
    DemandIntelligenceSnapshotV0_1,
    DemandIntelligenceValidationError,
    DemandSerializationError,
    DemandSubjectNotFoundError,
    MetricCandidateState,
)


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEMAND_SOURCE = REPOSITORY_ROOT / "src" / "amazon_product_intelligence" / "demand_intelligence"
PYTHON_SOURCE = REPOSITORY_ROOT / "src"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def context(payload_kind: str, *, request: dict[str, object] | None = None) -> AdaptationContext:
    source_tools = {
        "asin_info": "get_asin_info",
        "keyword_info": "get_keyword_info",
        "keyword_asin_analysis": "get_keyword_asin_analysis",
        "asin_keywords": "get_asin_keywords",
    }
    return AdaptationContext(
        provider="xiyou",
        payload_kind=payload_kind,
        source_tool=source_tools[payload_kind],
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:xiyou:{payload_kind}:demand-fixture",
        sanitized_request=request or {},
        currency="USD",
    )


def adapt(
    fixture_name: str,
    payload_kind: str,
    *,
    request: dict[str, object] | None = None,
    payload: dict[str, object] | None = None,
):
    return XiYouAdapterV0_1().adapt(
        load_fixture(fixture_name) if payload is None else payload,
        context(payload_kind, request=request),
    )


def first_keyword(bundle: CanonicalEvidenceBundle, metric: str | None = None) -> KeywordIdentity:
    for observation in bundle.observations:
        if isinstance(observation, KeywordMetricObservation) and (
            metric is None or observation.metric == metric
        ):
            return observation.keyword
    raise AssertionError("fixture has no matching keyword metric")


def snapshot(target: KeywordIdentity, *bundles: CanonicalEvidenceBundle) -> DemandIntelligenceSnapshotV0_1:
    return DemandIntelligenceBuilderV0_1().build(
        DemandIntelligenceRequest(
            target_keyword_identity=target,
            canonical_bundles=tuple(bundles),
        )
    )


def rewrite_query_outcome(
    bundle: CanonicalEvidenceBundle, outcome: QueryExecutionOutcome
) -> CanonicalEvidenceBundle:
    old = bundle.query_execution_records[0]
    new_id = query_execution_id(
        query_keyword=old.query_keyword,
        query_product=old.query_product,
        direction=old.direction,
        outcome=outcome,
        related_relationship_observation_ids=(),
        provenance=old.provenance,
        quality_issue_ids=old.quality_issue_ids,
    )
    new_query = replace(
        old,
        query_execution_id=new_id,
        outcome=outcome,
        related_relationship_observation_ids=(),
    )
    old_id = old.query_execution_id
    runs = tuple(
        replace(
            run,
            output_query_execution_ids=tuple(
                new_id if item == old_id else item for item in run.output_query_execution_ids
            ),
        )
        for run in bundle.transformation_runs
    )
    return CanonicalEvidenceBundle(
        transformation_runs=runs,
        observations=bundle.observations,
        conflicts=bundle.conflicts,
        resolutions=bundle.resolutions,
        quality_issues=bundle.quality_issues,
        raw_evidence_references=bundle.raw_evidence_references,
        query_execution_records=(new_query,),
    )


def reverse_non_result_for_product(
    bundle: CanonicalEvidenceBundle,
    product,
    outcome: QueryExecutionOutcome,
) -> CanonicalEvidenceBundle:
    old = bundle.query_execution_records[0]
    provenance = replace(
        old.provenance,
        source_record_identity=product.product_id,
    )
    new_id = query_execution_id(
        query_keyword=None,
        query_product=product,
        direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
        outcome=outcome,
        related_relationship_observation_ids=(),
        provenance=provenance,
        quality_issue_ids=(),
    )
    query = replace(
        old,
        query_execution_id=new_id,
        query_keyword=None,
        query_product=product,
        outcome=outcome,
        related_relationship_observation_ids=(),
        provenance=provenance,
        quality_issue_ids=(),
    )
    runs = tuple(
        replace(
            run,
            output_observation_ids=(),
            quality_issue_ids=(),
            output_query_execution_ids=(new_id,),
        )
        for run in bundle.transformation_runs
    )
    return CanonicalEvidenceBundle(
        transformation_runs=runs,
        observations=(),
        conflicts=(),
        resolutions=(),
        quality_issues=(),
        raw_evidence_references=bundle.raw_evidence_references,
        query_execution_records=(query,),
    )


def rewrite_one_metric_unknown(bundle: CanonicalEvidenceBundle) -> CanonicalEvidenceBundle:
    old = next(
        item
        for item in bundle.observations
        if isinstance(item, KeywordMetricObservation) and item.metric == "search_volume"
    )
    new_id = "obs:test-demand-unknown-metric"
    value = ValueEnvelope(
        presence_status=PresenceStatus.UNKNOWN,
        raw_value=None,
        normalized_value=None,
        value_type=old.value.value_type,
        unit=old.value.unit,
        normalization_status=NormalizationStatus.NOT_ATTEMPTED,
        semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
    )
    new_observation = replace(
        old,
        observation_id=new_id,
        value=value,
        result_status=ResultStatus.PARTIAL,
    )
    observations = tuple(
        new_observation if item.observation_id == old.observation_id else item
        for item in bundle.observations
    )
    runs = tuple(
        replace(
            run,
            output_observation_ids=tuple(
                new_id if item == old.observation_id else item
                for item in run.output_observation_ids
            ),
        )
        for run in bundle.transformation_runs
    )
    return CanonicalEvidenceBundle(
        transformation_runs=runs,
        observations=observations,
        conflicts=bundle.conflicts,
        resolutions=bundle.resolutions,
        quality_issues=bundle.quality_issues,
        raw_evidence_references=bundle.raw_evidence_references,
        query_execution_records=bundle.query_execution_records,
    )


def rewrite_one_relationship_unknown_channel(
    bundle: CanonicalEvidenceBundle,
) -> CanonicalEvidenceBundle:
    old_observation = next(
        item
        for item in bundle.observations
        if isinstance(item, ProductKeywordRelationshipObservation)
        and item.channel is Channel.ORGANIC
    )
    new_observation_id = "obs:test-demand-unknown-channel"
    new_observation = replace(
        old_observation,
        observation_id=new_observation_id,
        relationship_id="rel:test-demand-unknown-channel",
        channel=Channel.UNKNOWN,
    )
    old_query = bundle.query_execution_records[0]
    new_related = tuple(
        new_observation_id if item == old_observation.observation_id else item
        for item in old_query.related_relationship_observation_ids
    )
    new_query_id = query_execution_id(
        query_keyword=old_query.query_keyword,
        query_product=old_query.query_product,
        direction=old_query.direction,
        outcome=old_query.outcome,
        related_relationship_observation_ids=new_related,
        provenance=old_query.provenance,
        quality_issue_ids=old_query.quality_issue_ids,
    )
    new_query = replace(
        old_query,
        query_execution_id=new_query_id,
        related_relationship_observation_ids=new_related,
    )
    observations = tuple(
        new_observation if item.observation_id == old_observation.observation_id else item
        for item in bundle.observations
    )
    runs = tuple(
        replace(
            run,
            output_observation_ids=tuple(
                new_observation_id if item == old_observation.observation_id else item
                for item in run.output_observation_ids
            ),
            output_query_execution_ids=tuple(
                new_query_id if item == old_query.query_execution_id else item
                for item in run.output_query_execution_ids
            ),
        )
        for run in bundle.transformation_runs
    )
    return CanonicalEvidenceBundle(
        transformation_runs=runs,
        observations=observations,
        conflicts=bundle.conflicts,
        resolutions=bundle.resolutions,
        quality_issues=bundle.quality_issues,
        raw_evidence_references=bundle.raw_evidence_references,
        query_execution_records=(new_query,),
    )


def synthetic_provider_metric_bundle(
    source_bundle: CanonicalEvidenceBundle,
    *,
    observation_id: str = "obs:synthetic-provider-search-volume",
    keep_original_observation_id: bool = False,
    value: int | None = None,
) -> CanonicalEvidenceBundle:
    old = next(
        item
        for item in source_bundle.observations
        if isinstance(item, KeywordMetricObservation) and item.metric == "search_volume"
    )
    old_run = source_bundle.transformation_runs[0]
    raw_id = "raw:synthetic-provider-keyword-info"
    run_id = "transform:synthetic-provider-keyword-info"
    collection_id = "collection:synthetic-provider-keyword-info"
    transformation = replace(
        old.provenance.transformation,
        collection_run_id=collection_id,
        mapping_version="synthetic_keyword_mapping_v1",
        transformation_run_id=run_id,
        raw_evidence_reference=raw_id,
    )
    provenance = replace(
        old.provenance,
        provider="synthetic-provider",
        source_tool="synthetic_keyword_info",
        source_record_identity="synthetic:plastic-spoons",
        transformation=transformation,
    )
    new_value = old.value
    if value is not None:
        new_value = replace(old.value, raw_value=value, normalized_value=value)
    new_observation = replace(
        old,
        semantic_observation_id="obss:synthetic-provider-search-volume",
        observation_id=old.observation_id if keep_original_observation_id else observation_id,
        provenance=provenance,
        value=new_value,
        quality_issue_ids=(),
    )
    run = replace(
        old_run,
        provider="synthetic-provider",
        collection_run_id=collection_id,
        mapping_version="synthetic_keyword_mapping_v1",
        transformation_run_id=run_id,
        input_raw_evidence_references=(raw_id,),
        output_observation_ids=(new_observation.observation_id,),
        quality_issue_ids=(),
        output_query_execution_ids=(),
    )
    return CanonicalEvidenceBundle(
        transformation_runs=(run,),
        observations=(new_observation,),
        conflicts=(),
        resolutions=(),
        quality_issues=(),
        raw_evidence_references=(raw_id,),
        query_execution_records=(),
    )


class DemandFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.keyword_info = adapt("xiyou_keyword_info.json", "keyword_info")
        cls.forward = adapt(
            "xiyou_keyword_forward_populated.json",
            "keyword_asin_analysis",
            request={"keyword": "plastic spoons"},
        )
        cls.forward_empty = adapt(
            "xiyou_keyword_forward_empty.json",
            "keyword_asin_analysis",
            request={"keyword": "1/2 ball valve"},
        )
        cls.reverse = adapt(
            "xiyou_asin_keywords_reverse.json",
            "asin_keywords",
            request={"asin": "B0G2VV4RBW"},
        )
        for result in (
            cls.keyword_info,
            cls.forward,
            cls.forward_empty,
            cls.reverse,
        ):
            if not result.succeeded:
                raise AssertionError(result.errors)
        cls.plastic = first_keyword(cls.keyword_info.bundle, "search_volume")
        cls.ball = cls.forward_empty.bundle.query_execution_records[0].query_keyword
        if cls.ball is None:
            raise AssertionError("forward empty fixture has no query keyword")
        cls.plastic_snapshot = snapshot(
            cls.plastic, cls.keyword_info.bundle, cls.forward.bundle
        )
        cls.asymmetric_snapshot = snapshot(
            cls.ball, cls.forward_empty.bundle, cls.reverse.bundle
        )


class PublicApiAndBoundaryTests(DemandFixtureCase):
    def test_public_api_is_explicit(self) -> None:
        expected = {
            "DEMAND_INTELLIGENCE_RULESET_VERSION",
            "DemandIntelligenceRequest",
            "DemandIntelligenceSnapshotV0_1",
            "DemandIntelligenceBuilderV0_1",
            "DemandIntelligenceError",
            "DemandIntelligenceValidationError",
            "DemandSubjectNotFoundError",
            "DemandIdentityCollisionError",
            "DemandSerializationError",
            "MetricCandidateState",
            "DemandSourceRecordType",
            "DemandLineageReference",
            "KeywordMetricCandidate",
            "KeywordMetricEvidenceSet",
            "RelationshipEvidenceItem",
            "RelationshipEvidenceGroup",
            "QueryExecutionEvidenceItem",
            "RelatedProductEvidence",
            "OutOfScopeEvidenceReference",
            "DemandQualityIssueReference",
            "DemandIntelligenceDiagnostic",
            "DemandEvidenceCoverage",
        }
        self.assertEqual(set(demand.__all__), expected)
        self.assertEqual(DEMAND_INTELLIGENCE_RULESET_VERSION, "demand-intelligence-v0.1")

    def test_source_dependency_boundary_excludes_adapters_and_product_intelligence(self) -> None:
        for source in DEMAND_SOURCE.glob("*.py"):
            text = source.read_text(encoding="utf-8")
            tree = ast.parse(text)
            imported = {
                node.module
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module is not None
            }
            self.assertNotIn("amazon_product_intelligence.adapters", imported)
            self.assertNotIn("amazon_product_intelligence.product_intelligence", imported)
            self.assertNotIn("AdapterResult", text)
            self.assertNotIn("AdaptationContext", text)
            self.assertNotIn("ProductIntelligenceSnapshot", text)

    def test_public_request_accepts_only_canonical_bundles(self) -> None:
        with self.assertRaises(DemandIntelligenceValidationError):
            DemandIntelligenceRequest(
                target_keyword_identity=self.plastic,
                canonical_bundles=({"raw": "provider-json"},),  # type: ignore[arg-type]
            )
        with self.assertRaises(DemandIntelligenceValidationError):
            DemandIntelligenceBuilderV0_1().build(self.keyword_info)  # type: ignore[arg-type]


class KeywordIdentityTests(DemandFixtureCase):
    def test_exact_canonical_identity_matches(self) -> None:
        self.assertEqual(self.plastic_snapshot.target_keyword_identity, self.plastic)
        self.assertTrue(self.plastic_snapshot.keyword_metric_evidence_sets)

    def test_raw_text_difference_is_not_normalized_by_demand_layer(self) -> None:
        different_raw_text = KeywordIdentity(
            keyword_id=self.plastic.keyword_id,
            marketplace=self.plastic.marketplace,
            locale=self.plastic.locale,
            normalized_text=self.plastic.normalized_text,
            raw_text="Plastic Spoons",
        )
        with self.assertRaises(DemandSubjectNotFoundError):
            snapshot(different_raw_text, self.keyword_info.bundle)

    def test_marketplace_separation_is_exact(self) -> None:
        canada = KeywordIdentity(
            keyword_id=keyword_id("CA", self.plastic.locale, self.plastic.normalized_text),
            marketplace="CA",
            locale=self.plastic.locale,
            normalized_text=self.plastic.normalized_text,
            raw_text=self.plastic.raw_text,
        )
        with self.assertRaises(DemandSubjectNotFoundError):
            snapshot(canada, self.keyword_info.bundle)

    def test_similar_fixture_text_with_different_raw_identity_is_not_merged(self) -> None:
        upper_raw = next(
            item.keyword
            for item in self.keyword_info.bundle.observations
            if isinstance(item, KeywordMetricObservation)
            and item.keyword.normalized_text == "1/2 ball valve"
        )
        self.assertEqual(upper_raw.keyword_id, self.ball.keyword_id)
        self.assertNotEqual(upper_raw, self.ball)
        upper_snapshot = snapshot(upper_raw, self.keyword_info.bundle)
        self.assertTrue(upper_snapshot.keyword_metric_evidence_sets)
        self.assertFalse(upper_snapshot.query_execution_evidence)


class KeywordMetricEvidenceTests(DemandFixtureCase):
    def test_four_metric_families_remain_separate(self) -> None:
        metrics = {item.metric for item in self.plastic_snapshot.keyword_metric_evidence_sets}
        self.assertEqual(
            metrics,
            {"search_volume", "aba_search_frequency_rank", "cpc", "competition_difficulty"},
        )
        self.assertTrue(
            all(
                item.candidate_state is MetricCandidateState.ONE_DISTINCT_PRESENT_VALUE
                for item in self.plastic_snapshot.keyword_metric_evidence_sets
            )
        )

    def test_metric_candidates_preserve_canonical_semantics_without_aggregation(self) -> None:
        for evidence_set in self.plastic_snapshot.keyword_metric_evidence_sets:
            candidate = evidence_set.candidates[0]
            self.assertEqual(candidate.metric, evidence_set.metric)
            self.assertEqual(candidate.metric_semantic, evidence_set.metric_semantic)
            self.assertEqual(candidate.value.unit, evidence_set.unit)
            self.assertEqual(candidate.scope, evidence_set.scope)
            self.assertEqual(candidate.evidence_type, evidence_set.evidence_type)
            self.assertEqual(candidate.time.period_type, evidence_set.period_type)
            self.assertFalse(hasattr(evidence_set, "preferred_value"))
            self.assertFalse(hasattr(evidence_set, "resolved_value"))

    def test_explicit_null_is_not_missing(self) -> None:
        source = load_fixture("xiyou_keyword_info.json")
        source["data"]["list"] = [deepcopy(source["data"]["list"][1])]  # type: ignore[index]
        source["data"]["total"] = 1  # type: ignore[index]
        result = adapt("xiyou_keyword_info.json", "keyword_info", payload=source)
        target = first_keyword(result.bundle)
        built = snapshot(target, result.bundle)
        by_metric = {item.metric: item for item in built.keyword_metric_evidence_sets}
        self.assertEqual(
            by_metric["search_volume"].candidates[0].value.presence_status,
            PresenceStatus.EXPLICIT_NULL,
        )
        self.assertEqual(
            by_metric["search_volume"].candidate_state,
            MetricCandidateState.NO_PRESENT_CANDIDATE,
        )

    def test_missing_source_field_is_not_synthesized(self) -> None:
        source = load_fixture("xiyou_keyword_info.json")
        row = deepcopy(source["data"]["list"][1])  # type: ignore[index]
        del row["abaReport"]
        source["data"]["list"] = [row]  # type: ignore[index]
        source["data"]["total"] = 1  # type: ignore[index]
        result = adapt("xiyou_keyword_info.json", "keyword_info", payload=source)
        target = first_keyword(result.bundle)
        built = snapshot(target, result.bundle)
        self.assertNotIn(
            "search_volume", {item.metric for item in built.keyword_metric_evidence_sets}
        )

    def test_numeric_zero_remains_present(self) -> None:
        source = load_fixture("xiyou_keyword_info.json")
        row = source["data"]["list"][0]  # type: ignore[index]
        row["abaReport"]["weeklySearchVolume"] = 0  # type: ignore[index]
        row["abaReport"]["searchFrequencyRank"] = 0  # type: ignore[index]
        row["competitiveDifficulty"] = 0  # type: ignore[index]
        row["costPerClick"] = {"minSuggestedBid": "0", "maxSuggestedBid": "0", "value": "0"}  # type: ignore[index]
        source["data"]["list"] = [row]  # type: ignore[index]
        source["data"]["total"] = 1  # type: ignore[index]
        result = adapt("xiyou_keyword_info.json", "keyword_info", payload=source)
        built = snapshot(first_keyword(result.bundle), result.bundle)
        for evidence_set in built.keyword_metric_evidence_sets:
            self.assertEqual(evidence_set.candidates[0].value.normalized_value, 0)
            self.assertEqual(
                evidence_set.candidates[0].value.presence_status, PresenceStatus.PRESENT
            )

    def test_unknown_presence_is_retained(self) -> None:
        bundle = rewrite_one_metric_unknown(self.keyword_info.bundle)
        built = snapshot(self.plastic, bundle)
        search_volume = next(
            item for item in built.keyword_metric_evidence_sets if item.metric == "search_volume"
        )
        self.assertEqual(
            search_volume.candidates[0].value.presence_status, PresenceStatus.UNKNOWN
        )
        self.assertEqual(
            search_volume.candidate_state, MetricCandidateState.NO_PRESENT_CANDIDATE
        )

    def test_multi_provider_candidates_remain_unresolved(self) -> None:
        second = synthetic_provider_metric_bundle(
            self.keyword_info.bundle, value=50000
        )
        built = snapshot(self.plastic, self.keyword_info.bundle, second)
        search_volume = next(
            item for item in built.keyword_metric_evidence_sets if item.metric == "search_volume"
        )
        self.assertEqual(search_volume.candidate_count, 2)
        self.assertEqual(
            search_volume.candidate_state,
            MetricCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES,
        )
        self.assertEqual(
            {item.provider for item in search_volume.candidates},
            {"xiyou", "synthetic-provider"},
        )
        self.assertIn("synthetic-provider", built.evidence_coverage.providers)


class RelationshipAndQueryEvidenceTests(DemandFixtureCase):
    def test_relationships_are_separated_by_direction_and_channel(self) -> None:
        plastic_boundaries = {
            (group.direction, group.channel)
            for group in self.plastic_snapshot.relationship_evidence_groups
        }
        self.assertIn((RelationshipDirection.KEYWORD_TO_PRODUCT, Channel.ORGANIC), plastic_boundaries)
        self.assertIn((RelationshipDirection.KEYWORD_TO_PRODUCT, Channel.SPONSORED), plastic_boundaries)
        reverse_boundaries = {
            (group.direction, group.channel)
            for group in self.asymmetric_snapshot.relationship_evidence_groups
        }
        self.assertIn((RelationshipDirection.PRODUCT_TO_KEYWORD, Channel.ORGANIC), reverse_boundaries)
        self.assertIn((RelationshipDirection.PRODUCT_TO_KEYWORD, Channel.SPONSORED), reverse_boundaries)

    def test_rank_and_traffic_are_retained_per_observation(self) -> None:
        records = [
            item
            for group in self.plastic_snapshot.relationship_evidence_groups
            for item in group.records
        ]
        self.assertTrue(any(item.rank is not None for item in records))
        self.assertTrue(any(item.traffic is not None for item in records))
        self.assertFalse(any(hasattr(item, "aggregate_rank") for item in records))

    def test_unknown_channel_has_its_own_group(self) -> None:
        rewritten = rewrite_one_relationship_unknown_channel(self.forward.bundle)
        built = snapshot(self.plastic, rewritten)
        self.assertIn(
            Channel.UNKNOWN,
            {group.channel for group in built.relationship_evidence_groups},
        )

    def test_query_outcomes_keep_forward_empty_and_reverse_present_separate(self) -> None:
        boundaries = {
            (item.direction, item.outcome)
            for item in self.asymmetric_snapshot.query_execution_evidence
        }
        self.assertIn(
            (RelationshipDirection.KEYWORD_TO_PRODUCT, QueryExecutionOutcome.EXPLICIT_EMPTY),
            boundaries,
        )
        self.assertIn(
            (RelationshipDirection.PRODUCT_TO_KEYWORD, QueryExecutionOutcome.RESULTS_RETURNED),
            boundaries,
        )
        self.assertIn(
            "DIRECTIONAL_QUERY_ASYMMETRY",
            {item.code for item in self.asymmetric_snapshot.diagnostics},
        )

    def test_explicit_empty_is_evidence_not_absence_or_zero(self) -> None:
        forward_empty = next(
            item
            for item in self.asymmetric_snapshot.query_execution_evidence
            if item.direction is RelationshipDirection.KEYWORD_TO_PRODUCT
        )
        self.assertEqual(forward_empty.outcome, QueryExecutionOutcome.EXPLICIT_EMPTY)
        self.assertEqual(forward_empty.related_relationship_observation_ids, ())
        self.assertFalse(
            any(
                group.direction is RelationshipDirection.KEYWORD_TO_PRODUCT
                for group in self.asymmetric_snapshot.relationship_evidence_groups
            )
        )
        serialized = self.asymmetric_snapshot.to_dict()
        self.assertNotIn("demand", serialized)
        self.assertFalse(hasattr(self.asymmetric_snapshot, "competitor_count"))

    def test_unknown_and_failed_query_outcomes_are_retained(self) -> None:
        for outcome in (
            QueryExecutionOutcome.OUTCOME_UNKNOWN,
            QueryExecutionOutcome.EXECUTION_FAILED,
        ):
            with self.subTest(outcome=outcome):
                rewritten = rewrite_query_outcome(self.forward_empty.bundle, outcome)
                built = snapshot(self.ball, rewritten)
                self.assertEqual(built.query_execution_evidence[0].outcome, outcome)
                self.assertFalse(built.query_execution_evidence[0].related_relationship_observation_ids)

    def test_reverse_empty_is_associated_only_through_observed_product_endpoint(self) -> None:
        product = next(
            item.product
            for item in self.forward.bundle.observations
            if isinstance(item, ProductKeywordRelationshipObservation)
        )
        reverse_empty = reverse_non_result_for_product(
            self.reverse.bundle, product, QueryExecutionOutcome.EXPLICIT_EMPTY
        )
        built = snapshot(self.plastic, self.forward.bundle, reverse_empty)
        evidence = next(
            item
            for item in built.query_execution_evidence
            if item.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
        )
        self.assertEqual(evidence.outcome, QueryExecutionOutcome.EXPLICIT_EMPTY)
        self.assertEqual(evidence.related_relationship_observation_ids, ())
        self.assertTrue(evidence.target_related_relationship_observation_ids)
        relationship_ids = {
            item.observation_id
            for group in built.relationship_evidence_groups
            for item in group.records
        }
        self.assertTrue(
            set(evidence.target_related_relationship_observation_ids) <= relationship_ids
        )

    def test_related_products_are_explicitly_evidence_inventory(self) -> None:
        inventory = self.plastic_snapshot.related_product_evidence_inventory
        self.assertTrue(inventory)
        relationship_ids = {
            item.observation_id
            for group in self.plastic_snapshot.relationship_evidence_groups
            for item in group.records
        }
        self.assertTrue(
            all(set(item.relationship_observation_ids) <= relationship_ids for item in inventory)
        )
        keys = set(self.plastic_snapshot.to_dict())
        self.assertIn("related_product_evidence_inventory", keys)
        self.assertNotIn("competitor_set", keys)
        self.assertNotIn("competitor_count", keys)


class CoverageOutOfScopeAndLineageTests(DemandFixtureCase):
    def test_coverage_is_inventory_only(self) -> None:
        coverage = self.plastic_snapshot.evidence_coverage
        self.assertEqual(coverage.source_bundle_count, 2)
        self.assertGreater(coverage.raw_evidence_reference_count, 0)
        self.assertGreater(coverage.transformation_run_count, 0)
        self.assertGreater(coverage.keyword_metric_observation_count, 0)
        self.assertGreater(coverage.relationship_observation_count, 0)
        self.assertGreater(coverage.query_execution_record_count, 0)
        payload = coverage.to_dict()
        self.assertFalse(any("score" in key or "confidence" in key for key in payload))

    def test_product_fact_metric_and_review_observations_are_out_of_scope(self) -> None:
        product = adapt(
            "xiyou_asin_info.json",
            "asin_info",
            request={"asin": "B0G2VV4RBW"},
        )
        built = snapshot(self.plastic, self.keyword_info.bundle, product.bundle)
        kinds = {
            item.observation_kind
            for item in built.out_of_scope_evidence_references
            if item.observation_kind is not None
        }
        self.assertTrue(kinds)
        self.assertIn(
            "NON_KEYWORD_OBSERVATIONS_OUT_OF_SCOPE",
            {item.code for item in built.diagnostics},
        )
        self.assertEqual(
            built.evidence_coverage.out_of_scope_record_count,
            len(built.out_of_scope_evidence_references),
        )

    def test_metric_relationship_and_query_lineage_reaches_collection(self) -> None:
        metric = self.plastic_snapshot.keyword_metric_evidence_sets[0].candidates[0]
        relationship = self.plastic_snapshot.relationship_evidence_groups[0].records[0]
        query = self.plastic_snapshot.query_execution_evidence[0]
        for reference in (
            metric.lineage_references[0],
            relationship.lineage_references[0],
            query.lineage_references[0],
        ):
            self.assertTrue(reference.source_record_id)
            self.assertTrue(reference.transformation_run_id)
            self.assertTrue(reference.mapping_version)
            self.assertTrue(reference.raw_evidence_id)
            self.assertTrue(reference.collection_run_id)
            self.assertTrue(reference.source_bundle_fingerprints)

    def test_validate_against_bundles_replays_all_lineage(self) -> None:
        self.assertIs(
            self.plastic_snapshot.validate_against_bundles(
                (self.forward.bundle, self.keyword_info.bundle)
            ),
            self.plastic_snapshot,
        )

    def test_validate_against_bundles_rejects_wrong_type_and_fingerprint(self) -> None:
        with self.assertRaises(DemandIntelligenceValidationError):
            self.plastic_snapshot.validate_against_bundles(({},))  # type: ignore[arg-type]
        with self.assertRaises(DemandIntelligenceValidationError):
            self.plastic_snapshot.validate_against_bundles((self.keyword_info.bundle,))

    def test_validate_against_bundles_rejects_orphan_lineage(self) -> None:
        orphan = replace(
            self.plastic_snapshot.lineage_index[0], raw_evidence_id="raw:orphan-demand-test"
        )
        payload = self.plastic_snapshot.to_dict()
        payload["lineage_index"][0] = orphan.to_dict()
        payload["lineage_index"] = sorted(payload["lineage_index"], key=canonical_json)
        payload.pop("snapshot_id")
        tampered_id = deterministic_id("demand-snapshot", payload)
        payload["snapshot_id"] = tampered_id
        tampered = DemandIntelligenceSnapshotV0_1.from_dict(payload)
        with self.assertRaises(DemandIntelligenceValidationError):
            tampered.validate_against_bundles(
                (self.keyword_info.bundle, self.forward.bundle)
            )

    def test_builder_rejects_observation_identity_collision(self) -> None:
        colliding = synthetic_provider_metric_bundle(
            self.keyword_info.bundle,
            keep_original_observation_id=True,
            value=50000,
        )
        with self.assertRaises(DemandIdentityCollisionError):
            snapshot(self.plastic, self.keyword_info.bundle, colliding)


class ImmutabilityDeterminismAndSerializationTests(DemandFixtureCase):
    def test_request_and_snapshot_are_deeply_immutable(self) -> None:
        request = DemandIntelligenceRequest(
            target_keyword_identity=self.plastic,
            canonical_bundles=(self.keyword_info.bundle,),
        )
        with self.assertRaises(FrozenInstanceError):
            request.target_keyword_identity = self.ball  # type: ignore[misc]
        built = snapshot(self.plastic, self.keyword_info.bundle)
        with self.assertRaises(FrozenInstanceError):
            built.snapshot_id = "changed"  # type: ignore[misc]
        metric = built.keyword_metric_evidence_sets[0]
        with self.assertRaises(TypeError):
            metric.presence_counts["PRESENT"] = 99  # type: ignore[index]
        candidate = metric.candidates[0]
        if candidate.range is not None:
            with self.assertRaises(TypeError):
                candidate.range["min"] = 0  # type: ignore[index]

    def test_same_process_and_bundle_order_are_deterministic(self) -> None:
        first = snapshot(self.plastic, self.keyword_info.bundle, self.forward.bundle)
        second = snapshot(self.plastic, self.keyword_info.bundle, self.forward.bundle)
        reordered = snapshot(self.plastic, self.forward.bundle, self.keyword_info.bundle)
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.snapshot_id, reordered.snapshot_id)
        self.assertEqual(canonical_json(first), canonical_json(reordered))

    def test_fresh_process_is_deterministic(self) -> None:
        script = r'''
import json
from pathlib import Path
import sys
from amazon_product_intelligence.adapters import AdaptationContext, XiYouAdapterV0_1
from amazon_product_intelligence.contracts import KeywordMetricObservation
from amazon_product_intelligence.demand_intelligence import DemandIntelligenceBuilderV0_1, DemandIntelligenceRequest

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
context = AdaptationContext(
    provider="xiyou", payload_kind="keyword_info", source_tool="get_keyword_info",
    marketplace="US", locale="en-us", retrieved_at="2026-08-14T09:00:00Z",
    transformed_at="2026-08-14T09:01:00Z",
    collection_run_id="collection:xiyou:keyword_info:demand-fixture",
    sanitized_request={}, currency="USD",
)
bundle = XiYouAdapterV0_1().adapt(payload, context).bundle
target = next(item.keyword for item in bundle.observations if isinstance(item, KeywordMetricObservation))
snapshot = DemandIntelligenceBuilderV0_1().build(DemandIntelligenceRequest(target_keyword_identity=target, canonical_bundles=(bundle,)))
print(snapshot.snapshot_id)
'''
        command = [sys.executable, "-c", script, str(FIXTURES / "xiyou_keyword_info.json")]
        environment = {"PYTHONPATH": str(PYTHON_SOURCE), "PYTHONDONTWRITEBYTECODE": "1"}
        import os

        process_environment = os.environ.copy()
        process_environment.update(environment)
        first = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=process_environment,
        ).stdout.strip()
        second = subprocess.run(
            command,
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=process_environment,
        ).stdout.strip()
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("demand-snapshot:"))

    def test_strict_round_trip(self) -> None:
        payload = json.loads(canonical_json(self.plastic_snapshot))
        reconstructed = DemandIntelligenceSnapshotV0_1.from_dict(payload)
        self.assertEqual(reconstructed, self.plastic_snapshot)
        self.assertEqual(canonical_json(reconstructed), canonical_json(self.plastic_snapshot))

    def test_unknown_field_is_rejected(self) -> None:
        payload = self.plastic_snapshot.to_dict()
        payload["future_score"] = 1
        with self.assertRaises(DemandSerializationError):
            DemandIntelligenceSnapshotV0_1.from_dict(payload)

    def test_invalid_enum_is_rejected(self) -> None:
        payload = self.plastic_snapshot.to_dict()
        payload["relationship_evidence_groups"][0]["channel"] = "PAID_ORGANIC"
        with self.assertRaises(DemandSerializationError):
            DemandIntelligenceSnapshotV0_1.from_dict(payload)

    def test_snapshot_identity_mismatch_is_rejected(self) -> None:
        payload = self.plastic_snapshot.to_dict()
        payload["snapshot_id"] = "demand-snapshot:incorrect"
        with self.assertRaises(DemandSerializationError):
            DemandIntelligenceSnapshotV0_1.from_dict(payload)

    def test_snapshot_contains_no_score_resolution_or_recommendation(self) -> None:
        serialized = canonical_json(self.plastic_snapshot).casefold()
        for forbidden in (
            "demand_score",
            "opportunity_score",
            "market_size",
            "competitor_count",
            "preferred_value",
            "resolved_value",
            "recommendation",
        ):
            self.assertNotIn(forbidden, serialized)


if __name__ == "__main__":
    unittest.main()
