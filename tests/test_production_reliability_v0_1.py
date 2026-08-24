from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from amazon_product_intelligence.connectors import (
    BoundedTransientRetryPolicy,
    NoRetryPolicy,
    ProviderConfig,
    ProviderRegistry,
    ProviderRequest,
    TransportResponse,
    XiYouProvider,
)
from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report.delivery import OperatorReportDeliveryResult
from amazon_product_intelligence.production_pipeline import (
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunStatus,
    ProviderCreditSemantics,
)
from amazon_product_intelligence.production_pipeline.cli import main
from amazon_product_intelligence.production_pipeline.orchestrator import (
    ProductionPipelineOrchestrator,
    ProviderRuntime,
)
from amazon_product_intelligence.production_pipeline.providers import (
    FixtureTransport,
    RecordingTransport,
)
from amazon_product_intelligence.production_pipeline.recovery import (
    CHECKPOINT_CONTRACT_VERSION,
    CheckpointStore,
    run_request_fingerprint,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = (
    ROOT
    / "src"
    / "amazon_product_intelligence"
    / "production_pipeline"
    / "fixtures"
    / "dog_water_bottle_v0_1.json"
)
ASINS = ("B0DWB00001", "B0DWB00002", "B0DWB00003")


class DeterministicDelivery:
    def deliver(self, source, output_directory, *, operator_workflow=None):
        output = Path(output_directory)
        output.mkdir(parents=True, exist_ok=True)
        markdown = output / "operator_market_report.md"
        xlsx = output / "operator_market_report.xlsx"
        markdown.write_text(f"# Recovery test\n\n{source.report_id}\n", encoding="utf-8")
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


class FaultInjectingFixtureTransport:
    """Deterministic zero-network fixture transport with per-operation outcomes."""

    def __init__(self, fixture, outcomes):
        self.fixture = FixtureTransport(fixture)
        self.outcomes = {key: list(value) for key, value in outcomes.items()}
        self.calls: list[str] = []
        self.network_call_count = 0

    def execute(self, request):
        key = (
            request.operation
            if request.operation == "asin_info"
            else f"{request.operation}:{request.parameters.get('asin')}"
        )
        self.calls.append(key)
        planned = self.outcomes.get(key)
        if planned:
            outcome = planned.pop(0)
            if isinstance(outcome, Exception):
                raise outcome
            return outcome
        return self.fixture.execute(request)


def response(status: int, credits: float | None = None) -> TransportResponse:
    metadata = {} if credits is None else {"cost_credits": credits}
    return TransportResponse(status_code=status, payload={}, metadata=metadata)


def runtime_factory(
    transport,
    captures: list[RecordingTransport],
    *,
    retry_policy=None,
    max_attempts: int = 2,
    secret: str = "fixture-runtime-secret",
):
    def factory(request):
        metadata = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        recording = RecordingTransport(transport)
        captures.append(recording)
        provider = XiYouProvider(
            recording,
            environment={"TEST_RECOVERY_SECRET": secret},
            retry_policy=retry_policy or BoundedTransientRetryPolicy(),
        )
        registry = ProviderRegistry()
        registry.register(
            provider,
            ProviderConfig(
                provider_id="xiyou",
                enabled=True,
                priority=1,
                credential_env="TEST_RECOVERY_SECRET",
                timeout_seconds=1.0,
                max_attempts=max_attempts,
            ),
        )
        return ProviderRuntime(
            registry=registry,
            provider=provider,
            recording_transport=recording,
            metadata=metadata,
            credit_semantics=ProviderCreditSemantics.FIXTURE_REFERENCE,
        )

    return factory


def directory_hashes(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


class ProductionReliabilityV01Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(dir=ROOT / "outputs")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def request(
        self,
        name: str,
        *,
        run_id: str,
        resume_from: Path | None = None,
        asins: tuple[str, ...] = ASINS,
    ) -> ProductionRunRequest:
        return ProductionRunRequest(
            marketplace="US",
            asins=asins,
            output_directory=self.root / name,
            run_id=run_id,
            mode=ProductionRunMode.FIXTURE,
            resume_from=resume_from,
        )

    def failed_partial_run(self, name: str = "failed"):
        transport = FaultInjectingFixtureTransport(
            self.fixture,
            {
                f"asin_keywords:{ASINS[1]}": [
                    response(503, 0.25),
                    response(503, 0.25),
                ]
            },
        )
        captures: list[RecordingTransport] = []
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=runtime_factory(transport, captures),
            delivery=DeterministicDelivery(),
        ).run(self.request(name, run_id=f"{name}-run"))
        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("BOUNDED_RETRY_EXHAUSTED", result.error["code"])
        return result, transport, captures[0]

    def test_transient_failure_then_success_has_two_attempts_one_logical_operation(self):
        transport = FaultInjectingFixtureTransport(
            self.fixture,
            {"asin_info": [response(503, 0.25)]},
        )
        captures: list[RecordingTransport] = []
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=runtime_factory(transport, captures),
            delivery=DeterministicDelivery(),
        ).run(self.request("retry-success", run_id="retry-success"))

        self.assertIs(result.status, ProductionRunStatus.SUCCEEDED)
        summary = result.provider_summary
        self.assertEqual(4, summary.operation_count)
        self.assertEqual(5, summary.transport_attempt_count)
        self.assertEqual(4, summary.executed_operation_count)
        self.assertEqual(0, summary.replayed_operation_count)
        self.assertEqual(4.25, summary.credits)
        self.assertEqual(["FAILED", "SUCCEEDED"], [
            item.status.value for item in summary.transport_attempts[:2]
        ])
        self.assertEqual([1, 2], [item.attempt_ordinal for item in summary.transport_attempts[:2]])
        self.assertEqual([0.25, 1.0], [item.credits for item in summary.transport_attempts[:2]])
        self.assertEqual(2, transport.calls.count("asin_info"))

    def test_transient_failure_twice_is_bounded_and_never_third_attempt(self):
        transport = FaultInjectingFixtureTransport(
            self.fixture,
            {"asin_info": [response(503, 0.5), response(503, 0.5), response(200)]},
        )
        captures: list[RecordingTransport] = []
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=runtime_factory(transport, captures),
            delivery=DeterministicDelivery(),
        ).run(self.request("retry-exhausted", run_id="retry-exhausted"))

        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("BOUNDED_RETRY_EXHAUSTED", result.error["code"])
        self.assertEqual(2, transport.calls.count("asin_info"))
        self.assertEqual(1, result.provider_summary.operation_count)
        self.assertEqual(2, result.provider_summary.transport_attempt_count)
        self.assertEqual(1.0, result.provider_summary.credits)
        self.assertEqual(0, result.recovery["checkpoint_count"])

    def test_non_retryable_failure_has_exactly_one_attempt(self):
        transport = FaultInjectingFixtureTransport(
            self.fixture,
            {"asin_info": [response(400, 0.1), response(200)]},
        )
        captures: list[RecordingTransport] = []
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=runtime_factory(transport, captures),
            delivery=DeterministicDelivery(),
        ).run(self.request("non-retryable", run_id="non-retryable"))

        self.assertIs(result.status, ProductionRunStatus.FAILED)
        self.assertEqual("PROVIDER_FAILURE", result.error["code"])
        self.assertEqual(1, transport.calls.count("asin_info"))
        self.assertEqual(1, result.provider_summary.transport_attempt_count)
        self.assertEqual("BAD_RESPONSE", result.provider_summary.transport_attempts[0].provider_error_code)

    def test_live_runtime_defaults_to_bounded_two_attempt_contract_without_calling_provider(self):
        request = ProductionRunRequest(
            marketplace="US",
            asins=ASINS,
            output_directory=self.root / "live-construction-only",
            run_id="live-construction-only",
            mode=ProductionRunMode.LIVE,
            category_name="dog water bottle",
        )
        with patch.dict(
            os.environ,
            {"XIYOU_API_KEY": "construction-only-secret", "XIYOU_API_BASE_URL": "https://example.invalid"},
        ):
            runtime = ProductionPipelineOrchestrator._default_provider_runtime(request)
        candidate = runtime.registry.candidates("metric.price")[0]
        self.assertEqual(2, candidate.configuration.max_attempts)
        self.assertIsInstance(runtime.provider._retry_policy, BoundedTransientRetryPolicy)
        self.assertEqual(0, runtime.recording_transport.operation_count)

    def test_successful_checkpoints_are_atomic_integrity_bound_and_secret_free(self):
        secret = "checkpoint-secret-must-not-appear"
        transport = FaultInjectingFixtureTransport(self.fixture, {})
        captures: list[RecordingTransport] = []
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=runtime_factory(transport, captures, secret=secret),
            delivery=DeterministicDelivery(),
        ).run(self.request("checkpoint-success", run_id="checkpoint-success"))

        self.assertIs(result.status, ProductionRunStatus.SUCCEEDED)
        checkpoint_paths = sorted((self.root / "checkpoint-success" / "checkpoints").glob("*.json"))
        self.assertEqual(4, len(checkpoint_paths))
        self.assertEqual([], list((self.root / "checkpoint-success").rglob("*.tmp")))
        for path in checkpoint_paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(CHECKPOINT_CONTRACT_VERSION, payload["checkpoint_contract_version"])
            self.assertEqual("xiyou", payload["provider_id"])
            self.assertIn("operation_contract", payload)
            self.assertIn("provenance_raw_evidence_id", payload)
            self.assertEqual(64, len(payload["integrity_sha256"]))
            self.assertNotIn(secret, path.read_text(encoding="utf-8"))
            self.assertNotIn("authorization", path.read_text(encoding="utf-8").casefold())

    def test_unsafe_checkpoint_payload_is_rejected_recursively(self):
        request = self.request("unsafe-checkpoint", run_id="unsafe-checkpoint")
        store = CheckpointStore(
            request.output_directory,
            run_id=request.run_id,
            request_fingerprint=run_request_fingerprint(request),
        )
        provider_request = ProviderRequest(
            canonical_field="metric.price",
            parameters={"entities": [{"country": "US", "asin": ASINS[0]}]},
            marketplace="US",
            locale="en-us",
            retrieved_at="2026-01-01T00:00:00Z",
            transformed_at="2026-01-01T00:00:00Z",
            collection_run_id="unsafe-checkpoint",
            currency="USD",
        )
        with self.assertRaisesRegex(Exception, "unsafe") as caught:
            store.write_success(
                operation="asin_info",
                request=provider_request,
                response=TransportResponse(
                    status_code=200,
                    payload={"nested": {"X-Api-Key": "must-never-persist"}},
                ),
                provenance_id="raw:test",
            )
        self.assertEqual("UNSAFE_CHECKPOINT_CONTENT", caught.exception.code.value)
        self.assertFalse(request.output_directory.exists())

    def test_failed_partial_cohort_preserves_only_completed_operations_and_no_report(self):
        result, transport, _ = self.failed_partial_run()
        output = self.root / "failed"
        self.assertEqual(2, result.recovery["checkpoint_count"])
        self.assertEqual(3, result.provider_summary.operation_count)
        self.assertEqual(4, result.provider_summary.transport_attempt_count)
        self.assertEqual(
            ["asin_info", f"asin_keywords:{ASINS[0]}", f"asin_keywords:{ASINS[1]}", f"asin_keywords:{ASINS[1]}"],
            transport.calls,
        )
        self.assertTrue((output / "run_manifest.json").is_file())
        self.assertFalse((output / "market_report.json").exists())
        self.assertFalse((output / "operator_market_report.xlsx").exists())
        self.assertFalse((output / "operator_market_report.md").exists())

    def test_faulted_run_plus_resume_equals_uninterrupted_and_calls_only_missing_operations(self):
        uninterrupted = ProductionPipelineOrchestrator(delivery=DeterministicDelivery()).run(
            self.request("uninterrupted", run_id="uninterrupted")
        )
        failed, _, _ = self.failed_partial_run("faulted")
        source = self.root / "faulted"
        source_hashes = directory_hashes(source)
        resumed_transport = FaultInjectingFixtureTransport(self.fixture, {})
        captures: list[RecordingTransport] = []
        resumed = ProductionPipelineOrchestrator(
            provider_runtime_factory=runtime_factory(
                resumed_transport,
                captures,
                retry_policy=NoRetryPolicy(),
                max_attempts=1,
            ),
            delivery=DeterministicDelivery(),
        ).run(self.request("resumed", run_id="resumed", resume_from=source))

        self.assertIs(failed.status, ProductionRunStatus.FAILED)
        self.assertIs(resumed.status, ProductionRunStatus.SUCCEEDED)
        self.assertEqual(3, resumed.requested_asin_count)
        self.assertEqual(3, resumed.resolved_asin_count)
        self.assertEqual(
            [f"asin_keywords:{ASINS[1]}", f"asin_keywords:{ASINS[2]}"],
            resumed_transport.calls,
        )
        self.assertEqual(2, resumed.provider_summary.replayed_operation_count)
        self.assertEqual(2, resumed.provider_summary.executed_operation_count)
        self.assertEqual(2, resumed.provider_summary.transport_attempt_count)
        self.assertEqual(4, len(resumed.artifact_paths))
        self.assertTrue(all(Path(path).is_file() for path in resumed.artifact_paths.values()))
        baseline_report = json.loads(Path(uninterrupted.artifact_paths["market_report_json"]).read_text(encoding="utf-8"))
        resumed_report = json.loads(Path(resumed.artifact_paths["market_report_json"]).read_text(encoding="utf-8"))
        self.assertEqual(baseline_report, resumed_report)
        self.assertEqual(
            uninterrupted.operator_workflow["semantic_fingerprint"],
            resumed.operator_workflow["semantic_fingerprint"],
        )
        self.assertEqual(
            uninterrupted.operator_workflow["operator_action"],
            resumed.operator_workflow["operator_action"],
        )
        self.assertEqual(
            uninterrupted.operator_workflow["next_actions"],
            resumed.operator_workflow["next_actions"],
        )
        self.assertNotEqual(
            uninterrupted.operator_workflow["run_health"],
            resumed.operator_workflow["run_health"],
        )
        self.assertFalse(uninterrupted.operator_workflow["run_health"]["resumed"])
        self.assertTrue(resumed.operator_workflow["run_health"]["resumed"])
        self.assertEqual(source_hashes, directory_hashes(source))
        self.assertEqual("faulted-run", resumed.recovery["resume_source_run_id"])
        self.assertEqual(4, resumed.recovery["checkpoint_count"])

    def test_resume_input_mismatch_fails_before_provider_factory(self):
        self.failed_partial_run("mismatch-source")
        calls: list[int] = []

        def forbidden_factory(request):
            calls.append(1)
            raise AssertionError("provider factory must not run")

        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=forbidden_factory,
            delivery=DeterministicDelivery(),
        ).run(
            self.request(
                "mismatch-destination",
                run_id="mismatch-destination",
                resume_from=self.root / "mismatch-source",
                asins=ASINS[:2],
            )
        )
        self.assertEqual([], calls)
        self.assertEqual("INCOMPATIBLE_RESUME_SOURCE", result.error["code"])
        self.assertEqual(0, result.provider_summary.operation_count if result.provider_summary else 0)

    def test_corrupt_unsupported_and_unsafe_checkpoints_fail_before_provider_factory(self):
        self.failed_partial_run("invalid-source")
        source = self.root / "invalid-source"
        checkpoint_path = sorted((source / "checkpoints").glob("*.json"))[0]
        original = checkpoint_path.read_bytes()
        calls: list[int] = []

        def forbidden_factory(request):
            calls.append(1)
            raise AssertionError("provider factory must not run")

        cases = (
            ("corrupt", lambda payload: payload.__setitem__("integrity_sha256", "0" * 64), "CHECKPOINT_INTEGRITY_FAILURE"),
            ("unsupported", lambda payload: payload.__setitem__("checkpoint_contract_version", "future-v9"), "UNSUPPORTED_CHECKPOINT_VERSION"),
            ("unsafe", lambda payload: payload.__setitem__("authorization", "do-not-copy"), "UNSAFE_CHECKPOINT_CONTENT"),
        )
        for name, mutate, expected in cases:
            with self.subTest(name=name):
                payload = json.loads(original.decode("utf-8"))
                mutate(payload)
                checkpoint_path.write_text(json.dumps(payload), encoding="utf-8")
                result = ProductionPipelineOrchestrator(
                    provider_runtime_factory=forbidden_factory,
                    delivery=DeterministicDelivery(),
                ).run(
                    self.request(
                        f"invalid-{name}",
                        run_id=f"invalid-{name}",
                        resume_from=source,
                    )
                )
                self.assertEqual(expected, result.error["code"])
                self.assertNotIn("do-not-copy", canonical_json(result.to_dict()))
                checkpoint_path.write_bytes(original)
        self.assertEqual([], calls)

    def test_resume_destination_output_ownership_conflict_precedes_provider_access(self):
        self.failed_partial_run("ownership-source")
        destination = self.root / "owned-destination"
        destination.mkdir()
        stale = destination / "market_report.json"
        stale.write_bytes(b'{"owner":"older-run"}\n')
        original_hash = sha256(stale.read_bytes()).hexdigest()
        calls: list[int] = []

        def forbidden_factory(request):
            calls.append(1)
            raise AssertionError("provider factory must not run")

        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=forbidden_factory,
            delivery=DeterministicDelivery(),
        ).run(
            ProductionRunRequest(
                marketplace="US",
                asins=ASINS,
                output_directory=destination,
                run_id="owned-destination",
                mode=ProductionRunMode.FIXTURE,
                resume_from=self.root / "ownership-source",
            )
        )
        self.assertEqual("OUTPUT_ARTIFACT_CONFLICT", result.error["code"])
        self.assertEqual([], calls)
        self.assertEqual(original_hash, sha256(stale.read_bytes()).hexdigest())
        self.assertEqual({}, result.artifact_paths)

    def test_cli_resume_success_and_incompatible_failure_exit_semantics(self):
        self.failed_partial_run("cli-source")
        transport = FaultInjectingFixtureTransport(self.fixture, {})
        captures: list[RecordingTransport] = []
        stdout, stderr = StringIO(), StringIO()
        code = main(
            [
                "run", "--market", "US",
                *[value for asin in ASINS for value in ("--asin", asin)],
                "--output-dir", str(self.root / "cli-resumed"),
                "--run-id", "cli-resumed",
                "--resume-from", str(self.root / "cli-source"),
            ],
            orchestrator=ProductionPipelineOrchestrator(
                provider_runtime_factory=runtime_factory(
                    transport, captures, retry_policy=NoRetryPolicy(), max_attempts=1
                ),
                delivery=DeterministicDelivery(),
            ),
            stdout=stdout,
            stderr=stderr,
        )
        self.assertEqual(0, code)
        self.assertIn("replayed: 2", stdout.getvalue())
        self.assertEqual("", stderr.getvalue())

        failed_stdout, failed_stderr = StringIO(), StringIO()
        failed_code = main(
            [
                "run", "--market", "US", "--asin", ASINS[0],
                "--output-dir", str(self.root / "cli-incompatible"),
                "--resume-from", str(self.root / "cli-source"),
            ],
            orchestrator=ProductionPipelineOrchestrator(delivery=DeterministicDelivery()),
            stdout=failed_stdout,
            stderr=failed_stderr,
        )
        self.assertEqual(1, failed_code)
        self.assertIn("INCOMPATIBLE_RESUME_SOURCE", failed_stderr.getvalue())

    def test_fixture_fault_and_resume_paths_make_zero_network_calls_and_leak_no_secret(self):
        secret = "sp036-secret-sentinel"
        transport = FaultInjectingFixtureTransport(
            self.fixture,
            {f"asin_keywords:{ASINS[1]}": [response(503), response(503)]},
        )
        captures: list[RecordingTransport] = []
        with patch(
            "amazon_product_intelligence.connectors.transport.urlopen",
            side_effect=AssertionError("network access attempted"),
        ):
            failed = ProductionPipelineOrchestrator(
                provider_runtime_factory=runtime_factory(transport, captures, secret=secret),
                delivery=DeterministicDelivery(),
            ).run(self.request("secret-source", run_id="secret-source"))
        serialized = canonical_json(failed.to_dict())
        for path in (self.root / "secret-source").rglob("*"):
            if path.is_file():
                self.assertNotIn(secret.encode(), path.read_bytes())
        self.assertNotIn(secret, serialized)
        self.assertEqual(0, transport.network_call_count)
        self.assertEqual(0, transport.fixture.network_call_count)


if __name__ == "__main__":
    unittest.main()
