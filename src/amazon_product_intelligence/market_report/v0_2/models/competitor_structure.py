"""Compatible aggregate competitor-structure projection contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import COMPETITOR_STRUCTURE_CONTRACT_VERSION
from .common import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    identity,
    normalize_references,
    text,
    texts,
    validate_registered_references,
)
from .metric_context import MetricContextEnvelope


_METRIC_FIELDS = (
    "competitor_count",
    "product_concentration",
    "brand_concentration",
    "seller_concentration",
    "review_barrier",
    "rating_barrier",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitorStructureSection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    marketplace: str
    scope_context_reference_id: str
    true_competitor_set_reference_id: str
    included_cohort_reference_id: str | None
    product_grain_reference_id: str
    unsafe_aggregate_guard: bool
    competitor_count: MetricContextEnvelope
    product_concentration: MetricContextEnvelope
    brand_concentration: MetricContextEnvelope
    seller_concentration: MetricContextEnvelope
    review_barrier: MetricContextEnvelope
    rating_barrier: MetricContextEnvelope
    head_entity_reference_ids: tuple[str, ...]
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != COMPETITOR_STRUCTURE_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported competitor-structure contract version"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "competitor-structure availability is invalid"
            )
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError(
                "competitor-structure marketplace must be uppercase text"
            )
        for name in (
            "scope_context_reference_id",
            "true_competitor_set_reference_id",
            "product_grain_reference_id",
        ):
            text(getattr(self, name), f"CompetitorStructureSection.{name}")
        if self.included_cohort_reference_id is not None:
            text(
                self.included_cohort_reference_id,
                "CompetitorStructureSection.included_cohort_reference_id",
            )
        if type(self.unsafe_aggregate_guard) is not bool:
            raise MarketReportV0_2ValidationError("unsafe_aggregate_guard must be boolean")

        metrics = tuple(getattr(self, name) for name in _METRIC_FIELDS)
        if any(not isinstance(metric, MetricContextEnvelope) for metric in metrics):
            raise MarketReportV0_2ValidationError(
                "competitor structure contains a non-metric envelope"
            )
        if tuple(metric.metric_name for metric in metrics) != _METRIC_FIELDS:
            raise MarketReportV0_2ValidationError(
                "competitor-structure metric names do not match the contract"
            )
        for metric in metrics:
            if metric.marketplace != self.marketplace:
                raise MarketReportV0_2ValidationError(
                    "competitor-structure metric marketplace mismatch"
                )
            if metric.product_grain_reference_id != self.product_grain_reference_id:
                raise MarketReportV0_2ValidationError(
                    "competitor-structure metric grain mismatch"
                )
            if metric.availability is not Availability.UNAVAILABLE and (
                metric.method_policy_id is None or metric.method_policy_version is None
            ):
                raise MarketReportV0_2ValidationError(
                    "published competitor aggregate requires governed method policy"
                )
            if metric.availability is not Availability.UNAVAILABLE and (
                self.included_cohort_reference_id is None
                or metric.cohort_reference_id != self.included_cohort_reference_id
            ):
                raise MarketReportV0_2ValidationError(
                    "published competitor metric requires the exact included cohort"
                )

        expected_availability = self._expected_availability(metrics)
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "competitor-structure availability does not match metrics"
            )
        heads = texts(
            self.head_entity_reference_ids,
            "CompetitorStructureSection.head_entity_reference_ids",
        )
        if self.unsafe_aggregate_guard:
            if any(metric.availability is not Availability.UNAVAILABLE for metric in metrics):
                raise MarketReportV0_2ValidationError(
                    "unsafe competitor structure cannot publish aggregate metrics"
                )
            if heads or self.included_cohort_reference_id is not None:
                raise MarketReportV0_2ValidationError(
                    "unsafe competitor structure cannot publish head/cohort references"
                )

        references = normalize_references(
            self.references, "CompetitorStructureSection.references"
        )
        referenced = {
            self.scope_context_reference_id,
            self.true_competitor_set_reference_id,
            self.product_grain_reference_id,
            *heads,
            *(value for value in (self.included_cohort_reference_id,) if value is not None),
            *(value for metric in metrics for value in metric.referenced_contract_ids()),
        }
        validate_registered_references(referenced, references, "CompetitorStructureSection")
        provenance = texts(
            self.provenance_reference_ids,
            "CompetitorStructureSection.provenance_reference_ids",
            allow_empty=False,
        )
        required_provenance = {
            *(value for metric in metrics for value in metric.provenance_reference_ids),
            *(value for reference in references for value in reference.provenance_reference_ids),
        }
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "competitor structure omits metric/reference provenance"
            )
        limitations = texts(self.limitations, "CompetitorStructureSection.limitations")
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable competitor structure requires limitations"
            )
        object.__setattr__(self, "head_entity_reference_ids", heads)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity(
            "market-report-v0.2-competitor-structure", self, "section_id"
        ):
            raise MarketReportV0_2ValidationError(
                "competitor-structure section_id does not match content"
            )

    @staticmethod
    def _expected_availability(
        metrics: tuple[MetricContextEnvelope, ...],
    ) -> Availability:
        states = {metric.availability for metric in metrics}
        if states == {Availability.AVAILABLE}:
            return Availability.AVAILABLE
        if states == {Availability.UNAVAILABLE}:
            return Availability.UNAVAILABLE
        return Availability.PARTIAL


def build_competitor_structure(**content: Any) -> CompetitorStructureSection:
    normalized = dict(content)
    for name in (
        "head_entity_reference_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    material = {"contract_version": COMPETITOR_STRUCTURE_CONTRACT_VERSION, **normalized}
    return CompetitorStructureSection(
        section_id=deterministic_id(
            "market-report-v0.2-competitor-structure", material
        ),
        **material,
    )


__all__ = ("CompetitorStructureSection", "build_competitor_structure")
