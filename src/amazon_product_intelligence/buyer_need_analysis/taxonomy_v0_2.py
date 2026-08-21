"""Buyer Need Taxonomy V0.2 without changing replayable V0.1 semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from amazon_product_intelligence.contracts import JsonContract, deterministic_id

from .errors import BuyerNeedValidationError
from .models import (
    BUYER_NEED_TAXONOMY_VERSION,
    BuyerNeedEvidenceRequirement,
    BuyerNeedLabelStrategy,
    BuyerNeedMatchStrength,
    BuyerNeedTaxonomyEntry,
    BuyerNeedTaxonomyRegistry,
    BuyerNeedTextSourceType,
    BuyerNeedType,
)
from .models_v0_2 import BUYER_NEED_TAXONOMY_VERSION_V0_2
from .taxonomy import BUYER_NEED_TAXONOMY_V0_1


_BUYER_EXPRESSION_SOURCES = (
    BuyerNeedTextSourceType.SEARCH_TERM,
    BuyerNeedTextSourceType.REVIEW,
)


def _entry(
    *,
    need_type: BuyerNeedType,
    canonical_label: str,
    definition: str,
    patterns: tuple[str, ...],
    strength: BuyerNeedMatchStrength = BuyerNeedMatchStrength.EXPLICIT,
) -> BuyerNeedTaxonomyEntry:
    payload = {
        "need_type": need_type,
        "canonical_label": canonical_label,
        "definition": definition,
        "regex_patterns": tuple(sorted(patterns)),
        "applicable_source_types": tuple(
            sorted(_BUYER_EXPRESSION_SOURCES, key=lambda item: item.value)
        ),
        "match_strength": strength,
        "label_strategy": BuyerNeedLabelStrategy.CANONICAL,
        "evidence_requirement": BuyerNeedEvidenceRequirement.EXPLICIT_TEXT_SPAN,
    }
    return BuyerNeedTaxonomyEntry(
        taxonomy_need_id=deterministic_id("buyer-need-taxonomy-entry", payload),
        **payload,
    )


COLLAPSIBLE_STRUCTURE_ENTRY_V0_2 = _entry(
    need_type=BuyerNeedType.SPECIFICATION_PREFERENCE,
    canonical_label="compact size / collapsible structure",
    definition=(
        "The buyer explicitly searches for a collapsible dog bowl or water-bottle "
        "structure. This rule is limited to the dog travel water-bottle query scope."
    ),
    patterns=(
        r"\bcollapsible\s+(?:dog\s+)?(?:water\s+)?(?:bottles?|bowls?)\b",
    ),
)


INTEGRATED_BOWL_ENTRY_V0_2 = _entry(
    need_type=BuyerNeedType.ATTRIBUTE_NEED,
    canonical_label="Integrated Bowl",
    definition=(
        "The buyer explicitly requests a water bottle with an integrated built-in bowl."
    ),
    patterns=(r"\bbuilt[ -]?in\s+bowl\b",),
)


CRATE_COMPATIBILITY_EXPERIMENT_V0_2 = _entry(
    need_type=BuyerNeedType.COMPATIBILITY,
    canonical_label="compatibility requirement",
    definition=(
        "Experimental dog-crate compatibility expression supported by one audited ASIN; "
        "independent holdout confirmation is required."
    ),
    patterns=(
        r"\bdog\s+crate\s+water\s+bottle\b",
        r"\bwater\s+bottle\s+for\s+(?:a\s+)?dog\s+crate\b",
    ),
    strength=BuyerNeedMatchStrength.WEAK,
)


def build_buyer_need_taxonomy_v0_2() -> BuyerNeedTaxonomyRegistry:
    """Extend, rather than mutate, the immutable V0.1 registry."""

    entries = (
        *BUYER_NEED_TAXONOMY_V0_1.entries,
        COLLAPSIBLE_STRUCTURE_ENTRY_V0_2,
        INTEGRATED_BOWL_ENTRY_V0_2,
        CRATE_COMPATIBILITY_EXPERIMENT_V0_2,
    )
    payload = {
        "taxonomy_version": BUYER_NEED_TAXONOMY_VERSION_V0_2,
        "entries": tuple(sorted(entries, key=lambda item: item.taxonomy_need_id)),
    }
    return BuyerNeedTaxonomyRegistry(
        registry_id=deterministic_id("buyer-need-taxonomy", payload),
        **payload,
    )


BUYER_NEED_TAXONOMY_V0_2 = build_buyer_need_taxonomy_v0_2()


# These entries must only be evaluated when an explicit category scope is supplied.
BUYER_NEED_SCOPED_TAXONOMY_ENTRY_IDS_V0_2 = frozenset(
    {
        COLLAPSIBLE_STRUCTURE_ENTRY_V0_2.taxonomy_need_id,
        INTEGRATED_BOWL_ENTRY_V0_2.taxonomy_need_id,
        CRATE_COMPATIBILITY_EXPERIMENT_V0_2.taxonomy_need_id,
    }
)


class BuyerNeedTaxonomyProposalStatus(StrEnum):
    ACTIVE_EXPERIMENTAL = "ACTIVE_EXPERIMENTAL"
    PROPOSAL_ONLY = "PROPOSAL_ONLY"


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedTaxonomyProposal(JsonContract):
    proposal_id: str
    proposed_label: str
    need_type: BuyerNeedType
    status: BuyerNeedTaxonomyProposalStatus
    evidence_relation_count: int
    evidence_asin_count: int
    cohort_asin_count: int
    supporting_patterns: tuple[str, ...]
    holdout_required: bool
    active_taxonomy_need_id: str | None
    rationale: str
    target_taxonomy_version: str = BUYER_NEED_TAXONOMY_VERSION_V0_2

    def __post_init__(self) -> None:
        if type(self.proposed_label) is not str or not self.proposed_label.strip():
            raise BuyerNeedValidationError("taxonomy proposal requires a label")
        if not isinstance(self.need_type, BuyerNeedType) or self.need_type is BuyerNeedType.UNKNOWN:
            raise BuyerNeedValidationError("taxonomy proposal requires a concrete NeedType")
        if not isinstance(self.status, BuyerNeedTaxonomyProposalStatus):
            raise BuyerNeedValidationError("taxonomy proposal status is invalid")
        if (
            type(self.evidence_relation_count) is not int
            or type(self.evidence_asin_count) is not int
            or type(self.cohort_asin_count) is not int
            or self.evidence_relation_count <= 0
            or self.evidence_asin_count <= 0
            or self.cohort_asin_count < self.evidence_asin_count
        ):
            raise BuyerNeedValidationError("taxonomy proposal evidence counts are invalid")
        if not self.supporting_patterns or any(
            type(item) is not str or not item.strip() for item in self.supporting_patterns
        ):
            raise BuyerNeedValidationError("taxonomy proposal requires supporting patterns")
        if type(self.holdout_required) is not bool:
            raise BuyerNeedValidationError("taxonomy proposal holdout flag must be boolean")
        if self.status is BuyerNeedTaxonomyProposalStatus.ACTIVE_EXPERIMENTAL:
            if self.active_taxonomy_need_id is None:
                raise BuyerNeedValidationError("active experiment requires a taxonomy entry")
        elif self.active_taxonomy_need_id is not None:
            raise BuyerNeedValidationError("proposal-only metadata cannot claim an active entry")
        if type(self.rationale) is not str or not self.rationale.strip():
            raise BuyerNeedValidationError("taxonomy proposal requires rationale")
        if self.target_taxonomy_version != BUYER_NEED_TAXONOMY_VERSION_V0_2:
            raise BuyerNeedValidationError("taxonomy proposal version mismatch")
        payload: dict[str, Any] = self.to_dict()
        payload.pop("proposal_id")
        if self.proposal_id != deterministic_id("buyer-need-taxonomy-proposal", payload):
            raise BuyerNeedValidationError("taxonomy proposal ID does not match content")


def _proposal(**payload: Any) -> BuyerNeedTaxonomyProposal:
    return BuyerNeedTaxonomyProposal(
        proposal_id=deterministic_id("buyer-need-taxonomy-proposal", payload),
        **payload,
    )


CRATE_COMPATIBILITY_PROPOSAL_V0_2 = _proposal(
    proposed_label="dog crate compatibility",
    need_type=BuyerNeedType.COMPATIBILITY,
    status=BuyerNeedTaxonomyProposalStatus.ACTIVE_EXPERIMENTAL,
    evidence_relation_count=2,
    evidence_asin_count=1,
    cohort_asin_count=20,
    supporting_patterns=CRATE_COMPATIBILITY_EXPERIMENT_V0_2.regex_patterns,
    holdout_required=True,
    active_taxonomy_need_id=CRATE_COMPATIBILITY_EXPERIMENT_V0_2.taxonomy_need_id,
    rationale="One audited ASIN supports two word-order variants; confidence remains LOW.",
    target_taxonomy_version=BUYER_NEED_TAXONOMY_VERSION_V0_2,
)


INSULATED_TEMPERATURE_RETENTION_PROPOSAL_V0_2 = _proposal(
    proposed_label="Insulated / Temperature Retention",
    need_type=BuyerNeedType.SPECIFICATION_PREFERENCE,
    status=BuyerNeedTaxonomyProposalStatus.PROPOSAL_ONLY,
    evidence_relation_count=9,
    evidence_asin_count=7,
    cohort_asin_count=20,
    supporting_patterns=(
        r"\binsulated\s+(?:dog\s+)?water\s+bottle\b",
        r"\bwater\s+bottle\s+insulated\b",
    ),
    holdout_required=True,
    active_taxonomy_need_id=None,
    rationale=(
        "The 20-ASIN pilot contains a real signal, but branded and generic bottle queries "
        "make independent holdout confirmation necessary."
    ),
    target_taxonomy_version=BUYER_NEED_TAXONOMY_VERSION_V0_2,
)


BUYER_NEED_TAXONOMY_PROPOSALS_V0_2 = (
    CRATE_COMPATIBILITY_PROPOSAL_V0_2,
    INSULATED_TEMPERATURE_RETENTION_PROPOSAL_V0_2,
)


def get_buyer_need_taxonomy(version: str) -> BuyerNeedTaxonomyRegistry:
    """Select a taxonomy explicitly; V0.1 remains the default only in its legacy builder."""

    if version == BUYER_NEED_TAXONOMY_VERSION:
        return BUYER_NEED_TAXONOMY_V0_1
    if version == BUYER_NEED_TAXONOMY_VERSION_V0_2:
        return BUYER_NEED_TAXONOMY_V0_2
    raise BuyerNeedValidationError(f"unsupported Buyer Need taxonomy version: {version}")


__all__ = (
    "BUYER_NEED_SCOPED_TAXONOMY_ENTRY_IDS_V0_2",
    "BUYER_NEED_TAXONOMY_PROPOSALS_V0_2",
    "BUYER_NEED_TAXONOMY_V0_2",
    "COLLAPSIBLE_STRUCTURE_ENTRY_V0_2",
    "CRATE_COMPATIBILITY_EXPERIMENT_V0_2",
    "CRATE_COMPATIBILITY_PROPOSAL_V0_2",
    "INSULATED_TEMPERATURE_RETENTION_PROPOSAL_V0_2",
    "INTEGRATED_BOWL_ENTRY_V0_2",
    "BuyerNeedTaxonomyProposal",
    "BuyerNeedTaxonomyProposalStatus",
    "build_buyer_need_taxonomy_v0_2",
    "get_buyer_need_taxonomy",
)
