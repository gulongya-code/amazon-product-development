"""Explicit non-scoring Opportunity Candidate classification rules V0.1."""

from __future__ import annotations

from amazon_product_intelligence.supply_demand_gap import GapType

from .models import (
    CompetitionLevel,
    OpportunityCandidateType,
    OpportunityConfidence,
    OpportunityEvidenceStatus,
)


class OpportunityCandidateClassifierV0_1:
    """Classify evidence states without modifying the upstream gap or assigning a score."""

    @staticmethod
    def classify(
        *,
        demand_status: OpportunityEvidenceStatus,
        supply_status: OpportunityEvidenceStatus,
        gap_status: OpportunityEvidenceStatus,
        gap_type: GapType,
        competition_status: OpportunityEvidenceStatus,
        competition_level: CompetitionLevel,
    ) -> OpportunityCandidateType:
        if (
            demand_status is OpportunityEvidenceStatus.UNKNOWN
            or supply_status is OpportunityEvidenceStatus.UNKNOWN
            or gap_status is OpportunityEvidenceStatus.UNKNOWN
            or gap_type is GapType.INSUFFICIENT_EVIDENCE
        ):
            return OpportunityCandidateType.INSUFFICIENT_EVIDENCE
        if gap_type in {GapType.LOW_DEMAND_LOW_SUPPLY, GapType.LOW_DEMAND_HIGH_SUPPLY}:
            return OpportunityCandidateType.LOW_DEMAND_AREA
        if gap_type is GapType.HIGH_DEMAND_LOW_SUPPLY:
            if (
                competition_status is OpportunityEvidenceStatus.AVAILABLE
                and competition_level is CompetitionLevel.LOW
            ):
                return OpportunityCandidateType.POTENTIAL_ENTRY_AREA
            return OpportunityCandidateType.NEEDS_VALIDATION
        if gap_type is GapType.HIGH_DEMAND_HIGH_SUPPLY:
            if (
                competition_status is OpportunityEvidenceStatus.AVAILABLE
                and competition_level is CompetitionLevel.HIGH
            ):
                return OpportunityCandidateType.HIGH_COMPETITION_AREA
            return OpportunityCandidateType.NEEDS_VALIDATION
        return OpportunityCandidateType.INSUFFICIENT_EVIDENCE

    @staticmethod
    def confidence(
        *,
        demand_status: OpportunityEvidenceStatus,
        demand_reliability: OpportunityConfidence,
        supply_status: OpportunityEvidenceStatus,
        supply_reliability: OpportunityConfidence,
        gap_status: OpportunityEvidenceStatus,
        gap_reliability: OpportunityConfidence,
        competition_status: OpportunityEvidenceStatus,
        economic_status: OpportunityEvidenceStatus,
    ) -> OpportunityConfidence:
        if (
            OpportunityEvidenceStatus.UNKNOWN in {demand_status, supply_status, gap_status}
            or OpportunityConfidence.UNKNOWN
            in {demand_reliability, supply_reliability, gap_reliability}
        ):
            return OpportunityConfidence.UNKNOWN
        if (
            competition_status is OpportunityEvidenceStatus.UNKNOWN
            or economic_status is OpportunityEvidenceStatus.UNKNOWN
            or OpportunityConfidence.LOW
            in {demand_reliability, supply_reliability, gap_reliability}
        ):
            return OpportunityConfidence.LOW
        if (
            OpportunityEvidenceStatus.PARTIAL
            in {demand_status, supply_status, gap_status, competition_status, economic_status}
            or OpportunityConfidence.MEDIUM
            in {demand_reliability, supply_reliability, gap_reliability}
        ):
            return OpportunityConfidence.MEDIUM
        return OpportunityConfidence.HIGH


__all__ = ("OpportunityCandidateClassifierV0_1",)
