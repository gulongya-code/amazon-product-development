from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.adapters as adapters
from amazon_product_intelligence.adapters import (
    AdaptationContext,
    AdapterContextError,
    ProviderAdapter,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    Channel,
    EvidenceType,
    NormalizationStatus,
    ObservedAtStatus,
    PeriodType,
    PresenceStatus,
    QueryExecutionOutcome,
    RelationshipDirection,
    ScopeType,
    ScopeStatus,
    SemanticStatus,
    TransformationStatus,
    canonical_json,
)


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"

SOURCE_TOOLS = {
    ("xiyou", "asin_info"): "get_asin_info",
    ("xiyou", "asin_variations"): "get_asin_variations",
    ("xiyou", "asin_orders_last_30_days"): "get_asin_orders_last_30_days",
    ("xiyou", "asin_bsr_trends"): "get_asin_bsr_trends",
    ("xiyou", "keyword_info"): "get_keyword_info",
    ("xiyou", "keyword_asin_analysis"): "get_keyword_asin_analysis",
    ("xiyou", "asin_keywords"): "get_asin_keywords",
    ("sorftime", "product_detail"): "product_detail",
    ("sorftime", "product_variations"): "product_variations",
    ("sorftime", "product_reviews"): "product_reviews",
}

FIXTURE_BY_KIND = {
    ("xiyou", "asin_info"): "xiyou_asin_info.json",
    ("xiyou", "asin_variations"): "xiyou_asin_variations.json",
    ("xiyou", "asin_orders_last_30_days"): "xiyou_asin_orders.json",
    ("xiyou", "asin_bsr_trends"): "xiyou_asin_bsr.json",
    ("xiyou", "keyword_info"): "xiyou_keyword_info.json",
    ("xiyou", "keyword_asin_analysis"): "xiyou_keyword_forward_populated.json",
    ("xiyou", "asin_keywords"): "xiyou_asin_keywords_reverse.json",
    ("sorftime", "product_detail"): "sorftime_product_detail.json",
    ("sorftime", "product_variations"): "sorftime_product_variations.json",
    ("sorftime", "product_reviews"): "sorftime_product_reviews.json",
}


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def context(
    provider: str,
    payload_kind: str,
    *,
    source_tool: str | None = None,
    request: dict[str, object] | None = None,
    currency: str | None = "USD",
) -> AdaptationContext:
    if request is None:
        request = {}
        if payload_kind in {"product_detail", "product_variations", "product_reviews", "asin_keywords"}:
            request["asin"] = "B0G2VV4RBW"
        if payload_kind == "keyword_asin_analysis":
            request["keyword"] = "plastic spoons"
    return AdaptationContext(
        provider=provider,
        payload_kind=payload_kind,
        source_tool=source_tool or SOURCE_TOOLS.get((provider, payload_kind), "unsupported_tool"),
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:{provider}:{payload_kind}:fixture",
        sanitized_request=request,
        currency=currency,
    )


def adapter_for(provider: str) -> ProviderAdapter:
    return XiYouAdapterV0_1() if provider == "xiyou" else SorftimeAdapterV0_1()


def adapt_fixture(provider: str, payload_kind: str, **kwargs: object):
    payload = load_fixture(FIXTURE_BY_KIND[(provider, payload_kind)])
    return adapter_for(provider).adapt(payload, context(provider, payload_kind, **kwargs))


def metric_observations(result, metric: str):
    return [item for item in result.bundle.observations if getattr(item, "metric", None) == metric]


def fact_observations(result, dimension: str):
    return [item for item in result.bundle.observations if getattr(item, "dimension", None) == dimension]


def relationship_observations(result, relationship_type=None):
    rows = [item for item in result.bundle.observations if hasattr(item, "direction")]
    if relationship_type is not None:
        rows = [item for item in rows if item.relationship_type is relationship_type]
    return rows


def reverse_mapping_order(value):
    if isinstance(value, dict):
        return {key: reverse_mapping_order(value[key]) for key in reversed(list(value))}
    if isinstance(value, list):
        return [reverse_mapping_order(item) for item in value]
    return value


def fresh_process_serialization(
    provider: str,
    payload_kind: str,
    fixture_name: str | None = None,
) -> str:
    fixture = FIXTURES / (fixture_name or FIXTURE_BY_KIND[(provider, payload_kind)])
    source_tool = SOURCE_TOOLS[(provider, payload_kind)]
    script = """
import json
from pathlib import Path
import sys

sys.path.insert(0, "src")

from amazon_product_intelligence.adapters import (
    AdaptationContext,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.contracts import canonical_json

provider, payload_kind, source_tool, fixture = sys.argv[1:5]
payload = json.loads(Path(fixture).read_text(encoding="utf-8"))
context = AdaptationContext(
    provider=provider,
    payload_kind=payload_kind,
    source_tool=source_tool,
    marketplace="US",
    locale="en-us",
    retrieved_at="2026-08-14T09:00:00Z",
    transformed_at="2026-08-14T09:01:00Z",
    collection_run_id=f"collection:{provider}:{payload_kind}:fixture",
    sanitized_request=(
        {"asin": "B0G2VV4RBW"}
        if payload_kind in {"product_detail", "product_variations", "product_reviews", "asin_keywords"}
        else (
            {
                "keyword": (
                    "1/2 ball valve"
                    if Path(fixture).name == "xiyou_keyword_forward_empty.json"
                    else "plastic spoons"
                )
            }
            if payload_kind == "keyword_asin_analysis"
            else {}
        )
    ),
    currency="USD",
)
adapter = XiYouAdapterV0_1() if provider == "xiyou" else SorftimeAdapterV0_1()
print(canonical_json(adapter.adapt(payload, context).to_dict()))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, provider, payload_kind, source_tool, str(fixture)],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


class PublicApiAndBoundaryTests(unittest.TestCase):
    def test_public_api_is_explicit_and_has_no_internal_leaks(self) -> None:
        expected = {
            "ADAPTER_RULESET_VERSION",
            "AdapterError",
            "AdapterContextError",
            "MappingDisposition",
            "AdapterFailureLevel",
            "MappingSpecification",
            "AdaptationContext",
            "AdapterDiagnostic",
            "AdapterFailure",
            "AdaptationStatistics",
            "AdaptationResult",
            "ProviderAdapter",
            "XiYouAdapterV0_1",
            "SorftimeAdapterV0_1",
        }
        self.assertEqual(set(adapters.__all__), expected)
        self.assertFalse(any(name.startswith("_") for name in adapters.__all__))
        self.assertTrue(isinstance(XiYouAdapterV0_1(), ProviderAdapter))
        self.assertTrue(isinstance(SorftimeAdapterV0_1(), ProviderAdapter))

    def test_v0_1_5_ruleset_and_affected_mapping_versions_are_explicit(self) -> None:
        self.assertEqual(len(adapters.__all__), 14)
        self.assertEqual(adapters.ADAPTER_RULESET_VERSION, "provider-adapters-v0.1.5")
        self.assertEqual(XiYouAdapterV0_1.adapter_version, "0.1.5")
        self.assertEqual(SorftimeAdapterV0_1.adapter_version, "0.1.1")

        xiyou_specs = XiYouAdapterV0_1.mapping_specifications
        self.assertEqual(xiyou_specs["asin_info_http_v2"].version, "0.1.1")
        self.assertEqual(
            xiyou_specs["asin_info_http_v2"].mapping_version,
            "xiyou_product_info_http_v2_mapping_v2",
        )
        self.assertEqual(xiyou_specs["asin_variations"].version, "0.1.1")
        self.assertEqual(
            xiyou_specs["asin_variations"].mapping_version,
            "xiyou_variations_mapping_v1_1",
        )
        self.assertEqual(
            xiyou_specs["asin_variations_http_v2"].mapping_version,
            "xiyou_variations_http_v2_mapping_v1",
        )
        self.assertEqual(
            xiyou_specs["asin_bsr_trends_http_v2"].mapping_version,
            "xiyou_bsr_http_v2_mapping_v1",
        )
        self.assertEqual(xiyou_specs["asin_info"].version, "0.1")
        self.assertEqual(
            xiyou_specs["keyword_info_http_v2"].mapping_version,
            "xiyou_keyword_info_http_v2_mapping_v1",
        )
        self.assertEqual(
            xiyou_specs["keyword_asin_analysis_http_v2"].mapping_version,
            "xiyou_keyword_to_asin_http_v2_mapping_v1",
        )
        self.assertEqual(
            xiyou_specs["asin_keywords_http_v2"].mapping_version,
            "xiyou_asin_to_keyword_http_v2_mapping_v1",
        )
        self.assertEqual(xiyou_specs["keyword_asin_analysis"].version, "0.1.1")
        self.assertEqual(
            xiyou_specs["keyword_asin_analysis"].mapping_version,
            "xiyou_keyword_to_asin_mapping_v1_1",
        )
        self.assertEqual(xiyou_specs["asin_keywords"].version, "0.1.1")
        self.assertEqual(
            xiyou_specs["asin_keywords"].mapping_version,
            "xiyou_asin_to_keyword_mapping_v1_1",
        )

        sorftime_specs = SorftimeAdapterV0_1.mapping_specifications
        self.assertEqual(sorftime_specs["product_variations"].version, "0.1.1")
        self.assertEqual(
            sorftime_specs["product_variations"].mapping_version,
            "sorftime_variations_mapping_v1_1",
        )
        self.assertEqual(sorftime_specs["product_detail"].version, "0.1")

    def test_invalid_required_context_is_rejected(self) -> None:
        with self.assertRaises(AdapterContextError):
            AdaptationContext(
                provider="",
                payload_kind="asin_info",
                source_tool="get_asin_info",
                marketplace="US",
                locale="en-us",
                retrieved_at=RETRIEVED_AT,
                transformed_at=TRANSFORMED_AT,
                collection_run_id="collection:test",
            )

    def test_unsupported_provider_fails_without_transformation_or_observation(self) -> None:
        payload = load_fixture("xiyou_asin_info.json")
        result = XiYouAdapterV0_1().adapt(payload, context("sorftime", "asin_info"))
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].code, "UNSUPPORTED_PROVIDER")
        self.assertEqual(result.bundle.observations, ())
        self.assertEqual(result.bundle.transformation_runs, ())

    def test_unsupported_payload_kind_fails_closed(self) -> None:
        payload = load_fixture("xiyou_asin_info.json")
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "not_supported"))
        self.assertFalse(result.succeeded)
        self.assertEqual(result.errors[0].code, "UNSUPPORTED_PAYLOAD_KIND")
        self.assertFalse(result.bundle.observations)

    def test_source_tool_mismatch_fails_closed(self) -> None:
        payload = load_fixture("xiyou_asin_info.json")
        result = XiYouAdapterV0_1().adapt(
            payload,
            context("xiyou", "asin_info", source_tool="get_keyword_info"),
        )
        self.assertEqual(result.errors[0].code, "SOURCE_TOOL_MISMATCH")
        self.assertFalse(result.bundle.transformation_runs)

    def test_malformed_top_level_and_non_string_keys_are_rejected(self) -> None:
        malformed = XiYouAdapterV0_1().adapt([], context("xiyou", "asin_info"))
        self.assertEqual(malformed.errors[0].code, "MALFORMED_TOP_LEVEL_PAYLOAD")
        self.assertFalse(malformed.bundle.observations)
        invalid_key = XiYouAdapterV0_1().adapt(
            {"status": 200, "data": {1: "bad"}},
            context("xiyou", "asin_info"),
        )
        self.assertEqual(invalid_key.errors[0].code, "INVALID_JSON_PAYLOAD")
        self.assertIsNone(invalid_key.raw_evidence)

    def test_collection_envelope_failure_has_no_fake_success_run(self) -> None:
        result = XiYouAdapterV0_1().adapt(
            {"status": True, "data": {"entities": []}},
            context("xiyou", "asin_info"),
        )
        self.assertEqual(result.errors[0].code, "UNSUPPORTED_PROVIDER_STATUS")
        self.assertFalse(result.bundle.transformation_runs)
        self.assertFalse(result.bundle.observations)

    def test_nan_is_rejected_before_raw_identity_is_claimed(self) -> None:
        result = XiYouAdapterV0_1().adapt(
            {"status": 200, "data": {"entities": [{"ratings": math.nan}]}},
            context("xiyou", "asin_info"),
        )
        self.assertEqual(result.errors[0].code, "INVALID_JSON_PAYLOAD")
        self.assertIsNone(result.raw_evidence)


class ImmutabilityDeterminismAndLineageTests(unittest.TestCase):
    def test_nested_input_is_not_modified_and_snapshot_is_immutable(self) -> None:
        payload = load_fixture("xiyou_asin_info.json")
        original = deepcopy(payload)
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_info"))
        self.assertEqual(payload, original)
        with self.assertRaises(TypeError):
            result.raw_snapshot["data"] = {}  # type: ignore[index]
        with self.assertRaises(TypeError):
            result.raw_snapshot["data"]["entities"][0]["title"] = "changed"  # type: ignore[index]
        payload["data"]["entities"][0]["title"] = "changed after adaptation"  # type: ignore[index]
        self.assertEqual(
            result.raw_snapshot["data"]["entities"][0]["title"],
            original["data"]["entities"][0]["title"],  # type: ignore[index]
        )

    def test_context_metadata_is_detached_and_recursively_immutable(self) -> None:
        request = {"filters": {"channels": ["organic", "sponsored"]}}
        adaptation_context = context("xiyou", "asin_info", request=request)
        request["filters"]["channels"].append("changed")  # type: ignore[index, union-attr]
        self.assertEqual(
            adaptation_context.sanitized_request["filters"]["channels"],
            ("organic", "sponsored"),
        )
        with self.assertRaises(TypeError):
            adaptation_context.sanitized_request["filters"]["channels"][0] = "changed"  # type: ignore[index]

    def test_mapping_order_does_not_change_raw_or_result_identity(self) -> None:
        cases = (
            ("sorftime", "product_detail"),
            ("sorftime", "product_variations"),
            ("xiyou", "asin_variations"),
        )
        for provider, kind in cases:
            with self.subTest(provider=provider, kind=kind):
                payload = load_fixture(FIXTURE_BY_KIND[(provider, kind)])
                reordered = reverse_mapping_order(payload)
                first = adapter_for(provider).adapt(payload, context(provider, kind))
                second = adapter_for(provider).adapt(reordered, context(provider, kind))
                self.assertEqual(first.raw_evidence.raw_evidence_id, second.raw_evidence.raw_evidence_id)
                self.assertEqual(canonical_json(first.to_dict()), canonical_json(second.to_dict()))

    def test_repeated_replay_is_identical(self) -> None:
        for provider, kind in (("xiyou", "asin_info"), ("sorftime", "product_detail")):
            with self.subTest(provider=provider):
                first = adapt_fixture(provider, kind)
                second = adapt_fixture(provider, kind)
                self.assertEqual(canonical_json(first.to_dict()), canonical_json(second.to_dict()))
                self.assertIs(first.bundle.validate(), first.bundle)
                restored = CanonicalEvidenceBundle.from_dict(first.bundle.to_dict())
                self.assertIs(restored.validate(), restored)
                self.assertEqual(canonical_json(restored), canonical_json(first.bundle))

    def test_fresh_process_replay_is_identical(self) -> None:
        for provider, kind in (
            ("xiyou", "asin_info"),
            ("sorftime", "product_detail"),
            ("xiyou", "asin_variations"),
            ("sorftime", "product_variations"),
        ):
            with self.subTest(provider=provider):
                first = fresh_process_serialization(provider, kind)
                second = fresh_process_serialization(provider, kind)
                self.assertEqual(first, second)

    def test_directional_query_fixtures_are_deterministic_and_immutable(self) -> None:
        cases = (
            ("keyword_asin_analysis", "xiyou_keyword_forward_populated.json"),
            ("keyword_asin_analysis", "xiyou_keyword_forward_empty.json"),
            ("asin_keywords", "xiyou_asin_keywords_reverse.json"),
        )
        for kind, fixture_name in cases:
            with self.subTest(kind=kind, fixture=fixture_name):
                payload = load_fixture(fixture_name)
                original = deepcopy(payload)
                adapter = XiYouAdapterV0_1()
                request = (
                    {"keyword": "1/2 ball valve"}
                    if fixture_name == "xiyou_keyword_forward_empty.json"
                    else None
                )
                first = adapter.adapt(payload, context("xiyou", kind, request=request))
                same_process = adapter.adapt(
                    deepcopy(payload),
                    context("xiyou", kind, request=request),
                )
                reordered = adapter.adapt(
                    reverse_mapping_order(payload),
                    context("xiyou", kind, request=request),
                )
                first_json = canonical_json(first.to_dict())
                self.assertEqual(first_json, canonical_json(same_process.to_dict()))
                self.assertEqual(first_json, canonical_json(reordered.to_dict()))
                self.assertEqual(payload, original)
                self.assertEqual(
                    CanonicalEvidenceBundle.from_dict(first.bundle.to_dict()),
                    first.bundle,
                )
                self.assertEqual(
                    fresh_process_serialization("xiyou", kind, fixture_name),
                    fresh_process_serialization("xiyou", kind, fixture_name),
                )

    def test_variation_adaptation_does_not_mutate_inputs(self) -> None:
        for provider, kind in (
            ("xiyou", "asin_variations"),
            ("sorftime", "product_variations"),
        ):
            with self.subTest(provider=provider):
                payload = load_fixture(FIXTURE_BY_KIND[(provider, kind)])
                original = deepcopy(payload)
                adapter_for(provider).adapt(payload, context(provider, kind))
                self.assertEqual(payload, original)

    def test_unknown_raw_field_is_retained_but_not_mapped(self) -> None:
        payload = load_fixture("xiyou_asin_info.json")
        baseline = XiYouAdapterV0_1().adapt(deepcopy(payload), context("xiyou", "asin_info"))
        payload["data"]["entities"][0]["future_field"] = {"nested": [1, 2]}  # type: ignore[index]
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_info"))
        self.assertEqual(
            result.raw_snapshot["data"]["entities"][0]["future_field"]["nested"],
            (1, 2),
        )
        self.assertEqual(
            result.statistics.mapped_observation_count,
            baseline.statistics.mapped_observation_count,
        )
        self.assertIn("UNMAPPED_SOURCE_FIELD", {item.code for item in result.diagnostics})

    def test_bool_numeric_field_is_rejected_without_blocking_safe_title(self) -> None:
        payload = load_fixture("xiyou_asin_info.json")
        payload["data"]["entities"][0]["ratings"] = True  # type: ignore[index]
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_info"))
        self.assertTrue(fact_observations(result, "title"))
        self.assertFalse(metric_observations(result, "review_count"))
        self.assertIn("INVALID_REVIEW_COUNT_PRIMITIVE", {item.issue_code for item in result.bundle.quality_issues})
        self.assertEqual(result.bundle.transformation_runs[0].status, TransformationStatus.PARTIAL)

    def test_observation_time_never_uses_retrieval_time(self) -> None:
        result = adapt_fixture("xiyou", "asin_info")
        for observation in result.bundle.observations:
            self.assertIsNone(observation.time.observed_at)
            self.assertEqual(observation.time.observed_at_status, ObservedAtStatus.UNKNOWN)
            self.assertEqual(observation.time.retrieved_at, RETRIEVED_AT)

    def test_bundle_round_trip_and_cross_reference_validation(self) -> None:
        cases = (
            ("xiyou", "asin_info"),
            ("xiyou", "asin_variations"),
            ("xiyou", "asin_keywords"),
            ("sorftime", "product_detail"),
            ("sorftime", "product_variations"),
            ("sorftime", "product_reviews"),
        )
        for provider, kind in cases:
            with self.subTest(provider=provider, kind=kind):
                result = adapt_fixture(provider, kind)
                restored = CanonicalEvidenceBundle.from_dict(
                    json.loads(json.dumps(result.bundle.to_dict(), ensure_ascii=False))
                )
                self.assertEqual(restored.to_dict(), result.bundle.to_dict())
                self.assertIs(restored.validate(), restored)

    def test_every_observation_traces_run_mapping_raw_and_collection(self) -> None:
        result = adapt_fixture("sorftime", "product_detail")
        run_by_id = {item.transformation_run_id: item for item in result.bundle.transformation_runs}
        for observation in result.bundle.observations:
            transform = observation.provenance.transformation
            run = run_by_id[transform.transformation_run_id]
            self.assertEqual(transform.mapping_version, result.mapping_specification.mapping_version)
            self.assertEqual(transform.raw_evidence_reference, result.raw_evidence.raw_evidence_id)
            self.assertEqual(run.collection_run_id, result.raw_evidence.collection_run_id)
            self.assertIn(observation.observation_id, run.output_observation_ids)

    def test_each_provider_operates_independently(self) -> None:
        xiyou = adapt_fixture("xiyou", "asin_info")
        sorftime = adapt_fixture("sorftime", "product_detail")
        self.assertTrue(xiyou.succeeded)
        self.assertTrue(sorftime.succeeded)
        self.assertTrue(xiyou.bundle.observations)
        self.assertTrue(sorftime.bundle.observations)


class PresenceAndPrimitiveTests(unittest.TestCase):
    def test_missing_explicit_null_unknown_and_zero_remain_distinct(self) -> None:
        source = load_fixture("xiyou_keyword_info.json")
        null_payload = {"status": 200, "data": {"list": [deepcopy(source["data"]["list"][1])], "total": 1}}
        null_result = XiYouAdapterV0_1().adapt(null_payload, context("xiyou", "keyword_info"))
        null_volume = metric_observations(null_result, "search_volume")[0]
        self.assertEqual(null_volume.value.presence_status, PresenceStatus.EXPLICIT_NULL)

        missing_payload = deepcopy(null_payload)
        del missing_payload["data"]["list"][0]["abaReport"]
        missing_result = XiYouAdapterV0_1().adapt(missing_payload, context("xiyou", "keyword_info"))
        self.assertFalse(metric_observations(missing_result, "search_volume"))
        self.assertIn("SOURCE_FIELD_MISSING", {item.code for item in missing_result.diagnostics})

        zero_payload = deepcopy(source)
        row = zero_payload["data"]["list"][0]
        row["abaReport"]["weeklySearchVolume"] = 0
        row["abaReport"]["searchFrequencyRank"] = 0
        row["competitiveDifficulty"] = 0
        row["costPerClick"] = {"minSuggestedBid": "0", "maxSuggestedBid": "0", "value": "0"}
        zero_payload["data"]["list"] = [row]
        zero_payload["data"]["total"] = 1
        zero_result = XiYouAdapterV0_1().adapt(zero_payload, context("xiyou", "keyword_info"))
        for metric in ("search_volume", "aba_search_frequency_rank", "competition_difficulty", "cpc"):
            self.assertEqual(metric_observations(zero_result, metric)[0].value.normalized_value, 0)
            self.assertEqual(
                metric_observations(zero_result, metric)[0].value.presence_status,
                PresenceStatus.PRESENT,
            )

        variation = adapt_fixture("sorftime", "product_variations")
        unknown = [
            item
            for item in metric_observations(variation, "estimated_sales_volume")
            if item.value.presence_status is PresenceStatus.UNKNOWN
        ]
        self.assertEqual(len(unknown), 1)
        self.assertIsNone(unknown[0].value.normalized_value)

    def test_generic_numeric_string_is_not_accepted_for_sorftime_number(self) -> None:
        payload = load_fixture("sorftime_product_detail.json")
        payload["data"]["price"] = "18.99"
        result = SorftimeAdapterV0_1().adapt(payload, context("sorftime", "product_detail"))
        self.assertFalse(metric_observations(result, "price"))
        self.assertIn("INVALID_METRIC_PRIMITIVE", {item.issue_code for item in result.bundle.quality_issues})

    def test_http_v2_explicit_null_price_is_preserved_with_subject_and_currency(self) -> None:
        payload = {
            "entities": [
                {
                    "asin": "B000000001",
                    "country": "US",
                    "currency": "USD",
                    "price": None,
                    "ratings": 10,
                    "stars": "4.5",
                    "title": "Schema-focused product",
                }
            ]
        }
        result = XiYouAdapterV0_1().adapt(
            payload,
            context(
                "xiyou",
                "asin_info_http_v2",
                source_tool="get_asin_info",
            ),
        )
        price = metric_observations(result, "price")[0]
        self.assertEqual(price.subject.subject_id, "product:US:B000000001")
        self.assertEqual(price.value.presence_status, PresenceStatus.EXPLICIT_NULL)
        self.assertIsNone(price.value.normalized_value)
        self.assertEqual(price.value.unit.unit_code, "USD")
        self.assertEqual(price.provenance.source_field, "entities[0].price")
        self.assertEqual(
            price.provenance.transformation.mapping_version,
            "xiyou_product_info_http_v2_mapping_v2",
        )


class XiYouMappingTests(unittest.TestCase):
    def test_http_v2_keyword_metrics_use_root_list_with_truthful_source_fields(self) -> None:
        legacy = load_fixture("xiyou_keyword_info.json")
        result = XiYouAdapterV0_1().adapt(
            legacy["data"],
            context(
                "xiyou",
                "keyword_info_http_v2",
                source_tool="get_keyword_info",
            ),
        )
        self.assertTrue(result.succeeded)
        volume = metric_observations(result, "search_volume")[0]
        self.assertEqual(
            volume.provenance.source_field,
            "list[0].abaReport.weeklySearchVolume",
        )
        self.assertEqual(
            volume.provenance.transformation.mapping_version,
            "xiyou_keyword_info_http_v2_mapping_v1",
        )
        self.assertEqual(set(result.raw_snapshot), {"list", "total"})

    def test_http_v2_directional_relationships_use_root_list(self) -> None:
        forward_fixture = load_fixture("xiyou_keyword_forward_populated.json")
        forward = XiYouAdapterV0_1().adapt(
            forward_fixture["data"],
            context(
                "xiyou",
                "keyword_asin_analysis_http_v2",
                source_tool="get_keyword_asin_analysis",
                request={"keyword": "plastic spoons", "page": 1, "pageSize": 20},
            ),
        )
        reverse_fixture = load_fixture("xiyou_asin_keywords_reverse.json")
        reverse = XiYouAdapterV0_1().adapt(
            reverse_fixture["data"],
            context(
                "xiyou",
                "asin_keywords_http_v2",
                source_tool="get_asin_keywords",
                request={"asin": "B0G2VV4RBW"},
            ),
        )
        self.assertTrue(forward.succeeded)
        self.assertTrue(reverse.succeeded)
        self.assertEqual(
            forward.bundle.query_execution_records[0].provenance.source_field,
            "list",
        )
        self.assertEqual(
            reverse.bundle.query_execution_records[0].provenance.source_field,
            "list",
        )
        self.assertEqual(
            forward.mapping_specification.mapping_version,
            "xiyou_keyword_to_asin_http_v2_mapping_v1",
        )
        self.assertEqual(
            reverse.mapping_specification.mapping_version,
            "xiyou_asin_to_keyword_http_v2_mapping_v1",
        )
        self.assertEqual(forward.raw_evidence.response_status, "PARTIAL")
        self.assertEqual(
            forward.raw_evidence.pagination,
            {
                "request_page": 1,
                "request_page_size": 20,
                "returned_count": 1,
                "provider_total": 647,
                "collection_status": "PARTIAL_PAGE",
            },
        )

    def test_product_info_maps_only_audited_observed_evidence(self) -> None:
        result = adapt_fixture("xiyou", "asin_info")
        self.assertEqual(len(fact_observations(result, "title")), 1)
        self.assertEqual(metric_observations(result, "price")[0].evidence_type, EvidenceType.OBSERVED)
        self.assertEqual(metric_observations(result, "rating")[0].value.normalized_value, 4.8)
        self.assertEqual(metric_observations(result, "review_count")[0].value.normalized_value, 20)
        self.assertFalse(fact_observations(result, "brand"))
        self.assertFalse(fact_observations(result, "structured_attributes"))
        self.assertFalse(fact_observations(result, "bullet_points"))

    def test_orders_are_estimate_with_unconfirmed_scope_and_preserve_zero(self) -> None:
        payload = load_fixture("xiyou_asin_orders.json")
        payload["data"]["entities"][0]["orders"] = 0
        result = XiYouAdapterV0_1().adapt(
            payload,
            context("xiyou", "asin_orders_last_30_days"),
        )
        observation = metric_observations(result, "orders")[0]
        self.assertEqual(observation.evidence_type, EvidenceType.PROVIDER_ESTIMATE)
        self.assertEqual(observation.value.normalized_value, 0)
        self.assertEqual(observation.value.semantic_status, SemanticStatus.SEMANTICS_UNCONFIRMED)
        self.assertEqual(observation.scope.scope_status, ScopeStatus.SCOPE_UNCONFIRMED)
        self.assertEqual(observation.time.period_type, PeriodType.ROLLING_30_DAYS)

    def test_keyword_metrics_keep_estimate_observed_period_range_and_null(self) -> None:
        result = adapt_fixture("xiyou", "keyword_info")
        volume = [item for item in metric_observations(result, "search_volume") if item.value.presence_status is PresenceStatus.PRESENT][0]
        aba = [item for item in metric_observations(result, "aba_search_frequency_rank") if item.value.presence_status is PresenceStatus.PRESENT][0]
        cpc = [item for item in metric_observations(result, "cpc") if item.value.presence_status is PresenceStatus.PRESENT][0]
        self.assertEqual(volume.evidence_type, EvidenceType.PROVIDER_ESTIMATE)
        self.assertEqual(volume.time.period_type, PeriodType.CALENDAR_WEEK)
        self.assertEqual(aba.evidence_type, EvidenceType.OBSERVED)
        self.assertEqual(cpc.range, {"minimum": 1.98, "maximum": 3.36, "currency": "USD"})
        self.assertTrue(
            any(item.value.presence_status is PresenceStatus.EXPLICIT_NULL for item in metric_observations(result, "cpc"))
        )

    def test_forward_and_reverse_directions_have_distinct_identities(self) -> None:
        reverse_payload = load_fixture("xiyou_asin_keywords_reverse.json")
        reverse = XiYouAdapterV0_1().adapt(
            reverse_payload,
            context("xiyou", "asin_keywords", request={"asin": "B0G2VV4RBW"}),
        )
        forward_row = deepcopy(reverse_payload["data"]["list"][0])
        forward_row["asin"] = "B0G2VV4RBW"
        forward_payload = {"status": 200, "data": {"list": [forward_row], "total": 1}}
        forward = XiYouAdapterV0_1().adapt(
            forward_payload,
            context(
                "xiyou",
                "keyword_asin_analysis",
                request={"keyword": "1/2 ball valve"},
            ),
        )
        reverse_membership = [item for item in relationship_observations(reverse) if item.relationship_type.value == "CANDIDATE_MEMBERSHIP"][0]
        forward_membership = [item for item in relationship_observations(forward) if item.relationship_type.value == "CANDIDATE_MEMBERSHIP"][0]
        self.assertEqual(reverse_membership.direction, RelationshipDirection.PRODUCT_TO_KEYWORD)
        self.assertEqual(forward_membership.direction, RelationshipDirection.KEYWORD_TO_PRODUCT)
        self.assertNotEqual(reverse_membership.semantic_observation_id, forward_membership.semantic_observation_id)
        self.assertNotEqual(reverse_membership.relationship_id, forward_membership.relationship_id)

    def test_organic_and_sponsored_are_separate_and_zero_is_present(self) -> None:
        result = adapt_fixture("xiyou", "asin_keywords")
        relationships = relationship_observations(result)
        channels = {item.channel for item in relationships}
        self.assertIn(Channel.ORGANIC, channels)
        self.assertIn(Channel.SPONSORED, channels)
        sponsored_zero = [
            item
            for item in relationships
            if item.relationship_type.value == "TRAFFIC"
            and item.channel is Channel.SPONSORED
            and item.value.normalized_value == 0
        ]
        self.assertEqual(len(sponsored_zero), 1)
        self.assertEqual(sponsored_zero[0].value.presence_status, PresenceStatus.PRESENT)

    def test_forward_empty_does_not_create_zero_market_metric_or_delete_reverse(self) -> None:
        empty = XiYouAdapterV0_1().adapt(
            load_fixture("xiyou_keyword_forward_empty.json"),
            context(
                "xiyou",
                "keyword_asin_analysis",
                request={"keyword": "1/2 ball valve"},
            ),
        )
        reverse = adapt_fixture("xiyou", "asin_keywords")
        self.assertTrue(empty.succeeded)
        self.assertFalse(empty.bundle.observations)
        self.assertEqual(empty.raw_evidence.response_status, "EMPTY")
        self.assertIn("QUERY_RETURNED_EMPTY", {item.code for item in empty.diagnostics})
        forbidden = {"market_size", "competitor_count", "demand"}
        self.assertFalse(forbidden & {getattr(item, "metric", None) for item in empty.bundle.observations})
        self.assertTrue(relationship_observations(reverse))

    def test_forward_populated_publishes_canonical_query_execution(self) -> None:
        result = adapt_fixture("xiyou", "keyword_asin_analysis")
        self.assertEqual(len(result.bundle.query_execution_records), 1)
        record = result.bundle.query_execution_records[0]
        relationships = relationship_observations(result)
        self.assertEqual(record.direction, RelationshipDirection.KEYWORD_TO_PRODUCT)
        self.assertEqual(record.outcome, QueryExecutionOutcome.RESULTS_RETURNED)
        self.assertEqual(record.query_keyword.normalized_text, "plastic spoons")
        self.assertIsNone(record.query_product)
        self.assertEqual(
            set(record.related_relationship_observation_ids),
            {item.observation_id for item in relationships},
        )
        run = result.bundle.transformation_runs[0]
        self.assertEqual(run.output_query_execution_ids, (record.query_execution_id,))
        self.assertEqual(record.provenance.transformation.transformation_run_id, run.transformation_run_id)
        self.assertEqual(record.provenance.transformation.mapping_version, "xiyou_keyword_to_asin_mapping_v1_1")
        self.assertEqual(CanonicalEvidenceBundle.from_dict(result.bundle.to_dict()), result.bundle)

    def test_forward_empty_is_reconstructable_from_bundle_alone(self) -> None:
        result = XiYouAdapterV0_1().adapt(
            load_fixture("xiyou_keyword_forward_empty.json"),
            context("xiyou", "keyword_asin_analysis", request={"keyword": "1/2 ball valve"}),
        )
        bundle = CanonicalEvidenceBundle.from_dict(result.bundle.to_dict())
        self.assertEqual(relationship_observations(result), [])
        self.assertEqual(len(bundle.query_execution_records), 1)
        record = bundle.query_execution_records[0]
        run = bundle.transformation_runs[0]
        self.assertEqual(record.outcome, QueryExecutionOutcome.EXPLICIT_EMPTY)
        self.assertEqual(record.direction, RelationshipDirection.KEYWORD_TO_PRODUCT)
        self.assertEqual(record.query_keyword.normalized_text, "1/2 ball valve")
        self.assertIsNone(record.query_product)
        self.assertEqual(record.related_relationship_observation_ids, ())
        self.assertEqual(run.status, TransformationStatus.SUCCESS)
        self.assertEqual(run.output_observation_ids, ())
        self.assertEqual(run.output_query_execution_ids, (record.query_execution_id,))
        self.assertEqual(record.provenance.transformation.raw_evidence_reference, bundle.raw_evidence_references[0])
        self.assertEqual(record.provenance.source_tool, "get_keyword_asin_analysis")
        self.assertFalse(bundle.quality_issues)
        serialized = canonical_json(bundle)
        for forbidden in ("demand_zero", "market_size", "competitor_count"):
            self.assertNotIn(forbidden, serialized)

    def test_reverse_populated_publishes_product_subject_query_execution(self) -> None:
        result = adapt_fixture("xiyou", "asin_keywords")
        self.assertEqual(len(result.bundle.query_execution_records), 1)
        record = result.bundle.query_execution_records[0]
        relationships = relationship_observations(result)
        self.assertEqual(record.direction, RelationshipDirection.PRODUCT_TO_KEYWORD)
        self.assertEqual(record.outcome, QueryExecutionOutcome.RESULTS_RETURNED)
        self.assertEqual(record.query_product.product_id, "product:US:B0G2VV4RBW")
        self.assertIsNone(record.query_keyword)
        self.assertEqual(
            set(record.related_relationship_observation_ids),
            {item.observation_id for item in relationships},
        )
        self.assertEqual(
            record.provenance.transformation.mapping_version,
            "xiyou_asin_to_keyword_mapping_v1_1",
        )
        self.assertEqual(
            result.bundle.transformation_runs[0].output_query_execution_ids,
            (record.query_execution_id,),
        )

    def test_variation_relationships_use_explicit_parent_as_subject(self) -> None:
        variations = adapt_fixture("xiyou", "asin_variations")
        self.assertFalse(fact_observations(variations, "parent_product_relationship"))
        children = fact_observations(variations, "child_product_relationship")
        self.assertEqual(len(children), 2)
        self.assertEqual(
            {(item.subject.subject_id, item.value.normalized_value) for item in children},
            {
                ("product:US:B0G2VVX3ML", "B0G2VV4RBW"),
                ("product:US:B0G2VVX3ML", "B0G2VZSWRN"),
            },
        )
        self.assertEqual({item.scope.scope_type for item in children}, {ScopeType.PARENT_ASIN})
        self.assertEqual(
            {item.provenance.source_field for item in children},
            {"data.childAsins[0]", "data.childAsins[1]"},
        )
        self.assertEqual(
            {item.provenance.transformation.mapping_version for item in children},
            {"xiyou_variations_mapping_v1_1"},
        )
        self.assertEqual(
            {item.provenance.transformation.transformation_run_id for item in children},
            {variations.bundle.transformation_runs[0].transformation_run_id},
        )
        self.assertEqual(
            {item.value.semantic_status for item in children},
            {SemanticStatus.CONFIRMED},
        )
        self.assertEqual(variations.raw_snapshot["data"]["parentAsin"], "B0G2VVX3ML")

    def test_variation_self_members_and_duplicates_stay_raw_without_extra_edges(self) -> None:
        payload = load_fixture("xiyou_asin_variations.json")
        payload["data"]["childAsins"].extend(["B0G2VVX3ML", "B0G2VV4RBW"])
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_variations"))
        children = fact_observations(result, "child_product_relationship")
        self.assertEqual(len(children), 2)
        self.assertFalse(
            any(item.subject.subject_id.rsplit(":", 1)[-1] == item.value.normalized_value for item in children)
        )
        codes = {item.code for item in result.diagnostics}
        self.assertIn("VARIATION_SELF_MEMBER_NOT_PUBLISHED", codes)
        self.assertIn("DUPLICATE_VARIATION_MEMBER_NOT_PUBLISHED", codes)
        self.assertEqual(
            result.raw_snapshot["data"]["childAsins"][-2:],
            ("B0G2VVX3ML", "B0G2VV4RBW"),
        )

    def test_family_members_without_confirmed_parent_do_not_become_directed_edges(self) -> None:
        cases = (
            ("missing", object(), "MISSING_VARIATION_PARENT_UNCONFIRMED"),
            ("null", None, "NULL_VARIATION_PARENT_UNCONFIRMED"),
            ("empty", "", "EMPTY_VARIATION_RELATIONSHIP_UNCONFIRMED"),
            ("invalid", "not-an-asin", "INVALID_PARENT_ASIN"),
        )
        for label, parent, expected_code in cases:
            with self.subTest(case=label):
                payload = load_fixture("xiyou_asin_variations.json")
                if label == "missing":
                    del payload["data"]["parentAsin"]
                else:
                    payload["data"]["parentAsin"] = parent
                result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_variations"))
                self.assertFalse(fact_observations(result, "parent_product_relationship"))
                self.assertFalse(fact_observations(result, "child_product_relationship"))
                reported_codes = {item.code for item in result.diagnostics} | {
                    item.issue_code for item in result.bundle.quality_issues
                }
                self.assertIn(expected_code, reported_codes)
                self.assertEqual(len(result.raw_snapshot["data"]["childAsins"]), 2)

    def test_empty_member_list_does_not_synthesize_query_as_child(self) -> None:
        payload = load_fixture("xiyou_asin_variations.json")
        payload["data"]["childAsins"] = []
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_variations"))
        self.assertFalse(fact_observations(result, "child_product_relationship"))
        self.assertEqual(
            {"EMPTY_VARIATION_RELATIONSHIP_UNCONFIRMED", "QUERY_AS_CHILD_NOT_CONFIRMED"},
            {
                item.code
                for item in result.diagnostics
                if item.code in {"EMPTY_VARIATION_RELATIONSHIP_UNCONFIRMED", "QUERY_AS_CHILD_NOT_CONFIRMED"}
            },
        )
        self.assertEqual(result.raw_snapshot["data"]["childAsins"], ())
        self.assertEqual(result.bundle.transformation_runs[0].status, TransformationStatus.PARTIAL)
        self.assertIs(result.bundle.validate(), result.bundle)

    def test_malformed_child_members_do_not_synthesize_query_as_child(self) -> None:
        payload = load_fixture("xiyou_asin_variations.json")
        payload["data"]["childAsins"] = [None, 42, "bad"]
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_variations"))
        self.assertFalse(fact_observations(result, "child_product_relationship"))
        self.assertEqual(
            sum(item.issue_code == "INVALID_CHILD_ASIN" for item in result.bundle.quality_issues),
            3,
        )
        self.assertIn("QUERY_AS_CHILD_NOT_CONFIRMED", {item.code for item in result.diagnostics})
        self.assertEqual(result.raw_snapshot["data"]["childAsins"], (None, 42, "bad"))
        self.assertEqual(result.bundle.transformation_runs[0].status, TransformationStatus.PARTIAL)
        self.assertIs(result.bundle.validate(), result.bundle)

    def test_query_absent_from_child_list_is_not_synthesized(self) -> None:
        payload = load_fixture("xiyou_asin_variations.json")
        payload["data"]["childAsins"] = ["B0G2VZSWRN"]
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_variations"))
        children = fact_observations(result, "child_product_relationship")
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].subject.subject_id, "product:US:B0G2VVX3ML")
        self.assertEqual(children[0].value.normalized_value, "B0G2VZSWRN")
        self.assertEqual(children[0].value.semantic_status, SemanticStatus.CONFIRMED)
        self.assertEqual(children[0].provenance.source_field, "data.childAsins[0]")
        self.assertNotEqual(children[0].value.normalized_value, payload["data"]["asin"])
        self.assertIn("QUERY_AS_CHILD_NOT_CONFIRMED", {item.code for item in result.diagnostics})
        self.assertEqual(result.bundle.transformation_runs[0].status, TransformationStatus.PARTIAL)
        self.assertIs(result.bundle.validate(), result.bundle)

    def test_conflicting_parent_candidate_container_is_not_resolved_by_order(self) -> None:
        payload = load_fixture("xiyou_asin_variations.json")
        payload["data"]["parentAsin"] = ["B0G2VVX3ML", "B0G2VZSWRN"]
        result = XiYouAdapterV0_1().adapt(payload, context("xiyou", "asin_variations"))
        self.assertFalse(fact_observations(result, "parent_product_relationship"))
        self.assertFalse(fact_observations(result, "child_product_relationship"))
        self.assertIn(
            "INVALID_PRIMITIVE_TYPE",
            {item.issue_code for item in result.bundle.quality_issues},
        )
        self.assertEqual(
            result.raw_snapshot["data"]["parentAsin"],
            ("B0G2VVX3ML", "B0G2VZSWRN"),
        )

    def test_bsr_category_context_is_preserved(self) -> None:
        bsr = adapt_fixture("xiyou", "asin_bsr_trends")
        ranks = metric_observations(bsr, "bsr")
        self.assertEqual(len(ranks), 2)
        self.assertEqual(ranks[0].time.observed_at_status, ObservedAtStatus.UNKNOWN)
        self.assertEqual(ranks[0].rank_context["source_date"], "2026-08-07")

    def test_current_http_variation_and_bsr_roots_keep_truthful_provenance(self) -> None:
        variation_payload = load_fixture("xiyou_asin_variations.json")["data"]
        variations = XiYouAdapterV0_1().adapt(
            variation_payload,
            context("xiyou", "asin_variations_http_v2", source_tool="get_asin_variations"),
        )
        children = fact_observations(variations, "child_product_relationship")
        self.assertEqual(len(children), 2)
        self.assertEqual(children[0].provenance.source_field, "childAsins[0]")

        bsr_payload = load_fixture("xiyou_asin_bsr.json")["data"]
        bsr = XiYouAdapterV0_1().adapt(
            bsr_payload,
            context("xiyou", "asin_bsr_trends_http_v2", source_tool="get_asin_bsr_trends"),
        )
        ranks = metric_observations(bsr, "bsr")
        self.assertEqual(len(ranks), 2)
        self.assertEqual(ranks[0].provenance.source_field, "trends[0].values[0].rank")
        self.assertEqual(ranks[0].rank_context["category_id"], "1265144011")


class SorftimeMappingTests(unittest.TestCase):
    def test_product_facts_attributes_and_description_keep_provenance(self) -> None:
        result = adapt_fixture("sorftime", "product_detail")
        self.assertEqual(len(fact_observations(result, "brand")), 2)
        self.assertTrue(fact_observations(result, "material"))
        self.assertTrue(fact_observations(result, "inlet_connection_size"))
        description = fact_observations(result, "description")[0]
        self.assertEqual(description.provenance.source_field, "data.description")
        self.assertFalse(fact_observations(result, "bullet_points"))
        self.assertIn("BULLET_POINTS_NOT_PRESENT", {item.code for item in result.diagnostics})

    def test_pressure_units_remain_three_independent_unresolved_candidates(self) -> None:
        result = adapt_fixture("sorftime", "product_detail")
        pressure = fact_observations(result, "maximum_operating_pressure")
        self.assertEqual(len(pressure), 3)
        self.assertEqual({item.value.unit.unit_code for item in pressure}, {"Pa", "WOG", "psi"})
        self.assertTrue(any(item.value.normalization_status is NormalizationStatus.AMBIGUOUS for item in pressure))
        self.assertIn("UNIT_SEMANTIC_CONFLICT", {item.issue_code for item in result.bundle.quality_issues})
        self.assertFalse(result.bundle.resolutions)

    def test_product_metrics_keep_observed_and_estimated_separate(self) -> None:
        result = adapt_fixture("sorftime", "product_detail")
        self.assertEqual(metric_observations(result, "price")[0].evidence_type, EvidenceType.OBSERVED)
        sales = metric_observations(result, "estimated_monthly_sales")[0]
        self.assertEqual(sales.evidence_type, EvidenceType.PROVIDER_ESTIMATE)
        self.assertEqual(sales.time.period_type, PeriodType.UNKNOWN)
        self.assertEqual(sales.value.semantic_status, SemanticStatus.SEMANTICS_UNCONFIRMED)

    def test_review_mapping_keeps_missing_helpful_votes_and_unknown_observation_time(self) -> None:
        result = adapt_fixture("sorftime", "product_reviews")
        self.assertEqual(len(result.bundle.observations), 1)
        review = result.bundle.observations[0]
        self.assertEqual(review.helpful_votes.presence_status, PresenceStatus.MISSING)
        self.assertIsNone(review.helpful_votes.normalized_value)
        self.assertEqual(review.review_date.normalized_value, "2026-02-25")
        self.assertEqual(review.time.observed_at_status, ObservedAtStatus.UNKNOWN)

    def test_empty_review_title_and_missing_title_are_not_conflated(self) -> None:
        payload = load_fixture("sorftime_product_reviews.json")
        payload["data"][0]["title"] = ""
        empty = SorftimeAdapterV0_1().adapt(payload, context("sorftime", "product_reviews"))
        self.assertEqual(empty.bundle.observations[0].title.presence_status, PresenceStatus.PRESENT)
        self.assertEqual(empty.bundle.observations[0].title.normalized_value, "")
        del payload["data"][0]["title"]
        missing = SorftimeAdapterV0_1().adapt(payload, context("sorftime", "product_reviews"))
        self.assertEqual(missing.bundle.observations[0].title.presence_status, PresenceStatus.MISSING)

    def test_malformed_review_emits_issue_and_no_fake_observation(self) -> None:
        payload = load_fixture("sorftime_product_reviews.json")
        del payload["data"][0]["review_date"]
        result = SorftimeAdapterV0_1().adapt(payload, context("sorftime", "product_reviews"))
        self.assertFalse(result.bundle.observations)
        self.assertIn(
            "UNSTABLE_OR_MALFORMED_REVIEW_IDENTITY",
            {item.issue_code for item in result.bundle.quality_issues},
        )

    def test_variations_preserve_child_property_and_sales_without_inventing_parent(self) -> None:
        result = adapt_fixture("sorftime", "product_variations")
        self.assertFalse(fact_observations(result, "parent_product_relationship"))
        self.assertFalse(fact_observations(result, "child_product_relationship"))
        size = fact_observations(result, "size")
        self.assertEqual(len(size), 2)
        self.assertIn("product:US:B0G2VV4RBW", {item.subject.subject_id for item in size})
        sales = metric_observations(result, "estimated_sales_volume")
        self.assertEqual(len(sales), 2)
        self.assertFalse(metric_observations(result, "revenue"))
        self.assertEqual(
            {item.value.presence_status for item in sales},
            {PresenceStatus.PRESENT, PresenceStatus.UNKNOWN},
        )
        present = [item for item in sales if item.value.presence_status is PresenceStatus.PRESENT][0]
        self.assertIn("not revenue", present.metric_semantic)
        self.assertEqual(present.scope.scope_type, ScopeType.CHILD_ASIN)
        self.assertIn("product:US:B0G2VV4RBW", {item.subject.subject_id for item in sales})
        self.assertIn(
            "VARIATION_PARENT_SEMANTICS_UNCONFIRMED",
            {item.code for item in result.diagnostics},
        )
        self.assertEqual(result.mapping_specification.version, "0.1.1")
        self.assertEqual(
            result.mapping_specification.mapping_version,
            "sorftime_variations_mapping_v1_1",
        )
        self.assertEqual(result.raw_snapshot["data"][1]["Asin"], "B0G2VV4RBW")

    def test_request_asin_is_query_context_even_when_it_is_a_returned_child(self) -> None:
        result = adapt_fixture("sorftime", "product_variations")
        query_subject = "product:US:B0G2VV4RBW"
        query_facts = [
            item
            for item in result.bundle.observations
            if item.subject.subject_id == query_subject
        ]
        self.assertTrue(fact_observations(result, "size"))
        self.assertTrue(query_facts)
        self.assertFalse(
            any(
                getattr(item, "dimension", None)
                in {"parent_product_relationship", "child_product_relationship"}
                for item in result.bundle.observations
            )
        )

    def test_sales_amount_without_returned_semantics_is_not_published(self) -> None:
        payload = load_fixture("sorftime_product_variations.json")
        payload["doc"]["sales_amount"] = "Unconfirmed amount field."
        result = SorftimeAdapterV0_1().adapt(payload, context("sorftime", "product_variations"))
        self.assertFalse(metric_observations(result, "estimated_sales_volume"))
        self.assertFalse(metric_observations(result, "revenue"))
        self.assertEqual(
            sum(item.issue_code == "SALES_AMOUNT_SEMANTICS_UNCONFIRMED" for item in result.bundle.quality_issues),
            2,
        )
        self.assertEqual(result.raw_snapshot["data"][1]["SalesAmount"], 100)


class FixturePolicyTests(unittest.TestCase):
    def test_every_fixture_is_valid_json(self) -> None:
        files = sorted(FIXTURES.glob("*.json"))
        self.assertGreater(len(files), 1)
        for path in files:
            with self.subTest(path=path.name):
                with path.open("r", encoding="utf-8") as handle:
                    json.load(handle)

    def test_manifest_documents_every_provider_fixture_as_captured_and_sanitized(self) -> None:
        manifest = load_fixture("fixture_manifest.json")
        provider_files = {path.name for path in FIXTURES.glob("*.json")} - {"fixture_manifest.json"}
        self.assertEqual(set(manifest["fixtures"]), provider_files)
        for metadata in manifest["fixtures"].values():
            self.assertEqual(metadata["classification"], "CAPTURED_AND_SANITIZED")
            self.assertRegex(metadata["fixture_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(metadata["source_sha256"], r"^[0-9a-f]{64}$")

    def test_manifest_hashes_match_normalized_fixture_content(self) -> None:
        manifest = load_fixture("fixture_manifest.json")
        for name, metadata in manifest["fixtures"].items():
            with self.subTest(fixture=name):
                fixture_path = FIXTURES / name
                normalized_bytes = fixture_path.read_bytes().replace(b"\r\n", b"\n")
                self.assertEqual(sha256(normalized_bytes).hexdigest(), metadata["fixture_sha256"])

                source_reference = Path(metadata["source"])
                self.assertFalse(source_reference.is_absolute())
                self.assertNotIn("..", source_reference.parts)

    def test_fixture_keys_and_text_have_no_credential_markers(self) -> None:
        markers = {
            "authorization",
            "api_key",
            "apikey",
            "access_token",
            "refresh_token",
            "cookie",
            "set-cookie",
            "secret",
            "client_secret",
            "password",
            "passwd",
            "bearer",
            "session",
            "sessionid",
            "token",
        }
        for path in FIXTURES.glob("*.json"):
            text = path.read_text(encoding="utf-8").casefold()
            with self.subTest(path=path.name):
                self.assertFalse({marker for marker in markers if marker in text})

    def test_all_supported_payload_fixtures_replay_deterministically(self) -> None:
        for provider, kind in FIXTURE_BY_KIND:
            with self.subTest(provider=provider, kind=kind):
                first = adapt_fixture(provider, kind)
                second = adapt_fixture(provider, kind)
                self.assertEqual(canonical_json(first.to_dict()), canonical_json(second.to_dict()))

    def test_all_eleven_provider_fixtures_produce_valid_non_orphan_bundles(self) -> None:
        cases = [
            (provider, kind, fixture_name)
            for (provider, kind), fixture_name in FIXTURE_BY_KIND.items()
        ]
        cases.append(
            ("xiyou", "keyword_asin_analysis", "xiyou_keyword_forward_empty.json")
        )
        self.assertEqual(len(cases), 11)
        query_ids: set[str] = set()
        for provider, kind, fixture_name in cases:
            with self.subTest(provider=provider, kind=kind, fixture=fixture_name):
                result = adapter_for(provider).adapt(
                    load_fixture(fixture_name),
                    context(
                        provider,
                        kind,
                        request=(
                            {"keyword": "1/2 ball valve"}
                            if fixture_name == "xiyou_keyword_forward_empty.json"
                            else None
                        ),
                    ),
                )
                self.assertIs(result.bundle.validate(), result.bundle)
                self.assertEqual(
                    CanonicalEvidenceBundle.from_dict(result.bundle.to_dict()),
                    result.bundle,
                )
                expected_query_count = 1 if kind in {
                    "keyword_asin_analysis",
                    "asin_keywords",
                } else 0
                self.assertEqual(
                    len(result.bundle.query_execution_records),
                    expected_query_count,
                )
                for record in result.bundle.query_execution_records:
                    self.assertNotIn(record.query_execution_id, query_ids)
                    query_ids.add(record.query_execution_id)
        self.assertEqual(len(query_ids), 3)


if __name__ == "__main__":
    unittest.main()
