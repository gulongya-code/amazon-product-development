"""Read-only projection of stable V0.1 context values into V0.2 owners."""

from __future__ import annotations

from amazon_product_intelligence.market_report.models import (
    CategoryInformation,
    DataWindow,
    ReportAvailability,
    SampleInformation,
)

from ..models.report_context import (
    CategoryContextV0_2,
    DataWindowContextV0_2,
    SampleContextV0_2,
    build_category_context,
    build_data_window_context,
    build_sample_context,
)
from ..models.common import Availability, ContractReference, MarketReportV0_2ValidationError


_AVAILABILITY = {
    ReportAvailability.AVAILABLE: Availability.AVAILABLE,
    ReportAvailability.PARTIAL: Availability.PARTIAL,
    ReportAvailability.UNAVAILABLE: Availability.UNAVAILABLE,
}


class ReportContextAdapter:
    def category(self, source: CategoryInformation, *, source_reference: ContractReference) -> CategoryContextV0_2:
        if not isinstance(source, CategoryInformation):
            raise TypeError("source must be CategoryInformation")
        return build_category_context(
            category_name=source.category_name,
            marketplace=source.marketplace,
            scope=source.scope,
            source_reference_id=source_reference.reference_id,
            provenance_reference_ids=source.provenance_reference_ids,
        )

    def sample(
        self,
        source: SampleInformation,
        *,
        source_reference: ContractReference,
        analysis_cohort_reference: ContractReference,
    ) -> SampleContextV0_2:
        if not isinstance(source, SampleInformation):
            raise TypeError("source must be SampleInformation")
        if source.unique_asin_count > source.sample_size:
            raise MarketReportV0_2ValidationError("source sample violates cohort bounds")
        return build_sample_context(
            availability=_AVAILABILITY[source.availability],
            analysis_cohort_reference_id=analysis_cohort_reference.reference_id,
            sample_size=source.sample_size,
            unique_asin_count=source.unique_asin_count,
            provider_total=source.provider_total,
            asin_coverage=source.asin_coverage,
            source_reference_id=source_reference.reference_id,
            provenance_reference_ids=source.provenance_reference_ids,
            limitations=source.limitations,
        )

    def data_window(
        self,
        source: DataWindow,
        *,
        source_reference: ContractReference,
        retrieved_at: str | None = None,
    ) -> DataWindowContextV0_2:
        if not isinstance(source, DataWindow):
            raise TypeError("source must be DataWindow")
        return build_data_window_context(
            availability=_AVAILABILITY[source.availability],
            period=source.period,
            start_at=source.start_at,
            end_at=source.end_at,
            retrieved_at=retrieved_at,
            source_reference_id=source_reference.reference_id,
            provenance_reference_ids=source.provenance_reference_ids,
            limitations=source.limitations,
        )


__all__ = ("ReportContextAdapter",)
