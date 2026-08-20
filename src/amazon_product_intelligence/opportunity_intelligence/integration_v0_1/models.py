"""Read-only Opportunity Candidate integration contracts V0.1.

This package intentionally sits above the Opportunity Intelligence Foundation.
It consumes immutable upstream snapshots and records an explainable candidate
classification; it never changes an upstream conclusion or computes a score.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Self

from amazon_product_intelligence.buyer_need_map import BuyerNeedMapSnapshot
from amazon_product_intelligence.category_product_map import (
    CategoryProductMapSnapshot,
    CategoryScope,
)
from amazon_product_intelligence.competition_intelligence import (
    CompetitionIntelligenceSnapshotV0_1,
)
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    Severity,
    deterministic_id,
)
from amazon_product_intelligence.market_analysis import MarketAnalysisResult
from amazon_product_intelligence.product_attribute_extraction import (
    CanonicalProductAttributeProfile,
)
from amazon_product_intelligence.supply_demand_gap import (
    GapStrength,
    GapType,
    SupplyDemandGapSnapshot,
)


OPPORTUNITY_INTELLIGENCE_INTEGRATION_RULESET_VERSION = (
    "opportunity-intelligence-integration-v0.1"
)


class OpportunityIntegrationValidationError(ValueError):
    """Raised when an Opportunity Candidate integration contract is invalid."""


class OpportunityIntegrationSerializationError(OpportunityIntegrationValidationError):
    """Raised when strict Opportunity Candidate deserialization fails."""


class OpportunityCandidateType(StrEnum):
    """Evidence-state classifications; none is a product recommendation."""

    POTENTIAL_ENTRY_AREA = "POTENTIAL_ENTRY_AREA"
    NEEDS_VALIDATION = "NEEDS_VALIDATION"
    HIGH_COMPETITION_AREA = "HIGH_COMPETITION_AREA"
    LOW_DEMAND_AREA = "LOW_DEMAND_AREA"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class OpportunityConfidence(StrEnum):
    """Completeness confidence, deliberately separate from any opportunity score."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class OpportunityEvidenceStatus(StrEnum):
    """Availability state for evidence; UNKNOWN is never coerced to zero."""

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class CompetitionLevel(StrEnum):
    """A categorical competition observation, never a numeric score."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class CompetitionSignalName(StrEnum):
    MARKET_CONCENTRATION = "MARKET_CONCENTRATION"
    TOP_ASIN_DOMINANCE = "TOP_ASIN_DOMINANCE"
    BRAND_CONCENTRATION = "BRAND_CONCENTRATION"
    REVIEW_BARRIER = "REVIEW_BARRIER"
    PRICE_COMPETITION = "PRICE_COMPETITION"


class OpportunityEvidenceSource(StrEnum):
    BUYER_NEED_MAP = "BUYER_NEED_MAP"
    CATEGORY_PRODUCT_MAP = "CATEGORY_PRODUCT_MAP"
    SUPPLY_DEMAND_GAP = "SUPPLY_DEMAND_GAP"
    COMPETITION_INTELLIGENCE = "COMPETITION_INTELLIGENCE"
    PRODUCT_ATTRIBUTE_PROFILE = "PRODUCT_ATTRIBUTE_PROFILE"
    MARKET_ANALYSIS = "MARKET_ANALYSIS"
    UNKNOWN_ECONOMIC_EVIDENCE = "UNKNOWN_ECONOMIC_EVIDENCE"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OpportunityIntegrationValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise OpportunityIntegrationValidationError(f"{path} must be a sequence")
    return tuple(value)


def _texts(value: Sequence[str], path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    values = _tuple(value, path)
    if not allow_empty and not values:
        raise OpportunityIntegrationValidationError(f"{path} must not be empty")
    if any(type(item) is not str or not item.strip() for item in values):
        raise OpportunityIntegrationValidationError(f"{path} must contain non-empty text")
    if len(set(values)) != len(values):
        raise OpportunityIntegrationValidationError(f"{path} must contain unique values")
    return tuple(sorted(values))


def _typed_unique(value: Sequence[Any], expected: type, path: str, key) -> tuple[Any, ...]:
    values = _tuple(value, path)
    if any(not isinstance(item, expected) for item in values):
        raise OpportunityIntegrationValidationError(f"{path} contains a wrong type")
    ordered = tuple(sorted(values, key=key))
    if len({key(item) for item in ordered}) != len(ordered):
        raise OpportunityIntegrationValidationError(f"{path} contains duplicate identities")
    return ordered


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    material = model.to_dict()
    material.pop(field_name)
    return deterministic_id(prefix, material)


class _IntegrationModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except OpportunityIntegrationSerializationError:
            raise
        except (
            OpportunityIntegrationValidationError,
            ContractValidationError,
            TypeError,
            ValueError,
        ) as exc:
            raise OpportunityIntegrationSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityEvidenceReference(_IntegrationModel):
    """One immutable, typed pointer to an upstream snapshot or explicit unknown."""

    reference_id: str
    source: OpportunityEvidenceSource
    source_id: str
    record_ids: tuple[str, ...]
    missing: bool
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.reference_id, "OpportunityEvidenceReference.reference_id")
        if not isinstance(self.source, OpportunityEvidenceSource):
            raise OpportunityIntegrationValidationError("reference source is invalid")
        _text(self.source_id, "OpportunityEvidenceReference.source_id")
        object.__setattr__(self, "record_ids", _texts(self.record_ids, "reference record_ids"))
        limitations = _texts(self.limitations, "reference limitations")
        if self.missing and not limitations:
            raise OpportunityIntegrationValidationError(
                "a missing reference requires a limitation"
            )
        if self.source is OpportunityEvidenceSource.UNKNOWN_ECONOMIC_EVIDENCE and not self.missing:
            raise OpportunityIntegrationValidationError(
                "UNKNOWN_ECONOMIC_EVIDENCE must be marked missing"
            )
        object.__setattr__(self, "limitations", limitations)
        if self.reference_id != _identity("opportunity-evidence-reference", self, "reference_id"):
            raise OpportunityIntegrationValidationError("reference_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityMetricEvidence(_IntegrationModel):
    """A bounded metric or availability observation with its source records."""

    evidence_id: str
    metric_name: str
    status: OpportunityEvidenceStatus
    value: str | None
    source_record_ids: tuple[str, ...]
    source_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.evidence_id, "OpportunityMetricEvidence.evidence_id")
        _text(self.metric_name, "OpportunityMetricEvidence.metric_name")
        if not isinstance(self.status, OpportunityEvidenceStatus):
            raise OpportunityIntegrationValidationError("metric evidence status is invalid")
        _optional_text(self.value, "OpportunityMetricEvidence.value")
        records = _texts(self.source_record_ids, "metric source_record_ids")
        references = _texts(
            self.source_reference_ids,
            "metric source_reference_ids",
            allow_empty=False,
        )
        limitations = _texts(self.limitations, "metric limitations")
        if self.status is OpportunityEvidenceStatus.UNKNOWN:
            if self.value is not None or not limitations:
                raise OpportunityIntegrationValidationError(
                    "UNKNOWN metric evidence requires null value and limitations"
                )
        elif self.status is OpportunityEvidenceStatus.AVAILABLE:
            if self.value is None or not records or limitations:
                raise OpportunityIntegrationValidationError(
                    "AVAILABLE metric evidence requires a value, records, and no limitations"
                )
        elif not records or not limitations:
            raise OpportunityIntegrationValidationError(
                "PARTIAL metric evidence requires records and limitations"
            )
        object.__setattr__(self, "source_record_ids", records)
        object.__setattr__(self, "source_reference_ids", references)
        object.__setattr__(self, "limitations", limitations)
        if self.evidence_id != _identity("opportunity-metric-evidence", self, "evidence_id"):
            raise OpportunityIntegrationValidationError("metric evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandEvidence(_IntegrationModel):
    demand_evidence_id: str
    need_cluster_id: str
    metrics: tuple[OpportunityMetricEvidence, ...]
    search_evidence_record_ids: tuple[str, ...]
    review_evidence_record_ids: tuple[str, ...]
    status: OpportunityEvidenceStatus
    reliability: OpportunityConfidence

    def __post_init__(self) -> None:
        _text(self.demand_evidence_id, "DemandEvidence.demand_evidence_id")
        _text(self.need_cluster_id, "DemandEvidence.need_cluster_id")
        metrics = _typed_unique(
            self.metrics, OpportunityMetricEvidence, "demand metrics", lambda item: item.evidence_id
        )
        if not metrics:
            raise OpportunityIntegrationValidationError("demand evidence requires evaluated metrics")
        if not isinstance(self.status, OpportunityEvidenceStatus) or not isinstance(
            self.reliability, OpportunityConfidence
        ):
            raise OpportunityIntegrationValidationError("demand status or reliability is invalid")
        if self.status is OpportunityEvidenceStatus.UNKNOWN and self.reliability is not OpportunityConfidence.UNKNOWN:
            raise OpportunityIntegrationValidationError(
                "UNKNOWN demand evidence requires UNKNOWN reliability"
            )
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(
            self,
            "search_evidence_record_ids",
            _texts(self.search_evidence_record_ids, "search evidence record ids"),
        )
        object.__setattr__(
            self,
            "review_evidence_record_ids",
            _texts(self.review_evidence_record_ids, "review evidence record ids"),
        )
        if self.demand_evidence_id != _identity("opportunity-demand-evidence", self, "demand_evidence_id"):
            raise OpportunityIntegrationValidationError("demand_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class SupplyEvidence(_IntegrationModel):
    supply_evidence_id: str
    product_coverage: OpportunityMetricEvidence
    attribute_distributions: tuple[OpportunityMetricEvidence, ...]
    existing_product_ids: tuple[str, ...]
    status: OpportunityEvidenceStatus
    reliability: OpportunityConfidence

    def __post_init__(self) -> None:
        _text(self.supply_evidence_id, "SupplyEvidence.supply_evidence_id")
        if not isinstance(self.product_coverage, OpportunityMetricEvidence):
            raise OpportunityIntegrationValidationError("supply product_coverage is invalid")
        distributions = _typed_unique(
            self.attribute_distributions,
            OpportunityMetricEvidence,
            "supply attribute_distributions",
            lambda item: item.evidence_id,
        )
        if not distributions:
            raise OpportunityIntegrationValidationError("supply evidence requires attribute distributions")
        products = _texts(self.existing_product_ids, "supply existing_product_ids", allow_empty=False)
        if not isinstance(self.status, OpportunityEvidenceStatus) or not isinstance(
            self.reliability, OpportunityConfidence
        ):
            raise OpportunityIntegrationValidationError("supply status or reliability is invalid")
        if self.status is OpportunityEvidenceStatus.UNKNOWN and self.reliability is not OpportunityConfidence.UNKNOWN:
            raise OpportunityIntegrationValidationError(
                "UNKNOWN supply evidence requires UNKNOWN reliability"
            )
        object.__setattr__(self, "attribute_distributions", distributions)
        object.__setattr__(self, "existing_product_ids", products)
        if self.supply_evidence_id != _identity("opportunity-supply-evidence", self, "supply_evidence_id"):
            raise OpportunityIntegrationValidationError("supply_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionSignalEvidence(_IntegrationModel):
    signal_id: str
    signal_name: CompetitionSignalName
    status: OpportunityEvidenceStatus
    level: CompetitionLevel
    source_record_ids: tuple[str, ...]
    source_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.signal_id, "CompetitionSignalEvidence.signal_id")
        if not isinstance(self.signal_name, CompetitionSignalName):
            raise OpportunityIntegrationValidationError("competition signal_name is invalid")
        if not isinstance(self.status, OpportunityEvidenceStatus) or not isinstance(
            self.level, CompetitionLevel
        ):
            raise OpportunityIntegrationValidationError("competition signal status or level is invalid")
        records = _texts(self.source_record_ids, "competition signal record ids")
        references = _texts(
            self.source_reference_ids,
            "competition signal reference ids",
            allow_empty=False,
        )
        limitations = _texts(self.limitations, "competition signal limitations")
        if self.status is OpportunityEvidenceStatus.UNKNOWN:
            if self.level is not CompetitionLevel.UNKNOWN or not limitations:
                raise OpportunityIntegrationValidationError(
                    "UNKNOWN competition signal requires UNKNOWN level and limitations"
                )
        elif self.status is OpportunityEvidenceStatus.AVAILABLE:
            if self.level is CompetitionLevel.UNKNOWN or not records or limitations:
                raise OpportunityIntegrationValidationError(
                    "AVAILABLE competition signal requires a level, records, and no limitations"
                )
        elif not records or not limitations:
            raise OpportunityIntegrationValidationError(
                "PARTIAL competition signal requires records and limitations"
            )
        object.__setattr__(self, "source_record_ids", records)
        object.__setattr__(self, "source_reference_ids", references)
        object.__setattr__(self, "limitations", limitations)
        if self.signal_id != _identity("opportunity-competition-signal", self, "signal_id"):
            raise OpportunityIntegrationValidationError("competition signal_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitionEvidence(_IntegrationModel):
    competition_evidence_id: str
    market_concentration: CompetitionSignalEvidence
    top_asin_dominance: CompetitionSignalEvidence
    brand_concentration: CompetitionSignalEvidence
    review_barrier: CompetitionSignalEvidence
    price_competition: CompetitionSignalEvidence
    status: OpportunityEvidenceStatus
    overall_level: CompetitionLevel
    source_reference_id: str

    def __post_init__(self) -> None:
        _text(self.competition_evidence_id, "CompetitionEvidence.competition_evidence_id")
        names = (
            ("market_concentration", CompetitionSignalName.MARKET_CONCENTRATION),
            ("top_asin_dominance", CompetitionSignalName.TOP_ASIN_DOMINANCE),
            ("brand_concentration", CompetitionSignalName.BRAND_CONCENTRATION),
            ("review_barrier", CompetitionSignalName.REVIEW_BARRIER),
            ("price_competition", CompetitionSignalName.PRICE_COMPETITION),
        )
        for field_name, expected_name in names:
            signal = getattr(self, field_name)
            if not isinstance(signal, CompetitionSignalEvidence) or signal.signal_name is not expected_name:
                raise OpportunityIntegrationValidationError(
                    f"competition evidence {field_name} is invalid"
                )
        if not isinstance(self.status, OpportunityEvidenceStatus) or not isinstance(
            self.overall_level, CompetitionLevel
        ):
            raise OpportunityIntegrationValidationError("competition status or overall_level is invalid")
        if self.status is OpportunityEvidenceStatus.UNKNOWN and self.overall_level is not CompetitionLevel.UNKNOWN:
            raise OpportunityIntegrationValidationError("UNKNOWN competition evidence requires UNKNOWN level")
        if self.status is OpportunityEvidenceStatus.AVAILABLE and self.overall_level is CompetitionLevel.UNKNOWN:
            raise OpportunityIntegrationValidationError("AVAILABLE competition evidence requires a level")
        _text(self.source_reference_id, "CompetitionEvidence.source_reference_id")
        if self.competition_evidence_id != _identity(
            "opportunity-competition-evidence", self, "competition_evidence_id"
        ):
            raise OpportunityIntegrationValidationError(
                "competition_evidence_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityGapEvidence(_IntegrationModel):
    gap_evidence_id: str
    gap_id: str
    gap_type: GapType
    gap_strength: GapStrength
    reliability: OpportunityConfidence
    status: OpportunityEvidenceStatus
    source_reference_id: str
    source_metric_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.gap_evidence_id, "OpportunityGapEvidence.gap_evidence_id")
        _text(self.gap_id, "OpportunityGapEvidence.gap_id")
        if not isinstance(self.gap_type, GapType) or not isinstance(self.gap_strength, GapStrength):
            raise OpportunityIntegrationValidationError("gap type or strength is invalid")
        if not isinstance(self.reliability, OpportunityConfidence) or not isinstance(
            self.status, OpportunityEvidenceStatus
        ):
            raise OpportunityIntegrationValidationError("gap evidence reliability or status is invalid")
        if self.gap_type is GapType.INSUFFICIENT_EVIDENCE and self.status is not OpportunityEvidenceStatus.UNKNOWN:
            raise OpportunityIntegrationValidationError("insufficient gap must have UNKNOWN status")
        _text(self.source_reference_id, "OpportunityGapEvidence.source_reference_id")
        object.__setattr__(self, "source_metric_ids", _texts(self.source_metric_ids, "gap source_metric_ids"))
        if self.gap_evidence_id != _identity("opportunity-gap-evidence", self, "gap_evidence_id"):
            raise OpportunityIntegrationValidationError("gap_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class EconomicEvidence(_IntegrationModel):
    """Availability-only economic evidence. It contains no profit or return calculation."""

    economic_evidence_id: str
    price_band: OpportunityMetricEvidence
    sales_availability: OpportunityMetricEvidence
    revenue_availability: OpportunityMetricEvidence
    market_size_signal: OpportunityMetricEvidence
    status: OpportunityEvidenceStatus
    source_reference_id: str

    def __post_init__(self) -> None:
        _text(self.economic_evidence_id, "EconomicEvidence.economic_evidence_id")
        for field_name, expected_metric in (
            ("price_band", "price_band"),
            ("sales_availability", "sales_availability"),
            ("revenue_availability", "revenue_availability"),
            ("market_size_signal", "market_size_signal"),
        ):
            metric = getattr(self, field_name)
            if not isinstance(metric, OpportunityMetricEvidence) or metric.metric_name != expected_metric:
                raise OpportunityIntegrationValidationError(f"economic {field_name} is invalid")
        statuses = {
            self.price_band.status,
            self.sales_availability.status,
            self.revenue_availability.status,
            self.market_size_signal.status,
        }
        if not isinstance(self.status, OpportunityEvidenceStatus):
            raise OpportunityIntegrationValidationError("economic evidence status is invalid")
        if self.status is OpportunityEvidenceStatus.AVAILABLE and statuses != {OpportunityEvidenceStatus.AVAILABLE}:
            raise OpportunityIntegrationValidationError("AVAILABLE economic evidence requires every field")
        if self.status is OpportunityEvidenceStatus.UNKNOWN and statuses != {OpportunityEvidenceStatus.UNKNOWN}:
            raise OpportunityIntegrationValidationError("UNKNOWN economic evidence requires every field UNKNOWN")
        if self.status is OpportunityEvidenceStatus.PARTIAL and (
            statuses == {OpportunityEvidenceStatus.UNKNOWN} or statuses == {OpportunityEvidenceStatus.AVAILABLE}
        ):
            raise OpportunityIntegrationValidationError("PARTIAL economic evidence has inconsistent field states")
        _text(self.source_reference_id, "EconomicEvidence.source_reference_id")
        if self.economic_evidence_id != _identity(
            "opportunity-economic-evidence", self, "economic_evidence_id"
        ):
            raise OpportunityIntegrationValidationError("economic_evidence_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunitySegmentDefinition(_IntegrationModel):
    segment_id: str
    source_category_map_id: str
    source_category_segment_ids: tuple[str, ...]
    dimensions: tuple[str, ...]
    canonical_value_ids: tuple[str, ...]
    member_grain_product_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.segment_id, "OpportunitySegmentDefinition.segment_id")
        _text(self.source_category_map_id, "OpportunitySegmentDefinition.source_category_map_id")
        object.__setattr__(
            self,
            "source_category_segment_ids",
            _texts(self.source_category_segment_ids, "segment source ids"),
        )
        object.__setattr__(self, "dimensions", _texts(self.dimensions, "segment dimensions"))
        object.__setattr__(
            self,
            "canonical_value_ids",
            _texts(self.canonical_value_ids, "segment canonical value ids"),
        )
        object.__setattr__(
            self,
            "member_grain_product_ids",
            _texts(self.member_grain_product_ids, "segment member products", allow_empty=False),
        )
        if self.segment_id != _identity("opportunity-segment-definition", self, "segment_id"):
            raise OpportunityIntegrationValidationError("segment_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductAttributeSegment(_IntegrationModel):
    product_attribute_segment_id: str
    profile_ids: tuple[str, ...]
    attribute_distribution_ids: tuple[str, ...]
    dimensions: tuple[str, ...]
    canonical_value_ids: tuple[str, ...]
    existing_product_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.product_attribute_segment_id, "ProductAttributeSegment.product_attribute_segment_id")
        object.__setattr__(self, "profile_ids", _texts(self.profile_ids, "attribute segment profiles", allow_empty=False))
        object.__setattr__(
            self,
            "attribute_distribution_ids",
            _texts(self.attribute_distribution_ids, "attribute segment distribution ids"),
        )
        object.__setattr__(self, "dimensions", _texts(self.dimensions, "attribute segment dimensions"))
        object.__setattr__(
            self,
            "canonical_value_ids",
            _texts(self.canonical_value_ids, "attribute segment canonical value ids"),
        )
        object.__setattr__(
            self,
            "existing_product_ids",
            _texts(self.existing_product_ids, "attribute segment products", allow_empty=False),
        )
        if self.product_attribute_segment_id != _identity(
            "opportunity-product-attribute-segment", self, "product_attribute_segment_id"
        ):
            raise OpportunityIntegrationValidationError(
                "product_attribute_segment_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityCandidateDiagnostic(_IntegrationModel):
    diagnostic_id: str
    code: str
    severity: Severity
    related_evidence_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.diagnostic_id, "OpportunityCandidateDiagnostic.diagnostic_id")
        _text(self.code, "OpportunityCandidateDiagnostic.code")
        if not isinstance(self.severity, Severity):
            raise OpportunityIntegrationValidationError("candidate diagnostic severity is invalid")
        object.__setattr__(
            self,
            "related_evidence_ids",
            _texts(self.related_evidence_ids, "candidate diagnostic evidence ids"),
        )
        _text(self.message, "OpportunityCandidateDiagnostic.message")
        if self.diagnostic_id != _identity("opportunity-candidate-diagnostic", self, "diagnostic_id"):
            raise OpportunityIntegrationValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityEvidenceBundle(_IntegrationModel):
    evidence_bundle_id: str
    demand: DemandEvidence
    supply: SupplyEvidence
    competition: CompetitionEvidence
    gap: OpportunityGapEvidence
    economic: EconomicEvidence
    source_references: tuple[OpportunityEvidenceReference, ...]
    missing_evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.evidence_bundle_id, "OpportunityEvidenceBundle.evidence_bundle_id")
        for field_name, expected in (
            ("demand", DemandEvidence),
            ("supply", SupplyEvidence),
            ("competition", CompetitionEvidence),
            ("gap", OpportunityGapEvidence),
            ("economic", EconomicEvidence),
        ):
            if not isinstance(getattr(self, field_name), expected):
                raise OpportunityIntegrationValidationError(f"evidence bundle {field_name} is invalid")
        references = _typed_unique(
            self.source_references,
            OpportunityEvidenceReference,
            "evidence bundle source_references",
            lambda item: item.reference_id,
        )
        required_sources = {
            OpportunityEvidenceSource.BUYER_NEED_MAP,
            OpportunityEvidenceSource.CATEGORY_PRODUCT_MAP,
            OpportunityEvidenceSource.SUPPLY_DEMAND_GAP,
            OpportunityEvidenceSource.COMPETITION_INTELLIGENCE,
            OpportunityEvidenceSource.PRODUCT_ATTRIBUTE_PROFILE,
        }
        if not required_sources <= {item.source for item in references}:
            raise OpportunityIntegrationValidationError("evidence bundle is missing required source lineage")
        reference_ids = {item.reference_id for item in references}
        all_evidence_ids = {
            *(item.evidence_id for item in self.demand.metrics),
            self.supply.product_coverage.evidence_id,
            *(item.evidence_id for item in self.supply.attribute_distributions),
            self.competition.market_concentration.signal_id,
            self.competition.top_asin_dominance.signal_id,
            self.competition.brand_concentration.signal_id,
            self.competition.review_barrier.signal_id,
            self.competition.price_competition.signal_id,
            self.gap.gap_evidence_id,
            self.economic.price_band.evidence_id,
            self.economic.sales_availability.evidence_id,
            self.economic.revenue_availability.evidence_id,
            self.economic.market_size_signal.evidence_id,
        }
        missing = _texts(self.missing_evidence_ids, "bundle missing_evidence_ids")
        if not set(missing) <= all_evidence_ids:
            raise OpportunityIntegrationValidationError("missing evidence id is absent from bundle")
        for metric in (
            *self.demand.metrics,
            self.supply.product_coverage,
            *self.supply.attribute_distributions,
            self.economic.price_band,
            self.economic.sales_availability,
            self.economic.revenue_availability,
            self.economic.market_size_signal,
        ):
            if not set(metric.source_reference_ids) <= reference_ids:
                raise OpportunityIntegrationValidationError("metric references an absent source reference")
        for signal in (
            self.competition.market_concentration,
            self.competition.top_asin_dominance,
            self.competition.brand_concentration,
            self.competition.review_barrier,
            self.competition.price_competition,
        ):
            if not set(signal.source_reference_ids) <= reference_ids:
                raise OpportunityIntegrationValidationError("competition signal references an absent source")
        for reference_id in (
            self.competition.source_reference_id,
            self.gap.source_reference_id,
            self.economic.source_reference_id,
        ):
            if reference_id not in reference_ids:
                raise OpportunityIntegrationValidationError("evidence references an absent source reference")
        object.__setattr__(self, "source_references", references)
        object.__setattr__(self, "missing_evidence_ids", missing)
        if self.evidence_bundle_id != _identity(
            "opportunity-evidence-bundle", self, "evidence_bundle_id"
        ):
            raise OpportunityIntegrationValidationError("evidence_bundle_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityCandidateSnapshot(_IntegrationModel):
    candidate_id: str
    category_scope: CategoryScope
    segment_definition: OpportunitySegmentDefinition
    need_cluster_id: str
    product_attribute_segment: ProductAttributeSegment
    gap_reference: OpportunityEvidenceReference
    competition_reference: OpportunityEvidenceReference
    economic_reference: OpportunityEvidenceReference
    confidence: OpportunityConfidence
    status: OpportunityCandidateType
    evidence: OpportunityEvidenceBundle
    diagnostics: tuple[OpportunityCandidateDiagnostic, ...]
    ruleset_version: str = OPPORTUNITY_INTELLIGENCE_INTEGRATION_RULESET_VERSION

    def __post_init__(self) -> None:
        _text(self.candidate_id, "OpportunityCandidateSnapshot.candidate_id")
        if self.ruleset_version != OPPORTUNITY_INTELLIGENCE_INTEGRATION_RULESET_VERSION:
            raise OpportunityIntegrationValidationError("candidate ruleset_version is invalid")
        if not isinstance(self.category_scope, CategoryScope):
            raise OpportunityIntegrationValidationError("candidate category_scope is invalid")
        if not isinstance(self.segment_definition, OpportunitySegmentDefinition) or not isinstance(
            self.product_attribute_segment, ProductAttributeSegment
        ):
            raise OpportunityIntegrationValidationError("candidate segment is invalid")
        _text(self.need_cluster_id, "OpportunityCandidateSnapshot.need_cluster_id")
        for field_name, source in (
            ("gap_reference", OpportunityEvidenceSource.SUPPLY_DEMAND_GAP),
            ("competition_reference", OpportunityEvidenceSource.COMPETITION_INTELLIGENCE),
        ):
            reference = getattr(self, field_name)
            if not isinstance(reference, OpportunityEvidenceReference) or reference.source is not source:
                raise OpportunityIntegrationValidationError(f"candidate {field_name} is invalid")
        if not isinstance(self.economic_reference, OpportunityEvidenceReference) or self.economic_reference.source not in {
            OpportunityEvidenceSource.MARKET_ANALYSIS,
            OpportunityEvidenceSource.UNKNOWN_ECONOMIC_EVIDENCE,
        }:
            raise OpportunityIntegrationValidationError("candidate economic_reference is invalid")
        if not isinstance(self.confidence, OpportunityConfidence) or not isinstance(
            self.status, OpportunityCandidateType
        ):
            raise OpportunityIntegrationValidationError("candidate confidence or status is invalid")
        if not isinstance(self.evidence, OpportunityEvidenceBundle):
            raise OpportunityIntegrationValidationError("candidate evidence is invalid")
        if self.need_cluster_id != self.evidence.demand.need_cluster_id:
            raise OpportunityIntegrationValidationError("candidate need cluster differs from demand evidence")
        source_ids = {item.reference_id for item in self.evidence.source_references}
        if {
            self.gap_reference.reference_id,
            self.competition_reference.reference_id,
            self.economic_reference.reference_id,
        } - source_ids:
            raise OpportunityIntegrationValidationError("candidate references absent bundle lineage")
        if self.gap_reference.source_id != self.evidence.gap.gap_id:
            raise OpportunityIntegrationValidationError("candidate gap reference diverges from gap evidence")
        if self.competition_reference.reference_id != self.evidence.competition.source_reference_id:
            raise OpportunityIntegrationValidationError("candidate competition reference diverges")
        if self.economic_reference.reference_id != self.evidence.economic.source_reference_id:
            raise OpportunityIntegrationValidationError("candidate economic reference diverges")
        diagnostics = _typed_unique(
            self.diagnostics,
            OpportunityCandidateDiagnostic,
            "candidate diagnostics",
            lambda item: item.diagnostic_id,
        )
        object.__setattr__(self, "diagnostics", diagnostics)
        if self.candidate_id != _identity("opportunity-candidate", self, "candidate_id"):
            raise OpportunityIntegrationValidationError("candidate_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OpportunityCandidateRequest:
    """Immutable, read-only handoff of already-built upstream evidence snapshots."""

    buyer_need_map: BuyerNeedMapSnapshot
    category_product_map: CategoryProductMapSnapshot
    supply_demand_gap: SupplyDemandGapSnapshot
    competition_intelligence: CompetitionIntelligenceSnapshotV0_1
    product_attribute_profiles: tuple[CanonicalProductAttributeProfile, ...]
    market_analysis: MarketAnalysisResult | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.buyer_need_map, BuyerNeedMapSnapshot):
            raise OpportunityIntegrationValidationError("request requires BuyerNeedMapSnapshot")
        if not isinstance(self.category_product_map, CategoryProductMapSnapshot):
            raise OpportunityIntegrationValidationError("request requires CategoryProductMapSnapshot")
        if not isinstance(self.supply_demand_gap, SupplyDemandGapSnapshot):
            raise OpportunityIntegrationValidationError("request requires SupplyDemandGapSnapshot")
        if not isinstance(self.competition_intelligence, CompetitionIntelligenceSnapshotV0_1):
            raise OpportunityIntegrationValidationError(
                "request requires CompetitionIntelligenceSnapshotV0_1"
            )
        profiles = _tuple(self.product_attribute_profiles, "request product_attribute_profiles")
        if not profiles or any(not isinstance(item, CanonicalProductAttributeProfile) for item in profiles):
            raise OpportunityIntegrationValidationError(
                "request requires CanonicalProductAttributeProfile values"
            )
        if len({item.profile_id for item in profiles}) != len(profiles):
            raise OpportunityIntegrationValidationError("request profile ids must be unique")
        if self.market_analysis is not None and not isinstance(self.market_analysis, MarketAnalysisResult):
            raise OpportunityIntegrationValidationError("request market_analysis is invalid")
        category_scope = self.category_product_map.category_scope
        if self.buyer_need_map.category_scope != category_scope or self.supply_demand_gap.category_scope != category_scope:
            raise OpportunityIntegrationValidationError("request upstream category scopes do not match")
        if (
            self.buyer_need_map.marketplace != self.category_product_map.marketplace
            or self.supply_demand_gap.evidence.category_product_map.map_id
            != self.category_product_map.map_id
            or self.supply_demand_gap.evidence.buyer_need_map.map_id != self.buyer_need_map.map_id
        ):
            raise OpportunityIntegrationValidationError("request upstream snapshot continuity is invalid")
        if not any(
            item.cluster_id == self.supply_demand_gap.need_cluster_id
            for item in self.buyer_need_map.need_clusters
        ):
            raise OpportunityIntegrationValidationError("gap need cluster is absent from Buyer Need Map")
        expected_profiles = {
            item.profile_id for item in self.supply_demand_gap.evidence.product_attribute_profiles
        }
        if {item.profile_id for item in profiles} != expected_profiles:
            raise OpportunityIntegrationValidationError(
                "request profiles must exactly match Supply/Demand Gap evidence"
            )
        if self.market_analysis is not None and self.market_analysis.scope.marketplace != self.category_product_map.marketplace:
            raise OpportunityIntegrationValidationError("Market Analysis marketplace differs from category map")
        object.__setattr__(
            self,
            "product_attribute_profiles",
            tuple(sorted(profiles, key=lambda item: item.profile_id)),
        )


__all__ = (
    "OPPORTUNITY_INTELLIGENCE_INTEGRATION_RULESET_VERSION",
    "CompetitionEvidence",
    "CompetitionLevel",
    "CompetitionSignalEvidence",
    "CompetitionSignalName",
    "DemandEvidence",
    "EconomicEvidence",
    "OpportunityCandidateDiagnostic",
    "OpportunityCandidateRequest",
    "OpportunityCandidateSnapshot",
    "OpportunityCandidateType",
    "OpportunityConfidence",
    "OpportunityEvidenceBundle",
    "OpportunityEvidenceReference",
    "OpportunityEvidenceSource",
    "OpportunityEvidenceStatus",
    "OpportunityGapEvidence",
    "OpportunityIntegrationSerializationError",
    "OpportunityIntegrationValidationError",
    "OpportunityMetricEvidence",
    "OpportunitySegmentDefinition",
    "ProductAttributeSegment",
    "SupplyEvidence",
)
