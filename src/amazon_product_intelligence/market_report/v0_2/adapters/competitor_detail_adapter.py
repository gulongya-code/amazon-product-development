"""Bounded projection from governed Product Intelligence and competitor inputs."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from amazon_product_intelligence.product_intelligence import (
    ProductIntelligenceSnapshotV0_1,
)

from ..models import (
    Availability,
    CompletenessStatus,
    CompetitorDetailPurpose,
    CompetitorDetailRecord,
    CompetitorDetailSection,
    ContractReference,
    EvidenceAwareFieldProjection,
    MarketReportV0_2ValidationError,
    MetricContextEnvelope,
    MetricValueType,
    PresenceStatus,
    ReferenceKind,
    ScopeContext,
    TrueCompetitorSetSection,
    build_competitor_detail_record,
    build_competitor_detail_section,
    build_reference,
    unavailable_metric,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class MetricCompatibilityBoundary:
    """Caller-supplied governed context used only for compatibility checks."""

    cohort_reference_id: str | None
    denominator_reference_id: str | None
    period_reference_id: str | None
    currency: str | None


class CompetitorDetailAdapter:
    """Project referenced source truth without extraction or field inference."""

    def project_record(
        self,
        *,
        scope_context: ScopeContext,
        scope_reference: ContractReference,
        true_competitor_set: TrueCompetitorSetSection,
        true_competitor_set_reference: ContractReference,
        purpose: CompetitorDetailPurpose,
        grain_entity_reference_id: str,
        product_intelligence_snapshot: ProductIntelligenceSnapshotV0_1,
        product_intelligence_reference: ContractReference,
        canonical_references: tuple[ContractReference, ...],
        fields: tuple[EvidenceAwareFieldProjection, ...],
        metrics: tuple[MetricContextEnvelope, ...],
        metric_boundaries: Mapping[str, MetricCompatibilityBoundary],
        references: tuple[ContractReference, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> CompetitorDetailRecord:
        if not isinstance(scope_context, ScopeContext):
            raise TypeError("scope_context must be ScopeContext")
        if not isinstance(true_competitor_set, TrueCompetitorSetSection):
            raise TypeError("true_competitor_set must be TrueCompetitorSetSection")
        if not isinstance(product_intelligence_snapshot, ProductIntelligenceSnapshotV0_1):
            raise TypeError(
                "product_intelligence_snapshot must be ProductIntelligenceSnapshotV0_1"
            )
        if scope_reference.target_id != scope_context.scope_context_id:
            raise MarketReportV0_2ValidationError(
                "scope reference target does not match ScopeContext"
            )
        if true_competitor_set_reference.target_id != true_competitor_set.set_id:
            raise MarketReportV0_2ValidationError(
                "True Competitor reference target does not match supplied set"
            )
        if true_competitor_set.scope_context_reference_id != scope_reference.reference_id:
            raise MarketReportV0_2ValidationError(
                "True Competitor Set belongs to another scope"
            )
        dispositions = tuple(
            item
            for item in true_competitor_set.dispositions
            if item.grain_entity_reference_id == grain_entity_reference_id
        )
        if len(dispositions) != 1:
            raise MarketReportV0_2ValidationError(
                "competitor detail grain entity does not resolve to exactly one disposition"
            )
        disposition = dispositions[0]
        canonical_ids = {item.reference_id for item in canonical_references}
        if not canonical_references or any(
            item.kind is not ReferenceKind.EXTERNAL_PROVENANCE
            or not item.namespace.startswith("canonical")
            for item in canonical_references
        ):
            raise MarketReportV0_2ValidationError(
                "competitor detail requires external canonical source references"
            )
        if not set(disposition.product_reference_ids) <= canonical_ids:
            raise MarketReportV0_2ValidationError(
                "competitor detail canonical references do not cover disposition products"
            )
        product_intelligence_snapshot.validate()
        if (
            product_intelligence_reference.kind is not ReferenceKind.EXTERNAL_PROVENANCE
            or product_intelligence_reference.namespace != "product-intelligence"
        ):
            raise MarketReportV0_2ValidationError(
                "competitor detail requires an external Product Intelligence reference"
            )
        if (
            product_intelligence_reference.target_id
            != product_intelligence_snapshot.snapshot_id
            or product_intelligence_reference.target_version
            != product_intelligence_snapshot.ruleset_version
        ):
            raise MarketReportV0_2ValidationError(
                "Product Intelligence reference does not match supplied snapshot"
            )
        canonical_targets = {item.target_id for item in canonical_references}
        if product_intelligence_snapshot.target_product_identity.product_id not in canonical_targets:
            raise MarketReportV0_2ValidationError(
                "Product Intelligence target is not a canonical row product"
            )
        if any(not isinstance(item, EvidenceAwareFieldProjection) for item in fields):
            raise TypeError("fields must be EvidenceAwareFieldProjection records")
        if any(not isinstance(item, MetricContextEnvelope) for item in metrics):
            raise TypeError("metrics must be MetricContextEnvelope records")
        metric_names = {item.metric_name for item in metrics}
        if metric_names != set(metric_boundaries):
            raise MarketReportV0_2ValidationError(
                "every competitor metric requires one explicit compatibility boundary"
            )
        if any(
            not isinstance(item, MetricCompatibilityBoundary)
            for item in metric_boundaries.values()
        ):
            raise TypeError("metric boundaries contain an invalid record")

        projected_metrics = []
        projection_limitations = set(limitations)
        for source in metrics:
            boundary = metric_boundaries[source.metric_name]
            reason = self._incompatibility_reason(
                source=source,
                scope_reference_id=scope_reference.reference_id,
                marketplace=scope_context.marketplace,
                product_reference_ids=disposition.product_reference_ids,
                boundary=boundary,
            )
            if reason is None:
                projected = source
            else:
                limitation = f"{source.metric_name}: {reason}"
                projection_limitations.add(limitation)
                projected = unavailable_metric(
                    metric_name=source.metric_name,
                    value_type=source.value_type,
                    marketplace=scope_context.marketplace,
                    product_grain_reference_id=scope_reference.reference_id,
                    provenance_reference_ids=source.provenance_reference_ids,
                    limitations=(limitation,),
                    presence_status=(
                        source.presence_status
                        if source.presence_status is not PresenceStatus.PRESENT
                        else PresenceStatus.UNKNOWN
                    ),
                    evidence_ids=source.evidence_ids,
                    unit=source.unit,
                    currency_code=(
                        boundary.currency
                        if source.value_type is MetricValueType.MONEY
                        else None
                    ),
                    period_reference_id=boundary.period_reference_id,
                    subject_reference_ids=disposition.product_reference_ids,
                    cohort_reference_id=boundary.cohort_reference_id,
                    denominator_reference_id=boundary.denominator_reference_id,
                )
            projected_metrics.append(projected)
            projection_limitations.update(projected.limitations)

        disposition_reference = build_reference(
            kind=ReferenceKind.REPORT_LOCAL,
            namespace="market-report-v0.2.true-competitor-disposition",
            target_id=disposition.disposition_id,
            target_version=true_competitor_set.contract_version,
        )
        registry_items = [
            *references,
            *scope_context.references,
            *true_competitor_set.references,
            scope_reference,
            true_competitor_set_reference,
            disposition_reference,
            product_intelligence_reference,
            *canonical_references,
        ]
        registry = tuple(
            {item.reference_id: item for item in registry_items}.values()
        )
        evidence = tuple(
            sorted(
                {
                    *(value for item in fields for value in item.evidence_ids),
                    *(value for item in projected_metrics for value in item.evidence_ids),
                }
            )
        )
        provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *scope_context.provenance_reference_ids,
                    *true_competitor_set.provenance_reference_ids,
                    *(value for item in fields for value in item.provenance_reference_ids),
                    *(value for item in projected_metrics for value in item.provenance_reference_ids),
                    *(value for item in registry for value in item.provenance_reference_ids),
                }
            )
        )
        projection_limitations.update(
            value for item in fields for value in item.limitations
        )
        represented = tuple(
            [item.availability for item in fields]
            + [item.availability for item in projected_metrics]
        )
        availability = CompetitorDetailRecord._expected_availability(represented)
        return build_competitor_detail_record(
            purpose=purpose,
            availability=availability,
            marketplace=scope_context.marketplace,
            scope_context_reference_id=scope_reference.reference_id,
            true_competitor_set_reference_id=true_competitor_set_reference.reference_id,
            disposition_reference_id=disposition_reference.reference_id,
            disposition=disposition.disposition,
            grain_entity_reference_id=disposition.grain_entity_reference_id,
            product_identity_reference_ids=disposition.product_reference_ids,
            product_intelligence_reference_ids=(
                product_intelligence_reference.reference_id,
            ),
            canonical_source_reference_ids=tuple(
                sorted(item.reference_id for item in canonical_references)
            ),
            fields=fields,
            metrics=tuple(projected_metrics),
            references=registry,
            evidence_ids=evidence,
            provenance_reference_ids=provenance,
            limitations=tuple(sorted(projection_limitations)),
        )

    def compose_section(
        self,
        *,
        purpose: CompetitorDetailPurpose,
        scope_reference: ContractReference,
        true_competitor_set_reference: ContractReference,
        records: tuple[CompetitorDetailRecord, ...],
        provenance_reference_ids: tuple[str, ...],
        limitations: tuple[str, ...] = (),
    ) -> CompetitorDetailSection:
        if any(not isinstance(item, CompetitorDetailRecord) for item in records):
            raise TypeError("records must be CompetitorDetailRecord values")
        states = {item.availability for item in records}
        availability = (
            Availability.UNAVAILABLE
            if not records
            else Availability.AVAILABLE
            if states == {Availability.AVAILABLE}
            else Availability.UNAVAILABLE
            if states == {Availability.UNAVAILABLE}
            else Availability.PARTIAL
        )
        registry = tuple(
            {
                item.reference_id: item
                for item in (
                    scope_reference,
                    true_competitor_set_reference,
                    *(reference for record in records for reference in record.references),
                )
            }.values()
        )
        provenance = tuple(
            sorted(
                {
                    *provenance_reference_ids,
                    *(value for record in records for value in record.provenance_reference_ids),
                    *(value for item in registry for value in item.provenance_reference_ids),
                }
            )
        )
        combined_limitations = tuple(
            sorted(
                {
                    *limitations,
                    *(value for record in records for value in record.limitations),
                }
            )
        )
        return build_competitor_detail_section(
            availability=availability,
            purpose=purpose,
            scope_context_reference_id=scope_reference.reference_id,
            true_competitor_set_reference_id=true_competitor_set_reference.reference_id,
            records=records,
            references=registry,
            provenance_reference_ids=provenance,
            limitations=combined_limitations,
        )

    @staticmethod
    def _incompatibility_reason(
        *,
        source: MetricContextEnvelope,
        scope_reference_id: str,
        marketplace: str,
        product_reference_ids: tuple[str, ...],
        boundary: MetricCompatibilityBoundary,
    ) -> str | None:
        if source.marketplace != marketplace:
            return "metric marketplace is incompatible"
        if source.product_grain_reference_id != scope_reference_id:
            return "metric product grain is incompatible"
        if source.cohort_reference_id != boundary.cohort_reference_id:
            return "metric cohort is incompatible"
        if source.denominator_reference_id != boundary.denominator_reference_id:
            return "metric denominator is incompatible"
        if source.period_reference_id != boundary.period_reference_id:
            return "metric period/window is incompatible"
        if source.value_type is MetricValueType.MONEY and source.currency != boundary.currency:
            return "metric currency is incompatible"
        if source.availability is not Availability.UNAVAILABLE and not (
            set(source.subject_reference_ids) & set(product_reference_ids)
        ):
            return "metric subject does not resolve to the competitor row"
        if source.availability is not Availability.UNAVAILABLE and (
            source.method_policy_id is None or source.method_policy_version is None
        ):
            return "metric lacks a governed method policy"
        if source.availability is not Availability.UNAVAILABLE and (
            source.completeness
            in {CompletenessStatus.UNKNOWN, CompletenessStatus.UNRESOLVED}
        ):
            return "metric completeness is incompatible"
        return None


__all__ = ("CompetitorDetailAdapter", "MetricCompatibilityBoundary")
