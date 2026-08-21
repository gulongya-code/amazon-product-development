"""Real-data validation contract preparation for TASK-SP-031."""

from __future__ import annotations

from amazon_product_intelligence.contracts import deterministic_id

from .models import (
    OpportunityScoreDimension,
    OpportunityScoreMetricStatus,
    OpportunityScoreValidationContract,
    OpportunityScoringIntegrationInput,
)


class OpportunityScoreValidationBuilder:
    """Describe Candidate data/evidence coverage without changing a score."""

    def build(
        self, scoring_input: OpportunityScoringIntegrationInput
    ) -> OpportunityScoreValidationContract:
        if not isinstance(scoring_input, OpportunityScoringIntegrationInput):
            raise TypeError(
                "scoring_input must be OpportunityScoringIntegrationInput"
            )
        evidence_coverage: dict[str, str] = {}
        for dimension in OpportunityScoreDimension:
            statuses = {
                item.status
                for item in scoring_input.metrics
                if item.dimension is dimension
            }
            if statuses == {OpportunityScoreMetricStatus.AVAILABLE}:
                coverage = "AVAILABLE"
            elif statuses == {OpportunityScoreMetricStatus.UNKNOWN}:
                coverage = "UNKNOWN"
            else:
                coverage = "PARTIAL"
            evidence_coverage[dimension.value] = coverage
        metric_availability = {
            item.metric_id: item.status.value for item in scoring_input.metrics
        }
        limitations = tuple(
            sorted(
                {
                    *scoring_input.limitations,
                    *(
                        limitation
                        for item in scoring_input.metrics
                        for limitation in item.limitations
                    ),
                }
            )
        )
        material = {
            "category_scope": scoring_input.category_scope,
            "candidate_count": 1,
            "evidence_coverage": evidence_coverage,
            "metric_availability": metric_availability,
            "limitations": limitations,
        }
        return OpportunityScoreValidationContract(
            validation_contract_id=deterministic_id(
                "opportunity-score-validation", material
            ),
            **material,
        )


__all__ = ("OpportunityScoreValidationBuilder",)
