from __future__ import annotations

import json
from pathlib import Path
import unittest

import amazon_product_intelligence.product_attribute_extraction as attributes_api
from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    PresenceStatus,
    ProductIdentity,
    Unit,
    canonical_json,
    deterministic_id,
    product_id,
)
from amazon_product_intelligence.product_attribute_extraction import (
    ATTRIBUTE_DIMENSION_REGISTRY_V0_1,
    ATTRIBUTE_TAXONOMY_VERSION,
    AttributeAssertionStatus,
    AttributeConfidence,
    AttributeConfidenceLevel,
    AttributeCoverage,
    AttributeDimension,
    AttributeEvidenceSource,
    AttributeExtractionMethod,
    AttributeExtractionRun,
    AttributeProfileStatus,
    AttributeResolutionStatus,
    AttributeSourceEvidence,
    AttributeState,
    AttributeValueType,
    CanonicalAttributeAssertion,
    CanonicalAttributeConflict,
    CanonicalAttributeSlot,
    CanonicalAttributeValue,
    CanonicalProductAttributeProfile,
    ProductAttributeContractError,
    ProductGrain,
)
from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductScope,
)


FIXTURE = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1" / "sorftime_product_detail.json"
TARGET_ASIN = "B0G2VV4RBW"
PARENT_ASIN = "B0G2VVX3ML"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


def target() -> ProductIdentity:
    return ProductIdentity(
        product_id=product_id("US", TARGET_ASIN),
        marketplace="US",
        asin=TARGET_ASIN,
        parent_asin=PARENT_ASIN,
        identity_status="CONFIRMED",
    )


def source_adaptation_result():
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return SorftimeAdapterV0_1().adapt(
        payload,
        AdaptationContext(
            provider="sorftime",
            payload_kind="product_detail",
            source_tool="product_detail",
            marketplace="US",
            locale="en-us",
            retrieved_at=RETRIEVED_AT,
            transformed_at=TRANSFORMED_AT,
            collection_run_id="collection:sorftime:product-detail:attribute-contract-test",
            sanitized_request={"asin": TARGET_ASIN},
            currency="USD",
        ),
    )


def source_snapshot(bundle: CanonicalEvidenceBundle):
    return ProductIntelligenceBuilderV0_1().build(
        ProductIntelligenceRequest(
            target_product_identity=target(),
            scope=ProductScope.EXACT_PRODUCT,
            canonical_bundles=(bundle,),
        )
    )


def make_value(
    dimension: AttributeDimension,
    value,
    display_value: str,
    *,
    value_type: AttributeValueType = AttributeValueType.TEXT,
    taxonomy_value_id: str | None = None,
    unit: Unit | None = None,
) -> CanonicalAttributeValue:
    payload = {
        "dimension": dimension,
        "value_type": value_type,
        "value": value,
        "display_value": display_value,
        "taxonomy_version": ATTRIBUTE_TAXONOMY_VERSION,
        "taxonomy_value_id": taxonomy_value_id,
        "unit": unit,
    }
    return CanonicalAttributeValue(
        value_id=deterministic_id("attribute-value", payload),
        **payload,
    )


def candidate_for(snapshot, dimension: str):
    evidence_set = next(item for item in snapshot.product_fact_evidence_sets if item.dimension == dimension)
    return evidence_set.subject_product_identity, next(
        item for item in evidence_set.candidates if item.presence_status is PresenceStatus.PRESENT
    )


def make_source(snapshot, dimension: str, *, direct_bundle: bool = False) -> AttributeSourceEvidence:
    product, candidate = candidate_for(snapshot, dimension)
    lineage = candidate.lineage_references[0]
    source_type = (
        AttributeEvidenceSource.CANONICAL_EVIDENCE_BUNDLE
        if direct_bundle
        else AttributeEvidenceSource.PRODUCT_INTELLIGENCE_SNAPSHOT
    )
    artifacts = lineage.source_bundle_fingerprints if direct_bundle else (snapshot.snapshot_id,)
    payload = {
        "source_type": source_type,
        "source_artifact_ids": artifacts,
        "product_identity": product,
        "lineage_reference": lineage,
        "source_raw_value": candidate.raw_value,
        "source_normalized_value": candidate.normalized_value,
        "source_unit": candidate.unit,
        "observed_at": candidate.time.observed_at,
        "retrieved_at": candidate.time.retrieved_at,
    }
    return AttributeSourceEvidence(
        source_evidence_id=deterministic_id("attribute-source", payload),
        **payload,
    )


def make_assertion(
    source: AttributeSourceEvidence,
    value: CanonicalAttributeValue,
    *,
    raw_value=None,
    normalized_value=None,
    method: AttributeExtractionMethod = AttributeExtractionMethod.EXPLICIT_STRUCTURED,
    status: AttributeAssertionStatus = AttributeAssertionStatus.CONFIRMED,
) -> CanonicalAttributeAssertion:
    payload = {
        "raw_value": source.source_raw_value if raw_value is None else raw_value,
        "normalized_value": value.value if normalized_value is None else normalized_value,
        "canonical_value": value,
        "unit": value.unit,
        "source_evidence": (source,),
        "extraction_method": method,
        "extractor_version": "attribute-contract-test-v0.1",
        "confidence": AttributeConfidence(
            level=AttributeConfidenceLevel.HIGH,
            basis=("explicit canonical test evidence",),
        ),
        "status": status,
    }
    return CanonicalAttributeAssertion(
        assertion_id=deterministic_id("attribute-assertion", payload),
        **payload,
    )


def unknown_slot(dimension: AttributeDimension) -> CanonicalAttributeSlot:
    return CanonicalAttributeSlot(
        dimension=dimension,
        state=AttributeState.UNKNOWN,
        resolved_value=(),
        assertions=(),
        conflicts=(),
        resolution_status=AttributeResolutionStatus.NOT_REQUIRED,
    )


def present_slot(
    dimension: AttributeDimension,
    *assertions: CanonicalAttributeAssertion,
) -> CanonicalAttributeSlot:
    values = tuple(
        {item.canonical_value.value_id: item.canonical_value for item in assertions if item.canonical_value}.values()
    )
    return CanonicalAttributeSlot(
        dimension=dimension,
        state=AttributeState.PRESENT,
        resolved_value=values,
        assertions=assertions,
        conflicts=(),
        resolution_status=AttributeResolutionStatus.RESOLVED,
    )


def conflict_slot(
    dimension: AttributeDimension,
    *assertions: CanonicalAttributeAssertion,
) -> CanonicalAttributeSlot:
    conflict_payload = {
        "assertion_ids": tuple(sorted(item.assertion_id for item in assertions)),
        "reason_code": "DISTINCT_CANONICAL_VALUES",
        "description": "Structured and title evidence publish different canonical material values.",
    }
    conflict = CanonicalAttributeConflict(
        conflict_id=deterministic_id("attribute-conflict", conflict_payload),
        **conflict_payload,
    )
    return CanonicalAttributeSlot(
        dimension=dimension,
        state=AttributeState.CONFLICTED,
        resolved_value=(),
        assertions=assertions,
        conflicts=(conflict,),
        resolution_status=AttributeResolutionStatus.BLOCKED_BY_CONFLICT,
    )


def extraction_run(source_type: AttributeEvidenceSource) -> AttributeExtractionRun:
    payload = {
        "extractor_name": "attribute-contract-test",
        "extractor_version": "0.1",
        "taxonomy_version": ATTRIBUTE_TAXONOMY_VERSION,
        "started_at": "2026-08-20T00:00:00Z",
        "completed_at": "2026-08-20T00:00:01Z",
        "source_types": (source_type,),
    }
    return AttributeExtractionRun(
        extraction_run_id=deterministic_id("attribute-extraction-run", payload),
        **payload,
    )


def profile_status(slots: tuple[CanonicalAttributeSlot, ...]) -> AttributeProfileStatus:
    if any(item.state is AttributeState.CONFLICTED for item in slots):
        return AttributeProfileStatus.CONFLICTED
    if all(item.state in {AttributeState.UNKNOWN, AttributeState.NOT_APPLICABLE} for item in slots):
        return AttributeProfileStatus.UNKNOWN
    if any(item.state in {AttributeState.UNKNOWN, AttributeState.AMBIGUOUS} for item in slots):
        return AttributeProfileStatus.PARTIAL
    return AttributeProfileStatus.READY


def make_profile(
    slots: tuple[CanonicalAttributeSlot, ...],
    *,
    source_type: AttributeEvidenceSource = AttributeEvidenceSource.PRODUCT_INTELLIGENCE_SNAPSHOT,
) -> CanonicalProductAttributeProfile:
    slots = tuple(sorted(slots, key=lambda item: item.dimension.value))
    source_by_id = {
        source.source_evidence_id: source
        for slot in slots
        for assertion in slot.assertions
        for source in assertion.source_evidence
    }
    sources = tuple(sorted(source_by_id.values(), key=lambda item: item.source_evidence_id))
    coverage = AttributeCoverage(
        total_dimension_count=len(slots),
        present_dimension_count=sum(item.state is AttributeState.PRESENT for item in slots),
        unknown_dimension_count=sum(item.state is AttributeState.UNKNOWN for item in slots),
        ambiguous_dimension_count=sum(item.state is AttributeState.AMBIGUOUS for item in slots),
        conflicted_dimension_count=sum(item.state is AttributeState.CONFLICTED for item in slots),
        not_applicable_dimension_count=sum(item.state is AttributeState.NOT_APPLICABLE for item in slots),
        assertion_count=sum(len(item.assertions) for item in slots),
        source_evidence_count=len(sources),
    )
    payload = {
        "product_identity": target(),
        "product_grain": ProductGrain.CHILD_ASIN,
        "status": profile_status(slots),
        "attributes": slots,
        "extraction_run": extraction_run(source_type),
        "source_evidence": sources,
        "coverage": coverage,
        "diagnostics": (),
    }
    return CanonicalProductAttributeProfile(
        profile_id=deterministic_id("attribute-profile", payload),
        **payload,
    )


class ProductAttributeContractV01Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.adaptation = source_adaptation_result()
        cls.bundle = cls.adaptation.bundle.validate()
        cls.snapshot = source_snapshot(cls.bundle)
        cls.material_source = make_source(cls.snapshot, "material")
        cls.title_source = make_source(cls.snapshot, "title")

    def material_assertion(self) -> CanonicalAttributeAssertion:
        value = make_value(
            AttributeDimension.MATERIAL,
            "plastic",
            "Plastic",
            taxonomy_value_id="material.plastic",
        )
        return make_assertion(self.material_source, value)

    def test_public_api_and_registry_cover_all_required_dimensions(self) -> None:
        expected_dimensions = {
            "product_type", "material", "color", "capacity", "dimension", "size", "structure",
            "feature", "operation_method", "compatibility", "package_quantity", "audience",
            "use_case", "problem_solved", "price_band",
        }
        self.assertEqual(expected_dimensions, {item.value for item in AttributeDimension})
        self.assertEqual(expected_dimensions, {
            item.dimension.value for item in ATTRIBUTE_DIMENSION_REGISTRY_V0_1.dimensions
        })
        self.assertEqual(len(attributes_api.__all__), len(set(attributes_api.__all__)))
        self.assertFalse(any(name.startswith("_") for name in attributes_api.__all__))

    def test_create_complete_profile_with_unknown_dimensions(self) -> None:
        material = present_slot(AttributeDimension.MATERIAL, self.material_assertion())
        slots = tuple(
            material if dimension is AttributeDimension.MATERIAL else unknown_slot(dimension)
            for dimension in AttributeDimension
        )
        profile = make_profile(slots)
        self.assertEqual(15, profile.coverage.total_dimension_count)
        self.assertEqual(1, profile.coverage.present_dimension_count)
        self.assertEqual(14, profile.coverage.unknown_dimension_count)
        self.assertIs(AttributeProfileStatus.PARTIAL, profile.status)
        self.assertIs(
            AttributeState.UNKNOWN,
            next(item for item in profile.attributes if item.dimension is AttributeDimension.SIZE).state,
        )
        self.assertIs(profile, profile.validate_against_registry(ATTRIBUTE_DIMENSION_REGISTRY_V0_1))
        self.assertIs(profile, profile.validate_against_product_intelligence_snapshot(self.snapshot))

    def test_unknown_material_is_not_zero_or_an_empty_assertion(self) -> None:
        slot = unknown_slot(AttributeDimension.MATERIAL)
        self.assertIs(AttributeState.UNKNOWN, slot.state)
        self.assertEqual((), slot.resolved_value)
        self.assertEqual((), slot.assertions)
        self.assertNotIn("0", canonical_json(slot))

    def test_multi_value_feature_preserves_each_evidence_backed_assertion(self) -> None:
        leakproof = make_value(
            AttributeDimension.FEATURE,
            "leakproof",
            "Leakproof",
            taxonomy_value_id="feature.leakproof",
        )
        portable = make_value(
            AttributeDimension.FEATURE,
            "portable",
            "Portable",
            taxonomy_value_id="feature.portable",
        )
        slot = present_slot(
            AttributeDimension.FEATURE,
            make_assertion(
                self.title_source,
                leakproof,
                raw_value="Leakproof",
                method=AttributeExtractionMethod.EXPLICIT_TEXT,
            ),
            make_assertion(
                self.title_source,
                portable,
                raw_value="Portable",
                method=AttributeExtractionMethod.EXPLICIT_TEXT,
            ),
        )
        self.assertEqual({"leakproof", "portable"}, {item.value for item in slot.resolved_value})
        self.assertEqual(2, len(slot.assertions))

    def test_conflicting_structured_and_title_material_stays_unresolved(self) -> None:
        plastic = self.material_assertion()
        steel_value = make_value(
            AttributeDimension.MATERIAL,
            "stainless_steel",
            "Stainless Steel",
            taxonomy_value_id="material.stainless_steel",
        )
        steel = make_assertion(
            self.title_source,
            steel_value,
            raw_value="stainless steel",
            method=AttributeExtractionMethod.EXPLICIT_TEXT,
        )
        slot = conflict_slot(AttributeDimension.MATERIAL, plastic, steel)
        profile = make_profile(tuple(
            slot if dimension is AttributeDimension.MATERIAL else unknown_slot(dimension)
            for dimension in AttributeDimension
        ))
        self.assertIs(AttributeState.CONFLICTED, slot.state)
        self.assertEqual((), slot.resolved_value)
        self.assertIs(AttributeResolutionStatus.BLOCKED_BY_CONFLICT, slot.resolution_status)
        self.assertIs(AttributeProfileStatus.CONFLICTED, profile.status)
        self.assertEqual({plastic.assertion_id, steel.assertion_id}, set(slot.conflicts[0].assertion_ids))

    def test_evidence_lineage_replays_against_snapshot_and_bundle(self) -> None:
        snapshot_profile = make_profile((
            present_slot(AttributeDimension.MATERIAL, self.material_assertion()),
        ))
        self.assertIs(
            snapshot_profile,
            snapshot_profile.validate_against_product_intelligence_snapshot(self.snapshot),
        )

        direct_source = make_source(self.snapshot, "material", direct_bundle=True)
        value = make_value(
            AttributeDimension.MATERIAL,
            "plastic",
            "Plastic",
            taxonomy_value_id="material.plastic",
        )
        direct_profile = make_profile(
            (present_slot(AttributeDimension.MATERIAL, make_assertion(direct_source, value)),),
            source_type=AttributeEvidenceSource.CANONICAL_EVIDENCE_BUNDLE,
        )
        self.assertIs(direct_profile, direct_profile.validate_against_canonical_bundles((self.bundle,)))
        self.assertIs(
            direct_profile,
            direct_profile.validate_against_raw_evidence_records((self.adaptation.raw_evidence,)),
        )
        reference = direct_profile.source_evidence[0]
        self.assertEqual(self.material_source.lineage_reference.observation_id, reference.lineage_reference.observation_id)
        self.assertEqual(RETRIEVED_AT, reference.retrieved_at)
        self.assertEqual("US", reference.product_identity.marketplace)
        self.assertEqual(TARGET_ASIN, reference.product_identity.asin)

    def test_serialization_is_strict_and_json_safe(self) -> None:
        profile = make_profile((present_slot(AttributeDimension.MATERIAL, self.material_assertion()),))
        serialized = profile.to_dict()
        json.dumps(serialized, ensure_ascii=False, allow_nan=False)
        restored = CanonicalProductAttributeProfile.from_dict(serialized)
        self.assertEqual(canonical_json(profile), canonical_json(restored))
        tampered = dict(serialized)
        tampered["unexpected"] = True
        with self.assertRaises(ProductAttributeContractError):
            CanonicalProductAttributeProfile.from_dict(tampered)

    def test_deterministic_ids_ignore_caller_collection_order(self) -> None:
        leakproof = make_assertion(
            self.title_source,
            make_value(
                AttributeDimension.FEATURE,
                "leakproof",
                "Leakproof",
                taxonomy_value_id="feature.leakproof",
            ),
            raw_value="Leakproof",
            method=AttributeExtractionMethod.EXPLICIT_TEXT,
        )
        portable = make_assertion(
            self.title_source,
            make_value(
                AttributeDimension.FEATURE,
                "portable",
                "Portable",
                taxonomy_value_id="feature.portable",
            ),
            raw_value="Portable",
            method=AttributeExtractionMethod.EXPLICIT_TEXT,
        )
        first = make_profile((present_slot(AttributeDimension.FEATURE, leakproof, portable),))
        second = make_profile((present_slot(AttributeDimension.FEATURE, portable, leakproof),))
        self.assertEqual(first.profile_id, second.profile_id)
        self.assertEqual(canonical_json(first), canonical_json(second))

    def test_assertion_without_evidence_and_confirmed_ai_are_rejected(self) -> None:
        value = make_value(AttributeDimension.MATERIAL, "plastic", "Plastic")
        payload = {
            "raw_value": "plastic",
            "normalized_value": "plastic",
            "canonical_value": value,
            "unit": None,
            "source_evidence": (),
            "extraction_method": AttributeExtractionMethod.EXPLICIT_TEXT,
            "extractor_version": "test-v0.1",
            "confidence": AttributeConfidence(
                level=AttributeConfidenceLevel.HIGH,
                basis=("test",),
            ),
            "status": AttributeAssertionStatus.CONFIRMED,
        }
        with self.assertRaises(ProductAttributeContractError):
            CanonicalAttributeAssertion(
                assertion_id=deterministic_id("attribute-assertion", payload),
                **payload,
            )

        with self.assertRaises(ProductAttributeContractError):
            make_assertion(
                self.material_source,
                value,
                method=AttributeExtractionMethod.AI_INFERRED,
                status=AttributeAssertionStatus.CONFIRMED,
            )


if __name__ == "__main__":
    unittest.main()
