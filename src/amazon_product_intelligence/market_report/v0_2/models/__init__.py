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
from .competitor_details import (
    CompetitorDetailPurpose,
    CompetitorDetailRecord,
    CompetitorDetailSection,
    CompetitorFieldGroup,
    EvidenceAwareFieldProjection,
    build_competitor_detail_record,
    build_competitor_detail_section,
    build_field_projection,
)
from .distributions import (
    DistributionKind,
    DistributionMembershipMode,
    DistributionMetricName,
    DistributionSectionItem,
    DistributionSegment,
    MembershipDisclosure,
    SegmentClassification,
    build_distribution_section,
    build_distribution_segment,
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
    "CompetitorDetailPurpose",
    "CompetitorDetailRecord",
    "CompetitorDetailSection",
    "CompetitorFieldGroup",
    "ConfidenceContext",
    "ContractReference",
    "DuplicateControlStatus",
    "EvidenceSemantics",
    "EvidenceAwareFieldProjection",
    "DistributionKind",
    "DistributionMembershipMode",
    "DistributionMetricName",
    "DistributionSectionItem",
    "DistributionSegment",
    "MarketReportV0_2ValidationError",
    "MarketSizeSection",
    "MembershipDisclosure",
    "MetricContextEnvelope",
    "MetricSampleContext",
    "MetricValueType",
    "PresenceStatus",
    "ProductGrainV0_2",
    "ReferenceKind",
    "ScopeContext",
    "SegmentClassification",
    "TrueCompetitorSetSection",
    "build_competitor_disposition",
    "build_competitor_detail_record",
    "build_competitor_detail_section",
    "build_competitor_structure",
    "build_market_size_section",
    "build_distribution_section",
    "build_distribution_segment",
    "build_field_projection",
    "build_metric_context",
    "build_reference",
    "build_scope_context",
    "build_true_competitor_set",
    "unavailable_metric",
)
