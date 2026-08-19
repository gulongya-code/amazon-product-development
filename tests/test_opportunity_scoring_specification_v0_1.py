from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = (
    ROOT
    / "docs"
    / "intelligence"
    / "OPPORTUNITY_SCORING_SPECIFICATION_V0.1.md"
)
START_MARKER = "<!-- MACHINE-READABLE-SPEC:START -->"
END_MARKER = "<!-- MACHINE-READABLE-SPEC:END -->"


def specification_text() -> str:
    return SPECIFICATION.read_text(encoding="utf-8")


def specification_manifest() -> dict[str, object]:
    text = specification_text()
    if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
        raise AssertionError("specification must contain one machine-readable manifest")
    payload = text.split(START_MARKER, 1)[1].split(END_MARKER, 1)[0].strip()
    if not payload.startswith("```json\n") or not payload.endswith("\n```"):
        raise AssertionError("manifest must be a fenced JSON document")
    return json.loads(payload.removeprefix("```json\n").removesuffix("\n```"))


class OpportunityScoringSpecificationV01Tests(unittest.TestCase):
    def test_versions_and_non_executable_boundary_are_explicit(self) -> None:
        manifest = specification_manifest()
        self.assertEqual(
            "opportunity-scoring-specification-v0.1",
            manifest["specification_version"],
        )
        self.assertEqual("opportunity-score-v0.1", manifest["reserved_score_version"])
        self.assertEqual("opportunity-score-metrics-v0.1", manifest["metric_definition_version"])
        self.assertEqual("opportunity-score-missing-policy-v0.1", manifest["missing_policy_version"])
        self.assertEqual("NON_EXECUTABLE", manifest["execution_status"])
        self.assertIs(manifest["evaluator_implemented"], False)
        for version_name in (
            "normalization_version",
            "weight_version",
            "aggregation_version",
            "confidence_policy_version",
        ):
            with self.subTest(version=version_name):
                self.assertEqual(
                    "UNASSIGNED_BUSINESS_DECISION_REQUIRED",
                    manifest[version_name],
                )

    def test_all_dimensions_have_complete_contracts(self) -> None:
        manifest = specification_manifest()
        dimensions = manifest["dimensions"]
        self.assertIsInstance(dimensions, list)
        expected = {
            "DEMAND_POTENTIAL",
            "COMPETITION_ACCESSIBILITY",
            "PRODUCT_ECONOMICS_READINESS",
            "MARKET_AND_PRODUCT_CONTEXT",
            "DATA_CONFIDENCE_AND_COMPLETENESS",
            "RISK_AND_LIMITATIONS",
        }
        self.assertEqual(expected, {item["dimension_id"] for item in dimensions})
        required = {
            "dimension_id",
            "classification",
            "purpose",
            "business_meaning",
            "owner_layer",
            "normalization_requirement",
            "missing_policy",
            "quality_impact",
            "confidence",
            "formula_status",
            "executable",
            "metric_ids",
        }
        for dimension in dimensions:
            with self.subTest(dimension=dimension["dimension_id"]):
                self.assertEqual(required, set(dimension))
                self.assertTrue(all(dimension[field] for field in required - {"executable"}))
                self.assertIs(dimension["executable"], False)
                self.assertIsInstance(dimension["metric_ids"], list)
                self.assertGreater(len(dimension["metric_ids"]), 0)

    def test_all_metrics_have_owner_direction_normalization_missing_and_quality(self) -> None:
        manifest = specification_manifest()
        metrics = manifest["metrics"]
        self.assertIsInstance(metrics, list)
        self.assertEqual(len(metrics), len({metric["metric_id"] for metric in metrics}))
        required = {
            "metric_id",
            "owner",
            "direction",
            "normalization",
            "missing_policy",
            "quality_impact",
            "formula_status",
            "executable",
        }
        legal_directions = {"POSITIVE", "NEGATIVE", "NEUTRAL"}
        for metric in metrics:
            with self.subTest(metric=metric["metric_id"]):
                self.assertEqual(required, set(metric))
                self.assertTrue(all(metric[field] for field in required - {"executable"}))
                self.assertIn(metric["direction"], legal_directions)
                self.assertIn("NO_ZERO_FILL", metric["missing_policy"])
                self.assertIs(metric["executable"], False)

        dimension_metric_ids = {
            metric_id
            for dimension in manifest["dimensions"]
            for metric_id in dimension["metric_ids"]
        }
        self.assertEqual(
            {metric["metric_id"] for metric in metrics},
            dimension_metric_ids,
        )

    def test_no_undefined_formula_is_marked_executable(self) -> None:
        manifest = specification_manifest()
        legal_non_executable_statuses = {
            "BUSINESS_DECISION_REQUIRED",
            "BLOCKED_DEPENDENCY",
            "NOT_APPLICABLE_CONTEXT_ONLY",
        }
        records = [*manifest["dimensions"], *manifest["metrics"]]
        for record in records:
            with self.subTest(record=record.get("dimension_id", record.get("metric_id"))):
                self.assertIn(record["formula_status"], legal_non_executable_statuses)
                self.assertIs(record["executable"], False)
        self.assertNotIn("OpportunityScoreEvaluator", specification_text())

    def test_existing_process_score_is_excluded_from_business_score(self) -> None:
        boundary = specification_manifest()["existing_process_score_boundary"]
        self.assertEqual(
            "workbook.opportunity_analysis.rule_process_score",
            boundary["field_id"],
        )
        self.assertEqual(25, boundary["fixed_component_value"])
        self.assertEqual(
            "PROCESS_RULE_ALLOCATION_NOT_BUSINESS_DESIRABILITY",
            boundary["meaning"],
        )
        self.assertIs(boundary["included_in_opportunity_score"], False)

    def test_blocked_dependencies_and_excluded_inputs_are_complete(self) -> None:
        manifest = specification_manifest()
        self.assertEqual(
            {
                "BLOCKED_BY_ESTIMATE_METHOD",
                "BLOCKED_BY_MEMBERSHIP_SOURCE",
                "BLOCKED_BY_PROFITABILITY_INPUTS",
                "BLOCKED_BY_TREND_DEFINITION",
                "BLOCKED_BY_VARIATION_GRAIN",
                "BLOCKED_BY_SELLER_IDENTITY",
                "BLOCKED_BY_BSR_DIRECTION_POLICY",
                "BLOCKED_BY_CPC_DIRECTION_POLICY",
                "BLOCKED_BY_SCORING_CONFIGURATION",
            },
            set(manifest["blocked_dependencies"]),
        )
        excluded = set(manifest["excluded_inputs"])
        self.assertIn("workbook.product_structure.minimum_comparable_price", excluded)
        self.assertIn("workbook.product_structure.maximum_comparable_price", excluded)
        self.assertIn("workbook.market_overview.evidence_backed_trend", excluded)
        self.assertIn("workbook.opportunity_analysis.rule_process_score", excluded)
        self.assertIn("AI_GENERATED_SCORE", excluded)

    def test_business_decision_queue_has_p0_p1_and_p2_without_hidden_choice(self) -> None:
        queue = specification_manifest()["decision_queue"]
        self.assertEqual({"P0", "P1", "P2"}, set(queue))
        self.assertGreaterEqual(len(queue["P0"]), 10)
        self.assertGreaterEqual(len(queue["P1"]), 5)
        self.assertGreaterEqual(len(queue["P2"]), 3)
        self.assertIn("WEIGHT_SOURCE_AND_VALUES", queue["P0"])
        self.assertIn("MISSING_AND_PARTIAL_SCORE_POLICY", queue["P0"])
        self.assertIn("CATEGORY_SPECIFIC_CONFIGURATION", queue["P1"])
        self.assertIn("DISPLAY_FORMAT_LABELS_AND_COLORS", queue["P2"])

    def test_output_and_provenance_contracts_are_documented(self) -> None:
        text = specification_text()
        for required in (
            "`score_value`",
            "`score_status`",
            "`score_version`",
            "dimension records",
            "contributing metrics",
            "missing inputs",
            "confidence/completeness result",
            "risk and limitation evidence",
            "end-to-end provenance",
            "RawEvidenceRef",
            "Provider",
        ):
            with self.subTest(required=required):
                self.assertIn(required, text)
        self.assertIn("must never be serialized or displayed as only a number", text)


if __name__ == "__main__":
    unittest.main()
