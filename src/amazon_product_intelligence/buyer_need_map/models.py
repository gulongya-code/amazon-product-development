"""Immutable Buyer Need Map and Demand Measurement contracts V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Mapping, Self, TypeAlias

from amazon_product_intelligence.buyer_need_analysis import BuyerNeedEvidence
from amazon_product_intelligence.category_product_map import (
    AnalysisWindow,
    CategoryMapSourceEvidence,
    CategoryProductMapSnapshot,
    CategoryScope,
)
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    Severity,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.demand_intelligence import KeywordMetricEvidenceSet
from amazon_product_intelligence.product_attribute_extraction import (
    AttributeDimension,
    CanonicalAttributeValue,
)
from amazon_product_intelligence.semantic_clustering import (
    SemanticClusterSnapshot,
    SemanticConfidence,
)

from .errors import BuyerNeedMapSerializationError, BuyerNeedMapValidationError


BUYER_NEED_MAP_RULESET_VERSION = "buyer-need-map-v0.1"
DEMAND_METRIC_REGISTRY_VERSION = "buyer-need-demand-metrics-v0.1"


class DemandMetricType(StrEnum):
    SEARCH_DEMAND_SHARE = "SEARCH_DEMAND_SHARE"
    REVIEW_MENTION_SHARE = "REVIEW_MENTION_SHARE"
    PRODUCT_COVERAGE_SHARE = "PRODUCT_COVERAGE_SHARE"
    SALES_ASSOCIATED_SHARE = "SALES_ASSOCIATED_SHARE"
    REVENUE_ASSOCIATED_SHARE = "REVENUE_ASSOCIATED_SHARE"


class DemandMetricStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class DemandDenominatorStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    UNKNOWN = "UNKNOWN"


class DemandMetricConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


class EvidencePopulationStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class BuyerNeedMapEvidenceType(StrEnum):
    BUYER_NEED = "BUYER_NEED"
    SEMANTIC_CLUSTER = "SEMANTIC_CLUSTER"
    SEARCH_METRIC = "SEARCH_METRIC"
    CATEGORY_PRODUCT_MAP = "CATEGORY_PRODUCT_MAP"
    PRODUCT_ATTRIBUTE = "PRODUCT_ATTRIBUTE"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise BuyerNeedMapValidationError(f"{path} must be non-empty text")
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise BuyerNeedMapValidationError(f"{path} must be a sequence")
    return tuple(value)


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise BuyerNeedMapValidationError(f"{path} must be a non-negative integer")
    return value


def _decimal(value: str, path: str, *, share: bool = False) -> Decimal:
    if type(value) is not str or not value.strip():
        raise BuyerNeedMapValidationError(f"{path} must be decimal text")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise BuyerNeedMapValidationError(f"{path} must be decimal text") from exc
    if not result.is_finite() or result < 0 or (share and result > 1):
        boundary = " between zero and one" if share else " non-negative and finite"
        raise BuyerNeedMapValidationError(f"{path} must be{boundary}")
    return result


def decimal_text(value: Decimal | int | float) -> str:
    candidate = value if isinstance(value, Decimal) else Decimal(str(value))
    if not candidate.is_finite() or candidate < 0:
        raise BuyerNeedMapValidationError("decimal value must be non-negative and finite")
    rendered = format(candidate, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def demand_share_text(numerator: int, denominator: int) -> str | None:
    _count(numerator, "share numerator")
    _count(denominator, "share denominator")
    if denominator == 0:
        return None
    with localcontext() as context:
        context.prec = 28
        return decimal_text(Decimal(numerator) / Decimal(denominator))


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    payload = model.to_dict()
    payload.pop(field_name)
    return deterministic_id(prefix, payload)


class _BuyerNeedMapModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except BuyerNeedMapValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise BuyerNeedMapSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandMetricDefinition(_BuyerNeedMapModel):
    metric_id: str
    metric_type: DemandMetricType
    numerator_definition: str
    denominator_definition: str
    weighting_rule: str
    time_window: str
    coverage_requirement: str
    confidence_rule: str

    def __post_init__(self) -> None:
        if not isinstance(self.metric_type, DemandMetricType):
            raise BuyerNeedMapValidationError("demand metric type is invalid")
        for name in (
            "numerator_definition",
            "denominator_definition",
            "weighting_rule",
            "time_window",
            "coverage_requirement",
            "confidence_rule",
        ):
            _text(getattr(self, name), f"DemandMetricDefinition.{name}")
        if self.metric_id != _identity("demand-metric-definition", self, "metric_id"):
            raise BuyerNeedMapValidationError("metric_id does not match definition content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandMetricRegistry(_BuyerNeedMapModel):
    registry_id: str
    registry_version: str
    definitions: tuple[DemandMetricDefinition, ...]

    def __post_init__(self) -> None:
        _text(self.registry_version, "DemandMetricRegistry.registry_version")
        definitions = _tuple(self.definitions, "DemandMetricRegistry.definitions")
        if any(not isinstance(item, DemandMetricDefinition) for item in definitions):
            raise BuyerNeedMapValidationError("metric registry contains a wrong type")
        if {item.metric_type for item in definitions} != set(DemandMetricType):
            raise BuyerNeedMapValidationError("metric registry must define every metric type exactly once")
        if len({item.metric_id for item in definitions}) != len(definitions):
            raise BuyerNeedMapValidationError("metric registry ids must be unique")
        object.__setattr__(
            self,
            "definitions",
            tuple(sorted(definitions, key=lambda item: item.metric_type.value)),
        )
        if self.registry_id != _identity("demand-metric-registry", self, "registry_id"):
            raise BuyerNeedMapValidationError("registry_id does not match metric registry content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandMetricConfidence(_BuyerNeedMapModel):
    level: DemandMetricConfidenceLevel
    evidence_coverage: str | None
    basis: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.level, DemandMetricConfidenceLevel):
            raise BuyerNeedMapValidationError("demand metric confidence level is invalid")
        if self.evidence_coverage is not None:
            _decimal(self.evidence_coverage, "confidence evidence_coverage", share=True)
        basis = _tuple(self.basis, "DemandMetricConfidence.basis")
        if not basis or any(type(item) is not str or not item.strip() for item in basis):
            raise BuyerNeedMapValidationError("demand metric confidence requires basis")
        if len(set(basis)) != len(basis):
            raise BuyerNeedMapValidationError("demand metric confidence basis must be unique")
        if self.level is DemandMetricConfidenceLevel.UNKNOWN and self.evidence_coverage is not None:
            raise BuyerNeedMapValidationError("UNKNOWN confidence cannot claim evidence coverage")
        if self.level is not DemandMetricConfidenceLevel.UNKNOWN and self.evidence_coverage is None:
            raise BuyerNeedMapValidationError("known confidence requires evidence coverage")
        object.__setattr__(self, "basis", tuple(sorted(basis)))


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandDenominator(_BuyerNeedMapModel):
    denominator_id: str
    metric_type: DemandMetricType
    category_scope_id: str
    status: DemandDenominatorStatus
    value: str | None
    unit: str
    population_definition: str
    analysis_window: AnalysisWindow
    eligible_ids: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.metric_type, DemandMetricType):
            raise BuyerNeedMapValidationError("denominator metric_type is invalid")
        _text(self.category_scope_id, "DemandDenominator.category_scope_id")
        if not isinstance(self.status, DemandDenominatorStatus):
            raise BuyerNeedMapValidationError("denominator status is invalid")
        _text(self.unit, "DemandDenominator.unit")
        _text(self.population_definition, "DemandDenominator.population_definition")
        if not isinstance(self.analysis_window, AnalysisWindow):
            raise BuyerNeedMapValidationError("denominator analysis_window has a wrong type")
        eligible = _tuple(self.eligible_ids, "DemandDenominator.eligible_ids")
        evidence = _tuple(self.evidence_reference_ids, "DemandDenominator.evidence_reference_ids")
        limitations = _tuple(self.limitations, "DemandDenominator.limitations")
        for name, values in (("eligible_ids", eligible), ("evidence_reference_ids", evidence), ("limitations", limitations)):
            if any(type(item) is not str or not item.strip() for item in values):
                raise BuyerNeedMapValidationError(f"denominator {name} requires text")
            if len(set(values)) != len(values):
                raise BuyerNeedMapValidationError(f"denominator {name} must be unique")
        if self.status is DemandDenominatorStatus.UNKNOWN:
            if self.value is not None or eligible:
                raise BuyerNeedMapValidationError("UNKNOWN denominator cannot publish value or eligible ids")
            if not limitations:
                raise BuyerNeedMapValidationError("UNKNOWN denominator requires a limitation")
        else:
            if self.value is None:
                raise BuyerNeedMapValidationError("AVAILABLE denominator requires a value")
            _decimal(self.value, "DemandDenominator.value")
            if not evidence:
                raise BuyerNeedMapValidationError("AVAILABLE denominator requires evidence")
        object.__setattr__(self, "eligible_ids", tuple(sorted(eligible)))
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))
        object.__setattr__(self, "limitations", tuple(sorted(limitations)))
        if self.denominator_id != _identity("demand-denominator", self, "denominator_id"):
            raise BuyerNeedMapValidationError("denominator_id does not match denominator content")


@dataclass(frozen=True, slots=True, kw_only=True)
class DemandMetricResult(_BuyerNeedMapModel):
    metric_result_id: str
    metric_id: str
    metric_type: DemandMetricType
    cluster_id: str
    status: DemandMetricStatus
    numerator_value: str | None
    denominator_id: str
    share: str | None
    confidence: DemandMetricConfidence
    evidence_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.metric_id, "DemandMetricResult.metric_id")
        if not isinstance(self.metric_type, DemandMetricType):
            raise BuyerNeedMapValidationError("metric result type is invalid")
        _text(self.cluster_id, "DemandMetricResult.cluster_id")
        if not isinstance(self.status, DemandMetricStatus):
            raise BuyerNeedMapValidationError("metric result status is invalid")
        _text(self.denominator_id, "DemandMetricResult.denominator_id")
        if not isinstance(self.confidence, DemandMetricConfidence):
            raise BuyerNeedMapValidationError("metric result confidence has a wrong type")
        evidence = _tuple(self.evidence_reference_ids, "DemandMetricResult.evidence_reference_ids")
        limitations = _tuple(self.limitations, "DemandMetricResult.limitations")
        if any(type(item) is not str or not item.strip() for item in evidence + limitations):
            raise BuyerNeedMapValidationError("metric evidence and limitations require text")
        if len(set(evidence)) != len(evidence) or len(set(limitations)) != len(limitations):
            raise BuyerNeedMapValidationError("metric evidence and limitations must be unique")
        if self.status is DemandMetricStatus.UNKNOWN:
            if self.numerator_value is not None or self.share is not None:
                raise BuyerNeedMapValidationError("UNKNOWN metric cannot publish numerator or share")
            if self.confidence.level is not DemandMetricConfidenceLevel.UNKNOWN or not limitations:
                raise BuyerNeedMapValidationError("UNKNOWN metric requires UNKNOWN confidence and limitations")
        else:
            if self.numerator_value is None or self.share is None:
                raise BuyerNeedMapValidationError("measured metric requires numerator and share")
            _decimal(self.numerator_value, "DemandMetricResult.numerator_value")
            _decimal(self.share, "DemandMetricResult.share", share=True)
            if self.confidence.level is DemandMetricConfidenceLevel.UNKNOWN or not evidence:
                raise BuyerNeedMapValidationError("measured metric requires evidence and known confidence")
            if self.status is DemandMetricStatus.PARTIAL and not limitations:
                raise BuyerNeedMapValidationError("PARTIAL metric requires limitations")
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))
        object.__setattr__(self, "limitations", tuple(sorted(limitations)))
        if self.metric_result_id != _identity("demand-metric-result", self, "metric_result_id"):
            raise BuyerNeedMapValidationError("metric_result_id does not match metric content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedRelatedAttribute(_BuyerNeedMapModel):
    dimension: AttributeDimension
    canonical_value: CanonicalAttributeValue
    member_grain_product_ids: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, AttributeDimension):
            raise BuyerNeedMapValidationError("related attribute dimension is invalid")
        if not isinstance(self.canonical_value, CanonicalAttributeValue):
            raise BuyerNeedMapValidationError("related attribute value has a wrong type")
        if self.canonical_value.dimension is not self.dimension:
            raise BuyerNeedMapValidationError("related attribute dimension/value mismatch")
        members = _tuple(self.member_grain_product_ids, "related attribute products")
        evidence = _tuple(self.evidence_reference_ids, "related attribute evidence")
        if not members or not evidence:
            raise BuyerNeedMapValidationError("related attribute requires products and evidence")
        if len(set(members)) != len(members) or len(set(evidence)) != len(evidence):
            raise BuyerNeedMapValidationError("related attribute products and evidence must be unique")
        object.__setattr__(self, "member_grain_product_ids", tuple(sorted(members)))
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedClusterSummary(_BuyerNeedMapModel):
    cluster_id: str
    cluster_label: str
    need_ids: tuple[str, ...]
    need_type_distribution: Mapping[str, int]
    related_attributes: tuple[BuyerNeedRelatedAttribute, ...]
    related_products: tuple[str, ...]
    evidence_count: int
    confidence: SemanticConfidence
    evidence_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.cluster_id, "BuyerNeedClusterSummary.cluster_id")
        _text(self.cluster_label, "BuyerNeedClusterSummary.cluster_label")
        need_ids = _tuple(self.need_ids, "BuyerNeedClusterSummary.need_ids")
        if not need_ids or len(set(need_ids)) != len(need_ids):
            raise BuyerNeedMapValidationError("cluster summary requires unique need ids")
        if not isinstance(self.need_type_distribution, MappingABC):
            raise BuyerNeedMapValidationError("need type distribution must be an object")
        distribution = dict(self.need_type_distribution)
        if any(type(key) is not str or not key for key in distribution) or any(
            type(value) is not int or value <= 0 for value in distribution.values()
        ):
            raise BuyerNeedMapValidationError("need type distribution requires positive counts")
        if sum(distribution.values()) != len(need_ids):
            raise BuyerNeedMapValidationError("need type distribution must cover every need")
        attributes = _tuple(self.related_attributes, "BuyerNeedClusterSummary.related_attributes")
        products = _tuple(self.related_products, "BuyerNeedClusterSummary.related_products")
        evidence = _tuple(self.evidence_reference_ids, "BuyerNeedClusterSummary.evidence_reference_ids")
        if any(not isinstance(item, BuyerNeedRelatedAttribute) for item in attributes):
            raise BuyerNeedMapValidationError("related attributes contain a wrong type")
        if len({(item.dimension, item.canonical_value.value_id) for item in attributes}) != len(attributes):
            raise BuyerNeedMapValidationError("related attributes must be unique")
        if len(set(products)) != len(products) or len(set(evidence)) != len(evidence):
            raise BuyerNeedMapValidationError("related products and evidence must be unique")
        _count(self.evidence_count, "BuyerNeedClusterSummary.evidence_count")
        if self.evidence_count <= 0:
            raise BuyerNeedMapValidationError("cluster summary requires evidence")
        if not isinstance(self.confidence, SemanticConfidence):
            raise BuyerNeedMapValidationError("cluster summary confidence must preserve cluster confidence")
        object.__setattr__(self, "need_ids", tuple(sorted(need_ids)))
        object.__setattr__(self, "need_type_distribution", MappingProxyType(dict(sorted(distribution.items()))))
        object.__setattr__(
            self,
            "related_attributes",
            tuple(sorted(attributes, key=lambda item: (item.dimension.value, item.canonical_value.value_id))),
        )
        object.__setattr__(self, "related_products", tuple(sorted(products)))
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))


BuyerNeedMapSourceRecord: TypeAlias = (
    BuyerNeedEvidence
    | SemanticClusterSnapshot
    | KeywordMetricEvidenceSet
    | CategoryProductMapSnapshot
    | CategoryMapSourceEvidence
)


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedMapSourceEvidence(_BuyerNeedMapModel):
    evidence_reference_id: str
    evidence_type: BuyerNeedMapEvidenceType
    source_id: str
    source_record: BuyerNeedMapSourceRecord

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_type, BuyerNeedMapEvidenceType):
            raise BuyerNeedMapValidationError("map evidence type is invalid")
        _text(self.source_id, "BuyerNeedMapSourceEvidence.source_id")
        expected: tuple[type, str]
        if self.evidence_type is BuyerNeedMapEvidenceType.BUYER_NEED:
            expected = (BuyerNeedEvidence, "need_id")
        elif self.evidence_type is BuyerNeedMapEvidenceType.SEMANTIC_CLUSTER:
            expected = (SemanticClusterSnapshot, "cluster_id")
        elif self.evidence_type is BuyerNeedMapEvidenceType.SEARCH_METRIC:
            expected = (KeywordMetricEvidenceSet, "metric_evidence_set_id")
        elif self.evidence_type is BuyerNeedMapEvidenceType.CATEGORY_PRODUCT_MAP:
            expected = (CategoryProductMapSnapshot, "map_id")
        else:
            expected = (CategoryMapSourceEvidence, "evidence_reference_id")
        if not isinstance(self.source_record, expected[0]):
            raise BuyerNeedMapValidationError("map evidence type and source record disagree")
        if self.source_id != getattr(self.source_record, expected[1]):
            raise BuyerNeedMapValidationError("map evidence source_id does not match source record")
        if self.evidence_reference_id != _identity(
            "buyer-need-map-evidence", self, "evidence_reference_id"
        ):
            raise BuyerNeedMapValidationError("evidence_reference_id does not match source content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedMapCoverage(_BuyerNeedMapModel):
    cluster_count: int
    buyer_need_count: int
    metric_count: int
    available_metric_count: int
    partial_metric_count: int
    unknown_metric_count: int
    metric_availability_rate: str
    source_evidence_count: int
    denominator_count: int

    def __post_init__(self) -> None:
        for name in (
            "cluster_count",
            "buyer_need_count",
            "metric_count",
            "available_metric_count",
            "partial_metric_count",
            "unknown_metric_count",
            "source_evidence_count",
            "denominator_count",
        ):
            _count(getattr(self, name), f"BuyerNeedMapCoverage.{name}")
        if self.available_metric_count + self.partial_metric_count + self.unknown_metric_count != self.metric_count:
            raise BuyerNeedMapValidationError("metric coverage counts do not sum to metric_count")
        _decimal(self.metric_availability_rate, "coverage metric_availability_rate", share=True)
        expected = demand_share_text(
            self.available_metric_count + self.partial_metric_count,
            self.metric_count,
        )
        if self.metric_availability_rate != (expected or "0"):
            raise BuyerNeedMapValidationError("metric availability rate does not match counts")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedMapDiagnostic(_BuyerNeedMapModel):
    diagnostic_id: str
    code: str
    severity: Severity
    cluster_ids: tuple[str, ...]
    related_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.code, "BuyerNeedMapDiagnostic.code")
        if not isinstance(self.severity, Severity):
            raise BuyerNeedMapValidationError("map diagnostic severity is invalid")
        clusters = _tuple(self.cluster_ids, "BuyerNeedMapDiagnostic.cluster_ids")
        related = _tuple(self.related_ids, "BuyerNeedMapDiagnostic.related_ids")
        if len(set(clusters)) != len(clusters) or len(set(related)) != len(related):
            raise BuyerNeedMapValidationError("diagnostic references must be unique")
        _text(self.message, "BuyerNeedMapDiagnostic.message")
        object.__setattr__(self, "cluster_ids", tuple(sorted(clusters)))
        object.__setattr__(self, "related_ids", tuple(sorted(related)))
        if self.diagnostic_id != _identity("buyer-need-map-diagnostic", self, "diagnostic_id"):
            raise BuyerNeedMapValidationError("diagnostic_id does not match diagnostic content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedMapRequest(_BuyerNeedMapModel):
    category_scope: CategoryScope
    marketplace: str
    analysis_window: AnalysisWindow
    buyer_need_evidence: tuple[BuyerNeedEvidence, ...]
    semantic_clusters: tuple[SemanticClusterSnapshot, ...]
    search_metric_evidence_sets: tuple[KeywordMetricEvidenceSet, ...] = ()
    category_product_map: CategoryProductMapSnapshot | None = None
    search_population_status: EvidencePopulationStatus = EvidencePopulationStatus.UNKNOWN
    review_population_status: EvidencePopulationStatus = EvidencePopulationStatus.UNKNOWN

    def __post_init__(self) -> None:
        if not isinstance(self.category_scope, CategoryScope):
            raise BuyerNeedMapValidationError("request category_scope has a wrong type")
        if self.marketplace != self.marketplace.strip().upper():
            raise BuyerNeedMapValidationError("request marketplace must be uppercase")
        if not isinstance(self.analysis_window, AnalysisWindow):
            raise BuyerNeedMapValidationError("request analysis_window has a wrong type")
        needs = _tuple(self.buyer_need_evidence, "BuyerNeedMapRequest.buyer_need_evidence")
        clusters = _tuple(self.semantic_clusters, "BuyerNeedMapRequest.semantic_clusters")
        search_sets = _tuple(self.search_metric_evidence_sets, "BuyerNeedMapRequest.search_metric_evidence_sets")
        if not clusters or any(not isinstance(item, SemanticClusterSnapshot) for item in clusters):
            raise BuyerNeedMapValidationError("Buyer Need Map requires semantic clusters")
        if any(not isinstance(item, BuyerNeedEvidence) for item in needs):
            raise BuyerNeedMapValidationError("request buyer_need_evidence contains a wrong type")
        if any(not isinstance(item, KeywordMetricEvidenceSet) for item in search_sets):
            raise BuyerNeedMapValidationError("request search evidence contains a wrong type")
        if len({item.need_id for item in needs}) != len(needs):
            raise BuyerNeedMapValidationError("request Buyer Need ids must be unique")
        if len({item.cluster_id for item in clusters}) != len(clusters):
            raise BuyerNeedMapValidationError("request cluster ids must be unique")
        if len({item.metric_evidence_set_id for item in search_sets}) != len(search_sets):
            raise BuyerNeedMapValidationError("request search evidence ids must be unique")
        need_by_id = {item.need_id: item for item in needs}
        clustered_ids: list[str] = []
        for cluster in clusters:
            clustered_ids.extend(cluster.source_need_ids)
            if any(need_by_id.get(item.need_id) != item for item in cluster.source_needs):
                raise BuyerNeedMapValidationError(
                    "semantic clusters must preserve request BuyerNeedEvidence records"
                )
        if len(clustered_ids) != len(set(clustered_ids)):
            raise BuyerNeedMapValidationError("a Buyer Need cannot occur in multiple clusters")
        if any(item.metric != "search_volume" for item in search_sets):
            raise BuyerNeedMapValidationError("search_metric_evidence_sets accepts only search_volume")
        if any(item.keyword_identity.marketplace != self.marketplace for item in search_sets):
            raise BuyerNeedMapValidationError("search evidence marketplace mismatch")
        if not isinstance(self.search_population_status, EvidencePopulationStatus) or not isinstance(
            self.review_population_status, EvidencePopulationStatus
        ):
            raise BuyerNeedMapValidationError("request population status is invalid")
        if self.category_product_map is not None:
            if not isinstance(self.category_product_map, CategoryProductMapSnapshot):
                raise BuyerNeedMapValidationError("request category_product_map has a wrong type")
            if (
                self.category_product_map.category_scope != self.category_scope
                or self.category_product_map.marketplace != self.marketplace
            ):
                raise BuyerNeedMapValidationError("Category Product Map scope or marketplace mismatch")
        object.__setattr__(self, "buyer_need_evidence", tuple(sorted(needs, key=lambda item: item.need_id)))
        object.__setattr__(self, "semantic_clusters", tuple(sorted(clusters, key=lambda item: item.cluster_id)))
        object.__setattr__(
            self,
            "search_metric_evidence_sets",
            tuple(sorted(search_sets, key=lambda item: item.metric_evidence_set_id)),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedMapSnapshot(_BuyerNeedMapModel):
    map_id: str
    category_scope: CategoryScope
    marketplace: str
    analysis_window: AnalysisWindow
    need_clusters: tuple[BuyerNeedClusterSummary, ...]
    demand_metrics: tuple[DemandMetricResult, ...]
    coverage: BuyerNeedMapCoverage
    denominator_registry: tuple[DemandDenominator, ...]
    source_evidence: tuple[BuyerNeedMapSourceEvidence, ...]
    diagnostics: tuple[BuyerNeedMapDiagnostic, ...]
    metric_registry: DemandMetricRegistry
    ruleset_version: str = BUYER_NEED_MAP_RULESET_VERSION

    def __post_init__(self) -> None:
        if self.ruleset_version != BUYER_NEED_MAP_RULESET_VERSION:
            raise BuyerNeedMapValidationError("invalid Buyer Need Map ruleset version")
        if not isinstance(self.category_scope, CategoryScope):
            raise BuyerNeedMapValidationError("snapshot category_scope has a wrong type")
        if self.marketplace != self.marketplace.strip().upper():
            raise BuyerNeedMapValidationError("snapshot marketplace must be uppercase")
        if not isinstance(self.analysis_window, AnalysisWindow):
            raise BuyerNeedMapValidationError("snapshot analysis_window has a wrong type")
        if not isinstance(self.metric_registry, DemandMetricRegistry):
            raise BuyerNeedMapValidationError("snapshot metric_registry has a wrong type")
        if not isinstance(self.coverage, BuyerNeedMapCoverage):
            raise BuyerNeedMapValidationError("snapshot coverage has a wrong type")
        typed = (
            ("need_clusters", BuyerNeedClusterSummary, lambda item: item.cluster_id),
            ("demand_metrics", DemandMetricResult, lambda item: item.metric_result_id),
            ("denominator_registry", DemandDenominator, lambda item: item.denominator_id),
            ("source_evidence", BuyerNeedMapSourceEvidence, lambda item: item.evidence_reference_id),
            ("diagnostics", BuyerNeedMapDiagnostic, lambda item: item.diagnostic_id),
        )
        for name, expected, key in typed:
            values = _tuple(getattr(self, name), f"BuyerNeedMapSnapshot.{name}")
            if any(not isinstance(item, expected) for item in values):
                raise BuyerNeedMapValidationError(f"snapshot {name} contains a wrong type")
            keys = [key(item) for item in values]
            if len(set(keys)) != len(keys):
                raise BuyerNeedMapValidationError(f"snapshot {name} contains duplicate identities")
            object.__setattr__(self, name, tuple(sorted(values, key=key)))
        if not self.need_clusters:
            raise BuyerNeedMapValidationError("Buyer Need Map requires cluster summaries")
        cluster_ids = {item.cluster_id for item in self.need_clusters}
        evidence_by_id = {item.evidence_reference_id: item for item in self.source_evidence}
        denominator_by_id = {item.denominator_id: item for item in self.denominator_registry}
        definition_by_id = {item.metric_id: item for item in self.metric_registry.definitions}
        cluster_sources = {
            item.source_id: item.source_record
            for item in self.source_evidence
            if item.evidence_type is BuyerNeedMapEvidenceType.SEMANTIC_CLUSTER
        }
        for summary in self.need_clusters:
            source = cluster_sources.get(summary.cluster_id)
            if not isinstance(source, SemanticClusterSnapshot):
                raise BuyerNeedMapValidationError("cluster summary lacks SemanticClusterSnapshot source")
            expected_distribution: dict[str, int] = {}
            for need in source.source_needs:
                expected_distribution[need.need_type.value] = expected_distribution.get(need.need_type.value, 0) + 1
            if (
                summary.cluster_label != source.cluster_label
                or summary.need_ids != source.source_need_ids
                or dict(summary.need_type_distribution) != expected_distribution
                or summary.evidence_count != source.evidence_count
                or summary.confidence != source.confidence
            ):
                raise BuyerNeedMapValidationError("cluster summary diverges from SemanticClusterSnapshot")
            if not set(summary.evidence_reference_ids) <= set(evidence_by_id):
                raise BuyerNeedMapValidationError("cluster summary references absent evidence")
        metric_pairs = {(item.cluster_id, item.metric_type) for item in self.demand_metrics}
        expected_pairs = {(cluster_id, metric_type) for cluster_id in cluster_ids for metric_type in DemandMetricType}
        if metric_pairs != expected_pairs or len(metric_pairs) != len(self.demand_metrics):
            raise BuyerNeedMapValidationError("each cluster requires exactly one result per metric type")
        for metric in self.demand_metrics:
            definition = definition_by_id.get(metric.metric_id)
            denominator = denominator_by_id.get(metric.denominator_id)
            if definition is None or definition.metric_type is not metric.metric_type:
                raise BuyerNeedMapValidationError("metric result references an absent definition")
            if denominator is None or denominator.metric_type is not metric.metric_type:
                raise BuyerNeedMapValidationError("metric result references an absent denominator")
            if metric.cluster_id not in cluster_ids:
                raise BuyerNeedMapValidationError("metric result references an absent cluster")
            if not set(metric.evidence_reference_ids) <= set(evidence_by_id):
                raise BuyerNeedMapValidationError("metric result references absent evidence")
            if metric.status is not DemandMetricStatus.UNKNOWN:
                if denominator.status is not DemandDenominatorStatus.AVAILABLE or denominator.value is None:
                    raise BuyerNeedMapValidationError("measured metric requires an available denominator")
                denominator_value = _decimal(denominator.value, "snapshot denominator value")
                if denominator_value == 0:
                    raise BuyerNeedMapValidationError("measured metric denominator must be positive")
                assert metric.numerator_value is not None and metric.share is not None
                numerator = _decimal(metric.numerator_value, "snapshot numerator value")
                with localcontext() as context:
                    context.prec = 28
                    expected_share = decimal_text(numerator / denominator_value)
                if metric.share != expected_share:
                    raise BuyerNeedMapValidationError("metric share does not match numerator/denominator")
        if any(
            not set(item.evidence_reference_ids) <= set(evidence_by_id)
            for item in self.denominator_registry
        ):
            raise BuyerNeedMapValidationError("denominator references absent source evidence")
        expected_coverage = BuyerNeedMapCoverage(
            cluster_count=len(self.need_clusters),
            buyer_need_count=len({need_id for item in self.need_clusters for need_id in item.need_ids}),
            metric_count=len(self.demand_metrics),
            available_metric_count=sum(item.status is DemandMetricStatus.AVAILABLE for item in self.demand_metrics),
            partial_metric_count=sum(item.status is DemandMetricStatus.PARTIAL for item in self.demand_metrics),
            unknown_metric_count=sum(item.status is DemandMetricStatus.UNKNOWN for item in self.demand_metrics),
            metric_availability_rate=demand_share_text(
                sum(item.status is not DemandMetricStatus.UNKNOWN for item in self.demand_metrics),
                len(self.demand_metrics),
            ) or "0",
            source_evidence_count=len(self.source_evidence),
            denominator_count=len(self.denominator_registry),
        )
        if self.coverage != expected_coverage:
            raise BuyerNeedMapValidationError("snapshot coverage does not match contents")
        if self.map_id != _identity("buyer-need-map", self, "map_id"):
            raise BuyerNeedMapValidationError("map_id does not match Buyer Need Map content")

    def validate(self) -> Self:
        self.__post_init__()
        return self


__all__ = (
    "BUYER_NEED_MAP_RULESET_VERSION",
    "DEMAND_METRIC_REGISTRY_VERSION",
    "BuyerNeedClusterSummary",
    "BuyerNeedMapCoverage",
    "BuyerNeedMapDiagnostic",
    "BuyerNeedMapEvidenceType",
    "BuyerNeedMapRequest",
    "BuyerNeedMapSnapshot",
    "BuyerNeedMapSourceEvidence",
    "BuyerNeedRelatedAttribute",
    "DemandDenominator",
    "DemandDenominatorStatus",
    "DemandMetricConfidence",
    "DemandMetricConfidenceLevel",
    "DemandMetricDefinition",
    "DemandMetricRegistry",
    "DemandMetricResult",
    "DemandMetricStatus",
    "DemandMetricType",
    "EvidencePopulationStatus",
    "decimal_text",
    "demand_share_text",
)
