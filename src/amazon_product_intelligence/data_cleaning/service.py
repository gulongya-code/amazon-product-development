"""Thin Provider-neutral orchestration from Connector output to clean data."""

from __future__ import annotations

from typing import Iterable

from amazon_product_intelligence.connectors import (
    CapabilityStatus,
    ProviderCapability,
    ProviderConnectorError,
    ProviderErrorCode,
    ProviderRegistry,
    ProviderRequest,
)
from amazon_product_intelligence.contracts import (
    DataQualityIssue,
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
)
from amazon_product_intelligence.normalization import (
    CanonicalNormalizationPipeline,
    NormalizationContext,
    NormalizationInput,
)

from .models import (
    CleanCanonicalResult,
    CleanFieldResult,
    CleaningQualitySummary,
    CleaningRunStatus,
    DataCleaningRequest,
)


class DataCleaningService:
    """Orchestrate existing Provider, Canonical, normalization, and quality contracts."""

    def __init__(
        self,
        registry: ProviderRegistry,
        normalization: CanonicalNormalizationPipeline,
    ) -> None:
        self._registry = registry
        self._normalization = normalization

    def clean(self, request: DataCleaningRequest) -> CleanCanonicalResult:
        provider = self._registry.get(request.provider_id)
        configuration = self._registry.configuration(request.provider_id)
        capabilities = tuple(
            sorted(
                (
                    item
                    for item in provider.capabilities
                    if item.operation == request.operation
                    and item.capability_status in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
                ),
                key=lambda item: item.canonical_field,
            )
        )
        if not capabilities:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                "provider operation is not declared by its audited capability contract",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        driving = next(
            (
                item
                for item in capabilities
                if item.selector is not None and item.selector.observation_kind is not None
            ),
            capabilities[0],
        )
        fetched = provider.fetch(
            ProviderRequest(
                canonical_field=driving.canonical_field,
                parameters=request.parameters,
                marketplace=request.marketplace,
                locale=request.locale,
                retrieved_at=request.retrieved_at,
                transformed_at=request.transformed_at,
                collection_run_id=request.collection_run_id,
                currency=request.currency,
            ),
            configuration,
        )
        adaptation = fetched.adaptation
        normalization_context = NormalizationContext(
            normalization_run_id=request.normalization_run_id,
            normalized_at=request.normalized_at,
        )
        raw_reference = (
            adaptation.raw_evidence.raw_evidence_id
            if adaptation.raw_evidence is not None
            else None
        )
        fields: list[CleanFieldResult] = []
        for capability in capabilities:
            selector = capability.selector
            # Context-only capabilities (for example marketplace identity) do not
            # claim a field observation and must not synthesize one.
            if selector is None or (
                selector.observation_kind is None and not selector.canonical_names
            ):
                continue
            matches = tuple(
                observation
                for observation in adaptation.bundle.observations
                if selector.matches(observation)
            )
            if not matches:
                names = set(selector.canonical_names) | {capability.canonical_field.rsplit(".", 1)[-1]}
                related_issues = tuple(
                    issue
                    for issue in adaptation.bundle.quality_issues
                    if issue.dimension in names or issue.dimension == capability.canonical_field
                )
                fields.append(
                    self._absent_field(
                        capability,
                        request.operation,
                        raw_reference,
                        related_issues,
                    )
                )
                continue
            for observation in matches:
                normalized = self._normalization.normalize(
                    NormalizationInput.from_observation(
                        observation,
                        canonical_field=capability.canonical_field,
                        capability_status=capability.capability_status,
                    ),
                    normalization_context,
                )
                fields.append(
                    CleanFieldResult(
                        canonical_field=capability.canonical_field,
                        subject=observation.subject,
                        provider=capability.provider_id,
                        source_operation=request.operation,
                        source_field=observation.provenance.source_field,
                        capability_status=capability.capability_status,
                        observation_id=observation.observation_id,
                        raw_evidence_reference=observation.provenance.transformation.raw_evidence_reference,
                        raw_value=normalized.raw_value,
                        mapped_value=normalized.mapped_value,
                        normalized_value=normalized.normalized_value,
                        presence_status=normalized.presence_status,
                        normalization_status=normalized.normalization_status,
                        semantic_status=normalized.semantic_status,
                        unit=normalized.unit,
                        issues=normalized.issues,
                        application=normalized.application,
                        provenance=normalized.provenance,
                    )
                )

        ordered_fields = tuple(
            sorted(fields, key=lambda item: (item.canonical_field, item.observation_id or ""))
        )
        issues = self._unique_issues(
            (*adaptation.bundle.quality_issues, *(issue for field in ordered_fields for issue in field.issues))
        )
        summary = self._summarize(ordered_fields, len(issues))
        partial = any(
            (
                summary.fields_missing,
                summary.fields_explicit_null,
                summary.fields_unknown,
                summary.fields_query_returned_empty,
                summary.fields_invalid,
                summary.fields_partial,
                summary.quality_issue_count,
            )
        )
        runs = adaptation.bundle.transformation_runs
        return CleanCanonicalResult(
            run_id=request.normalization_run_id,
            provider=request.provider_id,
            operation=request.operation,
            retrieved_at=request.retrieved_at,
            status=(CleaningRunStatus.PARTIAL_SUCCESS if partial else CleaningRunStatus.SUCCESS),
            fields=ordered_fields,
            quality_summary=summary,
            issues=issues,
            diagnostics=tuple(item.to_dict() for item in adaptation.diagnostics),
            raw_evidence_references=tuple(sorted(adaptation.bundle.raw_evidence_references)),
            transformation_run_ids=tuple(sorted(item.transformation_run_id for item in runs)),
            mapping_versions=tuple(sorted({item.mapping_version for item in runs})),
            query_execution_ids=tuple(
                sorted(item.query_execution_id for item in adaptation.bundle.query_execution_records)
            ),
        )

    @staticmethod
    def _absent_field(
        capability: ProviderCapability,
        operation: str,
        raw_reference: str | None,
        issues: tuple[DataQualityIssue, ...],
    ) -> CleanFieldResult:
        invalid = bool(issues)
        return CleanFieldResult(
            canonical_field=capability.canonical_field,
            subject=None,
            provider=capability.provider_id,
            source_operation=operation,
            source_field=capability.source_field,
            capability_status=capability.capability_status,
            observation_id=None,
            raw_evidence_reference=raw_reference,
            raw_value=None,
            mapped_value=None,
            normalized_value=None,
            presence_status=PresenceStatus.UNKNOWN if invalid else PresenceStatus.MISSING,
            normalization_status=(
                NormalizationStatus.FAILED if invalid else NormalizationStatus.NOT_ATTEMPTED
            ),
            semantic_status=(
                SemanticStatus.INVALID if invalid else SemanticStatus.SEMANTICS_UNCONFIRMED
            ),
            unit=None,
            issues=issues,
            application=None,
            provenance=None,
        )

    @staticmethod
    def _unique_issues(issues: Iterable[DataQualityIssue]) -> tuple[DataQualityIssue, ...]:
        indexed = {issue.issue_id: issue for issue in issues}
        return tuple(indexed[key] for key in sorted(indexed))

    @staticmethod
    def _summarize(
        fields: tuple[CleanFieldResult, ...],
        issue_count: int,
    ) -> CleaningQualitySummary:
        observed = sum(item.presence_status is PresenceStatus.PRESENT for item in fields)
        changed = sum(
            item.normalization_status is NormalizationStatus.NORMALIZED
            and item.normalized_value != item.mapped_value
            for item in fields
        )
        unchanged = sum(
            item.presence_status is PresenceStatus.PRESENT
            and (
                (
                    item.normalization_status is NormalizationStatus.NORMALIZED
                    and item.normalized_value == item.mapped_value
                )
                or item.normalization_status is NormalizationStatus.NOT_APPLICABLE
            )
            for item in fields
        )
        return CleaningQualitySummary(
            fields_observed=observed,
            fields_normalized=changed,
            fields_unchanged=unchanged,
            fields_missing=sum(item.presence_status is PresenceStatus.MISSING for item in fields),
            fields_explicit_null=sum(
                item.presence_status is PresenceStatus.EXPLICIT_NULL for item in fields
            ),
            fields_unknown=sum(item.presence_status is PresenceStatus.UNKNOWN for item in fields),
            fields_query_returned_empty=sum(
                item.presence_status is PresenceStatus.QUERY_RETURNED_EMPTY for item in fields
            ),
            fields_not_applicable=sum(
                item.presence_status is PresenceStatus.NOT_APPLICABLE for item in fields
            ),
            fields_invalid=sum(
                item.semantic_status is SemanticStatus.INVALID
                or item.normalization_status is NormalizationStatus.FAILED
                for item in fields
            ),
            fields_partial=sum(
                item.capability_status is CapabilityStatus.PARTIAL
                or item.normalization_status is NormalizationStatus.AMBIGUOUS
                for item in fields
            ),
            quality_issue_count=issue_count,
        )


__all__ = ("DataCleaningService",)
