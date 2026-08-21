"""Context-aware Organic Query Intent Classifier V0.3.

V0.3 is intentionally isolated from the replayable V0.2 classifier. It changes
only the intent boundary and continues to consume the unchanged Taxonomy V0.2.
"""

from __future__ import annotations

from enum import StrEnum
import re
from typing import Any

from amazon_product_intelligence.contracts import deterministic_id

from .errors import BuyerNeedValidationError
from .models import BuyerNeedTaxonomyRegistry, BuyerNeedTextEvidence, BuyerNeedTextSourceType
from .models_v0_2 import (
    BUYER_NEED_INTENT_RULESET_VERSION,
    BuyerNeedQueryIntent,
    BuyerNeedQueryIntentConfidence,
    BuyerNeedQueryIntentRegistry,
    BuyerNeedQueryIntentRule,
    BuyerNeedQueryScope,
)
from .models_v0_3 import (
    BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3,
    BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
    BuyerNeedQueryIntentEvidenceV0_3,
    IntentBoundaryV0_3,
    IntentClassificationContext,
)
from .taxonomy_v0_2 import (
    BUYER_NEED_SCOPED_TAXONOMY_ENTRY_IDS_V0_2,
    BUYER_NEED_TAXONOMY_V0_2,
)


_DOG_SCOPE = (BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,)
_CATEGORY_QUALIFIER_PATTERN = re.compile(
    r"\b(?:dogs?|doggy|pupp(?:y|ies)|pets?)\b",
    flags=re.IGNORECASE,
)


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
        "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
    }
    return BuyerNeedQueryIntentRule(
        rule_id=deterministic_id("buyer-need-query-intent-rule", payload),
        **payload,
    )


def build_buyer_need_query_intent_registry_v0_3() -> BuyerNeedQueryIntentRegistry:
    """Build structural gates; these do not add or change Buyer Need taxonomy entries."""

    rules = (
        _rule(
            intent=BuyerNeedQueryIntent.OUT_OF_SCOPE,
            regex_patterns=(
                r"\b(?:animal|cats?|rabbits?|bunn(?:y|ies)|hamsters?|guinea\s+pigs?|birds?|chinchillas?|rats?|parrots?)\b",
            ),
            rationale="An explicit non-dog audience is outside the selected category scope.",
        ),
        _rule(
            intent=BuyerNeedQueryIntent.BRAND_MODEL,
            regex_patterns=(
                r"\basobu\b",
                r"\blesotc\b",
                r"\blixit\b",
                r"\bpawb\b",
                r"\bpup\s*flask\b",
                r"\bpupflask\b",
                r"\brover\s+and\s+oak\b",
                r"\bruffland\b",
                r"\bspringer\b",
                r"\bspringland\b",
                r"\bsuper\s+design\b",
                r"\btrail\s*hound\b",
                r"\btrailhound\b",
                r"\byeti\b",
            ),
            rationale=(
                "A finite, audited brand/model alias is primary; any Need-looking modifier "
                "is retained separately and cannot silently override the primary intent."
            ),
        ),
        _rule(
            intent=BuyerNeedQueryIntent.ACCESSORY_RELATED,
            exact_queries=("dog mom",),
            regex_patterns=(
                r"\b(?:accessories?|backpacks?|bags?|carriers?|food\s+storage|feeders?|gifts?|pouches?|toys?)\b",
                r"\bpoop\s+bags?\b",
                r"\b(?:food|treat|snack)\s+containers?\b",
            ),
            rationale=(
                "The query head/object names a related product or accessory, so a travel "
                "or walking modifier cannot promote it to a target-product Buyer Need."
            ),
        ),
        _rule(
            intent=BuyerNeedQueryIntent.BROAD_QUERY,
            exact_queries=("dog water",),
            regex_patterns=(r"\b(?:essentials?|gear|supplies|stuff)\b",),
            rationale="The query supplies broad shopping context without a target product relation.",
        ),
        _rule(
            intent=BuyerNeedQueryIntent.PRODUCT_OBJECT,
            exact_queries=("botella de agua para perros",),
            regex_patterns=(
                r"\b(?:water\s+)?(?:bottles?|bowls?|dispensers?)\b",
                r"\bbottle\s+water\b",
            ),
            rationale="The query contains a target-category product object.",
        ),
    )
    payload = {
        "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
        "rules": tuple(sorted(rules, key=lambda item: item.rule_id)),
    }
    return BuyerNeedQueryIntentRegistry(
        registry_id=deterministic_id("buyer-need-query-intent-registry", payload),
        **payload,
    )


BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3 = build_buyer_need_query_intent_registry_v0_3()


# These are intent signals, not Buyer Need taxonomy entries. They determine whether
# a product-object query carries an explicit modifier that is worth sending to the
# unchanged taxonomy, which may still return UNKNOWN.
_NEED_EXPRESSION_PATTERNS = (
    r"\b(?:automatic|bpa[ -]?free|collapsible|cooling|foldable|gravity|insulated|leak[ -]?proof|portable|silicone)\b",
    r"\b(?:travel|walking|walks?|hiking|running|outdoor|camping|beach)\b",
    r"\b(?:built[ -]?in|integrated)\s+bowl\b",
    r"\bwith\s+(?:a\s+)?(?:built[ -]?in\s+)?bowl\b",
    r"\b(?:crate|kennel|cage)\b",
    r"\b(?:large|small)\s+(?:size\s+)?dogs?\b",
    r"\bsmall\s+size\b",
    r"\bpupp(?:y|ies)\b",
    r"\b(?:no[ -]?spill|dishwasher[ -]?safe|cup\s+holder|on\s+the\s+go)\b",
    r"\b(?:2|3)\s*(?:in|-)\s*1\b",
    r"\bwith\s+(?:a\s+)?snack\s+compartment\b",
)


def _all_matches(patterns: tuple[str, ...], text: str) -> tuple[str, ...]:
    matches = {
        match.group(0).casefold()
        for pattern in patterns
        for match in re.finditer(pattern, text, flags=re.IGNORECASE)
        if match.group(0).strip()
    }
    return tuple(sorted(matches))


def _rule_matches(
    rule: BuyerNeedQueryIntentRule,
    text: str,
) -> tuple[str, ...]:
    matches = set()
    if text in rule.exact_queries:
        matches.add(text)
    matches.update(_all_matches(rule.regex_patterns, text))
    return tuple(sorted(matches))


def _gate_id(name: str) -> str:
    return deterministic_id(
        "buyer-need-intent-gate-v0.3",
        {"gate": name, "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3},
    )


def _modifier_diagnostics(
    normalized_query: str,
    product_matches: tuple[str, ...],
    need_matches: tuple[str, ...],
) -> tuple[str, ...]:
    diagnostics: set[str] = set()
    if _CATEGORY_QUALIFIER_PATTERN.search(normalized_query):
        diagnostics.add("category_qualifier=dog_or_pet")
    else:
        diagnostics.add("category_qualifier=missing")
    positions: list[tuple[int, str]] = []
    for product in product_matches:
        product_index = normalized_query.find(product)
        if product_index < 0:
            continue
        product_token = len(normalized_query[:product_index].split())
        for need in need_matches:
            need_index = normalized_query.find(need)
            if need_index < 0:
                continue
            need_token = len(normalized_query[:need_index].split())
            distance = abs(product_token - need_token)
            position = "before_product" if need_token < product_token else "after_product"
            positions.append((distance, position))
    if positions:
        distance, position = min(positions)
        diagnostics.add(f"modifier_position={position}")
        diagnostics.add(f"modifier_token_distance={distance}")
    else:
        diagnostics.add("modifier_position=unlinked")
    return tuple(sorted(diagnostics))


class BuyerNeedQueryIntentClassifierV0_3:
    """Choose a primary intent through context gates before invoking taxonomy."""

    def __init__(
        self,
        *,
        registry: BuyerNeedQueryIntentRegistry = BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3,
        taxonomy: BuyerNeedTaxonomyRegistry = BUYER_NEED_TAXONOMY_V0_2,
    ) -> None:
        if not isinstance(registry, BuyerNeedQueryIntentRegistry):
            raise BuyerNeedValidationError("V0.3 intent classifier requires a registry")
        if registry.ruleset_version != BUYER_NEED_INTENT_RULESET_VERSION_V0_3:
            raise BuyerNeedValidationError("V0.3 intent classifier requires rules v0.3")
        if not isinstance(taxonomy, BuyerNeedTaxonomyRegistry):
            raise BuyerNeedValidationError("V0.3 intent classifier requires a taxonomy")
        self.registry = registry
        self.taxonomy = taxonomy

    def classify(
        self,
        text_evidence: BuyerNeedTextEvidence,
        *,
        query_scope: BuyerNeedQueryScope,
    ) -> BuyerNeedQueryIntentEvidenceV0_3:
        if not isinstance(text_evidence, BuyerNeedTextEvidence):
            raise BuyerNeedValidationError("V0.3 intent input must be BuyerNeedTextEvidence")
        if text_evidence.source_type is not BuyerNeedTextSourceType.SEARCH_TERM:
            raise BuyerNeedValidationError("query intent V0.3 accepts Search Term evidence only")
        if not isinstance(query_scope, BuyerNeedQueryScope):
            raise BuyerNeedValidationError("V0.3 intent requires an explicit query scope")

        context, matches_by_intent = self._build_context(text_evidence, query_scope)
        taxonomy_entry_ids = self._matching_taxonomy_entry_ids(text_evidence, query_scope)
        decision = self._decide(context, matches_by_intent, taxonomy_entry_ids)
        primary_intent, confidence, boundary, rule_ids, rationale = decision
        secondary = (
            context.need_expression_matches
            if primary_intent is not BuyerNeedQueryIntent.NEED_CANDIDATE
            else ()
        )
        payload = {
            "primary_intent": primary_intent,
            "confidence": confidence,
            "boundary": boundary,
            "context": context,
            "source_evidence": text_evidence,
            "matched_rule_ids": tuple(sorted(rule_ids)),
            "secondary_need_signals": secondary,
            "rationale": rationale,
            "eligible_for_taxonomy": primary_intent is BuyerNeedQueryIntent.NEED_CANDIDATE,
            "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
            "contract_version": BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3,
        }
        return BuyerNeedQueryIntentEvidenceV0_3(
            intent_id=deterministic_id("buyer-need-query-intent-v0.3", payload),
            **payload,
        )

    def _build_context(
        self,
        text_evidence: BuyerNeedTextEvidence,
        query_scope: BuyerNeedQueryScope,
    ) -> tuple[IntentClassificationContext, dict[BuyerNeedQueryIntent, tuple[str, ...]]]:
        text = text_evidence.normalized_text
        matches_by_intent: dict[BuyerNeedQueryIntent, set[str]] = {
            intent: set() for intent in BuyerNeedQueryIntent
        }
        for rule in self.registry.rules:
            if query_scope not in rule.query_scopes:
                continue
            matches_by_intent[rule.intent].update(_rule_matches(rule, text))
        frozen_matches = {
            intent: tuple(sorted(values)) for intent, values in matches_by_intent.items()
        }
        product_matches = frozen_matches[BuyerNeedQueryIntent.PRODUCT_OBJECT]
        need_matches = _all_matches(_NEED_EXPRESSION_PATTERNS, text)
        diagnostics = set(_modifier_diagnostics(text, product_matches, need_matches))
        diagnostics.add(f"category_scope={query_scope.value}")
        payload = {
            "normalized_query": text,
            "category_scope": query_scope,
            "product_object_matches": product_matches,
            "brand_model_matches": frozen_matches[BuyerNeedQueryIntent.BRAND_MODEL],
            "accessory_matches": frozen_matches[BuyerNeedQueryIntent.ACCESSORY_RELATED],
            "broad_query_matches": frozen_matches[BuyerNeedQueryIntent.BROAD_QUERY],
            "out_of_scope_matches": frozen_matches[BuyerNeedQueryIntent.OUT_OF_SCOPE],
            "need_expression_matches": need_matches,
            "diagnostics": tuple(sorted(diagnostics)),
            "contract_version": BUYER_NEED_INTENT_CONTRACT_VERSION_V0_3,
        }
        context = IntentClassificationContext(
            context_id=deterministic_id("buyer-need-intent-context-v0.3", payload),
            **payload,
        )
        return context, frozen_matches

    def _decide(
        self,
        context: IntentClassificationContext,
        matches_by_intent: dict[BuyerNeedQueryIntent, tuple[str, ...]],
        taxonomy_entry_ids: tuple[str, ...],
    ) -> tuple[
        BuyerNeedQueryIntent,
        BuyerNeedQueryIntentConfidence,
        IntentBoundaryV0_3,
        tuple[str, ...],
        str,
    ]:
        matched_rule_ids = tuple(
            sorted(
                rule.rule_id
                for rule in self.registry.rules
                if _rule_matches(rule, context.normalized_query)
                and context.category_scope in rule.query_scopes
            )
        )
        category_present = "category_qualifier=dog_or_pet" in context.diagnostics
        modifier_distance = next(
            (
                int(item.split("=", 1)[1])
                for item in context.diagnostics
                if item.startswith("modifier_token_distance=")
            ),
            None,
        )
        linked_modifier = (
            bool(context.product_object_matches)
            and bool(context.need_expression_matches)
            and modifier_distance is not None
            and modifier_distance <= 6
        )

        if context.out_of_scope_matches:
            return (
                BuyerNeedQueryIntent.OUT_OF_SCOPE,
                BuyerNeedQueryIntentConfidence.HIGH,
                IntentBoundaryV0_3.OUT_OF_SCOPE_AUDIENCE,
                (*matched_rule_ids, _gate_id("out-of-scope-precedence")),
                "An explicit non-dog audience takes precedence in the dog category scope.",
            )
        if context.brand_model_matches:
            boundary = (
                IntentBoundaryV0_3.BRAND_WITH_SECONDARY_NEED_SIGNAL
                if context.need_expression_matches
                else IntentBoundaryV0_3.BRAND_MODEL_PRIMARY
            )
            return (
                BuyerNeedQueryIntent.BRAND_MODEL,
                BuyerNeedQueryIntentConfidence.MEDIUM,
                boundary,
                (*matched_rule_ids, _gate_id("brand-primary-secondary-need")),
                "Brand/model is primary; explicit Need-looking text remains secondary evidence.",
            )
        if context.accessory_matches:
            return (
                BuyerNeedQueryIntent.ACCESSORY_RELATED,
                BuyerNeedQueryIntentConfidence.HIGH,
                IntentBoundaryV0_3.ACCESSORY_OBJECT,
                (*matched_rule_ids, _gate_id("accessory-object-precedence")),
                "A related-product object blocks travel/walking tokens from becoming target-product Needs.",
            )
        if context.broad_query_matches and not linked_modifier:
            return (
                BuyerNeedQueryIntent.BROAD_QUERY,
                BuyerNeedQueryIntentConfidence.HIGH,
                IntentBoundaryV0_3.BROAD_CONTEXT,
                (*matched_rule_ids, _gate_id("broad-context-precedence")),
                "Broad shopping context lacks a linked target-product Need expression.",
            )
        if context.product_object_matches:
            if context.need_expression_matches:
                if category_present and linked_modifier:
                    taxonomy_route = (
                        (
                            deterministic_id(
                                "buyer-need-query-taxonomy-route-v0.3",
                                {
                                    "query_scope": context.category_scope,
                                    "taxonomy_version": self.taxonomy.taxonomy_version,
                                    "taxonomy_entry_ids": taxonomy_entry_ids,
                                    "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
                                },
                            ),
                        )
                        if taxonomy_entry_ids
                        else ()
                    )
                    return (
                        BuyerNeedQueryIntent.NEED_CANDIDATE,
                        (
                            BuyerNeedQueryIntentConfidence.HIGH
                            if taxonomy_entry_ids
                            else BuyerNeedQueryIntentConfidence.MEDIUM
                        ),
                        IntentBoundaryV0_3.PRODUCT_OBJECT_WITH_NEED_MODIFIER,
                        (*matched_rule_ids, *taxonomy_route, _gate_id("product-plus-need-modifier")),
                        "A nearby explicit modifier is linked to a category-qualified target product.",
                    )
                return (
                    BuyerNeedQueryIntent.AMBIGUOUS,
                    BuyerNeedQueryIntentConfidence.UNKNOWN,
                    IntentBoundaryV0_3.CONTEXT_MISSING,
                    (*matched_rule_ids, _gate_id("generic-modifier-context-missing")),
                    "A Need-looking modifier lacks dog/pet category context or a close product relation.",
                )
            if taxonomy_entry_ids and category_present:
                return (
                    BuyerNeedQueryIntent.NEED_CANDIDATE,
                    BuyerNeedQueryIntentConfidence.HIGH,
                    IntentBoundaryV0_3.TAXONOMY_NEED_EXPRESSION,
                    (
                        *matched_rule_ids,
                        deterministic_id(
                            "buyer-need-query-taxonomy-route-v0.3",
                            {
                                "query_scope": context.category_scope,
                                "taxonomy_version": self.taxonomy.taxonomy_version,
                                "taxonomy_entry_ids": taxonomy_entry_ids,
                                "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
                            },
                        ),
                    ),
                    "An unchanged Taxonomy V0.2 rule supplies the explicit Need expression.",
                )
            return (
                BuyerNeedQueryIntent.PRODUCT_OBJECT,
                BuyerNeedQueryIntentConfidence.HIGH,
                IntentBoundaryV0_3.PURE_PRODUCT_OBJECT,
                (*matched_rule_ids, _gate_id("pure-product-object")),
                "A target product is named without an explicit Need modifier.",
            )
        if context.broad_query_matches:
            return (
                BuyerNeedQueryIntent.BROAD_QUERY,
                BuyerNeedQueryIntentConfidence.HIGH,
                IntentBoundaryV0_3.BROAD_CONTEXT,
                (*matched_rule_ids, _gate_id("broad-context-precedence")),
                "Broad context is not linked to a target product object.",
            )
        if taxonomy_entry_ids and category_present:
            return (
                BuyerNeedQueryIntent.NEED_CANDIDATE,
                BuyerNeedQueryIntentConfidence.HIGH,
                IntentBoundaryV0_3.TAXONOMY_NEED_EXPRESSION,
                (
                    *matched_rule_ids,
                    deterministic_id(
                        "buyer-need-query-taxonomy-route-v0.3",
                        {
                            "query_scope": context.category_scope,
                            "taxonomy_version": self.taxonomy.taxonomy_version,
                            "taxonomy_entry_ids": taxonomy_entry_ids,
                            "ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
                        },
                    ),
                ),
                "A taxonomy expression has explicit dog/pet category context.",
            )
        return (
            BuyerNeedQueryIntent.AMBIGUOUS,
            BuyerNeedQueryIntentConfidence.UNKNOWN,
            IntentBoundaryV0_3.UNRESOLVED,
            (*matched_rule_ids, _gate_id("unresolved-no-guess")),
            "The query lacks enough structural evidence for either Need or NON_NEED intent.",
        )

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


class BuyerNeedIntentClassifierVersion(StrEnum):
    V0_2 = BUYER_NEED_INTENT_RULESET_VERSION
    V0_3 = BUYER_NEED_INTENT_RULESET_VERSION_V0_3


def get_buyer_need_query_intent_classifier(
    version: str | BuyerNeedIntentClassifierVersion,
    *,
    taxonomy: BuyerNeedTaxonomyRegistry = BUYER_NEED_TAXONOMY_V0_2,
) -> Any:
    """Select an intent classifier explicitly without changing the V0.2 default."""

    selected = version.value if isinstance(version, BuyerNeedIntentClassifierVersion) else version
    if selected == BUYER_NEED_INTENT_RULESET_VERSION:
        from .intent_v0_2 import BuyerNeedQueryIntentClassifierV0_2

        return BuyerNeedQueryIntentClassifierV0_2(taxonomy=taxonomy)
    if selected == BUYER_NEED_INTENT_RULESET_VERSION_V0_3:
        return BuyerNeedQueryIntentClassifierV0_3(taxonomy=taxonomy)
    raise BuyerNeedValidationError(f"unsupported Buyer Need intent classifier version: {selected}")


__all__ = (
    "BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3",
    "BuyerNeedIntentClassifierVersion",
    "BuyerNeedQueryIntentClassifierV0_3",
    "build_buyer_need_query_intent_registry_v0_3",
    "get_buyer_need_query_intent_classifier",
)
