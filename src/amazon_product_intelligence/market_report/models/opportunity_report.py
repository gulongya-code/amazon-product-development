"""Evidence-based Opportunity Score report contracts."""

from __future__ import annotations

from dataclasses import dataclass

from amazon_product_intelligence.contracts import JsonContract

from .report_schema import MarketReportValidationError, _text, _texts


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityDimensionReport(JsonContract):
    dimension: str
    status: str
    score_value: float | None
    contribution: float | None
    max_contribution: float
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    explanation: str

    def __post_init__(self) -> None:
        for name in ("dimension", "status", "explanation"):
            _text(getattr(self, name), f"OpportunityDimensionReport.{name}")
        for name in ("score_value", "contribution", "max_contribution"):
            value = getattr(self, name)
            if value is not None and (type(value) not in {int, float} or isinstance(value, bool) or float(value) < 0):
                raise MarketReportValidationError(f"OpportunityDimensionReport.{name} must be non-negative")
            if value is not None:
                object.__setattr__(self, name, float(value))
        if self.max_contribution is None:
            raise MarketReportValidationError("dimension max contribution is required")
        if self.status == "UNKNOWN" and (self.score_value is not None or self.contribution is not None):
            raise MarketReportValidationError("UNKNOWN dimension cannot contain a numeric score")
        object.__setattr__(
            self,
            "evidence_ids",
            _texts(self.evidence_ids, "opportunity dimension evidence", allow_empty=False),
        )
        object.__setattr__(
            self,
            "provenance_reference_ids",
            _texts(self.provenance_reference_ids, "opportunity dimension provenance", allow_empty=False),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityReportSection(JsonContract):
    score_id: str
    candidate_id: str
    score_status: str
    score_value: float | None
    confidence: str
    policy_version: str
    policy_fingerprint: str
    dimensions: tuple[OpportunityDimensionReport, ...]
    risks: tuple[str, ...]
    limitations: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "score_id",
            "candidate_id",
            "score_status",
            "confidence",
            "policy_version",
            "policy_fingerprint",
        ):
            _text(getattr(self, name), f"OpportunityReportSection.{name}")
        if self.score_value is not None:
            if (
                type(self.score_value) not in {int, float}
                or isinstance(self.score_value, bool)
                or not 0 <= float(self.score_value) <= 100
            ):
                raise MarketReportValidationError("opportunity score must be between 0 and 100")
            object.__setattr__(self, "score_value", float(self.score_value))
        if self.score_status == "PENDING_DATA" and self.score_value is not None:
            raise MarketReportValidationError("pending score cannot contain a numeric value")
        if self.score_status != "PENDING_DATA" and self.score_value is None:
            raise MarketReportValidationError("calculated score requires a numeric value")
        dimensions = tuple(sorted(self.dimensions, key=lambda item: item.dimension))
        if not dimensions or any(not isinstance(item, OpportunityDimensionReport) for item in dimensions):
            raise MarketReportValidationError("opportunity report requires dimension breakdown")
        if len({item.dimension for item in dimensions}) != len(dimensions):
            raise MarketReportValidationError("opportunity dimensions must be unique")
        refs = _texts(self.provenance_reference_ids, "opportunity section provenance", allow_empty=False)
        if not all(set(item.provenance_reference_ids) <= set(refs) for item in dimensions):
            raise MarketReportValidationError("opportunity section omits dimension provenance")
        object.__setattr__(self, "dimensions", dimensions)
        object.__setattr__(self, "risks", _texts(self.risks, "opportunity risks"))
        object.__setattr__(self, "limitations", _texts(self.limitations, "opportunity limitations"))
        object.__setattr__(
            self,
            "evidence_ids",
            _texts(self.evidence_ids, "opportunity evidence", allow_empty=False),
        )
        object.__setattr__(self, "provenance_reference_ids", refs)


__all__ = ("OpportunityDimensionReport", "OpportunityReportSection")
