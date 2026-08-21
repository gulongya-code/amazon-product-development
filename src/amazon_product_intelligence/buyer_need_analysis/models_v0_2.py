"""Versioned query-intent and Buyer Need analysis contracts for V0.2."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
import re
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    deterministic_id,
)

from .errors import BuyerNeedSerializationError, BuyerNeedValidationError
from .models import (
    BuyerNeedCandidateStatus,
    BuyerNeedEvidence,
    BuyerNeedTextEvidence,
)


BUYER_NEED_INTENT_CONTRACT_VERSION = "buyer-need-intent-contract-v0.2"
BUYER_NEED_INTENT_RULESET_VERSION = "buyer-need-intent-rules-v0.2"
BUYER_NEED_TAXONOMY_VERSION_V0_2 = "buyer-need-taxonomy-v0.2"
BUYER_NEED_RULESET_VERSION_V0_2 = "buyer-need-rules-v0.2"


class BuyerNeedQueryIntent(StrEnum):
    NEED_CANDIDATE = "NEED_CANDIDATE"
    PRODUCT_OBJECT = "PRODUCT_OBJECT"
    BRAND_MODEL = "BRAND_MODEL"
    ACCESSORY_RELATED = "ACCESSORY_RELATED"
    BROAD_QUERY = "BROAD_QUERY"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"
    AMBIGUOUS = "AMBIGUOUS"

    @property
    def is_non_need(self) -> bool:
        return self in {
            BuyerNeedQueryIntent.PRODUCT_OBJECT,
            BuyerNeedQueryIntent.BRAND_MODEL,
            BuyerNeedQueryIntent.ACCESSORY_RELATED,
            BuyerNeedQueryIntent.BROAD_QUERY,
            BuyerNeedQueryIntent.OUT_OF_SCOPE,
        }


class BuyerNeedQueryScope(StrEnum):
    DOG_TRAVEL_WATER_BOTTLES = "DOG_TRAVEL_WATER_BOTTLES"
    UNKNOWN = "UNKNOWN"


class BuyerNeedQueryIntentConfidence(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise BuyerNeedValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise BuyerNeedValidationError(f"{path} must be a sequence")
    return tuple(value)


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    payload = model.to_dict()
    payload.pop(field_name)
    return deterministic_id(prefix, payload)


class _BuyerNeedV02Model(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except BuyerNeedValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise BuyerNeedSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedQueryIntentRule(_BuyerNeedV02Model):
    rule_id: str
    intent: BuyerNeedQueryIntent
    query_scopes: tuple[BuyerNeedQueryScope, ...]
    exact_queries: tuple[str, ...]
    regex_patterns: tuple[str, ...]
    rationale: str
    ruleset_version: str = BUYER_NEED_INTENT_RULESET_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.intent, BuyerNeedQueryIntent):
            raise BuyerNeedValidationError("query intent rule has an invalid intent")
        if self.intent is BuyerNeedQueryIntent.NEED_CANDIDATE:
            raise BuyerNeedValidationError("NEED_CANDIDATE is selected after NON_NEED routing")
        scopes = _tuple(self.query_scopes, "BuyerNeedQueryIntentRule.query_scopes")
        exact = _tuple(self.exact_queries, "BuyerNeedQueryIntentRule.exact_queries")
        patterns = _tuple(self.regex_patterns, "BuyerNeedQueryIntentRule.regex_patterns")
        if not scopes or any(not isinstance(item, BuyerNeedQueryScope) for item in scopes):
            raise BuyerNeedValidationError("query intent rule requires supported scopes")
        if not exact and not patterns:
            raise BuyerNeedValidationError("query intent rule requires exact queries or regex")
        if any(type(item) is not str or not item.strip() for item in exact + patterns):
            raise BuyerNeedValidationError("query intent rule expressions require text")
        if len(set(scopes)) != len(scopes) or len(set(exact)) != len(exact):
            raise BuyerNeedValidationError("query intent rule values must be unique")
        for pattern in patterns:
            try:
                re.compile(pattern, flags=re.IGNORECASE)
            except re.error as exc:
                raise BuyerNeedValidationError(
                    f"invalid query intent regex {pattern!r}: {exc}"
                ) from exc
        _text(self.rationale, "BuyerNeedQueryIntentRule.rationale")
        _text(self.ruleset_version, "BuyerNeedQueryIntentRule.ruleset_version")
        object.__setattr__(self, "query_scopes", tuple(sorted(scopes, key=lambda item: item.value)))
        object.__setattr__(self, "exact_queries", tuple(sorted(exact)))
        object.__setattr__(self, "regex_patterns", tuple(sorted(patterns)))
        if self.rule_id != _identity("buyer-need-query-intent-rule", self, "rule_id"):
            raise BuyerNeedValidationError("query intent rule_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedQueryIntentRegistry(_BuyerNeedV02Model):
    registry_id: str
    ruleset_version: str
    rules: tuple[BuyerNeedQueryIntentRule, ...]

    def __post_init__(self) -> None:
        _text(self.ruleset_version, "BuyerNeedQueryIntentRegistry.ruleset_version")
        rules = _tuple(self.rules, "BuyerNeedQueryIntentRegistry.rules")
        if not rules or any(not isinstance(item, BuyerNeedQueryIntentRule) for item in rules):
            raise BuyerNeedValidationError("query intent registry requires rules")
        if any(item.ruleset_version != self.ruleset_version for item in rules):
            raise BuyerNeedValidationError("query intent registry ruleset mismatch")
        if len({item.rule_id for item in rules}) != len(rules):
            raise BuyerNeedValidationError("query intent registry rule IDs must be unique")
        object.__setattr__(self, "rules", tuple(sorted(rules, key=lambda item: item.rule_id)))
        if self.registry_id != _identity("buyer-need-query-intent-registry", self, "registry_id"):
            raise BuyerNeedValidationError("query intent registry_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedQueryIntentEvidence(_BuyerNeedV02Model):
    intent_id: str
    intent: BuyerNeedQueryIntent
    confidence: BuyerNeedQueryIntentConfidence
    query_scope: BuyerNeedQueryScope
    source_evidence: BuyerNeedTextEvidence
    matched_rule_id: str | None
    rationale: str
    eligible_for_semantic_clustering: bool
    ruleset_version: str = BUYER_NEED_INTENT_RULESET_VERSION
    contract_version: str = BUYER_NEED_INTENT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.intent, BuyerNeedQueryIntent):
            raise BuyerNeedValidationError("query intent evidence has an invalid intent")
        if not isinstance(self.confidence, BuyerNeedQueryIntentConfidence):
            raise BuyerNeedValidationError("query intent evidence has invalid confidence")
        if not isinstance(self.query_scope, BuyerNeedQueryScope):
            raise BuyerNeedValidationError("query intent evidence has an invalid scope")
        if not isinstance(self.source_evidence, BuyerNeedTextEvidence):
            raise BuyerNeedValidationError("query intent evidence must preserve text provenance")
        _optional_text(self.matched_rule_id, "BuyerNeedQueryIntentEvidence.matched_rule_id")
        _text(self.rationale, "BuyerNeedQueryIntentEvidence.rationale")
        _text(self.ruleset_version, "BuyerNeedQueryIntentEvidence.ruleset_version")
        _text(self.contract_version, "BuyerNeedQueryIntentEvidence.contract_version")
        if self.contract_version != BUYER_NEED_INTENT_CONTRACT_VERSION:
            raise BuyerNeedValidationError("query intent contract version mismatch")
        expected_eligible = self.intent is BuyerNeedQueryIntent.NEED_CANDIDATE
        if self.eligible_for_semantic_clustering is not expected_eligible:
            raise BuyerNeedValidationError(
                "only NEED_CANDIDATE may be eligible for semantic clustering"
            )
        if self.intent is BuyerNeedQueryIntent.AMBIGUOUS and (
            self.confidence is not BuyerNeedQueryIntentConfidence.UNKNOWN
        ):
            raise BuyerNeedValidationError("AMBIGUOUS intent requires UNKNOWN confidence")
        if self.intent_id != _identity("buyer-need-query-intent", self, "intent_id"):
            raise BuyerNeedValidationError("query intent ID does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedAnalysisResultV0_2(_BuyerNeedV02Model):
    result_id: str
    intent_evidence: BuyerNeedQueryIntentEvidence
    buyer_need_candidates: tuple[BuyerNeedEvidence, ...]
    taxonomy_version: str = BUYER_NEED_TAXONOMY_VERSION_V0_2
    ruleset_version: str = BUYER_NEED_RULESET_VERSION_V0_2

    def __post_init__(self) -> None:
        if not isinstance(self.intent_evidence, BuyerNeedQueryIntentEvidence):
            raise BuyerNeedValidationError("analysis result requires query intent evidence")
        candidates = _tuple(
            self.buyer_need_candidates,
            "BuyerNeedAnalysisResultV0_2.buyer_need_candidates",
        )
        if any(not isinstance(item, BuyerNeedEvidence) for item in candidates):
            raise BuyerNeedValidationError("analysis result contains invalid Buyer Need candidates")
        if len({item.need_id for item in candidates}) != len(candidates):
            raise BuyerNeedValidationError("analysis result candidate IDs must be unique")
        _text(self.taxonomy_version, "BuyerNeedAnalysisResultV0_2.taxonomy_version")
        _text(self.ruleset_version, "BuyerNeedAnalysisResultV0_2.ruleset_version")
        if self.taxonomy_version != BUYER_NEED_TAXONOMY_VERSION_V0_2:
            raise BuyerNeedValidationError("analysis result taxonomy version mismatch")
        if self.ruleset_version != BUYER_NEED_RULESET_VERSION_V0_2:
            raise BuyerNeedValidationError("analysis result ruleset version mismatch")
        if self.intent_evidence.intent is BuyerNeedQueryIntent.NEED_CANDIDATE:
            if not candidates:
                raise BuyerNeedValidationError("NEED_CANDIDATE requires taxonomy output")
            if any(
                item.source_evidence[0].source_reference.source_reference_id
                != self.intent_evidence.source_evidence.source_reference.source_reference_id
                or item.source_text != self.intent_evidence.source_evidence.raw_text
                or item.normalized_text
                != self.intent_evidence.source_evidence.normalized_text
                for item in candidates
            ):
                raise BuyerNeedValidationError("intent and Buyer Need provenance must agree")
            if any(
                item.taxonomy_version != self.taxonomy_version
                or item.ruleset_version != self.ruleset_version
                for item in candidates
            ):
                raise BuyerNeedValidationError("analysis result candidate version mismatch")
        elif candidates:
            raise BuyerNeedValidationError("NON_NEED or AMBIGUOUS intent cannot publish Buyer Need")
        object.__setattr__(
            self,
            "buyer_need_candidates",
            tuple(sorted(candidates, key=lambda item: item.need_id)),
        )
        if self.result_id != _identity("buyer-need-analysis-v0.2", self, "result_id"):
            raise BuyerNeedValidationError("analysis result ID does not match content")

    @property
    def semantic_cluster_inputs(self) -> tuple[BuyerNeedEvidence, ...]:
        if self.intent_evidence.intent is not BuyerNeedQueryIntent.NEED_CANDIDATE:
            return ()
        return tuple(
            item
            for item in self.buyer_need_candidates
            if item.status is BuyerNeedCandidateStatus.CANDIDATE
        )


__all__ = (
    "BUYER_NEED_INTENT_CONTRACT_VERSION",
    "BUYER_NEED_INTENT_RULESET_VERSION",
    "BUYER_NEED_RULESET_VERSION_V0_2",
    "BUYER_NEED_TAXONOMY_VERSION_V0_2",
    "BuyerNeedAnalysisResultV0_2",
    "BuyerNeedQueryIntent",
    "BuyerNeedQueryIntentConfidence",
    "BuyerNeedQueryIntentEvidence",
    "BuyerNeedQueryIntentRegistry",
    "BuyerNeedQueryIntentRule",
    "BuyerNeedQueryScope",
)
