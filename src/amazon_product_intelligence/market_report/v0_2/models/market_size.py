"""Data-gated monthly sales and revenue section for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import MARKET_SIZE_CONTRACT_VERSION
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
from .metric_context import MetricContextEnvelope, MetricValueType


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketSizeSection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    marketplace: str
    scope_context_reference_id: str
    cohort_reference_id: str
    product_grain_reference_id: str
    unsafe_aggregate_guard: bool
    monthly_sales: MetricContextEnvelope
    monthly_revenue: MetricContextEnvelope
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != MARKET_SIZE_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported market-size contract version")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("market-size availability is invalid")
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError("market-size marketplace must be uppercase text")
        for name in (
            "scope_context_reference_id",
            "cohort_reference_id",
            "product_grain_reference_id",
        ):
            text(getattr(self, name), f"MarketSizeSection.{name}")
        if type(self.unsafe_aggregate_guard) is not bool:
            raise MarketReportV0_2ValidationError("unsafe_aggregate_guard must be boolean")
        if not isinstance(self.monthly_sales, MetricContextEnvelope):
            raise MarketReportV0_2ValidationError("monthly_sales must be MetricContextEnvelope")
        if not isinstance(self.monthly_revenue, MetricContextEnvelope):
            raise MarketReportV0_2ValidationError("monthly_revenue must be MetricContextEnvelope")
        if self.monthly_sales.metric_name != "monthly_sales":
            raise MarketReportV0_2ValidationError("monthly sales metric name is invalid")
        if self.monthly_sales.value_type not in {
            MetricValueType.COUNT,
            MetricValueType.NUMBER,
        }:
            raise MarketReportV0_2ValidationError("monthly sales must be COUNT or NUMBER")
        if self.monthly_revenue.metric_name != "monthly_revenue":
            raise MarketReportV0_2ValidationError("monthly revenue metric name is invalid")
        if self.monthly_revenue.value_type is not MetricValueType.MONEY:
            raise MarketReportV0_2ValidationError("monthly revenue must be MONEY")

        metrics = (self.monthly_sales, self.monthly_revenue)
        if self.monthly_sales.period_reference_id != self.monthly_revenue.period_reference_id:
            raise MarketReportV0_2ValidationError(
                "monthly sales and revenue must use the same governed period"
            )
        for metric in metrics:
            if metric.marketplace != self.marketplace:
                raise MarketReportV0_2ValidationError("market-size metric marketplace mismatch")
            if metric.cohort_reference_id != self.cohort_reference_id:
                raise MarketReportV0_2ValidationError("market-size metric cohort mismatch")
            if metric.product_grain_reference_id != self.product_grain_reference_id:
                raise MarketReportV0_2ValidationError("market-size metric grain mismatch")
            if metric.period_reference_id is None:
                raise MarketReportV0_2ValidationError("monthly metric requires a period reference")
            if metric.availability is not Availability.UNAVAILABLE and (
                metric.method_policy_id is None or metric.method_policy_version is None
            ):
                raise MarketReportV0_2ValidationError(
                    "published market-size aggregate requires governed method policy"
                )
        if self.monthly_sales.availability is Availability.AVAILABLE and self.monthly_sales.unit is None:
            raise MarketReportV0_2ValidationError("available monthly sales requires an explicit unit")

        expected_availability = self._expected_availability(metrics)
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "market-size section availability does not match metric availability"
            )
        if self.unsafe_aggregate_guard and any(
            metric.availability is not Availability.UNAVAILABLE for metric in metrics
        ):
            raise MarketReportV0_2ValidationError(
                "unsafe scope requires unavailable market-size totals"
            )

        references = normalize_references(self.references, "MarketSizeSection.references")
        referenced = {
            self.scope_context_reference_id,
            self.cohort_reference_id,
            self.product_grain_reference_id,
            *(value for metric in metrics for value in metric.referenced_contract_ids()),
        }
        validate_registered_references(referenced, references, "MarketSizeSection")
        provenance = texts(
            self.provenance_reference_ids,
            "MarketSizeSection.provenance_reference_ids",
            allow_empty=False,
        )
        required_provenance = {
            *(value for metric in metrics for value in metric.provenance_reference_ids),
            *(value for reference in references for value in reference.provenance_reference_ids),
        }
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "market-size section omits metric/reference provenance"
            )
        limitations = texts(self.limitations, "MarketSizeSection.limitations")
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable market-size section requires limitations"
            )
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity(
            "market-report-v0.2-market-size", self, "section_id"
        ):
            raise MarketReportV0_2ValidationError(
                "market-size section_id does not match content"
            )

    @staticmethod
    def _expected_availability(
        metrics: tuple[MetricContextEnvelope, MetricContextEnvelope],
    ) -> Availability:
        states = {metric.availability for metric in metrics}
        if states == {Availability.AVAILABLE}:
            return Availability.AVAILABLE
        if states == {Availability.UNAVAILABLE}:
            return Availability.UNAVAILABLE
        return Availability.PARTIAL


def build_market_size_section(**content: Any) -> MarketSizeSection:
    normalized = dict(content)
    for name in ("provenance_reference_ids", "limitations"):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    material = {"contract_version": MARKET_SIZE_CONTRACT_VERSION, **normalized}
    return MarketSizeSection(
        section_id=deterministic_id("market-report-v0.2-market-size", material),
        **material,
    )


__all__ = ("MarketSizeSection", "build_market_size_section")
