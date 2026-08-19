from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.calculations import CalculationStatus
from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
)
from amazon_product_intelligence.market_analysis import (
    MarketAnalysisBuilderV0_1,
    MarketAnalysisRequest,
    MarketAnalysisStatus,
    MarketMetricStatus,
)
from tests.test_data_cleaning_e2e_v0_1 import cleaning_request, payload, service_for


ROOT = Path(__file__).resolve().parents[1]
PROVIDER_FIXTURES = ROOT / "tests" / "fixtures" / "provider_adapters" / "v0_1"


def product(
    asin: str,
    *,
    price: object = "10.00",
    currency: str = "USD",
    stars: object = "4.0",
    ratings: object = 10,
    include_price: bool = True,
) -> dict[str, object]:
    value: dict[str, object] = {
        "asin": asin,
        "country": "US",
        "currency": currency,
        "stars": stars,
        "ratings": ratings,
        "title": f"Product {asin}",
    }
    if include_price:
        value["price"] = price
    return value


def clean_products(*entities: dict[str, object]):
    body = {"entities": list(entities)}
    return service_for("xiyou", "asin_info", body).clean(
        cleaning_request("xiyou", "asin_info", {"entities": []})
    )


def analyze(clean_result):
    return MarketAnalysisBuilderV0_1().build(
        MarketAnalysisRequest(marketplace="US", clean_results=(clean_result,))
    )


class ProductNumericSummaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.clean = clean_products(
            product("B000000001", price="10.00", stars="4.0", ratings=0),
            product("B000000002", price="20", stars=5, ratings=10),
        )
        self.analysis = analyze(self.clean)

    def test_price_summary_has_explicit_deterministic_formula_and_unit(self) -> None:
        metric = self.analysis.numeric_metric("market_analysis.observed_product_price")
        self.assertEqual(metric.status, MarketMetricStatus.CALCULATED)
        self.assertEqual(metric.valid_sample_count, 2)
        self.assertEqual(
            metric.distribution.to_dict(),
            {"minimum": "10", "maximum": "20", "mean": "15", "median": "15"},
        )
        self.assertEqual(metric.unit.unit_code, "USD")
        self.assertEqual(
            metric.provenance.calculation_rule_id,
            "market_analysis.observed_product_price",
        )

    def test_rating_and_review_summaries_preserve_zero(self) -> None:
        rating = self.analysis.numeric_metric("market_analysis.product_rating")
        reviews = self.analysis.numeric_metric("market_analysis.product_review_count")
        self.assertEqual(rating.distribution.mean, Decimal("4.5"))
        self.assertEqual(rating.distribution.median, Decimal("4.5"))
        self.assertEqual(reviews.distribution.minimum, Decimal(0))
        self.assertEqual(reviews.distribution.maximum, Decimal(10))
        self.assertEqual(reviews.distribution.mean, Decimal(5))
        self.assertEqual(reviews.valid_sample_count, 2)

    def test_observed_product_count_reuses_calculation_engine(self) -> None:
        count = self.analysis.count_metric("workbook.market_overview.observed_product_count")
        self.assertEqual(count.status, CalculationStatus.CALCULATED)
        self.assertEqual(count.value, 2)
        self.assertEqual(
            count.calculation_rule_id,
            "calculation.observed_product_count",
        )
        self.assertEqual(self.analysis.scope.product_ids, ("product:US:B000000001", "product:US:B000000002"))

    def test_clean_result_carries_canonical_subject_identity(self) -> None:
        subjects = {field.subject.subject_id for field in self.clean.fields if field.subject}
        self.assertEqual(subjects, set(self.analysis.scope.product_ids))
        serialized = self.clean.to_dict()
        self.assertTrue(all("subject" in field for field in serialized["fields"]))

    def test_complete_two_product_input_has_complete_quality(self) -> None:
        self.assertEqual(self.analysis.status, MarketAnalysisStatus.COMPLETE)
        self.assertEqual(self.analysis.quality.product_subject_count, 2)
        self.assertEqual(self.analysis.quality.fields_invalid, 0)
        self.assertEqual(self.analysis.quality.quality_issue_count, 0)


class QualityGateTests(unittest.TestCase):
    def test_missing_and_invalid_values_are_excluded_not_zero_filled(self) -> None:
        clean = clean_products(
            product("B000000001", price="10"),
            product("B000000002", include_price=False),
            product("B000000003", price="free"),
        )
        metric = analyze(clean).numeric_metric("market_analysis.observed_product_price")
        self.assertEqual(metric.status, MarketMetricStatus.PARTIAL)
        self.assertEqual(metric.valid_sample_count, 1)
        self.assertEqual(metric.excluded_missing_count, 1)
        self.assertEqual(metric.excluded_invalid_count, 1)
        self.assertEqual(metric.distribution.minimum, Decimal(10))
        self.assertIn("INVALID_INPUTS_EXCLUDED", metric.limitations)
        self.assertIn("MISSING_INPUTS_EXCLUDED", metric.limitations)

    def test_unknown_is_not_zero_and_keeps_partial_status(self) -> None:
        clean = clean_products(
            product("B000000001", price="10"),
            product("B000000002", price="20"),
        )
        price_fields = [field for field in clean.fields if field.canonical_field == "metric.price"]
        unknown = replace(
            price_fields[1],
            raw_value=None,
            mapped_value=None,
            normalized_value=None,
            presence_status=PresenceStatus.UNKNOWN,
            normalization_status=NormalizationStatus.NOT_ATTEMPTED,
            semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
            application=None,
        )
        fields = tuple(unknown if field is price_fields[1] else field for field in clean.fields)
        metric = analyze(replace(clean, fields=fields)).numeric_metric(
            "market_analysis.observed_product_price"
        )
        self.assertEqual(metric.valid_sample_count, 1)
        self.assertEqual(metric.excluded_unknown_count, 1)
        self.assertEqual(metric.status, MarketMetricStatus.PARTIAL)

    def test_explicit_null_price_has_its_own_exclusion_category(self) -> None:
        clean = clean_products(
            product("B000000001", price="10"),
            product("B000000002", price=None),
        )
        metric = analyze(clean).numeric_metric("market_analysis.observed_product_price")
        self.assertEqual(metric.status, MarketMetricStatus.PARTIAL)
        self.assertEqual(metric.valid_sample_count, 1)
        self.assertEqual(metric.excluded_explicit_null_count, 1)
        self.assertEqual(metric.excluded_missing_count, 0)
        self.assertEqual(metric.distribution.minimum, Decimal(10))
        self.assertIn("EXPLICIT_NULL_INPUTS_EXCLUDED", metric.limitations)

    def test_multiple_candidates_for_one_subject_block_instead_of_average(self) -> None:
        clean = clean_products(product("B000000001", price="10"))
        duplicate_price = next(
            field for field in clean.fields if field.canonical_field == "metric.price"
        )
        duplicated = replace(clean, fields=(*clean.fields, duplicate_price))
        metric = analyze(duplicated).numeric_metric(
            "market_analysis.observed_product_price"
        )
        self.assertEqual(metric.status, MarketMetricStatus.BLOCKED)
        self.assertEqual(metric.valid_sample_count, 0)
        self.assertEqual(metric.excluded_conflict_count, 1)

    def test_currency_mismatch_blocks_observed_price_summary(self) -> None:
        clean = clean_products(
            product("B000000001", price="10", currency="USD"),
            product("B000000002", price="20", currency="EUR"),
        )
        metric = analyze(clean).numeric_metric("market_analysis.observed_product_price")
        self.assertEqual(metric.status, MarketMetricStatus.BLOCKED)
        self.assertEqual(metric.excluded_unit_mismatch_count, 2)
        self.assertIn("UNIT_OR_CURRENCY_MISMATCH", metric.limitations)

    def test_empty_input_is_empty_and_metrics_are_missing(self) -> None:
        result = MarketAnalysisBuilderV0_1().build(
            MarketAnalysisRequest(marketplace="US", clean_results=())
        )
        self.assertEqual(result.status, MarketAnalysisStatus.EMPTY)
        self.assertEqual(
            result.count_metric("workbook.market_overview.observed_product_count").status,
            CalculationStatus.MISSING_INPUT,
        )
        self.assertEqual(
            result.numeric_metric("market_analysis.observed_product_price").status,
            MarketMetricStatus.MISSING,
        )
        self.assertIn("NO_CLEAN_RESULTS", result.quality.limitations)


class DemandStructureAndBoundaryTests(unittest.TestCase):
    def test_available_keyword_metrics_are_aggregated_but_difficulty_stays_blocked(self) -> None:
        body = json.loads(
            (PROVIDER_FIXTURES / "xiyou_keyword_info.json").read_text(encoding="utf-8")
        )
        clean = service_for("xiyou", "keyword_info", body).clean(
            cleaning_request("xiyou", "keyword_info", {})
        )
        result = analyze(clean)
        for metric_id in (
            "market_analysis.keyword_cpc",
            "market_analysis.keyword_aba_rank",
        ):
            metric = result.numeric_metric(metric_id)
            self.assertGreater(metric.valid_sample_count, 0)
            self.assertIn(metric.status, {MarketMetricStatus.CALCULATED, MarketMetricStatus.PARTIAL})
        search_volume = result.numeric_metric("market_analysis.keyword_search_volume")
        self.assertEqual(search_volume.status, MarketMetricStatus.BLOCKED)
        self.assertGreater(search_volume.excluded_invalid_count, 0)
        blocked = {item.metric_id: item.reason_code for item in result.blocked_metrics}
        self.assertEqual(
            blocked["market_analysis.keyword_difficulty_summary"],
            "PROVIDER_SCALE_UNCONFIRMED",
        )

    def test_comparable_group_trend_and_variation_metrics_remain_blocked(self) -> None:
        result = analyze(clean_products(product("B000000001")))
        blocked = {item.metric_id: item.reason_code for item in result.blocked_metrics}
        self.assertEqual(
            blocked["workbook.product_structure.minimum_comparable_price"],
            "BLOCKED_BY_MEMBERSHIP_SOURCE",
        )
        self.assertEqual(
            blocked["workbook.product_structure.maximum_comparable_price"],
            "BLOCKED_BY_MEMBERSHIP_SOURCE",
        )
        self.assertEqual(
            blocked["workbook.competition_evidence.variation_evidence_count"],
            "SEMANTIC_AMBIGUITY",
        )
        self.assertEqual(
            blocked["workbook.market_overview.evidence_backed_trend"],
            "FORMULA_UNSPECIFIED",
        )

    def test_provider_neutrality_accepts_sorftime_clean_result(self) -> None:
        body = payload("sorftime_product_detail.json")
        clean = service_for("sorftime", "product_detail", body).clean(
            cleaning_request("sorftime", "product_detail", {})
        )
        result = analyze(clean)
        metric = result.numeric_metric("market_analysis.observed_product_price")
        self.assertGreater(metric.valid_sample_count, 0)
        providers = {
            provenance.provider
            for lineage in metric.provenance.input_lineage
            for provenance in lineage.provenances
        }
        self.assertEqual(providers, {"sorftime"})

    def test_provenance_reaches_normalized_input_raw_reference_and_provider(self) -> None:
        result = analyze(clean_products(product("B000000001", price="12.50")))
        metric = result.numeric_metric("market_analysis.observed_product_price")
        lineage = metric.provenance.input_lineage[0]
        self.assertEqual(lineage.field_id, "metric.price")
        self.assertEqual(lineage.normalization_status, NormalizationStatus.NORMALIZED)
        self.assertTrue(any(item.startswith("raw:") for item in lineage.evidence_references))
        self.assertEqual(lineage.provenances[0].provider, "xiyou")
        self.assertTrue(
            lineage.provenances[0].transformation.raw_evidence_reference.startswith("raw:")
        )

    def test_xiyou_http_v2_fixture_covers_small_live_data_boundary_offline(self) -> None:
        clean = service_for("xiyou", "asin_info", payload("xiyou_asin_info_http_v2.json")).clean(
            cleaning_request("xiyou", "asin_info", {"entities": []})
        )
        result = analyze(clean)
        self.assertEqual(result.scope.providers, ("xiyou",))
        self.assertEqual(result.quality.product_subject_count, 1)
        self.assertEqual(
            result.numeric_metric("market_analysis.observed_product_price").valid_sample_count,
            1,
        )
        self.assertIn("SMALL_OBSERVED_PRODUCT_SAMPLE", result.quality.limitations)
        self.assertEqual(result.status, MarketAnalysisStatus.PARTIAL)


class DeterminismTests(unittest.TestCase):
    def test_output_is_deterministic_under_clean_field_reordering(self) -> None:
        clean = clean_products(
            product("B000000001", price="10"),
            product("B000000002", price="20"),
        )
        first = analyze(clean).to_json(indent=None)
        second = analyze(replace(clean, fields=tuple(reversed(clean.fields)))).to_json(indent=None)
        self.assertEqual(first, second)

    def test_output_contains_no_full_provider_payload(self) -> None:
        result = analyze(clean_products(product("B000000001")))
        serialized = result.to_json(indent=None)
        self.assertNotIn("raw_snapshot", serialized)
        self.assertNotIn("authorization", serialized.casefold())


if __name__ == "__main__":
    unittest.main()
