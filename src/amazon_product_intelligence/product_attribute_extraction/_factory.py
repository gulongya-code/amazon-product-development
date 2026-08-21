"""Internal constructors that centralize deterministic contract identities."""

from __future__ import annotations

from typing import Any

from amazon_product_intelligence.contracts import ProductIdentity, Unit, deterministic_id
from amazon_product_intelligence.product_intelligence import (
    EvidenceCandidate,
    ProductIntelligenceSnapshotV0_1,
)

from .models import (
    AttributeAssertionStatus,
    AttributeConfidence,
    AttributeConfidenceLevel,
    AttributeDimension,
    AttributeEvidenceSource,
    AttributeExtractionMethod,
    AttributeSourceEvidence,
    AttributeValueType,
    CanonicalAttributeAssertion,
    CanonicalAttributeValue,
)
from .quantity import QuantityCandidate
from .registry import ATTRIBUTE_TAXONOMY_VERSION


def confidence(level: AttributeConfidenceLevel, basis: str) -> AttributeConfidence:
    return AttributeConfidence(level=level, basis=(basis,))


def source_evidence(
    snapshot: ProductIntelligenceSnapshotV0_1,
    product: ProductIdentity,
    candidate: EvidenceCandidate,
) -> tuple[AttributeSourceEvidence, ...]:
    result: list[AttributeSourceEvidence] = []
    for lineage in candidate.lineage_references:
        payload = {
            "source_type": AttributeEvidenceSource.PRODUCT_INTELLIGENCE_SNAPSHOT,
            "source_artifact_ids": (snapshot.snapshot_id,),
            "product_identity": product,
            "lineage_reference": lineage,
            "source_raw_value": candidate.raw_value,
            "source_normalized_value": candidate.normalized_value,
            "source_unit": candidate.unit,
            "observed_at": candidate.time.observed_at,
            "retrieved_at": candidate.time.retrieved_at,
        }
        result.append(AttributeSourceEvidence(
            source_evidence_id=deterministic_id("attribute-source", payload),
            **payload,
        ))
    return tuple(sorted(result, key=lambda item: item.source_evidence_id))


def canonical_value(
    *,
    dimension: AttributeDimension,
    value_type: AttributeValueType,
    value: Any,
    display_value: str,
    taxonomy_value_id: str | None,
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


def assertion(
    *,
    raw_value: Any,
    normalized_value: Any,
    canonical: CanonicalAttributeValue,
    evidence: tuple[AttributeSourceEvidence, ...],
    method: AttributeExtractionMethod,
    extractor_version: str,
    confidence_value: AttributeConfidence,
    status: AttributeAssertionStatus,
) -> CanonicalAttributeAssertion:
    ordered_evidence = tuple(sorted(evidence, key=lambda item: item.source_evidence_id))
    payload = {
        "raw_value": raw_value,
        "normalized_value": normalized_value,
        "canonical_value": canonical,
        "unit": canonical.unit,
        "source_evidence": ordered_evidence,
        "extraction_method": method,
        "extractor_version": extractor_version,
        "confidence": confidence_value,
        "status": status,
    }
    return CanonicalAttributeAssertion(
        assertion_id=deterministic_id("attribute-assertion", payload),
        **payload,
    )


def quantity_candidate(
    *,
    dimension: AttributeDimension,
    raw_value: str,
    magnitude: str,
    original_unit: str,
    evidence: tuple[AttributeSourceEvidence, ...],
    method: AttributeExtractionMethod,
    extractor_version: str,
    confidence_value: AttributeConfidence,
    status: AttributeAssertionStatus = AttributeAssertionStatus.CONFIRMED,
) -> QuantityCandidate:
    ordered_evidence = tuple(sorted(evidence, key=lambda item: item.source_evidence_id))
    payload = {
        "dimension": dimension,
        "raw_value": raw_value,
        "magnitude": magnitude,
        "original_unit": original_unit,
        "source_evidence": ordered_evidence,
        "extraction_method": method,
        "extractor_version": extractor_version,
        "confidence": confidence_value,
        "assertion_status": status,
    }
    return QuantityCandidate(
        quantity_candidate_id=deterministic_id("quantity-candidate", payload),
        **payload,
    )


__all__ = ("assertion", "canonical_value", "confidence", "quantity_candidate", "source_evidence")
