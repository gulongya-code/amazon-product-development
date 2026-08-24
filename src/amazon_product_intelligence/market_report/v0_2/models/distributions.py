"""Versioned, policy-owned distribution contracts for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import (
    DISTRIBUTION_CONTRACT_VERSION,
    DISTRIBUTION_SEGMENT_CONTRACT_VERSION,
)
from .common import (
    Availability,
    CompletenessStatus,
    ContractReference,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    currency,
    freeze_json,
    identity,
    normalize_references,
    optional_text,
    policy_pair,
    text,
    texts,
    validate_registered_references,
)
from .metric_context import MetricContextEnvelope, MetricValueType


class DistributionKind(StrEnum):
    ATTRIBUTE_VALUE = "ATTRIBUTE_VALUE"
    NUMERIC_BUCKET = "NUMERIC_BUCKET"


class DistributionMetricName(StrEnum):
    PRODUCT_COUNT = "product_count"
    PRODUCT_SHARE = "product_share"
    SALES = "sales"
    SALES_SHARE = "sales_share"
    REVENUE = "revenue"
    REVENUE_SHARE = "revenue_share"
    AVERAGE_PRICE = "average_price"
    MEDIAN_PRICE = "median_price"


class SegmentClassification(StrEnum):
    CLASSIFIED = "CLASSIFIED"
    UNKNOWN_UNCLASSIFIED = "UNKNOWN_UNCLASSIFIED"


class DistributionMembershipMode(StrEnum):
    SINGLE_CLASSIFICATION = "SINGLE_CLASSIFICATION"
    MULTI_VALUE = "MULTI_VALUE"


class MembershipDisclosure(StrEnum):
    COMPLETE = "COMPLETE"
    NOT_DISCLOSED = "NOT_DISCLOSED"


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

_ECONOMIC_METRICS = {
    DistributionMetricName.SALES,
    DistributionMetricName.SALES_SHARE,
    DistributionMetricName.REVENUE,
    DistributionMetricName.REVENUE_SHARE,
    DistributionMetricName.AVERAGE_PRICE,
    DistributionMetricName.MEDIAN_PRICE,
}


@dataclass(frozen=True, slots=True, kw_only=True)
class DistributionSegment(V0_2Contract):
    segment_id: str
    contract_version: str
    policy_value_id: str
    policy_ordinal: int
    display_label: str
    canonical_definition: Any
    classification: SegmentClassification
    membership_disclosure: MembershipDisclosure
    metrics: tuple[MetricContextEnvelope, ...]
    member_grain_entity_reference_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != DISTRIBUTION_SEGMENT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported distribution segment contract version"
            )
        text(self.policy_value_id, "DistributionSegment.policy_value_id")
        if type(self.policy_ordinal) is not int or self.policy_ordinal < 0:
            raise MarketReportV0_2ValidationError(
                "DistributionSegment.policy_ordinal must be a non-negative integer"
            )
        text(self.display_label, "DistributionSegment.display_label")
        if not isinstance(self.classification, SegmentClassification):
            raise MarketReportV0_2ValidationError(
                "distribution segment classification is invalid"
            )
        if not isinstance(self.membership_disclosure, MembershipDisclosure):
            raise MarketReportV0_2ValidationError(
                "distribution membership disclosure is invalid"
            )
        definition = (
            None
            if self.canonical_definition is None
            else freeze_json(
                self.canonical_definition,
                "DistributionSegment.canonical_definition",
            )
        )
        if self.classification is SegmentClassification.UNKNOWN_UNCLASSIFIED:
            if definition is not None:
                raise MarketReportV0_2ValidationError(
                    "unknown/unclassified segment requires null canonical definition"
                )
        elif definition is None:
            raise MarketReportV0_2ValidationError(
                "classified segment requires a canonical value or governed bounds"
            )

        metrics = tuple(sorted(self.metrics, key=lambda item: item.metric_name))
        if not metrics or any(
            not isinstance(item, MetricContextEnvelope) for item in metrics
        ):
            raise MarketReportV0_2ValidationError(
                "distribution segment requires metric envelopes"
            )
        if len({item.metric_name for item in metrics}) != len(metrics):
            raise MarketReportV0_2ValidationError(
                "distribution segment contains duplicate metric names"
            )
        members = texts(
            self.member_grain_entity_reference_ids,
            "DistributionSegment.member_grain_entity_reference_ids",
        )
        if self.membership_disclosure is MembershipDisclosure.NOT_DISCLOSED and members:
            raise MarketReportV0_2ValidationError(
                "NOT_DISCLOSED membership cannot publish member references"
            )
        product_count = next(
            (item for item in metrics if item.metric_name == "product_count"),
            None,
        )
        if (
            self.membership_disclosure is MembershipDisclosure.COMPLETE
            and product_count is not None
            and product_count.availability is Availability.AVAILABLE
            and product_count.value != len(members)
        ):
            raise MarketReportV0_2ValidationError(
                "complete segment membership must reconcile with product_count"
            )
        evidence = texts(self.evidence_ids, "DistributionSegment.evidence_ids")
        provenance = texts(
            self.provenance_reference_ids,
            "DistributionSegment.provenance_reference_ids",
            allow_empty=False,
        )
        limitations = texts(self.limitations, "DistributionSegment.limitations")
        required_evidence = {
            value for metric in metrics for value in metric.evidence_ids
        }
        required_provenance = {
            value for metric in metrics for value in metric.provenance_reference_ids
        }
        if not required_evidence <= set(evidence):
            raise MarketReportV0_2ValidationError(
                "distribution segment omits metric evidence"
            )
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "distribution segment omits metric provenance"
            )
        if any(
            metric.availability is not Availability.AVAILABLE for metric in metrics
        ) and not limitations:
            raise MarketReportV0_2ValidationError(
                "segment with partial/unavailable metrics requires limitations"
            )
        object.__setattr__(self, "canonical_definition", definition)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "member_grain_entity_reference_ids", members)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.segment_id != identity(
            "market-report-v0.2-distribution-segment", self, "segment_id"
        ):
            raise MarketReportV0_2ValidationError(
                "distribution segment_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DistributionSectionItem(V0_2Contract):
    distribution_id: str
    contract_version: str
    distribution_kind: DistributionKind
    dimension: str | None
    availability: Availability
    marketplace: str
    policy_id: str
    policy_version: str
    membership_mode: DistributionMembershipMode
    scope_context_reference_id: str
    cohort_reference_id: str
    product_denominator_reference_id: str
    sales_denominator_reference_id: str | None
    revenue_denominator_reference_id: str | None
    product_grain_reference_id: str
    period_reference_id: str | None
    currency: str | None
    declared_metric_names: tuple[DistributionMetricName, ...]
    segments: tuple[DistributionSegment, ...]
    unsafe_aggregate_guard: bool
    references: tuple[ContractReference, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != DISTRIBUTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported distribution contract version"
            )
        if not isinstance(self.distribution_kind, DistributionKind):
            raise MarketReportV0_2ValidationError("distribution kind is invalid")
        optional_text(self.dimension, "DistributionSectionItem.dimension")
        if (
            self.distribution_kind is DistributionKind.ATTRIBUTE_VALUE
            and self.dimension is None
        ):
            raise MarketReportV0_2ValidationError(
                "attribute distribution requires an explicit dimension"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("distribution availability is invalid")
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError(
                "distribution marketplace must be uppercase text"
            )
        policy_pair(
            self.policy_id,
            self.policy_version,
            "DistributionSectionItem.policy",
            required=True,
        )
        if not isinstance(self.membership_mode, DistributionMembershipMode):
            raise MarketReportV0_2ValidationError(
                "distribution membership mode is invalid"
            )
        for name in (
            "scope_context_reference_id",
            "cohort_reference_id",
            "product_denominator_reference_id",
            "product_grain_reference_id",
        ):
            text(getattr(self, name), f"DistributionSectionItem.{name}")
        optional_text(
            self.sales_denominator_reference_id,
            "DistributionSectionItem.sales_denominator_reference_id",
        )
        optional_text(
            self.revenue_denominator_reference_id,
            "DistributionSectionItem.revenue_denominator_reference_id",
        )
        optional_text(
            self.period_reference_id,
            "DistributionSectionItem.period_reference_id",
        )
        currency(self.currency, "DistributionSectionItem.currency")
        if type(self.unsafe_aggregate_guard) is not bool:
            raise MarketReportV0_2ValidationError(
                "distribution unsafe_aggregate_guard must be boolean"
            )

        declared = tuple(sorted(self.declared_metric_names, key=lambda item: item.value))
        if not declared or any(
            not isinstance(item, DistributionMetricName) for item in declared
        ):
            raise MarketReportV0_2ValidationError(
                "distribution requires declared metric names"
            )
        if len(set(declared)) != len(declared):
            raise MarketReportV0_2ValidationError(
                "distribution declared metric names must be unique"
            )
        if not {
            DistributionMetricName.PRODUCT_COUNT,
            DistributionMetricName.PRODUCT_SHARE,
        } <= set(declared):
            raise MarketReportV0_2ValidationError(
                "distribution must declare product_count and product_share"
            )
        if (
            DistributionMetricName.SALES_SHARE in declared
            and self.sales_denominator_reference_id is None
        ):
            raise MarketReportV0_2ValidationError(
                "sales_share requires an exact sales denominator"
            )
        if (
            DistributionMetricName.REVENUE_SHARE in declared
            and self.revenue_denominator_reference_id is None
        ):
            raise MarketReportV0_2ValidationError(
                "revenue_share requires an exact revenue denominator"
            )
        if any(_METRIC_TYPES[item] is MetricValueType.MONEY for item in declared) and (
            self.currency is None
        ):
            raise MarketReportV0_2ValidationError(
                "distribution with money metrics requires explicit currency"
            )

        segments = tuple(
            sorted(self.segments, key=lambda item: (item.policy_ordinal, item.policy_value_id))
        )
        if not segments or any(
            not isinstance(item, DistributionSegment) for item in segments
        ):
            raise MarketReportV0_2ValidationError(
                "distribution requires deterministic segments"
            )
        if len({item.policy_value_id for item in segments}) != len(segments):
            raise MarketReportV0_2ValidationError(
                "distribution contains duplicate policy value IDs"
            )
        if len({item.segment_id for item in segments}) != len(segments):
            raise MarketReportV0_2ValidationError(
                "distribution contains duplicate segment IDs"
            )
        if len({item.policy_ordinal for item in segments}) != len(segments):
            raise MarketReportV0_2ValidationError(
                "distribution contains duplicate policy ordinals"
            )
        unknown = tuple(
            item
            for item in segments
            if item.classification is SegmentClassification.UNKNOWN_UNCLASSIFIED
        )
        if len(unknown) != 1:
            raise MarketReportV0_2ValidationError(
                "distribution requires exactly one unknown/unclassified segment"
            )
        declared_values = {item.value for item in declared}
        for segment in segments:
            actual_names = {metric.metric_name for metric in segment.metrics}
            if actual_names != declared_values:
                raise MarketReportV0_2ValidationError(
                    "every segment must explicitly represent the declared metric set"
                )
            self._validate_segment_metrics(segment)

        unknown_members = set(unknown[0].member_grain_entity_reference_ids)
        known_members = {
            value
            for segment in segments
            if segment.classification is SegmentClassification.CLASSIFIED
            for value in segment.member_grain_entity_reference_ids
        }
        if unknown_members & known_members:
            raise MarketReportV0_2ValidationError(
                "unknown segment membership must be disjoint from classified membership"
            )
        if self.membership_mode is DistributionMembershipMode.SINGLE_CLASSIFICATION:
            member_ids = [
                value
                for segment in segments
                for value in segment.member_grain_entity_reference_ids
            ]
            if len(member_ids) != len(set(member_ids)):
                raise MarketReportV0_2ValidationError(
                    "single-classification distribution contains duplicate membership"
                )
            product_shares = tuple(
                next(
                    metric
                    for metric in segment.metrics
                    if metric.metric_name == DistributionMetricName.PRODUCT_SHARE.value
                )
                for segment in segments
            )
            if all(
                metric.availability is Availability.AVAILABLE
                for metric in product_shares
            ) and not math.isclose(
                sum(float(metric.value) for metric in product_shares),
                1.0,
                rel_tol=0.0,
                abs_tol=1e-12,
            ):
                raise MarketReportV0_2ValidationError(
                    "single-classification product shares must reconcile to one"
                )

        metrics = tuple(metric for segment in segments for metric in segment.metrics)
        expected_availability = self._expected_availability(metrics)
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "distribution availability does not match represented metrics"
            )
        if self.unsafe_aggregate_guard and any(
            metric.availability is not Availability.UNAVAILABLE for metric in metrics
        ):
            raise MarketReportV0_2ValidationError(
                "unsafe distribution cannot publish aggregate metrics"
            )
        if self.unsafe_aggregate_guard and any(
            segment.membership_disclosure is not MembershipDisclosure.NOT_DISCLOSED
            or segment.member_grain_entity_reference_ids
            for segment in segments
        ):
            raise MarketReportV0_2ValidationError(
                "unsafe distribution cannot publish bucket membership"
            )

        references = normalize_references(
            self.references, "DistributionSectionItem.references"
        )
        referenced = {
            self.scope_context_reference_id,
            self.cohort_reference_id,
            self.product_denominator_reference_id,
            self.product_grain_reference_id,
            self.sales_denominator_reference_id,
            self.revenue_denominator_reference_id,
            self.period_reference_id,
            *(value for segment in segments for value in segment.member_grain_entity_reference_ids),
            *(value for metric in metrics for value in metric.referenced_contract_ids()),
        }
        validate_registered_references(
            referenced, references, "DistributionSectionItem"
        )
        evidence = texts(self.evidence_ids, "DistributionSectionItem.evidence_ids")
        provenance = texts(
            self.provenance_reference_ids,
            "DistributionSectionItem.provenance_reference_ids",
            allow_empty=False,
        )
        limitations = texts(self.limitations, "DistributionSectionItem.limitations")
        child_evidence = {value for item in segments for value in item.evidence_ids}
        child_provenance = {
            value for item in segments for value in item.provenance_reference_ids
        }
        reference_provenance = {
            value for item in references for value in item.provenance_reference_ids
        }
        if not child_evidence <= set(evidence):
            raise MarketReportV0_2ValidationError(
                "distribution omits segment evidence"
            )
        if not (child_provenance | reference_provenance) <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "distribution omits segment/reference provenance"
            )
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable distribution requires limitations"
            )
        object.__setattr__(self, "declared_metric_names", declared)
        object.__setattr__(self, "segments", segments)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.distribution_id != identity(
            "market-report-v0.2-distribution", self, "distribution_id"
        ):
            raise MarketReportV0_2ValidationError(
                "distribution_id does not match content"
            )

    def _validate_segment_metrics(self, segment: DistributionSegment) -> None:
        for metric in segment.metrics:
            name = DistributionMetricName(metric.metric_name)
            if metric.value_type is not _METRIC_TYPES[name]:
                raise MarketReportV0_2ValidationError(
                    f"distribution metric {name.value} has an incompatible value type"
                )
            if metric.marketplace != self.marketplace:
                raise MarketReportV0_2ValidationError(
                    "distribution metric marketplace mismatch"
                )
            if metric.product_grain_reference_id != self.product_grain_reference_id:
                raise MarketReportV0_2ValidationError(
                    "distribution metric product grain mismatch"
                )
            if metric.cohort_reference_id != self.cohort_reference_id:
                raise MarketReportV0_2ValidationError(
                    "distribution metric cohort mismatch"
                )
            expected_denominator = {
                DistributionMetricName.PRODUCT_COUNT: None,
                DistributionMetricName.PRODUCT_SHARE: self.product_denominator_reference_id,
                DistributionMetricName.SALES: None,
                DistributionMetricName.SALES_SHARE: self.sales_denominator_reference_id,
                DistributionMetricName.REVENUE: None,
                DistributionMetricName.REVENUE_SHARE: self.revenue_denominator_reference_id,
                DistributionMetricName.AVERAGE_PRICE: self.product_denominator_reference_id,
                DistributionMetricName.MEDIAN_PRICE: self.product_denominator_reference_id,
            }[name]
            if metric.denominator_reference_id != expected_denominator:
                raise MarketReportV0_2ValidationError(
                    f"distribution metric {name.value} denominator mismatch"
                )
            if name in _ECONOMIC_METRICS:
                if metric.period_reference_id != self.period_reference_id:
                    raise MarketReportV0_2ValidationError(
                        f"distribution metric {name.value} period mismatch"
                    )
            if _METRIC_TYPES[name] is MetricValueType.MONEY and (
                metric.currency != self.currency
            ):
                raise MarketReportV0_2ValidationError(
                    f"distribution metric {name.value} currency mismatch"
                )
            if metric.availability is not Availability.UNAVAILABLE and (
                metric.method_policy_id is None or metric.method_policy_version is None
            ):
                raise MarketReportV0_2ValidationError(
                    f"distribution metric {name.value} lacks governed method policy"
                )
            if metric.availability is not Availability.UNAVAILABLE and (
                metric.completeness
                in {CompletenessStatus.UNKNOWN, CompletenessStatus.UNRESOLVED}
            ):
                raise MarketReportV0_2ValidationError(
                    f"distribution metric {name.value} completeness is incompatible"
                )
            if (
                segment.membership_disclosure is MembershipDisclosure.COMPLETE
                and metric.availability is not Availability.UNAVAILABLE
                and set(metric.subject_reference_ids)
                != set(segment.member_grain_entity_reference_ids)
            ):
                raise MarketReportV0_2ValidationError(
                    f"distribution metric {name.value} subjects mismatch disclosed membership"
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


def build_distribution_segment(**content: Any) -> DistributionSegment:
    normalized = dict(content)
    if "metrics" in normalized:
        normalized["metrics"] = tuple(
            sorted(normalized["metrics"], key=lambda item: item.metric_name)
        )
    for name in (
        "member_grain_entity_reference_ids",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {"contract_version": DISTRIBUTION_SEGMENT_CONTRACT_VERSION, **normalized}
    return DistributionSegment(
        segment_id=deterministic_id(
            "market-report-v0.2-distribution-segment", material
        ),
        **material,
    )


def build_distribution_section(**content: Any) -> DistributionSectionItem:
    normalized = dict(content)
    if "declared_metric_names" in normalized:
        normalized["declared_metric_names"] = tuple(
            sorted(normalized["declared_metric_names"], key=lambda item: item.value)
        )
    if "segments" in normalized:
        normalized["segments"] = tuple(
            sorted(
                normalized["segments"],
                key=lambda item: (item.policy_ordinal, item.policy_value_id),
            )
        )
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    for name in ("evidence_ids", "provenance_reference_ids", "limitations"):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {"contract_version": DISTRIBUTION_CONTRACT_VERSION, **normalized}
    return DistributionSectionItem(
        distribution_id=deterministic_id(
            "market-report-v0.2-distribution", material
        ),
        **material,
    )


__all__ = (
    "DistributionKind",
    "DistributionMembershipMode",
    "DistributionMetricName",
    "DistributionSectionItem",
    "DistributionSegment",
    "MembershipDisclosure",
    "SegmentClassification",
    "build_distribution_section",
    "build_distribution_segment",
)
