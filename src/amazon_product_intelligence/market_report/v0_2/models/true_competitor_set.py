"""Auditable market-level True Competitor disposition contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import TRUE_COMPETITOR_SET_CONTRACT_VERSION
from .common import (
    Availability,
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


class CompetitorDispositionType(StrEnum):
    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitorDisposition(V0_2Contract):
    disposition_id: str
    grain_entity_reference_id: str
    product_reference_ids: tuple[str, ...]
    disposition: CompetitorDispositionType
    reason_codes: tuple[str, ...]
    authority_id: str | None
    authority_version: str | None
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        text(
            self.grain_entity_reference_id,
            "CompetitorDisposition.grain_entity_reference_id",
        )
        products = texts(
            self.product_reference_ids,
            "CompetitorDisposition.product_reference_ids",
            allow_empty=False,
        )
        if not isinstance(self.disposition, CompetitorDispositionType):
            raise MarketReportV0_2ValidationError("competitor disposition is invalid")
        reasons = texts(
            self.reason_codes,
            "CompetitorDisposition.reason_codes",
            allow_empty=False,
        )
        final_decision = self.disposition in {
            CompetitorDispositionType.INCLUDED,
            CompetitorDispositionType.EXCLUDED,
        }
        policy_pair(
            self.authority_id,
            self.authority_version,
            "CompetitorDisposition.authority",
            required=final_decision,
        )
        evidence = texts(
            self.evidence_ids,
            "CompetitorDisposition.evidence_ids",
            allow_empty=False,
        )
        provenance = texts(
            self.provenance_reference_ids,
            "CompetitorDisposition.provenance_reference_ids",
            allow_empty=False,
        )
        limitations = texts(self.limitations, "CompetitorDisposition.limitations")
        if self.disposition is CompetitorDispositionType.REVIEW_REQUIRED and not limitations:
            raise MarketReportV0_2ValidationError(
                "REVIEW_REQUIRED disposition requires limitations"
            )
        object.__setattr__(self, "product_reference_ids", products)
        object.__setattr__(self, "reason_codes", reasons)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.disposition_id != identity(
            "market-report-v0.2-competitor-disposition",
            self,
            "disposition_id",
        ):
            raise MarketReportV0_2ValidationError(
                "disposition_id does not match disposition content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class TrueCompetitorSetSection(V0_2Contract):
    set_id: str
    contract_version: str
    availability: Availability
    scope_context_reference_id: str
    candidate_cohort_reference_id: str
    product_grain_reference_id: str
    membership_authority_id: str | None
    membership_authority_version: str | None
    reason_code_policy_id: str
    reason_code_policy_version: str
    candidate_universe_completeness: CompletenessStatus
    dispositions: tuple[CompetitorDisposition, ...]
    included_count: int
    excluded_count: int
    review_required_count: int
    included_cohort_reference_id: str | None
    included_denominator_reference_id: str | None
    is_valid_empty: bool
    unsafe_aggregate_guard: bool
    references: tuple[ContractReference, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != TRUE_COMPETITOR_SET_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported True Competitor Set contract version"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("True Competitor availability is invalid")
        for name in (
            "scope_context_reference_id",
            "candidate_cohort_reference_id",
            "product_grain_reference_id",
            "reason_code_policy_id",
            "reason_code_policy_version",
        ):
            text(getattr(self, name), f"TrueCompetitorSetSection.{name}")
        policy_pair(
            self.membership_authority_id,
            self.membership_authority_version,
            "TrueCompetitorSetSection.membership_authority",
        )
        policy_pair(
            self.reason_code_policy_id,
            self.reason_code_policy_version,
            "TrueCompetitorSetSection.reason_code_policy",
            required=True,
        )
        if not isinstance(self.candidate_universe_completeness, CompletenessStatus):
            raise MarketReportV0_2ValidationError(
                "candidate universe completeness is invalid"
            )
        for name in ("included_count", "excluded_count", "review_required_count"):
            count(getattr(self, name), f"TrueCompetitorSetSection.{name}")
        if type(self.is_valid_empty) is not bool or type(self.unsafe_aggregate_guard) is not bool:
            raise MarketReportV0_2ValidationError(
                "True Competitor empty/aggregate guards must be boolean"
            )

        dispositions = tuple(
            sorted(
                self.dispositions,
                key=lambda item: (
                    item.grain_entity_reference_id,
                    item.disposition.value,
                    item.disposition_id,
                ),
            )
        )
        if any(not isinstance(item, CompetitorDisposition) for item in dispositions):
            raise MarketReportV0_2ValidationError(
                "True Competitor Set contains an invalid disposition"
            )
        if len({item.disposition_id for item in dispositions}) != len(dispositions):
            raise MarketReportV0_2ValidationError("duplicate disposition IDs")
        if len({item.grain_entity_reference_id for item in dispositions}) != len(dispositions):
            raise MarketReportV0_2ValidationError(
                "each evaluated grain entity requires exactly one disposition"
            )
        product_refs = [value for item in dispositions for value in item.product_reference_ids]
        if len(set(product_refs)) != len(product_refs):
            raise MarketReportV0_2ValidationError(
                "one product reference cannot belong to multiple grain dispositions"
            )

        actual_counts = {
            CompetitorDispositionType.INCLUDED: sum(
                item.disposition is CompetitorDispositionType.INCLUDED for item in dispositions
            ),
            CompetitorDispositionType.EXCLUDED: sum(
                item.disposition is CompetitorDispositionType.EXCLUDED for item in dispositions
            ),
            CompetitorDispositionType.REVIEW_REQUIRED: sum(
                item.disposition is CompetitorDispositionType.REVIEW_REQUIRED
                for item in dispositions
            ),
        }
        if (
            self.included_count != actual_counts[CompetitorDispositionType.INCLUDED]
            or self.excluded_count != actual_counts[CompetitorDispositionType.EXCLUDED]
            or self.review_required_count
            != actual_counts[CompetitorDispositionType.REVIEW_REQUIRED]
        ):
            raise MarketReportV0_2ValidationError(
                "True Competitor disposition counts do not reconcile"
            )

        for disposition in dispositions:
            if disposition.disposition in {
                CompetitorDispositionType.INCLUDED,
                CompetitorDispositionType.EXCLUDED,
            } and (
                disposition.authority_id != self.membership_authority_id
                or disposition.authority_version != self.membership_authority_version
            ):
                raise MarketReportV0_2ValidationError(
                    "final dispositions must use the set membership authority"
                )

        expected_availability = self._expected_availability(dispositions)
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "True Competitor section availability does not match dispositions"
            )
        expected_valid_empty = (
            bool(dispositions)
            and self.candidate_universe_completeness is CompletenessStatus.COMPLETE
            and self.included_count == 0
            and self.review_required_count == 0
            and self.excluded_count == len(dispositions)
            and self.membership_authority_id is not None
        )
        if self.is_valid_empty != expected_valid_empty:
            raise MarketReportV0_2ValidationError(
                "valid empty flag requires complete governed all-excluded evaluation"
            )
        expected_guard = not (
            self.candidate_universe_completeness is CompletenessStatus.COMPLETE
            and self.review_required_count == 0
            and bool(dispositions)
        )
        if self.unsafe_aggregate_guard != expected_guard:
            raise MarketReportV0_2ValidationError(
                "unsafe aggregate guard disagrees with candidate completeness/dispositions"
            )

        downstream_ready = not self.unsafe_aggregate_guard and self.included_count > 0
        if downstream_ready:
            if (
                self.included_cohort_reference_id is None
                or self.included_denominator_reference_id is None
            ):
                raise MarketReportV0_2ValidationError(
                    "complete included competitors require cohort and denominator references"
                )
        elif (
            self.included_cohort_reference_id is not None
            or self.included_denominator_reference_id is not None
        ):
            raise MarketReportV0_2ValidationError(
                "unsafe/empty competitor set cannot publish included aggregate references"
            )

        references = normalize_references(
            self.references, "TrueCompetitorSetSection.references"
        )
        referenced = {
            self.scope_context_reference_id,
            self.candidate_cohort_reference_id,
            self.product_grain_reference_id,
            *(item.grain_entity_reference_id for item in dispositions),
            *(value for item in dispositions for value in item.product_reference_ids),
            *(value for value in (
                self.included_cohort_reference_id,
                self.included_denominator_reference_id,
            ) if value is not None),
        }
        validate_registered_references(referenced, references, "TrueCompetitorSetSection")
        evidence = texts(self.evidence_ids, "TrueCompetitorSetSection.evidence_ids")
        provenance = texts(
            self.provenance_reference_ids,
            "TrueCompetitorSetSection.provenance_reference_ids",
            allow_empty=False,
        )
        child_evidence = {value for item in dispositions for value in item.evidence_ids}
        child_provenance = {
            value for item in dispositions for value in item.provenance_reference_ids
        }
        reference_provenance = {
            value for reference in references for value in reference.provenance_reference_ids
        }
        if not child_evidence <= set(evidence):
            raise MarketReportV0_2ValidationError(
                "True Competitor section omits disposition evidence"
            )
        if not (child_provenance | reference_provenance) <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "True Competitor section omits disposition/reference provenance"
            )
        limitations = texts(self.limitations, "TrueCompetitorSetSection.limitations")
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable True Competitor Set requires limitations"
            )
        object.__setattr__(self, "dispositions", dispositions)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.set_id != identity(
            "market-report-v0.2-true-competitor-set", self, "set_id"
        ):
            raise MarketReportV0_2ValidationError(
                "True Competitor set_id does not match content"
            )

    def _expected_availability(
        self,
        dispositions: tuple[CompetitorDisposition, ...],
    ) -> Availability:
        if not dispositions:
            return Availability.UNAVAILABLE
        if (
            self.candidate_universe_completeness is CompletenessStatus.COMPLETE
            and self.review_required_count == 0
            and self.membership_authority_id is not None
        ):
            return Availability.AVAILABLE
        return Availability.PARTIAL


def build_competitor_disposition(**content: Any) -> CompetitorDisposition:
    normalized = dict(content)
    for name in (
        "product_reference_ids",
        "reason_codes",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    return CompetitorDisposition(
        disposition_id=deterministic_id(
            "market-report-v0.2-competitor-disposition", normalized
        ),
        **normalized,
    )


def build_true_competitor_set(**content: Any) -> TrueCompetitorSetSection:
    normalized = dict(content)
    if "dispositions" in normalized:
        normalized["dispositions"] = tuple(
            sorted(
                normalized["dispositions"],
                key=lambda item: (
                    item.grain_entity_reference_id,
                    item.disposition.value,
                    item.disposition_id,
                ),
            )
        )
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    for name in ("evidence_ids", "provenance_reference_ids", "limitations"):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {"contract_version": TRUE_COMPETITOR_SET_CONTRACT_VERSION, **normalized}
    return TrueCompetitorSetSection(
        set_id=deterministic_id(
            "market-report-v0.2-true-competitor-set", material
        ),
        **material,
    )


__all__ = (
    "CompetitorDisposition",
    "CompetitorDispositionType",
    "TrueCompetitorSetSection",
    "build_competitor_disposition",
    "build_true_competitor_set",
)
