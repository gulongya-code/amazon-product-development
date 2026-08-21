"""RapidFuzz-backed lexical similarity evidence V0.1."""

from __future__ import annotations

from decimal import Decimal

from rapidfuzz import __version__ as rapidfuzz_version
from rapidfuzz import fuzz

from amazon_product_intelligence.buyer_need_analysis import BuyerNeedEvidence
from amazon_product_intelligence.contracts import deterministic_id

from .errors import SemanticClusteringValidationError
from .models import (
    SemanticSimilarityEvidence,
    SemanticSimilarityMethod,
    ratio_text,
)
from .rules import (
    SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
    SemanticNormalizationRegistry,
)


class RapidFuzzLexicalSimilarity:
    """Create auditable pairwise evidence from canonical Buyer Need labels."""

    method = SemanticSimilarityMethod.LEXICAL

    def __init__(
        self,
        *,
        registry: SemanticNormalizationRegistry = SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
    ) -> None:
        if not isinstance(registry, SemanticNormalizationRegistry):
            raise SemanticClusteringValidationError(
                "lexical similarity requires SemanticNormalizationRegistry"
            )
        self.registry = registry
        self.model_version = f"rapidfuzz-{rapidfuzz_version}:fuzz.ratio"

    def compare(
        self,
        left: BuyerNeedEvidence,
        right: BuyerNeedEvidence,
    ) -> SemanticSimilarityEvidence:
        if not isinstance(left, BuyerNeedEvidence) or not isinstance(right, BuyerNeedEvidence):
            raise SemanticClusteringValidationError(
                "similarity inputs must be BuyerNeedEvidence"
            )
        if left.need_id == right.need_id:
            raise SemanticClusteringValidationError(
                "similarity evidence requires two distinct Buyer Needs"
            )
        source, target = sorted((left, right), key=lambda item: item.need_id)
        source_normalized = self.registry.normalize(source.need_label)
        target_normalized = self.registry.normalize(target.need_label)
        raw_score = fuzz.ratio(
            source_normalized.canonical_key,
            target_normalized.canonical_key,
        )
        score = ratio_text(Decimal(str(raw_score)) / Decimal("100"))
        references = tuple(
            sorted(
                {
                    evidence.text_id
                    for need in (source, target)
                    for evidence in need.source_evidence
                }
            )
        )
        payload = {
            "source_need_id": source.need_id,
            "target_need_id": target.need_id,
            "method": self.method,
            "score": score,
            "model_version": self.model_version,
            "evidence_reference": references,
        }
        return SemanticSimilarityEvidence(
            similarity_id=deterministic_id("semantic-similarity", payload),
            **payload,
        )


__all__ = ("RapidFuzzLexicalSimilarity",)
