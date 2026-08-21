"""Read-only Competition/Market Analysis to Market Report adapter."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.market_report.models import (
    CompetitionMetric,
    CompetitionReportSection,
    MarketReportValidationError,
    ProvenanceReference,
    ReportAvailability,
)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if hasattr(value, "to_dict"):
        value = value.to_dict()
    if not isinstance(value, Mapping):
        raise MarketReportValidationError(f"{path} must be a mapping or serializable contract")
    return value


def _rows(value: Any) -> tuple[Mapping[str, Any], ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _reference(payload: Mapping[str, Any], *, module: str, record_key: str, version_key: str) -> ProvenanceReference:
    record_id = str(payload.get(record_key) or "")
    if not record_id:
        raise MarketReportValidationError(f"{module} output requires {record_key}")
    evidence_ids = tuple(
        sorted(
            {
                str(value)
                for summary in (
                    *(_rows(payload.get("numeric_summaries"))),
                    *(
                        item
                        for item in (
                            payload.get("rating_summary"),
                            payload.get("review_count_summary"),
                        )
                        if isinstance(item, Mapping)
                    ),
                )
                for value in summary.get("source_observation_ids", ())
                if str(value)
            }
        )
    )
    material = {
        "source_module": module,
        "source_version": str(payload.get(version_key) or "UNKNOWN_VERSION"),
        "source_record_id": record_id,
        "availability": ReportAvailability.AVAILABLE,
        "evidence_ids": evidence_ids,
        "limitations": (),
    }
    return ProvenanceReference(
        reference_id=deterministic_id("market-report-provenance", material),
        **material,
    )


def _availability(status: Any) -> ReportAvailability:
    return {
        "CALCULATED": ReportAvailability.AVAILABLE,
        "COMPLETE": ReportAvailability.AVAILABLE,
        "AVAILABLE": ReportAvailability.AVAILABLE,
        "PARTIAL": ReportAvailability.PARTIAL,
    }.get(str(status), ReportAvailability.UNAVAILABLE)


def _unit(summary: Mapping[str, Any]) -> str | None:
    unit = summary.get("unit")
    if isinstance(unit, Mapping):
        return str(unit.get("unit_code") or unit.get("symbol") or unit.get("unit_name") or "") or None
    return str(unit) if unit else None


def _metric_from_summary(
    name: str, summary: Mapping[str, Any] | None, reference: ProvenanceReference, *, fallback_id: str
) -> CompetitionMetric:
    if not isinstance(summary, Mapping):
        return CompetitionMetric(
            metric_name=name,
            availability=ReportAvailability.UNAVAILABLE,
            value=None,
            unit=None,
            evidence_ids=(),
            provenance_reference_ids=(reference.reference_id,),
            limitations=(f"{name.upper()}_UNAVAILABLE",),
        )
    status = _availability(summary.get("status"))
    distribution = summary.get("distribution")
    evidence = tuple(sorted(str(value) for value in summary.get("source_observation_ids", ()) if str(value)))
    if status is ReportAvailability.UNAVAILABLE or not isinstance(distribution, Mapping):
        limitations = tuple(sorted(str(value) for value in summary.get("limitations", ()) if str(value)))
        return CompetitionMetric(
            metric_name=name,
            availability=ReportAvailability.UNAVAILABLE,
            value=None,
            unit=None,
            evidence_ids=(),
            provenance_reference_ids=(reference.reference_id,),
            limitations=limitations or (f"{name.upper()}_UNAVAILABLE",),
        )
    if not evidence:
        evidence = (str(summary.get("metric_id") or fallback_id),)
    limitations = tuple(sorted(str(value) for value in summary.get("limitations", ()) if str(value)))
    if status is ReportAvailability.PARTIAL and not limitations:
        limitations = (f"{name.upper()}_PARTIAL",)
    return CompetitionMetric(
        metric_name=name,
        availability=status,
        value={str(key): value for key, value in distribution.items()},
        unit=_unit(summary),
        evidence_ids=evidence,
        provenance_reference_ids=(reference.reference_id,),
        limitations=limitations,
    )


def _explicit_metric(
    name: str, value: Any, reference: ProvenanceReference, *, unavailable_code: str
) -> CompetitionMetric:
    if value is None:
        return CompetitionMetric(
            metric_name=name,
            availability=ReportAvailability.UNAVAILABLE,
            value=None,
            unit=None,
            evidence_ids=(),
            provenance_reference_ids=(reference.reference_id,),
            limitations=(unavailable_code,),
        )
    if isinstance(value, Mapping):
        status = _availability(value.get("status", "AVAILABLE"))
        metric_value = value.get("value")
        evidence = tuple(sorted(str(item) for item in value.get("evidence_ids", ()) if str(item)))
        limitations = tuple(sorted(str(item) for item in value.get("limitations", ()) if str(item)))
        unit = str(value.get("unit")) if value.get("unit") else None
    else:
        status = ReportAvailability.AVAILABLE
        metric_value = value
        evidence = (reference.source_record_id,)
        limitations = ()
        unit = None
    if status is ReportAvailability.UNAVAILABLE or metric_value is None:
        return CompetitionMetric(
            metric_name=name,
            availability=ReportAvailability.UNAVAILABLE,
            value=None,
            unit=None,
            evidence_ids=(),
            provenance_reference_ids=(reference.reference_id,),
            limitations=limitations or (unavailable_code,),
        )
    if not evidence:
        evidence = (reference.source_record_id,)
    if status is ReportAvailability.PARTIAL and not limitations:
        limitations = (f"{name.upper()}_PARTIAL",)
    return CompetitionMetric(
        metric_name=name,
        availability=status,
        value=metric_value,
        unit=unit,
        evidence_ids=evidence,
        provenance_reference_ids=(reference.reference_id,),
        limitations=limitations,
    )


class CompetitionReportAdapter:
    """Join existing Competition Analysis and optional Market Analysis outputs."""

    def adapt(
        self,
        competition_output: Any,
        *,
        market_analysis_output: Any | None = None,
    ) -> tuple[CompetitionReportSection, tuple[ProvenanceReference, ...]]:
        competition = _mapping(competition_output, "Competition Analysis output")
        competition_ref = _reference(
            competition,
            module="competition_analysis",
            record_key="analysis_id",
            version_key="analysis_version",
        )
        market = (
            _mapping(market_analysis_output, "Market Analysis output")
            if market_analysis_output is not None
            else None
        )
        market_ref = (
            _reference(
                market,
                module="market_analysis",
                record_key="analysis_id",
                version_key="analysis_version",
            )
            if market is not None
            else None
        )
        refs = tuple(item for item in (competition_ref, market_ref) if item is not None)
        ref_ids = tuple(item.reference_id for item in refs)

        observed = competition.get("observed_product_count")
        if (
            isinstance(observed, Mapping)
            and _availability(observed.get("status"))
            is not ReportAvailability.UNAVAILABLE
            and observed.get("value") is not None
        ):
            observed_availability = _availability(observed.get("status"))
            observed_limitations = tuple(
                sorted(str(value) for value in observed.get("limitations", ()) if str(value))
            )
            if observed_availability is ReportAvailability.PARTIAL and not observed_limitations:
                observed_limitations = ("ASIN_COUNT_PARTIAL",)
            asin_count = CompetitionMetric(
                metric_name="asin_count",
                availability=observed_availability,
                value=observed.get("value"),
                unit=None,
                evidence_ids=(
                    str(observed.get("result_id") or competition_ref.source_record_id),
                ),
                provenance_reference_ids=(competition_ref.reference_id,),
                limitations=observed_limitations,
            )
        else:
            asin_count = _explicit_metric(
                "asin_count",
                competition.get("asin_count"),
                competition_ref,
                unavailable_code="ASIN_COUNT_UNAVAILABLE",
            )

        numeric = _rows(market.get("numeric_summaries")) if market is not None else ()
        numeric_by_id = {str(item.get("metric_id")): item for item in numeric}
        price = _metric_from_summary(
            "price_distribution",
            numeric_by_id.get("market_analysis.observed_product_price"),
            market_ref or competition_ref,
            fallback_id="market_analysis.observed_product_price",
        )
        rating_source = competition.get("rating_summary") or numeric_by_id.get(
            "market_analysis.product_rating"
        )
        review_source = competition.get("review_count_summary") or numeric_by_id.get(
            "market_analysis.product_review_count"
        )
        rating = _metric_from_summary(
            "rating_distribution",
            rating_source if isinstance(rating_source, Mapping) else None,
            (
                competition_ref
                if competition.get("rating_summary")
                else (market_ref or competition_ref)
            ),
            fallback_id="market_analysis.product_rating",
        )
        reviews = _metric_from_summary(
            "review_distribution",
            review_source if isinstance(review_source, Mapping) else None,
            (
                competition_ref
                if competition.get("review_count_summary")
                else (market_ref or competition_ref)
            ),
            fallback_id="market_analysis.product_review_count",
        )
        brand = _explicit_metric(
            "brand_count",
            competition.get("brand_count"),
            competition_ref,
            unavailable_code="BRAND_IDENTITY_UNAVAILABLE",
        )
        concentration = _explicit_metric(
            "competition_concentration",
            competition.get(
                "competition_concentration", competition.get("market_concentration")
            ),
            competition_ref,
            unavailable_code="COMPETITION_CONCENTRATION_UNAVAILABLE",
        )
        level = _explicit_metric(
            "competition_level",
            competition.get("competition_level", competition.get("level")),
            competition_ref,
            unavailable_code="COMPETITION_LEVEL_UNAVAILABLE",
        )
        metrics = (asin_count, brand, price, rating, reviews, concentration, level)
        unavailable = tuple(
            item.metric_name
            for item in metrics
            if item.availability is ReportAvailability.UNAVAILABLE
        )
        partial = tuple(
            item.metric_name
            for item in metrics
            if item.availability is ReportAvailability.PARTIAL
        )
        status = (
            ReportAvailability.AVAILABLE
            if not unavailable and not partial
            else ReportAvailability.PARTIAL
            if any(item.availability is not ReportAvailability.UNAVAILABLE for item in metrics)
            else ReportAvailability.UNAVAILABLE
        )
        limitations = tuple(
            sorted(
                {
                    *(f"UNAVAILABLE:{name}" for name in unavailable),
                    *(f"PARTIAL:{name}" for name in partial),
                }
            )
        )
        section = CompetitionReportSection(
            source_record_ids=tuple(item.source_record_id for item in refs),
            status=status,
            asin_count=asin_count,
            brand_count=brand,
            price_distribution=price,
            rating_distribution=rating,
            review_distribution=reviews,
            competition_concentration=concentration,
            competition_level=level,
            provenance_reference_ids=ref_ids,
            limitations=limitations,
        )
        return section, refs


__all__ = ("CompetitionReportAdapter",)
