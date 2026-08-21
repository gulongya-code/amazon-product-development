"""Candidate-only input adapter for Opportunity Scoring Integration V0.1."""

from __future__ import annotations

from collections.abc import Iterable

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.opportunity_intelligence.integration_v0_1 import (
    CompetitionSignalEvidence,
    OpportunityCandidateSnapshot,
    OpportunityEvidenceStatus,
    OpportunityMetricEvidence,
)

from .models import (
    OPPORTUNITY_SCORING_INTEGRATION_VERSION,
    OpportunityScoreDimension,
    OpportunityScoreEvidenceReference,
    OpportunityScoreMetricStatus,
    OpportunityScoringIntegrationInput,
    OpportunityScoringIntegrationValidationError,
    OpportunityScoringMetricInput,
)


_STATUS_MAP = {
    OpportunityEvidenceStatus.AVAILABLE: OpportunityScoreMetricStatus.AVAILABLE,
    OpportunityEvidenceStatus.PARTIAL: OpportunityScoreMetricStatus.PARTIAL,
    OpportunityEvidenceStatus.UNKNOWN: OpportunityScoreMetricStatus.UNKNOWN,
}


class OpportunityScoreInputAdapter:
    """Convert one Opportunity Candidate without reading its upstream raw modules."""

    def adapt(
        self, candidate: OpportunityCandidateSnapshot
    ) -> OpportunityScoringIntegrationInput:
        if not isinstance(candidate, OpportunityCandidateSnapshot):
            raise OpportunityScoringIntegrationValidationError(
                "candidate must be OpportunityCandidateSnapshot"
            )

        references = tuple(
            OpportunityScoreEvidenceReference(
                reference_id=item.reference_id,
                source=item.source.value,
                source_id=item.source_id,
                record_ids=item.record_ids,
                missing=item.missing,
                limitations=item.limitations,
            )
            for item in candidate.evidence.source_references
        )
        metrics = tuple(
            sorted(
                (
                    *self._demand_metrics(candidate),
                    *self._gap_metrics(candidate),
                    *self._competition_metrics(candidate),
                    *self._economic_metrics(candidate),
                    *self._completeness_metrics(candidate),
                ),
                key=lambda item: item.metric_id,
            )
        )
        evidence_ids = self._evidence_ids(candidate)
        limitations = self._limitations(candidate)
        payload = {
            "candidate_id": candidate.candidate_id,
            "category_scope": candidate.category_scope.to_dict(),
            "candidate_confidence": candidate.confidence,
            "metrics": metrics,
            "evidence_ids": evidence_ids,
            "source_references": references,
            "limitations": limitations,
            "integration_version": OPPORTUNITY_SCORING_INTEGRATION_VERSION,
        }
        return OpportunityScoringIntegrationInput(
            input_id=deterministic_id("opportunity-score-input", payload),
            **payload,
        )

    def _demand_metrics(
        self, candidate: OpportunityCandidateSnapshot
    ) -> tuple[OpportunityScoringMetricInput, ...]:
        demand = candidate.evidence.demand
        by_name = {item.metric_name: item for item in demand.metrics}
        reference_ids = self._references_for(demand.metrics)
        source_evidence_ids = (
            demand.demand_evidence_id,
            *(item.evidence_id for item in demand.metrics),
        )
        metrics = tuple(
            self._from_metric(
                metric_id=f"demand.{name}",
                dimension=OpportunityScoreDimension.DEMAND_STRENGTH,
                metric=by_name.get(name),
                fallback_evidence_ids=source_evidence_ids,
                fallback_reference_ids=reference_ids,
                missing_limitation=f"MISSING_{name.upper()}",
            )
            for name in ("search_demand_share", "review_mention_share")
        )
        confidence_status = (
            OpportunityScoreMetricStatus.UNKNOWN
            if demand.reliability.value == "unknown"
            else _STATUS_MAP[demand.status]
        )
        confidence_limitations = (
            ("DEMAND_CONFIDENCE_UNKNOWN",)
            if confidence_status is OpportunityScoreMetricStatus.UNKNOWN
            else (
                ("DEMAND_EVIDENCE_PARTIAL",)
                if confidence_status is OpportunityScoreMetricStatus.PARTIAL
                else ()
            )
        )
        return (
            *metrics,
            OpportunityScoringMetricInput(
                metric_id="demand.confidence",
                dimension=OpportunityScoreDimension.DEMAND_STRENGTH,
                value=(
                    None
                    if confidence_status is OpportunityScoreMetricStatus.UNKNOWN
                    else demand.reliability.value.upper()
                ),
                status=confidence_status,
                source_evidence_ids=source_evidence_ids,
                source_reference_ids=reference_ids,
                limitations=confidence_limitations,
            ),
        )

    @staticmethod
    def _gap_metrics(
        candidate: OpportunityCandidateSnapshot,
    ) -> tuple[OpportunityScoringMetricInput, ...]:
        gap = candidate.evidence.gap
        status = _STATUS_MAP[gap.status]
        source_ids = (gap.gap_evidence_id, *gap.source_metric_ids)
        limitations = (
            ()
            if status is OpportunityScoreMetricStatus.AVAILABLE
            else ("SUPPLY_DEMAND_GAP_NOT_FULLY_AVAILABLE",)
        )
        value_type = (
            gap.gap_type.value
            if status is not OpportunityScoreMetricStatus.UNKNOWN
            else None
        )
        value_strength = (
            gap.gap_strength.value
            if status is not OpportunityScoreMetricStatus.UNKNOWN
            else None
        )
        return (
            OpportunityScoringMetricInput(
                metric_id="supply_gap.gap_type",
                dimension=OpportunityScoreDimension.SUPPLY_GAP,
                value=value_type,
                status=status,
                source_evidence_ids=source_ids,
                source_reference_ids=(gap.source_reference_id,),
                limitations=limitations,
            ),
            OpportunityScoringMetricInput(
                metric_id="supply_gap.gap_strength",
                dimension=OpportunityScoreDimension.SUPPLY_GAP,
                value=value_strength,
                status=status,
                source_evidence_ids=source_ids,
                source_reference_ids=(gap.source_reference_id,),
                limitations=limitations,
            ),
        )

    @staticmethod
    def _competition_metrics(
        candidate: OpportunityCandidateSnapshot,
    ) -> tuple[OpportunityScoringMetricInput, ...]:
        competition = candidate.evidence.competition
        fields = (
            ("market_concentration", competition.market_concentration),
            ("brand_concentration", competition.brand_concentration),
            ("review_barrier", competition.review_barrier),
            ("price_competition", competition.price_competition),
        )
        return tuple(
            OpportunityScoreInputAdapter._from_competition_signal(name, signal)
            for name, signal in fields
        )

    @staticmethod
    def _from_competition_signal(
        name: str, signal: CompetitionSignalEvidence
    ) -> OpportunityScoringMetricInput:
        status = _STATUS_MAP[signal.status]
        value = (
            None
            if status is OpportunityScoreMetricStatus.UNKNOWN
            or signal.level.value == "UNKNOWN"
            else signal.level.value
        )
        limitations = signal.limitations
        if value is None and not limitations:
            limitations = (f"{name.upper()}_LEVEL_UNKNOWN",)
        return OpportunityScoringMetricInput(
            metric_id=f"competition.{name}",
            dimension=OpportunityScoreDimension.COMPETITION_FAVORABILITY,
            value=value,
            status=status,
            source_evidence_ids=(signal.signal_id,),
            source_reference_ids=signal.source_reference_ids,
            limitations=limitations,
        )

    def _economic_metrics(
        self, candidate: OpportunityCandidateSnapshot
    ) -> tuple[OpportunityScoringMetricInput, ...]:
        economic = candidate.evidence.economic
        return tuple(
            self._from_metric(
                metric_id=f"economic.{name}",
                dimension=OpportunityScoreDimension.ECONOMIC_EVIDENCE,
                metric=getattr(economic, name),
                fallback_evidence_ids=(economic.economic_evidence_id,),
                fallback_reference_ids=(economic.source_reference_id,),
                missing_limitation=f"{name.upper()}_UNKNOWN",
            )
            for name in (
                "price_band",
                "sales_availability",
                "revenue_availability",
            )
        )

    @staticmethod
    def _completeness_metrics(
        candidate: OpportunityCandidateSnapshot,
    ) -> tuple[OpportunityScoringMetricInput, ...]:
        evidence = candidate.evidence
        areas = (
            (
                "demand",
                evidence.demand.status,
                (evidence.demand.demand_evidence_id,),
                tuple(
                    value
                    for item in evidence.demand.metrics
                    for value in item.source_reference_ids
                ),
            ),
            (
                "supply",
                evidence.supply.status,
                (evidence.supply.supply_evidence_id,),
                (
                    *evidence.supply.product_coverage.source_reference_ids,
                    *(
                        value
                        for item in evidence.supply.attribute_distributions
                        for value in item.source_reference_ids
                    ),
                ),
            ),
            (
                "gap",
                evidence.gap.status,
                (evidence.gap.gap_evidence_id,),
                (evidence.gap.source_reference_id,),
            ),
            (
                "competition",
                evidence.competition.status,
                (evidence.competition.competition_evidence_id,),
                (evidence.competition.source_reference_id,),
            ),
            (
                "economic",
                evidence.economic.status,
                (evidence.economic.economic_evidence_id,),
                (evidence.economic.source_reference_id,),
            ),
        )
        metrics: list[OpportunityScoringMetricInput] = []
        for name, source_status, evidence_ids, reference_ids in areas:
            status = _STATUS_MAP[source_status]
            limitations = (
                ()
                if status is OpportunityScoreMetricStatus.AVAILABLE
                else (
                    f"{name.upper()}_EVIDENCE_{status.value}",
                )
            )
            metrics.append(
                OpportunityScoringMetricInput(
                    metric_id=f"evidence_confidence.{name}",
                    dimension=OpportunityScoreDimension.EVIDENCE_CONFIDENCE,
                    value=(
                        None
                        if status is OpportunityScoreMetricStatus.UNKNOWN
                        else status.value
                    ),
                    status=status,
                    source_evidence_ids=tuple(dict.fromkeys(evidence_ids)),
                    source_reference_ids=tuple(dict.fromkeys(reference_ids)),
                    limitations=limitations,
                )
            )
        return tuple(metrics)

    @staticmethod
    def _from_metric(
        *,
        metric_id: str,
        dimension: OpportunityScoreDimension,
        metric: OpportunityMetricEvidence | None,
        fallback_evidence_ids: tuple[str, ...],
        fallback_reference_ids: tuple[str, ...],
        missing_limitation: str,
    ) -> OpportunityScoringMetricInput:
        if metric is None:
            return OpportunityScoringMetricInput(
                metric_id=metric_id,
                dimension=dimension,
                value=None,
                status=OpportunityScoreMetricStatus.UNKNOWN,
                source_evidence_ids=fallback_evidence_ids,
                source_reference_ids=fallback_reference_ids,
                limitations=(missing_limitation,),
            )
        return OpportunityScoringMetricInput(
            metric_id=metric_id,
            dimension=dimension,
            value=metric.value,
            status=_STATUS_MAP[metric.status],
            source_evidence_ids=(metric.evidence_id,),
            source_reference_ids=metric.source_reference_ids,
            limitations=metric.limitations,
        )

    @staticmethod
    def _references_for(
        metrics: Iterable[OpportunityMetricEvidence],
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    reference_id
                    for metric in metrics
                    for reference_id in metric.source_reference_ids
                }
            )
        )

    @staticmethod
    def _evidence_ids(
        candidate: OpportunityCandidateSnapshot,
    ) -> tuple[str, ...]:
        evidence = candidate.evidence
        competition_signals = (
            evidence.competition.market_concentration,
            evidence.competition.top_asin_dominance,
            evidence.competition.brand_concentration,
            evidence.competition.review_barrier,
            evidence.competition.price_competition,
        )
        economic_metrics = (
            evidence.economic.price_band,
            evidence.economic.sales_availability,
            evidence.economic.revenue_availability,
            evidence.economic.market_size_signal,
        )
        return tuple(
            sorted(
                {
                    evidence.evidence_bundle_id,
                    evidence.demand.demand_evidence_id,
                    *(item.evidence_id for item in evidence.demand.metrics),
                    evidence.supply.supply_evidence_id,
                    evidence.supply.product_coverage.evidence_id,
                    *(
                        item.evidence_id
                        for item in evidence.supply.attribute_distributions
                    ),
                    evidence.gap.gap_evidence_id,
                    *evidence.gap.source_metric_ids,
                    evidence.competition.competition_evidence_id,
                    *(item.signal_id for item in competition_signals),
                    evidence.economic.economic_evidence_id,
                    *(item.evidence_id for item in economic_metrics),
                }
            )
        )

    @staticmethod
    def _limitations(
        candidate: OpportunityCandidateSnapshot,
    ) -> tuple[str, ...]:
        evidence = candidate.evidence
        metric_limitations = (
            *(
                value
                for item in evidence.demand.metrics
                for value in item.limitations
            ),
            *evidence.supply.product_coverage.limitations,
            *(
                value
                for item in evidence.supply.attribute_distributions
                for value in item.limitations
            ),
            *evidence.competition.market_concentration.limitations,
            *evidence.competition.top_asin_dominance.limitations,
            *evidence.competition.brand_concentration.limitations,
            *evidence.competition.review_barrier.limitations,
            *evidence.competition.price_competition.limitations,
            *evidence.economic.price_band.limitations,
            *evidence.economic.sales_availability.limitations,
            *evidence.economic.revenue_availability.limitations,
            *evidence.economic.market_size_signal.limitations,
        )
        return tuple(
            sorted(
                {
                    *metric_limitations,
                    *(
                        value
                        for item in evidence.source_references
                        for value in item.limitations
                    ),
                    *(
                        f"{item.code}: {item.message}"
                        for item in candidate.diagnostics
                    ),
                }
            )
        )


__all__ = ("OpportunityScoreInputAdapter",)
