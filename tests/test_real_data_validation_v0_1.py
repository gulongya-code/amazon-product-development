from __future__ import annotations

from dataclasses import FrozenInstanceError
from copy import deepcopy
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.real_data_validation import (
    REAL_DATA_VALIDATION_VERSION,
    AttributeAccuracyReport,
    AttributeDimensionAccuracy,
    ModuleVersion,
    ValidationAnalysisWindow,
    ValidationCategoryScope,
    ValidationDataSource,
    ValidationDiagnostic,
    ValidationIssueCategory,
    ValidationSeverity,
    ValidationStageStatus,
    build_stage_coverage,
    build_validation_issue,
    build_validation_issue_log,
    build_validation_run_snapshot,
    render_validation_report,
)
from amazon_product_intelligence.real_data_validation.live_pipeline import run
from amazon_product_intelligence.real_data_validation.live_pipeline import (
    RealDataValidationPipelineV0_1,
)
from amazon_product_intelligence.connectors import TransportResponse


ROOT = Path(__file__).resolve().parents[1]


class _SequenceHttpTransport:
    def __init__(self, payloads):
        self.payloads = payloads

    def execute(self, request):
        return TransportResponse(
            status_code=200,
            payload=deepcopy(self.payloads[request.operation]),
            metadata={"trace_id": f"offline:{request.operation}", "cost_credits": "0"},
        )


class RealDataValidationContractTests(unittest.TestCase):
    def test_stage_coverage_preserves_unknown_separately_from_failure(self) -> None:
        coverage = build_stage_coverage(
            stage="Attribute Extraction",
            input_count=500,
            output_count=175,
            failure_count=0,
            unknown_count=325,
            covered_count=175,
        )
        self.assertEqual(coverage.coverage, "0.3500")
        self.assertEqual(coverage.unknown_rate, "0.6500")
        self.assertIs(coverage.status, ValidationStageStatus.PARTIAL)

    def test_issue_log_is_typed_versioned_and_deterministic(self) -> None:
        issue = build_validation_issue(
            category=ValidationIssueCategory.DATA_QUALITY,
            severity=ValidationSeverity.WARNING,
            title="Review evidence unavailable",
            problem="The provider returned no review text.",
            affected_modules=("buyer_need_map",),
            recommended_fix="Add an audited review source in a later task.",
        )
        first = build_validation_issue_log((issue,))
        second = build_validation_issue_log((issue,))
        self.assertEqual(first, second)
        self.assertEqual(first.version, REAL_DATA_VALIDATION_VERSION)
        self.assertEqual(first.issues[0].category, ValidationIssueCategory.DATA_QUALITY)

    def test_validation_run_has_required_contract_fields_and_stable_id(self) -> None:
        issue_log = build_validation_issue_log(())
        values = dict(
            category_scope=ValidationCategoryScope(
                category="Pet Supplies",
                subcategory="Dog Travel Water Bottles",
                cohort_query="dog water bottle",
                inclusion_rule="Bounded live keyword cohort.",
            ),
            marketplace="US",
            analysis_window=ValidationAnalysisWindow(
                period_label="last7days",
                period_start=None,
                period_end=None,
                retrieved_at="2026-08-20T00:00:00+00:00",
            ),
            data_source=(
                ValidationDataSource(
                    provider="XiYou OpenAPI V2",
                    operation="asin_info",
                    source_reference="POST /v1/asins/info",
                    live_request=True,
                ),
            ),
            pipeline_version="product-intelligence-pipeline-validation-v0.1",
            module_versions=(ModuleVersion(module="product_intelligence", version="v0.1"),),
            coverage=(
                build_stage_coverage(
                    stage="Data Input",
                    input_count=100,
                    output_count=100,
                    failure_count=0,
                    unknown_count=0,
                ),
            ),
            limitations=("Review text unavailable.",),
            diagnostics=(
                ValidationDiagnostic(
                    code="EXAMPLE",
                    severity=ValidationSeverity.INFO,
                    stage="Data Input",
                    message="Contract fixture.",
                ),
            ),
            issue_log=issue_log,
        )
        first = build_validation_run_snapshot(**values)
        second = build_validation_run_snapshot(**values)
        self.assertEqual(first.run_id, second.run_id)
        self.assertEqual(first.to_dict()["marketplace"], "US")
        self.assertEqual(first.to_dict()["version"], REAL_DATA_VALIDATION_VERSION)
        with self.assertRaises(FrozenInstanceError):
            first.marketplace = "CA"  # type: ignore[misc]

    def test_attribute_report_keeps_unknown_out_of_accuracy_denominator(self) -> None:
        dimension = AttributeDimensionAccuracy(
            dimension="capacity",
            correct_count=20,
            error_count=0,
            unknown_count=80,
            sample_count=100,
            accuracy="1.0000",
            known_coverage="0.2000",
        )
        material = {
            "sample_size": 100,
            "population_size": 200,
            "sampling_method": "Deterministic sample.",
            "evidence_basis": "Source-title concordance.",
            "dimensions": (dimension,),
            "limitations": ("No structured ground truth.",),
            "version": REAL_DATA_VALIDATION_VERSION,
        }
        report = AttributeAccuracyReport(
            report_id=deterministic_id("attribute-accuracy-report", material),
            **material,
        )
        self.assertEqual(report.dimensions[0].accuracy, "1.0000")
        self.assertEqual(report.dimensions[0].known_coverage, "0.2000")

    def test_cli_requires_explicit_live_gate_before_any_provider_call(self) -> None:
        with self.assertRaises(SystemExit) as raised:
            run(["--policy", str(Path("policy.json"))])
        self.assertIn("--live is required", str(raised.exception))

    def test_existing_modules_compose_end_to_end_with_captured_payloads(self) -> None:
        fixture_root = ROOT / "tests" / "fixtures"
        forward = json.loads(
            (fixture_root / "provider_adapters" / "v0_1" / "xiyou_keyword_forward_populated.json").read_text(
                encoding="utf-8"
            )
        )["data"]
        product = json.loads(
            (fixture_root / "data_cleaning_v0_1" / "xiyou_asin_info_http_v2.json").read_text(
                encoding="utf-8"
            )
        )
        keyword = json.loads(
            (fixture_root / "provider_adapters" / "v0_1" / "xiyou_keyword_info.json").read_text(
                encoding="utf-8"
            )
        )["data"]
        asin = product["entities"][0]["asin"]
        forward["list"][0]["asin"] = asin
        forward["total"] = 1
        keyword["list"] = [deepcopy(keyword["list"][0]), deepcopy(keyword["list"][0])]
        keyword["list"][0]["searchTerm"] = "portable dog water bottle"
        keyword["list"][1]["searchTerm"] = "leakproof dog water bottle"
        keyword["total"] = 2
        pipeline = RealDataValidationPipelineV0_1(
            policy_path=(
                fixture_root
                / "opportunity_scoring"
                / "opportunity_score_policy_integration_v0_1.json"
            ),
            policy_version="opportunity-score-policy-v0.1",
            cohort_size=1,
            sample_size=1,
            need_queries=(
                "portable dog water bottle",
                "leakproof dog water bottle",
            ),
            environment={"XIYOU_API_KEY": "offline-test-only"},
        )
        pipeline._http = _SequenceHttpTransport(  # type: ignore[assignment]
            {
                "keyword_asin_analysis": forward,
                "asin_info": product,
                "keyword_info": keyword,
            }
        )
        result = pipeline.run()
        self.assertEqual(result.provider_summary["cohort_returned"], 1)
        self.assertEqual(result.attribute_accuracy.sample_size, 1)
        self.assertEqual(len(result.opportunity_ranking_review), 2)
        self.assertIn(
            "DETERMINISTIC_SCORE_REPLAY_MATCHED",
            {item.code for item in result.validation_run.diagnostics},
        )
        report = render_validation_report(result, baseline_commit="c25d9eeb")
        for heading in (
            "## 3. Pipeline 运行结果",
            "## 5. Attribute 验证",
            "## 6. Category Product Map 验证",
            "## 7. Buyer Need 验证",
            "## 8. Supply/Demand Gap 验证",
            "## 9. Opportunity Score 验证",
            "## 10. 发现问题",
        ):
            self.assertIn(heading, report)
        self.assertIn("Baseline commit: `c25d9eeb`", report)


if __name__ == "__main__":
    unittest.main()
