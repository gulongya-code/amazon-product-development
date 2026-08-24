"""Bounded adapters for explicit V0.2 analytical scope declarations."""

from __future__ import annotations

from amazon_product_intelligence.category_product_map import CategoryProductMapSnapshot
from amazon_product_intelligence.product_attribute_extraction import ProductGrain

from ..models import (
    CompletenessStatus,
    ContractReference,
    DuplicateControlStatus,
    MarketReportV0_2ValidationError,
    ProductGrainV0_2,
    ScopeContext,
    build_scope_context,
)


_GRAIN_MAP = {
    ProductGrain.CHILD_ASIN: ProductGrainV0_2.CHILD_ASIN,
    ProductGrain.PARENT_ASIN: ProductGrainV0_2.PARENT_ASIN,
    ProductGrain.PRODUCT_FAMILY: ProductGrainV0_2.PRODUCT_FAMILY,
}


class ScopeContextAdapter:
    """Project governed Category Product Map scope without topology inference."""

    def from_category_product_map(
        self,
        snapshot: CategoryProductMapSnapshot,
        *,
        category_reference: ContractReference,
        cohort_reference: ContractReference,
        duplicate_control_policy_id: str,
        duplicate_control_policy_version: str,
        aggregation_policy_id: str | None = None,
        aggregation_policy_version: str | None = None,
        family_relationship_evidence_ids: tuple[str, ...] = (),
        completeness: CompletenessStatus = CompletenessStatus.COMPLETE,
        unresolved_grain_entity_count: int = 0,
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> ScopeContext:
        if not isinstance(snapshot, CategoryProductMapSnapshot):
            raise TypeError("snapshot must be CategoryProductMapSnapshot")
        snapshot.validate()
        grain = _GRAIN_MAP[snapshot.product_grain]
        grain_ids = [item.grain_product_id for item in snapshot.included_products]
        if len(set(grain_ids)) != len(grain_ids):
            raise MarketReportV0_2ValidationError(
                "Category Product Map contains duplicate grain identities"
            )
        product_ids = [
            member.product_id
            for item in snapshot.included_products
            for member in item.member_product_identities
        ]
        if len(set(product_ids)) != len(product_ids):
            raise MarketReportV0_2ValidationError(
                "one Canonical ProductIdentity appears in multiple grain entities"
            )
        return build_scope_context(
            marketplace=snapshot.marketplace,
            category_reference_id=category_reference.reference_id,
            analysis_cohort_reference_id=cohort_reference.reference_id,
            product_grain=grain,
            aggregation_policy_id=aggregation_policy_id,
            aggregation_policy_version=aggregation_policy_version,
            family_relationship_evidence_ids=family_relationship_evidence_ids,
            duplicate_control_status=DuplicateControlStatus.APPLIED,
            duplicate_control_policy_id=duplicate_control_policy_id,
            duplicate_control_policy_version=duplicate_control_policy_version,
            completeness=completeness,
            included_grain_entity_count=len(snapshot.included_products),
            excluded_grain_entity_count=len(snapshot.excluded_products),
            unresolved_grain_entity_count=unresolved_grain_entity_count,
            unsafe_aggregate_guard=False,
            references=(category_reference, cohort_reference),
            provenance_reference_ids=provenance_reference_ids,
            limitations=limitations,
        )

    def mixed_unresolved(
        self,
        *,
        marketplace: str,
        category_reference: ContractReference,
        cohort_reference: ContractReference,
        included_grain_entity_count: int,
        excluded_grain_entity_count: int,
        unresolved_grain_entity_count: int,
        family_relationship_evidence_ids: tuple[str, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> ScopeContext:
        return build_scope_context(
            marketplace=marketplace,
            category_reference_id=category_reference.reference_id,
            analysis_cohort_reference_id=cohort_reference.reference_id,
            product_grain=ProductGrainV0_2.MIXED_UNRESOLVED,
            aggregation_policy_id=None,
            aggregation_policy_version=None,
            family_relationship_evidence_ids=family_relationship_evidence_ids,
            duplicate_control_status=DuplicateControlStatus.BLOCKED,
            duplicate_control_policy_id=None,
            duplicate_control_policy_version=None,
            completeness=CompletenessStatus.UNRESOLVED,
            included_grain_entity_count=included_grain_entity_count,
            excluded_grain_entity_count=excluded_grain_entity_count,
            unresolved_grain_entity_count=unresolved_grain_entity_count,
            unsafe_aggregate_guard=True,
            references=(category_reference, cohort_reference),
            provenance_reference_ids=provenance_reference_ids,
            limitations=limitations,
        )


__all__ = ("ScopeContextAdapter",)
