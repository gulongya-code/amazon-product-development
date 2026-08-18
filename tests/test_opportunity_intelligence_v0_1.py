from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.opportunity_intelligence as opportunity
from amazon_product_intelligence.adapters import (
    AdaptationContext,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    Channel,
    ProductKeywordRelationshipObservation,
    RelationshipDirection,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.opportunity_intelligence import (
    OPPORTUNITY_INTELLIGENCE_RULESET_VERSION,
    OpportunityIdentityCollisionError,
    OpportunityIntelligenceBuilderV0_1,
    OpportunityIntelligenceRequest,
    OpportunityIntelligenceSnapshotV0_1,
    OpportunityMissingEvidenceKind,
    OpportunityRiskType,
    OpportunitySerializationError,
    OpportunitySignalClassification,
    OpportunitySignalType,
    OpportunityValidationError,
)


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
OPPORTUNITY_SOURCE = SOURCE_ROOT / "amazon_product_intelligence" / "opportunity_intelligence"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


CASES = {
    "keyword": (
        "xiyou", "xiyou_keyword_info.json", "keyword_info", "get_keyword_info",
        {"keyword": "plastic spoons"},
    ),
    "forward": (
        "xiyou", "xiyou_keyword_forward_populated.json", "keyword_asin_analysis",
        "get_keyword_asin_analysis", {"keyword": "plastic spoons"},
    ),
    "forward_empty": (
        "xiyou", "xiyou_keyword_forward_empty.json", "keyword_asin_analysis",
        "get_keyword_asin_analysis", {"keyword": "plastic spoons"},
    ),
    "reverse": (
        "xiyou", "xiyou_asin_keywords_reverse.json", "asin_keywords",
        "get_asin_keywords", {"asin": "B0G2VV4RBW"},
    ),
    "variations": (
        "xiyou", "xiyou_asin_variations.json", "asin_variations",
        "get_asin_variations", {"asin": "B0G2VV4RBW"},
    ),
    "detail": (
        "sorftime", "sorftime_product_detail.json", "product_detail",
        "product_detail", {"asin": "B0G2VV4RBW"},
    ),
    "reviews": (
        "sorftime", "sorftime_product_reviews.json", "product_reviews",
        "product_reviews", {"asin": "B0G2VV4RBW"},
    ),
}


def load_fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def adapt(case: str, *, marketplace: str = "US") -> CanonicalEvidenceBundle:
    provider, fixture, payload_kind, source_tool, request = CASES[case]
    context = AdaptationContext(
        provider=provider,
        payload_kind=payload_kind,
        source_tool=source_tool,
        marketplace=marketplace,
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:{provider}:{payload_kind}:{marketplace}:opportunity",
        sanitized_request=request,
        currency="USD",
    )
    adapter = XiYouAdapterV0_1() if provider == "xiyou" else SorftimeAdapterV0_1()
    result = adapter.adapt(load_fixture(fixture), context)
    if not result.succeeded:
        raise AssertionError(result.errors)
    return result.bundle


def build(*bundles: CanonicalEvidenceBundle) -> OpportunityIntelligenceSnapshotV0_1:
    return OpportunityIntelligenceBuilderV0_1().build(
        OpportunityIntelligenceRequest(canonical_bundles=tuple(bundles))
    )


def signal_types(snapshot: OpportunityIntelligenceSnapshotV0_1):
    return {item.signal_type for item in snapshot.observed_signals + snapshot.derived_signals}


class OpportunityFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.keyword = adapt("keyword")
        cls.forward = adapt("forward")
        cls.reverse = adapt("reverse")
        cls.variations = adapt("variations")
        cls.detail = adapt("detail")
        cls.reviews = adapt("reviews")
        cls.bundles = (
            cls.keyword, cls.forward, cls.reverse,
            cls.variations, cls.detail, cls.reviews,
        )
        cls.snapshot = build(*cls.bundles)


class PublicApiAndDependencyTests(OpportunityFixtureCase):
    def test_public_api_is_explicit_and_real(self) -> None:
        expected = {
            "OPPORTUNITY_INTELLIGENCE_RULESET_VERSION",
            "OpportunityIntelligenceRequest",
            "OpportunityIntelligenceSnapshotV0_1",
            "OpportunityIntelligenceBuilderV0_1",
            "OpportunityIntelligenceError",
            "OpportunityValidationError",
            "OpportunitySerializationError",
            "OpportunityIdentityCollisionError",
            "OpportunitySignalClassification",
            "OpportunitySignalType",
            "OpportunitySourceRecordType",
            "OpportunityMissingEvidenceKind",
            "OpportunityRiskType",
            "OpportunitySignalEvidence",
            "OpportunityRiskEvidence",
            "OpportunityMissingEvidence",
            "MissingEvidenceInventory",
            "OpportunityCoverageSummary",
            "OpportunityLineageReference",
            "OpportunityQualityIssueReference",
            "OpportunityDiagnostic",
        }
        self.assertEqual(set(opportunity.__all__), expected)
        self.assertEqual(
            OPPORTUNITY_INTELLIGENCE_RULESET_VERSION,
            "opportunity-intelligence-v0.1",
        )
        self.assertFalse(any(name.startswith("_") for name in opportunity.__all__))
        self.assertFalse([name for name in opportunity.__all__ if not hasattr(opportunity, name)])

    def test_source_dependency_boundary_is_contracts_and_standard_library_only(self) -> None:
        forbidden = {
            "amazon_product_intelligence.adapters",
            "amazon_product_intelligence.product_intelligence",
            "amazon_product_intelligence.demand_intelligence",
            "amazon_product_intelligence.competition_intelligence",
        }
        imported: set[str] = set()
        for source in OPPORTUNITY_SOURCE.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module)
        self.assertFalse(forbidden & imported)
        self.assertIn("amazon_product_intelligence.contracts", imported)

    def test_request_accepts_canonical_bundles_only(self) -> None:
        with self.assertRaises(OpportunityValidationError):
            OpportunityIntelligenceRequest(canonical_bundles=({"provider": "xiyou"},))  # type: ignore[arg-type]
        with self.assertRaises(OpportunityValidationError):
            OpportunityIntelligenceBuilderV0_1().build(self.keyword)  # type: ignore[arg-type]


class SignalModelAndIntegrationTests(OpportunityFixtureCase):
    def test_observed_and_derived_signal_classifications_are_separate(self) -> None:
        self.assertEqual(len(self.snapshot.observed_signals), 39)
        self.assertEqual(len(self.snapshot.derived_signals), 15)
        self.assertTrue(all(
            item.classification is OpportunitySignalClassification.OBSERVED_SIGNAL
            for item in self.snapshot.observed_signals
        ))
        self.assertTrue(all(
            item.classification is OpportunitySignalClassification.DERIVED_SIGNAL
            for item in self.snapshot.derived_signals
        ))

    def test_all_canonical_source_signal_types_are_present(self) -> None:
        expected = {
            OpportunitySignalType.PRODUCT_FACT_OBSERVED,
            OpportunitySignalType.PRODUCT_METRIC_OBSERVED,
            OpportunitySignalType.KEYWORD_METRIC_OBSERVED,
            OpportunitySignalType.KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED,
            OpportunitySignalType.QUERY_EXECUTION_OBSERVED,
            OpportunitySignalType.REVIEW_OBSERVED,
            OpportunitySignalType.VARIATION_RELATIONSHIP_OBSERVED,
        }
        observed = {item.signal_type for item in self.snapshot.observed_signals}
        self.assertEqual(observed, expected)

    def test_all_mechanical_derived_signal_types_are_present(self) -> None:
        expected = {
            OpportunitySignalType.PRODUCT_EVIDENCE_PRESENT,
            OpportunitySignalType.KEYWORD_EVIDENCE_PRESENT,
            OpportunitySignalType.RELATIONSHIP_EVIDENCE_PRESENT,
            OpportunitySignalType.CONFIRMED_VARIATION_EVIDENCE_PRESENT,
        }
        derived = {item.signal_type for item in self.snapshot.derived_signals}
        self.assertEqual(derived, expected)
        observed_ids = {item.signal_id for item in self.snapshot.observed_signals}
        self.assertTrue(all(
            item.supporting_signal_ids and set(item.supporting_signal_ids) <= observed_ids
            for item in self.snapshot.derived_signals
        ))

    def test_real_integration_has_expected_products_and_providers(self) -> None:
        products = {
            product.asin
            for signal in self.snapshot.observed_signals
            for product in signal.product_identities
        }
        providers = {item.provider for item in self.snapshot.lineage_index}
        self.assertEqual(
            products,
            {"B0G2VVX3ML", "B0G2VV4RBW", "B0G2VZSWRN", "B0CDV36NF6"},
        )
        self.assertEqual(providers, {"xiyou", "sorftime"})

    def test_exact_keyword_identity_variants_are_not_silently_merged(self) -> None:
        keywords = {
            (keyword.keyword_id, keyword.raw_text)
            for signal in self.snapshot.observed_signals
            for keyword in signal.keyword_identities
        }
        self.assertEqual(len(keywords), 3)
        self.assertIn(
            ("keyword:273f9f9576d89c784d93d455f61feb0ee2e0b26853020f29b320eb71f09d174c", "1/2 Ball Valve"),
            keywords,
        )
        self.assertIn(
            ("keyword:273f9f9576d89c784d93d455f61feb0ee2e0b26853020f29b320eb71f09d174c", "1/2 ball valve"),
            keywords,
        )

    def test_relationship_signals_preserve_direction_channel_rank_and_traffic(self) -> None:
        records = [
            item for item in self.snapshot.observed_signals
            if item.signal_type is OpportunitySignalType.KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED
        ]
        self.assertEqual(len(records), 10)
        self.assertEqual(
            {item.evidence_attributes["direction"] for item in records},
            {
                RelationshipDirection.KEYWORD_TO_PRODUCT.value,
                RelationshipDirection.PRODUCT_TO_KEYWORD.value,
            },
        )
        self.assertEqual(
            {item.evidence_attributes["channel"] for item in records},
            {Channel.ORGANIC.value, Channel.SPONSORED.value, Channel.UNKNOWN.value},
        )
        self.assertTrue(any(item.evidence_attributes["rank"] is not None for item in records))
        self.assertTrue(any(item.evidence_attributes["traffic"] is not None for item in records))

    def test_query_outcomes_are_observed_not_interpreted(self) -> None:
        queries = [
            item for item in self.snapshot.observed_signals
            if item.signal_type is OpportunitySignalType.QUERY_EXECUTION_OBSERVED
        ]
        self.assertEqual(len(queries), 2)
        self.assertEqual(
            {item.evidence_attributes["outcome"] for item in queries},
            {"RESULTS_RETURNED"},
        )
        self.assertEqual(
            {item.evidence_attributes["direction"] for item in queries},
            {"KEYWORD_TO_PRODUCT", "PRODUCT_TO_KEYWORD"},
        )

    def test_confirmed_variation_direction_is_explicit_and_has_no_sibling_signal(self) -> None:
        variations = [
            item for item in self.snapshot.derived_signals
            if item.signal_type is OpportunitySignalType.CONFIRMED_VARIATION_EVIDENCE_PRESENT
        ]
        pairs = {
            (
                item.evidence_attributes["variation_parent_product_id"],
                item.evidence_attributes["variation_child_product_id"],
            )
            for item in variations
        }
        self.assertEqual(pairs, {
            ("product:US:B0G2VVX3ML", "product:US:B0G2VV4RBW"),
            ("product:US:B0G2VVX3ML", "product:US:B0G2VZSWRN"),
        })
        self.assertNotIn(
            ("product:US:B0G2VV4RBW", "product:US:B0G2VZSWRN"), pairs
        )


class MissingAndRiskEvidenceTests(OpportunityFixtureCase):
    def test_complete_fixture_set_has_no_missing_evaluated_category(self) -> None:
        self.assertEqual(self.snapshot.missing_evidence.items, ())
        self.assertEqual(
            set(self.snapshot.missing_evidence.evaluated_evidence_kinds),
            set(OpportunityMissingEvidenceKind),
        )

    def test_missing_evidence_inventory_is_explicit(self) -> None:
        detail_only = build(self.detail)
        kinds = {item.evidence_kind for item in detail_only.missing_evidence.items}
        self.assertEqual(kinds, {
            OpportunityMissingEvidenceKind.KEYWORD_EVIDENCE,
            OpportunityMissingEvidenceKind.KEYWORD_PRODUCT_RELATIONSHIP_EVIDENCE,
            OpportunityMissingEvidenceKind.QUERY_EXECUTION_EVIDENCE,
            OpportunityMissingEvidenceKind.REVIEW_EVIDENCE,
        })
        self.assertTrue(all(
            item.classification is OpportunitySignalClassification.MISSING_EVIDENCE_SIGNAL
            for item in detail_only.missing_evidence.items
        ))

    def test_missing_evidence_is_not_negative_evidence(self) -> None:
        detail_only = build(self.detail)
        self.assertEqual(
            detail_only.missing_evidence.interpretation,
            "MISSING_EVIDENCE_IS_NOT_NEGATIVE_EVIDENCE",
        )
        self.assertIn(
            "MISSING_EVIDENCE_NOT_NEGATIVE",
            {item.code for item in detail_only.diagnostics},
        )
        self.assertFalse(any(
            hasattr(item, "negative_value") or hasattr(item, "penalty")
            for item in detail_only.missing_evidence.items
        ))

    def test_full_fixture_risk_inventory_is_methodological_only(self) -> None:
        self.assertEqual(
            {item.risk_type for item in self.snapshot.risk_evidence},
            {
                OpportunityRiskType.UNKNOWN_PERIOD,
                OpportunityRiskType.UNKNOWN_OBSERVATION_TIME,
                OpportunityRiskType.PROVIDER_METHOD_UNDECLARED,
            },
        )
        self.assertTrue(all(
            item.classification is OpportunitySignalClassification.RISK_EVIDENCE
            for item in self.snapshot.risk_evidence
        ))
        self.assertTrue(all(item.lineage_references for item in self.snapshot.risk_evidence))

    def test_single_provider_and_missing_review_are_limitations_without_scores(self) -> None:
        detail_only = build(self.detail)
        types = {item.risk_type for item in detail_only.risk_evidence}
        self.assertIn(OpportunityRiskType.SINGLE_PROVIDER_EVIDENCE, types)
        self.assertIn(OpportunityRiskType.REVIEW_EVIDENCE_ABSENT, types)
        for item in detail_only.risk_evidence:
            keys = set(item.to_dict())
            self.assertFalse({"risk_score", "probability", "severity", "ranking"} & keys)

    def test_risk_sources_have_exact_lineage(self) -> None:
        for item in self.snapshot.risk_evidence:
            self.assertEqual(
                {lineage.source_record_id for lineage in item.lineage_references},
                set(item.source_record_ids),
            )

    def test_explicit_empty_query_is_a_limitation_not_negative_demand(self) -> None:
        empty = build(adapt("forward_empty"))
        query = next(
            item for item in empty.observed_signals
            if item.signal_type is OpportunitySignalType.QUERY_EXECUTION_OBSERVED
        )
        self.assertEqual(query.evidence_attributes["outcome"], "EXPLICIT_EMPTY")
        self.assertIn(
            OpportunityRiskType.QUERY_OUTCOME_LIMITATION,
            {item.risk_type for item in empty.risk_evidence},
        )
        self.assertIn(
            OpportunityMissingEvidenceKind.KEYWORD_PRODUCT_RELATIONSHIP_EVIDENCE,
            {item.evidence_kind for item in empty.missing_evidence.items},
        )
        self.assertNotIn(
            OpportunitySignalType.RELATIONSHIP_EVIDENCE_PRESENT,
            signal_types(empty),
        )


class CoverageLineageAndValidationTests(OpportunityFixtureCase):
    def test_coverage_matches_real_integration_inventory(self) -> None:
        coverage = self.snapshot.coverage
        self.assertEqual(coverage.source_bundle_count, 6)
        self.assertEqual(coverage.observed_signal_count, 39)
        self.assertEqual(coverage.derived_signal_count, 15)
        self.assertEqual(coverage.missing_evidence_count, 0)
        self.assertEqual(coverage.risk_evidence_count, 3)
        self.assertEqual(coverage.product_identity_count, 4)
        self.assertEqual(coverage.keyword_identity_count, 3)
        self.assertEqual(coverage.product_fact_observation_count, 14)
        self.assertEqual(coverage.product_metric_observation_count, 4)
        self.assertEqual(coverage.keyword_metric_observation_count, 8)
        self.assertEqual(coverage.relationship_observation_count, 10)
        self.assertEqual(coverage.query_execution_record_count, 2)
        self.assertEqual(coverage.review_observation_count, 1)
        self.assertEqual(coverage.confirmed_variation_observation_count, 3)
        self.assertEqual(coverage.competition_related_evidence_count, 13)
        self.assertEqual(coverage.provider_count, 2)
        self.assertEqual(coverage.quality_issue_count, 9)

    def test_coverage_has_no_score_confidence_or_completeness_fields(self) -> None:
        keys = set(self.snapshot.coverage.to_dict())
        self.assertFalse(any(
            "score" in key or "confidence" in key or "completeness" in key or "ranking" in key
            for key in keys
        ))

    def test_validate_against_bundles_replays_observations_queries_and_quality(self) -> None:
        self.assertIs(
            self.snapshot.validate_against_bundles(tuple(reversed(self.bundles))),
            self.snapshot,
        )
        source_types = {item.source_record_type.value for item in self.snapshot.lineage_index}
        self.assertEqual(source_types, {
            "PRODUCT_FACT", "PRODUCT_METRIC", "KEYWORD_METRIC",
            "KEYWORD_PRODUCT_RELATIONSHIP", "QUERY_EXECUTION", "REVIEW",
        })

    def test_validate_against_bundles_rejects_wrong_type_and_fingerprint(self) -> None:
        with self.assertRaises(OpportunityValidationError):
            self.snapshot.validate_against_bundles(({},))  # type: ignore[arg-type]
        with self.assertRaises(OpportunityValidationError):
            self.snapshot.validate_against_bundles((self.keyword,))

    def test_validate_against_bundles_rejects_orphan_raw_lineage(self) -> None:
        orphan = replace(
            self.snapshot.lineage_index[0], raw_evidence_id="raw:opportunity-orphan"
        )
        payload = self.snapshot.to_dict()
        payload["lineage_index"][0] = orphan.to_dict()
        payload["lineage_index"] = sorted(payload["lineage_index"], key=canonical_json)
        payload.pop("snapshot_id")
        payload["snapshot_id"] = deterministic_id("opportunity-snapshot", payload)
        tampered = OpportunityIntelligenceSnapshotV0_1.from_dict(payload)
        with self.assertRaises(OpportunityValidationError):
            tampered.validate_against_bundles(self.bundles)

    def test_builder_rejects_observation_identity_collision(self) -> None:
        old = next(
            item for item in self.forward.observations
            if isinstance(item, ProductKeywordRelationshipObservation)
            and item.channel is Channel.ORGANIC
        )
        changed = replace(old, channel=Channel.MIXED)
        colliding = replace(
            self.forward,
            observations=tuple(
                changed if item.observation_id == old.observation_id else item
                for item in self.forward.observations
            ),
        ).validate()
        with self.assertRaises(OpportunityIdentityCollisionError):
            build(self.forward, colliding)

    def test_quality_issue_references_are_complete(self) -> None:
        expected = {issue.issue_id for bundle in self.bundles for issue in bundle.quality_issues}
        actual = {item.issue_id for item in self.snapshot.quality_issue_references}
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 9)


class DeterminismSerializationAndScopeTests(OpportunityFixtureCase):
    def test_request_and_snapshot_are_deeply_immutable(self) -> None:
        request = OpportunityIntelligenceRequest(canonical_bundles=[self.keyword])  # type: ignore[arg-type]
        self.assertIsInstance(request.canonical_bundles, tuple)
        with self.assertRaises(FrozenInstanceError):
            request.canonical_bundles = ()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.snapshot_id = "changed"  # type: ignore[misc]
        relationship = next(
            item for item in self.snapshot.observed_signals
            if item.signal_type is OpportunitySignalType.KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED
            and item.evidence_attributes["rank"] is not None
        )
        with self.assertRaises(TypeError):
            relationship.evidence_attributes["rank"]["page"] = 99  # type: ignore[index]

    def test_same_process_and_bundle_order_are_deterministic(self) -> None:
        first = build(*self.bundles)
        second = build(*self.bundles)
        reordered = build(*reversed(self.bundles))
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.snapshot_id, reordered.snapshot_id)
        self.assertEqual(canonical_json(first), canonical_json(reordered))

    def test_fresh_process_is_deterministic(self) -> None:
        script = r'''
import json
from pathlib import Path
import sys
from amazon_product_intelligence.adapters import AdaptationContext, XiYouAdapterV0_1
from amazon_product_intelligence.opportunity_intelligence import OpportunityIntelligenceBuilderV0_1, OpportunityIntelligenceRequest
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
context = AdaptationContext(
    provider="xiyou", payload_kind="keyword_info", source_tool="get_keyword_info",
    marketplace="US", locale="en-us", retrieved_at="2026-08-14T09:00:00Z",
    transformed_at="2026-08-14T09:01:00Z", collection_run_id="collection:fresh:opportunity",
    sanitized_request={"keyword":"plastic spoons"}, currency="USD",
)
bundle = XiYouAdapterV0_1().adapt(payload, context).bundle
snapshot = OpportunityIntelligenceBuilderV0_1().build(OpportunityIntelligenceRequest(canonical_bundles=(bundle,)))
print(snapshot.snapshot_id)
'''
        command = [
            sys.executable, "-c", script,
            str(FIXTURES / "xiyou_keyword_info.json"),
        ]
        environment = os.environ.copy()
        environment.update({"PYTHONPATH": str(SOURCE_ROOT), "PYTHONDONTWRITEBYTECODE": "1"})
        first = subprocess.run(
            command, cwd=REPOSITORY_ROOT, check=True, capture_output=True,
            text=True, encoding="utf-8", env=environment,
        ).stdout.strip()
        second = subprocess.run(
            command, cwd=REPOSITORY_ROOT, check=True, capture_output=True,
            text=True, encoding="utf-8", env=environment,
        ).stdout.strip()
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("opportunity-snapshot:"))

    def test_strict_serialization_round_trip(self) -> None:
        reconstructed = OpportunityIntelligenceSnapshotV0_1.from_dict(
            json.loads(canonical_json(self.snapshot))
        )
        self.assertEqual(reconstructed, self.snapshot)
        self.assertEqual(canonical_json(reconstructed), canonical_json(self.snapshot))

    def test_unknown_field_is_rejected(self) -> None:
        payload = self.snapshot.to_dict()
        payload["selection_recommendation"] = None
        with self.assertRaises(OpportunitySerializationError):
            OpportunityIntelligenceSnapshotV0_1.from_dict(payload)

    def test_snapshot_identity_mismatch_is_rejected(self) -> None:
        payload = self.snapshot.to_dict()
        payload["snapshot_id"] = "opportunity-snapshot:incorrect"
        with self.assertRaises(OpportunitySerializationError):
            OpportunityIntelligenceSnapshotV0_1.from_dict(payload)

    def test_snapshot_contains_no_score_ranking_recommendation_or_business_conclusion(self) -> None:
        payload = canonical_json(self.snapshot).casefold()
        for forbidden in (
            "opportunity_score", "product_score", "risk_score", "product_ranking",
            "selection_recommendation", "enter_market_recommendation",
            "reject_product_recommendation", "profit_prediction", "revenue_prediction",
            "roi_prediction", "investment_decision", "winning_product",
            "ai_recommendation",
        ):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main()
