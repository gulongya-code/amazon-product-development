"""Competition section contracts with explicit unavailable semantics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from amazon_product_intelligence.contracts import JsonContract

from .report_schema import (
    MarketReportValidationError,
    ReportAvailability,
    _json_copy,
    _text,
    _texts,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionMetric(JsonContract):
    metric_name: str
    availability: ReportAvailability
    value: Any
    unit: str | None
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.metric_name, "CompetitionMetric.metric_name")
        if not isinstance(self.availability, ReportAvailability):
            raise MarketReportValidationError("competition metric availability is invalid")
        if self.unit is not None:
            _text(self.unit, "CompetitionMetric.unit")
        value = _json_copy(self.value, f"CompetitionMetric.{self.metric_name}.value")
        evidence = _texts(self.evidence_ids, "competition metric evidence")
        refs = _texts(self.provenance_reference_ids, "competition metric provenance", allow_empty=False)
        limits = _texts(self.limitations, "competition metric limitations")
        if self.availability is ReportAvailability.UNAVAILABLE:
            if value is not None or evidence or not limits:
                raise MarketReportValidationError(
                    "unavailable competition metric requires null value, no evidence, and limitations"
                )
        elif value is None or not evidence:
            raise MarketReportValidationError("available/partial competition metric requires value and evidence")
        if self.availability is ReportAvailability.PARTIAL and not limits:
            raise MarketReportValidationError("partial competition metric requires limitations")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", refs)
        object.__setattr__(self, "limitations", limits)


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionReportSection(JsonContract):
    source_record_ids: tuple[str, ...]
    status: ReportAvailability
    asin_count: CompetitionMetric
    brand_count: CompetitionMetric
    price_distribution: CompetitionMetric
    rating_distribution: CompetitionMetric
    review_distribution: CompetitionMetric
    competition_concentration: CompetitionMetric
    competition_level: CompetitionMetric
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, ReportAvailability):
            raise MarketReportValidationError("competition section status is invalid")
        object.__setattr__(
            self,
            "source_record_ids",
            _texts(self.source_record_ids, "competition source records", allow_empty=False),
        )
        metrics = (
            self.asin_count,
            self.brand_count,
            self.price_distribution,
            self.rating_distribution,
            self.review_distribution,
            self.competition_concentration,
            self.competition_level,
        )
        if any(not isinstance(item, CompetitionMetric) for item in metrics):
            raise MarketReportValidationError("competition section contains an invalid metric")
        expected_names = (
            "asin_count",
            "brand_count",
            "price_distribution",
            "rating_distribution",
            "review_distribution",
            "competition_concentration",
            "competition_level",
        )
        if tuple(item.metric_name for item in metrics) != expected_names:
            raise MarketReportValidationError("competition metric names do not match schema")
        refs = _texts(self.provenance_reference_ids, "competition section provenance", allow_empty=False)
        if not all(set(item.provenance_reference_ids) <= set(refs) for item in metrics):
            raise MarketReportValidationError("competition section omits metric provenance")
        limits = _texts(self.limitations, "competition section limitations")
        if self.status is not ReportAvailability.AVAILABLE and not limits:
            raise MarketReportValidationError("partial/unavailable competition section requires limitations")
        object.__setattr__(self, "provenance_reference_ids", refs)
        object.__setattr__(self, "limitations", limits)


__all__ = ("CompetitionMetric", "CompetitionReportSection")
