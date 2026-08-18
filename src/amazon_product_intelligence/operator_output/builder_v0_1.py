"""Deterministic Operator Output Layer V0.1 builder."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping as MappingABC
from typing import Any, Mapping, Sequence

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    canonical_json,
    deterministic_id,
)

from .errors import OperatorOutputValidationError
from .models import (
    OPERATOR_OUTPUT_RULESET_VERSION,
    CompetitionOutputRow,
    KeywordOutputRow,
    OpportunityOutputRow,
    OperatorOutputRequest,
    OperatorOutputSnapshotV0_1,
    OutputDiagnostic,
    OutputLineageReference,
    ProductOutputRow,
    RecommendationOutputRow,
    bundle_fingerprint,
    coverage_from_rows,
)


_PRODUCT_FACT_FIELDS = {
    "fact_set_id", "subject_product_identity", "dimension", "fact_group", "scope",
    "unit", "provider_semantic", "candidate_state", "distinct_present_value_count",
    "candidates",
}
_PRODUCT_METRIC_FIELDS = {
    "metric_series_id", "subject_product_identity", "metric", "measurement_type",
    "evidence_type", "unit", "scope", "period_type", "period_start", "period_end",
    "observed_at_status", "timezone", "currency", "rank_context", "metric_semantic",
    "candidate_count", "presence_counts", "candidates",
}
_PRODUCT_LINEAGE_FIELDS = {
    "observation_id", "semantic_observation_id", "observation_kind",
    "transformation_run_id", "mapping_version", "raw_evidence_id",
    "collection_run_id", "provider", "source_tool", "source_field",
    "source_bundle_fingerprints",
}
_DEMAND_METRIC_FIELDS = {
    "metric_evidence_set_id", "keyword_identity", "metric", "metric_semantic", "unit",
    "period_type", "period_start", "period_end", "observed_at_status", "timezone",
    "scope", "evidence_type", "provider_semantic", "candidate_state",
    "distinct_present_value_count", "candidate_count", "presence_counts", "candidates",
}
_DEMAND_RELATIONSHIP_GROUP_FIELDS = {
    "relationship_group_id", "keyword_identity", "direction", "channel", "records",
}
_DEMAND_RELATIONSHIP_FIELDS = {
    "observation_id", "semantic_observation_id", "relationship_id", "product_identity",
    "keyword_identity", "direction", "relationship_type", "channel",
    "query_result_status", "rank", "traffic", "evidence_type", "value", "scope",
    "time", "result_status", "provider_semantic", "provider", "source_tool",
    "lineage_references",
}
_DEMAND_QUERY_FIELDS = {
    "query_execution_id", "query_keyword", "query_product", "direction", "outcome",
    "related_relationship_observation_ids", "target_related_relationship_observation_ids",
    "provenance", "quality_issue_ids", "lineage_references",
}
_DEMAND_RELATED_FIELDS = {
    "inventory_item_id", "product_identity", "relationship_observation_ids", "directions",
    "channels", "providers", "lineage_references",
}
_DEMAND_LINEAGE_FIELDS = {
    "source_record_id", "source_record_type", "semantic_observation_id", "observation_kind",
    "transformation_run_id", "mapping_version", "raw_evidence_id", "collection_run_id",
    "provider", "source_tool", "source_field", "source_bundle_fingerprints",
}
_COMPETITION_RELATIONSHIP_FIELDS = {
    "observation_id", "semantic_observation_id", "classification", "relationship_id",
    "product_identity", "keyword_identity", "direction", "relationship_type", "channel",
    "query_result_status", "rank", "traffic", "evidence_type", "value", "scope", "time",
    "result_status", "provider_semantic", "provider", "source_tool", "lineage_references",
}
_COMPETITION_VARIATION_FIELDS = {
    "variation_evidence_id", "observation_id", "semantic_observation_id", "classification",
    "parent_product_identity", "child_product_identity", "source_dimension", "evidence_type",
    "value", "scope", "time", "result_status", "provider_semantic", "provider",
    "source_tool", "lineage_references",
}
_COMPETITION_LINEAGE_FIELDS = {
    "observation_id", "semantic_observation_id", "observation_kind", "source_record_type",
    "transformation_run_id", "mapping_version", "raw_evidence_id", "collection_run_id",
    "provider", "source_tool", "source_field", "source_bundle_fingerprints",
}
_OPPORTUNITY_SIGNAL_FIELDS = {
    "signal_id", "classification", "signal_type", "product_identities", "keyword_identities",
    "source_record_ids", "supporting_signal_ids", "providers", "source_tools",
    "evidence_attributes", "lineage_references",
}
_OPPORTUNITY_MISSING_FIELDS = {
    "missing_evidence_id", "classification", "evidence_kind", "basis",
    "source_bundle_fingerprints",
}
_OPPORTUNITY_MISSING_INVENTORY_FIELDS = {
    "evaluated_evidence_kinds", "items", "interpretation",
}
_OPPORTUNITY_RISK_FIELDS = {
    "risk_evidence_id", "classification", "risk_type", "source_record_ids",
    "missing_evidence_ids", "providers", "source_tools", "message", "lineage_references",
}
_OPPORTUNITY_LINEAGE_FIELDS = {
    "source_record_id", "source_record_type", "semantic_observation_id", "observation_kind",
    "transformation_run_id", "mapping_version", "raw_evidence_id", "collection_run_id",
    "provider", "source_tool", "source_field", "source_bundle_fingerprints",
}
_SCORE_CALCULATION_FIELDS = {
    "calculation_id", "factor_id", "component_id", "calculation_method", "input_components",
    "result_value", "result_status", "version", "decision_evaluation_ids",
    "decision_lineage_ids", "policy_evaluation_ids", "conflict_ids", "evidence_ids",
    "process_interpretation",
}
_SCORE_EXPLANATION_FIELDS = {
    "explanation_id", "factor_id", "component_id", "calculation_id", "factor_explanation",
    "calculation_rule", "version", "evidence_ids", "decision_evaluation_ids",
    "policy_evaluation_ids", "conflict_ids", "result_interpretation",
}
_SCORE_LINEAGE_FIELDS = {
    "score_lineage_id", "factor_id", "component_id", "calculation_id", "rule_id",
    "decision_evaluation_id", "decision_lineage_id", "policy_id", "policy_evaluation_id",
    "support_record_id", "conflict_record_id", "conflict_analysis_id",
    "conflict_candidate_id", "resolution_attempt_ids", "observation_id",
    "semantic_observation_id", "observation_kind", "evidence_type",
    "transformation_run_id", "mapping_version", "raw_evidence_id", "collection_run_id",
    "provider", "source_tool", "source_field", "source_bundle_fingerprints",
}
_RECOMMENDATION_RULE_FIELDS = {
    "rule_id", "rule_version", "description", "input_requirements", "conditions",
    "expected_recommendation_behavior",
}
_RECOMMENDATION_GENERATION_FIELDS = {
    "recommendation_generation_id", "rule_id", "recommendation_applicability_id",
    "input_evidence_ids", "decision_evaluation_ids", "score_component_ids",
    "score_calculation_ids", "policy_evaluation_ids", "conflict_ids",
    "recommendation_type", "explanation_id", "process_interpretation",
}
_RECOMMENDATION_EXPLANATION_FIELDS = {
    "explanation_id", "rule_id", "recommendation_type", "rule_explanation", "evidence_ids",
    "decision_evaluation_ids", "score_component_ids", "score_calculation_ids",
    "policy_evaluation_ids", "conflict_ids", "limitations",
}
_RECOMMENDATION_LINEAGE_FIELDS = {
    "recommendation_lineage_id", "recommendation_rule_id", "recommendation_applicability_id",
    "recommendation_generation_id", "explanation_id", "score_factor_id",
    "score_component_id", "score_calculation_id", "score_lineage_id", "decision_rule_id",
    "decision_evaluation_id", "decision_lineage_id", "policy_id", "policy_evaluation_id",
    "support_record_id", "conflict_record_id", "conflict_analysis_id",
    "conflict_candidate_id", "resolution_attempt_ids", "observation_id",
    "semantic_observation_id", "observation_kind", "evidence_type",
    "transformation_run_id", "mapping_version", "raw_evidence_id", "collection_run_id",
    "provider", "source_tool", "source_field", "source_bundle_fingerprints",
}


def _mapping(value: Any, path: str, fields: set[str] | None = None) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise OperatorOutputValidationError(f"{path} must be an object")
    if fields is not None and set(value) != fields:
        raise OperatorOutputValidationError(
            f"invalid {path} fields; missing={sorted(fields - set(value))}, "
            f"extra={sorted(set(value) - fields)}"
        )
    return value


def _records(
    snapshot: Mapping[str, Any], key: str, fields: set[str], path: str
) -> tuple[Mapping[str, Any], ...]:
    values = snapshot[key]
    if not isinstance(values, tuple):
        raise OperatorOutputValidationError(f"{path} must be an array")
    return tuple(_mapping(item, f"{path}[{index}]", fields) for index, item in enumerate(values))


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OperatorOutputValidationError(f"{path} must be non-empty text")
    return value


def _row_id(prefix: str, content: Mapping[str, Any]) -> str:
    return deterministic_id(prefix, content)


def _ordered_mappings(
    values: Sequence[Mapping[str, Any]],
) -> tuple[Mapping[str, Any], ...]:
    return tuple(sorted(values, key=canonical_json))


def _identifier_values(value: Any, key: str = "") -> set[str]:
    values: set[str] = set()
    if isinstance(value, MappingABC):
        for child_key, child in value.items():
            values.update(_identifier_values(child, child_key))
    elif isinstance(value, (tuple, list)):
        if key.endswith("_ids"):
            values.update(item for item in value if type(item) is str and item.strip())
        for child in value:
            values.update(_identifier_values(child, key))
    elif key.endswith("_id") and type(value) is str and value.strip():
        values.add(value)
    return values


class _CanonicalIndex:
    def __init__(self, bundles: Sequence[CanonicalEvidenceBundle]) -> None:
        self.records: dict[tuple[str, str], tuple[Any, str, set[str]]] = {}
        self.by_semantic_run: dict[tuple[str, str], tuple[str, str]] = {}
        for bundle in bundles:
            fingerprint = bundle_fingerprint(bundle)
            entries = tuple((item, "OBSERVATION") for item in bundle.observations) + tuple(
                (item, "QUERY_EXECUTION") for item in bundle.query_execution_records
            )
            for record, reference_type in entries:
                reference_id = (
                    record.observation_id if reference_type == "OBSERVATION" else record.query_execution_id
                )
                run_id = record.provenance.transformation.transformation_run_id
                key = (reference_id, run_id)
                prior = self.records.get(key)
                if prior is not None and canonical_json(prior[0]) != canonical_json(record):
                    raise OperatorOutputValidationError("canonical emission identity collision")
                if prior is None:
                    self.records[key] = (record, reference_type, {fingerprint})
                else:
                    prior[2].add(fingerprint)
                semantic_id = getattr(record, "semantic_observation_id", None)
                if semantic_id is not None:
                    semantic_key = (semantic_id, run_id)
                    existing = self.by_semantic_run.get(semantic_key)
                    if existing is not None and existing != key:
                        raise OperatorOutputValidationError("canonical semantic emission collision")
                    self.by_semantic_run[semantic_key] = key

    def resolve(self, lineage: Mapping[str, Any]) -> tuple[str, str, Any, set[str]]:
        run_id = _text(lineage.get("transformation_run_id"), "source lineage transformation_run_id")
        candidates = (
            lineage.get("observation_id"),
            lineage.get("source_record_id"),
        )
        key = next(
            ((item, run_id) for item in candidates if type(item) is str and (item, run_id) in self.records),
            None,
        )
        if key is None:
            semantic_id = lineage.get("semantic_observation_id")
            if type(semantic_id) is str:
                key = self.by_semantic_run.get((semantic_id, run_id))
        if key is None:
            raise OperatorOutputValidationError("source lineage cannot be resolved to canonical emission")
        record, reference_type, fingerprints = self.records[key]
        return key[0], reference_type, record, fingerprints


def _source_record_id(lineage: Mapping[str, Any], canonical_reference_id: str) -> str:
    for key in (
        "recommendation_generation_id", "calculation_id", "source_record_id",
        "observation_id", "semantic_observation_id",
    ):
        value = lineage.get(key)
        if type(value) is str and value.strip():
            return value
    return canonical_reference_id


def _source_lineage_id(
    lineage: Mapping[str, Any], source_snapshot_id: str
) -> str:
    for key in ("recommendation_lineage_id", "score_lineage_id"):
        value = lineage.get(key)
        if type(value) is str and value.strip():
            return value
    return deterministic_id(
        "serialized-source-lineage",
        {"source_snapshot_id": source_snapshot_id, "lineage": lineage},
    )


def _output_lineages(
    *,
    output_row_id: str,
    output_view: str,
    source_snapshot_id: str,
    source_lineages: Sequence[Mapping[str, Any]],
    canonical: _CanonicalIndex,
) -> tuple[OutputLineageReference, ...]:
    result: list[OutputLineageReference] = []
    for source in source_lineages:
        canonical_id, reference_type, record, emission_fingerprints = canonical.resolve(source)
        provenance = record.provenance
        transformation = provenance.transformation
        for key, expected in (
            ("transformation_run_id", transformation.transformation_run_id),
            ("mapping_version", transformation.mapping_version),
            ("raw_evidence_id", transformation.raw_evidence_reference),
            ("collection_run_id", transformation.collection_run_id),
            ("provider", provenance.provider),
            ("source_tool", provenance.source_tool),
            ("source_field", provenance.source_field),
        ):
            if source.get(key) != expected:
                raise OperatorOutputValidationError(f"source lineage {key} mismatch")
        source_fingerprints = source.get("source_bundle_fingerprints")
        if (
            not isinstance(source_fingerprints, tuple)
            or not source_fingerprints
            or not set(source_fingerprints) <= emission_fingerprints
        ):
            raise OperatorOutputValidationError("source lineage bundle fingerprints mismatch")
        payload = {
            "output_row_id": output_row_id,
            "output_view": output_view,
            "source_snapshot_id": source_snapshot_id,
            "source_record_id": _source_record_id(source, canonical_id),
            "source_lineage_id": _source_lineage_id(source, source_snapshot_id),
            "canonical_reference_id": canonical_id,
            "canonical_reference_type": reference_type,
            "semantic_observation_id": getattr(record, "semantic_observation_id", None),
            "transformation_run_id": transformation.transformation_run_id,
            "mapping_version": transformation.mapping_version,
            "raw_evidence_id": transformation.raw_evidence_reference,
            "collection_run_id": transformation.collection_run_id,
            "provider": provenance.provider,
            "source_tool": provenance.source_tool,
            "source_field": provenance.source_field,
            "source_bundle_fingerprints": tuple(sorted(source_fingerprints)),
        }
        result.append(OutputLineageReference(
            output_lineage_id=deterministic_id("operator-output-lineage", payload),
            **payload,
        ))
    ordered = tuple(sorted(result, key=lambda item: item.output_lineage_id))
    if not ordered:
        raise OperatorOutputValidationError(f"{output_view} row has no canonical lineage")
    if len({item.output_lineage_id for item in ordered}) != len(ordered):
        raise OperatorOutputValidationError("output lineage contains duplicates")
    return ordered


def _lineages_present_in_row(
    content: Mapping[str, Any],
    source_lineages: Sequence[Mapping[str, Any]],
    canonical: _CanonicalIndex,
) -> tuple[Mapping[str, Any], ...]:
    source_record_ids = _identifier_values(content)
    selected: list[Mapping[str, Any]] = []
    for lineage in source_lineages:
        canonical_id, _, _, _ = canonical.resolve(lineage)
        if _source_record_id(lineage, canonical_id) in source_record_ids:
            selected.append(lineage)
    return tuple(selected)


def _product_view(
    snapshot: Mapping[str, Any], canonical: _CanonicalIndex
) -> tuple[tuple[ProductOutputRow, ...], tuple[OutputLineageReference, ...]]:
    facts = _records(snapshot, "product_fact_evidence_sets", _PRODUCT_FACT_FIELDS, "product facts")
    metrics = _records(snapshot, "product_metric_series", _PRODUCT_METRIC_FIELDS, "product metrics")
    lineages = _records(snapshot, "lineage_index", _PRODUCT_LINEAGE_FIELDS, "product lineage")
    target = _mapping(snapshot["target_product_identity"], "product target")
    asin = _text(target.get("asin"), "product target asin")
    marketplace = _text(target.get("marketplace"), "product target marketplace")
    title_candidates = _ordered_mappings(tuple(
        candidate
        for fact in facts
        if "title" in str(fact["dimension"]).lower()
        for candidate in fact["candidates"]
    ))
    quality = tuple(snapshot["quality_issue_references"]) + tuple(snapshot["diagnostics"])
    content = {
        "asin": asin,
        "marketplace": marketplace,
        "title": title_candidates,
        "product_facts": _ordered_mappings(facts),
        "metrics": _ordered_mappings(metrics),
        "variation_information": snapshot["variation_topology"],
        "review_summary": snapshot["review_evidence_summary"],
        "data_quality_indicators": _ordered_mappings(quality),
        "source_snapshot_id": snapshot["snapshot_id"],
    }
    output_row_id = _row_id("operator-product-row", content)
    output_lineages = _output_lineages(
        output_row_id=output_row_id,
        output_view="PRODUCT",
        source_snapshot_id=snapshot["snapshot_id"],
        source_lineages=_lineages_present_in_row(content, lineages, canonical),
        canonical=canonical,
    )
    row = ProductOutputRow(
        output_row_id=output_row_id,
        lineage_reference_ids=tuple(item.output_lineage_id for item in output_lineages),
        **content,
    )
    return (row,), output_lineages


def _keyword_view(
    snapshot: Mapping[str, Any], canonical: _CanonicalIndex
) -> tuple[tuple[KeywordOutputRow, ...], tuple[OutputLineageReference, ...]]:
    metrics = _records(snapshot, "keyword_metric_evidence_sets", _DEMAND_METRIC_FIELDS, "keyword metrics")
    groups = _records(snapshot, "relationship_evidence_groups", _DEMAND_RELATIONSHIP_GROUP_FIELDS, "keyword relationship groups")
    queries = _records(snapshot, "query_execution_evidence", _DEMAND_QUERY_FIELDS, "keyword query execution")
    related = _records(snapshot, "related_product_evidence_inventory", _DEMAND_RELATED_FIELDS, "keyword related products")
    lineages = _records(snapshot, "lineage_index", _DEMAND_LINEAGE_FIELDS, "keyword lineage")
    channels: set[str] = set()
    providers: set[str] = set()
    for index, group in enumerate(groups):
        channel = group["channel"]
        if type(channel) is str and channel.strip():
            channels.add(channel)
        records = group["records"]
        if not isinstance(records, tuple):
            raise OperatorOutputValidationError("keyword relationship records must be an array")
        for record_index, record in enumerate(records):
            item = _mapping(record, f"keyword relationship groups[{index}].records[{record_index}]", _DEMAND_RELATIONSHIP_FIELDS)
            providers.add(_text(item["provider"], "keyword relationship provider"))
    for item in related:
        channels.update(item["channels"])
        providers.update(item["providers"])
    content = {
        "keyword": snapshot["target_keyword_identity"],
        "keyword_metrics": _ordered_mappings(metrics),
        "query_status": _ordered_mappings(queries),
        "related_products": _ordered_mappings(related),
        "channels": tuple(sorted(channels)),
        "providers": tuple(sorted(providers)),
        "limitations": (
            "DIRECTIONAL_QUERY_EVIDENCE_ONLY",
            "NO_DEMAND_OR_MARKET_SIZE_INFERENCE",
            "UNKNOWN_AND_EMPTY_RESULTS_REMAIN_DISTINCT",
        ),
        "source_snapshot_id": snapshot["snapshot_id"],
    }
    output_row_id = _row_id("operator-keyword-row", content)
    output_lineages = _output_lineages(
        output_row_id=output_row_id,
        output_view="KEYWORD",
        source_snapshot_id=snapshot["snapshot_id"],
        source_lineages=_lineages_present_in_row(content, lineages, canonical),
        canonical=canonical,
    )
    row = KeywordOutputRow(
        output_row_id=output_row_id,
        lineage_reference_ids=tuple(item.output_lineage_id for item in output_lineages),
        **content,
    )
    return (row,), output_lineages


def _product_id(identity: Any, path: str) -> str:
    value = _mapping(identity, path).get("product_id")
    return _text(value, f"{path}.product_id")


def _competition_view(
    snapshot: Mapping[str, Any], canonical: _CanonicalIndex
) -> tuple[tuple[CompetitionOutputRow, ...], tuple[OutputLineageReference, ...]]:
    relationships = _records(
        snapshot, "keyword_relationship_evidence", _COMPETITION_RELATIONSHIP_FIELDS,
        "competition keyword relationships",
    )
    variations = _records(snapshot, "variation_evidence", _COMPETITION_VARIATION_FIELDS, "competition variations")
    source_lineages = _records(snapshot, "lineage_index", _COMPETITION_LINEAGE_FIELDS, "competition lineage")
    groups: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in relationships:
        key = canonical_json({
            "product": item["product_identity"],
            "keyword": item["keyword_identity"],
            "direction": item["direction"],
            "relationship_type": item["relationship_type"],
            "channel": item["channel"],
            "provider": item["provider"],
        })
        groups[key].append(item)
    rows: list[CompetitionOutputRow] = []
    all_output_lineages: list[OutputLineageReference] = []
    for key in sorted(groups):
        records = tuple(sorted(groups[key], key=canonical_json))
        first = records[0]
        endpoint_id = _product_id(first["product_identity"], "competition product endpoint")
        variation_records = tuple(
            item for item in variations
            if endpoint_id in {
                _product_id(item["parent_product_identity"], "competition variation parent"),
                _product_id(item["child_product_identity"], "competition variation child"),
            }
        )
        observation_ids = {item["observation_id"] for item in records}
        observation_ids.update(item["observation_id"] for item in variation_records)
        selected_lineages = tuple(
            item for item in source_lineages if item["observation_id"] in observation_ids
        )
        relationship_view = {
            "keyword_identity": first["keyword_identity"],
            "direction": first["direction"],
            "query_result_statuses": tuple(sorted({item["query_result_status"] for item in records})),
            "relationship_observation_ids": tuple(sorted(observation_ids & {item["observation_id"] for item in records})),
        }
        content = {
            "product_endpoint": first["product_identity"],
            "keyword_relationship": relationship_view,
            "relationship_type": first["relationship_type"],
            "channel": first["channel"],
            "provider": first["provider"],
            "evidence_count": len(records),
            "variation_evidence": _ordered_mappings(variation_records),
            "limitations": tuple(sorted((
                "OBSERVED_RELATIONSHIPS_ONLY",
                "NO_COMPETITION_STRENGTH_OR_RANKING_INFERENCE",
            ))),
            "source_snapshot_id": snapshot["snapshot_id"],
        }
        output_row_id = _row_id("operator-competition-row", content)
        output_lineages = _output_lineages(
            output_row_id=output_row_id,
            output_view="COMPETITION_EVIDENCE",
            source_snapshot_id=snapshot["snapshot_id"],
            source_lineages=selected_lineages,
            canonical=canonical,
        )
        rows.append(CompetitionOutputRow(
            output_row_id=output_row_id,
            lineage_reference_ids=tuple(item.output_lineage_id for item in output_lineages),
            **content,
        ))
        all_output_lineages.extend(output_lineages)
    return tuple(sorted(rows, key=lambda item: item.output_row_id)), tuple(all_output_lineages)


def _opportunity_view(
    opportunity: Mapping[str, Any], scoring: Mapping[str, Any], canonical: _CanonicalIndex
) -> tuple[tuple[OpportunityOutputRow, ...], tuple[OutputLineageReference, ...]]:
    observed = _records(opportunity, "observed_signals", _OPPORTUNITY_SIGNAL_FIELDS, "opportunity observed signals")
    derived = _records(opportunity, "derived_signals", _OPPORTUNITY_SIGNAL_FIELDS, "opportunity derived signals")
    missing_inventory = _mapping(
        opportunity["missing_evidence"],
        "opportunity missing evidence inventory",
        _OPPORTUNITY_MISSING_INVENTORY_FIELDS,
    )
    if not isinstance(missing_inventory["items"], tuple):
        raise OperatorOutputValidationError("opportunity missing evidence items must be an array")
    missing = tuple(
        _mapping(item, f"opportunity missing evidence[{index}]", _OPPORTUNITY_MISSING_FIELDS)
        for index, item in enumerate(missing_inventory["items"])
    )
    risks = _records(opportunity, "risk_evidence", _OPPORTUNITY_RISK_FIELDS, "opportunity risk evidence")
    opportunity_lineages = _records(opportunity, "lineage_index", _OPPORTUNITY_LINEAGE_FIELDS, "opportunity lineage")
    calculations = _records(scoring, "calculations", _SCORE_CALCULATION_FIELDS, "score calculations")
    explanations = _records(scoring, "explanations", _SCORE_EXPLANATION_FIELDS, "score explanations")
    score_lineages = _records(scoring, "lineage_index", _SCORE_LINEAGE_FIELDS, "score lineage")
    products: dict[str, Mapping[str, Any]] = {}
    for signal in observed + derived:
        identities = signal["product_identities"]
        if not isinstance(identities, tuple):
            raise OperatorOutputValidationError("opportunity product identities must be an array")
        for identity in identities:
            products[canonical_json(identity)] = identity
    score_references = tuple({
        "calculation_id": item["calculation_id"],
        "factor_id": item["factor_id"],
        "component_id": item["component_id"],
        "result_value": item["result_value"],
        "result_status": item["result_status"],
        "version": item["version"],
    } for item in calculations)
    explanation_references = tuple({
        "explanation_id": item["explanation_id"],
        "factor_id": item["factor_id"],
        "calculation_id": item["calculation_id"],
        "factor_explanation": item["factor_explanation"],
        "result_interpretation": item["result_interpretation"],
    } for item in explanations)
    content = {
        "product": tuple(products[key] for key in sorted(products)),
        "signals": _ordered_mappings(observed + derived),
        "missing_evidence": _ordered_mappings(missing),
        "risk_evidence": _ordered_mappings(risks),
        "score_references": _ordered_mappings(score_references),
        "explanation_references": _ordered_mappings(explanation_references),
        "source_snapshot_ids": tuple(sorted((opportunity["snapshot_id"], scoring["snapshot_id"]))),
    }
    output_row_id = _row_id("operator-opportunity-row", content)
    first_lineages = _output_lineages(
        output_row_id=output_row_id,
        output_view="OPPORTUNITY",
        source_snapshot_id=opportunity["snapshot_id"],
        source_lineages=_lineages_present_in_row(
            content, opportunity_lineages, canonical
        ),
        canonical=canonical,
    )
    second_lineages = _output_lineages(
        output_row_id=output_row_id,
        output_view="OPPORTUNITY",
        source_snapshot_id=scoring["snapshot_id"],
        source_lineages=_lineages_present_in_row(content, score_lineages, canonical),
        canonical=canonical,
    )
    output_lineages = tuple(sorted(first_lineages + second_lineages, key=lambda item: item.output_lineage_id))
    row = OpportunityOutputRow(
        output_row_id=output_row_id,
        lineage_reference_ids=tuple(item.output_lineage_id for item in output_lineages),
        **content,
    )
    return (row,), output_lineages


def _recommendation_view(
    snapshot: Mapping[str, Any], canonical: _CanonicalIndex
) -> tuple[tuple[RecommendationOutputRow, ...], tuple[OutputLineageReference, ...]]:
    rules = _records(snapshot, "recommendation_rules", _RECOMMENDATION_RULE_FIELDS, "recommendation rules")
    generations = _records(snapshot, "generation_records", _RECOMMENDATION_GENERATION_FIELDS, "recommendation generations")
    explanations = _records(snapshot, "explanations", _RECOMMENDATION_EXPLANATION_FIELDS, "recommendation explanations")
    source_lineages = _records(snapshot, "lineage_index", _RECOMMENDATION_LINEAGE_FIELDS, "recommendation lineage")
    rule_by_id = {item["rule_id"]: item for item in rules}
    explanation_by_id = {item["explanation_id"]: item for item in explanations}
    rows: list[RecommendationOutputRow] = []
    all_output_lineages: list[OutputLineageReference] = []
    for generation in generations:
        rule = rule_by_id.get(generation["rule_id"])
        explanation = explanation_by_id.get(generation["explanation_id"])
        if rule is None or explanation is None:
            raise OperatorOutputValidationError("recommendation generation has broken references")
        selected_lineages = tuple(
            item for item in source_lineages
            if item["recommendation_generation_id"] == generation["recommendation_generation_id"]
        )
        evidence_ids = set(generation["input_evidence_ids"])
        evidence_ids.update(explanation["evidence_ids"])
        content = {
            "recommendation_type": generation["recommendation_type"],
            "rule_reference": rule,
            "explanation": explanation,
            "evidence_references": tuple(sorted(evidence_ids)),
            "limitations": tuple(explanation["limitations"]),
            "source_record_id": generation["recommendation_generation_id"],
            "source_snapshot_id": snapshot["snapshot_id"],
        }
        output_row_id = _row_id("operator-recommendation-row", content)
        output_lineages = _output_lineages(
            output_row_id=output_row_id,
            output_view="RECOMMENDATION",
            source_snapshot_id=snapshot["snapshot_id"],
            source_lineages=selected_lineages,
            canonical=canonical,
        )
        rows.append(RecommendationOutputRow(
            output_row_id=output_row_id,
            lineage_reference_ids=tuple(item.output_lineage_id for item in output_lineages),
            **content,
        ))
        all_output_lineages.extend(output_lineages)
    return tuple(sorted(rows, key=lambda item: item.output_row_id)), tuple(all_output_lineages)


class OperatorOutputBuilderV0_1:
    """Project existing serialized intelligence into audited operator tables."""

    def build(self, request: OperatorOutputRequest) -> OperatorOutputSnapshotV0_1:
        if not isinstance(request, OperatorOutputRequest):
            raise OperatorOutputValidationError("request must be OperatorOutputRequest")
        canonical = _CanonicalIndex(request.canonical_bundles)
        product_rows, product_lineage = _product_view(
            request.product_intelligence_snapshot, canonical
        )
        keyword_rows, keyword_lineage = _keyword_view(
            request.demand_intelligence_snapshot, canonical
        )
        competition_rows, competition_lineage = _competition_view(
            request.competition_intelligence_snapshot, canonical
        )
        opportunity_rows, opportunity_lineage = _opportunity_view(
            request.opportunity_intelligence_snapshot,
            request.opportunity_scoring_snapshot,
            canonical,
        )
        recommendation_rows, recommendation_lineage = _recommendation_view(
            request.recommendation_framework_snapshot, canonical
        )
        lineage = tuple(sorted(
            product_lineage + keyword_lineage + competition_lineage
            + opportunity_lineage + recommendation_lineage,
            key=lambda item: item.output_lineage_id,
        ))
        source_snapshot_ids = {
            "product_intelligence": request.product_intelligence_snapshot["snapshot_id"],
            "demand_intelligence": request.demand_intelligence_snapshot["snapshot_id"],
            "competition_intelligence": request.competition_intelligence_snapshot["snapshot_id"],
            "opportunity_intelligence": request.opportunity_intelligence_snapshot["snapshot_id"],
            "opportunity_scoring": request.opportunity_scoring_snapshot["snapshot_id"],
            "recommendation_framework": request.recommendation_framework_snapshot["snapshot_id"],
        }
        diagnostic_content = {
            "code": "OUTPUT_LAYER_PRESENTATION_ONLY",
            "severity": "INFO",
            "message": (
                "Rows reproduce existing evidence, score, and recommendation records; "
                "this layer performs no analysis, scoring, selection, or recommendation generation."
            ),
            "source_snapshot_ids": tuple(sorted(source_snapshot_ids.values())),
        }
        diagnostics = (OutputDiagnostic(
            diagnostic_id=deterministic_id("operator-output-diagnostic", diagnostic_content),
            **diagnostic_content,
        ),)
        coverage = coverage_from_rows(
            product_rows=product_rows,
            keyword_rows=keyword_rows,
            competition_rows=competition_rows,
            opportunity_rows=opportunity_rows,
            recommendation_rows=recommendation_rows,
            source_snapshot_ids=source_snapshot_ids,
            lineage=lineage,
            diagnostics=diagnostics,
        )
        content = {
            "ruleset_version": OPERATOR_OUTPUT_RULESET_VERSION,
            "source_bundle_fingerprints": tuple(sorted(
                bundle_fingerprint(item) for item in request.canonical_bundles
            )),
            "source_snapshot_ids": source_snapshot_ids,
            "product_rows": product_rows,
            "keyword_rows": keyword_rows,
            "competition_rows": competition_rows,
            "opportunity_rows": opportunity_rows,
            "recommendation_rows": recommendation_rows,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": lineage,
        }
        snapshot = OperatorOutputSnapshotV0_1(
            snapshot_id=deterministic_id("operator-output-snapshot", content),
            **content,
        )
        return snapshot.validate_against_bundles(request.canonical_bundles)


__all__ = ("OperatorOutputBuilderV0_1",)
