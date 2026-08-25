"""Read-only projection of an already validated Buyer Need report."""

from __future__ import annotations

from amazon_product_intelligence.market_report.models import (
    BuyerNeedReportSection,
    ReportAvailability,
)

from ..models.buyer_needs import BuyerNeedProjection, build_buyer_need_projection
from ..models.common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    ReferenceKind,
)


class BuyerNeedProjectionAdapter:
    """Preserve source identity, order, labels, shares, and evidence unchanged."""

    def adapt(
        self,
        *,
        source_section: BuyerNeedReportSection,
        source_reference: ContractReference,
        source_contract_version: str,
        required_intent_ruleset_version: str,
        required_taxonomy_version: str,
        required_validation_status: str,
        source_validation_fingerprint: str,
        query_intent_ruleset_fingerprint: str,
        taxonomy_fingerprint: str,
        semantic_normalization_version: str,
        semantic_normalization_fingerprint: str,
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> BuyerNeedProjection:
        if not isinstance(source_section, BuyerNeedReportSection):
            raise TypeError("source_section must be BuyerNeedReportSection")
        if not isinstance(source_reference, ContractReference):
            raise TypeError("source_reference must be ContractReference")
        if source_reference.kind is not ReferenceKind.EXTERNAL_PROVENANCE:
            raise MarketReportV0_2ValidationError(
                "Buyer Need source must use an external provenance reference"
            )
        if source_section.validation_status != required_validation_status:
            raise MarketReportV0_2ValidationError(
                "Buyer Need source validation status is incompatible"
            )
        if (
            source_section.intent_ruleset_version
            != required_intent_ruleset_version
            or source_section.taxonomy_version != required_taxonomy_version
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need source ruleset/taxonomy version is incompatible"
            )
        if (
            source_reference.target_id != source_section.source_record_id
            or source_reference.target_version != source_contract_version
            or source_reference.content_fingerprint != source_validation_fingerprint
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need source reference does not match source identity"
            )
        if not source_section.needs:
            raise MarketReportV0_2ValidationError(
                "Buyer Need source must contain governed need records"
            )
        need_ids = tuple(item.need_id for item in source_section.needs)
        if len(set(need_ids)) != len(need_ids):
            raise MarketReportV0_2ValidationError(
                "Buyer Need source contains duplicate need identity"
            )
        states = {item.availability for item in source_section.needs}
        availability = (
            Availability.AVAILABLE
            if states == {ReportAvailability.AVAILABLE}
            else Availability.UNAVAILABLE
            if states == {ReportAvailability.UNAVAILABLE}
            else Availability.PARTIAL
        )
        combined_provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *source_section.provenance_reference_ids,
                    *source_reference.provenance_reference_ids,
                }
            )
        )
        combined_limitations = tuple(
            sorted({*limitations, *source_section.limitations})
        )
        return build_buyer_need_projection(
            availability=availability,
            source_contract_version=source_contract_version,
            source_report_reference_id=source_reference.reference_id,
            source_validation_fingerprint=source_validation_fingerprint,
            query_intent_ruleset_fingerprint=query_intent_ruleset_fingerprint,
            taxonomy_fingerprint=taxonomy_fingerprint,
            semantic_normalization_version=semantic_normalization_version,
            semantic_normalization_fingerprint=semantic_normalization_fingerprint,
            source_need_order=need_ids,
            source_section=source_section,
            references=(source_reference,),
            provenance_reference_ids=combined_provenance,
            limitations=combined_limitations,
        )


__all__ = ("BuyerNeedProjectionAdapter",)
