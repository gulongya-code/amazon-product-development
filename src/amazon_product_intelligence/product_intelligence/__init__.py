"""Stable public API for Product Intelligence Foundation V0.1."""

from .builder_v0_1 import ProductIntelligenceBuilderV0_1
from .errors import (
    ProductIdentityCollisionError,
    ProductIntelligenceError,
    ProductIntelligenceValidationError,
    ProductSubjectNotFoundError,
    ProductTopologyError,
    SnapshotSerializationError,
)
from .models import (
    PRODUCT_INTELLIGENCE_RULESET_VERSION,
    EvidenceCandidate,
    EvidenceCoverageSummary,
    FactCandidateState,
    LineageReference,
    OutOfScopeObservationReference,
    ProductFactEvidenceSet,
    ProductIntelligenceDiagnostic,
    ProductIntelligenceRequest,
    ProductIntelligenceSnapshotV0_1,
    ProductMetricSeries,
    ProductScope,
    QualityIssueReference,
    ReviewEvidenceSummary,
    VariationEdge,
    VariationTopology,
)


__all__ = (
    "PRODUCT_INTELLIGENCE_RULESET_VERSION",
    "ProductScope",
    "FactCandidateState",
    "ProductIntelligenceRequest",
    "ProductIntelligenceSnapshotV0_1",
    "ProductIntelligenceBuilderV0_1",
    "ProductIntelligenceError",
    "ProductIntelligenceValidationError",
    "ProductSubjectNotFoundError",
    "ProductTopologyError",
    "ProductIdentityCollisionError",
    "SnapshotSerializationError",
    "EvidenceCandidate",
    "ProductFactEvidenceSet",
    "ProductMetricSeries",
    "VariationTopology",
    "VariationEdge",
    "ReviewEvidenceSummary",
    "EvidenceCoverageSummary",
    "LineageReference",
    "QualityIssueReference",
    "OutOfScopeObservationReference",
    "ProductIntelligenceDiagnostic",
)
