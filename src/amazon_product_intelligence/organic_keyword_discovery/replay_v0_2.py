"""Pure offline replay of the SP-032B snapshot through Buyer Need V0.2."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedAnalysisPipelineV0_2,
    BuyerNeedAnalysisResultV0_2,
    BuyerNeedCandidateStatus,
    BuyerNeedQueryIntent,
    BuyerNeedQueryScope,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.contracts import JsonContract, KeywordIdentity, deterministic_id


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{path} must be non-empty text")
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ValueError(f"{path} must be a sequence")
    return tuple(value)


@dataclass(frozen=True, slots=True, kw_only=True)
class OrganicKeywordReplayRelationV0_2(JsonContract):
    relation_id: str
    discovery_id: str
    source_asin: str
    analysis_result: BuyerNeedAnalysisResultV0_2

    def __post_init__(self) -> None:
        _text(self.discovery_id, "OrganicKeywordReplayRelationV0_2.discovery_id")
        _text(self.source_asin, "OrganicKeywordReplayRelationV0_2.source_asin")
        if not isinstance(self.analysis_result, BuyerNeedAnalysisResultV0_2):
            raise ValueError("replay relation requires a V0.2 analysis result")
        payload = self.to_dict()
        payload.pop("relation_id")
        if self.relation_id != deterministic_id("organic-keyword-v0.2-replay-relation", payload):
            raise ValueError("replay relation ID does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedIntentRelationCountV0_2(JsonContract):
    intent: BuyerNeedQueryIntent
    relation_count: int

    def __post_init__(self) -> None:
        if not isinstance(self.intent, BuyerNeedQueryIntent):
            raise ValueError("intent relation count has an invalid intent")
        if type(self.relation_count) is not int or self.relation_count < 0:
            raise ValueError("intent relation count must be non-negative")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedTaxonomyReplayV0_2(JsonContract):
    replay_id: str
    source_run_id: str
    baseline_commit: str
    raw_relation_count: int
    v0_1_matched_relation_count: int
    v0_1_unknown_relation_count: int
    v0_2_need_candidate_relation_count: int
    v0_2_matched_relation_count: int
    v0_2_unknown_need_candidate_relation_count: int
    v0_2_non_need_intent_relation_count: int
    v0_2_ambiguous_relation_count: int
    true_need_resolution_count: int
    true_need_resolution_rate: str
    remaining_unresolved_count: int
    intent_distribution: tuple[BuyerNeedIntentRelationCountV0_2, ...]
    relations: tuple[OrganicKeywordReplayRelationV0_2, ...]

    def __post_init__(self) -> None:
        _text(self.source_run_id, "BuyerNeedTaxonomyReplayV0_2.source_run_id")
        _text(self.baseline_commit, "BuyerNeedTaxonomyReplayV0_2.baseline_commit")
        numeric_fields = (
            self.raw_relation_count,
            self.v0_1_matched_relation_count,
            self.v0_1_unknown_relation_count,
            self.v0_2_need_candidate_relation_count,
            self.v0_2_matched_relation_count,
            self.v0_2_unknown_need_candidate_relation_count,
            self.v0_2_non_need_intent_relation_count,
            self.v0_2_ambiguous_relation_count,
            self.true_need_resolution_count,
            self.remaining_unresolved_count,
        )
        if any(type(item) is not int or item < 0 for item in numeric_fields):
            raise ValueError("replay counts must be non-negative integers")
        relations = _tuple(self.relations, "BuyerNeedTaxonomyReplayV0_2.relations")
        if any(not isinstance(item, OrganicKeywordReplayRelationV0_2) for item in relations):
            raise ValueError("replay contains an invalid relation")
        if len({item.discovery_id for item in relations}) != len(relations):
            raise ValueError("replay discovery IDs must be unique")
        distribution = _tuple(
            self.intent_distribution,
            "BuyerNeedTaxonomyReplayV0_2.intent_distribution",
        )
        if any(not isinstance(item, BuyerNeedIntentRelationCountV0_2) for item in distribution):
            raise ValueError("replay intent distribution is invalid")
        if len({item.intent for item in distribution}) != len(distribution):
            raise ValueError("replay intent distribution must be unique")
        observed = Counter(
            item.analysis_result.intent_evidence.intent for item in relations
        )
        expected_distribution = tuple(
            BuyerNeedIntentRelationCountV0_2(intent=intent, relation_count=count)
            for intent, count in sorted(observed.items(), key=lambda item: item[0].value)
        )
        if tuple(sorted(distribution, key=lambda item: item.intent.value)) != expected_distribution:
            raise ValueError("replay intent distribution does not match relations")
        if self.raw_relation_count != len(relations):
            raise ValueError("raw replay count must equal relation lineage count")
        if self.v0_1_matched_relation_count + self.v0_1_unknown_relation_count != len(relations):
            raise ValueError("V0.1 replay counts do not cover the source relations")
        if (
            self.v0_2_need_candidate_relation_count
            + self.v0_2_non_need_intent_relation_count
            + self.v0_2_ambiguous_relation_count
            != len(relations)
        ):
            raise ValueError("V0.2 intent counts do not cover the source relations")
        if (
            self.v0_2_matched_relation_count
            + self.v0_2_unknown_need_candidate_relation_count
            != self.v0_2_need_candidate_relation_count
        ):
            raise ValueError("V0.2 Need counts do not cover NEED_CANDIDATE relations")
        if self.true_need_resolution_count != (
            self.v0_2_matched_relation_count + self.v0_2_non_need_intent_relation_count
        ):
            raise ValueError("true resolution must count matched Need plus explicit NON_NEED")
        if self.remaining_unresolved_count != (
            self.v0_2_unknown_need_candidate_relation_count
            + self.v0_2_ambiguous_relation_count
        ):
            raise ValueError("remaining unresolved count mismatch")
        expected_rate = (
            format(Decimal(self.true_need_resolution_count) / Decimal(len(relations)), "f")
            if relations
            else "0"
        )
        if self.true_need_resolution_rate != expected_rate:
            raise ValueError("true resolution rate mismatch")
        object.__setattr__(self, "relations", tuple(sorted(relations, key=lambda item: item.relation_id)))
        object.__setattr__(
            self,
            "intent_distribution",
            tuple(sorted(distribution, key=lambda item: item.intent.value)),
        )
        payload = self.to_dict()
        payload.pop("replay_id")
        if self.replay_id != deterministic_id("buyer-need-taxonomy-v0.2-replay", payload):
            raise ValueError("replay ID does not match content")


def replay_buyer_need_taxonomy_v0_2(
    snapshot: Mapping[str, Any],
    *,
    query_scope: BuyerNeedQueryScope = BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,
) -> BuyerNeedTaxonomyReplayV0_2:
    """Replay a saved snapshot only; this function has no connector or API dependency."""

    if not isinstance(snapshot, Mapping):
        raise ValueError("offline replay requires a snapshot mapping")
    raw_records = snapshot.get("organic_keyword_records")
    if isinstance(raw_records, (str, bytes)) or not isinstance(raw_records, Sequence):
        raise ValueError("snapshot organic_keyword_records must be a sequence")
    source_run_id = _text(snapshot.get("run_id"), "snapshot.run_id")
    baseline_commit = _text(snapshot.get("baseline_commit"), "snapshot.baseline_commit")
    legacy = snapshot.get("classification_summary")
    if not isinstance(legacy, Mapping):
        raise ValueError("snapshot classification_summary is required")

    pipeline = BuyerNeedAnalysisPipelineV0_2(query_scope=query_scope)
    relations = []
    for record in raw_records:
        if not isinstance(record, Mapping):
            raise ValueError("snapshot relation must be an object")
        keyword_payload = record.get("keyword_identity")
        if not isinstance(keyword_payload, Mapping):
            raise ValueError("snapshot relation requires KeywordIdentity")
        keyword = KeywordIdentity.from_dict(keyword_payload)
        text = build_search_term_text_evidence(keyword)
        analysis = pipeline.analyze(text)
        relation_payload = {
            "discovery_id": _text(record.get("discovery_id"), "record.discovery_id"),
            "source_asin": _text(record.get("source_asin"), "record.source_asin"),
            "analysis_result": analysis,
        }
        relations.append(
            OrganicKeywordReplayRelationV0_2(
                relation_id=deterministic_id(
                    "organic-keyword-v0.2-replay-relation",
                    relation_payload,
                ),
                **relation_payload,
            )
        )
    relations = tuple(sorted(relations, key=lambda item: item.relation_id))
    intent_counts = Counter(
        item.analysis_result.intent_evidence.intent for item in relations
    )
    need_relations = tuple(
        item
        for item in relations
        if item.analysis_result.intent_evidence.intent
        is BuyerNeedQueryIntent.NEED_CANDIDATE
    )
    matched = sum(
        any(
            candidate.status is BuyerNeedCandidateStatus.CANDIDATE
            for candidate in item.analysis_result.buyer_need_candidates
        )
        for item in need_relations
    )
    unknown_need = len(need_relations) - matched
    non_need = sum(
        count for intent, count in intent_counts.items() if intent.is_non_need
    )
    ambiguous = intent_counts[BuyerNeedQueryIntent.AMBIGUOUS]
    resolved = matched + non_need
    relation_count = len(relations)
    distribution = tuple(
        BuyerNeedIntentRelationCountV0_2(intent=intent, relation_count=count)
        for intent, count in sorted(intent_counts.items(), key=lambda item: item[0].value)
    )
    payload = {
        "source_run_id": source_run_id,
        "baseline_commit": baseline_commit,
        "raw_relation_count": relation_count,
        "v0_1_matched_relation_count": int(legacy["matched_relation_count"]),
        "v0_1_unknown_relation_count": int(legacy["unknown_relation_count"]),
        "v0_2_need_candidate_relation_count": len(need_relations),
        "v0_2_matched_relation_count": matched,
        "v0_2_unknown_need_candidate_relation_count": unknown_need,
        "v0_2_non_need_intent_relation_count": non_need,
        "v0_2_ambiguous_relation_count": ambiguous,
        "true_need_resolution_count": resolved,
        "true_need_resolution_rate": (
            format(Decimal(resolved) / Decimal(relation_count), "f")
            if relation_count
            else "0"
        ),
        "remaining_unresolved_count": unknown_need + ambiguous,
        "intent_distribution": distribution,
        "relations": relations,
    }
    return BuyerNeedTaxonomyReplayV0_2(
        replay_id=deterministic_id("buyer-need-taxonomy-v0.2-replay", payload),
        **payload,
    )


__all__ = (
    "BuyerNeedIntentRelationCountV0_2",
    "BuyerNeedTaxonomyReplayV0_2",
    "OrganicKeywordReplayRelationV0_2",
    "replay_buyer_need_taxonomy_v0_2",
)
