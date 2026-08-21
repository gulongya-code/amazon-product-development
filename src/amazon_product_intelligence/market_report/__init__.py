"""Stable public API for Market Report Pipeline Foundation V0.1."""

from .adapters import (
    BUYER_NEED_INTENT_STABLE_VERSION,
    BUYER_NEED_TAXONOMY_STABLE_VERSION,
    BuyerNeedReportAdapter,
    CompetitionReportAdapter,
    OpportunityReportAdapter,
)
from .builder import (
    MarketReportBuildRequest,
    MarketReportBuilderV0_1,
    MarketReportSectionBuilder,
)
from .models import (
    MARKET_REPORT_JSON_SCHEMA,
    MARKET_REPORT_VERSION,
    BuyerNeedReportItem,
    BuyerNeedReportSection,
    CategoryInformation,
    CompetitionMetric,
    CompetitionReportSection,
    DataWindow,
    MarketReportSnapshot,
    MarketReportValidationError,
    OpportunityDimensionReport,
    OpportunityReportSection,
    ProductAttributeDistributionReport,
    ProductAttributeValueReport,
    ProvenanceReference,
    ReportAvailability,
    SampleInformation,
    validate_market_report_payload,
)


__all__ = (
    "BUYER_NEED_INTENT_STABLE_VERSION",
    "BUYER_NEED_TAXONOMY_STABLE_VERSION",
    "MARKET_REPORT_JSON_SCHEMA",
    "MARKET_REPORT_VERSION",
    "BuyerNeedReportAdapter",
    "BuyerNeedReportItem",
    "BuyerNeedReportSection",
    "CategoryInformation",
    "CompetitionMetric",
    "CompetitionReportAdapter",
    "CompetitionReportSection",
    "DataWindow",
    "MarketReportBuildRequest",
    "MarketReportBuilderV0_1",
    "MarketReportSectionBuilder",
    "MarketReportSnapshot",
    "MarketReportValidationError",
    "OpportunityDimensionReport",
    "OpportunityReportAdapter",
    "OpportunityReportSection",
    "ProductAttributeDistributionReport",
    "ProductAttributeValueReport",
    "ProvenanceReference",
    "ReportAvailability",
    "SampleInformation",
    "validate_market_report_payload",
)
