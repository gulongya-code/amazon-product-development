from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import unittest

from amazon_product_intelligence.category_product_map import (
    CategoryProductMapBuilderV0_1,
    CategoryProductMapRequest,
    CategoryScopeType,
    build_category_scope,
    unknown_analysis_window,
)
from amazon_product_intelligence.competition_intelligence import (
    CompetitionIntelligenceBuilderV0_1,
    CompetitionIntelligenceRequest,
)
from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.opportunity_intelligence.integration_v0_1 import (
    CompetitionLevel,
    OpportunityCandidateBuilderV0_1,
    OpportunityCandidateClassifierV0_1,
    OpportunityCandidateRequest,
    OpportunityCandidateSnapshot,
    OpportunityCandidateType,
    OpportunityConfidence,
    OpportunityEvidenceSource,
    OpportunityEvidenceStatus,
    OpportunityIntegrationValidationError,
)
from amazon_product_intelligence.product_attribute_extraction import ProductGrain

from tests.test_competition_intelligence_v0_1 import adapt
from tests.test_supply_demand_gap_v0_1 import gap_for, profiles_for


class OpportunityCandidateFixtureCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.high_demand_low_supply_gap = gap_for(30, 1)
        cls.low_demand_gap = gap_for(10, 1)
        cls.missing_demand_gap = gap_for(None, 1)
        cls.profiles = profiles_for(1)
        bundle = adapt(
            provider="xiyou",
            fixture="xiyou_keyword_forward_populated.json",
            payload_kind="keyword_asin_analysis",
            source_tool="get_keyword_asin_analysis",
            request={"keyword": "plastic spoons"},
        )
        cls.competition = CompetitionIntelligenceBuilderV0_1().build(
            CompetitionIntelligenceRequest(canonical_bundles=(bundle,))
        )
        cls.builder = OpportunityCandidateBuilderV0_1()
        cls.classifier = OpportunityCandidateClassifierV0_1()

    def request_for(self, gap):
        return OpportunityCandidateRequest(
            buyer_need_map=gap.evidence.buyer_need_map,
            category_product_map=gap.evidence.category_product_map,
            supply_demand_gap=gap,
            competition_intelligence=self.competition,
            product_attribute_profiles=self.profiles,
        )

    def candidate_for(self, gap):
        return self.builder.build(self.request_for(gap))


class OpportunityCandidateClassificationTests(OpportunityCandidateFixtureCase):
    def test_high_demand_low_supply_and_low_competition_is_potential_entry_area(self) -> None:
        result = self.classifier.classify(
            demand_status=OpportunityEvidenceStatus.AVAILABLE,
            supply_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_type=self.high_demand_low_supply_gap.gap_type,
            competition_status=OpportunityEvidenceStatus.AVAILABLE,
            competition_level=CompetitionLevel.LOW,
        )
        self.assertIs(result, OpportunityCandidateType.POTENTIAL_ENTRY_AREA)

    def test_high_demand_low_supply_and_high_competition_needs_validation(self) -> None:
        result = self.classifier.classify(
            demand_status=OpportunityEvidenceStatus.AVAILABLE,
            supply_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_type=self.high_demand_low_supply_gap.gap_type,
            competition_status=OpportunityEvidenceStatus.AVAILABLE,
            competition_level=CompetitionLevel.HIGH,
        )
        self.assertIs(result, OpportunityCandidateType.NEEDS_VALIDATION)

    def test_high_demand_high_supply_and_high_competition_is_high_competition_area(self) -> None:
        result = self.classifier.classify(
            demand_status=OpportunityEvidenceStatus.AVAILABLE,
            supply_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_type=self.high_demand_low_supply_gap.gap_type.HIGH_DEMAND_HIGH_SUPPLY,
            competition_status=OpportunityEvidenceStatus.AVAILABLE,
            competition_level=CompetitionLevel.HIGH,
        )
        self.assertIs(result, OpportunityCandidateType.HIGH_COMPETITION_AREA)

    def test_low_demand_is_low_demand_area(self) -> None:
        candidate = self.candidate_for(self.low_demand_gap)
        self.assertIs(candidate.status, OpportunityCandidateType.LOW_DEMAND_AREA)

    def test_missing_demand_is_insufficient_evidence(self) -> None:
        candidate = self.candidate_for(self.missing_demand_gap)
        self.assertIs(candidate.status, OpportunityCandidateType.INSUFFICIENT_EVIDENCE)
        self.assertTrue(candidate.evidence.missing_evidence_ids)
        self.assertIn(
            "DEMAND_EVIDENCE_UNKNOWN",
            {item.code for item in candidate.diagnostics},
        )

    def test_partial_competition_requires_validation_without_changing_gap(self) -> None:
        candidate = self.candidate_for(self.high_demand_low_supply_gap)
        self.assertIs(candidate.status, OpportunityCandidateType.NEEDS_VALIDATION)
        self.assertIs(
            candidate.evidence.gap.gap_type,
            self.high_demand_low_supply_gap.gap_type,
        )
        self.assertIs(candidate.evidence.competition.status, OpportunityEvidenceStatus.PARTIAL)


class OpportunityCandidateEvidenceTests(OpportunityCandidateFixtureCase):
    def test_evidence_lineage_references_every_required_upstream_layer(self) -> None:
        candidate = self.candidate_for(self.high_demand_low_supply_gap)
        references = {item.source: item for item in candidate.evidence.source_references}
        self.assertEqual(
            references[OpportunityEvidenceSource.BUYER_NEED_MAP].source_id,
            self.high_demand_low_supply_gap.evidence.buyer_need_map.map_id,
        )
        self.assertEqual(
            references[OpportunityEvidenceSource.CATEGORY_PRODUCT_MAP].source_id,
            self.high_demand_low_supply_gap.evidence.category_product_map.map_id,
        )
        self.assertEqual(
            candidate.gap_reference.source_id,
            self.high_demand_low_supply_gap.gap_id,
        )
        self.assertEqual(
            candidate.competition_reference.source_id,
            self.competition.snapshot_id,
        )
        self.assertIn(OpportunityEvidenceSource.PRODUCT_ATTRIBUTE_PROFILE, references)
        self.assertIs(
            candidate.economic_reference.source,
            OpportunityEvidenceSource.UNKNOWN_ECONOMIC_EVIDENCE,
        )

    def test_confidence_is_separate_from_candidate_classification(self) -> None:
        candidate = self.candidate_for(self.high_demand_low_supply_gap)
        self.assertIs(candidate.status, OpportunityCandidateType.NEEDS_VALIDATION)
        self.assertIs(candidate.confidence, OpportunityConfidence.LOW)
        potential = self.classifier.classify(
            demand_status=OpportunityEvidenceStatus.AVAILABLE,
            supply_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_status=OpportunityEvidenceStatus.AVAILABLE,
            gap_type=self.high_demand_low_supply_gap.gap_type,
            competition_status=OpportunityEvidenceStatus.AVAILABLE,
            competition_level=CompetitionLevel.LOW,
        )
        self.assertIs(potential, OpportunityCandidateType.POTENTIAL_ENTRY_AREA)

    def test_unknown_is_not_converted_to_zero_or_a_competition_level(self) -> None:
        candidate = self.candidate_for(self.high_demand_low_supply_gap)
        self.assertIs(
            candidate.evidence.competition.market_concentration.status,
            OpportunityEvidenceStatus.UNKNOWN,
        )
        self.assertIs(
            candidate.evidence.competition.market_concentration.level,
            CompetitionLevel.UNKNOWN,
        )
        self.assertIs(
            candidate.evidence.economic.market_size_signal.status,
            OpportunityEvidenceStatus.UNKNOWN,
        )
        self.assertIsNone(candidate.evidence.economic.market_size_signal.value)

    def test_candidate_builder_is_read_only(self) -> None:
        request = self.request_for(self.high_demand_low_supply_gap)
        before = (
            canonical_json(request.buyer_need_map),
            canonical_json(request.category_product_map),
            canonical_json(request.supply_demand_gap),
            canonical_json(request.competition_intelligence),
            tuple(canonical_json(item) for item in request.product_attribute_profiles),
        )
        self.builder.build(request)
        after = (
            canonical_json(request.buyer_need_map),
            canonical_json(request.category_product_map),
            canonical_json(request.supply_demand_gap),
            canonical_json(request.competition_intelligence),
            tuple(canonical_json(item) for item in request.product_attribute_profiles),
        )
        self.assertEqual(after, before)


class OpportunityCandidateContractTests(OpportunityCandidateFixtureCase):
    def test_candidate_id_is_deterministic(self) -> None:
        first = self.candidate_for(self.high_demand_low_supply_gap)
        second = self.candidate_for(self.high_demand_low_supply_gap)
        self.assertEqual(first.candidate_id, second.candidate_id)
        self.assertEqual(canonical_json(first), canonical_json(second))

    def test_scope_mismatch_is_rejected(self) -> None:
        different_map = CategoryProductMapBuilderV0_1().build(
            CategoryProductMapRequest(
                category_scope=build_category_scope(
                    scope_type=CategoryScopeType.INPUT_COHORT,
                    scope_value="different-opportunity-scope",
                    inclusion_rule="A deliberately distinct scope for validation.",
                ),
                marketplace="US",
                analysis_window=unknown_analysis_window(),
                product_grain=ProductGrain.CHILD_ASIN,
                product_profiles=self.profiles,
                combination_dimensions=(),
            )
        )
        with self.assertRaises(OpportunityIntegrationValidationError):
            OpportunityCandidateRequest(
                buyer_need_map=self.high_demand_low_supply_gap.evidence.buyer_need_map,
                category_product_map=different_map,
                supply_demand_gap=self.high_demand_low_supply_gap,
                competition_intelligence=self.competition,
                product_attribute_profiles=self.profiles,
            )

    def test_strict_serialization_round_trip_and_unknown_field_rejection(self) -> None:
        candidate = self.candidate_for(self.high_demand_low_supply_gap)
        reconstructed = OpportunityCandidateSnapshot.from_dict(
            json.loads(canonical_json(candidate))
        )
        self.assertEqual(reconstructed, candidate)
        payload = candidate.to_dict()
        payload["unexpected"] = "not allowed"
        with self.assertRaises(Exception):
            OpportunityCandidateSnapshot.from_dict(payload)

    def test_candidate_is_immutable(self) -> None:
        candidate = self.candidate_for(self.high_demand_low_supply_gap)
        with self.assertRaises(FrozenInstanceError):
            candidate.status = OpportunityCandidateType.LOW_DEMAND_AREA  # type: ignore[misc]

    def test_candidate_output_has_no_forbidden_recommendation_vocabulary(self) -> None:
        payload = canonical_json(self.candidate_for(self.high_demand_low_supply_gap)).casefold()
        for forbidden in (
            "good_product",
            "best_product",
            "recommend_build",
            "should_launch",
            "winner_product",
            "product_recommendation",
        ):
            self.assertNotIn(forbidden, payload)


if __name__ == "__main__":
    unittest.main()
