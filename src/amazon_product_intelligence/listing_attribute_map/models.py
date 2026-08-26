"""Auditable Product Attribute Map V1.0 contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
from typing import Any

from amazon_product_intelligence.product_attribute_extraction.models import (
    AttributeConfidenceLevel,
)

from .rule_pack import DIMENSIONS, SourceKind


PRODUCT_ATTRIBUTE_MAP_VERSION = "product-attribute-map-v1.0"
LISTING_ATTRIBUTE_ENGINE_VERSION = "listing-attribute-engine-v1.0"


class AttributeValueStatus(StrEnum):
    OBSERVED = "OBSERVED"
    DERIVED_RULE = "DERIVED_RULE"


class AttributeSlotStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    evidence_id: str
    source_kind: SourceKind
    source_priority: int
    source_field: str
    source_key: str | None
    source_snippet: str
    upstream_record_fingerprint: str
    confidence: AttributeConfidenceLevel
    rule_id: str
    rule_pack_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_id": self.evidence_id,
            "source_kind": self.source_kind.value,
            "source_priority": self.source_priority,
            "source_field": self.source_field,
            "source_key": self.source_key,
            "source_snippet": self.source_snippet,
            "upstream_record_fingerprint": self.upstream_record_fingerprint,
            "confidence": self.confidence.value,
            "rule_id": self.rule_id,
            "rule_pack_version": self.rule_pack_version,
        }


@dataclass(frozen=True, slots=True)
class AttributeValue:
    value_id: str
    value: Any
    status: AttributeValueStatus
    confidence: AttributeConfidenceLevel
    evidence_ids: tuple[str, ...]
    rule_id: str
    rule_pack_version: str

    def to_dict(self) -> dict[str, object]:
        return {
            "value_id": self.value_id,
            "value": self.value,
            "status": self.status.value,
            "confidence": self.confidence.value,
            "evidence_ids": list(self.evidence_ids),
            "rule_id": self.rule_id,
            "rule_pack_version": self.rule_pack_version,
        }


@dataclass(frozen=True, slots=True)
class AttributeConflict:
    conflict_id: str
    code: str
    dimension: str
    candidate_value_ids: tuple[str, ...]
    note: str

    def to_dict(self) -> dict[str, object]:
        return {
            "conflict_id": self.conflict_id,
            "code": self.code,
            "dimension": self.dimension,
            "candidate_value_ids": list(self.candidate_value_ids),
            "note": self.note,
        }


@dataclass(frozen=True, slots=True)
class AttributeSlot:
    dimension: str
    status: AttributeSlotStatus
    values: tuple[AttributeValue, ...]
    review_candidates: tuple[AttributeValue, ...]
    conflicts: tuple[AttributeConflict, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.dimension not in DIMENSIONS:
            raise ValueError(f"unsupported dimension: {self.dimension}")

    def to_dict(self) -> dict[str, object]:
        return {
            "dimension": self.dimension,
            "status": self.status.value,
            "values": [item.to_dict() for item in self.values],
            "review_candidates": [
                item.to_dict() for item in self.review_candidates
            ],
            "conflicts": [item.to_dict() for item in self.conflicts],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class ProductAttributeRecord:
    record_id: str
    semantic_fingerprint: str
    asin: str
    upstream_record_fingerprint: str
    structured_parameter_fingerprint: str | None
    evidence: tuple[EvidenceReference, ...]
    attributes: tuple[AttributeSlot, ...]
    review_required_count: int
    record_limitations: tuple[str, ...]
    conflict_count: int

    def logical_dict(self) -> dict[str, object]:
        return {
            "asin": self.asin,
            "upstream_record_fingerprint": self.upstream_record_fingerprint,
            "structured_parameter_fingerprint":
                self.structured_parameter_fingerprint,
            "evidence": [item.to_dict() for item in self.evidence],
            "attributes": [item.to_dict() for item in self.attributes],
            "review_required_count": self.review_required_count,
            "record_limitations": list(self.record_limitations),
            "conflict_count": self.conflict_count,
        }

    def to_dict(self) -> dict[str, object]:
        result = self.logical_dict()
        result.update({
            "record_id": self.record_id,
            "semantic_fingerprint": self.semantic_fingerprint,
        })
        return result


@dataclass(frozen=True, slots=True)
class ProductAttributeMapV1:
    dataset_id: str
    semantic_fingerprint: str
    upstream_dataset_id: str
    upstream_semantic_fingerprint: str
    rule_pack_id: str
    rule_pack_version: str
    rule_pack_fingerprint: str
    parser_version: str
    measurement_parser_version: str
    engine_version: str
    listing_count: int
    mapped_listing_count: int
    review_required_count: int
    conflict_count: int
    coverage: tuple[tuple[str, int], ...]
    records: tuple[ProductAttributeRecord, ...]
    contract_version: str = PRODUCT_ATTRIBUTE_MAP_VERSION

    def to_dict(self) -> dict[str, object]:
        return {
            "contract_version": self.contract_version,
            "dataset_id": self.dataset_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            "upstream": {
                "dataset_id": self.upstream_dataset_id,
                "semantic_fingerprint": self.upstream_semantic_fingerprint,
            },
            "rule_pack": {
                "id": self.rule_pack_id,
                "version": self.rule_pack_version,
                "fingerprint": self.rule_pack_fingerprint,
            },
            "parser_versions": {
                "detailed_parameters": self.parser_version,
                "measurement": self.measurement_parser_version,
                "engine": self.engine_version,
            },
            "counts": {
                "listings": self.listing_count,
                "mapped_listings": self.mapped_listing_count,
                "review_required": self.review_required_count,
                "conflicts": self.conflict_count,
            },
            "coverage": {
                dimension: count for dimension, count in self.coverage
            },
            "records": [record.to_dict() for record in self.records],
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), allow_nan=False, ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        )


__all__ = (
    "AttributeConflict", "AttributeSlot", "AttributeSlotStatus",
    "AttributeValue", "AttributeValueStatus", "EvidenceReference",
    "LISTING_ATTRIBUTE_ENGINE_VERSION", "PRODUCT_ATTRIBUTE_MAP_VERSION",
    "ProductAttributeMapV1", "ProductAttributeRecord",
)
