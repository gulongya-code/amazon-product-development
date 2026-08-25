"""Production-facing composition of the existing public intelligence APIs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping
from uuid import uuid4

from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedAnalysisPipelineV0_3,
    BuyerNeedQueryScope,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.category_product_map import (
    CategoryProductMapBuilderV0_1,
    CategoryProductMapRequest,
    CategoryScopeType,
    build_category_scope,
    unknown_analysis_window,
)
from amazon_product_intelligence.competition_analysis import (
    CompetitionAnalysisBuilderV0_1,
    CompetitionAnalysisRequest,
)
from amazon_product_intelligence.competition_intelligence import (
    CompetitionIntelligenceBuilderV0_1,
    CompetitionIntelligenceRequest,
)
from amazon_product_intelligence.connectors import (
    BoundedTransientRetryPolicy,
    HttpJsonTransport,
    NoRetryPolicy,
    ProviderConfig,
    ProviderConnectorError,
    ProviderAttemptStatus,
    ProviderErrorCode,
    ProviderRegistry,
    ProviderRequest,
    ProviderResolver,
    XiYouProvider,
)
from amazon_product_intelligence.contracts import (
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    deterministic_id,
    product_id,
)
from amazon_product_intelligence.data_cleaning import (
    DataCleaningRequest,
    DataCleaningService,
)
from amazon_product_intelligence.market_analysis import (
    MarketAnalysisBuilderV0_1,
    MarketAnalysisRequest,
)
from amazon_product_intelligence.market_report import (
    MARKET_REPORT_VERSION,
    MarketReportBuildRequest,
    MarketReportBuilderV0_1,
    validate_market_report_payload,
)
from amazon_product_intelligence.market_report.delivery import OperatorReportDelivery
from amazon_product_intelligence.market_report.v0_2 import market_report_v0_2_from_dict
from amazon_product_intelligence.market_report.v0_2.delivery import OperatorReportDeliveryV0_2
from amazon_product_intelligence.market_report.v0_2.production_adapter import (
    ProductionMarketReportV0_2Adapter,
)
from amazon_product_intelligence.normalization import CanonicalNormalizationPipeline
from amazon_product_intelligence.opportunity_intelligence import (
    OpportunityIntelligenceBuilderV0_1,
    OpportunityIntelligenceRequest,
)
from amazon_product_intelligence.opportunity_intelligence.integration_v0_1 import (
    OpportunityConfidence,
)
from amazon_product_intelligence.opportunity_scoring.integration_v0_1 import (
    EXPECTED_METRICS,
    EvidenceBasedOpportunityScorerV0_1,
    OpportunityScoreEvidenceReference,
    OpportunityScoreMetricStatus,
    OpportunityScorePolicyLoader,
    OpportunityScoringIntegrationInput,
    OpportunityScoringMetricInput,
)
from amazon_product_intelligence.product_attribute_extraction import (
    AttributeExtractionPipeline,
    ProductGrain,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)
from amazon_product_intelligence.operator_workflow import (
    OperatorWorkflowBuilderV0_1,
    OperatorWorkflowRequest,
)
from amazon_product_intelligence.semantic_clustering import SemanticClusterBuilder

from .artifacts import RunArtifactLayout, write_json_atomic
from .errors import (
    OutputArtifactConflictError,
    ProductionPipelineError,
    ProductionPipelineErrorCode,
    UnsupportedCapabilityError,
)
from .models import (
    PRODUCTION_PIPELINE_VERSION,
    PipelineStage,
    ProviderCreditSemantics,
    ProviderLogicalOperationSummary,
    ProviderOperationExecutionSource,
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunResult,
    ProductionRunStatus,
    ProviderOperationSummary,
    ProviderTransportAttemptStatus,
    ProviderTransportAttemptSummary,
    StageResult,
    StageStatus,
)
from .providers import (
    AcquiredReplayProvider,
    FixtureTransport,
    RecordingTransport,
    xiyou_reverse_keyword_parameters,
)
from .recovery import (
    RECOVERY_CONTRACT_VERSION,
    CheckpointReplayTransport,
    CheckpointStore,
    ResumeCheckpointSet,
    load_resume_source,
    logical_operation_id,
    run_request_fingerprint,
)


_FIXTURE = Path(__file__).parent / "fixtures" / "dog_water_bottle_v0_1.json"
_SCORE_POLICY = Path(__file__).parent / "fixtures" / "opportunity_score_policy_v0_1.json"
_SAFE_RESOLVER_ATTEMPT_STATUSES = frozenset(
    item.value for item in ProviderAttemptStatus
)
_SAFE_PROVIDER_ERROR_CODES = frozenset(item.value for item in ProviderErrorCode)


@dataclass(slots=True)
class ProviderRuntime:
    registry: ProviderRegistry
    provider: XiYouProvider
    recording_transport: RecordingTransport
    metadata: Mapping[str, Any]
    credit_semantics: ProviderCreditSemantics


ProviderRuntimeFactory = Callable[[ProductionRunRequest], ProviderRuntime]
ReportValidator = Callable[[Mapping[str, Any]], Any]


class _StageTracker:
    def __init__(self) -> None:
        self._records = {
            stage: StageResult(stage=stage, status=StageStatus.NOT_STARTED, detail="not started")
            for stage in PipelineStage
        }

    def start(self, stage: PipelineStage) -> None:
        self._records[stage] = StageResult(
            stage=stage, status=StageStatus.RUNNING, detail="running"
        )

    def finish(
        self,
        stage: PipelineStage,
        detail: str,
        *,
        partial: bool = False,
        evidence_ids: tuple[str, ...] = (),
    ) -> None:
        self._records[stage] = StageResult(
            stage=stage,
            status=StageStatus.PARTIAL if partial else StageStatus.COMPLETE,
            detail=detail,
            evidence_ids=tuple(sorted(set(evidence_ids))),
        )

    def fail(self, stage: PipelineStage, error: ProductionPipelineError) -> None:
        self._records[stage] = StageResult(
            stage=stage,
            status=StageStatus.FAILED,
            detail=str(error),
            error_code=error.code.value,
        )

    def skip_remaining(self) -> None:
        for stage, result in tuple(self._records.items()):
            if result.status is StageStatus.NOT_STARTED and stage is not PipelineStage.MANIFEST:
                self._records[stage] = StageResult(
                    stage=stage,
                    status=StageStatus.SKIPPED,
                    detail="skipped after an earlier failure",
                )

    def skip(self, stage: PipelineStage, detail: str) -> None:
        self._records[stage] = StageResult(
            stage=stage,
            status=StageStatus.SKIPPED,
            detail=detail,
        )

    def records(self) -> tuple[StageResult, ...]:
        return tuple(self._records[stage] for stage in PipelineStage)


class ProductionPipelineOrchestrator:
    """Run SP-034 and write the manifest last after output ownership is established."""

    def __init__(
        self,
        *,
        provider_runtime_factory: ProviderRuntimeFactory | None = None,
        delivery: OperatorReportDelivery | None = None,
        delivery_v0_2: OperatorReportDeliveryV0_2 | None = None,
        report_validator: ReportValidator = validate_market_report_payload,
    ) -> None:
        self._provider_runtime_factory = provider_runtime_factory or self._default_provider_runtime
        self._delivery = delivery or OperatorReportDelivery()
        self._delivery_v0_2 = delivery_v0_2 or OperatorReportDeliveryV0_2()
        self._report_validator = report_validator

    def run(self, request: ProductionRunRequest) -> ProductionRunResult:
        if not isinstance(request, ProductionRunRequest):
            raise TypeError("run requires ProductionRunRequest")
        layout = RunArtifactLayout(output_directory=request.output_directory)
        tracker = _StageTracker()
        run_id = request.run_id or f"run-{uuid4().hex}"
        runtime: ProviderRuntime | None = None
        provider_summary: ProviderOperationSummary | None = None
        logical_operations: list[ProviderLogicalOperationSummary] = []
        transport_attempts: list[ProviderTransportAttemptSummary] = []
        provenance_seen: set[str] = set()
        resolved_count = 0
        warnings: set[str] = set()
        unavailable: set[str] = set()
        produced_report_id: str | None = None
        delivery_status: str | None = None
        request_fingerprint = run_request_fingerprint(request)
        checkpoint_store = CheckpointStore(
            request.output_directory,
            run_id=run_id,
            request_fingerprint=request_fingerprint,
        )
        resume_set: ResumeCheckpointSet | None = None
        current = PipelineStage.INPUT_VALIDATION
        try:
            tracker.start(current)
            conflicts = layout.conflicts()
            if conflicts:
                raise OutputArtifactConflictError(conflicts)
            if (layout.output_directory / "checkpoints").exists():
                raise OutputArtifactConflictError(("recovery_checkpoints",))
            self._validate_operator_request(request)
            if request.resume_from is not None:
                resume_set = load_resume_source(
                    request.resume_from,
                    expected_request_fingerprint=request_fingerprint,
                )
            tracker.finish(current, "operator input validated before provider construction")

            runtime = self._provider_runtime_factory(request)
            timestamps = self._timestamps(request, runtime.metadata)
            data_run_id = deterministic_id(
                "production-data-run",
                {"marketplace": request.marketplace, "asins": request.asins},
            )

            current = PipelineStage.PROVIDER_RESOLUTION
            tracker.start(current)
            resolver = ProviderResolver(runtime.registry)
            product_request = ProviderRequest(
                canonical_field="metric.price",
                parameters={
                    "entities": [
                        {"country": request.marketplace, "asin": asin}
                        for asin in request.asins
                    ]
                },
                marketplace=request.marketplace,
                locale=str(runtime.metadata["locale"]),
                retrieved_at=timestamps["retrieved_at"],
                transformed_at=timestamps["transformed_at"],
                collection_run_id=f"{data_run_id}:asin-info",
                currency=str(runtime.metadata["currency"]),
            )
            product_resolution = self._resolve_operation(
                runtime=runtime,
                resolver=resolver,
                provider_request=product_request,
                operation="asin_info",
                checkpoint_store=checkpoint_store,
                resume_set=resume_set,
                logical_operations=logical_operations,
                transport_attempts=transport_attempts,
            )
            if product_resolution.result.adaptation.raw_evidence is not None:
                provenance_seen.add(
                    product_resolution.result.adaptation.raw_evidence.raw_evidence_id
                )
            tracker.finish(
                current,
                f"selected provider {product_resolution.selected_provider_id}",
                evidence_ids=tuple(
                    item.raw_evidence_id
                    for item in (product_resolution.result.adaptation.raw_evidence,)
                    if item is not None
                ),
            )

            current = PipelineStage.ACQUISITION
            tracker.start(current)
            acquisitions = [product_resolution.result]
            for asin in request.asins:
                keyword_request = ProviderRequest(
                    canonical_field="relationship.product_to_keyword",
                    parameters=xiyou_reverse_keyword_parameters(
                        asin=asin,
                        marketplace=request.marketplace,
                    ),
                    marketplace=request.marketplace,
                    locale=str(runtime.metadata["locale"]),
                    retrieved_at=timestamps["retrieved_at"],
                    transformed_at=timestamps["transformed_at"],
                    collection_run_id=f"{data_run_id}:asin-keywords:{asin}",
                    currency=str(runtime.metadata["currency"]),
                )
                keyword_resolution = self._resolve_operation(
                    runtime=runtime,
                    resolver=resolver,
                    provider_request=keyword_request,
                    operation="asin_keywords",
                    checkpoint_store=checkpoint_store,
                    resume_set=resume_set,
                    logical_operations=logical_operations,
                    transport_attempts=transport_attempts,
                )
                acquisitions.append(keyword_resolution.result)
                if keyword_resolution.result.adaptation.raw_evidence is not None:
                    provenance_seen.add(
                        keyword_resolution.result.adaptation.raw_evidence.raw_evidence_id
                    )
            bundles = tuple(item.adaptation.bundle for item in acquisitions)
            resolved_asins = {
                asin
                for observation in product_resolution.result.adaptation.bundle.observations
                for asin in request.asins
                if observation.subject.subject_id.endswith(f":{asin}")
            }
            resolved_count = len(resolved_asins)
            if resolved_count != len(request.asins):
                raise ProductionPipelineError(
                    ProductionPipelineErrorCode.PROVIDER_FAILURE,
                    "provider did not resolve the complete explicit ASIN cohort",
                    stage=current.value,
                    details={
                        "requested_asin_count": len(request.asins),
                        "resolved_asin_count": resolved_count,
                    },
                )
            provenance_ids = tuple(
                sorted(
                    item.adaptation.raw_evidence.raw_evidence_id
                    for item in acquisitions
                    if item.adaptation.raw_evidence is not None
                )
            )
            provider_summary = self._provider_summary(
                runtime,
                provenance_ids,
                logical_operations,
                transport_attempts,
            )
            tracker.finish(
                current,
                f"acquired {len(acquisitions)} minimum provider operation payloads",
                evidence_ids=provenance_ids,
            )

            current = PipelineStage.DATA_CLEANING
            tracker.start(current)
            replay = AcquiredReplayProvider(runtime.provider, product_resolution.result)
            replay_registry = ProviderRegistry()
            replay_registry.register(
                replay,
                ProviderConfig(
                    provider_id=replay.provider_id,
                    enabled=True,
                    priority=1,
                    credential_env=None,
                    timeout_seconds=1.0,
                    max_attempts=1,
                ),
            )
            clean_result = DataCleaningService(
                replay_registry, CanonicalNormalizationPipeline.with_defaults()
            ).clean(
                DataCleaningRequest(
                    provider_id=replay.provider_id,
                    operation="asin_info",
                    parameters={
                        "entities": [
                            {"country": request.marketplace, "asin": asin}
                            for asin in request.asins
                        ]
                    },
                    marketplace=request.marketplace,
                    locale=str(runtime.metadata["locale"]),
                    retrieved_at=timestamps["retrieved_at"],
                    transformed_at=timestamps["transformed_at"],
                    collection_run_id=f"{data_run_id}:asin-info",
                    normalization_run_id=f"{data_run_id}:normalization",
                    normalized_at=timestamps["transformed_at"],
                    currency=str(runtime.metadata["currency"]),
                )
            )
            tracker.finish(
                current,
                f"canonical cleaning completed with status {clean_result.status.value}",
                partial=clean_result.status.value != "SUCCESS",
                evidence_ids=clean_result.raw_evidence_references,
            )

            current = PipelineStage.CATEGORY_COMPETITION
            tracker.start(current)
            competition = CompetitionAnalysisBuilderV0_1().build(
                CompetitionAnalysisRequest(
                    marketplace=request.marketplace,
                    clean_results=(clean_result,),
                )
            )
            market_analysis = MarketAnalysisBuilderV0_1().build(
                MarketAnalysisRequest(
                    marketplace=request.marketplace,
                    clean_results=(clean_result,),
                )
            )
            profiles = tuple(
                AttributeExtractionPipeline().extract(
                    ProductIntelligenceBuilderV0_1().build(
                        ProductIntelligenceRequest(
                            target_product_identity=ProductIdentity(
                                product_id=product_id(request.marketplace, asin),
                                marketplace=request.marketplace,
                                asin=asin,
                                parent_asin=None,
                                identity_status="CONFIRMED",
                            ),
                            scope=ProductScope.EXACT_PRODUCT,
                            canonical_bundles=(product_resolution.result.adaptation.bundle,),
                        )
                    )
                )
                for asin in request.asins
            )
            category_map = CategoryProductMapBuilderV0_1().build(
                CategoryProductMapRequest(
                    category_scope=build_category_scope(
                        scope_type=CategoryScopeType.INPUT_COHORT,
                        scope_value=deterministic_id(
                            "production-category-cohort",
                            {"marketplace": request.marketplace, "asins": request.asins},
                        ),
                        inclusion_rule="All explicit marketplace-matching ASINs in the operator cohort.",
                    ),
                    marketplace=request.marketplace,
                    analysis_window=unknown_analysis_window(),
                    product_grain=ProductGrain.CHILD_ASIN,
                    product_profiles=profiles,
                    combination_dimensions=(),
                )
            )
            category_partial = competition.status.value != "COMPLETE"
            if category_partial:
                warnings.add(f"competition analysis status is {competition.status.value}")
            tracker.finish(
                current,
                "category map and competition inputs built through public builders",
                partial=category_partial,
                evidence_ids=(category_map.map_id, competition.analysis_id),
            )

            current = PipelineStage.BUYER_NEED
            tracker.start(current)
            buyer_output = self._build_buyer_need_output(
                acquisitions[1:], request.asins
            )
            tracker.finish(
                current,
                "Buyer Need V0.3 intent and stable semantic clustering completed",
                evidence_ids=(str(buyer_output["analysis_id"]),),
            )

            current = PipelineStage.OPPORTUNITY
            tracker.start(current)
            competition_intelligence = CompetitionIntelligenceBuilderV0_1().build(
                CompetitionIntelligenceRequest(canonical_bundles=bundles)
            )
            opportunity_intelligence = OpportunityIntelligenceBuilderV0_1().build(
                OpportunityIntelligenceRequest(canonical_bundles=bundles)
            )
            opportunity_score = self._score_available_opportunity_evidence(
                request=request,
                category_map_id=category_map.map_id,
                opportunity_snapshot=opportunity_intelligence,
            )
            if opportunity_score.score_value is None:
                unavailable.add("numeric opportunity score: candidate metric adapter not available")
            tracker.finish(
                current,
                "opportunity intelligence and governed scoring path executed",
                partial=opportunity_score.score_value is None,
                evidence_ids=(
                    competition_intelligence.snapshot_id,
                    opportunity_intelligence.snapshot_id,
                    opportunity_score.score_id,
                ),
            )

            current = PipelineStage.MARKET_REPORT
            tracker.start(current)
            category_name = request.category_name or str(runtime.metadata["category_name"])
            source_report = MarketReportBuilderV0_1().build(
                MarketReportBuildRequest(
                    category_name=category_name,
                    marketplace=request.marketplace,
                    category_scope=str(runtime.metadata["category_scope"]),
                    sample_size=len(request.asins),
                    unique_asin_count=len(request.asins),
                    provider_total=resolved_count,
                    data_window_period="fixture_snapshot" if request.mode is ProductionRunMode.FIXTURE else "live_snapshot",
                    data_window_start=None,
                    data_window_end=None,
                    generated_at=timestamps["generated_at"],
                    pipeline_version=PRODUCTION_PIPELINE_VERSION,
                    source_record_id=deterministic_id(
                        "production-run-source",
                        {"marketplace": request.marketplace, "asins": request.asins},
                    ),
                    source_evidence_ids=tuple(
                        sorted(
                            {
                                *provenance_ids,
                                clean_result.run_id,
                                category_map.map_id,
                                competition.analysis_id,
                                str(buyer_output["analysis_id"]),
                                opportunity_score.score_id,
                            }
                        )
                    ),
                    buyer_need_output=buyer_output,
                    competition_output=competition,
                    market_analysis_output=market_analysis,
                    category_product_map_output=category_map,
                    opportunity_score_output=opportunity_score,
                    limitations=tuple(sorted({*warnings, *unavailable})),
                )
            )
            if request.report_version == MARKET_REPORT_VERSION:
                report = source_report
                MarketReportBuilderV0_1().write_json(report, layout.market_report)
                report_id = report.report_id
            else:
                report = ProductionMarketReportV0_2Adapter().adapt(
                    source_report,
                    operational_metadata={
                        "run_id": run_id,
                        "mode": request.mode.value,
                        "provider_id": request.provider_preference,
                        "request_fingerprint": request_fingerprint,
                    },
                )
                write_json_atomic(layout.market_report, report.to_dict())
                report_id = report.metadata.report_id
            produced_report_id = report_id
            tracker.finish(
                current,
                f"{request.report_version} JSON built and written",
                evidence_ids=(report_id,),
            )

            current = PipelineStage.SCHEMA_VALIDATION
            tracker.start(current)
            serialized = json.loads(layout.market_report.read_text(encoding="utf-8"))
            validated = (
                self._report_validator(serialized)
                if request.report_version == MARKET_REPORT_VERSION
                else market_report_v0_2_from_dict(serialized)
            )
            validated_report_id = (
                validated.report_id
                if request.report_version == MARKET_REPORT_VERSION
                else validated.metadata.report_id
            )
            tracker.finish(
                current,
                "serialized market_report.json validated before delivery",
                evidence_ids=(validated_report_id,),
            )

            current = PipelineStage.DELIVERY
            tracker.start(current)
            recovery_evidence = self._recovery_evidence(
                request_fingerprint,
                checkpoint_store,
                resume_set,
                logical_operations,
            )
            workflow = None
            if request.report_version == MARKET_REPORT_VERSION:
                workflow = OperatorWorkflowBuilderV0_1().build(
                    OperatorWorkflowRequest(
                        report=validated,
                        run_id=run_id,
                        run_status=ProductionRunStatus.SUCCEEDED.value,
                        provider_summary=(provider_summary.to_dict() if provider_summary is not None else None),
                        recovery=recovery_evidence,
                    )
                )
                delivered = self._delivery.deliver(
                    validated, layout.output_directory, operator_workflow=workflow,
                )
                delivery_evidence = (
                    workflow.snapshot_id, delivered.xlsx_sha256, delivered.markdown_sha256,
                )
            else:
                delivered = self._delivery_v0_2.deliver(validated, layout.output_directory)
                delivery_evidence = (
                    delivered.xlsx_sha256,
                    delivered.xlsx_package_content_sha256,
                    delivered.markdown_sha256,
                )
            delivery_status = "SUCCEEDED"
            tracker.finish(
                current,
                "XLSX and Markdown delivered from the same validated report snapshot",
                evidence_ids=delivery_evidence,
            )

            current = PipelineStage.MANIFEST
            tracker.start(current)
            tracker.finish(current, "run manifest written last")
            result = ProductionRunResult(
                run_id=run_id,
                status=ProductionRunStatus.SUCCEEDED,
                requested_asin_count=len(request.asins),
                resolved_asin_count=resolved_count,
                stages=tracker.records(),
                artifact_paths=self._artifact_paths(layout, include_all=True),
                market_report_version=request.report_version,
                provider_summary=provider_summary,
                warnings=tuple(sorted(warnings)),
                unavailable_evidence=tuple(sorted(unavailable)),
                recovery=recovery_evidence,
                operator_workflow=workflow.to_dict() if workflow is not None else None,
                requested_market_report_version=(
                    request.report_version if request.report_version != MARKET_REPORT_VERSION else None
                ),
                market_report_id=(
                    produced_report_id if request.report_version != MARKET_REPORT_VERSION else None
                ),
                delivery_status=(
                    delivery_status if request.report_version != MARKET_REPORT_VERSION else None
                ),
            )
            write_json_atomic(layout.manifest, result.to_dict())
            return result
        except Exception as exc:
            error = self._typed_error(exc, current)
            tracker.fail(current, error)
            tracker.skip_remaining()
            output_conflict = (
                error.code is ProductionPipelineErrorCode.OUTPUT_ARTIFACT_CONFLICT
            )
            if output_conflict:
                tracker.skip(
                    PipelineStage.MANIFEST,
                    "not written because the output directory is owned by an earlier run",
                )
            else:
                tracker.start(PipelineStage.MANIFEST)
                tracker.finish(PipelineStage.MANIFEST, "failure manifest written last")
            if runtime is not None and provider_summary is None:
                provider_summary = self._provider_summary(
                    runtime,
                    tuple(sorted(provenance_seen)),
                    logical_operations,
                    transport_attempts,
                )
            result = ProductionRunResult(
                run_id=run_id,
                status=ProductionRunStatus.FAILED,
                requested_asin_count=len(request.asins),
                resolved_asin_count=resolved_count,
                stages=tracker.records(),
                artifact_paths=(
                    {} if output_conflict else self._artifact_paths(layout, include_all=False)
                ),
                market_report_version=request.report_version,
                provider_summary=provider_summary,
                warnings=tuple(sorted(warnings)),
                unavailable_evidence=tuple(sorted(unavailable)),
                error=error.to_dict(),
                recovery=self._recovery_evidence(
                    request_fingerprint,
                    checkpoint_store,
                    resume_set,
                    logical_operations,
                ),
                requested_market_report_version=(
                    request.report_version if request.report_version != MARKET_REPORT_VERSION else None
                ),
                market_report_id=(
                    produced_report_id if request.report_version != MARKET_REPORT_VERSION else None
                ),
                delivery_status=(
                    "FAILED" if request.report_version != MARKET_REPORT_VERSION else None
                ),
            )
            if not output_conflict:
                write_json_atomic(layout.manifest, result.to_dict())
            return result

    @staticmethod
    def _validate_operator_request(request: ProductionRunRequest) -> None:
        if request.seed_keyword is not None:
            raise UnsupportedCapabilityError(
                "seed-keyword cohort discovery is unsupported in SP-034; provide explicit ASINs"
            )
        if request.provider_preference != "xiyou":
            raise UnsupportedCapabilityError(
                "SP-034 production orchestration currently supports provider preference 'xiyou'"
            )
        if request.provider_config_reference != "environment":
            raise UnsupportedCapabilityError(
                "SP-034 accepts only the credential-safe 'environment' provider config reference"
            )
        if request.mode is ProductionRunMode.LIVE and request.category_name is None:
            raise UnsupportedCapabilityError(
                "live mode requires an explicit category_name; category inference is not validated"
            )
        if request.category_name is not None and request.category_name.strip().casefold() != "dog water bottle":
            raise UnsupportedCapabilityError(
                "SP-034 Buyer Need V0.3 orchestration is validated only for the dog water bottle scope"
            )

    @staticmethod
    def _default_provider_runtime(request: ProductionRunRequest) -> ProviderRuntime:
        if request.mode is ProductionRunMode.FIXTURE:
            metadata = json.loads(_FIXTURE.read_text(encoding="utf-8"))
            fixture_asins = {
                item["asin"]
                for item in metadata["operations"]["asin_info"]["payload"]["entities"]
            }
            if not set(request.asins) <= fixture_asins:
                raise UnsupportedCapabilityError(
                    "fixture mode supports only the checked-in dog-water-bottle ASIN cohort"
                )
            transport = RecordingTransport(FixtureTransport(metadata))
            environment = {"AMAZON_INTEL_OFFLINE_FIXTURE_KEY": "offline-fixture-sentinel"}
            credential_env = "AMAZON_INTEL_OFFLINE_FIXTURE_KEY"
            credit_semantics = ProviderCreditSemantics.FIXTURE_REFERENCE
        else:
            base_url = os.environ.get("XIYOU_API_BASE_URL")
            if not base_url:
                raise ProductionPipelineError(
                    ProductionPipelineErrorCode.INVALID_INPUT,
                    "XIYOU_API_BASE_URL is required for live mode",
                    stage=PipelineStage.INPUT_VALIDATION.value,
                )
            if not os.environ.get("XIYOU_API_KEY"):
                raise ProductionPipelineError(
                    ProductionPipelineErrorCode.INVALID_INPUT,
                    "XIYOU_API_KEY is required for live mode",
                    stage=PipelineStage.INPUT_VALIDATION.value,
                )
            transport = RecordingTransport(HttpJsonTransport({"xiyou": base_url}))
            environment = os.environ
            credential_env = "XIYOU_API_KEY"
            credit_semantics = ProviderCreditSemantics.LIVE_PROVIDER_REPORTED
            now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            metadata = {
                "locale": "en-us",
                "currency": "USD",
                "retrieved_at": now,
                "transformed_at": now,
                "generated_at": now,
                "category_name": request.category_name,
                "category_scope": f"Amazon {request.marketplace} > {request.category_name}",
            }
        provider = XiYouProvider(
            transport,
            environment=environment,
            retry_policy=(
                NoRetryPolicy()
                if request.mode is ProductionRunMode.FIXTURE
                else BoundedTransientRetryPolicy()
            ),
        )
        registry = ProviderRegistry()
        registry.register(
            provider,
            ProviderConfig(
                provider_id="xiyou",
                enabled=True,
                priority=1,
                credential_env=credential_env,
                timeout_seconds=15.0,
                max_attempts=(1 if request.mode is ProductionRunMode.FIXTURE else 2),
            ),
        )
        return ProviderRuntime(
            registry=registry,
            provider=provider,
            recording_transport=transport,
            metadata=metadata,
            credit_semantics=credit_semantics,
        )

    @staticmethod
    def _timestamps(
        request: ProductionRunRequest, metadata: Mapping[str, Any]
    ) -> dict[str, str]:
        return {
            key: str(metadata[key])
            for key in ("retrieved_at", "transformed_at", "generated_at")
        }

    @staticmethod
    def _build_buyer_need_output(
        acquisitions: list[Any], asins: tuple[str, ...]
    ) -> dict[str, Any]:
        keywords: dict[str, Any] = {}
        keyword_asins: dict[str, set[str]] = {}
        for acquired in acquisitions:
            for observation in acquired.adaptation.bundle.observations:
                if not isinstance(observation, ProductKeywordRelationshipObservation):
                    continue
                keywords[observation.keyword.keyword_id] = observation.keyword
                keyword_asins.setdefault(observation.keyword.keyword_id, set()).add(
                    observation.product.asin
                )
        pipeline = BuyerNeedAnalysisPipelineV0_3(
            query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
        )
        results = tuple(
            pipeline.analyze(build_search_term_text_evidence(keywords[key]))
            for key in sorted(keywords)
        )
        needs = tuple(
            need for result in results for need in result.semantic_cluster_inputs
        )
        clusters = SemanticClusterBuilder().build(needs)
        need_asins: dict[str, set[str]] = {}
        for result in results:
            keyword = result.intent_evidence.source_evidence.source_reference.keyword_identity
            source_asins = keyword_asins.get(keyword.keyword_id, set()) if keyword else set()
            for need in result.semantic_cluster_inputs:
                need_asins.setdefault(need.need_id, set()).update(source_asins)
        rows = []
        for cluster in clusters.clusters:
            source = set().union(
                *(need_asins.get(need_id, set()) for need_id in cluster.source_need_ids)
            )
            rows.append(
                {
                    "cluster_id": cluster.cluster_id,
                    "cluster_label": cluster.cluster_label,
                    "need_count": len(cluster.source_need_ids),
                    "source_asin_count": len(source),
                    "asin_coverage": str(Decimal(len(source)) / Decimal(len(asins))),
                    "source_need_ids": list(cluster.source_need_ids),
                }
            )
        if not rows:
            raise ProductionPipelineError(
                ProductionPipelineErrorCode.INTELLIGENCE_FAILURE,
                "Buyer Need V0.3 produced no eligible semantic clusters",
                stage=PipelineStage.BUYER_NEED.value,
            )
        material = {
            "intent_result_ids": tuple(item.result_id for item in results),
            "semantic_clustering_result_id": clusters.result_id,
            "semantic_clusters": rows,
        }
        return {
            "analysis_id": deterministic_id("production-buyer-need-analysis", material),
            "final_decision": {
                "code": "A",
                "label": "V0.3_STABLE",
                "reason": "SP-034 executed frozen V0.3 intent and V0.2 taxonomy boundaries.",
            },
            "semantic_clusters": rows,
        }

    @staticmethod
    def _score_available_opportunity_evidence(
        *,
        request: ProductionRunRequest,
        category_map_id: str,
        opportunity_snapshot: Any,
    ) -> Any:
        evidence_id = opportunity_snapshot.snapshot_id
        reference = OpportunityScoreEvidenceReference(
            reference_id=deterministic_id(
                "opportunity-score-source-reference", {"source_id": evidence_id}
            ),
            source="opportunity_intelligence",
            source_id=evidence_id,
            record_ids=(evidence_id,),
            missing=False,
            limitations=("CANDIDATE_METRIC_ADAPTER_UNAVAILABLE_IN_SP_034",),
        )
        metrics = tuple(sorted((
            OpportunityScoringMetricInput(
                metric_id=metric_id,
                dimension=dimension,
                value=None,
                status=OpportunityScoreMetricStatus.UNKNOWN,
                source_evidence_ids=(evidence_id,),
                source_reference_ids=(reference.reference_id,),
                limitations=("SOURCE_METRIC_UNAVAILABLE",),
            )
            for dimension, metric_ids in EXPECTED_METRICS.items()
            for metric_id in metric_ids
        ), key=lambda item: item.metric_id))
        material = {
            "candidate_id": deterministic_id(
                "production-opportunity-candidate",
                {"marketplace": request.marketplace, "asins": request.asins},
            ),
            "category_scope": {"category_map_id": category_map_id},
            "candidate_confidence": OpportunityConfidence.UNKNOWN,
            "metrics": metrics,
            "evidence_ids": (evidence_id,),
            "source_references": (reference,),
            "limitations": ("CANDIDATE_METRIC_ADAPTER_UNAVAILABLE_IN_SP_034",),
            "integration_version": "opportunity-scoring-integration-v0.1",
        }
        scoring_input = OpportunityScoringIntegrationInput(
            input_id=deterministic_id("opportunity-score-input", material),
            **material,
        )
        policy = OpportunityScorePolicyLoader().load(
            _SCORE_POLICY,
            policy_version="opportunity-score-policy-v0.1",
        )
        return EvidenceBasedOpportunityScorerV0_1().score(scoring_input, policy)

    @staticmethod
    def _resolve_operation(
        *,
        runtime: ProviderRuntime,
        resolver: ProviderResolver,
        provider_request: ProviderRequest,
        operation: str,
        checkpoint_store: CheckpointStore,
        resume_set: ResumeCheckpointSet | None,
        logical_operations: list[ProviderLogicalOperationSummary],
        transport_attempts: list[ProviderTransportAttemptSummary],
    ) -> Any:
        operation_id = logical_operation_id(operation, provider_request)
        checkpoint = (
            resume_set.find(operation, provider_request)
            if resume_set is not None
            else None
        )
        if checkpoint is not None:
            replay_transport = CheckpointReplayTransport(checkpoint)
            replay_provider = XiYouProvider(
                replay_transport,
                environment={"CHECKPOINT_REPLAY_SENTINEL": "offline-only"},
                retry_policy=NoRetryPolicy(),
            )
            replay_registry = ProviderRegistry()
            replay_registry.register(
                replay_provider,
                ProviderConfig(
                    provider_id="xiyou",
                    enabled=True,
                    priority=1,
                    credential_env="CHECKPOINT_REPLAY_SENTINEL",
                    timeout_seconds=1.0,
                    max_attempts=1,
                ),
            )
            replay_request = checkpoint.replay_request(provider_request)
            resolution = ProviderResolver(replay_registry).resolve(replay_request)
            raw_evidence = resolution.result.adaptation.raw_evidence
            if (
                replay_transport.execute_count != 1
                or raw_evidence is None
                or raw_evidence.raw_evidence_id
                != checkpoint.payload["provenance_raw_evidence_id"]
            ):
                raise ProductionPipelineError(
                    ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
                    "checkpoint replay did not reproduce its audited provenance identity",
                    stage=PipelineStage.ACQUISITION.value,
                )
            copied = checkpoint_store.write_success(
                operation=operation,
                request=replay_request,
                response=checkpoint.response,
                provenance_id=raw_evidence.raw_evidence_id,
                replayed_from=checkpoint.checkpoint_id,
            )
            logical_operations.append(
                ProviderLogicalOperationSummary(
                    logical_operation_id=operation_id,
                    operation=operation,
                    canonical_field=provider_request.canonical_field,
                    execution_source=ProviderOperationExecutionSource.CHECKPOINT_REPLAY,
                    status="SUCCEEDED",
                    transport_attempt_count=0,
                    checkpoint_id=copied.checkpoint_id,
                )
            )
            return resolution

        before = len(runtime.recording_transport.attempt_records)
        try:
            resolution = resolver.resolve(provider_request)
        except Exception as exc:
            records = runtime.recording_transport.attempt_records[before:]
            ProductionPipelineOrchestrator._record_transport_attempts(
                operation_id,
                operation,
                records,
                transport_attempts,
            )
            logical_operations.append(
                ProviderLogicalOperationSummary(
                    logical_operation_id=operation_id,
                    operation=operation,
                    canonical_field=provider_request.canonical_field,
                    execution_source=ProviderOperationExecutionSource.NEW_PROVIDER,
                    status="FAILED",
                    transport_attempt_count=len(records),
                )
            )
            transient = {
                ProviderErrorCode.NETWORK.value,
                ProviderErrorCode.TIMEOUT.value,
                ProviderErrorCode.PROVIDER_UNAVAILABLE.value,
            }
            if (
                len(records) >= 2
                and records[-1].provider_error_code in transient
                and all(item.provider_error_code in transient for item in records)
            ):
                raise ProductionPipelineError(
                    ProductionPipelineErrorCode.BOUNDED_RETRY_EXHAUSTED,
                    "transient provider failure exhausted the bounded attempt limit",
                    stage=PipelineStage.ACQUISITION.value,
                    details={
                        "operation": operation,
                        "transport_attempt_count": len(records),
                        "final_provider_error_code": records[-1].provider_error_code,
                    },
                ) from exc
            raise

        records = runtime.recording_transport.attempt_records[before:]
        ProductionPipelineOrchestrator._record_transport_attempts(
            operation_id,
            operation,
            records,
            transport_attempts,
        )
        raw_evidence = resolution.result.adaptation.raw_evidence
        successful_response = next(
            (
                item.response
                for item in reversed(records)
                if item.status == "SUCCEEDED" and item.response is not None
            ),
            None,
        )
        if raw_evidence is None or successful_response is None:
            raise ProductionPipelineError(
                ProductionPipelineErrorCode.INTERNAL_FAILURE,
                "successful provider operation lacked checkpointable audited evidence",
                stage=PipelineStage.ACQUISITION.value,
            )
        checkpoint = checkpoint_store.write_success(
            operation=operation,
            request=provider_request,
            response=successful_response,
            provenance_id=raw_evidence.raw_evidence_id,
        )
        logical_operations.append(
            ProviderLogicalOperationSummary(
                logical_operation_id=operation_id,
                operation=operation,
                canonical_field=provider_request.canonical_field,
                execution_source=ProviderOperationExecutionSource.NEW_PROVIDER,
                status="SUCCEEDED",
                transport_attempt_count=len(records),
                checkpoint_id=checkpoint.checkpoint_id,
            )
        )
        return resolution

    @staticmethod
    def _record_transport_attempts(
        operation_id: str,
        operation: str,
        records: list[Any],
        destination: list[ProviderTransportAttemptSummary],
    ) -> None:
        for ordinal, record in enumerate(records, 1):
            destination.append(
                ProviderTransportAttemptSummary(
                    logical_operation_id=operation_id,
                    operation=operation,
                    attempt_ordinal=ordinal,
                    status=(
                        ProviderTransportAttemptStatus.SUCCEEDED
                        if record.status == "SUCCEEDED"
                        else ProviderTransportAttemptStatus.FAILED
                    ),
                    provider_error_code=record.provider_error_code,
                    credits=record.credits,
                )
            )

    @staticmethod
    def _recovery_evidence(
        request_fingerprint: str,
        checkpoint_store: CheckpointStore,
        resume_set: ResumeCheckpointSet | None,
        logical_operations: list[ProviderLogicalOperationSummary],
    ) -> dict[str, Any]:
        replayed_source_ids = tuple(
            sorted(
                checkpoint.checkpoint_id
                for checkpoint in (resume_set.checkpoints.values() if resume_set else ())
            )
        )
        return {
            "contract_version": RECOVERY_CONTRACT_VERSION,
            "request_fingerprint": request_fingerprint,
            "checkpoint_contract_version": "production-provider-checkpoint-v0.1",
            "checkpoint_directory": "checkpoints",
            "checkpoint_ids": list(checkpoint_store.checkpoint_ids),
            "checkpoint_count": len(checkpoint_store.checkpoint_ids),
            "resume_source_run_id": resume_set.source_run_id if resume_set else None,
            "resume_source_checkpoint_ids": list(replayed_source_ids),
            "executed_operation_count": sum(
                item.execution_source is ProviderOperationExecutionSource.NEW_PROVIDER
                for item in logical_operations
            ),
            "replayed_operation_count": sum(
                item.execution_source is ProviderOperationExecutionSource.CHECKPOINT_REPLAY
                for item in logical_operations
            ),
        }

    @staticmethod
    def _provider_summary(
        runtime: ProviderRuntime,
        provenance_ids: tuple[str, ...],
        logical_operations: list[ProviderLogicalOperationSummary],
        transport_attempts: list[ProviderTransportAttemptSummary],
    ) -> ProviderOperationSummary:
        recording = runtime.recording_transport
        return ProviderOperationSummary(
            provider_id=runtime.provider.provider_id,
            operations=tuple(item.operation for item in logical_operations),
            operation_count=len(logical_operations),
            credits=recording.credits,
            credit_semantics=runtime.credit_semantics,
            provenance_ids=tuple(sorted(provenance_ids)),
            transport_attempt_count=len(transport_attempts),
            executed_operation_count=sum(
                item.execution_source is ProviderOperationExecutionSource.NEW_PROVIDER
                for item in logical_operations
            ),
            replayed_operation_count=sum(
                item.execution_source is ProviderOperationExecutionSource.CHECKPOINT_REPLAY
                for item in logical_operations
            ),
            logical_operations=tuple(logical_operations),
            transport_attempts=tuple(transport_attempts),
        )

    @staticmethod
    def _artifact_paths(
        layout: RunArtifactLayout, *, include_all: bool
    ) -> dict[str, str]:
        paths = {
            "market_report_json": str(layout.market_report.resolve()),
            "operator_xlsx": str(layout.operator_xlsx.resolve()),
            "operator_markdown": str(layout.operator_markdown.resolve()),
            "run_manifest": str(layout.manifest.resolve()),
        }
        if include_all:
            return paths
        return {
            name: value
            for name, value in paths.items()
            if name == "run_manifest" or Path(value).is_file()
        }

    @staticmethod
    def _typed_error(exc: Exception, stage: PipelineStage) -> ProductionPipelineError:
        if isinstance(exc, ProductionPipelineError):
            return exc
        if isinstance(exc, ProviderConnectorError):
            details: dict[str, Any] = {
                "provider_error_code": exc.code.value,
                "provider_id": exc.provider_id,
                "operation": exc.operation,
                "retryable": exc.retryable,
            }
            resolver_attempts = ProductionPipelineOrchestrator._safe_resolver_attempts(
                exc
            )
            if resolver_attempts:
                details["resolver_attempts"] = resolver_attempts
            return ProductionPipelineError(
                ProductionPipelineErrorCode.PROVIDER_FAILURE,
                "provider acquisition failed",
                stage=stage.value,
                details=details,
            )
        if stage is PipelineStage.SCHEMA_VALIDATION:
            code = ProductionPipelineErrorCode.SCHEMA_VALIDATION_FAILURE
            message = "serialized Market Report schema validation failed"
        elif stage is PipelineStage.DELIVERY:
            code = ProductionPipelineErrorCode.DELIVERY_FAILURE
            message = "operator report delivery failed"
        elif stage in {
            PipelineStage.CATEGORY_COMPETITION,
            PipelineStage.BUYER_NEED,
            PipelineStage.OPPORTUNITY,
            PipelineStage.MARKET_REPORT,
        }:
            code = ProductionPipelineErrorCode.INTELLIGENCE_FAILURE
            message = "intelligence composition failed"
        else:
            code = ProductionPipelineErrorCode.INTERNAL_FAILURE
            message = "production pipeline failed"
        return ProductionPipelineError(
            code,
            message,
            stage=stage.value,
            details={"exception_type": type(exc).__name__},
        )

    @staticmethod
    def _safe_resolver_attempts(
        error: ProviderConnectorError,
    ) -> list[dict[str, str | None]]:
        raw_attempts = error.details.get("attempts")
        if not isinstance(raw_attempts, (list, tuple)):
            return []
        safe: list[dict[str, str | None]] = []
        for attempt in raw_attempts:
            if not isinstance(attempt, Mapping):
                continue
            provider_id = attempt.get("provider_id")
            status = attempt.get("status")
            error_code = attempt.get("error_code")
            if provider_id != "xiyou":
                continue
            if status not in _SAFE_RESOLVER_ATTEMPT_STATUSES:
                continue
            if error_code is not None and error_code not in _SAFE_PROVIDER_ERROR_CODES:
                continue
            safe.append(
                {
                    "provider_id": "xiyou",
                    "status": str(status),
                    "error_code": str(error_code) if error_code is not None else None,
                }
            )
        return safe


__all__ = ("ProductionPipelineOrchestrator", "ProviderRuntime", "ProviderRuntimeFactory")
