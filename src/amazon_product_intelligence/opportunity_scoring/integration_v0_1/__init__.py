"""Public Candidate scoring integration API, isolated from legacy scoring."""

from .adapter import OpportunityScoreInputAdapter
from .evaluator import OpportunityScoreEvaluator
from .models import (
    OPPORTUNITY_SCORING_INTEGRATION_VERSION,
    EvidenceBasedOpportunityScore,
    OpportunityDimensionScore,
    OpportunityMetricScoreTrace,
    OpportunityScoreDimension,
    OpportunityScoreDimensionStatus,
    OpportunityScoreEvidenceReference,
    OpportunityScoreExplanation,
    OpportunityScoreMetricStatus,
    OpportunityScoreMissingDataPolicy,
    OpportunityScorePolicy,
    OpportunityScoreRoundingMode,
    OpportunityScoreRoundingPolicy,
    OpportunityScoreStatus,
    OpportunityScoreValidationContract,
    OpportunityScoringIntegrationError,
    OpportunityScoringIntegrationInput,
    OpportunityScoringIntegrationSerializationError,
    OpportunityScoringIntegrationValidationError,
    OpportunityScoringMetricInput,
)
from .policy import (
    EXPECTED_METRICS,
    OpportunityScorePolicyLoadError,
    OpportunityScorePolicyLoader,
    OpportunityScorePolicyValidator,
    calculate_policy_fingerprint,
)
from .scorer import (
    EvidenceBasedOpportunityScorerV0_1,
    OpportunityScoringIntegrationV0_1,
)
from .validation import OpportunityScoreValidationBuilder


__all__ = (
    "EXPECTED_METRICS",
    "OPPORTUNITY_SCORING_INTEGRATION_VERSION",
    "EvidenceBasedOpportunityScore",
    "EvidenceBasedOpportunityScorerV0_1",
    "OpportunityDimensionScore",
    "OpportunityMetricScoreTrace",
    "OpportunityScoreDimension",
    "OpportunityScoreDimensionStatus",
    "OpportunityScoreEvidenceReference",
    "OpportunityScoreEvaluator",
    "OpportunityScoreExplanation",
    "OpportunityScoreInputAdapter",
    "OpportunityScoreMetricStatus",
    "OpportunityScoreMissingDataPolicy",
    "OpportunityScorePolicy",
    "OpportunityScorePolicyLoadError",
    "OpportunityScorePolicyLoader",
    "OpportunityScorePolicyValidator",
    "OpportunityScoreRoundingMode",
    "OpportunityScoreRoundingPolicy",
    "OpportunityScoreStatus",
    "OpportunityScoreValidationBuilder",
    "OpportunityScoreValidationContract",
    "OpportunityScoringIntegrationError",
    "OpportunityScoringIntegrationInput",
    "OpportunityScoringIntegrationSerializationError",
    "OpportunityScoringIntegrationV0_1",
    "OpportunityScoringIntegrationValidationError",
    "OpportunityScoringMetricInput",
    "calculate_policy_fingerprint",
)
