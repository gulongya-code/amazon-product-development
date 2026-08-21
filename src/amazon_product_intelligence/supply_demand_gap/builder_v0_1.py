"""Evidence-linked Supply/Demand Gap Analysis builder V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal

from amazon_product_intelligence.buyer_need_map import (
    BuyerNeedClusterSummary,
    BuyerNeedMapEvidenceType,
    BuyerNeedMapSnapshot,
    DemandMetricConfidenceLevel,
    DemandMetricResult,
    DemandMetricStatus,
    DemandMetricType,
)
from amazon_product_intelligence.category_product_map import (
    AnalysisWindowStatus,
    CategoryMapSourceEvidence,
    CategoryProductMapSnapshot,
    EvidenceAwareMetricStatus,
)
from amazon_product_intelligence.contracts import Severity, deterministic_id
from amazon_product_intelligence.product_attribute_extraction import (
    CanonicalProductAttributeProfile,
)

from .classifier import GapClassifier
from .errors import SupplyDemandGapValidationError
from .models import (
    SUPPLY_DEMAND_GAP_RULESET_VERSION,
    GapClassificationPolicy,
    GapConfidenceLevel,
    GapDiagnostic,
    GapEvidence,
    GapMetricConfidence,
    GapSignalStatus,
    GapSupplyMetric,
    GapType,
    GapTypeRegistry,
    SupplyDemandGapRequest,
    SupplyDemandGapSnapshot,
    SupplyMetricType,
)
from .registry import GAP_CLASSIFICATION_POLICY_V0_1, GAP_TYPE_REGISTRY_V0_1


_DEMAND_TYPES = frozenset(
    {
        DemandMetricType.SEARCH_DEMAND_SHARE,
        DemandMetricType.REVIEW_MENTION_SHARE,
        DemandMetricType.SALES_ASSOCIATED_SHARE,
        DemandMetricType.REVENUE_ASSOCIATED_SHARE,
    }
)


def _confidence_level(level: DemandMetricConfidenceLevel) -> GapConfidenceLevel:
    return GapConfidenceLevel(level.value)


class SupplyDemandGapBuilderV0_1:
    """Detect a gap pattern while preserving upstream demand and supply facts."""

    ruleset_version = SUPPLY_DEMAND_GAP_RULESET_VERSION

    def __init__(
        self,
        *,
        type_registry: GapTypeRegistry = GAP_TYPE_REGISTRY_V0_1,
        classification_policy: GapClassificationPolicy = GAP_CLASSIFICATION_POLICY_V0_1,
    ) -> None:
        self.classifier = GapClassifier(
            type_registry=type_registry,
            classification_policy=classification_policy,
        )
        self.type_registry = type_registry
        self.classification_policy = classification_policy

    def build(self, request: SupplyDemandGapRequest) -> SupplyDemandGapSnapshot:
        if not isinstance(request, SupplyDemandGapRequest):
            raise SupplyDemandGapValidationError(
                "builder input must be SupplyDemandGapRequest"
            )
        summary = self._cluster_summary(request.buyer_need_map, request.need_cluster_id)
        demand_metrics = tuple(
            sorted(
                (
                    item
                    for item in request.buyer_need_map.demand_metrics
                    if item.cluster_id == request.need_cluster_id
                    and item.metric_type in _DEMAND_TYPES
                ),
                key=lambda item: item.metric_type.value,
            )
        )
        if {item.metric_type for item in demand_metrics} != _DEMAND_TYPES:
            raise SupplyDemandGapValidationError(
                "Buyer Need Map does not contain every supported demand metric"
            )
        product_coverage = self._metric(
            request.buyer_need_map,
            request.need_cluster_id,
            DemandMetricType.PRODUCT_COVERAGE_SHARE,
        )
        category_evidence_ids = self._category_evidence_ids(
            request.buyer_need_map,
            summary,
            request.category_product_map,
        )
        supply_metrics = self._supply_metrics(
            summary=summary,
            product_coverage=product_coverage,
            category_map=request.category_product_map,
            category_evidence_ids=category_evidence_ids,
        )
        evidence = self._evidence(
            request=request,
            summary=summary,
            demand_metrics=demand_metrics,
            supply_metrics=supply_metrics,
        )
        confidence = self.classifier.confidence(
            demand_metrics,
            supply_metrics,
            evidence_completeness="1",
        )
        gap_type = self.classifier.classify(demand_metrics, supply_metrics)
        gap_strength = self.classifier.strength(
            gap_type,
            demand_metrics,
            supply_metrics,
            confidence,
        )
        diagnostics = self._diagnostics(
            request=request,
            gap_type=gap_type,
            demand_metrics=demand_metrics,
            supply_metrics=supply_metrics,
        )
        payload = {
            "category_scope": request.buyer_need_map.category_scope,
            "analysis_window": request.buyer_need_map.analysis_window,
            "need_cluster_id": request.need_cluster_id,
            "demand_metrics": demand_metrics,
            "supply_metrics": supply_metrics,
            "gap_type": gap_type,
            "gap_strength": gap_strength,
            "confidence": confidence,
            "evidence": evidence,
            "diagnostics": diagnostics,
            "type_registry": self.type_registry,
            "classification_policy": self.classification_policy,
            "ruleset_version": self.ruleset_version,
        }
        return SupplyDemandGapSnapshot(
            gap_id=deterministic_id("supply-demand-gap", payload),
            **payload,
        )

    def build_all(
        self,
        buyer_need_map: BuyerNeedMapSnapshot,
        category_product_map: CategoryProductMapSnapshot,
        product_attribute_profiles: Sequence[CanonicalProductAttributeProfile],
    ) -> tuple[SupplyDemandGapSnapshot, ...]:
        """Build one deterministic snapshot for every Buyer Need cluster."""

        if not isinstance(buyer_need_map, BuyerNeedMapSnapshot) or not isinstance(
            category_product_map, CategoryProductMapSnapshot
        ):
            raise SupplyDemandGapValidationError("build_all requires both source snapshots")
        return tuple(
            sorted(
                (
                    self.build(
                        SupplyDemandGapRequest(
                            buyer_need_map=buyer_need_map,
                            category_product_map=category_product_map,
                            need_cluster_id=summary.cluster_id,
                            product_attribute_profiles=tuple(product_attribute_profiles),
                        )
                    )
                    for summary in buyer_need_map.need_clusters
                ),
                key=lambda item: item.gap_id,
            )
        )

    @staticmethod
    def _cluster_summary(
        buyer_need_map: BuyerNeedMapSnapshot,
        cluster_id: str,
    ) -> BuyerNeedClusterSummary:
        result = next(
            (item for item in buyer_need_map.need_clusters if item.cluster_id == cluster_id),
            None,
        )
        if result is None:
            raise SupplyDemandGapValidationError("need cluster is absent from Buyer Need Map")
        return result

    @staticmethod
    def _metric(
        buyer_need_map: BuyerNeedMapSnapshot,
        cluster_id: str,
        metric_type: DemandMetricType,
    ) -> DemandMetricResult:
        result = next(
            (
                item
                for item in buyer_need_map.demand_metrics
                if item.cluster_id == cluster_id and item.metric_type is metric_type
            ),
            None,
        )
        if result is None:
            raise SupplyDemandGapValidationError(
                f"Buyer Need Map lacks {metric_type.value} for the cluster"
            )
        return result

    @staticmethod
    def _category_evidence_ids(
        buyer_need_map: BuyerNeedMapSnapshot,
        summary: BuyerNeedClusterSummary,
        category_map: CategoryProductMapSnapshot,
    ) -> tuple[str, ...]:
        evidence_by_id = {
            item.evidence_reference_id: item for item in buyer_need_map.source_evidence
        }
        ids = {category_map.map_id}
        for related in summary.related_attributes:
            for reference_id in related.evidence_reference_ids:
                wrapper = evidence_by_id.get(reference_id)
                if (
                    wrapper is not None
                    and wrapper.evidence_type is BuyerNeedMapEvidenceType.PRODUCT_ATTRIBUTE
                    and isinstance(wrapper.source_record, CategoryMapSourceEvidence)
                ):
                    ids.add(wrapper.source_record.evidence_reference_id)
        return tuple(sorted(ids))

    def _supply_metrics(
        self,
        *,
        summary: BuyerNeedClusterSummary,
        product_coverage: DemandMetricResult,
        category_map: CategoryProductMapSnapshot,
        category_evidence_ids: tuple[str, ...],
    ) -> tuple[GapSupplyMetric, ...]:
        metrics = [
            self._product_coverage_metric(
                summary.cluster_id,
                product_coverage,
                category_evidence_ids,
            ),
            self._matching_product_count_metric(
                summary.cluster_id,
                product_coverage,
                category_evidence_ids,
            ),
        ]
        dimensions = tuple(sorted({item.dimension for item in summary.related_attributes}, key=lambda item: item.value))
        for dimension in dimensions:
            distribution = next(
                (
                    item
                    for item in category_map.attribute_distributions
                    if item.dimension is dimension
                ),
                None,
            )
            if distribution is None:
                continue
            ids = tuple(
                sorted(
                    {
                        category_map.map_id,
                        *distribution.evidence_reference_ids,
                    }
                )
            )
            coverage = Decimal(distribution.attribute_coverage)
            status = (
                GapSignalStatus.AVAILABLE
                if coverage == Decimal("1")
                else GapSignalStatus.PARTIAL
            )
            level = (
                GapConfidenceLevel.HIGH
                if coverage == Decimal("1")
                else GapConfidenceLevel.MEDIUM
                if coverage >= Decimal("0.5")
                else GapConfidenceLevel.LOW
            )
            metrics.append(
                self._supply_metric(
                    metric_type=SupplyMetricType.ATTRIBUTE_COVERAGE,
                    metric_scope_id=f"{summary.cluster_id}:{dimension.value}",
                    status=status,
                    value=distribution.attribute_coverage,
                    unit="share",
                    source_metric_id=distribution.distribution_id,
                    denominator_id=distribution.coverage_denominator_id,
                    confidence=GapMetricConfidence(
                        level=level,
                        evidence_coverage=distribution.attribute_coverage,
                        basis=(
                            "category_product_map_attribute_coverage",
                            "attribute_coverage_is_not_demand",
                        ),
                    ),
                    evidence_reference_ids=ids,
                    limitations=(
                        ()
                        if status is GapSignalStatus.AVAILABLE
                        else ("CATEGORY_ATTRIBUTE_VALUES_INCLUDE_UNKNOWN_PRODUCTS",)
                    ),
                )
            )
        if not dimensions:
            metrics.append(
                self._unknown_supply_metric(
                    SupplyMetricType.ATTRIBUTE_COVERAGE,
                    summary.cluster_id,
                    "NO_VERSIONED_NEED_ATTRIBUTE_LINK",
                )
            )

        relevant_products = set(summary.related_products)
        competition_count = 0
        for segment in category_map.combination_segments:
            source = segment.competition_metrics
            if not relevant_products.intersection(segment.member_grain_product_ids):
                continue
            if source.status is EvidenceAwareMetricStatus.UNKNOWN:
                continue
            status = (
                GapSignalStatus.AVAILABLE
                if source.status is EvidenceAwareMetricStatus.AVAILABLE
                else GapSignalStatus.PARTIAL
            )
            evidence_ids = tuple(sorted({category_map.map_id, *source.evidence_ids}))
            metrics.append(
                self._supply_metric(
                    metric_type=SupplyMetricType.COMPETITION_EVIDENCE,
                    metric_scope_id=segment.segment_id,
                    status=status,
                    value=source.value,
                    unit=source.unit.unit_code if source.unit is not None else None,
                    source_metric_id=source.metric_id,
                    denominator_id=source.denominator_id,
                    confidence=GapMetricConfidence(
                        level=(
                            GapConfidenceLevel.HIGH
                            if status is GapSignalStatus.AVAILABLE
                            else GapConfidenceLevel.MEDIUM
                        ),
                        evidence_coverage="1",
                        basis=(
                            "category_product_map_competition_evidence",
                            "competition_context_does_not_change_gap_classification",
                        ),
                    ),
                    evidence_reference_ids=evidence_ids,
                    limitations=source.limitations,
                )
            )
            competition_count += 1
        if competition_count == 0:
            metrics.append(
                self._unknown_supply_metric(
                    SupplyMetricType.COMPETITION_EVIDENCE,
                    summary.cluster_id,
                    "NO_CLUSTER_LINKED_COMPETITION_EVIDENCE",
                )
            )
        return tuple(sorted(metrics, key=lambda item: item.supply_metric_id))

    def _product_coverage_metric(
        self,
        cluster_id: str,
        source: DemandMetricResult,
        evidence_ids: tuple[str, ...],
    ) -> GapSupplyMetric:
        if source.status is DemandMetricStatus.UNKNOWN or source.share is None:
            return self._unknown_supply_metric(
                SupplyMetricType.PRODUCT_COVERAGE_SHARE,
                cluster_id,
                "BUYER_NEED_MAP_PRODUCT_COVERAGE_UNKNOWN",
                source_metric_id=source.metric_result_id,
            )
        status = (
            GapSignalStatus.AVAILABLE
            if source.status is DemandMetricStatus.AVAILABLE
            else GapSignalStatus.PARTIAL
        )
        return self._supply_metric(
            metric_type=SupplyMetricType.PRODUCT_COVERAGE_SHARE,
            metric_scope_id=cluster_id,
            status=status,
            value=source.share,
            unit="share",
            source_metric_id=source.metric_result_id,
            denominator_id=source.denominator_id,
            confidence=GapMetricConfidence(
                level=_confidence_level(source.confidence.level),
                evidence_coverage=source.confidence.evidence_coverage,
                basis=tuple(
                    sorted(
                        {
                            *source.confidence.basis,
                            "consumed_without_recomputing_product_coverage",
                            "product_coverage_is_supply_not_opportunity",
                        }
                    )
                ),
            ),
            evidence_reference_ids=evidence_ids,
            limitations=source.limitations,
        )

    def _matching_product_count_metric(
        self,
        cluster_id: str,
        source: DemandMetricResult,
        evidence_ids: tuple[str, ...],
    ) -> GapSupplyMetric:
        if source.status is DemandMetricStatus.UNKNOWN or source.numerator_value is None:
            return self._unknown_supply_metric(
                SupplyMetricType.MATCHING_PRODUCT_COUNT,
                cluster_id,
                "BUYER_NEED_MAP_MATCHING_PRODUCT_COUNT_UNKNOWN",
                source_metric_id=source.metric_result_id,
            )
        status = (
            GapSignalStatus.AVAILABLE
            if source.status is DemandMetricStatus.AVAILABLE
            else GapSignalStatus.PARTIAL
        )
        return self._supply_metric(
            metric_type=SupplyMetricType.MATCHING_PRODUCT_COUNT,
            metric_scope_id=cluster_id,
            status=status,
            value=source.numerator_value,
            unit="product_count",
            source_metric_id=source.metric_result_id,
            denominator_id=None,
            confidence=GapMetricConfidence(
                level=_confidence_level(source.confidence.level),
                evidence_coverage=source.confidence.evidence_coverage,
                basis=(
                    "buyer_need_map_product_coverage_numerator",
                    "consumed_without_recomputing_matching_products",
                ),
            ),
            evidence_reference_ids=evidence_ids,
            limitations=source.limitations,
        )

    @staticmethod
    def _supply_metric(
        *,
        metric_type: SupplyMetricType,
        metric_scope_id: str,
        status: GapSignalStatus,
        value: object,
        unit: str | None,
        source_metric_id: str | None,
        denominator_id: str | None,
        confidence: GapMetricConfidence,
        evidence_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> GapSupplyMetric:
        payload = {
            "metric_type": metric_type,
            "metric_scope_id": metric_scope_id,
            "status": status,
            "value": value,
            "unit": unit,
            "source_metric_id": source_metric_id,
            "denominator_id": denominator_id,
            "confidence": confidence,
            "evidence_reference_ids": tuple(sorted(set(evidence_reference_ids))),
            "limitations": tuple(sorted(set(limitations))),
        }
        return GapSupplyMetric(
            supply_metric_id=deterministic_id("gap-supply-metric", payload),
            **payload,
        )

    def _unknown_supply_metric(
        self,
        metric_type: SupplyMetricType,
        scope_id: str,
        limitation: str,
        *,
        source_metric_id: str | None = None,
    ) -> GapSupplyMetric:
        return self._supply_metric(
            metric_type=metric_type,
            metric_scope_id=scope_id,
            status=GapSignalStatus.UNKNOWN,
            value=None,
            unit=None,
            source_metric_id=source_metric_id,
            denominator_id=None,
            confidence=GapMetricConfidence(
                level=GapConfidenceLevel.UNKNOWN,
                evidence_coverage=None,
                basis=(
                    "insufficient_evidence_for_supply_metric",
                    "unknown_is_not_zero",
                ),
            ),
            evidence_reference_ids=(),
            limitations=(limitation,),
        )

    @staticmethod
    def _evidence(
        *,
        request: SupplyDemandGapRequest,
        summary: BuyerNeedClusterSummary,
        demand_metrics: tuple[DemandMetricResult, ...],
        supply_metrics: tuple[GapSupplyMetric, ...],
    ) -> GapEvidence:
        source_by_id = {
            item.evidence_reference_id: item for item in request.buyer_need_map.source_evidence
        }
        demand_source_ids = {
            *summary.evidence_reference_ids,
            *(reference_id for item in demand_metrics for reference_id in item.evidence_reference_ids),
        }
        demand_source_ids = {
            reference_id
            for reference_id in demand_source_ids
            if reference_id in source_by_id
            and source_by_id[reference_id].evidence_type
            in {
                BuyerNeedMapEvidenceType.BUYER_NEED,
                BuyerNeedMapEvidenceType.SEMANTIC_CLUSTER,
                BuyerNeedMapEvidenceType.SEARCH_METRIC,
            }
        }
        supply_source_ids = {
            reference_id
            for item in supply_metrics
            for reference_id in item.evidence_reference_ids
        }
        included = request.category_product_map.included_products
        grain_product_ids = tuple(sorted(item.grain_product_id for item in included))
        profile_ids = tuple(
            sorted(profile_id for item in included for profile_id in item.source_profile_ids)
        )
        identities = tuple(
            sorted(
                (identity for item in included for identity in item.member_product_identities),
                key=lambda item: item.product_id,
            )
        )
        profiles = tuple(sorted(request.product_attribute_profiles, key=lambda item: item.profile_id))
        payload = {
            "buyer_need_map": request.buyer_need_map,
            "category_product_map": request.category_product_map,
            "need_cluster_id": request.need_cluster_id,
            "need_ids": tuple(sorted(summary.need_ids)),
            "demand_metric_result_ids": tuple(
                sorted(item.metric_result_id for item in demand_metrics)
            ),
            "demand_denominator_ids": tuple(
                sorted(item.denominator_id for item in demand_metrics)
            ),
            "demand_source_evidence_reference_ids": tuple(sorted(demand_source_ids)),
            "supply_metric_ids": tuple(
                sorted(item.supply_metric_id for item in supply_metrics)
            ),
            "supply_source_evidence_reference_ids": tuple(sorted(supply_source_ids)),
            "grain_product_ids": grain_product_ids,
            "profile_ids": profile_ids,
            "product_attribute_profiles": profiles,
            "product_identities": identities,
        }
        return GapEvidence(
            evidence_id=deterministic_id("supply-demand-gap-evidence", payload),
            **payload,
        )

    @staticmethod
    def _diagnostic(code: str, related_ids: Sequence[str], message: str) -> GapDiagnostic:
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_ids": tuple(sorted(set(related_ids))),
            "message": message,
        }
        return GapDiagnostic(
            diagnostic_id=deterministic_id("supply-demand-gap-diagnostic", payload),
            **payload,
        )

    def _diagnostics(
        self,
        *,
        request: SupplyDemandGapRequest,
        gap_type: GapType,
        demand_metrics: tuple[DemandMetricResult, ...],
        supply_metrics: tuple[GapSupplyMetric, ...],
    ) -> tuple[GapDiagnostic, ...]:
        diagnostics = [
            self._diagnostic(
                f"GAP_CLASSIFICATION_{gap_type.value}",
                (
                    request.need_cluster_id,
                    *(item.metric_result_id for item in demand_metrics),
                    *(item.supply_metric_id for item in supply_metrics),
                ),
                (
                    "Demand and supply signals were classified under the versioned Gap policy. "
                    "This result reports signal alignment or mismatch only."
                ),
            )
        ]
        unknown_demand = tuple(
            item.metric_result_id
            for item in demand_metrics
            if item.status is DemandMetricStatus.UNKNOWN
        )
        if unknown_demand:
            diagnostics.append(
                self._diagnostic(
                    "DEMAND_METRICS_UNKNOWN",
                    unknown_demand,
                    "One or more demand metrics remain UNKNOWN and were not treated as zero.",
                )
            )
        unknown_supply = tuple(
            item.supply_metric_id
            for item in supply_metrics
            if item.status is GapSignalStatus.UNKNOWN
        )
        if unknown_supply:
            diagnostics.append(
                self._diagnostic(
                    "SUPPLY_METRICS_UNKNOWN",
                    unknown_supply,
                    "One or more supply context metrics remain UNKNOWN and were not treated as zero.",
                )
            )
        if (
            request.buyer_need_map.analysis_window.status is AnalysisWindowStatus.KNOWN
            and request.category_product_map.analysis_window.status is AnalysisWindowStatus.UNKNOWN
        ):
            diagnostics.append(
                self._diagnostic(
                    "SUPPLY_ANALYSIS_WINDOW_UNKNOWN",
                    (request.category_product_map.map_id,),
                    "Supply evidence has no known analysis window; the demand window is retained.",
                )
            )
        return tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id))


__all__ = ("SupplyDemandGapBuilderV0_1",)
