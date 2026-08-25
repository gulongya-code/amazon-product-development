"""Frozen-semantics Buyer Need projection for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import (
    BuyerNeedReportSection,
    ReportAvailability,
)

from ..version import BUYER_NEED_PROJECTION_CONTRACT_VERSION
from .common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    identity,
    normalize_references,
    text,
    texts,
    validate_registered_references,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedProjection(V0_2Contract):
    """A V0.2-owned reference boundary around unchanged V0.1 Buyer Need truth."""

    projection_id: str
    contract_version: str
    availability: Availability
    source_contract_version: str
    source_report_reference_id: str
    source_validation_fingerprint: str
    query_intent_ruleset_fingerprint: str
    taxonomy_fingerprint: str
    semantic_normalization_version: str
    semantic_normalization_fingerprint: str
    source_need_order: tuple[str, ...]
    source_section: BuyerNeedReportSection
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != BUYER_NEED_PROJECTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported Buyer Need projection contract version"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection availability is invalid"
            )
        if not isinstance(self.source_section, BuyerNeedReportSection):
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection requires a validated BuyerNeedReportSection"
            )
        for name in (
            "source_contract_version",
            "source_report_reference_id",
            "source_validation_fingerprint",
            "query_intent_ruleset_fingerprint",
            "taxonomy_fingerprint",
            "semantic_normalization_version",
            "semantic_normalization_fingerprint",
        ):
            text(getattr(self, name), f"BuyerNeedProjection.{name}")

        source_order = tuple(self.source_need_order)
        if any(type(item) is not str or not item.strip() for item in source_order):
            raise MarketReportV0_2ValidationError(
                "Buyer Need source order must contain non-empty need IDs"
            )
        if len(set(source_order)) != len(source_order):
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection contains duplicate source need identity"
            )
        actual_order = tuple(item.need_id for item in self.source_section.needs)
        if source_order != actual_order:
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection must preserve exact governed source ordering"
            )

        source_states = {item.availability for item in self.source_section.needs}
        expected_availability = (
            Availability.AVAILABLE
            if source_states == {ReportAvailability.AVAILABLE}
            else Availability.UNAVAILABLE
            if source_states == {ReportAvailability.UNAVAILABLE}
            else Availability.PARTIAL
        )
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection availability must equal the frozen source state"
            )

        references = normalize_references(
            self.references, "BuyerNeedProjection.references"
        )
        validate_registered_references(
            (self.source_report_reference_id,), references, "BuyerNeedProjection"
        )
        source_reference = next(
            item
            for item in references
            if item.reference_id == self.source_report_reference_id
        )
        if (
            source_reference.target_id != self.source_section.source_record_id
            or source_reference.target_version != self.source_contract_version
            or source_reference.content_fingerprint
            != self.source_validation_fingerprint
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need source reference version/fingerprint is incompatible"
            )

        provenance = texts(
            self.provenance_reference_ids,
            "BuyerNeedProjection.provenance_reference_ids",
            allow_empty=False,
        )
        required_provenance = {
            *self.source_section.provenance_reference_ids,
            *(value for item in references for value in item.provenance_reference_ids),
        }
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection omits source/reference provenance"
            )
        limitations = texts(
            self.limitations, "BuyerNeedProjection.limitations"
        )
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable Buyer Need projection requires limitations"
            )
        object.__setattr__(self, "source_need_order", source_order)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.projection_id != identity(
            "market-report-v0.2-buyer-need-projection", self, "projection_id"
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection_id does not match content"
            )


def build_buyer_need_projection(**content: Any) -> BuyerNeedProjection:
    normalized = dict(content)
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    for name in ("provenance_reference_ids", "limitations"):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {
        "contract_version": BUYER_NEED_PROJECTION_CONTRACT_VERSION,
        **normalized,
    }
    return BuyerNeedProjection(
        projection_id=deterministic_id(
            "market-report-v0.2-buyer-need-projection", material
        ),
        **material,
    )


__all__ = ("BuyerNeedProjection", "build_buyer_need_projection")
