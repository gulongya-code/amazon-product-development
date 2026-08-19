"""Deterministic Clean Canonical Data to Market Analysis V1 builder."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
from typing import Any, Iterable

from amazon_product_intelligence.calculations import (
    CalculationContext,
    CalculationCurrencyMismatchError,
    CalculationEngine,
    CalculationInput,
    CalculationInputLineage,
    CalculationProvenance,
    CalculationStatus,
    CalculationUnitMismatchError,
    InputResolutionStatus,
    build_audited_registry,
    decimal_value,
    json_value,
    require_compatible_currencies,
    require_compatible_units,
)
from amazon_product_intelligence.connectors import CapabilityStatus
from amazon_product_intelligence.contracts import (
    DataQualityIssue,
    NormalizationStatus,
    PresenceStatus,
    Provenance,
    SemanticStatus,
    SubjectType,
    Unit,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.data_cleaning import (
    CleanCanonicalResult,
    CleanFieldResult,
    CleaningRunStatus,
)

from .errors import MarketAnalysisValidationError
from .models import (
    MARKET_ANALYSIS_VERSION,
    BlockedMarketMetric,
    MarketAnalysisQualitySummary,
    MarketAnalysisRequest,
    MarketAnalysisResult,
    MarketAnalysisScope,
    MarketAnalysisStatus,
    MarketMetricStatus,
    NumericDistribution,
    NumericMetricSummary,
)


_CALCULATION_PRECISION = 28
_SUMMARY_VERSION = "v0.1-observed-summary"
_OBSERVED_PRODUCT_COUNT = "workbook.market_overview.observed_product_count"
_PRODUCT_IDENTITY_INPUT = "canonical.snapshot_product_identities"


@dataclass(frozen=True, slots=True)
class _NumericSpec:
    metric_id: str
    canonical_field: str
    subject_type: SubjectType
    monetary: bool = False


_NUMERIC_SPECS = (
    _NumericSpec(
        "market_analysis.observed_product_price",
        "metric.price",
        SubjectType.PRODUCT,
        monetary=True,
    ),
    _NumericSpec(
        "market_analysis.product_rating",
        "metric.rating",
        SubjectType.PRODUCT,
    ),
    _NumericSpec(
        "market_analysis.product_review_count",
        "metric.review_count",
        SubjectType.PRODUCT,
    ),
    _NumericSpec(
        "market_analysis.keyword_search_volume",
        "keyword.search_volume",
        SubjectType.KEYWORD,
    ),
    _NumericSpec(
        "market_analysis.keyword_cpc",
        "keyword.cpc",
        SubjectType.KEYWORD,
        monetary=True,
    ),
    _NumericSpec(
        "market_analysis.keyword_aba_rank",
        "keyword.aba_rank",
        SubjectType.KEYWORD,
    ),
)


def _fingerprint(value: Any) -> str:
    payload = json.dumps(
        json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(payload.encode("utf-8")).hexdigest()


def _canonical_decimal(value: Decimal) -> Decimal:
    if value == 0:
        return Decimal(0)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return Decimal(text)


def _distribution(values: tuple[Decimal, ...]) -> NumericDistribution:
    ordered = tuple(sorted(values))
    with localcontext(Context(prec=_CALCULATION_PRECISION, rounding=ROUND_HALF_EVEN)):
        mean = sum(ordered, Decimal(0)) / Decimal(len(ordered))
        middle = len(ordered) // 2
        median = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / Decimal(2)
        )
    return NumericDistribution(
        minimum=_canonical_decimal(ordered[0]),
        maximum=_canonical_decimal(ordered[-1]),
        mean=_canonical_decimal(mean),
        median=_canonical_decimal(median),
    )


def _unique_provenances(fields: Iterable[CleanFieldResult]) -> tuple[Provenance, ...]:
    indexed: dict[str, Provenance] = {}
    for field in fields:
        if field.provenance is not None:
            indexed[canonical_json(field.provenance)] = field.provenance
    return tuple(indexed[key] for key in sorted(indexed))


def _evidence_references(fields: Iterable[CleanFieldResult]) -> tuple[str, ...]:
    values: set[str] = set()
    for field in fields:
        if field.observation_id:
            values.add(field.observation_id)
        if field.raw_evidence_reference:
            values.add(field.raw_evidence_reference)
    return tuple(sorted(values))


def _related_issue(issue: DataQualityIssue, canonical_field: str) -> bool:
    leaf = canonical_field.rsplit(".", 1)[-1]
    return issue.dimension in {canonical_field, leaf}


class MarketAnalysisBuilderV0_1:
    """Build deterministic, quality-aware market statistics from clean results."""

    def __init__(self, calculation_engine: CalculationEngine | None = None) -> None:
        self._calculation_engine = calculation_engine or CalculationEngine(
            build_audited_registry()
        )

    def build(self, request: MarketAnalysisRequest) -> MarketAnalysisResult:
        if not isinstance(request, MarketAnalysisRequest):
            raise TypeError("request must be MarketAnalysisRequest")
        fields = tuple(
            field
            for result in request.clean_results
            for field in result.fields
        )
        issues = self._issues(request.clean_results)
        self._validate_marketplace(request.marketplace, fields, issues)
        product_ids = self._subject_ids(fields, issues, SubjectType.PRODUCT)
        keyword_ids = self._subject_ids(fields, issues, SubjectType.KEYWORD)
        providers = tuple(
            sorted(
                {
                    *(result.provider for result in request.clean_results),
                    *(
                        field.provenance.provider
                        for field in fields
                        if field.provenance is not None
                    ),
                }
            )
        )
        snapshot_at = (
            max(result.retrieved_at for result in request.clean_results)
            if request.clean_results
            else None
        )
        scope_material = {
            "marketplace": request.marketplace,
            "snapshot_at": snapshot_at,
            "clean_run_ids": [result.run_id for result in request.clean_results],
            "product_ids": list(product_ids),
            "keyword_ids": list(keyword_ids),
            "providers": list(providers),
        }
        scope = MarketAnalysisScope(
            scope_id=deterministic_id("market-analysis-scope", scope_material),
            marketplace=request.marketplace,
            snapshot_at=snapshot_at,
            clean_run_ids=tuple(scope_material["clean_run_ids"]),
            product_ids=product_ids,
            keyword_ids=keyword_ids,
            providers=providers,
        )
        calculation_run_id = deterministic_id(
            "market-analysis-calculation",
            {"scope_id": scope.scope_id, "analysis_version": MARKET_ANALYSIS_VERSION},
        )
        count_metrics = tuple(
            sorted(
                self._count_metrics(product_ids, fields, calculation_run_id),
                key=lambda item: item.field_id,
            )
        )
        summaries = tuple(
            sorted(
                (
                    self._numeric_summary(
                        spec,
                        request.clean_results,
                        fields,
                        issues,
                        product_ids
                        if spec.subject_type is SubjectType.PRODUCT
                        else keyword_ids,
                        calculation_run_id,
                    )
                    for spec in _NUMERIC_SPECS
                ),
                key=lambda item: item.metric_id,
            )
        )
        quality = self._quality(request.clean_results, product_ids, keyword_ids, issues)
        status = self._status(request, count_metrics, summaries, product_ids, keyword_ids)
        blocked = tuple(
            sorted(self._blocked_metrics(), key=lambda item: item.metric_id)
        )
        identity_material = {
            "analysis_version": MARKET_ANALYSIS_VERSION,
            "status": status.value,
            "calculation_run_id": calculation_run_id,
            "scope": scope.to_dict(),
            "count_metrics": [item.to_dict() for item in count_metrics],
            "numeric_summaries": [item.to_dict() for item in summaries],
            "quality": quality.to_dict(),
            "source_quality_issues": [item.to_dict() for item in issues],
            "blocked_metrics": [item.to_dict() for item in blocked],
        }
        return MarketAnalysisResult(
            analysis_id=deterministic_id("market-analysis", identity_material),
            analysis_version=MARKET_ANALYSIS_VERSION,
            status=status,
            calculation_run_id=calculation_run_id,
            scope=scope,
            count_metrics=count_metrics,
            numeric_summaries=summaries,
            quality=quality,
            source_quality_issues=issues,
            blocked_metrics=blocked,
        )

    @staticmethod
    def _issues(results: tuple[CleanCanonicalResult, ...]) -> tuple[DataQualityIssue, ...]:
        indexed = {
            issue.issue_id: issue
            for result in results
            for issue in result.issues
        }
        return tuple(indexed[key] for key in sorted(indexed))

    @staticmethod
    def _validate_marketplace(
        marketplace: str,
        fields: tuple[CleanFieldResult, ...],
        issues: tuple[DataQualityIssue, ...],
    ) -> None:
        mismatches = {
            subject.marketplace
            for subject in (
                *(field.subject for field in fields if field.subject is not None),
                *(issue.subject for issue in issues),
            )
            if subject.marketplace != marketplace
        }
        if mismatches:
            raise MarketAnalysisValidationError(
                "all Canonical subjects must match the requested marketplace"
            )

    @staticmethod
    def _subject_ids(
        fields: tuple[CleanFieldResult, ...],
        issues: tuple[DataQualityIssue, ...],
        subject_type: SubjectType,
    ) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    *(field.subject.subject_id for field in fields if field.subject is not None and field.subject.subject_type is subject_type),
                    *(issue.subject.subject_id for issue in issues if issue.subject.subject_type is subject_type),
                }
            )
        )

    def _count_metrics(
        self,
        product_ids: tuple[str, ...],
        fields: tuple[CleanFieldResult, ...],
        calculation_run_id: str,
    ) -> tuple[Any, ...]:
        product_fields = tuple(
            field
            for field in fields
            if field.subject is not None
            and field.subject.subject_type is SubjectType.PRODUCT
            and field.subject.subject_id in product_ids
            and field.provenance is not None
        )
        inputs: dict[str, CalculationInput] = {}
        provenances = _unique_provenances(product_fields)
        references = _evidence_references(product_fields)
        if product_ids and provenances and references:
            inputs[_PRODUCT_IDENTITY_INPUT] = CalculationInput(
                field_id=_PRODUCT_IDENTITY_INPUT,
                value=product_ids,
                presence_status=PresenceStatus.PRESENT,
                normalization_status=NormalizationStatus.NORMALIZED,
                semantic_status=SemanticStatus.CONFIRMED,
                unit=None,
                resolution_status=InputResolutionStatus.RESOLVED,
                evidence_references=references,
                provenances=provenances,
                quality_issues=(),
            )
        batch = self._calculation_engine.calculate(
            (_OBSERVED_PRODUCT_COUNT,),
            inputs,
            CalculationContext(
                calculation_run_id=calculation_run_id,
                configuration_version=MARKET_ANALYSIS_VERSION,
            ),
        )
        return batch.results

    def _numeric_summary(
        self,
        spec: _NumericSpec,
        results: tuple[CleanCanonicalResult, ...],
        fields: tuple[CleanFieldResult, ...],
        issues: tuple[DataQualityIssue, ...],
        subject_ids: tuple[str, ...],
        calculation_run_id: str,
    ) -> NumericMetricSummary:
        del results
        relevant_fields = tuple(
            field
            for field in fields
            if field.canonical_field == spec.canonical_field
            and field.subject is not None
            and field.subject.subject_type is spec.subject_type
            and field.subject.subject_id in subject_ids
        )
        relevant_issues = tuple(
            issue
            for issue in issues
            if issue.subject.subject_type is spec.subject_type
            and issue.subject.subject_id in subject_ids
            and _related_issue(issue, spec.canonical_field)
        )
        fields_by_subject: dict[str, list[CleanFieldResult]] = {
            subject_id: [] for subject_id in subject_ids
        }
        for field in relevant_fields:
            fields_by_subject[field.subject.subject_id].append(field)  # type: ignore[union-attr]
        issues_by_subject: dict[str, list[DataQualityIssue]] = {
            subject_id: [] for subject_id in subject_ids
        }
        for issue in relevant_issues:
            issues_by_subject[issue.subject.subject_id].append(issue)

        selected: list[tuple[CleanFieldResult, Decimal]] = []
        missing = explicit_null = unknown = invalid = conflicts = partial = 0
        for subject_id in subject_ids:
            candidates: list[tuple[CleanFieldResult, Decimal]] = []
            issue_invalid = any(issue.blocking for issue in issues_by_subject[subject_id])
            field_invalid = False
            subject_unknown = False
            subject_explicit_null = False
            subject_missing = False
            for field in fields_by_subject[subject_id]:
                if (
                    field.presence_status is PresenceStatus.PRESENT
                    and field.semantic_status is SemanticStatus.CONFIRMED
                    and field.normalization_status
                    in {NormalizationStatus.NORMALIZED, NormalizationStatus.NOT_APPLICABLE}
                    and field.normalized_value is not None
                    and not any(issue.blocking for issue in field.issues)
                ):
                    try:
                        candidates.append((field, decimal_value(field.normalized_value)))
                    except Exception:
                        field_invalid = True
                elif (
                    field.semantic_status is SemanticStatus.INVALID
                    or field.normalization_status is NormalizationStatus.FAILED
                    or any(issue.blocking for issue in field.issues)
                ):
                    field_invalid = True
                elif field.presence_status is PresenceStatus.EXPLICIT_NULL:
                    subject_explicit_null = True
                elif field.presence_status is PresenceStatus.UNKNOWN:
                    subject_unknown = True
                else:
                    subject_missing = True

            if len(candidates) > 1 or (candidates and field_invalid):
                conflicts += 1
            elif issue_invalid:
                invalid += 1
            elif len(candidates) == 1:
                field, value = candidates[0]
                selected.append((field, value))
                if field.capability_status is CapabilityStatus.PARTIAL:
                    partial += 1
            elif field_invalid:
                invalid += 1
            elif subject_unknown:
                unknown += 1
            elif subject_explicit_null:
                explicit_null += 1
            elif subject_missing or not fields_by_subject[subject_id]:
                missing += 1

        limitations: set[str] = set()
        if missing:
            limitations.add("MISSING_INPUTS_EXCLUDED")
        if explicit_null:
            limitations.add("EXPLICIT_NULL_INPUTS_EXCLUDED")
        if unknown:
            limitations.add("UNKNOWN_INPUTS_EXCLUDED")
        if invalid:
            limitations.add("INVALID_INPUTS_EXCLUDED")
        if conflicts:
            limitations.add("MULTIPLE_CANDIDATES_BLOCKED")
        if partial:
            limitations.add("PARTIAL_INPUTS_INCLUDED")

        unit: Unit | None = None
        unit_mismatch = 0
        if selected:
            try:
                units = tuple(field.unit for field, _ in selected)
                if any(item is None for item in units):
                    raise CalculationUnitMismatchError("numeric summary requires explicit units")
                unit = (
                    require_compatible_currencies(units)
                    if spec.monetary
                    else require_compatible_units(units)
                )
            except (CalculationCurrencyMismatchError, CalculationUnitMismatchError):
                unit_mismatch = len(selected)
                limitations.add("UNIT_OR_CURRENCY_MISMATCH")

        if conflicts or unit_mismatch:
            status = MarketMetricStatus.BLOCKED
            distribution = None
            provenance = None
            source_observation_ids: tuple[str, ...] = ()
            valid_sample_count = 0
        elif not selected:
            status = (
                MarketMetricStatus.BLOCKED
                if invalid or unknown
                else MarketMetricStatus.MISSING
            )
            distribution = None
            provenance = None
            source_observation_ids = ()
            valid_sample_count = 0
        else:
            if len(selected) < 2:
                limitations.add("SMALL_SAMPLE_SIZE_LT_2")
            status = (
                MarketMetricStatus.PARTIAL
                if limitations
                else MarketMetricStatus.CALCULATED
            )
            values = tuple(value for _, value in selected)
            distribution = _distribution(values)
            selected_fields = tuple(
                field
                for field, _ in sorted(
                    selected,
                    key=lambda item: item[0].observation_id or "",
                )
            )
            source_observation_ids = tuple(
                sorted(
                    field.observation_id
                    for field in selected_fields
                    if field.observation_id is not None
                )
            )
            provenance = self._summary_provenance(
                spec,
                selected_fields,
                distribution,
                unit,
                calculation_run_id,
            )
            valid_sample_count = len(selected_fields)

        return NumericMetricSummary(
            metric_id=spec.metric_id,
            source_canonical_field=spec.canonical_field,
            status=status,
            distribution=distribution,
            unit=unit if status in {MarketMetricStatus.CALCULATED, MarketMetricStatus.PARTIAL} else None,
            total_subject_count=len(subject_ids),
            valid_sample_count=valid_sample_count,
            excluded_missing_count=missing,
            excluded_explicit_null_count=explicit_null,
            excluded_unknown_count=unknown,
            excluded_invalid_count=invalid,
            excluded_conflict_count=conflicts,
            excluded_unit_mismatch_count=unit_mismatch,
            partial_input_count=partial,
            source_observation_ids=source_observation_ids,
            quality_issue_ids=tuple(sorted(issue.issue_id for issue in relevant_issues)),
            limitations=tuple(sorted(limitations)),
            provenance=provenance,
        )

    @staticmethod
    def _summary_provenance(
        spec: _NumericSpec,
        fields: tuple[CleanFieldResult, ...],
        distribution: NumericDistribution,
        unit: Unit | None,
        calculation_run_id: str,
    ) -> CalculationProvenance:
        lineage = tuple(
            CalculationInputLineage(
                field_id=field.canonical_field,
                normalized_value=field.normalized_value,
                presence_status=field.presence_status,
                normalization_status=field.normalization_status,
                semantic_status=field.semantic_status,
                resolution_status=InputResolutionStatus.RESOLVED,
                unit=field.unit,
                evidence_references=tuple(
                    sorted(
                        {
                            item
                            for item in (
                                field.observation_id,
                                field.raw_evidence_reference,
                            )
                            if item is not None
                        }
                    )
                ),
                provenances=(field.provenance,) if field.provenance is not None else (),
                quality_issue_ids=tuple(issue.issue_id for issue in field.issues),
                input_fingerprint=_fingerprint(field.to_dict()),
            )
            for field in fields
        )
        input_material = [item.to_dict() for item in lineage]
        output_material = {
            "metric_id": spec.metric_id,
            "distribution": distribution.to_dict(),
            "unit": None if unit is None else unit.to_dict(),
            "valid_sample_count": len(fields),
        }
        return CalculationProvenance(
            calculation_rule_id=spec.metric_id,
            calculation_version=_SUMMARY_VERSION,
            calculation_run_id=calculation_run_id,
            configuration_version=MARKET_ANALYSIS_VERSION,
            input_lineage=lineage,
            calculated_dependency_result_ids=(),
            input_fingerprint=_fingerprint(input_material),
            output_fingerprint=_fingerprint(output_material),
        )

    @staticmethod
    def _quality(
        results: tuple[CleanCanonicalResult, ...],
        product_ids: tuple[str, ...],
        keyword_ids: tuple[str, ...],
        issues: tuple[DataQualityIssue, ...],
    ) -> MarketAnalysisQualitySummary:
        limitations: set[str] = set()
        if not results:
            limitations.add("NO_CLEAN_RESULTS")
        if any(result.status is CleaningRunStatus.PARTIAL_SUCCESS for result in results):
            limitations.add("PARTIAL_CLEAN_RUNS")
        if issues:
            limitations.add("SOURCE_QUALITY_ISSUES")
        if results and not product_ids and not keyword_ids:
            limitations.add("NO_CANONICAL_SUBJECT_IDENTITIES")
        if 0 < len(product_ids) < 2:
            limitations.add("SMALL_OBSERVED_PRODUCT_SAMPLE")
        return MarketAnalysisQualitySummary(
            clean_run_count=len(results),
            successful_clean_run_count=sum(
                result.status is CleaningRunStatus.SUCCESS for result in results
            ),
            partial_clean_run_count=sum(
                result.status is CleaningRunStatus.PARTIAL_SUCCESS for result in results
            ),
            source_field_count=sum(len(result.fields) for result in results),
            fields_observed=sum(result.quality_summary.fields_observed for result in results),
            fields_missing=sum(result.quality_summary.fields_missing for result in results),
            fields_explicit_null=sum(
                result.quality_summary.fields_explicit_null for result in results
            ),
            fields_unknown=sum(result.quality_summary.fields_unknown for result in results),
            fields_invalid=sum(result.quality_summary.fields_invalid for result in results),
            fields_partial=sum(result.quality_summary.fields_partial for result in results),
            quality_issue_count=len(issues),
            product_subject_count=len(product_ids),
            keyword_subject_count=len(keyword_ids),
            limitations=tuple(sorted(limitations)),
        )

    @staticmethod
    def _status(
        request: MarketAnalysisRequest,
        count_metrics: tuple[Any, ...],
        summaries: tuple[NumericMetricSummary, ...],
        product_ids: tuple[str, ...],
        keyword_ids: tuple[str, ...],
    ) -> MarketAnalysisStatus:
        if not request.clean_results:
            return MarketAnalysisStatus.EMPTY
        relevant = tuple(
            summary
            for summary in summaries
            if (
                summary.source_canonical_field.startswith("metric.") and product_ids
            )
            or (
                summary.source_canonical_field.startswith("keyword.") and keyword_ids
            )
        )
        if (
            any(result.status is not CleaningRunStatus.SUCCESS for result in request.clean_results)
            or not (product_ids or keyword_ids)
            or (product_ids and count_metrics[0].status is not CalculationStatus.CALCULATED)
            or any(summary.status is not MarketMetricStatus.CALCULATED for summary in relevant)
        ):
            return MarketAnalysisStatus.PARTIAL
        return MarketAnalysisStatus.COMPLETE

    @staticmethod
    def _blocked_metrics() -> tuple[BlockedMarketMetric, ...]:
        definitions = (
            (
                "workbook.product_structure.product_count",
                "EXACT_PRODUCT_TYPE_GROUP_UNAVAILABLE",
                "No approved exact product-type group membership is present in CleanCanonicalResult.",
                ("canonical.group_product_identities",),
            ),
            (
                "workbook.product_structure.member_product_ids",
                "EXACT_PRODUCT_TYPE_GROUP_UNAVAILABLE",
                "Member IDs require an approved exact product-type group and are not inferred from the analysis scope.",
                ("canonical.group_product_identities",),
            ),
            (
                "workbook.product_structure.observed_share",
                "EXACT_PRODUCT_TYPE_GROUP_UNAVAILABLE",
                "Observed Share requires an approved exact group contained in the explicit observed snapshot.",
                (
                    "canonical.group_product_identities",
                    "canonical.snapshot_product_identities",
                ),
            ),
            (
                "workbook.product_structure.minimum_comparable_price",
                "BLOCKED_BY_MEMBERSHIP_SOURCE",
                "Comparable price requires governed Comparable Product membership; observed prices are not comparable membership.",
                ("canonical.comparable_price_observations",),
            ),
            (
                "workbook.product_structure.maximum_comparable_price",
                "BLOCKED_BY_MEMBERSHIP_SOURCE",
                "Comparable price requires governed Comparable Product membership; observed prices are not comparable membership.",
                ("canonical.comparable_price_observations",),
            ),
            (
                "workbook.competition_evidence.variation_evidence_count",
                "SEMANTIC_AMBIGUITY",
                "Variation edges and competition variation-evidence records do not define one approved counting grain.",
                ("canonical.variation_evidence_records",),
            ),
            (
                "workbook.market_overview.evidence_backed_trend",
                "FORMULA_UNSPECIFIED",
                "No approved trend window, direction, threshold, or tie policy exists.",
                ("canonical.dated_trend_observations",),
            ),
            (
                "market_analysis.keyword_difficulty_summary",
                "PROVIDER_SCALE_UNCONFIRMED",
                "Keyword difficulty cannot be aggregated until the provider scale and method are confirmed.",
                ("keyword.difficulty",),
            ),
            (
                "market_analysis.product_bsr_summary",
                "RANK_CONTEXT_COMPATIBILITY_UNRESOLVED",
                "BSR values cannot be aggregated across unverified category and rank contexts.",
                ("metric.bsr",),
            ),
        )
        return tuple(
            BlockedMarketMetric(
                metric_id=metric_id,
                reason_code=reason,
                message=message,
                dependencies=tuple(sorted(dependencies)),
            )
            for metric_id, reason, message, dependencies in definitions
        )


__all__ = ("MarketAnalysisBuilderV0_1",)
