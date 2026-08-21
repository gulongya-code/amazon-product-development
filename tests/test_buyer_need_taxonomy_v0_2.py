from __future__ import annotations

import json
from pathlib import Path
import unittest

from amazon_product_intelligence.buyer_need_analysis import (
    BUYER_NEED_TAXONOMY_PROPOSALS_V0_2,
    BUYER_NEED_TAXONOMY_V0_1,
    BUYER_NEED_TAXONOMY_V0_2,
    BUYER_NEED_TAXONOMY_VERSION,
    BUYER_NEED_TAXONOMY_VERSION_V0_2,
    CRATE_COMPATIBILITY_PROPOSAL_V0_2,
    INSULATED_TEMPERATURE_RETENTION_PROPOSAL_V0_2,
    BuyerNeedAnalysisPipelineV0_2,
    BuyerNeedAnalysisResultV0_2,
    BuyerNeedCandidateBuilder,
    BuyerNeedCandidateStatus,
    BuyerNeedConfidenceLevel,
    BuyerNeedQueryIntent,
    BuyerNeedQueryScope,
    BuyerNeedTaxonomyProposalStatus,
    BuyerNeedType,
    build_search_term_text_evidence,
    get_buyer_need_taxonomy,
)
from amazon_product_intelligence.contracts import (
    KeywordIdentity,
    canonical_json,
    keyword_id,
)
from amazon_product_intelligence.normalization import normalize_keyword_text
from amazon_product_intelligence.organic_keyword_discovery import (
    BuyerNeedTaxonomyReplayV0_2,
    replay_buyer_need_taxonomy_v0_2,
)
from amazon_product_intelligence.semantic_clustering import (
    SemanticClusterBuilder,
    SemanticClusteringValidationError,
)


ROOT = Path(__file__).resolve().parents[1]
SP032B_SNAPSHOT = (
    ROOT / "docs" / "validation" / "ORGANIC_BUYER_NEED_DISCOVERY_PILOT_V0.1.json"
)


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


def analyze(
    text: str,
    *,
    scope: BuyerNeedQueryScope = BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,
):
    _, evidence = search_term_evidence(text)
    return BuyerNeedAnalysisPipelineV0_2(query_scope=scope).analyze(evidence)


class BuyerNeedTaxonomyV02Tests(unittest.TestCase):
    def test_high_precision_non_need_intent_examples(self) -> None:
        cases = {
            "dog water bottle": BuyerNeedQueryIntent.PRODUCT_OBJECT,
            "PupFlask": BuyerNeedQueryIntent.BRAND_MODEL,
            "poop bags for dogs": BuyerNeedQueryIntent.ACCESSORY_RELATED,
            "dog accessories": BuyerNeedQueryIntent.BROAD_QUERY,
            "hamster water bottle": BuyerNeedQueryIntent.OUT_OF_SCOPE,
            "hemli": BuyerNeedQueryIntent.AMBIGUOUS,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                result = analyze(text)
                self.assertIs(expected, result.intent_evidence.intent)
                self.assertEqual((), result.buyer_need_candidates)
                self.assertEqual((), result.semantic_cluster_inputs)

    def test_product_object_rules_are_category_scoped(self) -> None:
        scoped = analyze("dog water bottle")
        unscoped = analyze("dog water bottle", scope=BuyerNeedQueryScope.UNKNOWN)

        self.assertIs(
            BuyerNeedQueryIntent.PRODUCT_OBJECT,
            scoped.intent_evidence.intent,
        )
        self.assertIs(
            BuyerNeedQueryIntent.NEED_CANDIDATE,
            unscoped.intent_evidence.intent,
        )
        self.assertIs(
            BuyerNeedCandidateStatus.UNKNOWN,
            unscoped.buyer_need_candidates[0].status,
        )

    def test_non_need_intent_preserves_keyword_provenance(self) -> None:
        keyword, evidence = search_term_evidence("dog water bottle")
        result = BuyerNeedAnalysisPipelineV0_2(
            query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
        ).analyze(evidence)

        source = result.intent_evidence.source_evidence
        self.assertEqual(keyword.keyword_id, source.source_reference.reference_id)
        self.assertEqual(evidence.text_id, source.text_id)
        self.assertTrue(result.intent_evidence.intent.is_non_need)

    def test_collapsible_recall_is_scoped_and_explicit(self) -> None:
        result = analyze("collapsible dog bowls")
        candidate = result.buyer_need_candidates[0]

        self.assertIs(BuyerNeedQueryIntent.NEED_CANDIDATE, result.intent_evidence.intent)
        self.assertIs(BuyerNeedCandidateStatus.CANDIDATE, candidate.status)
        self.assertIs(BuyerNeedType.SPECIFICATION_PREFERENCE, candidate.need_type)
        self.assertEqual("compact size / collapsible structure", candidate.need_label)
        self.assertEqual("collapsible dog bowls", candidate.source_evidence[0].span.matched_text)

        unscoped = analyze(
            "collapsible dog bowls",
            scope=BuyerNeedQueryScope.UNKNOWN,
        )
        self.assertIs(BuyerNeedCandidateStatus.UNKNOWN, unscoped.buyer_need_candidates[0].status)

    def test_integrated_bowl_is_the_only_formal_new_need(self) -> None:
        result = analyze("dog water bottle with built-in bowl")
        candidate = result.buyer_need_candidates[0]

        self.assertIs(BuyerNeedCandidateStatus.CANDIDATE, candidate.status)
        self.assertIs(BuyerNeedType.ATTRIBUTE_NEED, candidate.need_type)
        self.assertEqual("Integrated Bowl", candidate.need_label)
        self.assertEqual("built-in bowl", candidate.source_evidence[0].span.matched_text)

    def test_generic_dog_water_bowl_is_not_integrated_bowl(self) -> None:
        result = analyze("dog water bowl")

        self.assertIs(BuyerNeedQueryIntent.PRODUCT_OBJECT, result.intent_evidence.intent)
        self.assertEqual((), result.buyer_need_candidates)

    def test_crate_compatibility_is_low_confidence_and_holdout_required(self) -> None:
        result = analyze("water bottle for dog crate")
        candidate = result.buyer_need_candidates[0]

        self.assertIs(BuyerNeedCandidateStatus.CANDIDATE, candidate.status)
        self.assertIs(BuyerNeedType.COMPATIBILITY, candidate.need_type)
        self.assertEqual("compatibility requirement", candidate.need_label)
        self.assertIs(BuyerNeedConfidenceLevel.LOW, candidate.confidence.level)
        self.assertIs(
            BuyerNeedTaxonomyProposalStatus.ACTIVE_EXPERIMENTAL,
            CRATE_COMPATIBILITY_PROPOSAL_V0_2.status,
        )
        self.assertTrue(CRATE_COMPATIBILITY_PROPOSAL_V0_2.holdout_required)
        self.assertEqual(
            candidate.taxonomy_need_id,
            CRATE_COMPATIBILITY_PROPOSAL_V0_2.active_taxonomy_need_id,
        )

    def test_insulated_remains_proposal_only_and_unknown(self) -> None:
        result = analyze("insulated dog water bottle")
        candidate = result.buyer_need_candidates[0]

        self.assertIs(BuyerNeedQueryIntent.NEED_CANDIDATE, result.intent_evidence.intent)
        self.assertIs(BuyerNeedCandidateStatus.UNKNOWN, candidate.status)
        self.assertIs(
            BuyerNeedTaxonomyProposalStatus.PROPOSAL_ONLY,
            INSULATED_TEMPERATURE_RETENTION_PROPOSAL_V0_2.status,
        )
        self.assertIsNone(
            INSULATED_TEMPERATURE_RETENTION_PROPOSAL_V0_2.active_taxonomy_need_id
        )
        self.assertEqual(2, len(BUYER_NEED_TAXONOMY_PROPOSALS_V0_2))

    def test_non_need_cannot_enter_semantic_clustering(self) -> None:
        non_need = analyze("dog water bottle")
        integrated = analyze("dog water bottle with built-in bowl")

        self.assertEqual((), non_need.semantic_cluster_inputs)
        with self.assertRaises(SemanticClusteringValidationError):
            SemanticClusterBuilder().build((non_need.intent_evidence,))
        clustered = SemanticClusterBuilder().build(integrated.semantic_cluster_inputs)
        self.assertEqual(1, len(clustered.clusters))

    def test_v0_1_replay_ids_and_explicit_version_selection_are_unchanged(self) -> None:
        _, evidence = search_term_evidence("dog bottle for hiking")
        legacy = BuyerNeedCandidateBuilder().build(evidence)[0]

        self.assertEqual(BUYER_NEED_TAXONOMY_VERSION, legacy.taxonomy_version)
        self.assertEqual(
            "buyer-need-taxonomy:1389f2a73d55520c6949abcc00c9e52580407b324f2069abc7e9bce242b721c4",
            BUYER_NEED_TAXONOMY_V0_1.registry_id,
        )
        self.assertEqual(
            "buyer-need:a248776039a01da508c821229a338d73ee5756c9561f7b87b03057c7e07d7500",
            legacy.need_id,
        )
        self.assertIs(
            BUYER_NEED_TAXONOMY_V0_1,
            get_buyer_need_taxonomy(BUYER_NEED_TAXONOMY_VERSION),
        )
        self.assertIs(
            BUYER_NEED_TAXONOMY_V0_2,
            get_buyer_need_taxonomy(BUYER_NEED_TAXONOMY_VERSION_V0_2),
        )

    def test_v0_2_ids_are_deterministic_and_json_round_trip(self) -> None:
        first = analyze("dog water bottle with built-in bowl")
        second = analyze("dog water bottle with built-in bowl")

        self.assertEqual(first.result_id, second.result_id)
        self.assertEqual(canonical_json(first), canonical_json(second))
        restored = BuyerNeedAnalysisResultV0_2.from_dict(
            json.loads(json.dumps(first.to_dict(), sort_keys=True))
        )
        self.assertEqual(first, restored)
        self.assertEqual(first.result_id, restored.result_id)

    def test_offline_sp032b_replay_has_expected_v0_2_partition(self) -> None:
        snapshot = json.loads(SP032B_SNAPSHOT.read_text(encoding="utf-8"))
        replay = replay_buyer_need_taxonomy_v0_2(snapshot)
        distribution = {
            item.intent: item.relation_count for item in replay.intent_distribution
        }

        self.assertEqual(395, replay.raw_relation_count)
        self.assertEqual(207, replay.v0_1_matched_relation_count)
        self.assertEqual(188, replay.v0_1_unknown_relation_count)
        self.assertEqual(240, replay.v0_2_need_candidate_relation_count)
        self.assertEqual(229, replay.v0_2_matched_relation_count)
        self.assertEqual(11, replay.v0_2_unknown_need_candidate_relation_count)
        self.assertEqual(154, replay.v0_2_non_need_intent_relation_count)
        self.assertEqual(1, replay.v0_2_ambiguous_relation_count)
        self.assertEqual(383, replay.true_need_resolution_count)
        self.assertEqual("0.9696202531645569620253164557", replay.true_need_resolution_rate)
        self.assertEqual(12, replay.remaining_unresolved_count)
        self.assertEqual(89, distribution[BuyerNeedQueryIntent.PRODUCT_OBJECT])
        self.assertEqual(29, distribution[BuyerNeedQueryIntent.BRAND_MODEL])
        self.assertEqual(20, distribution[BuyerNeedQueryIntent.ACCESSORY_RELATED])
        self.assertEqual(13, distribution[BuyerNeedQueryIntent.BROAD_QUERY])
        self.assertEqual(3, distribution[BuyerNeedQueryIntent.OUT_OF_SCOPE])
        self.assertEqual(1, distribution[BuyerNeedQueryIntent.AMBIGUOUS])

        reversed_replay = replay_buyer_need_taxonomy_v0_2(
            {**snapshot, "organic_keyword_records": list(reversed(snapshot["organic_keyword_records"]))}
        )
        self.assertEqual(replay.replay_id, reversed_replay.replay_id)
        self.assertEqual(canonical_json(replay), canonical_json(reversed_replay))

    def test_replay_contract_json_round_trip(self) -> None:
        snapshot = json.loads(SP032B_SNAPSHOT.read_text(encoding="utf-8"))
        replay = replay_buyer_need_taxonomy_v0_2(snapshot)
        restored = BuyerNeedTaxonomyReplayV0_2.from_dict(
            json.loads(json.dumps(replay.to_dict(), sort_keys=True))
        )

        self.assertEqual(replay.replay_id, restored.replay_id)
        self.assertEqual(replay.remaining_unresolved_count, restored.remaining_unresolved_count)
        self.assertEqual(canonical_json(replay), canonical_json(restored))


if __name__ == "__main__":
    unittest.main()
