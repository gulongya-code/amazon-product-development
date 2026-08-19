from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import unittest

from amazon_product_intelligence.calculations import CalculationStatus
from amazon_product_intelligence.competition_analysis import (
    CompetitionAnalysisBuilderV0_1,
    CompetitionAnalysisRequest,
)
from amazon_product_intelligence.contracts import NormalizationStatus, PresenceStatus, SemanticStatus
from amazon_product_intelligence.market_analysis import MarketAnalysisStatus, MarketMetricStatus
from tests.test_data_cleaning_e2e_v0_1 import cleaning_request, service_for


def clean(operation: str, body: object, *, run_id: str, parameters: dict[str, object]):
    request = replace(
        cleaning_request("xiyou", operation, parameters),
        collection_run_id=f"collection:{run_id}",
        normalization_run_id=f"normalization:{run_id}",
    )
    return service_for("xiyou", operation, body).clean(request)


def product_info():
    return clean(
        "asin_info",
        {
            "entities": [
                {"asin": "B000000001", "country": "US", "title": "A", "currency": "USD", "price": "10", "stars": "4.0", "ratings": 0},
                {"asin": "B000000002", "country": "US", "title": "B", "currency": "USD", "price": "20", "stars": "5", "ratings": 20},
            ]
        },
        run_id="products",
        parameters={"entities": []},
    )


def bsr(asin: str, rank: int, *, category_id: str = "100", name: str = "Category"):
    return clean(
        "asin_bsr_trends",
        {
            "country": "US",
            "asin": asin,
            "categoryTree": [{"categoryId": category_id, "name": name, "root": False}],
            "trends": [{"date": "2026-08-18", "values": [{"categoryId": category_id, "rank": rank}]}],
        },
        run_id=f"bsr-{asin}-{category_id}",
        parameters={"country": "US", "asin": asin, "startDate": "2026-08-18", "endDate": "2026-08-18"},
    )


def variation():
    return clean(
        "asin_variations",
        {
            "country": "US",
            "asin": "B000000001",
            "parentAsin": "B000000099",
            "childAsins": ["B000000001", "B000000002"],
            "lastUpdatedTime": "2026-08-18 00:00:00",
        },
        run_id="variations",
        parameters={"country": "US", "asin": "B000000001"},
    )


def analyze(*results):
    return CompetitionAnalysisBuilderV0_1().build(
        CompetitionAnalysisRequest(marketplace="US", clean_results=tuple(results))
    )


class CleaningBoundaryTests(unittest.TestCase):
    def test_bsr_context_is_metadata_not_a_duplicate_value_field(self) -> None:
        cleaned = bsr("B000000001", 24)
        self.assertEqual(
            [field.canonical_field for field in cleaned.fields],
            ["metric.bsr"],
        )
        self.assertEqual(cleaned.fields[0].rank_context["category_id"], "100")
        self.assertEqual(cleaned.fields[0].provenance.source_field, "trends[0].values[0].rank")
        self.assertNotIn("UNSUPPORTED_FIELD", {issue.issue_code for issue in cleaned.issues})

    def test_variation_cleaning_preserves_explicit_parent_child_context(self) -> None:
        cleaned = variation()
        rows = [field for field in cleaned.fields if field.canonical_field == "product.variation"]
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(field.normalization_status is NormalizationStatus.NORMALIZED for field in rows))
        self.assertEqual(
            {(field.variation_parent_product_id, field.variation_child_product_id) for field in rows},
            {
                ("product:US:B000000099", "product:US:B000000001"),
                ("product:US:B000000099", "product:US:B000000002"),
            },
        )


class CompetitionCoreMetricTests(unittest.TestCase):
    def test_reuses_count_rating_review_and_mechanically_matches(self) -> None:
        result = analyze(product_info(), bsr("B000000001", 10), bsr("B000000002", 30))
        self.assertEqual(result.observed_product_count.status, CalculationStatus.CALCULATED)
        self.assertEqual(result.observed_product_count.value, 2)
        self.assertEqual(result.rating_summary.distribution.to_dict(), {"minimum": "4", "maximum": "5", "mean": "4.5", "median": "4.5"})
        self.assertEqual(result.review_count_summary.distribution.to_dict(), {"minimum": "0", "maximum": "20", "mean": "10", "median": "10"})
        self.assertEqual(len(result.bsr_summaries), 1)
        summary = result.bsr_summaries[0].summary
        self.assertEqual(summary.status, MarketMetricStatus.CALCULATED)
        self.assertEqual(summary.valid_sample_count, 2)
        self.assertEqual(summary.distribution.to_dict(), {"minimum": "10", "maximum": "30", "mean": "20", "median": "20"})
        self.assertEqual(summary.provenance.calculation_version, "v0.1-exact-rank-context-summary")
        self.assertEqual(len(summary.provenance.input_lineage), 2)

    def test_bsr_different_categories_are_never_averaged_together(self) -> None:
        result = analyze(
            product_info(),
            bsr("B000000001", 10, category_id="100", name="A"),
            bsr("B000000002", 1000, category_id="200", name="B"),
        )
        self.assertEqual(len(result.bsr_summaries), 2)
        self.assertEqual({item.summary.valid_sample_count for item in result.bsr_summaries}, {1})
        self.assertEqual(
            {item.summary.distribution.mean for item in result.bsr_summaries},
            {Decimal(10), Decimal(1000)},
        )
        self.assertTrue(all(item.summary.status is MarketMetricStatus.PARTIAL for item in result.bsr_summaries))

    def test_bsr_without_complete_context_is_excluded_and_explicitly_blocked(self) -> None:
        cleaned = bsr("B000000001", 24)
        uncontextualized = replace(cleaned.fields[0], rank_context=None)
        cleaned = replace(cleaned, fields=(uncontextualized,))
        result = analyze(product_info(), cleaned)
        self.assertFalse(result.bsr_summaries)
        blocked = {metric.metric_id: metric.reason_code for metric in result.blocked_metrics}
        self.assertEqual(
            blocked["competition_analysis.bsr_uncontextualized_input"],
            "INCOMPLETE_RANK_CONTEXT",
        )
        self.assertEqual(result.status, MarketAnalysisStatus.PARTIAL)

    def test_missing_invalid_and_zero_follow_quality_gate(self) -> None:
        info = product_info()
        rating_fields = [field for field in info.fields if field.canonical_field == "metric.rating"]
        invalid = replace(
            rating_fields[1],
            raw_value="bad",
            mapped_value="bad",
            normalized_value=None,
            presence_status=PresenceStatus.PRESENT,
            normalization_status=NormalizationStatus.FAILED,
            semantic_status=SemanticStatus.INVALID,
            application=None,
        )
        info = replace(
            info,
            fields=tuple(invalid if field is rating_fields[1] else field for field in info.fields),
        )
        result = analyze(info)
        self.assertEqual(result.rating_summary.valid_sample_count, 1)
        self.assertEqual(result.rating_summary.excluded_invalid_count, 1)
        self.assertEqual(result.review_count_summary.distribution.minimum, Decimal(0))
        self.assertEqual(result.status, MarketAnalysisStatus.PARTIAL)

    def test_empty_input_is_explicit_and_seller_stays_unknown(self) -> None:
        result = analyze()
        self.assertEqual(result.status, MarketAnalysisStatus.EMPTY)
        blocked = {metric.metric_id: metric.reason_code for metric in result.blocked_metrics}
        self.assertEqual(blocked["competition_analysis.seller_count"], "SELLER_IDENTITY_UNAVAILABLE")
        self.assertEqual(blocked["competition_analysis.bsr_summary"], "RANK_CONTEXT_UNAVAILABLE")


class VariationAndNeutralityTests(unittest.TestCase):
    def test_variation_grains_are_separate_and_ambiguous_metric_stays_blocked(self) -> None:
        result = analyze(product_info(), variation())
        structure = result.variation_structure
        self.assertEqual(structure.source_record_count, 2)
        self.assertEqual(structure.unique_parent_child_pair_count, 2)
        self.assertEqual(structure.unique_parent_count, 1)
        self.assertEqual(structure.unique_child_count, 2)
        self.assertEqual(structure.duplicate_source_record_count, 0)
        self.assertIn("product:US:B000000099", result.scope.product_ids)
        blocked = {metric.metric_id: metric.reason_code for metric in result.blocked_metrics}
        self.assertEqual(
            blocked["workbook.competition_evidence.variation_evidence_count"],
            "SEMANTIC_AMBIGUITY",
        )

    def test_output_is_deterministic_and_provider_payload_is_not_an_input(self) -> None:
        inputs = (product_info(), bsr("B000000001", 7), variation())
        first = analyze(*inputs)
        second = analyze(*reversed(inputs))
        self.assertEqual(first.to_json(indent=None), second.to_json(indent=None))
        self.assertTrue(all(field.provenance is not None for field in inputs[0].fields if field.observation_id))
        self.assertNotIn("XiYou", type(first).__name__)


if __name__ == "__main__":
    unittest.main()
