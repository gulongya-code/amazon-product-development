from __future__ import annotations

from dataclasses import replace
from io import BytesIO, StringIO
import json
from pathlib import Path
import socket
from types import SimpleNamespace
import unittest
from urllib.error import HTTPError, URLError

from amazon_product_intelligence.connectors import (
    BoundedTransientRetryPolicy,
    CanonicalSelector,
    CapabilityStatus,
    HttpJsonTransport,
    ProviderCapability,
    ProviderConfig,
    ProviderConnectorError,
    ProviderCredential,
    ProviderErrorCode,
    ProviderRegistry,
    ProviderRequest,
    TransportRequest,
    XiYouProvider,
)
from amazon_product_intelligence.connectors.sorftime_legacy import (
    LegacySorftimeFixtureProvider,
)
from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    ObservationKind,
    PresenceStatus,
    SemanticStatus,
)
from amazon_product_intelligence.data_cleaning import DataCleaningRequest, DataCleaningService
from amazon_product_intelligence.data_cleaning.cli import StaticJsonTransport, run
from amazon_product_intelligence.normalization import CanonicalNormalizationPipeline


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "data_cleaning_v0_1"
SECRET = "test-secret-must-never-appear"
NOW = "2025-01-15T00:00:00+00:00"


class FakeResponse:
    def __init__(self, payload: object, *, status: int = 200, headers: dict[str, str] | None = None):
        self.status = status
        self.headers = headers or {}
        self._body = json.dumps(payload).encode("utf-8") if not isinstance(payload, bytes) else payload

    def read(self, size: int = -1) -> bytes:
        return self._body[:size] if size >= 0 else self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class SequenceOpener:
    def __init__(self, *outcomes: object):
        self.outcomes = list(outcomes)
        self.requests: list[object] = []

    def __call__(self, request: object, *, timeout: float) -> object:
        self.requests.append(request)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def payload(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def transport_request() -> TransportRequest:
    return TransportRequest(
        provider_id="xiyou",
        operation="asin_info",
        method="POST",
        endpoint="/v1/asins/info",
        parameters={"entities": [{"country": "US", "asin": "B0G2VV4RBW"}]},
        timeout_seconds=2.0,
        public_headers={"X-Auth-Version": "2.0"},
        credential=ProviderCredential(
            environment_variable="XIYOU_API_KEY",
            injection_name="X-Api-Key",
            value=SECRET,
        ),
    )


def provider_request(field: str = "product.title") -> ProviderRequest:
    return ProviderRequest(
        canonical_field=field,
        parameters={"entities": [{"country": "US", "asin": "B0G2VV4RBW"}]},
        marketplace="US",
        locale="en-us",
        retrieved_at=NOW,
        transformed_at=NOW,
        collection_run_id="collection:data-cleaning-test",
        currency="USD",
    )


def cleaning_request(provider: str, operation: str, parameters: dict[str, object]) -> DataCleaningRequest:
    return DataCleaningRequest(
        provider_id=provider,
        operation=operation,
        parameters=parameters,
        marketplace="US",
        locale="en-us",
        retrieved_at=NOW,
        transformed_at=NOW,
        collection_run_id="collection:data-cleaning-test",
        normalization_run_id="normalization:data-cleaning-test",
        normalized_at=NOW,
        currency="USD",
    )


def service_for(provider_id: str, operation: str, body: object) -> DataCleaningService:
    environment_name = "XIYOU_API_KEY" if provider_id == "xiyou" else "SORFTIME_API_KEY"
    transport = StaticJsonTransport(operation, body)
    provider = (
        XiYouProvider(transport, environment={environment_name: "fixture-only"})
        if provider_id == "xiyou"
        else LegacySorftimeFixtureProvider(
            transport,
            fixture_only=True,
            environment={environment_name: "fixture-only"},
        )
    )
    registry = ProviderRegistry()
    registry.register(
        provider,
        ProviderConfig(
            provider_id=provider_id,
            enabled=True,
            priority=1,
            credential_env=environment_name,
        ),
    )
    return DataCleaningService(registry, CanonicalNormalizationPipeline.with_defaults())


class ProductionTransportTests(unittest.TestCase):
    def test_success_posts_deterministic_json_and_injects_secret_only_in_header(self) -> None:
        opener = SequenceOpener(
            FakeResponse(
                payload("xiyou_asin_info_http_v2.json"),
                headers={"X-Trace-Id": "trace-safe", "X-Cost-Credits": "1"},
            )
        )
        response = HttpJsonTransport({"xiyou": "https://openapi.xydc.com"}, opener=opener).execute(
            transport_request()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.metadata["trace_id"], "trace-safe")
        sent = opener.requests[0]
        headers = {key.casefold(): value for key, value in sent.header_items()}
        self.assertEqual(sent.full_url, "https://openapi.xydc.com/v1/asins/info")
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(headers["x-api-key"], SECRET)
        self.assertNotIn(SECRET, transport_request().to_safe_dict().__repr__())

    def test_timeout_is_sanitized_and_retryable(self) -> None:
        transport = HttpJsonTransport(
            {"xiyou": "https://openapi.xydc.com"},
            opener=SequenceOpener(socket.timeout(f"timeout {SECRET}")),
        )
        with self.assertRaises(ProviderConnectorError) as captured:
            transport.execute(transport_request())
        self.assertEqual(captured.exception.code, ProviderErrorCode.TIMEOUT)
        self.assertTrue(captured.exception.retryable)
        self.assertNotIn(SECRET, str(captured.exception.to_dict()))

    def test_invalid_json_is_controlled(self) -> None:
        transport = HttpJsonTransport(
            {"xiyou": "https://openapi.xydc.com"},
            opener=SequenceOpener(FakeResponse(b"not-json")),
        )
        with self.assertRaises(ProviderConnectorError) as captured:
            transport.execute(transport_request())
        self.assertEqual(captured.exception.code, ProviderErrorCode.BAD_RESPONSE)

    def test_response_size_limit_fails_closed(self) -> None:
        transport = HttpJsonTransport(
            {"xiyou": "https://openapi.xydc.com"},
            opener=SequenceOpener(FakeResponse(b"{}x")),
            max_response_bytes=2,
        )
        with self.assertRaises(ProviderConnectorError) as captured:
            transport.execute(transport_request())
        self.assertEqual(captured.exception.code, ProviderErrorCode.BAD_RESPONSE)

    def test_network_exception_does_not_leak_provider_detail(self) -> None:
        transport = HttpJsonTransport(
            {"xiyou": "https://openapi.xydc.com"},
            opener=SequenceOpener(URLError(f"network {SECRET}")),
        )
        with self.assertRaises(ProviderConnectorError) as captured:
            transport.execute(transport_request())
        self.assertEqual(captured.exception.code, ProviderErrorCode.NETWORK)
        self.assertNotIn(SECRET, str(captured.exception.to_dict()))

    def _fetch_with(self, opener: SequenceOpener, *, attempts: int = 3) -> object:
        provider = XiYouProvider(
            HttpJsonTransport({"xiyou": "https://openapi.xydc.com"}, opener=opener),
            environment={"XIYOU_API_KEY": SECRET},
            retry_policy=BoundedTransientRetryPolicy(),
        )
        return provider.fetch(
            provider_request(),
            ProviderConfig(
                provider_id="xiyou",
                enabled=True,
                priority=1,
                credential_env="XIYOU_API_KEY",
                max_attempts=attempts,
            ),
        )

    def test_bounded_retry_recovers_from_two_timeouts(self) -> None:
        opener = SequenceOpener(
            socket.timeout(),
            socket.timeout(),
            FakeResponse(payload("xiyou_asin_info_http_v2.json")),
        )
        result = self._fetch_with(opener)
        self.assertEqual(len(opener.requests), 3)
        self.assertTrue(result.adaptation.succeeded)

    def test_authentication_failure_is_not_retried(self) -> None:
        error = HTTPError("https://safe.invalid", 401, "denied", {}, BytesIO(b"{}"))
        opener = SequenceOpener(error)
        with self.assertRaises(ProviderConnectorError) as captured:
            self._fetch_with(opener)
        self.assertEqual(captured.exception.code, ProviderErrorCode.AUTHENTICATION)
        self.assertEqual(len(opener.requests), 1)

    def test_rate_limit_is_unified_and_not_blindly_retried(self) -> None:
        error = HTTPError(
            "https://safe.invalid",
            429,
            "limited",
            {"Retry-After": "9"},
            BytesIO(b"{}"),
        )
        opener = SequenceOpener(error)
        with self.assertRaises(ProviderConnectorError) as captured:
            self._fetch_with(opener)
        self.assertEqual(captured.exception.code, ProviderErrorCode.RATE_LIMIT)
        self.assertEqual(captured.exception.details["retry_after_seconds"], 9)
        self.assertEqual(len(opener.requests), 1)

    def test_5xx_retry_is_bounded(self) -> None:
        def failure() -> HTTPError:
            return HTTPError("https://safe.invalid", 503, "down", {}, BytesIO(b"{}"))

        opener = SequenceOpener(failure(), failure(), failure())
        with self.assertRaises(ProviderConnectorError) as captured:
            self._fetch_with(opener)
        self.assertEqual(captured.exception.code, ProviderErrorCode.PROVIDER_UNAVAILABLE)
        self.assertEqual(len(opener.requests), 3)

    def test_schema_mismatch_is_controlled_after_http_success(self) -> None:
        opener = SequenceOpener(FakeResponse({"entities": "unexpected"}))
        with self.assertRaises(ProviderConnectorError) as captured:
            self._fetch_with(opener)
        self.assertEqual(captured.exception.code, ProviderErrorCode.SCHEMA_MISMATCH)


class CleaningServiceTests(unittest.TestCase):
    def test_xiyou_fixture_runs_connector_mapping_normalization_and_quality(self) -> None:
        result = service_for(
            "xiyou", "asin_info", payload("xiyou_asin_info_http_v2.json")
        ).clean(
            cleaning_request(
                "xiyou",
                "asin_info",
                {"entities": [{"country": "US", "asin": "B0G2VV4RBW"}]},
            )
        )
        self.assertEqual(result.provider, "xiyou")
        self.assertEqual(result.quality_summary.fields_observed, 4)
        self.assertEqual({item.canonical_field for item in result.fields}, {
            "product.title", "metric.price", "metric.rating", "metric.review_count"
        })
        price = next(item for item in result.fields if item.canonical_field == "metric.price")
        self.assertEqual(price.normalized_value.__str__(), "18.99")
        self.assertEqual(price.provenance.provider, "xiyou")
        self.assertEqual(price.provenance.source_tool, "get_asin_info")
        self.assertEqual(price.provenance.source_field, "entities[0].price")
        self.assertEqual(result.mapping_versions, ("xiyou_product_info_http_v2_mapping_v2",))

    def test_sorftime_uses_same_service_core(self) -> None:
        result = service_for(
            "sorftime", "product_detail", payload("sorftime_product_detail.json")
        ).clean(
            cleaning_request(
                "sorftime", "product_detail", {"amz_site": "US", "asin": "B0G2VV4RBW"}
            )
        )
        self.assertEqual(result.provider, "sorftime")
        self.assertGreater(result.quality_summary.fields_observed, 4)
        self.assertTrue(any(item.canonical_field == "product.title" for item in result.fields))

    def test_partial_success_retains_valid_fields_and_marks_invalid_field(self) -> None:
        body = payload("xiyou_asin_info_http_v2.json")
        body["entities"][0]["stars"] = "not-a-rating"
        result = service_for("xiyou", "asin_info", body).clean(
            cleaning_request("xiyou", "asin_info", {"entities": []})
        )
        self.assertEqual(result.status.value, "PARTIAL_SUCCESS")
        self.assertEqual(result.quality_summary.fields_invalid, 1)
        rating = next(item for item in result.fields if item.canonical_field == "metric.rating")
        self.assertEqual(rating.semantic_status, SemanticStatus.INVALID)
        self.assertTrue(any(item.canonical_field == "product.title" and item.normalized_value for item in result.fields))

    def test_missing_field_stays_missing_and_does_not_become_zero(self) -> None:
        body = payload("xiyou_asin_info_http_v2.json")
        del body["entities"][0]["ratings"]
        result = service_for("xiyou", "asin_info", body).clean(
            cleaning_request("xiyou", "asin_info", {"entities": []})
        )
        review = next(item for item in result.fields if item.canonical_field == "metric.review_count")
        self.assertEqual(review.presence_status, PresenceStatus.MISSING)
        self.assertIsNone(review.normalized_value)

    def test_explicit_null_price_is_subject_preserving_not_missing(self) -> None:
        body = {
            "entities": [
                {
                    "asin": "B000000001",
                    "country": "US",
                    "currency": "USD",
                    "price": "10.00",
                    "ratings": 10,
                    "stars": "4.5",
                    "title": "Valid price",
                },
                {
                    "asin": "B000000002",
                    "country": "US",
                    "currency": "USD",
                    "price": None,
                    "ratings": 20,
                    "stars": "4.6",
                    "title": "Explicit null price",
                },
            ]
        }
        result = service_for("xiyou", "asin_info", body).clean(
            cleaning_request("xiyou", "asin_info", {"entities": []})
        )
        prices = {
            field.subject.subject_id: field
            for field in result.fields
            if field.canonical_field == "metric.price" and field.subject is not None
        }
        explicit_null = prices["product:US:B000000002"]
        self.assertEqual(result.status.value, "PARTIAL_SUCCESS")
        self.assertEqual(result.quality_summary.fields_explicit_null, 1)
        self.assertEqual(result.quality_summary.fields_missing, 0)
        self.assertEqual(explicit_null.presence_status, PresenceStatus.EXPLICIT_NULL)
        self.assertIsNone(explicit_null.normalized_value)
        self.assertEqual(explicit_null.unit.unit_code, "USD")
        self.assertEqual(
            result.mapping_versions,
            ("xiyou_product_info_http_v2_mapping_v2",),
        )

    def test_extra_provider_field_is_retained_as_diagnostic_not_invented_canonical(self) -> None:
        body = payload("xiyou_asin_info_http_v2.json")
        body["entities"][0]["newProviderOnlyField"] = "unmapped"
        result = service_for("xiyou", "asin_info", body).clean(
            cleaning_request("xiyou", "asin_info", {"entities": []})
        )
        self.assertTrue(any(item["code"] == "UNMAPPED_SOURCE_FIELD" for item in result.diagnostics))
        self.assertFalse(any(item.canonical_field.endswith("newProviderOnlyField") for item in result.fields))

    def test_summary_keeps_unknown_empty_false_zero_and_empty_collection_distinct(self) -> None:
        base = service_for(
            "xiyou", "asin_info", payload("xiyou_asin_info_http_v2.json")
        ).clean(cleaning_request("xiyou", "asin_info", {"entities": []})).fields[0]
        unknown = replace(
            base,
            raw_value=None,
            mapped_value=None,
            normalized_value=None,
            presence_status=PresenceStatus.UNKNOWN,
            semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
            normalization_status=NormalizationStatus.NOT_ATTEMPTED,
        )
        empty_query = replace(unknown, presence_status=PresenceStatus.QUERY_RETURNED_EMPTY)
        zero = replace(base, raw_value=0, mapped_value=0, normalized_value=0)
        false = replace(base, raw_value=False, mapped_value=False, normalized_value=False)
        empty_collection = replace(base, raw_value=(), mapped_value=(), normalized_value=())
        summary = DataCleaningService._summarize(
            (unknown, empty_query, zero, false, empty_collection), 0
        )
        self.assertEqual(summary.fields_unknown, 1)
        self.assertEqual(summary.fields_query_returned_empty, 1)
        self.assertEqual(summary.fields_observed, 3)
        self.assertEqual(summary.fields_missing, 0)

    def test_clean_result_serialization_is_deterministic_and_excludes_raw_payload(self) -> None:
        service = service_for("xiyou", "asin_info", payload("xiyou_asin_info_http_v2.json"))
        request = cleaning_request("xiyou", "asin_info", {"entities": []})
        first = service.clean(request).to_json(indent=None)
        second = service.clean(request).to_json(indent=None)
        self.assertEqual(first, second)
        self.assertNotIn("raw_snapshot", first)
        self.assertNotIn(SECRET, first)

    def test_future_provider_uses_same_core_without_provider_branch(self) -> None:
        base_service = service_for("xiyou", "asin_info", payload("xiyou_asin_info_http_v2.json"))
        base_result = base_service._registry.get("xiyou").fetch(
            provider_request(), base_service._registry.configuration("xiyou")
        )
        observation = next(
            item
            for item in base_result.adaptation.bundle.observations
            if getattr(item, "dimension", None) == "title"
        )
        provenance = replace(
            observation.provenance,
            provider="future_provider",
            source_tool="future_product_detail",
        )
        future_observation = replace(observation, provenance=provenance)
        future_capability = ProviderCapability(
            provider_id="future_provider",
            canonical_field="product.title",
            capability_status=CapabilityStatus.AVAILABLE,
            source_field="record.title",
            endpoint="provider-tool://future/product_detail",
            operation="product_detail",
            payload_kind="product_detail",
            selector=CanonicalSelector(
                observation_kind=ObservationKind.PRODUCT_FACT,
                canonical_names=("title",),
            ),
        )

        class FakeProvider:
            provider_id = "future_provider"
            display_name = "Future Provider"

            def __init__(self) -> None:
                self.capabilities = (future_capability,)

            def capability(self, canonical_field: str) -> ProviderCapability | None:
                return future_capability if canonical_field == "product.title" else None

            def fetch(self, request: object, configuration: object) -> object:
                bundle = SimpleNamespace(
                    observations=(future_observation,),
                    quality_issues=(),
                    raw_evidence_references=(
                        future_observation.provenance.transformation.raw_evidence_reference,
                    ),
                    transformation_runs=base_result.adaptation.bundle.transformation_runs,
                    query_execution_records=(),
                )
                adaptation = SimpleNamespace(
                    bundle=bundle,
                    diagnostics=(),
                    raw_evidence=base_result.adaptation.raw_evidence,
                )
                return SimpleNamespace(adaptation=adaptation)

        registry = ProviderRegistry()
        registry.register(
            FakeProvider(),
            ProviderConfig(
                provider_id="future_provider",
                enabled=True,
                priority=1,
                credential_env=None,
            ),
        )
        result = DataCleaningService(
            registry, CanonicalNormalizationPipeline.with_defaults()
        ).clean(cleaning_request("future_provider", "product_detail", {}))
        self.assertEqual(result.provider, "future_provider")
        self.assertEqual(result.fields[0].provenance.provider, "future_provider")


class EntryPointTests(unittest.TestCase):
    def test_fixture_mode_returns_structured_summary_offline(self) -> None:
        stdout = StringIO()
        code = run(
            ["--fixture", "--provider", "xiyou", "--operation", "asin_info"],
            environ={},
            stdout=stdout,
        )
        result = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(result["provider"], "xiyou")
        self.assertEqual(result["fields_observed"], 4)

    def test_live_mode_missing_credential_is_blocked_before_network(self) -> None:
        stdout = StringIO()
        code = run(
            ["--live", "--provider", "xiyou", "--operation", "asin_info"],
            environ={},
            stdout=stdout,
        )
        result = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(result["status"], "BLOCKED_CONFIGURATION")
        self.assertEqual(result["error"]["code"], "CONFIGURATION")

    def test_invalid_provider_and_operation_are_controlled(self) -> None:
        for arguments in (
            ["--fixture", "--provider", "not_registered", "--operation", "x"],
            ["--fixture", "--provider", "xiyou", "--operation", "not_a_real_operation"],
        ):
            with self.subTest(arguments=arguments):
                stdout = StringIO()
                self.assertEqual(run(arguments, environ={}, stdout=stdout), 2)
                self.assertEqual(json.loads(stdout.getvalue())["status"], "FAILED")

    def test_fixture_json_output_is_stable_and_secret_safe(self) -> None:
        arguments = [
            "--fixture", "--provider", "sorftime", "--operation", "product_detail", "--output", "json"
        ]
        outputs = []
        for _ in range(2):
            stdout = StringIO()
            self.assertEqual(run(arguments, environ={"SORFTIME_API_KEY": SECRET}, stdout=stdout), 0)
            outputs.append(stdout.getvalue())
        self.assertEqual(outputs[0], outputs[1])
        self.assertNotIn(SECRET, outputs[0])
        self.assertNotIn("raw_snapshot", outputs[0])


if __name__ == "__main__":
    unittest.main()
