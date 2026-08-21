"""Query-intent-first Buyer Need Analysis pipeline V0.2."""

from __future__ import annotations

from amazon_product_intelligence.contracts import deterministic_id

from .builder_v0_1 import BuyerNeedCandidateBuilder
from .errors import BuyerNeedValidationError
from .intent_v0_2 import BuyerNeedQueryIntentClassifierV0_2
from .models import (
    BuyerNeedCategoryContext,
    BuyerNeedProductContext,
    BuyerNeedTaxonomyRegistry,
    BuyerNeedTextEvidence,
)
from .models_v0_2 import (
    BUYER_NEED_RULESET_VERSION_V0_2,
    BUYER_NEED_TAXONOMY_VERSION_V0_2,
    BuyerNeedAnalysisResultV0_2,
    BuyerNeedQueryIntent,
    BuyerNeedQueryScope,
)
from .taxonomy_v0_2 import (
    BUYER_NEED_SCOPED_TAXONOMY_ENTRY_IDS_V0_2,
    BUYER_NEED_TAXONOMY_V0_2,
)


class BuyerNeedCandidateBuilderV0_2(BuyerNeedCandidateBuilder):
    """V0.2 taxonomy evaluator with an explicit category-scope gate."""

    ruleset_version = BUYER_NEED_RULESET_VERSION_V0_2

    def __init__(
        self,
        *,
        query_scope: BuyerNeedQueryScope,
        taxonomy: BuyerNeedTaxonomyRegistry = BUYER_NEED_TAXONOMY_V0_2,
    ) -> None:
        if not isinstance(query_scope, BuyerNeedQueryScope):
            raise BuyerNeedValidationError("V0.2 builder requires an explicit query scope")
        if taxonomy.taxonomy_version != BUYER_NEED_TAXONOMY_VERSION_V0_2:
            raise BuyerNeedValidationError("V0.2 builder requires taxonomy v0.2")
        self.query_scope = query_scope
        super().__init__(taxonomy=taxonomy)

    def _match(self, text_evidence: BuyerNeedTextEvidence):
        matches = super()._match(text_evidence)
        if self.query_scope is BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES:
            return matches
        return tuple(
            item
            for item in matches
            if item.entry.taxonomy_need_id
            not in BUYER_NEED_SCOPED_TAXONOMY_ENTRY_IDS_V0_2
        )


class BuyerNeedAnalysisPipelineV0_2:
    """Classify query intent first and publish BuyerNeedEvidence only for Need candidates."""

    def __init__(
        self,
        *,
        query_scope: BuyerNeedQueryScope,
        taxonomy: BuyerNeedTaxonomyRegistry = BUYER_NEED_TAXONOMY_V0_2,
    ) -> None:
        if not isinstance(query_scope, BuyerNeedQueryScope):
            raise BuyerNeedValidationError("V0.2 analysis requires an explicit query scope")
        if taxonomy.taxonomy_version != BUYER_NEED_TAXONOMY_VERSION_V0_2:
            raise BuyerNeedValidationError("V0.2 analysis requires taxonomy v0.2")
        self.query_scope = query_scope
        self.taxonomy = taxonomy
        self.intent_classifier = BuyerNeedQueryIntentClassifierV0_2(taxonomy=taxonomy)
        self.candidate_builder = BuyerNeedCandidateBuilderV0_2(
            query_scope=query_scope,
            taxonomy=taxonomy,
        )

    def analyze(
        self,
        text_evidence: BuyerNeedTextEvidence,
        *,
        product_context: BuyerNeedProductContext | None = None,
        category_context: BuyerNeedCategoryContext | None = None,
    ) -> BuyerNeedAnalysisResultV0_2:
        intent = self.intent_classifier.classify(
            text_evidence,
            query_scope=self.query_scope,
        )
        if intent.intent is BuyerNeedQueryIntent.NEED_CANDIDATE:
            candidates = self.candidate_builder.build(
                text_evidence,
                product_context=product_context,
                category_context=category_context,
            )
        else:
            candidates = ()
        payload = {
            "intent_evidence": intent,
            "buyer_need_candidates": candidates,
            "taxonomy_version": BUYER_NEED_TAXONOMY_VERSION_V0_2,
            "ruleset_version": BUYER_NEED_RULESET_VERSION_V0_2,
        }
        return BuyerNeedAnalysisResultV0_2(
            result_id=deterministic_id("buyer-need-analysis-v0.2", payload),
            **payload,
        )


__all__ = (
    "BuyerNeedAnalysisPipelineV0_2",
    "BuyerNeedCandidateBuilderV0_2",
)
