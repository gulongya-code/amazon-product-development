"""Validation-only SP-036A live fault/retry/checkpoint/resume runner.

The injected NETWORK failures occur before the wrapped HttpJsonTransport is
called.  This file is not imported by normal production execution.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from typing import Any
from urllib.parse import urlsplit

from amazon_product_intelligence.connectors import (
    BoundedTransientRetryPolicy,
    HttpJsonTransport,
    ProviderConfig,
    ProviderConnectorError,
    ProviderErrorCode,
    ProviderRegistry,
    TransportRequest,
    TransportResponse,
    XiYouProvider,
)
from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report import validate_market_report_payload
from amazon_product_intelligence.production_pipeline.artifacts import write_json_atomic
from amazon_product_intelligence.production_pipeline.models import (
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunStatus,
    ProviderCreditSemantics,
)
from amazon_product_intelligence.production_pipeline.orchestrator import (
    ProductionPipelineOrchestrator,
    ProviderRuntime,
)
from amazon_product_intelligence.production_pipeline.providers import RecordingTransport
from amazon_product_intelligence.production_pipeline.recovery import (
    load_resume_source,
    run_request_fingerprint,
)


BASELINE = "6d7dc8edc9b0d2470f31ff6f8ae557ba4c23ffac"
VALIDATION_CONTRACT_VERSION = "sp-036a-live-reliability-validation-v0.1"
ASINS = ("B09265WXY5", "B0GGR3F5KZ", "B0H235BRVX")
MARKETPLACE = "US"
CATEGORY = "dog water bottle"
DEFAULT_BASE_URL = "https://openapi.xydc.com"

_FAULT_SCHEDULE = {
    f"asin_keywords:{ASINS[1]}": frozenset({1}),
    f"asin_keywords:{ASINS[2]}": frozenset({1, 2}),
}


class ValidationGateError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ValidationGateError(code)


def _credit(response: TransportResponse) -> float | None:
    value = response.metadata.get("cost_credits")
    if value is None and isinstance(response.payload, Mapping):
        value = response.payload.get("cost_credits")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


class PreNetworkFaultInjectionTransport:
    """Inject configured failures without delegating to the HTTP transport."""

    def __init__(self, delegate: Any, schedule: Mapping[str, frozenset[int]]) -> None:
        self._delegate = delegate
        self._schedule = dict(schedule)
        self._attempts: defaultdict[str, int] = defaultdict(int)
        self.events: list[dict[str, Any]] = []
        self.http_delegation_count = 0

    @staticmethod
    def operation_key(request: TransportRequest) -> str:
        if request.operation == "asin_info":
            return "asin_info"
        asin = request.parameters.get("asin")
        return f"{request.operation}:{asin}"

    def execute(self, request: TransportRequest) -> TransportResponse:
        key = self.operation_key(request)
        self._attempts[key] += 1
        ordinal = self._attempts[key]
        event = {
            "operation_key": key,
            "operation": request.operation,
            "attempt_ordinal": ordinal,
            "action": "INJECT_NETWORK" if ordinal in self._schedule.get(key, ()) else "DELEGATE_HTTP",
            "delegated_to_http": False,
            "status_code": None,
            "provider_error_code": None,
            "provider_reported_credits": None,
        }
        if event["action"] == "INJECT_NETWORK":
            event["provider_error_code"] = ProviderErrorCode.NETWORK.value
            self.events.append(event)
            raise ProviderConnectorError(
                ProviderErrorCode.NETWORK,
                "SP-036A deterministic pre-network fault injection",
                provider_id=request.provider_id,
                operation=request.operation,
                retryable=True,
            )

        self.http_delegation_count += 1
        event["delegated_to_http"] = True
        try:
            response = self._delegate.execute(request)
        except ProviderConnectorError as exc:
            event["provider_error_code"] = exc.code.value
            self.events.append(event)
            raise
        event["status_code"] = response.status_code
        event["provider_reported_credits"] = _credit(response)
        self.events.append(event)
        return response


class _SelfTestDelegate:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, request: TransportRequest) -> TransportResponse:
        self.calls.append(PreNetworkFaultInjectionTransport.operation_key(request))
        return TransportResponse(
            status_code=200,
            payload={},
            metadata={"cost_credits": 1.0},
        )


def _test_request(operation: str, asin: str | None = None) -> TransportRequest:
    parameters: dict[str, Any]
    if operation == "asin_info":
        parameters = {"entities": [{"country": MARKETPLACE, "asin": value} for value in ASINS]}
    else:
        parameters = {"asin": asin, "country": MARKETPLACE}
    return TransportRequest(
        provider_id="xiyou",
        operation=operation,
        method="POST",
        endpoint="/validation-only",
        parameters=parameters,
        timeout_seconds=1.0,
        public_headers={},
    )


def self_test() -> dict[str, Any]:
    delegate = _SelfTestDelegate()
    wrapper = PreNetworkFaultInjectionTransport(delegate, _FAULT_SCHEDULE)
    wrapper.execute(_test_request("asin_info"))
    wrapper.execute(_test_request("asin_keywords", ASINS[0]))
    for asin, attempts in ((ASINS[1], 2), (ASINS[2], 2)):
        for _ in range(attempts):
            try:
                wrapper.execute(_test_request("asin_keywords", asin))
            except ProviderConnectorError as exc:
                _require(exc.code is ProviderErrorCode.NETWORK, "SELF_TEST_WRONG_ERROR")
    _require(
        delegate.calls
        == ["asin_info", f"asin_keywords:{ASINS[0]}", f"asin_keywords:{ASINS[1]}"],
        "SELF_TEST_DELEGATION_SCHEDULE",
    )
    injected = [item for item in wrapper.events if item["action"] == "INJECT_NETWORK"]
    _require(len(injected) == 3, "SELF_TEST_INJECTED_COUNT")
    _require(all(not item["delegated_to_http"] for item in injected), "SELF_TEST_PRE_NETWORK")
    _require(all(item["provider_reported_credits"] is None for item in injected), "SELF_TEST_CREDITS")
    return {
        "status": "PASS",
        "attempt_count": len(wrapper.events),
        "injected_failure_count": len(injected),
        "http_delegation_count": wrapper.http_delegation_count,
        "delegated_operations": list(delegate.calls),
    }


def _runtime_factory(
    *,
    base_url: str,
    schedule: Mapping[str, frozenset[int]],
    captures: list[tuple[ProviderRuntime, PreNetworkFaultInjectionTransport]],
):
    def factory(request: ProductionRunRequest) -> ProviderRuntime:
        wrapper = PreNetworkFaultInjectionTransport(
            HttpJsonTransport({"xiyou": base_url}),
            schedule,
        )
        recording = RecordingTransport(wrapper)
        provider = XiYouProvider(
            recording,
            environment=os.environ,
            retry_policy=BoundedTransientRetryPolicy(),
        )
        registry = ProviderRegistry()
        registry.register(
            provider,
            ProviderConfig(
                provider_id="xiyou",
                enabled=True,
                priority=1,
                credential_env="XIYOU_API_KEY",
                timeout_seconds=15.0,
                max_attempts=2,
            ),
        )
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        runtime = ProviderRuntime(
            registry=registry,
            provider=provider,
            recording_transport=recording,
            metadata={
                "locale": "en-us",
                "currency": "USD",
                "retrieved_at": now,
                "transformed_at": now,
                "generated_at": now,
                "category_name": CATEGORY,
                "category_scope": f"Amazon {MARKETPLACE} > {CATEGORY}",
            },
            credit_semantics=ProviderCreditSemantics.LIVE_PROVIDER_REPORTED,
        )
        captures.append((runtime, wrapper))
        return runtime

    return factory


def _request(output: Path, run_id: str, *, resume_from: Path | None = None) -> ProductionRunRequest:
    return ProductionRunRequest(
        marketplace=MARKETPLACE,
        asins=ASINS,
        output_directory=output,
        provider_preference="xiyou",
        provider_config_reference="environment",
        run_id=run_id,
        mode=ProductionRunMode.LIVE,
        category_name=CATEGORY,
        resume_from=resume_from,
    )


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _directory_hashes(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): _sha256(item)
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def _operation_summary(result: Any) -> dict[str, Any]:
    summary = result.provider_summary
    _require(summary is not None, "PROVIDER_SUMMARY_MISSING")
    return {
        "provider_id": summary.provider_id,
        "credit_semantics": summary.credit_semantics.value,
        "credits": summary.credits,
        "logical_operation_count": summary.operation_count,
        "transport_attempt_count": summary.transport_attempt_count,
        "executed_operation_count": summary.executed_operation_count,
        "replayed_operation_count": summary.replayed_operation_count,
        "logical_operations": [item.to_dict() for item in summary.logical_operations],
        "transport_attempts": [item.to_dict() for item in summary.transport_attempts],
    }


def _checkpoint_inventory(output: Path) -> list[dict[str, Any]]:
    inventory = []
    for path in sorted((output / "checkpoints").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        parameters = payload["normalized_request_parameters"]
        inventory.append(
            {
                "filename": path.name,
                "file_sha256": _sha256(path),
                "checkpoint_id": payload["checkpoint_id"],
                "integrity_sha256": payload["integrity_sha256"],
                "operation": payload["operation"],
                "asin": parameters.get("asin") if isinstance(parameters, Mapping) else None,
                "provenance_raw_evidence_id": payload["provenance_raw_evidence_id"],
            }
        )
    return inventory


def _scan_secret(paths: tuple[Path, ...], secret: str) -> dict[str, Any]:
    secret_bytes = secret.encode("utf-8")
    matches: list[str] = []
    forbidden_header_matches: list[str] = []
    filename_match = False
    for root in paths:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if secret in path.name:
                filename_match = True
            if not path.is_file():
                continue
            content = path.read_bytes()
            relative = f"{root.name}/{path.relative_to(root).as_posix()}"
            if secret_bytes in content:
                matches.append(relative)
            lowered = content.lower()
            if b"x-api-key" in lowered or b'"authorization"' in lowered:
                forbidden_header_matches.append(relative)
    return {
        "credential_value_match_count": len(matches),
        "credential_value_matches": matches,
        "credential_filename_match": filename_match,
        "forbidden_secret_header_match_count": len(forbidden_header_matches),
        "forbidden_secret_header_matches": forbidden_header_matches,
    }


def _first_run_evidence(result: Any, wrapper: PreNetworkFaultInjectionTransport) -> dict[str, Any]:
    summary = result.provider_summary
    _require(result.status is ProductionRunStatus.FAILED, "FIRST_STATUS")
    _require(result.error is not None and result.error["code"] == "BOUNDED_RETRY_EXHAUSTED", "FIRST_ERROR")
    _require(summary is not None, "FIRST_SUMMARY")
    _require(summary.credit_semantics is ProviderCreditSemantics.LIVE_PROVIDER_REPORTED, "FIRST_CREDIT_SEMANTICS")
    _require(summary.credits is not None, "CREDIT_GATE_UNAVAILABLE_FIRST")
    _require(summary.credits <= 6, "CREDIT_GATE_FIRST_OVER_6")
    _require(summary.operation_count == 4, "FIRST_LOGICAL_COUNT")
    _require(summary.transport_attempt_count == 6, "FIRST_ATTEMPT_COUNT")
    _require(summary.executed_operation_count == 4 and summary.replayed_operation_count == 0, "FIRST_EXECUTION_COUNTS")
    logical = summary.logical_operations
    _require(tuple(item.operation for item in logical) == ("asin_info", "asin_keywords", "asin_keywords", "asin_keywords"), "FIRST_OPERATION_ORDER")
    attempts_by_id = {
        item.logical_operation_id: [attempt for attempt in summary.transport_attempts if attempt.logical_operation_id == item.logical_operation_id]
        for item in logical
    }
    asin2_attempts = attempts_by_id[logical[2].logical_operation_id]
    asin3_attempts = attempts_by_id[logical[3].logical_operation_id]
    _require(
        [(item.attempt_ordinal, item.status.value, item.provider_error_code) for item in asin2_attempts]
        == [(1, "FAILED", "NETWORK"), (2, "SUCCEEDED", None)],
        "FIRST_ASIN2_ATTEMPTS",
    )
    _require(
        [(item.attempt_ordinal, item.status.value, item.provider_error_code) for item in asin3_attempts]
        == [(1, "FAILED", "NETWORK"), (2, "FAILED", "NETWORK")],
        "FIRST_ASIN3_ATTEMPTS",
    )
    injected = [item for item in wrapper.events if item["action"] == "INJECT_NETWORK"]
    delegated = [item for item in wrapper.events if item["delegated_to_http"]]
    _require(len(injected) == 3, "FIRST_INJECTED_COUNT")
    _require(all(not item["delegated_to_http"] for item in injected), "FIRST_INJECTION_PRE_NETWORK")
    _require(all(item["provider_reported_credits"] is None for item in injected), "FIRST_INJECTION_CREDITS")
    _require(wrapper.http_delegation_count == 3, "FIRST_HTTP_DELEGATION_COUNT")
    _require(
        [item["operation_key"] for item in delegated]
        == ["asin_info", f"asin_keywords:{ASINS[0]}", f"asin_keywords:{ASINS[1]}"],
        "FIRST_HTTP_OPERATION_SET",
    )
    output = Path(result.artifact_paths["run_manifest"]).parent
    inventory = _checkpoint_inventory(output)
    _require(len(inventory) == 3, "FIRST_CHECKPOINT_COUNT")
    request = _request(output, result.run_id)
    loaded = load_resume_source(output, expected_request_fingerprint=run_request_fingerprint(request))
    _require(len(loaded.checkpoints) == 3, "FIRST_CHECKPOINT_VALIDATION")
    _require(not (output / "market_report.json").exists(), "FIRST_REPORT_PRESENT")
    _require(not (output / "operator_market_report.xlsx").exists(), "FIRST_XLSX_PRESENT")
    _require(not (output / "operator_market_report.md").exists(), "FIRST_MARKDOWN_PRESENT")
    manifest = json.loads((output / "run_manifest.json").read_text(encoding="utf-8"))
    _require(manifest["stages"][-1]["stage"] == "run_manifest", "FIRST_MANIFEST_ORDER")
    _require(manifest["stages"][-1]["status"] == "COMPLETE", "FIRST_MANIFEST_COMPLETE")
    return {
        "status": result.status.value,
        "error_code": result.error["code"],
        "provider": _operation_summary(result),
        "transport_events": deepcopy(wrapper.events),
        "injected_failure_count": len(injected),
        "http_delegation_count": wrapper.http_delegation_count,
        "checkpoint_count": len(inventory),
        "checkpoints": inventory,
        "normal_delivery_artifacts_present": False,
        "manifest_final_stage": manifest["stages"][-1],
    }


def _resume_evidence(result: Any, wrapper: PreNetworkFaultInjectionTransport, output: Path) -> dict[str, Any]:
    summary = result.provider_summary
    _require(result.status is ProductionRunStatus.SUCCEEDED, "RESUME_STATUS")
    _require(result.requested_asin_count == 3 and result.resolved_asin_count == 3, "RESUME_COHORT")
    _require(summary is not None, "RESUME_SUMMARY")
    _require(summary.credit_semantics is ProviderCreditSemantics.LIVE_PROVIDER_REPORTED, "RESUME_CREDIT_SEMANTICS")
    _require(summary.credits is not None, "CREDIT_GATE_UNAVAILABLE_RESUME")
    _require(summary.operation_count == 4, "RESUME_LOGICAL_COUNT")
    _require(summary.replayed_operation_count == 3, "RESUME_REPLAY_COUNT")
    _require(summary.executed_operation_count == 1, "RESUME_EXECUTED_COUNT")
    _require(summary.transport_attempt_count == 1, "RESUME_ATTEMPT_COUNT")
    _require(wrapper.http_delegation_count == 1, "RESUME_HTTP_DELEGATION_COUNT")
    _require(len(wrapper.events) == 1, "RESUME_EVENT_COUNT")
    _require(wrapper.events[0]["operation_key"] == f"asin_keywords:{ASINS[2]}", "RESUME_HTTP_OPERATION")
    _require(wrapper.events[0]["attempt_ordinal"] == 1, "RESUME_HTTP_ATTEMPT")
    _require(wrapper.events[0]["action"] == "DELEGATE_HTTP", "RESUME_UNEXPECTED_INJECTION")
    _require(len(result.artifact_paths) == 4, "RESUME_ARTIFACT_COUNT")
    destination = output.resolve()
    for path_text in result.artifact_paths.values():
        path = Path(path_text).resolve()
        _require(path.is_file() and path.is_relative_to(destination), "RESUME_ARTIFACT_OWNERSHIP")
    report_path = Path(result.artifact_paths["market_report_json"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    validated = validate_market_report_payload(report)
    _require(report["report_version"] == "market-report-v0.1", "RESUME_REPORT_VERSION")
    xlsx_path = Path(result.artifact_paths["operator_xlsx"])
    markdown_path = Path(result.artifact_paths["operator_markdown"])
    _require(xlsx_path.stat().st_size > 2 and xlsx_path.read_bytes()[:2] == b"PK", "RESUME_XLSX")
    _require(markdown_path.stat().st_size > 0, "RESUME_MARKDOWN")
    manifest = json.loads(Path(result.artifact_paths["run_manifest"]).read_text(encoding="utf-8"))
    _require(manifest["stages"][-1]["stage"] == "run_manifest", "RESUME_MANIFEST_ORDER")
    _require(manifest["stages"][-1]["status"] == "COMPLETE", "RESUME_MANIFEST_COMPLETE")
    competition = report["competition"]
    _require(competition["status"] == "PARTIAL", "RESUME_COMPETITION_STATUS")
    for key in ("brand_count", "competition_concentration", "competition_level"):
        _require(competition[key]["availability"] == "UNAVAILABLE", f"RESUME_{key.upper()}_AVAILABILITY")
        _require(competition[key]["value"] is None, f"RESUME_{key.upper()}_VALUE")
    opportunity = report["opportunity_score"]
    _require(opportunity["score_status"] == "PENDING_DATA", "RESUME_OPPORTUNITY_STATUS")
    _require(opportunity["score_value"] is None, "RESUME_OPPORTUNITY_VALUE")
    _require(
        all(
            item["status"] == "UNKNOWN"
            and item["score_value"] is None
            and item["contribution"] is None
            for item in opportunity["dimensions"]
        ),
        "RESUME_OPPORTUNITY_DIMENSIONS",
    )
    artifact_hashes = {
        name: {"path": str(Path(path).resolve()), "size": Path(path).stat().st_size, "sha256": _sha256(Path(path))}
        for name, path in sorted(result.artifact_paths.items())
    }
    return {
        "status": result.status.value,
        "requested_asin_count": result.requested_asin_count,
        "resolved_asin_count": result.resolved_asin_count,
        "report_id": validated.report_id,
        "report_version": report["report_version"],
        "provider": _operation_summary(result),
        "transport_events": deepcopy(wrapper.events),
        "http_delegation_count": wrapper.http_delegation_count,
        "artifacts": artifact_hashes,
        "manifest_final_stage": manifest["stages"][-1],
        "truthful_unavailable": True,
        "checkpoint_count": result.recovery["checkpoint_count"],
        "resume_source_run_id": result.recovery["resume_source_run_id"],
    }


def _safe_base_url(value: str) -> str:
    parsed = urlsplit(value)
    _require(
        parsed.scheme == "https"
        and bool(parsed.netloc)
        and parsed.username is None
        and parsed.password is None
        and parsed.path in {"", "/"}
        and not parsed.query
        and not parsed.fragment,
        "BASE_URL_INVALID",
    )
    return value.rstrip("/")


def run_live(args: argparse.Namespace) -> int:
    faulted_output = args.faulted_output.resolve()
    resume_output = args.resume_output.resolve()
    evidence_path = args.evidence_path.resolve()
    evidence: dict[str, Any] = {
        "validation_contract_version": VALIDATION_CONTRACT_VERSION,
        "baseline": BASELINE,
        "cohort": list(ASINS),
        "marketplace": MARKETPLACE,
        "category": CATEGORY,
        "mode": "live",
        "credential_status": {"XIYOU_API_KEY_configured": False},
        "pipeline_invocation_count": 0,
        "verdict": "BLOCKED",
        "failure_gate": None,
    }
    secret = os.environ.get("XIYOU_API_KEY", "")
    try:
        _require(bool(secret.strip()), "CREDENTIAL_UNAVAILABLE")
        evidence["credential_status"]["XIYOU_API_KEY_configured"] = True
        base_url = _safe_base_url(args.base_url)
        _require(faulted_output != resume_output, "OUTPUT_DIRECTORIES_NOT_DISTINCT")
        _require(not faulted_output.exists(), "FAULTED_OUTPUT_NOT_FRESH")
        _require(not resume_output.exists(), "RESUME_OUTPUT_NOT_FRESH")
        _require(not evidence_path.is_relative_to(faulted_output), "EVIDENCE_INSIDE_FAULTED_OUTPUT")
        _require(not evidence_path.is_relative_to(resume_output), "EVIDENCE_INSIDE_RESUME_OUTPUT")
        evidence["base_url_origin"] = base_url
        evidence["fault_schedule"] = {
            "asin_info": "delegate attempt 1",
            ASINS[0]: "delegate attempt 1",
            ASINS[1]: "inject attempt 1; delegate attempt 2",
            ASINS[2]: "inject attempts 1 and 2; no attempt 3",
        }
        evidence["pre_network_self_test"] = self_test()

        first_captures: list[tuple[ProviderRuntime, PreNetworkFaultInjectionTransport]] = []
        first_request = _request(faulted_output, "sp036a-faulted-6d7dc8e")
        evidence["pipeline_invocation_count"] += 1
        first_result = ProductionPipelineOrchestrator(
            provider_runtime_factory=_runtime_factory(
                base_url=base_url,
                schedule=_FAULT_SCHEDULE,
                captures=first_captures,
            )
        ).run(first_request)
        _require(len(first_captures) == 1, "FIRST_RUNTIME_COUNT")
        evidence["first_run"] = _first_run_evidence(first_result, first_captures[0][1])

        first_secret_scan = _scan_secret((faulted_output,), secret)
        _require(first_secret_scan["credential_value_match_count"] == 0, "FIRST_SECRET_VALUE")
        _require(not first_secret_scan["credential_filename_match"], "FIRST_SECRET_FILENAME")
        _require(first_secret_scan["forbidden_secret_header_match_count"] == 0, "FIRST_SECRET_HEADER")
        evidence["first_run"]["secret_safety"] = first_secret_scan
        source_hashes_before = _directory_hashes(faulted_output)

        resume_captures: list[tuple[ProviderRuntime, PreNetworkFaultInjectionTransport]] = []
        resume_request = _request(
            resume_output,
            "sp036a-resume-6d7dc8e",
            resume_from=faulted_output,
        )
        evidence["pipeline_invocation_count"] += 1
        resume_result = ProductionPipelineOrchestrator(
            provider_runtime_factory=_runtime_factory(
                base_url=base_url,
                schedule={},
                captures=resume_captures,
            )
        ).run(resume_request)
        _require(len(resume_captures) == 1, "RESUME_RUNTIME_COUNT")
        evidence["resume_run"] = _resume_evidence(
            resume_result,
            resume_captures[0][1],
            resume_output,
        )
        source_hashes_after = _directory_hashes(faulted_output)
        _require(source_hashes_before == source_hashes_after, "SOURCE_IMMUTABILITY")
        evidence["source_immutability"] = {
            "unchanged": True,
            "file_count": len(source_hashes_before),
            "before": source_hashes_before,
            "after": source_hashes_after,
        }

        first_credits = evidence["first_run"]["provider"]["credits"]
        resume_credits = evidence["resume_run"]["provider"]["credits"]
        cumulative = first_credits + resume_credits
        _require(cumulative <= 8, "CREDIT_GATE_CUMULATIVE_OVER_8")
        actual_operations = [
            item["operation_key"]
            for item in (
                evidence["first_run"]["transport_events"]
                + evidence["resume_run"]["transport_events"]
            )
            if item["delegated_to_http"]
        ]
        _require(
            actual_operations
            == [
                "asin_info",
                f"asin_keywords:{ASINS[0]}",
                f"asin_keywords:{ASINS[1]}",
                f"asin_keywords:{ASINS[2]}",
            ],
            "CUMULATIVE_HTTP_OPERATION_SET",
        )
        evidence["credit_audit"] = {
            "first_run_provider_reported_credits": first_credits,
            "resume_provider_reported_credits": resume_credits,
            "cumulative_provider_reported_credits": cumulative,
            "maximum_allowed": 8,
            "historical_credits_recounted": False,
            "actual_http_operations": actual_operations,
            "actual_http_operation_count": len(actual_operations),
            "injected_attempt_credits": 0,
        }
        combined_secret_scan = _scan_secret((faulted_output, resume_output), secret)
        _require(combined_secret_scan["credential_value_match_count"] == 0, "FINAL_SECRET_VALUE")
        _require(not combined_secret_scan["credential_filename_match"], "FINAL_SECRET_FILENAME")
        _require(combined_secret_scan["forbidden_secret_header_match_count"] == 0, "FINAL_SECRET_HEADER")
        evidence["secret_safety"] = combined_secret_scan
        _require(secret not in canonical_json(evidence), "EVIDENCE_SECRET_VALUE")
        evidence["verdict"] = "PASS"
    except ValidationGateError as exc:
        evidence["failure_gate"] = exc.code
    except Exception as exc:  # Do not serialize raw exception strings.
        evidence["failure_gate"] = "UNEXPECTED_VALIDATION_FAILURE"
        evidence["unexpected_exception_type"] = type(exc).__name__
    finally:
        if secret:
            _require(secret not in canonical_json(evidence), "FINAL_EVIDENCE_SECRET_VALUE")
        write_json_atomic(evidence_path, evidence)

    print(
        json.dumps(
            {
                "verdict": evidence["verdict"],
                "failure_gate": evidence["failure_gate"],
                "pipeline_invocation_count": evidence["pipeline_invocation_count"],
                "evidence_path": str(evidence_path),
            },
            sort_keys=True,
        )
    )
    return 0 if evidence["verdict"] == "PASS" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--faulted-output", type=Path)
    parser.add_argument("--resume-output", type=Path)
    parser.add_argument("--evidence-path", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.self_test:
        print(json.dumps(self_test(), sort_keys=True))
        return 0
    if args.live:
        if args.faulted_output is None or args.resume_output is None or args.evidence_path is None:
            print("live validation requires faulted-output, resume-output and evidence-path", file=sys.stderr)
            return 2
        return run_live(args)
    print("choose exactly one of --self-test or --live", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
