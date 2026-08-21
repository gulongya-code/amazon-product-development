"""Deterministic builders for non-intelligence Market Report sections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import (
    CategoryInformation,
    DataWindow,
    MarketReportValidationError,
    ProductAttributeDistributionReport,
    ProductAttributeValueReport,
    ProvenanceReference,
    ReportAvailability,
    SampleInformation,
)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise MarketReportValidationError(f"{path} must be a mapping or serializable contract")
    return value


def _rows(value: Any, path: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise MarketReportValidationError(f"{path} must be an array")
    return tuple(_mapping(item, f"{path}[]") for item in value)


def _reference(
    *,
    source_module: str,
    source_version: str,
    source_record_id: str,
    availability: ReportAvailability,
    evidence_ids: tuple[str, ...],
    limitations: tuple[str, ...],
) -> ProvenanceReference:
    material = {
        "source_module": source_module,
        "source_version": source_version,
        "source_record_id": source_record_id,
        "availability": availability,
        "evidence_ids": tuple(sorted(set(evidence_ids))),
        "limitations": tuple(sorted(set(limitations))),
    }
    return ProvenanceReference(
        reference_id=deterministic_id("market-report-provenance", material),
        **material,
    )


class MarketReportSectionBuilder:
    """Build descriptive report sections without deriving new intelligence."""

    def build_input_provenance(
        self,
        *,
        pipeline_version: str,
        source_record_id: str,
        evidence_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> ProvenanceReference:
        return _reference(
            source_module="market_report_pipeline_input",
            source_version=pipeline_version,
            source_record_id=source_record_id,
            availability=ReportAvailability.PARTIAL if limitations else ReportAvailability.AVAILABLE,
            evidence_ids=evidence_ids,
            limitations=limitations,
        )

    def build_category(
        self,
        *,
        category_name: str,
        marketplace: str,
        scope: str,
        provenance_reference_id: str,
    ) -> CategoryInformation:
        normalized_marketplace = marketplace.strip().upper()
        material = {
            "category_name": category_name,
            "marketplace": normalized_marketplace,
            "scope": scope,
        }
        return CategoryInformation(
            category_id=deterministic_id("market-report-category", material),
            category_name=category_name,
            marketplace=normalized_marketplace,
            scope=scope,
            provenance_reference_ids=(provenance_reference_id,),
        )

    def build_sample(
        self,
        *,
        sample_size: int,
        unique_asin_count: int,
        provider_total: int | None,
        provenance_reference_id: str,
    ) -> SampleInformation:
        coverage = unique_asin_count / provider_total if provider_total else None
        limitations: tuple[str, ...] = ()
        availability = ReportAvailability.AVAILABLE
        if provider_total is None:
            availability = ReportAvailability.PARTIAL
            limitations = ("PROVIDER_TOTAL_UNAVAILABLE",)
        elif provider_total == 0:
            availability = ReportAvailability.PARTIAL
            limitations = ("PROVIDER_TOTAL_NOT_POSITIVE",)
        material = {
            "sample_size": sample_size,
            "unique_asin_count": unique_asin_count,
            "provider_total": provider_total,
            "asin_coverage": coverage,
            "availability": availability,
            "provenance_reference_ids": (provenance_reference_id,),
            "limitations": limitations,
        }
        return SampleInformation(
            sample_id=deterministic_id("market-report-sample", material),
            **material,
        )

    def build_data_window(
        self,
        *,
        period: str,
        start_at: str | None,
        end_at: str | None,
        provenance_reference_id: str,
    ) -> DataWindow:
        if (start_at is None) != (end_at is None):
            raise MarketReportValidationError("data window requires both bounds or neither bound")
        if start_at is not None:
            availability = ReportAvailability.AVAILABLE
            limitations: tuple[str, ...] = ()
        elif period.strip().upper() != "UNKNOWN":
            availability = ReportAvailability.PARTIAL
            limitations = ("DATA_WINDOW_BOUNDS_UNAVAILABLE",)
        else:
            availability = ReportAvailability.UNAVAILABLE
            limitations = ("DATA_WINDOW_UNAVAILABLE",)
        material = {
            "period": period,
            "start_at": start_at,
            "end_at": end_at,
            "availability": availability,
            "provenance_reference_ids": (provenance_reference_id,),
            "limitations": limitations,
        }
        return DataWindow(
            window_id=deterministic_id("market-report-data-window", material),
            **material,
        )

    def build_product_attributes(
        self,
        source: Any | None,
    ) -> tuple[
        tuple[ProductAttributeDistributionReport, ...],
        tuple[ProvenanceReference, ...],
    ]:
        if source is None:
            return (), ()
        payload = _mapping(source, "Category Product Map output")
        map_id = str(payload.get("map_id") or "")
        if not map_id:
            raise MarketReportValidationError("Category Product Map output requires map_id")
        distributions = _rows(payload.get("attribute_distributions"), "attribute_distributions")
        evidence_ids = tuple(
            sorted(
                {
                    str(evidence_id)
                    for distribution in distributions
                    for evidence_id in distribution.get("evidence_reference_ids", ())
                    if str(evidence_id)
                }
            )
        )
        reference = _reference(
            source_module="category_product_map",
            source_version=str(payload.get("ruleset_version") or "UNKNOWN_VERSION"),
            source_record_id=map_id,
            availability=ReportAvailability.AVAILABLE,
            evidence_ids=evidence_ids or (map_id,),
            limitations=(),
        )
        items: list[ProductAttributeDistributionReport] = []
        for distribution in distributions:
            total = int(distribution.get("total_product_count", 0))
            known = int(distribution.get("known_value_count", 0))
            unknown = int(distribution.get("unknown_count", 0))
            raw_values = _rows(distribution.get("values", ()), "attribute distribution values")
            values = []
            for item in raw_values:
                canonical = _mapping(item.get("canonical_value"), "canonical attribute value")
                value_evidence = tuple(
                    sorted(str(value) for value in item.get("evidence_reference_ids", ()) if str(value))
                )
                values.append(
                    ProductAttributeValueReport(
                        value_id=str(canonical.get("value_id") or item.get("value_metric_id") or ""),
                        display_value=str(canonical.get("display_value") or ""),
                        canonical_value=canonical.get("value"),
                        asin_count=int(item.get("asin_count", 0)),
                        asin_share=float(item.get("asin_share", 0.0)),
                        evidence_ids=value_evidence or (str(item.get("value_metric_id") or map_id),),
                    )
                )
            if total == 0:
                availability = ReportAvailability.UNAVAILABLE
                limitations = ("ATTRIBUTE_DENOMINATOR_EMPTY",)
            elif unknown:
                availability = ReportAvailability.PARTIAL
                limitations = ("ATTRIBUTE_VALUES_PARTIAL",)
            elif not values:
                availability = ReportAvailability.UNAVAILABLE
                limitations = ("ATTRIBUTE_VALUES_UNAVAILABLE",)
            else:
                availability = ReportAvailability.AVAILABLE
                limitations = ()
            distribution_evidence = tuple(
                sorted(str(value) for value in distribution.get("evidence_reference_ids", ()) if str(value))
            )
            items.append(
                ProductAttributeDistributionReport(
                    distribution_id=str(distribution.get("distribution_id") or ""),
                    dimension=str(distribution.get("dimension") or ""),
                    availability=availability,
                    total_product_count=total,
                    known_value_count=known,
                    unknown_count=unknown,
                    attribute_coverage=float(distribution.get("attribute_coverage", 0.0)),
                    unknown_rate=float(distribution.get("unknown_rate", 0.0)),
                    values=tuple(values),
                    evidence_ids=distribution_evidence,
                    provenance_reference_ids=(reference.reference_id,),
                    limitations=limitations,
                )
            )
        return tuple(items), (reference,)


__all__ = ("MarketReportSectionBuilder",)
