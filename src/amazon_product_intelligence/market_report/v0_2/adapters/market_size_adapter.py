"""Projection-only adapter for governed monthly market-size metrics."""

from __future__ import annotations

from ..models import (
    Availability,
    ContractReference,
    MarketReportV0_2ValidationError,
    MarketSizeSection,
    MetricContextEnvelope,
    ScopeContext,
    build_market_size_section,
)


class MarketSizeAdapter:
    """Compose compatible metric envelopes without calculating market size."""

    def adapt(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        monthly_sales: MetricContextEnvelope,
        monthly_revenue: MetricContextEnvelope,
        references: tuple[ContractReference, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> MarketSizeSection:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "scope reference target does not match ScopeContext"
            )
        metrics = (monthly_sales, monthly_revenue)
        if any(not isinstance(metric, MetricContextEnvelope) for metric in metrics):
            raise TypeError("monthly sales/revenue must be MetricContextEnvelope")
        if scope_context.unsafe_aggregate_guard and any(
            metric.availability is not Availability.UNAVAILABLE for metric in metrics
        ):
            raise MarketReportV0_2ValidationError(
                "MIXED_UNRESOLVED scope cannot project market-size totals"
            )
        expected_grain_ref = scope_reference.reference_id
        if any(
            metric.product_grain_reference_id != expected_grain_ref for metric in metrics
        ):
            raise MarketReportV0_2ValidationError(
                "market-size metric grain reference must resolve to supplied scope"
            )
        if any(
            metric.cohort_reference_id != scope_context.analysis_cohort_reference_id
            for metric in metrics
        ):
            raise MarketReportV0_2ValidationError(
                "market-size metrics must use the scope analysis cohort"
            )
        if monthly_sales.period_reference_id != monthly_revenue.period_reference_id:
            raise MarketReportV0_2ValidationError(
                "monthly sales and revenue must use the exact same governed period"
            )
        for metric in metrics:
            if metric.availability is Availability.UNAVAILABLE:
                continue
            if metric.method_policy_id is None or metric.method_policy_version is None:
                raise MarketReportV0_2ValidationError(
                    "published market-size aggregates require governed method policy"
                )
            if (
                metric.sample_context.is_known
                and metric.sample_context.total_count
                != scope_context.included_grain_entity_count
            ):
                raise MarketReportV0_2ValidationError(
                    "market-size metric sample does not match the scope grain cohort"
                )
        states = {metric.availability for metric in metrics}
        availability = (
            Availability.AVAILABLE
            if states == {Availability.AVAILABLE}
            else Availability.UNAVAILABLE
            if states == {Availability.UNAVAILABLE}
            else Availability.PARTIAL
        )
        combined_limitations = tuple(
            sorted(
                {
                    *limitations,
                    *(value for metric in metrics for value in metric.limitations),
                    *(scope_context.limitations if scope_context.unsafe_aggregate_guard else ()),
                }
            )
        )
        combined_provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *scope_context.provenance_reference_ids,
                    *(value for metric in metrics for value in metric.provenance_reference_ids),
                }
            )
        )
        registry = tuple(
            {
                item.reference_id: item
                for item in (*references, *scope_context.references, scope_reference)
            }.values()
        )
        return build_market_size_section(
            availability=availability,
            marketplace=scope_context.marketplace,
            scope_context_reference_id=scope_reference.reference_id,
            cohort_reference_id=scope_context.analysis_cohort_reference_id,
            product_grain_reference_id=scope_reference.reference_id,
            unsafe_aggregate_guard=scope_context.unsafe_aggregate_guard,
            monthly_sales=monthly_sales,
            monthly_revenue=monthly_revenue,
            references=registry,
            provenance_reference_ids=combined_provenance,
            limitations=combined_limitations,
        )


__all__ = ("MarketSizeAdapter",)
