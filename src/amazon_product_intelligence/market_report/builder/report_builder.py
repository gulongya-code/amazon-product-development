"""Composition-only Market Report Builder V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.adapters import (
    BuyerNeedReportAdapter,
    CompetitionReportAdapter,
    OpportunityReportAdapter,
)
from amazon_product_intelligence.market_report.models import (
    MARKET_REPORT_VERSION,
    MarketReportSnapshot,
    MarketReportValidationError,
    ProvenanceReference,
    validate_market_report_payload,
)

from .section_builder import MarketReportSectionBuilder


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketReportBuildRequest:
    category_name: str
    marketplace: str
    category_scope: str
    sample_size: int
    unique_asin_count: int
    provider_total: int | None
    data_window_period: str
    data_window_start: str | None
    data_window_end: str | None
    generated_at: str
    pipeline_version: str
    source_record_id: str
    source_evidence_ids: tuple[str, ...]
    buyer_need_output: Any
    competition_output: Any
    opportunity_score_output: Any
    category_product_map_output: Any | None = None
    market_analysis_output: Any | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "category_name",
            "marketplace",
            "category_scope",
            "data_window_period",
            "generated_at",
            "pipeline_version",
            "source_record_id",
        ):
            value = getattr(self, name)
            if type(value) is not str or not value.strip():
                raise MarketReportValidationError(f"MarketReportBuildRequest.{name} must be non-empty text")
        for name in ("sample_size", "unique_asin_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise MarketReportValidationError(f"MarketReportBuildRequest.{name} must be non-negative")
        if self.unique_asin_count > self.sample_size:
            raise MarketReportValidationError("unique ASIN count cannot exceed sample size")
        if self.provider_total is not None and (type(self.provider_total) is not int or self.provider_total < 0):
            raise MarketReportValidationError("provider_total must be a non-negative integer or null")
        if not self.source_evidence_ids or any(
            type(value) is not str or not value.strip() for value in self.source_evidence_ids
        ):
            raise MarketReportValidationError("source_evidence_ids must contain non-empty evidence IDs")
        if len(set(self.source_evidence_ids)) != len(self.source_evidence_ids):
            raise MarketReportValidationError("source_evidence_ids must be unique")
        if any(type(value) is not str or not value.strip() for value in self.limitations):
            raise MarketReportValidationError("limitations must contain non-empty text")
        object.__setattr__(self, "source_evidence_ids", tuple(sorted(self.source_evidence_ids)))
        object.__setattr__(self, "limitations", tuple(sorted(set(self.limitations))))


class MarketReportBuilderV0_1:
    """Compose already-calculated module outputs into one governed JSON report."""

    def __init__(
        self,
        *,
        buyer_need_adapter: BuyerNeedReportAdapter | None = None,
        competition_adapter: CompetitionReportAdapter | None = None,
        opportunity_adapter: OpportunityReportAdapter | None = None,
        section_builder: MarketReportSectionBuilder | None = None,
    ) -> None:
        self._buyer_need_adapter = buyer_need_adapter or BuyerNeedReportAdapter()
        self._competition_adapter = competition_adapter or CompetitionReportAdapter()
        self._opportunity_adapter = opportunity_adapter or OpportunityReportAdapter()
        self._section_builder = section_builder or MarketReportSectionBuilder()

    def build(self, request: MarketReportBuildRequest) -> MarketReportSnapshot:
        if not isinstance(request, MarketReportBuildRequest):
            raise MarketReportValidationError("build requires MarketReportBuildRequest")

        input_ref = self._section_builder.build_input_provenance(
            pipeline_version=request.pipeline_version,
            source_record_id=request.source_record_id,
            evidence_ids=request.source_evidence_ids,
            limitations=request.limitations,
        )
        category = self._section_builder.build_category(
            category_name=request.category_name,
            marketplace=request.marketplace,
            scope=request.category_scope,
            provenance_reference_id=input_ref.reference_id,
        )
        sample = self._section_builder.build_sample(
            sample_size=request.sample_size,
            unique_asin_count=request.unique_asin_count,
            provider_total=request.provider_total,
            provenance_reference_id=input_ref.reference_id,
        )
        data_window = self._section_builder.build_data_window(
            period=request.data_window_period,
            start_at=request.data_window_start,
            end_at=request.data_window_end,
            provenance_reference_id=input_ref.reference_id,
        )
        buyer_needs, buyer_refs = self._buyer_need_adapter.adapt(request.buyer_need_output)
        competition, competition_refs = self._competition_adapter.adapt(
            request.competition_output,
            market_analysis_output=request.market_analysis_output,
        )
        opportunity, opportunity_refs = self._opportunity_adapter.adapt(
            request.opportunity_score_output
        )
        attributes, attribute_refs = self._section_builder.build_product_attributes(
            request.category_product_map_output
        )
        provenance = self._unique_provenance(
            (input_ref, *buyer_refs, *competition_refs, *opportunity_refs, *attribute_refs)
        )
        limitations = tuple(sorted(set(request.limitations)))
        material = {
            "report_version": MARKET_REPORT_VERSION,
            "generated_at": request.generated_at,
            "pipeline_version": request.pipeline_version,
            "category": category,
            "sample": sample,
            "data_window": data_window,
            "buyer_needs": buyer_needs,
            "product_attributes": tuple(sorted(attributes, key=lambda item: (item.dimension, item.distribution_id))),
            "competition": competition,
            "opportunity_score": opportunity,
            "provenance": provenance,
            "limitations": limitations,
        }
        report = MarketReportSnapshot(
            report_id=deterministic_id("market-report", material),
            **material,
        )
        return validate_market_report_payload(report.to_dict())

    def write_json(
        self,
        report: MarketReportSnapshot,
        destination: str | Path,
    ) -> Path:
        validated = validate_market_report_payload(report.to_dict())
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        temporary.write_text(validated.to_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
        return target

    @staticmethod
    def _unique_provenance(
        references: tuple[ProvenanceReference, ...],
    ) -> tuple[ProvenanceReference, ...]:
        by_id: dict[str, ProvenanceReference] = {}
        for reference in references:
            existing = by_id.get(reference.reference_id)
            if existing is not None and existing != reference:
                raise MarketReportValidationError("provenance ID collision")
            by_id[reference.reference_id] = reference
        return tuple(sorted(by_id.values(), key=lambda item: item.reference_id))


__all__ = ("MarketReportBuildRequest", "MarketReportBuilderV0_1")
