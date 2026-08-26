"""Governed Product Map, route membership, and opportunity-result contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from amazon_product_intelligence.market_report.v0_2.models.common import (
    Availability,
    ContractReference,
)
from amazon_product_intelligence.market_report.v0_2.models.metric_context import (
    MetricContextEnvelope,
)


PRODUCT_MAP_CONTRACT_VERSION = "product-map-record-v1.0"
PRODUCT_ROUTE_RESULT_VERSION = "product-route-opportunity-v1.0"


class MembershipStatus(StrEnum):
    ASSIGNED = "ASSIGNED"
    UNCLASSIFIED = "UNCLASSIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class CandidateSelectionStatus(StrEnum):
    SELECTED = "SELECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass(frozen=True, slots=True)
class ProductMapField:
    field_id: str
    name: str
    source_header: str
    availability: Availability
    value: Any
    evidence_semantics: str
    upstream_record_fingerprint: str
    issue_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id, "name": self.name,
            "source_header": self.source_header,
            "availability": self.availability.value, "value": self.value,
            "evidence_semantics": self.evidence_semantics,
            "upstream_record_fingerprint": self.upstream_record_fingerprint,
            "issue_codes": list(self.issue_codes),
        }


@dataclass(frozen=True, slots=True)
class RouteAttribute:
    dimension: str
    status: str
    values: tuple[Any, ...]
    evidence_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "dimension": self.dimension, "status": self.status,
            "values": list(self.values), "evidence_ids": list(self.evidence_ids),
            "conflict_ids": list(self.conflict_ids), "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class ProductMapRecord:
    record_id: str
    semantic_fingerprint: str
    asin: str
    parent_asin: str | None
    parent_evidence_id: str
    upstream_listing_fingerprint: str
    attribute_record_id: str
    attribute_record_fingerprint: str
    attributes: tuple[RouteAttribute, ...]
    fields: tuple[ProductMapField, ...]
    flags: tuple[tuple[str, bool | None], ...]
    limitations: tuple[str, ...]
    contract_version: str = PRODUCT_MAP_CONTRACT_VERSION

    def field(self, name: str) -> ProductMapField:
        return next(item for item in self.fields if item.name == name)

    def attribute(self, dimension: str) -> RouteAttribute:
        return next(item for item in self.attributes if item.dimension == dimension)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version, "record_id": self.record_id,
            "semantic_fingerprint": self.semantic_fingerprint, "asin": self.asin,
            "parent_asin": self.parent_asin, "parent_evidence_id": self.parent_evidence_id,
            "upstream_listing_fingerprint": self.upstream_listing_fingerprint,
            "attribute_record_id": self.attribute_record_id,
            "attribute_record_fingerprint": self.attribute_record_fingerprint,
            "attributes": [item.to_dict() for item in self.attributes],
            "fields": [item.to_dict() for item in self.fields],
            "flags": {key: value for key, value in self.flags},
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class RouteMembership:
    membership_id: str
    product_map_record_id: str
    listing_reference: str
    status: MembershipStatus
    primary_route_id: str | None
    assignment_attributes: tuple[tuple[str, str], ...]
    evidence_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "membership_id": self.membership_id,
            "product_map_record_id": self.product_map_record_id,
            "listing_reference": self.listing_reference,
            "status": self.status.value, "primary_route_id": self.primary_route_id,
            "assignment_attributes": [
                {"dimension": key, "value_key": value}
                for key, value in self.assignment_attributes
            ],
            "evidence_ids": list(self.evidence_ids),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class MetricDenominator:
    denominator_id: str
    name: str
    numerator: str
    denominator: str
    eligible_count: int
    excluded_unclassified_count: int
    excluded_review_required_count: int
    unknown_count: int
    member_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "denominator_id": self.denominator_id, "name": self.name,
            "numerator": self.numerator, "denominator": self.denominator,
            "eligible_count": self.eligible_count,
            "excluded_unclassified_count": self.excluded_unclassified_count,
            "excluded_review_required_count": self.excluded_review_required_count,
            "unknown_count": self.unknown_count,
            "member_reference_ids": list(self.member_reference_ids),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class ProductRoute:
    route_id: str
    semantic_fingerprint: str
    label: str
    defining_attributes: tuple[tuple[str, str], ...]
    secondary_descriptors: tuple[tuple[str, str], ...]
    member_count: int
    member_listing_references: tuple[str, ...]
    membership_ids: tuple[str, ...]
    assignment_evidence_ids: tuple[str, ...]
    assignment_limitations: tuple[str, ...]
    attribute_coverage: tuple[tuple[str, float], ...]
    discovery_method: str
    discovery_version: str
    config_fingerprint: str
    metrics: tuple[tuple[str, MetricContextEnvelope], ...]

    def metric(self, name: str) -> MetricContextEnvelope:
        return dict(self.metrics)[name]

    def to_dict(self) -> dict[str, Any]:
        return {
            "route_id": self.route_id, "semantic_fingerprint": self.semantic_fingerprint,
            "label": self.label,
            "defining_attributes": [
                {"dimension": key, "value_key": value}
                for key, value in self.defining_attributes
            ],
            "secondary_descriptors": [
                {"dimension": key, "value_key": value}
                for key, value in self.secondary_descriptors
            ],
            "member_count": self.member_count,
            "member_listing_references": list(self.member_listing_references),
            "membership_ids": list(self.membership_ids),
            "assignment_evidence_ids": list(self.assignment_evidence_ids),
            "assignment_limitations": list(self.assignment_limitations),
            "attribute_coverage": {key: value for key, value in self.attribute_coverage},
            "discovery": {
                "method": self.discovery_method, "version": self.discovery_version,
                "config_fingerprint": self.config_fingerprint,
            },
            "metrics": {key: value.to_dict() for key, value in self.metrics},
        }


@dataclass(frozen=True, slots=True)
class CandidateRoute:
    priority: int
    route_id: str
    reason_codes: tuple[str, ...]
    minimum_distance_to_prior: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority, "route_id": self.route_id,
            "reason_codes": list(self.reason_codes),
            "minimum_distance_to_prior": self.minimum_distance_to_prior,
        }


@dataclass(frozen=True, slots=True)
class ProductRouteOpportunityResult:
    result_id: str
    semantic_fingerprint: str
    upstream_dataset_id: str
    upstream_dataset_fingerprint: str
    upstream_attribute_map_id: str
    upstream_attribute_map_fingerprint: str
    route_engine_version: str
    route_config_id: str
    route_config_version: str
    route_config_fingerprint: str
    listing_count: int
    assigned_count: int
    unclassified_count: int
    review_required_count: int
    product_map_records: tuple[ProductMapRecord, ...]
    memberships: tuple[RouteMembership, ...]
    routes: tuple[ProductRoute, ...]
    denominators: tuple[MetricDenominator, ...]
    references: tuple[ContractReference, ...]
    candidate_selection_status: CandidateSelectionStatus
    candidates: tuple[CandidateRoute, ...]
    diagnostics: tuple[tuple[str, Any], ...]
    contract_version: str = PRODUCT_ROUTE_RESULT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "result_id": self.result_id, "semantic_fingerprint": self.semantic_fingerprint,
            "upstream": {
                "governed_market_dataset": {
                    "id": self.upstream_dataset_id,
                    "fingerprint": self.upstream_dataset_fingerprint,
                },
                "product_attribute_map": {
                    "id": self.upstream_attribute_map_id,
                    "fingerprint": self.upstream_attribute_map_fingerprint,
                },
            },
            "engine": {
                "version": self.route_engine_version,
                "config_id": self.route_config_id,
                "config_version": self.route_config_version,
                "config_fingerprint": self.route_config_fingerprint,
            },
            "counts": {
                "listings": self.listing_count, "assigned": self.assigned_count,
                "unclassified": self.unclassified_count,
                "review_required": self.review_required_count,
                "routes": len(self.routes), "candidates": len(self.candidates),
            },
            "product_map_records": [item.to_dict() for item in self.product_map_records],
            "memberships": [item.to_dict() for item in self.memberships],
            "routes": [item.to_dict() for item in self.routes],
            "denominators": [item.to_dict() for item in self.denominators],
            "references": [item.to_dict() for item in self.references],
            "candidate_selection": {
                "status": self.candidate_selection_status.value,
                "candidates": [item.to_dict() for item in self.candidates],
            },
            "diagnostics": {key: value for key, value in self.diagnostics},
        }


__all__ = (
    "CandidateRoute", "CandidateSelectionStatus", "MembershipStatus",
    "MetricDenominator", "ProductMapField", "ProductMapRecord", "ProductRoute",
    "ProductRouteOpportunityResult", "RouteAttribute", "RouteMembership",
)
