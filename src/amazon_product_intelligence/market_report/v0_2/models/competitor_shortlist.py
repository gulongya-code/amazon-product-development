"""Governed human-review Competitor Shortlist contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import (
    COMPETITOR_SHORTLIST_ITEM_CONTRACT_VERSION,
    COMPETITOR_SHORTLIST_SECTION_CONTRACT_VERSION,
)
from .buyer_need_links import validate_sp039d_reference_safety
from .common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    identity,
    normalize_references,
    policy_pair,
    text,
    texts,
    validate_registered_references,
)
from .true_competitor_set import CompetitorDispositionType


class ReviewPriority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNSPECIFIED = "UNSPECIFIED"


REVIEW_PRIORITY_ORDER = {
    ReviewPriority.HIGH: 0,
    ReviewPriority.MEDIUM: 1,
    ReviewPriority.LOW: 2,
    ReviewPriority.UNSPECIFIED: 3,
}


_FORBIDDEN_RANKING = re.compile(
    r"(?:WINNER|BEST_PRODUCT|LAUNCH|BUY|PROFITABLE|DESIRABILITY|OPPORTUNITY_RANK|MARKET_RANK|PROVIDER_RANK)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitorShortlistItem(V0_2Contract):
    item_id: str
    contract_version: str
    grain_entity_reference_id: str
    disposition_reference_id: str
    disposition: CompetitorDispositionType
    competitor_detail_reference_id: str
    selection_reason_codes: tuple[str, ...]
    selection_reason_policy_id: str
    selection_reason_policy_version: str
    selection_authority_id: str
    selection_authority_version: str
    product_direction_reference_ids: tuple[str, ...]
    representative_metric_reference_ids: tuple[str, ...]
    representative_evidence_reference_ids: tuple[str, ...]
    review_priority: ReviewPriority
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != COMPETITOR_SHORTLIST_ITEM_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported Competitor Shortlist item contract version"
            )
        for name in (
            "grain_entity_reference_id",
            "disposition_reference_id",
            "competitor_detail_reference_id",
        ):
            text(getattr(self, name), f"CompetitorShortlistItem.{name}")
        if self.disposition not in {
            CompetitorDispositionType.INCLUDED,
            CompetitorDispositionType.REVIEW_REQUIRED,
        }:
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist rejects EXCLUDED/invalid dispositions"
            )
        if not isinstance(self.review_priority, ReviewPriority):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist review priority is invalid"
            )
        policy_pair(
            self.selection_reason_policy_id,
            self.selection_reason_policy_version,
            "CompetitorShortlistItem.selection_reason_policy",
            required=True,
        )
        policy_pair(
            self.selection_authority_id,
            self.selection_authority_version,
            "CompetitorShortlistItem.selection_authority",
            required=True,
        )
        normalized = {}
        for name in (
            "selection_reason_codes",
            "product_direction_reference_ids",
            "representative_metric_reference_ids",
            "representative_evidence_reference_ids",
            "evidence_ids",
            "provenance_reference_ids",
            "limitations",
        ):
            normalized[name] = texts(
                getattr(self, name),
                f"CompetitorShortlistItem.{name}",
                allow_empty=name
                not in {
                    "selection_reason_codes",
                    "evidence_ids",
                    "provenance_reference_ids",
                },
            )
        if any(
            _FORBIDDEN_RANKING.search(code)
            for code in normalized["selection_reason_codes"]
        ):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist reason cannot encode ranking/decision semantics"
            )
        for name, values in normalized.items():
            object.__setattr__(self, name, values)
        if self.item_id != identity(
            "market-report-v0.2-competitor-shortlist-item", self, "item_id"
        ):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist item_id does not match content"
            )

    def referenced_contract_ids(self) -> tuple[str, ...]:
        return (
            self.grain_entity_reference_id,
            self.disposition_reference_id,
            self.competitor_detail_reference_id,
            *self.product_direction_reference_ids,
            *self.representative_metric_reference_ids,
            *self.representative_evidence_reference_ids,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitorShortlistSection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    scope_context_reference_id: str
    true_competitor_set_reference_id: str
    selection_authority_id: str | None
    selection_authority_version: str | None
    selection_reason_policy_id: str
    selection_reason_policy_version: str
    items: tuple[CompetitorShortlistItem, ...]
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != COMPETITOR_SHORTLIST_SECTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported Competitor Shortlist section contract version"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist availability is invalid"
            )
        text(self.scope_context_reference_id, "CompetitorShortlistSection.scope")
        text(
            self.true_competitor_set_reference_id,
            "CompetitorShortlistSection.true_competitor_set_reference_id",
        )
        policy_pair(
            self.selection_authority_id,
            self.selection_authority_version,
            "CompetitorShortlistSection.selection_authority",
        )
        policy_pair(
            self.selection_reason_policy_id,
            self.selection_reason_policy_version,
            "CompetitorShortlistSection.selection_reason_policy",
            required=True,
        )
        items = tuple(
            sorted(
                self.items,
                key=lambda item: (
                    REVIEW_PRIORITY_ORDER[item.review_priority],
                    item.grain_entity_reference_id,
                    item.item_id,
                ),
            )
        )
        if any(not isinstance(item, CompetitorShortlistItem) for item in items):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist contains an invalid item"
            )
        if len({item.item_id for item in items}) != len(items):
            raise MarketReportV0_2ValidationError(
                "duplicate Competitor Shortlist item IDs"
            )
        if len({item.grain_entity_reference_id for item in items}) != len(items):
            raise MarketReportV0_2ValidationError(
                "one competitor can appear only once in a shortlist"
            )
        if items and self.selection_authority_id is None:
            raise MarketReportV0_2ValidationError(
                "published Competitor Shortlist requires selection authority"
            )
        if any(
            item.selection_authority_id != self.selection_authority_id
            or item.selection_authority_version != self.selection_authority_version
            or item.selection_reason_policy_id != self.selection_reason_policy_id
            or item.selection_reason_policy_version
            != self.selection_reason_policy_version
            for item in items
        ):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist item policy/authority must match section"
            )
        expected_availability = (
            Availability.UNAVAILABLE
            if not items
            else Availability.PARTIAL
            if any(
                item.disposition is CompetitorDispositionType.REVIEW_REQUIRED
                or item.limitations
                for item in items
            )
            else Availability.AVAILABLE
        )
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist availability does not match items"
            )
        references = normalize_references(
            self.references, "CompetitorShortlistSection.references"
        )
        validate_sp039d_reference_safety(references, "CompetitorShortlistSection")
        validate_registered_references(
            (
                self.scope_context_reference_id,
                self.true_competitor_set_reference_id,
                *(value for item in items for value in item.referenced_contract_ids()),
            ),
            references,
            "CompetitorShortlistSection",
        )
        provenance = texts(
            self.provenance_reference_ids,
            "CompetitorShortlistSection.provenance_reference_ids",
            allow_empty=False,
        )
        required_provenance = {
            *(value for item in items for value in item.provenance_reference_ids),
            *(value for item in references for value in item.provenance_reference_ids),
        }
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist omits item/reference provenance"
            )
        limitations = texts(
            self.limitations, "CompetitorShortlistSection.limitations"
        )
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable Competitor Shortlist requires limitations"
            )
        object.__setattr__(self, "items", items)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity(
            "market-report-v0.2-competitor-shortlist", self, "section_id"
        ):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist section_id does not match content"
            )


def build_competitor_shortlist_item(**content: Any) -> CompetitorShortlistItem:
    normalized = dict(content)
    for name in (
        "selection_reason_codes",
        "product_direction_reference_ids",
        "representative_metric_reference_ids",
        "representative_evidence_reference_ids",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {
        "contract_version": COMPETITOR_SHORTLIST_ITEM_CONTRACT_VERSION,
        **normalized,
    }
    return CompetitorShortlistItem(
        item_id=deterministic_id(
            "market-report-v0.2-competitor-shortlist-item", material
        ),
        **material,
    )


def build_competitor_shortlist_section(**content: Any) -> CompetitorShortlistSection:
    normalized = dict(content)
    if "items" in normalized:
        normalized["items"] = tuple(
            sorted(
                normalized["items"],
                key=lambda item: (
                    REVIEW_PRIORITY_ORDER[item.review_priority],
                    item.grain_entity_reference_id,
                    item.item_id,
                ),
            )
        )
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    for name in ("provenance_reference_ids", "limitations"):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {
        "contract_version": COMPETITOR_SHORTLIST_SECTION_CONTRACT_VERSION,
        **normalized,
    }
    return CompetitorShortlistSection(
        section_id=deterministic_id(
            "market-report-v0.2-competitor-shortlist", material
        ),
        **material,
    )


__all__ = (
    "CompetitorShortlistItem",
    "CompetitorShortlistSection",
    "REVIEW_PRIORITY_ORDER",
    "ReviewPriority",
    "build_competitor_shortlist_item",
    "build_competitor_shortlist_section",
)
