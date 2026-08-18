"""Stable public API for Competition Intelligence Foundation V0.1."""

from .builder_v0_1 import CompetitionIntelligenceBuilderV0_1
from .errors import (
    CompetitionIdentityCollisionError,
    CompetitionIntelligenceError,
    CompetitionIntelligenceValidationError,
    CompetitionSerializationError,
)
from .models import (
    COMPETITION_INTELLIGENCE_RULESET_VERSION,
    CompetitionCoverageSummary,
    CompetitionDiagnostic,
    CompetitionEvidenceGraph,
    CompetitionEvidenceGraphEdge,
    CompetitionEvidenceGraphNode,
    CompetitionIntelligenceRequest,
    CompetitionIntelligenceSnapshotV0_1,
    CompetitionKeywordEvidence,
    CompetitionLineageReference,
    CompetitionProductEvidence,
    CompetitionQualityIssueReference,
    CompetitionRelationshipEvidence,
    CompetitionSourceRecordType,
    CompetitionVariationEvidence,
    EvidenceClassification,
    EvidenceGraphEdgeType,
)


__all__ = (
    "COMPETITION_INTELLIGENCE_RULESET_VERSION",
    "CompetitionIntelligenceRequest",
    "CompetitionIntelligenceSnapshotV0_1",
    "CompetitionIntelligenceBuilderV0_1",
    "CompetitionIntelligenceError",
    "CompetitionIntelligenceValidationError",
    "CompetitionIdentityCollisionError",
    "CompetitionSerializationError",
    "EvidenceClassification",
    "EvidenceGraphEdgeType",
    "CompetitionSourceRecordType",
    "CompetitionProductEvidence",
    "CompetitionRelationshipEvidence",
    "CompetitionVariationEvidence",
    "CompetitionKeywordEvidence",
    "CompetitionEvidenceGraphNode",
    "CompetitionEvidenceGraphEdge",
    "CompetitionEvidenceGraph",
    "CompetitionCoverageSummary",
    "CompetitionLineageReference",
    "CompetitionQualityIssueReference",
    "CompetitionDiagnostic",
)
