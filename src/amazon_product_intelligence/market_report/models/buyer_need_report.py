"""Buyer Need section contracts for Market Report V0.1."""

from __future__ import annotations

from dataclasses import dataclass

from amazon_product_intelligence.contracts import JsonContract

from .report_schema import (
    MarketReportValidationError,
    ReportAvailability,
    _share,
    _text,
    _texts,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedReportItem(JsonContract):
    need_id: str
    need_label: str
    share: float | None
    share_basis: str
    availability: ReportAvailability
    confidence: str
    validation_status: str
    evidence_count: int
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("need_id", "need_label", "share_basis", "confidence", "validation_status"):
            _text(getattr(self, name), f"BuyerNeedReportItem.{name}")
        if not isinstance(self.availability, ReportAvailability):
            raise MarketReportValidationError("Buyer Need availability is invalid")
        if self.share is not None:
            object.__setattr__(self, "share", _share(self.share, "Buyer Need share"))
        if self.availability is ReportAvailability.UNAVAILABLE and self.share is not None:
            raise MarketReportValidationError("unavailable Buyer Need cannot publish a share")
        if self.availability is not ReportAvailability.UNAVAILABLE and self.share is None:
            raise MarketReportValidationError("available/partial Buyer Need requires a share")
        if type(self.evidence_count) is not int or self.evidence_count < 1:
            raise MarketReportValidationError("Buyer Need evidence_count must be positive")
        evidence = _texts(self.evidence_ids, "Buyer Need evidence", allow_empty=False)
        refs = _texts(self.provenance_reference_ids, "Buyer Need provenance", allow_empty=False)
        limits = _texts(self.limitations, "Buyer Need limitations")
        if self.availability is not ReportAvailability.AVAILABLE and not limits:
            raise MarketReportValidationError("partial/unavailable Buyer Need requires limitations")
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", refs)
        object.__setattr__(self, "limitations", limits)


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedReportSection(JsonContract):
    source_record_id: str
    intent_ruleset_version: str
    taxonomy_version: str
    validation_status: str
    needs: tuple[BuyerNeedReportItem, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "source_record_id",
            "intent_ruleset_version",
            "taxonomy_version",
            "validation_status",
        ):
            _text(getattr(self, name), f"BuyerNeedReportSection.{name}")
        needs = tuple(
            sorted(
                self.needs,
                key=lambda item: (
                    item.share is None,
                    -(item.share or 0.0),
                    item.need_label.casefold(),
                    item.need_id,
                ),
            )
        )
        if not needs or any(not isinstance(item, BuyerNeedReportItem) for item in needs):
            raise MarketReportValidationError("Buyer Need report requires typed needs")
        if len({item.need_id for item in needs}) != len(needs):
            raise MarketReportValidationError("Buyer Need report contains duplicate need IDs")
        refs = _texts(self.provenance_reference_ids, "Buyer Need section provenance", allow_empty=False)
        if not all(set(item.provenance_reference_ids) <= set(refs) for item in needs):
            raise MarketReportValidationError("Buyer Need section omits item provenance")
        object.__setattr__(self, "needs", needs)
        object.__setattr__(self, "provenance_reference_ids", refs)
        object.__setattr__(self, "limitations", _texts(self.limitations, "Buyer Need section limitations"))


__all__ = ("BuyerNeedReportItem", "BuyerNeedReportSection")
