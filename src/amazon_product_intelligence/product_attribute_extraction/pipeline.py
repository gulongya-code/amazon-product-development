"""End-to-end deterministic Attribute Extraction Pipeline V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from amazon_product_intelligence.contracts import deterministic_id
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceSnapshotV0_1,
    ProductScope,
)

from ._factory import assertion, canonical_value
from .errors import ProductAttributeContractError
from .extractors import (
    BulletAttributeExtractor,
    DescriptionAttributeExtractor,
    ExtractionBatch,
    StructuredAttributeExtractor,
    TitleAttributeExtractor,
)
from .models import (
    AttributeCoverage,
    AttributeDimension,
    AttributeDimensionRegistry,
    AttributeEvidenceSource,
    AttributeExtractionRun,
    AttributeProfileStatus,
    AttributeState,
    AttributeValueType,
    CanonicalAttributeAssertion,
    CanonicalAttributeSlot,
    CanonicalProductAttributeProfile,
    ProductGrain,
)
from .quantity import (
    AttributeUnitNormalizer,
    DeterministicAttributeUnitNormalizerV0_1,
    QuantityCandidate,
)
from .registry import ATTRIBUTE_DIMENSION_REGISTRY_V0_1, ATTRIBUTE_TAXONOMY_VERSION
from .resolver import AttributeConflictResolver


ATTRIBUTE_RULES_ENGINE_VERSION = "attribute-rules-engine-v0.1"


class AttributeExtractionPipeline:
    """Run reviewed extraction stages and emit one canonical attribute profile."""

    version = ATTRIBUTE_RULES_ENGINE_VERSION

    def __init__(
        self,
        *,
        registry: AttributeDimensionRegistry = ATTRIBUTE_DIMENSION_REGISTRY_V0_1,
        unit_normalizer: AttributeUnitNormalizer | None = None,
    ) -> None:
        if not isinstance(registry, AttributeDimensionRegistry):
            raise ProductAttributeContractError("attribute pipeline requires AttributeDimensionRegistry")
        if registry.taxonomy_version != ATTRIBUTE_TAXONOMY_VERSION:
            raise ProductAttributeContractError("V0.1 pipeline requires the V0.1 attribute taxonomy")
        normalizer = unit_normalizer or DeterministicAttributeUnitNormalizerV0_1()
        if not isinstance(normalizer, AttributeUnitNormalizer):
            raise ProductAttributeContractError("unit_normalizer does not implement AttributeUnitNormalizer")
        self._registry = registry
        self._unit_normalizer = normalizer
        self._structured = StructuredAttributeExtractor(registry)
        self._title = TitleAttributeExtractor(registry)
        self._bullet = BulletAttributeExtractor(registry)
        self._description = DescriptionAttributeExtractor(registry)
        self._resolver = AttributeConflictResolver(registry)

    def extract(
        self,
        snapshot: ProductIntelligenceSnapshotV0_1,
        *,
        product_grain: ProductGrain | None = None,
    ) -> CanonicalProductAttributeProfile:
        if not isinstance(snapshot, ProductIntelligenceSnapshotV0_1):
            raise ProductAttributeContractError("attribute pipeline requires Product Intelligence snapshot")
        snapshot.validate()
        grain = product_grain or (
            ProductGrain.CHILD_ASIN
            if snapshot.scope is ProductScope.EXACT_PRODUCT
            else ProductGrain.PRODUCT_FAMILY
        )
        if not isinstance(grain, ProductGrain):
            raise ProductAttributeContractError("product_grain must be ProductGrain")
        extracted = ExtractionBatch.combine(
            self._structured.extract(snapshot),
            self._title.extract(snapshot),
            self._bullet.extract(snapshot),
            self._description.extract(snapshot),
        )
        quantity_assertions = tuple(
            result
            for candidate in extracted.quantity_candidates
            if (result := self._normalize_quantity(candidate)) is not None
        )
        all_assertions = tuple(extracted.assertions) + quantity_assertions
        slots = self._resolver.resolve(all_assertions)
        profile = self._build_profile(snapshot, grain, slots)
        profile.validate_against_registry(self._registry)
        profile.validate_against_product_intelligence_snapshot(snapshot)
        return profile

    def _normalize_quantity(
        self,
        candidate: QuantityCandidate,
    ) -> CanonicalAttributeAssertion | None:
        normalized = self._unit_normalizer.normalize(candidate)
        if normalized is None:
            return None
        value_type = (
            AttributeValueType.INTEGER
            if candidate.dimension is AttributeDimension.PACKAGE_QUANTITY
            else AttributeValueType.NUMBER
        )
        value = canonical_value(
            dimension=candidate.dimension,
            value_type=value_type,
            value=normalized.canonical_magnitude,
            display_value=(
                f"{normalized.canonical_magnitude_text} "
                f"{normalized.canonical_unit.unit_code or normalized.canonical_unit.dimension}"
            ),
            taxonomy_value_id=None,
            unit=normalized.canonical_unit,
        )
        normalized_payload = {
            "original_magnitude": normalized.original_magnitude,
            "original_unit": normalized.original_unit,
            "canonical_magnitude": normalized.canonical_magnitude,
            "canonical_magnitude_text": normalized.canonical_magnitude_text,
            "canonical_unit": normalized.canonical_unit.to_dict(),
            "normalizer_version": normalized.normalizer_version,
            "transformations": normalized.transformations,
        }
        return assertion(
            raw_value=candidate.raw_value,
            normalized_value=normalized_payload,
            canonical=value,
            evidence=candidate.source_evidence,
            method=candidate.extraction_method,
            extractor_version=f"{candidate.extractor_version}+{normalized.normalizer_version}",
            confidence_value=candidate.confidence,
            status=candidate.assertion_status,
        )

    def _build_profile(
        self,
        snapshot: ProductIntelligenceSnapshotV0_1,
        grain: ProductGrain,
        slots: Sequence[CanonicalAttributeSlot],
    ) -> CanonicalProductAttributeProfile:
        ordered_slots = tuple(sorted(slots, key=lambda item: item.dimension.value))
        evidence_by_id = {
            evidence.source_evidence_id: evidence
            for slot in ordered_slots
            for item in slot.assertions
            for evidence in item.source_evidence
        }
        evidence = tuple(sorted(evidence_by_id.values(), key=lambda item: item.source_evidence_id))
        logical_time = self._logical_extraction_time(snapshot)
        run_payload = {
            "extractor_name": "AttributeExtractionPipeline",
            "extractor_version": self.version,
            "taxonomy_version": self._registry.taxonomy_version,
            "started_at": logical_time,
            "completed_at": logical_time,
            "source_types": (AttributeEvidenceSource.PRODUCT_INTELLIGENCE_SNAPSHOT,),
        }
        run = AttributeExtractionRun(
            extraction_run_id=deterministic_id("attribute-extraction-run", run_payload),
            **run_payload,
        )
        coverage = AttributeCoverage(
            total_dimension_count=len(ordered_slots),
            present_dimension_count=sum(item.state is AttributeState.PRESENT for item in ordered_slots),
            unknown_dimension_count=sum(item.state is AttributeState.UNKNOWN for item in ordered_slots),
            ambiguous_dimension_count=sum(item.state is AttributeState.AMBIGUOUS for item in ordered_slots),
            conflicted_dimension_count=sum(item.state is AttributeState.CONFLICTED for item in ordered_slots),
            not_applicable_dimension_count=sum(
                item.state is AttributeState.NOT_APPLICABLE for item in ordered_slots
            ),
            assertion_count=sum(len(item.assertions) for item in ordered_slots),
            source_evidence_count=len(evidence),
        )
        status = (
            AttributeProfileStatus.CONFLICTED
            if any(item.state is AttributeState.CONFLICTED for item in ordered_slots)
            else AttributeProfileStatus.UNKNOWN
            if all(
                item.state in {AttributeState.UNKNOWN, AttributeState.NOT_APPLICABLE}
                for item in ordered_slots
            )
            else AttributeProfileStatus.PARTIAL
            if any(item.state in {AttributeState.UNKNOWN, AttributeState.AMBIGUOUS} for item in ordered_slots)
            else AttributeProfileStatus.READY
        )
        payload = {
            "product_identity": snapshot.target_product_identity,
            "product_grain": grain,
            "status": status,
            "attributes": ordered_slots,
            "extraction_run": run,
            "source_evidence": evidence,
            "coverage": coverage,
            "diagnostics": (),
        }
        return CanonicalProductAttributeProfile(
            profile_id=deterministic_id("attribute-profile", payload),
            **payload,
        )

    @staticmethod
    def _logical_extraction_time(snapshot: ProductIntelligenceSnapshotV0_1) -> str | None:
        retrieved = [
            candidate.time.retrieved_at
            for evidence_set in snapshot.product_fact_evidence_sets
            for candidate in evidence_set.candidates
        ] + [
            candidate.time.retrieved_at
            for series in snapshot.product_metric_series
            for candidate in series.candidates
        ]
        return max(retrieved) if retrieved else None


__all__ = ("ATTRIBUTE_RULES_ENGINE_VERSION", "AttributeExtractionPipeline")
