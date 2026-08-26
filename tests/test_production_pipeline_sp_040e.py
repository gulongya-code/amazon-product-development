from __future__ import annotations

from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from amazon_product_intelligence.connectors import (
    NoRetryPolicy,
    ProviderConfig,
    ProviderRegistry,
    SORFTIME_CREDENTIAL_ENV,
    SorftimeProvider,
)
from amazon_product_intelligence.market_report.delivery import OperatorReportDeliveryResult
from amazon_product_intelligence.production_pipeline import (
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunStatus,
    ProductionRunValidationError,
    ProviderOperationExecutionSource,
    ProviderUsageUnit,
)
from amazon_product_intelligence.production_pipeline.cli import build_parser, main
from amazon_product_intelligence.production_pipeline.orchestrator import (
    ProductionPipelineOrchestrator,
    ProviderRuntime,
)
from amazon_product_intelligence.production_pipeline.planner import (
    ACQUISITION_PLAN_CONTRACT_VERSION,
    AcquisitionRole,
    build_acquisition_plan,
)
from amazon_product_intelligence.production_pipeline.providers import (
    FixtureTransport,
    RecordingTransport,
)


ROOT = Path(__file__).resolve().parents[1]
SORFTIME_FIXTURE = (
    ROOT
    / "src"
    / "amazon_product_intelligence"
    / "production_pipeline"
    / "fixtures"
    / "sorftime_b09265wxy5_v0_1.json"
)
ASIN = "B09265WXY5"


class RecordingDelivery:
    def deliver(self, source, output_directory, *, operator_workflow=None):
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        markdown = output / "operator_market_report.md"
        xlsx = output / "operator_market_report.xlsx"
        markdown.write_text(f"# Offline Sorftime fixture\n\n{source.report_id}\n", encoding="utf-8")
        with zipfile.ZipFile(xlsx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
        return OperatorReportDeliveryResult(
            source_report_id=source.report_id,
            delivery_version="operator-market-report-delivery-v0.1",
            xlsx_path=xlsx,
            markdown_path=markdown,
            xlsx_sha256=sha256(xlsx.read_bytes()).hexdigest(),
            markdown_sha256=sha256(markdown.read_bytes()).hexdigest(),
            operator_workflow_id=(operator_workflow.snapshot_id if operator_workflow else None),
        )


class KeywordFaultTransport:
    def __init__(self, fixture):
        self.fixture = FixtureTransport(fixture)
        self.operations: list[str] = []
        self.network_call_count = 0

    def execute(self, request):
        self.operations.append(request.operation)
        if request.operation == "ASINRequestKeyword":
            raise OSError("injected offline transient fault")
        return self.fixture.execute(request)


def sorftime_runtime(transport) -> ProviderRuntime:
    metadata = json.loads(SORFTIME_FIXTURE.read_text(encoding="utf-8"))
    recording = RecordingTransport(transport)
    provider = SorftimeProvider(
        recording,
        environment={SORFTIME_CREDENTIAL_ENV: "offline-fixture-sentinel"},
        retry_policy=NoRetryPolicy(),
    )
    registry = ProviderRegistry()
    registry.register(
        provider,
        ProviderConfig(
            provider_id="sorftime",
            enabled=True,
            priority=1,
            credential_env=SORFTIME_CREDENTIAL_ENV,
            timeout_seconds=1,
            max_attempts=1,
        ),
    )
    return ProviderRuntime(
        registry=registry,
        provider=provider,
        recording_transport=recording,
        metadata=metadata,
        credit_semantics=None,
    )


def request(output: Path, **overrides) -> ProductionRunRequest:
    values = {
        "marketplace": "US",
        "asins": (ASIN,),
        "output_directory": output,
        "provider_preference": "sorftime",
        "mode": ProductionRunMode.FIXTURE,
        "category_name": "dog water bottle",
        "run_id": "sp-040e-offline",
    }
    values.update(overrides)
    return ProductionRunRequest(**values)


class AcquisitionPlannerTests(unittest.TestCase):
    def test_explicit_provider_contract_and_default(self):
        with TemporaryDirectory() as directory:
            default = ProductionRunRequest(
                marketplace="US",
                asins=("B0DWB00001",),
                output_directory=Path(directory),
            )
            self.assertEqual(default.provider_preference, "xiyou")
            for invalid in ("", "XiYou", "other"):
                with self.subTest(invalid=invalid), self.assertRaises(
                    ProductionRunValidationError
                ):
                    request(Path(directory), provider_preference=invalid)

    def test_xiyou_plan_is_byte_compatible_in_shape(self):
        asins = ("B0DWB00001", "B0DWB00002")
        plan = build_acquisition_plan(provider_id="xiyou", marketplace="US", asins=asins)
        self.assertEqual(plan.contract_version, ACQUISITION_PLAN_CONTRACT_VERSION)
        self.assertEqual([item.operation for item in plan.steps], ["asin_info", "asin_keywords", "asin_keywords"])
        self.assertEqual(plan.steps[0].canonical_field, "metric.price")
        self.assertEqual(
            dict(plan.steps[1].parameters),
            {
                "asin": asins[0],
                "country": "US",
                "page": 1,
                "pageSize": 20,
                "period": "last7days",
                "sort": {"field": "traffic", "order": "desc"},
            },
        )

    def test_sorftime_plan_is_exact_minimum_and_deterministic(self):
        plan = build_acquisition_plan(provider_id="sorftime", marketplace="US", asins=(ASIN,))
        repeated = build_acquisition_plan(provider_id="sorftime", marketplace="US", asins=(ASIN,))
        self.assertEqual(plan.steps, repeated.steps)
        self.assertEqual([item.operation for item in plan.steps], ["ProductRequest", "ASINRequestKeyword"])
        self.assertEqual(dict(plan.steps[0].parameters), {"ASIN": ASIN, "Trend": 2})
        self.assertEqual(
            dict(plan.steps[1].parameters),
            {"ASIN": ASIN, "PageIndex": 1, "PageSize": 20},
        )
        self.assertEqual([item.role for item in plan.steps], [AcquisitionRole.PRODUCT, AcquisitionRole.REVERSE_KEYWORD])
        self.assertNotIn("ProductVariations", {item.operation for item in plan.steps})

    def test_sorftime_plan_is_two_n_and_immutable(self):
        plan = build_acquisition_plan(
            provider_id="sorftime", marketplace="US", asins=(ASIN, "B09TSGDJLD")
        )
        self.assertEqual(len(plan.steps), 4)
        with self.assertRaises(TypeError):
            plan.steps[0].parameters["Trend"] = 1  # type: ignore[index]
        with self.assertRaises(ValueError):
            build_acquisition_plan(provider_id="sorftime", marketplace="CA", asins=(ASIN,))

    def test_cli_provider_domain_is_exact(self):
        parser = build_parser()
        args = parser.parse_args(["run", "--market", "US", "--asin", ASIN, "--output-dir", "out"])
        self.assertEqual(args.provider, "xiyou")
        with self.assertRaises(SystemExit):
            parser.parse_args(["run", "--market", "US", "--asin", ASIN, "--provider", "other", "--output-dir", "out"])


class SorftimeFixturePipelineTests(unittest.TestCase):
    def test_fixture_e2e_uses_real_typed_provider_and_writes_four_artifacts(self):
        with TemporaryDirectory() as directory:
            result = ProductionPipelineOrchestrator(delivery=RecordingDelivery()).run(
                request(Path(directory))
            )
            self.assertEqual(result.status, ProductionRunStatus.SUCCEEDED)
            self.assertEqual(set(result.artifact_paths), {"market_report_json", "operator_xlsx", "operator_markdown", "run_manifest"})
            self.assertTrue(all(Path(path).is_file() for path in result.artifact_paths.values()))
            summary = result.provider_summary
            self.assertIsNotNone(summary)
            assert summary is not None
            self.assertEqual(summary.provider_id, "sorftime")
            self.assertEqual(summary.operations, ("ProductRequest", "ASINRequestKeyword"))
            self.assertEqual(summary.operation_count, 2)
            self.assertIsNone(summary.credits)
            self.assertIsNone(summary.credit_semantics)
            self.assertEqual(summary.provider_usage.unit, ProviderUsageUnit.REQUEST)
            self.assertEqual(summary.provider_usage.consumed, 2)
            self.assertEqual(summary.provider_usage.remaining, 1346)

            manifest = json.loads(Path(result.artifact_paths["run_manifest"]).read_text(encoding="utf-8"))
            provider = manifest["provider_summary"]
            self.assertEqual(provider["provider_usage"]["unit"], "REQUEST")
            self.assertEqual(provider["credits"], None)
            self.assertNotIn("ProductVariations", json.dumps(manifest))

    def test_default_fixture_runtime_has_zero_network_and_no_environment_credential(self):
        captured: list[ProviderRuntime] = []

        def factory(run_request):
            runtime = ProductionPipelineOrchestrator._default_provider_runtime(run_request)
            captured.append(runtime)
            return runtime

        with TemporaryDirectory() as directory:
            result = ProductionPipelineOrchestrator(
                provider_runtime_factory=factory, delivery=RecordingDelivery()
            ).run(request(Path(directory)))
        self.assertEqual(result.status, ProductionRunStatus.SUCCEEDED)
        self.assertEqual(len(captured), 1)
        wrapped = captured[0].recording_transport.wrapped
        self.assertEqual(wrapped.network_call_count, 0)
        self.assertEqual(wrapped.execute_count, 2)

    def test_live_gate_precedes_runtime_construction_and_credential_access(self):
        calls: list[str] = []

        def forbidden_factory(_request):
            calls.append("constructed")
            raise AssertionError("runtime must not be constructed")

        with TemporaryDirectory() as directory:
            result = ProductionPipelineOrchestrator(
                provider_runtime_factory=forbidden_factory, delivery=RecordingDelivery()
            ).run(request(Path(directory), mode=ProductionRunMode.LIVE))
        self.assertEqual(result.status, ProductionRunStatus.FAILED)
        self.assertEqual(calls, [])
        self.assertIn("fixture-only until SP-040F", result.error["message"])

    def test_cli_reports_requests_not_credits(self):
        with TemporaryDirectory() as directory:
            stdout, stderr = StringIO(), StringIO()
            code = main(
                [
                    "run", "--market", "US", "--asin", ASIN,
                    "--provider", "sorftime", "--mode", "fixture",
                    "--category-name", "dog water bottle",
                    "--output-dir", directory,
                ],
                orchestrator=ProductionPipelineOrchestrator(delivery=RecordingDelivery()),
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertIn("provider requests consumed: 2", stdout.getvalue())
        self.assertNotIn("credits:", stdout.getvalue())


class SorftimeRecoveryTests(unittest.TestCase):
    def test_offline_fault_then_resume_replays_product_and_executes_only_keyword(self):
        fixture = json.loads(SORFTIME_FIXTURE.read_text(encoding="utf-8"))
        fault = KeywordFaultTransport(fixture)
        first_runtime = sorftime_runtime(fault)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            failed_dir, resumed_dir = root / "failed", root / "resumed"
            failed = ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: first_runtime,
                delivery=RecordingDelivery(),
            ).run(request(failed_dir, run_id="sorftime-fault"))
            self.assertEqual(failed.status, ProductionRunStatus.FAILED)
            self.assertEqual(fault.operations, ["ProductRequest", "ASINRequestKeyword"])
            failed_manifest = json.loads((failed_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(failed_manifest["recovery"]["checkpoint_count"], 1)

            fresh_transport = FixtureTransport(fixture)
            resumed = ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: sorftime_runtime(fresh_transport),
                delivery=RecordingDelivery(),
            ).run(
                request(
                    resumed_dir,
                    run_id="sorftime-resume",
                    resume_from=failed_dir,
                )
            )
            self.assertEqual(resumed.status, ProductionRunStatus.SUCCEEDED)
            self.assertEqual(fresh_transport.execute_count, 1)
            self.assertEqual(fresh_transport.network_call_count, 0)
            summary = resumed.provider_summary
            assert summary is not None
            self.assertEqual(summary.executed_operation_count, 1)
            self.assertEqual(summary.replayed_operation_count, 1)
            self.assertEqual(summary.provider_usage.consumed, 1)
            self.assertEqual(summary.provider_usage.remaining, 1346)
            self.assertEqual(
                tuple(item.execution_source for item in summary.logical_operations),
                (
                    ProviderOperationExecutionSource.CHECKPOINT_REPLAY,
                    ProviderOperationExecutionSource.NEW_PROVIDER,
                ),
            )

    def test_cross_provider_resume_is_rejected_before_runtime_construction(self):
        fixture = json.loads(SORFTIME_FIXTURE.read_text(encoding="utf-8"))
        with TemporaryDirectory() as directory:
            root = Path(directory)
            failed_dir = root / "failed"
            ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: sorftime_runtime(KeywordFaultTransport(fixture)),
                delivery=RecordingDelivery(),
            ).run(request(failed_dir, run_id="source"))
            calls: list[str] = []
            result = ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: calls.append("constructed"),  # type: ignore[arg-type]
                delivery=RecordingDelivery(),
            ).run(
                ProductionRunRequest(
                    marketplace="US",
                    asins=(ASIN,),
                    output_directory=root / "target",
                    provider_preference="xiyou",
                    mode=ProductionRunMode.FIXTURE,
                    category_name="dog water bottle",
                    resume_from=failed_dir,
                )
            )
            self.assertEqual(result.status, ProductionRunStatus.FAILED)
            self.assertEqual(calls, [])
            self.assertEqual(result.error["code"], "INCOMPATIBLE_RESUME_SOURCE")


class AcceptanceScenarioInventoryTests(unittest.TestCase):
    def test_issue_41_acceptance_inventory_has_38_deterministic_scenarios(self):
        scenarios = (
            "default-xiyou", "explicit-xiyou", "explicit-sorftime", "reject-provider",
            "xiyou-cohort-product", "xiyou-keyword-per-asin", "xiyou-page-one",
            "xiyou-page-size-20", "xiyou-last7days", "xiyou-traffic-desc",
            "sorftime-product-per-asin", "sorftime-trend-2", "sorftime-keyword-per-asin",
            "sorftime-page-one", "sorftime-page-size-20", "no-product-variations",
            "two-n-operations", "deterministic-step-id", "immutable-plan", "us-only",
            "selected-provider-only", "no-cross-fallback", "typed-product-dto",
            "typed-keyword-dto", "provider-neutral-cleaning", "provider-neutral-buyer-need",
            "request-unit", "request-consumed", "request-left", "credits-null",
            "provider-qualified-fingerprint", "legacy-xiyou-checkpoint", "cross-provider-reject",
            "product-checkpoint", "keyword-fault", "resume-missing-only", "live-precredential-gate",
            "zero-network",
        )
        self.assertEqual(len(scenarios), 38)
        self.assertEqual(len(set(scenarios)), 38)
        for ordinal, scenario in enumerate(scenarios, 1):
            with self.subTest(ordinal=ordinal, scenario=scenario):
                self.assertTrue(scenario)
                self.assertEqual(scenarios[ordinal - 1], scenario)


if __name__ == "__main__":
    unittest.main()
