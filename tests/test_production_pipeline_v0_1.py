from __future__ import annotations

from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from amazon_product_intelligence.buyer_need_analysis.intent_v0_3 import (
    BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3,
)
from amazon_product_intelligence.buyer_need_analysis.taxonomy_v0_2 import (
    BUYER_NEED_TAXONOMY_V0_2,
)
from amazon_product_intelligence.connectors import (
    ProviderConfig,
    ProviderConnectorError,
    ProviderErrorCode,
    ProviderRegistry,
    ProviderRequest,
    ProviderResolver,
    TransportResponse,
    XiYouProvider,
)
from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report import MARKET_REPORT_VERSION
from amazon_product_intelligence.market_report.delivery import (
    OperatorReportDeliveryResult,
)
from amazon_product_intelligence.production_pipeline import (
    PipelineStage,
    ProviderCreditSemantics,
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunStatus,
    StageStatus,
)
from amazon_product_intelligence.production_pipeline.cli import main
from amazon_product_intelligence.production_pipeline.orchestrator import (
    ProductionPipelineOrchestrator,
    ProviderRuntime,
)
from amazon_product_intelligence.production_pipeline.providers import (
    FixtureTransport,
    RecordingTransport,
    xiyou_reverse_keyword_parameters,
)
from amazon_product_intelligence.semantic_clustering.rules import (
    SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "src"
    / "amazon_product_intelligence"
    / "production_pipeline"
    / "fixtures"
    / "dog_water_bottle_v0_1.json"
)
ASINS = ("B0DWB00001", "B0DWB00002", "B0DWB00003")


class RecordingDelivery:
    def __init__(self) -> None:
        self.calls = 0

    def deliver(self, source, output_directory, *, operator_workflow=None):
        self.calls += 1
        self.operator_workflow = operator_workflow
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        markdown = output / "operator_market_report.md"
        xlsx = output / "operator_market_report.xlsx"
        markdown.write_text(f"# Test operator report\n\n{source.report_id}\n", encoding="utf-8")
        with zipfile.ZipFile(xlsx, "w") as package:
            package.writestr("[Content_Types].xml", "<Types/>")
        return OperatorReportDeliveryResult(
            source_report_id=source.report_id,
            delivery_version="operator-market-report-delivery-v0.1",
            xlsx_path=xlsx,
            markdown_path=markdown,
            xlsx_sha256=sha256(xlsx.read_bytes()).hexdigest(),
            markdown_sha256=sha256(markdown.read_bytes()).hexdigest(),
        )


class FailingTransport:
    def execute(self, request):
        return TransportResponse(status_code=503, payload={})


def failing_runtime(secret: str, counter: list[int]):
    def factory(request):
        counter.append(1)
        metadata = json.loads(FIXTURE.read_text(encoding="utf-8"))
        recording = RecordingTransport(FailingTransport())
        provider = XiYouProvider(
            recording,
            environment={"TEST_LIVE_SECRET": secret},
        )
        registry = ProviderRegistry()
        registry.register(
            provider,
            ProviderConfig(
                provider_id="xiyou",
                enabled=True,
                priority=1,
                credential_env="TEST_LIVE_SECRET",
            ),
        )
        return ProviderRuntime(
            registry=registry,
            provider=provider,
            recording_transport=recording,
            metadata=metadata,
            credit_semantics=ProviderCreditSemantics.LIVE_PROVIDER_REPORTED,
        )

    return factory


def live_fixture_runtime(secret: str):
    def factory(request):
        metadata = json.loads(FIXTURE.read_text(encoding="utf-8"))
        recording = RecordingTransport(FixtureTransport(metadata))
        provider = XiYouProvider(
            recording,
            environment={"TEST_LIVE_SECRET": secret},
        )
        registry = ProviderRegistry()
        registry.register(
            provider,
            ProviderConfig(
                provider_id="xiyou",
                enabled=True,
                priority=1,
                credential_env="TEST_LIVE_SECRET",
            ),
        )
        return ProviderRuntime(
            registry=registry,
            provider=provider,
            recording_transport=recording,
            metadata=metadata,
            credit_semantics=ProviderCreditSemantics.LIVE_PROVIDER_REPORTED,
        )

    return factory


class ProductionPipelineV01Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(dir=ROOT / "outputs")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def request(self, name: str = "run", *, run_id: str | None = "test-run"):
        return ProductionRunRequest(
            marketplace="US",
            asins=ASINS,
            output_directory=self.root / name,
            run_id=run_id,
            mode=ProductionRunMode.FIXTURE,
        )

    def run_success(self, name: str = "run", *, run_id: str | None = "test-run"):
        delivery = RecordingDelivery()
        result = ProductionPipelineOrchestrator(delivery=delivery).run(
            self.request(name, run_id=run_id)
        )
        self.assertEqual(1, delivery.calls)
        self.assertIs(result.status, ProductionRunStatus.SUCCEEDED)
        return result

    def test_fixture_offline_full_e2e_and_expected_four_artifacts(self) -> None:
        result = self.run_success()

        self.assertEqual(3, result.requested_asin_count)
        self.assertEqual(3, result.resolved_asin_count)
        self.assertEqual(4, len(result.artifact_paths))
        self.assertTrue(all(Path(path).is_file() for path in result.artifact_paths.values()))
        self.assertEqual(4, result.provider_summary.operation_count)
        self.assertEqual(4.0, result.provider_summary.credits)
        self.assertIs(
            result.provider_summary.credit_semantics,
            ProviderCreditSemantics.FIXTURE_REFERENCE,
        )
        self.assertEqual(
            "FIXTURE_REFERENCE",
            result.to_dict()["provider_summary"]["credit_semantics"],
        )

    def test_fixture_mode_has_zero_network_calls(self) -> None:
        from unittest.mock import patch

        with patch(
            "amazon_product_intelligence.connectors.transport.urlopen",
            side_effect=AssertionError("network access attempted"),
        ):
            result = self.run_success("zero-network")
        self.assertIs(result.status, ProductionRunStatus.SUCCEEDED)

    def test_fixture_reverse_keyword_requests_use_exact_bounded_contract(self) -> None:
        recording_transports: list[RecordingTransport] = []

        def captured_fixture_runtime(request):
            runtime = ProductionPipelineOrchestrator._default_provider_runtime(request)
            recording_transports.append(runtime.recording_transport)
            return runtime

        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=captured_fixture_runtime,
            delivery=RecordingDelivery(),
        ).run(self.request("bounded-reverse-keywords"))

        self.assertIs(result.status, ProductionRunStatus.SUCCEEDED)
        self.assertEqual(1, len(recording_transports))
        recording = recording_transports[0]
        reverse_requests = [
            item for item in recording.safe_requests if item["operation"] == "asin_keywords"
        ]
        self.assertEqual(len(ASINS), len(reverse_requests))
        self.assertEqual(
            [
                xiyou_reverse_keyword_parameters(asin=asin, marketplace="US")
                for asin in ASINS
            ],
            [item["parameters"] for item in reverse_requests],
        )
        self.assertEqual(
            ("asin_info", "asin_keywords", "asin_keywords", "asin_keywords"),
            recording.operations,
        )
        self.assertEqual(4, recording.operation_count)
        self.assertIsInstance(recording.wrapped, FixtureTransport)
        self.assertEqual(4, recording.wrapped.execute_count)
        self.assertEqual(0, recording.wrapped.network_call_count)

        runtime = ProductionPipelineOrchestrator._default_provider_runtime(
            self.request("bounded-reverse-keyword-provenance")
        )
        expected_parameters = xiyou_reverse_keyword_parameters(
            asin=ASINS[0],
            marketplace="US",
        )
        resolution = ProviderResolver(runtime.registry).resolve(
            ProviderRequest(
                canonical_field="relationship.product_to_keyword",
                parameters=expected_parameters,
                marketplace="US",
                locale=str(runtime.metadata["locale"]),
                retrieved_at=str(runtime.metadata["retrieved_at"]),
                transformed_at=str(runtime.metadata["transformed_at"]),
                collection_run_id="bounded-reverse-keyword-provenance",
                currency=str(runtime.metadata["currency"]),
            )
        )
        self.assertEqual(
            canonical_json(expected_parameters),
            canonical_json(resolution.result.adaptation.raw_evidence.sanitized_request),
        )
        self.assertEqual(0, runtime.recording_transport.wrapped.network_call_count)

    def test_managed_output_conflict_is_safe_before_provider_access(self) -> None:
        from unittest.mock import patch

        output = self.root / "owned-output"
        output.mkdir()
        contents = {
            "market_report.json": b'{"owner":"earlier-run"}\n',
            "operator_market_report.xlsx": b"PK\x03\x04earlier-xlsx",
            "operator_market_report.md": b"# Earlier operator report\n",
            "run_manifest.json": b'{"run_id":"earlier-run"}\n',
        }
        for name, content in contents.items():
            (output / name).write_bytes(content)
        original_hashes = {
            name: sha256((output / name).read_bytes()).hexdigest()
            for name in contents
        }
        provider_factory_calls: list[int] = []

        def forbidden_factory(request):
            provider_factory_calls.append(1)
            raise AssertionError("provider factory must not be called")

        orchestrator = ProductionPipelineOrchestrator(
            provider_runtime_factory=forbidden_factory,
            delivery=RecordingDelivery(),
        )
        with patch(
            "amazon_product_intelligence.connectors.transport.urlopen",
            side_effect=AssertionError("network access attempted"),
        ):
            result = orchestrator.run(
                ProductionRunRequest(
                    marketplace="US",
                    asins=ASINS,
                    output_directory=output,
                    run_id="rejected-run",
                    mode=ProductionRunMode.FIXTURE,
                )
            )

        self.assertEqual([], provider_factory_calls)
        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("OUTPUT_ARTIFACT_CONFLICT", result.error["code"])
        self.assertEqual({}, result.artifact_paths)
        self.assertIsNone(result.provider_summary)
        self.assertEqual(
            StageStatus.SKIPPED,
            result.stages[-1].status,
        )
        self.assertEqual(
            original_hashes,
            {
                name: sha256((output / name).read_bytes()).hexdigest()
                for name in contents
            },
        )
        self.assertNotIn("operator_xlsx", result.artifact_paths)
        self.assertNotIn("operator_markdown", result.artifact_paths)

        stdout, stderr = StringIO(), StringIO()
        code = main(
            [
                "run", "--market", "US",
                "--asin", ASINS[0], "--asin", ASINS[1], "--asin", ASINS[2],
                "--output-dir", str(output),
                "--run-id", "cli-rejected-run",
            ],
            orchestrator=orchestrator,
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(1, code)
        self.assertEqual([], provider_factory_calls)
        self.assertIn("OUTPUT_ARTIFACT_CONFLICT", stderr.getvalue())
        self.assertIn("no artifacts written", stderr.getvalue())
        self.assertNotIn(str(output / "operator_market_report.xlsx"), stderr.getvalue())
        self.assertNotIn(str(output / "operator_market_report.md"), stderr.getvalue())
        self.assertEqual(
            original_hashes,
            {
                name: sha256((output / name).read_bytes()).hexdigest()
                for name in contents
            },
        )

    def test_each_managed_artifact_independently_conflicts(self) -> None:
        managed_names = (
            "market_report.json",
            "operator_market_report.xlsx",
            "operator_market_report.md",
            "run_manifest.json",
        )
        provider_factory_calls: list[str] = []

        def forbidden_factory(request):
            provider_factory_calls.append(request.run_id or "missing")
            raise AssertionError("provider factory must not be called")

        orchestrator = ProductionPipelineOrchestrator(
            provider_runtime_factory=forbidden_factory,
            delivery=RecordingDelivery(),
        )
        for index, managed_name in enumerate(managed_names):
            with self.subTest(managed_name=managed_name):
                output = self.root / f"single-conflict-{index}"
                output.mkdir()
                managed_path = output / managed_name
                managed_path.write_bytes(f"earlier-{managed_name}".encode())
                original_hash = sha256(managed_path.read_bytes()).hexdigest()

                result = orchestrator.run(
                    ProductionRunRequest(
                        marketplace="US",
                        asins=ASINS,
                        output_directory=output,
                        run_id=f"single-conflict-{index}",
                        mode=ProductionRunMode.FIXTURE,
                    )
                )

                self.assertEqual("OUTPUT_ARTIFACT_CONFLICT", result.error["code"])
                self.assertEqual({}, result.artifact_paths)
                self.assertEqual(original_hash, sha256(managed_path.read_bytes()).hexdigest())
        self.assertEqual([], provider_factory_calls)

    def test_invalid_seed_keyword_fails_before_provider_factory(self) -> None:
        calls: list[int] = []

        def forbidden_factory(request):
            calls.append(1)
            raise AssertionError("provider factory must not be called")

        request = ProductionRunRequest(
            marketplace="US",
            asins=(),
            seed_keyword="dog water bottle",
            output_directory=self.root / "invalid",
            mode=ProductionRunMode.FIXTURE,
        )
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=forbidden_factory,
            delivery=RecordingDelivery(),
        ).run(request)

        self.assertEqual([], calls)
        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("UNSUPPORTED_CAPABILITY", result.error["code"])
        self.assertEqual(0, result.provider_summary.operation_count if result.provider_summary else 0)

    def test_provider_failure_is_typed_recorded_and_secret_safe(self) -> None:
        secret = "super-secret-provider-token"
        calls: list[int] = []
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=failing_runtime(secret, calls),
            delivery=RecordingDelivery(),
        ).run(self.request("provider-failure"))

        self.assertEqual([1], calls)
        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("PROVIDER_FAILURE", result.error["code"])
        self.assertEqual(
            ProviderErrorCode.RESOLUTION_EXHAUSTED.value,
            result.error["details"]["provider_error_code"],
        )
        expected_attempts = [
            {
                "provider_id": "xiyou",
                "status": "FAILED",
                "error_code": "PROVIDER_UNAVAILABLE",
            }
        ]
        self.assertEqual(
            expected_attempts,
            result.error["details"]["resolver_attempts"],
        )
        manifest = Path(result.artifact_paths["run_manifest"]).read_text(encoding="utf-8")
        manifest_payload = json.loads(manifest)
        self.assertEqual(
            expected_attempts,
            manifest_payload["error"]["details"]["resolver_attempts"],
        )
        self.assertNotIn(secret, canonical_json(result.to_dict()))
        self.assertNotIn(secret, manifest)

        stdout, stderr = StringIO(), StringIO()
        code = main(
            [
                "run", "--market", "US",
                "--asin", ASINS[0], "--asin", ASINS[1], "--asin", ASINS[2],
                "--output-dir", str(self.root / "provider-failure-cli"),
                "--run-id", "provider-failure-cli",
            ],
            orchestrator=ProductionPipelineOrchestrator(
                provider_runtime_factory=failing_runtime(secret, calls),
                delivery=RecordingDelivery(),
            ),
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(1, code)
        self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())

    def test_safe_resolver_diagnostics_allowlist_distinguishes_attempts(self) -> None:
        secret = "resolver-secret-must-not-survive"
        connector_error = ProviderConnectorError(
            ProviderErrorCode.RESOLUTION_EXHAUSTED,
            secret,
            details={
                "attempts": (
                    {
                        "provider_id": "xiyou",
                        "status": "FAILED",
                        "error_code": "SCHEMA_MISMATCH",
                        "raw_response": secret,
                    },
                    {
                        "provider_id": "xiyou",
                        "status": "FIELD_MISSING",
                        "error_code": None,
                        "headers": {"authorization": secret},
                    },
                    {
                        "provider_id": "xiyou",
                        "status": "FAILED",
                        "error_code": "PROVIDER_UNAVAILABLE",
                        "exception_text": secret,
                    },
                    {
                        "provider_id": secret,
                        "status": "FAILED",
                        "error_code": "SCHEMA_MISMATCH",
                    },
                    {
                        "provider_id": "xiyou",
                        "status": secret,
                        "error_code": "SCHEMA_MISMATCH",
                    },
                ),
                "raw_response": secret,
                "headers": {"X-Api-Key": secret},
            },
        )

        typed = ProductionPipelineOrchestrator._typed_error(
            connector_error,
            PipelineStage.ACQUISITION,
        )

        self.assertEqual("PROVIDER_FAILURE", typed.code.value)
        self.assertEqual(
            [
                {
                    "provider_id": "xiyou",
                    "status": "FAILED",
                    "error_code": "SCHEMA_MISMATCH",
                },
                {
                    "provider_id": "xiyou",
                    "status": "FIELD_MISSING",
                    "error_code": None,
                },
                {
                    "provider_id": "xiyou",
                    "status": "FAILED",
                    "error_code": "PROVIDER_UNAVAILABLE",
                },
            ],
            typed.details["resolver_attempts"],
        )
        self.assertNotIn(secret, canonical_json(typed.to_dict()))

    def test_same_fixture_produces_identical_market_report_content(self) -> None:
        first = self.run_success("deterministic-a", run_id="runtime-a")
        second = self.run_success("deterministic-b", run_id="runtime-b")

        first_payload = json.loads(Path(first.artifact_paths["market_report_json"]).read_text(encoding="utf-8"))
        second_payload = json.loads(Path(second.artifact_paths["market_report_json"]).read_text(encoding="utf-8"))
        self.assertEqual(first_payload, second_payload)
        self.assertEqual(first_payload["report_id"], second_payload["report_id"])

    def test_schema_validation_occurs_before_delivery(self) -> None:
        delivery = RecordingDelivery()

        def reject(payload):
            raise ValueError("test schema rejection")

        result = ProductionPipelineOrchestrator(
            delivery=delivery,
            report_validator=reject,
        ).run(self.request("schema-failure"))

        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("SCHEMA_VALIDATION_FAILURE", result.error["code"])
        self.assertEqual(0, delivery.calls)
        self.assertTrue(Path(result.artifact_paths["market_report_json"]).is_file())
        self.assertNotIn("operator_xlsx", result.artifact_paths)

    def test_delivery_failure_never_marks_valid_report_successful(self) -> None:
        class FailingDelivery:
            def deliver(self, source, output_directory, *, operator_workflow=None):
                raise RuntimeError("delivery unavailable")

        result = ProductionPipelineOrchestrator(delivery=FailingDelivery()).run(
            self.request("delivery-failure")
        )
        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("DELIVERY_FAILURE", result.error["code"])
        self.assertTrue(Path(result.artifact_paths["market_report_json"]).is_file())

    def test_manifest_records_artifact_paths_and_explicit_stage_states(self) -> None:
        result = self.run_success("manifest")
        manifest = json.loads(
            Path(result.artifact_paths["run_manifest"]).read_text(encoding="utf-8")
        )

        self.assertEqual(result.artifact_paths, manifest["artifact_paths"])
        self.assertEqual("SUCCEEDED", manifest["status"])
        self.assertEqual(PipelineStage.MANIFEST.value, manifest["stages"][-1]["stage"])
        self.assertEqual("COMPLETE", manifest["stages"][-1]["status"])
        self.assertTrue(
            all(item["status"] in {state.value for state in StageStatus} for item in manifest["stages"])
        )

    def test_cli_success_exit_code_and_operator_summary(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        code = main(
            [
                "run", "--market", "US",
                "--asin", ASINS[0], "--asin", ASINS[1], "--asin", ASINS[2],
                "--output-dir", str(self.root / "cli-success"),
                "--run-id", "cli-success",
            ],
            orchestrator=ProductionPipelineOrchestrator(delivery=RecordingDelivery()),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(0, code)
        self.assertIn("3/3 ASINs", stdout.getvalue())
        self.assertIn("operator_xlsx", stdout.getvalue())
        self.assertIn("provider operations: 4", stdout.getvalue())
        self.assertIn("fixture reference credits: 4.0 (not billed)", stdout.getvalue())
        self.assertNotIn("live provider-reported credits", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

    def test_live_provider_reported_credit_semantics_are_secret_safe(self) -> None:
        secret = "live-secret-must-not-be-printed"
        orchestrator = ProductionPipelineOrchestrator(
            provider_runtime_factory=live_fixture_runtime(secret),
            delivery=RecordingDelivery(),
        )
        request = ProductionRunRequest(
            marketplace="US",
            asins=ASINS,
            output_directory=self.root / "live-summary",
            run_id="live-summary",
            mode=ProductionRunMode.LIVE,
            category_name="dog water bottle",
        )
        result = orchestrator.run(request)

        self.assertIs(result.status, ProductionRunStatus.SUCCEEDED)
        self.assertEqual(4.0, result.provider_summary.credits)
        self.assertIs(
            result.provider_summary.credit_semantics,
            ProviderCreditSemantics.LIVE_PROVIDER_REPORTED,
        )
        self.assertNotIn(secret, canonical_json(result.to_dict()))

        stdout, stderr = StringIO(), StringIO()
        code = main(
            [
                "run", "--market", "US",
                "--asin", ASINS[0], "--asin", ASINS[1], "--asin", ASINS[2],
                "--output-dir", str(self.root / "live-cli-summary"),
                "--run-id", "live-cli-summary",
                "--mode", "live",
                "--category-name", "dog water bottle",
            ],
            orchestrator=orchestrator,
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(0, code)
        self.assertIn("live provider-reported credits: 4.0", stdout.getvalue())
        self.assertNotIn("not billed", stdout.getvalue())
        self.assertNotIn(secret, stdout.getvalue() + stderr.getvalue())

    def test_cli_failure_exit_code(self) -> None:
        stdout, stderr = StringIO(), StringIO()
        code = main(
            [
                "run", "--market", "US",
                "--seed-keyword", "dog water bottle",
                "--output-dir", str(self.root / "cli-failure"),
            ],
            orchestrator=ProductionPipelineOrchestrator(delivery=RecordingDelivery()),
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(1, code)
        self.assertIn("UNSUPPORTED_CAPABILITY", stderr.getvalue())
        self.assertNotIn("token", stderr.getvalue().casefold())

    def test_buyer_need_v0_3_fingerprints_are_unchanged(self) -> None:
        expected = {
            BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3: "75f5accba6ad961e65849e0ee46933d361434144c251b512ae639d6523d21755",
            BUYER_NEED_TAXONOMY_V0_2: "8db4987d3324d1b8ab14cd71f5190bb69a81d5e9a3ca9ca65e3a41f589ff59f6",
            SEMANTIC_NORMALIZATION_REGISTRY_V0_1: "49ad3da401daded53c9cf1dc0272aa844919485598cd28a6667d2fee505e5eb2",
        }
        for registry, fingerprint in expected.items():
            self.assertEqual(
                fingerprint,
                sha256(canonical_json(registry.to_dict()).encode("utf-8")).hexdigest(),
            )

    def test_market_report_version_is_frozen(self) -> None:
        result = self.run_success("report-version")
        payload = json.loads(Path(result.artifact_paths["market_report_json"]).read_text(encoding="utf-8"))
        self.assertEqual("market-report-v0.1", MARKET_REPORT_VERSION)
        self.assertEqual(MARKET_REPORT_VERSION, result.market_report_version)
        self.assertEqual(MARKET_REPORT_VERSION, payload["report_version"])


if __name__ == "__main__":
    unittest.main()
