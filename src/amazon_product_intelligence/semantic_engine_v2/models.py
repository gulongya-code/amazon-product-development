"""Deterministic provider-neutral contracts for Semantic Engine V2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
import json
from typing import Any, Iterable

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.market_report.v0_2.models.common import (
    Availability,
    ContractReference,
)
from amazon_product_intelligence.product_attribute_extraction.models import (
    AttributeConfidenceLevel,
)

from .errors import SemanticEngineV2Error


SEMANTIC_ENGINE_VERSION = "semantic-engine-v2.0"
SEMANTIC_FACT_CONTRACT_VERSION = "semantic-fact-v2.0"
SEMANTIC_RELATIONSHIP_CONTRACT_VERSION = "evidence-relationship-v1.1"
SEMANTIC_RESULT_CONTRACT_VERSION = "semantic-engine-result-v2.0"


class UniversalSemanticRole(StrEnum):
    PRODUCT_IDENTITY = "PRODUCT_IDENTITY"
    PRODUCT_ROLE = "PRODUCT_ROLE"
    STRUCTURAL_FORM = "STRUCTURAL_FORM"
    USAGE_ARCHITECTURE = "USAGE_ARCHITECTURE"
    INSTALLATION_ARCHITECTURE = "INSTALLATION_ARCHITECTURE"
    ATTACHMENT_MECHANISM = "ATTACHMENT_MECHANISM"
    OPERATION_MECHANISM = "OPERATION_MECHANISM"
    POWER_MODE = "POWER_MODE"
    COMPATIBILITY = "COMPATIBILITY"
    MATERIAL = "MATERIAL"
    SIZE_CAPACITY = "SIZE_CAPACITY"
    QUANTITY = "QUANTITY"
    FUNCTIONAL_FEATURE = "FUNCTIONAL_FEATURE"
    COSMETIC = "COSMETIC"


class EvidenceRelationshipState(StrEnum):
    AGREES = "AGREES"
    COMPLEMENTARY = "COMPLEMENTARY"
    COMPATIBLE_MULTI_VALUE = "COMPATIBLE_MULTI_VALUE"
    SOURCE_ONLY_TITLE = "SOURCE_ONLY_TITLE"
    SOURCE_ONLY_STRUCTURED = "SOURCE_ONLY_STRUCTURED"
    UNAVAILABLE = "UNAVAILABLE"
    TRUE_CONFLICT = "TRUE_CONFLICT"
    ROUTE_CRITICAL_CONFLICT = "ROUTE_CRITICAL_CONFLICT"


class SemanticSourceClass(StrEnum):
    LISTING_TITLE = "LISTING_TITLE"
    STRUCTURED_PARAMETERS = "STRUCTURED_PARAMETERS"
    DEDICATED_GOVERNED_FIELD = "DEDICATED_GOVERNED_FIELD"
    AUTHORIZED_SKU = "AUTHORIZED_SKU"
    BULLET_OR_ITEM_HIGHLIGHT = "BULLET_OR_ITEM_HIGHLIGHT"
    PROVIDER_CATEGORY_CONTEXT = "PROVIDER_CATEGORY_CONTEXT"
    TARGETED_ENRICHMENT = "TARGETED_ENRICHMENT"
    LLM_DERIVED_CANDIDATE = "LLM_DERIVED_CANDIDATE"


class SemanticFactStatus(StrEnum):
    OBSERVED = "OBSERVED"
    DETERMINISTIC_DERIVED = "DETERMINISTIC_DERIVED"


class SemanticDecisionStatus(StrEnum):
    GOVERNED = "GOVERNED"
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class RelationRole(StrEnum):
    PRIMARY_PRODUCT = "PRIMARY_PRODUCT"
    ACCESSORY = "ACCESSORY"
    REPLACEMENT = "REPLACEMENT"
    REFILL = "REFILL"
    BUNDLE = "BUNDLE"
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ConsumptionLifecycle(StrEnum):
    REUSABLE_DURABLE = "REUSABLE_DURABLE"
    CONSUMABLE = "CONSUMABLE"
    PERIODIC_REPLACEMENT = "PERIODIC_REPLACEMENT"
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class QuantitySubtype(StrEnum):
    PACKAGE_COUNT = "PACKAGE_COUNT"
    STRUCTURAL_COMPONENT_COUNT = "STRUCTURAL_COMPONENT_COUNT"
    CONSUMABLE_UNIT_COUNT = "CONSUMABLE_UNIT_COUNT"


class SemanticScope(StrEnum):
    ITEM = "ITEM"
    PACKAGE = "PACKAGE"
    STRUCTURAL_COMPONENT = "STRUCTURAL_COMPONENT"
    CONSUMABLE_UNIT = "CONSUMABLE_UNIT"
    HOST_DEVICE = "HOST_DEVICE"
    UNSPECIFIED = "UNSPECIFIED"


class RoleRelevance(StrEnum):
    CORE = "CORE"
    SECONDARY = "SECONDARY"
    FACET_ONLY = "FACET_ONLY"
    IGNORE = "IGNORE"


class CohortEligibilityState(StrEnum):
    PRIMARY_COHORT_ELIGIBLE = "PRIMARY_COHORT_ELIGIBLE"
    NON_PRIMARY_EXCLUDED = "NON_PRIMARY_EXCLUDED"
    OFF_TARGET_EXCLUDED = "OFF_TARGET_EXCLUDED"
    UNKNOWN = "UNKNOWN"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_value(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _texts(values: Iterable[str], name: str) -> tuple[str, ...]:
    result = tuple(sorted(set(values)))
    if any(not isinstance(item, str) or not item.strip() for item in result):
        raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", f"{name} contains blank text")
    return result


@dataclass(frozen=True, slots=True)
class SemanticEvidenceReference:
    evidence_id: str
    source_class: SemanticSourceClass
    source_field: str
    source_key: str | None
    source_content_fingerprint: str
    upstream_record_fingerprint: str
    profile_rule_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_class, SemanticSourceClass):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid source class")
        for value in (
            self.evidence_id, self.source_field, self.source_content_fingerprint,
            self.upstream_record_fingerprint, self.profile_rule_id,
        ):
            if not isinstance(value, str) or not value.strip():
                raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "evidence text is blank")

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id, "source_class": self.source_class.value,
            "source_field": self.source_field, "source_key": self.source_key,
            "source_content_fingerprint": self.source_content_fingerprint,
            "upstream_record_fingerprint": self.upstream_record_fingerprint,
            "profile_rule_id": self.profile_rule_id,
        }


@dataclass(frozen=True, slots=True)
class SemanticFact:
    fact_id: str
    semantic_fingerprint: str
    listing_reference: str
    upstream_record_fingerprint: str
    role: UniversalSemanticRole
    dimension: str
    normalized_value: Any
    availability: Availability
    fact_status: SemanticFactStatus
    confidence: AttributeConfidenceLevel
    source_classes: tuple[SemanticSourceClass, ...]
    evidence_ids: tuple[str, ...]
    quantity_kind: str | None
    semantic_scope: SemanticScope | None
    quantity_subtype: QuantitySubtype | None
    profile_id: str
    profile_version: str
    profile_fingerprint: str
    rule_id: str
    limitations: tuple[str, ...]
    review_reason_codes: tuple[str, ...]
    contract_version: str = SEMANTIC_FACT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != SEMANTIC_FACT_CONTRACT_VERSION:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "unsupported fact version")
        if not isinstance(self.role, UniversalSemanticRole):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid semantic role")
        if not isinstance(self.availability, Availability):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid availability")
        if not isinstance(self.fact_status, SemanticFactStatus):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid fact status")
        if not isinstance(self.confidence, AttributeConfidenceLevel):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid confidence")
        if self.availability is Availability.UNAVAILABLE:
            if self.normalized_value is not None or self.evidence_ids:
                raise SemanticEngineV2Error(
                    "SEMANTIC_CONTRACT_INVALID", "unavailable fact cannot publish a value/evidence"
                )
        elif self.normalized_value is None or not self.evidence_ids:
            raise SemanticEngineV2Error(
                "SEMANTIC_CONTRACT_INVALID", "available/partial fact requires value and evidence"
            )
        if self.role is UniversalSemanticRole.QUANTITY and self.quantity_subtype is None:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "quantity requires subtype")
        if self.role is UniversalSemanticRole.SIZE_CAPACITY and (
            self.quantity_kind is None or self.semantic_scope is None
        ):
            raise SemanticEngineV2Error(
                "SEMANTIC_CONTRACT_INVALID", "size/capacity requires kind and scope"
            )
        object.__setattr__(self, "normalized_value", _json_value(self.normalized_value))
        object.__setattr__(self, "source_classes", tuple(sorted(set(self.source_classes), key=lambda x: x.value)))
        object.__setattr__(self, "evidence_ids", _texts(self.evidence_ids, "fact evidence"))
        object.__setattr__(self, "limitations", _texts(self.limitations, "fact limitations"))
        object.__setattr__(self, "review_reason_codes", _texts(self.review_reason_codes, "fact review reasons"))
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "fact fingerprint mismatch")
        if self.fact_id != deterministic_id("semantic-fact-v2", logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "fact ID mismatch")

    def logical_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "listing_reference": self.listing_reference,
            "upstream_record_fingerprint": self.upstream_record_fingerprint,
            "role": self.role.value, "dimension": self.dimension,
            "normalized_value": self.normalized_value,
            "availability": self.availability.value, "fact_status": self.fact_status.value,
            "confidence": self.confidence.value,
            "source_classes": [item.value for item in self.source_classes],
            "evidence_ids": list(self.evidence_ids), "quantity_kind": self.quantity_kind,
            "semantic_scope": None if self.semantic_scope is None else self.semantic_scope.value,
            "quantity_subtype": None if self.quantity_subtype is None else self.quantity_subtype.value,
            "profile_id": self.profile_id, "profile_version": self.profile_version,
            "profile_fingerprint": self.profile_fingerprint, "rule_id": self.rule_id,
            "limitations": list(self.limitations),
            "review_reason_codes": list(self.review_reason_codes),
        }

    def to_dict(self) -> dict[str, Any]:
        return {"fact_id": self.fact_id, "semantic_fingerprint": self.semantic_fingerprint, **self.logical_dict()}


def build_semantic_fact(**content: Any) -> SemanticFact:
    material = dict(content)
    for name in ("source_classes", "evidence_ids", "limitations", "review_reason_codes"):
        if name in material:
            material[name] = tuple(sorted(set(material[name]), key=lambda x: x.value if isinstance(x, StrEnum) else x))
    logical = {
        "contract_version": SEMANTIC_FACT_CONTRACT_VERSION,
        **{
            key: (
                value.value if isinstance(value, StrEnum)
                else [item.value if isinstance(item, StrEnum) else item for item in value]
                if isinstance(value, tuple)
                else _json_value(value)
            )
            for key, value in material.items()
        },
    }
    fingerprint = _hash(logical)
    return SemanticFact(
        fact_id=deterministic_id("semantic-fact-v2", logical),
        semantic_fingerprint=fingerprint,
        **material,
    )


@dataclass(frozen=True, slots=True)
class EvidenceRelationship:
    relationship_id: str
    semantic_fingerprint: str
    listing_reference: str
    role: UniversalSemanticRole
    dimension: str
    state: EvidenceRelationshipState
    fact_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    profile_rule_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    route_critical: bool
    contract_version: str = SEMANTIC_RELATIONSHIP_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != SEMANTIC_RELATIONSHIP_CONTRACT_VERSION:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "relationship version mismatch")
        if not isinstance(self.state, EvidenceRelationshipState):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid relationship state")
        for name in ("fact_ids", "evidence_ids", "profile_rule_ids", "reason_codes"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))
        if self.state is EvidenceRelationshipState.UNAVAILABLE and self.fact_ids:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "unavailable relationship has facts")
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "relationship fingerprint mismatch")
        if self.relationship_id != deterministic_id("evidence-relationship-v1.1", logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "relationship ID mismatch")

    def logical_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "listing_reference": self.listing_reference, "role": self.role.value,
            "dimension": self.dimension, "state": self.state.value,
            "fact_ids": list(self.fact_ids), "evidence_ids": list(self.evidence_ids),
            "profile_rule_ids": list(self.profile_rule_ids),
            "reason_codes": list(self.reason_codes), "route_critical": self.route_critical,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "relationship_id": self.relationship_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            **self.logical_dict(),
        }


def build_evidence_relationship(**content: Any) -> EvidenceRelationship:
    material = dict(content)
    for name in ("fact_ids", "evidence_ids", "profile_rule_ids", "reason_codes"):
        material[name] = tuple(sorted(set(material.get(name, ()))))
    logical = {
        "contract_version": SEMANTIC_RELATIONSHIP_CONTRACT_VERSION,
        **{key: value.value if isinstance(value, StrEnum) else list(value) if isinstance(value, tuple) else value for key, value in material.items()},
    }
    return EvidenceRelationship(
        relationship_id=deterministic_id("evidence-relationship-v1.1", logical),
        semantic_fingerprint=_hash(logical),
        **material,
    )


@dataclass(frozen=True, slots=True)
class ProductIdentity:
    status: SemanticDecisionStatus
    normalized_identity: str | None
    is_target_identity: bool | None
    fact_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.status, SemanticDecisionStatus):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid identity status")
        if self.status is SemanticDecisionStatus.GOVERNED:
            if not isinstance(self.normalized_identity, str) or not self.normalized_identity.strip():
                raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "governed identity is blank")
            if type(self.is_target_identity) is not bool or not self.fact_ids:
                raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "governed identity lacks evidence")
        elif self.normalized_identity is not None or self.is_target_identity is not None:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "ungoverned identity publishes a value")
        for name in ("fact_ids", "evidence_ids", "reason_codes"):
            object.__setattr__(self, name, _texts(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value, "normalized_identity": self.normalized_identity,
            "is_target_identity": self.is_target_identity,
            "fact_ids": list(self.fact_ids), "evidence_ids": list(self.evidence_ids),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ProductRole:
    relation_role: RelationRole
    relation_status: SemanticDecisionStatus
    relation_fact_ids: tuple[str, ...]
    relation_reason_codes: tuple[str, ...]
    consumption_lifecycle: ConsumptionLifecycle
    lifecycle_status: SemanticDecisionStatus
    lifecycle_fact_ids: tuple[str, ...]
    lifecycle_reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.relation_role, RelationRole) or not isinstance(
            self.consumption_lifecycle, ConsumptionLifecycle
        ):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid Product Role enum")
        if not isinstance(self.relation_status, SemanticDecisionStatus) or not isinstance(
            self.lifecycle_status, SemanticDecisionStatus
        ):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid Product Role status")
        relation_expected = {
            SemanticDecisionStatus.UNKNOWN: RelationRole.UNKNOWN,
            SemanticDecisionStatus.REVIEW_REQUIRED: RelationRole.REVIEW_REQUIRED,
        }.get(self.relation_status)
        lifecycle_expected = {
            SemanticDecisionStatus.UNKNOWN: ConsumptionLifecycle.UNKNOWN,
            SemanticDecisionStatus.REVIEW_REQUIRED: ConsumptionLifecycle.REVIEW_REQUIRED,
        }.get(self.lifecycle_status)
        if relation_expected is not None and self.relation_role is not relation_expected:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "relation role/status mismatch")
        if lifecycle_expected is not None and self.consumption_lifecycle is not lifecycle_expected:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "lifecycle/status mismatch")
        if self.relation_status is SemanticDecisionStatus.GOVERNED and not self.relation_fact_ids:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "governed relation lacks facts")
        if self.lifecycle_status is SemanticDecisionStatus.GOVERNED and not self.lifecycle_fact_ids:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "governed lifecycle lacks facts")
        for name in (
            "relation_fact_ids", "relation_reason_codes",
            "lifecycle_fact_ids", "lifecycle_reason_codes",
        ):
            object.__setattr__(self, name, _texts(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation_role": self.relation_role.value,
            "relation_status": self.relation_status.value,
            "relation_fact_ids": list(self.relation_fact_ids),
            "relation_reason_codes": list(self.relation_reason_codes),
            "consumption_lifecycle": self.consumption_lifecycle.value,
            "lifecycle_status": self.lifecycle_status.value,
            "lifecycle_fact_ids": list(self.lifecycle_fact_ids),
            "lifecycle_reason_codes": list(self.lifecycle_reason_codes),
        }


@dataclass(frozen=True, slots=True)
class APDMarketCohortEligibility:
    state: CohortEligibilityState
    eligible_for_primary_cohort: bool
    policy_id: str
    policy_version: str
    evidence_fact_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.state, CohortEligibilityState):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid cohort state")
        if type(self.eligible_for_primary_cohort) is not bool:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "invalid cohort eligibility")
        if self.eligible_for_primary_cohort != (
            self.state is CohortEligibilityState.PRIMARY_COHORT_ELIGIBLE
        ):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "cohort state/boolean mismatch")
        for value in (self.policy_id, self.policy_version):
            if not isinstance(value, str) or not value.strip():
                raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "cohort policy is blank")
        object.__setattr__(self, "evidence_fact_ids", _texts(self.evidence_fact_ids, "cohort facts"))
        object.__setattr__(self, "reason_codes", _texts(self.reason_codes, "cohort reasons"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state.value,
            "eligible_for_primary_cohort": self.eligible_for_primary_cohort,
            "policy_id": self.policy_id, "policy_version": self.policy_version,
            "evidence_fact_ids": list(self.evidence_fact_ids),
            "reason_codes": list(self.reason_codes),
        }


@dataclass(frozen=True, slots=True)
class ListingSemanticResult:
    listing_result_id: str
    semantic_fingerprint: str
    listing_reference: str
    upstream_record_fingerprint: str
    evidence: tuple[SemanticEvidenceReference, ...]
    facts: tuple[SemanticFact, ...]
    relationships: tuple[EvidenceRelationship, ...]
    product_identity: ProductIdentity
    product_role: ProductRole
    market_cohort_eligibility: APDMarketCohortEligibility
    role_coverage: tuple[tuple[UniversalSemanticRole, Availability], ...]
    review_reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.listing_reference, str) or not self.listing_reference.strip():
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "listing reference is blank")
        if any(item.listing_reference != self.listing_reference for item in self.facts):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "fact listing mismatch")
        if any(item.listing_reference != self.listing_reference for item in self.relationships):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "relationship listing mismatch")
        evidence_ids = {item.evidence_id for item in self.evidence}
        fact_ids = {item.fact_id for item in self.facts}
        if len(evidence_ids) != len(self.evidence) or len(fact_ids) != len(self.facts):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "duplicate evidence or fact IDs")
        if any(set(item.evidence_ids) - evidence_ids for item in self.facts):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "fact references unknown evidence")
        if any(set(item.fact_ids) - fact_ids for item in self.relationships):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "relationship references unknown facts")
        if len(self.role_coverage) != len(UniversalSemanticRole) or {
            role for role, _ in self.role_coverage
        } != set(UniversalSemanticRole):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "role coverage is incomplete")
        object.__setattr__(self, "review_reason_codes", _texts(self.review_reason_codes, "listing reviews"))
        object.__setattr__(self, "limitations", _texts(self.limitations, "listing limitations"))
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "listing fingerprint mismatch")
        if self.listing_result_id != deterministic_id("listing-semantic-result-v2", logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "listing result ID mismatch")

    def logical_dict(self) -> dict[str, Any]:
        return {
            "listing_reference": self.listing_reference,
            "upstream_record_fingerprint": self.upstream_record_fingerprint,
            "evidence": [item.to_dict() for item in self.evidence],
            "facts": [item.to_dict() for item in self.facts],
            "relationships": [item.to_dict() for item in self.relationships],
            "product_identity": self.product_identity.to_dict(),
            "product_role": self.product_role.to_dict(),
            "market_cohort_eligibility": self.market_cohort_eligibility.to_dict(),
            "role_coverage": {role.value: availability.value for role, availability in self.role_coverage},
            "review_reason_codes": list(self.review_reason_codes),
            "limitations": list(self.limitations),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "listing_result_id": self.listing_result_id,
            "semantic_fingerprint": self.semantic_fingerprint,
            **self.logical_dict(),
        }


@dataclass(frozen=True, slots=True)
class SemanticEngineV2Result:
    result_id: str
    semantic_fingerprint: str
    upstream_dataset_id: str
    upstream_dataset_fingerprint: str
    semantic_engine_version: str
    profile_id: str
    profile_version: str
    profile_fingerprint: str
    listing_count: int
    listings: tuple[ListingSemanticResult, ...]
    references: tuple[ContractReference, ...]
    role_coverage_summary: tuple[tuple[str, int, int], ...]
    relationship_state_counts: tuple[tuple[str, int], ...]
    identity_status_counts: tuple[tuple[str, int], ...]
    relation_role_counts: tuple[tuple[str, int], ...]
    lifecycle_counts: tuple[tuple[str, int], ...]
    cohort_state_counts: tuple[tuple[str, int], ...]
    review_listing_count: int
    unknown_identity_count: int
    diagnostics: tuple[tuple[str, Any], ...]
    contract_version: str = SEMANTIC_RESULT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != SEMANTIC_RESULT_CONTRACT_VERSION:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "result version mismatch")
        if self.semantic_engine_version != SEMANTIC_ENGINE_VERSION:
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "engine version mismatch")
        if self.listing_count != len(self.listings):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "listing count mismatch")
        listing_ids = {item.listing_reference for item in self.listings}
        if len(listing_ids) != len(self.listings):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "duplicate listing results")
        if any(
            fact.profile_id != self.profile_id
            or fact.profile_version != self.profile_version
            or fact.profile_fingerprint != self.profile_fingerprint
            for listing in self.listings for fact in listing.facts
        ):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "profile lineage mismatch")
        logical = self.logical_dict()
        if self.semantic_fingerprint != _hash(logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "result fingerprint mismatch")
        if self.result_id != deterministic_id("semantic-engine-result-v2", logical):
            raise SemanticEngineV2Error("SEMANTIC_CONTRACT_INVALID", "result ID mismatch")

    def logical_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "upstream_dataset_id": self.upstream_dataset_id,
            "upstream_dataset_fingerprint": self.upstream_dataset_fingerprint,
            "semantic_engine_version": self.semantic_engine_version,
            "profile_id": self.profile_id, "profile_version": self.profile_version,
            "profile_fingerprint": self.profile_fingerprint,
            "listing_count": self.listing_count,
            "listings": [item.to_dict() for item in self.listings],
            "references": [item.to_dict() for item in self.references],
            "role_coverage_summary": [
                {"role": role, "available_count": available, "total_count": total}
                for role, available, total in self.role_coverage_summary
            ],
            "relationship_state_counts": dict(self.relationship_state_counts),
            "identity_status_counts": dict(self.identity_status_counts),
            "relation_role_counts": dict(self.relation_role_counts),
            "lifecycle_counts": dict(self.lifecycle_counts),
            "cohort_state_counts": dict(self.cohort_state_counts),
            "review_listing_count": self.review_listing_count,
            "unknown_identity_count": self.unknown_identity_count,
            "diagnostics": {key: value for key, value in self.diagnostics},
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id, "semantic_fingerprint": self.semantic_fingerprint,
            **self.logical_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.to_dict(), ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        )


__all__ = (
    "APDMarketCohortEligibility", "CohortEligibilityState",
    "ConsumptionLifecycle", "EvidenceRelationship", "EvidenceRelationshipState",
    "ListingSemanticResult", "ProductIdentity", "ProductRole", "QuantitySubtype",
    "RelationRole", "RoleRelevance", "SEMANTIC_ENGINE_VERSION",
    "SEMANTIC_FACT_CONTRACT_VERSION", "SEMANTIC_RELATIONSHIP_CONTRACT_VERSION",
    "SEMANTIC_RESULT_CONTRACT_VERSION", "SemanticDecisionStatus",
    "SemanticEngineV2Result", "SemanticEvidenceReference", "SemanticFact",
    "SemanticFactStatus", "SemanticScope", "SemanticSourceClass",
    "UniversalSemanticRole", "build_evidence_relationship", "build_semantic_fact",
)
