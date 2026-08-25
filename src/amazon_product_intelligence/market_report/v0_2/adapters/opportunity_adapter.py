"""Opportunity V0.1-to-V0.2 copy boundary; never a score calculator."""

from __future__ import annotations

from amazon_product_intelligence.market_report.models import OpportunityReportSection

from ..models import Availability, ContractReference
from ..models.opportunity import OpportunityProjectionV0_2, build_opportunity_projection


class OpportunityProjectionAdapter:
    def adapt(
        self,
        source: OpportunityReportSection,
        *,
        source_contract_version: str,
        source_reference: ContractReference,
        limitations: tuple[str, ...] | None = None,
    ) -> OpportunityProjectionV0_2:
        if not isinstance(source, OpportunityReportSection):
            raise TypeError("source must be OpportunityReportSection")
        pending = source.score_status == "PENDING_DATA"
        source_limits = tuple(sorted(set(source.limitations)))
        projected_limits = tuple(sorted(set(limitations if limitations is not None else source_limits)))
        if pending and not projected_limits:
            projected_limits = ("Opportunity score is pending governed source data",)
        availability = (
            Availability.UNAVAILABLE
            if pending
            else Availability.PARTIAL
            if "PARTIAL" in source.score_status
            else Availability.AVAILABLE
        )
        return build_opportunity_projection(
            availability=availability,
            source_contract_version=source_contract_version,
            source_reference_id=source_reference.reference_id,
            source_section=source,
            provenance_reference_ids=source.provenance_reference_ids,
            limitations=projected_limits,
        )


__all__ = ("OpportunityProjectionAdapter",)
