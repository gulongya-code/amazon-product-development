from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from amazon_product_intelligence.connectors import (
    HttpJsonTransport,
    SORFTIME_ORIGIN,
)
from amazon_product_intelligence.production_pipeline import (
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunStatus,
    ProductionRunValidationError,
    ProviderUsageSemantics,
    ProviderUsageUnit,
)
import amazon_product_intelligence.production_pipeline.orchestrator as orchestrator
from amazon_product_intelligence.production_pipeline.orchestrator import (
    ProductionPipelineOrchestrator,
)
from amazon_product_intelligence.production_pipeline.planner import build_acquisition_plan
from amazon_product_intelligence.production_pipeline.providers import FixtureTransport

from test_production_pipeline_sp_040e import (
    ASIN,
    RecordingDelivery,
    SORFTIME_FIXTURE,
    request,
    sorftime_runtime,
)


class ProductFaultTransport:
    def __init__(self) -> None:
        self.operations: list[str] = []
        self.network_call_count = 0

    def execute(self, request):
        self.operations.append(request.operation)
        raise OSError("injected deterministic offline fault")


class SorftimeLiveRuntimeTests(unittest.TestCase):
    _RELEASE_FLAG = (
        "amazon_product_intelligence.production_pipeline.orchestrator."
        "_SORFTIME_V0_1_LIVE_RELEASE_ENABLED"
    )

    def test_default_live_runtime_is_pinned_single_attempt_sorftime_only(self):
        with patch(self._RELEASE_FLAG, True), TemporaryDirectory() as directory:
            run_request = request(Path(directory), mode=ProductionRunMode.LIVE)
            runtime = ProductionPipelineOrchestrator._default_provider_runtime(run_request)
        self.assertEqual(runtime.provider.provider_id, "sorftime")
        self.assertEqual(
            tuple(item.provider_id for item in runtime.registry.enabled()),
            ("sorftime",),
        )
        configuration = runtime.registry.configuration("sorftime")
        self.assertEqual(configuration.max_attempts, 1)
        self.assertEqual(configuration.credential_env, "SORFTIME_API_KEY")
        self.assertIsNone(runtime.credit_semantics)
        self.assertEqual(
            runtime.usage_semantics,
            ProviderUsageSemantics.LIVE_PROVIDER_REPORTED,
        )
        self.assertIsInstance(runtime.recording_transport.wrapped, HttpJsonTransport)
        self.assertEqual(
            runtime.recording_transport.wrapped.base_origin("sorftime"),
            SORFTIME_ORIGIN,
        )

    def test_injected_live_path_succeeds_with_exact_usage_and_no_credits(self):
        fixture = json.loads(SORFTIME_FIXTURE.read_text(encoding="utf-8"))
        transport = FixtureTransport(fixture)
        with patch(self._RELEASE_FLAG, True), TemporaryDirectory() as directory:
            result = ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: sorftime_runtime(
                    transport,
                    usage_semantics=ProviderUsageSemantics.LIVE_PROVIDER_REPORTED,
                ),
                delivery=RecordingDelivery(),
            ).run(request(Path(directory), mode=ProductionRunMode.LIVE))
            self.assertEqual(result.status, ProductionRunStatus.SUCCEEDED)
            self.assertEqual(set(result.artifact_paths), {
                "market_report_json", "operator_xlsx", "operator_markdown", "run_manifest"
            })
        summary = result.provider_summary
        assert summary is not None and summary.provider_usage is not None
        self.assertEqual(summary.provider_id, "sorftime")
        self.assertEqual(summary.operations, ("ProductRequest", "ASINRequestKeyword"))
        self.assertEqual(summary.transport_attempt_count, 2)
        self.assertEqual(summary.executed_operation_count, 2)
        self.assertEqual(summary.replayed_operation_count, 0)
        self.assertIsNone(summary.credits)
        self.assertIsNone(summary.credit_semantics)
        self.assertEqual(summary.provider_usage.unit, ProviderUsageUnit.REQUEST)
        self.assertEqual(summary.provider_usage.consumed, 2)
        self.assertEqual(summary.provider_usage.remaining, 1346)
        self.assertEqual(
            summary.provider_usage.semantics,
            ProviderUsageSemantics.LIVE_PROVIDER_REPORTED,
        )
        self.assertEqual(transport.network_call_count, 0)

    def test_live_usage_mismatch_blocks_release_without_normalization(self):
        fixture = json.loads(SORFTIME_FIXTURE.read_text(encoding="utf-8"))
        fixture = deepcopy(fixture)
        fixture["operations"]["ProductRequest"][ASIN]["payload"]["RequestConsumed"] = 2
        transport = FixtureTransport(fixture)
        with patch(self._RELEASE_FLAG, True), TemporaryDirectory() as directory:
            result = ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: sorftime_runtime(
                    transport,
                    usage_semantics=ProviderUsageSemantics.LIVE_PROVIDER_REPORTED,
                ),
                delivery=RecordingDelivery(),
            ).run(request(Path(directory), mode=ProductionRunMode.LIVE))
        self.assertEqual(result.status, ProductionRunStatus.FAILED)
        self.assertEqual(result.error["code"], "PROVIDER_FAILURE")
        self.assertEqual(result.provider_summary.provider_usage.consumed, 3)
        self.assertEqual(transport.execute_count, 2)

    def test_product_failure_has_one_attempt_no_keyword_and_no_retry(self):
        transport = ProductFaultTransport()
        with patch(self._RELEASE_FLAG, True), TemporaryDirectory() as directory:
            result = ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: sorftime_runtime(
                    transport,
                    usage_semantics=ProviderUsageSemantics.LIVE_PROVIDER_REPORTED,
                ),
                delivery=RecordingDelivery(),
            ).run(request(Path(directory), mode=ProductionRunMode.LIVE))
        self.assertEqual(result.status, ProductionRunStatus.FAILED)
        self.assertEqual(transport.operations, ["ProductRequest"])
        self.assertEqual(result.provider_summary.transport_attempt_count, 1)
        self.assertEqual(result.provider_summary.operations, ("ProductRequest",))
        self.assertIsNone(result.provider_summary.provider_usage.consumed)

    def test_live_scope_gates_precede_runtime_construction(self):
        cases = (
            {"asins": ("B09TSGDJLD",)},
            {"marketplace": "CA"},
            {"resume_from": Path("offline-source")},
        )
        for overrides in cases:
            calls: list[str] = []
            with (
                self.subTest(overrides=overrides),
                patch(self._RELEASE_FLAG, True),
                TemporaryDirectory() as directory,
            ):
                result = ProductionPipelineOrchestrator(
                    provider_runtime_factory=lambda _: calls.append("constructed"),  # type: ignore[arg-type]
                    delivery=RecordingDelivery(),
                ).run(
                    request(
                        Path(directory),
                        mode=ProductionRunMode.LIVE,
                        **overrides,
                    )
                )
                self.assertEqual(result.status, ProductionRunStatus.FAILED)
                self.assertEqual(calls, [])

    def test_v0_2_live_and_unknown_provider_remain_blocked(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ProductionRunValidationError):
                request(
                    Path(directory),
                    mode=ProductionRunMode.LIVE,
                    report_version="market-report-v0.2",
                )
            with self.assertRaises(ProductionRunValidationError):
                request(Path(directory), provider_preference="other")

    def test_r7_pass_keeps_sorftime_v0_1_live_gate_enabled(self):
        self.assertIs(orchestrator._SORFTIME_V0_1_LIVE_RELEASE_ENABLED, True)

    def test_plan_remains_exactly_two_operations_without_variations(self):
        plan = build_acquisition_plan(
            provider_id="sorftime", marketplace="US", asins=(ASIN,)
        )
        self.assertEqual(
            tuple(item.operation for item in plan.steps),
            ("ProductRequest", "ASINRequestKeyword"),
        )
        self.assertEqual(len(plan.steps), 2)
        self.assertEqual(dict(plan.steps[0].parameters), {"ASIN": ASIN, "Trend": 2})
        self.assertEqual(
            dict(plan.steps[1].parameters),
            {"ASIN": ASIN, "PageIndex": 1, "PageSize": 20},
        )


if __name__ == "__main__":
    unittest.main()
