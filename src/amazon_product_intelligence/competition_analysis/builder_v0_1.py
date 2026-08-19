"""Deterministic Clean Canonical Data to Competition Analysis V1 builder."""

from __future__ import annotations

from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
from hashlib import sha256
import json
from typing import Any, Mapping

from amazon_product_intelligence.calculations import (
    CalculationInputLineage,
    CalculationProvenance,
    CalculationStatus,
    InputResolutionStatus,
    decimal_value,
    json_value,
)
from amazon_product_intelligence.connectors import CapabilityStatus
from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
    SubjectType,
    Unit,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.data_cleaning import CleanFieldResult, CleaningRunStatus
from amazon_product_intelligence.market_analysis import (
    BlockedMarketMetric,
    MarketAnalysisBuilderV0_1,
    MarketAnalysisRequest,
    MarketAnalysisStatus,
    MarketMetricStatus,
    NumericDistribution,
    NumericMetricSummary,
)

from .models import (
    COMPETITION_ANALYSIS_VERSION,
    BsrRankContext,
    CompetitionAnalysisRequest,
    CompetitionAnalysisResult,
    ContextualBsrSummary,
    VariationRelationshipRecord,
    VariationStructureSummary,
)


_PRECISION = 28
_SUMMARY_VERSION = "v0.1-exact-rank-context-summary"
_INCOMPLETE_VARIATION_CODES = frozenset(
    {
        "MISSING_VARIATION_PARENT_UNCONFIRMED",
        "NULL_VARIATION_PARENT_UNCONFIRMED",
        "EMPTY_VARIATION_RELATIONSHIP_UNCONFIRMED",
        "INVALID_PARENT_ASIN",
        "INVALID_CHILD_ASIN",
        "QUERY_AS_CHILD_NOT_CONFIRMED",
    }
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
    with localcontext(Context(prec=_PRECISION, rounding=ROUND_HALF_EVEN)):
        mean = sum(ordered, Decimal(0)) / Decimal(len(ordered))
        midpoint = len(ordered) // 2
        median = (
            ordered[midpoint]
            if len(ordered) % 2
            else (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)
        )
    return NumericDistribution(
        minimum=_canonical_decimal(ordered[0]),
        maximum=_canonical_decimal(ordered[-1]),
        mean=_canonical_decimal(mean),
        median=_canonical_decimal(median),
    )


def _context_material(field: CleanFieldResult) -> dict[str, Any] | None:
    context = field.rank_context
    if not isinstance(context, Mapping) or field.subject is None or field.unit is None:
        return None
    required = ("category_id", "category_name", "root", "source_date", "date_precision")
    if any(name not in context for name in required):
        return None
    category_id = context["category_id"]
    category_name = context["category_name"]
    source_date = context["source_date"]
    date_precision = context["date_precision"]
    root = context["root"]
    if (
        any(not isinstance(value, str) or not value.strip() for value in (
            category_id,
            category_name,
            source_date,
            date_precision,
        ))
        or type(root) is not bool
    ):
        return None
    return {
        "marketplace": field.subject.marketplace,
        "category_id": category_id,
        "category_name": category_name,
        "root": root,
        "source_date": source_date,
        "date_precision": date_precision,
        "unit": field.unit.to_dict(),
    }


class CompetitionAnalysisBuilderV0_1:
    """Build context-safe competition statistics without parsing provider payloads."""

    def __init__(self, market_builder: MarketAnalysisBuilderV0_1 | None = None) -> None:
        self._market_builder = market_builder or MarketAnalysisBuilderV0_1()

    def build(self, request: CompetitionAnalysisRequest) -> CompetitionAnalysisResult:
        if not isinstance(request, CompetitionAnalysisRequest):
            raise TypeError("request must be CompetitionAnalysisRequest")
        market = self._market_builder.build(
            MarketAnalysisRequest(
                marketplace=request.marketplace,
                clean_results=request.clean_results,
            )
        )
        fields = tuple(field for result in request.clean_results for field in result.fields)
        calculation_run_id = deterministic_id(
            "competition-analysis-calculation",
            {
                "scope_id": market.scope.scope_id,
                "analysis_version": COMPETITION_ANALYSIS_VERSION,
            },
        )
        bsr_summaries = self._bsr_summaries(
            fields,
            market.scope.product_ids,
            calculation_run_id,
        )
        unsafe_bsr_context_count = sum(
            field.canonical_field == "metric.bsr" and _context_material(field) is None
            for field in fields
        )
        variation_structure = self._variation_structure(request, fields)
        blocked = self._blocked_metrics(
            has_contextual_bsr=bool(bsr_summaries),
            has_unsafe_bsr_context=bool(unsafe_bsr_context_count),
        )
        rating = market.numeric_metric("market_analysis.product_rating")
        reviews = market.numeric_metric("market_analysis.product_review_count")
        count = market.count_metric("workbook.market_overview.observed_product_count")
        status = self._status(
            request,
            count.status,
            rating,
            reviews,
            bsr_summaries,
            has_unsafe_bsr_context=bool(unsafe_bsr_context_count),
        )
        material = {
            "analysis_version": COMPETITION_ANALYSIS_VERSION,
            "status": status.value,
            "calculation_run_id": calculation_run_id,
            "scope": market.scope.to_dict(),
            "observed_product_count": count.to_dict(),
            "rating_summary": rating.to_dict(),
            "review_count_summary": reviews.to_dict(),
            "bsr_summaries": [summary.to_dict() for summary in bsr_summaries],
            "variation_structure": variation_structure.to_dict(),
            "quality": market.quality.to_dict(),
            "source_quality_issues": [issue.to_dict() for issue in market.source_quality_issues],
            "blocked_metrics": [metric.to_dict() for metric in blocked],
            "base_market_analysis_id": market.analysis_id,
        }
        return CompetitionAnalysisResult(
            analysis_id=deterministic_id("competition-analysis", material),
            analysis_version=COMPETITION_ANALYSIS_VERSION,
            status=status,
            calculation_run_id=calculation_run_id,
            scope=market.scope,
            observed_product_count=count,
            rating_summary=rating,
            review_count_summary=reviews,
            bsr_summaries=bsr_summaries,
            variation_structure=variation_structure,
            quality=market.quality,
            source_quality_issues=market.source_quality_issues,
            blocked_metrics=blocked,
            base_market_analysis_id=market.analysis_id,
        )

    def _bsr_summaries(
        self,
        fields: tuple[CleanFieldResult, ...],
        product_ids: tuple[str, ...],
        calculation_run_id: str,
    ) -> tuple[ContextualBsrSummary, ...]:
        grouped: dict[str, tuple[dict[str, Any], list[CleanFieldResult]]] = {}
        for field in fields:
            if field.canonical_field != "metric.bsr":
                continue
            material = _context_material(field)
            if material is None:
                continue
            key = canonical_json(material)
            grouped.setdefault(key, (material, []))[1].append(field)
        summaries = tuple(
            self._bsr_summary(material, tuple(context_fields), product_ids, calculation_run_id)
            for material, context_fields in (grouped[key] for key in sorted(grouped))
        )
        return tuple(sorted(summaries, key=lambda item: item.context.context_id))

    def _bsr_summary(
        self,
        material: dict[str, Any],
        fields: tuple[CleanFieldResult, ...],
        product_ids: tuple[str, ...],
        calculation_run_id: str,
    ) -> ContextualBsrSummary:
        first = fields[0]
        context = BsrRankContext(
            context_id=deterministic_id("competition-bsr-context", material),
            marketplace=material["marketplace"],
            category_id=material["category_id"],
            category_name=material["category_name"],
            root=material["root"],
            source_date=material["source_date"],
            date_precision=material["date_precision"],
            unit=first.unit,
        )
        by_subject: dict[str, list[CleanFieldResult]] = {
            subject_id: [] for subject_id in product_ids
        }
        for field in fields:
            if field.subject is not None:
                by_subject.setdefault(field.subject.subject_id, []).append(field)
        selected: list[tuple[CleanFieldResult, Decimal]] = []
        missing = invalid = conflicts = partial = 0
        for subject_id in product_ids:
            candidates: list[tuple[CleanFieldResult, Decimal]] = []
            unsafe = False
            for field in by_subject.get(subject_id, []):
                if (
                    field.presence_status is PresenceStatus.PRESENT
                    and field.semantic_status is SemanticStatus.CONFIRMED
                    and field.normalization_status
                    in {NormalizationStatus.NORMALIZED, NormalizationStatus.NOT_APPLICABLE}
                    and field.normalized_value is not None
                    and field.provenance is not None
                    and not any(issue.blocking for issue in field.issues)
                ):
                    try:
                        candidates.append((field, decimal_value(field.normalized_value)))
                    except Exception:
                        unsafe = True
                else:
                    unsafe = True
            if len(candidates) > 1 or (candidates and unsafe):
                conflicts += 1
            elif len(candidates) == 1:
                selected.append(candidates[0])
                if candidates[0][0].capability_status is CapabilityStatus.PARTIAL:
                    partial += 1
            elif unsafe:
                invalid += 1
            else:
                missing += 1
        limitations: set[str] = set()
        if missing:
            limitations.add("MISSING_CONTEXT_MEMBERS_EXCLUDED")
        if invalid:
            limitations.add("INVALID_INPUTS_EXCLUDED")
        if conflicts:
            limitations.add("MULTIPLE_CANDIDATES_BLOCKED")
        if partial:
            limitations.add("PARTIAL_INPUTS_INCLUDED")
        unit_mismatch = sum(field.unit != context.unit for field, _ in selected)
        if unit_mismatch:
            limitations.add("RANK_UNIT_MISMATCH")
        if conflicts or unit_mismatch:
            status = MarketMetricStatus.BLOCKED
            distribution = None
            provenance = None
            selected_fields: tuple[CleanFieldResult, ...] = ()
        elif not selected:
            status = MarketMetricStatus.BLOCKED if invalid else MarketMetricStatus.MISSING
            distribution = None
            provenance = None
            selected_fields = ()
        else:
            if len(selected) < 2:
                limitations.add("SMALL_SAMPLE_SIZE_LT_2")
            status = MarketMetricStatus.PARTIAL if limitations else MarketMetricStatus.CALCULATED
            distribution = _distribution(tuple(value for _, value in selected))
            selected_fields = tuple(
                field for field, _ in sorted(selected, key=lambda item: item[0].observation_id or "")
            )
            provenance = self._summary_provenance(
                context,
                selected_fields,
                distribution,
                calculation_run_id,
            )
        metric_id = f"competition_analysis.bsr_context_{context.context_id.rsplit(':', 1)[-1][:16]}"
        return ContextualBsrSummary(
            context=context,
            summary=NumericMetricSummary(
                metric_id=metric_id,
                source_canonical_field="metric.bsr",
                status=status,
                distribution=distribution,
                unit=context.unit if distribution is not None else None,
                total_subject_count=len(product_ids),
                valid_sample_count=len(selected_fields),
                excluded_missing_count=missing,
                excluded_explicit_null_count=0,
                excluded_unknown_count=0,
                excluded_invalid_count=invalid,
                excluded_conflict_count=conflicts,
                excluded_unit_mismatch_count=unit_mismatch,
                partial_input_count=partial,
                source_observation_ids=tuple(
                    sorted(field.observation_id for field in selected_fields if field.observation_id)
                ),
                quality_issue_ids=tuple(
                    sorted(
                        {
                            issue.issue_id
                            for field in fields
                            for issue in field.issues
                        }
                    )
                ),
                limitations=tuple(sorted(limitations)),
                provenance=provenance,
            ),
        )

    @staticmethod
    def _summary_provenance(
        context: BsrRankContext,
        fields: tuple[CleanFieldResult, ...],
        distribution: NumericDistribution,
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
                        value
                        for value in (field.observation_id, field.raw_evidence_reference)
                        if value is not None
                    )
                ),
                provenances=(field.provenance,) if field.provenance is not None else (),
                quality_issue_ids=tuple(sorted(issue.issue_id for issue in field.issues)),
                input_fingerprint=_fingerprint(field.to_dict()),
            )
            for field in fields
        )
        metric_id = f"competition_analysis.bsr_context_{context.context_id.rsplit(':', 1)[-1][:16]}"
        output = {
            "context": context.to_dict(),
            "distribution": distribution.to_dict(),
            "valid_sample_count": len(fields),
        }
        return CalculationProvenance(
            calculation_rule_id=metric_id,
            calculation_version=_SUMMARY_VERSION,
            calculation_run_id=calculation_run_id,
            configuration_version=COMPETITION_ANALYSIS_VERSION,
            input_lineage=lineage,
            calculated_dependency_result_ids=(),
            input_fingerprint=_fingerprint([item.to_dict() for item in lineage]),
            output_fingerprint=_fingerprint(output),
        )

    @staticmethod
    def _variation_structure(
        request: CompetitionAnalysisRequest,
        fields: tuple[CleanFieldResult, ...],
    ) -> VariationStructureSummary:
        eligible = tuple(
            field
            for field in fields
            if field.canonical_field == "product.variation"
            and field.variation_parent_product_id is not None
            and field.variation_child_product_id is not None
            and field.observation_id is not None
            and field.raw_evidence_reference is not None
            and field.provenance is not None
            and field.presence_status is PresenceStatus.PRESENT
            and field.semantic_status is SemanticStatus.CONFIRMED
            and field.normalization_status
            in {NormalizationStatus.NORMALIZED, NormalizationStatus.NOT_APPLICABLE}
            and not any(issue.blocking for issue in field.issues)
        )
        records = tuple(
            VariationRelationshipRecord(
                parent_product_id=field.variation_parent_product_id,
                child_product_id=field.variation_child_product_id,
                source_observation_id=field.observation_id,
                raw_evidence_reference=field.raw_evidence_reference,
                provenance=field.provenance,
            )
            for field in eligible
        )
        pairs = {(record.parent_product_id, record.child_product_id) for record in records}
        incomplete_runs = 0
        for result in request.clean_results:
            codes = {
                value
                for diagnostic in result.diagnostics
                for value in (diagnostic.get("code"), diagnostic.get("issue_code"))
                if isinstance(value, str)
            } | {issue.issue_code for issue in result.issues}
            if codes & _INCOMPLETE_VARIATION_CODES:
                incomplete_runs += 1
        limitations: set[str] = set()
        if not records:
            limitations.add("NO_CONFIRMED_VARIATION_RELATIONSHIPS")
        if len(records) > len(pairs):
            limitations.add("DUPLICATE_RELATIONSHIP_RECORDS_RETAINED")
        if incomplete_runs:
            limitations.add("INCOMPLETE_FAMILY_EVIDENCE")
        return VariationStructureSummary(
            relationship_records=records,
            source_record_count=len(records),
            unique_parent_child_pair_count=len(pairs),
            unique_parent_count=len({parent for parent, _ in pairs}),
            unique_child_count=len({child for _, child in pairs}),
            duplicate_source_record_count=len(records) - len(pairs),
            incomplete_family_run_count=incomplete_runs,
            limitations=tuple(sorted(limitations)),
        )

    @staticmethod
    def _status(
        request: CompetitionAnalysisRequest,
        count_status: CalculationStatus,
        rating: NumericMetricSummary,
        reviews: NumericMetricSummary,
        bsr: tuple[ContextualBsrSummary, ...],
        *,
        has_unsafe_bsr_context: bool,
    ) -> MarketAnalysisStatus:
        if not request.clean_results:
            return MarketAnalysisStatus.EMPTY
        if (
            any(result.status is not CleaningRunStatus.SUCCESS for result in request.clean_results)
            or count_status is not CalculationStatus.CALCULATED
            or rating.status is not MarketMetricStatus.CALCULATED
            or reviews.status is not MarketMetricStatus.CALCULATED
            or not bsr
            or any(item.summary.status is not MarketMetricStatus.CALCULATED for item in bsr)
            or has_unsafe_bsr_context
        ):
            return MarketAnalysisStatus.PARTIAL
        return MarketAnalysisStatus.COMPLETE

    @staticmethod
    def _blocked_metrics(
        *,
        has_contextual_bsr: bool,
        has_unsafe_bsr_context: bool,
    ) -> tuple[BlockedMarketMetric, ...]:
        definitions = [
            (
                "competition_analysis.seller_count",
                "SELLER_IDENTITY_UNAVAILABLE",
                "The audited XiYou product contract does not expose a confirmed seller identity.",
                ("product.seller",),
            ),
            (
                "workbook.product_structure.minimum_comparable_price",
                "BLOCKED_BY_MEMBERSHIP_SOURCE",
                "Observed products are not governed Comparable Product membership.",
                ("canonical.comparable_price_observations",),
            ),
            (
                "workbook.product_structure.maximum_comparable_price",
                "BLOCKED_BY_MEMBERSHIP_SOURCE",
                "Observed products are not governed Comparable Product membership.",
                ("canonical.comparable_price_observations",),
            ),
            (
                "workbook.competition_evidence.variation_evidence_count",
                "SEMANTIC_AMBIGUITY",
                "Edge, evidence-record, and unique-variant grains remain separate and ungoverned.",
                ("canonical.variation_evidence_records",),
            ),
        ]
        if not has_contextual_bsr:
            definitions.append(
                (
                    "competition_analysis.bsr_summary",
                    "RANK_CONTEXT_UNAVAILABLE",
                    "No complete marketplace/category/date/rank-unit context is available for safe BSR aggregation.",
                    ("metric.bsr", "metric.bsr_context"),
                )
            )
        if has_unsafe_bsr_context:
            definitions.append(
                (
                    "competition_analysis.bsr_uncontextualized_input",
                    "INCOMPLETE_RANK_CONTEXT",
                    "At least one BSR input lacked complete marketplace/category/date/rank-unit context and was excluded from every aggregation.",
                    ("metric.bsr", "metric.bsr_context"),
                )
            )
        return tuple(
            sorted(
                (
                    BlockedMarketMetric(
                        metric_id=metric_id,
                        reason_code=reason,
                        message=message,
                        dependencies=tuple(sorted(dependencies)),
                    )
                    for metric_id, reason, message, dependencies in definitions
                ),
                key=lambda item: item.metric_id,
            )
        )


__all__ = ("CompetitionAnalysisBuilderV0_1",)
