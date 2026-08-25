"""Frozen-semantics Opportunity projection for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import OpportunityReportSection

from ..version import OPPORTUNITY_PROJECTION_CONTRACT_VERSION
from .common import (
    Availability,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    identity,
    text,
    texts,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityProjectionV0_2(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    source_contract_version: str
    source_reference_id: str
    source_section: OpportunityReportSection
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != OPPORTUNITY_PROJECTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported Opportunity projection version")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("Opportunity availability is invalid")
        text(self.source_contract_version, "Opportunity source contract version")
        text(self.source_reference_id, "Opportunity source reference")
        if not isinstance(self.source_section, OpportunityReportSection):
            raise MarketReportV0_2ValidationError("Opportunity source_section has a wrong type")
        if self.source_section.score_status == "PENDING_DATA":
            if self.source_section.score_value is not None:
                raise MarketReportV0_2ValidationError("PENDING_DATA Opportunity score must remain null")
            if self.availability is Availability.AVAILABLE:
                raise MarketReportV0_2ValidationError("PENDING_DATA Opportunity cannot be upgraded to AVAILABLE")
        elif self.source_section.score_value is None:
            raise MarketReportV0_2ValidationError("calculated Opportunity source requires its source value")
        provenance = texts(self.provenance_reference_ids, "Opportunity provenance", allow_empty=False)
        if not set(self.source_section.provenance_reference_ids) <= set(provenance):
            raise MarketReportV0_2ValidationError("Opportunity projection omits source provenance")
        limitations = texts(self.limitations, "Opportunity limitations")
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError("partial/unavailable Opportunity requires limitations")
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity("market-report-v0.2-opportunity", self, "section_id"):
            raise MarketReportV0_2ValidationError("Opportunity section_id does not match content")


def build_opportunity_projection(**content: Any) -> OpportunityProjectionV0_2:
    content["provenance_reference_ids"] = tuple(sorted(content["provenance_reference_ids"]))
    content["limitations"] = tuple(sorted(content["limitations"]))
    material = {"contract_version": OPPORTUNITY_PROJECTION_CONTRACT_VERSION, **content}
    return OpportunityProjectionV0_2(
        section_id=deterministic_id("market-report-v0.2-opportunity", material),
        **material,
    )


__all__ = ("OpportunityProjectionV0_2", "build_opportunity_projection")
