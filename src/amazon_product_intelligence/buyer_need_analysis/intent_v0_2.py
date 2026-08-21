"""High-precision, category-scoped query-intent routing for Buyer Need V0.2."""

from __future__ import annotations

import re

from amazon_product_intelligence.contracts import deterministic_id

from .errors import BuyerNeedValidationError
from .models import BuyerNeedTaxonomyRegistry, BuyerNeedTextEvidence, BuyerNeedTextSourceType
from .models_v0_2 import (
    BUYER_NEED_INTENT_CONTRACT_VERSION,
    BUYER_NEED_INTENT_RULESET_VERSION,
    BuyerNeedQueryIntent,
    BuyerNeedQueryIntentConfidence,
    BuyerNeedQueryIntentEvidence,
    BuyerNeedQueryIntentRegistry,
    BuyerNeedQueryIntentRule,
    BuyerNeedQueryScope,
)
from .taxonomy_v0_2 import (
    BUYER_NEED_SCOPED_TAXONOMY_ENTRY_IDS_V0_2,
    BUYER_NEED_TAXONOMY_V0_2,
)


_DOG_SCOPE = (BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,)


def _rule(
    *,
    intent: BuyerNeedQueryIntent,
    exact_queries: tuple[str, ...] = (),
    regex_patterns: tuple[str, ...] = (),
    rationale: str,
) -> BuyerNeedQueryIntentRule:
    payload = {
        "intent": intent,
        "query_scopes": _DOG_SCOPE,
        "exact_queries": tuple(sorted(exact_queries)),
        "regex_patterns": tuple(sorted(regex_patterns)),
        "rationale": rationale,
        "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION,
    }
    return BuyerNeedQueryIntentRule(
        rule_id=deterministic_id("buyer-need-query-intent-rule", payload),
        **payload,
    )


def build_buyer_need_query_intent_registry_v0_2() -> BuyerNeedQueryIntentRegistry:
    rules = (
        _rule(
            intent=BuyerNeedQueryIntent.AMBIGUOUS,
            exact_queries=("hemli",),
            rationale="The audited token has insufficient provenance for a brand or Need claim.",
        ),
        _rule(
            intent=BuyerNeedQueryIntent.OUT_OF_SCOPE,
            exact_queries=(
                "guinea pig water bottle",
                "hamster water bottle",
                "mom water bottle",
            ),
            rationale="The audited audience or product is outside the dog travel bottle scope.",
        ),
        _rule(
            intent=BuyerNeedQueryIntent.ACCESSORY_RELATED,
            exact_queries=(
                "dachshund gifts",
                "dog backpack carrier",
                "dog carrier bag",
                "dog diaper bag",
                "dog food container",
                "dog food storage container",
                "dog gifts for women",
                "dog lovers gifts for women",
                "dog mom",
                "dog mom gift",
                "dog mom gifts",
                "dog mom gifts for women",
                "dog treat container",
                "dog treat pouch",
                "poop bags for dogs",
                "puppy bowls",
                "puppy milk replacement",
                "water bottle dog toy",
            ),
            rationale="The query is audited market-adjacency evidence, not a bottle Buyer Need.",
        ),
        _rule(
            intent=BuyerNeedQueryIntent.BROAD_QUERY,
            exact_queries=(
                "dog accessories",
                "dog accessories girl",
                "dog essentials",
                "dog stuff",
                "dog water",
                "pet dog supplies",
                "puppy essentials",
            ),
            rationale="The query is too broad to support a specific Buyer Need.",
        ),
        _rule(
            intent=BuyerNeedQueryIntent.BRAND_MODEL,
            regex_patterns=(
                r"\blesotc\b",
                r"\blixit\b",
                r"\bpawb\b",
                r"\bpup\s*flask\b",
                r"\bpupflask\b",
                r"\brover\s+and\s+oak\b",
                r"\bruffland\b",
                r"\bspringer\b",
                r"\bsuper\s+design\b",
                r"\btrailhound\b",
                r"\byeti\b",
            ),
            rationale="A finite, audited alias set identifies brand/model shopping intent.",
        ),
        _rule(
            intent=BuyerNeedQueryIntent.PRODUCT_OBJECT,
            exact_queries=(
                "botella de agua para perros",
                "dog bottle",
                "dog bottle water dispenser",
                "dog water bottle",
                "dog water bottle dispenser",
                "dog water bottles",
                "dog water bowl",
                "dog water bowl dispenser",
                "dog water dispenser",
                "dog waterbottle",
                "pet water bottle",
                "pet water dispenser",
                "water bottle",
                "water bottle dog",
                "water bottle for dog",
                "water bottle for dogs",
                "water bottles for dogs",
                "water dispenser for dogs",
            ),
            rationale="The exact audited query names the category product rather than a Need.",
        ),
    )
    payload = {
        "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION,
        "rules": tuple(sorted(rules, key=lambda item: item.rule_id)),
    }
    return BuyerNeedQueryIntentRegistry(
        registry_id=deterministic_id("buyer-need-query-intent-registry", payload),
        **payload,
    )


BUYER_NEED_QUERY_INTENT_REGISTRY_V0_2 = (
    build_buyer_need_query_intent_registry_v0_2()
)


_INTENT_PRIORITY = {
    BuyerNeedQueryIntent.AMBIGUOUS: 0,
    BuyerNeedQueryIntent.OUT_OF_SCOPE: 1,
    BuyerNeedQueryIntent.ACCESSORY_RELATED: 2,
    BuyerNeedQueryIntent.BROAD_QUERY: 3,
    BuyerNeedQueryIntent.BRAND_MODEL: 4,
    BuyerNeedQueryIntent.PRODUCT_OBJECT: 5,
}


class BuyerNeedQueryIntentClassifierV0_2:
    """Route only audited, high-precision NON_NEED intents before taxonomy matching."""

    def __init__(
        self,
        *,
        registry: BuyerNeedQueryIntentRegistry = BUYER_NEED_QUERY_INTENT_REGISTRY_V0_2,
        taxonomy: BuyerNeedTaxonomyRegistry = BUYER_NEED_TAXONOMY_V0_2,
    ) -> None:
        if not isinstance(registry, BuyerNeedQueryIntentRegistry):
            raise BuyerNeedValidationError("intent classifier requires an intent registry")
        if not isinstance(taxonomy, BuyerNeedTaxonomyRegistry):
            raise BuyerNeedValidationError("intent classifier requires a taxonomy registry")
        self.registry = registry
        self.taxonomy = taxonomy

    def classify(
        self,
        text_evidence: BuyerNeedTextEvidence,
        *,
        query_scope: BuyerNeedQueryScope,
    ) -> BuyerNeedQueryIntentEvidence:
        if not isinstance(text_evidence, BuyerNeedTextEvidence):
            raise BuyerNeedValidationError("query intent input must be BuyerNeedTextEvidence")
        if text_evidence.source_type is not BuyerNeedTextSourceType.SEARCH_TERM:
            raise BuyerNeedValidationError("query intent V0.2 accepts Search Term evidence only")
        if not isinstance(query_scope, BuyerNeedQueryScope):
            raise BuyerNeedValidationError("query intent requires an explicit query scope")

        selected = self._matched_intent_rule(text_evidence.normalized_text, query_scope)
        if selected is not None:
            intent = selected.intent
            confidence = (
                BuyerNeedQueryIntentConfidence.UNKNOWN
                if intent is BuyerNeedQueryIntent.AMBIGUOUS
                else BuyerNeedQueryIntentConfidence.MEDIUM
                if intent is BuyerNeedQueryIntent.BRAND_MODEL
                else BuyerNeedQueryIntentConfidence.HIGH
            )
            matched_rule_id = selected.rule_id
            rationale = selected.rationale
        else:
            taxonomy_entry_ids = self._matching_taxonomy_entry_ids(
                text_evidence,
                query_scope,
            )
            intent = BuyerNeedQueryIntent.NEED_CANDIDATE
            if taxonomy_entry_ids:
                confidence = BuyerNeedQueryIntentConfidence.HIGH
                matched_rule_id = deterministic_id(
                    "buyer-need-query-taxonomy-route",
                    {
                        "query_scope": query_scope,
                        "taxonomy_version": self.taxonomy.taxonomy_version,
                        "taxonomy_entry_ids": taxonomy_entry_ids,
                    },
                )
                rationale = "A versioned Buyer Need taxonomy rule explicitly matches the query."
            else:
                confidence = BuyerNeedQueryIntentConfidence.LOW
                matched_rule_id = None
                rationale = (
                    "No high-precision NON_NEED rule matched; preserve the query as an "
                    "unresolved Need candidate rather than guessing."
                )

        payload = {
            "intent": intent,
            "confidence": confidence,
            "query_scope": query_scope,
            "source_evidence": text_evidence,
            "matched_rule_id": matched_rule_id,
            "rationale": rationale,
            "eligible_for_semantic_clustering": (
                intent is BuyerNeedQueryIntent.NEED_CANDIDATE
            ),
            "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION,
            "contract_version": BUYER_NEED_INTENT_CONTRACT_VERSION,
        }
        return BuyerNeedQueryIntentEvidence(
            intent_id=deterministic_id("buyer-need-query-intent", payload),
            **payload,
        )

    def _matched_intent_rule(
        self,
        normalized_text: str,
        query_scope: BuyerNeedQueryScope,
    ) -> BuyerNeedQueryIntentRule | None:
        eligible = sorted(
            (
                item
                for item in self.registry.rules
                if query_scope in item.query_scopes
            ),
            key=lambda item: (_INTENT_PRIORITY[item.intent], item.rule_id),
        )
        for rule in eligible:
            if normalized_text in rule.exact_queries or any(
                re.search(pattern, normalized_text, flags=re.IGNORECASE)
                for pattern in rule.regex_patterns
            ):
                return rule
        return None

    def _matching_taxonomy_entry_ids(
        self,
        text_evidence: BuyerNeedTextEvidence,
        query_scope: BuyerNeedQueryScope,
    ) -> tuple[str, ...]:
        matches = []
        for entry in self.taxonomy.entries:
            if text_evidence.source_type not in entry.applicable_source_types:
                continue
            if (
                entry.taxonomy_need_id in BUYER_NEED_SCOPED_TAXONOMY_ENTRY_IDS_V0_2
                and query_scope is not BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
            ):
                continue
            if any(
                re.search(pattern, text_evidence.raw_text, flags=re.IGNORECASE)
                for pattern in entry.regex_patterns
            ):
                matches.append(entry.taxonomy_need_id)
        return tuple(sorted(matches))


__all__ = (
    "BUYER_NEED_QUERY_INTENT_REGISTRY_V0_2",
    "BuyerNeedQueryIntentClassifierV0_2",
    "build_buyer_need_query_intent_registry_v0_2",
)
