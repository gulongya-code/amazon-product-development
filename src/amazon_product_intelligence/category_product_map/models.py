"""Immutable, evidence-aware Category Product Map contracts V0.1."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import json
import re
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.calculations import safe_decimal_ratio
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    ProductIdentity,
    Severity,
    Unit,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.product_attribute_extraction import (
    AttributeDimension,
    AttributeSourceEvidence,
    CanonicalAttributeAssertion,
    CanonicalAttributeValue,
    CanonicalProductAttributeProfile,
    ProductAttributeContractError,
    ProductGrain,
)

from .errors import CategoryProductMapSerializationError, CategoryProductMapValidationError


CATEGORY_PRODUCT_MAP_VERSION = "category-product-map-v0.1"
_ASIN = re.compile(r"^[A-Z0-9]{10}$")


class CategoryScopeType(StrEnum):
    AMAZON_BROWSE_NODE = "AMAZON_BROWSE_NODE"
    INPUT_COHORT = "INPUT_COHORT"
    SEARCH_QUERY = "SEARCH_QUERY"


class AnalysisWindowStatus(StrEnum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class DenominatorType(StrEnum):
    ALL_INCLUDED_PRODUCTS = "ALL_INCLUDED_PRODUCTS"
    KNOWN_ATTRIBUTE_PRODUCTS = "KNOWN_ATTRIBUTE_PRODUCTS"
    COMPLETE_COMBINATION_PRODUCTS = "COMPLETE_COMBINATION_PRODUCTS"


class EvidenceAwareMetricStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise CategoryProductMapValidationError(f"{path} must be non-empty text")
    return value


def _count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise CategoryProductMapValidationError(f"{path} must be a non-negative integer")
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CategoryProductMapValidationError(f"{path} must be a sequence")
    return tuple(value)


def _datetime(value: str | None, path: str) -> None:
    if value is None:
        return
    _text(value, path)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise CategoryProductMapValidationError(f"{path} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise CategoryProductMapValidationError(f"{path} must include a UTC offset or Z")


def _freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise CategoryProductMapValidationError(f"{path} must contain finite JSON data: {exc}") from exc

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


def ratio_text(numerator: int, denominator: int) -> str | None:
    """Reuse the governed decimal ratio helper and return JSON-safe exact text."""

    _count(numerator, "ratio numerator")
    _count(denominator, "ratio denominator")
    if denominator == 0:
        return None
    ratio = safe_decimal_ratio(numerator, denominator)
    rendered = format(ratio, "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


def _ratio(value: str | None, path: str, *, required: bool = True) -> Decimal | None:
    if value is None:
        if required:
            raise CategoryProductMapValidationError(f"{path} requires a ratio")
        return None
    if type(value) is not str or not value.strip():
        raise CategoryProductMapValidationError(f"{path} must be decimal ratio text")
    try:
        ratio = Decimal(value)
    except InvalidOperation as exc:
        raise CategoryProductMapValidationError(f"{path} must be decimal ratio text") from exc
    if not ratio.is_finite() or ratio < 0 or ratio > 1:
        raise CategoryProductMapValidationError(f"{path} must be between zero and one")
    return ratio


class _CategoryMapModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except CategoryProductMapValidationError:
            raise
        except (ContractValidationError, ProductAttributeContractError, TypeError, ValueError) as exc:
            raise CategoryProductMapSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryScope(_CategoryMapModel):
    category_scope_id: str
    scope_type: CategoryScopeType
    scope_value: str
    inclusion_rule: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope_type, CategoryScopeType):
            raise CategoryProductMapValidationError("category scope_type is invalid")
        _text(self.scope_value, "CategoryScope.scope_value")
        _text(self.inclusion_rule, "CategoryScope.inclusion_rule")
        if self.category_scope_id != _identity("category-scope", self, "category_scope_id"):
            raise CategoryProductMapValidationError("category_scope_id does not match scope content")


@dataclass(frozen=True, slots=True, kw_only=True)
class AnalysisWindow(_CategoryMapModel):
    status: AnalysisWindowStatus
    period_start: str | None
    period_end: str | None

    def __post_init__(self) -> None:
        if not isinstance(self.status, AnalysisWindowStatus):
            raise CategoryProductMapValidationError("analysis window status is invalid")
        _datetime(self.period_start, "AnalysisWindow.period_start")
        _datetime(self.period_end, "AnalysisWindow.period_end")
        if self.status is AnalysisWindowStatus.UNKNOWN:
            if self.period_start is not None or self.period_end is not None:
                raise CategoryProductMapValidationError("UNKNOWN analysis window requires null bounds")
        elif self.period_start is None or self.period_end is None:
            raise CategoryProductMapValidationError("KNOWN analysis window requires both bounds")
        if self.period_start is not None and self.period_end is not None:
            start = datetime.fromisoformat(
                self.period_start[:-1] + "+00:00" if self.period_start.endswith("Z") else self.period_start
            )
            end = datetime.fromisoformat(
                self.period_end[:-1] + "+00:00" if self.period_end.endswith("Z") else self.period_end
            )
            if start > end:
                raise CategoryProductMapValidationError("analysis window start must not follow end")


@dataclass(frozen=True, slots=True, kw_only=True)
class IncludedCategoryProduct(_CategoryMapModel):
    grain_product_id: str
    marketplace: str
    grain_asin: str
    member_product_identities: tuple[ProductIdentity, ...]
    source_profile_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.grain_product_id, "IncludedCategoryProduct.grain_product_id")
        if self.marketplace != self.marketplace.strip().upper():
            raise CategoryProductMapValidationError("included product marketplace must be uppercase")
        if not _ASIN.fullmatch(self.grain_asin):
            raise CategoryProductMapValidationError("included grain_asin must be a normalized ASIN")
        members = _tuple(self.member_product_identities, "included member_product_identities")
        profiles = _tuple(self.source_profile_ids, "included source_profile_ids")
        if not members or any(not isinstance(item, ProductIdentity) for item in members):
            raise CategoryProductMapValidationError("included product requires member ProductIdentity values")
        if not profiles or any(type(item) is not str or not item.strip() for item in profiles):
            raise CategoryProductMapValidationError("included product requires source profile ids")
        if any(item.marketplace != self.marketplace for item in members):
            raise CategoryProductMapValidationError("included product member marketplace mismatch")
        if len({item.product_id for item in members}) != len(members) or len(set(profiles)) != len(profiles):
            raise CategoryProductMapValidationError("included product members and profiles must be unique")
        object.__setattr__(self, "member_product_identities", tuple(sorted(members, key=lambda item: item.product_id)))
        object.__setattr__(self, "source_profile_ids", tuple(sorted(profiles)))


@dataclass(frozen=True, slots=True, kw_only=True)
class ExcludedCategoryProduct(_CategoryMapModel):
    profile_id: str
    product_identity: ProductIdentity
    reason_code: str
    message: str

    def __post_init__(self) -> None:
        _text(self.profile_id, "ExcludedCategoryProduct.profile_id")
        if not isinstance(self.product_identity, ProductIdentity):
            raise CategoryProductMapValidationError("excluded product requires ProductIdentity")
        _text(self.reason_code, "ExcludedCategoryProduct.reason_code")
        _text(self.message, "ExcludedCategoryProduct.message")


@dataclass(frozen=True, slots=True, kw_only=True)
class DistributionDenominator(_CategoryMapModel):
    denominator_id: str
    metric_name: str
    denominator_type: DenominatorType
    eligible_product_count: int
    excluded_product_count: int
    unknown_count: int
    grain_policy: ProductGrain
    filter_conditions: tuple[str, ...]
    eligible_grain_product_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.metric_name, "DistributionDenominator.metric_name")
        if not isinstance(self.denominator_type, DenominatorType):
            raise CategoryProductMapValidationError("denominator type is invalid")
        if not isinstance(self.grain_policy, ProductGrain):
            raise CategoryProductMapValidationError("denominator grain policy is invalid")
        for name in ("eligible_product_count", "excluded_product_count", "unknown_count"):
            _count(getattr(self, name), f"DistributionDenominator.{name}")
        conditions = _tuple(self.filter_conditions, "denominator filter_conditions")
        products = _tuple(self.eligible_grain_product_ids, "denominator eligible products")
        if any(type(item) is not str or not item.strip() for item in conditions + products):
            raise CategoryProductMapValidationError("denominator conditions and products require text")
        if len(set(conditions)) != len(conditions) or len(set(products)) != len(products):
            raise CategoryProductMapValidationError("denominator conditions and products must be unique")
        if self.eligible_product_count != len(products):
            raise CategoryProductMapValidationError("denominator count must match eligible product ids")
        object.__setattr__(self, "filter_conditions", tuple(sorted(conditions)))
        object.__setattr__(self, "eligible_grain_product_ids", tuple(sorted(products)))
        if self.denominator_id != _identity("distribution-denominator", self, "denominator_id"):
            raise CategoryProductMapValidationError("denominator_id does not match denominator content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryMapSourceEvidence(_CategoryMapModel):
    evidence_reference_id: str
    profile_id: str
    grain_product_id: str
    product_identity: ProductIdentity
    dimension: AttributeDimension
    assertion: CanonicalAttributeAssertion
    source_evidence: tuple[AttributeSourceEvidence, ...]

    def __post_init__(self) -> None:
        _text(self.profile_id, "CategoryMapSourceEvidence.profile_id")
        _text(self.grain_product_id, "CategoryMapSourceEvidence.grain_product_id")
        if not isinstance(self.product_identity, ProductIdentity):
            raise CategoryProductMapValidationError("map evidence requires ProductIdentity")
        if not isinstance(self.dimension, AttributeDimension):
            raise CategoryProductMapValidationError("map evidence dimension is invalid")
        if not isinstance(self.assertion, CanonicalAttributeAssertion):
            raise CategoryProductMapValidationError("map evidence requires canonical attribute assertion")
        if self.assertion.canonical_value is None or self.assertion.canonical_value.dimension is not self.dimension:
            raise CategoryProductMapValidationError("map evidence assertion dimension mismatch")
        sources = _tuple(self.source_evidence, "map source_evidence")
        if not sources or any(not isinstance(item, AttributeSourceEvidence) for item in sources):
            raise CategoryProductMapValidationError("map evidence requires attribute source evidence")
        if tuple(sorted(sources, key=lambda item: item.source_evidence_id)) != tuple(self.assertion.source_evidence):
            raise CategoryProductMapValidationError("map evidence must preserve the assertion source evidence")
        object.__setattr__(self, "source_evidence", tuple(sorted(sources, key=lambda item: item.source_evidence_id)))
        if self.evidence_reference_id != _identity("category-map-evidence", self, "evidence_reference_id"):
            raise CategoryProductMapValidationError("evidence_reference_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeValueDistribution(_CategoryMapModel):
    value_metric_id: str
    canonical_value: CanonicalAttributeValue
    asin_count: int
    asin_share: str
    denominator_id: str
    member_grain_product_ids: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.canonical_value, CanonicalAttributeValue):
            raise CategoryProductMapValidationError("value distribution requires CanonicalAttributeValue")
        _count(self.asin_count, "AttributeValueDistribution.asin_count")
        _ratio(self.asin_share, "AttributeValueDistribution.asin_share")
        _text(self.denominator_id, "AttributeValueDistribution.denominator_id")
        members = _tuple(self.member_grain_product_ids, "value distribution members")
        evidence = _tuple(self.evidence_reference_ids, "value distribution evidence")
        if not members or self.asin_count != len(members) or len(set(members)) != len(members):
            raise CategoryProductMapValidationError("value distribution count must match unique members")
        if not evidence or len(set(evidence)) != len(evidence):
            raise CategoryProductMapValidationError("value distribution requires unique evidence references")
        object.__setattr__(self, "member_grain_product_ids", tuple(sorted(members)))
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))
        if self.value_metric_id != _identity("attribute-value-distribution", self, "value_metric_id"):
            raise CategoryProductMapValidationError("value_metric_id does not match distribution content")


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeDistribution(_CategoryMapModel):
    distribution_id: str
    dimension: AttributeDimension
    values: tuple[AttributeValueDistribution, ...]
    total_product_count: int
    known_value_count: int
    unknown_count: int
    attribute_coverage: str
    unknown_rate: str
    known_value_denominator_id: str
    coverage_denominator_id: str
    unknown_rate_denominator_id: str
    known_grain_product_ids: tuple[str, ...]
    unknown_grain_product_ids: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.dimension, AttributeDimension):
            raise CategoryProductMapValidationError("attribute distribution dimension is invalid")
        for name in ("total_product_count", "known_value_count", "unknown_count"):
            _count(getattr(self, name), f"AttributeDistribution.{name}")
        if self.known_value_count + self.unknown_count != self.total_product_count:
            raise CategoryProductMapValidationError("known and unknown counts must equal total products")
        _ratio(self.attribute_coverage, "AttributeDistribution.attribute_coverage")
        _ratio(self.unknown_rate, "AttributeDistribution.unknown_rate")
        if self.attribute_coverage != ratio_text(self.known_value_count, self.total_product_count):
            raise CategoryProductMapValidationError("attribute coverage does not match counts")
        if self.unknown_rate != ratio_text(self.unknown_count, self.total_product_count):
            raise CategoryProductMapValidationError("attribute unknown rate does not match counts")
        for name in (
            "known_value_denominator_id",
            "coverage_denominator_id",
            "unknown_rate_denominator_id",
        ):
            _text(getattr(self, name), f"AttributeDistribution.{name}")
        values = _tuple(self.values, "AttributeDistribution.values")
        known = _tuple(self.known_grain_product_ids, "attribute known products")
        unknown = _tuple(self.unknown_grain_product_ids, "attribute unknown products")
        evidence = _tuple(self.evidence_reference_ids, "attribute distribution evidence")
        if any(not isinstance(item, AttributeValueDistribution) for item in values):
            raise CategoryProductMapValidationError("attribute distribution values contain a wrong type")
        if any(item.canonical_value.dimension is not self.dimension for item in values):
            raise CategoryProductMapValidationError("attribute distribution value dimension mismatch")
        if len({item.canonical_value.value_id for item in values}) != len(values):
            raise CategoryProductMapValidationError("attribute distribution canonical values must be unique")
        if len(set(known)) != len(known) or len(set(unknown)) != len(unknown) or set(known) & set(unknown):
            raise CategoryProductMapValidationError("known and unknown product inventories must be disjoint")
        if len(known) != self.known_value_count or len(unknown) != self.unknown_count:
            raise CategoryProductMapValidationError("attribute product inventories do not match counts")
        membership_products = (
            set().union(*(set(item.member_grain_product_ids) for item in values))
            if values
            else set()
        )
        if membership_products != set(known):
            raise CategoryProductMapValidationError("value memberships do not cover known products")
        value_evidence = {ref for item in values for ref in item.evidence_reference_ids}
        if value_evidence != set(evidence):
            raise CategoryProductMapValidationError("attribute evidence inventory mismatch")
        object.__setattr__(self, "values", tuple(sorted(values, key=lambda item: item.canonical_value.value_id)))
        object.__setattr__(self, "known_grain_product_ids", tuple(sorted(known)))
        object.__setattr__(self, "unknown_grain_product_ids", tuple(sorted(unknown)))
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))
        if self.distribution_id != _identity("attribute-distribution", self, "distribution_id"):
            raise CategoryProductMapValidationError("distribution_id does not match distribution content")


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceAwareMetric(_CategoryMapModel):
    metric_id: str
    metric_name: str
    metric_scope_id: str
    status: EvidenceAwareMetricStatus
    value: Any
    unit: Unit | None
    denominator_id: str | None
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.metric_name, "EvidenceAwareMetric.metric_name")
        _text(self.metric_scope_id, "EvidenceAwareMetric.metric_scope_id")
        if not isinstance(self.status, EvidenceAwareMetricStatus):
            raise CategoryProductMapValidationError("evidence-aware metric status is invalid")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise CategoryProductMapValidationError("evidence-aware metric unit is invalid")
        if self.denominator_id is not None:
            _text(self.denominator_id, "EvidenceAwareMetric.denominator_id")
        evidence = _tuple(self.evidence_ids, "EvidenceAwareMetric.evidence_ids")
        limitations = _tuple(self.limitations, "EvidenceAwareMetric.limitations")
        if len(set(evidence)) != len(evidence) or len(set(limitations)) != len(limitations):
            raise CategoryProductMapValidationError("metric evidence and limitations must be unique")
        frozen = _freeze_json(self.value, "EvidenceAwareMetric.value")
        if self.status is EvidenceAwareMetricStatus.UNKNOWN:
            if frozen is not None or self.unit is not None or self.denominator_id is not None or evidence:
                raise CategoryProductMapValidationError("UNKNOWN metric cannot publish value, unit, denominator, or evidence")
            if not limitations:
                raise CategoryProductMapValidationError("UNKNOWN metric requires a limitation")
        else:
            if frozen is None or not evidence:
                raise CategoryProductMapValidationError("available/partial metric requires value and evidence")
            if self.metric_name.endswith("_share") and self.denominator_id is None:
                raise CategoryProductMapValidationError("share metric requires a denominator")
            if self.status is EvidenceAwareMetricStatus.PARTIAL and not limitations:
                raise CategoryProductMapValidationError("PARTIAL metric requires a limitation")
        object.__setattr__(self, "value", frozen)
        object.__setattr__(self, "evidence_ids", tuple(sorted(evidence)))
        object.__setattr__(self, "limitations", tuple(sorted(limitations)))
        if self.metric_id != _identity("evidence-aware-metric", self, "metric_id"):
            raise CategoryProductMapValidationError("metric_id does not match metric content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryCombinationSegment(_CategoryMapModel):
    segment_id: str
    dimensions: tuple[AttributeDimension, ...]
    canonical_values: tuple[CanonicalAttributeValue, ...]
    asin_count: int
    asin_share: str
    coverage: str
    share_denominator_id: str
    coverage_denominator_id: str
    member_grain_product_ids: tuple[str, ...]
    sales_metrics: EvidenceAwareMetric
    revenue_metrics: EvidenceAwareMetric
    review_metrics: EvidenceAwareMetric
    competition_metrics: EvidenceAwareMetric
    evidence_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        dimensions = _tuple(self.dimensions, "combination dimensions")
        values = _tuple(self.canonical_values, "combination canonical_values")
        if len(dimensions) < 2 or len(set(dimensions)) != len(dimensions):
            raise CategoryProductMapValidationError("combination requires at least two unique dimensions")
        if any(not isinstance(item, AttributeDimension) for item in dimensions):
            raise CategoryProductMapValidationError("combination dimensions contain a wrong type")
        if len(values) != len(dimensions) or any(not isinstance(item, CanonicalAttributeValue) for item in values):
            raise CategoryProductMapValidationError("combination values must align with dimensions")
        pairs = tuple(sorted(zip(dimensions, values), key=lambda item: item[0].value))
        if any(dimension is not value.dimension for dimension, value in pairs):
            raise CategoryProductMapValidationError("combination canonical value dimension mismatch")
        _count(self.asin_count, "CategoryCombinationSegment.asin_count")
        _ratio(self.asin_share, "CategoryCombinationSegment.asin_share")
        _ratio(self.coverage, "CategoryCombinationSegment.coverage")
        _text(self.share_denominator_id, "segment share_denominator_id")
        _text(self.coverage_denominator_id, "segment coverage_denominator_id")
        members = _tuple(self.member_grain_product_ids, "combination members")
        evidence = _tuple(self.evidence_reference_ids, "combination evidence")
        if not members or self.asin_count != len(members) or len(set(members)) != len(members):
            raise CategoryProductMapValidationError("combination asin_count must match unique members")
        if not evidence or len(set(evidence)) != len(evidence):
            raise CategoryProductMapValidationError("combination segment requires unique evidence")
        for metric in (
            self.sales_metrics,
            self.revenue_metrics,
            self.review_metrics,
            self.competition_metrics,
        ):
            if not isinstance(metric, EvidenceAwareMetric):
                raise CategoryProductMapValidationError("combination metric has a wrong type")
        object.__setattr__(self, "dimensions", tuple(item[0] for item in pairs))
        object.__setattr__(self, "canonical_values", tuple(item[1] for item in pairs))
        object.__setattr__(self, "member_grain_product_ids", tuple(sorted(members)))
        object.__setattr__(self, "evidence_reference_ids", tuple(sorted(evidence)))
        if self.segment_id != _identity("category-combination-segment", self, "segment_id"):
            raise CategoryProductMapValidationError("segment_id does not match segment content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryMapCoverage(_CategoryMapModel):
    input_profile_count: int
    included_product_count: int
    excluded_profile_count: int
    attribute_dimension_count: int
    dimensions_with_known_values: int
    dimensions_without_known_values: int
    combination_definition_count: int
    combination_segment_count: int
    source_evidence_count: int

    def __post_init__(self) -> None:
        for name in (
            "input_profile_count",
            "included_product_count",
            "excluded_profile_count",
            "attribute_dimension_count",
            "dimensions_with_known_values",
            "dimensions_without_known_values",
            "combination_definition_count",
            "combination_segment_count",
            "source_evidence_count",
        ):
            _count(getattr(self, name), f"CategoryMapCoverage.{name}")
        if self.dimensions_with_known_values + self.dimensions_without_known_values != self.attribute_dimension_count:
            raise CategoryProductMapValidationError("category map dimension coverage counts are inconsistent")


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryMapDiagnostic(_CategoryMapModel):
    diagnostic_id: str
    code: str
    severity: Severity
    related_profile_ids: tuple[str, ...]
    related_grain_product_ids: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        _text(self.code, "CategoryMapDiagnostic.code")
        if not isinstance(self.severity, Severity):
            raise CategoryProductMapValidationError("category map diagnostic severity is invalid")
        profiles = _tuple(self.related_profile_ids, "diagnostic profile ids")
        products = _tuple(self.related_grain_product_ids, "diagnostic product ids")
        if len(set(profiles)) != len(profiles) or len(set(products)) != len(products):
            raise CategoryProductMapValidationError("diagnostic references must be unique")
        _text(self.message, "CategoryMapDiagnostic.message")
        object.__setattr__(self, "related_profile_ids", tuple(sorted(profiles)))
        object.__setattr__(self, "related_grain_product_ids", tuple(sorted(products)))
        if self.diagnostic_id != _identity("category-map-diagnostic", self, "diagnostic_id"):
            raise CategoryProductMapValidationError("diagnostic_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryProductMapSnapshot(_CategoryMapModel):
    map_id: str
    ruleset_version: str
    category_scope: CategoryScope
    marketplace: str
    analysis_window: AnalysisWindow
    product_grain: ProductGrain
    included_products: tuple[IncludedCategoryProduct, ...]
    excluded_products: tuple[ExcludedCategoryProduct, ...]
    attribute_distributions: tuple[AttributeDistribution, ...]
    combination_segments: tuple[CategoryCombinationSegment, ...]
    coverage: CategoryMapCoverage
    denominator_registry: tuple[DistributionDenominator, ...]
    source_evidence: tuple[CategoryMapSourceEvidence, ...]
    diagnostics: tuple[CategoryMapDiagnostic, ...]

    def __post_init__(self) -> None:
        if self.ruleset_version != CATEGORY_PRODUCT_MAP_VERSION:
            raise CategoryProductMapValidationError("invalid Category Product Map ruleset version")
        if not isinstance(self.category_scope, CategoryScope):
            raise CategoryProductMapValidationError("category_scope has a wrong type")
        if self.marketplace != self.marketplace.strip().upper():
            raise CategoryProductMapValidationError("map marketplace must be uppercase")
        if not isinstance(self.analysis_window, AnalysisWindow):
            raise CategoryProductMapValidationError("analysis_window has a wrong type")
        if not isinstance(self.product_grain, ProductGrain):
            raise CategoryProductMapValidationError("product_grain has a wrong type")
        if not isinstance(self.coverage, CategoryMapCoverage):
            raise CategoryProductMapValidationError("coverage has a wrong type")
        typed = (
            ("included_products", IncludedCategoryProduct, lambda item: item.grain_product_id),
            ("excluded_products", ExcludedCategoryProduct, lambda item: item.profile_id),
            ("attribute_distributions", AttributeDistribution, lambda item: item.dimension.value),
            ("combination_segments", CategoryCombinationSegment, lambda item: item.segment_id),
            ("denominator_registry", DistributionDenominator, lambda item: item.denominator_id),
            ("source_evidence", CategoryMapSourceEvidence, lambda item: item.evidence_reference_id),
            ("diagnostics", CategoryMapDiagnostic, lambda item: item.diagnostic_id),
        )
        for name, expected, key in typed:
            values = _tuple(getattr(self, name), f"CategoryProductMapSnapshot.{name}")
            if any(not isinstance(item, expected) for item in values):
                raise CategoryProductMapValidationError(f"{name} contains a wrong type")
            keys = [key(item) for item in values]
            if len(set(keys)) != len(keys):
                raise CategoryProductMapValidationError(f"{name} contains duplicate identities")
            object.__setattr__(self, name, tuple(sorted(values, key=key)))
        if not self.included_products:
            raise CategoryProductMapValidationError("Category Product Map requires included products")
        if any(item.marketplace != self.marketplace for item in self.included_products):
            raise CategoryProductMapValidationError("included product marketplace differs from map")
        included_ids = {item.grain_product_id for item in self.included_products}
        denominators = {item.denominator_id: item for item in self.denominator_registry}
        evidence = {item.evidence_reference_id: item for item in self.source_evidence}
        referenced_evidence: set[str] = set()
        for distribution in self.attribute_distributions:
            known_denominator = denominators.get(distribution.known_value_denominator_id)
            coverage_denominator = denominators.get(distribution.coverage_denominator_id)
            unknown_denominator = denominators.get(distribution.unknown_rate_denominator_id)
            if known_denominator is None or coverage_denominator is None or unknown_denominator is None:
                raise CategoryProductMapValidationError("attribute distribution references an absent denominator")
            if known_denominator.eligible_product_count != distribution.known_value_count:
                raise CategoryProductMapValidationError("known-value denominator count mismatch")
            if coverage_denominator.eligible_product_count != distribution.total_product_count:
                raise CategoryProductMapValidationError("coverage denominator count mismatch")
            if unknown_denominator.eligible_product_count != distribution.total_product_count:
                raise CategoryProductMapValidationError("unknown-rate denominator count mismatch")
            if any(item.denominator_id != known_denominator.denominator_id for item in distribution.values):
                raise CategoryProductMapValidationError("value share denominator mismatch")
            if not set(distribution.known_grain_product_ids + distribution.unknown_grain_product_ids) <= included_ids:
                raise CategoryProductMapValidationError("attribute distribution references absent products")
            referenced_evidence.update(distribution.evidence_reference_ids)
        for segment in self.combination_segments:
            share_denominator = denominators.get(segment.share_denominator_id)
            coverage_denominator = denominators.get(segment.coverage_denominator_id)
            if share_denominator is None or coverage_denominator is None:
                raise CategoryProductMapValidationError("combination segment references an absent denominator")
            if segment.asin_share != ratio_text(segment.asin_count, share_denominator.eligible_product_count):
                raise CategoryProductMapValidationError("combination share does not match denominator")
            if segment.coverage != ratio_text(
                share_denominator.eligible_product_count,
                coverage_denominator.eligible_product_count,
            ):
                raise CategoryProductMapValidationError("combination coverage does not match denominator")
            if not set(segment.member_grain_product_ids) <= included_ids:
                raise CategoryProductMapValidationError("combination segment references absent products")
            referenced_evidence.update(segment.evidence_reference_ids)
        if referenced_evidence != set(evidence):
            raise CategoryProductMapValidationError("map source evidence must exactly index reported statistics")
        if any(item.grain_product_id not in included_ids for item in evidence.values()):
            raise CategoryProductMapValidationError("map evidence references an absent grain product")
        expected_coverage = CategoryMapCoverage(
            input_profile_count=sum(len(item.source_profile_ids) for item in self.included_products)
            + len(self.excluded_products),
            included_product_count=len(self.included_products),
            excluded_profile_count=len(self.excluded_products),
            attribute_dimension_count=len(self.attribute_distributions),
            dimensions_with_known_values=sum(item.known_value_count > 0 for item in self.attribute_distributions),
            dimensions_without_known_values=sum(item.known_value_count == 0 for item in self.attribute_distributions),
            combination_definition_count=len({item.dimensions for item in self.combination_segments}),
            combination_segment_count=len(self.combination_segments),
            source_evidence_count=len(self.source_evidence),
        )
        if self.coverage != expected_coverage:
            raise CategoryProductMapValidationError("category map coverage does not match snapshot contents")
        if self.map_id != _identity("category-product-map", self, "map_id"):
            raise CategoryProductMapValidationError("map_id does not match snapshot content")

    def validate(self) -> Self:
        self.__post_init__()
        return self


@dataclass(frozen=True, slots=True, kw_only=True)
class CategoryProductMapRequest(_CategoryMapModel):
    category_scope: CategoryScope
    marketplace: str
    analysis_window: AnalysisWindow
    product_grain: ProductGrain
    product_profiles: tuple[CanonicalProductAttributeProfile, ...]
    combination_dimensions: tuple[tuple[AttributeDimension, ...], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.category_scope, CategoryScope):
            raise CategoryProductMapValidationError("request category_scope has a wrong type")
        if self.marketplace != self.marketplace.strip().upper():
            raise CategoryProductMapValidationError("request marketplace must be uppercase")
        if not isinstance(self.analysis_window, AnalysisWindow):
            raise CategoryProductMapValidationError("request analysis_window has a wrong type")
        if not isinstance(self.product_grain, ProductGrain):
            raise CategoryProductMapValidationError("request product_grain has a wrong type")
        profiles = _tuple(self.product_profiles, "request product_profiles")
        if not profiles or any(not isinstance(item, CanonicalProductAttributeProfile) for item in profiles):
            raise CategoryProductMapValidationError("request requires Product Attribute Profiles")
        if len({item.profile_id for item in profiles}) != len(profiles):
            raise CategoryProductMapValidationError("request profile ids must be unique")
        product_profile_keys = [(item.product_identity.product_id, item.profile_id) for item in profiles]
        if len({item[0] for item in product_profile_keys}) != len(product_profile_keys):
            raise CategoryProductMapValidationError("request cannot contain multiple profiles for one ProductIdentity")
        combinations = _tuple(self.combination_dimensions, "request combination_dimensions")
        normalized: list[tuple[AttributeDimension, ...]] = []
        for combination in combinations:
            values = _tuple(combination, "request combination")
            if len(values) < 2 or any(not isinstance(item, AttributeDimension) for item in values):
                raise CategoryProductMapValidationError("each combination requires at least two dimensions")
            ordered = tuple(sorted(set(values), key=lambda item: item.value))
            if len(ordered) != len(values):
                raise CategoryProductMapValidationError("combination dimensions must be unique")
            normalized.append(ordered)
        if len(set(normalized)) != len(normalized):
            raise CategoryProductMapValidationError("combination definitions must be unique")
        object.__setattr__(self, "product_profiles", tuple(sorted(profiles, key=lambda item: item.profile_id)))
        object.__setattr__(self, "combination_dimensions", tuple(sorted(normalized, key=lambda item: tuple(d.value for d in item))))


def build_category_scope(
    *,
    scope_type: CategoryScopeType,
    scope_value: str,
    inclusion_rule: str,
) -> CategoryScope:
    payload = {
        "scope_type": scope_type,
        "scope_value": scope_value,
        "inclusion_rule": inclusion_rule,
    }
    return CategoryScope(
        category_scope_id=deterministic_id("category-scope", payload),
        **payload,
    )


def unknown_analysis_window() -> AnalysisWindow:
    return AnalysisWindow(
        status=AnalysisWindowStatus.UNKNOWN,
        period_start=None,
        period_end=None,
    )


__all__ = (
    "CATEGORY_PRODUCT_MAP_VERSION",
    "CategoryScopeType",
    "AnalysisWindowStatus",
    "DenominatorType",
    "EvidenceAwareMetricStatus",
    "CategoryScope",
    "AnalysisWindow",
    "IncludedCategoryProduct",
    "ExcludedCategoryProduct",
    "DistributionDenominator",
    "CategoryMapSourceEvidence",
    "AttributeValueDistribution",
    "AttributeDistribution",
    "EvidenceAwareMetric",
    "CategoryCombinationSegment",
    "CategoryMapCoverage",
    "CategoryMapDiagnostic",
    "CategoryProductMapSnapshot",
    "CategoryProductMapRequest",
    "build_category_scope",
    "unknown_analysis_window",
    "ratio_text",
)
