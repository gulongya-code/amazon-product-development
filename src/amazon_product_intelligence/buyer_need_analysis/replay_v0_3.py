"""Offline-only V0.2 versus V0.3 intent replay for saved holdout artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
import re
from typing import Any

from amazon_product_intelligence.contracts import KeywordIdentity, keyword_id
from amazon_product_intelligence.normalization import normalize_keyword_text

from .builder_v0_2 import BuyerNeedAnalysisPipelineV0_2
from .builder_v0_3 import BuyerNeedAnalysisPipelineV0_3
from .models import BuyerNeedCandidateStatus, build_search_term_text_evidence
from .models_v0_2 import (
    BUYER_NEED_INTENT_RULESET_VERSION,
    BuyerNeedQueryIntent,
    BuyerNeedQueryScope,
)
from .models_v0_3 import BUYER_NEED_INTENT_RULESET_VERSION_V0_3


_OUTDOOR_PATTERNS = {
    "portable": r"\bportable\b",
    "travel": r"\btravel\b",
    "walking": r"\bwalk(?:ing|s)?\b",
    "hiking": r"\bhiking\b",
}
_TARGET_CATEGORY = re.compile(r"\b(?:dogs?|doggy|pupp(?:y|ies)|pets?)\b", re.IGNORECASE)
_TARGET_PRODUCT = re.compile(
    r"\b(?:water\s+)?(?:bottles?|bowls?|dispensers?)\b",
    re.IGNORECASE,
)


def _ratio(numerator: int, denominator: int) -> str | None:
    if denominator == 0:
        return None
    return format(Decimal(numerator) / Decimal(denominator), "f")


def _evidence(
    keyword: str,
    *,
    marketplace: str,
    locale: str,
):
    normalized = normalize_keyword_text(keyword)
    identity = KeywordIdentity(
        keyword_id=keyword_id(marketplace, locale, normalized),
        marketplace=marketplace,
        locale=locale,
        normalized_text=normalized,
        raw_text=keyword,
    )
    return build_search_term_text_evidence(identity)


def _prediction(intent: BuyerNeedQueryIntent) -> str:
    if intent is BuyerNeedQueryIntent.NEED_CANDIDATE:
        return "NEED_CANDIDATE"
    if intent.is_non_need:
        return "NON_NEED"
    return "AMBIGUOUS"


def _truth(item: Mapping[str, Any]) -> str | None:
    group = item.get("audit_group")
    label = item.get("manual_label")
    if label not in {"CORRECT", "INCORRECT"}:
        return None
    if group == "NEED_CANDIDATE":
        return "NEED_CANDIDATE" if label == "CORRECT" else "NON_NEED"
    if group == "NON_NEED":
        return "NON_NEED" if label == "CORRECT" else "NEED_CANDIDATE"
    raise ValueError(f"unsupported precision audit group: {group}")


def _metrics(rows: Sequence[Mapping[str, Any]], prediction_key: str) -> dict[str, Any]:
    evaluated = tuple(item for item in rows if item["truth"] is not None)
    true_need = sum(item["truth"] == "NEED_CANDIDATE" for item in evaluated)
    true_non_need = sum(item["truth"] == "NON_NEED" for item in evaluated)
    predicted_need = sum(item[prediction_key] == "NEED_CANDIDATE" for item in evaluated)
    predicted_non_need = sum(item[prediction_key] == "NON_NEED" for item in evaluated)
    predicted_ambiguous = sum(item[prediction_key] == "AMBIGUOUS" for item in evaluated)
    true_positive = sum(
        item["truth"] == "NEED_CANDIDATE" and item[prediction_key] == "NEED_CANDIDATE"
        for item in evaluated
    )
    false_positive = sum(
        item["truth"] == "NON_NEED" and item[prediction_key] == "NEED_CANDIDATE"
        for item in evaluated
    )
    true_negative = sum(
        item["truth"] == "NON_NEED" and item[prediction_key] == "NON_NEED"
        for item in evaluated
    )
    false_negative = sum(
        item["truth"] == "NEED_CANDIDATE" and item[prediction_key] != "NEED_CANDIDATE"
        for item in evaluated
    )
    resolved_true_need = sum(
        item["truth"] == "NEED_CANDIDATE"
        and item[prediction_key] == "NEED_CANDIDATE"
        and item[f"{prediction_key}_resolved"]
        for item in evaluated
    )
    return {
        "evaluated_count": len(evaluated),
        "true_need_count": true_need,
        "true_non_need_count": true_non_need,
        "predicted_need_count": predicted_need,
        "predicted_non_need_count": predicted_non_need,
        "predicted_ambiguous_count": predicted_ambiguous,
        "true_positive_count": true_positive,
        "false_positive_count": false_positive,
        "true_negative_count": true_negative,
        "false_negative_count": false_negative,
        "need_precision": _ratio(true_positive, predicted_need),
        "non_need_precision": _ratio(true_negative, predicted_non_need),
        "need_recall_proxy": _ratio(true_positive, true_need),
        "true_need_resolution_count": resolved_true_need,
        "true_need_resolution_rate": _ratio(resolved_true_need, true_need),
        "note": (
            "Historical annotation replay only. AMBIGUOUS labels are excluded; recall is a "
            "proxy over the V0.2-selected audit sample, not population recall."
        ),
    }


def replay_intent_precision_v0_3(
    snapshot: Mapping[str, Any],
    *,
    query_scope: BuyerNeedQueryScope = BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,
) -> dict[str, Any]:
    """Replay a saved precision audit without connector or API dependencies."""

    if not isinstance(snapshot, Mapping):
        raise ValueError("intent replay requires a snapshot mapping")
    precision = snapshot.get("precision_audit")
    if not isinstance(precision, Mapping):
        raise ValueError("snapshot precision_audit is required")
    items = precision.get("items")
    if isinstance(items, (str, bytes)) or not isinstance(items, Sequence):
        raise ValueError("snapshot precision_audit.items must be a sequence")
    marketplace = str(snapshot.get("marketplace", "US"))
    locale = "en-us"
    v02 = BuyerNeedAnalysisPipelineV0_2(query_scope=query_scope)
    v03 = BuyerNeedAnalysisPipelineV0_3(query_scope=query_scope)
    rows = []
    for item in sorted(items, key=lambda value: str(value.get("discovery_id", ""))):
        if not isinstance(item, Mapping):
            raise ValueError("precision audit item must be an object")
        keyword = str(item.get("keyword", ""))
        evidence = _evidence(keyword, marketplace=marketplace, locale=locale)
        before = v02.analyze(evidence)
        after = v03.analyze(evidence)
        before_intent = before.intent_evidence.intent
        after_intent = after.intent_evidence.primary_intent
        recorded_intent = item.get("predicted_intent")
        if recorded_intent != before_intent.value:
            raise ValueError(
                f"V0.2 replay drift for {keyword!r}: {before_intent.value} != {recorded_intent}"
            )
        rows.append(
            {
                "discovery_id": str(item.get("discovery_id", "")),
                "source_asin": str(item.get("source_asin", "")),
                "keyword": keyword,
                "manual_label": str(item.get("manual_label", "")),
                "audit_group": str(item.get("audit_group", "")),
                "truth": _truth(item),
                "v0_2_prediction": _prediction(before_intent),
                "v0_2_intent": before_intent.value,
                "v0_2_prediction_resolved": any(
                    candidate.status is BuyerNeedCandidateStatus.CANDIDATE
                    for candidate in before.buyer_need_candidates
                ),
                "v0_3_prediction": _prediction(after_intent),
                "v0_3_intent": after_intent.value,
                "v0_3_boundary": after.intent_evidence.boundary.value,
                "v0_3_secondary_need_signals": list(
                    after.intent_evidence.secondary_need_signals
                ),
                "v0_3_prediction_resolved": any(
                    candidate.status is BuyerNeedCandidateStatus.CANDIDATE
                    for candidate in after.buyer_need_candidates
                ),
            }
        )
    return {
        "baseline_commit": snapshot.get("baseline_commit"),
        "source_analysis_id": snapshot.get("analysis_id"),
        "query_scope": query_scope.value,
        "v0_2_ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION,
        "v0_3_ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
        "v0_2": _metrics(rows, "v0_2_prediction"),
        "v0_3": _metrics(rows, "v0_3_prediction"),
        "rows": rows,
    }


def replay_intent_regressions_v0_3(
    snapshot: Mapping[str, Any],
    *,
    query_scope: BuyerNeedQueryScope = BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,
) -> dict[str, Any]:
    """Measure routing retention for stable Integrated Bowl and outdoor expressions."""

    relations = snapshot.get("relations")
    if isinstance(relations, (str, bytes)) or not isinstance(relations, Sequence):
        raise ValueError("snapshot relations must be a sequence")
    marketplace = str(snapshot.get("marketplace", "US"))
    pipeline = BuyerNeedAnalysisPipelineV0_3(query_scope=query_scope)
    integrated_baseline = 0
    integrated_retained = 0
    outdoor = {
        term: {
            "v0_2_need_count": 0,
            "v0_3_need_count": 0,
            "target_context_count": 0,
            "target_context_retained_count": 0,
        }
        for term in _OUTDOOR_PATTERNS
    }
    for relation in relations:
        if not isinstance(relation, Mapping):
            raise ValueError("snapshot relation must be an object")
        keyword = str(relation.get("keyword", ""))
        normalized = normalize_keyword_text(keyword)
        before_intent = str(relation.get("intent", ""))
        original_needs = relation.get("buyer_needs", ())
        if isinstance(original_needs, (str, bytes)) or not isinstance(original_needs, Sequence):
            raise ValueError("snapshot relation buyer_needs must be a sequence")
        integrated = any(
            isinstance(item, Mapping)
            and item.get("need_label") == "Integrated Bowl"
            and item.get("status") == BuyerNeedCandidateStatus.CANDIDATE.value
            for item in original_needs
        )
        relevant_terms = tuple(
            term
            for term, pattern in _OUTDOOR_PATTERNS.items()
            if re.search(pattern, normalized, flags=re.IGNORECASE)
            and before_intent == BuyerNeedQueryIntent.NEED_CANDIDATE.value
        )
        if not integrated and not relevant_terms:
            continue
        after = pipeline.analyze(_evidence(keyword, marketplace=marketplace, locale="en-us"))
        after_is_need = (
            after.intent_evidence.primary_intent is BuyerNeedQueryIntent.NEED_CANDIDATE
        )
        if integrated:
            integrated_baseline += 1
            if any(
                candidate.need_label == "Integrated Bowl"
                and candidate.status is BuyerNeedCandidateStatus.CANDIDATE
                for candidate in after.buyer_need_candidates
            ):
                integrated_retained += 1
        for term in relevant_terms:
            outdoor[term]["v0_2_need_count"] += 1
            if after_is_need:
                outdoor[term]["v0_3_need_count"] += 1
            if _TARGET_CATEGORY.search(normalized) and _TARGET_PRODUCT.search(normalized):
                outdoor[term]["target_context_count"] += 1
                if after_is_need:
                    outdoor[term]["target_context_retained_count"] += 1
    for counts in outdoor.values():
        counts["routing_recall"] = _ratio(
            counts["v0_3_need_count"], counts["v0_2_need_count"]
        )
        counts["target_context_routing_recall"] = _ratio(
            counts["target_context_retained_count"], counts["target_context_count"]
        )
    return {
        "integrated_bowl": {
            "v0_2_candidate_count": integrated_baseline,
            "v0_3_retained_count": integrated_retained,
            "recall": _ratio(integrated_retained, integrated_baseline),
        },
        "outdoor_portability": outdoor,
        "note": (
            "Routing retention over saved V0.2 relations; it is a regression proxy, not "
            "a new manual precision judgement."
        ),
    }


__all__ = (
    "replay_intent_precision_v0_3",
    "replay_intent_regressions_v0_3",
)
