"""Explicit analytical scope and product-grain contract for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import SCOPE_CONTEXT_CONTRACT_VERSION
from .common import (
    CompletenessStatus,
    ContractReference,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    count,
    identity,
    normalize_references,
    policy_pair,
    text,
    texts,
    validate_registered_references,
)


class ProductGrainV0_2(StrEnum):
    CHILD_ASIN = "CHILD_ASIN"
    PARENT_ASIN = "PARENT_ASIN"
    PRODUCT_FAMILY = "PRODUCT_FAMILY"
    MIXED_UNRESOLVED = "MIXED_UNRESOLVED"


class DuplicateControlStatus(StrEnum):
    APPLIED = "APPLIED"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True, slots=True, kw_only=True)
class ScopeContext(V0_2Contract):
    scope_context_id: str
    contract_version: str
    marketplace: str
    category_reference_id: str
    analysis_cohort_reference_id: str
    product_grain: ProductGrainV0_2
    aggregation_policy_id: str | None
    aggregation_policy_version: str | None
    family_relationship_evidence_ids: tuple[str, ...]
    duplicate_control_status: DuplicateControlStatus
    duplicate_control_policy_id: str | None
    duplicate_control_policy_version: str | None
    completeness: CompletenessStatus
    included_grain_entity_count: int
    excluded_grain_entity_count: int
    unresolved_grain_entity_count: int
    unsafe_aggregate_guard: bool
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != SCOPE_CONTEXT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported scope context version")
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError("scope marketplace must be uppercase text")
        text(self.category_reference_id, "ScopeContext.category_reference_id")
        text(self.analysis_cohort_reference_id, "ScopeContext.analysis_cohort_reference_id")
        if not isinstance(self.product_grain, ProductGrainV0_2):
            raise MarketReportV0_2ValidationError("scope product_grain is invalid")
        if not isinstance(self.duplicate_control_status, DuplicateControlStatus):
            raise MarketReportV0_2ValidationError("scope duplicate_control_status is invalid")
        if not isinstance(self.completeness, CompletenessStatus):
            raise MarketReportV0_2ValidationError("scope completeness is invalid")
        if type(self.unsafe_aggregate_guard) is not bool:
            raise MarketReportV0_2ValidationError("unsafe_aggregate_guard must be boolean")
        for name in (
            "included_grain_entity_count",
            "excluded_grain_entity_count",
            "unresolved_grain_entity_count",
        ):
            count(getattr(self, name), f"ScopeContext.{name}")

        aggregation_required = self.product_grain in {
            ProductGrainV0_2.PARENT_ASIN,
            ProductGrainV0_2.PRODUCT_FAMILY,
        }
        policy_pair(
            self.aggregation_policy_id,
            self.aggregation_policy_version,
            "ScopeContext.aggregation",
            required=aggregation_required,
        )
        family_evidence = texts(
            self.family_relationship_evidence_ids,
            "ScopeContext.family_relationship_evidence_ids",
            allow_empty=not aggregation_required,
        )
        duplicate_policy_required = self.duplicate_control_status is DuplicateControlStatus.APPLIED
        policy_pair(
            self.duplicate_control_policy_id,
            self.duplicate_control_policy_version,
            "ScopeContext.duplicate_control",
            required=duplicate_policy_required,
        )
        if self.duplicate_control_status is not DuplicateControlStatus.APPLIED and (
            self.duplicate_control_policy_id is not None
        ):
            raise MarketReportV0_2ValidationError(
                "non-applied duplicate control cannot claim an executing policy"
            )

        if self.product_grain is ProductGrainV0_2.CHILD_ASIN and (
            self.aggregation_policy_id is not None
        ):
            raise MarketReportV0_2ValidationError(
                "CHILD_ASIN scope cannot claim parent/family aggregation"
            )
        if self.product_grain is ProductGrainV0_2.MIXED_UNRESOLVED:
            if not self.unsafe_aggregate_guard:
                raise MarketReportV0_2ValidationError(
                    "MIXED_UNRESOLVED must block unsafe aggregates"
                )
            if self.completeness is not CompletenessStatus.UNRESOLVED:
                raise MarketReportV0_2ValidationError(
                    "MIXED_UNRESOLVED requires UNRESOLVED completeness"
                )
            if self.duplicate_control_status is not DuplicateControlStatus.BLOCKED:
                raise MarketReportV0_2ValidationError(
                    "MIXED_UNRESOLVED requires blocked duplicate control"
                )
            if self.aggregation_policy_id is not None:
                raise MarketReportV0_2ValidationError(
                    "MIXED_UNRESOLVED is not an aggregation policy"
                )
        elif self.unsafe_aggregate_guard:
            raise MarketReportV0_2ValidationError(
                "unsafe aggregate guard is reserved for MIXED_UNRESOLVED scope"
            )

        references = normalize_references(self.references, "ScopeContext.references")
        validate_registered_references(
            (self.category_reference_id, self.analysis_cohort_reference_id),
            references,
            "ScopeContext",
        )
        provenance = texts(
            self.provenance_reference_ids,
            "ScopeContext.provenance_reference_ids",
            allow_empty=False,
        )
        limitations = texts(self.limitations, "ScopeContext.limitations")
        if (
            self.completeness is not CompletenessStatus.COMPLETE
            or self.duplicate_control_status is not DuplicateControlStatus.APPLIED
        ) and not limitations:
            raise MarketReportV0_2ValidationError(
                "incomplete or duplicate-unsafe scope requires limitations"
            )
        reference_provenance = {
            value
            for reference in references
            for value in reference.provenance_reference_ids
        }
        if not reference_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "scope omits provenance used by contract references"
            )
        object.__setattr__(self, "family_relationship_evidence_ids", family_evidence)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.scope_context_id != identity(
            "market-report-v0.2-scope", self, "scope_context_id"
        ):
            raise MarketReportV0_2ValidationError(
                "scope_context_id does not match scope content"
            )


def build_scope_context(**content: Any) -> ScopeContext:
    normalized = dict(content)
    for name in (
        "family_relationship_evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    material = {"contract_version": SCOPE_CONTEXT_CONTRACT_VERSION, **normalized}
    return ScopeContext(
        scope_context_id=deterministic_id("market-report-v0.2-scope", material),
        **material,
    )


__all__ = (
    "DuplicateControlStatus",
    "ProductGrainV0_2",
    "ScopeContext",
    "build_scope_context",
)
