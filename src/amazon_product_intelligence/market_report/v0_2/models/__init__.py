"""Public models for the isolated Market Report V0.2 foundation slice."""

from .common import (
    Availability,
    CompletenessStatus,
    ContractReference,
    EvidenceSemantics,
    MarketReportV0_2ValidationError,
    PresenceStatus,
    ReferenceKind,
    build_reference,
)
from .competitor_structure import (
    CompetitorStructureSection,
    build_competitor_structure,
)
from .market_size import MarketSizeSection, build_market_size_section
from .metric_context import (
    ConfidenceContext,
    MetricContextEnvelope,
    MetricSampleContext,
    MetricValueType,
    build_metric_context,
    unavailable_metric,
)
from .scope_context import (
    DuplicateControlStatus,
    ProductGrainV0_2,
    ScopeContext,
    build_scope_context,
)
from .true_competitor_set import (
    CompetitorDisposition,
    CompetitorDispositionType,
    TrueCompetitorSetSection,
    build_competitor_disposition,
    build_true_competitor_set,
)


__all__ = (
    "Availability",
    "CompletenessStatus",
    "CompetitorDisposition",
    "CompetitorDispositionType",
    "CompetitorStructureSection",
    "ConfidenceContext",
    "ContractReference",
    "DuplicateControlStatus",
    "EvidenceSemantics",
    "MarketReportV0_2ValidationError",
    "MarketSizeSection",
    "MetricContextEnvelope",
    "MetricSampleContext",
    "MetricValueType",
    "PresenceStatus",
    "ProductGrainV0_2",
    "ReferenceKind",
    "ScopeContext",
    "TrueCompetitorSetSection",
    "build_competitor_disposition",
    "build_competitor_structure",
    "build_market_size_section",
    "build_metric_context",
    "build_reference",
    "build_scope_context",
    "build_true_competitor_set",
    "unavailable_metric",
)
