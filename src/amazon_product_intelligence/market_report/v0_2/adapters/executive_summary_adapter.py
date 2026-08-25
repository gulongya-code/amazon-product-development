"""Bounded composition of caller-governed claims from validated sources."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ..models import Availability, MarketReportV0_2ValidationError
from ..models.executive_summary import (
    ExecutiveClaim,
    ExecutiveClaimCategory,
    ExecutiveSummarySection,
    build_executive_claim,
    build_executive_summary,
)


_RANK = {Availability.UNAVAILABLE: 0, Availability.PARTIAL: 1, Availability.AVAILABLE: 2}


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatedExecutiveSource:
    reference_id: str
    availability: Availability
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    confidence: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class GovernedExecutiveClaimInput:
    category: ExecutiveClaimCategory
    availability: Availability
    text: str | None
    typed_value: Any | None
    source_reference_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    confidence: str | None
    limitations: tuple[str, ...]


class ExecutiveSummaryAdapter:
    def compose(
        self,
        *,
        inputs: tuple[GovernedExecutiveClaimInput, ...],
        validated_sources: Mapping[str, ValidatedExecutiveSource],
        limitations: tuple[str, ...] = (),
    ) -> ExecutiveSummarySection:
        claims: list[ExecutiveClaim] = []
        for item in inputs:
            sources = []
            for reference_id in item.source_reference_ids:
                source = validated_sources.get(reference_id)
                if source is None:
                    raise MarketReportV0_2ValidationError(f"Executive claim source is not validated: {reference_id}")
                sources.append(source)
            if not sources:
                raise MarketReportV0_2ValidationError("Executive claim requires a validated source")
            maximum = min(_RANK[source.availability] for source in sources)
            if _RANK[item.availability] > maximum:
                raise MarketReportV0_2ValidationError("Executive claim cannot upgrade source availability")
            source_evidence = {value for source in sources for value in source.evidence_ids}
            if not set(item.evidence_ids) <= source_evidence:
                raise MarketReportV0_2ValidationError("Executive claim evidence is not supplied by its sources")
            source_provenance = {value for source in sources for value in source.provenance_reference_ids}
            if not set(item.provenance_reference_ids) <= source_provenance:
                raise MarketReportV0_2ValidationError("Executive claim provenance is not supplied by its sources")
            confidence = item.confidence
            source_confidence = {source.confidence for source in sources if source.confidence is not None}
            if confidence is not None and confidence not in source_confidence:
                raise MarketReportV0_2ValidationError("Executive claim cannot invent confidence")
            claims.append(build_executive_claim(**asdict(item)))
        availability = (
            Availability.AVAILABLE
            if claims and all(item.availability is Availability.AVAILABLE for item in claims)
            else Availability.UNAVAILABLE
            if not claims or all(item.availability is Availability.UNAVAILABLE for item in claims)
            else Availability.PARTIAL
        )
        summary_limitations = tuple(sorted(set(limitations)))
        if availability is not Availability.AVAILABLE and not summary_limitations:
            summary_limitations = ("One or more executive claims are constrained by unavailable evidence",)
        provenance = tuple(sorted({value for claim in claims for value in claim.provenance_reference_ids}))
        return build_executive_summary(
            availability=availability,
            claims=tuple(claims),
            provenance_reference_ids=provenance,
            limitations=summary_limitations,
        )


__all__ = ("ExecutiveSummaryAdapter", "GovernedExecutiveClaimInput", "ValidatedExecutiveSource")
