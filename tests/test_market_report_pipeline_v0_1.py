from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from amazon_product_intelligence.buyer_need_analysis.intent_v0_3 import (
    BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3,
)
from amazon_product_intelligence.buyer_need_analysis.taxonomy_v0_2 import (
    BUYER_NEED_TAXONOMY_V0_2,
)
from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report import (
    MARKET_REPORT_JSON_SCHEMA,
    MARKET_REPORT_VERSION,
    BuyerNeedReportAdapter,
    CompetitionReportAdapter,
    MarketReportBuildRequest,
    MarketReportBuilderV0_1,
    MarketReportValidationError,
    OpportunityReportAdapter,
    ReportAvailability,
    validate_market_report_payload,
)
from amazon_product_intelligence.semantic_clustering.rules import (
    SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
)


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "market_report"
    / "market_report_input_v0_1.json"
)
EXAMPLE = Path(__file__).parents[1] / "docs" / "examples" / "market_report.json"


def fixture_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def request_from(payload: dict) -> MarketReportBuildRequest:
    return MarketReportBuildRequest(**payload)


class MarketReportPipelineV01Tests(unittest.TestCase):
    def test_report_schema_validation_and_strict_round_trip(self) -> None:
        report = MarketReportBuilderV0_1().build(request_from(fixture_payload()))
        reconstructed = validate_market_report_payload(report.to_dict())

        self.assertEqual(MARKET_REPORT_VERSION, report.report_version)
        self.assertEqual(report, reconstructed)
        self.assertFalse(MARKET_REPORT_JSON_SCHEMA["additionalProperties"])

        invalid = report.to_dict()
        invalid.pop("category")
        with self.assertRaises(MarketReportValidationError):
            validate_market_report_payload(invalid)

    def test_buyer_need_adapter_preserves_stable_output_and_lineage(self) -> None:
        source = fixture_payload()["buyer_need_output"]
        original = deepcopy(source)

        section, provenance = BuyerNeedReportAdapter().adapt(source)

        self.assertEqual(original, source)
        self.assertEqual("V0.3_STABLE", section.validation_status)
        self.assertEqual(
            ["Outdoor Portability", "Leak Prevention"],
            [item.need_label for item in section.needs],
        )
        self.assertEqual(0.27, section.needs[0].share)
        self.assertEqual("UNKNOWN", section.needs[0].confidence)
        self.assertEqual(
            ("buyer-need:portable-001", "buyer-need:portable-002"),
            section.needs[0].evidence_ids,
        )
        self.assertEqual("buyer_need_analysis", provenance[0].source_module)

    def test_competition_adapter_marks_absent_metrics_unavailable(self) -> None:
        payload = fixture_payload()
        competition = deepcopy(payload["competition_output"])
        competition.pop("brand_count")
        competition.pop("competition_concentration")
        competition.pop("competition_level")

        section, provenance = CompetitionReportAdapter().adapt(
            competition,
            market_analysis_output=payload["market_analysis_output"],
        )

        self.assertEqual(100, section.asin_count.value)
        self.assertEqual(ReportAvailability.AVAILABLE, section.price_distribution.availability)
        self.assertEqual(ReportAvailability.UNAVAILABLE, section.brand_count.availability)
        self.assertIsNone(section.brand_count.value)
        self.assertEqual(
            ReportAvailability.UNAVAILABLE,
            section.competition_concentration.availability,
        )
        self.assertEqual(
            {"competition_analysis", "market_analysis"},
            {item.source_module for item in provenance},
        )

    def test_opportunity_adapter_keeps_score_and_confidence_separate(self) -> None:
        source = fixture_payload()["opportunity_score_output"]
        original = deepcopy(source)

        section, provenance = OpportunityReportAdapter().adapt(source)

        self.assertEqual(original, source)
        self.assertEqual(82.0, section.score_value)
        self.assertEqual("LOW", section.confidence)
        self.assertEqual(5, len(section.dimensions))
        self.assertIn("Sales Evidence Partial", section.risks)
        self.assertTrue(provenance)

    def test_report_builder_is_deterministic_traceable_and_writable(self) -> None:
        payload = fixture_payload()
        original = deepcopy(payload)
        builder = MarketReportBuilderV0_1()

        first = builder.build(request_from(payload))
        reordered = deepcopy(payload)
        reordered["source_evidence_ids"].reverse()
        second = builder.build(request_from(reordered))

        self.assertEqual(original, payload)
        self.assertEqual(first.report_id, second.report_id)
        self.assertEqual(first.to_json(), second.to_json())
        self.assertEqual("dog water bottle", first.category.category_name)
        self.assertEqual(100, first.sample.sample_size)
        self.assertEqual(2, len(first.buyer_needs.needs))
        self.assertEqual(2, len(first.product_attributes))
        self.assertEqual("MEDIUM", first.competition.competition_level.value)
        self.assertEqual(82.0, first.opportunity_score.score_value)
        self.assertTrue(first.provenance)

        with TemporaryDirectory() as directory:
            target = Path(directory) / "market_report.json"
            builder.write_json(first, target)
            saved = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(first.report_id, saved["report_id"])
            self.assertEqual(first, validate_market_report_payload(saved))

    def test_checked_in_example_is_exact_builder_output(self) -> None:
        expected = MarketReportBuilderV0_1().build(request_from(fixture_payload()))
        example = json.loads(EXAMPLE.read_text(encoding="utf-8"))

        self.assertEqual(expected.to_dict(), example)
        self.assertEqual(expected, validate_market_report_payload(example))

    def test_buyer_need_v0_3_stable_registry_fingerprints_unchanged(self) -> None:
        expected = {
            BUYER_NEED_QUERY_INTENT_REGISTRY_V0_3: (
                "75f5accba6ad961e65849e0ee46933d361434144c251b512ae639d6523d21755"
            ),
            BUYER_NEED_TAXONOMY_V0_2: (
                "8db4987d3324d1b8ab14cd71f5190bb69a81d5e9a3ca9ca65e3a41f589ff59f6"
            ),
            SEMANTIC_NORMALIZATION_REGISTRY_V0_1: (
                "49ad3da401daded53c9cf1dc0272aa844919485598cd28a6667d2fee505e5eb2"
            ),
        }
        for registry, fingerprint in expected.items():
            actual = hashlib.sha256(
                canonical_json(registry.to_dict()).encode("utf-8")
            ).hexdigest()
            self.assertEqual(fingerprint, actual)


if __name__ == "__main__":
    unittest.main()
