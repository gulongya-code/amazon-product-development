"""Cross-reference-safe projection of governed Buyer Need links."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.buyer_need_links import (
    BuyerNeedLinkSection,
    BuyerNeedLinkType,
    GovernedNeedCoverageState,
    build_buyer_need_link,
    build_buyer_need_link_section,
)
from ..models.buyer_needs import BuyerNeedProjection
from ..models.common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    ReferenceKind,
)
from ..models.competitor_details import CompetitorDetailSection
from ..models.distributions import DistributionSectionItem
from ..models.metric_context import ConfidenceContext
from ..models.scope_context import ScopeContext
from ..models.true_competitor_set import TrueCompetitorSetSection


@dataclass(frozen=True, slots=True, kw_only=True)
class GovernedBuyerNeedLinkInput:
    """An upstream-authorized link; this adapter performs no inference."""

    link_type: BuyerNeedLinkType
    reason_code: str
    need_id: str
    evidence_subject_reference_ids: tuple[str, ...] = ()
    competitor_disposition_reference_ids: tuple[str, ...] = ()
    competitor_detail_reference_ids: tuple[str, ...] = ()
    distribution_reference_ids: tuple[str, ...] = ()
    external_gap_reference_ids: tuple[str, ...] = ()
    coverage_state: GovernedNeedCoverageState | None = None
    coverage_authority_id: str | None = None
    coverage_authority_version: str | None = None
    confidence: ConfidenceContext | None = None
    evidence_ids: tuple[str, ...] = ()
    provenance_reference_ids: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()


class BuyerNeedLinkAdapter:
    """Validate governed references without deciding need coverage or gaps."""

    def adapt(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        buyer_need_projection: BuyerNeedProjection,
        buyer_need_projection_reference: ContractReference,
        inputs: tuple[GovernedBuyerNeedLinkInput, ...],
        link_authority_id: str | None,
        link_authority_version: str | None,
        reason_code_policy_id: str,
        reason_code_policy_version: str,
        true_competitor_set: TrueCompetitorSetSection | None = None,
        competitor_detail_sections: tuple[CompetitorDetailSection, ...] = (),
        distributions: tuple[DistributionSectionItem, ...] = (),
        references: tuple[ContractReference, ...] = (),
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> BuyerNeedLinkSection:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "Buyer Need link scope reference does not match ScopeContext"
            )
        if not isinstance(buyer_need_projection, BuyerNeedProjection):
            raise TypeError("buyer_need_projection must be BuyerNeedProjection")
        if (
            buyer_need_projection_reference.kind is not ReferenceKind.REPORT_LOCAL
            or buyer_need_projection_reference.target_id
            != buyer_need_projection.projection_id
            or buyer_need_projection_reference.target_version
            != buyer_need_projection.contract_version
        ):
            raise MarketReportV0_2ValidationError(
                "Buyer Need projection reference is incompatible"
            )
        if any(not isinstance(item, GovernedBuyerNeedLinkInput) for item in inputs):
            raise TypeError("inputs must be GovernedBuyerNeedLinkInput records")
        if inputs and (
            link_authority_id is None or link_authority_version is None
        ):
            return self._unavailable(
                scope_reference=scope_reference,
                projection=buyer_need_projection,
                projection_reference=buyer_need_projection_reference,
                reason_code_policy_id=reason_code_policy_id,
                reason_code_policy_version=reason_code_policy_version,
                references=references,
                provenance_reference_ids=provenance_reference_ids,
                limitations=tuple(
                    sorted(
                        {
                            *limitations,
                            "governed Buyer Need link authority is unavailable",
                        }
                    )
                ),
            )

        for section in competitor_detail_sections:
            if section.scope_context_reference_id != scope_reference.reference_id:
                raise MarketReportV0_2ValidationError(
                    "competitor detail section belongs to another scope"
                )
        for distribution in distributions:
            if distribution.scope_context_reference_id != scope_reference.reference_id:
                raise MarketReportV0_2ValidationError(
                    "distribution belongs to another scope"
                )
        if (
            true_competitor_set is not None
            and true_competitor_set.scope_context_reference_id
            != scope_reference.reference_id
        ):
            raise MarketReportV0_2ValidationError(
                "True Competitor Set belongs to another scope"
            )

        registry_items = [
            *references,
            *scope_context.references,
            *buyer_need_projection.references,
            scope_reference,
            buyer_need_projection_reference,
            *(reference for section in competitor_detail_sections for reference in section.references),
            *(reference for item in distributions for reference in item.references),
            *(
                true_competitor_set.references
                if true_competitor_set is not None
                else ()
            ),
        ]
        registry = {
            item.reference_id: item for item in registry_items
        }
        disposition_ids = {
            item.disposition_id
            for item in (
                true_competitor_set.dispositions
                if true_competitor_set is not None
                else ()
            )
        }
        detail_ids = {
            record.record_id
            for section in competitor_detail_sections
            for record in section.records
        }
        distribution_ids = {
            value
            for item in distributions
            for value in (
                item.distribution_id,
                *(segment.segment_id for segment in item.segments),
            )
        }

        projected = []
        all_provenance = set(provenance_reference_ids)
        all_limitations = set(limitations)
        for item in inputs:
            self._validate_reference_targets(
                item.competitor_disposition_reference_ids,
                registry,
                disposition_ids,
                "competitor disposition",
            )
            self._validate_reference_targets(
                item.competitor_detail_reference_ids,
                registry,
                detail_ids,
                "competitor detail",
            )
            self._validate_reference_targets(
                item.distribution_reference_ids,
                registry,
                distribution_ids,
                "distribution/segment",
            )
            self._validate_reference_targets(
                item.evidence_subject_reference_ids,
                registry,
                None,
                "evidence subject",
            )
            self._validate_reference_targets(
                item.external_gap_reference_ids,
                registry,
                None,
                "external Demand-Supply Gap",
                external=True,
            )
            link = build_buyer_need_link(
                link_type=item.link_type,
                reason_code=item.reason_code,
                reason_code_policy_id=reason_code_policy_id,
                reason_code_policy_version=reason_code_policy_version,
                need_id=item.need_id,
                evidence_subject_reference_ids=item.evidence_subject_reference_ids,
                competitor_disposition_reference_ids=item.competitor_disposition_reference_ids,
                competitor_detail_reference_ids=item.competitor_detail_reference_ids,
                distribution_reference_ids=item.distribution_reference_ids,
                external_gap_reference_ids=item.external_gap_reference_ids,
                coverage_state=item.coverage_state,
                coverage_authority_id=item.coverage_authority_id,
                coverage_authority_version=item.coverage_authority_version,
                confidence=item.confidence,
                evidence_ids=item.evidence_ids,
                provenance_reference_ids=item.provenance_reference_ids,
                limitations=item.limitations,
            )
            projected.append(link)
            all_provenance.update(link.provenance_reference_ids)
            all_limitations.update(link.limitations)

        declared_need_ids = buyer_need_projection.source_need_order
        covered = {item.need_id for item in projected}
        availability = (
            Availability.UNAVAILABLE
            if not projected
            else Availability.AVAILABLE
            if covered == set(declared_need_ids)
            else Availability.PARTIAL
        )
        if availability is Availability.UNAVAILABLE:
            all_limitations.add("governed Buyer Need link evidence is unavailable")
        elif availability is Availability.PARTIAL:
            all_limitations.add("governed Buyer Need link coverage is incomplete")
        all_provenance.update(
            value for reference in registry.values() for value in reference.provenance_reference_ids
        )
        return build_buyer_need_link_section(
            availability=availability,
            scope_context_reference_id=scope_reference.reference_id,
            buyer_need_projection_reference_id=buyer_need_projection_reference.reference_id,
            link_authority_id=link_authority_id,
            link_authority_version=link_authority_version,
            reason_code_policy_id=reason_code_policy_id,
            reason_code_policy_version=reason_code_policy_version,
            declared_need_ids=declared_need_ids,
            links=tuple(projected),
            references=tuple(registry.values()),
            provenance_reference_ids=tuple(sorted(all_provenance)),
            limitations=tuple(sorted(all_limitations)),
        )

    @staticmethod
    def _validate_reference_targets(
        reference_ids: tuple[str, ...],
        registry: dict[str, ContractReference],
        allowed_target_ids: set[str] | None,
        label: str,
        *,
        external: bool = False,
    ) -> None:
        for reference_id in reference_ids:
            reference = registry.get(reference_id)
            if reference is None:
                raise MarketReportV0_2ValidationError(
                    f"orphan {label} reference: {reference_id}"
                )
            if allowed_target_ids is not None and reference.target_id not in allowed_target_ids:
                raise MarketReportV0_2ValidationError(
                    f"{label} reference does not resolve to the supplied graph"
                )
            if external and reference.kind is not ReferenceKind.EXTERNAL_PROVENANCE:
                raise MarketReportV0_2ValidationError(
                    f"{label} reference must use an external namespace"
                )

    def _unavailable(
        self,
        *,
        scope_reference: ContractReference,
        projection: BuyerNeedProjection,
        projection_reference: ContractReference,
        reason_code_policy_id: str,
        reason_code_policy_version: str,
        references: tuple[ContractReference, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...],
    ) -> BuyerNeedLinkSection:
        registry = {
            item.reference_id: item
            for item in (
                *references,
                *projection.references,
                scope_reference,
                projection_reference,
            )
        }
        provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *projection.provenance_reference_ids,
                    *(value for item in registry.values() for value in item.provenance_reference_ids),
                }
            )
        )
        return build_buyer_need_link_section(
            availability=Availability.UNAVAILABLE,
            scope_context_reference_id=scope_reference.reference_id,
            buyer_need_projection_reference_id=projection_reference.reference_id,
            link_authority_id=None,
            link_authority_version=None,
            reason_code_policy_id=reason_code_policy_id,
            reason_code_policy_version=reason_code_policy_version,
            declared_need_ids=projection.source_need_order,
            links=(),
            references=tuple(registry.values()),
            provenance_reference_ids=provenance,
            limitations=limitations,
        )


__all__ = ("BuyerNeedLinkAdapter", "GovernedBuyerNeedLinkInput")
