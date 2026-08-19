"""Bounded, secret-safe XiYou Competition Analysis V1 live validation.

This script makes exactly three no-retry requests when invoked with ``--live``.
It emits schema signatures, quality counts, derived metrics, and independent
recalculation comparisons; provider payload values are never printed or saved.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from decimal import Context, Decimal, ROUND_HALF_EVEN, localcontext
import json
import os
from typing import Any, Mapping

from amazon_product_intelligence.competition_analysis import (
    CompetitionAnalysisBuilderV0_1,
    CompetitionAnalysisRequest,
)
from amazon_product_intelligence.connectors import (
    HttpJsonTransport,
    NoRetryPolicy,
    ProviderConfig,
    ProviderConnectorError,
    ProviderRegistry,
    TransportRequest,
    TransportResponse,
    XiYouProvider,
)
from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
    SubjectType,
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.data_cleaning import (
    DataCleaningRequest,
    DataCleaningService,
)
from amazon_product_intelligence.normalization import CanonicalNormalizationPipeline


_DEFAULT_ASINS = ("B0G2VV4RBW", "B0G2VZSWRN", "B0G2VVX3ML")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="live-validate-competition-v0.1")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--asins", nargs=3, default=_DEFAULT_ASINS)
    parser.add_argument("--bsr-date", default="2026-08-07")
    return parser


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if type(value) is int:
        return "integer"
    if type(value) is float:
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    return type(value).__name__


def _schema(value: Any, depth: int = 0) -> dict[str, Any]:
    kind = _type_name(value)
    result: dict[str, Any] = {"type": kind}
    if depth >= 5:
        return result
    if isinstance(value, Mapping):
        result["keys"] = sorted(str(key) for key in value)
        result["fields"] = {
            str(key): _schema(value[key], depth + 1)
            for key in sorted(value, key=str)
        }
    elif isinstance(value, list):
        result["length"] = len(value)
        variants = {
            canonical_json(_schema(item, depth + 1)): _schema(item, depth + 1)
            for item in value
        }
        result["item_schemas"] = [variants[key] for key in sorted(variants)]
    return result


class AuditedTransport:
    def __init__(self) -> None:
        self._delegate = HttpJsonTransport({"xiyou": "https://openapi.xydc.com"})
        self.request_count = 0
        self.credit_headers: list[str] = []
        self.schemas: dict[str, dict[str, Any]] = {}

    def execute(self, request: TransportRequest) -> TransportResponse:
        self.request_count += 1
        response = self._delegate.execute(request)
        self.schemas[request.operation] = _schema(response.payload)
        credit = response.metadata.get("cost_credits")
        if isinstance(credit, str) and credit.strip():
            self.credit_headers.append(credit.strip())
        return response


def _request(operation: str, parameters: Mapping[str, Any]) -> DataCleaningRequest:
    observed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    collection_id = deterministic_id(
        "collection",
        {
            "provider": "xiyou",
            "operation": operation,
            "parameters": parameters,
            "marketplace": "US",
            "retrieved_at": observed_at,
        },
    )
    return DataCleaningRequest(
        provider_id="xiyou",
        operation=operation,
        parameters=parameters,
        marketplace="US",
        locale="en-us",
        retrieved_at=observed_at,
        transformed_at=observed_at,
        collection_run_id=collection_id,
        normalization_run_id=deterministic_id(
            "normalization",
            {"collection_run_id": collection_id, "version": "canonical-normalization-v0.1"},
        ),
        normalized_at=observed_at,
        currency="USD",
    )


def _distribution(values: list[Decimal]) -> dict[str, str] | None:
    if not values:
        return None
    ordered = sorted(values)
    with localcontext(Context(prec=28, rounding=ROUND_HALF_EVEN)):
        mean = sum(ordered, Decimal(0)) / Decimal(len(ordered))
        midpoint = len(ordered) // 2
        median = (
            ordered[midpoint]
            if len(ordered) % 2
            else (ordered[midpoint - 1] + ordered[midpoint]) / Decimal(2)
        )
    return {
        "minimum": str(ordered[0]),
        "maximum": str(ordered[-1]),
        "mean": str(mean),
        "median": str(median),
    }


def _valid_numeric(fields: tuple[Any, ...], canonical_field: str) -> list[Decimal]:
    values: list[Decimal] = []
    for field in fields:
        if (
            field.canonical_field == canonical_field
            and field.presence_status is PresenceStatus.PRESENT
            and field.semantic_status is SemanticStatus.CONFIRMED
            and field.normalization_status
            in {NormalizationStatus.NORMALIZED, NormalizationStatus.NOT_APPLICABLE}
            and field.normalized_value is not None
            and not any(issue.blocking for issue in field.issues)
        ):
            values.append(Decimal(str(field.normalized_value)))
    return values


def _safe_error(error: ProviderConnectorError) -> dict[str, Any]:
    return {
        "status": "BLOCKED",
        "credential": "CONFIGURED",
        "error": {
            "code": error.code.value,
            "provider_id": error.provider_id,
            "operation": error.operation,
            "retryable": error.retryable,
        },
    }


def main() -> None:
    args = _parser().parse_args()
    if not args.live:
        print(json.dumps({"status": "BLOCKED", "reason": "EXPLICIT_LIVE_GATE_REQUIRED"}))
        raise SystemExit(2)
    key = os.environ.get("XIYOU_API_KEY")
    if not isinstance(key, str) or not key.strip():
        print(json.dumps({"status": "BLOCKED", "credential": "NOT_CONFIGURED"}))
        raise SystemExit(2)

    transport = AuditedTransport()
    provider = XiYouProvider(transport, environment=os.environ, retry_policy=NoRetryPolicy())
    registry = ProviderRegistry()
    registry.register(
        provider,
        ProviderConfig(
            provider_id="xiyou",
            enabled=True,
            priority=1,
            credential_env="XIYOU_API_KEY",
            timeout_seconds=15.0,
            max_attempts=1,
        ),
    )
    cleaning = DataCleaningService(
        registry,
        CanonicalNormalizationPipeline.with_defaults(),
    )
    operations = (
        (
            "asin_info",
            {"entities": [{"country": "US", "asin": asin} for asin in args.asins]},
        ),
        ("asin_variations", {"country": "US", "asin": args.asins[0]}),
        (
            "asin_bsr_trends",
            {
                "country": "US",
                "asin": args.asins[0],
                "startDate": args.bsr_date,
                "endDate": args.bsr_date,
            },
        ),
    )
    try:
        clean_results = tuple(
            cleaning.clean(_request(operation, parameters))
            for operation, parameters in operations
        )
    except ProviderConnectorError as error:
        print(json.dumps(_safe_error(error), ensure_ascii=False, sort_keys=True, indent=2))
        raise SystemExit(2) from None

    analysis = CompetitionAnalysisBuilderV0_1().build(
        CompetitionAnalysisRequest(marketplace="US", clean_results=clean_results)
    )
    fields = tuple(field for result in clean_results for field in result.fields)
    independent_product_ids = {
        field.subject.subject_id
        for field in fields
        if field.subject is not None and field.subject.subject_type is SubjectType.PRODUCT
    }
    independent_product_ids.update(
        value
        for field in fields
        for value in (
            field.variation_parent_product_id,
            field.variation_child_product_id,
        )
        if value is not None
    )
    rating_values = _valid_numeric(fields, "metric.rating")
    review_values = _valid_numeric(fields, "metric.review_count")
    bsr_comparisons = []
    for item in analysis.bsr_summaries:
        context = item.context
        context_values = [
            Decimal(str(field.normalized_value))
            for field in fields
            if field.canonical_field == "metric.bsr"
            and field.rank_context is not None
            and field.rank_context.get("category_id") == context.category_id
            and field.rank_context.get("category_name") == context.category_name
            and field.rank_context.get("root") == context.root
            and field.rank_context.get("source_date") == context.source_date
            and field.rank_context.get("date_precision") == context.date_precision
            and field.unit == context.unit
            and field.presence_status is PresenceStatus.PRESENT
            and field.semantic_status is SemanticStatus.CONFIRMED
            and field.normalization_status
            in {NormalizationStatus.NORMALIZED, NormalizationStatus.NOT_APPLICABLE}
            and field.normalized_value is not None
            and not any(issue.blocking for issue in field.issues)
        ]
        independent = _distribution(context_values)
        produced = None if item.summary.distribution is None else item.summary.distribution.to_dict()
        bsr_comparisons.append(
            {
                "context_id": context.context_id,
                "valid_sample_count": len(context_values),
                "excluded_count": item.summary.total_subject_count - len(context_values),
                "independent": independent,
                "produced": produced,
                "match": independent == produced
                and len(context_values) == item.summary.valid_sample_count,
            }
        )

    credits: int | str
    if transport.credit_headers and all(value.isdigit() for value in transport.credit_headers):
        credits = sum(int(value) for value in transport.credit_headers)
    else:
        credits = "UNKNOWN"
    quality = {
        key: sum(getattr(result.quality_summary, key) for result in clean_results)
        for key in (
            "fields_observed",
            "fields_normalized",
            "fields_unchanged",
            "fields_missing",
            "fields_explicit_null",
            "fields_unknown",
            "fields_invalid",
            "fields_partial",
            "quality_issue_count",
        )
    }
    rating_independent = _distribution(rating_values)
    reviews_independent = _distribution(review_values)
    payload = {
        "status": "COMPLETE"
        if (
            transport.request_count == 3
            and analysis.observed_product_count.value == len(independent_product_ids)
            and rating_independent
            == (None if analysis.rating_summary.distribution is None else analysis.rating_summary.distribution.to_dict())
            and reviews_independent
            == (None if analysis.review_count_summary.distribution is None else analysis.review_count_summary.distribution.to_dict())
            and bsr_comparisons
            and all(item["match"] for item in bsr_comparisons)
        )
        else "BLOCKED",
        "credential": "CONFIGURED",
        "requests": transport.request_count,
        "credits": credits,
        "requested_asin_count": len(args.asins),
        "received_product_identity_count": transport.schemas.get("asin_info", {})
        .get("fields", {})
        .get("entities", {})
        .get("length", 0),
        "usable_observed_product_count": len(independent_product_ids),
        "schemas": transport.schemas,
        "mapping_versions": sorted(
            {version for result in clean_results for version in result.mapping_versions}
        ),
        "cleaning_quality": quality,
        "quality_issue_codes": sorted({issue.issue_code for result in clean_results for issue in result.issues}),
        "analysis_status": analysis.status.value,
        "metrics": {
            "observed_product_count": analysis.observed_product_count.value,
            "rating": {
                "status": analysis.rating_summary.status.value,
                "distribution": None if analysis.rating_summary.distribution is None else analysis.rating_summary.distribution.to_dict(),
                "valid_sample_count": analysis.rating_summary.valid_sample_count,
                "excluded_count": analysis.rating_summary.total_subject_count - analysis.rating_summary.valid_sample_count,
            },
            "review_count": {
                "status": analysis.review_count_summary.status.value,
                "distribution": None if analysis.review_count_summary.distribution is None else analysis.review_count_summary.distribution.to_dict(),
                "valid_sample_count": analysis.review_count_summary.valid_sample_count,
                "excluded_count": analysis.review_count_summary.total_subject_count - analysis.review_count_summary.valid_sample_count,
            },
            "bsr_contexts": [
                {
                    "context_id": item.context.context_id,
                    "category_id": item.context.category_id,
                    "category_name": item.context.category_name,
                    "root": item.context.root,
                    "source_date": item.context.source_date,
                    "status": item.summary.status.value,
                    "distribution": None if item.summary.distribution is None else item.summary.distribution.to_dict(),
                    "valid_sample_count": item.summary.valid_sample_count,
                    "excluded_count": item.summary.total_subject_count - item.summary.valid_sample_count,
                }
                for item in analysis.bsr_summaries
            ],
            "variation_structure": {
                "source_record_count": analysis.variation_structure.source_record_count,
                "unique_parent_child_pair_count": analysis.variation_structure.unique_parent_child_pair_count,
                "unique_parent_count": analysis.variation_structure.unique_parent_count,
                "unique_child_count": analysis.variation_structure.unique_child_count,
                "duplicate_source_record_count": analysis.variation_structure.duplicate_source_record_count,
                "incomplete_family_run_count": analysis.variation_structure.incomplete_family_run_count,
                "limitations": list(analysis.variation_structure.limitations),
            },
        },
        "independent_recalculation": {
            "observed_product_count": {
                "independent": len(independent_product_ids),
                "produced": analysis.observed_product_count.value,
                "match": len(independent_product_ids) == analysis.observed_product_count.value,
            },
            "rating": {
                "valid_sample_count": len(rating_values),
                "excluded_count": len(independent_product_ids) - len(rating_values),
                "independent": rating_independent,
                "produced": None if analysis.rating_summary.distribution is None else analysis.rating_summary.distribution.to_dict(),
                "match": rating_independent == (None if analysis.rating_summary.distribution is None else analysis.rating_summary.distribution.to_dict()),
            },
            "review_count": {
                "valid_sample_count": len(review_values),
                "excluded_count": len(independent_product_ids) - len(review_values),
                "independent": reviews_independent,
                "produced": None if analysis.review_count_summary.distribution is None else analysis.review_count_summary.distribution.to_dict(),
                "match": reviews_independent == (None if analysis.review_count_summary.distribution is None else analysis.review_count_summary.distribution.to_dict()),
            },
            "bsr_contexts": bsr_comparisons,
        },
        "blocked_metrics": [metric.to_dict() for metric in analysis.blocked_metrics],
        "provenance": {
            "observed_product_count_rule": analysis.observed_product_count.calculation_rule_id,
            "rating_rule": None if analysis.rating_summary.provenance is None else analysis.rating_summary.provenance.calculation_rule_id,
            "review_rule": None if analysis.review_count_summary.provenance is None else analysis.review_count_summary.provenance.calculation_rule_id,
            "bsr_lineage_count": sum(
                len(item.summary.provenance.input_lineage)
                for item in analysis.bsr_summaries
                if item.summary.provenance is not None
            ),
        },
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    raise SystemExit(0 if payload["status"] == "COMPLETE" else 2)


if __name__ == "__main__":
    main()
