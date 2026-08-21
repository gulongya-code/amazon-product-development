"""TASK-SP-032E bounded live capture and offline holdout analysis.

The live boundary is deliberately small: one deterministic forward cohort call,
one first-page reverse-keyword call per holdout ASIN, and one optional batched
keyword enrichment call.  Raw provider payloads are checkpointed after every
successful call so offline replay never needs to spend credits again.
"""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

from amazon_product_intelligence.buyer_need_analysis import (
    CRATE_COMPATIBILITY_EXPERIMENT_V0_2,
    INTEGRATED_BOWL_ENTRY_V0_2,
    COLLAPSIBLE_STRUCTURE_ENTRY_V0_2,
    BuyerNeedAnalysisPipelineV0_2,
    BuyerNeedCandidateStatus,
    BuyerNeedQueryIntent,
    BuyerNeedQueryScope,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.connectors import (
    ProviderConnectorError,
    ProviderErrorCode,
    TransportRequest,
    TransportResponse,
)
from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.demand_intelligence import (
    DemandIntelligenceBuilderV0_1,
    DemandIntelligenceRequest,
)
from amazon_product_intelligence.semantic_clustering import SemanticClusterBuilder

from .capture import XiYouLiveCaptureClient
from .models import QueryOrigin
from .runner import CreditApprovalRequired, OrganicKeywordDiscoveryRunner


HOLDOUT_CONTRACT_VERSION = "organic-buyer-need-holdout-v0.1"
HOLDOUT_QUERY = "dog water bottle"
HOLDOUT_MARKETPLACE = "US"
HOLDOUT_PERIOD = "last7days"
HOLDOUT_ASIN_COUNT = 100
HOLDOUT_COHORT_PAGE_SIZE = 200
HOLDOUT_REVERSE_PAGE_SIZE = 20
HOLDOUT_CREDIT_GATE = 150

SP032B_PILOT_ASINS = frozenset(
    {
        "B09F5ZYV7M",
        "B0GTQZG7J3",
        "B098KBJNMH",
        "B07GKRKT33",
        "B09CH9W2XS",
        "B0BZR44DQF",
        "B07Q56TTD4",
        "B089W25KG3",
        "B07C79KZLL",
        "B0DP3MMNFM",
        "B0F6MS3VGK",
        "B0H48MWCQL",
        "B07GKP62WV",
        "B0H33P63FW",
        "B0CJ29S8PG",
        "B07DFX3Q79",
        "B08MBDK747",
        "B0DBJCDR4W",
        "B0B497MVR1",
        "B0FN8B96G8",
    }
)

_PRECISION_LABELS = frozenset({"CORRECT", "INCORRECT", "AMBIGUOUS"})
_UNKNOWN_CATEGORIES = frozenset(
    {
        "NEW_VALID_BUYER_NEED",
        "EXISTING_TAXONOMY_GAP",
        "PRODUCT_OR_NON_NEED_MISROUTED",
        "NON_NEED_MISROUTED_AS_NEED",
        "AMBIGUOUS",
        "OTHER",
    }
)
_SPECIAL_LABELS = frozenset({"TRUE_POSITIVE", "FALSE_POSITIVE", "AMBIGUOUS"})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _share(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0"
    return format(Decimal(numerator) / Decimal(denominator), "f")


def _integer(value: Any) -> int | None:
    if type(value) is int and value >= 0:
        return value
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _atomic_json_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json_object(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


@dataclass(frozen=True, slots=True)
class HoldoutCreditPlan:
    cohort_credits: int = 1
    reverse_credits: int = HOLDOUT_ASIN_COUNT
    enrichment_credits: int = 1
    gate_credits: int = HOLDOUT_CREDIT_GATE

    @property
    def estimated_total_credits(self) -> int:
        return self.cohort_credits + self.reverse_credits + self.enrichment_credits

    def enforce(self) -> None:
        if self.estimated_total_credits > self.gate_credits:
            raise CreditApprovalRequired(
                "CREDIT APPROVAL REQUIRED: estimated total "
                f"{self.estimated_total_credits} > gate {self.gate_credits}"
            )

    def to_dict(self) -> dict[str, int]:
        return {
            "cohort_credits": self.cohort_credits,
            "reverse_credits": self.reverse_credits,
            "enrichment_credits": self.enrichment_credits,
            "estimated_total_credits": self.estimated_total_credits,
            "gate_credits": self.gate_credits,
        }


def _response_rows(payload: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    data = payload.get("data")
    container = data if isinstance(data, Mapping) else payload
    rows = container.get("list")
    return tuple(item for item in rows if isinstance(item, Mapping)) if isinstance(rows, list) else ()


def _response_total(payload: Mapping[str, Any]) -> int | None:
    data = payload.get("data")
    container = data if isinstance(data, Mapping) else payload
    return _integer(container.get("total"))


def _capture_record(capture: Any, *, canonical_field: str) -> dict[str, Any]:
    return {
        "operation": capture.operation,
        "canonical_field": canonical_field,
        "parameters": dict(capture.parameters),
        "payload": dict(capture.payload),
        "metadata": dict(capture.metadata),
        "request_ref": capture.request_ref,
        "response_ref": capture.response_ref,
        "cost_credits": capture.cost_credits,
        "x_cost_credits": capture.x_cost_credits,
        "captured_at": _utc_now(),
    }


def _parent_asin(row: Mapping[str, Any]) -> str | None:
    for key in ("parentAsin", "parent_asin", "parentASIN", "parent"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().upper()
    return None


def select_holdout_cohort(
    payload: Mapping[str, Any],
    *,
    asin_count: int = HOLDOUT_ASIN_COUNT,
    excluded_asins: frozenset[str] = SP032B_PILOT_ASINS,
) -> tuple[dict[str, Any], ...]:
    """Take the first unique valid provider rows after the frozen pilot exclusion."""

    selected: list[dict[str, Any]] = []
    observed: set[str] = set()
    for response_index, row in enumerate(_response_rows(payload), 1):
        value = row.get("asin")
        if not isinstance(value, str):
            continue
        asin = value.strip().upper()
        if len(asin) != 10 or not asin.isalnum() or asin in observed:
            continue
        observed.add(asin)
        if asin in excluded_asins:
            continue
        selected.append(
            {
                "asin": asin,
                "parent_asin": _parent_asin(row),
                "product_grain": "CHILD_ASIN",
                "cohort_query": HOLDOUT_QUERY,
                "marketplace": HOLDOUT_MARKETPLACE,
                "period": HOLDOUT_PERIOD,
                "provider_page": 1,
                "provider_response_rank": response_index,
                "provider_row": dict(row),
            }
        )
        if len(selected) == asin_count:
            break
    if len(selected) != asin_count:
        raise RuntimeError(
            f"holdout requires {asin_count} independent ASINs; provider yielded {len(selected)}"
        )
    asins = {item["asin"] for item in selected}
    overlap = asins & excluded_asins
    if overlap:
        raise RuntimeError(f"holdout overlaps SP-032B: {sorted(overlap)}")
    return tuple(selected)


class OrganicHoldoutLiveCaptureV0_1:
    """Credit-gated, checkpointed XiYou capture for exactly 100 holdout ASINs."""

    def __init__(
        self,
        capture_client: XiYouLiveCaptureClient,
        *,
        baseline_commit: str,
        checkpoint_path: str | Path,
        include_enrichment: bool = True,
        credit_gate: int = HOLDOUT_CREDIT_GATE,
    ) -> None:
        self.capture_client = capture_client
        self.baseline_commit = baseline_commit
        self.checkpoint_path = Path(checkpoint_path)
        self.include_enrichment = include_enrichment
        self.credit_plan = HoldoutCreditPlan(
            enrichment_credits=1 if include_enrichment else 0,
            gate_credits=credit_gate,
        )

    def run(self) -> dict[str, Any]:
        self.credit_plan.enforce()
        checkpoint = self._load_or_initialize()
        if checkpoint.get("status") == "COMPLETE":
            return checkpoint

        if checkpoint.get("cohort_capture") is None:
            parameters = {
                "keyword": HOLDOUT_QUERY,
                "searchTerm": HOLDOUT_QUERY,
                "country": HOLDOUT_MARKETPLACE,
                "page": 1,
                "pageSize": HOLDOUT_COHORT_PAGE_SIZE,
                "period": HOLDOUT_PERIOD,
                "sort": {"field": "traffic", "order": "desc"},
            }
            capture = self.capture_client.capture(
                operation="keyword_asin_analysis",
                canonical_field="relationship.keyword_to_product",
                parameters=parameters,
            )
            checkpoint["cohort_capture"] = _capture_record(
                capture,
                canonical_field="relationship.keyword_to_product",
            )
            checkpoint["cohort"] = list(select_holdout_cohort(capture.payload))
            self._save(checkpoint)

        asins = tuple(item["asin"] for item in checkpoint["cohort"])
        captured_asins = {
            item["source_asin"] for item in checkpoint["reverse_captures"]
        }
        for asin in asins:
            if asin in captured_asins:
                continue
            parameters = {
                "asin": asin,
                "country": HOLDOUT_MARKETPLACE,
                "page": 1,
                "pageSize": HOLDOUT_REVERSE_PAGE_SIZE,
                "period": HOLDOUT_PERIOD,
                "sort": {"field": "traffic", "order": "desc"},
            }
            capture = self.capture_client.capture(
                operation="asin_keywords",
                canonical_field="relationship.product_to_keyword",
                parameters=parameters,
            )
            record = _capture_record(
                capture,
                canonical_field="relationship.product_to_keyword",
            )
            record["source_asin"] = asin
            checkpoint["reverse_captures"].append(record)
            self._save(checkpoint)

        if self.include_enrichment and checkpoint.get("enrichment_capture") is None:
            discovery = replay_holdout_discovery(checkpoint)
            terms = [
                item.keyword_identity.raw_text
                for item in discovery.corpus.top_keywords[:30]
            ]
            capture = self.capture_client.capture(
                operation="keyword_info",
                canonical_field="keyword.search_volume",
                parameters={"country": HOLDOUT_MARKETPLACE, "searchTerms": terms},
            )
            checkpoint["enrichment_capture"] = _capture_record(
                capture,
                canonical_field="keyword.search_volume",
            )
            checkpoint["enrichment_selection"] = {
                "selection_rule": (
                    "Top 30 by ASIN coverage, provider traffic, organic rank, stable text"
                ),
                "query_origin": QueryOrigin.ASIN_REVERSE_RETURNED.value,
                "keywords": terms,
            }
            self._save(checkpoint)

        checkpoint["status"] = "COMPLETE"
        checkpoint["completed_at"] = _utc_now()
        self._save(checkpoint)
        return checkpoint

    def _load_or_initialize(self) -> dict[str, Any]:
        if self.checkpoint_path.exists():
            checkpoint = load_json_object(self.checkpoint_path)
            expected = {
                "contract_version": HOLDOUT_CONTRACT_VERSION,
                "baseline_commit": self.baseline_commit,
                "cohort_query": HOLDOUT_QUERY,
                "marketplace": HOLDOUT_MARKETPLACE,
                "period": HOLDOUT_PERIOD,
            }
            for key, value in expected.items():
                if checkpoint.get(key) != value:
                    raise ValueError(f"checkpoint {key} does not match requested run")
            if checkpoint.get("credit_plan") != self.credit_plan.to_dict():
                raise ValueError("checkpoint credit plan does not match requested run")
            return checkpoint
        return {
            "contract_version": HOLDOUT_CONTRACT_VERSION,
            "baseline_commit": self.baseline_commit,
            "retrieved_at": self.capture_client.retrieved_at,
            "created_at": _utc_now(),
            "completed_at": None,
            "status": "IN_PROGRESS",
            "cohort_query": HOLDOUT_QUERY,
            "marketplace": HOLDOUT_MARKETPLACE,
            "period": HOLDOUT_PERIOD,
            "category_scope": "Amazon US > Pet Supplies > Dog Travel Water Bottles",
            "credit_plan": self.credit_plan.to_dict(),
            "pilot_excluded_asins": sorted(SP032B_PILOT_ASINS),
            "cohort_capture": None,
            "cohort": [],
            "reverse_captures": [],
            "enrichment_capture": None,
            "enrichment_selection": None,
        }

    def _save(self, checkpoint: Mapping[str, Any]) -> None:
        _atomic_json_write(self.checkpoint_path, checkpoint)


class _CheckpointTransport:
    def __init__(self, captures: Sequence[Mapping[str, Any]]) -> None:
        self._responses: dict[tuple[str, str], Mapping[str, Any]] = {}
        for capture in captures:
            key = (
                str(capture["operation"]),
                canonical_json(capture["parameters"]),
            )
            if key in self._responses:
                raise ValueError(f"duplicate checkpoint response: {key[0]}")
            self._responses[key] = capture

    def execute(self, request: TransportRequest) -> TransportResponse:
        key = (request.operation, canonical_json(request.parameters))
        capture = self._responses.get(key)
        if capture is None:
            raise ProviderConnectorError(
                ProviderErrorCode.FIELD_UNAVAILABLE,
                "checkpoint has no response for this operation and parameter set",
                provider_id=request.provider_id,
                operation=request.operation,
            )
        return TransportResponse(
            status_code=200,
            payload=capture["payload"],
            metadata=capture.get("metadata", {}),
        )


def _checkpoint_capture_sequence(checkpoint: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    captures: list[Mapping[str, Any]] = []
    cohort = checkpoint.get("cohort_capture")
    if isinstance(cohort, Mapping):
        captures.append(cohort)
    reverse = checkpoint.get("reverse_captures")
    if isinstance(reverse, Sequence) and not isinstance(reverse, (str, bytes)):
        captures.extend(item for item in reverse if isinstance(item, Mapping))
    enrichment = checkpoint.get("enrichment_capture")
    if isinstance(enrichment, Mapping):
        captures.append(enrichment)
    return tuple(captures)


def replay_holdout_discovery(checkpoint: Mapping[str, Any]):
    cohort = checkpoint.get("cohort")
    if not isinstance(cohort, Sequence) or isinstance(cohort, (str, bytes)):
        raise ValueError("checkpoint cohort is missing")
    asins = tuple(str(item["asin"]) for item in cohort if isinstance(item, Mapping))
    if len(asins) != HOLDOUT_ASIN_COUNT:
        raise ValueError("checkpoint does not contain the required 100-ASIN cohort")
    reverse = checkpoint.get("reverse_captures")
    if not isinstance(reverse, Sequence) or len(reverse) != HOLDOUT_ASIN_COUNT:
        raise ValueError("checkpoint does not contain 100 reverse-keyword responses")
    first_reverse = reverse[0]
    if not isinstance(first_reverse, Mapping):
        raise ValueError("checkpoint reverse capture is invalid")
    reverse_operation = str(first_reverse.get("operation", "asin_keywords"))
    first_parameters = first_reverse.get("parameters")
    if not isinstance(first_parameters, Mapping):
        raise ValueError("checkpoint reverse parameters are invalid")
    window_parameters = {
        key: value
        for key, value in first_parameters.items()
        if key not in {"asin", "country", "page", "pageSize", "sort"}
    }
    client = XiYouLiveCaptureClient(
        environment={"XIYOU_API_KEY": "checkpoint-replay-only"},
        transport=_CheckpointTransport(_checkpoint_capture_sequence(checkpoint)),
        retrieved_at=str(checkpoint["retrieved_at"]),
    )
    return OrganicKeywordDiscoveryRunner(
        client,
        marketplace=str(checkpoint.get("marketplace", HOLDOUT_MARKETPLACE)),
        period=str(checkpoint.get("period", HOLDOUT_PERIOD)),
        page_size=HOLDOUT_REVERSE_PAGE_SIZE,
        max_pages=1,
        reverse_operation=reverse_operation,
        request_window_parameters=window_parameters,
    ).run(asins)


def _relation_analysis(discovery: Any) -> tuple[dict[str, Any], ...]:
    pipeline = BuyerNeedAnalysisPipelineV0_2(
        query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
    )
    rows = []
    for record in discovery.records:
        text = build_search_term_text_evidence(
            record.keyword_identity,
            demand_lineage=discovery.lineage_by_discovery_id[record.discovery_id],
        )
        analysis = pipeline.analyze(text)
        intent = analysis.intent_evidence.intent
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
                "intent_confidence": analysis.intent_evidence.confidence.value,
                "intent_rule_id": analysis.intent_evidence.matched_rule_id,
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


def _term_rank_index(discovery: Any) -> dict[str, tuple[Any, ...]]:
    return {
        item.keyword_identity.normalized_text: (
            -item.asin_coverage_count,
            -(
                Decimal(item.provider_traffic_sum)
                if item.provider_traffic_sum is not None
                else Decimal("-1")
            ),
            item.best_organic_rank if item.best_organic_rank is not None else 10**9,
            item.keyword_identity.normalized_text,
        )
        for item in discovery.corpus.top_keywords
    }


def build_precision_audit_candidates(
    relations: Sequence[Mapping[str, Any]],
    discovery: Any,
    *,
    need_count: int = 50,
    non_need_count: int = 30,
) -> tuple[dict[str, Any], ...]:
    """Select unique terms deterministically; NON_NEED selection is intent-stratified."""

    rank = _term_rank_index(discovery)
    by_term: dict[str, Mapping[str, Any]] = {}
    for row in relations:
        term = str(row["normalized_keyword"])
        current = by_term.get(term)
        if current is None or str(row["discovery_id"]) < str(current["discovery_id"]):
            by_term[term] = row

    need = sorted(
        (
            row
            for row in by_term.values()
            if row["intent"] == BuyerNeedQueryIntent.NEED_CANDIDATE.value
        ),
        key=lambda item: rank[str(item["normalized_keyword"])],
    )[:need_count]

    non_need_groups: dict[str, deque[Mapping[str, Any]]] = {}
    for intent in sorted(
        (item for item in BuyerNeedQueryIntent if item.is_non_need),
        key=lambda item: item.value,
    ):
        values = sorted(
            (row for row in by_term.values() if row["intent"] == intent.value),
            key=lambda item: rank[str(item["normalized_keyword"])],
        )
        non_need_groups[intent.value] = deque(values)
    non_need: list[Mapping[str, Any]] = []
    while len(non_need) < non_need_count and any(non_need_groups.values()):
        for intent in sorted(non_need_groups):
            if non_need_groups[intent] and len(non_need) < non_need_count:
                non_need.append(non_need_groups[intent].popleft())

    candidates = []
    for group, rows in (("NEED_CANDIDATE", need), ("NON_NEED", non_need)):
        for row in rows:
            candidates.append(
                {
                    "audit_group": group,
                    "discovery_id": row["discovery_id"],
                    "source_asin": row["source_asin"],
                    "keyword": row["keyword"],
                    "normalized_keyword": row["normalized_keyword"],
                    "predicted_intent": row["intent"],
                    "predicted_resolution": row["resolution"],
                    "predicted_needs": row["buyer_needs"],
                }
            )
    return tuple(candidates)


def _annotations_by_term(annotations: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if annotations is None:
        return {}
    terms = annotations.get("term_reviews", {})
    if not isinstance(terms, Mapping):
        raise ValueError("annotations.term_reviews must be an object")
    expanded = {str(term): dict(review) for term, review in terms.items() if isinstance(review, Mapping)}
    grouped = annotations.get("review_groups", {})
    if not isinstance(grouped, Mapping):
        raise ValueError("annotations.review_groups must be an object")

    def assign(group_name: str, target_key: str, allowed: frozenset[str]) -> None:
        values = grouped.get(group_name, {})
        if not isinstance(values, Mapping):
            raise ValueError(f"annotations.review_groups.{group_name} must be an object")
        for label, grouped_terms in values.items():
            if label not in allowed:
                raise ValueError(f"invalid {group_name} label: {label}")
            if isinstance(grouped_terms, (str, bytes)) or not isinstance(grouped_terms, Sequence):
                raise ValueError(f"{group_name}.{label} must be a term sequence")
            for term in grouped_terms:
                if not isinstance(term, str) or not term.strip():
                    raise ValueError(f"{group_name}.{label} contains an invalid term")
                review = expanded.setdefault(term, {})
                current = review.get(target_key)
                if current is not None and current != label:
                    raise ValueError(f"conflicting {target_key} labels for {term!r}")
                review[target_key] = label

    assign("precision_labels", "precision_label", _PRECISION_LABELS)
    assign("unknown_categories", "unknown_category", _UNKNOWN_CATEGORIES)
    for group_name, target_key in (
        ("integrated_bowl_labels", "integrated_bowl_label"),
        ("collapsible_labels", "collapsible_label"),
        ("crate_labels", "crate_label"),
        ("insulated_labels", "insulated_label"),
    ):
        assign(group_name, target_key, _SPECIAL_LABELS)
    defaults = annotations.get("reason_defaults", {})
    if isinstance(defaults, Mapping):
        for review in expanded.values():
            if "precision_label" in review and "precision_reason" not in review:
                review["precision_reason"] = defaults.get(review["precision_label"])
            if "unknown_category" in review and "unknown_reason" not in review:
                review["unknown_reason"] = defaults.get(review["unknown_category"])
    return expanded


def _precision_result(
    audit_candidates: Sequence[Mapping[str, Any]],
    annotations: Mapping[str, Any] | None,
) -> dict[str, Any]:
    term_reviews = _annotations_by_term(annotations)
    rows = []
    for candidate in audit_candidates:
        review = term_reviews.get(candidate["normalized_keyword"], {})
        if not isinstance(review, Mapping):
            review = {}
        label = review.get("precision_label")
        if label is not None and label not in _PRECISION_LABELS:
            raise ValueError(f"invalid precision label: {label}")
        rows.append(
            {
                **dict(candidate),
                "manual_label": label or "UNREVIEWED",
                "manual_reason": review.get("precision_reason"),
            }
        )
    summary: dict[str, Any] = {}
    for group in ("NEED_CANDIDATE", "NON_NEED"):
        selected = tuple(item for item in rows if item["audit_group"] == group)
        correct = sum(item["manual_label"] == "CORRECT" for item in selected)
        incorrect = sum(item["manual_label"] == "INCORRECT" for item in selected)
        ambiguous = sum(item["manual_label"] == "AMBIGUOUS" for item in selected)
        unreviewed = sum(item["manual_label"] == "UNREVIEWED" for item in selected)
        denominator = correct + incorrect
        summary[group] = {
            "selected_count": len(selected),
            "correct_count": correct,
            "incorrect_count": incorrect,
            "ambiguous_count": ambiguous,
            "unreviewed_count": unreviewed,
            "precision": _share(correct, denominator) if denominator else None,
            "precision_denominator": denominator,
            "note": "AMBIGUOUS and UNREVIEWED are excluded from the precision denominator.",
        }
    return {"summary": summary, "items": rows}


def _special_review(
    relations: Sequence[Mapping[str, Any]],
    *,
    taxonomy_need_id: str,
    review_key: str,
    annotations: Mapping[str, Any] | None,
) -> dict[str, Any]:
    supporting = tuple(
        row
        for row in relations
        if any(
            need.get("taxonomy_need_id") == taxonomy_need_id
            and need.get("status") == BuyerNeedCandidateStatus.CANDIDATE.value
            for need in row["buyer_needs"]
        )
    )
    term_reviews = _annotations_by_term(annotations)
    reviewed = []
    for row in supporting:
        review = term_reviews.get(row["normalized_keyword"], {})
        label = review.get(review_key) if isinstance(review, Mapping) else None
        if label is not None and label not in _SPECIAL_LABELS:
            raise ValueError(f"invalid {review_key}: {label}")
        reviewed.append({**dict(row), "manual_label": label or "UNREVIEWED"})
    true_positive = sum(item["manual_label"] == "TRUE_POSITIVE" for item in reviewed)
    false_positive = sum(item["manual_label"] == "FALSE_POSITIVE" for item in reviewed)
    ambiguous = sum(item["manual_label"] == "AMBIGUOUS" for item in reviewed)
    denominator = true_positive + false_positive
    return {
        "relation_count": len(supporting),
        "source_asin_count": len({item["source_asin"] for item in supporting}),
        "asin_coverage": _share(
            len({item["source_asin"] for item in supporting}), HOLDOUT_ASIN_COUNT
        ),
        "expressions": sorted({str(item["keyword"]) for item in supporting}),
        "true_positive_count": true_positive,
        "false_positive_count": false_positive,
        "ambiguous_count": ambiguous,
        "unreviewed_count": sum(item["manual_label"] == "UNREVIEWED" for item in reviewed),
        "precision": _share(true_positive, denominator) if denominator else None,
        "items": reviewed,
    }


def _insulated_review(
    relations: Sequence[Mapping[str, Any]],
    annotations: Mapping[str, Any] | None,
) -> dict[str, Any]:
    rows = tuple(
        row for row in relations if re.search(r"\binsulat\w*\b", str(row["normalized_keyword"]))
    )
    term_reviews = _annotations_by_term(annotations)
    reviewed = []
    for row in rows:
        term = str(row["normalized_keyword"])
        review = term_reviews.get(term, {})
        label = review.get("insulated_label") if isinstance(review, Mapping) else None
        if label is not None and label not in _SPECIAL_LABELS:
            raise ValueError(f"invalid insulated_label: {label}")
        dog_related = bool(re.search(r"\b(dog|dogs|puppy|pet|canine)\b", term))
        branded = row["intent"] == BuyerNeedQueryIntent.BRAND_MODEL.value
        reviewed.append(
            {
                **dict(row),
                "expression_class": (
                    "BRANDED" if branded else "DOG_RELATED" if dog_related else "GENERIC"
                ),
                "manual_label": label or "UNREVIEWED",
            }
        )
    counts = Counter(item["expression_class"] for item in reviewed)
    true_positive = sum(item["manual_label"] == "TRUE_POSITIVE" for item in reviewed)
    false_positive = sum(item["manual_label"] == "FALSE_POSITIVE" for item in reviewed)
    if rows and not any(item["manual_label"] == "UNREVIEWED" for item in reviewed):
        dog_asins = {
            item["source_asin"]
            for item in reviewed
            if item["expression_class"] == "DOG_RELATED"
            and item["manual_label"] == "TRUE_POSITIVE"
        }
        if len(dog_asins) >= 3 and false_positive == 0:
            judgement = "PROMOTE_CANDIDATE"
        elif true_positive == 0 and false_positive > 0:
            judgement = "REJECT"
        else:
            judgement = "KEEP_PROPOSAL"
    else:
        judgement = "KEEP_PROPOSAL"
    return {
        "relation_count": len(rows),
        "source_asin_count": len({item["source_asin"] for item in rows}),
        "asin_coverage": _share(len({item["source_asin"] for item in rows}), HOLDOUT_ASIN_COUNT),
        "exact_dog_related_relation_count": counts["DOG_RELATED"],
        "generic_relation_count": counts["GENERIC"],
        "branded_relation_count": counts["BRANDED"],
        "false_positive_count": false_positive,
        "unreviewed_count": sum(item["manual_label"] == "UNREVIEWED" for item in reviewed),
        "judgement": judgement,
        "items": reviewed,
    }


def _outdoor_bias(relations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    # Mirror the frozen v0.2 taxonomy expressions exactly for an apples-to-apples
    # raw-corpus check; this is an audit detector, not a new classification rule.
    pattern = re.compile(
        r"\b(portable|travel(?:s|ed|ing|led|ling)?|walk(?:s|ed|ing)?|hik(?:e|es|ed|ing))\b",
        re.IGNORECASE,
    )
    raw = tuple(row for row in relations if pattern.search(str(row["normalized_keyword"])))
    matched_need = tuple(row for row in relations if row["resolution"] == "RESOLVED_BUYER_NEED")
    outdoor_labels = {"portable", "travel", "walking", "outdoor hiking"}
    matched_outdoor = tuple(
        row
        for row in matched_need
        if any(need.get("need_label") in outdoor_labels for need in row["buyer_needs"])
    )
    asins = {row["source_asin"] for row in raw}
    return {
        "matched_need_relation_count": len(matched_need),
        "outdoor_matched_need_relation_count": len(matched_outdoor),
        "outdoor_share_within_matched_need_relations": _share(
            len(matched_outdoor), len(matched_need)
        ),
        "raw_organic_relation_count": len(relations),
        "outdoor_raw_organic_relation_count": len(raw),
        "outdoor_share_within_raw_organic_relations": _share(len(raw), len(relations)),
        "outdoor_source_asin_count": len(asins),
        "outdoor_source_asin_coverage": _share(len(asins), HOLDOUT_ASIN_COUNT),
        "judgement": (
            "DATA_DRIVEN_DOMINANCE"
            if len(raw) == len(matched_outdoor) and len(asins) > 0
            else "TAXONOMY_COVERAGE_BIAS"
        ),
        "note": "ASIN coverage is cohort recurrence, not Demand Share.",
    }


def _unknown_audit(
    relations: Sequence[Mapping[str, Any]],
    annotations: Mapping[str, Any] | None,
    *,
    pilot_unknown_terms: frozenset[str],
) -> dict[str, Any]:
    unknown_rows = tuple(
        row
        for row in relations
        if row["resolution"] in {"UNKNOWN_NEED_CANDIDATE", "AMBIGUOUS"}
    )
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in unknown_rows:
        grouped[str(row["normalized_keyword"])].append(row)
    term_reviews = _annotations_by_term(annotations)
    terms = []
    for term in sorted(grouped):
        review = term_reviews.get(term, {})
        category = review.get("unknown_category") if isinstance(review, Mapping) else None
        if category is not None and category not in _UNKNOWN_CATEGORIES:
            raise ValueError(f"invalid unknown category: {category}")
        rows = grouped[term]
        terms.append(
            {
                "normalized_keyword": term,
                "raw_expressions": sorted({str(item["keyword"]) for item in rows}),
                "relation_count": len(rows),
                "source_asin_count": len({item["source_asin"] for item in rows}),
                "new_vs_20_asin_pilot": term not in pilot_unknown_terms,
                "category": category or "UNREVIEWED",
                "reason": review.get("unknown_reason") if isinstance(review, Mapping) else None,
                "discovery_ids": sorted(str(item["discovery_id"]) for item in rows),
            }
        )
    return {
        "relation_count": len(unknown_rows),
        "unique_term_count": len(grouped),
        "new_unique_term_count": sum(item["new_vs_20_asin_pilot"] for item in terms),
        "unreviewed_unique_term_count": sum(item["category"] == "UNREVIEWED" for item in terms),
        "category_distribution": dict(
            sorted(Counter(item["category"] for item in terms).items())
        ),
        "terms": terms,
    }


def _keyword_enrichment(checkpoint: Mapping[str, Any], discovery: Any) -> dict[str, Any]:
    stored = checkpoint.get("enrichment_capture")
    if not isinstance(stored, Mapping):
        return {"executed": False, "items": []}
    client = XiYouLiveCaptureClient(
        environment={"XIYOU_API_KEY": "checkpoint-replay-only"},
        transport=_CheckpointTransport((stored,)),
        retrieved_at=str(checkpoint["retrieved_at"]),
    )
    capture = client.capture(
        operation="keyword_info",
        canonical_field="keyword.search_volume",
        parameters=stored["parameters"],
    )
    items = []
    for summary in discovery.corpus.top_keywords[:30]:
        keyword = summary.keyword_identity
        try:
            snapshot = DemandIntelligenceBuilderV0_1().build(
                DemandIntelligenceRequest(
                    target_keyword_identity=keyword,
                    canonical_bundles=(capture.bundle,),
                )
            )
        except Exception:
            metrics: dict[str, str | None] = {}
            evidence_ids: tuple[str, ...] = ()
        else:
            metrics = {}
            evidence_ids = []
            for evidence_set in snapshot.keyword_metric_evidence_sets:
                values = [
                    item.value.normalized_value
                    for item in evidence_set.candidates
                    if item.value.presence_status.value == "PRESENT"
                    and item.value.normalized_value is not None
                ]
                value = str(values[0]) if values else None
                metrics[evidence_set.metric] = value
                evidence_ids.append(evidence_set.metric_evidence_set_id)
            evidence_ids = tuple(sorted(evidence_ids))
        items.append(
            {
                "keyword": keyword.raw_text,
                "normalized_keyword": keyword.normalized_text,
                "query_origin": QueryOrigin.ASIN_REVERSE_RETURNED.value,
                "search_volume": metrics.get("search_volume"),
                "aba_rank": metrics.get("aba_search_frequency_rank"),
                "cpc": metrics.get("cpc"),
                "difficulty": metrics.get("competition_difficulty"),
                "source_evidence_ids": list(evidence_ids),
            }
        )
    return {"executed": True, "items": items}


def _pilot_unknown_terms(pilot_snapshot: Mapping[str, Any] | None) -> frozenset[str]:
    if pilot_snapshot is None:
        return frozenset()
    from .replay_v0_2 import replay_buyer_need_taxonomy_v0_2

    replay = replay_buyer_need_taxonomy_v0_2(pilot_snapshot)
    return frozenset(
        relation.analysis_result.intent_evidence.source_evidence.normalized_text
        for relation in replay.relations
        if relation.analysis_result.intent_evidence.intent is BuyerNeedQueryIntent.AMBIGUOUS
        or (
            relation.analysis_result.intent_evidence.intent
            is BuyerNeedQueryIntent.NEED_CANDIDATE
            and not any(
                candidate.status is BuyerNeedCandidateStatus.CANDIDATE
                for candidate in relation.analysis_result.buyer_need_candidates
            )
        )
    )


def _credit_audit(checkpoint: Mapping[str, Any]) -> dict[str, Any]:
    captures = _checkpoint_capture_sequence(checkpoint)
    calls = []
    known_total = 0
    unknown = 0
    for capture in captures:
        cost = _integer(capture.get("cost_credits"))
        if cost is None:
            unknown += 1
        else:
            known_total += cost
        calls.append(
            {
                "operation": capture["operation"],
                "parameters": capture["parameters"],
                "source_asin": capture.get("source_asin"),
                "returned_rows": len(_response_rows(capture["payload"])),
                "provider_total": _response_total(capture["payload"]),
                "request_ref": capture.get("request_ref"),
                "response_ref": capture.get("response_ref"),
                "credits": cost,
                "x_cost_credits": capture.get("x_cost_credits"),
            }
        )
    return {
        "request_count": len(captures),
        "known_credits": known_total,
        "unknown_credit_call_count": unknown,
        "estimated_credits": checkpoint["credit_plan"]["estimated_total_credits"],
        "gate_credits": checkpoint["credit_plan"]["gate_credits"],
        "calls": calls,
    }


def _top_keywords(discovery: Any, limit: int = 100) -> list[dict[str, Any]]:
    return [
        {
            "keyword": item.keyword_identity.raw_text,
            "normalized_keyword": item.keyword_identity.normalized_text,
            "relation_count": item.relation_count,
            "asin_coverage_count": item.asin_coverage_count,
            "asin_coverage_share": item.asin_coverage_share,
            "provider_traffic_sum": item.provider_traffic_sum,
            "best_organic_rank": item.best_organic_rank,
            "discovery_ids": list(item.discovery_ids),
        }
        for item in discovery.corpus.top_keywords[:limit]
    ]


def _semantic_clusters(relations: Sequence[Mapping[str, Any]], discovery: Any) -> list[dict[str, Any]]:
    pipeline = BuyerNeedAnalysisPipelineV0_2(
        query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
    )
    needs = []
    need_to_relation: dict[str, Mapping[str, Any]] = {}
    records = {item.discovery_id: item for item in discovery.records}
    for row in relations:
        record = records[row["discovery_id"]]
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
        source = [need_to_relation[item] for item in cluster.source_need_ids]
        rows.append(
            {
                "cluster_id": cluster.cluster_id,
                "cluster_label": cluster.cluster_label,
                "need_count": len(cluster.source_need_ids),
                "relation_count": len({item["discovery_id"] for item in source}),
                "source_asin_count": len({item["source_asin"] for item in source}),
                "asin_coverage": _share(
                    len({item["source_asin"] for item in source}), HOLDOUT_ASIN_COUNT
                ),
                "expressions": sorted({str(item["keyword"]) for item in source}),
                "source_need_ids": list(cluster.source_need_ids),
            }
        )
    return sorted(rows, key=lambda item: (-item["source_asin_count"], item["cluster_label"]))


def analyze_holdout_checkpoint(
    checkpoint: Mapping[str, Any],
    *,
    annotations: Mapping[str, Any] | None = None,
    pilot_snapshot: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Replay saved evidence through unchanged V0.2 code and compute validation results."""

    if checkpoint.get("status") != "COMPLETE":
        raise ValueError("holdout checkpoint must be complete before analysis")
    discovery = replay_holdout_discovery(checkpoint)
    relations = _relation_analysis(discovery)
    intent_distribution = dict(sorted(Counter(row["intent"] for row in relations).items()))
    resolution_distribution = dict(
        sorted(Counter(row["resolution"] for row in relations).items())
    )
    resolved_need = resolution_distribution.get("RESOLVED_BUYER_NEED", 0)
    non_need = resolution_distribution.get("EXPLICIT_NON_NEED", 0)
    ambiguous = resolution_distribution.get("AMBIGUOUS", 0)
    unknown = resolution_distribution.get("UNKNOWN_NEED_CANDIDATE", 0)
    total = len(relations)
    audit_candidates = build_precision_audit_candidates(relations, discovery)
    precision = _precision_result(audit_candidates, annotations)
    pilot_unknown = _pilot_unknown_terms(pilot_snapshot)
    unknown_audit = _unknown_audit(
        relations,
        annotations,
        pilot_unknown_terms=pilot_unknown,
    )
    bowl = _special_review(
        relations,
        taxonomy_need_id=INTEGRATED_BOWL_ENTRY_V0_2.taxonomy_need_id,
        review_key="integrated_bowl_label",
        annotations=annotations,
    )
    bowl_precision = _decimal_or_none(bowl["precision"])
    if bowl["unreviewed_count"]:
        bowl["judgement"] = "WEAK"
    elif bowl["relation_count"] == 0:
        bowl["judgement"] = "WEAK"
    elif bowl_precision is not None and bowl_precision >= Decimal("0.9"):
        bowl["judgement"] = "CONFIRMED"
    else:
        bowl["judgement"] = "FAILED"

    collapsible = _special_review(
        relations,
        taxonomy_need_id=COLLAPSIBLE_STRUCTURE_ENTRY_V0_2.taxonomy_need_id,
        review_key="collapsible_label",
        annotations=annotations,
    )
    collapse_raw = tuple(
        row for row in relations if "collaps" in str(row["normalized_keyword"])
    )
    collapse_relevant = sum(
        _annotations_by_term(annotations)
        .get(row["normalized_keyword"], {})
        .get("collapsible_label")
        == "TRUE_POSITIVE"
        for row in collapse_raw
    )
    collapsible["raw_collapsible_relation_count"] = len(collapse_raw)
    collapsible["recall_observation"] = (
        _share(collapsible["true_positive_count"], collapse_relevant)
        if collapse_relevant
        else None
    )

    crate = _special_review(
        relations,
        taxonomy_need_id=CRATE_COMPATIBILITY_EXPERIMENT_V0_2.taxonomy_need_id,
        review_key="crate_label",
        annotations=annotations,
    )
    crate_precision = _decimal_or_none(crate["precision"])
    crate["judgement"] = (
        "PROMOTE_CANDIDATE"
        if crate["source_asin_count"] >= 3
        and crate_precision is not None
        and crate_precision >= Decimal("0.9")
        and crate["unreviewed_count"] == 0
        else "KEEP_EXPERIMENTAL"
    )
    insulated = _insulated_review(relations, annotations)
    outdoor = _outdoor_bias(relations)

    need_precision = _decimal_or_none(
        precision["summary"]["NEED_CANDIDATE"]["precision"]
    )
    non_need_precision = _decimal_or_none(
        precision["summary"]["NON_NEED"]["precision"]
    )
    audit_complete = (
        precision["summary"]["NEED_CANDIDATE"]["selected_count"] >= 50
        and precision["summary"]["NON_NEED"]["selected_count"] >= 30
        and precision["summary"]["NEED_CANDIDATE"]["unreviewed_count"] == 0
        and precision["summary"]["NON_NEED"]["unreviewed_count"] == 0
        and unknown_audit["unreviewed_unique_term_count"] == 0
        and bowl["unreviewed_count"] == 0
        and collapsible["unreviewed_count"] == 0
        and crate["unreviewed_count"] == 0
        and insulated["unreviewed_count"] == 0
    )
    independence = not (
        {item["asin"] for item in checkpoint["cohort"]} & SP032B_PILOT_ASINS
    )
    true_resolution_rate = _share(resolved_need + non_need, total)
    unresolved_rate = _share(unknown + ambiguous, total)
    success = {
        "holdout_independent": independence,
        "true_need_resolution_rate_gte_85pct": Decimal(true_resolution_rate) >= Decimal("0.85"),
        "buyer_need_unresolved_rate_lte_30pct": Decimal(unresolved_rate) <= Decimal("0.30"),
        "need_precision_gte_90pct": need_precision is not None and need_precision >= Decimal("0.90"),
        "non_need_precision_gte_90pct": (
            non_need_precision is not None and non_need_precision >= Decimal("0.90")
        ),
        "integrated_bowl_independently_addressed": bowl["judgement"] in {"CONFIRMED", "WEAK"},
        "collapsible_precision_not_collapsed": (
            collapsible["relation_count"] == 0
            or (
                _decimal_or_none(collapsible["precision"]) is not None
                and _decimal_or_none(collapsible["precision"]) >= Decimal("0.90")
            )
        ),
        "lineage_complete": all(
            row["provider_request_ref"] and row["provider_response_ref"] for row in relations
        ),
        "manual_audit_complete": audit_complete,
    }
    if not audit_complete or len(checkpoint["cohort"]) != HOLDOUT_ASIN_COUNT:
        judgement = "INSUFFICIENT_EVIDENCE"
    elif not all(
        success[key]
        for key in (
            "holdout_independent",
            "true_need_resolution_rate_gte_85pct",
            "buyer_need_unresolved_rate_lte_30pct",
            "need_precision_gte_90pct",
            "non_need_precision_gte_90pct",
            "lineage_complete",
        )
    ):
        judgement = "TAXONOMY_V0_2_OVERFIT"
    elif not success["collapsible_precision_not_collapsed"] or bowl["judgement"] == "FAILED":
        judgement = "TAXONOMY_V0_2_PARTIALLY_GENERALIZES"
    else:
        judgement = "TAXONOMY_V0_2_GENERALIZES"

    corpus = discovery.corpus
    payload = {
        "contract_version": HOLDOUT_CONTRACT_VERSION,
        "analysis_id": None,
        "baseline_commit": checkpoint["baseline_commit"],
        "category_scope": checkpoint["category_scope"],
        "marketplace": checkpoint["marketplace"],
        "period": checkpoint["period"],
        "cohort_query": checkpoint["cohort_query"],
        "cohort_selection_method": (
            "XiYou keyword_asin_analysis page 1, last7days, traffic descending; "
            "preserve provider response order, deduplicate ASIN, exclude frozen SP-032B 20-ASIN "
            "set, take first 100 without handpicking."
        ),
        "cohort": checkpoint["cohort"],
        "pilot_excluded_asins": checkpoint["pilot_excluded_asins"],
        "cohort_provider_total": _response_total(checkpoint["cohort_capture"]["payload"]),
        "credit_audit": _credit_audit(checkpoint),
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
        "buyer_need_resolution": {
            "resolved_buyer_need_relations": resolved_need,
            "explicit_non_need_relations": non_need,
            "unknown_need_candidate_relations": unknown,
            "ambiguous_relations": ambiguous,
            "true_need_resolution_count": resolved_need + non_need,
            "true_need_resolution_rate": true_resolution_rate,
            "buyer_need_unresolved_rate": unresolved_rate,
            "non_need_share": _share(non_need, total),
            "note": "NON_NEED is resolution coverage, not Buyer Need coverage.",
        },
        "semantic_clusters": _semantic_clusters(relations, discovery),
        "precision_audit": precision,
        "integrated_bowl_validation": bowl,
        "collapsible_validation": collapsible,
        "crate_validation": crate,
        "insulated_validation": insulated,
        "outdoor_portability_bias": outdoor,
        "unknown_audit": unknown_audit,
        "keyword_enrichment": _keyword_enrichment(checkpoint, discovery),
        "relations": list(relations),
        "success_criteria": success,
        "generalization_judgement": judgement,
        "limitations": [
            "Only first-page/top-20 reverse keywords per ASIN were captured.",
            "ASIN coverage is recurrence in this cohort and is not Demand Share.",
            "Provider traffic semantics remain provider-defined and uncalibrated.",
            "Parent ASIN is UNKNOWN whenever the forward response omits it.",
            "Manual precision is a structured term audit, not Amazon behavioral ground truth.",
        ],
        "next_step_unique_recommendation": (
            "Keep v0.2 frozen and run a second independent time-window holdout before any "
            "taxonomy promotion or rule change."
        ),
    }
    identity_payload = dict(payload)
    identity_payload.pop("analysis_id")
    payload["analysis_id"] = deterministic_id("organic-buyer-need-holdout-analysis", identity_payload)
    return payload


__all__ = (
    "HOLDOUT_ASIN_COUNT",
    "HOLDOUT_CONTRACT_VERSION",
    "HOLDOUT_CREDIT_GATE",
    "SP032B_PILOT_ASINS",
    "HoldoutCreditPlan",
    "OrganicHoldoutLiveCaptureV0_1",
    "analyze_holdout_checkpoint",
    "build_precision_audit_candidates",
    "load_json_object",
    "replay_holdout_discovery",
    "select_holdout_cohort",
)
