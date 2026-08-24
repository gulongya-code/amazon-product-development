"""Reusable evidence/context envelope for Market Report V0.2 metrics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import METRIC_CONTEXT_CONTRACT_VERSION
from .common import (
    Availability,
    CompletenessStatus,
    EvidenceSemantics,
    MarketReportV0_2ValidationError,
    PresenceStatus,
    V0_2Contract,
    count,
    currency,
    freeze_json,
    identity,
    optional_text,
    policy_pair,
    share,
    text,
    texts,
)


class MetricValueType(StrEnum):
    COUNT = "COUNT"
    NUMBER = "NUMBER"
    MONEY = "MONEY"
    SHARE = "SHARE"
    RANGE = "RANGE"
    DISTRIBUTION = "DISTRIBUTION"


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricSampleContext(V0_2Contract):
    total_count: int | None
    included_count: int | None
    excluded_count: int | None
    unknown_count: int | None

    def __post_init__(self) -> None:
        values = (
            self.total_count,
            self.included_count,
            self.excluded_count,
            self.unknown_count,
        )
        if all(value is None for value in values):
            return
        if any(value is None for value in values):
            raise MarketReportV0_2ValidationError(
                "sample context counts must be all present or all null"
            )
        for name in ("total_count", "included_count", "excluded_count", "unknown_count"):
            count(getattr(self, name), f"MetricSampleContext.{name}")
        if self.included_count + self.excluded_count + self.unknown_count != self.total_count:
            raise MarketReportV0_2ValidationError(
                "sample context included/excluded/unknown counts must equal total"
            )

    @property
    def is_known(self) -> bool:
        return self.total_count is not None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConfidenceContext(V0_2Contract):
    value: Any
    scale: str
    method_policy_id: str
    method_policy_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", freeze_json(self.value, "ConfidenceContext.value"))
        text(self.scale, "ConfidenceContext.scale")
        policy_pair(
            self.method_policy_id,
            self.method_policy_version,
            "ConfidenceContext",
            required=True,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricContextEnvelope(V0_2Contract):
    metric_id: str
    contract_version: str
    metric_name: str
    value_type: MetricValueType
    availability: Availability
    presence_status: PresenceStatus
    evidence_semantics: EvidenceSemantics
    value: Any
    unit: str | None
    currency: str | None
    period_reference_id: str | None
    marketplace: str
    subject_reference_ids: tuple[str, ...]
    cohort_reference_id: str | None
    denominator_reference_id: str | None
    product_grain_reference_id: str
    method_policy_id: str | None
    method_policy_version: str | None
    sample_context: MetricSampleContext
    coverage: float | None
    completeness: CompletenessStatus
    confidence: ConfidenceContext | None
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != METRIC_CONTEXT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported metric context contract version")
        text(self.metric_name, "MetricContextEnvelope.metric_name")
        if not isinstance(self.value_type, MetricValueType):
            raise MarketReportV0_2ValidationError("metric value_type is invalid")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("metric availability is invalid")
        if not isinstance(self.presence_status, PresenceStatus):
            raise MarketReportV0_2ValidationError("metric presence status is invalid")
        if not isinstance(self.evidence_semantics, EvidenceSemantics):
            raise MarketReportV0_2ValidationError("metric evidence semantics is invalid")
        if not isinstance(self.completeness, CompletenessStatus):
            raise MarketReportV0_2ValidationError("metric completeness is invalid")
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError("metric marketplace must be uppercase text")
        for name in (
            "unit",
            "period_reference_id",
            "cohort_reference_id",
            "denominator_reference_id",
        ):
            optional_text(getattr(self, name), f"MetricContextEnvelope.{name}")
        text(self.product_grain_reference_id, "MetricContextEnvelope.product_grain_reference_id")
        currency(self.currency, "MetricContextEnvelope.currency")
        policy_pair(
            self.method_policy_id,
            self.method_policy_version,
            "MetricContextEnvelope.method",
        )
        if self.evidence_semantics in {EvidenceSemantics.RESOLVED, EvidenceSemantics.DERIVED}:
            policy_pair(
                self.method_policy_id,
                self.method_policy_version,
                "MetricContextEnvelope.method",
                required=True,
            )
        if not isinstance(self.sample_context, MetricSampleContext):
            raise MarketReportV0_2ValidationError("metric sample_context has a wrong type")
        if self.coverage is not None:
            object.__setattr__(self, "coverage", share(self.coverage, "MetricContextEnvelope.coverage"))
        if self.confidence is not None and not isinstance(self.confidence, ConfidenceContext):
            raise MarketReportV0_2ValidationError("metric confidence has a wrong type")

        subjects = texts(self.subject_reference_ids, "metric subjects")
        evidence = texts(self.evidence_ids, "metric evidence")
        provenance = texts(
            self.provenance_reference_ids,
            "metric provenance",
            allow_empty=False,
        )
        limitations = texts(self.limitations, "metric limitations")
        value = None if self.value is None else freeze_json(self.value, "MetricContextEnvelope.value")

        if self.presence_status is PresenceStatus.PRESENT:
            if value is None:
                raise MarketReportV0_2ValidationError("PRESENT metric requires a business value")
        elif value is not None:
            raise MarketReportV0_2ValidationError(
                "non-PRESENT metric cannot publish a business value"
            )

        if self.availability is Availability.AVAILABLE:
            if self.presence_status is not PresenceStatus.PRESENT or value is None or not evidence:
                raise MarketReportV0_2ValidationError(
                    "available metric requires PRESENT value and evidence"
                )
            if self.completeness is not CompletenessStatus.COMPLETE:
                raise MarketReportV0_2ValidationError(
                    "available metric requires COMPLETE context"
                )
        elif self.availability is Availability.PARTIAL:
            if not limitations:
                raise MarketReportV0_2ValidationError("partial metric requires limitations")
            if self.completeness is CompletenessStatus.COMPLETE:
                raise MarketReportV0_2ValidationError(
                    "partial metric must expose non-complete context"
                )
            if value is not None and not evidence:
                raise MarketReportV0_2ValidationError("partial value requires evidence")
        else:
            if value is not None or not limitations:
                raise MarketReportV0_2ValidationError(
                    "unavailable metric requires null value and limitations"
                )

        if self.presence_status is PresenceStatus.QUERY_RETURNED_EMPTY and not evidence:
            raise MarketReportV0_2ValidationError(
                "QUERY_RETURNED_EMPTY requires query evidence"
            )
        if value is None and self.evidence_semantics is not EvidenceSemantics.UNKNOWN:
            raise MarketReportV0_2ValidationError(
                "metric without a business value must use UNKNOWN evidence semantics"
            )
        if self.evidence_semantics is EvidenceSemantics.PROVIDER_ESTIMATE and not evidence:
            raise MarketReportV0_2ValidationError("Provider estimate requires evidence")

        self._validate_value(value)
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "subject_reference_ids", subjects)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.metric_id != identity("market-report-v0.2-metric", self, "metric_id"):
            raise MarketReportV0_2ValidationError("metric_id does not match metric content")

    def _validate_value(self, value: Any) -> None:
        if value is None:
            return
        if self.value_type in {
            MetricValueType.COUNT,
            MetricValueType.NUMBER,
            MetricValueType.MONEY,
            MetricValueType.SHARE,
        }:
            if type(value) not in {int, float} or isinstance(value, bool):
                raise MarketReportV0_2ValidationError(
                    f"{self.value_type.value} metric requires a numeric value"
                )
            if not math.isfinite(float(value)):
                raise MarketReportV0_2ValidationError("metric numeric value must be finite")
        if self.value_type is MetricValueType.COUNT and (
            type(value) is not int or value < 0
        ):
            raise MarketReportV0_2ValidationError("COUNT metric requires a non-negative integer")
        if self.value_type is MetricValueType.SHARE:
            share(value, "MetricContextEnvelope.value")
        if self.value_type is MetricValueType.MONEY:
            if self.currency is None:
                raise MarketReportV0_2ValidationError("MONEY metric requires explicit currency")
        elif self.currency is not None:
            raise MarketReportV0_2ValidationError("only MONEY metrics may declare currency")

    def referenced_contract_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    *self.subject_reference_ids,
                    self.product_grain_reference_id,
                    *(value for value in (
                        self.period_reference_id,
                        self.cohort_reference_id,
                        self.denominator_reference_id,
                    ) if value is not None),
                }
            )
        )


def build_metric_context(**content: Any) -> MetricContextEnvelope:
    normalized = dict(content)
    for name in (
        "subject_reference_ids",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {"contract_version": METRIC_CONTEXT_CONTRACT_VERSION, **normalized}
    return MetricContextEnvelope(
        metric_id=deterministic_id("market-report-v0.2-metric", material),
        **material,
    )


def unavailable_metric(
    *,
    metric_name: str,
    value_type: MetricValueType,
    marketplace: str,
    product_grain_reference_id: str,
    provenance_reference_ids: tuple[str, ...],
    limitations: tuple[str, ...],
    presence_status: PresenceStatus = PresenceStatus.UNKNOWN,
    evidence_ids: tuple[str, ...] = (),
    unit: str | None = None,
    currency_code: str | None = None,
    period_reference_id: str | None = None,
    subject_reference_ids: tuple[str, ...] = (),
    cohort_reference_id: str | None = None,
    denominator_reference_id: str | None = None,
) -> MetricContextEnvelope:
    return build_metric_context(
        metric_name=metric_name,
        value_type=value_type,
        availability=Availability.UNAVAILABLE,
        presence_status=presence_status,
        evidence_semantics=EvidenceSemantics.UNKNOWN,
        value=None,
        unit=unit,
        currency=currency_code,
        period_reference_id=period_reference_id,
        marketplace=marketplace,
        subject_reference_ids=subject_reference_ids,
        cohort_reference_id=cohort_reference_id,
        denominator_reference_id=denominator_reference_id,
        product_grain_reference_id=product_grain_reference_id,
        method_policy_id=None,
        method_policy_version=None,
        sample_context=MetricSampleContext(
            total_count=None,
            included_count=None,
            excluded_count=None,
            unknown_count=None,
        ),
        coverage=None,
        completeness=CompletenessStatus.UNKNOWN,
        confidence=None,
        evidence_ids=evidence_ids,
        provenance_reference_ids=provenance_reference_ids,
        limitations=limitations,
    )


__all__ = (
    "ConfidenceContext",
    "MetricContextEnvelope",
    "MetricSampleContext",
    "MetricValueType",
    "build_metric_context",
    "unavailable_metric",
)
