"""Versioned Demand Metric and Need-to-Attribute registries V0.1."""

from __future__ import annotations

from dataclasses import dataclass

from amazon_product_intelligence.contracts import JsonContract, deterministic_id
from amazon_product_intelligence.product_attribute_extraction import AttributeDimension

from .errors import BuyerNeedMapValidationError
from .models import (
    DEMAND_METRIC_REGISTRY_VERSION,
    DemandMetricDefinition,
    DemandMetricRegistry,
    DemandMetricType,
)


NEED_ATTRIBUTE_LINK_REGISTRY_VERSION = "buyer-need-attribute-links-v0.1"


def _definition(
    *,
    metric_type: DemandMetricType,
    numerator_definition: str,
    denominator_definition: str,
    weighting_rule: str,
    time_window: str,
    coverage_requirement: str,
    confidence_rule: str,
) -> DemandMetricDefinition:
    payload = {
        "metric_type": metric_type,
        "numerator_definition": numerator_definition,
        "denominator_definition": denominator_definition,
        "weighting_rule": weighting_rule,
        "time_window": time_window,
        "coverage_requirement": coverage_requirement,
        "confidence_rule": confidence_rule,
    }
    return DemandMetricDefinition(
        metric_id=deterministic_id("demand-metric-definition", payload),
        **payload,
    )


def build_demand_metric_registry_v0_1() -> DemandMetricRegistry:
    definitions = (
        _definition(
            metric_type=DemandMetricType.SEARCH_DEMAND_SHARE,
            numerator_definition=(
                "Sum of unique, evidence-backed search_volume values for Search Term "
                "KeywordIdentity records represented by one Semantic Cluster."
            ),
            denominator_definition=(
                "Sum of unique, valid category search_volume values supplied for the same "
                "marketplace and declared analysis population."
            ),
            weighting_rule="SUM_UNIQUE_KEYWORD_SEARCH_VOLUME",
            time_window="SOURCE_SEARCH_METRIC_PERIOD_WITH_REQUEST_WINDOW_COMPATIBILITY",
            coverage_requirement="COMPLETE_DECLARED_SEARCH_POPULATION_AND_RESOLVED_VALUES",
            confidence_rule="SEPARATE_VALUE_FROM_KEYWORD_AND_POPULATION_EVIDENCE_COVERAGE",
        ),
        _definition(
            metric_type=DemandMetricType.REVIEW_MENTION_SHARE,
            numerator_definition=(
                "Count of unique Review BuyerNeedTextEvidence records represented by one "
                "Semantic Cluster."
            ),
            denominator_definition=(
                "Count of all unique valid Review BuyerNeedTextEvidence records supplied for "
                "the declared category review population."
            ),
            weighting_rule="COUNT_UNIQUE_REVIEW_TEXT_EVIDENCE",
            time_window="REQUEST_ANALYSIS_WINDOW_WITH_SOURCE_REVIEW_TIMESTAMPS",
            coverage_requirement="DECLARED_REVIEW_POPULATION_STATUS",
            confidence_rule="SEPARATE_VALUE_FROM_REVIEW_POPULATION_COMPLETENESS",
        ),
        _definition(
            metric_type=DemandMetricType.PRODUCT_COVERAGE_SHARE,
            numerator_definition=(
                "Count of Category Product Map grain products with a confirmed canonical "
                "attribute linked to the Semantic Cluster."
            ),
            denominator_definition="All included grain products in the Category Product Map.",
            weighting_rule="COUNT_UNIQUE_CATEGORY_GRAIN_PRODUCTS",
            time_window="CATEGORY_PRODUCT_MAP_ANALYSIS_WINDOW",
            coverage_requirement="CATEGORY_MAP_AND_VERSIONED_NEED_ATTRIBUTE_LINK_REQUIRED",
            confidence_rule="ATTRIBUTE_EVIDENCE_COVERAGE_ONLY_NOT_DEMAND_CONFIDENCE",
        ),
        _definition(
            metric_type=DemandMetricType.SALES_ASSOCIATED_SHARE,
            numerator_definition="Sales associated with products linked to one Semantic Cluster.",
            denominator_definition="All eligible category sales in the declared analysis window.",
            weighting_rule="SUM_EVIDENCE_BACKED_ASSOCIATED_SALES",
            time_window="EXACT_SALES_EVIDENCE_WINDOW",
            coverage_requirement="EXPLICIT_PRODUCT_SALES_ASSOCIATION_EVIDENCE_REQUIRED",
            confidence_rule="UNKNOWN_WHEN_ASSOCIATION_OR_DENOMINATOR_IS_ABSENT",
        ),
        _definition(
            metric_type=DemandMetricType.REVENUE_ASSOCIATED_SHARE,
            numerator_definition="Revenue associated with products linked to one Semantic Cluster.",
            denominator_definition="All eligible category revenue in the declared analysis window.",
            weighting_rule="SUM_EVIDENCE_BACKED_ASSOCIATED_REVENUE",
            time_window="EXACT_REVENUE_EVIDENCE_WINDOW",
            coverage_requirement="EXPLICIT_PRODUCT_REVENUE_ASSOCIATION_EVIDENCE_REQUIRED",
            confidence_rule="UNKNOWN_WHEN_ASSOCIATION_OR_DENOMINATOR_IS_ABSENT",
        ),
    )
    ordered = tuple(sorted(definitions, key=lambda item: item.metric_type.value))
    payload = {
        "registry_version": DEMAND_METRIC_REGISTRY_VERSION,
        "definitions": ordered,
    }
    return DemandMetricRegistry(
        registry_id=deterministic_id("demand-metric-registry", payload),
        **payload,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class NeedAttributeLinkDefinition(JsonContract):
    link_id: str
    cluster_label: str
    dimension: AttributeDimension
    canonical_value: str

    def __post_init__(self) -> None:
        if type(self.cluster_label) is not str or not self.cluster_label.strip():
            raise BuyerNeedMapValidationError("Need Attribute link requires cluster_label")
        if not isinstance(self.dimension, AttributeDimension):
            raise BuyerNeedMapValidationError("Need Attribute link dimension is invalid")
        if type(self.canonical_value) is not str or not self.canonical_value.strip():
            raise BuyerNeedMapValidationError("Need Attribute link requires canonical_value")
        payload = self.to_dict()
        payload.pop("link_id")
        if self.link_id != deterministic_id("need-attribute-link", payload):
            raise BuyerNeedMapValidationError("link_id does not match link content")


@dataclass(frozen=True, slots=True, kw_only=True)
class NeedAttributeLinkRegistry(JsonContract):
    registry_id: str
    registry_version: str
    links: tuple[NeedAttributeLinkDefinition, ...]

    def __post_init__(self) -> None:
        if self.registry_version != NEED_ATTRIBUTE_LINK_REGISTRY_VERSION:
            raise BuyerNeedMapValidationError("Need Attribute link registry version mismatch")
        links = tuple(self.links)
        if any(not isinstance(item, NeedAttributeLinkDefinition) for item in links):
            raise BuyerNeedMapValidationError("Need Attribute link registry contains a wrong type")
        keys = [(item.cluster_label.casefold(), item.dimension, item.canonical_value) for item in links]
        if len(set(keys)) != len(keys) or len({item.link_id for item in links}) != len(links):
            raise BuyerNeedMapValidationError("Need Attribute links must be unique")
        object.__setattr__(self, "links", tuple(sorted(links, key=lambda item: item.link_id)))
        payload = self.to_dict()
        payload.pop("registry_id")
        if self.registry_id != deterministic_id("need-attribute-link-registry", payload):
            raise BuyerNeedMapValidationError("registry_id does not match Need Attribute links")

    def for_cluster_label(self, cluster_label: str) -> tuple[NeedAttributeLinkDefinition, ...]:
        return tuple(
            item for item in self.links if item.cluster_label.casefold() == cluster_label.casefold()
        )


def _link(
    cluster_label: str,
    dimension: AttributeDimension,
    canonical_value: str,
) -> NeedAttributeLinkDefinition:
    payload = {
        "cluster_label": cluster_label,
        "dimension": dimension,
        "canonical_value": canonical_value,
    }
    return NeedAttributeLinkDefinition(
        link_id=deterministic_id("need-attribute-link", payload),
        **payload,
    )


def build_need_attribute_link_registry_v0_1() -> NeedAttributeLinkRegistry:
    links = (
        _link("Leak Prevention", AttributeDimension.FEATURE, "leakproof"),
        _link("Outdoor Portability", AttributeDimension.FEATURE, "portable"),
    )
    ordered = tuple(sorted(links, key=lambda item: item.link_id))
    payload = {
        "registry_version": NEED_ATTRIBUTE_LINK_REGISTRY_VERSION,
        "links": ordered,
    }
    return NeedAttributeLinkRegistry(
        registry_id=deterministic_id("need-attribute-link-registry", payload),
        **payload,
    )


DEMAND_METRIC_REGISTRY_V0_1 = build_demand_metric_registry_v0_1()
NEED_ATTRIBUTE_LINK_REGISTRY_V0_1 = build_need_attribute_link_registry_v0_1()


__all__ = (
    "DEMAND_METRIC_REGISTRY_V0_1",
    "NEED_ATTRIBUTE_LINK_REGISTRY_V0_1",
    "NEED_ATTRIBUTE_LINK_REGISTRY_VERSION",
    "NeedAttributeLinkDefinition",
    "NeedAttributeLinkRegistry",
    "build_demand_metric_registry_v0_1",
    "build_need_attribute_link_registry_v0_1",
)
