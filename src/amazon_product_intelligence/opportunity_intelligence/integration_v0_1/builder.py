"""Read-only builder for Opportunity Candidate snapshots V0.1."""

from __future__ import annotations

from amazon_product_intelligence.contracts import Severity, deterministic_id

from .classifier import OpportunityCandidateClassifierV0_1
from .evidence_builder import OpportunityEvidenceBuilderV0_1
from .models import (
    OpportunityCandidateDiagnostic,
    OpportunityCandidateRequest,
    OpportunityCandidateSnapshot,
    OpportunityCandidateType,
    OpportunityConfidence,
    OpportunityEvidenceBundle,
    OpportunityEvidenceReference,
    OpportunityEvidenceSource,
    OpportunityEvidenceStatus,
    OpportunitySegmentDefinition,
    ProductAttributeSegment,
)


def _diagnostic(
    *,
    code: str,
    severity: Severity,
    related_evidence_ids: tuple[str, ...],
    message: str,
) -> OpportunityCandidateDiagnostic:
    material = {
        "code": code,
        "severity": severity,
        "related_evidence_ids": tuple(sorted(related_evidence_ids)),
        "message": message,
    }
    return OpportunityCandidateDiagnostic(
        diagnostic_id=deterministic_id("opportunity-candidate-diagnostic", material),
        **material,
    )


class OpportunityCandidateBuilderV0_1:
    """Combine upstream evidence snapshots into one immutable Candidate view."""

    def __init__(
        self,
        evidence_builder: OpportunityEvidenceBuilderV0_1 | None = None,
        classifier: OpportunityCandidateClassifierV0_1 | None = None,
    ) -> None:
        self._evidence_builder = evidence_builder or OpportunityEvidenceBuilderV0_1()
        self._classifier = classifier or OpportunityCandidateClassifierV0_1()

    def build(self, request: OpportunityCandidateRequest) -> OpportunityCandidateSnapshot:
        if not isinstance(request, OpportunityCandidateRequest):
            raise TypeError("request must be OpportunityCandidateRequest")
        evidence = self._evidence_builder.build(request)
        confidence = self._classifier.confidence(
            demand_status=evidence.demand.status,
            demand_reliability=evidence.demand.reliability,
            supply_status=evidence.supply.status,
            supply_reliability=evidence.supply.reliability,
            gap_status=evidence.gap.status,
            gap_reliability=evidence.gap.reliability,
            competition_status=evidence.competition.status,
            economic_status=evidence.economic.status,
        )
        status = self._classifier.classify(
            demand_status=evidence.demand.status,
            supply_status=evidence.supply.status,
            gap_status=evidence.gap.status,
            gap_type=evidence.gap.gap_type,
            competition_status=evidence.competition.status,
            competition_level=evidence.competition.overall_level,
        )
        references = {item.source: item for item in evidence.source_references}
        gap_reference = references[OpportunityEvidenceSource.SUPPLY_DEMAND_GAP]
        competition_reference = references[OpportunityEvidenceSource.COMPETITION_INTELLIGENCE]
        economic_reference = next(
            item
            for item in evidence.source_references
            if item.reference_id == evidence.economic.source_reference_id
        )
        segment_definition = self._segment_definition(request)
        product_attribute_segment = self._product_attribute_segment(request, segment_definition)
        diagnostics = self._diagnostics(evidence, status)
        material = {
            "category_scope": request.category_product_map.category_scope,
            "segment_definition": segment_definition,
            "need_cluster_id": request.supply_demand_gap.need_cluster_id,
            "product_attribute_segment": product_attribute_segment,
            "gap_reference": gap_reference,
            "competition_reference": competition_reference,
            "economic_reference": economic_reference,
            "confidence": confidence,
            "status": status,
            "evidence": evidence,
            "diagnostics": diagnostics,
            "ruleset_version": "opportunity-intelligence-integration-v0.1",
        }
        return OpportunityCandidateSnapshot(
            candidate_id=deterministic_id("opportunity-candidate", material),
            **material,
        )

    @staticmethod
    def _segment_definition(request: OpportunityCandidateRequest) -> OpportunitySegmentDefinition:
        cluster = next(
            item
            for item in request.buyer_need_map.need_clusters
            if item.cluster_id == request.supply_demand_gap.need_cluster_id
        )
        dimensions = tuple(sorted({item.dimension.value for item in cluster.related_attributes}))
        value_ids = tuple(
            sorted({item.canonical_value.value_id for item in cluster.related_attributes})
        )
        member_products = tuple(sorted(cluster.related_products)) or tuple(
            sorted(item.grain_product_id for item in request.category_product_map.included_products)
        )
        related_dimensions = set(dimensions)
        category_segments = tuple(
            sorted(
                item.segment_id
                for item in request.category_product_map.combination_segments
                if related_dimensions and related_dimensions <= {dimension.value for dimension in item.dimensions}
            )
        )
        material = {
            "source_category_map_id": request.category_product_map.map_id,
            "source_category_segment_ids": category_segments,
            "dimensions": dimensions,
            "canonical_value_ids": value_ids,
            "member_grain_product_ids": member_products,
        }
        return OpportunitySegmentDefinition(
            segment_id=deterministic_id("opportunity-segment-definition", material),
            **material,
        )

    @staticmethod
    def _product_attribute_segment(
        request: OpportunityCandidateRequest,
        definition: OpportunitySegmentDefinition,
    ) -> ProductAttributeSegment:
        distributions = request.category_product_map.attribute_distributions
        material = {
            "profile_ids": tuple(
                sorted(item.profile_id for item in request.product_attribute_profiles)
            ),
            "attribute_distribution_ids": tuple(
                sorted(item.distribution_id for item in distributions)
            ),
            "dimensions": definition.dimensions,
            "canonical_value_ids": definition.canonical_value_ids,
            "existing_product_ids": tuple(
                sorted(item.grain_product_id for item in request.category_product_map.included_products)
            ),
        }
        return ProductAttributeSegment(
            product_attribute_segment_id=deterministic_id(
                "opportunity-product-attribute-segment", material
            ),
            **material,
        )

    @staticmethod
    def _diagnostics(
        evidence: OpportunityEvidenceBundle,
        status: OpportunityCandidateType,
    ) -> tuple[OpportunityCandidateDiagnostic, ...]:
        diagnostics: list[OpportunityCandidateDiagnostic] = []
        if evidence.demand.status is OpportunityEvidenceStatus.UNKNOWN:
            diagnostics.append(
                _diagnostic(
                    code="DEMAND_EVIDENCE_UNKNOWN",
                    severity=Severity.WARNING,
                    related_evidence_ids=tuple(
                        item.evidence_id
                        for item in evidence.demand.metrics
                        if item.status is OpportunityEvidenceStatus.UNKNOWN
                    ),
                    message="Demand evidence is unavailable; UNKNOWN is not interpreted as zero demand.",
                )
            )
        if evidence.supply.status is OpportunityEvidenceStatus.UNKNOWN:
            diagnostics.append(
                _diagnostic(
                    code="SUPPLY_EVIDENCE_UNKNOWN",
                    severity=Severity.WARNING,
                    related_evidence_ids=(evidence.supply.product_coverage.evidence_id,),
                    message="Supply coverage is unavailable; no supply conclusion was fabricated.",
                )
            )
        if evidence.gap.status is OpportunityEvidenceStatus.UNKNOWN:
            diagnostics.append(
                _diagnostic(
                    code="GAP_CLASSIFICATION_UNKNOWN",
                    severity=Severity.WARNING,
                    related_evidence_ids=(evidence.gap.gap_evidence_id,),
                    message="Supply/Demand Gap cannot be determined from the available evidence.",
                )
            )
        if evidence.competition.status is not OpportunityEvidenceStatus.AVAILABLE:
            diagnostics.append(
                _diagnostic(
                    code="COMPETITION_EVIDENCE_INCOMPLETE",
                    severity=Severity.INFO,
                    related_evidence_ids=tuple(
                        item.signal_id
                        for item in (
                            evidence.competition.market_concentration,
                            evidence.competition.top_asin_dominance,
                            evidence.competition.brand_concentration,
                            evidence.competition.review_barrier,
                            evidence.competition.price_competition,
                        )
                        if item.status is not OpportunityEvidenceStatus.AVAILABLE
                    ),
                    message="Competition evidence remains separate from Gap and requires governed context.",
                )
            )
        if evidence.economic.status is not OpportunityEvidenceStatus.AVAILABLE:
            diagnostics.append(
                _diagnostic(
                    code="ECONOMIC_EVIDENCE_INCOMPLETE",
                    severity=Severity.INFO,
                    related_evidence_ids=tuple(
                        item.evidence_id
                        for item in (
                            evidence.economic.price_band,
                            evidence.economic.sales_availability,
                            evidence.economic.revenue_availability,
                            evidence.economic.market_size_signal,
                        )
                        if item.status is not OpportunityEvidenceStatus.AVAILABLE
                    ),
                    message="Economic evidence records availability only; no profit or margin calculation exists.",
                )
            )
        if status is OpportunityCandidateType.NEEDS_VALIDATION:
            diagnostics.append(
                _diagnostic(
                    code="CANDIDATE_REQUIRES_VALIDATION",
                    severity=Severity.INFO,
                    related_evidence_ids=(evidence.evidence_bundle_id,),
                    message="The current evidence state requires validation and is not a product recommendation.",
                )
            )
        return tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id))


__all__ = ("OpportunityCandidateBuilderV0_1",)
