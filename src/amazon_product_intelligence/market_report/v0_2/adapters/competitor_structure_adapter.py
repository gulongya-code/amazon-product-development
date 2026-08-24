"""Compatibility-gated projection for competitor-structure metrics."""

from __future__ import annotations

from collections.abc import Mapping

from ..models import (
    Availability,
    CompletenessStatus,
    CompetitorStructureSection,
    ContractReference,
    MarketReportV0_2ValidationError,
    MetricContextEnvelope,
    MetricValueType,
    ScopeContext,
    TrueCompetitorSetSection,
    build_competitor_structure,
    unavailable_metric,
)


_METRIC_TYPES = {
    "competitor_count": MetricValueType.COUNT,
    "product_concentration": MetricValueType.SHARE,
    "brand_concentration": MetricValueType.SHARE,
    "seller_concentration": MetricValueType.SHARE,
    "review_barrier": MetricValueType.NUMBER,
    "rating_barrier": MetricValueType.NUMBER,
}
_DENOMINATOR_METRICS = {
    "product_concentration",
    "brand_concentration",
    "seller_concentration",
}


class CompetitorStructureAdapter:
    """Project only compatible governed metrics; never calculate replacements."""

    def adapt(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        true_competitor_set: TrueCompetitorSetSection,
        true_competitor_set_reference: ContractReference,
        governed_metrics: Mapping[str, MetricContextEnvelope],
        head_entity_reference_ids: tuple[str, ...],
        references: tuple[ContractReference, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> CompetitorStructureSection:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if not isinstance(true_competitor_set, TrueCompetitorSetSection):
            raise TypeError("true_competitor_set must be TrueCompetitorSetSection")
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "scope reference target does not match ScopeContext"
            )
        if true_competitor_set_reference.target_id != true_competitor_set.set_id:
            raise MarketReportV0_2ValidationError(
                "True Competitor reference target does not match the supplied set"
            )
        if true_competitor_set.scope_context_reference_id != scope_reference.reference_id:
            raise MarketReportV0_2ValidationError(
                "True Competitor Set belongs to a different scope"
            )
        unknown_names = sorted(set(governed_metrics) - set(_METRIC_TYPES))
        if unknown_names:
            raise MarketReportV0_2ValidationError(
                f"unsupported competitor-structure metrics: {unknown_names}"
            )
        if any(not isinstance(item, MetricContextEnvelope) for item in governed_metrics.values()):
            raise TypeError("governed_metrics values must be MetricContextEnvelope")
        if not provenance_reference_ids:
            raise MarketReportV0_2ValidationError(
                "competitor-structure projection requires provenance"
            )

        included_cohort_id = true_competitor_set.included_cohort_reference_id
        included_denominator_id = true_competitor_set.included_denominator_reference_id
        unsafe_guard = (
            scope_context.unsafe_aggregate_guard
            or true_competitor_set.unsafe_aggregate_guard
            or included_cohort_id is None
            or included_denominator_id is None
        )
        output_cohort_id = None if unsafe_guard else included_cohort_id
        output_heads = () if unsafe_guard else head_entity_reference_ids
        projected: dict[str, MetricContextEnvelope] = {}
        projection_limitations = set(limitations)

        for name, value_type in _METRIC_TYPES.items():
            source = governed_metrics.get(name)
            reason = self._incompatibility_reason(
                name=name,
                value_type=value_type,
                source=source,
                marketplace=scope_context.marketplace,
                product_grain_reference_id=scope_reference.reference_id,
                included_cohort_reference_id=included_cohort_id,
                included_denominator_reference_id=included_denominator_id,
                included_count=true_competitor_set.included_count,
                unsafe_guard=unsafe_guard,
            )
            if reason is None:
                projected[name] = source  # type: ignore[assignment]
                projection_limitations.update(source.limitations)
                continue
            limitation = f"{name}: {reason}"
            projection_limitations.add(limitation)
            projected[name] = unavailable_metric(
                metric_name=name,
                value_type=value_type,
                marketplace=scope_context.marketplace,
                product_grain_reference_id=scope_reference.reference_id,
                provenance_reference_ids=provenance_reference_ids,
                limitations=(limitation,),
            )

        states = {item.availability for item in projected.values()}
        availability = (
            Availability.AVAILABLE
            if states == {Availability.AVAILABLE}
            else Availability.UNAVAILABLE
            if states == {Availability.UNAVAILABLE}
            else Availability.PARTIAL
        )
        registry = tuple(
            {
                item.reference_id: item
                for item in (
                    *references,
                    *scope_context.references,
                    *true_competitor_set.references,
                    scope_reference,
                    true_competitor_set_reference,
                )
            }.values()
        )
        provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *scope_context.provenance_reference_ids,
                    *true_competitor_set.provenance_reference_ids,
                    *(value for item in projected.values() for value in item.provenance_reference_ids),
                    *(value for item in registry for value in item.provenance_reference_ids),
                }
            )
        )
        return build_competitor_structure(
            availability=availability,
            marketplace=scope_context.marketplace,
            scope_context_reference_id=scope_reference.reference_id,
            true_competitor_set_reference_id=true_competitor_set_reference.reference_id,
            included_cohort_reference_id=output_cohort_id,
            product_grain_reference_id=scope_reference.reference_id,
            unsafe_aggregate_guard=unsafe_guard,
            competitor_count=projected["competitor_count"],
            product_concentration=projected["product_concentration"],
            brand_concentration=projected["brand_concentration"],
            seller_concentration=projected["seller_concentration"],
            review_barrier=projected["review_barrier"],
            rating_barrier=projected["rating_barrier"],
            head_entity_reference_ids=output_heads,
            references=registry,
            provenance_reference_ids=provenance,
            limitations=tuple(sorted(projection_limitations)),
        )

    @staticmethod
    def _incompatibility_reason(
        *,
        name: str,
        value_type: MetricValueType,
        source: MetricContextEnvelope | None,
        marketplace: str,
        product_grain_reference_id: str,
        included_cohort_reference_id: str | None,
        included_denominator_reference_id: str | None,
        included_count: int,
        unsafe_guard: bool,
    ) -> str | None:
        if unsafe_guard:
            return "aggregate projection blocked by unresolved or empty competitor scope"
        if source is None:
            return "governed compatible metric was not supplied"
        if source.metric_name != name or source.value_type is not value_type:
            return "metric name or value type is incompatible"
        if source.marketplace != marketplace:
            return "metric marketplace is incompatible"
        if source.product_grain_reference_id != product_grain_reference_id:
            return "metric product grain is incompatible"
        if source.cohort_reference_id != included_cohort_reference_id:
            return "metric cohort is not the exact included competitor cohort"
        if source.availability is not Availability.UNAVAILABLE and (
            source.method_policy_id is None or source.method_policy_version is None
        ):
            return "metric lacks a governed method policy"
        if source.completeness in {
            CompletenessStatus.UNKNOWN,
            CompletenessStatus.UNRESOLVED,
        }:
            return "metric completeness is incompatible with aggregate projection"
        if (
            source.sample_context.is_known
            and source.sample_context.total_count != included_count
        ):
            return "metric sample does not match the exact included competitor cohort"
        if (
            name == "competitor_count"
            and source.value is not None
            and source.value != included_count
        ):
            return "competitor count contradicts the governed included cohort"
        if (
            name in _DENOMINATOR_METRICS
            and source.denominator_reference_id != included_denominator_reference_id
        ):
            return "metric denominator is not the exact included competitor denominator"
        return None


__all__ = ("CompetitorStructureAdapter",)
