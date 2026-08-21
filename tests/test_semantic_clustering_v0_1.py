from __future__ import annotations

import json
import unittest

from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedCandidateBuilder,
    BuyerNeedEvidence,
    build_search_term_text_evidence,
)
from amazon_product_intelligence.contracts import (
    KeywordIdentity,
    canonical_json,
    keyword_id,
)
from amazon_product_intelligence.normalization import normalize_keyword_text
from amazon_product_intelligence.semantic_clustering import (
    RapidFuzzLexicalSimilarity,
    SemanticClusterBuilder,
    SemanticClusteringConfig,
    SemanticClusteringResult,
    SemanticEmbeddingProvider,
    SemanticEmbeddingResult,
    SemanticSimilarityMethod,
)


def buyer_needs(text: str) -> tuple[BuyerNeedEvidence, ...]:
    normalized = normalize_keyword_text(text)
    keyword = KeywordIdentity(
        keyword_id=keyword_id("US", "en-us", normalized),
        marketplace="US",
        locale="en-us",
        normalized_text=normalized,
        raw_text=text,
    )
    evidence = build_search_term_text_evidence(keyword)
    return BuyerNeedCandidateBuilder().build(evidence)


def buyer_need(text: str, *, label: str | None = None) -> BuyerNeedEvidence:
    candidates = buyer_needs(text)
    if label is None:
        if len(candidates) != 1:
            raise AssertionError(f"expected one Buyer Need for {text!r}: {candidates!r}")
        return candidates[0]
    return next(item for item in candidates if item.need_label == label)


class FakeEmbeddingProvider:
    provider = "test-provider"
    model_name = "test-embedding"
    model_version = "0.0"

    def embed(self, normalized_text: str) -> SemanticEmbeddingResult:
        return SemanticEmbeddingResult(
            normalized_text=normalized_text,
            vector=(0.25, 0.75),
            provider=self.provider,
            model_name=self.model_name,
            model_version=self.model_version,
        )


class SemanticClusteringV01Tests(unittest.TestCase):
    def test_synonymous_expressions_join_same_explainable_cluster(self) -> None:
        portable = buyer_need("portable")
        easy_carry = buyer_need("easy to carry")
        hiking = buyer_need("great for hiking")

        result = SemanticClusterBuilder().build((portable, easy_carry, hiking))

        self.assertEqual(1, len(result.clusters))
        cluster = result.clusters[0]
        self.assertEqual("Outdoor Portability", cluster.cluster_label)
        self.assertEqual(
            {portable.need_id, easy_carry.need_id, hiking.need_id},
            set(cluster.source_need_ids),
        )
        self.assertEqual(cluster.cluster_label, SemanticClusterBuilder().regenerate_label(cluster))

    def test_lexical_spacing_variant_joins_same_cluster(self) -> None:
        leakproof = buyer_need("leakproof bottle")
        leak_proof = buyer_need("leak proof bottle")

        result = SemanticClusterBuilder().build((leakproof, leak_proof))

        self.assertEqual(1, len(result.clusters))
        self.assertEqual("Leak Prevention", result.clusters[0].cluster_label)

    def test_different_needs_remain_separate(self) -> None:
        capacity = buyer_need("large capacity")
        leakproof = buyer_need("leakproof")

        result = SemanticClusterBuilder().build((capacity, leakproof))

        self.assertEqual(2, len(result.clusters))
        self.assertEqual(
            {frozenset((capacity.need_id,)), frozenset((leakproof.need_id,))},
            {frozenset(item.source_need_ids) for item in result.clusters},
        )

    def test_cluster_members_preserve_need_and_original_evidence_lineage(self) -> None:
        portable = buyer_need("portable")
        easy_carry = buyer_need("easy to carry")

        cluster = SemanticClusterBuilder().build((portable, easy_carry)).clusters[0]

        self.assertEqual((portable.source_evidence[0].text_id,), next(
            item.evidence_reference
            for item in cluster.cluster_members
            if item.need_id == portable.need_id
        ))
        embedded = {item.need_id: item for item in cluster.source_needs}
        self.assertEqual(portable, embedded[portable.need_id])
        self.assertEqual(
            portable.source_evidence[0].source_reference.reference_id,
            embedded[portable.need_id].source_evidence[0].source_reference.reference_id,
        )

    def test_pairwise_similarity_evidence_is_present_and_traceable(self) -> None:
        portable = buyer_need("portable")
        easy_carry = buyer_need("easy to carry")

        result = SemanticClusterBuilder().build((portable, easy_carry))

        self.assertEqual(1, len(result.similarity_evidence))
        evidence = result.similarity_evidence[0]
        self.assertIs(SemanticSimilarityMethod.LEXICAL, evidence.method)
        self.assertEqual("1", evidence.score)
        self.assertEqual(
            {
                portable.source_evidence[0].text_id,
                easy_carry.source_evidence[0].text_id,
            },
            set(evidence.evidence_reference),
        )
        self.assertTrue(evidence.model_version.startswith("rapidfuzz-"))
        direct = RapidFuzzLexicalSimilarity().compare(portable, easy_carry)
        self.assertEqual(evidence, direct)

    def test_similarity_threshold_is_configurable(self) -> None:
        large_dogs = buyer_need("for large dogs")
        small_dogs = buyer_need("for small dogs")

        permissive = SemanticClusterBuilder(
            config=SemanticClusteringConfig(lexical_threshold="0.6")
        ).build((large_dogs, small_dogs))
        strict = SemanticClusterBuilder(
            config=SemanticClusteringConfig(lexical_threshold="0.61")
        ).build((large_dogs, small_dogs))

        self.assertEqual(1, len(permissive.clusters))
        self.assertEqual(2, len(strict.clusters))

    def test_unknown_is_preserved_but_never_clustered(self) -> None:
        known = buyer_need("portable")
        unknown = buyer_need("generic item")

        result = SemanticClusterBuilder().build((known, unknown))

        self.assertIn(unknown, result.source_needs)
        self.assertEqual((unknown.need_id,), result.excluded_unknown_need_ids)
        self.assertNotIn(
            unknown.need_id,
            {need_id for cluster in result.clusters for need_id in cluster.source_need_ids},
        )
        self.assertEqual("UNKNOWN_BUYER_NEED_EXCLUDED", result.diagnostics[0].code)

    def test_output_and_ids_are_deterministic_and_json_safe(self) -> None:
        needs = (buyer_need("portable"), buyer_need("easy to carry"))
        builder = SemanticClusterBuilder()

        first = builder.build(needs)
        second = builder.build(tuple(reversed(needs)))

        self.assertEqual(first.result_id, second.result_id)
        self.assertEqual(first.clusters[0].cluster_id, second.clusters[0].cluster_id)
        self.assertEqual(canonical_json(first), canonical_json(second))
        encoded = json.dumps(first.to_dict(), sort_keys=True)
        restored = SemanticClusteringResult.from_dict(json.loads(encoded))
        self.assertEqual(first, restored)
        self.assertEqual(canonical_json(first), canonical_json(restored))

    def test_embedding_provider_contract_needs_no_real_model(self) -> None:
        provider = FakeEmbeddingProvider()

        self.assertIsInstance(provider, SemanticEmbeddingProvider)
        result = provider.embed("portable product")
        self.assertEqual((0.25, 0.75), result.vector)
        self.assertEqual("test-provider", result.provider)
        self.assertEqual("test-embedding", result.model_name)
        self.assertEqual("0.0", result.model_version)
        self.assertEqual(result, SemanticEmbeddingResult.from_dict(result.to_dict()))


if __name__ == "__main__":
    unittest.main()
