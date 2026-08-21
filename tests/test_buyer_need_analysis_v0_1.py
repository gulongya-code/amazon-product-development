from __future__ import annotations

import json
from pathlib import Path
import unittest

from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.buyer_need_analysis import (
    BUYER_NEED_TAXONOMY_V0_1,
    BUYER_NEED_TAXONOMY_VERSION,
    BuyerNeedCandidateBuilder,
    BuyerNeedCandidateStatus,
    BuyerNeedConfidenceLevel,
    BuyerNeedContextStatus,
    BuyerNeedEvidence,
    BuyerNeedSourceReferenceType,
    BuyerNeedTextSourceType,
    BuyerNeedType,
    build_review_text_evidence,
    build_search_term_text_evidence,
    build_source_reference,
    build_text_evidence,
)
from amazon_product_intelligence.contracts import (
    KeywordIdentity,
    ProductFactObservation,
    ProductIdentity,
    ReviewObservation,
    canonical_json,
    keyword_id,
    product_id,
)
from amazon_product_intelligence.normalization import normalize_keyword_text


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
ASIN = "B0G2VV4RBW"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"


def adaptation_context(payload_kind: str) -> AdaptationContext:
    return AdaptationContext(
        provider="sorftime",
        payload_kind=payload_kind,
        source_tool=payload_kind,
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:sorftime:{payload_kind}:buyer-need-test",
        sanitized_request={"asin": ASIN},
        currency="USD",
    )


def review_evidence(text: str):
    payload = json.loads(
        (FIXTURES / "sorftime_product_reviews.json").read_text(encoding="utf-8")
    )
    payload["data"][0]["content"] = text
    bundle = SorftimeAdapterV0_1().adapt(
        payload,
        adaptation_context("product_reviews"),
    ).bundle.validate()
    observation = next(
        item for item in bundle.observations if isinstance(item, ReviewObservation)
    )
    return observation, build_review_text_evidence(observation)


def search_term_evidence(text: str):
    normalized = normalize_keyword_text(text)
    keyword = KeywordIdentity(
        keyword_id=keyword_id("US", "en-us", normalized),
        marketplace="US",
        locale="en-us",
        normalized_text=normalized,
        raw_text=text,
    )
    return keyword, build_search_term_text_evidence(keyword)


def title_evidence(text: str):
    payload = json.loads(
        (FIXTURES / "sorftime_product_detail.json").read_text(encoding="utf-8")
    )
    payload["data"]["asin"] = ASIN
    payload["data"]["title"] = text
    payload["data"]["attributes"] = "{}"
    payload["data"].pop("parent_asin", None)
    bundle = SorftimeAdapterV0_1().adapt(
        payload,
        adaptation_context("product_detail"),
    ).bundle.validate()
    observation = next(
        item
        for item in bundle.observations
        if isinstance(item, ProductFactObservation) and item.dimension == "title"
    )
    identity = ProductIdentity(
        product_id=product_id("US", ASIN),
        marketplace="US",
        asin=ASIN,
        parent_asin=None,
        identity_status="CONFIRMED",
    )
    reference = build_source_reference(
        reference_type=BuyerNeedSourceReferenceType.PRODUCT_FACT_OBSERVATION,
        reference_id=observation.observation_id,
        canonical_observation_id=observation.observation_id,
        product_identity=identity,
        provenance=observation.provenance,
    )
    return observation, build_text_evidence(
        raw_text=text,
        source_type=BuyerNeedTextSourceType.TITLE,
        source_reference=reference,
    )


class BuyerNeedAnalysisV01Tests(unittest.TestCase):
    def test_review_extracts_problem_solution_candidate(self) -> None:
        observation, evidence = review_evidence("Doesn't leak in my backpack")
        candidates = BuyerNeedCandidateBuilder().build(evidence)

        self.assertEqual(1, len(candidates))
        candidate = candidates[0]
        self.assertIs(BuyerNeedType.PROBLEM_SOLUTION, candidate.need_type)
        self.assertEqual("prevent leaking", candidate.need_label)
        self.assertIs(BuyerNeedCandidateStatus.CANDIDATE, candidate.status)
        self.assertIs(BuyerNeedConfidenceLevel.HIGH, candidate.confidence.level)
        self.assertEqual("Doesn't leak", candidate.source_evidence[0].span.matched_text)
        self.assertEqual(observation.product, candidate.product_context.product_identities[0])

    def test_search_term_extracts_use_case_candidate(self) -> None:
        keyword, evidence = search_term_evidence("dog bottle for hiking")
        candidate = BuyerNeedCandidateBuilder().build(evidence)[0]

        self.assertIs(BuyerNeedType.USE_CASE, candidate.need_type)
        self.assertEqual("outdoor hiking", candidate.need_label)
        self.assertIs(BuyerNeedConfidenceLevel.HIGH, candidate.confidence.level)
        self.assertEqual(
            keyword.keyword_id,
            candidate.source_evidence[0].source_reference.reference_id,
        )
        self.assertIs(BuyerNeedContextStatus.UNKNOWN, candidate.product_context.status)
        self.assertIs(BuyerNeedContextStatus.UNKNOWN, candidate.category_context.status)

    def test_audience_candidate_preserves_explicit_span(self) -> None:
        _, evidence = search_term_evidence("bottle for large dogs")
        candidate = BuyerNeedCandidateBuilder().build(evidence)[0]

        self.assertIs(BuyerNeedType.AUDIENCE, candidate.need_type)
        self.assertEqual("large dogs", candidate.need_label)
        span = candidate.source_evidence[0].span
        self.assertEqual("for large dogs", span.matched_text)
        self.assertEqual(
            candidate.source_text[span.start : span.end],
            span.matched_text,
        )

    def test_listing_material_is_not_converted_directly_to_buyer_need(self) -> None:
        _, evidence = title_evidence("Stainless Steel Bottle")
        candidate = BuyerNeedCandidateBuilder().build(evidence)[0]

        self.assertIs(BuyerNeedType.UNKNOWN, candidate.need_type)
        self.assertIs(BuyerNeedCandidateStatus.UNKNOWN, candidate.status)
        self.assertNotEqual("stainless steel", candidate.need_label)
        self.assertIs(BuyerNeedConfidenceLevel.UNKNOWN, candidate.confidence.level)

    def test_quantity_is_a_specification_preference_not_general_need(self) -> None:
        _, evidence = title_evidence("20oz Bottle")
        candidate = BuyerNeedCandidateBuilder().build(evidence)[0]

        self.assertIs(BuyerNeedType.SPECIFICATION_PREFERENCE, candidate.need_type)
        self.assertEqual("20oz", candidate.need_label)
        self.assertIs(BuyerNeedConfidenceLevel.MEDIUM, candidate.confidence.level)

    def test_weak_search_term_signal_has_low_classification_confidence(self) -> None:
        _, evidence = search_term_evidence("stainless steel bottle")
        candidate = BuyerNeedCandidateBuilder().build(evidence)[0]

        self.assertIs(BuyerNeedType.SPECIFICATION_PREFERENCE, candidate.need_type)
        self.assertEqual("stainless steel", candidate.need_label)
        self.assertIs(BuyerNeedConfidenceLevel.LOW, candidate.confidence.level)
        self.assertIn(
            "confidence_represents_classification_evidence_not_demand_size",
            candidate.confidence.basis,
        )

    def test_review_evidence_lineage_preserves_asin_provenance_and_raw_text(self) -> None:
        observation, evidence = review_evidence("Doesn't leak in my backpack")
        candidate = BuyerNeedCandidateBuilder().build(evidence)[0]
        source = candidate.source_evidence[0]
        reference = source.source_reference

        self.assertEqual(observation.review_observation_id, reference.reference_id)
        self.assertEqual(observation.observation_id, reference.canonical_observation_id)
        self.assertEqual(ASIN, reference.product_identity.asin)
        self.assertEqual(observation.provenance, reference.provenance)
        self.assertEqual(
            observation.provenance.transformation.raw_evidence_reference,
            reference.provenance.transformation.raw_evidence_reference,
        )
        self.assertEqual("Doesn't leak in my backpack", source.raw_text)
        self.assertEqual("doesn't leak in my backpack", source.normalized_text)

    def test_unrecognized_text_returns_explicit_unknown(self) -> None:
        _, evidence = search_term_evidence("generic item")
        candidate = BuyerNeedCandidateBuilder().build(evidence)[0]

        self.assertIs(BuyerNeedType.UNKNOWN, candidate.need_type)
        self.assertEqual("UNKNOWN", candidate.need_label)
        self.assertIs(BuyerNeedCandidateStatus.UNKNOWN, candidate.status)
        self.assertTrue(candidate.diagnostics)
        self.assertEqual((), candidate.confidence.basis)
        self.assertEqual("generic item", candidate.source_text)

    def test_deterministic_id_and_json_safe_round_trip(self) -> None:
        _, first_evidence = search_term_evidence("dog bottle for hiking")
        _, second_evidence = search_term_evidence("dog bottle for hiking")
        builder = BuyerNeedCandidateBuilder()
        first = builder.build(first_evidence)[0]
        second = builder.build(second_evidence)[0]

        self.assertEqual(first.need_id, second.need_id)
        self.assertEqual(canonical_json(first), canonical_json(second))
        encoded = json.dumps(first.to_dict(), sort_keys=True)
        restored = BuyerNeedEvidence.from_dict(json.loads(encoded))
        self.assertEqual(first.need_id, restored.need_id)
        self.assertEqual(canonical_json(first), canonical_json(restored))

    def test_taxonomy_is_versioned_compact_and_covers_supported_types(self) -> None:
        self.assertEqual(
            BUYER_NEED_TAXONOMY_VERSION,
            BUYER_NEED_TAXONOMY_V0_1.taxonomy_version,
        )
        self.assertLess(len(BUYER_NEED_TAXONOMY_V0_1.entries), 50)
        self.assertEqual(
            set(BuyerNeedType) - {BuyerNeedType.UNKNOWN},
            {item.need_type for item in BUYER_NEED_TAXONOMY_V0_1.entries},
        )
        self.assertTrue(
            all(item.regex_patterns for item in BUYER_NEED_TAXONOMY_V0_1.entries)
        )


if __name__ == "__main__":
    unittest.main()
