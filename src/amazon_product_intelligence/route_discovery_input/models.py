"""Provider-neutral contracts for supplying governed Route Discovery inputs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from amazon_product_intelligence.normalization.models import json_value
from amazon_product_intelligence.sellersprite_import.models import (
    GovernedMarketDatasetV1,
)


ROUTE_INPUT_CONTRACT_VERSION = "route-discovery-provider-input-v1.0"
ROUTE_INPUT_MAPPING_VERSION = "route-discovery-canonical-field-map-v1.0"


def _datetime(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError(f"{name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")


class RouteInputAvailabilityStatus(StrEnum):
    AVAILABLE = "AVAILABLE"
    MISSING = "MISSING"
    EXPLICIT_NULL = "EXPLICIT_NULL"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"


class RouteInputLineageDisposition(StrEnum):
    ACCEPTED = "ACCEPTED"
    ACCEPTED_EQUIVALENT = "ACCEPTED_EQUIVALENT"
    ATTRIBUTE_CONFLICT_PRESERVED = "ATTRIBUTE_CONFLICT_PRESERVED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    CONFLICT = "CONFLICT"


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteDiscoveryInputContext:
    marketplace: str
    category: str
    imported_at: str
    normalization_run_id: str
    normalized_at: str
    observed_date: str | None = None

    def __post_init__(self) -> None:
        if self.marketplace != self.marketplace.strip().upper():
            raise ValueError("marketplace must be normalized uppercase text")
        for name in ("category", "normalization_run_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        _datetime("imported_at", self.imported_at)
        _datetime("normalized_at", self.normalized_at)
        if self.observed_date is not None:
            try:
                date.fromisoformat(self.observed_date)
            except (TypeError, ValueError) as exc:
                raise ValueError("observed_date must use ISO YYYY-MM-DD") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteInputFieldMapping:
    observation_kind: str
    canonical_name: str
    canonical_field: str
    target_header: str
    required_unit_dimension: str | None = None
    required_unit_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_kind": self.observation_kind,
            "canonical_name": self.canonical_name,
            "canonical_field": self.canonical_field,
            "target_header": self.target_header,
            "required_unit_dimension": self.required_unit_dimension,
            "required_unit_code": self.required_unit_code,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteInputFieldAvailability:
    asin: str
    target_header: str
    canonical_field: str
    status: RouteInputAvailabilityStatus
    observation_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "asin": self.asin,
            "target_header": self.target_header,
            "canonical_field": self.canonical_field,
            "status": self.status.value,
            "observation_ids": list(self.observation_ids),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteInputFieldLineage:
    lineage_id: str
    asin: str
    target_header: str
    canonical_field: str
    canonical_name: str
    observation_id: str
    semantic_observation_id: str
    provider: str
    source_tool: str
    source_field: str
    raw_evidence_reference: str
    transformation_run_id: str
    mapping_version: str
    normalization_rule_id: str | None
    presence_status: str
    normalization_status: str
    semantic_status: str
    unit_dimension: str | None
    unit_code: str | None
    normalized_value_fingerprint: str | None
    disposition: RouteInputLineageDisposition

    def to_dict(self) -> dict[str, Any]:
        return {
            "lineage_id": self.lineage_id,
            "asin": self.asin,
            "target_header": self.target_header,
            "canonical_field": self.canonical_field,
            "canonical_name": self.canonical_name,
            "observation_id": self.observation_id,
            "semantic_observation_id": self.semantic_observation_id,
            "provider": self.provider,
            "source_tool": self.source_tool,
            "source_field": self.source_field,
            "raw_evidence_reference": self.raw_evidence_reference,
            "transformation_run_id": self.transformation_run_id,
            "mapping_version": self.mapping_version,
            "normalization_rule_id": self.normalization_rule_id,
            "presence_status": self.presence_status,
            "normalization_status": self.normalization_status,
            "semantic_status": self.semantic_status,
            "unit_dimension": self.unit_dimension,
            "unit_code": self.unit_code,
            "normalized_value_fingerprint": self.normalized_value_fingerprint,
            "disposition": self.disposition.value,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteInputIssue:
    issue_id: str
    code: str
    asin: str | None
    canonical_field: str | None
    observation_ids: tuple[str, ...]
    blocking: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "issue_id": self.issue_id,
            "code": self.code,
            "asin": self.asin,
            "canonical_field": self.canonical_field,
            "observation_ids": list(self.observation_ids),
            "blocking": self.blocking,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class RouteDiscoveryInputPackage:
    package_id: str
    semantic_fingerprint: str
    dataset: GovernedMarketDatasetV1
    provider_ids: tuple[str, ...]
    source_bundle_fingerprints: tuple[str, ...]
    source_raw_evidence_references: tuple[str, ...]
    source_transformation_run_ids: tuple[str, ...]
    field_availability: tuple[RouteInputFieldAvailability, ...]
    field_lineage: tuple[RouteInputFieldLineage, ...]
    issues: tuple[RouteInputIssue, ...]
    duplicate_observation_count: int
    conflict_field_count: int
    ignored_observation_count: int
    contract_version: str = ROUTE_INPUT_CONTRACT_VERSION
    mapping_version: str = ROUTE_INPUT_MAPPING_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "mapping_version": self.mapping_version,
            "package_id": self.package_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            "provider_ids": list(self.provider_ids),
            "source_bundle_fingerprints": list(self.source_bundle_fingerprints),
            "source_raw_evidence_references": list(
                self.source_raw_evidence_references
            ),
            "source_transformation_run_ids": list(
                self.source_transformation_run_ids
            ),
            "counts": {
                "duplicate_observations": self.duplicate_observation_count,
                "conflict_fields": self.conflict_field_count,
                "ignored_observations": self.ignored_observation_count,
            },
            "field_availability": [
                item.to_dict() for item in self.field_availability
            ],
            "field_lineage": [item.to_dict() for item in self.field_lineage],
            "issues": [item.to_dict() for item in self.issues],
            "dataset": self.dataset.to_dict(),
        }

    def semantic_dict(self) -> dict[str, Any]:
        """Return the exact material covered by the package fingerprint."""

        return json_value({
            "contract_version": self.contract_version,
            "mapping_version": self.mapping_version,
            "dataset_fingerprint": self.dataset.semantic_fingerprint,
            "provider_ids": list(self.provider_ids),
            "source_bundle_fingerprints": list(self.source_bundle_fingerprints),
            "source_raw_evidence_references": list(
                self.source_raw_evidence_references
            ),
            "source_transformation_run_ids": list(
                self.source_transformation_run_ids
            ),
            "field_availability": [
                item.to_dict() for item in self.field_availability
            ],
            "field_lineage": [item.to_dict() for item in self.field_lineage],
            "issues": [item.to_dict() for item in self.issues],
            "counts": {
                "duplicate_observations": self.duplicate_observation_count,
                "conflict_fields": self.conflict_field_count,
                "ignored_observations": self.ignored_observation_count,
            },
        })


__all__ = (
    "ROUTE_INPUT_CONTRACT_VERSION",
    "ROUTE_INPUT_MAPPING_VERSION",
    "RouteDiscoveryInputContext",
    "RouteDiscoveryInputPackage",
    "RouteInputAvailabilityStatus",
    "RouteInputFieldAvailability",
    "RouteInputFieldLineage",
    "RouteInputFieldMapping",
    "RouteInputIssue",
    "RouteInputLineageDisposition",
)
