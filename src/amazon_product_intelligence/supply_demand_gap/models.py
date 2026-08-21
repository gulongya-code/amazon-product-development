"""Immutable Supply/Demand Gap Analysis contracts V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.buyer_need_map import (
    BuyerNeedMapEvidenceType,
    BuyerNeedMapSnapshot,
    DemandMetricResult,
    DemandMetricStatus,
    DemandMetricType,
)
from amazon_product_intelligence.category_product_map import (
    AnalysisWindow,
    AnalysisWindowStatus,
    CategoryProductMapSnapshot,
    CategoryScope,
)
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    ProductIdentity,
    Severity,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.product_attribute_extraction import (
    CanonicalProductAttributeProfile,
)

from .errors import SupplyDemandGapSerializationError, SupplyDemandGapValidationError


SUPPLY_DEMAND_GAP_RULESET_VERSION = "supply-demand-gap-v0.1"
GAP_TYPE_REGISTRY_VERSION = "supply-demand-gap-types-v0.1"
GAP_CLASSIFICATION_POLICY_VERSION = "supply-demand-gap-classification-v0.1"


class GapType(StrEnum):
    HIGH_DEMAND_LOW_SUPPLY = "HIGH_DEMAND_LOW_SUPPLY"
    HIGH_DEMAND_HIGH_SUPPLY = "HIGH_DEMAND_HIGH_SUPPLY"
    LOW_DEMAND_LOW_SUPPLY = "LOW_DEMAND_LOW_SUPPLY"
    LOW_DEMAND_HIGH_SUPPLY = "LOW_DEMAND_HIGH_SUPPLY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class GapStrength(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class GapSignalBand(StrEnum):
    HIGH = "HIGH"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class GapSignalStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class GapConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class SupplyMetricType(StrEnum):
    PRODUCT_COVERAGE_SHARE = "PRODUCT_COVERAGE_SHARE"
    ATTRIBUTE_COVERAGE = "ATTRIBUTE_COVERAGE"
    MATCHING_PRODUCT_COUNT = "MATCHING_PRODUCT_COUNT"
    COMPETITION_EVIDENCE = "COMPETITION_EVIDENCE"


_DEMAND_TYPES = frozenset(
    {
        DemandMetricType.SEARCH_DEMAND_SHARE,
        DemandMetricType.REVIEW_MENTION_SHARE,
        DemandMetricType.SALES_ASSOCIATED_SHARE,
        DemandMetricType.REVENUE_ASSOCIATED_SHARE,
    }
)


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise SupplyDemandGapValidationError(f"{path} must be non-empty text")
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SupplyDemandGapValidationError(f"{path} must be a sequence")
    return tuple(value)


def _decimal(value: str, path: str, *, share: bool = False) -> Decimal:
    if type(value) is not str or not value.strip():
        raise SupplyDemandGapValidationError(f"{path} must be decimal text")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise SupplyDemandGapValidationError(f"{path} must be decimal text") from exc
    if not result.is_finite() or result < 0 or (share and result > 1):
        raise SupplyDemandGapValidationError(f"{path} is outside its valid range")
    return result


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise SupplyDemandGapValidationError(f"{path} must contain finite JSON data: {exc}") from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def _without_id(model: JsonContract, field_name: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field_name)
    return payload


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    return deterministic_id(prefix, _without_id(model, field_name))


class _GapModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except SupplyDemandGapValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise SupplyDemandGapSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class GapTypeDefinition(_GapModel):
    definition_id: str
    gap_type: GapType
    demand_band: GapSignalBand
    supply_band: GapSignalBand
    definition: str

    def __post_init__(self) -> None:
        if not isinstance(self.gap_type, GapType):
            raise SupplyDemandGapValidationError("gap type definition has an invalid gap_type")
        if not isinstance(self.demand_band, GapSignalBand) or not isinstance(
            self.supply_band, GapSignalBand
        ):
            raise SupplyDemandGapValidationError("gap type definition has an invalid signal band")
        _text(self.definition, "GapTypeDefinition.definition")
        unknown = self.gap_type is GapType.INSUFFICIENT_EVIDENCE
        if unknown != (
            self.demand_band is GapSignalBand.UNKNOWN
            and self.supply_band is GapSignalBand.UNKNOWN
        ):
            raise SupplyDemandGapValidationError(
                "only INSUFFICIENT_EVIDENCE may use UNKNOWN/UNKNOWN bands"
            )
        if not unknown and GapSignalBand.UNKNOWN in {self.demand_band, self.supply_band}:
            raise SupplyDemandGapValidationError("classified gap types require known signal bands")
        if self.definition_id != _identity("gap-type-definition", self, "definition_id"):
            raise SupplyDemandGapValidationError("definition_id does not match definition content")


@dataclass(frozen=True, slots=True, kw_only=True)
class GapTypeRegistry(_GapModel):
    registry_id: str
    registry_version: str
    definitions: tuple[GapTypeDefinition, ...]

    def __post_init__(self) -> None:
        if self.registry_version != GAP_TYPE_REGISTRY_VERSION:
            raise SupplyDemandGapValidationError("invalid Gap Type Registry version")
        definitions = _tuple(self.definitions, "GapTypeRegistry.definitions")
        if any(not isinstance(item, GapTypeDefinition) for item in definitions):
            raise SupplyDemandGapValidationError("Gap Type Registry contains a wrong type")
        if {item.gap_type for item in definitions} != set(GapType):
            raise SupplyDemandGapValidationError("Gap Type Registry must define every gap type")
        band_pairs = [(item.demand_band, item.supply_band) for item in definitions]
        if len(set(band_pairs)) != len(band_pairs):
            raise SupplyDemandGapValidationError("Gap Type Registry band pairs must be unique")
        object.__setattr__(self, "definitions", tuple(sorted(definitions, key=lambda item: item.gap_type.value)))
        if self.registry_id != _identity("gap-type-registry", self, "registry_id"):
            raise SupplyDemandGapValidationError("registry_id does not match Gap Type Registry content")

    def for_bands(self, demand_band: GapSignalBand, supply_band: GapSignalBand) -> GapType:
        match = next(
            (
                item.gap_type
                for item in self.definitions
                if item.demand_band is demand_band and item.supply_band is supply_band
            ),
            None,
        )
        if match is None:
            return GapType.INSUFFICIENT_EVIDENCE
        return match


@dataclass(frozen=True, slots=True, kw_only=True)
class GapClassificationPolicy(_GapModel):
    policy_id: str
    policy_version: str
    high_demand_threshold: str
    high_supply_threshold: str
    medium_gap_margin: str
    high_gap_margin: str
    minimum_high_strength_demand_metric_coverage: str
    minimum_high_strength_supply_metric_coverage: str

    def __post_init__(self) -> None:
        if self.policy_version != GAP_CLASSIFICATION_POLICY_VERSION:
            raise SupplyDemandGapValidationError("invalid Gap Classification Policy version")
        for name in (
            "high_demand_threshold",
            "high_supply_threshold",
            "medium_gap_margin",
            "high_gap_margin",
            "minimum_high_strength_demand_metric_coverage",
            "minimum_high_strength_supply_metric_coverage",
        ):
            _decimal(getattr(self, name), f"GapClassificationPolicy.{name}", share=True)
        if Decimal(self.medium_gap_margin) > Decimal(self.high_gap_margin):
            raise SupplyDemandGapValidationError("medium gap margin must not exceed high gap margin")
        if self.policy_id != _identity("gap-classification-policy", self, "policy_id"):
            raise SupplyDemandGapValidationError("policy_id does not match classification policy content")


@dataclass(frozen=True, slots=True, kw_only=True)
class GapMetricConfidence(_GapModel):
    level: GapConfidenceLevel
    evidence_coverage: str | None
    basis: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.level, GapConfidenceLevel):
            raise SupplyDemandGapValidationError("gap metric confidence level is invalid")
        if self.evidence_coverage is not None:
            _decimal(self.evidence_coverage, "GapMetricConfidence.evidence_coverage", share=True)
        basis = _tuple(self.basis, "GapMetricConfidence.basis")
        if not basis or any(type(item) is not str or not item.strip() for item in basis):
            raise SupplyDemandGapValidationError("gap metric confidence requires a basis")
        if len(set(basis)) != len(basis):
            raise SupplyDemandGapValidationError("gap metric confidence basis must be unique")
        if self.level is GapConfidenceLevel.UNKNOWN and self.evidence_coverage is not None:
            raise SupplyDemandGapValidationError("UNKNOWN confidence cannot claim evidence coverage")
        if self.level is not GapConfidenceLevel.UNKNOWN and self.evidence_coverage is None:
            raise SupplyDemandGapValidationError("known confidence requires evidence coverage")
        object.__setattr__(self, "basis", tuple(sorted(basis)))


@dataclass(frozen=True, slots=True, kw_only=True)
class GapSupplyMetric(_GapModel):
    supply_metric_id: str
    metric_type: SupplyMetricType
    metric_scope_id: str
    status: GapSignalStatus
    value: Any
    unit: str | None
    source_metric_id: str | None
    denominator_id: str | None
    confidence: GapMetricConfidence
    evidence_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.metric_type, SupplyMetricType):
            raise SupplyDemandGapValidationError("supply metric type is invalid")
        _text(self.metric_scope_id, "GapSupplyMetric.metric_scope_id")
        if not isinstance(self.status, GapSignalStatus):
            raise SupplyDemandGapValidationError("supply metric status is invalid")
        if self.unit is not None:
            _text(self.unit, "GapSupplyMetric.unit")
        if self.source_metric_id is not None:
            _text(self.source_metric_id, "GapSupplyMetric.source_metric_id")
        if self.denominator_id is not None:
            _text(self.denominator_id, "GapSupplyMetric.denominator_id")
        if not isinstance(self.confidence, GapMetricConfidence):
            raise SupplyDemandGapValidationError("supply metric confidence has a wrong type")
        evidence = _tuple(self.evidence_reference_ids, "GapSupplyMetric.evidence_reference_ids")
        limitations = _tuple(self.limitations, "GapSupplyMetric.limitations")
        if any(type(item) is not str or not item.strip() for item in evidence + limitations):
            raise SupplyDemandGapValidationError("supply metric evidence and limitations require text")
        if len(set(evidence)) != len(evidence) or len(set(limitations)) != len(limitations):
            raise SupplyDemandGapValidationError("supply metric evidence and limitations must be unique")
        frozen = _freeze_json(self.value, "GapSupplyMetric.value")
        if self.status is GapSignalStatus.UNKNOWN:
            if frozen is not None or self.unit is not None or self.denominator_id is not None or evidence:
                raise SupplyDemandGapValidationError(
                    "UNKNOWN supply metric cannot publish value, unit, denominator, or evidence"
                )
            if self.confidence.level is not GapConfidenceLevel.UNKNOWN or not limitations:
                raise SupplyDemandGapValidationError(
                    "UNKNOWN supply metric requires UNKNOWN confidence and limitations"
                )
        else:
            if frozen is None or not evidence:
                raise SupplyDemandGapValidationError("measured supply metric requires value and evidence")
            if self.confidence.level is GapConfidenceLevel.UNKNOWN:
                raise SupplyDemandGapValidationError("measured supply metric requires known confidence")
            if self.status is GapSignalStatus.PARTIAL and not limitations:
                raise SupplyDemandGapValidationError("PARTIAL supply metric requires limitations")
            if self.metric_type is SupplyMetricType.PRODUCT_COVERAGE_SHARE:
                if type(frozen) is not str:
                    raise SupplyDemandGapValidationError("product coverage share must be decimal text")
                _decimal(frozen, "GapSupplyMetric.value", share=True)
        object.__setattr__(self, "value", frozen)
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))
        object.__setattr__(self, "limitations", tuple(sorted(limitations)))
        if self.supply_metric_id != _identity("gap-supply-metric", self, "supply_metric_id"):
            raise SupplyDemandGapValidationError("supply_metric_id does not match metric content")


@dataclass(frozen=True, slots=True, kw_only=True)
class GapConfidence(_GapModel):
    level: GapConfidenceLevel
    demand_confidence: GapConfidenceLevel
    supply_confidence: GapConfidenceLevel
    demand_metric_coverage: str
    supply_metric_coverage: str
    evidence_completeness: str
    basis: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("level", "demand_confidence", "supply_confidence"):
            if not isinstance(getattr(self, name), GapConfidenceLevel):
                raise SupplyDemandGapValidationError(f"GapConfidence.{name} is invalid")
        for name in (
            "demand_metric_coverage",
            "supply_metric_coverage",
            "evidence_completeness",
        ):
            _decimal(getattr(self, name), f"GapConfidence.{name}", share=True)
        basis = _tuple(self.basis, "GapConfidence.basis")
        if not basis or any(type(item) is not str or not item.strip() for item in basis):
            raise SupplyDemandGapValidationError("gap confidence requires a basis")
        if len(set(basis)) != len(basis):
            raise SupplyDemandGapValidationError("gap confidence basis must be unique")
        if GapConfidenceLevel.UNKNOWN in {self.demand_confidence, self.supply_confidence}:
            if self.level is not GapConfidenceLevel.UNKNOWN:
                raise SupplyDemandGapValidationError("unknown side confidence requires UNKNOWN overall confidence")
        object.__setattr__(self, "basis", tuple(sorted(basis)))


@dataclass(frozen=True, slots=True, kw_only=True)
class GapEvidence(_GapModel):
    evidence_id: str
    buyer_need_map: BuyerNeedMapSnapshot
    category_product_map: CategoryProductMapSnapshot
    need_cluster_id: str
    need_ids: tuple[str, ...]
    demand_metric_result_ids: tuple[str, ...]
    demand_denominator_ids: tuple[str, ...]
    demand_source_evidence_reference_ids: tuple[str, ...]
    supply_metric_ids: tuple[str, ...]
    supply_source_evidence_reference_ids: tuple[str, ...]
    grain_product_ids: tuple[str, ...]
    profile_ids: tuple[str, ...]
    product_attribute_profiles: tuple[CanonicalProductAttributeProfile, ...]
    product_identities: tuple[ProductIdentity, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.buyer_need_map, BuyerNeedMapSnapshot):
            raise SupplyDemandGapValidationError("gap evidence requires BuyerNeedMapSnapshot")
        if not isinstance(self.category_product_map, CategoryProductMapSnapshot):
            raise SupplyDemandGapValidationError("gap evidence requires CategoryProductMapSnapshot")
        _text(self.need_cluster_id, "GapEvidence.need_cluster_id")
        sequences = (
            "need_ids",
            "demand_metric_result_ids",
            "demand_denominator_ids",
            "demand_source_evidence_reference_ids",
            "supply_metric_ids",
            "supply_source_evidence_reference_ids",
            "grain_product_ids",
            "profile_ids",
        )
        for name in sequences:
            values = _tuple(getattr(self, name), f"GapEvidence.{name}")
            if any(type(item) is not str or not item.strip() for item in values):
                raise SupplyDemandGapValidationError(f"GapEvidence.{name} requires text")
            if len(set(values)) != len(values):
                raise SupplyDemandGapValidationError(f"GapEvidence.{name} must be unique")
            object.__setattr__(self, name, tuple(sorted(values)))
        profiles = _tuple(
            self.product_attribute_profiles,
            "GapEvidence.product_attribute_profiles",
        )
        if any(not isinstance(item, CanonicalProductAttributeProfile) for item in profiles):
            raise SupplyDemandGapValidationError(
                "GapEvidence.product_attribute_profiles contains a wrong type"
            )
        if len({item.profile_id for item in profiles}) != len(profiles):
            raise SupplyDemandGapValidationError(
                "GapEvidence.product_attribute_profiles must be unique"
            )
        object.__setattr__(
            self,
            "product_attribute_profiles",
            tuple(sorted(profiles, key=lambda item: item.profile_id)),
        )
        identities = _tuple(self.product_identities, "GapEvidence.product_identities")
        if any(not isinstance(item, ProductIdentity) for item in identities):
            raise SupplyDemandGapValidationError("GapEvidence.product_identities contains a wrong type")
        if len({item.product_id for item in identities}) != len(identities):
            raise SupplyDemandGapValidationError("GapEvidence.product_identities must be unique")
        object.__setattr__(self, "product_identities", tuple(sorted(identities, key=lambda item: item.product_id)))
        summary = next(
            (item for item in self.buyer_need_map.need_clusters if item.cluster_id == self.need_cluster_id),
            None,
        )
        if summary is None or tuple(sorted(summary.need_ids)) != self.need_ids:
            raise SupplyDemandGapValidationError("gap evidence cluster or need inventory is absent")
        map_metric_ids = {item.metric_result_id for item in self.buyer_need_map.demand_metrics}
        map_denominator_ids = {item.denominator_id for item in self.buyer_need_map.denominator_registry}
        map_evidence_ids = {item.evidence_reference_id for item in self.buyer_need_map.source_evidence}
        category_evidence_ids = {
            self.category_product_map.map_id,
            *(item.evidence_reference_id for item in self.category_product_map.source_evidence),
        }
        if not set(self.demand_metric_result_ids) <= map_metric_ids:
            raise SupplyDemandGapValidationError("gap demand metric reference is absent from Buyer Need Map")
        if not set(self.demand_denominator_ids) <= map_denominator_ids:
            raise SupplyDemandGapValidationError("gap demand denominator reference is absent")
        if not set(self.demand_source_evidence_reference_ids) <= map_evidence_ids:
            raise SupplyDemandGapValidationError("gap demand evidence reference is absent")
        if not set(self.supply_source_evidence_reference_ids) <= category_evidence_ids:
            raise SupplyDemandGapValidationError("gap supply evidence reference is absent")
        included = {item.grain_product_id: item for item in self.category_product_map.included_products}
        if not set(self.grain_product_ids) <= set(included):
            raise SupplyDemandGapValidationError("gap evidence grain product is absent")
        available_profiles = {
            profile_id
            for item in self.category_product_map.included_products
            for profile_id in item.source_profile_ids
        }
        if not set(self.profile_ids) <= available_profiles:
            raise SupplyDemandGapValidationError("gap evidence profile is absent")
        if set(self.profile_ids) != {item.profile_id for item in self.product_attribute_profiles}:
            raise SupplyDemandGapValidationError(
                "gap evidence profile ids and embedded profiles differ"
            )
        available_product_ids = {
            identity.product_id
            for item in self.category_product_map.included_products
            for identity in item.member_product_identities
        }
        if not {item.product_id for item in self.product_identities} <= available_product_ids:
            raise SupplyDemandGapValidationError("gap evidence ProductIdentity is absent")
        if self.evidence_id != _identity("supply-demand-gap-evidence", self, "evidence_id"):
            raise SupplyDemandGapValidationError("evidence_id does not match gap evidence content")


@dataclass(frozen=True, slots=True, kw_only=True)
class GapDiagnostic(_GapModel):
    diagnostic_id: str
    code: str
    severity: Severity
    related_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.code, "GapDiagnostic.code")
        if not isinstance(self.severity, Severity):
            raise SupplyDemandGapValidationError("gap diagnostic severity is invalid")
        related = _tuple(self.related_ids, "GapDiagnostic.related_ids")
        if any(type(item) is not str or not item.strip() for item in related):
            raise SupplyDemandGapValidationError("gap diagnostic related_ids require text")
        if len(set(related)) != len(related):
            raise SupplyDemandGapValidationError("gap diagnostic related_ids must be unique")
        _text(self.message, "GapDiagnostic.message")
        object.__setattr__(self, "related_ids", tuple(sorted(related)))
        if self.diagnostic_id != _identity("supply-demand-gap-diagnostic", self, "diagnostic_id"):
            raise SupplyDemandGapValidationError("diagnostic_id does not match gap diagnostic content")


@dataclass(frozen=True, slots=True, kw_only=True)
class SupplyDemandGapRequest(_GapModel):
    buyer_need_map: BuyerNeedMapSnapshot
    category_product_map: CategoryProductMapSnapshot
    need_cluster_id: str
    product_attribute_profiles: tuple[CanonicalProductAttributeProfile, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.buyer_need_map, BuyerNeedMapSnapshot):
            raise SupplyDemandGapValidationError("request requires BuyerNeedMapSnapshot")
        if not isinstance(self.category_product_map, CategoryProductMapSnapshot):
            raise SupplyDemandGapValidationError("request requires CategoryProductMapSnapshot")
        _text(self.need_cluster_id, "SupplyDemandGapRequest.need_cluster_id")
        profiles = _tuple(
            self.product_attribute_profiles,
            "SupplyDemandGapRequest.product_attribute_profiles",
        )
        if not profiles or any(
            not isinstance(item, CanonicalProductAttributeProfile) for item in profiles
        ):
            raise SupplyDemandGapValidationError(
                "request requires Product Attribute Profiles"
            )
        if len({item.profile_id for item in profiles}) != len(profiles):
            raise SupplyDemandGapValidationError("request profile ids must be unique")
        if self.buyer_need_map.category_scope != self.category_product_map.category_scope:
            raise SupplyDemandGapValidationError("Buyer Need Map and Category Product Map scope mismatch")
        if self.buyer_need_map.marketplace != self.category_product_map.marketplace:
            raise SupplyDemandGapValidationError("Buyer Need Map and Category Product Map marketplace mismatch")
        if not any(item.cluster_id == self.need_cluster_id for item in self.buyer_need_map.need_clusters):
            raise SupplyDemandGapValidationError("requested need cluster is absent from Buyer Need Map")
        category_map_sources = {
            item.source_id
            for item in self.buyer_need_map.source_evidence
            if item.evidence_type is BuyerNeedMapEvidenceType.CATEGORY_PRODUCT_MAP
        }
        if self.category_product_map.map_id not in category_map_sources:
            raise SupplyDemandGapValidationError(
                "Buyer Need Map does not preserve the supplied Category Product Map"
            )
        required_profile_ids = {
            profile_id
            for item in self.category_product_map.included_products
            for profile_id in item.source_profile_ids
        }
        if {item.profile_id for item in profiles} != required_profile_ids:
            raise SupplyDemandGapValidationError(
                "request profiles must exactly cover Category Product Map source profiles"
            )
        profile_by_id = {item.profile_id: item for item in profiles}
        for source in self.category_product_map.source_evidence:
            profile = profile_by_id.get(source.profile_id)
            if profile is None or profile.product_identity != source.product_identity:
                raise SupplyDemandGapValidationError(
                    "request profile identity does not match Category Product Map evidence"
                )
        object.__setattr__(
            self,
            "product_attribute_profiles",
            tuple(sorted(profiles, key=lambda item: item.profile_id)),
        )
        demand_window = self.buyer_need_map.analysis_window
        supply_window = self.category_product_map.analysis_window
        if (
            demand_window.status is AnalysisWindowStatus.KNOWN
            and supply_window.status is AnalysisWindowStatus.KNOWN
            and demand_window != supply_window
        ):
            raise SupplyDemandGapValidationError("known demand and supply analysis windows mismatch")


@dataclass(frozen=True, slots=True, kw_only=True)
class SupplyDemandGapSnapshot(_GapModel):
    gap_id: str
    category_scope: CategoryScope
    analysis_window: AnalysisWindow
    need_cluster_id: str
    demand_metrics: tuple[DemandMetricResult, ...]
    supply_metrics: tuple[GapSupplyMetric, ...]
    gap_type: GapType
    gap_strength: GapStrength
    confidence: GapConfidence
    evidence: GapEvidence
    diagnostics: tuple[GapDiagnostic, ...]
    type_registry: GapTypeRegistry
    classification_policy: GapClassificationPolicy
    ruleset_version: str = SUPPLY_DEMAND_GAP_RULESET_VERSION

    def __post_init__(self) -> None:
        if self.ruleset_version != SUPPLY_DEMAND_GAP_RULESET_VERSION:
            raise SupplyDemandGapValidationError("invalid Supply/Demand Gap ruleset version")
        if not isinstance(self.category_scope, CategoryScope):
            raise SupplyDemandGapValidationError("gap category_scope has a wrong type")
        if not isinstance(self.analysis_window, AnalysisWindow):
            raise SupplyDemandGapValidationError("gap analysis_window has a wrong type")
        _text(self.need_cluster_id, "SupplyDemandGapSnapshot.need_cluster_id")
        demand = _tuple(self.demand_metrics, "SupplyDemandGapSnapshot.demand_metrics")
        supply = _tuple(self.supply_metrics, "SupplyDemandGapSnapshot.supply_metrics")
        diagnostics = _tuple(self.diagnostics, "SupplyDemandGapSnapshot.diagnostics")
        if any(not isinstance(item, DemandMetricResult) for item in demand):
            raise SupplyDemandGapValidationError("gap demand_metrics contains a wrong type")
        if any(not isinstance(item, GapSupplyMetric) for item in supply):
            raise SupplyDemandGapValidationError("gap supply_metrics contains a wrong type")
        if any(not isinstance(item, GapDiagnostic) for item in diagnostics):
            raise SupplyDemandGapValidationError("gap diagnostics contains a wrong type")
        if {item.metric_type for item in demand} != _DEMAND_TYPES or len(demand) != len(_DEMAND_TYPES):
            raise SupplyDemandGapValidationError("gap must preserve exactly four demand metric types")
        if any(item.cluster_id != self.need_cluster_id for item in demand):
            raise SupplyDemandGapValidationError("gap demand metric cluster mismatch")
        required_supply_types = {
            SupplyMetricType.PRODUCT_COVERAGE_SHARE,
            SupplyMetricType.ATTRIBUTE_COVERAGE,
            SupplyMetricType.MATCHING_PRODUCT_COUNT,
            SupplyMetricType.COMPETITION_EVIDENCE,
        }
        if {item.metric_type for item in supply} != required_supply_types:
            raise SupplyDemandGapValidationError("gap must preserve every supply metric type")
        if sum(item.metric_type is SupplyMetricType.PRODUCT_COVERAGE_SHARE for item in supply) != 1:
            raise SupplyDemandGapValidationError("gap requires one Product Coverage supply metric")
        if sum(item.metric_type is SupplyMetricType.MATCHING_PRODUCT_COUNT for item in supply) != 1:
            raise SupplyDemandGapValidationError("gap requires one Matching Product Count supply metric")
        if len({item.supply_metric_id for item in supply}) != len(supply):
            raise SupplyDemandGapValidationError("gap supply metric ids must be unique")
        if len({item.diagnostic_id for item in diagnostics}) != len(diagnostics):
            raise SupplyDemandGapValidationError("gap diagnostic ids must be unique")
        if not isinstance(self.gap_type, GapType) or not isinstance(self.gap_strength, GapStrength):
            raise SupplyDemandGapValidationError("gap classification is invalid")
        if self.gap_type is GapType.INSUFFICIENT_EVIDENCE:
            if self.gap_strength is not GapStrength.UNKNOWN:
                raise SupplyDemandGapValidationError("insufficient evidence requires UNKNOWN strength")
        elif self.gap_strength is GapStrength.UNKNOWN:
            raise SupplyDemandGapValidationError("classified gap requires known strength")
        if not isinstance(self.confidence, GapConfidence):
            raise SupplyDemandGapValidationError("gap confidence has a wrong type")
        if not isinstance(self.evidence, GapEvidence):
            raise SupplyDemandGapValidationError("gap evidence has a wrong type")
        if not isinstance(self.type_registry, GapTypeRegistry) or not isinstance(
            self.classification_policy, GapClassificationPolicy
        ):
            raise SupplyDemandGapValidationError("gap registry or policy has a wrong type")
        if (
            self.category_scope != self.evidence.buyer_need_map.category_scope
            or self.category_scope != self.evidence.category_product_map.category_scope
            or self.analysis_window != self.evidence.buyer_need_map.analysis_window
            or self.need_cluster_id != self.evidence.need_cluster_id
        ):
            raise SupplyDemandGapValidationError("gap context diverges from embedded evidence")
        source_demand = {
            item.metric_result_id: item for item in self.evidence.buyer_need_map.demand_metrics
        }
        if any(source_demand.get(item.metric_result_id) != item for item in demand):
            raise SupplyDemandGapValidationError("gap demand metric diverges from Buyer Need Map")
        if set(self.evidence.demand_metric_result_ids) != {item.metric_result_id for item in demand}:
            raise SupplyDemandGapValidationError("gap evidence demand metric inventory mismatch")
        if set(self.evidence.supply_metric_ids) != {item.supply_metric_id for item in supply}:
            raise SupplyDemandGapValidationError("gap evidence supply metric inventory mismatch")
        allowed_supply_evidence = set(self.evidence.supply_source_evidence_reference_ids)
        if any(not set(item.evidence_reference_ids) <= allowed_supply_evidence for item in supply):
            raise SupplyDemandGapValidationError("supply metric references evidence outside gap inventory")
        object.__setattr__(self, "demand_metrics", tuple(sorted(demand, key=lambda item: item.metric_type.value)))
        object.__setattr__(self, "supply_metrics", tuple(sorted(supply, key=lambda item: item.supply_metric_id)))
        object.__setattr__(self, "diagnostics", tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)))
        if self.gap_id != _identity("supply-demand-gap", self, "gap_id"):
            raise SupplyDemandGapValidationError("gap_id does not match Supply/Demand Gap content")

    def validate(self) -> Self:
        self.__post_init__()
        return self


__all__ = (
    "GAP_CLASSIFICATION_POLICY_VERSION",
    "GAP_TYPE_REGISTRY_VERSION",
    "SUPPLY_DEMAND_GAP_RULESET_VERSION",
    "GapClassificationPolicy",
    "GapConfidence",
    "GapConfidenceLevel",
    "GapDiagnostic",
    "GapEvidence",
    "GapMetricConfidence",
    "GapSignalBand",
    "GapSignalStatus",
    "GapStrength",
    "GapSupplyMetric",
    "GapType",
    "GapTypeDefinition",
    "GapTypeRegistry",
    "SupplyDemandGapRequest",
    "SupplyDemandGapSnapshot",
    "SupplyMetricType",
)
