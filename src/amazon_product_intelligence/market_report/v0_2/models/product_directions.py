"""Human-validation-only Product Direction contracts for Market Report V0.2."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import (
    PRODUCT_DIRECTION_CONTRACT_VERSION,
    PRODUCT_DIRECTION_SECTION_CONTRACT_VERSION,
)
from .buyer_need_links import validate_sp039d_reference_safety
from .common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    freeze_json,
    identity,
    normalize_references,
    optional_text,
    policy_pair,
    text,
    texts,
    validate_registered_references,
)
from .metric_context import ConfidenceContext


class ProductDirectionSemantic(StrEnum):
    HYPOTHESIS_FOR_VALIDATION = "HYPOTHESIS_FOR_VALIDATION"


_FORBIDDEN_DECISION = re.compile(
    r"\b(?:WINNER|BEST_PRODUCT|BUY|LAUNCH|GO|NO_GO|PROFITABLE|PROFITABILITY_RANK|DESIRABILITY_RANK|OPPORTUNITY_RANK)\b",
    re.IGNORECASE,
)


def _assert_hypothesis_text(value: Any, path: str) -> None:
    if isinstance(value, str):
        if _FORBIDDEN_DECISION.search(value):
            raise MarketReportV0_2ValidationError(
                f"{path} contains forbidden automatic decision/ranking semantics"
            )
    elif isinstance(value, Mapping):
        for key, item in value.items():
            _assert_hypothesis_text(key, f"{path}.key")
            _assert_hypothesis_text(item, f"{path}.{key}")
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            _assert_hypothesis_text(item, f"{path}[{index}]")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductDirection(V0_2Contract):
    direction_id: str
    contract_version: str
    availability: Availability
    proposal_semantic: ProductDirectionSemantic
    proposal_authority_id: str
    proposal_authority_version: str
    marketplace: str
    scope_context_reference_id: str
    proposed_product_type: str
    proposed_configuration: Any
    buyer_need_link_reference_ids: tuple[str, ...]
    market_size_reference_ids: tuple[str, ...]
    distribution_reference_ids: tuple[str, ...]
    competitor_structure_reference_ids: tuple[str, ...]
    competitor_detail_reference_ids: tuple[str, ...]
    target_price_metric_reference_id: str | None
    direct_competitor_reference_ids: tuple[str, ...]
    entry_rationale: str
    rationale_reference_ids: tuple[str, ...]
    validation_items: tuple[str, ...]
    risk_reference_ids: tuple[str, ...]
    confidence: ConfidenceContext | None
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != PRODUCT_DIRECTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported Product Direction contract version"
            )
        if self.availability not in {Availability.AVAILABLE, Availability.PARTIAL}:
            raise MarketReportV0_2ValidationError(
                "published Product Direction must be available or partial"
            )
        if (
            not isinstance(self.proposal_semantic, ProductDirectionSemantic)
            or self.proposal_semantic
            is not ProductDirectionSemantic.HYPOTHESIS_FOR_VALIDATION
        ):
            raise MarketReportV0_2ValidationError(
                "Product Direction semantic must be HYPOTHESIS_FOR_VALIDATION"
            )
        policy_pair(
            self.proposal_authority_id,
            self.proposal_authority_version,
            "ProductDirection.proposal_authority",
            required=True,
        )
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError(
                "Product Direction marketplace must be uppercase text"
            )
        text(self.scope_context_reference_id, "ProductDirection.scope")
        text(self.proposed_product_type, "ProductDirection.proposed_product_type")
        text(self.entry_rationale, "ProductDirection.entry_rationale")
        _assert_hypothesis_text(
            self.proposed_product_type, "ProductDirection.proposed_product_type"
        )
        _assert_hypothesis_text(
            self.entry_rationale, "ProductDirection.entry_rationale"
        )
        proposed_configuration = freeze_json(
            self.proposed_configuration, "ProductDirection.proposed_configuration"
        )
        if not isinstance(proposed_configuration, Mapping) or not proposed_configuration:
            raise MarketReportV0_2ValidationError(
                "Product Direction proposed configuration must be a non-empty object"
            )
        _assert_hypothesis_text(
            proposed_configuration, "ProductDirection.proposed_configuration"
        )
        optional_text(
            self.target_price_metric_reference_id,
            "ProductDirection.target_price_metric_reference_id",
        )
        if self.confidence is not None and not isinstance(
            self.confidence, ConfidenceContext
        ):
            raise MarketReportV0_2ValidationError(
                "Product Direction confidence is invalid"
            )
        normalized = {}
        for name in (
            "buyer_need_link_reference_ids",
            "market_size_reference_ids",
            "distribution_reference_ids",
            "competitor_structure_reference_ids",
            "competitor_detail_reference_ids",
            "direct_competitor_reference_ids",
            "rationale_reference_ids",
            "validation_items",
            "risk_reference_ids",
            "evidence_ids",
            "provenance_reference_ids",
            "limitations",
        ):
            normalized[name] = texts(
                getattr(self, name),
                f"ProductDirection.{name}",
                allow_empty=name
                not in {
                    "buyer_need_link_reference_ids",
                    "rationale_reference_ids",
                    "validation_items",
                    "evidence_ids",
                    "provenance_reference_ids",
                },
            )
        _assert_hypothesis_text(
            normalized["validation_items"], "ProductDirection.validation_items"
        )
        if (
            self.target_price_metric_reference_id is None
            and self.availability is Availability.AVAILABLE
        ):
            raise MarketReportV0_2ValidationError(
                "direction without governed target price must remain PARTIAL"
            )
        if self.availability is Availability.PARTIAL and not normalized["limitations"]:
            raise MarketReportV0_2ValidationError(
                "partial Product Direction requires limitations"
            )
        object.__setattr__(self, "proposed_configuration", proposed_configuration)
        for name, values in normalized.items():
            object.__setattr__(self, name, values)
        if self.direction_id != identity(
            "market-report-v0.2-product-direction", self, "direction_id"
        ):
            raise MarketReportV0_2ValidationError(
                "Product Direction direction_id does not match content"
            )

    def referenced_contract_ids(self) -> tuple[str, ...]:
        return tuple(
            value
            for values in (
                (self.scope_context_reference_id,),
                self.buyer_need_link_reference_ids,
                self.market_size_reference_ids,
                self.distribution_reference_ids,
                self.competitor_structure_reference_ids,
                self.competitor_detail_reference_ids,
                (
                    (self.target_price_metric_reference_id,)
                    if self.target_price_metric_reference_id is not None
                    else ()
                ),
                self.direct_competitor_reference_ids,
                self.rationale_reference_ids,
                self.risk_reference_ids,
            )
            for value in values
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductDirectionSection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    scope_context_reference_id: str
    buyer_need_link_section_reference_id: str
    proposal_authority_id: str | None
    proposal_authority_version: str | None
    directions: tuple[ProductDirection, ...]
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != PRODUCT_DIRECTION_SECTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported Product Direction section contract version"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "Product Direction section availability is invalid"
            )
        text(self.scope_context_reference_id, "ProductDirectionSection.scope")
        text(
            self.buyer_need_link_section_reference_id,
            "ProductDirectionSection.buyer_need_link_section_reference_id",
        )
        policy_pair(
            self.proposal_authority_id,
            self.proposal_authority_version,
            "ProductDirectionSection.proposal_authority",
        )
        directions = tuple(sorted(self.directions, key=lambda item: item.direction_id))
        if any(not isinstance(item, ProductDirection) for item in directions):
            raise MarketReportV0_2ValidationError(
                "Product Direction section contains an invalid item"
            )
        if len({item.direction_id for item in directions}) != len(directions):
            raise MarketReportV0_2ValidationError("duplicate Product Direction IDs")
        if directions and self.proposal_authority_id is None:
            raise MarketReportV0_2ValidationError(
                "published Product Directions require governed proposal authority"
            )
        if any(
            item.proposal_authority_id != self.proposal_authority_id
            or item.proposal_authority_version != self.proposal_authority_version
            or item.scope_context_reference_id != self.scope_context_reference_id
            for item in directions
        ):
            raise MarketReportV0_2ValidationError(
                "Product Direction authority/scope must match the section"
            )
        states = {item.availability for item in directions}
        expected_availability = (
            Availability.UNAVAILABLE
            if not directions
            else Availability.AVAILABLE
            if states == {Availability.AVAILABLE}
            else Availability.PARTIAL
        )
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "Product Direction section availability does not match items"
            )
        references = normalize_references(
            self.references, "ProductDirectionSection.references"
        )
        validate_sp039d_reference_safety(references, "ProductDirectionSection")
        validate_registered_references(
            (
                self.scope_context_reference_id,
                self.buyer_need_link_section_reference_id,
                *(value for item in directions for value in item.referenced_contract_ids()),
            ),
            references,
            "ProductDirectionSection",
        )
        provenance = texts(
            self.provenance_reference_ids,
            "ProductDirectionSection.provenance_reference_ids",
            allow_empty=False,
        )
        required_provenance = {
            *(value for item in directions for value in item.provenance_reference_ids),
            *(value for item in references for value in item.provenance_reference_ids),
        }
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "Product Direction section omits item/reference provenance"
            )
        limitations = texts(
            self.limitations, "ProductDirectionSection.limitations"
        )
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable Product Direction section requires limitations"
            )
        object.__setattr__(self, "directions", directions)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity(
            "market-report-v0.2-product-directions", self, "section_id"
        ):
            raise MarketReportV0_2ValidationError(
                "Product Direction section_id does not match content"
            )


def build_product_direction(**content: Any) -> ProductDirection:
    normalized = dict(content)
    for name in (
        "buyer_need_link_reference_ids",
        "market_size_reference_ids",
        "distribution_reference_ids",
        "competitor_structure_reference_ids",
        "competitor_detail_reference_ids",
        "direct_competitor_reference_ids",
        "rationale_reference_ids",
        "validation_items",
        "risk_reference_ids",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {"contract_version": PRODUCT_DIRECTION_CONTRACT_VERSION, **normalized}
    return ProductDirection(
        direction_id=deterministic_id(
            "market-report-v0.2-product-direction", material
        ),
        **material,
    )


def build_product_direction_section(**content: Any) -> ProductDirectionSection:
    normalized = dict(content)
    if "directions" in normalized:
        normalized["directions"] = tuple(
            sorted(normalized["directions"], key=lambda item: item.direction_id)
        )
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    for name in ("provenance_reference_ids", "limitations"):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {
        "contract_version": PRODUCT_DIRECTION_SECTION_CONTRACT_VERSION,
        **normalized,
    }
    return ProductDirectionSection(
        section_id=deterministic_id(
            "market-report-v0.2-product-directions", material
        ),
        **material,
    )


__all__ = (
    "ProductDirection",
    "ProductDirectionSection",
    "ProductDirectionSemantic",
    "build_product_direction",
    "build_product_direction_section",
)
