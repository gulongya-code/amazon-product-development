from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.competition_intelligence as competition
from amazon_product_intelligence.adapters import (
    AdaptationContext,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    Channel,
    ProductFactObservation,
    ProductKeywordRelationshipObservation,
    RelationshipDirection,
    SemanticStatus,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.competition_intelligence import (
    COMPETITION_INTELLIGENCE_RULESET_VERSION,
    CompetitionIdentityCollisionError,
    CompetitionIntelligenceBuilderV0_1,
    CompetitionIntelligenceRequest,
    CompetitionIntelligenceSnapshotV0_1,
    CompetitionIntelligenceValidationError,
    CompetitionSerializationError,
    EvidenceClassification,
    EvidenceGraphEdgeType,
)


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
COMPETITION_SOURCE = SOURCE_ROOT / "amazon_product_intelligence" / "competition_intelligence"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def adapt(
    *,
    provider: str,
    fixture: str,
    payload_kind: str,
    source_tool: str,
    request: dict[str, object],
    marketplace: str = "US",
) -> CanonicalEvidenceBundle:
    context = AdaptationContext(
        provider=provider,
        payload_kind=payload_kind,
        source_tool=source_tool,
        marketplace=marketplace,
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:{provider}:{payload_kind}:{marketplace}:competition",
        sanitized_request=request,
        currency="USD",
    )
    adapter = XiYouAdapterV0_1() if provider == "xiyou" else SorftimeAdapterV0_1()
    result = adapter.adapt(load_fixture(fixture), context)
    if not result.succeeded:
        raise AssertionError(result.errors)
    return result.bundle


def build(*bundles: CanonicalEvidenceBundle) -> CompetitionIntelligenceSnapshotV0_1:
    return CompetitionIntelligenceBuilderV0_1().build(
        CompetitionIntelligenceRequest(canonical_bundles=tuple(bundles))
    )


def variation_edges(snapshot: CompetitionIntelligenceSnapshotV0_1):
    return [
        edge
        for edge in snapshot.relationship_evidence_graph.edges
        if edge.edge_type is EvidenceGraphEdgeType.VARIATION_RELATIONSHIP
    ]


def keyword_edges(snapshot: CompetitionIntelligenceSnapshotV0_1):
    return [
        edge
        for edge in snapshot.relationship_evidence_graph.edges
        if edge.edge_type is EvidenceGraphEdgeType.KEYWORD_OBSERVED_RELATIONSHIP
    ]


class CompetitionFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.forward = adapt(
            provider="xiyou",
            fixture="xiyou_keyword_forward_populated.json",
            payload_kind="keyword_asin_analysis",
            source_tool="get_keyword_asin_analysis",
            request={"keyword": "plastic spoons"},
        )
        cls.reverse = adapt(
            provider="xiyou",
            fixture="xiyou_asin_keywords_reverse.json",
            payload_kind="asin_keywords",
            source_tool="get_asin_keywords",
            request={"asin": "B0G2VV4RBW"},
        )
        cls.variations = adapt(
            provider="xiyou",
            fixture="xiyou_asin_variations.json",
            payload_kind="asin_variations",
            source_tool="get_asin_variations",
            request={"asin": "B0G2VV4RBW"},
        )
        cls.detail = adapt(
            provider="sorftime",
            fixture="sorftime_product_detail.json",
            payload_kind="product_detail",
            source_tool="product_detail",
            request={"asin": "B0G2VV4RBW"},
        )
        cls.snapshot = build(cls.forward, cls.reverse, cls.variations, cls.detail)


class PublicApiAndDependencyTests(CompetitionFixtureCase):
    def test_public_api_is_explicit_and_real(self) -> None:
        expected = {
            "COMPETITION_INTELLIGENCE_RULESET_VERSION",
            "CompetitionIntelligenceRequest",
            "CompetitionIntelligenceSnapshotV0_1",
            "CompetitionIntelligenceBuilderV0_1",
            "CompetitionIntelligenceError",
            "CompetitionIntelligenceValidationError",
            "CompetitionIdentityCollisionError",
            "CompetitionSerializationError",
            "EvidenceClassification",
            "EvidenceGraphEdgeType",
            "CompetitionSourceRecordType",
            "CompetitionProductEvidence",
            "CompetitionRelationshipEvidence",
            "CompetitionVariationEvidence",
            "CompetitionKeywordEvidence",
            "CompetitionEvidenceGraphNode",
            "CompetitionEvidenceGraphEdge",
            "CompetitionEvidenceGraph",
            "CompetitionCoverageSummary",
            "CompetitionLineageReference",
            "CompetitionQualityIssueReference",
            "CompetitionDiagnostic",
        }
        self.assertEqual(set(competition.__all__), expected)
        self.assertEqual(COMPETITION_INTELLIGENCE_RULESET_VERSION, "competition-intelligence-v0.1")
        self.assertFalse(any(name.startswith("_") for name in competition.__all__))
        self.assertFalse([name for name in competition.__all__ if not hasattr(competition, name)])

    def test_source_dependency_boundary_is_contracts_and_standard_library_only(self) -> None:
        forbidden = {
            "amazon_product_intelligence.adapters",
            "amazon_product_intelligence.product_intelligence",
            "amazon_product_intelligence.demand_intelligence",
        }
        imported: set[str] = set()
        for source in COMPETITION_SOURCE.glob("*.py"):
            tree = ast.parse(source.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    imported.add(node.module)
        self.assertFalse(forbidden & imported)
        self.assertIn("amazon_product_intelligence.contracts", imported)

    def test_request_rejects_provider_json_and_adapter_result(self) -> None:
        with self.assertRaises(CompetitionIntelligenceValidationError):
            CompetitionIntelligenceRequest(canonical_bundles=({"provider": "xiyou"},))  # type: ignore[arg-type]
        with self.assertRaises(CompetitionIntelligenceValidationError):
            CompetitionIntelligenceBuilderV0_1().build(self.forward)  # type: ignore[arg-type]


class EvidenceClassificationAndInventoryTests(CompetitionFixtureCase):
    def test_direct_and_derived_evidence_are_separate(self) -> None:
        self.assertTrue(self.snapshot.keyword_relationship_evidence)
        self.assertTrue(self.snapshot.variation_evidence)
        self.assertTrue(
            all(
                item.classification is EvidenceClassification.DIRECT_EVIDENCE
                for item in self.snapshot.keyword_relationship_evidence
                + self.snapshot.variation_evidence
            )
        )
        derived = (
            self.snapshot.observed_product_inventory
            + self.snapshot.keyword_evidence
            + self.snapshot.relationship_evidence_graph.nodes
            + self.snapshot.relationship_evidence_graph.edges
        )
        self.assertTrue(
            all(item.classification is EvidenceClassification.DERIVED_EVIDENCE for item in derived)
        )

    def test_observed_product_inventory_contains_real_fixture_endpoints(self) -> None:
        asins = {item.product_identity.asin for item in self.snapshot.observed_product_inventory}
        self.assertEqual(
            asins,
            {"B0CDV36NF6", "B0G2VV4RBW", "B0G2VVX3ML", "B0G2VZSWRN"},
        )

    def test_same_product_is_one_inventory_identity_with_all_sources(self) -> None:
        target = [
            item
            for item in self.snapshot.observed_product_inventory
            if item.product_identity.asin == "B0G2VV4RBW"
        ]
        self.assertEqual(len(target), 1)
        self.assertEqual(set(target[0].providers), {"xiyou", "sorftime"})
        self.assertGreater(len(target[0].source_observation_ids), 2)

    def test_same_asin_in_different_marketplaces_remains_separate(self) -> None:
        canada = adapt(
            provider="sorftime",
            fixture="sorftime_product_detail.json",
            payload_kind="product_detail",
            source_tool="product_detail",
            request={"asin": "B0G2VV4RBW"},
            marketplace="CA",
        )
        separated = build(self.detail, canada)
        targets = [
            item.product_identity
            for item in separated.observed_product_inventory
            if item.product_identity.asin == "B0G2VV4RBW"
        ]
        self.assertEqual({item.marketplace for item in targets}, {"US", "CA"})
        self.assertEqual(len({item.product_id for item in targets}), 2)

    def test_product_inventory_retains_keyword_direction_channel_and_lineage(self) -> None:
        product = next(
            item
            for item in self.snapshot.observed_product_inventory
            if item.product_identity.asin == "B0CDV36NF6"
        )
        self.assertEqual({item.raw_text for item in product.keywords}, {"plastic spoons"})
        self.assertEqual(set(product.directions), {RelationshipDirection.KEYWORD_TO_PRODUCT})
        self.assertEqual(set(product.channels), {Channel.ORGANIC, Channel.SPONSORED, Channel.UNKNOWN})
        self.assertEqual(
            {item.observation_id for item in product.lineage_references},
            set(product.source_observation_ids),
        )


class RelationshipAndVariationTests(CompetitionFixtureCase):
    def test_forward_and_reverse_relationships_remain_separate(self) -> None:
        directions = {item.direction for item in self.snapshot.keyword_relationship_evidence}
        self.assertEqual(
            directions,
            {RelationshipDirection.KEYWORD_TO_PRODUCT, RelationshipDirection.PRODUCT_TO_KEYWORD},
        )

    def test_organic_sponsored_and_unknown_channels_remain_separate(self) -> None:
        channels = {item.channel for item in self.snapshot.keyword_relationship_evidence}
        self.assertEqual(channels, {Channel.ORGANIC, Channel.SPONSORED, Channel.UNKNOWN})

    def test_rank_traffic_and_relationship_type_are_not_aggregated(self) -> None:
        evidence = self.snapshot.keyword_relationship_evidence
        self.assertTrue(any(item.rank is not None for item in evidence))
        self.assertTrue(any(item.traffic is not None for item in evidence))
        self.assertEqual(len(evidence), 10)
        self.assertFalse(any(hasattr(item, "aggregate_rank") for item in evidence))
        self.assertFalse(any(hasattr(item, "best_channel") for item in evidence))

    def test_variation_direction_normalizes_both_canonical_dimensions(self) -> None:
        parent_child = {
            (
                item.parent_product_identity.asin,
                item.child_product_identity.asin,
                item.source_dimension,
            )
            for item in self.snapshot.variation_evidence
        }
        self.assertIn(
            ("B0G2VVX3ML", "B0G2VV4RBW", "child_product_relationship"),
            parent_child,
        )
        self.assertIn(
            ("B0G2VVX3ML", "B0G2VV4RBW", "parent_product_relationship"),
            parent_child,
        )

    def test_multi_source_parent_child_edge_retains_both_direct_observations(self) -> None:
        edge = next(
            item
            for item in variation_edges(self.snapshot)
            if item.variation_parent_product_identity.asin == "B0G2VVX3ML"
            and item.variation_child_product_identity.asin == "B0G2VV4RBW"
        )
        self.assertEqual(len(edge.source_observation_ids), 2)
        self.assertEqual(set(edge.providers), {"xiyou", "sorftime"})

    def test_siblings_never_receive_a_product_to_product_edge(self) -> None:
        pairs = {
            frozenset(item.product_id for item in edge.endpoint_product_identities)
            for edge in variation_edges(self.snapshot)
        }
        siblings = frozenset(
            {
                "product:US:B0G2VV4RBW",
                "product:US:B0G2VZSWRN",
            }
        )
        self.assertNotIn(siblings, pairs)
        self.assertIn(
            "SIBLING_COMPETITION_NOT_INFERRED",
            {item.code for item in self.snapshot.diagnostics},
        )

    def test_unconfirmed_variation_is_excluded_with_diagnostic(self) -> None:
        old = next(
            item
            for item in self.variations.observations
            if isinstance(item, ProductFactObservation)
            and item.dimension == "child_product_relationship"
        )
        changed = replace(old, value=replace(old.value, semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED))
        bundle = replace(
            self.variations,
            observations=tuple(changed if item.observation_id == old.observation_id else item for item in self.variations.observations),
        ).validate()
        built = build(bundle)
        self.assertEqual(len(built.variation_evidence), 1)
        self.assertIn(
            "UNCONFIRMED_VARIATION_RELATIONSHIP_EXCLUDED",
            {item.code for item in built.diagnostics},
        )


class GraphKeywordAndCoverageTests(CompetitionFixtureCase):
    def test_graph_nodes_exactly_match_product_inventory(self) -> None:
        inventory = {item.product_identity.product_id for item in self.snapshot.observed_product_inventory}
        nodes = {item.product_identity.product_id for item in self.snapshot.relationship_evidence_graph.nodes}
        self.assertEqual(nodes, inventory)

    def test_graph_has_only_keyword_and_variation_edge_types(self) -> None:
        types = {item.edge_type for item in self.snapshot.relationship_evidence_graph.edges}
        self.assertEqual(
            types,
            {
                EvidenceGraphEdgeType.KEYWORD_OBSERVED_RELATIONSHIP,
                EvidenceGraphEdgeType.VARIATION_RELATIONSHIP,
            },
        )
        self.assertEqual(len(keyword_edges(self.snapshot)), 10)
        self.assertEqual(len(variation_edges(self.snapshot)), 2)

    def test_keyword_graph_edges_are_unary_product_attachments(self) -> None:
        for edge in keyword_edges(self.snapshot):
            self.assertEqual(len(edge.endpoint_product_identities), 1)
            self.assertIsNotNone(edge.keyword_identity)
            self.assertIsNone(edge.variation_parent_product_identity)
            self.assertIsNone(edge.variation_child_product_identity)

    def test_every_graph_edge_has_source_observations_and_lineage(self) -> None:
        for edge in self.snapshot.relationship_evidence_graph.edges:
            self.assertEqual(
                {item.observation_id for item in edge.lineage_references},
                set(edge.source_observation_ids),
            )
            self.assertTrue(all(item.raw_evidence_id for item in edge.lineage_references))

    def test_keyword_evidence_references_direct_relationships_only(self) -> None:
        direct_ids = {item.observation_id for item in self.snapshot.keyword_relationship_evidence}
        self.assertEqual(len(self.snapshot.keyword_evidence), 2)
        for item in self.snapshot.keyword_evidence:
            self.assertTrue(set(item.relationship_observation_ids) <= direct_ids)
            self.assertTrue(item.product_identities)

    def test_coverage_is_inventory_without_scores(self) -> None:
        coverage = self.snapshot.coverage
        self.assertEqual(coverage.source_bundle_count, 4)
        self.assertEqual(coverage.observed_product_identity_count, 4)
        self.assertEqual(coverage.observed_keyword_identity_count, 2)
        self.assertEqual(coverage.relationship_observation_count, 10)
        self.assertEqual(coverage.variation_observation_count, 3)
        self.assertEqual(coverage.keyword_graph_edge_count, 10)
        self.assertEqual(coverage.variation_graph_edge_count, 2)
        self.assertEqual(coverage.provider_count, 2)
        self.assertFalse(
            any("score" in key or "percentage" in key or "ranking" in key for key in coverage.to_dict())
        )

    def test_product_detail_observations_create_inventory_not_extra_graph_edges(self) -> None:
        detail_only = build(self.detail)
        self.assertEqual(
            {item.product_identity.asin for item in detail_only.observed_product_inventory},
            {"B0G2VV4RBW", "B0G2VVX3ML"},
        )
        self.assertEqual(len(keyword_edges(detail_only)), 0)
        self.assertEqual(len(variation_edges(detail_only)), 1)


class LineageCollisionAndValidationTests(CompetitionFixtureCase):
    def test_validate_against_bundles_replays_complete_lineage(self) -> None:
        self.assertIs(
            self.snapshot.validate_against_bundles(
                (self.detail, self.variations, self.reverse, self.forward)
            ),
            self.snapshot,
        )

    def test_validate_against_bundles_rejects_wrong_type_and_fingerprint(self) -> None:
        with self.assertRaises(CompetitionIntelligenceValidationError):
            self.snapshot.validate_against_bundles(({},))  # type: ignore[arg-type]
        with self.assertRaises(CompetitionIntelligenceValidationError):
            self.snapshot.validate_against_bundles((self.forward,))

    def test_validate_against_bundles_rejects_orphan_raw_lineage(self) -> None:
        orphan = replace(
            self.snapshot.lineage_index[0], raw_evidence_id="raw:competition-orphan"
        )
        payload = self.snapshot.to_dict()
        payload["lineage_index"][0] = orphan.to_dict()
        payload["lineage_index"] = sorted(payload["lineage_index"], key=canonical_json)
        payload.pop("snapshot_id")
        payload["snapshot_id"] = deterministic_id("competition-snapshot", payload)
        tampered = CompetitionIntelligenceSnapshotV0_1.from_dict(payload)
        with self.assertRaises(CompetitionIntelligenceValidationError):
            tampered.validate_against_bundles(
                (self.forward, self.reverse, self.variations, self.detail)
            )

    def test_builder_rejects_observation_identity_collision(self) -> None:
        old = next(
            item
            for item in self.forward.observations
            if isinstance(item, ProductKeywordRelationshipObservation)
            and item.channel is Channel.ORGANIC
        )
        changed = replace(old, channel=Channel.MIXED)
        colliding = replace(
            self.forward,
            observations=tuple(changed if item.observation_id == old.observation_id else item for item in self.forward.observations),
        ).validate()
        with self.assertRaises(CompetitionIdentityCollisionError):
            build(self.forward, colliding)


class DeterminismSerializationAndScopeTests(CompetitionFixtureCase):
    def test_request_and_snapshot_are_deeply_immutable(self) -> None:
        request = CompetitionIntelligenceRequest(canonical_bundles=(self.forward,))
        with self.assertRaises(FrozenInstanceError):
            request.canonical_bundles = ()  # type: ignore[misc]
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.snapshot_id = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            self.snapshot.coverage.channel_counts["ORGANIC"] = 99  # type: ignore[index]

    def test_same_process_and_bundle_order_are_deterministic(self) -> None:
        first = build(self.forward, self.reverse, self.variations, self.detail)
        second = build(self.forward, self.reverse, self.variations, self.detail)
        reordered = build(self.detail, self.variations, self.reverse, self.forward)
        self.assertEqual(first.snapshot_id, second.snapshot_id)
        self.assertEqual(first.snapshot_id, reordered.snapshot_id)
        self.assertEqual(canonical_json(first), canonical_json(reordered))

    def test_fresh_process_is_deterministic(self) -> None:
        script = r'''
import json
from pathlib import Path
import sys
from amazon_product_intelligence.adapters import AdaptationContext, XiYouAdapterV0_1
from amazon_product_intelligence.competition_intelligence import CompetitionIntelligenceBuilderV0_1, CompetitionIntelligenceRequest
payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
context = AdaptationContext(
    provider="xiyou", payload_kind="keyword_asin_analysis", source_tool="get_keyword_asin_analysis",
    marketplace="US", locale="en-us", retrieved_at="2026-08-14T09:00:00Z",
    transformed_at="2026-08-14T09:01:00Z", collection_run_id="collection:fresh:competition",
    sanitized_request={"keyword":"plastic spoons"}, currency="USD",
)
bundle = XiYouAdapterV0_1().adapt(payload, context).bundle
snapshot = CompetitionIntelligenceBuilderV0_1().build(CompetitionIntelligenceRequest(canonical_bundles=(bundle,)))
print(snapshot.snapshot_id)
'''
        command = [
            sys.executable,
            "-c",
            script,
            str(FIXTURES / "xiyou_keyword_forward_populated.json"),
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
        self.assertTrue(first.startswith("competition-snapshot:"))

    def test_strict_serialization_round_trip(self) -> None:
        reconstructed = CompetitionIntelligenceSnapshotV0_1.from_dict(
            json.loads(canonical_json(self.snapshot))
        )
        self.assertEqual(reconstructed, self.snapshot)
        self.assertEqual(canonical_json(reconstructed), canonical_json(self.snapshot))

    def test_unknown_field_is_rejected(self) -> None:
        payload = self.snapshot.to_dict()
        payload["competitor_set"] = []
        with self.assertRaises(CompetitionSerializationError):
            CompetitionIntelligenceSnapshotV0_1.from_dict(payload)

    def test_snapshot_identity_mismatch_is_rejected(self) -> None:
        payload = self.snapshot.to_dict()
        payload["snapshot_id"] = "competition-snapshot:incorrect"
        with self.assertRaises(CompetitionSerializationError):
            CompetitionIntelligenceSnapshotV0_1.from_dict(payload)

    def test_snapshot_contains_no_competitor_conclusion_score_or_recommendation(self) -> None:
        payload = canonical_json(self.snapshot).casefold()
        for forbidden in (
            "competitor_edge",
            "competitor_set",
            "competitor_count",
            "competitor_score",
            "competition_intensity",
            "market_share",
            "opportunity_score",
            "recommendation",
            "product_ranking",
        ):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main()
