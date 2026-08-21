"""Context-aware Query Intent pipeline V0.3 with unchanged Taxonomy V0.2."""

from __future__ import annotations

from amazon_product_intelligence.contracts import deterministic_id

from .builder_v0_2 import BuyerNeedCandidateBuilderV0_2
from .errors import BuyerNeedValidationError
from .intent_v0_3 import BuyerNeedQueryIntentClassifierV0_3
from .models import (
    BuyerNeedCategoryContext,
    BuyerNeedProductContext,
    BuyerNeedTaxonomyRegistry,
    BuyerNeedTextEvidence,
)
from .models_v0_2 import (
    BUYER_NEED_RULESET_VERSION_V0_2,
    BUYER_NEED_TAXONOMY_VERSION_V0_2,
    BuyerNeedQueryIntent,
    BuyerNeedQueryScope,
)
from .models_v0_3 import (
    BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
    BuyerNeedAnalysisResultV0_3,
)
from .taxonomy_v0_2 import BUYER_NEED_TAXONOMY_V0_2


class BuyerNeedAnalysisPipelineV0_3:
    """Apply V0.3 Intent gates; only NEED_CANDIDATE reaches Taxonomy V0.2."""

    def __init__(
        self,
        *,
        query_scope: BuyerNeedQueryScope,
        taxonomy: BuyerNeedTaxonomyRegistry = BUYER_NEED_TAXONOMY_V0_2,
    ) -> None:
        if not isinstance(query_scope, BuyerNeedQueryScope):
            raise BuyerNeedValidationError("V0.3 analysis requires an explicit query scope")
        if taxonomy.taxonomy_version != BUYER_NEED_TAXONOMY_VERSION_V0_2:
            raise BuyerNeedValidationError("V0.3 analysis keeps taxonomy v0.2")
        self.query_scope = query_scope
        self.taxonomy = taxonomy
        self.intent_classifier = BuyerNeedQueryIntentClassifierV0_3(taxonomy=taxonomy)
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
    ) -> BuyerNeedAnalysisResultV0_3:
        intent = self.intent_classifier.classify(
            text_evidence,
            query_scope=self.query_scope,
        )
        if intent.primary_intent is BuyerNeedQueryIntent.NEED_CANDIDATE:
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
            "buyer_need_ruleset_version": BUYER_NEED_RULESET_VERSION_V0_2,
            "intent_ruleset_version": BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
        }
        return BuyerNeedAnalysisResultV0_3(
            result_id=deterministic_id("buyer-need-analysis-v0.3", payload),
            **payload,
        )


__all__ = ("BuyerNeedAnalysisPipelineV0_3",)
