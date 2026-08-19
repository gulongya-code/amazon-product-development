"""Provider-neutral clean-run contracts for Data Cleaning V1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
import json
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.contracts import (
    DataQualityIssue,
    NormalizationStatus,
    PresenceStatus,
    Provenance,
    SemanticStatus,
    Unit,
)
from amazon_product_intelligence.normalization import NormalizationRuleApplication
from amazon_product_intelligence.normalization.models import json_value
from amazon_product_intelligence.provider_capabilities import CapabilityStatus


class CleaningRunStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    BLOCKED_CONFIGURATION = "BLOCKED_CONFIGURATION"


@dataclass(frozen=True, slots=True, kw_only=True)
class DataCleaningRequest:
    provider_id: str
    operation: str
    parameters: Mapping[str, Any]
    marketplace: str
    locale: str
    retrieved_at: str
    transformed_at: str
    collection_run_id: str
    normalization_run_id: str
    normalized_at: str
    currency: str | None = None

    def __post_init__(self) -> None:
        for name in (
            "provider_id",
            "operation",
            "marketplace",
            "locale",
            "retrieved_at",
            "transformed_at",
            "collection_run_id",
            "normalization_run_id",
            "normalized_at",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))


@dataclass(frozen=True, slots=True, kw_only=True)
class CleanFieldResult:
    canonical_field: str
    provider: str
    source_operation: str
    source_field: str | None
    capability_status: CapabilityStatus
    observation_id: str | None
    raw_evidence_reference: str | None
    raw_value: Any
    mapped_value: Any
    normalized_value: Any
    presence_status: PresenceStatus
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    unit: Unit | None
    issues: tuple[DataQualityIssue, ...]
    application: NormalizationRuleApplication | None
    provenance: Provenance | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "issues", tuple(self.issues))

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_field": self.canonical_field,
            "provider": self.provider,
            "source_operation": self.source_operation,
            "source_field": self.source_field,
            "capability_status": self.capability_status.value,
            "observation_id": self.observation_id,
            "raw_evidence_reference": self.raw_evidence_reference,
            "raw_value": json_value(self.raw_value),
            "mapped_value": json_value(self.mapped_value),
            "normalized_value": json_value(self.normalized_value),
            "presence_status": self.presence_status.value,
            "normalization_status": self.normalization_status.value,
            "semantic_status": self.semantic_status.value,
            "unit": None if self.unit is None else self.unit.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
            "application": None if self.application is None else self.application.to_dict(),
            "provenance": None if self.provenance is None else self.provenance.to_dict(),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CleaningQualitySummary:
    fields_observed: int
    fields_normalized: int
    fields_unchanged: int
    fields_missing: int
    fields_explicit_null: int
    fields_unknown: int
    fields_query_returned_empty: int
    fields_not_applicable: int
    fields_invalid: int
    fields_partial: int
    quality_issue_count: int

    def to_dict(self) -> dict[str, int]:
        return {
            "fields_observed": self.fields_observed,
            "fields_normalized": self.fields_normalized,
            "fields_unchanged": self.fields_unchanged,
            "fields_missing": self.fields_missing,
            "fields_explicit_null": self.fields_explicit_null,
            "fields_unknown": self.fields_unknown,
            "fields_query_returned_empty": self.fields_query_returned_empty,
            "fields_not_applicable": self.fields_not_applicable,
            "fields_invalid": self.fields_invalid,
            "fields_partial": self.fields_partial,
            "quality_issue_count": self.quality_issue_count,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CleanCanonicalResult:
    run_id: str
    provider: str
    operation: str
    retrieved_at: str
    status: CleaningRunStatus
    fields: tuple[CleanFieldResult, ...]
    quality_summary: CleaningQualitySummary
    issues: tuple[DataQualityIssue, ...]
    diagnostics: tuple[Mapping[str, Any], ...] = field(default_factory=tuple)
    raw_evidence_references: tuple[str, ...] = field(default_factory=tuple)
    transformation_run_ids: tuple[str, ...] = field(default_factory=tuple)
    mapping_versions: tuple[str, ...] = field(default_factory=tuple)
    query_execution_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fields", tuple(self.fields))
        object.__setattr__(self, "issues", tuple(self.issues))
        object.__setattr__(
            self,
            "diagnostics",
            tuple(MappingProxyType(dict(item)) for item in self.diagnostics),
        )
        for name in (
            "raw_evidence_references",
            "transformation_run_ids",
            "mapping_versions",
            "query_execution_ids",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "provider": self.provider,
            "operation": self.operation,
            "retrieved_at": self.retrieved_at,
            "status": self.status.value,
            "quality_summary": self.quality_summary.to_dict(),
            "fields": [item.to_dict() for item in self.fields],
            "issues": [item.to_dict() for item in self.issues],
            "diagnostics": [dict(item) for item in self.diagnostics],
            "raw_evidence_references": list(self.raw_evidence_references),
            "transformation_run_ids": list(self.transformation_run_ids),
            "mapping_versions": list(self.mapping_versions),
            "query_execution_ids": list(self.query_execution_ids),
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(
            self.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":") if indent is None else None,
            indent=indent,
        )


__all__ = (
    "CleanCanonicalResult",
    "CleanFieldResult",
    "CleaningQualitySummary",
    "CleaningRunStatus",
    "DataCleaningRequest",
)
