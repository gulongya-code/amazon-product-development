"""Evidence-backed Buyer Need Map and Demand Measurement builder V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedEvidence,
    BuyerNeedTextSourceType,
)
from amazon_product_intelligence.category_product_map import (
    AnalysisWindow,
    AnalysisWindowStatus,
    AttributeDistribution,
    CategoryMapSourceEvidence,
    CategoryProductMapSnapshot,
)
from amazon_product_intelligence.contracts import PresenceStatus, Severity, deterministic_id
from amazon_product_intelligence.demand_intelligence import (
    KeywordMetricEvidenceSet,
    MetricCandidateState,
)
from amazon_product_intelligence.semantic_clustering import SemanticClusterSnapshot

from .errors import BuyerNeedMapValidationError
from .models import (
    BUYER_NEED_MAP_RULESET_VERSION,
    BuyerNeedClusterSummary,
    BuyerNeedMapCoverage,
    BuyerNeedMapDiagnostic,
    BuyerNeedMapEvidenceType,
    BuyerNeedMapRequest,
    BuyerNeedMapSnapshot,
    BuyerNeedMapSourceEvidence,
    BuyerNeedRelatedAttribute,
    DemandDenominator,
    DemandDenominatorStatus,
    DemandMetricConfidence,
    DemandMetricConfidenceLevel,
    DemandMetricDefinition,
    DemandMetricRegistry,
    DemandMetricResult,
    DemandMetricStatus,
    DemandMetricType,
    EvidencePopulationStatus,
    decimal_text,
    demand_share_text,
)
from .registry import (
    DEMAND_METRIC_REGISTRY_V0_1,
    NEED_ATTRIBUTE_LINK_REGISTRY_V0_1,
    NeedAttributeLinkRegistry,
)


class BuyerNeedMapBuilderV0_1:
    """Measure evidence populations without producing opportunity judgments."""

    ruleset_version = BUYER_NEED_MAP_RULESET_VERSION

    def __init__(
        self,
        *,
        metric_registry: DemandMetricRegistry = DEMAND_METRIC_REGISTRY_V0_1,
        attribute_link_registry: NeedAttributeLinkRegistry = NEED_ATTRIBUTE_LINK_REGISTRY_V0_1,
    ) -> None:
        if not isinstance(metric_registry, DemandMetricRegistry):
            raise BuyerNeedMapValidationError("builder requires DemandMetricRegistry")
        if not isinstance(attribute_link_registry, NeedAttributeLinkRegistry):
            raise BuyerNeedMapValidationError("builder requires NeedAttributeLinkRegistry")
        self.metric_registry = metric_registry
        self.attribute_link_registry = attribute_link_registry
        self._definitions = {item.metric_type: item for item in metric_registry.definitions}

    def build(self, request: BuyerNeedMapRequest) -> BuyerNeedMapSnapshot:
        if not isinstance(request, BuyerNeedMapRequest):
            raise BuyerNeedMapValidationError("builder input must be BuyerNeedMapRequest")

        evidence_index: dict[str, BuyerNeedMapSourceEvidence] = {}
        cluster_refs = {
            cluster.cluster_id: self._add_evidence(
                evidence_index,
                BuyerNeedMapEvidenceType.SEMANTIC_CLUSTER,
                cluster,
            )
            for cluster in request.semantic_clusters
        }
        need_refs = {
            need.need_id: self._add_evidence(
                evidence_index,
                BuyerNeedMapEvidenceType.BUYER_NEED,
                need,
            )
            for need in request.buyer_need_evidence
        }
        search_refs = {
            evidence.metric_evidence_set_id: self._add_evidence(
                evidence_index,
                BuyerNeedMapEvidenceType.SEARCH_METRIC,
                evidence,
            )
            for evidence in request.search_metric_evidence_sets
        }
        category_map_ref = (
            self._add_evidence(
                evidence_index,
                BuyerNeedMapEvidenceType.CATEGORY_PRODUCT_MAP,
                request.category_product_map,
            )
            if request.category_product_map is not None
            else None
        )

        search_values, search_limitations = self._search_values(
            request.search_metric_evidence_sets
        )
        denominators = {
            DemandMetricType.SEARCH_DEMAND_SHARE: self._search_denominator(
                request=request,
                values=search_values,
                limitations=search_limitations,
                search_refs=search_refs,
            ),
            DemandMetricType.REVIEW_MENTION_SHARE: self._review_denominator(
                request=request,
                need_refs=need_refs,
            ),
            DemandMetricType.PRODUCT_COVERAGE_SHARE: self._product_denominator(
                request=request,
                category_map_ref=category_map_ref,
            ),
            DemandMetricType.SALES_ASSOCIATED_SHARE: self._unknown_denominator(
                request=request,
                metric_type=DemandMetricType.SALES_ASSOCIATED_SHARE,
                unit="sales_count",
                limitation="NO_EXPLICIT_CLUSTER_PRODUCT_SALES_ASSOCIATION_EVIDENCE",
            ),
            DemandMetricType.REVENUE_ASSOCIATED_SHARE: self._unknown_denominator(
                request=request,
                metric_type=DemandMetricType.REVENUE_ASSOCIATED_SHARE,
                unit="currency_amount",
                limitation="NO_EXPLICIT_CLUSTER_PRODUCT_REVENUE_ASSOCIATION_EVIDENCE",
            ),
        }

        summaries: list[BuyerNeedClusterSummary] = []
        metrics: list[DemandMetricResult] = []
        diagnostics: list[BuyerNeedMapDiagnostic] = []
        for cluster in request.semantic_clusters:
            search_metric = self._search_metric(
                request=request,
                cluster=cluster,
                denominator=denominators[DemandMetricType.SEARCH_DEMAND_SHARE],
                values=search_values,
                cluster_ref=cluster_refs[cluster.cluster_id],
                need_refs=need_refs,
                search_refs=search_refs,
            )
            review_metric = self._review_metric(
                request=request,
                cluster=cluster,
                denominator=denominators[DemandMetricType.REVIEW_MENTION_SHARE],
                cluster_ref=cluster_refs[cluster.cluster_id],
                need_refs=need_refs,
            )
            product_metric, related_attributes, related_products = self._product_metric(
                request=request,
                cluster=cluster,
                denominator=denominators[DemandMetricType.PRODUCT_COVERAGE_SHARE],
                cluster_ref=cluster_refs[cluster.cluster_id],
                need_refs=need_refs,
                category_map_ref=category_map_ref,
                evidence_index=evidence_index,
            )
            sales_metric = self._unknown_metric(
                cluster=cluster,
                definition=self._definitions[DemandMetricType.SALES_ASSOCIATED_SHARE],
                denominator=denominators[DemandMetricType.SALES_ASSOCIATED_SHARE],
                limitation="SALES_ASSOCIATION_NOT_IMPLEMENTED_WITHOUT_EXPLICIT_EVIDENCE",
                evidence_reference_ids=(cluster_refs[cluster.cluster_id],),
            )
            revenue_metric = self._unknown_metric(
                cluster=cluster,
                definition=self._definitions[DemandMetricType.REVENUE_ASSOCIATED_SHARE],
                denominator=denominators[DemandMetricType.REVENUE_ASSOCIATED_SHARE],
                limitation="REVENUE_ASSOCIATION_NOT_IMPLEMENTED_WITHOUT_EXPLICIT_EVIDENCE",
                evidence_reference_ids=(cluster_refs[cluster.cluster_id],),
            )
            cluster_metrics = (
                search_metric,
                review_metric,
                product_metric,
                sales_metric,
                revenue_metric,
            )
            metrics.extend(cluster_metrics)
            summary_evidence = {
                cluster_refs[cluster.cluster_id],
                *(need_refs[need_id] for need_id in cluster.source_need_ids),
                *(ref for item in related_attributes for ref in item.evidence_reference_ids),
            }
            distribution: dict[str, int] = {}
            for need in cluster.source_needs:
                distribution[need.need_type.value] = distribution.get(need.need_type.value, 0) + 1
            summaries.append(
                BuyerNeedClusterSummary(
                    cluster_id=cluster.cluster_id,
                    cluster_label=cluster.cluster_label,
                    need_ids=cluster.source_need_ids,
                    need_type_distribution=distribution,
                    related_attributes=related_attributes,
                    related_products=related_products,
                    evidence_count=cluster.evidence_count,
                    confidence=cluster.confidence,
                    evidence_reference_ids=tuple(sorted(summary_evidence)),
                )
            )
            diagnostics.extend(
                self._metric_diagnostic(cluster, metric)
                for metric in cluster_metrics
                if metric.status is DemandMetricStatus.UNKNOWN
            )

        ordered_metrics = tuple(sorted(metrics, key=lambda item: item.metric_result_id))
        ordered_summaries = tuple(sorted(summaries, key=lambda item: item.cluster_id))
        ordered_denominators = tuple(
            sorted(denominators.values(), key=lambda item: item.denominator_id)
        )
        source_evidence = tuple(
            sorted(evidence_index.values(), key=lambda item: item.evidence_reference_id)
        )
        ordered_diagnostics = tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id))
        coverage = BuyerNeedMapCoverage(
            cluster_count=len(ordered_summaries),
            buyer_need_count=len(
                {need_id for item in ordered_summaries for need_id in item.need_ids}
            ),
            metric_count=len(ordered_metrics),
            available_metric_count=sum(
                item.status is DemandMetricStatus.AVAILABLE for item in ordered_metrics
            ),
            partial_metric_count=sum(
                item.status is DemandMetricStatus.PARTIAL for item in ordered_metrics
            ),
            unknown_metric_count=sum(
                item.status is DemandMetricStatus.UNKNOWN for item in ordered_metrics
            ),
            metric_availability_rate=demand_share_text(
                sum(item.status is not DemandMetricStatus.UNKNOWN for item in ordered_metrics),
                len(ordered_metrics),
            )
            or "0",
            source_evidence_count=len(source_evidence),
            denominator_count=len(ordered_denominators),
        )
        payload = {
            "category_scope": request.category_scope,
            "marketplace": request.marketplace,
            "analysis_window": request.analysis_window,
            "need_clusters": ordered_summaries,
            "demand_metrics": ordered_metrics,
            "coverage": coverage,
            "denominator_registry": ordered_denominators,
            "source_evidence": source_evidence,
            "diagnostics": ordered_diagnostics,
            "metric_registry": self.metric_registry,
            "ruleset_version": self.ruleset_version,
        }
        return BuyerNeedMapSnapshot(
            map_id=deterministic_id("buyer-need-map", payload),
            **payload,
        )

    @staticmethod
    def _source_id(evidence_type: BuyerNeedMapEvidenceType, record: object) -> str:
        attributes = {
            BuyerNeedMapEvidenceType.BUYER_NEED: "need_id",
            BuyerNeedMapEvidenceType.SEMANTIC_CLUSTER: "cluster_id",
            BuyerNeedMapEvidenceType.SEARCH_METRIC: "metric_evidence_set_id",
            BuyerNeedMapEvidenceType.CATEGORY_PRODUCT_MAP: "map_id",
            BuyerNeedMapEvidenceType.PRODUCT_ATTRIBUTE: "evidence_reference_id",
        }
        return getattr(record, attributes[evidence_type])

    def _add_evidence(
        self,
        index: dict[str, BuyerNeedMapSourceEvidence],
        evidence_type: BuyerNeedMapEvidenceType,
        record: object,
    ) -> str:
        source_id = self._source_id(evidence_type, record)
        payload = {
            "evidence_type": evidence_type,
            "source_id": source_id,
            "source_record": record,
        }
        evidence = BuyerNeedMapSourceEvidence(
            evidence_reference_id=deterministic_id("buyer-need-map-evidence", payload),
            **payload,
        )
        index[evidence.evidence_reference_id] = evidence
        return evidence.evidence_reference_id

    @staticmethod
    def _search_values(
        evidence_sets: Sequence[KeywordMetricEvidenceSet],
    ) -> tuple[dict[tuple[str, str], tuple[int, KeywordMetricEvidenceSet]], tuple[str, ...]]:
        grouped: dict[tuple[str, str], list[KeywordMetricEvidenceSet]] = {}
        limitations: list[str] = []
        for evidence in evidence_sets:
            key = (evidence.keyword_identity.keyword_id, evidence.keyword_identity.raw_text)
            grouped.setdefault(key, []).append(evidence)
        values: dict[tuple[str, str], tuple[int, KeywordMetricEvidenceSet]] = {}
        for key, grouped_sets in sorted(grouped.items()):
            if len(grouped_sets) != 1:
                limitations.append(f"MULTIPLE_SEARCH_EVIDENCE_SETS_FOR_KEYWORD:{key[0]}")
                continue
            evidence = grouped_sets[0]
            if evidence.candidate_state is not MetricCandidateState.ONE_DISTINCT_PRESENT_VALUE:
                limitations.append(f"UNRESOLVED_SEARCH_VOLUME:{evidence.metric_evidence_set_id}")
                continue
            candidates = tuple(
                item
                for item in evidence.candidates
                if item.value.presence_status is PresenceStatus.PRESENT
            )
            if not candidates:
                limitations.append(f"MISSING_SEARCH_VOLUME:{evidence.metric_evidence_set_id}")
                continue
            value = candidates[0].value.normalized_value
            if type(value) is not int or value < 0:
                limitations.append(f"NON_INTEGER_SEARCH_VOLUME:{evidence.metric_evidence_set_id}")
                continue
            values[key] = (value, evidence)
        return values, tuple(sorted(limitations))

    def _search_denominator(
        self,
        *,
        request: BuyerNeedMapRequest,
        values: dict[tuple[str, str], tuple[int, KeywordMetricEvidenceSet]],
        limitations: tuple[str, ...],
        search_refs: dict[str, str],
    ) -> DemandDenominator:
        definition = self._definitions[DemandMetricType.SEARCH_DEMAND_SHARE]
        source_windows = {
            (
                item.period_start,
                item.period_end,
                item.period_type.value,
                item.timezone,
            )
            for item in request.search_metric_evidence_sets
        }
        resolved_window = request.analysis_window
        window_limitations: set[str] = set()
        if len(source_windows) > 1:
            window_limitations.add("INCOMPATIBLE_SEARCH_EVIDENCE_TIME_WINDOWS")
        elif source_windows:
            period_start, period_end, _, _ = next(iter(source_windows))
            if period_start is not None and period_end is not None:
                source_window = AnalysisWindow(
                    status=AnalysisWindowStatus.KNOWN,
                    period_start=period_start,
                    period_end=period_end,
                )
                if (
                    request.analysis_window.status is AnalysisWindowStatus.KNOWN
                    and request.analysis_window != source_window
                ):
                    window_limitations.add("SEARCH_EVIDENCE_WINDOW_DIFFERS_FROM_REQUEST")
                else:
                    resolved_window = source_window
        combined_limitations = tuple(sorted(set(limitations) | window_limitations))
        unavailable = (
            request.search_population_status is EvidencePopulationStatus.UNKNOWN
            or not request.search_metric_evidence_sets
            or not values
            or bool(window_limitations)
            or (
                request.search_population_status is EvidencePopulationStatus.COMPLETE
                and bool(combined_limitations)
            )
        )
        if unavailable:
            reasons = set(combined_limitations)
            if not request.search_metric_evidence_sets:
                reasons.add("NO_SEARCH_VOLUME_EVIDENCE")
            if request.search_population_status is EvidencePopulationStatus.UNKNOWN:
                reasons.add("SEARCH_POPULATION_COMPLETENESS_UNKNOWN")
            return self._denominator(
                metric_type=definition.metric_type,
                request=request,
                status=DemandDenominatorStatus.UNKNOWN,
                value=None,
                unit="search_volume",
                population_definition=definition.denominator_definition,
                eligible_ids=(),
                evidence_reference_ids=tuple(
                    sorted(search_refs[item.metric_evidence_set_id] for item in request.search_metric_evidence_sets)
                ),
                limitations=tuple(sorted(reasons or {"SEARCH_DENOMINATOR_UNKNOWN"})),
                analysis_window=resolved_window,
            )
        evidence_sets = tuple(value[1] for value in values.values())
        return self._denominator(
            metric_type=definition.metric_type,
            request=request,
            status=DemandDenominatorStatus.AVAILABLE,
            value=decimal_text(sum(value[0] for value in values.values())),
            unit="search_volume",
            population_definition=definition.denominator_definition,
            eligible_ids=tuple(item.metric_evidence_set_id for item in evidence_sets),
            evidence_reference_ids=tuple(search_refs[item.metric_evidence_set_id] for item in evidence_sets),
            limitations=(
                combined_limitations
                if request.search_population_status is EvidencePopulationStatus.PARTIAL
                else ()
            ),
            analysis_window=resolved_window,
        )

    def _review_denominator(
        self,
        *,
        request: BuyerNeedMapRequest,
        need_refs: dict[str, str],
    ) -> DemandDenominator:
        definition = self._definitions[DemandMetricType.REVIEW_MENTION_SHARE]
        review_needs = tuple(
            item
            for item in request.buyer_need_evidence
            if item.evidence_source is BuyerNeedTextSourceType.REVIEW
        )
        if (
            request.review_population_status is EvidencePopulationStatus.UNKNOWN
            or not review_needs
        ):
            limitations = []
            if not review_needs:
                limitations.append("NO_REVIEW_BUYER_NEED_EVIDENCE")
            if request.review_population_status is EvidencePopulationStatus.UNKNOWN:
                limitations.append("REVIEW_POPULATION_COMPLETENESS_UNKNOWN")
            return self._denominator(
                metric_type=definition.metric_type,
                request=request,
                status=DemandDenominatorStatus.UNKNOWN,
                value=None,
                unit="review_mention_count",
                population_definition=definition.denominator_definition,
                eligible_ids=(),
                evidence_reference_ids=tuple(need_refs[item.need_id] for item in review_needs),
                limitations=tuple(sorted(limitations)),
            )
        text_ids = tuple(sorted({item.source_evidence[0].text_id for item in review_needs}))
        return self._denominator(
            metric_type=definition.metric_type,
            request=request,
            status=DemandDenominatorStatus.AVAILABLE,
            value=decimal_text(len(text_ids)),
            unit="review_mention_count",
            population_definition=definition.denominator_definition,
            eligible_ids=text_ids,
            evidence_reference_ids=tuple(need_refs[item.need_id] for item in review_needs),
            limitations=(
                ("DECLARED_REVIEW_POPULATION_IS_PARTIAL",)
                if request.review_population_status is EvidencePopulationStatus.PARTIAL
                else ()
            ),
        )

    def _product_denominator(
        self,
        *,
        request: BuyerNeedMapRequest,
        category_map_ref: str | None,
    ) -> DemandDenominator:
        definition = self._definitions[DemandMetricType.PRODUCT_COVERAGE_SHARE]
        if request.category_product_map is None or category_map_ref is None:
            return self._denominator(
                metric_type=definition.metric_type,
                request=request,
                status=DemandDenominatorStatus.UNKNOWN,
                value=None,
                unit="grain_product_count",
                population_definition=definition.denominator_definition,
                eligible_ids=(),
                evidence_reference_ids=(),
                limitations=("CATEGORY_PRODUCT_MAP_NOT_SUPPLIED",),
            )
        products = request.category_product_map.included_products
        return self._denominator(
            metric_type=definition.metric_type,
            request=request,
            status=DemandDenominatorStatus.AVAILABLE,
            value=decimal_text(len(products)),
            unit="grain_product_count",
            population_definition=definition.denominator_definition,
            eligible_ids=tuple(item.grain_product_id for item in products),
            evidence_reference_ids=(category_map_ref,),
            limitations=(),
            analysis_window=request.category_product_map.analysis_window,
        )

    def _unknown_denominator(
        self,
        *,
        request: BuyerNeedMapRequest,
        metric_type: DemandMetricType,
        unit: str,
        limitation: str,
    ) -> DemandDenominator:
        return self._denominator(
            metric_type=metric_type,
            request=request,
            status=DemandDenominatorStatus.UNKNOWN,
            value=None,
            unit=unit,
            population_definition=self._definitions[metric_type].denominator_definition,
            eligible_ids=(),
            evidence_reference_ids=(),
            limitations=(limitation,),
        )

    @staticmethod
    def _denominator(
        *,
        metric_type: DemandMetricType,
        request: BuyerNeedMapRequest,
        status: DemandDenominatorStatus,
        value: str | None,
        unit: str,
        population_definition: str,
        eligible_ids: tuple[str, ...],
        evidence_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...],
        analysis_window: AnalysisWindow | None = None,
    ) -> DemandDenominator:
        payload = {
            "metric_type": metric_type,
            "category_scope_id": request.category_scope.category_scope_id,
            "status": status,
            "value": value,
            "unit": unit,
            "population_definition": population_definition,
            "analysis_window": analysis_window or request.analysis_window,
            "eligible_ids": tuple(sorted(eligible_ids)),
            "evidence_reference_ids": tuple(sorted(evidence_reference_ids)),
            "limitations": tuple(sorted(limitations)),
        }
        return DemandDenominator(
            denominator_id=deterministic_id("demand-denominator", payload),
            **payload,
        )

    def _search_metric(
        self,
        *,
        request: BuyerNeedMapRequest,
        cluster: SemanticClusterSnapshot,
        denominator: DemandDenominator,
        values: dict[tuple[str, str], tuple[int, KeywordMetricEvidenceSet]],
        cluster_ref: str,
        need_refs: dict[str, str],
        search_refs: dict[str, str],
    ) -> DemandMetricResult:
        definition = self._definitions[DemandMetricType.SEARCH_DEMAND_SHARE]
        search_needs = tuple(
            item
            for item in cluster.source_needs
            if item.evidence_source is BuyerNeedTextSourceType.SEARCH_TERM
        )
        keyword_keys = {
            (
                item.source_evidence[0].source_reference.keyword_identity.keyword_id,
                item.source_evidence[0].source_reference.keyword_identity.raw_text,
            )
            for item in search_needs
            if item.source_evidence[0].source_reference.keyword_identity is not None
        }
        missing = tuple(sorted(key for key in keyword_keys if key not in values))
        if (
            not keyword_keys
            or missing
            or denominator.status is DemandDenominatorStatus.UNKNOWN
            or denominator.value in {None, "0"}
        ):
            limitations = []
            if not keyword_keys:
                limitations.append("CLUSTER_HAS_NO_SEARCH_TERM_EVIDENCE")
            if missing:
                limitations.extend(f"MISSING_CLUSTER_SEARCH_VOLUME:{item[0]}" for item in missing)
            if denominator.status is DemandDenominatorStatus.UNKNOWN:
                limitations.append("SEARCH_DENOMINATOR_UNKNOWN")
            if denominator.value == "0":
                limitations.append("SEARCH_DENOMINATOR_ZERO")
            evidence_refs = {
                cluster_ref,
                *(need_refs[item.need_id] for item in search_needs),
                *denominator.evidence_reference_ids,
            }
            return self._unknown_metric(
                cluster=cluster,
                definition=definition,
                denominator=denominator,
                limitation=";".join(sorted(limitations)),
                evidence_reference_ids=tuple(sorted(evidence_refs)),
            )
        numerator = sum(values[key][0] for key in keyword_keys)
        metric_search_refs = tuple(
            search_refs[values[key][1].metric_evidence_set_id] for key in keyword_keys
        )
        evidence_refs = {
            cluster_ref,
            *(need_refs[item.need_id] for item in search_needs),
            *metric_search_refs,
            *denominator.evidence_reference_ids,
        }
        status = (
            DemandMetricStatus.AVAILABLE
            if request.search_population_status is EvidencePopulationStatus.COMPLETE
            else DemandMetricStatus.PARTIAL
        )
        confidence = DemandMetricConfidence(
            level=(
                DemandMetricConfidenceLevel.HIGH
                if status is DemandMetricStatus.AVAILABLE
                else DemandMetricConfidenceLevel.MEDIUM
            ),
            evidence_coverage="1",
            basis=(
                "all_cluster_search_keywords_have_resolved_search_volume",
                f"search_population_status:{request.search_population_status.value}",
                "confidence_is_not_demand_size",
            ),
        )
        return self._measured_metric(
            cluster=cluster,
            definition=definition,
            denominator=denominator,
            numerator=numerator,
            status=status,
            confidence=confidence,
            evidence_reference_ids=tuple(sorted(evidence_refs)),
            limitations=denominator.limitations,
        )

    def _review_metric(
        self,
        *,
        request: BuyerNeedMapRequest,
        cluster: SemanticClusterSnapshot,
        denominator: DemandDenominator,
        cluster_ref: str,
        need_refs: dict[str, str],
    ) -> DemandMetricResult:
        definition = self._definitions[DemandMetricType.REVIEW_MENTION_SHARE]
        review_needs = tuple(
            item
            for item in cluster.source_needs
            if item.evidence_source is BuyerNeedTextSourceType.REVIEW
        )
        if denominator.status is DemandDenominatorStatus.UNKNOWN or denominator.value in {None, "0"}:
            return self._unknown_metric(
                cluster=cluster,
                definition=definition,
                denominator=denominator,
                limitation=(
                    "REVIEW_DENOMINATOR_UNKNOWN"
                    if denominator.status is DemandDenominatorStatus.UNKNOWN
                    else "REVIEW_DENOMINATOR_ZERO"
                ),
                evidence_reference_ids=tuple(
                    sorted({cluster_ref, *denominator.evidence_reference_ids})
                ),
            )
        numerator = len({item.source_evidence[0].text_id for item in review_needs})
        status = (
            DemandMetricStatus.AVAILABLE
            if request.review_population_status is EvidencePopulationStatus.COMPLETE
            else DemandMetricStatus.PARTIAL
        )
        evidence_refs = {
            cluster_ref,
            *(need_refs[item.need_id] for item in review_needs),
            *denominator.evidence_reference_ids,
        }
        confidence = DemandMetricConfidence(
            level=(
                DemandMetricConfidenceLevel.HIGH
                if status is DemandMetricStatus.AVAILABLE
                else DemandMetricConfidenceLevel.MEDIUM
            ),
            evidence_coverage="1",
            basis=(
                "unique_review_text_evidence_counted_once",
                f"review_population_status:{request.review_population_status.value}",
                "confidence_is_not_demand_size",
            ),
        )
        return self._measured_metric(
            cluster=cluster,
            definition=definition,
            denominator=denominator,
            numerator=numerator,
            status=status,
            confidence=confidence,
            evidence_reference_ids=tuple(sorted(evidence_refs)),
            limitations=denominator.limitations,
        )

    def _product_metric(
        self,
        *,
        request: BuyerNeedMapRequest,
        cluster: SemanticClusterSnapshot,
        denominator: DemandDenominator,
        cluster_ref: str,
        need_refs: dict[str, str],
        category_map_ref: str | None,
        evidence_index: dict[str, BuyerNeedMapSourceEvidence],
    ) -> tuple[DemandMetricResult, tuple[BuyerNeedRelatedAttribute, ...], tuple[str, ...]]:
        definition = self._definitions[DemandMetricType.PRODUCT_COVERAGE_SHARE]
        category_map = request.category_product_map
        if (
            category_map is None
            or category_map_ref is None
            or denominator.status is DemandDenominatorStatus.UNKNOWN
            or denominator.value in {None, "0"}
        ):
            return (
                self._unknown_metric(
                    cluster=cluster,
                    definition=definition,
                    denominator=denominator,
                    limitation="CATEGORY_PRODUCT_MAP_OR_DENOMINATOR_UNAVAILABLE",
                    evidence_reference_ids=(cluster_ref,),
                ),
                (),
                (),
            )
        links = self.attribute_link_registry.for_cluster_label(cluster.cluster_label)
        if not links:
            return (
                self._unknown_metric(
                    cluster=cluster,
                    definition=definition,
                    denominator=denominator,
                    limitation="NO_VERSIONED_NEED_ATTRIBUTE_LINK",
                    evidence_reference_ids=(cluster_ref, category_map_ref),
                ),
                (),
                (),
            )
        related_attributes: list[BuyerNeedRelatedAttribute] = []
        related_products: set[str] = set()
        distribution_coverages: list[Decimal] = []
        metric_evidence = {
            cluster_ref,
            category_map_ref,
            *(need_refs[need_id] for need_id in cluster.source_need_ids),
        }
        matched_distribution = False
        for link in links:
            distribution = self._distribution(category_map, link.dimension)
            if distribution is None:
                continue
            matched_distribution = True
            distribution_coverages.append(Decimal(distribution.attribute_coverage))
            value = next(
                (
                    item
                    for item in distribution.values
                    if item.canonical_value.value == link.canonical_value
                ),
                None,
            )
            if value is None:
                continue
            evidence_refs = tuple(
                self._add_category_attribute_evidence(
                    category_map=category_map,
                    source_evidence_id=source_id,
                    evidence_index=evidence_index,
                )
                for source_id in value.evidence_reference_ids
            )
            related_attributes.append(
                BuyerNeedRelatedAttribute(
                    dimension=link.dimension,
                    canonical_value=value.canonical_value,
                    member_grain_product_ids=value.member_grain_product_ids,
                    evidence_reference_ids=evidence_refs,
                )
            )
            related_products.update(value.member_grain_product_ids)
            metric_evidence.update(evidence_refs)
        if not matched_distribution:
            return (
                self._unknown_metric(
                    cluster=cluster,
                    definition=definition,
                    denominator=denominator,
                    limitation="LINKED_ATTRIBUTE_DIMENSION_NOT_IN_CATEGORY_MAP",
                    evidence_reference_ids=tuple(sorted(metric_evidence)),
                ),
                (),
                (),
            )
        evidence_coverage = min(distribution_coverages, default=Decimal("0"))
        status = (
            DemandMetricStatus.AVAILABLE
            if evidence_coverage == Decimal("1")
            else DemandMetricStatus.PARTIAL
        )
        limitations = (
            ()
            if status is DemandMetricStatus.AVAILABLE
            else ("CATEGORY_ATTRIBUTE_VALUES_INCLUDE_UNKNOWN_PRODUCTS",)
        )
        confidence = DemandMetricConfidence(
            level=(
                DemandMetricConfidenceLevel.HIGH
                if status is DemandMetricStatus.AVAILABLE
                else DemandMetricConfidenceLevel.MEDIUM
            ),
            evidence_coverage=decimal_text(evidence_coverage),
            basis=(
                "versioned_need_attribute_link",
                "category_product_map_confirmed_attribute_membership",
                "product_coverage_is_not_demand_share",
            ),
        )
        metric = self._measured_metric(
            cluster=cluster,
            definition=definition,
            denominator=denominator,
            numerator=len(related_products),
            status=status,
            confidence=confidence,
            evidence_reference_ids=tuple(sorted(metric_evidence)),
            limitations=limitations,
        )
        return (
            metric,
            tuple(sorted(related_attributes, key=lambda item: item.canonical_value.value_id)),
            tuple(sorted(related_products)),
        )

    def _add_category_attribute_evidence(
        self,
        *,
        category_map: CategoryProductMapSnapshot,
        source_evidence_id: str,
        evidence_index: dict[str, BuyerNeedMapSourceEvidence],
    ) -> str:
        source = next(
            (
                item
                for item in category_map.source_evidence
                if item.evidence_reference_id == source_evidence_id
            ),
            None,
        )
        if not isinstance(source, CategoryMapSourceEvidence):
            raise BuyerNeedMapValidationError(
                "Category Product Map value references absent attribute evidence"
            )
        return self._add_evidence(
            evidence_index,
            BuyerNeedMapEvidenceType.PRODUCT_ATTRIBUTE,
            source,
        )

    @staticmethod
    def _distribution(
        category_map: CategoryProductMapSnapshot,
        dimension: object,
    ) -> AttributeDistribution | None:
        return next(
            (item for item in category_map.attribute_distributions if item.dimension is dimension),
            None,
        )

    def _measured_metric(
        self,
        *,
        cluster: SemanticClusterSnapshot,
        definition: DemandMetricDefinition,
        denominator: DemandDenominator,
        numerator: int,
        status: DemandMetricStatus,
        confidence: DemandMetricConfidence,
        evidence_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> DemandMetricResult:
        if denominator.value is None:
            raise BuyerNeedMapValidationError("measured metric requires denominator value")
        denominator_value = int(denominator.value)
        share = demand_share_text(numerator, denominator_value)
        if share is None:
            raise BuyerNeedMapValidationError("measured metric denominator must be positive")
        payload = {
            "metric_id": definition.metric_id,
            "metric_type": definition.metric_type,
            "cluster_id": cluster.cluster_id,
            "status": status,
            "numerator_value": decimal_text(numerator),
            "denominator_id": denominator.denominator_id,
            "share": share,
            "confidence": confidence,
            "evidence_reference_ids": tuple(sorted(set(evidence_reference_ids))),
            "limitations": tuple(sorted(set(limitations))),
        }
        return DemandMetricResult(
            metric_result_id=deterministic_id("demand-metric-result", payload),
            **payload,
        )

    def _unknown_metric(
        self,
        *,
        cluster: SemanticClusterSnapshot,
        definition: DemandMetricDefinition,
        denominator: DemandDenominator,
        limitation: str,
        evidence_reference_ids: tuple[str, ...],
    ) -> DemandMetricResult:
        payload = {
            "metric_id": definition.metric_id,
            "metric_type": definition.metric_type,
            "cluster_id": cluster.cluster_id,
            "status": DemandMetricStatus.UNKNOWN,
            "numerator_value": None,
            "denominator_id": denominator.denominator_id,
            "share": None,
            "confidence": DemandMetricConfidence(
                level=DemandMetricConfidenceLevel.UNKNOWN,
                evidence_coverage=None,
                basis=(
                    "insufficient_evidence_for_measurement",
                    "unknown_is_not_zero",
                    "confidence_is_not_demand_size",
                ),
            ),
            "evidence_reference_ids": tuple(sorted(set(evidence_reference_ids))),
            "limitations": (limitation,),
        }
        return DemandMetricResult(
            metric_result_id=deterministic_id("demand-metric-result", payload),
            **payload,
        )

    @staticmethod
    def _metric_diagnostic(
        cluster: SemanticClusterSnapshot,
        metric: DemandMetricResult,
    ) -> BuyerNeedMapDiagnostic:
        payload = {
            "code": f"{metric.metric_type.value}_UNKNOWN",
            "severity": Severity.INFO,
            "cluster_ids": (cluster.cluster_id,),
            "related_ids": tuple(sorted((metric.metric_result_id, metric.denominator_id))),
            "message": (
                f"{metric.metric_type.value} remains UNKNOWN: "
                f"{'; '.join(metric.limitations)}"
            ),
        }
        return BuyerNeedMapDiagnostic(
            diagnostic_id=deterministic_id("buyer-need-map-diagnostic", payload),
            **payload,
        )


__all__ = ("BuyerNeedMapBuilderV0_1",)
