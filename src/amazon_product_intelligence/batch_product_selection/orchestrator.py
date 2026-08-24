"""Sequential orchestration over the existing Production Pipeline."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.production_pipeline import (
    ProductionPipelineOrchestrator,
    RecoveryContractError,
    ProductionRunRequest,
    ProductionRunStatus,
)
from amazon_product_intelligence.production_pipeline.recovery import (
    load_resume_source,
    run_request_fingerprint,
)

from .delivery import BatchSummaryDelivery
from .errors import BatchSelectionError, BatchSelectionErrorCode
from .models import (
    BATCH_INPUT_CONTRACT_VERSION,
    BATCH_RANKING_STATUS,
    BatchCandidateDefinition,
    BatchCandidateSummary,
    BatchSelectionRequest,
    BatchSelectionResult,
    BatchStatus,
    BatchUsageSummary,
    CandidateExecutionSource,
    CandidateRecoveryDisposition,
)


PipelineFactory = Callable[[str], ProductionPipelineOrchestrator]

_CANDIDATE_ARTIFACTS = {
    "market_report_json": "market_report.json",
    "operator_xlsx": "operator_market_report.xlsx",
    "operator_markdown": "operator_market_report.md",
    "run_manifest": "run_manifest.json",
}


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path, *, code: BatchSelectionErrorCode, message: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BatchSelectionError(code, message, details={"file": path.name}) from exc
    if not isinstance(payload, Mapping):
        raise BatchSelectionError(code, message, details={"file": path.name})
    return payload


def _candidate_fingerprint(
    request: BatchSelectionRequest, candidate: BatchCandidateDefinition
) -> str:
    return deterministic_id(
        "batch-selection-candidate",
        {
            "batch_input_fingerprint": request.input_fingerprint,
            "candidate": candidate.fingerprint_material(),
        },
    )


def _provider_usage(
    provider_summary: Mapping[str, Any] | None,
    *,
    reused_success: bool = False,
) -> dict[str, Any]:
    if provider_summary is None:
        return {
            "provider_id": "UNAVAILABLE",
            "logical_operation_count": 0,
            "new_transport_attempts": 0,
            "executed_operations": 0,
            "checkpoint_replayed_operations": 0,
            "reused_source_operations": 0,
            "current_run_observed_credits": None,
            "source_observed_credits": None,
            "credit_semantics": "UNAVAILABLE",
            "billing_note": "provider usage unavailable",
        }
    semantics = str(provider_summary.get("credit_semantics", "UNAVAILABLE"))
    logical = int(provider_summary.get("operation_count", 0))
    credits = provider_summary.get("credits")
    if reused_success:
        return {
            "provider_id": str(provider_summary.get("provider_id", "UNAVAILABLE")),
            "logical_operation_count": logical,
            "new_transport_attempts": 0,
            "executed_operations": 0,
            "checkpoint_replayed_operations": 0,
            "reused_source_operations": logical,
            "current_run_observed_credits": 0.0,
            "source_observed_credits": credits,
            "credit_semantics": semantics,
            "billing_note": (
                "successful source artifacts reused; no current-run provider call; "
                + ("fixture reference credits are not billed" if semantics == "FIXTURE_REFERENCE" else "source provider usage is historical")
            ),
        }
    return {
        "provider_id": str(provider_summary.get("provider_id", "UNAVAILABLE")),
        "logical_operation_count": logical,
        "new_transport_attempts": int(provider_summary.get("transport_attempt_count", 0)),
        "executed_operations": int(provider_summary.get("executed_operation_count", 0)),
        "checkpoint_replayed_operations": int(
            provider_summary.get("replayed_operation_count", 0)
        ),
        "reused_source_operations": 0,
        "current_run_observed_credits": credits,
        "source_observed_credits": None,
        "credit_semantics": semantics,
        "billing_note": (
            "fixture reference credits; not billed"
            if semantics == "FIXTURE_REFERENCE"
            else "live provider-reported credits"
            if semantics == "LIVE_PROVIDER_REPORTED"
            else "provider usage unavailable"
        ),
    }


def _artifact_hashes(paths: Mapping[str, str]) -> dict[str, str]:
    return {
        name: _sha256(Path(path))
        for name, path in sorted(paths.items())
        if Path(path).is_file()
    }


def _candidate_summary_from_manifest(
    *,
    request: BatchSelectionRequest,
    candidate: BatchCandidateDefinition,
    manifest: Mapping[str, Any],
    execution_source: CandidateExecutionSource,
    reused_success: bool = False,
) -> BatchCandidateSummary:
    status = str(manifest.get("status", "FAILED"))
    artifact_paths = manifest.get("artifact_paths")
    if not isinstance(artifact_paths, Mapping):
        artifact_paths = {}
    safe_paths = {
        str(name): str(path)
        for name, path in artifact_paths.items()
        if isinstance(name, str) and isinstance(path, str) and Path(path).is_file()
    }
    provider_summary = manifest.get("provider_summary")
    provider_mapping = provider_summary if isinstance(provider_summary, Mapping) else None
    workflow = manifest.get("operator_workflow")
    workflow_mapping = workflow if isinstance(workflow, Mapping) else None
    report: Mapping[str, Any] | None = None
    if status == ProductionRunStatus.SUCCEEDED.value:
        required = set(_CANDIDATE_ARTIFACTS)
        if set(safe_paths) != required:
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "successful candidate does not own all normal production artifacts",
                details={"candidate_id": candidate.candidate_id},
            )
        if workflow_mapping is None:
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "successful candidate is missing operator workflow",
                details={"candidate_id": candidate.candidate_id},
            )
        report = _load_json(
            Path(safe_paths["market_report_json"]),
            code=BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
            message="candidate Market Report is unreadable",
        )
    top_themes = tuple(workflow_mapping.get("top_buyer_need_themes", ()))[:3] if workflow_mapping else ()
    top_missing = tuple(workflow_mapping.get("missing_evidence", ()))[:3] if workflow_mapping else ()
    next_actions = tuple(workflow_mapping.get("next_actions", ()))[:3] if workflow_mapping else ()
    opportunity = report.get("opportunity_score") if report else None
    competition = report.get("competition") if report else None
    opportunity_mapping = opportunity if isinstance(opportunity, Mapping) else {}
    competition_mapping = competition if isinstance(competition, Mapping) else {}
    error = manifest.get("error")
    error_mapping = error if isinstance(error, Mapping) else None
    lineage = set(workflow_mapping.get("lineage_reference_ids", ())) if workflow_mapping else set()
    if workflow_mapping:
        lineage.update(
            value
            for value in (
                workflow_mapping.get("snapshot_id"),
                workflow_mapping.get("semantic_fingerprint"),
                workflow_mapping.get("market_report_id"),
            )
            if isinstance(value, str)
        )
    return BatchCandidateSummary(
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=_candidate_fingerprint(request, candidate),
        execution_source=execution_source,
        production_run_status=status,
        requested_asin_count=int(manifest.get("requested_asin_count", len(candidate.asins))),
        resolved_asin_count=int(manifest.get("resolved_asin_count", 0)),
        market_report_id=(
            str(report.get("report_id")) if report and report.get("report_id") else None
        ),
        market_report_version=(
            str(report.get("report_version"))
            if report and report.get("report_version")
            else None
        ),
        operator_workflow_ruleset_version=(
            str(workflow_mapping.get("ruleset_version")) if workflow_mapping else None
        ),
        operator_semantic_fingerprint=(
            str(workflow_mapping.get("semantic_fingerprint")) if workflow_mapping else None
        ),
        operator_action=(
            str(workflow_mapping.get("operator_action")) if workflow_mapping else None
        ),
        recommendation_type=(
            str(workflow_mapping.get("recommendation_type")) if workflow_mapping else None
        ),
        evidence_readiness=(
            str(workflow_mapping.get("evidence_readiness")) if workflow_mapping else None
        ),
        action_reason=(
            str(workflow_mapping.get("action_reason")) if workflow_mapping else None
        ),
        top_buyer_need_themes=tuple(top_themes),
        competition_status=(
            str(competition_mapping.get("status"))
            if competition_mapping.get("status") is not None
            else None
        ),
        missing_evidence_count=(
            len(tuple(workflow_mapping.get("missing_evidence", ())))
            if workflow_mapping
            else None
        ),
        top_missing_evidence=tuple(top_missing),
        opportunity_score_status=(
            str(opportunity_mapping.get("score_status"))
            if opportunity_mapping.get("score_status") is not None
            else None
        ),
        opportunity_score_value=opportunity_mapping.get("score_value"),
        ranking_status=BATCH_RANKING_STATUS,
        next_actions=tuple(next_actions),
        run_health=(workflow_mapping.get("run_health") if workflow_mapping else None),
        provider_usage=_provider_usage(provider_mapping, reused_success=reused_success),
        artifact_paths=safe_paths,
        artifact_hashes=_artifact_hashes(safe_paths),
        lineage_reference_ids=tuple(sorted(lineage)),
        error=error_mapping,
        recovery_disposition=(
            CandidateRecoveryDisposition.NOT_APPLICABLE
            if status == ProductionRunStatus.SUCCEEDED.value
            else CandidateRecoveryDisposition.CHECKPOINT_RESUME_AVAILABLE
            if "run_manifest" in safe_paths
            else CandidateRecoveryDisposition.FRESH_EXECUTION_REQUIRED
        ),
    )


def _failed_exception_summary(
    request: BatchSelectionRequest,
    candidate: BatchCandidateDefinition,
    *,
    execution_source: CandidateExecutionSource,
) -> BatchCandidateSummary:
    return BatchCandidateSummary(
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=_candidate_fingerprint(request, candidate),
        execution_source=execution_source,
        production_run_status="FAILED",
        requested_asin_count=len(candidate.asins),
        resolved_asin_count=0,
        market_report_id=None,
        market_report_version=None,
        operator_workflow_ruleset_version=None,
        operator_semantic_fingerprint=None,
        operator_action=None,
        recommendation_type=None,
        evidence_readiness=None,
        action_reason=None,
        top_buyer_need_themes=(),
        competition_status=None,
        missing_evidence_count=None,
        top_missing_evidence=(),
        opportunity_score_status=None,
        opportunity_score_value=None,
        ranking_status=BATCH_RANKING_STATUS,
        next_actions=(),
        run_health=None,
        provider_usage=_provider_usage(None),
        artifact_paths={},
        artifact_hashes={},
        lineage_reference_ids=(),
        error={
            "code": "CANDIDATE_ORCHESTRATOR_EXCEPTION",
            "message": "candidate orchestration failed before a safe result was returned",
        },
        recovery_disposition=CandidateRecoveryDisposition.FRESH_EXECUTION_REQUIRED,
    )


def _production_request(
    request: BatchSelectionRequest,
    candidate: BatchCandidateDefinition,
    *,
    output_directory: Path,
    resume_from: Path | None,
) -> ProductionRunRequest:
    return ProductionRunRequest(
        marketplace=request.marketplace,
        asins=candidate.asins,
        output_directory=output_directory,
        provider_preference=request.provider_preference,
        provider_config_reference=request.provider_config_reference,
        run_id=f"{request.batch_id}:{candidate.candidate_id}",
        mode=request.mode,
        category_name=request.category_name,
        resume_from=resume_from,
    )


def _aggregate_usage(candidates: tuple[BatchCandidateSummary, ...]) -> BatchUsageSummary:
    semantics = {
        str(item.provider_usage["credit_semantics"])
        for item in candidates
        if item.provider_usage["credit_semantics"] != "UNAVAILABLE"
    }
    credits = [
        item.provider_usage["current_run_observed_credits"] for item in candidates
    ]
    if len(semantics) > 1:
        credit_semantics = "MIXED_UNAVAILABLE"
        observed_credits = None
        billing_note = "incompatible credit semantics; no combined billed total"
    elif semantics == {"FIXTURE_REFERENCE"}:
        credit_semantics = "FIXTURE_REFERENCE"
        observed_credits = sum(float(value or 0.0) for value in credits)
        billing_note = "fixture reference credits; not billed"
    elif semantics == {"LIVE_PROVIDER_REPORTED"}:
        credit_semantics = "LIVE_PROVIDER_REPORTED"
        observed_credits = sum(float(value or 0.0) for value in credits)
        billing_note = "live provider-reported current-run credits"
    else:
        credit_semantics = "UNAVAILABLE"
        observed_credits = None
        billing_note = "provider credit semantics unavailable"
    return BatchUsageSummary(
        total_logical_operations=sum(
            int(item.provider_usage["logical_operation_count"]) for item in candidates
        ),
        new_transport_attempts=sum(
            int(item.provider_usage["new_transport_attempts"]) for item in candidates
        ),
        executed_operations=sum(
            int(item.provider_usage["executed_operations"]) for item in candidates
        ),
        checkpoint_replayed_operations=sum(
            int(item.provider_usage["checkpoint_replayed_operations"])
            for item in candidates
        ),
        reused_source_operations=sum(
            int(item.provider_usage["reused_source_operations"]) for item in candidates
        ),
        current_run_observed_credits=observed_credits,
        credit_semantics=credit_semantics,
        billing_note=billing_note,
        per_candidate_semantics={
            item.candidate_id: str(item.provider_usage["credit_semantics"])
            for item in candidates
        },
    )


class BatchProductSelectionOrchestrator:
    """Run explicit candidates sequentially through ProductionPipelineOrchestrator."""

    def __init__(
        self,
        *,
        pipeline_factory: PipelineFactory | None = None,
        delivery: BatchSummaryDelivery | None = None,
    ) -> None:
        self._pipeline_factory = pipeline_factory or (
            lambda _candidate_id: ProductionPipelineOrchestrator()
        )
        self._delivery = delivery or BatchSummaryDelivery()

    def run(self, request: BatchSelectionRequest) -> BatchSelectionResult:
        if not isinstance(request, BatchSelectionRequest):
            raise TypeError("run requires BatchSelectionRequest")
        self._assert_fresh_destination(request.output_directory)
        source: BatchSelectionResult | None = None
        resume_sources: dict[str, Path | None] = {}
        if request.resume_from:
            source, resume_sources = self._load_resume_batch(request)
        source_by_id = (
            {item.candidate_id: item for item in source.candidates} if source else {}
        )
        request.output_directory.mkdir(parents=True)
        candidate_root = request.output_directory / "candidates"
        summaries: list[BatchCandidateSummary] = []
        for candidate in request.candidates:
            prior = source_by_id.get(candidate.candidate_id)
            if prior is not None and prior.production_run_status == "SUCCEEDED":
                source_directory = resume_sources[candidate.candidate_id]
                assert source_directory is not None
                manifest = _load_json(
                    source_directory / "run_manifest.json",
                    code=BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                    message="reused candidate manifest is unreadable",
                )
                summaries.append(
                    _candidate_summary_from_manifest(
                        request=request,
                        candidate=candidate,
                        manifest=manifest,
                        execution_source=CandidateExecutionSource.REUSED_SUCCESS,
                        reused_success=True,
                    )
                )
                continue
            resume_from = None
            execution_source = CandidateExecutionSource.NEW_EXECUTION
            if prior is not None and resume_sources[candidate.candidate_id] is not None:
                resume_from = resume_sources[candidate.candidate_id]
                execution_source = CandidateExecutionSource.CHECKPOINT_RESUME
            candidate_output = candidate_root / candidate.candidate_id
            production_request = _production_request(
                request,
                candidate,
                output_directory=candidate_output,
                resume_from=resume_from,
            )
            try:
                result = self._pipeline_factory(candidate.candidate_id).run(
                    production_request
                )
                manifest = result.to_dict()
                summaries.append(
                    _candidate_summary_from_manifest(
                        request=request,
                        candidate=candidate,
                        manifest=manifest,
                        execution_source=execution_source,
                    )
                )
            except BatchSelectionError:
                raise
            except Exception:
                summaries.append(
                    _failed_exception_summary(
                        request,
                        candidate,
                        execution_source=execution_source,
                    )
                )
        candidate_summaries = tuple(sorted(summaries, key=lambda item: item.candidate_id))
        succeeded = sum(
            item.production_run_status == ProductionRunStatus.SUCCEEDED.value
            for item in candidate_summaries
        )
        failed = len(candidate_summaries) - succeeded
        status = (
            BatchStatus.SUCCEEDED
            if failed == 0
            else BatchStatus.FAILED
            if succeeded == 0
            else BatchStatus.PARTIAL
        )
        artifact_paths = {
            "batch_json": str(
                (request.output_directory / "batch_selection_result.json").resolve()
            ),
            "batch_xlsx": str(
                (request.output_directory / "batch_selection_summary.xlsx").resolve()
            ),
            "batch_markdown": str(
                (request.output_directory / "batch_selection_summary.md").resolve()
            ),
        }
        semantic_fingerprint = deterministic_id(
            "batch-selection-semantic",
            {
                "input_fingerprint": request.input_fingerprint,
                "status": status.value,
                "candidates": [item.semantic_view() for item in candidate_summaries],
            },
        )
        batch_result = BatchSelectionResult(
            batch_id=request.batch_id,
            input_contract_version=BATCH_INPUT_CONTRACT_VERSION,
            input_fingerprint=request.input_fingerprint,
            semantic_fingerprint=semantic_fingerprint,
            status=status,
            candidate_count=len(candidate_summaries),
            succeeded_count=succeeded,
            failed_count=failed,
            candidates=candidate_summaries,
            usage=_aggregate_usage(candidate_summaries),
            batch_artifact_paths=artifact_paths,
            source_batch_directory=(
                str(request.resume_from.resolve()) if request.resume_from else None
            ),
            warnings=(
                "Ranking is UNAVAILABLE; candidate order is deterministic workflow organization, not product attractiveness.",
            ),
        )
        try:
            self._delivery.deliver(batch_result, request.output_directory)
        except BatchSelectionError:
            raise
        except Exception as exc:
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_DELIVERY_FAILURE,
                "batch aggregate delivery failed",
            ) from exc
        return batch_result

    @staticmethod
    def _assert_fresh_destination(destination: Path) -> None:
        if destination.exists() or destination.is_symlink():
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_OUTPUT_CONFLICT,
                "batch output directory must be fresh and must not already exist",
                details={"output_directory": str(destination)},
            )

    def _load_resume_batch(
        self, request: BatchSelectionRequest
    ) -> tuple[BatchSelectionResult, dict[str, Path | None]]:
        source_directory = request.resume_from
        assert source_directory is not None
        payload = _load_json(
            source_directory / "batch_selection_result.json",
            code=BatchSelectionErrorCode.INCOMPATIBLE_BATCH_RESUME,
            message="resume source does not contain a readable batch result",
        )
        try:
            result = BatchSelectionResult.from_dict(payload)
        except Exception as exc:
            raise BatchSelectionError(
                BatchSelectionErrorCode.INCOMPATIBLE_BATCH_RESUME,
                "resume source batch result contract is invalid",
            ) from exc
        if result.input_fingerprint != request.input_fingerprint:
            raise BatchSelectionError(
                BatchSelectionErrorCode.INCOMPATIBLE_BATCH_RESUME,
                "resume source batch input fingerprint does not match",
            )
        current_ids = tuple(item.candidate_id for item in request.candidates)
        source_ids = tuple(item.candidate_id for item in result.candidates)
        if source_ids != current_ids:
            raise BatchSelectionError(
                BatchSelectionErrorCode.INCOMPATIBLE_BATCH_RESUME,
                "resume source candidate inventory does not match",
            )
        resume_sources: dict[str, Path | None] = {}
        for candidate, prior in zip(request.candidates, result.candidates, strict=True):
            if prior.candidate_fingerprint != _candidate_fingerprint(request, candidate):
                raise BatchSelectionError(
                    BatchSelectionErrorCode.INCOMPATIBLE_BATCH_RESUME,
                    "resume source candidate fingerprint does not match",
                    details={"candidate_id": candidate.candidate_id},
                )
            resume_sources[candidate.candidate_id] = self._preflight_source_candidate(
                request,
                candidate,
                prior,
                source_result=result,
            )
        return result, resume_sources

    @staticmethod
    def _source_candidate_directory(
        source_directory: Path, candidate_id: str
    ) -> Path:
        return source_directory / "candidates" / candidate_id

    def _preflight_source_candidate(
        self,
        request: BatchSelectionRequest,
        candidate: BatchCandidateDefinition,
        prior: BatchCandidateSummary,
        *,
        source_result: BatchSelectionResult,
    ) -> Path | None:
        if prior.production_run_status == ProductionRunStatus.SUCCEEDED.value:
            return self._resolve_successful_artifact_origin(
                request,
                candidate,
                prior,
                source_result=source_result,
            )

        if not prior.artifact_paths:
            if prior.artifact_hashes:
                raise BatchSelectionError(
                    BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                    "failed candidate has hashes without recorded artifacts",
                    details={"candidate_id": candidate.candidate_id},
                )
            return None

        source_directory = request.resume_from
        assert source_directory is not None
        directory = self._source_candidate_directory(
            source_directory, candidate.candidate_id
        )
        expected_manifest = directory / "run_manifest.json"
        recorded_manifest = prior.artifact_paths.get("run_manifest")
        if (
            set(prior.artifact_paths) != {"run_manifest"}
            or set(prior.artifact_hashes) != {"run_manifest"}
            or not expected_manifest.is_file()
            or recorded_manifest is None
            or not Path(recorded_manifest).is_absolute()
            or Path(recorded_manifest).resolve() != expected_manifest.resolve()
            or prior.artifact_hashes.get("run_manifest") != _sha256(expected_manifest)
        ):
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "resume source candidate manifest ownership is invalid",
                details={"candidate_id": candidate.candidate_id},
            )
        manifest = _load_json(
            expected_manifest,
            code=BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
            message="failed candidate manifest is unreadable",
        )
        manifest_paths = manifest.get("artifact_paths")
        if (
            manifest.get("status") != ProductionRunStatus.FAILED.value
            or not isinstance(manifest_paths, Mapping)
            or set(manifest_paths) != {"run_manifest"}
            or Path(str(manifest_paths["run_manifest"])).resolve()
            != expected_manifest.resolve()
        ):
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "failed candidate production ownership is invalid",
                details={"candidate_id": candidate.candidate_id},
            )
        candidate_request = _production_request(
            request,
            candidate,
            output_directory=request.output_directory
            / "candidates"
            / candidate.candidate_id,
            resume_from=directory,
        )
        try:
            load_resume_source(
                directory,
                expected_request_fingerprint=run_request_fingerprint(candidate_request),
            )
        except RecoveryContractError as exc:
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "failed candidate checkpoint source failed integrity validation",
                details={"candidate_id": candidate.candidate_id},
            ) from exc
        return directory

    def _resolve_successful_artifact_origin(
        self,
        request: BatchSelectionRequest,
        candidate: BatchCandidateDefinition,
        prior: BatchCandidateSummary,
        *,
        source_result: BatchSelectionResult,
    ) -> Path:
        candidate_id = candidate.candidate_id
        if (
            set(prior.artifact_paths) != set(_CANDIDATE_ARTIFACTS)
            or set(prior.artifact_hashes) != set(_CANDIDATE_ARTIFACTS)
        ):
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "successful candidate artifact inventory is invalid",
                details={"candidate_id": candidate_id},
            )
        paths = {name: Path(prior.artifact_paths[name]) for name in _CANDIDATE_ARTIFACTS}
        if any(not path.is_absolute() for path in paths.values()):
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "successful candidate artifact paths must be absolute",
                details={"candidate_id": candidate_id},
            )
        origin = paths["run_manifest"].parent
        for name, filename in _CANDIDATE_ARTIFACTS.items():
            path = paths[name]
            if (
                not path.is_file()
                or path.is_symlink()
                or path.resolve() != (origin / filename).resolve()
                or prior.artifact_hashes[name] != _sha256(path)
            ):
                raise BatchSelectionError(
                    BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                    "resume source successful candidate artifact integrity failed",
                    details={"candidate_id": candidate_id, "artifact": name},
                )
        manifest = _load_json(
            paths["run_manifest"],
            code=BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
            message="reused candidate manifest is unreadable",
        )
        manifest_paths = manifest.get("artifact_paths")
        if (
            manifest.get("status") != ProductionRunStatus.SUCCEEDED.value
            or manifest.get("run_id") != f"{request.batch_id}:{candidate_id}"
            or manifest.get("requested_asin_count") != len(candidate.asins)
            or manifest.get("resolved_asin_count") != len(candidate.asins)
            or not isinstance(manifest_paths, Mapping)
            or set(manifest_paths) != set(_CANDIDATE_ARTIFACTS)
            or any(
                not isinstance(manifest_paths.get(name), str)
                or Path(manifest_paths[name]).resolve() != paths[name].resolve()
                for name in _CANDIDATE_ARTIFACTS
            )
        ):
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "successful candidate production artifact ownership is invalid",
                details={"candidate_id": candidate_id},
            )

        source_directory = request.resume_from
        assert source_directory is not None
        current_directory = source_directory.resolve()
        current_result = source_result
        seen: set[Path] = set()
        while True:
            if current_directory in seen:
                raise BatchSelectionError(
                    BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                    "batch artifact ownership lineage contains a cycle",
                    details={"candidate_id": candidate_id},
                )
            seen.add(current_directory)
            self._validate_lineage_generation(
                request,
                candidate,
                prior,
                current_directory=current_directory,
                current_result=current_result,
            )
            direct_owner = self._source_candidate_directory(
                current_directory, candidate_id
            ).resolve()
            if direct_owner == origin.resolve():
                return origin
            parent = current_result.source_batch_directory
            if parent is None or not Path(parent).is_absolute():
                raise BatchSelectionError(
                    BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                    "successful candidate artifact origin is outside recorded batch lineage",
                    details={"candidate_id": candidate_id},
                )
            current_directory = Path(parent).resolve()
            payload = _load_json(
                current_directory / "batch_selection_result.json",
                code=BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                message="recorded ancestor batch result is unreadable",
            )
            try:
                current_result = BatchSelectionResult.from_dict(payload)
            except Exception as exc:
                raise BatchSelectionError(
                    BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                    "recorded ancestor batch result contract is invalid",
                    details={"candidate_id": candidate_id},
                ) from exc

    def _validate_lineage_generation(
        self,
        request: BatchSelectionRequest,
        candidate: BatchCandidateDefinition,
        target: BatchCandidateSummary,
        *,
        current_directory: Path,
        current_result: BatchSelectionResult,
    ) -> None:
        batch_json = current_directory / "batch_selection_result.json"
        recorded_batch_json = current_result.batch_artifact_paths.get("batch_json")
        candidates = {item.candidate_id: item for item in current_result.candidates}
        generation_candidate = candidates.get(candidate.candidate_id)
        if (
            not batch_json.is_file()
            or recorded_batch_json is None
            or not Path(recorded_batch_json).is_absolute()
            or Path(recorded_batch_json).resolve() != batch_json.resolve()
            or current_result.input_fingerprint != request.input_fingerprint
            or tuple(candidates) != tuple(item.candidate_id for item in request.candidates)
            or generation_candidate is None
            or generation_candidate.candidate_fingerprint
            != _candidate_fingerprint(request, candidate)
            or generation_candidate.production_run_status
            != ProductionRunStatus.SUCCEEDED.value
            or dict(generation_candidate.artifact_paths) != dict(target.artifact_paths)
            or dict(generation_candidate.artifact_hashes) != dict(target.artifact_hashes)
        ):
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_ARTIFACT_INTEGRITY,
                "batch artifact ownership lineage is inconsistent",
                details={"candidate_id": candidate.candidate_id},
            )


__all__ = ("BatchProductSelectionOrchestrator", "PipelineFactory")
