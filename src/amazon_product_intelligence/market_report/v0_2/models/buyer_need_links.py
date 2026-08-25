"""Typed one-way Buyer Need cross-links for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import (
    BUYER_NEED_LINK_CONTRACT_VERSION,
    BUYER_NEED_LINK_SECTION_CONTRACT_VERSION,
)
from .common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    ReferenceKind,
    V0_2Contract,
    identity,
    normalize_references,
    policy_pair,
    text,
    texts,
    validate_registered_references,
)
from .metric_context import ConfidenceContext


class BuyerNeedLinkType(StrEnum):
    EVIDENCE_CONTEXT = "EVIDENCE_CONTEXT"
    COMPETITOR_CONTEXT = "COMPETITOR_CONTEXT"
    DISTRIBUTION_CONTEXT = "DISTRIBUTION_CONTEXT"
    MULTI_SOURCE_CONTEXT = "MULTI_SOURCE_CONTEXT"
    EXTERNAL_DEMAND_SUPPLY_GAP = "EXTERNAL_DEMAND_SUPPLY_GAP"


class GovernedNeedCoverageState(StrEnum):
    COVERED = "COVERED"
    PARTIALLY_COVERED = "PARTIALLY_COVERED"
    NOT_COVERED = "NOT_COVERED"
    UNKNOWN = "UNKNOWN"


_UNAUTHORIZED_INFERENCE = re.compile(r"(?:SATISF|UNMET|GAP)", re.IGNORECASE)
_UNSAFE_REFERENCE = re.compile(
    r"(?:raw_payload|authorization|api[_-]?key|access[_-]?token|credential|secret|file://|^[A-Za-z]:[\\/]|/tmp/)",
    re.IGNORECASE,
)


def validate_sp039d_reference_safety(
    references: tuple[ContractReference, ...], path: str
) -> None:
    for reference in references:
        material = " ".join(
            value
            for value in (
                reference.namespace,
                reference.target_id,
                reference.target_version,
                reference.content_fingerprint,
            )
            if value is not None
        )
        if _UNSAFE_REFERENCE.search(material):
            raise MarketReportV0_2ValidationError(
                f"{path} contains runtime, raw-payload, or credential reference material"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedLink(V0_2Contract):
    link_id: str
    contract_version: str
    link_type: BuyerNeedLinkType
    reason_code: str
    reason_code_policy_id: str
    reason_code_policy_version: str
    need_id: str
    evidence_subject_reference_ids: tuple[str, ...]
    competitor_disposition_reference_ids: tuple[str, ...]
    competitor_detail_reference_ids: tuple[str, ...]
    distribution_reference_ids: tuple[str, ...]
    external_gap_reference_ids: tuple[str, ...]
    coverage_state: GovernedNeedCoverageState | None
    coverage_authority_id: str | None
    coverage_authority_version: str | None
    confidence: ConfidenceContext | None
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != BUYER_NEED_LINK_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported Buyer Need link contract version"
            )
        if not isinstance(self.link_type, BuyerNeedLinkType):
            raise MarketReportV0_2ValidationError("Buyer Need link type is invalid")
        text(self.reason_code, "BuyerNeedLink.reason_code")
        text(self.need_id, "BuyerNeedLink.need_id")
        policy_pair(
            self.reason_code_policy_id,
            self.reason_code_policy_version,
            "BuyerNeedLink.reason_code_policy",
            required=True,
        )
        policy_pair(
            self.coverage_authority_id,
            self.coverage_authority_version,
            "BuyerNeedLink.coverage_authority",
        )
        if self.coverage_state is not None:
            if not isinstance(self.coverage_state, GovernedNeedCoverageState):
                raise MarketReportV0_2ValidationError(
                    "Buyer Need coverage state is invalid"
                )
            policy_pair(
                self.coverage_authority_id,
                self.coverage_authority_version,
                "BuyerNeedLink.coverage_authority",
                required=True,
            )
        elif self.coverage_authority_id is not None:
            raise MarketReportV0_2ValidationError(
                "coverage authority cannot exist without a governed coverage state"
            )
        if (
            self.coverage_state is None
            and self.link_type is not BuyerNeedLinkType.EXTERNAL_DEMAND_SUPPLY_GAP
            and _UNAUTHORIZED_INFERENCE.search(self.reason_code)
        ):
            raise MarketReportV0_2ValidationError(
                "satisfaction/unmet/gap reason requires governed coverage authority"
            )
        if self.confidence is not None and not isinstance(
            self.confidence, ConfidenceContext
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link confidence is invalid"
            )

        collections = {}
        for name in (
            "evidence_subject_reference_ids",
            "competitor_disposition_reference_ids",
            "competitor_detail_reference_ids",
            "distribution_reference_ids",
            "external_gap_reference_ids",
        ):
            collections[name] = texts(
                getattr(self, name), f"BuyerNeedLink.{name}"
            )
        if not any(collections.values()):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link requires at least one governed target reference"
            )
        if (
            self.link_type is BuyerNeedLinkType.EXTERNAL_DEMAND_SUPPLY_GAP
            and not collections["external_gap_reference_ids"]
        ):
            raise MarketReportV0_2ValidationError(
                "external Demand-Supply Gap link requires an external reference"
            )
        if (
            self.link_type is not BuyerNeedLinkType.EXTERNAL_DEMAND_SUPPLY_GAP
            and collections["external_gap_reference_ids"]
        ):
            raise MarketReportV0_2ValidationError(
                "external gap references require the explicit external gap link type"
            )
        evidence = texts(self.evidence_ids, "BuyerNeedLink.evidence_ids")
        provenance = texts(
            self.provenance_reference_ids,
            "BuyerNeedLink.provenance_reference_ids",
            allow_empty=False,
        )
        limitations = texts(self.limitations, "BuyerNeedLink.limitations")
        for name, values in collections.items():
            object.__setattr__(self, name, values)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.link_id != identity(
            "market-report-v0.2-buyer-need-link", self, "link_id"
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link_id does not match content"
            )

    def semantic_key(self) -> tuple[Any, ...]:
        return (
            self.need_id,
            self.link_type.value,
            self.evidence_subject_reference_ids,
            self.competitor_disposition_reference_ids,
            self.competitor_detail_reference_ids,
            self.distribution_reference_ids,
            self.external_gap_reference_ids,
        )

    def referenced_contract_ids(self) -> tuple[str, ...]:
        return tuple(
            value
            for values in (
                self.evidence_subject_reference_ids,
                self.competitor_disposition_reference_ids,
                self.competitor_detail_reference_ids,
                self.distribution_reference_ids,
                self.external_gap_reference_ids,
            )
            for value in values
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedLinkSection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    scope_context_reference_id: str
    buyer_need_projection_reference_id: str
    link_authority_id: str | None
    link_authority_version: str | None
    reason_code_policy_id: str
    reason_code_policy_version: str
    declared_need_ids: tuple[str, ...]
    links: tuple[BuyerNeedLink, ...]
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != BUYER_NEED_LINK_SECTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported Buyer Need link section contract version"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link section availability is invalid"
            )
        text(self.scope_context_reference_id, "BuyerNeedLinkSection.scope")
        text(
            self.buyer_need_projection_reference_id,
            "BuyerNeedLinkSection.buyer_need_projection_reference_id",
        )
        policy_pair(
            self.link_authority_id,
            self.link_authority_version,
            "BuyerNeedLinkSection.link_authority",
        )
        policy_pair(
            self.reason_code_policy_id,
            self.reason_code_policy_version,
            "BuyerNeedLinkSection.reason_code_policy",
            required=True,
        )
        declared_need_ids = tuple(self.declared_need_ids)
        if any(
            type(item) is not str or not item.strip() for item in declared_need_ids
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link section declared need IDs require text"
            )
        if len(set(declared_need_ids)) != len(declared_need_ids):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link section declared need IDs must be unique"
            )
        links = tuple(
            sorted(
                self.links,
                key=lambda item: (
                    item.need_id,
                    item.link_type.value,
                    item.referenced_contract_ids(),
                    item.link_id,
                ),
            )
        )
        if any(not isinstance(item, BuyerNeedLink) for item in links):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link section contains an invalid link"
            )
        if len({item.link_id for item in links}) != len(links):
            raise MarketReportV0_2ValidationError("duplicate Buyer Need link IDs")
        if len({item.semantic_key() for item in links}) != len(links):
            raise MarketReportV0_2ValidationError(
                "duplicate semantic Buyer Need links"
            )
        orphan_needs = sorted(
            {item.need_id for item in links} - set(declared_need_ids)
        )
        if orphan_needs:
            raise MarketReportV0_2ValidationError(
                f"Buyer Need links contain orphan need IDs: {orphan_needs}"
            )
        if links and self.link_authority_id is None:
            raise MarketReportV0_2ValidationError(
                "published Buyer Need links require governed link authority"
            )
        if any(
            item.reason_code_policy_id != self.reason_code_policy_id
            or item.reason_code_policy_version != self.reason_code_policy_version
            for item in links
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link reason policy must match the section"
            )
        covered = {item.need_id for item in links}
        expected_availability = (
            Availability.UNAVAILABLE
            if not links
            else Availability.AVAILABLE
            if covered == set(declared_need_ids)
            else Availability.PARTIAL
        )
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "Buyer Need link availability does not match governed coverage"
            )
        references = normalize_references(
            self.references, "BuyerNeedLinkSection.references"
        )
        validate_sp039d_reference_safety(references, "BuyerNeedLinkSection")
        validate_registered_references(
            (
                self.scope_context_reference_id,
                self.buyer_need_projection_reference_id,
                *(value for item in links for value in item.referenced_contract_ids()),
            ),
            references,
            "BuyerNeedLinkSection",
        )
        external_ids = {
            value for item in links for value in item.external_gap_reference_ids
        }
        if any(
            reference.reference_id in external_ids
            and reference.kind is not ReferenceKind.EXTERNAL_PROVENANCE
            for reference in references
        ):
            raise MarketReportV0_2ValidationError(
                "Demand-Supply Gap references must use an external namespace"
            )
        provenance = texts(
            self.provenance_reference_ids,
            "BuyerNeedLinkSection.provenance_reference_ids",
            allow_empty=False,
        )
        required_provenance = {
            *(value for item in links for value in item.provenance_reference_ids),
            *(value for item in references for value in item.provenance_reference_ids),
        }
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link section omits link/reference provenance"
            )
        limitations = texts(
            self.limitations, "BuyerNeedLinkSection.limitations"
        )
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable Buyer Need links require limitations"
            )
        object.__setattr__(self, "declared_need_ids", declared_need_ids)
        object.__setattr__(self, "links", links)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity(
            "market-report-v0.2-buyer-need-links", self, "section_id"
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need link section_id does not match content"
            )


def build_buyer_need_link(**content: Any) -> BuyerNeedLink:
    normalized = dict(content)
    for name in (
        "evidence_subject_reference_ids",
        "competitor_disposition_reference_ids",
        "competitor_detail_reference_ids",
        "distribution_reference_ids",
        "external_gap_reference_ids",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {"contract_version": BUYER_NEED_LINK_CONTRACT_VERSION, **normalized}
    return BuyerNeedLink(
        link_id=deterministic_id("market-report-v0.2-buyer-need-link", material),
        **material,
    )


def build_buyer_need_link_section(**content: Any) -> BuyerNeedLinkSection:
    normalized = dict(content)
    if "links" in normalized:
        normalized["links"] = tuple(
            sorted(
                normalized["links"],
                key=lambda item: (
                    item.need_id,
                    item.link_type.value,
                    item.referenced_contract_ids(),
                    item.link_id,
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
        "contract_version": BUYER_NEED_LINK_SECTION_CONTRACT_VERSION,
        **normalized,
    }
    return BuyerNeedLinkSection(
        section_id=deterministic_id(
            "market-report-v0.2-buyer-need-links", material
        ),
        **material,
    )


__all__ = (
    "BuyerNeedLink",
    "BuyerNeedLinkSection",
    "BuyerNeedLinkType",
    "GovernedNeedCoverageState",
    "build_buyer_need_link",
    "build_buyer_need_link_section",
)
