"""Context-aware Organic Query Intent contracts for Buyer Need V0.3."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    deterministic_id,
)

from .errors import BuyerNeedSerializationError, BuyerNeedValidationError
from .models import BuyerNeedCandidateStatus, BuyerNeedEvidence, BuyerNeedTextEvidence
from .models_v0_2 import (
    BUYER_NEED_RULESET_VERSION_V0_2,
    BUYER_NEED_TAXONOMY_VERSION_V0_2,
    BuyerNeedQueryIntent,
    BuyerNeedQueryIntentConfidence,
    BuyerNeedQueryScope,
)


BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3 = "buyer-need-intent-contract-v0.3"
BUYER_NEED_INTENT_RULESET_VERSION_V0_3 = "buyer-need-intent-rules-v0.3"


class IntentBoundaryV0_3(StrEnum):
    OUT_OF_SCOPE_AUDIENCE = "OUT_OF_SCOPE_AUDIENCE"
    BRAND_MODEL_PRIMARY = "BRAND_MODEL_PRIMARY"
    BRAND_WITH_SECONDARY_NEED_SIGNAL = "BRAND_WITH_SECONDARY_NEED_SIGNAL"
    ACCESSORY_OBJECT = "ACCESSORY_OBJECT"
    BROAD_CONTEXT = "BROAD_CONTEXT"
    PURE_PRODUCT_OBJECT = "PURE_PRODUCT_OBJECT"
    PRODUCT_OBJECT_WITH_NEED_MODIFIER = "PRODUCT_OBJECT_WITH_NEED_MODIFIER"
    TAXONOMY_NEED_EXPRESSION = "TAXONOMY_NEED_EXPRESSION"
    CONTEXT_MISSING = "CONTEXT_MISSING"
    UNRESOLVED = "UNRESOLVED"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise BuyerNeedValidationError(f"{path} must be non-empty text")
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise BuyerNeedValidationError(f"{path} must be a sequence")
    return tuple(value)


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    payload = model.to_dict()
    payload.pop(field_name)
    return deterministic_id(prefix, payload)


class _BuyerNeedV03Model(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except BuyerNeedValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise BuyerNeedSerializationError(f"invalid {cls.__name__}: {exc}") from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class IntentClassificationContext(_BuyerNeedV03Model):
    context_id: str
    normalized_query: str
    category_scope: BuyerNeedQueryScope
    product_object_matches: tuple[str, ...]
    brand_model_matches: tuple[str, ...]
    accessory_matches: tuple[str, ...]
    broad_query_matches: tuple[str, ...]
    out_of_scope_matches: tuple[str, ...]
    need_expression_matches: tuple[str, ...]
    diagnostics: tuple[str, ...]
    contract_version: str = BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3

    def __post_init__(self) -> None:
        _text(self.normalized_query, "IntentClassificationContext.normalized_query")
        if not isinstance(self.category_scope, BuyerNeedQueryScope):
            raise BuyerNeedValidationError("intent context requires a valid category scope")
        for field_name in (
            "product_object_matches",
            "brand_model_matches",
            "accessory_matches",
            "broad_query_matches",
            "out_of_scope_matches",
            "need_expression_matches",
            "diagnostics",
        ):
            values = _tuple(getattr(self, field_name), f"IntentClassificationContext.{field_name}")
            if any(type(item) is not str or not item.strip() for item in values):
                raise BuyerNeedValidationError(f"intent context {field_name} requires text values")
            if len(values) != len(set(values)):
                raise BuyerNeedValidationError(f"intent context {field_name} must be unique")
            object.__setattr__(self, field_name, tuple(sorted(values)))
        if self.contract_version != BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3:
            raise BuyerNeedValidationError("intent context contract version mismatch")
        if self.context_id != _identity("buyer-need-intent-context-v0.3", self, "context_id"):
            raise BuyerNeedValidationError("intent context ID does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedQueryIntentEvidenceV0_3(_BuyerNeedV03Model):
    intent_id: str
    primary_intent: BuyerNeedQueryIntent
    confidence: BuyerNeedQueryIntentConfidence
    boundary: IntentBoundaryV0_3
    context: IntentClassificationContext
    source_evidence: BuyerNeedTextEvidence
    matched_rule_ids: tuple[str, ...]
    secondary_need_signals: tuple[str, ...]
    rationale: str
    eligible_for_taxonomy: bool
    ruleset_version: str = BUYER_NEED_INTENT_RULESET_VERSION_V0_3
    contract_version: str = BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3

    def __post_init__(self) -> None:
        if not isinstance(self.primary_intent, BuyerNeedQueryIntent):
            raise BuyerNeedValidationError("V0.3 intent evidence has an invalid primary intent")
        if not isinstance(self.confidence, BuyerNeedQueryIntentConfidence):
            raise BuyerNeedValidationError("V0.3 intent evidence has invalid confidence")
        if not isinstance(self.boundary, IntentBoundaryV0_3):
            raise BuyerNeedValidationError("V0.3 intent evidence has an invalid boundary")
        if not isinstance(self.context, IntentClassificationContext):
            raise BuyerNeedValidationError("V0.3 intent evidence requires context")
        if not isinstance(self.source_evidence, BuyerNeedTextEvidence):
            raise BuyerNeedValidationError("V0.3 intent evidence must preserve text provenance")
        if self.source_evidence.normalized_text != self.context.normalized_query:
            raise BuyerNeedValidationError("intent context and source text must agree")
        matched = _tuple(self.matched_rule_ids, "BuyerNeedQueryIntentEvidenceV0_3.matched_rule_ids")
        secondary = _tuple(
            self.secondary_need_signals,
            "BuyerNeedQueryIntentEvidenceV0_3.secondary_need_signals",
        )
        if any(type(item) is not str or not item.strip() for item in matched + secondary):
            raise BuyerNeedValidationError("V0.3 intent evidence rule and signal IDs require text")
        if len(matched) != len(set(matched)) or len(secondary) != len(set(secondary)):
            raise BuyerNeedValidationError("V0.3 intent rule and signal IDs must be unique")
        if not set(secondary).issubset(self.context.need_expression_matches):
            raise BuyerNeedValidationError("secondary need signals must originate in context")
        _text(self.rationale, "BuyerNeedQueryIntentEvidenceV0_3.rationale")
        expected_eligible = self.primary_intent is BuyerNeedQueryIntent.NEED_CANDIDATE
        if self.eligible_for_taxonomy is not expected_eligible:
            raise BuyerNeedValidationError("only NEED_CANDIDATE may enter Buyer Need taxonomy")
        if self.primary_intent is BuyerNeedQueryIntent.AMBIGUOUS and (
            self.confidence is not BuyerNeedQueryIntentConfidence.UNKNOWN
        ):
            raise BuyerNeedValidationError("AMBIGUOUS V0.3 intent requires UNKNOWN confidence")
        if self.ruleset_version != BUYER_NEED_INTENT_RULESET_VERSION_V0_3:
            raise BuyerNeedValidationError("V0.3 intent ruleset version mismatch")
        if self.contract_version != BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3:
            raise BuyerNeedValidationError("V0.3 intent contract version mismatch")
        object.__setattr__(self, "matched_rule_ids", tuple(sorted(matched)))
        object.__setattr__(self, "secondary_need_signals", tuple(sorted(secondary)))
        if self.intent_id != _identity("buyer-need-query-intent-v0.3", self, "intent_id"):
            raise BuyerNeedValidationError("V0.3 intent ID does not match content")

    @property
    def intent(self) -> BuyerNeedQueryIntent:
        """Compatibility alias for consumers that read an intent evidence object."""

        return self.primary_intent


@dataclass(frozen=True, slots=True, kw_only=True)
class BuyerNeedAnalysisResultV0_3(_BuyerNeedV03Model):
    result_id: str
    intent_evidence: BuyerNeedQueryIntentEvidenceV0_3
    buyer_need_candidates: tuple[BuyerNeedEvidence, ...]
    taxonomy_version: str = BUYER_NEED_TAXONOMY_VERSION_V0_2
    buyer_need_ruleset_version: str = BUYER_NEED_RULESET_VERSION_V0_2
    intent_ruleset_version: str = BUYER_NEED_INTENT_RULESET_VERSION_V0_3

    def __post_init__(self) -> None:
        if not isinstance(self.intent_evidence, BuyerNeedQueryIntentEvidenceV0_3):
            raise BuyerNeedValidationError("V0.3 analysis result requires V0.3 intent evidence")
        candidates = _tuple(
            self.buyer_need_candidates,
            "BuyerNeedAnalysisResultV0_3.buyer_need_candidates",
        )
        if any(not isinstance(item, BuyerNeedEvidence) for item in candidates):
            raise BuyerNeedValidationError("V0.3 result contains invalid Buyer Need candidates")
        if len({item.need_id for item in candidates}) != len(candidates):
            raise BuyerNeedValidationError("V0.3 result candidate IDs must be unique")
        if self.taxonomy_version != BUYER_NEED_TAXONOMY_VERSION_V0_2:
            raise BuyerNeedValidationError("V0.3 analysis must keep taxonomy v0.2")
        if self.buyer_need_ruleset_version != BUYER_NEED_RULESET_VERSION_V0_2:
            raise BuyerNeedValidationError("V0.3 analysis must keep Buyer Need rules v0.2")
        if self.intent_ruleset_version != BUYER_NEED_INTENT_RULESET_VERSION_V0_3:
            raise BuyerNeedValidationError("V0.3 analysis intent ruleset mismatch")
        if self.intent_evidence.primary_intent is BuyerNeedQueryIntent.NEED_CANDIDATE:
            if not candidates:
                raise BuyerNeedValidationError("V0.3 NEED_CANDIDATE requires taxonomy output")
            if any(
                item.source_evidence[0].source_reference.source_reference_id
                != self.intent_evidence.source_evidence.source_reference.source_reference_id
                or item.source_text != self.intent_evidence.source_evidence.raw_text
                or item.normalized_text != self.intent_evidence.source_evidence.normalized_text
                for item in candidates
            ):
                raise BuyerNeedValidationError("V0.3 intent and Buyer Need provenance must agree")
            if any(
                item.taxonomy_version != self.taxonomy_version
                or item.ruleset_version != self.buyer_need_ruleset_version
                for item in candidates
            ):
                raise BuyerNeedValidationError("V0.3 candidate versions must remain V0.2")
        elif candidates:
            raise BuyerNeedValidationError("V0.3 NON_NEED or AMBIGUOUS cannot publish Buyer Need")
        object.__setattr__(
            self,
            "buyer_need_candidates",
            tuple(sorted(candidates, key=lambda item: item.need_id)),
        )
        if self.result_id != _identity("buyer-need-analysis-v0.3", self, "result_id"):
            raise BuyerNeedValidationError("V0.3 analysis result ID does not match content")

    @property
    def semantic_cluster_inputs(self) -> tuple[BuyerNeedEvidence, ...]:
        if self.intent_evidence.primary_intent is not BuyerNeedQueryIntent.NEED_CANDIDATE:
            return ()
        return tuple(
            item
            for item in self.buyer_need_candidates
            if item.status is BuyerNeedCandidateStatus.CANDIDATE
        )


__all__ = (
    "BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3",
    "BUYER_NEED_INTENT_RULESET_VERSION_V0_3",
    "BuyerNeedAnalysisResultV0_3",
    "BuyerNeedQueryIntentEvidenceV0_3",
    "IntentBoundaryV0_3",
    "IntentClassificationContext",
)
