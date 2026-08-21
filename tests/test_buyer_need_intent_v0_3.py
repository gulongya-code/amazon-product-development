from __future__ import annotations

import json
from pathlib import Path
import unittest

from amazon_product_intelligence.buyer_need_analysis import (
    BUYER_NEED_INTENT_RULESET_VERSION,
    BUYER_NEED_INTENT_RULESET_VERSION_V0_3,
    BUYER_NEED_QUERY_INTENT_REGISTRY_V0_2,
    BUYER_NEED_TAXONOMY_V0_2,
    BuyerNeedAnalysisPipelineV0_2,
    BuyerNeedAnalysisPipelineV0_3,
    BuyerNeedAnalysisResultV0_3,
    BuyerNeedIntentClassifierVersion,
    BuyerNeedQueryIntent,
    BuyerNeedQueryIntentClassifierV0_2,
    BuyerNeedQueryIntentClassifierV0_3,
    BuyerNeedQueryScope,
    BuyerNeedValidationError,
    IntentBoundaryV0_3,
    build_search_term_text_evidence,
    get_buyer_need_query_intent_classifier,
    replay_intent_precision_v0_3,
    replay_intent_regressions_v0_3,
)
from amazon_product_intelligence.contracts import (
    KeywordIdentity,
    canonical_json,
    keyword_id,
)
from amazon_product_intelligence.normalization import normalize_keyword_text


ROOT = Path(__file__).resolve().parents[1]
SP032E = ROOT / "docs" / "validation" / "ORGANIC_BUYER_NEED_HOLDOUT_100_V0.1.json"
SP032F = (
    ROOT
    / "docs"
    / "validation"
    / "ORGANIC_BUYER_NEED_TEMPORAL_HOLDOUT_V0.1.json"
)


def evidence(text: str):
    normalized = normalize_keyword_text(text)
    keyword = KeywordIdentity(
        keyword_id=keyword_id("US", "en-us", normalized),
        marketplace="US",
        locale="en-us",
        normalized_text=normalized,
        raw_text=text,
    )
    return build_search_term_text_evidence(keyword)


def analyze_v0_3(text: str):
    return BuyerNeedAnalysisPipelineV0_3(
        query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES
    ).analyze(evidence(text))


class BuyerNeedIntentV03BoundaryTests(unittest.TestCase):
    def test_pure_dog_water_bottle_is_product_object(self) -> None:
        result = analyze_v0_3("dog water bottle")

        self.assertIs(BuyerNeedQueryIntent.PRODUCT_OBJECT, result.intent_evidence.primary_intent)
        self.assertIs(IntentBoundaryV0_3.PURE_PRODUCT_OBJECT, result.intent_evidence.boundary)
        self.assertEqual((), result.buyer_need_candidates)

    def test_product_object_with_built_in_bowl_is_need_candidate(self) -> None:
        result = analyze_v0_3("dog water bottle with built-in bowl")

        self.assertIs(BuyerNeedQueryIntent.NEED_CANDIDATE, result.intent_evidence.primary_intent)
        self.assertIs(
            IntentBoundaryV0_3.PRODUCT_OBJECT_WITH_NEED_MODIFIER,
            result.intent_evidence.boundary,
        )
        self.assertEqual("Integrated Bowl", result.buyer_need_candidates[0].need_label)

    def test_travel_bag_is_accessory_related(self) -> None:
        result = analyze_v0_3("dog travel bag")

        self.assertIs(BuyerNeedQueryIntent.ACCESSORY_RELATED, result.intent_evidence.primary_intent)
        self.assertEqual(("travel",), result.intent_evidence.secondary_need_signals)

    def test_walking_accessories_cannot_enter_walking_need(self) -> None:
        result = analyze_v0_3("dog walking accessories")

        self.assertIs(BuyerNeedQueryIntent.ACCESSORY_RELATED, result.intent_evidence.primary_intent)
        self.assertEqual((), result.buyer_need_candidates)

    def test_travel_accessories_cannot_enter_outdoor_portability(self) -> None:
        result = analyze_v0_3("dog travel accessories")

        self.assertIs(BuyerNeedQueryIntent.ACCESSORY_RELATED, result.intent_evidence.primary_intent)
        self.assertNotIn("travel", [item.need_label for item in result.buyer_need_candidates])

    def test_brand_is_primary_intent(self) -> None:
        result = analyze_v0_3("TrailHound dog water bottle")

        self.assertIs(BuyerNeedQueryIntent.BRAND_MODEL, result.intent_evidence.primary_intent)
        self.assertIs(IntentBoundaryV0_3.BRAND_MODEL_PRIMARY, result.intent_evidence.boundary)

    def test_brand_with_explicit_modifier_preserves_secondary_signal(self) -> None:
        result = analyze_v0_3("TrailHound insulated dog water bottle")

        self.assertIs(BuyerNeedQueryIntent.BRAND_MODEL, result.intent_evidence.primary_intent)
        self.assertIs(
            IntentBoundaryV0_3.BRAND_WITH_SECONDARY_NEED_SIGNAL,
            result.intent_evidence.boundary,
        )
        self.assertEqual(("insulated",), result.intent_evidence.secondary_need_signals)
        self.assertEqual((), result.buyer_need_candidates)

    def test_generic_running_water_bottle_is_context_missing(self) -> None:
        result = analyze_v0_3("running water bottle")

        self.assertIs(BuyerNeedQueryIntent.AMBIGUOUS, result.intent_evidence.primary_intent)
        self.assertIs(IntentBoundaryV0_3.CONTEXT_MISSING, result.intent_evidence.boundary)

    def test_generic_insulated_water_bottle_is_not_dog_need(self) -> None:
        result = analyze_v0_3("insulated water bottle")

        self.assertIs(BuyerNeedQueryIntent.AMBIGUOUS, result.intent_evidence.primary_intent)
        self.assertEqual((), result.buyer_need_candidates)

    def test_portable_target_product_remains_need_candidate(self) -> None:
        result = analyze_v0_3("portable dog water bottle")

        self.assertIs(BuyerNeedQueryIntent.NEED_CANDIDATE, result.intent_evidence.primary_intent)
        self.assertIn("portable", [item.need_label for item in result.buyer_need_candidates])

    def test_travel_target_product_remains_need_candidate(self) -> None:
        result = analyze_v0_3("travel dog water bottle")

        self.assertIs(BuyerNeedQueryIntent.NEED_CANDIDATE, result.intent_evidence.primary_intent)
        self.assertIn("travel", [item.need_label for item in result.buyer_need_candidates])

    def test_hiking_rule_is_watched_not_removed(self) -> None:
        target = analyze_v0_3("hiking dog water bottle")
        broad = analyze_v0_3("dog hiking gear")

        self.assertIs(BuyerNeedQueryIntent.NEED_CANDIDATE, target.intent_evidence.primary_intent)
        self.assertIn("outdoor hiking", [item.need_label for item in target.buyer_need_candidates])
        self.assertIs(BuyerNeedQueryIntent.BROAD_QUERY, broad.intent_evidence.primary_intent)

    def test_context_contract_captures_required_gate_inputs(self) -> None:
        context = analyze_v0_3("portable dog water bottle").intent_evidence.context

        self.assertEqual("portable dog water bottle", context.normalized_query)
        self.assertIs(BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES, context.category_scope)
        self.assertIn("water bottle", context.product_object_matches)
        self.assertIn("portable", context.need_expression_matches)
        self.assertIn("category_qualifier=dog_or_pet", context.diagnostics)


class BuyerNeedIntentV03CompatibilityTests(unittest.TestCase):
    def test_explicit_version_selection_keeps_v0_2_replayable(self) -> None:
        direct = BuyerNeedQueryIntentClassifierV0_2().classify(
            evidence("dog travel accessories"),
            query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,
        )
        selected = get_buyer_need_query_intent_classifier(
            BuyerNeedIntentClassifierVersion.V0_2
        ).classify(
            evidence("dog travel accessories"),
            query_scope=BuyerNeedQueryScope.DOG_TRAVEL_WATER_BOTTLES,
        )

        self.assertIsInstance(
            get_buyer_need_query_intent_classifier(BUYER_NEED_INTENT_RULESET_VERSION),
            BuyerNeedQueryIntentClassifierV0_2,
        )
        self.assertIsInstance(
            get_buyer_need_query_intent_classifier(BUYER_NEED_INTENT_RULESET_VERSION_V0_3),
            BuyerNeedQueryIntentClassifierV0_3,
        )
        self.assertEqual(direct, selected)
        self.assertEqual(
            "buyer-need-query-intent-registry:099d6df1ed74a0e5098b98389e4472bb2eecb873881a907124fed21c34d04468",
            BUYER_NEED_QUERY_INTENT_REGISTRY_V0_2.registry_id,
        )

    def test_unsupported_classifier_version_is_rejected(self) -> None:
        with self.assertRaises(BuyerNeedValidationError):
            get_buyer_need_query_intent_classifier("buyer-need-intent-rules-v9")

    def test_v0_3_ids_are_deterministic(self) -> None:
        first = analyze_v0_3("dog water bottle with built-in bowl")
        second = analyze_v0_3("dog water bottle with built-in bowl")

        self.assertEqual(first.result_id, second.result_id)
        self.assertEqual(first.intent_evidence.intent_id, second.intent_evidence.intent_id)
        self.assertEqual(canonical_json(first), canonical_json(second))

    def test_v0_3_json_round_trip(self) -> None:
        result = analyze_v0_3("dog water bottle with built-in bowl")
        restored = BuyerNeedAnalysisResultV0_3.from_dict(
            json.loads(json.dumps(result.to_dict(), sort_keys=True))
        )

        self.assertEqual(result, restored)
        self.assertEqual(result.result_id, restored.result_id)

    def test_v0_3_keeps_taxonomy_v0_2_unchanged(self) -> None:
        before = BUYER_NEED_TAXONOMY_V0_2.registry_id
        result = analyze_v0_3("dog water bottle with built-in bowl")

        self.assertEqual(before, BUYER_NEED_TAXONOMY_V0_2.registry_id)
        self.assertEqual(BUYER_NEED_TAXONOMY_V0_2.taxonomy_version, result.taxonomy_version)
        self.assertEqual("buyer-need-rules-v0.2", result.buyer_need_ruleset_version)


class BuyerNeedIntentV03OfflineReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.e = json.loads(SP032E.read_text(encoding="utf-8"))
        cls.f = json.loads(SP032F.read_text(encoding="utf-8"))

    def test_sp032e_patch_replay_meets_precision_and_recall_targets(self) -> None:
        replay = replay_intent_precision_v0_3(self.e)

        self.assertEqual("0.8163265306122448979591836735", replay["v0_2"]["need_precision"])
        self.assertEqual("1", replay["v0_3"]["need_precision"])
        self.assertEqual("1", replay["v0_3"]["non_need_precision"])
        self.assertEqual("1", replay["v0_3"]["need_recall_proxy"])
        self.assertEqual(0, replay["v0_3"]["false_positive_count"])
        self.assertEqual(0, replay["v0_3"]["false_negative_count"])

    def test_sp032f_patch_replay_meets_precision_and_recall_targets(self) -> None:
        replay = replay_intent_precision_v0_3(self.f)

        self.assertEqual("0.84", replay["v0_2"]["need_precision"])
        self.assertEqual("1", replay["v0_3"]["need_precision"])
        self.assertEqual("1", replay["v0_3"]["non_need_precision"])
        self.assertEqual("1", replay["v0_3"]["need_recall_proxy"])
        self.assertEqual(0, replay["v0_3"]["false_positive_count"])
        self.assertEqual(0, replay["v0_3"]["false_negative_count"])

    def test_integrated_bowl_regression_is_100_percent(self) -> None:
        e = replay_intent_regressions_v0_3(self.e)["integrated_bowl"]
        f = replay_intent_regressions_v0_3(self.f)["integrated_bowl"]

        self.assertEqual((48, 48, "1"), (e["v0_2_candidate_count"], e["v0_3_retained_count"], e["recall"]))
        self.assertEqual((32, 32, "1"), (f["v0_2_candidate_count"], f["v0_3_retained_count"], f["recall"]))

    def test_outdoor_target_context_has_no_recall_collapse(self) -> None:
        for snapshot in (self.e, self.f):
            outdoor = replay_intent_regressions_v0_3(snapshot)["outdoor_portability"]
            for term in ("portable", "travel", "walking", "hiking"):
                with self.subTest(analysis=snapshot["analysis_id"], term=term):
                    self.assertGreater(outdoor[term]["target_context_count"], 0)
                    self.assertEqual("1", outdoor[term]["target_context_routing_recall"])


if __name__ == "__main__":
    unittest.main()
