"""Strict V0.2 report metadata, category, sample, and observation-window owners."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Mapping

from amazon_product_intelligence.contracts import deterministic_id

from ..version import MARKET_REPORT_V0_2_VERSION, REPORT_CONTEXT_CONTRACT_VERSION
from .common import (
    Availability,
    MarketReportV0_2ValidationError,
    V0_2Contract,
    count,
    freeze_json,
    identity,
    share,
    text,
    texts,
)


def _datetime(value: str | None, path: str, *, required: bool = True) -> None:
    if value is None:
        if required:
            raise MarketReportV0_2ValidationError(f"{path} is required")
        return
    text(value, path)
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError as exc:
        raise MarketReportV0_2ValidationError(f"{path} must be an RFC 3339 datetime") from exc
    if parsed.tzinfo is None:
        raise MarketReportV0_2ValidationError(f"{path} must include a UTC offset")


@dataclass(frozen=True, slots=True, kw_only=True)
class ReportMetadataV0_2(V0_2Contract):
    report_id: str
    report_version: str
    contract_version: str
    semantic_fingerprint: str
    generated_at: str
    producer_version: str
    operational_metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.report_version != MARKET_REPORT_V0_2_VERSION:
            raise MarketReportV0_2ValidationError("report_version must be market-report-v0.2")
        if self.contract_version != REPORT_CONTEXT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported report context version")
        for name in ("report_id", "semantic_fingerprint", "producer_version"):
            text(getattr(self, name), f"ReportMetadataV0_2.{name}")
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", self.semantic_fingerprint):
            raise MarketReportV0_2ValidationError("semantic_fingerprint must be sha256 content identity")
        _datetime(self.generated_at, "ReportMetadataV0_2.generated_at")
        object.__setattr__(
            self,
            "operational_metadata",
            freeze_json(self.operational_metadata, "ReportMetadataV0_2.operational_metadata"),
        )
        expected = deterministic_id(
            "market-report-v0.2",
            {
                "report_version": self.report_version,
                "semantic_fingerprint": self.semantic_fingerprint,
                "generated_at": self.generated_at,
            },
        )
        if self.report_id != expected:
            raise MarketReportV0_2ValidationError("report_id does not match version/fingerprint/generated_at")


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryContextV0_2(V0_2Contract):
    category_id: str
    contract_version: str
    category_name: str
    marketplace: str
    scope: str
    source_reference_id: str
    provenance_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != REPORT_CONTEXT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported category context version")
        for name in ("category_name", "scope", "source_reference_id"):
            text(getattr(self, name), f"CategoryContextV0_2.{name}")
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError("category marketplace must be uppercase text")
        object.__setattr__(self, "provenance_reference_ids", texts(self.provenance_reference_ids, "category provenance", allow_empty=False))
        if self.category_id != identity("market-report-v0.2-category", self, "category_id"):
            raise MarketReportV0_2ValidationError("category_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class SampleContextV0_2(V0_2Contract):
    sample_id: str
    contract_version: str
    availability: Availability
    analysis_cohort_reference_id: str
    sample_size: int
    unique_asin_count: int
    provider_total: int | None
    asin_coverage: float | None
    source_reference_id: str
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != REPORT_CONTEXT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported sample context version")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("sample availability is invalid")
        text(self.analysis_cohort_reference_id, "sample cohort reference")
        text(self.source_reference_id, "sample source reference")
        count(self.sample_size, "sample_size")
        count(self.unique_asin_count, "unique_asin_count")
        if self.unique_asin_count > self.sample_size:
            raise MarketReportV0_2ValidationError("unique ASIN count cannot exceed sample size")
        if self.provider_total is not None:
            count(self.provider_total, "provider_total")
            if self.unique_asin_count > self.provider_total:
                raise MarketReportV0_2ValidationError("unique ASIN count cannot exceed Provider total")
        if self.asin_coverage is not None:
            object.__setattr__(self, "asin_coverage", share(self.asin_coverage, "asin_coverage"))
        if self.provider_total:
            expected = self.unique_asin_count / self.provider_total
            if self.asin_coverage is None or abs(self.asin_coverage - expected) > 1e-12:
                raise MarketReportV0_2ValidationError("ASIN coverage must equal unique ASINs / Provider total")
        elif self.asin_coverage is not None:
            raise MarketReportV0_2ValidationError("ASIN coverage requires a positive governed Provider total")
        provenance = texts(self.provenance_reference_ids, "sample provenance", allow_empty=False)
        limitations = texts(self.limitations, "sample limitations")
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError("partial/unavailable sample requires limitations")
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.sample_id != identity("market-report-v0.2-sample", self, "sample_id"):
            raise MarketReportV0_2ValidationError("sample_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DataWindowContextV0_2(V0_2Contract):
    window_id: str
    contract_version: str
    availability: Availability
    period: str
    start_at: str | None
    end_at: str | None
    retrieved_at: str | None
    source_reference_id: str
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != REPORT_CONTEXT_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError("unsupported data-window context version")
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError("data-window availability is invalid")
        text(self.period, "data-window period")
        text(self.source_reference_id, "data-window source reference")
        _datetime(self.start_at, "data-window start_at", required=False)
        _datetime(self.end_at, "data-window end_at", required=False)
        _datetime(self.retrieved_at, "data-window retrieved_at", required=False)
        if self.start_at and self.end_at:
            start = datetime.fromisoformat(self.start_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.end_at.replace("Z", "+00:00"))
            if start > end:
                raise MarketReportV0_2ValidationError("data-window start must not follow end")
        provenance = texts(self.provenance_reference_ids, "data-window provenance", allow_empty=False)
        limitations = texts(self.limitations, "data-window limitations")
        if self.availability is Availability.UNAVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError("unavailable data window requires limitations")
        if self.availability is Availability.AVAILABLE and self.start_at is None and self.end_at is None:
            raise MarketReportV0_2ValidationError("available data window requires governed observation bounds")
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        identity_material = self.to_dict()
        identity_material.pop("window_id")
        identity_material.pop("retrieved_at")
        if self.window_id != deterministic_id("market-report-v0.2-data-window", identity_material):
            raise MarketReportV0_2ValidationError("window_id does not match content")


def _build(cls: type[V0_2Contract], prefix: str, id_name: str, content: Mapping[str, Any]):
    material = {"contract_version": REPORT_CONTEXT_CONTRACT_VERSION, **content}
    return cls(**{id_name: deterministic_id(prefix, material), **material})


def build_category_context(**content: Any) -> CategoryContextV0_2:
    content["provenance_reference_ids"] = tuple(sorted(content["provenance_reference_ids"]))
    return _build(CategoryContextV0_2, "market-report-v0.2-category", "category_id", content)


def build_sample_context(**content: Any) -> SampleContextV0_2:
    content["provenance_reference_ids"] = tuple(sorted(content["provenance_reference_ids"]))
    content["limitations"] = tuple(sorted(content["limitations"]))
    return _build(SampleContextV0_2, "market-report-v0.2-sample", "sample_id", content)


def build_data_window_context(**content: Any) -> DataWindowContextV0_2:
    content["provenance_reference_ids"] = tuple(sorted(content["provenance_reference_ids"]))
    content["limitations"] = tuple(sorted(content["limitations"]))
    material = {"contract_version": REPORT_CONTEXT_CONTRACT_VERSION, **content}
    identity_material = dict(material)
    identity_material.pop("retrieved_at", None)
    return DataWindowContextV0_2(
        window_id=deterministic_id("market-report-v0.2-data-window", identity_material),
        **material,
    )


__all__ = (
    "CategoryContextV0_2", "DataWindowContextV0_2", "ReportMetadataV0_2", "SampleContextV0_2",
    "build_category_context", "build_data_window_context", "build_sample_context",
)
