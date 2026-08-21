"""Deterministic Category Product Map aggregation from attribute profiles V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Mapping, Sequence

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.product_attribute_extraction import (
    ATTRIBUTE_DIMENSION_REGISTRY_V0_1,
    AttributeAssertionStatus,
    AttributeDimension,
    AttributeDimensionDefinition,
    AttributeDimensionRegistry,
    AttributeState,
    CanonicalAttributeAssertion,
    CanonicalAttributeValue,
    CanonicalProductAttributeProfile,
    ProductGrain,
)

from .errors import CategoryProductMapValidationError
from .models import (
    CATEGORY_PRODUCT_MAP_VERSION,
    AttributeDistribution,
    AttributeValueDistribution,
    CategoryCombinationSegment,
    CategoryMapCoverage,
    CategoryMapSourceEvidence,
    CategoryProductMapRequest,
    CategoryProductMapSnapshot,
    DenominatorType,
    DistributionDenominator,
    EvidenceAwareMetric,
    EvidenceAwareMetricStatus,
    ExcludedCategoryProduct,
    IncludedCategoryProduct,
    ratio_text,
)


DEFAULT_COMBINATION_DIMENSIONS: tuple[tuple[AttributeDimension, ...], ...] = (
    (AttributeDimension.CAPACITY, AttributeDimension.MATERIAL),
    (AttributeDimension.CAPACITY, AttributeDimension.FEATURE),
    (AttributeDimension.FEATURE, AttributeDimension.MATERIAL),
    (AttributeDimension.AUDIENCE, AttributeDimension.USE_CASE),
)

MAX_COMBINATION_MEMBERSHIPS_PER_PRODUCT = 256


@dataclass(frozen=True)
class _ResolvedGrainDimension:
    values: tuple[CanonicalAttributeValue, ...]
    evidence_by_value_id: Mapping[str, tuple[str, ...]]


@dataclass(frozen=True)
class _IncludedGrain:
    product: IncludedCategoryProduct
    dimensions: Mapping[AttributeDimension, _ResolvedGrainDimension | None]


class CategoryProductMapBuilderV0_1:
    """Aggregate resolved profile values without reparsing source text."""

    ruleset_version = CATEGORY_PRODUCT_MAP_VERSION

    def __init__(
        self,
        *,
        registry: AttributeDimensionRegistry = ATTRIBUTE_DIMENSION_REGISTRY_V0_1,
    ) -> None:
        self._registry = registry

    def build(self, request: CategoryProductMapRequest) -> CategoryProductMapSnapshot:
        included_profiles, excluded_products = self._select_profiles(request)
        if not included_profiles:
            raise CategoryProductMapValidationError(
                "Category Product Map requires at least one marketplace-matching profile"
            )

        evidence_index: dict[str, CategoryMapSourceEvidence] = {}
        grains = self._group_profiles(
            profiles=included_profiles,
            product_grain=request.product_grain,
            evidence_index=evidence_index,
        )
        denominator_index: dict[str, DistributionDenominator] = {}
        attribute_distributions = tuple(
            self._build_attribute_distribution(
                definition=definition,
                grains=grains,
                product_grain=request.product_grain,
                excluded_count=len(excluded_products),
                denominator_index=denominator_index,
            )
            for definition in self._registry.dimensions
        )
        combination_segments = self._build_combination_segments(
            definitions=request.combination_dimensions,
            grains=grains,
            product_grain=request.product_grain,
            excluded_count=len(excluded_products),
            denominator_index=denominator_index,
        )

        evidence_reference_ids = {
            evidence_id
            for distribution in attribute_distributions
            for evidence_id in distribution.evidence_reference_ids
        }
        source_evidence = tuple(
            sorted(
                (evidence_index[evidence_id] for evidence_id in evidence_reference_ids),
                key=lambda item: item.evidence_reference_id,
            )
        )
        included_products = tuple(
            sorted((grain.product for grain in grains), key=lambda item: item.grain_product_id)
        )
        excluded = tuple(sorted(excluded_products, key=lambda item: item.profile_id))
        coverage = CategoryMapCoverage(
            input_profile_count=len(request.product_profiles),
            included_product_count=len(included_products),
            excluded_profile_count=len(excluded),
            attribute_dimension_count=len(attribute_distributions),
            dimensions_with_known_values=sum(
                item.known_value_count > 0 for item in attribute_distributions
            ),
            dimensions_without_known_values=sum(
                item.known_value_count == 0 for item in attribute_distributions
            ),
            combination_definition_count=len(
                {item.dimensions for item in combination_segments}
            ),
            combination_segment_count=len(combination_segments),
            source_evidence_count=len(source_evidence),
        )
        payload = {
            "ruleset_version": self.ruleset_version,
            "category_scope": request.category_scope,
            "marketplace": request.marketplace,
            "analysis_window": request.analysis_window,
            "product_grain": request.product_grain,
            "included_products": included_products,
            "excluded_products": excluded,
            "attribute_distributions": attribute_distributions,
            "combination_segments": combination_segments,
            "coverage": coverage,
            "denominator_registry": tuple(
                sorted(denominator_index.values(), key=lambda item: item.denominator_id)
            ),
            "source_evidence": source_evidence,
            "diagnostics": (),
        }
        return CategoryProductMapSnapshot(
            map_id=deterministic_id("category-product-map", payload),
            **payload,
        )

    def _select_profiles(
        self,
        request: CategoryProductMapRequest,
    ) -> tuple[tuple[CanonicalProductAttributeProfile, ...], tuple[ExcludedCategoryProduct, ...]]:
        included: list[CanonicalProductAttributeProfile] = []
        excluded: list[ExcludedCategoryProduct] = []
        for profile in request.product_profiles:
            try:
                profile.validate_against_registry(self._registry)
            except Exception as exc:
                raise CategoryProductMapValidationError(
                    f"profile {profile.profile_id!r} is incompatible with attribute taxonomy "
                    f"{self._registry.taxonomy_version!r}: {exc}"
                ) from exc
            if profile.product_identity.marketplace != request.marketplace:
                excluded.append(
                    ExcludedCategoryProduct(
                        profile_id=profile.profile_id,
                        product_identity=profile.product_identity,
                        reason_code="MARKETPLACE_MISMATCH",
                        message=(
                            f"Profile marketplace {profile.product_identity.marketplace} does not "
                            f"match requested marketplace {request.marketplace}."
                        ),
                    )
                )
            else:
                included.append(profile)
        return tuple(included), tuple(excluded)

    def _group_profiles(
        self,
        *,
        profiles: Sequence[CanonicalProductAttributeProfile],
        product_grain: ProductGrain,
        evidence_index: dict[str, CategoryMapSourceEvidence],
    ) -> tuple[_IncludedGrain, ...]:
        grouped: dict[str, list[CanonicalProductAttributeProfile]] = {}
        for profile in profiles:
            grain_asin = self._grain_asin(profile, product_grain)
            grouped.setdefault(grain_asin, []).append(profile)

        results: list[_IncludedGrain] = []
        for grain_asin, grouped_profiles in sorted(grouped.items()):
            ordered_profiles = tuple(sorted(grouped_profiles, key=lambda item: item.profile_id))
            grain_payload = {
                "marketplace": ordered_profiles[0].product_identity.marketplace,
                "product_grain": product_grain,
                "grain_asin": grain_asin,
                "source_profile_ids": tuple(item.profile_id for item in ordered_profiles),
            }
            grain_product_id = deterministic_id("category-grain-product", grain_payload)
            included_product = IncludedCategoryProduct(
                grain_product_id=grain_product_id,
                marketplace=ordered_profiles[0].product_identity.marketplace,
                grain_asin=grain_asin,
                member_product_identities=tuple(
                    sorted(
                        (item.product_identity for item in ordered_profiles),
                        key=lambda item: item.product_id,
                    )
                ),
                source_profile_ids=tuple(item.profile_id for item in ordered_profiles),
            )
            dimensions = {
                definition.dimension: self._resolve_group_dimension(
                    profiles=ordered_profiles,
                    dimension=definition.dimension,
                    grain_product_id=grain_product_id,
                    evidence_index=evidence_index,
                )
                for definition in self._registry.dimensions
            }
            results.append(_IncludedGrain(product=included_product, dimensions=dimensions))
        return tuple(results)

    @staticmethod
    def _grain_asin(
        profile: CanonicalProductAttributeProfile,
        product_grain: ProductGrain,
    ) -> str:
        identity = profile.product_identity
        if product_grain is ProductGrain.CHILD_ASIN:
            return identity.asin
        if product_grain in {ProductGrain.PARENT_ASIN, ProductGrain.PRODUCT_FAMILY}:
            return identity.parent_asin or identity.asin
        raise CategoryProductMapValidationError(
            f"unsupported Category Product Map grain: {product_grain.value}"
        )

    def _resolve_group_dimension(
        self,
        *,
        profiles: Sequence[CanonicalProductAttributeProfile],
        dimension: AttributeDimension,
        grain_product_id: str,
        evidence_index: dict[str, CategoryMapSourceEvidence],
    ) -> _ResolvedGrainDimension | None:
        profile_slots = []
        for profile in profiles:
            slots = {slot.dimension: slot for slot in profile.attributes}
            slot = slots.get(dimension)
            if slot is None or slot.state is not AttributeState.PRESENT or not slot.resolved_value:
                return None
            profile_slots.append((profile, slot))

        values: dict[str, CanonicalAttributeValue] = {}
        evidence_by_value: dict[str, set[str]] = {}
        for profile, slot in profile_slots:
            assertions = self._confirmed_assertions_by_value(slot.assertions)
            for value in slot.resolved_value:
                previous = values.setdefault(value.value_id, value)
                if canonical_json(previous) != canonical_json(value):
                    raise CategoryProductMapValidationError(
                        f"canonical attribute value id collision: {value.value_id!r}"
                    )
                supporting_assertions = assertions.get(value.value_id, ())
                if not supporting_assertions:
                    raise CategoryProductMapValidationError(
                        f"resolved value {value.value_id!r} has no confirmed assertion"
                    )
                for assertion in supporting_assertions:
                    evidence = self._make_source_evidence(
                        profile=profile,
                        grain_product_id=grain_product_id,
                        dimension=dimension,
                        assertion=assertion,
                    )
                    existing = evidence_index.setdefault(
                        evidence.evidence_reference_id,
                        evidence,
                    )
                    if canonical_json(existing) != canonical_json(evidence):
                        raise CategoryProductMapValidationError(
                            "category evidence reference id collision: "
                            f"{evidence.evidence_reference_id!r}"
                        )
                    evidence_by_value.setdefault(value.value_id, set()).add(
                        evidence.evidence_reference_id
                    )
        return _ResolvedGrainDimension(
            values=tuple(sorted(values.values(), key=lambda item: item.value_id)),
            evidence_by_value_id={
                value_id: tuple(sorted(reference_ids))
                for value_id, reference_ids in sorted(evidence_by_value.items())
            },
        )

    @staticmethod
    def _confirmed_assertions_by_value(
        assertions: Sequence[CanonicalAttributeAssertion],
    ) -> dict[str, tuple[CanonicalAttributeAssertion, ...]]:
        grouped: dict[str, list[CanonicalAttributeAssertion]] = {}
        for assertion in assertions:
            if (
                assertion.status is AttributeAssertionStatus.CONFIRMED
                and assertion.canonical_value is not None
            ):
                grouped.setdefault(assertion.canonical_value.value_id, []).append(assertion)
        return {
            value_id: tuple(sorted(items, key=lambda item: item.assertion_id))
            for value_id, items in grouped.items()
        }

    @staticmethod
    def _make_source_evidence(
        *,
        profile: CanonicalProductAttributeProfile,
        grain_product_id: str,
        dimension: AttributeDimension,
        assertion: CanonicalAttributeAssertion,
    ) -> CategoryMapSourceEvidence:
        payload = {
            "profile_id": profile.profile_id,
            "grain_product_id": grain_product_id,
            "product_identity": profile.product_identity,
            "dimension": dimension,
            "assertion": assertion,
            "source_evidence": tuple(assertion.source_evidence),
        }
        return CategoryMapSourceEvidence(
            evidence_reference_id=deterministic_id("category-map-evidence", payload),
            **payload,
        )

    def _build_attribute_distribution(
        self,
        *,
        definition: AttributeDimensionDefinition,
        grains: Sequence[_IncludedGrain],
        product_grain: ProductGrain,
        excluded_count: int,
        denominator_index: dict[str, DistributionDenominator],
    ) -> AttributeDistribution:
        dimension = definition.dimension
        known_grains = tuple(
            grain for grain in grains if grain.dimensions[dimension] is not None
        )
        unknown_grains = tuple(
            grain for grain in grains if grain.dimensions[dimension] is None
        )
        all_ids = tuple(sorted(grain.product.grain_product_id for grain in grains))
        known_ids = tuple(sorted(grain.product.grain_product_id for grain in known_grains))
        unknown_ids = tuple(sorted(grain.product.grain_product_id for grain in unknown_grains))
        coverage_denominator = self._register_denominator(
            metric_name=f"attribute.{dimension.value}.coverage",
            denominator_type=DenominatorType.ALL_INCLUDED_PRODUCTS,
            eligible_ids=all_ids,
            excluded_count=excluded_count,
            unknown_count=len(unknown_ids),
            product_grain=product_grain,
            filter_conditions=("marketplace_match",),
            denominator_index=denominator_index,
        )
        unknown_rate_denominator = self._register_denominator(
            metric_name=f"attribute.{dimension.value}.unknown_rate",
            denominator_type=DenominatorType.ALL_INCLUDED_PRODUCTS,
            eligible_ids=all_ids,
            excluded_count=excluded_count,
            unknown_count=len(unknown_ids),
            product_grain=product_grain,
            filter_conditions=("marketplace_match",),
            denominator_index=denominator_index,
        )
        known_value_denominator = self._register_denominator(
            metric_name=f"attribute.{dimension.value}.known_value_share",
            denominator_type=DenominatorType.KNOWN_ATTRIBUTE_PRODUCTS,
            eligible_ids=known_ids,
            excluded_count=excluded_count,
            unknown_count=len(unknown_ids),
            product_grain=product_grain,
            filter_conditions=("marketplace_match", f"{dimension.value}_state_present"),
            denominator_index=denominator_index,
        )

        canonical_values: dict[str, CanonicalAttributeValue] = {}
        members_by_value: dict[str, set[str]] = {}
        evidence_by_value: dict[str, set[str]] = {}
        for grain in known_grains:
            resolved = grain.dimensions[dimension]
            assert resolved is not None
            for value in resolved.values:
                previous = canonical_values.setdefault(value.value_id, value)
                if canonical_json(previous) != canonical_json(value):
                    raise CategoryProductMapValidationError(
                        f"canonical attribute value id collision: {value.value_id!r}"
                    )
                members_by_value.setdefault(value.value_id, set()).add(
                    grain.product.grain_product_id
                )
                evidence_by_value.setdefault(value.value_id, set()).update(
                    resolved.evidence_by_value_id[value.value_id]
                )

        value_distributions: list[AttributeValueDistribution] = []
        for value_id in sorted(canonical_values):
            members = tuple(sorted(members_by_value[value_id]))
            evidence = tuple(sorted(evidence_by_value[value_id]))
            payload = {
                "canonical_value": canonical_values[value_id],
                "asin_count": len(members),
                "asin_share": ratio_text(len(members), len(known_ids)),
                "denominator_id": known_value_denominator.denominator_id,
                "member_grain_product_ids": members,
                "evidence_reference_ids": evidence,
            }
            value_distributions.append(
                AttributeValueDistribution(
                    value_metric_id=deterministic_id(
                        "attribute-value-distribution", payload
                    ),
                    **payload,
                )
            )

        distribution_evidence = tuple(
            sorted(
                {
                    evidence_id
                    for value in value_distributions
                    for evidence_id in value.evidence_reference_ids
                }
            )
        )
        payload = {
            "dimension": dimension,
            "values": tuple(value_distributions),
            "total_product_count": len(grains),
            "known_value_count": len(known_ids),
            "unknown_count": len(unknown_ids),
            "attribute_coverage": ratio_text(len(known_ids), len(grains)),
            "unknown_rate": ratio_text(len(unknown_ids), len(grains)),
            "known_value_denominator_id": known_value_denominator.denominator_id,
            "coverage_denominator_id": coverage_denominator.denominator_id,
            "unknown_rate_denominator_id": unknown_rate_denominator.denominator_id,
            "known_grain_product_ids": known_ids,
            "unknown_grain_product_ids": unknown_ids,
            "evidence_reference_ids": distribution_evidence,
        }
        return AttributeDistribution(
            distribution_id=deterministic_id("attribute-distribution", payload),
            **payload,
        )

    def _build_combination_segments(
        self,
        *,
        definitions: Sequence[tuple[AttributeDimension, ...]],
        grains: Sequence[_IncludedGrain],
        product_grain: ProductGrain,
        excluded_count: int,
        denominator_index: dict[str, DistributionDenominator],
    ) -> tuple[CategoryCombinationSegment, ...]:
        segments: list[CategoryCombinationSegment] = []
        all_ids = tuple(sorted(grain.product.grain_product_id for grain in grains))
        for dimensions in definitions:
            eligible_grains = tuple(
                grain
                for grain in grains
                if all(grain.dimensions[dimension] is not None for dimension in dimensions)
            )
            eligible_ids = tuple(
                sorted(grain.product.grain_product_id for grain in eligible_grains)
            )
            key = "+".join(item.value for item in dimensions)
            coverage_denominator = self._register_denominator(
                metric_name=f"combination.{key}.coverage",
                denominator_type=DenominatorType.ALL_INCLUDED_PRODUCTS,
                eligible_ids=all_ids,
                excluded_count=excluded_count,
                unknown_count=len(grains) - len(eligible_grains),
                product_grain=product_grain,
                filter_conditions=("marketplace_match",),
                denominator_index=denominator_index,
            )
            share_denominator = self._register_denominator(
                metric_name=f"combination.{key}.asin_share",
                denominator_type=DenominatorType.COMPLETE_COMBINATION_PRODUCTS,
                eligible_ids=eligible_ids,
                excluded_count=excluded_count,
                unknown_count=len(grains) - len(eligible_grains),
                product_grain=product_grain,
                filter_conditions=tuple(
                    sorted(
                        ("marketplace_match",)
                        + tuple(f"{dimension.value}_state_present" for dimension in dimensions)
                    )
                ),
                denominator_index=denominator_index,
            )

            values_by_combination: dict[
                tuple[str, ...], tuple[CanonicalAttributeValue, ...]
            ] = {}
            members_by_combination: dict[tuple[str, ...], set[str]] = {}
            evidence_by_combination: dict[tuple[str, ...], set[str]] = {}
            for grain in eligible_grains:
                resolved_dimensions = []
                membership_count = 1
                for dimension in dimensions:
                    resolved = grain.dimensions[dimension]
                    assert resolved is not None
                    resolved_dimensions.append(resolved)
                    membership_count *= len(resolved.values)
                if membership_count > MAX_COMBINATION_MEMBERSHIPS_PER_PRODUCT:
                    raise CategoryProductMapValidationError(
                        f"combination {key!r} expands product "
                        f"{grain.product.grain_product_id!r} to {membership_count} memberships; "
                        f"limit is {MAX_COMBINATION_MEMBERSHIPS_PER_PRODUCT}"
                    )
                for combination_values in product(
                    *(resolved.values for resolved in resolved_dimensions)
                ):
                    combination_key = tuple(value.value_id for value in combination_values)
                    previous = values_by_combination.setdefault(
                        combination_key,
                        tuple(combination_values),
                    )
                    if canonical_json(previous) != canonical_json(combination_values):
                        raise CategoryProductMapValidationError(
                            f"combination value id collision for {combination_key!r}"
                        )
                    members_by_combination.setdefault(combination_key, set()).add(
                        grain.product.grain_product_id
                    )
                    combination_evidence = evidence_by_combination.setdefault(
                        combination_key,
                        set(),
                    )
                    for index, value in enumerate(combination_values):
                        combination_evidence.update(
                            resolved_dimensions[index].evidence_by_value_id[value.value_id]
                        )

            for combination_key in sorted(values_by_combination):
                canonical_values = values_by_combination[combination_key]
                members = tuple(sorted(members_by_combination[combination_key]))
                evidence = tuple(sorted(evidence_by_combination[combination_key]))
                metric_scope_id = deterministic_id(
                    "category-combination-metric-scope",
                    {
                        "dimensions": dimensions,
                        "canonical_values": canonical_values,
                        "product_grain": product_grain,
                        "member_grain_product_ids": members,
                    },
                )
                payload = {
                    "dimensions": tuple(dimensions),
                    "canonical_values": canonical_values,
                    "asin_count": len(members),
                    "asin_share": ratio_text(len(members), len(eligible_ids)),
                    "coverage": ratio_text(len(eligible_ids), len(grains)),
                    "share_denominator_id": share_denominator.denominator_id,
                    "coverage_denominator_id": coverage_denominator.denominator_id,
                    "member_grain_product_ids": members,
                    "sales_metrics": self._unknown_metric(
                        metric_name="sales_share", metric_scope_id=metric_scope_id
                    ),
                    "revenue_metrics": self._unknown_metric(
                        metric_name="revenue_share", metric_scope_id=metric_scope_id
                    ),
                    "review_metrics": self._unknown_metric(
                        metric_name="review_share", metric_scope_id=metric_scope_id
                    ),
                    "competition_metrics": self._unknown_metric(
                        metric_name="competition_level", metric_scope_id=metric_scope_id
                    ),
                    "evidence_reference_ids": evidence,
                }
                segments.append(
                    CategoryCombinationSegment(
                        segment_id=deterministic_id(
                            "category-combination-segment", payload
                        ),
                        **payload,
                    )
                )
        return tuple(sorted(segments, key=lambda item: item.segment_id))

    @staticmethod
    def _unknown_metric(*, metric_name: str, metric_scope_id: str) -> EvidenceAwareMetric:
        payload = {
            "metric_name": metric_name,
            "metric_scope_id": metric_scope_id,
            "status": EvidenceAwareMetricStatus.UNKNOWN,
            "value": None,
            "unit": None,
            "denominator_id": None,
            "evidence_ids": (),
            "limitations": (
                "Category Product Map v0.1 receives attribute profiles only; "
                f"no observed {metric_name} evidence was supplied.",
            ),
        }
        return EvidenceAwareMetric(
            metric_id=deterministic_id("evidence-aware-metric", payload),
            **payload,
        )

    @staticmethod
    def _register_denominator(
        *,
        metric_name: str,
        denominator_type: DenominatorType,
        eligible_ids: Sequence[str],
        excluded_count: int,
        unknown_count: int,
        product_grain: ProductGrain,
        filter_conditions: Sequence[str],
        denominator_index: dict[str, DistributionDenominator],
    ) -> DistributionDenominator:
        sorted_eligible_ids = tuple(sorted(eligible_ids))
        sorted_conditions = tuple(sorted(filter_conditions))
        payload = {
            "metric_name": metric_name,
            "denominator_type": denominator_type,
            "eligible_product_count": len(sorted_eligible_ids),
            "excluded_product_count": excluded_count,
            "unknown_count": unknown_count,
            "grain_policy": product_grain,
            "filter_conditions": sorted_conditions,
            "eligible_grain_product_ids": sorted_eligible_ids,
        }
        denominator = DistributionDenominator(
            denominator_id=deterministic_id("distribution-denominator", payload),
            **payload,
        )
        existing = denominator_index.setdefault(denominator.denominator_id, denominator)
        if canonical_json(existing) != canonical_json(denominator):
            raise CategoryProductMapValidationError(
                f"denominator id collision: {denominator.denominator_id!r}"
            )
        return existing


__all__ = (
    "DEFAULT_COMBINATION_DIMENSIONS",
    "MAX_COMBINATION_MEMBERSHIPS_PER_PRODUCT",
    "CategoryProductMapBuilderV0_1",
)
