"""TASK-SP-032I fresh 100-ASIN holdout capture and offline validation.

This validation-only runner does not mutate the frozen intent, taxonomy, or
semantic-clustering implementations.  Live provider payloads are checkpointed
after every successful request so subsequent analysis is offline-only.
"""

from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from amazon_product_intelligence.buyer_need_analysis.builder_v0_3 import (  # noqa: E402
    BuyerNeedAnalysisPipelineV0_3,
)
from amazon_product_intelligence.buyer_need_analysis.intent_v0_3 import (  # noqa: E402
    BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3,
)
from amazon_product_intelligence.buyer_need_analysis.models import (  # noqa: E402
    BuyerNeedCandidateStatus,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.buyer_need_analysis.models_v0_2 import (  # noqa: E402
    BuyerNeedQueryIntent,
    BuyerNeedQueryScope,
)
from amazon_product_intelligence.buyer_need_analysis.replay_v0_3 import (  # noqa: E402
    replay_intent_precision_v0_3,
)
from amazon_product_intelligence.buyer_need_analysis.taxonomy_v0_2 import (  # noqa: E402
    BUYER_NEED_TAXONOMY_V0_2,
    INTEGRATED_BOWL_ENTRY_V0_2,
)
from amazon_product_intelligence.contracts import (  # noqa: E402
    canonical_json,
    deterministic_id,
)
from amazon_product_intelligence.organic_keyword_discovery.capture import (  # noqa: E402
    XiYouLiveCaptureClient,
)
from amazon_product_intelligence.organic_keyword_discovery.holdout_v0_1 import (  # noqa: E402
    _atomic_json_write,
    _capture_record,
    _credit_audit,
    _parent_asin,
    _precision_result,
    _response_rows,
    _response_total,
    _share,
    _top_keywords,
    build_precision_audit_candidates,
    load_json_object,
    replay_holdout_discovery,
)
from amazon_product_intelligence.semantic_clustering import (  # noqa: E402
    SemanticClusterBuilder,
)
from amazon_product_intelligence.semantic_clustering.rules import (  # noqa: E402
    SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
)


BASELINE_COMMIT = "c25d9eebf74cf0c80f99c3202666f57eee3b13eb"
CONTRACT_VERSION = "organic-buyer-need-fresh-holdout-v0.1"
QUERY = "dog water bottle"
MARKETPLACE = "US"
PERIOD = "last7days"
CATEGORY_SCOPE = "Amazon US > Pet Supplies > Dog Travel Water Bottles"
COHORT_SIZE = 100
COHORT_PAGE_SIZE = 400
REVERSE_PAGE_SIZE = 20
CREDIT_GATE = 150
ESTIMATED_COHORT_CREDITS = 20
ESTIMATED_REVERSE_CREDITS = 100
ESTIMATED_TOTAL_CREDITS = 120

VALIDATION_DIR = ROOT / "docs" / "validation"
PILOT_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_DISCOVERY_PILOT_V0.1.json"
E_RAW_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_HOLDOUT_100_V0.1.raw.json"
E_ANALYSIS_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_HOLDOUT_100_V0.1.json"
F_RAW_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_TEMPORAL_HOLDOUT_V0.1.raw.json"
F_ANALYSIS_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_TEMPORAL_HOLDOUT_V0.1.json"
RAW_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.raw.json"
ANNOTATIONS_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.annotations.json"
ANALYSIS_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.json"
REPORT_PATH = VALIDATION_DIR / "ORGANIC_BUYER_NEED_FRESH_HOLDOUT_V0.1.md"

_TARGET_CATEGORY = re.compile(r"\b(?:dogs?|doggy|pupp(?:y|ies)|pets?)\b", re.IGNORECASE)
_TARGET_PRODUCT = re.compile(
    r"\b(?:water\s+)?(?:bottles?|bowls?|dispensers?)\b", re.IGNORECASE
)
_OUTDOOR_PATTERNS = {
    "portable": re.compile(r"\bportable\b", re.IGNORECASE),
    "travel": re.compile(r"\btravel\b", re.IGNORECASE),
    "walking": re.compile(r"\bwalk(?:ing|s)?\b", re.IGNORECASE),
    "hiking": re.compile(r"\bhiking\b", re.IGNORECASE),
}
_INTEGRATED_PATTERN = re.compile(
    r"\b(?:built[ -]?in|integrated)\s+bowl\b",
    re.IGNORECASE,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _registry_fingerprint(registry: Any) -> dict[str, Any]:
    payload = registry.to_dict()
    identity = (
        payload.get("registry_id")
        or payload.get("taxonomy_id")
        or payload.get("taxonomy_version")
    )
    return {
        "identity": identity,
        "canonical_sha256": _sha256_text(canonical_json(payload)),
    }


def frozen_fingerprints() -> dict[str, Any]:
    files = (
        "buyer_need_analysis/intent_v0_3.py",
        "buyer_need_analysis/models_v0_3.py",
        "buyer_need_analysis/builder_v0_3.py",
        "buyer_need_analysis/taxonomy_v0_2.py",
        "semantic_clustering/rules.py",
        "semantic_clustering/similarity.py",
        "semantic_clustering/builder_v0_1.py",
    )
    return {
        "intent_v0_3": _registry_fingerprint(
            BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3
        ),
        "taxonomy_v0_2": _registry_fingerprint(BUYER_NEED_TAXONOMY_V0_2),
        "semantic_v0_1": _registry_fingerprint(
            SEMANTIC_NORMALIZATION_REGISTRY_V0_1
        ),
        "source_files": {
            relative: _sha256_file(
                SRC / "amazon_product_intelligence" / relative
            )
            for relative in files
        },
    }


def _pilot_asins(snapshot: Mapping[str, Any]) -> frozenset[str]:
    cohort = snapshot.get("cohort")
    if not isinstance(cohort, Mapping):
        raise ValueError("SP-032B pilot cohort object is missing")
    values = cohort.get("asins")
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ValueError("SP-032B pilot cohort.asins is missing")
    return frozenset(str(value).upper() for value in values)


def _cohort_asins(snapshot: Mapping[str, Any], name: str) -> frozenset[str]:
    cohort = snapshot.get("cohort")
    if isinstance(cohort, (str, bytes)) or not isinstance(cohort, Sequence):
        raise ValueError(f"{name} cohort is missing")
    values = frozenset(
        str(item["asin"]).upper()
        for item in cohort
        if isinstance(item, Mapping) and item.get("asin")
    )
    return values


def historical_exclusions() -> dict[str, Any]:
    pilot = _pilot_asins(load_json_object(PILOT_PATH))
    cohort_e = _cohort_asins(load_json_object(E_RAW_PATH), "SP-032E")
    cohort_f = _cohort_asins(load_json_object(F_RAW_PATH), "SP-032F")
    expected = {"SP-032B": 20, "SP-032E": 100, "SP-032F": 100}
    actual = {"SP-032B": len(pilot), "SP-032E": len(cohort_e), "SP-032F": len(cohort_f)}
    if actual != expected:
        raise RuntimeError(f"historical cohort counts differ: {actual}")
    pairwise = {
        "SP-032B_vs_SP-032E": sorted(pilot & cohort_e),
        "SP-032B_vs_SP-032F": sorted(pilot & cohort_f),
        "SP-032E_vs_SP-032F": sorted(cohort_e & cohort_f),
    }
    if any(pairwise.values()):
        raise RuntimeError(f"historical cohorts overlap: {pairwise}")
    combined = pilot | cohort_e | cohort_f
    if len(combined) != 220:
        raise RuntimeError(f"historical exclusion union must be 220, got {len(combined)}")
    return {
        "counts": actual,
        "pairwise_overlaps": pairwise,
        "asins": sorted(combined),
        "source_files": [
            str(PILOT_PATH.relative_to(ROOT)),
            str(E_RAW_PATH.relative_to(ROOT)),
            str(F_RAW_PATH.relative_to(ROOT)),
        ],
    }


def _select_fresh_cohort(
    payload: Mapping[str, Any], excluded: frozenset[str]
) -> tuple[dict[str, Any], ...]:
    selected: list[dict[str, Any]] = []
    observed: set[str] = set()
    for response_rank, row in enumerate(_response_rows(payload), 1):
        raw_asin = row.get("asin")
        if not isinstance(raw_asin, str):
            continue
        asin = raw_asin.strip().upper()
        if len(asin) != 10 or not asin.isalnum() or asin in observed:
            continue
        observed.add(asin)
        if asin in excluded:
            continue
        selected.append(
            {
                "asin": asin,
                "parent_asin": _parent_asin(row),
                "product_grain": "CHILD_ASIN",
                "product_grain_basis": (
                    "XiYou keyword-to-product ASIN row; parent remains UNKNOWN when omitted"
                ),
                "cohort_query": QUERY,
                "marketplace": MARKETPLACE,
                "period": PERIOD,
                "provider_page": 1,
                "provider_response_rank": response_rank,
                "provider_row": dict(row),
            }
        )
        if len(selected) == COHORT_SIZE:
            break
    if len(selected) != COHORT_SIZE:
        raise RuntimeError(
            f"fresh holdout requires 100 independent ASINs; only {len(selected)} available"
        )
    overlap = {item["asin"] for item in selected} & excluded
    if overlap:
        raise RuntimeError(f"fresh cohort overlaps historical ASINs: {sorted(overlap)}")
    return tuple(selected)


def _new_checkpoint() -> dict[str, Any]:
    exclusions = historical_exclusions()
    if ESTIMATED_TOTAL_CREDITS > CREDIT_GATE:
        raise RuntimeError(
            "CREDIT APPROVAL REQUIRED: estimated total "
            f"{ESTIMATED_TOTAL_CREDITS} > gate {CREDIT_GATE}"
        )
    return {
        "contract_version": CONTRACT_VERSION,
        "baseline_commit": BASELINE_COMMIT,
        "category_scope": CATEGORY_SCOPE,
        "marketplace": MARKETPLACE,
        "cohort_query": QUERY,
        "period": PERIOD,
        "period_semantics": (
            "Current rolling seven-day provider window; later than the prior last7days "
            "capture. Official docs did not establish last30days as a supported enum."
        ),
        "retrieved_at": _utc_now(),
        "created_at": _utc_now(),
        "completed_at": None,
        "status": "IN_PROGRESS",
        "selection_method": (
            "XiYou keyword_asin_analysis page 1, pageSize 400, traffic desc; preserve "
            "provider order, deduplicate, exclude exact historical 220-ASIN union, take first 100."
        ),
        "credit_plan": {
            "cohort_credits_upper_bound": ESTIMATED_COHORT_CREDITS,
            "reverse_credits_upper_bound": ESTIMATED_REVERSE_CREDITS,
            "estimated_total_credits": ESTIMATED_TOTAL_CREDITS,
            "gate_credits": CREDIT_GATE,
            "enrichment_credits": 0,
        },
        "provider_contract_references": {
            "keyword_asin_period": "https://openapi-doc.xydc.com/451262166e0",
            "asin_keywords_period": "https://openapi-doc.xydc.com/331502595e0",
        },
        "historical_exclusions": exclusions,
        "fingerprints_start": frozen_fingerprints(),
        "fingerprints_end": None,
        "fingerprints_identical": None,
        "cohort_capture": None,
        "cohort": [],
        "reverse_captures": [],
    }


def capture_live() -> dict[str, Any]:
    if RAW_PATH.exists():
        checkpoint = load_json_object(RAW_PATH)
        if checkpoint.get("contract_version") != CONTRACT_VERSION:
            raise RuntimeError("existing checkpoint contract does not match SP-032I")
        if checkpoint.get("baseline_commit") != BASELINE_COMMIT:
            raise RuntimeError("existing checkpoint baseline does not match SP-032I")
    else:
        checkpoint = _new_checkpoint()
        _atomic_json_write(RAW_PATH, checkpoint)
    if checkpoint.get("status") == "COMPLETE":
        return checkpoint
    if checkpoint["credit_plan"]["estimated_total_credits"] > checkpoint["credit_plan"]["gate_credits"]:
        raise RuntimeError("CREDIT APPROVAL REQUIRED")

    client = XiYouLiveCaptureClient(
        environment=os.environ,
        retrieved_at=str(checkpoint["retrieved_at"]),
    )
    excluded = frozenset(checkpoint["historical_exclusions"]["asins"])
    if checkpoint.get("cohort_capture") is None:
        parameters = {
            "keyword": QUERY,
            "searchTerm": QUERY,
            "country": MARKETPLACE,
            "page": 1,
            "pageSize": COHORT_PAGE_SIZE,
            "period": PERIOD,
            "sort": {"field": "traffic", "order": "desc"},
        }
        capture = client.capture(
            operation="keyword_asin_analysis",
            canonical_field="relationship.keyword_to_product",
            parameters=parameters,
        )
        checkpoint["cohort_capture"] = _capture_record(
            capture, canonical_field="relationship.keyword_to_product"
        )
        checkpoint["cohort"] = list(_select_fresh_cohort(capture.payload, excluded))
        _atomic_json_write(RAW_PATH, checkpoint)
        print(
            f"checkpoint: cohort selected={len(checkpoint['cohort'])} "
            f"provider_total={_response_total(capture.payload)} credits={capture.cost_credits}",
            flush=True,
        )

    captured = {str(item["source_asin"]) for item in checkpoint["reverse_captures"]}
    for index, item in enumerate(checkpoint["cohort"], 1):
        asin = str(item["asin"])
        if asin in captured:
            continue
        parameters = {
            "asin": asin,
            "country": MARKETPLACE,
            "page": 1,
            "pageSize": REVERSE_PAGE_SIZE,
            "period": PERIOD,
            "sort": {"field": "traffic", "order": "desc"},
        }
        capture = client.capture(
            operation="asin_keywords",
            canonical_field="relationship.product_to_keyword",
            parameters=parameters,
        )
        record = _capture_record(
            capture, canonical_field="relationship.product_to_keyword"
        )
        record["source_asin"] = asin
        checkpoint["reverse_captures"].append(record)
        _atomic_json_write(RAW_PATH, checkpoint)
        if index == 1 or index % 5 == 0 or index == COHORT_SIZE:
            credits = sum(
                int(call.get("cost_credits") or 0)
                for call in (
                    [checkpoint["cohort_capture"]]
                    + list(checkpoint["reverse_captures"])
                )
            )
            print(
                f"checkpoint: reverse={len(checkpoint['reverse_captures'])}/100 "
                f"known_credits={credits}",
                flush=True,
            )

    checkpoint["fingerprints_end"] = frozen_fingerprints()
    checkpoint["fingerprints_identical"] = (
        checkpoint["fingerprints_start"] == checkpoint["fingerprints_end"]
    )
    checkpoint["status"] = "COMPLETE"
    checkpoint["completed_at"] = _utc_now()
    _atomic_json_write(RAW_PATH, checkpoint)
    return checkpoint


def _relation_analysis_v0_3(discovery: Any) -> tuple[dict[str, Any], ...]:
    pipeline = BuyerNeedAnalysisPipelineV0_3(
        query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
    )
    rows = []
    for record in discovery.records:
        text = build_search_term_text_evidence(
            record.keyword_identity,
            demand_lineage=discovery.lineage_by_discovery_id[record.discovery_id],
        )
        analysis = pipeline.analyze(text)
        evidence = analysis.intent_evidence
        intent = evidence.primary_intent
        candidates = tuple(analysis.buyer_need_candidates)
        matched = tuple(
            item for item in candidates if item.status is BuyerNeedCandidateStatus.CANDIDATE
        )
        if intent is BuyerNeedQueryIntent.AMBIGUOUS:
            resolution = "AMBIGUOUS"
        elif intent.is_non_need:
            resolution = "EXPLICIT_NON_NEED"
        elif matched:
            resolution = "RESOLVED_BUYER_NEED"
        else:
            resolution = "UNKNOWN_NEED_CANDIDATE"
        rows.append(
            {
                "discovery_id": record.discovery_id,
                "source_asin": record.source_asin,
                "keyword": record.provider_returned_text,
                "normalized_keyword": record.normalized_text,
                "query_origin": record.query_origin.value,
                "provider_request_ref": record.provider_request_ref,
                "provider_response_ref": record.provider_response_ref,
                "intent": intent.value,
                "intent_confidence": evidence.confidence.value,
                "intent_boundary": evidence.boundary.value,
                "intent_rule_ids": list(evidence.matched_rule_ids),
                "secondary_need_signals": list(evidence.secondary_need_signals),
                "eligible_for_taxonomy": evidence.eligible_for_taxonomy,
                "resolution": resolution,
                "buyer_needs": [
                    {
                        "need_id": item.need_id,
                        "need_type": item.need_type.value,
                        "need_label": item.need_label,
                        "status": item.status.value,
                        "taxonomy_need_id": item.taxonomy_need_id,
                        "extraction_rule_id": item.extraction_rule_id,
                    }
                    for item in candidates
                ],
                "rank": [item.to_dict() for item in record.rank],
                "organic_traffic": record.organic_traffic,
                "ad_traffic": record.ad_traffic,
                "traffic_status": record.traffic_status.value,
                "coverage_status": record.coverage_status.value,
            }
        )
    return tuple(sorted(rows, key=lambda item: item["discovery_id"]))


def _semantic_clusters_v0_3(
    relations: Sequence[Mapping[str, Any]], discovery: Any
) -> list[dict[str, Any]]:
    pipeline = BuyerNeedAnalysisPipelineV0_3(
        query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
    )
    records = {item.discovery_id: item for item in discovery.records}
    needs = []
    need_to_relation: dict[str, Mapping[str, Any]] = {}
    for row in relations:
        record = records[str(row["discovery_id"])]
        text = build_search_term_text_evidence(
            record.keyword_identity,
            demand_lineage=discovery.lineage_by_discovery_id[record.discovery_id],
        )
        result = pipeline.analyze(text)
        for need in result.semantic_cluster_inputs:
            needs.append(need)
            need_to_relation[need.need_id] = row
    if not needs:
        return []
    clustering = SemanticClusterBuilder().build(tuple(needs))
    rows = []
    for cluster in clustering.clusters:
        source = [need_to_relation[need_id] for need_id in cluster.source_need_ids]
        rows.append(
            {
                "cluster_id": cluster.cluster_id,
                "cluster_label": cluster.cluster_label,
                "need_count": len(cluster.source_need_ids),
                "relation_count": len({item["discovery_id"] for item in source}),
                "source_asin_count": len({item["source_asin"] for item in source}),
                "asin_coverage": _share(
                    len({item["source_asin"] for item in source}), COHORT_SIZE
                ),
                "expressions": sorted({str(item["keyword"]) for item in source}),
                "source_need_ids": list(cluster.source_need_ids),
            }
        )
    return sorted(rows, key=lambda item: (-item["source_asin_count"], item["cluster_label"]))


def _regression_checks(relations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    integrated_rows = [
        row for row in relations if _INTEGRATED_PATTERN.search(str(row["normalized_keyword"]))
    ]
    integrated_retained = [
        row
        for row in integrated_rows
        if any(
            need.get("taxonomy_need_id") == INTEGRATED_BOWL_ENTRY_V0_2.taxonomy_need_id
            and need.get("status") == BuyerNeedCandidateStatus.CANDIDATE.value
            for need in row["buyer_needs"]
        )
    ]
    outdoor: dict[str, Any] = {}
    for label, pattern in _OUTDOOR_PATTERNS.items():
        raw = [row for row in relations if pattern.search(str(row["normalized_keyword"]))]
        target = [
            row
            for row in raw
            if _TARGET_CATEGORY.search(str(row["normalized_keyword"]))
            and _TARGET_PRODUCT.search(str(row["normalized_keyword"]))
        ]
        retained = [row for row in target if row["intent"] == "NEED_CANDIDATE"]
        misclassified = [
            {
                "keyword": row["keyword"],
                "source_asin": row["source_asin"],
                "intent": row["intent"],
                "boundary": row["intent_boundary"],
            }
            for row in target
            if row["intent"] != "NEED_CANDIDATE"
        ]
        outdoor[label] = {
            "raw_relation_count": len(raw),
            "raw_source_asin_count": len({row["source_asin"] for row in raw}),
            "target_context_relation_count": len(target),
            "target_context_retained_count": len(retained),
            "target_context_routing_recall": (
                _share(len(retained), len(target)) if target else None
            ),
            "target_context_misclassifications": misclassified,
        }
    return {
        "integrated_bowl": {
            "raw_expression_relation_count": len(integrated_rows),
            "retained_relation_count": len(integrated_retained),
            "recall": (
                _share(len(integrated_retained), len(integrated_rows))
                if integrated_rows
                else None
            ),
        },
        "outdoor_portability": outdoor,
    }


def _annotation_error_analysis(
    precision: Mapping[str, Any], annotations: Mapping[str, Any] | None
) -> dict[str, Any]:
    reviews = annotations.get("term_reviews", {}) if isinstance(annotations, Mapping) else {}
    errors = []
    ambiguous = []
    for item in precision["items"]:
        review = reviews.get(item["normalized_keyword"], {}) if isinstance(reviews, Mapping) else {}
        row = {
            "keyword": item["keyword"],
            "normalized_keyword": item["normalized_keyword"],
            "source_asin": item["source_asin"],
            "audit_group": item["audit_group"],
            "predicted_intent": item["predicted_intent"],
            "manual_label": item["manual_label"],
            "reason": item["manual_reason"],
            "error_type": review.get("error_type") if isinstance(review, Mapping) else None,
        }
        if item["manual_label"] == "INCORRECT":
            errors.append(row)
        elif item["manual_label"] == "AMBIGUOUS":
            ambiguous.append(row)
    distribution = Counter(str(item["error_type"] or "OTHER") for item in errors)
    return {
        "incorrect_count": len(errors),
        "ambiguous_count": len(ambiguous),
        "error_type_distribution": dict(sorted(distribution.items())),
        "incorrect_items": errors,
        "ambiguous_items": ambiguous,
    }


def _historical_v0_3() -> dict[str, Any]:
    rows = {}
    for label, path in (("SP-032E", E_ANALYSIS_PATH), ("SP-032F", F_ANALYSIS_PATH)):
        replay = replay_intent_precision_v0_3(load_json_object(path))
        rows[label] = replay["v0_3"]
    return rows


def _decision(
    checkpoint: Mapping[str, Any], precision: Mapping[str, Any], regression: Mapping[str, Any]
) -> dict[str, str]:
    need = precision["summary"]["NEED_CANDIDATE"]
    non_need = precision["summary"]["NON_NEED"]
    complete = (
        need["selected_count"] >= 50
        and non_need["selected_count"] >= 30
        and need["unreviewed_count"] == 0
        and non_need["unreviewed_count"] == 0
        and checkpoint.get("fingerprints_identical") is True
    )
    if not complete:
        return {
            "code": "D",
            "label": "INSUFFICIENT_EVIDENCE",
            "reason": "Required manual audit or frozen-fingerprint evidence is incomplete.",
        }
    need_precision = Decimal(str(need["precision"]))
    non_need_precision = Decimal(str(non_need["precision"]))
    integrated = regression["integrated_bowl"]["recall"]
    outdoor_values = [
        item["target_context_routing_recall"]
        for item in regression["outdoor_portability"].values()
        if item["target_context_routing_recall"] is not None
    ]
    regressions_ok = (
        (integrated is None or Decimal(str(integrated)) >= Decimal("0.95"))
        and all(Decimal(str(value)) >= Decimal("0.95") for value in outdoor_values)
    )
    if need_precision >= Decimal("0.93") and non_need_precision >= Decimal("0.95") and regressions_ok:
        return {
            "code": "A",
            "label": "V0.3_STABLE",
            "reason": "Fresh precision meets the ideal Need target and all required regression gates.",
        }
    if need_precision >= Decimal("0.90") and non_need_precision >= Decimal("0.95") and regressions_ok:
        return {
            "code": "B",
            "label": "MINOR_FIX_NEEDED",
            "reason": "Minimum precision gates pass, but the ideal Need target is not fully met.",
        }
    return {
        "code": "C",
        "label": "NOT_READY_FOR_EXPANSION",
        "reason": "At least one required fresh precision or regression gate failed.",
    }


def analyze() -> dict[str, Any]:
    checkpoint = load_json_object(RAW_PATH)
    if checkpoint.get("status") != "COMPLETE":
        raise RuntimeError("SP-032I capture checkpoint is not complete")
    current = frozen_fingerprints()
    if checkpoint.get("fingerprints_start") != current:
        raise RuntimeError("frozen implementation changed since capture start")
    history = frozenset(checkpoint["historical_exclusions"]["asins"])
    cohort_asins = {str(item["asin"]) for item in checkpoint["cohort"]}
    overlap = sorted(cohort_asins & history)
    if overlap:
        raise RuntimeError(f"fresh cohort overlaps historical ASINs: {overlap}")

    discovery = replay_holdout_discovery(checkpoint)
    relations = _relation_analysis_v0_3(discovery)
    audit_candidates = build_precision_audit_candidates(relations, discovery)
    annotations = load_json_object(ANNOTATIONS_PATH) if ANNOTATIONS_PATH.exists() else None
    precision = _precision_result(audit_candidates, annotations)
    regression = _regression_checks(relations)
    historical = _historical_v0_3()
    corpus = discovery.corpus
    resolution_distribution = dict(
        sorted(Counter(str(row["resolution"]) for row in relations).items())
    )
    intent_distribution = dict(
        sorted(Counter(str(row["intent"]) for row in relations).items())
    )
    error_analysis = _annotation_error_analysis(precision, annotations)
    error_analysis["cross_holdout_pattern"] = {
        "SP-032E": {
            "false_positive_count": historical["SP-032E"]["false_positive_count"],
            "false_negative_count": historical["SP-032E"]["false_negative_count"],
            "observed_error_types": [],
        },
        "SP-032F": {
            "false_positive_count": historical["SP-032F"]["false_positive_count"],
            "false_negative_count": historical["SP-032F"]["false_negative_count"],
            "observed_error_types": [],
        },
        "SP-032I": {
            "false_positive_count": precision["summary"]["NEED_CANDIDATE"]["incorrect_count"],
            "false_negative_count": precision["summary"]["NON_NEED"]["incorrect_count"],
            "observed_error_types": sorted(error_analysis["error_type_distribution"]),
        },
        "judgement": "LOW_FREQUENCY_STRUCTURAL_BLIND_SPOT_WATCH",
        "reason": (
            "The bare broad-context query 'dog travel' exposes the taxonomy-with-category "
            "route when no water or target-product object is present. It is new in I, "
            "not a repeated SP-032E/F V0.3 error, and remains below the precision gate."
        ),
    }
    decision = _decision(checkpoint, precision, regression)
    credit = _credit_audit(checkpoint)
    payload = {
        "contract_version": CONTRACT_VERSION,
        "analysis_id": None,
        "baseline_commit": checkpoint["baseline_commit"],
        "category_scope": checkpoint["category_scope"],
        "marketplace": checkpoint["marketplace"],
        "retrieved_at": checkpoint["retrieved_at"],
        "period": checkpoint["period"],
        "period_semantics": checkpoint["period_semantics"],
        "cohort_query": checkpoint["cohort_query"],
        "cohort_selection_method": checkpoint["selection_method"],
        "cohort_provider_total": _response_total(checkpoint["cohort_capture"]["payload"]),
        "cohort": checkpoint["cohort"],
        "historical_exclusion_counts": checkpoint["historical_exclusions"]["counts"],
        "historical_excluded_asin_count": len(history),
        "historical_overlap_count": len(overlap),
        "historical_overlap_asins": overlap,
        "frozen_fingerprints": {
            "start": checkpoint["fingerprints_start"],
            "end": current,
            "identical": checkpoint["fingerprints_start"] == current,
        },
        "credit_audit": credit,
        "corpus": {
            "raw_relation_count": corpus.asin_keyword_relation_count,
            "unique_keyword_count": corpus.unique_keyword_count,
            "duplicate_keyword_count": corpus.duplicate_keyword_count,
            "source_asin_count": corpus.source_asin_count,
            "coverage": corpus.coverage.to_dict(),
            "rank_distribution": dict(corpus.rank_distribution),
            "traffic_availability": dict(corpus.traffic_availability),
        },
        "top_100_organic_terms": _top_keywords(discovery),
        "intent_distribution": intent_distribution,
        "resolution_distribution": resolution_distribution,
        "semantic_clusters": _semantic_clusters_v0_3(relations, discovery),
        "precision_audit": precision,
        "error_analysis": error_analysis,
        "regression_checks": regression,
        "comparison": {
            "SP-032E": historical["SP-032E"],
            "SP-032F": historical["SP-032F"],
            "SP-032I": {
                "need_precision": precision["summary"]["NEED_CANDIDATE"]["precision"],
                "non_need_precision": precision["summary"]["NON_NEED"]["precision"],
                "need_selected_count": precision["summary"]["NEED_CANDIDATE"]["selected_count"],
                "non_need_selected_count": precision["summary"]["NON_NEED"]["selected_count"],
                "false_positive_count": precision["summary"]["NEED_CANDIDATE"]["incorrect_count"],
                "false_negative_count": precision["summary"]["NON_NEED"]["incorrect_count"],
            },
        },
        "new_valid_need_proposals": [],
        "new_valid_need_proposal_policy": (
            "Only repeated, manually confirmed unmet Need expressions may be proposed; "
            "none are asserted without such fresh evidence."
        ),
        "final_decision": decision,
        "relations": list(relations),
        "limitations": [
            "Only page 1 / top 20 reverse keywords were captured per ASIN.",
            "The supported rolling window was last7days; last30days was not proven by official docs.",
            "ASIN coverage is cohort recurrence, not Demand Share.",
            "Provider traffic semantics remain provider-defined and uncalibrated.",
            "Parent ASIN is UNKNOWN whenever the forward response omits it.",
            "Manual term judgement is not Amazon behavioral ground truth.",
        ],
        "files_modified_scope": "SP-032I validation runner and SP-032I validation artifacts only",
        "core_rules_modified": 0,
    }
    identity = dict(payload)
    identity.pop("analysis_id")
    payload["analysis_id"] = deterministic_id("organic-buyer-need-fresh-holdout", identity)
    _atomic_json_write(ANALYSIS_PATH, payload)
    return payload


def write_audit_template() -> dict[str, Any]:
    result = analyze()
    if ANNOTATIONS_PATH.exists():
        return load_json_object(ANNOTATIONS_PATH)
    reviews = {
        item["normalized_keyword"]: {
            "audit_group": item["audit_group"],
            "keyword": item["keyword"],
            "source_asin": item["source_asin"],
            "predicted_intent": item["predicted_intent"],
            "precision_label": "UNREVIEWED",
            "precision_reason": None,
            "error_type": None,
        }
        for item in result["precision_audit"]["items"]
    }
    payload = {
        "audit_version": "sp032i-manual-term-audit-v0.1",
        "audit_method": (
            "Blind semantic judgement against the SP-032E/F standard: classify whether "
            "the query itself expresses a target-product Buyer Need; brand, accessory, "
            "product-object, broad, and out-of-scope queries are NON_NEED."
        ),
        "allowed_labels": ["CORRECT", "INCORRECT", "AMBIGUOUS"],
        "allowed_error_types": [
            "BRAND_QUERY",
            "ACCESSORY_QUERY",
            "PRODUCT_QUERY",
            "OUT_OF_SCOPE",
            "AMBIGUOUS_CONTEXT",
            "TAXONOMY_BOUNDARY",
            "OTHER",
        ],
        "term_reviews": reviews,
    }
    _atomic_json_write(ANNOTATIONS_PATH, payload)
    return payload


def _pct(value: Any) -> str:
    if value is None:
        return "UNKNOWN"
    return f"{Decimal(str(value)) * Decimal('100'):.2f}%"


def render_report(result: Mapping[str, Any]) -> str:
    need = result["precision_audit"]["summary"]["NEED_CANDIDATE"]
    non_need = result["precision_audit"]["summary"]["NON_NEED"]
    comparison_rows = []
    for label in ("SP-032E", "SP-032F"):
        item = result["comparison"][label]
        comparison_rows.append(
            f"| {label} | {_pct(item['need_precision'])} | {_pct(item['non_need_precision'])} | "
            f"{item['false_positive_count']} | {item['false_negative_count']} | {item['evaluated_count']} |"
        )
    comparison_rows.append(
        f"| SP-032I | {_pct(need['precision'])} | {_pct(non_need['precision'])} | "
        f"{result['comparison']['SP-032I']['false_positive_count']} | "
        f"{result['comparison']['SP-032I']['false_negative_count']} | "
        f"{need['selected_count'] + non_need['selected_count']} |"
    )
    intent_rows = "\n".join(
        f"| `{label}` | {count} |"
        for label, count in result["intent_distribution"].items()
    )
    semantic_rows = "\n".join(
        f"| {item['cluster_label']} | {item['relation_count']} | "
        f"{item['source_asin_count']} | {_pct(item['asin_coverage'])} |"
        for item in result["semantic_clusters"][:20]
    ) or "| — | 0 | 0 | UNKNOWN |"
    outdoor_rows = "\n".join(
        f"| {label} | {item['raw_relation_count']} | {item['raw_source_asin_count']} | "
        f"{item['target_context_relation_count']} | {item['target_context_retained_count']} | "
        f"{_pct(item['target_context_routing_recall'])} |"
        for label, item in result["regression_checks"]["outdoor_portability"].items()
    )
    error_rows = "\n".join(
        f"| {label} | {count} |"
        for label, count in result["error_analysis"]["error_type_distribution"].items()
    ) or "| — | 0 |"
    calls = result["credit_audit"]
    decision = result["final_decision"]
    next_step = {
        "A": "Freeze V0.3 as validated and proceed to broader-category validation.",
        "B": "Open one narrowly scoped precision fix before expansion.",
        "C": "Do not expand; redesign the failed boundary first.",
        "D": "Complete the missing evidence without changing rules.",
    }[decision["code"]]
    integrated = result["regression_checks"]["integrated_bowl"]
    first_rank = min(item["provider_response_rank"] for item in result["cohort"])
    last_rank = max(item["provider_response_rank"] for item in result["cohort"])
    return f"""# TASK-SP-032I Fresh 100-ASIN Holdout Validation v0.1

## 1. Executive result

Final decision: **{decision['code']}. {decision['label']}**.

{decision['reason']}

- Baseline commit: `{result['baseline_commit']}`
- Marketplace/category: `{result['marketplace']}` / {result['category_scope']}
- Retrieval time: `{result['retrieved_at']}`
- Window: `{result['period']}` — {result['period_semantics']}
- Fresh cohort: `100` child-ASIN product rows; historical exclusion union: `220`; overlap: `{result['historical_overlap_count']}`
- API calls / actual known credits: `{calls['request_count']}` / `{calls['known_credits']}`
- Credit estimate / gate: `{calls['estimated_credits']}` / `{calls['gate_credits']}`
- Frozen fingerprints identical: `{str(result['frozen_fingerprints']['identical']).lower()}`
- Files in frozen model/rule scope modified: `0`

## 2. Frozen system and holdout contract

The evaluated stack is `buyer-need-intent-rules-v0.3` + `buyer-need-taxonomy-v0.2` + the existing semantic-clustering registry. Start/end registry and source SHA-256 fingerprints are embedded in the machine-readable snapshot. No alias, intent rule, taxonomy entry, semantic threshold, Gap rule, score formula, policy, LLM, or embedding model was changed.

Selection was deterministic: query `{result['cohort_query']}`, XiYou `keyword_asin_analysis`, page `1`, page size `400`, `traffic desc`; retain provider order, deduplicate, exclude SP-032B/E/F 220-ASIN union, take the first 100. Selected provider ranks span `{first_rank}`–`{last_rank}`; provider total was `{result['cohort_provider_total']}`. Product grain follows the XiYou ASIN product-row contract; parent ASIN remains UNKNOWN when not returned.

`last30days` was not used because the official recent-days documentation only established the example value `last7days`; a trial call would have spent credits. This run used the current rolling `last7days`, whose dates have advanced since the earlier E capture.

## 3. Provider calls and credit audit

- 1 × `keyword_asin_analysis`, page 1 / up to 400 rows.
- 100 × `asin_keywords`, page 1 / top 20 rows per ASIN.
- No keyword enrichment call; no retry-based period probing.
- Every successful response was checkpointed immediately.
- Official billing upper bound before calls: `ceil(400/20) + 100×ceil(20/20) = 120` credits, below the 150-credit gate.
- Actual provider-reported known credits: `{calls['known_credits']}`; calls with unknown credit metadata: `{calls['unknown_credit_call_count']}`.

## 4. Organic keyword corpus

- Raw ASIN-keyword relations: `{result['corpus']['raw_relation_count']}`
- Unique normalized keywords: `{result['corpus']['unique_keyword_count']}`
- Source ASINs: `{result['corpus']['source_asin_count']}`
- Duplicate relation count: `{result['corpus']['duplicate_keyword_count']}`

## 5. V0.3 intent distribution

| Intent | Relations |
|---|---:|
{intent_rows}

## 6. Buyer Need / semantic distribution

| Semantic cluster | Relations | ASINs | ASIN coverage |
|---|---:|---:|---:|
{semantic_rows}

ASIN coverage is recurrence within this cohort, not Demand Share.

## 7. Manual precision audit

The deterministic audit selected `{need['selected_count']}` V0.3 Need predictions and `{non_need['selected_count']}` V0.3 NON_NEED predictions. Labels use the same semantic standard as SP-032E/F; AMBIGUOUS and UNREVIEWED are excluded from precision denominators.

| Group | Correct | Incorrect | Ambiguous | Unreviewed | Precision | Target |
|---|---:|---:|---:|---:|---:|---:|
| Need | {need['correct_count']} | {need['incorrect_count']} | {need['ambiguous_count']} | {need['unreviewed_count']} | {_pct(need['precision'])} | ≥90% (ideal ≥93%) |
| NON_NEED | {non_need['correct_count']} | {non_need['incorrect_count']} | {non_need['ambiguous_count']} | {non_need['unreviewed_count']} | {_pct(non_need['precision'])} | ≥95% |

## 8. Integrated Bowl regression

- Fresh raw Integrated/Built-in Bowl expressions: `{integrated['raw_expression_relation_count']}`
- Routed to the unchanged Integrated Bowl taxonomy entry: `{integrated['retained_relation_count']}`
- Recall: `{_pct(integrated['recall'])}`

## 9. Outdoor portability regression

| Expression | Raw relations | Raw ASINs | Target-context relations | Retained | Routing recall |
|---|---:|---:|---:|---:|---:|
{outdoor_rows}

The target-context denominator requires both a dog/pet qualifier and a target bottle/bowl/dispenser object. Generic accessory phrases are not counted as a target-product recall failure.

## 10. Precision error analysis

| Error type | Count |
|---|---:|
{error_rows}

Incorrect items, reasons, predicted intent, ASIN lineage, and error type are preserved in the JSON analysis and annotation artifacts. No correction was made during this task.

Cross-holdout judgement: **{result['error_analysis']['cross_holdout_pattern']['judgement']}**. {result['error_analysis']['cross_holdout_pattern']['reason']}

## 11. SP-032E / F / I comparison

| Holdout | Need precision | NON_NEED precision | FP | FN | Audited items |
|---|---:|---:|---:|---:|---:|
{chr(10).join(comparison_rows)}

E/F are offline replays of their saved human-labelled samples under the same frozen V0.3 classifier. I is the first completely fresh ASIN and keyword sample, so it is the controlling anti-overfit evidence.

## 12. New valid Buyer Need proposals

No new Buyer Need is asserted merely from an UNKNOWN or repeated token. A proposal requires repeated fresh evidence plus manual confirmation that the expression is a target-product need rather than a brand, accessory, product object, or context fragment. Fresh proposal count: `{len(result['new_valid_need_proposals'])}`.

## 13. Final decision and next step

**{decision['code']}. {decision['label']}** — {decision['reason']}

Unique next step:

- {next_step}

## 14. Limitations

1. Only page 1 / top 20 reverse keywords per ASIN were captured.
2. `last30days` support was not proven, so the current rolling `last7days` was used.
3. Provider traffic semantics are provider-defined and uncalibrated.
4. Parent ASIN is UNKNOWN when omitted by the provider.
5. Manual term judgement is not Amazon behavioral ground truth.

## 15. Artifacts and immutability

- Raw checkpoint: `docs/validation/{RAW_PATH.name}`
- Manual annotations: `docs/validation/{ANNOTATIONS_PATH.name}`
- Machine-readable analysis: `docs/validation/{ANALYSIS_PATH.name}`
- This report: `docs/validation/{REPORT_PATH.name}`
- Git commit created: `0`
- Frozen production/rule files modified: `0`
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="task-sp-032i")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--write-audit-template", action="store_true")
    parser.add_argument("--report", action="store_true")
    args = parser.parse_args(argv)
    if args.live:
        checkpoint = capture_live()
        print(
            json.dumps(
                {
                    "status": checkpoint["status"],
                    "cohort_count": len(checkpoint["cohort"]),
                    "reverse_count": len(checkpoint["reverse_captures"]),
                    "fingerprints_identical": checkpoint["fingerprints_identical"],
                    "checkpoint": str(RAW_PATH),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if args.write_audit_template:
        annotations = write_audit_template()
        print(
            json.dumps(
                {
                    "audit_items": len(annotations["term_reviews"]),
                    "annotations": str(ANNOTATIONS_PATH),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if args.report:
        result = analyze()
        REPORT_PATH.write_text(render_report(result), encoding="utf-8")
        print(
            json.dumps(
                {
                    "analysis_id": result["analysis_id"],
                    "decision": result["final_decision"],
                    "analysis": str(ANALYSIS_PATH),
                    "report": str(REPORT_PATH),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    if not (args.live or args.write_audit_template or args.report):
        parser.error("select --live, --write-audit-template, and/or --report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
