"""Top-level immutable contracts and schema validation for Market Report V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import json
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    canonical_json,
    deterministic_id,
)


MARKET_REPORT_VERSION = "market-report-v0.1"


class MarketReportValidationError(ContractValidationError):
    """Raised when a report payload violates the V0.1 reporting contract."""


class ReportAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise MarketReportValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _texts(values: tuple[str, ...], path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    if not isinstance(values, tuple):
        values = tuple(values)
    if any(type(item) is not str or not item.strip() for item in values):
        raise MarketReportValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise MarketReportValidationError(f"{path} must contain unique values")
    if not allow_empty and not values:
        raise MarketReportValidationError(f"{path} must not be empty")
    return tuple(sorted(values))


def _nonnegative(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise MarketReportValidationError(f"{path} must be a non-negative integer")
    return value


def _share(value: Any, path: str) -> float:
    if type(value) not in {int, float} or isinstance(value, bool):
        raise MarketReportValidationError(f"{path} must be a numeric share")
    normalized = float(value)
    if not 0.0 <= normalized <= 1.0:
        raise MarketReportValidationError(f"{path} must be between 0 and 1")
    return normalized


def _datetime(value: str, path: str) -> None:
    _text(value, path)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise MarketReportValidationError(f"{path} must be an RFC 3339 datetime") from exc
    if parsed.tzinfo is None:
        raise MarketReportValidationError(f"{path} must include a UTC offset")


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    payload = model.to_dict()
    payload.pop(field_name)
    return deterministic_id(prefix, payload)


def _json_copy(value: Any, path: str) -> Any:
    try:
        return json.loads(canonical_json(value))
    except ContractValidationError as exc:
        raise MarketReportValidationError(f"{path} must be JSON-compatible: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ProvenanceReference(JsonContract):
    reference_id: str
    source_module: str
    source_version: str
    source_record_id: str
    availability: ReportAvailability
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("reference_id", "source_module", "source_version", "source_record_id"):
            _text(getattr(self, name), f"ProvenanceReference.{name}")
        if not isinstance(self.availability, ReportAvailability):
            raise MarketReportValidationError("provenance availability is invalid")
        evidence = _texts(self.evidence_ids, "ProvenanceReference.evidence_ids")
        limitations = _texts(self.limitations, "ProvenanceReference.limitations")
        if self.availability is ReportAvailability.UNAVAILABLE and not limitations:
            raise MarketReportValidationError("unavailable provenance requires a limitation")
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "limitations", limitations)
        if self.reference_id != _identity("market-report-provenance", self, "reference_id"):
            raise MarketReportValidationError("provenance reference_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryInformation(JsonContract):
    category_id: str
    category_name: str
    marketplace: str
    scope: str
    provenance_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("category_id", "category_name", "scope"):
            _text(getattr(self, name), f"CategoryInformation.{name}")
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportValidationError("category marketplace must be uppercase text")
        object.__setattr__(
            self,
            "provenance_reference_ids",
            _texts(self.provenance_reference_ids, "category provenance", allow_empty=False),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DataWindow(JsonContract):
    window_id: str
    period: str
    start_at: str | None
    end_at: str | None
    availability: ReportAvailability
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.window_id, "DataWindow.window_id")
        _text(self.period, "DataWindow.period")
        if self.start_at is not None:
            _datetime(self.start_at, "DataWindow.start_at")
        if self.end_at is not None:
            _datetime(self.end_at, "DataWindow.end_at")
        if not isinstance(self.availability, ReportAvailability):
            raise MarketReportValidationError("data window availability is invalid")
        if self.start_at and self.end_at:
            start = datetime.fromisoformat(self.start_at.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.end_at.replace("Z", "+00:00"))
            if start > end:
                raise MarketReportValidationError("data window start must not follow end")
        refs = _texts(self.provenance_reference_ids, "data window provenance", allow_empty=False)
        limits = _texts(self.limitations, "data window limitations")
        if self.availability is ReportAvailability.UNAVAILABLE and not limits:
            raise MarketReportValidationError("unavailable data window requires limitations")
        object.__setattr__(self, "provenance_reference_ids", refs)
        object.__setattr__(self, "limitations", limits)
        if self.window_id != _identity("market-report-data-window", self, "window_id"):
            raise MarketReportValidationError("data window ID does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class SampleInformation(JsonContract):
    sample_id: str
    sample_size: int
    unique_asin_count: int
    provider_total: int | None
    asin_coverage: float | None
    availability: ReportAvailability
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.sample_id, "SampleInformation.sample_id")
        _nonnegative(self.sample_size, "SampleInformation.sample_size")
        _nonnegative(self.unique_asin_count, "SampleInformation.unique_asin_count")
        if self.unique_asin_count > self.sample_size:
            raise MarketReportValidationError("unique ASIN count cannot exceed sample size")
        if self.provider_total is not None:
            _nonnegative(self.provider_total, "SampleInformation.provider_total")
            if self.unique_asin_count > self.provider_total:
                raise MarketReportValidationError("unique ASIN count cannot exceed provider total")
        if self.asin_coverage is not None:
            object.__setattr__(self, "asin_coverage", _share(self.asin_coverage, "ASIN coverage"))
        if self.provider_total:
            expected = self.unique_asin_count / self.provider_total
            if self.asin_coverage is None or abs(self.asin_coverage - expected) > 1e-12:
                raise MarketReportValidationError("ASIN coverage must equal unique ASINs/provider total")
        elif self.asin_coverage is not None:
            raise MarketReportValidationError("ASIN coverage requires a positive provider total")
        if not isinstance(self.availability, ReportAvailability):
            raise MarketReportValidationError("sample availability is invalid")
        refs = _texts(self.provenance_reference_ids, "sample provenance", allow_empty=False)
        limits = _texts(self.limitations, "sample limitations")
        if self.availability is not ReportAvailability.AVAILABLE and not limits:
            raise MarketReportValidationError("partial/unavailable sample requires limitations")
        object.__setattr__(self, "provenance_reference_ids", refs)
        object.__setattr__(self, "limitations", limits)
        if self.sample_id != _identity("market-report-sample", self, "sample_id"):
            raise MarketReportValidationError("sample ID does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductAttributeValueReport(JsonContract):
    value_id: str
    display_value: str
    canonical_value: Any
    asin_count: int
    asin_share: float
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.value_id, "ProductAttributeValueReport.value_id")
        _text(self.display_value, "ProductAttributeValueReport.display_value")
        object.__setattr__(self, "canonical_value", _json_copy(self.canonical_value, "canonical_value"))
        _nonnegative(self.asin_count, "ProductAttributeValueReport.asin_count")
        object.__setattr__(self, "asin_share", _share(self.asin_share, "attribute ASIN share"))
        object.__setattr__(
            self,
            "evidence_ids",
            _texts(self.evidence_ids, "attribute value evidence", allow_empty=False),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductAttributeDistributionReport(JsonContract):
    distribution_id: str
    dimension: str
    availability: ReportAvailability
    total_product_count: int
    known_value_count: int
    unknown_count: int
    attribute_coverage: float
    unknown_rate: float
    values: tuple[ProductAttributeValueReport, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.distribution_id, "attribute distribution ID")
        _text(self.dimension, "attribute dimension")
        if not isinstance(self.availability, ReportAvailability):
            raise MarketReportValidationError("attribute availability is invalid")
        for name in ("total_product_count", "known_value_count", "unknown_count"):
            _nonnegative(getattr(self, name), f"ProductAttributeDistributionReport.{name}")
        if self.known_value_count + self.unknown_count != self.total_product_count:
            raise MarketReportValidationError("attribute known and unknown counts must sum to total")
        object.__setattr__(self, "attribute_coverage", _share(self.attribute_coverage, "attribute coverage"))
        object.__setattr__(self, "unknown_rate", _share(self.unknown_rate, "attribute unknown rate"))
        expected_coverage = self.known_value_count / self.total_product_count if self.total_product_count else 0.0
        expected_unknown = self.unknown_count / self.total_product_count if self.total_product_count else 0.0
        if abs(self.attribute_coverage - expected_coverage) > 1e-12:
            raise MarketReportValidationError("attribute coverage does not match counts")
        if abs(self.unknown_rate - expected_unknown) > 1e-12:
            raise MarketReportValidationError("attribute unknown rate does not match counts")
        values = tuple(sorted(self.values, key=lambda item: item.value_id))
        if any(not isinstance(item, ProductAttributeValueReport) for item in values):
            raise MarketReportValidationError("attribute values have a wrong type")
        if len({item.value_id for item in values}) != len(values):
            raise MarketReportValidationError("attribute values must be unique")
        if sum(item.asin_count for item in values) < self.known_value_count:
            raise MarketReportValidationError("attribute values do not cover known product count")
        evidence = _texts(self.evidence_ids, "attribute distribution evidence")
        refs = _texts(self.provenance_reference_ids, "attribute distribution provenance", allow_empty=False)
        limits = _texts(self.limitations, "attribute distribution limitations")
        if self.availability is ReportAvailability.UNAVAILABLE and not limits:
            raise MarketReportValidationError("unavailable attribute distribution requires limitations")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", refs)
        object.__setattr__(self, "limitations", limits)


# Imported after common contracts are defined so section modules can reuse them.
from .buyer_need_report import BuyerNeedReportSection  # noqa: E402
from .competition_report import CompetitionReportSection  # noqa: E402
from .opportunity_report import OpportunityReportSection  # noqa: E402


@dataclass(frozen=True, slots=True, kw_only=True)
class MarketReportSnapshot(JsonContract):
    report_id: str
    report_version: str
    generated_at: str
    pipeline_version: str
    category: CategoryInformation
    sample: SampleInformation
    data_window: DataWindow
    buyer_needs: BuyerNeedReportSection
    product_attributes: tuple[ProductAttributeDistributionReport, ...]
    competition: CompetitionReportSection
    opportunity_score: OpportunityReportSection
    provenance: tuple[ProvenanceReference, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.report_version != MARKET_REPORT_VERSION:
            raise MarketReportValidationError(f"report_version must be {MARKET_REPORT_VERSION}")
        _datetime(self.generated_at, "MarketReportSnapshot.generated_at")
        _text(self.pipeline_version, "MarketReportSnapshot.pipeline_version")
        for value, expected, name in (
            (self.category, CategoryInformation, "category"),
            (self.sample, SampleInformation, "sample"),
            (self.data_window, DataWindow, "data_window"),
            (self.buyer_needs, BuyerNeedReportSection, "buyer_needs"),
            (self.competition, CompetitionReportSection, "competition"),
            (self.opportunity_score, OpportunityReportSection, "opportunity_score"),
        ):
            if not isinstance(value, expected):
                raise MarketReportValidationError(f"{name} has a wrong type")
        attributes = tuple(sorted(self.product_attributes, key=lambda item: (item.dimension, item.distribution_id)))
        if any(not isinstance(item, ProductAttributeDistributionReport) for item in attributes):
            raise MarketReportValidationError("product_attributes contain a wrong type")
        if len({item.dimension for item in attributes}) != len(attributes):
            raise MarketReportValidationError("product attribute dimensions must be unique")
        provenance = tuple(sorted(self.provenance, key=lambda item: item.reference_id))
        if not provenance or any(not isinstance(item, ProvenanceReference) for item in provenance):
            raise MarketReportValidationError("report requires provenance references")
        if len({item.reference_id for item in provenance}) != len(provenance):
            raise MarketReportValidationError("report provenance IDs must be unique")
        known_refs = {item.reference_id for item in provenance}
        referenced = {
            *self.category.provenance_reference_ids,
            *self.sample.provenance_reference_ids,
            *self.data_window.provenance_reference_ids,
            *self.buyer_needs.provenance_reference_ids,
            *self.competition.provenance_reference_ids,
            *self.opportunity_score.provenance_reference_ids,
            *(value for item in attributes for value in item.provenance_reference_ids),
        }
        if not referenced <= known_refs:
            raise MarketReportValidationError(
                f"report sections reference absent provenance: {sorted(referenced - known_refs)}"
            )
        object.__setattr__(self, "product_attributes", attributes)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "limitations", _texts(self.limitations, "report limitations"))
        if self.report_id != _identity("market-report", self, "report_id"):
            raise MarketReportValidationError("report_id does not match report content")

    def validate(self) -> Self:
        self.__post_init__()
        return self

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":") if indent is None else None,
            indent=indent,
        )


MARKET_REPORT_JSON_SCHEMA: Mapping[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://amazon-product-intelligence.local/schema/market-report-v0.1.json",
    "title": "Market Report V0.1",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "report_id",
        "report_version",
        "generated_at",
        "pipeline_version",
        "category",
        "sample",
        "data_window",
        "buyer_needs",
        "product_attributes",
        "competition",
        "opportunity_score",
        "provenance",
        "limitations",
    ],
    "properties": {
        "report_id": {"type": "string", "minLength": 1},
        "report_version": {"const": MARKET_REPORT_VERSION},
        "generated_at": {"type": "string", "format": "date-time"},
        "pipeline_version": {"type": "string", "minLength": 1},
        "category": {"type": "object"},
        "sample": {"type": "object"},
        "data_window": {"type": "object"},
        "buyer_needs": {"type": "object"},
        "product_attributes": {"type": "array"},
        "competition": {"type": "object"},
        "opportunity_score": {"type": "object"},
        "provenance": {"type": "array", "minItems": 1},
        "limitations": {"type": "array", "items": {"type": "string"}},
    },
}


def validate_market_report_payload(payload: Mapping[str, Any]) -> MarketReportSnapshot:
    """Validate JSON shape plus all cross-record report invariants."""

    if not isinstance(payload, Mapping):
        raise MarketReportValidationError("market report payload must be an object")
    required = set(MARKET_REPORT_JSON_SCHEMA["required"])
    missing = sorted(required - set(payload))
    extra = sorted(set(payload) - required)
    if missing:
        raise MarketReportValidationError(f"market report is missing fields: {', '.join(missing)}")
    if extra:
        raise MarketReportValidationError(f"market report has unknown fields: {', '.join(extra)}")
    return MarketReportSnapshot.from_dict(payload).validate()


__all__ = (
    "MARKET_REPORT_JSON_SCHEMA",
    "MARKET_REPORT_VERSION",
    "CategoryInformation",
    "DataWindow",
    "MarketReportSnapshot",
    "MarketReportValidationError",
    "ProductAttributeDistributionReport",
    "ProductAttributeValueReport",
    "ProvenanceReference",
    "ReportAvailability",
    "SampleInformation",
    "validate_market_report_payload",
)
