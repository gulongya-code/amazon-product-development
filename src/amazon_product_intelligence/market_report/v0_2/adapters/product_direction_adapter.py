"""Data-gated projection of caller-governed Product Direction hypotheses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..models.buyer_need_links import BuyerNeedLinkSection
from ..models.common import (
    Availability,
    CompletenessStatus,
    ContractReference,
    MarketReportV0_2ValidationError,
    ReferenceKind,
)
from ..models.competitor_details import CompetitorDetailSection
from ..models.competitor_structure import CompetitorStructureSection
from ..models.distributions import DistributionSectionItem
from ..models.market_size import MarketSizeSection
from ..models.metric_context import (
    ConfidenceContext,
    MetricContextEnvelope,
    MetricValueType,
)
from ..models.product_directions import (
    ProductDirectionSection,
    ProductDirectionSemantic,
    build_product_direction,
    build_product_direction_section,
)
from ..models.scope_context import ScopeContext
from ..models.true_competitor_set import TrueCompetitorSetSection


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductDirectionMetricBoundary:
    cohort_reference_id: str | None
    denominator_reference_id: str | None
    period_reference_id: str | None
    currency: str | None


@dataclass(frozen=True, slots=True, kw_only=True)
class GovernedProductDirectionInput:
    """Explicit upstream proposal content; no configuration is generated here."""

    proposed_product_type: str
    proposed_configuration: Any
    buyer_need_link_reference_ids: tuple[str, ...]
    market_size_reference_ids: tuple[str, ...] = ()
    distribution_reference_ids: tuple[str, ...] = ()
    competitor_structure_reference_ids: tuple[str, ...] = ()
    competitor_detail_reference_ids: tuple[str, ...] = ()
    target_price_metric_reference_id: str | None = None
    direct_competitor_reference_ids: tuple[str, ...] = ()
    entry_rationale: str = ""
    rationale_reference_ids: tuple[str, ...] = ()
    validation_items: tuple[str, ...] = ()
    risk_reference_ids: tuple[str, ...] = ()
    confidence: ConfidenceContext | None = None
    evidence_ids: tuple[str, ...] = ()
    provenance_reference_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class ProductDirectionAdapter:
    """Validate proposal authority and evidence without generating decisions."""

    def adapt(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        buyer_need_links: BuyerNeedLinkSection,
        buyer_need_link_section_reference: ContractReference,
        inputs: tuple[GovernedProductDirectionInput, ...],
        proposal_authority_id: str | None,
        proposal_authority_version: str | None,
        target_price_boundary: ProductDirectionMetricBoundary | None = None,
        metrics: tuple[MetricContextEnvelope, ...] = (),
        market_size_sections: tuple[MarketSizeSection, ...] = (),
        distributions: tuple[DistributionSectionItem, ...] = (),
        competitor_structures: tuple[CompetitorStructureSection, ...] = (),
        competitor_detail_sections: tuple[CompetitorDetailSection, ...] = (),
        true_competitor_set: TrueCompetitorSetSection | None = None,
        references: tuple[ContractReference, ...] = (),
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> ProductDirectionSection:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "Product Direction scope reference does not match ScopeContext"
            )
        if (
            buyer_need_link_section_reference.kind is not ReferenceKind.REPORT_LOCAL
            or buyer_need_link_section_reference.target_id != buyer_need_links.section_id
            or buyer_need_link_section_reference.target_version
            != buyer_need_links.contract_version
        ):
            raise MarketReportV0_2ValidationError(
                "Product Direction Buyer Need link section reference is incompatible"
            )
        if buyer_need_links.scope_context_reference_id != scope_reference.reference_id:
            raise MarketReportV0_2ValidationError(
                "Product Direction Buyer Need links belong to another scope"
            )
        if any(not isinstance(item, GovernedProductDirectionInput) for item in inputs):
            raise TypeError("inputs must be GovernedProductDirectionInput records")

        registry_items = [
            *references,
            *scope_context.references,
            *buyer_need_links.references,
            scope_reference,
            buyer_need_link_section_reference,
            *(reference for item in market_size_sections for reference in item.references),
            *(reference for item in distributions for reference in item.references),
            *(reference for item in competitor_structures for reference in item.references),
            *(reference for section in competitor_detail_sections for reference in section.references),
            *(
                true_competitor_set.references
                if true_competitor_set is not None
                else ()
            ),
        ]
        registry = {item.reference_id: item for item in registry_items}
        if (
            not inputs
            or proposal_authority_id is None
            or proposal_authority_version is None
            or buyer_need_links.availability is Availability.UNAVAILABLE
        ):
            reason = (
                "governed proposal input is unavailable"
                if not inputs
                else "governed proposal authority is unavailable"
                if proposal_authority_id is None or proposal_authority_version is None
                else "Buyer Need links are unavailable"
            )
            return self._unavailable(
                scope_reference=scope_reference,
                link_section_reference=buyer_need_link_section_reference,
                registry=registry,
                provenance_reference_ids=(
                    *provenance_reference_ids,
                    *buyer_need_links.provenance_reference_ids,
                ),
                limitations=tuple(sorted({*limitations, reason})),
            )

        for item in (
            *market_size_sections,
            *distributions,
            *competitor_structures,
            *competitor_detail_sections,
        ):
            if item.scope_context_reference_id != scope_reference.reference_id:
                raise MarketReportV0_2ValidationError(
                    "Product Direction evidence belongs to another scope"
                )
        if (
            true_competitor_set is not None
            and true_competitor_set.scope_context_reference_id
            != scope_reference.reference_id
        ):
            raise MarketReportV0_2ValidationError(
                "Product Direction competitor set belongs to another scope"
            )

        allowed_targets = {
            "buyer_need": {item.link_id for item in buyer_need_links.links},
            "market_size": {item.section_id for item in market_size_sections},
            "distribution": {
                value
                for item in distributions
                for value in (
                    item.distribution_id,
                    *(segment.segment_id for segment in item.segments),
                )
            },
            "competitor_structure": {
                item.section_id for item in competitor_structures
            },
            "competitor_detail": {
                record.record_id
                for section in competitor_detail_sections
                for record in section.records
            },
            "competitor": {
                value
                for disposition in (
                    true_competitor_set.dispositions
                    if true_competitor_set is not None
                    else ()
                )
                for value in (
                    disposition.disposition_id,
                    disposition.grain_entity_reference_id,
                    *disposition.product_reference_ids,
                )
            },
        }
        metric_by_id = {item.metric_id: item for item in metrics}
        projected = []
        all_provenance = set(provenance_reference_ids)
        all_limitations = set(limitations)
        for item in inputs:
            for label, reference_ids in (
                ("buyer_need", item.buyer_need_link_reference_ids),
                ("market_size", item.market_size_reference_ids),
                ("distribution", item.distribution_reference_ids),
                ("competitor_structure", item.competitor_structure_reference_ids),
                ("competitor_detail", item.competitor_detail_reference_ids),
                ("competitor", item.direct_competitor_reference_ids),
            ):
                self._validate_targets(
                    reference_ids, registry, allowed_targets[label], label
                )
            self._validate_targets(
                item.rationale_reference_ids, registry, None, "rationale"
            )
            self._validate_targets(
                item.risk_reference_ids, registry, None, "risk"
            )
            target_price_reference_id = item.target_price_metric_reference_id
            item_limitations = set(item.limitations)
            if target_price_reference_id is not None:
                reference = registry.get(target_price_reference_id)
                metric = metric_by_id.get(reference.target_id) if reference else None
                incompatibility = self._target_price_incompatibility(
                    metric=metric,
                    scope=scope_context,
                    scope_reference=scope_reference,
                    boundary=target_price_boundary,
                )
                if incompatibility is not None:
                    target_price_reference_id = None
                    item_limitations.add(
                        f"target price unavailable: {incompatibility}"
                    )
            else:
                item_limitations.add(
                    "target price unavailable: governed compatible metric was not supplied"
                )
            availability = (
                Availability.AVAILABLE
                if target_price_reference_id is not None and not item_limitations
                else Availability.PARTIAL
            )
            direction = build_product_direction(
                availability=availability,
                proposal_semantic=ProductDirectionSemantic.HYPOTHESIS_FOR_VALIDATION,
                proposal_authority_id=proposal_authority_id,
                proposal_authority_version=proposal_authority_version,
                marketplace=scope_context.marketplace,
                scope_context_reference_id=scope_reference.reference_id,
                proposed_product_type=item.proposed_product_type,
                proposed_configuration=item.proposed_configuration,
                buyer_need_link_reference_ids=item.buyer_need_link_reference_ids,
                market_size_reference_ids=item.market_size_reference_ids,
                distribution_reference_ids=item.distribution_reference_ids,
                competitor_structure_reference_ids=item.competitor_structure_reference_ids,
                competitor_detail_reference_ids=item.competitor_detail_reference_ids,
                target_price_metric_reference_id=target_price_reference_id,
                direct_competitor_reference_ids=item.direct_competitor_reference_ids,
                entry_rationale=item.entry_rationale,
                rationale_reference_ids=item.rationale_reference_ids,
                validation_items=item.validation_items,
                risk_reference_ids=item.risk_reference_ids,
                confidence=item.confidence,
                evidence_ids=item.evidence_ids,
                provenance_reference_ids=item.provenance_reference_ids,
                limitations=tuple(sorted(item_limitations)),
            )
            projected.append(direction)
            all_provenance.update(direction.provenance_reference_ids)
            all_limitations.update(direction.limitations)

        states = {item.availability for item in projected}
        availability = (
            Availability.AVAILABLE
            if states == {Availability.AVAILABLE}
            else Availability.PARTIAL
        )
        all_provenance.update(
            value for reference in registry.values() for value in reference.provenance_reference_ids
        )
        return build_product_direction_section(
            availability=availability,
            scope_context_reference_id=scope_reference.reference_id,
            buyer_need_link_section_reference_id=buyer_need_link_section_reference.reference_id,
            proposal_authority_id=proposal_authority_id,
            proposal_authority_version=proposal_authority_version,
            directions=tuple(projected),
            references=tuple(registry.values()),
            provenance_reference_ids=tuple(sorted(all_provenance)),
            limitations=tuple(sorted(all_limitations)),
        )

    @staticmethod
    def _validate_targets(
        reference_ids: tuple[str, ...],
        registry: dict[str, ContractReference],
        allowed_target_ids: set[str] | None,
        label: str,
    ) -> None:
        for reference_id in reference_ids:
            reference = registry.get(reference_id)
            if reference is None:
                raise MarketReportV0_2ValidationError(
                    f"orphan Product Direction {label} reference"
                )
            if allowed_target_ids is not None and reference.target_id not in allowed_target_ids:
                raise MarketReportV0_2ValidationError(
                    f"Product Direction {label} reference does not resolve"
                )

    @staticmethod
    def _target_price_incompatibility(
        *,
        metric: MetricContextEnvelope | None,
        scope: ScopeContext,
        scope_reference: ContractReference,
        boundary: ProductDirectionMetricBoundary | None,
    ) -> str | None:
        if metric is None:
            return "metric reference does not resolve"
        if boundary is None:
            return "metric compatibility boundary was not supplied"
        if metric.metric_name != "target_price_band":
            return "metric semantic is not target_price_band"
        if metric.value_type not in {MetricValueType.RANGE, MetricValueType.MONEY}:
            return "metric value type is incompatible"
        if metric.marketplace != scope.marketplace:
            return "metric marketplace is incompatible"
        if metric.product_grain_reference_id != scope_reference.reference_id:
            return "metric product grain is incompatible"
        if metric.cohort_reference_id != boundary.cohort_reference_id:
            return "metric cohort is incompatible"
        if metric.denominator_reference_id != boundary.denominator_reference_id:
            return "metric denominator is incompatible"
        if metric.period_reference_id != boundary.period_reference_id:
            return "metric period/window is incompatible"
        if metric.currency != boundary.currency:
            return "metric currency is incompatible"
        if metric.availability is Availability.UNAVAILABLE:
            return "metric is unavailable"
        if metric.method_policy_id is None or metric.method_policy_version is None:
            return "metric lacks governed method policy"
        if metric.completeness in {
            CompletenessStatus.UNKNOWN,
            CompletenessStatus.UNRESOLVED,
        }:
            return "metric completeness is incompatible"
        return None

    @staticmethod
    def _unavailable(
        *,
        scope_reference: ContractReference,
        link_section_reference: ContractReference,
        registry: dict[str, ContractReference],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> ProductDirectionSection:
        provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *(value for item in registry.values() for value in item.provenance_reference_ids),
                }
            )
        )
        return build_product_direction_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=scope_reference.reference_id,
            buyer_need_link_section_reference_id=link_section_reference.reference_id,
            proposal_authority_id=None,
            proposal_authority_version=None,
            directions=(),
            references=tuple(registry.values()),
            provenance_reference_ids=provenance,
            limitations=limitations,
        )


__all__ = (
    "GovernedProductDirectionInput",
    "ProductDirectionAdapter",
    "ProductDirectionMetricBoundary",
)
