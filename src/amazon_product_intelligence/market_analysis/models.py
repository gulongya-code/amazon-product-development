"""Immutable Provider-neutral result contracts for Market Analysis V1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
import json
import re
from typing import Any

from amazon_product_intelligence.calculations import (
    CalculationProvenance,
    CalculationResult,
    json_value,
)
from amazon_product_intelligence.contracts import (
    DataQualityIssue,
    Unit,
    deterministic_id,
)
from amazon_product_intelligence.data_cleaning import CleanCanonicalResult

from .errors import MarketAnalysisValidationError


MARKET_ANALYSIS_VERSION = "market-analysis-v0.1"
_FIELD_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class MarketAnalysisStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"


class MarketMetricStatus(StrEnum):
    CALCULATED = "CALCULATED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MarketAnalysisValidationError(f"{name} must be non-empty text")
    return value


def _field_id(name: str, value: str) -> str:
    _text(name, value)
    if _FIELD_ID.fullmatch(value) is None:
        raise MarketAnalysisValidationError(f"{name} must be a dotted lowercase identifier")
    return value


def _nonnegative(name: str, value: int) -> int:
    if type(value) is not int or value < 0:
        raise MarketAnalysisValidationError(f"{name} must be a non-negative integer")
    return value


def _sorted_unique(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    items = tuple(values)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise MarketAnalysisValidationError(f"{name} must contain non-empty text")
    if items != tuple(sorted(set(items))):
        raise MarketAnalysisValidationError(f"{name} must be sorted and unique")
    return items


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketAnalysisRequest:
    marketplace: str
    clean_results: tuple[CleanCanonicalResult, ...]

    def __post_init__(self) -> None:
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketAnalysisValidationError("marketplace must be normalized uppercase text")
        results = tuple(sorted(self.clean_results, key=lambda item: item.run_id))
        if any(not isinstance(item, CleanCanonicalResult) for item in results):
            raise MarketAnalysisValidationError(
                "clean_results must contain CleanCanonicalResult values"
            )
        if len({item.run_id for item in results}) != len(results):
            raise MarketAnalysisValidationError("clean_results must have unique run IDs")
        object.__setattr__(self, "clean_results", results)


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketAnalysisScope:
    scope_id: str
    marketplace: str
    snapshot_at: str | None
    clean_run_ids: tuple[str, ...]
    product_ids: tuple[str, ...]
    keyword_ids: tuple[str, ...]
    providers: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketAnalysisValidationError("scope marketplace must be normalized")
        if self.snapshot_at is not None:
            _text("snapshot_at", self.snapshot_at)
        for name in ("clean_run_ids", "product_ids", "keyword_ids", "providers"):
            object.__setattr__(self, name, _sorted_unique(name, tuple(getattr(self, name))))
        expected = deterministic_id("market-analysis-scope", self.identity_material())
        if self.scope_id != expected:
            raise MarketAnalysisValidationError("scope_id does not match scope content")

    def identity_material(self) -> dict[str, Any]:
        return {
            "marketplace": self.marketplace,
            "snapshot_at": self.snapshot_at,
            "clean_run_ids": list(self.clean_run_ids),
            "product_ids": list(self.product_ids),
            "keyword_ids": list(self.keyword_ids),
            "providers": list(self.providers),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"scope_id": self.scope_id, **self.identity_material()}


@dataclass(frozen=True, slots=True, kw_only=True)
class NumericDistribution:
    minimum: Decimal
    maximum: Decimal
    mean: Decimal
    median: Decimal

    def __post_init__(self) -> None:
        for name in ("minimum", "maximum", "mean", "median"):
            value = getattr(self, name)
            if not isinstance(value, Decimal) or not value.is_finite():
                raise MarketAnalysisValidationError(f"{name} must be a finite Decimal")
        if self.minimum > self.maximum:
            raise MarketAnalysisValidationError("minimum must not exceed maximum")

    def to_dict(self) -> dict[str, str]:
        return {
            "minimum": str(self.minimum),
            "maximum": str(self.maximum),
            "mean": str(self.mean),
            "median": str(self.median),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class NumericMetricSummary:
    metric_id: str
    source_canonical_field: str
    status: MarketMetricStatus
    distribution: NumericDistribution | None
    unit: Unit | None
    total_subject_count: int
    valid_sample_count: int
    excluded_missing_count: int
    excluded_explicit_null_count: int
    excluded_unknown_count: int
    excluded_invalid_count: int
    excluded_conflict_count: int
    excluded_unit_mismatch_count: int
    partial_input_count: int
    source_observation_ids: tuple[str, ...]
    quality_issue_ids: tuple[str, ...]
    limitations: tuple[str, ...]
    provenance: CalculationProvenance | None

    def __post_init__(self) -> None:
        _field_id("metric_id", self.metric_id)
        _field_id("source_canonical_field", self.source_canonical_field)
        if not isinstance(self.status, MarketMetricStatus):
            raise MarketAnalysisValidationError("status must be MarketMetricStatus")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise MarketAnalysisValidationError("unit must be Canonical Unit or None")
        for name in (
            "total_subject_count",
            "valid_sample_count",
            "excluded_missing_count",
            "excluded_explicit_null_count",
            "excluded_unknown_count",
            "excluded_invalid_count",
            "excluded_conflict_count",
            "excluded_unit_mismatch_count",
            "partial_input_count",
        ):
            _nonnegative(name, getattr(self, name))
        if self.valid_sample_count > self.total_subject_count:
            raise MarketAnalysisValidationError("valid samples cannot exceed subject count")
        for name in ("source_observation_ids", "quality_issue_ids", "limitations"):
            object.__setattr__(self, name, _sorted_unique(name, tuple(getattr(self, name))))
        successful = self.status in {MarketMetricStatus.CALCULATED, MarketMetricStatus.PARTIAL}
        if successful:
            if self.distribution is None or self.provenance is None or self.valid_sample_count == 0:
                raise MarketAnalysisValidationError(
                    "calculated/partial metric requires samples, distribution, and provenance"
                )
        elif self.distribution is not None or self.provenance is not None:
            raise MarketAnalysisValidationError(
                "missing/blocked metric cannot contain a distribution or provenance"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "source_canonical_field": self.source_canonical_field,
            "status": self.status.value,
            "distribution": None if self.distribution is None else self.distribution.to_dict(),
            "unit": None if self.unit is None else self.unit.to_dict(),
            "total_subject_count": self.total_subject_count,
            "valid_sample_count": self.valid_sample_count,
            "excluded_missing_count": self.excluded_missing_count,
            "excluded_explicit_null_count": self.excluded_explicit_null_count,
            "excluded_unknown_count": self.excluded_unknown_count,
            "excluded_invalid_count": self.excluded_invalid_count,
            "excluded_conflict_count": self.excluded_conflict_count,
            "excluded_unit_mismatch_count": self.excluded_unit_mismatch_count,
            "partial_input_count": self.partial_input_count,
            "source_observation_ids": list(self.source_observation_ids),
            "quality_issue_ids": list(self.quality_issue_ids),
            "limitations": list(self.limitations),
            "provenance": None if self.provenance is None else self.provenance.to_dict(),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class BlockedMarketMetric:
    metric_id: str
    reason_code: str
    message: str
    dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        _field_id("blocked metric_id", self.metric_id)
        _text("reason_code", self.reason_code)
        _text("message", self.message)
        object.__setattr__(
            self,
            "dependencies",
            _sorted_unique("dependencies", tuple(self.dependencies)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "status": MarketMetricStatus.BLOCKED.value,
            "reason_code": self.reason_code,
            "message": self.message,
            "dependencies": list(self.dependencies),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketAnalysisQualitySummary:
    clean_run_count: int
    successful_clean_run_count: int
    partial_clean_run_count: int
    source_field_count: int
    fields_observed: int
    fields_missing: int
    fields_explicit_null: int
    fields_unknown: int
    fields_invalid: int
    fields_partial: int
    quality_issue_count: int
    product_subject_count: int
    keyword_subject_count: int
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "clean_run_count",
            "successful_clean_run_count",
            "partial_clean_run_count",
            "source_field_count",
            "fields_observed",
            "fields_missing",
            "fields_explicit_null",
            "fields_unknown",
            "fields_invalid",
            "fields_partial",
            "quality_issue_count",
            "product_subject_count",
            "keyword_subject_count",
        ):
            _nonnegative(name, getattr(self, name))
        object.__setattr__(self, "limitations", _sorted_unique("limitations", self.limitations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "clean_run_count": self.clean_run_count,
            "successful_clean_run_count": self.successful_clean_run_count,
            "partial_clean_run_count": self.partial_clean_run_count,
            "source_field_count": self.source_field_count,
            "fields_observed": self.fields_observed,
            "fields_missing": self.fields_missing,
            "fields_explicit_null": self.fields_explicit_null,
            "fields_unknown": self.fields_unknown,
            "fields_invalid": self.fields_invalid,
            "fields_partial": self.fields_partial,
            "quality_issue_count": self.quality_issue_count,
            "product_subject_count": self.product_subject_count,
            "keyword_subject_count": self.keyword_subject_count,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketAnalysisResult:
    analysis_id: str
    analysis_version: str
    status: MarketAnalysisStatus
    calculation_run_id: str
    scope: MarketAnalysisScope
    count_metrics: tuple[CalculationResult, ...]
    numeric_summaries: tuple[NumericMetricSummary, ...]
    quality: MarketAnalysisQualitySummary
    source_quality_issues: tuple[DataQualityIssue, ...]
    blocked_metrics: tuple[BlockedMarketMetric, ...]

    def __post_init__(self) -> None:
        if self.analysis_version != MARKET_ANALYSIS_VERSION:
            raise MarketAnalysisValidationError(
                f"analysis_version must be {MARKET_ANALYSIS_VERSION}"
            )
        if not isinstance(self.status, MarketAnalysisStatus):
            raise MarketAnalysisValidationError("status must be MarketAnalysisStatus")
        _text("calculation_run_id", self.calculation_run_id)
        if not isinstance(self.scope, MarketAnalysisScope):
            raise MarketAnalysisValidationError("scope must be MarketAnalysisScope")
        counts = tuple(sorted(self.count_metrics, key=lambda item: item.field_id))
        summaries = tuple(sorted(self.numeric_summaries, key=lambda item: item.metric_id))
        issues = tuple(sorted(self.source_quality_issues, key=lambda item: item.issue_id))
        blocked = tuple(sorted(self.blocked_metrics, key=lambda item: item.metric_id))
        if len({item.field_id for item in counts}) != len(counts):
            raise MarketAnalysisValidationError("count_metrics contain duplicate field IDs")
        if len({item.metric_id for item in summaries}) != len(summaries):
            raise MarketAnalysisValidationError("numeric_summaries contain duplicate metric IDs")
        if len({item.issue_id for item in issues}) != len(issues):
            raise MarketAnalysisValidationError("source_quality_issues contain duplicates")
        if len({item.metric_id for item in blocked}) != len(blocked):
            raise MarketAnalysisValidationError("blocked_metrics contain duplicate metric IDs")
        object.__setattr__(self, "count_metrics", counts)
        object.__setattr__(self, "numeric_summaries", summaries)
        object.__setattr__(self, "source_quality_issues", issues)
        object.__setattr__(self, "blocked_metrics", blocked)
        expected = deterministic_id("market-analysis", self.identity_material())
        if self.analysis_id != expected:
            raise MarketAnalysisValidationError("analysis_id does not match result content")

    def identity_material(self) -> dict[str, Any]:
        return {
            "analysis_version": self.analysis_version,
            "status": self.status.value,
            "calculation_run_id": self.calculation_run_id,
            "scope": self.scope.to_dict(),
            "count_metrics": [item.to_dict() for item in self.count_metrics],
            "numeric_summaries": [item.to_dict() for item in self.numeric_summaries],
            "quality": self.quality.to_dict(),
            "source_quality_issues": [item.to_dict() for item in self.source_quality_issues],
            "blocked_metrics": [item.to_dict() for item in self.blocked_metrics],
        }

    def count_metric(self, field_id: str) -> CalculationResult:
        for metric in self.count_metrics:
            if metric.field_id == field_id:
                return metric
        raise KeyError(field_id)

    def numeric_metric(self, metric_id: str) -> NumericMetricSummary:
        for metric in self.numeric_summaries:
            if metric.metric_id == metric_id:
                return metric
        raise KeyError(metric_id)

    def to_dict(self) -> dict[str, Any]:
        return {"analysis_id": self.analysis_id, **self.identity_material()}

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            json_value(self.to_dict()),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":") if indent is None else None,
            indent=indent,
        )


__all__ = (
    "MARKET_ANALYSIS_VERSION",
    "BlockedMarketMetric",
    "MarketAnalysisQualitySummary",
    "MarketAnalysisRequest",
    "MarketAnalysisResult",
    "MarketAnalysisScope",
    "MarketAnalysisStatus",
    "MarketMetricStatus",
    "NumericDistribution",
    "NumericMetricSummary",
)
