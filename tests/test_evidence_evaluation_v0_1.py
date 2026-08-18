from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.evidence_evaluation as evidence_evaluation
from amazon_product_intelligence.adapters import (
    AdaptationContext,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.competition_intelligence import (
    CompetitionIntelligenceBuilderV0_1,
    CompetitionIntelligenceRequest,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    KeywordMetricObservation,
    PresenceStatus,
    ProductIdentity,
    canonical_json,
    deterministic_id,
    product_id,
)
from amazon_product_intelligence.demand_intelligence import (
    DemandIntelligenceBuilderV0_1,
    DemandIntelligenceRequest,
)
from amazon_product_intelligence.evidence_evaluation import (
    EVIDENCE_EVALUATION_RULESET_VERSION,
    EvidenceConflictRecord,
    EvidenceEvaluationBuilderV0_1,
    EvidenceEvaluationRequest,
    EvidenceEvaluationSnapshotV0_1,
    EvidenceSerializationError,
    EvidenceValidationError,
)
from amazon_product_intelligence.opportunity_intelligence import (
    OpportunityIntelligenceBuilderV0_1,
    OpportunityIntelligenceRequest,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"
TARGET_ASIN = "B0G2VV4RBW"
PARENT_ASIN = "B0G2VVX3ML"

CASES = {
    "xiyou_info": (
        "xiyou",
        "xiyou_asin_info.json",
        "asin_info",
        "get_asin_info",
        {},
    ),
    "xiyou_variations": (
        "xiyou",
        "xiyou_asin_variations.json",
        "asin_variations",
        "get_asin_variations",
        {"asin": TARGET_ASIN},
    ),
    "keyword": (
        "xiyou",
        "xiyou_keyword_info.json",
        "keyword_info",
        "get_keyword_info",
        {"keyword": "plastic spoons"},
    ),
    "forward": (
        "xiyou",
        "xiyou_keyword_forward_populated.json",
        "keyword_asin_analysis",
        "get_keyword_asin_analysis",
        {"keyword": "plastic spoons"},
    ),
    "reverse": (
        "xiyou",
        "xiyou_asin_keywords_reverse.json",
        "asin_keywords",
        "get_asin_keywords",
        {"asin": TARGET_ASIN},
    ),
    "detail": (
        "sorftime",
        "sorftime_product_detail.json",
        "product_detail",
        "product_detail",
        {"asin": TARGET_ASIN},
    ),
    "variations": (
        "sorftime",
        "sorftime_product_variations.json",
        "product_variations",
        "product_variations",
        {"asin": TARGET_ASIN},
    ),
    "reviews": (
        "sorftime",
        "sorftime_product_reviews.json",
        "product_reviews",
        "product_reviews",
        {"asin": TARGET_ASIN},
    ),
}


def adapt_payload(
    case: str, payload: dict[str, object], *, collection_suffix: str = "fixture"
) -> CanonicalEvidenceBundle:
    provider, fixture, payload_kind, source_tool, request = CASES[case]
    context = AdaptationContext(
        provider=provider,
        payload_kind=payload_kind,
        source_tool=source_tool,
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=(
            f"collection:{provider}:{payload_kind}:evidence-evaluation-test:{collection_suffix}"
        ),
        sanitized_request=request,
        currency="USD",
    )
    adapter = XiYouAdapterV0_1() if provider == "xiyou" else SorftimeAdapterV0_1()
    result = adapter.adapt(payload, context)
    if not result.succeeded:
        raise AssertionError(result.errors)
    return result.bundle.validate()


def adapt(case: str) -> CanonicalEvidenceBundle:
    _, fixture, _, _, _ = CASES[case]
    payload = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    return adapt_payload(case, payload)


def build(*bundles: CanonicalEvidenceBundle) -> EvidenceEvaluationSnapshotV0_1:
    return EvidenceEvaluationBuilderV0_1().build(
        EvidenceEvaluationRequest(canonical_bundles=tuple(bundles))
    )


def support_for(snapshot: EvidenceEvaluationSnapshotV0_1, dimension: str):
    return [item for item in snapshot.support_records if item.dimension == dimension]


def profile_for(snapshot: EvidenceEvaluationSnapshotV0_1, support_record_id: str):
    return next(
        item
        for item in snapshot.evidence_quality_profiles
        if item.support_record_id == support_record_id
    )


def reordered(bundle: CanonicalEvidenceBundle) -> CanonicalEvidenceBundle:
    return CanonicalEvidenceBundle(
        transformation_runs=tuple(reversed(bundle.transformation_runs)),
        observations=tuple(reversed(bundle.observations)),
        conflicts=tuple(reversed(bundle.conflicts)),
        resolutions=tuple(reversed(bundle.resolutions)),
        quality_issues=tuple(reversed(bundle.quality_issues)),
        raw_evidence_references=tuple(reversed(bundle.raw_evidence_references)),
        query_execution_records=tuple(reversed(bundle.query_execution_records)),
    )


class EvidenceEvaluationFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xiyou_info = adapt("xiyou_info")
        cls.xiyou_variations = adapt("xiyou_variations")
        cls.detail = adapt("detail")
        cls.variations = adapt("variations")
        cls.snapshot = build(cls.xiyou_info, cls.detail, cls.variations)

    def test_public_api_is_explicit_and_closed(self) -> None:
        expected = {
            "EVIDENCE_EVALUATION_RULESET_VERSION",
            "EvidenceEvaluationRequest",
            "EvidenceEvaluationSnapshotV0_1",
            "EvidenceEvaluationBuilderV0_1",
            "EvidenceEvaluationError",
            "EvidenceValidationError",
            "EvidenceSerializationError",
            "EvidenceQualityProfile",
            "EvidenceSupportRecord",
            "EvidenceConflictRecord",
            "EvidenceCoverageSummary",
            "EvidenceLineageReference",
            "EvidenceDiagnostic",
        }
        self.assertEqual(set(evidence_evaluation.__all__), expected)
        self.assertEqual(EVIDENCE_EVALUATION_RULESET_VERSION, "evidence-evaluation-v0.1")
        self.assertTrue(expected <= set(vars(evidence_evaluation)))

    def test_production_dependency_boundary(self) -> None:
        production = REPOSITORY_ROOT / "src" / "amazon_product_intelligence" / "evidence_evaluation"
        forbidden = {
            "adapters",
            "product_intelligence",
            "demand_intelligence",
            "competition_intelligence",
            "opportunity_intelligence",
        }
        for path in production.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            self.assertFalse(
                any(part in forbidden for name in imported for part in name.split(".")),
                path.name,
            )

    def test_multi_provider_same_value_support_is_qualitative(self) -> None:
        prices = support_for(self.snapshot, "price")
        self.assertEqual(len(prices), 1)
        price = prices[0]
        profile = profile_for(self.snapshot, price.support_record_id)
        self.assertEqual(price.providers, ("sorftime", "xiyou"))
        self.assertEqual(price.provider_count, 2)
        self.assertEqual(profile.source_diversity, "MULTI_PROVIDER_SUPPORT")
        self.assertEqual(profile.consistency, "SAME_VALUE")
        self.assertIn("COMPLETE_LINEAGE", profile.qualitative_attributes)

    def test_single_provider_support_remains_explicit(self) -> None:
        categories = support_for(self.snapshot, "category")
        self.assertEqual(len(categories), 1)
        support = categories[0]
        profile = profile_for(self.snapshot, support.support_record_id)
        self.assertEqual(support.provider_count, 1)
        self.assertEqual(profile.source_diversity, "SINGLE_PROVIDER")

    def test_unknown_period_and_observation_time_are_preserved(self) -> None:
        title = support_for(self.snapshot, "title")[0]
        profile = profile_for(self.snapshot, title.support_record_id)
        self.assertEqual(profile.period_status, "UNKNOWN_PERIOD")
        self.assertEqual(profile.observation_recency, "UNKNOWN_OBSERVATION_TIME")
        self.assertIn("UNKNOWN_PERIOD", profile.qualitative_attributes)

    def test_non_present_value_is_not_negative_evidence(self) -> None:
        sales = [
            item
            for item in support_for(self.snapshot, "estimated_sales_volume")
            if PresenceStatus.UNKNOWN in item.presence_statuses
        ]
        self.assertEqual(len(sales), 1)
        profile = profile_for(self.snapshot, sales[0].support_record_id)
        self.assertEqual(profile.completeness, "NO_PRESENT_VALUE")
        self.assertEqual(profile.consistency, "NO_PRESENT_VALUE")
        self.assertTrue(any(
            item.code == "NON_PRESENT_EVIDENCE_NOT_NEGATIVE"
            for item in self.snapshot.diagnostics
        ))

    def test_missing_null_unknown_and_zero_remain_distinct(self) -> None:
        source = json.loads(
            (FIXTURES / "xiyou_keyword_info.json").read_text(encoding="utf-8")
        )
        null_payload = {
            "status": 200,
            "data": {"list": [deepcopy(source["data"]["list"][1])], "total": 1},
        }
        null_snapshot = build(adapt_payload("keyword", null_payload, collection_suffix="null"))
        null_support = support_for(null_snapshot, "search_volume")[0]
        self.assertEqual(null_support.presence_statuses, (PresenceStatus.EXPLICIT_NULL,))
        self.assertEqual(
            profile_for(null_snapshot, null_support.support_record_id).completeness,
            "NO_PRESENT_VALUE",
        )

        missing_payload = deepcopy(null_payload)
        del missing_payload["data"]["list"][0]["abaReport"]
        missing_snapshot = build(
            adapt_payload("keyword", missing_payload, collection_suffix="missing")
        )
        self.assertFalse(support_for(missing_snapshot, "search_volume"))

        zero_payload = deepcopy(source)
        zero_row = zero_payload["data"]["list"][0]
        zero_row["abaReport"]["weeklySearchVolume"] = 0
        zero_payload["data"]["list"] = [zero_row]
        zero_payload["data"]["total"] = 1
        zero_snapshot = build(adapt_payload("keyword", zero_payload, collection_suffix="zero"))
        zero_support = support_for(zero_snapshot, "search_volume")[0]
        self.assertEqual(zero_support.presence_statuses, (PresenceStatus.PRESENT,))
        zero_observation_id = zero_support.supporting_observation_ids[0]
        zero_observation = next(
            item
            for item in adapt_payload(
                "keyword", zero_payload, collection_suffix="zero-observation"
            ).observations
            if item.metric == "search_volume"
        )
        self.assertEqual(zero_observation.value.normalized_value, 0)
        self.assertNotEqual(zero_observation_id, null_support.supporting_observation_ids[0])

        unknown_support = next(
            item
            for item in support_for(self.snapshot, "estimated_sales_volume")
            if PresenceStatus.UNKNOWN in item.presence_statuses
        )
        self.assertEqual(unknown_support.presence_statuses, (PresenceStatus.UNKNOWN,))

    def test_conflicts_describe_candidates_without_resolution(self) -> None:
        by_dimension = {item.dimension: item for item in self.snapshot.conflict_records}
        self.assertEqual(set(by_dimension), {"title", "rating", "review_count"})
        rating = by_dimension["rating"]
        self.assertIsInstance(rating, EvidenceConflictRecord)
        self.assertEqual(rating.conflict_status, "CONFLICT_PRESENT")
        self.assertEqual(set(rating.candidate_values), set(rating.candidate_observation_ids))
        values = {
            value.normalized_value for value in rating.candidate_values.values()
        }
        self.assertEqual(values, {4.8, 4.9})
        output_keys = set(rating.to_dict())
        self.assertFalse({"winner", "best_provider", "truth_value", "resolution"} & output_keys)

    def test_repeatable_variation_children_are_not_false_conflicts(self) -> None:
        snapshot = build(self.xiyou_variations)
        children = support_for(snapshot, "child_product_relationship")
        self.assertEqual(len(children), 2)
        self.assertFalse(any(
            item.dimension == "child_product_relationship" for item in snapshot.conflict_records
        ))

    def test_lineage_replays_observation_through_mapping_and_raw_reference(self) -> None:
        self.assertIs(
            self.snapshot.validate_against_bundles(
                (self.xiyou_info, self.detail, self.variations)
            ),
            self.snapshot,
        )
        self.assertEqual(
            {item.observation_id for item in self.snapshot.lineage_index},
            {
                item.observation_id
                for bundle in (self.xiyou_info, self.detail, self.variations)
                for item in bundle.observations
            },
        )
        self.assertTrue(all(item.mapping_version for item in self.snapshot.lineage_index))
        self.assertTrue(all(item.raw_evidence_id for item in self.snapshot.lineage_index))

    def test_missing_lineage_and_fingerprint_mismatch_fail_closed(self) -> None:
        payload = self.snapshot.to_dict()
        payload["lineage_index"] = payload["lineage_index"][1:]
        payload["snapshot_id"] = deterministic_id(
            "evidence-evaluation-snapshot",
            {key: value for key, value in payload.items() if key != "snapshot_id"},
        )
        with self.assertRaises(EvidenceSerializationError):
            EvidenceEvaluationSnapshotV0_1.from_dict(payload)
        with self.assertRaises(EvidenceValidationError):
            self.snapshot.validate_against_bundles((self.xiyou_info, self.detail))
        with self.assertRaises(EvidenceValidationError):
            self.snapshot.validate_against_bundles(({},))  # type: ignore[arg-type]

    def test_cross_bundle_observation_identity_collision_fails_closed(self) -> None:
        original = self.xiyou_info.observations[0]
        changed_value = replace(
            original.value,
            raw_value="changed title",
            normalized_value="changed title",
        )
        changed = replace(original, value=changed_value)
        colliding = replace(
            self.xiyou_info,
            observations=(changed,) + self.xiyou_info.observations[1:],
        )
        with self.assertRaises(EvidenceValidationError):
            build(self.xiyou_info, colliding)

    def test_models_are_deeply_immutable(self) -> None:
        conflict = self.snapshot.conflict_records[0]
        with self.assertRaises(FrozenInstanceError):
            conflict.dimension = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            conflict.candidate_values[conflict.candidate_observation_ids[0]] = next(  # type: ignore[index]
                iter(conflict.candidate_values.values())
            )
        with self.assertRaises(TypeError):
            self.snapshot.coverage.observation_kind_counts["METRIC"] = 0  # type: ignore[index]

    def test_strict_serialization_round_trip_and_unknown_field_rejection(self) -> None:
        payload = self.snapshot.to_dict()
        restored = EvidenceEvaluationSnapshotV0_1.from_dict(payload)
        self.assertEqual(restored, self.snapshot)
        self.assertEqual(canonical_json(restored), canonical_json(self.snapshot))
        payload["unexpected"] = True
        with self.assertRaises(EvidenceSerializationError):
            EvidenceEvaluationSnapshotV0_1.from_dict(payload)

    def test_determinism_ignores_bundle_and_record_order(self) -> None:
        reordered_snapshot = build(
            reordered(self.variations),
            reordered(self.detail),
            reordered(self.xiyou_info),
        )
        self.assertEqual(reordered_snapshot.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(canonical_json(reordered_snapshot), canonical_json(self.snapshot))

    def test_determinism_is_stable_across_processes(self) -> None:
        script = (
            "from tests.test_evidence_evaluation_v0_1 import adapt, build; "
            "print(build(adapt('xiyou_info'), adapt('detail'), adapt('variations')).snapshot_id)"
        )
        first = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=REPOSITORY_ROOT,
            text=True,
        ).strip()
        second = subprocess.check_output(
            [sys.executable, "-c", script],
            cwd=REPOSITORY_ROOT,
            text=True,
        ).strip()
        self.assertEqual(first, self.snapshot.snapshot_id)
        self.assertEqual(second, first)

    def test_output_has_no_numeric_weight_or_decision_fields(self) -> None:
        forbidden = {
            "score",
            "weight",
            "confidence",
            "trust",
            "probability",
            "winner",
            "preferred_provider",
            "provider_score",
            "reliability_score",
            "resolution",
            "recommendation",
            "ranking",
            "decision",
        }

        def keys(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    yield key.casefold()
                    yield from keys(child)
            elif isinstance(value, list):
                for child in value:
                    yield from keys(child)

        self.assertFalse(forbidden & set(keys(self.snapshot.to_dict())))


class EvidenceEvaluationRealIntegrationCase(unittest.TestCase):
    def test_existing_intelligence_evidence_flows_into_evaluation(self) -> None:
        xiyou_info = adapt("xiyou_info")
        keyword = adapt("keyword")
        forward = adapt("forward")
        reverse = adapt("reverse")
        variations = adapt("xiyou_variations")
        detail = adapt("detail")
        reviews = adapt("reviews")

        target_product = ProductIdentity(
            product_id=product_id("US", TARGET_ASIN),
            marketplace="US",
            asin=TARGET_ASIN,
            parent_asin=PARENT_ASIN,
            identity_status="CONFIRMED",
        )
        product_snapshot = ProductIntelligenceBuilderV0_1().build(
            ProductIntelligenceRequest(
                target_product_identity=target_product,
                scope=ProductScope.EXACT_PRODUCT,
                canonical_bundles=(xiyou_info, detail, reviews),
            )
        )
        target_keyword = next(
            item.keyword
            for item in keyword.observations
            if isinstance(item, KeywordMetricObservation)
        )
        demand_snapshot = DemandIntelligenceBuilderV0_1().build(
            DemandIntelligenceRequest(
                target_keyword_identity=target_keyword,
                canonical_bundles=(keyword, forward),
            )
        )
        competition_snapshot = CompetitionIntelligenceBuilderV0_1().build(
            CompetitionIntelligenceRequest(
                canonical_bundles=(forward, reverse, variations, detail)
            )
        )
        opportunity_snapshot = OpportunityIntelligenceBuilderV0_1().build(
            OpportunityIntelligenceRequest(
                canonical_bundles=(
                    xiyou_info,
                    keyword,
                    forward,
                    reverse,
                    variations,
                    detail,
                    reviews,
                )
            )
        )
        self.assertTrue(product_snapshot.product_fact_evidence_sets)
        self.assertTrue(demand_snapshot.keyword_metric_evidence_sets)
        self.assertTrue(competition_snapshot.relationship_evidence_graph.edges)
        self.assertTrue(opportunity_snapshot.observed_signals)

        evaluation = build(
            xiyou_info,
            keyword,
            forward,
            reverse,
            variations,
            detail,
            reviews,
        )
        self.assertTrue(evaluation.support_records)
        self.assertTrue(evaluation.evidence_quality_profiles)
        self.assertTrue(evaluation.conflict_records)
        self.assertGreaterEqual(evaluation.coverage.provider_count, 2)
        self.assertGreaterEqual(evaluation.coverage.multi_provider_support_count, 1)
        self.assertIs(
            evaluation.validate_against_bundles((
                xiyou_info,
                keyword,
                forward,
                reverse,
                variations,
                detail,
                reviews,
            )),
            evaluation,
        )


if __name__ == "__main__":
    unittest.main()
