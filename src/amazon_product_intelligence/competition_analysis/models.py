"""Immutable Provider-neutral contracts for Competition Analysis V1."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from amazon_product_intelligence.calculations import CalculationResult, json_value
from amazon_product_intelligence.contracts import DataQualityIssue, Provenance, Unit, deterministic_id
from amazon_product_intelligence.data_cleaning import CleanCanonicalResult
from amazon_product_intelligence.market_analysis import (
    BlockedMarketMetric,
    MarketAnalysisQualitySummary,
    MarketAnalysisScope,
    MarketAnalysisStatus,
    NumericMetricSummary,
)

from .errors import CompetitionAnalysisValidationError


COMPETITION_ANALYSIS_VERSION = "competition-analysis-v0.1"


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompetitionAnalysisValidationError(f"{name} must be non-empty text")
    return value


def _sorted_unique(name: str, values: tuple[str, ...]) -> tuple[str, ...]:
    values = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise CompetitionAnalysisValidationError(f"{name} must contain non-empty text")
    if values != tuple(sorted(set(values))):
        raise CompetitionAnalysisValidationError(f"{name} must be sorted and unique")
    return values


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionAnalysisRequest:
    marketplace: str
    clean_results: tuple[CleanCanonicalResult, ...]

    def __post_init__(self) -> None:
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise CompetitionAnalysisValidationError("marketplace must be normalized uppercase text")
        results = tuple(sorted(self.clean_results, key=lambda result: result.run_id))
        if any(not isinstance(result, CleanCanonicalResult) for result in results):
            raise CompetitionAnalysisValidationError(
                "clean_results must contain CleanCanonicalResult values"
            )
        if len({result.run_id for result in results}) != len(results):
            raise CompetitionAnalysisValidationError("clean_results must have unique run IDs")
        object.__setattr__(self, "clean_results", results)


@dataclass(frozen=True, slots=True, kw_only=True)
class BsrRankContext:
    context_id: str
    marketplace: str
    category_id: str
    category_name: str
    root: bool
    source_date: str
    date_precision: str
    unit: Unit

    def __post_init__(self) -> None:
        for name in ("marketplace", "category_id", "category_name", "source_date", "date_precision"):
            _text(name, getattr(self, name))
        if self.marketplace != self.marketplace.upper():
            raise CompetitionAnalysisValidationError("BSR marketplace must be normalized")
        if type(self.root) is not bool:
            raise CompetitionAnalysisValidationError("BSR root must be bool")
        if not isinstance(self.unit, Unit):
            raise CompetitionAnalysisValidationError("BSR context requires a Canonical Unit")
        expected = deterministic_id("competition-bsr-context", self.identity_material())
        if self.context_id != expected:
            raise CompetitionAnalysisValidationError("BSR context_id does not match content")

    def identity_material(self) -> dict[str, Any]:
        return {
            "marketplace": self.marketplace,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "root": self.root,
            "source_date": self.source_date,
            "date_precision": self.date_precision,
            "unit": self.unit.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"context_id": self.context_id, **self.identity_material()}


@dataclass(frozen=True, slots=True, kw_only=True)
class ContextualBsrSummary:
    context: BsrRankContext
    summary: NumericMetricSummary

    def __post_init__(self) -> None:
        if not isinstance(self.context, BsrRankContext):
            raise CompetitionAnalysisValidationError("context must be BsrRankContext")
        if not isinstance(self.summary, NumericMetricSummary):
            raise CompetitionAnalysisValidationError("summary must be NumericMetricSummary")
        if self.summary.source_canonical_field != "metric.bsr":
            raise CompetitionAnalysisValidationError("contextual summary must consume metric.bsr")
        if self.summary.unit != self.context.unit and self.summary.unit is not None:
            raise CompetitionAnalysisValidationError("BSR summary unit must match context")

    def to_dict(self) -> dict[str, Any]:
        return {"context": self.context.to_dict(), "summary": self.summary.to_dict()}


@dataclass(frozen=True, slots=True, kw_only=True)
class VariationRelationshipRecord:
    parent_product_id: str
    child_product_id: str
    source_observation_id: str
    raw_evidence_reference: str
    provenance: Provenance

    def __post_init__(self) -> None:
        for name in (
            "parent_product_id",
            "child_product_id",
            "source_observation_id",
            "raw_evidence_reference",
        ):
            _text(name, getattr(self, name))
        if self.parent_product_id == self.child_product_id:
            raise CompetitionAnalysisValidationError("variation relationship cannot be self-linked")
        if not isinstance(self.provenance, Provenance):
            raise CompetitionAnalysisValidationError("variation relationship requires provenance")

    def to_dict(self) -> dict[str, Any]:
        return {
            "parent_product_id": self.parent_product_id,
            "child_product_id": self.child_product_id,
            "source_observation_id": self.source_observation_id,
            "raw_evidence_reference": self.raw_evidence_reference,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class VariationStructureSummary:
    relationship_records: tuple[VariationRelationshipRecord, ...]
    source_record_count: int
    unique_parent_child_pair_count: int
    unique_parent_count: int
    unique_child_count: int
    duplicate_source_record_count: int
    incomplete_family_run_count: int
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        records = tuple(
            sorted(
                self.relationship_records,
                key=lambda record: (
                    record.parent_product_id,
                    record.child_product_id,
                    record.source_observation_id,
                ),
            )
        )
        if any(not isinstance(record, VariationRelationshipRecord) for record in records):
            raise CompetitionAnalysisValidationError("relationship_records have wrong type")
        object.__setattr__(self, "relationship_records", records)
        for name in (
            "source_record_count",
            "unique_parent_child_pair_count",
            "unique_parent_count",
            "unique_child_count",
            "duplicate_source_record_count",
            "incomplete_family_run_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise CompetitionAnalysisValidationError(f"{name} must be non-negative integer")
        if self.source_record_count != len(records):
            raise CompetitionAnalysisValidationError("source_record_count must match records")
        pairs = {(record.parent_product_id, record.child_product_id) for record in records}
        if self.unique_parent_child_pair_count != len(pairs):
            raise CompetitionAnalysisValidationError("unique pair count does not match records")
        if self.unique_parent_count != len({parent for parent, _ in pairs}):
            raise CompetitionAnalysisValidationError("unique parent count does not match records")
        if self.unique_child_count != len({child for _, child in pairs}):
            raise CompetitionAnalysisValidationError("unique child count does not match records")
        if self.duplicate_source_record_count != len(records) - len(pairs):
            raise CompetitionAnalysisValidationError("duplicate count does not match records")
        object.__setattr__(self, "limitations", _sorted_unique("limitations", self.limitations))

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_records": [record.to_dict() for record in self.relationship_records],
            "source_record_count": self.source_record_count,
            "unique_parent_child_pair_count": self.unique_parent_child_pair_count,
            "unique_parent_count": self.unique_parent_count,
            "unique_child_count": self.unique_child_count,
            "duplicate_source_record_count": self.duplicate_source_record_count,
            "incomplete_family_run_count": self.incomplete_family_run_count,
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionAnalysisResult:
    analysis_id: str
    analysis_version: str
    status: MarketAnalysisStatus
    calculation_run_id: str
    scope: MarketAnalysisScope
    observed_product_count: CalculationResult
    rating_summary: NumericMetricSummary
    review_count_summary: NumericMetricSummary
    bsr_summaries: tuple[ContextualBsrSummary, ...]
    variation_structure: VariationStructureSummary
    quality: MarketAnalysisQualitySummary
    source_quality_issues: tuple[DataQualityIssue, ...]
    blocked_metrics: tuple[BlockedMarketMetric, ...]
    base_market_analysis_id: str

    def __post_init__(self) -> None:
        if self.analysis_version != COMPETITION_ANALYSIS_VERSION:
            raise CompetitionAnalysisValidationError(
                f"analysis_version must be {COMPETITION_ANALYSIS_VERSION}"
            )
        if not isinstance(self.status, MarketAnalysisStatus):
            raise CompetitionAnalysisValidationError("status has wrong type")
        _text("calculation_run_id", self.calculation_run_id)
        _text("base_market_analysis_id", self.base_market_analysis_id)
        if not isinstance(self.scope, MarketAnalysisScope):
            raise CompetitionAnalysisValidationError("scope has wrong type")
        if not isinstance(self.observed_product_count, CalculationResult):
            raise CompetitionAnalysisValidationError("observed_product_count has wrong type")
        if not isinstance(self.rating_summary, NumericMetricSummary) or not isinstance(
            self.review_count_summary, NumericMetricSummary
        ):
            raise CompetitionAnalysisValidationError("rating/review summaries have wrong type")
        if not isinstance(self.variation_structure, VariationStructureSummary):
            raise CompetitionAnalysisValidationError("variation_structure has wrong type")
        if not isinstance(self.quality, MarketAnalysisQualitySummary):
            raise CompetitionAnalysisValidationError("quality has wrong type")
        if self.observed_product_count.field_id != "workbook.market_overview.observed_product_count":
            raise CompetitionAnalysisValidationError("wrong observed product count field")
        bsr = tuple(sorted(self.bsr_summaries, key=lambda item: item.context.context_id))
        issues = tuple(sorted(self.source_quality_issues, key=lambda item: item.issue_id))
        blocked = tuple(sorted(self.blocked_metrics, key=lambda item: item.metric_id))
        if len({item.context.context_id for item in bsr}) != len(bsr):
            raise CompetitionAnalysisValidationError("duplicate BSR contexts")
        object.__setattr__(self, "bsr_summaries", bsr)
        object.__setattr__(self, "source_quality_issues", issues)
        object.__setattr__(self, "blocked_metrics", blocked)
        expected = deterministic_id("competition-analysis", self.identity_material())
        if self.analysis_id != expected:
            raise CompetitionAnalysisValidationError("analysis_id does not match content")

    def identity_material(self) -> dict[str, Any]:
        return {
            "analysis_version": self.analysis_version,
            "status": self.status.value,
            "calculation_run_id": self.calculation_run_id,
            "scope": self.scope.to_dict(),
            "observed_product_count": self.observed_product_count.to_dict(),
            "rating_summary": self.rating_summary.to_dict(),
            "review_count_summary": self.review_count_summary.to_dict(),
            "bsr_summaries": [item.to_dict() for item in self.bsr_summaries],
            "variation_structure": self.variation_structure.to_dict(),
            "quality": self.quality.to_dict(),
            "source_quality_issues": [issue.to_dict() for issue in self.source_quality_issues],
            "blocked_metrics": [metric.to_dict() for metric in self.blocked_metrics],
            "base_market_analysis_id": self.base_market_analysis_id,
        }

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
    "COMPETITION_ANALYSIS_VERSION",
    "BsrRankContext",
    "CompetitionAnalysisRequest",
    "CompetitionAnalysisResult",
    "ContextualBsrSummary",
    "VariationRelationshipRecord",
    "VariationStructureSummary",
)
