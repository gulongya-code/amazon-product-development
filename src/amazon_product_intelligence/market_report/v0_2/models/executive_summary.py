"""Deterministic evidence-bound Executive Summary contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import EXECUTIVE_SUMMARY_CONTRACT_VERSION
from .common import (
    Availability,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    freeze_json,
    identity,
    optional_text,
    text,
    texts,
)


class ExecutiveClaimCategory(StrEnum):
    MARKET_CONTEXT = "MARKET_CONTEXT"
    COMPETITION = "COMPETITION"
    BUYER_NEED = "BUYER_NEED"
    PRODUCT_DIRECTION = "PRODUCT_DIRECTION"
    OPPORTUNITY = "OPPORTUNITY"
    EVIDENCE_GAP = "EVIDENCE_GAP"


EXECUTIVE_CLAIM_CATEGORY_ORDER = {
    ExecutiveClaimCategory.MARKET_CONTEXT: 10,
    ExecutiveClaimCategory.COMPETITION: 20,
    ExecutiveClaimCategory.BUYER_NEED: 30,
    ExecutiveClaimCategory.PRODUCT_DIRECTION: 40,
    ExecutiveClaimCategory.OPPORTUNITY: 50,
    ExecutiveClaimCategory.EVIDENCE_GAP: 60,
}

_FORBIDDEN_DECISION = re.compile(
    r"\b(winner|buy decision|launch decision|go/no-go|go decision|profitability)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutiveClaim(V0_2Contract):
    claim_id: str
    category: ExecutiveClaimCategory
    category_ordinal: int
    availability: Availability
    text: str | None
    typed_value: Any | None
    source_reference_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    confidence: str | None
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.category, ExecutiveClaimCategory):
            raise MarketReportV0_2ValidationError("Executive claim category is invalid")
        if self.category_ordinal != EXECUTIVE_CLAIM_CATEGORY_ORDER[self.category]:
            raise MarketReportV0_2ValidationError("Executive claim category ordinal is not governed")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("Executive claim availability is invalid")
        optional_text(self.text, "ExecutiveClaim.text")
        optional_text(self.confidence, "ExecutiveClaim.confidence")
        if self.text and _FORBIDDEN_DECISION.search(self.text):
            raise MarketReportV0_2ValidationError("Executive claim contains prohibited decision semantics")
        value = None if self.typed_value is None else freeze_json(self.typed_value, "ExecutiveClaim.typed_value")
        sources = texts(self.source_reference_ids, "Executive claim sources", allow_empty=False)
        evidence = texts(self.evidence_ids, "Executive claim evidence")
        provenance = texts(self.provenance_reference_ids, "Executive claim provenance", allow_empty=False)
        limitations = texts(self.limitations, "Executive claim limitations")
        if self.availability is Availability.AVAILABLE:
            if self.text is None and value is None:
                raise MarketReportV0_2ValidationError("available Executive claim requires text or typed value")
            if not evidence:
                raise MarketReportV0_2ValidationError("available Executive claim requires evidence")
        elif not limitations:
            raise MarketReportV0_2ValidationError("partial/unavailable Executive claim requires limitations")
        if self.availability is Availability.UNAVAILABLE and value is not None:
            raise MarketReportV0_2ValidationError("unavailable Executive claim cannot publish a value")
        object.__setattr__(self, "typed_value", value)
        object.__setattr__(self, "source_reference_ids", sources)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.claim_id != identity("market-report-v0.2-executive-claim", self, "claim_id"):
            raise MarketReportV0_2ValidationError("Executive claim_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutiveSummarySection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    claims: tuple[ExecutiveClaim, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != EXECUTIVE_SUMMARY_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported Executive Summary version")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("Executive Summary availability is invalid")
        claims = tuple(sorted(self.claims, key=lambda item: (item.category_ordinal, item.claim_id)))
        if any(not isinstance(item, ExecutiveClaim) for item in claims):
            raise MarketReportV0_2ValidationError("Executive Summary contains an invalid claim")
        if len({item.claim_id for item in claims}) != len(claims):
            raise MarketReportV0_2ValidationError("Executive claim IDs must be unique")
        provenance = texts(self.provenance_reference_ids, "Executive Summary provenance", allow_empty=False)
        if any(not set(item.provenance_reference_ids) <= set(provenance) for item in claims):
            raise MarketReportV0_2ValidationError("Executive Summary omits claim provenance")
        limitations = texts(self.limitations, "Executive Summary limitations")
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError("partial/unavailable Executive Summary requires limitations")
        if self.availability is Availability.AVAILABLE and any(item.availability is not Availability.AVAILABLE for item in claims):
            raise MarketReportV0_2ValidationError("Executive Summary cannot upgrade a partial/unavailable claim")
        object.__setattr__(self, "claims", claims)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity("market-report-v0.2-executive-summary", self, "section_id"):
            raise MarketReportV0_2ValidationError("Executive Summary section_id does not match content")


def build_executive_claim(**content: Any) -> ExecutiveClaim:
    normalized = dict(content)
    normalized["category_ordinal"] = EXECUTIVE_CLAIM_CATEGORY_ORDER[normalized["category"]]
    for name in ("source_reference_ids", "evidence_ids", "provenance_reference_ids", "limitations"):
        normalized[name] = tuple(sorted(normalized.get(name, ())))
    return ExecutiveClaim(
        claim_id=deterministic_id("market-report-v0.2-executive-claim", normalized),
        **normalized,
    )


def build_executive_summary(**content: Any) -> ExecutiveSummarySection:
    normalized = dict(content)
    normalized["claims"] = tuple(sorted(normalized.get("claims", ()), key=lambda item: (item.category_ordinal, item.claim_id)))
    normalized["provenance_reference_ids"] = tuple(sorted(normalized.get("provenance_reference_ids", ())))
    normalized["limitations"] = tuple(sorted(normalized.get("limitations", ())))
    material = {"contract_version": EXECUTIVE_SUMMARY_CONTRACT_VERSION, **normalized}
    return ExecutiveSummarySection(
        section_id=deterministic_id("market-report-v0.2-executive-summary", material),
        **material,
    )


__all__ = (
    "EXECUTIVE_CLAIM_CATEGORY_ORDER", "ExecutiveClaim", "ExecutiveClaimCategory",
    "ExecutiveSummarySection", "build_executive_claim", "build_executive_summary",
)
