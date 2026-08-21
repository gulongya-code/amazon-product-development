"""Read-only XiYou execution path for TASK-SP-031.

The runner composes the repository's existing modules.  It deliberately owns no
analysis rule, taxonomy, gap threshold, or score weight.  Provider payloads stay
in memory and only compact validation facts are emitted.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from amazon_product_intelligence.buyer_need_analysis import (
    BUYER_NEED_RULESET_VERSION,
    BuyerNeedCandidateBuilder,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.buyer_need_map import (
    BUYER_NEED_MAP_RULESET_VERSION,
    BuyerNeedMapBuilderV0_1,
    BuyerNeedMapRequest,
    DemandMetricStatus,
    DemandMetricType,
    EvidencePopulationStatus,
)
from amazon_product_intelligence.category_product_map import (
    CATEGORY_PRODUCT_MAP_VERSION,
    CategoryProductMapBuilderV0_1,
    CategoryProductMapRequest,
    CategoryScopeType,
    build_category_scope,
    unknown_analysis_window,
)
from amazon_product_intelligence.competition_intelligence import (
    COMPETITION_INTELLIGENCE_RULESET_VERSION,
    CompetitionIntelligenceBuilderV0_1,
    CompetitionIntelligenceRequest,
)
from amazon_product_intelligence.connectors import (
    HttpJsonTransport,
    ProviderConfig,
    ProviderConnectorError,
    ProviderCredential,
    ProviderErrorCode,
    ProviderRegistry,
    ProviderRequest,
    TransportRequest,
    TransportResponse,
    XIYOU_OPERATIONS,
    XiYouProvider,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    KeywordMetricObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.data_cleaning import (
    CleanCanonicalResult,
    DataCleaningRequest,
    DataCleaningService,
)
from amazon_product_intelligence.demand_intelligence import (
    DEMAND_INTELLIGENCE_RULESET_VERSION,
    DemandIntelligenceBuilderV0_1,
    DemandIntelligenceRequest,
    KeywordMetricEvidenceSet,
)
from amazon_product_intelligence.market_analysis import (
    MARKET_ANALYSIS_VERSION,
    MarketAnalysisBuilderV0_1,
    MarketAnalysisRequest,
)
from amazon_product_intelligence.normalization import CanonicalNormalizationPipeline
from amazon_product_intelligence.opportunity_intelligence.integration_v0_1 import (
    OPPORTUNITY_INTELLIGENCE_INTEGRATION_RULESET_VERSION,
    OpportunityCandidateBuilderV0_1,
    OpportunityCandidateRequest,
)
from amazon_product_intelligence.opportunity_scoring.integration_v0_1 import (
    OPPORTUNITY_SCORING_INTEGRATION_VERSION,
    OpportunityScorePolicyLoader,
    OpportunityScoringIntegrationV0_1,
)
from amazon_product_intelligence.product_attribute_extraction import (
    ATTRIBUTE_RULES_ENGINE_VERSION,
    ATTRIBUTE_TAXONOMY_VERSION,
    AttributeDimension,
    AttributeExtractionPipeline,
    AttributeState,
    ProductGrain,
)
from amazon_product_intelligence.product_intelligence import (
    PRODUCT_INTELLIGENCE_RULESET_VERSION,
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)
from amazon_product_intelligence.semantic_clustering import (
    SEMANTIC_CLUSTERING_RULESET_VERSION,
    SemanticClusterBuilder,
)
from amazon_product_intelligence.supply_demand_gap import (
    SUPPLY_DEMAND_GAP_RULESET_VERSION,
    GapType,
    SupplyDemandGapBuilderV0_1,
    SupplyDemandGapRequest,
)

from .models import (
    REAL_DATA_VALIDATION_VERSION,
    AttributeAccuracyReport,
    AttributeDimensionAccuracy,
    ModuleVersion,
    ValidationAnalysisWindow,
    ValidationCategoryScope,
    ValidationDataSource,
    ValidationDiagnostic,
    ValidationIssueCategory,
    ValidationRunSnapshot,
    ValidationSeverity,
    build_stage_coverage,
    build_validation_issue,
    build_validation_issue_log,
    build_validation_run_snapshot,
    ratio_text,
)


DEFAULT_COHORT_QUERY = "dog water bottle"
DEFAULT_NEED_QUERIES = (
    "portable dog water bottle",
    "leakproof dog water bottle",
    "travel dog water bottle",
    "dog water bottle for walking",
    "hiking dog water bottle",
    "dog water bottle for large dogs",
    "dog water bottle for small dogs",
    "easy to clean dog water bottle",
    "spill proof dog water bottle",
    "large capacity dog water bottle",
    "easy to carry dog water bottle",
    "dog water bottle fits in backpack",
    "lightweight dog water bottle",
    "durable dog water bottle",
    "12 oz dog water bottle",
    "19 oz dog water bottle",
    "27 oz dog water bottle",
    "32 oz dog water bottle",
    "stainless steel dog water bottle",
    "compact size dog water bottle",
    "dog water bottle compatible with car cup holder",
    "dog water bottle works with stroller cup holder",
    "dog water bottle fits bicycle bottle cage",
)
ATTRIBUTE_AUDIT_DIMENSIONS = (
    AttributeDimension.MATERIAL,
    AttributeDimension.CAPACITY,
    AttributeDimension.SIZE,
    AttributeDimension.FEATURE,
    AttributeDimension.PACKAGE_QUANTITY,
)


class _CapturedPayloadTransport:
    def __init__(self, operation: str, payload: Any) -> None:
        self.operation = operation
        self.payload = payload

    def execute(self, request: TransportRequest) -> TransportResponse:
        if request.operation != self.operation:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                "captured validation payload does not cover this operation",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        return TransportResponse(status_code=200, payload=self.payload)


@dataclass(frozen=True, slots=True)
class _CapturedOperation:
    operation: str
    parameters: Mapping[str, Any]
    payload: Mapping[str, Any]
    metadata: Mapping[str, Any]
    bundle: CanonicalEvidenceBundle
    clean_result: CleanCanonicalResult


@dataclass(frozen=True, slots=True)
class RealDataPipelineResult:
    validation_run: ValidationRunSnapshot
    attribute_accuracy: AttributeAccuracyReport
    category_map_review: Mapping[str, Any]
    buyer_need_review: tuple[Mapping[str, Any], ...]
    gap_review: tuple[Mapping[str, Any], ...]
    opportunity_ranking_review: tuple[Mapping[str, Any], ...]
    provider_summary: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "validation_run": self.validation_run.to_dict(),
            "attribute_accuracy": self.attribute_accuracy.to_dict(),
            "category_map_review": dict(self.category_map_review),
            "buyer_need_review": [dict(item) for item in self.buyer_need_review],
            "gap_review": [dict(item) for item in self.gap_review],
            "opportunity_ranking_review": [
                dict(item) for item in self.opportunity_ranking_review
            ],
            "provider_summary": dict(self.provider_summary),
        }


class RealDataValidationPipelineV0_1:
    """Compose existing intelligence modules over one bounded live cohort."""

    def __init__(
        self,
        *,
        policy_path: str | Path,
        policy_version: str,
        cohort_size: int = 200,
        sample_size: int = 100,
        cohort_query: str = DEFAULT_COHORT_QUERY,
        need_queries: Sequence[str] = DEFAULT_NEED_QUERIES,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        if cohort_size < sample_size or sample_size <= 0:
            raise ValueError("cohort_size must be at least the positive sample_size")
        if cohort_size > 10_000:
            raise ValueError("cohort_size exceeds the audited provider request maximum")
        self.policy_path = Path(policy_path)
        self.policy_version = policy_version
        self.cohort_size = cohort_size
        self.sample_size = sample_size
        self.cohort_query = cohort_query
        self.need_queries = tuple(dict.fromkeys(need_queries))
        self.environment = os.environ if environment is None else environment
        self.retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        self._operation_index = {item.operation: item for item in XIYOU_OPERATIONS}
        self._http = HttpJsonTransport({"xiyou": "https://openapi.xydc.com"})

    def run(self) -> RealDataPipelineResult:
        forward = self._capture(
            operation="keyword_asin_analysis",
            canonical_field="relationship.keyword_to_product",
            parameters={
                "keyword": self.cohort_query,
                "searchTerm": self.cohort_query,
                "country": "US",
                "page": 1,
                "pageSize": self.cohort_size,
                "period": "last7days",
                "sort": {"field": "traffic", "order": "desc"},
            },
        )
        product_identities = self._cohort_products(forward.bundle)
        product_operations = tuple(
            self._capture(
                operation="asin_info",
                canonical_field="product.asin",
                parameters={
                    "entities": [
                        {"country": "US", "asin": item.asin}
                        for item in product_identities[offset : offset + 100]
                    ]
                },
            )
            for offset in range(0, len(product_identities), 100)
        )
        keyword_info = self._capture(
            operation="keyword_info",
            canonical_field="keyword.search_volume",
            parameters={
                "country": "US",
                "searchTerms": list(self.need_queries),
            },
        )

        title_by_asin = self._title_index(product_operations)
        bundle_by_asin = self._bundle_index(product_operations)
        product_snapshots = []
        product_failures: list[str] = []
        profiles = []
        attribute_failures: list[str] = []
        for identity in product_identities:
            bundle = bundle_by_asin.get(identity.asin)
            if bundle is None:
                product_failures.append(identity.asin)
                continue
            try:
                snapshot = ProductIntelligenceBuilderV0_1().build(
                    ProductIntelligenceRequest(
                        target_product_identity=identity,
                        scope=ProductScope.EXACT_PRODUCT,
                        canonical_bundles=(bundle,),
                    )
                )
                product_snapshots.append(snapshot)
            except Exception:
                product_failures.append(identity.asin)
                continue
            try:
                profiles.append(AttributeExtractionPipeline().extract(snapshot))
            except Exception:
                attribute_failures.append(identity.asin)

        category_scope = build_category_scope(
            scope_type=CategoryScopeType.INPUT_COHORT,
            scope_value="Amazon US > Pet Supplies > Dog Travel Water Bottles",
            inclusion_rule=(
                f"ASINs returned on page 1 for {self.cohort_query!r}, last7days, "
                "traffic descending; only successfully adapted product profiles are included."
            ),
        )
        analysis_window = unknown_analysis_window()
        category_map = CategoryProductMapBuilderV0_1().build(
            CategoryProductMapRequest(
                category_scope=category_scope,
                marketplace="US",
                analysis_window=analysis_window,
                product_grain=ProductGrain.CHILD_ASIN,
                product_profiles=tuple(profiles),
                combination_dimensions=(
                    (AttributeDimension.MATERIAL, AttributeDimension.CAPACITY),
                    (AttributeDimension.CAPACITY, AttributeDimension.FEATURE),
                    (AttributeDimension.FEATURE, AttributeDimension.PACKAGE_QUANTITY),
                ),
            )
        )

        keywords = self._keyword_identities(keyword_info.bundle)
        demand_snapshots = []
        search_sets: list[KeywordMetricEvidenceSet] = []
        buyer_needs = []
        buyer_need_keyword_count = 0
        for keyword in keywords:
            demand = DemandIntelligenceBuilderV0_1().build(
                DemandIntelligenceRequest(
                    target_keyword_identity=keyword,
                    canonical_bundles=(keyword_info.bundle,),
                )
            )
            demand_snapshots.append(demand)
            search_sets.extend(
                item
                for item in demand.keyword_metric_evidence_sets
                if item.metric == "search_volume"
            )
            keyword_needs = BuyerNeedCandidateBuilder().build(
                build_search_term_text_evidence(keyword)
            )
            buyer_needs.extend(keyword_needs)
            buyer_need_keyword_count += bool(keyword_needs)
        if not buyer_needs:
            raise RuntimeError("live keyword evidence produced no V0.1 Buyer Need candidates")
        clustering = SemanticClusterBuilder().build(tuple(buyer_needs))
        returned_terms = {item.normalized_text for item in keywords}
        requested_terms = {item.strip().casefold() for item in self.need_queries}
        search_population_status = (
            EvidencePopulationStatus.COMPLETE
            if returned_terms == requested_terms and len(search_sets) == len(keywords)
            else EvidencePopulationStatus.PARTIAL
            if keywords
            else EvidencePopulationStatus.UNKNOWN
        )
        buyer_need_map = BuyerNeedMapBuilderV0_1().build(
            BuyerNeedMapRequest(
                category_scope=category_scope,
                marketplace="US",
                analysis_window=analysis_window,
                buyer_need_evidence=tuple(buyer_needs),
                semantic_clusters=clustering.clusters,
                search_metric_evidence_sets=tuple(search_sets),
                category_product_map=category_map,
                search_population_status=search_population_status,
                review_population_status=EvidencePopulationStatus.UNKNOWN,
            )
        )
        gaps = tuple(
            SupplyDemandGapBuilderV0_1().build(
                SupplyDemandGapRequest(
                    buyer_need_map=buyer_need_map,
                    category_product_map=category_map,
                    need_cluster_id=cluster.cluster_id,
                    product_attribute_profiles=tuple(profiles),
                )
            )
            for cluster in buyer_need_map.need_clusters
        )

        all_bundles = (forward.bundle,) + tuple(
            item.bundle for item in product_operations
        ) + (keyword_info.bundle,)
        competition = CompetitionIntelligenceBuilderV0_1().build(
            CompetitionIntelligenceRequest(canonical_bundles=all_bundles)
        )
        market_analysis = MarketAnalysisBuilderV0_1().build(
            MarketAnalysisRequest(
                marketplace="US",
                clean_results=tuple(item.clean_result for item in product_operations),
            )
        )
        candidates = tuple(
            OpportunityCandidateBuilderV0_1().build(
                OpportunityCandidateRequest(
                    buyer_need_map=buyer_need_map,
                    category_product_map=category_map,
                    supply_demand_gap=gap,
                    competition_intelligence=competition,
                    product_attribute_profiles=tuple(profiles),
                    market_analysis=market_analysis,
                )
            )
            for gap in gaps
        )
        policy = OpportunityScorePolicyLoader().load(
            self.policy_path,
            policy_version=self.policy_version,
        )
        scorer = OpportunityScoringIntegrationV0_1()
        scores = tuple(scorer.score_candidate(candidate, policy) for candidate in candidates)
        repeat_scores = tuple(
            scorer.score_candidate(candidate, policy) for candidate in candidates
        )
        if tuple(canonical_json(item) for item in scores) != tuple(
            canonical_json(item) for item in repeat_scores
        ):
            raise RuntimeError("Opportunity Score output is not deterministic")

        attribute_report = self._attribute_accuracy_report(
            profiles=tuple(profiles),
            title_by_asin=title_by_asin,
        )
        issues = self._issues(
            forward=forward,
            category_map=category_map,
            keyword_count=len(keywords),
            requested_keyword_count=len(self.need_queries),
            title_count=len(title_by_asin),
        )
        issue_log = build_validation_issue_log(issues)
        coverage = self._coverage(
            cohort_count=len(product_identities),
            product_count=len(product_snapshots),
            product_failures=len(product_failures),
            profiles=tuple(profiles),
            attribute_failures=len(attribute_failures),
            category_count=len(category_map.included_products),
            keywords=keywords,
            buyer_need_count=len(buyer_needs),
            buyer_need_keyword_count=buyer_need_keyword_count,
            cluster_count=len(clustering.clusters),
            buyer_need_map=buyer_need_map,
            gaps=gaps,
            candidates=candidates,
            scores=scores,
            competition=competition,
            market_analysis=market_analysis,
        )
        diagnostics = (
            ValidationDiagnostic(
                code="DETERMINISTIC_SCORE_REPLAY_MATCHED",
                severity=ValidationSeverity.INFO,
                stage="Opportunity Score",
                message=f"All {len(scores)} Candidate scores matched on immediate replay.",
                related_ids=tuple(item.score_id for item in scores),
            ),
            ValidationDiagnostic(
                code="ATTRIBUTE_AUDIT_IS_TITLE_CONCORDANCE",
                severity=ValidationSeverity.WARNING,
                stage="Attribute Extraction",
                message=(
                    "The 100-ASIN audit checks extraction/source-title concordance; the provider "
                    "does not expose independent structured attributes for ground-truth comparison."
                ),
            ),
        )
        validation_run = build_validation_run_snapshot(
            category_scope=ValidationCategoryScope(
                category="Pet Supplies",
                subcategory="Dog Travel Water Bottles",
                cohort_query=self.cohort_query,
                inclusion_rule=category_scope.inclusion_rule,
            ),
            marketplace="US",
            analysis_window=ValidationAnalysisWindow(
                period_label="last7days",
                period_start=None,
                period_end=None,
                retrieved_at=self.retrieved_at,
            ),
            data_source=(
                ValidationDataSource(
                    provider="XiYou OpenAPI V2",
                    operation="keyword_asin_analysis",
                    source_reference="POST /v1/searchTerms/analysis/list/period",
                    live_request=True,
                ),
                ValidationDataSource(
                    provider="XiYou OpenAPI V2",
                    operation="asin_info",
                    source_reference="POST /v1/asins/info",
                    live_request=True,
                ),
                ValidationDataSource(
                    provider="XiYou OpenAPI V2",
                    operation="keyword_info",
                    source_reference="POST /v1/searchTerms/info",
                    live_request=True,
                ),
            ),
            pipeline_version="product-intelligence-pipeline-validation-v0.1",
            module_versions=self._module_versions(),
            coverage=coverage,
            limitations=(
                "Cohort is a traffic-ranked keyword result page, not a complete Amazon browse-node census.",
                "XiYou asin_info exposes title, price, rating, and review count but no bullets, review text, brand, or structured attributes.",
                "Attribute audit is source-title concordance, not independent catalog ground truth.",
                "Review mention demand, brand concentration, sales, and revenue remain UNKNOWN.",
                "Provider traffic method and exact period semantics are unconfirmed by the canonical adapter.",
                "No scoring, extraction, taxonomy, gap, opportunity, or Foundation policy was changed during validation.",
            ),
            diagnostics=diagnostics,
            issue_log=issue_log,
        )
        category_review = self._category_review(category_map, market_analysis)
        buyer_review = self._buyer_review(buyer_need_map)
        gap_review = self._gap_review(gaps, buyer_need_map)
        ranking_review = self._ranking_review(
            scores, candidates, gaps, buyer_need_map
        )
        provider_summary = {
            "cohort_requested": self.cohort_size,
            "cohort_returned": len(product_identities),
            "provider_total": forward.payload.get("total"),
            "product_rows_returned": len(title_by_asin),
            "need_queries_requested": len(self.need_queries),
            "need_queries_returned": len(keywords),
            "request_count": 2 + len(product_operations),
            "cost_credits": sum(
                self._credit_value(item.metadata.get("cost_credits"))
                for item in (forward, *product_operations, keyword_info)
            ),
            "trace_ids": sorted(
                str(value)
                for item in (forward, *product_operations, keyword_info)
                if (value := item.metadata.get("trace_id"))
            ),
        }
        return RealDataPipelineResult(
            validation_run=validation_run,
            attribute_accuracy=attribute_report,
            category_map_review=category_review,
            buyer_need_review=buyer_review,
            gap_review=gap_review,
            opportunity_ranking_review=ranking_review,
            provider_summary=provider_summary,
        )

    def _capture(
        self,
        *,
        operation: str,
        canonical_field: str,
        parameters: Mapping[str, Any],
    ) -> _CapturedOperation:
        api_key = self.environment.get("XIYOU_API_KEY")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ProviderConnectorError(
                ProviderErrorCode.CONFIGURATION,
                "XIYOU_API_KEY is required for an explicit live validation run",
                provider_id="xiyou",
                operation=operation,
            )
        contract = self._operation_index[operation]
        response = self._http.execute(
            TransportRequest(
                provider_id="xiyou",
                operation=operation,
                method=contract.method,
                endpoint=contract.endpoint,
                parameters=parameters,
                timeout_seconds=30.0,
                public_headers=contract.public_headers,
                credential=ProviderCredential(
                    environment_variable="XIYOU_API_KEY",
                    injection_name="X-Api-Key",
                    value=api_key,
                ),
            )
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                f"provider returned HTTP {response.status_code}",
                provider_id="xiyou",
                operation=operation,
            )
        if not isinstance(response.payload, Mapping):
            raise ProviderConnectorError(
                ProviderErrorCode.BAD_RESPONSE,
                "provider response root is not an object",
                provider_id="xiyou",
                operation=operation,
            )
        payload = dict(response.payload)
        static_transport = _CapturedPayloadTransport(operation, payload)
        fixture_environment = {"XIYOU_API_KEY": "captured-payload-only"}
        provider = XiYouProvider(static_transport, environment=fixture_environment)
        configuration = ProviderConfig(
            provider_id="xiyou",
            enabled=True,
            priority=1,
            credential_env="XIYOU_API_KEY",
            timeout_seconds=1.0,
            max_attempts=1,
        )
        collection_run_id = deterministic_id(
            "collection",
            {
                "provider": "xiyou",
                "operation": operation,
                "parameters": parameters,
                "retrieved_at": self.retrieved_at,
            },
        )
        provider_request = ProviderRequest(
            canonical_field=canonical_field,
            parameters=parameters,
            marketplace="US",
            locale="en-us",
            retrieved_at=self.retrieved_at,
            transformed_at=self.retrieved_at,
            collection_run_id=collection_run_id,
            currency="USD",
        )
        fetched = provider.fetch(provider_request, configuration)
        registry = ProviderRegistry()
        registry.register(provider, configuration)
        normalization_run_id = deterministic_id(
            "normalization",
            {
                "collection_run_id": collection_run_id,
                "version": "canonical-normalization-v0.1",
            },
        )
        clean_result = DataCleaningService(
            registry,
            CanonicalNormalizationPipeline.with_defaults(),
        ).clean(
            DataCleaningRequest(
                provider_id="xiyou",
                operation=operation,
                parameters=parameters,
                marketplace="US",
                locale="en-us",
                retrieved_at=self.retrieved_at,
                transformed_at=self.retrieved_at,
                collection_run_id=collection_run_id,
                normalization_run_id=normalization_run_id,
                normalized_at=self.retrieved_at,
                currency="USD",
            )
        )
        return _CapturedOperation(
            operation=operation,
            parameters=dict(parameters),
            payload=payload,
            metadata=dict(response.metadata),
            bundle=fetched.adaptation.bundle.validate(),
            clean_result=clean_result,
        )

    @staticmethod
    def _cohort_products(bundle: CanonicalEvidenceBundle) -> tuple[ProductIdentity, ...]:
        products = {
            observation.product.product_id: observation.product
            for observation in bundle.observations
            if isinstance(observation, ProductKeywordRelationshipObservation)
        }
        return tuple(sorted(products.values(), key=lambda item: item.asin))

    @staticmethod
    def _title_index(operations: Sequence[_CapturedOperation]) -> dict[str, str]:
        index: dict[str, str] = {}
        for operation in operations:
            rows = operation.payload.get("entities", [])
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, Mapping):
                    continue
                asin = row.get("asin")
                title = row.get("title")
                if isinstance(asin, str) and isinstance(title, str) and title.strip():
                    index[asin] = title
        return index

    @staticmethod
    def _bundle_index(
        operations: Sequence[_CapturedOperation],
    ) -> dict[str, CanonicalEvidenceBundle]:
        index: dict[str, CanonicalEvidenceBundle] = {}
        for operation in operations:
            rows = operation.payload.get("entities", [])
            if not isinstance(rows, list):
                continue
            for row in rows:
                if isinstance(row, Mapping) and isinstance(row.get("asin"), str):
                    index[str(row["asin"])] = operation.bundle
        return index

    @staticmethod
    def _keyword_identities(bundle: CanonicalEvidenceBundle) -> tuple[Any, ...]:
        keywords = {
            observation.keyword.keyword_id: observation.keyword
            for observation in bundle.observations
            if isinstance(observation, KeywordMetricObservation)
        }
        return tuple(sorted(keywords.values(), key=lambda item: item.normalized_text))

    def _attribute_accuracy_report(
        self,
        *,
        profiles: tuple[Any, ...],
        title_by_asin: Mapping[str, str],
    ) -> AttributeAccuracyReport:
        population = tuple(sorted(profiles, key=lambda item: item.product_identity.asin))
        seed = int.from_bytes(
            sha256(b"TASK-SP-031:attribute-sample:v0.1").digest()[:8], "big"
        )
        sample = tuple(
            sorted(
                random.Random(seed).sample(population, self.sample_size),
                key=lambda item: item.product_identity.asin,
            )
        )
        dimension_results = []
        for dimension in ATTRIBUTE_AUDIT_DIMENSIONS:
            correct = 0
            error = 0
            unknown = 0
            for profile in sample:
                title = title_by_asin.get(profile.product_identity.asin, "")
                slot = next(item for item in profile.attributes if item.dimension is dimension)
                if slot.state is not AttributeState.PRESENT:
                    unknown += 1
                    continue
                raw_values = [
                    str(assertion.raw_value).strip().casefold()
                    for assertion in slot.assertions
                    if assertion.raw_value is not None
                ]
                if title and any(value and value in title.casefold() for value in raw_values):
                    correct += 1
                else:
                    error += 1
            known = correct + error
            dimension_results.append(
                AttributeDimensionAccuracy(
                    dimension=dimension.value,
                    correct_count=correct,
                    error_count=error,
                    unknown_count=unknown,
                    sample_count=len(sample),
                    accuracy=ratio_text(correct, known),
                    known_coverage=ratio_text(known, len(sample)),
                )
            )
        material = {
            "sample_size": len(sample),
            "population_size": len(population),
            "sampling_method": "Deterministic PRNG sample; SHA-256 seed TASK-SP-031:attribute-sample:v0.1",
            "evidence_basis": "Confirmed extractor assertion must be textually concordant with the live XiYou product title.",
            "dimensions": tuple(sorted(dimension_results, key=lambda item: item.dimension)),
            "limitations": tuple(sorted((
                "XiYou asin_info has no independent structured Material/Capacity/Size/Feature/Package Quantity ground truth.",
                "UNKNOWN means the title did not provide a resolvable value; it is not scored as an error.",
                "This report validates rule/source concordance, not complete catalog truth.",
            ))),
            "version": REAL_DATA_VALIDATION_VERSION,
        }
        return AttributeAccuracyReport(
            report_id=deterministic_id("attribute-accuracy-report", material),
            **material,
        )

    @staticmethod
    def _module_versions() -> tuple[ModuleVersion, ...]:
        versions = {
            "product_intelligence": PRODUCT_INTELLIGENCE_RULESET_VERSION,
            "attribute_extraction": ATTRIBUTE_RULES_ENGINE_VERSION,
            "attribute_taxonomy": ATTRIBUTE_TAXONOMY_VERSION,
            "category_product_map": CATEGORY_PRODUCT_MAP_VERSION,
            "buyer_need_analysis": BUYER_NEED_RULESET_VERSION,
            "demand_intelligence": DEMAND_INTELLIGENCE_RULESET_VERSION,
            "semantic_clustering": SEMANTIC_CLUSTERING_RULESET_VERSION,
            "buyer_need_map": BUYER_NEED_MAP_RULESET_VERSION,
            "supply_demand_gap": SUPPLY_DEMAND_GAP_RULESET_VERSION,
            "competition_intelligence": COMPETITION_INTELLIGENCE_RULESET_VERSION,
            "market_analysis": MARKET_ANALYSIS_VERSION,
            "opportunity_intelligence": OPPORTUNITY_INTELLIGENCE_INTEGRATION_RULESET_VERSION,
            "opportunity_scoring": OPPORTUNITY_SCORING_INTEGRATION_VERSION,
        }
        return tuple(
            ModuleVersion(module=module, version=version)
            for module, version in sorted(versions.items())
        )

    @staticmethod
    def _issues(
        *,
        forward: _CapturedOperation,
        category_map: Any,
        keyword_count: int,
        requested_keyword_count: int,
        title_count: int,
    ) -> tuple[Any, ...]:
        return (
            build_validation_issue(
                category=ValidationIssueCategory.OTHER,
                severity=ValidationSeverity.WARNING,
                title="XiYou forward request identity uses two equivalent fields",
                problem=(
                    "The live endpoint requires searchTerm while the audited adapter requires "
                    "sanitized_request.keyword for canonical relationship identity."
                ),
                affected_modules=("connectors", "data_cleaning"),
                recommended_fix=(
                    "Add a versioned request adapter that maps canonical keyword to provider "
                    "searchTerm while preserving canonical request context."
                ),
                evidence_references=(
                    "POST /v1/searchTerms/analysis/list/period",
                    forward.bundle.raw_evidence_references[0],
                ),
            ),
            build_validation_issue(
                category=ValidationIssueCategory.DATA_QUALITY,
                severity=ValidationSeverity.ERROR,
                title="Product detail source lacks bullets, reviews, brand, and structured attributes",
                problem=(
                    f"The live cohort has {title_count} titles, but the provider contract supplies "
                    "no review text, bullet text, brand identity, or structured catalog attributes."
                ),
                affected_modules=(
                    "product_intelligence",
                    "attribute_extraction",
                    "buyer_need_map",
                    "competition_intelligence",
                ),
                recommended_fix=(
                    "Add an audited provider source for bullets, review text, brand, and structured "
                    "attributes before calibration; do not infer absent facts."
                ),
            ),
            build_validation_issue(
                category=ValidationIssueCategory.DATA_QUALITY,
                severity=ValidationSeverity.WARNING,
                title="Traffic evidence method and exact period are unconfirmed",
                problem=(
                    "The canonical adapter preserves forward traffic but marks method, unit, and exact "
                    "period semantics unconfirmed."
                ),
                affected_modules=("demand_intelligence", "competition_intelligence"),
                recommended_fix="Obtain provider method documentation before treating traffic as a calibrated demand metric.",
                evidence_references=tuple(forward.bundle.raw_evidence_references),
            ),
            build_validation_issue(
                category=ValidationIssueCategory.DATA_QUALITY,
                severity=ValidationSeverity.WARNING,
                title="Keyword cohort is not a browse-node census",
                problem=(
                    "The category scope is operationally approximated by one traffic-ranked keyword "
                    "result set and can omit relevant products or include adjacent products."
                ),
                affected_modules=("category_product_map", "supply_demand_gap", "opportunity_intelligence"),
                recommended_fix="Validate against an audited Amazon browse-node or category inventory source in the next run.",
            ),
            build_validation_issue(
                category=ValidationIssueCategory.DEMAND_MODEL,
                severity=(
                    ValidationSeverity.WARNING
                    if keyword_count == requested_keyword_count
                    else ValidationSeverity.ERROR
                ),
                title="Demand validation has no Review or Bullet population",
                problem=(
                    f"Search-term coverage is {keyword_count}/{requested_keyword_count}; review and "
                    "bullet evidence populations are unavailable and remain UNKNOWN."
                ),
                affected_modules=("buyer_need_analysis", "buyer_need_map", "supply_demand_gap"),
                recommended_fix="Collect audited review and bullet evidence, then re-run without changing the taxonomy during validation.",
            ),
            build_validation_issue(
                category=ValidationIssueCategory.COMPETITION,
                severity=ValidationSeverity.WARNING,
                title="Brand concentration cannot be calculated",
                problem="The provider source has no canonical brand or seller identity for the cohort.",
                affected_modules=("competition_intelligence", "opportunity_scoring"),
                recommended_fix="Add canonical brand identity evidence and preserve UNKNOWN until it is available.",
            ),
            build_validation_issue(
                category=ValidationIssueCategory.SCORING,
                severity=ValidationSeverity.WARNING,
                title="Sales and revenue evidence are unavailable",
                problem=(
                    "Observed product price is available, but sales and revenue availability inputs "
                    "remain UNKNOWN and are excluded rather than filled with zero."
                ),
                affected_modules=("market_analysis", "opportunity_scoring"),
                recommended_fix="Add audited sales/revenue evidence in a later data-source task; do not change score policy in this validation task.",
            ),
            build_validation_issue(
                category=ValidationIssueCategory.OTHER,
                severity=ValidationSeverity.INFO,
                title="Category Product Map has no native price-band dimension",
                problem=(
                    f"The Category Product Map exposes {len(category_map.attribute_distributions)} "
                    "attribute distributions but price is reviewed through Market Analysis."
                ),
                affected_modules=("category_product_map", "market_analysis"),
                recommended_fix="Decide contract ownership for price bands before any future implementation task.",
            ),
        )

    @staticmethod
    def _coverage(
        *,
        cohort_count: int,
        product_count: int,
        product_failures: int,
        profiles: tuple[Any, ...],
        attribute_failures: int,
        category_count: int,
        keywords: tuple[Any, ...],
        buyer_need_count: int,
        buyer_need_keyword_count: int,
        cluster_count: int,
        buyer_need_map: Any,
        gaps: tuple[Any, ...],
        candidates: tuple[Any, ...],
        scores: tuple[Any, ...],
        competition: Any,
        market_analysis: Any,
    ) -> tuple[Any, ...]:
        requested_attribute_slots = len(profiles) * len(ATTRIBUTE_AUDIT_DIMENSIONS)
        known_attribute_slots = sum(
            next(item for item in profile.attributes if item.dimension is dimension).state
            is AttributeState.PRESENT
            for profile in profiles
            for dimension in ATTRIBUTE_AUDIT_DIMENSIONS
        )
        unknown_demand_clusters = len(
            {
                metric.cluster_id
                for metric in buyer_need_map.demand_metrics
                if metric.metric_type is DemandMetricType.SEARCH_DEMAND_SHARE
                and metric.status is DemandMetricStatus.UNKNOWN
            }
        )
        unknown_gaps = sum(item.gap_type is GapType.INSUFFICIENT_EVIDENCE for item in gaps)
        pending_scores = sum(item.score_value is None for item in scores)
        competition_unknown = 2
        price = market_analysis.numeric_metric("market_analysis.observed_product_price")
        economic_unknown = 2 if price.distribution is not None else 3
        return (
            build_stage_coverage(
                stage="Data Input",
                input_count=cohort_count,
                output_count=cohort_count,
                failure_count=0,
                unknown_count=0,
            ),
            build_stage_coverage(
                stage="Canonical Evidence",
                input_count=cohort_count,
                output_count=product_count,
                failure_count=product_failures,
                unknown_count=max(0, cohort_count - product_count - product_failures),
            ),
            build_stage_coverage(
                stage="Product Intelligence",
                input_count=cohort_count,
                output_count=product_count,
                failure_count=product_failures,
                unknown_count=max(0, cohort_count - product_count - product_failures),
            ),
            build_stage_coverage(
                stage="Attribute Extraction",
                input_count=requested_attribute_slots,
                output_count=known_attribute_slots,
                failure_count=attribute_failures,
                unknown_count=requested_attribute_slots - known_attribute_slots,
                covered_count=known_attribute_slots,
                notes=("Counts are requested Material/Capacity/Size/Feature/Package Quantity slots.",),
            ),
            build_stage_coverage(
                stage="Category Product Map",
                input_count=len(profiles),
                output_count=category_count,
                failure_count=max(0, len(profiles) - category_count),
                unknown_count=0,
            ),
            build_stage_coverage(
                stage="Buyer Need Evidence",
                input_count=len(keywords),
                output_count=buyer_need_keyword_count,
                failure_count=0,
                unknown_count=len(keywords) - buyer_need_keyword_count,
                covered_count=buyer_need_keyword_count,
                notes=(f"{buyer_need_count} Buyer Need candidates were emitted from search terms.",),
            ),
            build_stage_coverage(
                stage="Semantic Clustering",
                input_count=buyer_need_count,
                output_count=cluster_count,
                failure_count=0,
                unknown_count=0,
                covered_count=buyer_need_count,
                notes=("Output count is intentionally lower when equivalent needs cluster.",),
            ),
            build_stage_coverage(
                stage="Buyer Need Map",
                input_count=cluster_count,
                output_count=cluster_count,
                failure_count=0,
                unknown_count=unknown_demand_clusters,
                covered_count=cluster_count - unknown_demand_clusters,
            ),
            build_stage_coverage(
                stage="Supply Demand Gap",
                input_count=cluster_count,
                output_count=len(gaps),
                failure_count=0,
                unknown_count=unknown_gaps,
                covered_count=len(gaps) - unknown_gaps,
            ),
            build_stage_coverage(
                stage="Competition Intelligence",
                input_count=3,
                output_count=1,
                failure_count=0,
                unknown_count=competition_unknown,
                covered_count=1,
                notes=("Coverage units are market concentration, brand concentration, and review barrier.",),
            ),
            build_stage_coverage(
                stage="Economic Evidence",
                input_count=3,
                output_count=3 - economic_unknown,
                failure_count=0,
                unknown_count=economic_unknown,
                covered_count=3 - economic_unknown,
                notes=("Coverage units are observed price, sales availability, and revenue availability.",),
            ),
            build_stage_coverage(
                stage="Opportunity Intelligence",
                input_count=len(gaps),
                output_count=len(candidates),
                failure_count=max(0, len(gaps) - len(candidates)),
                unknown_count=0,
            ),
            build_stage_coverage(
                stage="Opportunity Score",
                input_count=len(candidates),
                output_count=len(scores),
                failure_count=max(0, len(candidates) - len(scores)),
                unknown_count=pending_scores,
                covered_count=len(scores) - pending_scores,
            ),
        )

    @staticmethod
    def _category_review(category_map: Any, market_analysis: Any) -> Mapping[str, Any]:
        distributions: dict[str, Any] = {}
        for distribution in category_map.attribute_distributions:
            if distribution.dimension not in ATTRIBUTE_AUDIT_DIMENSIONS:
                continue
            values = sorted(
                (
                    {
                        "value": item.canonical_value.display_value,
                        "asin_count": item.asin_count,
                        "asin_share": item.asin_share,
                    }
                    for item in distribution.values
                ),
                key=lambda item: (-item["asin_count"], item["value"]),
            )
            distributions[distribution.dimension.value] = {
                "known": distribution.known_value_count,
                "unknown": distribution.unknown_count,
                "coverage": distribution.attribute_coverage,
                "top_values": values[:10],
            }
        price = market_analysis.numeric_metric("market_analysis.observed_product_price")
        return {
            "judgement": "PARTIAL",
            "included_products": len(category_map.included_products),
            "attribute_distributions": distributions,
            "combination_segment_count": len(category_map.combination_segments),
            "top_combination_segments": [
                {
                    "label": " + ".join(
                        value.display_value for value in item.canonical_values
                    ),
                    "asin_count": item.asin_count,
                    "asin_share": item.asin_share,
                }
                for item in sorted(
                    category_map.combination_segments,
                    key=lambda item: (
                        -item.asin_count,
                        tuple(value.display_value for value in item.canonical_values),
                    ),
                )[:10]
            ],
            "price_band": (
                None if price.distribution is None else price.distribution.to_dict()
            ),
            "price_band_source": "Market Analysis observed product price; Category Product Map has no native price dimension.",
            "reason": "Bottle capacities/features are plausible where title evidence exists, but UNKNOWN rates are high and category membership is keyword-defined.",
        }

    @staticmethod
    def _buyer_review(buyer_need_map: Any) -> tuple[Mapping[str, Any], ...]:
        demand_by_cluster = {
            metric.cluster_id: metric
            for metric in buyer_need_map.demand_metrics
            if metric.metric_type is DemandMetricType.SEARCH_DEMAND_SHARE
        }
        rows = []
        for cluster in buyer_need_map.need_clusters:
            metric = demand_by_cluster[cluster.cluster_id]
            rows.append(
                {
                    "cluster_id": cluster.cluster_id,
                    "cluster_label": cluster.cluster_label,
                    "search_demand_share": metric.share,
                    "demand_status": metric.status.value,
                    "confidence": metric.confidence.level.value,
                    "sources": ["Search Term"],
                    "review_source_available": False,
                    "bullet_source_available": False,
                    "judgement": "POSSIBLE" if metric.share is not None else "INSUFFICIENT_DATA",
                    "reason": "Explicit live Search Term evidence; no Review or Bullet population for triangulation.",
                }
            )
        return tuple(
            sorted(
                rows,
                key=lambda item: (
                    -(float(item["search_demand_share"]) if item["search_demand_share"] else -1.0),
                    item["cluster_label"],
                ),
            )
        )

    @staticmethod
    def _gap_review(gaps: tuple[Any, ...], buyer_need_map: Any) -> tuple[Mapping[str, Any], ...]:
        label_by_id = {
            item.cluster_id: item.cluster_label for item in buyer_need_map.need_clusters
        }
        rows = []
        for gap in gaps:
            judgement = (
                "INSUFFICIENT_DATA"
                if gap.gap_type is GapType.INSUFFICIENT_EVIDENCE
                else "VALID_GAP"
                if gap.gap_type is GapType.HIGH_DEMAND_LOW_SUPPLY
                else "FALSE_GAP"
            )
            rows.append(
                {
                    "gap_id": gap.gap_id,
                    "cluster_label": label_by_id[gap.need_cluster_id],
                    "gap_type": gap.gap_type.value,
                    "gap_strength": gap.gap_strength.value,
                    "confidence": gap.confidence.level.value,
                    "judgement": judgement,
                    "reason": (
                        "Demand and linked supply metrics are evidence-backed."
                        if judgement == "VALID_GAP"
                        else "Demand or linked canonical supply evidence is incomplete; no zero was substituted."
                        if judgement == "INSUFFICIENT_DATA"
                        else "The evidence-backed classification does not show high demand with low supply."
                    ),
                }
            )
        return tuple(
            sorted(
                rows,
                key=lambda item: (
                    item["judgement"] == "INSUFFICIENT_DATA",
                    item["cluster_label"],
                ),
            )
        )

    @staticmethod
    def _ranking_review(
        scores: tuple[Any, ...],
        candidates: tuple[Any, ...],
        gaps: tuple[Any, ...],
        buyer_need_map: Any,
    ) -> tuple[Mapping[str, Any], ...]:
        candidate_by_id = {item.candidate_id: item for item in candidates}
        gap_by_id = {item.gap_id: item for item in gaps}
        label_by_id = {
            item.cluster_id: item.cluster_label for item in buyer_need_map.need_clusters
        }
        ordered = sorted(
            scores,
            key=lambda item: (
                item.score_value is None,
                -(item.score_value or 0.0),
                item.candidate_id,
            ),
        )
        rows = []
        for rank, score in enumerate(ordered[:20], start=1):
            candidate = candidate_by_id[score.candidate_id]
            gap = gap_by_id[candidate.gap_reference.source_id]
            judgement = (
                "STRONG"
                if score.score_value is not None
                and score.score_value >= 75
                and score.confidence.value in {"HIGH", "MEDIUM"}
                and gap.gap_type is GapType.HIGH_DEMAND_LOW_SUPPLY
                else "POSSIBLE"
                if score.score_value is not None
                and score.score_value >= 50
                and gap.gap_type is GapType.HIGH_DEMAND_LOW_SUPPLY
                else "WEAK"
            )
            rows.append(
                {
                    "rank": rank,
                    "candidate_id": candidate.candidate_id,
                    "candidate": label_by_id[gap.need_cluster_id],
                    "score": score.score_value,
                    "score_status": score.score_status.value,
                    "confidence": score.confidence.value,
                    "candidate_status": candidate.status.value,
                    "gap_type": gap.gap_type.value,
                    "judgement": judgement,
                    "reason": "; ".join(score.explanation.risks[:3])
                    or "No explicit score risk was emitted.",
                    "policy_version": score.policy_version,
                    "evidence_reference_count": len(score.explanation.evidence_references),
                }
            )
        return tuple(rows)

    @staticmethod
    def _credit_value(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="real-data-validation-v0.1")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--policy", required=True, type=Path)
    parser.add_argument("--policy-version", default="opportunity-score-policy-v0.1")
    parser.add_argument("--cohort-size", type=int, default=200)
    parser.add_argument("--sample-size", type=int, default=100)
    parser.add_argument("--output", choices=("summary", "json"), default="summary")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--baseline-commit")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.live:
        raise SystemExit("--live is required; this runner never performs an implicit provider request")
    result = RealDataValidationPipelineV0_1(
        policy_path=args.policy,
        policy_version=args.policy_version,
        cohort_size=args.cohort_size,
        sample_size=args.sample_size,
    ).run()
    if args.report is not None:
        if not args.baseline_commit:
            raise SystemExit("--baseline-commit is required with --report")
        from .report import render_validation_report

        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            render_validation_report(result, baseline_commit=args.baseline_commit),
            encoding="utf-8",
        )
    payload = result.to_dict()
    if args.output == "summary":
        payload = {
            "run_id": result.validation_run.run_id,
            "category_scope": result.validation_run.category_scope.to_dict(),
            "marketplace": result.validation_run.marketplace,
            "analysis_window": result.validation_run.analysis_window.to_dict(),
            "provider_summary": dict(result.provider_summary),
            "coverage": [item.to_dict() for item in result.validation_run.coverage],
            "attribute_accuracy": result.attribute_accuracy.to_dict(),
            "category_map_review": dict(result.category_map_review),
            "buyer_need_review": [dict(item) for item in result.buyer_need_review[:20]],
            "gap_review": [dict(item) for item in result.gap_review[:20]],
            "opportunity_ranking_review": [
                dict(item) for item in result.opportunity_ranking_review
            ],
            "issues": [item.to_dict() for item in result.validation_run.issue_log.issues],
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def main() -> None:
    raise SystemExit(run())


__all__ = (
    "DEFAULT_COHORT_QUERY",
    "DEFAULT_NEED_QUERIES",
    "RealDataPipelineResult",
    "RealDataValidationPipelineV0_1",
    "main",
    "run",
)
