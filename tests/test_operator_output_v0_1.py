from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.operator_output as operator_output
from amazon_product_intelligence.competition_intelligence import (
    CompetitionIntelligenceBuilderV0_1,
    CompetitionIntelligenceRequest,
)
from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.demand_intelligence import (
    DemandIntelligenceBuilderV0_1,
    DemandIntelligenceRequest,
)
from amazon_product_intelligence.opportunity_intelligence import (
    OpportunityIntelligenceBuilderV0_1,
    OpportunityIntelligenceRequest,
)
from amazon_product_intelligence.operator_output import (
    OPERATOR_OUTPUT_RULESET_VERSION,
    OperatorOutputBuilderV0_1,
    OperatorOutputRequest,
    OperatorOutputSerializationError,
    OperatorOutputSnapshotV0_1,
    OperatorOutputValidationError,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)
from tests.test_competition_intelligence_v0_1 import adapt as competition_adapt
from tests.test_conflict_resolution_v0_1 import (
    build_evaluation,
    build_resolution,
    synthetic_bundles,
)
from tests.test_decision_framework_v0_1 import build_decision
from tests.test_demand_intelligence_v0_1 import (
    adapt as demand_adapt,
    first_keyword,
)
from tests.test_evidence_policy_v0_1 import build_policy
from tests.test_opportunity_intelligence_v0_1 import adapt as opportunity_adapt
from tests.test_opportunity_scoring_v0_1 import build_score
from tests.test_product_intelligence_v0_1 import (
    adapt as product_adapt,
    target as product_target,
)
from tests.test_recommendation_framework_v0_1 import build_recommendation


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
OUTPUT_SOURCE = SOURCE_ROOT / "amazon_product_intelligence" / "operator_output"


def build_fixture():
    product_bundles = (
        product_adapt("xiyou", "asin_info"),
        product_adapt("xiyou", "asin_variations"),
        product_adapt("sorftime", "product_detail"),
        product_adapt("sorftime", "product_reviews"),
    )
    demand_results = (
        demand_adapt("xiyou_keyword_info.json", "keyword_info"),
        demand_adapt(
            "xiyou_keyword_forward_populated.json",
            "keyword_asin_analysis",
            request={"keyword": "plastic spoons"},
        ),
    )
    if any(not item.succeeded for item in demand_results):
        raise AssertionError("demand fixture adaptation failed")
    demand_bundles = tuple(item.bundle for item in demand_results)
    competition_bundles = (
        competition_adapt(
            provider="xiyou",
            fixture="xiyou_keyword_forward_populated.json",
            payload_kind="keyword_asin_analysis",
            source_tool="get_keyword_asin_analysis",
            request={"keyword": "plastic spoons"},
        ),
        competition_adapt(
            provider="xiyou",
            fixture="xiyou_asin_keywords_reverse.json",
            payload_kind="asin_keywords",
            source_tool="get_asin_keywords",
            request={"asin": "B0G2VV4RBW"},
        ),
        competition_adapt(
            provider="xiyou",
            fixture="xiyou_asin_variations.json",
            payload_kind="asin_variations",
            source_tool="get_asin_variations",
            request={"asin": "B0G2VV4RBW"},
        ),
        competition_adapt(
            provider="sorftime",
            fixture="sorftime_product_detail.json",
            payload_kind="product_detail",
            source_tool="product_detail",
            request={"asin": "B0G2VV4RBW"},
        ),
    )
    opportunity_bundles = tuple(opportunity_adapt(case) for case in (
        "keyword", "forward", "reverse", "variations", "detail", "reviews"
    ))
    scoring_bundles = synthetic_bundles()
    bundles = (
        product_bundles + demand_bundles + competition_bundles
        + opportunity_bundles + scoring_bundles
    )
    product = ProductIntelligenceBuilderV0_1().build(ProductIntelligenceRequest(
        target_product_identity=product_target(),
        scope=ProductScope.EXACT_PRODUCT,
        canonical_bundles=product_bundles,
    ))
    keyword = first_keyword(demand_bundles[0], "search_volume")
    demand = DemandIntelligenceBuilderV0_1().build(DemandIntelligenceRequest(
        target_keyword_identity=keyword,
        canonical_bundles=demand_bundles,
    ))
    competition = CompetitionIntelligenceBuilderV0_1().build(
        CompetitionIntelligenceRequest(canonical_bundles=competition_bundles)
    )
    opportunity = OpportunityIntelligenceBuilderV0_1().build(
        OpportunityIntelligenceRequest(canonical_bundles=opportunity_bundles)
    )
    evaluation = build_evaluation(*scoring_bundles)
    conflict = build_resolution(scoring_bundles, evaluation)
    policy = build_policy(scoring_bundles, evaluation, conflict)
    decision = build_decision(scoring_bundles, evaluation, conflict, policy)
    scoring = build_score(scoring_bundles, evaluation, conflict, policy, decision)
    recommendation = build_recommendation(
        scoring_bundles, evaluation, conflict, policy, decision, scoring
    )
    sources = (product, demand, competition, opportunity, scoring, recommendation)
    request = OperatorOutputRequest(
        canonical_bundles=bundles,
        product_intelligence_snapshot=product.to_dict(),
        demand_intelligence_snapshot=demand.to_dict(),
        competition_intelligence_snapshot=competition.to_dict(),
        opportunity_intelligence_snapshot=opportunity.to_dict(),
        opportunity_scoring_snapshot=scoring.to_dict(),
        recommendation_framework_snapshot=recommendation.to_dict(),
    )
    snapshot = OperatorOutputBuilderV0_1().build(request)
    return bundles, sources, request, snapshot


def recalculate_source_snapshot_id(payload: dict[str, object], prefix: str) -> None:
    content = dict(payload)
    content.pop("snapshot_id")
    payload["snapshot_id"] = deterministic_id(prefix, content)


def recalculate_output_snapshot_id(payload: dict[str, object]) -> None:
    content = dict(payload)
    content.pop("snapshot_id")
    payload["snapshot_id"] = deterministic_id("operator-output-snapshot", content)


def mutate_output_lineage(
    payload: dict[str, object], index: int, **changes: object
) -> None:
    lineage = payload["lineage_index"][index]
    old_id = lineage["output_lineage_id"]
    lineage.update(changes)
    content = dict(lineage)
    content.pop("output_lineage_id")
    new_id = deterministic_id("operator-output-lineage", content)
    lineage["output_lineage_id"] = new_id
    for name in (
        "product_rows", "keyword_rows", "competition_rows",
        "opportunity_rows", "recommendation_rows",
    ):
        for row in payload[name]:
            row["lineage_reference_ids"] = sorted(
                new_id if item == old_id else item
                for item in row["lineage_reference_ids"]
            )
    payload["lineage_index"] = sorted(
        payload["lineage_index"], key=lambda item: item["output_lineage_id"]
    )
    recalculate_output_snapshot_id(payload)


class OperatorOutputFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bundles, cls.sources, cls.request, cls.snapshot = build_fixture()
        (
            cls.product_source,
            cls.demand_source,
            cls.competition_source,
            cls.opportunity_source,
            cls.scoring_source,
            cls.recommendation_source,
        ) = cls.sources

    def test_public_api_is_exact_and_explicit(self):
        expected = {
            "OPERATOR_OUTPUT_RULESET_VERSION",
            "OperatorOutputRequest",
            "OperatorOutputSnapshotV0_1",
            "OperatorOutputBuilderV0_1",
            "OperatorOutputError",
            "OperatorOutputValidationError",
            "OperatorOutputSerializationError",
            "ProductOutputRow",
            "KeywordOutputRow",
            "CompetitionOutputRow",
            "OpportunityOutputRow",
            "RecommendationOutputRow",
            "OutputCoverageSummary",
            "OutputLineageReference",
            "OutputDiagnostic",
        }
        self.assertEqual(set(operator_output.__all__), expected)
        self.assertEqual(len(operator_output.__all__), 15)
        self.assertEqual(OPERATOR_OUTPUT_RULESET_VERSION, "operator-output-v0.1")

    def test_production_dependency_boundary(self):
        forbidden = {
            "product_intelligence", "demand_intelligence", "competition_intelligence",
            "opportunity_intelligence", "evidence_evaluation", "conflict_resolution",
            "evidence_policy", "decision_framework", "opportunity_scoring",
            "recommendation_framework", "adapters",
        }
        for path in OUTPUT_SOURCE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.append(node.module)
            for name in imports:
                self.assertFalse(any(part in name.split(".") for part in forbidden), (path, name))

    def test_five_operator_views_are_available(self):
        self.assertEqual(len(self.snapshot.product_rows), 1)
        self.assertEqual(len(self.snapshot.keyword_rows), 1)
        self.assertGreater(len(self.snapshot.competition_rows), 0)
        self.assertEqual(len(self.snapshot.opportunity_rows), 1)
        self.assertEqual(
            len(self.snapshot.recommendation_rows),
            len(self.recommendation_source.generation_records),
        )
        self.assertEqual(self.snapshot.coverage.source_snapshot_count, 6)

    def test_product_view_preserves_candidates_and_quality(self):
        row = self.snapshot.product_rows[0]
        self.assertEqual(row.asin, self.product_source.target_product_identity.asin)
        self.assertEqual(row.marketplace, self.product_source.target_product_identity.marketplace)
        self.assertEqual(
            {canonical_json(item) for item in row.product_facts},
            {canonical_json(item) for item in self.product_source.product_fact_evidence_sets},
        )
        self.assertEqual(
            {canonical_json(item) for item in row.metrics},
            {canonical_json(item) for item in self.product_source.product_metric_series},
        )
        self.assertEqual(
            canonical_json(row.variation_information),
            canonical_json(self.product_source.variation_topology),
        )
        self.assertEqual(
            canonical_json(row.review_summary),
            canonical_json(self.product_source.review_evidence_summary),
        )

    def test_keyword_view_preserves_direction_and_query_status(self):
        row = self.snapshot.keyword_rows[0]
        self.assertEqual(row.keyword, self.demand_source.target_keyword_identity.to_dict())
        self.assertEqual(
            {canonical_json(item) for item in row.query_status},
            {canonical_json(item) for item in self.demand_source.query_execution_evidence},
        )
        self.assertIn("DIRECTIONAL_QUERY_EVIDENCE_ONLY", row.limitations)
        outcomes = {item["outcome"] for item in row.query_status}
        self.assertTrue(outcomes)

    def test_competition_is_evidence_view_not_competitor_list(self):
        source_observation_ids = {
            item.observation_id for item in self.competition_source.keyword_relationship_evidence
        }
        output_observation_ids = {
            observation_id
            for row in self.snapshot.competition_rows
            for observation_id in row.keyword_relationship["relationship_observation_ids"]
        }
        self.assertEqual(output_observation_ids, source_observation_ids)
        self.assertTrue(all(row.evidence_count > 0 for row in self.snapshot.competition_rows))
        self.assertNotIn("competitor", canonical_json(self.snapshot.competition_rows).lower())

    def test_opportunity_view_copies_existing_score_references(self):
        row = self.snapshot.opportunity_rows[0]
        expected = {
            item.calculation_id: (item.result_status, item.result_value)
            for item in self.scoring_source.calculations
        }
        actual = {
            item["calculation_id"]: (item["result_status"], item["result_value"])
            for item in row.score_references
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            {item["signal_id"] for item in row.signals},
            {item.signal_id for item in self.opportunity_source.observed_signals + self.opportunity_source.derived_signals},
        )

    def test_recommendation_view_copies_existing_generations(self):
        expected = {
            item.recommendation_generation_id: item.recommendation_type
            for item in self.recommendation_source.generation_records
        }
        actual = {
            next(
                item.recommendation_generation_id
                for item in self.recommendation_source.generation_records
                if item.explanation_id == row.explanation["explanation_id"]
            ): row.recommendation_type
            for row in self.snapshot.recommendation_rows
        }
        self.assertEqual(actual, expected)
        self.assertTrue(all(row.limitations for row in self.snapshot.recommendation_rows))

    def test_lineage_replays_against_canonical_bundles(self):
        self.assertIs(self.snapshot.validate_against_bundles(self.bundles), self.snapshot)
        row_ids = {
            row.output_row_id
            for collection in (
                self.snapshot.product_rows,
                self.snapshot.keyword_rows,
                self.snapshot.competition_rows,
                self.snapshot.opportunity_rows,
                self.snapshot.recommendation_rows,
            )
            for row in collection
        }
        self.assertEqual({item.output_row_id for item in self.snapshot.lineage_index}, row_ids)
        self.assertTrue(all(item.raw_evidence_id for item in self.snapshot.lineage_index))

    def test_wrong_validation_bundles_fail_closed(self):
        with self.assertRaises(OperatorOutputValidationError):
            self.snapshot.validate_against_bundles(self.bundles[:-1])

    def test_csv_ready_tables_have_only_scalar_values(self):
        tables = self.snapshot.to_table_rows()
        self.assertEqual(
            set(tables),
            {"product", "keyword", "competition_evidence", "opportunity", "recommendation"},
        )
        self.assertTrue(all(tables.values()))
        for rows in tables.values():
            for row in rows:
                self.assertTrue(all(
                    value is None or type(value) in {str, bool, int, float}
                    for value in row.values()
                ))
        json.dumps(tables, allow_nan=False, ensure_ascii=False)

    def test_json_and_strict_round_trip(self):
        payload = self.snapshot.to_dict()
        restored = OperatorOutputSnapshotV0_1.from_dict(payload)
        self.assertEqual(restored, self.snapshot)
        self.assertEqual(restored.to_json(), canonical_json(self.snapshot))
        self.assertEqual(restored.snapshot_id, self.snapshot.snapshot_id)

    def test_unknown_output_fields_fail_closed(self):
        payload = self.snapshot.to_dict()
        payload["hidden"] = True
        with self.assertRaises(OperatorOutputSerializationError):
            OperatorOutputSnapshotV0_1.from_dict(payload)

    def test_snapshot_identity_mismatch_fails_closed(self):
        payload = self.snapshot.to_dict()
        payload["snapshot_id"] = "operator-output-snapshot:wrong"
        with self.assertRaises(OperatorOutputSerializationError):
            OperatorOutputSnapshotV0_1.from_dict(payload)

    def test_recomputed_lineage_cannot_claim_missing_source_record_or_wrong_view(self):
        payload = self.snapshot.to_dict()
        mutate_output_lineage(payload, 0, source_record_id="missing:source-record")
        with self.assertRaises(OperatorOutputSerializationError):
            OperatorOutputSnapshotV0_1.from_dict(payload)

        payload = self.snapshot.to_dict()
        current = payload["lineage_index"][0]["output_view"]
        wrong = "KEYWORD" if current != "KEYWORD" else "PRODUCT"
        mutate_output_lineage(payload, 0, output_view=wrong)
        with self.assertRaises(OperatorOutputSerializationError):
            OperatorOutputSnapshotV0_1.from_dict(payload)

    def test_recomputed_orphan_and_fingerprint_lineage_fail_closed(self):
        payload = self.snapshot.to_dict()
        mutate_output_lineage(payload, 0, canonical_reference_id="obs:missing")
        restored = OperatorOutputSnapshotV0_1.from_dict(payload)
        with self.assertRaises(OperatorOutputValidationError):
            restored.validate_against_bundles(self.bundles)

        payload = self.snapshot.to_dict()
        mutate_output_lineage(
            payload, 0, source_bundle_fingerprints=["0" * 64]
        )
        with self.assertRaises(OperatorOutputSerializationError):
            OperatorOutputSnapshotV0_1.from_dict(payload)

    def test_unknown_source_snapshot_fields_fail_closed(self):
        product = self.product_source.to_dict()
        product["unknown"] = "value"
        with self.assertRaises(OperatorOutputValidationError):
            replace(self.request, product_intelligence_snapshot=product)

    def test_nested_source_unknown_fields_fail_closed_in_builder(self):
        product = self.product_source.to_dict()
        product["product_fact_evidence_sets"][0]["unknown"] = "value"
        recalculate_source_snapshot_id(product, "snapshot")
        request = replace(self.request, product_intelligence_snapshot=product)
        with self.assertRaises(OperatorOutputValidationError):
            OperatorOutputBuilderV0_1().build(request)

    def test_forbidden_raw_payload_export_fails_closed(self):
        product = self.product_source.to_dict()
        product["product_fact_evidence_sets"][0]["raw_payload"] = {"secret": "x"}
        recalculate_source_snapshot_id(product, "snapshot")
        with self.assertRaises(OperatorOutputValidationError):
            replace(self.request, product_intelligence_snapshot=product)

    def test_source_snapshot_chain_mismatch_fails_closed(self):
        recommendation = self.recommendation_source.to_dict()
        recommendation["source_scoring_snapshot_id"] = "opportunity-scoring-snapshot:wrong"
        recalculate_source_snapshot_id(recommendation, "recommendation-framework-snapshot")
        with self.assertRaises(OperatorOutputValidationError):
            replace(self.request, recommendation_framework_snapshot=recommendation)

    def test_models_and_nested_context_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.snapshot.ruleset_version = "changed"  # type: ignore[misc]
        with self.assertRaises(TypeError):
            self.snapshot.source_snapshot_ids["product_intelligence"] = "changed"  # type: ignore[index]
        with self.assertRaises(TypeError):
            self.snapshot.product_rows[0].review_summary["sample_basis"] = "changed"  # type: ignore[index]

    def test_determinism_survives_bundle_and_mapping_order(self):
        source_payloads = [item.to_dict() for item in self.sources]
        reversed_payloads = [dict(reversed(list(item.items()))) for item in source_payloads]
        request = OperatorOutputRequest(
            canonical_bundles=tuple(reversed(self.bundles)),
            product_intelligence_snapshot=reversed_payloads[0],
            demand_intelligence_snapshot=reversed_payloads[1],
            competition_intelligence_snapshot=reversed_payloads[2],
            opportunity_intelligence_snapshot=reversed_payloads[3],
            opportunity_scoring_snapshot=reversed_payloads[4],
            recommendation_framework_snapshot=reversed_payloads[5],
        )
        rebuilt = OperatorOutputBuilderV0_1().build(request)
        self.assertEqual(rebuilt.snapshot_id, self.snapshot.snapshot_id)
        self.assertEqual(rebuilt.to_json(), self.snapshot.to_json())

    def test_caller_owned_payloads_are_detached(self):
        product = self.product_source.to_dict()
        request = replace(self.request, product_intelligence_snapshot=product)
        product["target_product_identity"]["asin"] = "MUTATED"
        self.assertEqual(
            request.product_intelligence_snapshot["target_product_identity"]["asin"],
            self.product_source.target_product_identity.asin,
        )

    def test_invalid_builder_input_fails_closed(self):
        with self.assertRaises(OperatorOutputValidationError):
            OperatorOutputBuilderV0_1().build(self.request.to_dict())  # type: ignore[arg-type]

    def test_cross_process_identity_is_stable(self):
        code = (
            "from tests.test_operator_output_v0_1 import build_fixture; "
            "print(build_fixture()[3].snapshot_id)"
        )
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(SOURCE_ROOT)
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=REPOSITORY_ROOT,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.stdout.strip(), self.snapshot.snapshot_id)

    def test_output_does_not_mutate_source_snapshots(self):
        before = tuple(canonical_json(item) for item in self.sources)
        OperatorOutputBuilderV0_1().build(self.request)
        after = tuple(canonical_json(item) for item in self.sources)
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
