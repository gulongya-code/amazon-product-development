"""Projection of explicit, governed Competitor Shortlist selections."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    ReferenceKind,
)
from ..models.competitor_details import CompetitorDetailSection
from ..models.competitor_shortlist import (
    CompetitorShortlistSection,
    ReviewPriority,
    build_competitor_shortlist_item,
    build_competitor_shortlist_section,
)
from ..models.metric_context import MetricContextEnvelope
from ..models.product_directions import ProductDirectionSection
from ..models.scope_context import ScopeContext
from ..models.true_competitor_set import (
    CompetitorDispositionType,
    TrueCompetitorSetSection,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GovernedCompetitorShortlistInput:
    """A caller-selected review candidate; no ranking occurs in this adapter."""

    disposition_reference_id: str
    competitor_detail_reference_id: str
    selection_reason_codes: tuple[str, ...]
    product_direction_reference_ids: tuple[str, ...] = ()
    representative_metric_reference_ids: tuple[str, ...] = ()
    representative_evidence_reference_ids: tuple[str, ...] = ()
    review_priority: ReviewPriority = ReviewPriority.UNSPECIFIED
    evidence_ids: tuple[str, ...] = ()
    provenance_reference_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class CompetitorShortlistAdapter:
    """Validate human-review selections against SP-039B/C/D graph identity."""

    def adapt(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        true_competitor_set: TrueCompetitorSetSection,
        true_competitor_set_reference: ContractReference,
        competitor_detail_sections: tuple[CompetitorDetailSection, ...],
        inputs: tuple[GovernedCompetitorShortlistInput, ...],
        selection_authority_id: str | None,
        selection_authority_version: str | None,
        selection_reason_policy_id: str,
        selection_reason_policy_version: str,
        product_direction_section: ProductDirectionSection | None = None,
        metrics: tuple[MetricContextEnvelope, ...] = (),
        references: tuple[ContractReference, ...] = (),
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> CompetitorShortlistSection:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist scope reference does not match ScopeContext"
            )
        if (
            true_competitor_set_reference.kind is not ReferenceKind.REPORT_LOCAL
            or true_competitor_set_reference.target_id != true_competitor_set.set_id
            or true_competitor_set_reference.target_version
            != true_competitor_set.contract_version
        ):
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist set reference is incompatible"
            )
        if true_competitor_set.scope_context_reference_id != scope_reference.reference_id:
            raise MarketReportV0_2ValidationError(
                "Competitor Shortlist set belongs to another scope"
            )
        if any(not isinstance(item, GovernedCompetitorShortlistInput) for item in inputs):
            raise TypeError("inputs must be GovernedCompetitorShortlistInput records")
        for section in competitor_detail_sections:
            if section.scope_context_reference_id != scope_reference.reference_id:
                raise MarketReportV0_2ValidationError(
                    "Competitor Shortlist detail belongs to another scope"
                )

        registry_items = [
            *references,
            *scope_context.references,
            *true_competitor_set.references,
            scope_reference,
            true_competitor_set_reference,
            *(reference for section in competitor_detail_sections for reference in section.references),
            *(
                product_direction_section.references
                if product_direction_section is not None
                else ()
            ),
        ]
        registry = {item.reference_id: item for item in registry_items}
        if not inputs or selection_authority_id is None or selection_authority_version is None:
            reason = (
                "governed shortlist selections are unavailable"
                if not inputs
                else "governed shortlist authority is unavailable"
            )
            return self._unavailable(
                scope_reference=scope_reference,
                set_reference=true_competitor_set_reference,
                registry=registry,
                selection_reason_policy_id=selection_reason_policy_id,
                selection_reason_policy_version=selection_reason_policy_version,
                provenance_reference_ids=provenance_reference_ids,
                limitations=tuple(sorted({*limitations, reason})),
            )

        disposition_by_id = {
            item.disposition_id: item for item in true_competitor_set.dispositions
        }
        detail_by_id = {
            record.record_id: record
            for section in competitor_detail_sections
            for record in section.records
        }
        direction_ids = {
            item.direction_id
            for item in (
                product_direction_section.directions
                if product_direction_section is not None
                else ()
            )
        }
        metric_ids = {item.metric_id for item in metrics}
        projected = []
        all_provenance = set(provenance_reference_ids)
        all_limitations = set(limitations)
        for item in inputs:
            disposition_reference = registry.get(item.disposition_reference_id)
            disposition = (
                disposition_by_id.get(disposition_reference.target_id)
                if disposition_reference is not None
                else None
            )
            if disposition is None:
                raise MarketReportV0_2ValidationError(
                    "shortlist disposition reference does not resolve"
                )
            if disposition.disposition is CompetitorDispositionType.EXCLUDED:
                raise MarketReportV0_2ValidationError(
                    "EXCLUDED competitor cannot enter the shortlist"
                )
            detail_reference = registry.get(item.competitor_detail_reference_id)
            detail = (
                detail_by_id.get(detail_reference.target_id)
                if detail_reference is not None
                else None
            )
            if detail is None:
                raise MarketReportV0_2ValidationError(
                    "shortlist competitor detail reference does not resolve"
                )
            if (
                detail.grain_entity_reference_id
                != disposition.grain_entity_reference_id
                or detail.disposition_reference_id != item.disposition_reference_id
                or detail.disposition is not disposition.disposition
            ):
                raise MarketReportV0_2ValidationError(
                    "shortlist detail and disposition identify different competitors"
                )
            self._validate_targets(
                item.product_direction_reference_ids,
                registry,
                direction_ids,
                "Product Direction",
            )
            self._validate_targets(
                item.representative_metric_reference_ids,
                registry,
                metric_ids,
                "representative metric",
            )
            self._validate_targets(
                item.representative_evidence_reference_ids,
                registry,
                None,
                "representative evidence",
            )
            shortlist_item = build_competitor_shortlist_item(
                grain_entity_reference_id=disposition.grain_entity_reference_id,
                disposition_reference_id=item.disposition_reference_id,
                disposition=disposition.disposition,
                competitor_detail_reference_id=item.competitor_detail_reference_id,
                selection_reason_codes=item.selection_reason_codes,
                selection_reason_policy_id=selection_reason_policy_id,
                selection_reason_policy_version=selection_reason_policy_version,
                selection_authority_id=selection_authority_id,
                selection_authority_version=selection_authority_version,
                product_direction_reference_ids=item.product_direction_reference_ids,
                representative_metric_reference_ids=item.representative_metric_reference_ids,
                representative_evidence_reference_ids=item.representative_evidence_reference_ids,
                review_priority=item.review_priority,
                evidence_ids=item.evidence_ids,
                provenance_reference_ids=item.provenance_reference_ids,
                limitations=item.limitations,
            )
            projected.append(shortlist_item)
            all_provenance.update(shortlist_item.provenance_reference_ids)
            all_limitations.update(shortlist_item.limitations)

        availability = (
            Availability.PARTIAL
            if any(
                item.disposition is CompetitorDispositionType.REVIEW_REQUIRED
                or item.limitations
                for item in projected
            )
            else Availability.AVAILABLE
        )
        if availability is Availability.PARTIAL:
            all_limitations.add(
                "shortlist includes REVIEW_REQUIRED or otherwise limited candidates"
            )
        all_provenance.update(
            value for reference in registry.values() for value in reference.provenance_reference_ids
        )
        return build_competitor_shortlist_section(
            availability=availability,
            scope_context_reference_id=scope_reference.reference_id,
            true_competitor_set_reference_id=true_competitor_set_reference.reference_id,
            selection_authority_id=selection_authority_id,
            selection_authority_version=selection_authority_version,
            selection_reason_policy_id=selection_reason_policy_id,
            selection_reason_policy_version=selection_reason_policy_version,
            items=tuple(projected),
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
                    f"orphan shortlist {label} reference"
                )
            if allowed_target_ids is not None and reference.target_id not in allowed_target_ids:
                raise MarketReportV0_2ValidationError(
                    f"shortlist {label} reference does not resolve"
                )

    @staticmethod
    def _unavailable(
        *,
        scope_reference: ContractReference,
        set_reference: ContractReference,
        registry: dict[str, ContractReference],
        selection_reason_policy_id: str,
        selection_reason_policy_version: str,
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> CompetitorShortlistSection:
        provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *(value for item in registry.values() for value in item.provenance_reference_ids),
                }
            )
        )
        return build_competitor_shortlist_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=scope_reference.reference_id,
            true_competitor_set_reference_id=set_reference.reference_id,
            selection_authority_id=None,
            selection_authority_version=None,
            selection_reason_policy_id=selection_reason_policy_id,
            selection_reason_policy_version=selection_reason_policy_version,
            items=(),
            references=tuple(registry.values()),
            provenance_reference_ids=provenance,
            limitations=limitations,
        )


__all__ = ("CompetitorShortlistAdapter", "GovernedCompetitorShortlistInput")
