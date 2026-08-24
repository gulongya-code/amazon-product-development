"""Bounded projection of governed competitor-membership decisions."""

from __future__ import annotations

from dataclasses import dataclass

from ..models import (
    Availability,
    CompletenessStatus,
    CompetitorDispositionType,
    ContractReference,
    MarketReportV0_2ValidationError,
    ScopeContext,
    TrueCompetitorSetSection,
    build_competitor_disposition,
    build_true_competitor_set,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class GovernedDispositionInput:
    """An upstream-governed decision; this adapter does not classify products."""

    grain_entity_reference_id: str
    product_reference_ids: tuple[str, ...]
    disposition: CompetitorDispositionType
    reason_codes: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()


class TrueCompetitorSetAdapter:
    """Package explicit membership decisions without inventing membership logic."""

    def adapt(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        candidate_cohort_reference: ContractReference,
        dispositions: tuple[GovernedDispositionInput, ...],
        membership_authority_id: str | None,
        membership_authority_version: str | None,
        reason_code_policy_id: str,
        reason_code_policy_version: str,
        candidate_universe_completeness: CompletenessStatus,
        included_cohort_reference: ContractReference | None,
        included_denominator_reference: ContractReference | None,
        references: tuple[ContractReference, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> TrueCompetitorSetSection:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "scope reference target does not match ScopeContext"
            )
        if (
            candidate_cohort_reference.reference_id
            != scope_context.analysis_cohort_reference_id
        ):
            raise MarketReportV0_2ValidationError(
                "candidate cohort must be the exact scope analysis cohort"
            )
        if not isinstance(candidate_universe_completeness, CompletenessStatus):
            raise MarketReportV0_2ValidationError(
                "candidate universe completeness is invalid"
            )
        if any(not isinstance(item, GovernedDispositionInput) for item in dispositions):
            raise TypeError("dispositions must be GovernedDispositionInput records")

        final_inputs = tuple(
            item
            for item in dispositions
            if item.disposition
            in {CompetitorDispositionType.INCLUDED, CompetitorDispositionType.EXCLUDED}
        )
        if final_inputs and (
            membership_authority_id is None or membership_authority_version is None
        ):
            raise MarketReportV0_2ValidationError(
                "final competitor decisions require membership authority"
            )
        if scope_context.unsafe_aggregate_guard:
            if any(
                item.disposition is not CompetitorDispositionType.REVIEW_REQUIRED
                for item in dispositions
            ):
                raise MarketReportV0_2ValidationError(
                    "unsafe mixed scope cannot publish final competitor membership"
                )
            if candidate_universe_completeness is not CompletenessStatus.UNRESOLVED:
                raise MarketReportV0_2ValidationError(
                    "unsafe mixed scope requires unresolved candidate completeness"
                )

        projected = tuple(
            build_competitor_disposition(
                grain_entity_reference_id=item.grain_entity_reference_id,
                product_reference_ids=item.product_reference_ids,
                disposition=item.disposition,
                reason_codes=item.reason_codes,
                authority_id=(
                    membership_authority_id
                    if item.disposition is not CompetitorDispositionType.REVIEW_REQUIRED
                    else None
                ),
                authority_version=(
                    membership_authority_version
                    if item.disposition is not CompetitorDispositionType.REVIEW_REQUIRED
                    else None
                ),
                evidence_ids=item.evidence_ids,
                provenance_reference_ids=item.provenance_reference_ids,
                limitations=item.limitations,
            )
            for item in dispositions
        )
        included_count = sum(
            item.disposition is CompetitorDispositionType.INCLUDED for item in projected
        )
        excluded_count = sum(
            item.disposition is CompetitorDispositionType.EXCLUDED for item in projected
        )
        review_count = sum(
            item.disposition is CompetitorDispositionType.REVIEW_REQUIRED
            for item in projected
        )
        unsafe_guard = not (
            candidate_universe_completeness is CompletenessStatus.COMPLETE
            and review_count == 0
            and bool(projected)
        )
        downstream_ready = not unsafe_guard and included_count > 0
        if downstream_ready != (
            included_cohort_reference is not None
            and included_denominator_reference is not None
        ):
            raise MarketReportV0_2ValidationError(
                "included cohort/denominator references must exist exactly when downstream aggregates are safe"
            )
        availability = (
            Availability.UNAVAILABLE
            if not projected
            else Availability.AVAILABLE
            if not unsafe_guard and membership_authority_id is not None
            else Availability.PARTIAL
        )

        registry_items = [
            *references,
            *scope_context.references,
            scope_reference,
            candidate_cohort_reference,
        ]
        if included_cohort_reference is not None:
            registry_items.append(included_cohort_reference)
        if included_denominator_reference is not None:
            registry_items.append(included_denominator_reference)
        registry = tuple(
            {item.reference_id: item for item in registry_items}.values()
        )
        evidence = tuple(
            sorted({value for item in projected for value in item.evidence_ids})
        )
        provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *scope_context.provenance_reference_ids,
                    *(value for item in projected for value in item.provenance_reference_ids),
                    *(value for item in registry for value in item.provenance_reference_ids),
                }
            )
        )
        combined_limitations = tuple(
            sorted(
                {
                    *limitations,
                    *(value for item in projected for value in item.limitations),
                    *(scope_context.limitations if scope_context.unsafe_aggregate_guard else ()),
                }
            )
        )
        return build_true_competitor_set(
            availability=availability,
            scope_context_reference_id=scope_reference.reference_id,
            candidate_cohort_reference_id=candidate_cohort_reference.reference_id,
            product_grain_reference_id=scope_reference.reference_id,
            membership_authority_id=membership_authority_id,
            membership_authority_version=membership_authority_version,
            reason_code_policy_id=reason_code_policy_id,
            reason_code_policy_version=reason_code_policy_version,
            candidate_universe_completeness=candidate_universe_completeness,
            dispositions=projected,
            included_count=included_count,
            excluded_count=excluded_count,
            review_required_count=review_count,
            included_cohort_reference_id=(
                included_cohort_reference.reference_id
                if included_cohort_reference is not None
                else None
            ),
            included_denominator_reference_id=(
                included_denominator_reference.reference_id
                if included_denominator_reference is not None
                else None
            ),
            is_valid_empty=(
                bool(projected)
                and candidate_universe_completeness is CompletenessStatus.COMPLETE
                and included_count == 0
                and review_count == 0
                and excluded_count == len(projected)
                and membership_authority_id is not None
            ),
            unsafe_aggregate_guard=unsafe_guard,
            references=registry,
            evidence_ids=evidence,
            provenance_reference_ids=provenance,
            limitations=combined_limitations,
        )


__all__ = ("GovernedDispositionInput", "TrueCompetitorSetAdapter")
