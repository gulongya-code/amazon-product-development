"""Compatibility-gated projection of already-governed distribution inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from ..models import (
    Availability,
    CompletenessStatus,
    ContractReference,
    DistributionKind,
    DistributionMembershipMode,
    DistributionMetricName,
    DistributionSectionItem,
    MarketReportV0_2ValidationError,
    MembershipDisclosure,
    MetricContextEnvelope,
    MetricValueType,
    PresenceStatus,
    ScopeContext,
    SegmentClassification,
    build_distribution_section,
    build_distribution_segment,
    unavailable_metric,
)


_METRIC_TYPES = {
    DistributionMetricName.PRODUCT_COUNT: MetricValueType.COUNT,
    DistributionMetricName.PRODUCT_SHARE: MetricValueType.SHARE,
    DistributionMetricName.SALES: MetricValueType.NUMBER,
    DistributionMetricName.SALES_SHARE: MetricValueType.SHARE,
    DistributionMetricName.REVENUE: MetricValueType.MONEY,
    DistributionMetricName.REVENUE_SHARE: MetricValueType.SHARE,
    DistributionMetricName.AVERAGE_PRICE: MetricValueType.MONEY,
    DistributionMetricName.MEDIAN_PRICE: MetricValueType.MONEY,
}
_ECONOMIC = {
    DistributionMetricName.SALES,
    DistributionMetricName.SALES_SHARE,
    DistributionMetricName.REVENUE,
    DistributionMetricName.REVENUE_SHARE,
    DistributionMetricName.AVERAGE_PRICE,
    DistributionMetricName.MEDIAN_PRICE,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class GovernedDistributionSegmentInput:
    """Policy output supplied by an upstream authority, never classified here."""

    policy_value_id: str
    policy_ordinal: int
    display_label: str
    canonical_definition: Any
    classification: SegmentClassification
    membership_disclosure: MembershipDisclosure
    member_grain_entity_reference_ids: tuple[str, ...]
    metrics: Mapping[str, MetricContextEnvelope]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()


class DistributionAdapter:
    """Project governed buckets and metrics without thresholds, joins, or formulas."""

    def adapt(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        distribution_kind: DistributionKind,
        dimension: str | None,
        policy_id: str,
        policy_version: str,
        membership_mode: DistributionMembershipMode,
        cohort_reference: ContractReference,
        product_denominator_reference: ContractReference,
        sales_denominator_reference: ContractReference | None,
        revenue_denominator_reference: ContractReference | None,
        period_reference: ContractReference | None,
        currency_code: str | None,
        declared_metric_names: tuple[DistributionMetricName, ...],
        segments: tuple[GovernedDistributionSegmentInput, ...],
        references: tuple[ContractReference, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> DistributionSectionItem:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "scope reference target does not match ScopeContext"
            )
        if any(
            not isinstance(item, GovernedDistributionSegmentInput)
            for item in segments
        ):
            raise TypeError("segments must be GovernedDistributionSegmentInput records")
        if not segments:
            raise MarketReportV0_2ValidationError(
                "governed distribution input requires segments"
            )
        declared = tuple(sorted(declared_metric_names, key=lambda item: item.value))
        if len(set(declared)) != len(declared):
            raise MarketReportV0_2ValidationError(
                "declared distribution metrics must be unique"
            )
        product_denominator_id = product_denominator_reference.reference_id
        sales_denominator_id = (
            sales_denominator_reference.reference_id
            if sales_denominator_reference is not None
            else None
        )
        revenue_denominator_id = (
            revenue_denominator_reference.reference_id
            if revenue_denominator_reference is not None
            else None
        )
        period_id = period_reference.reference_id if period_reference is not None else None
        expected_denominators = {
            DistributionMetricName.PRODUCT_COUNT: None,
            DistributionMetricName.PRODUCT_SHARE: product_denominator_id,
            DistributionMetricName.SALES: None,
            DistributionMetricName.SALES_SHARE: sales_denominator_id,
            DistributionMetricName.REVENUE: None,
            DistributionMetricName.REVENUE_SHARE: revenue_denominator_id,
            DistributionMetricName.AVERAGE_PRICE: product_denominator_id,
            DistributionMetricName.MEDIAN_PRICE: product_denominator_id,
        }
        projected_segments = []
        projection_limitations = set(limitations)
        all_evidence: set[str] = set()
        all_provenance = set(provenance_reference_ids)

        for segment in segments:
            unknown_names = sorted(set(segment.metrics) - {item.value for item in declared})
            if unknown_names:
                raise MarketReportV0_2ValidationError(
                    f"segment contains undeclared metrics: {unknown_names}"
                )
            projected_metrics = []
            segment_limitations = set(segment.limitations)
            members = (
                ()
                if scope_context.unsafe_aggregate_guard
                else segment.member_grain_entity_reference_ids
            )
            disclosure = (
                MembershipDisclosure.NOT_DISCLOSED
                if scope_context.unsafe_aggregate_guard
                else segment.membership_disclosure
            )
            for name in declared:
                source = segment.metrics.get(name.value)
                reason = self._incompatibility_reason(
                    name=name,
                    source=source,
                    marketplace=scope_context.marketplace,
                    grain_reference_id=scope_reference.reference_id,
                    cohort_reference_id=cohort_reference.reference_id,
                    denominator_reference_id=expected_denominators[name],
                    period_reference_id=period_id if name in _ECONOMIC else None,
                    currency_code=(
                        currency_code
                        if _METRIC_TYPES[name] is MetricValueType.MONEY
                        else None
                    ),
                    member_reference_ids=members,
                    disclosure=disclosure,
                    unsafe_guard=scope_context.unsafe_aggregate_guard,
                )
                if reason is None:
                    projected = source
                else:
                    limitation = f"{name.value}: {reason}"
                    segment_limitations.add(limitation)
                    projected = unavailable_metric(
                        metric_name=name.value,
                        value_type=_METRIC_TYPES[name],
                        marketplace=scope_context.marketplace,
                        product_grain_reference_id=scope_reference.reference_id,
                        provenance_reference_ids=(
                            source.provenance_reference_ids
                            if source is not None
                            else provenance_reference_ids
                        ),
                        limitations=(limitation,),
                        presence_status=(
                            source.presence_status
                            if source is not None
                            and source.presence_status is not PresenceStatus.PRESENT
                            else PresenceStatus.UNKNOWN
                        ),
                        evidence_ids=(source.evidence_ids if source is not None else ()),
                        unit=source.unit if source is not None else None,
                        currency_code=(
                            currency_code
                            if _METRIC_TYPES[name] is MetricValueType.MONEY
                            else None
                        ),
                        period_reference_id=(
                            period_id if name in _ECONOMIC else None
                        ),
                        subject_reference_ids=members,
                        cohort_reference_id=cohort_reference.reference_id,
                        denominator_reference_id=expected_denominators[name],
                    )
                projected_metrics.append(projected)
                all_evidence.update(projected.evidence_ids)
                all_provenance.update(projected.provenance_reference_ids)
                segment_limitations.update(projected.limitations)
            segment_evidence = tuple(
                sorted({*segment.evidence_ids, *(value for item in projected_metrics for value in item.evidence_ids)})
            )
            segment_provenance = tuple(
                sorted(
                    {
                        *segment.provenance_reference_ids,
                        *(value for item in projected_metrics for value in item.provenance_reference_ids),
                    }
                )
            )
            projected_segment = build_distribution_segment(
                policy_value_id=segment.policy_value_id,
                policy_ordinal=segment.policy_ordinal,
                display_label=segment.display_label,
                canonical_definition=segment.canonical_definition,
                classification=segment.classification,
                membership_disclosure=disclosure,
                metrics=tuple(projected_metrics),
                member_grain_entity_reference_ids=members,
                evidence_ids=segment_evidence,
                provenance_reference_ids=segment_provenance,
                limitations=tuple(sorted(segment_limitations)),
            )
            projected_segments.append(projected_segment)
            projection_limitations.update(projected_segment.limitations)
            all_evidence.update(projected_segment.evidence_ids)
            all_provenance.update(projected_segment.provenance_reference_ids)

        metric_states = {
            metric.availability
            for segment in projected_segments
            for metric in segment.metrics
        }
        availability = (
            Availability.AVAILABLE
            if metric_states == {Availability.AVAILABLE}
            else Availability.UNAVAILABLE
            if metric_states == {Availability.UNAVAILABLE}
            else Availability.PARTIAL
        )
        registry_items = [
            *references,
            *scope_context.references,
            scope_reference,
            cohort_reference,
            product_denominator_reference,
        ]
        for optional_reference in (
            sales_denominator_reference,
            revenue_denominator_reference,
            period_reference,
        ):
            if optional_reference is not None:
                registry_items.append(optional_reference)
        registry = tuple(
            {item.reference_id: item for item in registry_items}.values()
        )
        all_provenance.update(scope_context.provenance_reference_ids)
        all_provenance.update(
            value for item in registry for value in item.provenance_reference_ids
        )
        return build_distribution_section(
            distribution_kind=distribution_kind,
            dimension=dimension,
            availability=availability,
            marketplace=scope_context.marketplace,
            policy_id=policy_id,
            policy_version=policy_version,
            membership_mode=membership_mode,
            scope_context_reference_id=scope_reference.reference_id,
            cohort_reference_id=cohort_reference.reference_id,
            product_denominator_reference_id=product_denominator_id,
            sales_denominator_reference_id=sales_denominator_id,
            revenue_denominator_reference_id=revenue_denominator_id,
            product_grain_reference_id=scope_reference.reference_id,
            period_reference_id=period_id,
            currency=currency_code,
            declared_metric_names=declared,
            segments=tuple(projected_segments),
            unsafe_aggregate_guard=scope_context.unsafe_aggregate_guard,
            references=registry,
            evidence_ids=tuple(sorted(all_evidence)),
            provenance_reference_ids=tuple(sorted(all_provenance)),
            limitations=tuple(sorted(projection_limitations)),
        )

    @staticmethod
    def _incompatibility_reason(
        *,
        name: DistributionMetricName,
        source: MetricContextEnvelope | None,
        marketplace: str,
        grain_reference_id: str,
        cohort_reference_id: str,
        denominator_reference_id: str | None,
        period_reference_id: str | None,
        currency_code: str | None,
        member_reference_ids: tuple[str, ...],
        disclosure: MembershipDisclosure,
        unsafe_guard: bool,
    ) -> str | None:
        if unsafe_guard:
            return "aggregate projection blocked by MIXED_UNRESOLVED scope"
        if source is None:
            return "governed compatible metric was not supplied"
        if source.metric_name != name.value or source.value_type is not _METRIC_TYPES[name]:
            return "metric name or value type is incompatible"
        if source.marketplace != marketplace:
            return "metric marketplace is incompatible"
        if source.product_grain_reference_id != grain_reference_id:
            return "metric product grain is incompatible"
        if source.cohort_reference_id != cohort_reference_id:
            return "metric cohort is incompatible"
        if source.denominator_reference_id != denominator_reference_id:
            return "metric denominator is incompatible"
        if name in _ECONOMIC:
            if source.period_reference_id != period_reference_id:
                return "metric period/window is incompatible"
        if _METRIC_TYPES[name] is MetricValueType.MONEY and source.currency != currency_code:
            return "metric currency is incompatible"
        if source.availability is not Availability.UNAVAILABLE and (
            source.method_policy_id is None or source.method_policy_version is None
        ):
            return "metric lacks a governed method policy"
        if source.availability is not Availability.UNAVAILABLE and (
            source.completeness
            in {CompletenessStatus.UNKNOWN, CompletenessStatus.UNRESOLVED}
        ):
            return "metric completeness is incompatible"
        if (
            disclosure is MembershipDisclosure.COMPLETE
            and set(source.subject_reference_ids) != set(member_reference_ids)
        ):
            return "metric subjects do not match governed bucket membership"
        return None


__all__ = ("DistributionAdapter", "GovernedDistributionSegmentInput")
