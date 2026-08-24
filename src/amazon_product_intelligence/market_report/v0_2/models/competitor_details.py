"""Evidence-linked competitor detail projections for Market Report V0.2."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from ..version import (
    COMPETITOR_DETAIL_RECORD_CONTRACT_VERSION,
    COMPETITOR_DETAIL_SECTION_CONTRACT_VERSION,
    COMPETITOR_FIELD_CONTRACT_VERSION,
)
from .common import (
    Availability,
    CompletenessStatus,
    ContractReference,
    EvidenceSemantics,
    MarketReportV0_2ValidationError,
    PresenceStatus,
    V0_2Contract,
    freeze_json,
    identity,
    normalize_references,
    optional_text,
    policy_pair,
    text,
    texts,
    validate_registered_references,
)
from .metric_context import MetricContextEnvelope
from .true_competitor_set import CompetitorDispositionType


class CompetitorFieldGroup(StrEnum):
    IDENTITY_CATALOG = "IDENTITY_CATALOG"
    PRODUCT_FACTS = "PRODUCT_FACTS"
    MARKET_REVIEW_METRICS = "MARKET_REVIEW_METRICS"
    FULFILLMENT_ECONOMICS = "FULFILLMENT_ECONOMICS"
    SELLER_MARKETING = "SELLER_MARKETING"


class CompetitorDetailPurpose(StrEnum):
    EVALUATED_CANDIDATES = "EVALUATED_CANDIDATES"
    INCLUDED_COMPETITORS = "INCLUDED_COMPETITORS"
    REVIEW_QUEUE = "REVIEW_QUEUE"


_FORBIDDEN_FIELD_TOKENS = (
    "raw_payload",
    "authorization",
    "api_key",
    "credential",
    "access_token",
    "secret",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class EvidenceAwareFieldProjection(V0_2Contract):
    field_id: str
    contract_version: str
    field_name: str
    field_group: CompetitorFieldGroup
    availability: Availability
    presence_status: PresenceStatus
    evidence_semantics: EvidenceSemantics
    value: Any
    display_value: str | None
    method_policy_id: str | None
    method_policy_version: str | None
    source_reference_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.field_name, "EvidenceAwareFieldProjection.field_name")
        normalized_name = self.field_name.casefold()
        if any(token in normalized_name for token in _FORBIDDEN_FIELD_TOKENS):
            raise MarketReportV0_2ValidationError(
                "competitor field names cannot represent raw payloads or credentials"
            )
        if self.contract_version != COMPETITOR_FIELD_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported competitor field contract version"
            )
        if not isinstance(self.field_group, CompetitorFieldGroup):
            raise MarketReportV0_2ValidationError(
                "competitor field group is invalid"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "competitor field availability is invalid"
            )
        if not isinstance(self.presence_status, PresenceStatus):
            raise MarketReportV0_2ValidationError(
                "competitor field presence status is invalid"
            )
        if not isinstance(self.evidence_semantics, EvidenceSemantics):
            raise MarketReportV0_2ValidationError(
                "competitor field evidence semantics is invalid"
            )
        optional_text(self.display_value, "EvidenceAwareFieldProjection.display_value")
        policy_pair(
            self.method_policy_id,
            self.method_policy_version,
            "EvidenceAwareFieldProjection.method",
        )
        if self.evidence_semantics in {
            EvidenceSemantics.RESOLVED,
            EvidenceSemantics.DERIVED,
        }:
            policy_pair(
                self.method_policy_id,
                self.method_policy_version,
                "EvidenceAwareFieldProjection.method",
                required=True,
            )
        sources = texts(
            self.source_reference_ids,
            "EvidenceAwareFieldProjection.source_reference_ids",
            allow_empty=False,
        )
        evidence = texts(
            self.evidence_ids, "EvidenceAwareFieldProjection.evidence_ids"
        )
        provenance = texts(
            self.provenance_reference_ids,
            "EvidenceAwareFieldProjection.provenance_reference_ids",
            allow_empty=False,
        )
        limitations = texts(
            self.limitations, "EvidenceAwareFieldProjection.limitations"
        )
        value = None if self.value is None else freeze_json(
            self.value, "EvidenceAwareFieldProjection.value"
        )
        if isinstance(value, str) and not value.strip():
            raise MarketReportV0_2ValidationError(
                "competitor field cannot publish empty text"
            )
        if self.presence_status is PresenceStatus.PRESENT:
            if value is None or self.display_value is None:
                raise MarketReportV0_2ValidationError(
                    "PRESENT competitor field requires value and display value"
                )
        elif value is not None or self.display_value is not None:
            raise MarketReportV0_2ValidationError(
                "non-PRESENT competitor field cannot publish a value"
            )
        if self.availability is Availability.AVAILABLE:
            if (
                self.presence_status is not PresenceStatus.PRESENT
                or value is None
                or not evidence
            ):
                raise MarketReportV0_2ValidationError(
                    "available competitor field requires present value and evidence"
                )
        elif self.availability is Availability.PARTIAL:
            if not limitations:
                raise MarketReportV0_2ValidationError(
                    "partial competitor field requires limitations"
                )
            if value is not None and not evidence:
                raise MarketReportV0_2ValidationError(
                    "partial competitor field value requires evidence"
                )
        elif value is not None or self.display_value is not None or not limitations:
            raise MarketReportV0_2ValidationError(
                "unavailable competitor field requires null value and limitations"
            )
        if value is None and self.evidence_semantics is not EvidenceSemantics.UNKNOWN:
            raise MarketReportV0_2ValidationError(
                "competitor field without value must use UNKNOWN evidence semantics"
            )
        if self.evidence_semantics is EvidenceSemantics.PROVIDER_ESTIMATE and not evidence:
            raise MarketReportV0_2ValidationError(
                "Provider-estimated competitor field requires evidence"
            )
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "source_reference_ids", sources)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.field_id != identity(
            "market-report-v0.2-competitor-field", self, "field_id"
        ):
            raise MarketReportV0_2ValidationError(
                "competitor field_id does not match content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitorDetailRecord(V0_2Contract):
    record_id: str
    contract_version: str
    purpose: CompetitorDetailPurpose
    availability: Availability
    marketplace: str
    scope_context_reference_id: str
    true_competitor_set_reference_id: str
    disposition_reference_id: str
    disposition: CompetitorDispositionType
    grain_entity_reference_id: str
    product_identity_reference_ids: tuple[str, ...]
    product_intelligence_reference_ids: tuple[str, ...]
    canonical_source_reference_ids: tuple[str, ...]
    fields: tuple[EvidenceAwareFieldProjection, ...]
    metrics: tuple[MetricContextEnvelope, ...]
    references: tuple[ContractReference, ...]
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != COMPETITOR_DETAIL_RECORD_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported competitor detail record version"
            )
        if not isinstance(self.purpose, CompetitorDetailPurpose):
            raise MarketReportV0_2ValidationError(
                "competitor detail purpose is invalid"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "competitor detail availability is invalid"
            )
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise MarketReportV0_2ValidationError(
                "competitor detail marketplace must be uppercase text"
            )
        for name in (
            "scope_context_reference_id",
            "true_competitor_set_reference_id",
            "disposition_reference_id",
            "grain_entity_reference_id",
        ):
            text(getattr(self, name), f"CompetitorDetailRecord.{name}")
        if not isinstance(self.disposition, CompetitorDispositionType):
            raise MarketReportV0_2ValidationError(
                "competitor detail disposition is invalid"
            )
        self._validate_purpose()
        products = texts(
            self.product_identity_reference_ids,
            "CompetitorDetailRecord.product_identity_reference_ids",
            allow_empty=False,
        )
        product_intelligence = texts(
            self.product_intelligence_reference_ids,
            "CompetitorDetailRecord.product_intelligence_reference_ids",
            allow_empty=False,
        )
        canonical = texts(
            self.canonical_source_reference_ids,
            "CompetitorDetailRecord.canonical_source_reference_ids",
            allow_empty=False,
        )
        if not set(products) <= set(canonical):
            raise MarketReportV0_2ValidationError(
                "product identities must resolve through canonical source references"
            )

        fields = tuple(
            sorted(self.fields, key=lambda item: (item.field_group.value, item.field_name))
        )
        metrics = tuple(sorted(self.metrics, key=lambda item: item.metric_name))
        if any(not isinstance(item, EvidenceAwareFieldProjection) for item in fields):
            raise MarketReportV0_2ValidationError(
                "competitor detail contains an invalid field projection"
            )
        if any(not isinstance(item, MetricContextEnvelope) for item in metrics):
            raise MarketReportV0_2ValidationError(
                "competitor detail contains an invalid metric envelope"
            )
        if not fields and not metrics:
            raise MarketReportV0_2ValidationError(
                "competitor detail record requires fields or metrics"
            )
        if len({item.field_name for item in fields}) != len(fields):
            raise MarketReportV0_2ValidationError(
                "competitor detail contains duplicate field names"
            )
        if len({item.metric_name for item in metrics}) != len(metrics):
            raise MarketReportV0_2ValidationError(
                "competitor detail contains duplicate metric names"
            )
        for metric in metrics:
            if metric.marketplace != self.marketplace:
                raise MarketReportV0_2ValidationError(
                    "competitor detail metric marketplace mismatch"
                )
            if metric.product_grain_reference_id != self.scope_context_reference_id:
                raise MarketReportV0_2ValidationError(
                    "competitor detail metric grain/scope mismatch"
                )
            if metric.availability is not Availability.UNAVAILABLE and not (
                set(metric.subject_reference_ids) & set(products)
            ):
                raise MarketReportV0_2ValidationError(
                    "published competitor metric must reference the row product identity"
                )
            if metric.availability is not Availability.UNAVAILABLE and (
                metric.completeness
                in {CompletenessStatus.UNKNOWN, CompletenessStatus.UNRESOLVED}
            ):
                raise MarketReportV0_2ValidationError(
                    "published competitor metric completeness is incompatible"
                )

        represented = tuple(
            [item.availability for item in fields]
            + [item.availability for item in metrics]
        )
        expected_availability = self._expected_availability(represented)
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "competitor detail availability does not match fields/metrics"
            )
        references = normalize_references(
            self.references, "CompetitorDetailRecord.references"
        )
        referenced = {
            self.scope_context_reference_id,
            self.true_competitor_set_reference_id,
            self.disposition_reference_id,
            self.grain_entity_reference_id,
            *products,
            *product_intelligence,
            *canonical,
            *(value for field in fields for value in field.source_reference_ids),
            *(value for metric in metrics for value in metric.referenced_contract_ids()),
        }
        validate_registered_references(
            referenced, references, "CompetitorDetailRecord"
        )
        evidence = texts(self.evidence_ids, "CompetitorDetailRecord.evidence_ids")
        provenance = texts(
            self.provenance_reference_ids,
            "CompetitorDetailRecord.provenance_reference_ids",
            allow_empty=False,
        )
        limitations = texts(self.limitations, "CompetitorDetailRecord.limitations")
        child_evidence = {
            *(value for field in fields for value in field.evidence_ids),
            *(value for metric in metrics for value in metric.evidence_ids),
        }
        child_provenance = {
            *(value for field in fields for value in field.provenance_reference_ids),
            *(value for metric in metrics for value in metric.provenance_reference_ids),
            *(value for reference in references for value in reference.provenance_reference_ids),
        }
        if not child_evidence <= set(evidence):
            raise MarketReportV0_2ValidationError(
                "competitor detail omits field/metric evidence"
            )
        if not child_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "competitor detail omits field/metric/reference provenance"
            )
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable competitor detail requires limitations"
            )
        object.__setattr__(self, "product_identity_reference_ids", products)
        object.__setattr__(self, "product_intelligence_reference_ids", product_intelligence)
        object.__setattr__(self, "canonical_source_reference_ids", canonical)
        object.__setattr__(self, "fields", fields)
        object.__setattr__(self, "metrics", metrics)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "evidence_ids", evidence)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.record_id != identity(
            "market-report-v0.2-competitor-detail-record", self, "record_id"
        ):
            raise MarketReportV0_2ValidationError(
                "competitor detail record_id does not match content"
            )

    def _validate_purpose(self) -> None:
        if (
            self.purpose is CompetitorDetailPurpose.INCLUDED_COMPETITORS
            and self.disposition is not CompetitorDispositionType.INCLUDED
        ):
            raise MarketReportV0_2ValidationError(
                "included-competitor detail cannot promote another disposition"
            )
        if (
            self.purpose is CompetitorDetailPurpose.REVIEW_QUEUE
            and self.disposition is not CompetitorDispositionType.REVIEW_REQUIRED
        ):
            raise MarketReportV0_2ValidationError(
                "review-queue detail requires REVIEW_REQUIRED disposition"
            )

    @staticmethod
    def _expected_availability(values: tuple[Availability, ...]) -> Availability:
        states = set(values)
        if states == {Availability.AVAILABLE}:
            return Availability.AVAILABLE
        if states == {Availability.UNAVAILABLE}:
            return Availability.UNAVAILABLE
        return Availability.PARTIAL


@dataclass(frozen=True, slots=True, kw_only=True)
class CompetitorDetailSection(V0_2Contract):
    section_id: str
    contract_version: str
    availability: Availability
    purpose: CompetitorDetailPurpose
    scope_context_reference_id: str
    true_competitor_set_reference_id: str
    records: tuple[CompetitorDetailRecord, ...]
    references: tuple[ContractReference, ...]
    provenance_reference_ids: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != COMPETITOR_DETAIL_SECTION_CONTRACT_VERSION:
            raise MarketReportV0_2ValidationError(
                "unsupported competitor detail section version"
            )
        if not isinstance(self.availability, Availability):
            raise MarketReportV0_2ValidationError(
                "competitor detail section availability is invalid"
            )
        if not isinstance(self.purpose, CompetitorDetailPurpose):
            raise MarketReportV0_2ValidationError(
                "competitor detail section purpose is invalid"
            )
        text(
            self.scope_context_reference_id,
            "CompetitorDetailSection.scope_context_reference_id",
        )
        text(
            self.true_competitor_set_reference_id,
            "CompetitorDetailSection.true_competitor_set_reference_id",
        )
        records = tuple(
            sorted(self.records, key=lambda item: item.grain_entity_reference_id)
        )
        if any(not isinstance(item, CompetitorDetailRecord) for item in records):
            raise MarketReportV0_2ValidationError(
                "competitor detail section contains an invalid record"
            )
        if len({item.grain_entity_reference_id for item in records}) != len(records):
            raise MarketReportV0_2ValidationError(
                "duplicate competitor detail row for one grain entity"
            )
        for record in records:
            if record.purpose is not self.purpose:
                raise MarketReportV0_2ValidationError(
                    "competitor detail record purpose mismatch"
                )
            if (
                record.scope_context_reference_id != self.scope_context_reference_id
                or record.true_competitor_set_reference_id
                != self.true_competitor_set_reference_id
            ):
                raise MarketReportV0_2ValidationError(
                    "competitor detail record belongs to another scope or set"
                )
        expected_availability = (
            Availability.UNAVAILABLE
            if not records
            else CompetitorDetailRecord._expected_availability(
                tuple(item.availability for item in records)
            )
        )
        if self.availability is not expected_availability:
            raise MarketReportV0_2ValidationError(
                "competitor detail section availability does not match records"
            )
        references = normalize_references(
            self.references, "CompetitorDetailSection.references"
        )
        validate_registered_references(
            (
                self.scope_context_reference_id,
                self.true_competitor_set_reference_id,
            ),
            references,
            "CompetitorDetailSection",
        )
        registry = {item.reference_id: item for item in references}
        for record in records:
            for reference in record.references:
                if registry.get(reference.reference_id) != reference:
                    raise MarketReportV0_2ValidationError(
                        "competitor detail section omits or conflicts with record reference"
                    )
        provenance = texts(
            self.provenance_reference_ids,
            "CompetitorDetailSection.provenance_reference_ids",
            allow_empty=False,
        )
        required_provenance = {
            *(value for record in records for value in record.provenance_reference_ids),
            *(value for reference in references for value in reference.provenance_reference_ids),
        }
        if not required_provenance <= set(provenance):
            raise MarketReportV0_2ValidationError(
                "competitor detail section omits record/reference provenance"
            )
        limitations = texts(
            self.limitations, "CompetitorDetailSection.limitations"
        )
        if self.availability is not Availability.AVAILABLE and not limitations:
            raise MarketReportV0_2ValidationError(
                "partial/unavailable competitor detail section requires limitations"
            )
        object.__setattr__(self, "records", records)
        object.__setattr__(self, "references", references)
        object.__setattr__(self, "provenance_reference_ids", provenance)
        object.__setattr__(self, "limitations", limitations)
        if self.section_id != identity(
            "market-report-v0.2-competitor-detail-section", self, "section_id"
        ):
            raise MarketReportV0_2ValidationError(
                "competitor detail section_id does not match content"
            )


def build_field_projection(**content: Any) -> EvidenceAwareFieldProjection:
    normalized = dict(content)
    for name in (
        "source_reference_ids",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {"contract_version": COMPETITOR_FIELD_CONTRACT_VERSION, **normalized}
    return EvidenceAwareFieldProjection(
        field_id=deterministic_id(
            "market-report-v0.2-competitor-field", material
        ),
        **material,
    )


def build_competitor_detail_record(**content: Any) -> CompetitorDetailRecord:
    normalized = dict(content)
    if "fields" in normalized:
        normalized["fields"] = tuple(
            sorted(
                normalized["fields"],
                key=lambda item: (item.field_group.value, item.field_name),
            )
        )
    if "metrics" in normalized:
        normalized["metrics"] = tuple(
            sorted(normalized["metrics"], key=lambda item: item.metric_name)
        )
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    for name in (
        "product_identity_reference_ids",
        "product_intelligence_reference_ids",
        "canonical_source_reference_ids",
        "evidence_ids",
        "provenance_reference_ids",
        "limitations",
    ):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {
        "contract_version": COMPETITOR_DETAIL_RECORD_CONTRACT_VERSION,
        **normalized,
    }
    return CompetitorDetailRecord(
        record_id=deterministic_id(
            "market-report-v0.2-competitor-detail-record", material
        ),
        **material,
    )


def build_competitor_detail_section(**content: Any) -> CompetitorDetailSection:
    normalized = dict(content)
    if "records" in normalized:
        normalized["records"] = tuple(
            sorted(
                normalized["records"],
                key=lambda item: item.grain_entity_reference_id,
            )
        )
    if "references" in normalized:
        normalized["references"] = tuple(
            sorted(normalized["references"], key=lambda item: item.reference_id)
        )
    for name in ("provenance_reference_ids", "limitations"):
        if name in normalized:
            normalized[name] = tuple(sorted(normalized[name]))
    material = {
        "contract_version": COMPETITOR_DETAIL_SECTION_CONTRACT_VERSION,
        **normalized,
    }
    return CompetitorDetailSection(
        section_id=deterministic_id(
            "market-report-v0.2-competitor-detail-section", material
        ),
        **material,
    )


__all__ = (
    "CompetitorDetailPurpose",
    "CompetitorDetailRecord",
    "CompetitorDetailSection",
    "CompetitorFieldGroup",
    "EvidenceAwareFieldProjection",
    "build_competitor_detail_record",
    "build_competitor_detail_section",
    "build_field_projection",
)
