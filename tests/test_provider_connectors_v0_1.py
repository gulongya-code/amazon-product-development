from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.adapters import AdaptationResult, AdaptationStatistics
from amazon_product_intelligence.connectors import (
    CanonicalSelector,
    CapabilityStatus,
    DataProvider,
    ProviderAttemptStatus,
    ProviderCapability,
    ProviderConfig,
    ProviderConnectorError,
    ProviderErrorCode,
    ProviderFetchResult,
    ProviderFetchStatus,
    ProviderOperation,
    ProviderRegistry,
    ProviderRequest,
    ProviderResolver,
    SorftimeProvider,
    TransportResponse,
    XiYouProvider,
    build_registry,
)
from amazon_product_intelligence.contracts import CanonicalEvidenceBundle, ObservationKind


FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
RETRIEVED_AT = "2026-08-19T01:00:00Z"
TRANSFORMED_AT = "2026-08-19T01:00:01Z"
TEST_CREDENTIAL = "fixture-credential-not-real"


def load_fixture(name: str) -> dict[str, object]:
    with (FIXTURES / name).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def provider_request(
    canonical_field: str = "metric.price",
    *,
    parameters: dict[str, object] | None = None,
) -> ProviderRequest:
    return ProviderRequest(
        canonical_field=canonical_field,
        parameters=parameters or {"asin": "B0G2VV4RBW"},
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:connector-test:{canonical_field}",
        currency="USD",
    )


def configuration(
    provider_id: str,
    *,
    enabled: bool = True,
    priority: int = 10,
    max_attempts: int = 1,
    field_priorities: dict[str, int] | None = None,
) -> ProviderConfig:
    return ProviderConfig(
        provider_id=provider_id,
        enabled=enabled,
        priority=priority,
        credential_env=f"TEST_{provider_id.upper()}_CREDENTIAL",
        timeout_seconds=2.0,
        max_attempts=max_attempts,
        field_priorities=field_priorities or {},
    )


class StubTransport:
    def __init__(self, outcomes: dict[str, object]) -> None:
        self.outcomes = {key: list(value) if isinstance(value, list) else [value] for key, value in outcomes.items()}
        self.requests = []

    def execute(self, request):
        self.requests.append(request)
        queue = self.outcomes[request.operation]
        outcome = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(outcome, BaseException):
            raise outcome
        if isinstance(outcome, TransportResponse):
            return outcome
        return TransportResponse(status_code=200, payload=deepcopy(outcome))


class RetryRetryableOnce:
    def should_retry(self, error, *, attempt: int, max_attempts: int) -> bool:
        return error.retryable and attempt < max_attempts


class FakeProvider:
    """Test-only provider proving registry/resolver structural extensibility."""

    provider_id = "fake"
    display_name = "Fake Provider"
    capabilities = (
        ProviderCapability(
            provider_id="fake",
            canonical_field="relationship.keyword_to_product",
            capability_status=CapabilityStatus.AVAILABLE,
            source_field="fixture.empty_result",
            endpoint="fixture://empty-query",
            operation="empty_query",
            payload_kind="empty_query",
            selector=CanonicalSelector(
                observation_kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
            ),
            accepts_empty_query=True,
            notes="Test-only provider.",
        ),
    )

    def __init__(self) -> None:
        self.calls = 0

    def capability(self, canonical_field: str):
        return self.capabilities[0] if canonical_field == self.capabilities[0].canonical_field else None

    def fetch(self, request: ProviderRequest, provider_configuration: ProviderConfig) -> ProviderFetchResult:
        self.calls += 1
        bundle = CanonicalEvidenceBundle(
            transformation_runs=(),
            observations=(),
            conflicts=(),
            resolutions=(),
            quality_issues=(),
        )
        adaptation = AdaptationResult(
            provider="fake",
            adapter_version="test-only",
            payload_kind="empty_query",
            mapping_specification=None,
            raw_evidence=None,
            raw_snapshot={},
            bundle=bundle,
            diagnostics=(),
            errors=(),
            statistics=AdaptationStatistics(
                mapped_observation_count=0,
                quality_issue_count=0,
                diagnostic_count=0,
                error_count=0,
            ),
        )
        return ProviderFetchResult(
            provider_id="fake",
            canonical_field=request.canonical_field,
            capability=self.capabilities[0],
            status=ProviderFetchStatus.EMPTY,
            adaptation=adaptation,
            observations=(),
        )


class ProviderContractAndCapabilityTests(unittest.TestCase):
    def test_builtin_connectors_implement_provider_contract(self) -> None:
        xiyou = XiYouProvider(StubTransport({}), environment={})
        sorftime = SorftimeProvider(StubTransport({}), environment={})
        self.assertIsInstance(xiyou, DataProvider)
        self.assertIsInstance(sorftime, DataProvider)
        self.assertEqual(xiyou.provider_id, "xiyou")
        self.assertEqual(sorftime.provider_id, "sorftime")

    def test_capability_vocabulary_excludes_calculated(self) -> None:
        self.assertEqual(
            set(CapabilityStatus),
            {
                CapabilityStatus.AVAILABLE,
                CapabilityStatus.PARTIAL,
                CapabilityStatus.UNAVAILABLE,
                CapabilityStatus.UNKNOWN,
            },
        )
        with self.assertRaises(ValueError):
            CapabilityStatus("CALCULATED")

    def test_xiyou_exposes_all_four_provider_capability_states(self) -> None:
        provider = XiYouProvider(StubTransport({}), environment={})
        self.assertEqual(provider.capability("metric.price").capability_status, CapabilityStatus.AVAILABLE)
        self.assertEqual(provider.capability("keyword.channel").capability_status, CapabilityStatus.PARTIAL)
        self.assertEqual(provider.capability("keyword.locale").capability_status, CapabilityStatus.UNAVAILABLE)
        self.assertEqual(provider.capability("product.seller").capability_status, CapabilityStatus.UNKNOWN)

    def test_sorftime_unknown_fields_are_not_promoted(self) -> None:
        provider = SorftimeProvider(StubTransport({}), environment={})
        self.assertEqual(provider.capability("product.seller").capability_status, CapabilityStatus.UNKNOWN)
        self.assertEqual(
            provider.capability("keyword.estimate_method_status").capability_status,
            CapabilityStatus.UNKNOWN,
        )

    def test_request_rejects_embedded_credentials(self) -> None:
        with self.assertRaisesRegex(ValueError, "credential field"):
            provider_request(parameters={"asin": "B0G2VV4RBW", "api_key": "must-not-enter"})

    def test_operation_rejects_secret_bearing_public_headers(self) -> None:
        with self.assertRaisesRegex(ValueError, "ProviderCredential"):
            ProviderOperation(
                operation="unsafe",
                payload_kind="unsafe",
                source_tool="unsafe",
                method="POST",
                endpoint="fixture://unsafe",
                requires_credential=False,
                public_headers={"Authorization": "must-not-enter"},
            )


class ProviderRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.xiyou = XiYouProvider(StubTransport({}), environment={})
        self.sorftime = SorftimeProvider(StubTransport({}), environment={})

    def test_register_get_and_duplicate_behavior(self) -> None:
        registry = ProviderRegistry()
        registry.register(self.xiyou, configuration("xiyou"))
        self.assertIs(registry.get("xiyou"), self.xiyou)
        with self.assertRaises(ProviderConnectorError) as caught:
            registry.register(self.xiyou, configuration("xiyou"))
        self.assertEqual(caught.exception.code, ProviderErrorCode.DUPLICATE_PROVIDER)

    def test_unknown_provider_has_stable_error(self) -> None:
        with self.assertRaises(ProviderConnectorError) as caught:
            ProviderRegistry().get("missing")
        self.assertEqual(caught.exception.code, ProviderErrorCode.PROVIDER_NOT_REGISTERED)

    def test_both_enabled_are_sorted_by_configuration_priority(self) -> None:
        registry = build_registry(
            (
                (self.xiyou, configuration("xiyou", priority=20)),
                (self.sorftime, configuration("sorftime", priority=10)),
            )
        )
        self.assertEqual(tuple(item.provider_id for item in registry.enabled()), ("sorftime", "xiyou"))
        self.assertEqual(
            tuple(item.provider.provider_id for item in registry.candidates("metric.price")),
            ("sorftime", "xiyou"),
        )

    def test_xiyou_only_mode_initializes_without_sorftime(self) -> None:
        registry = build_registry(
            (
                (self.xiyou, configuration("xiyou", enabled=True)),
                (self.sorftime, configuration("sorftime", enabled=False)),
            )
        )
        self.assertEqual(tuple(item.provider_id for item in registry.enabled()), ("xiyou",))

    def test_sorftime_only_mode_initializes_without_xiyou(self) -> None:
        registry = build_registry(
            (
                (self.xiyou, configuration("xiyou", enabled=False)),
                (self.sorftime, configuration("sorftime", enabled=True)),
            )
        )
        self.assertEqual(tuple(item.provider_id for item in registry.enabled()), ("sorftime",))

    def test_runtime_enable_disable_and_field_priority_override(self) -> None:
        registry = build_registry(
            (
                (
                    self.xiyou,
                    configuration(
                        "xiyou",
                        priority=5,
                        field_priorities={"metric.price": 30},
                    ),
                ),
                (self.sorftime, configuration("sorftime", priority=20)),
            )
        )
        self.assertEqual(registry.candidates("metric.price")[0].provider.provider_id, "sorftime")
        registry.set_enabled("sorftime", False)
        self.assertEqual(tuple(item.provider_id for item in registry.enabled()), ("xiyou",))
        registry.set_enabled("sorftime", True)
        registry.set_priority("sorftime", 40)
        self.assertEqual(registry.configuration("sorftime").priority, 40)

    def test_generic_fake_provider_registers_and_runs_without_core_edits(self) -> None:
        fake = FakeProvider()
        registry = build_registry(((fake, configuration("fake", priority=1)),))
        result = ProviderResolver(registry).resolve(
            provider_request("relationship.keyword_to_product", parameters={"keyword": "fixture"})
        )
        self.assertEqual(result.selected_provider_id, "fake")
        self.assertEqual(result.result.status, ProviderFetchStatus.EMPTY)
        self.assertEqual(fake.calls, 1)

    def test_environment_configuration_is_strict_and_credential_free(self) -> None:
        config = ProviderConfig.from_environment(
            provider_id="xiyou",
            credential_env="XIYOU_API_KEY",
            environ={
                "API_PROVIDER_XIYOU_ENABLED": "true",
                "API_PROVIDER_XIYOU_PRIORITY": "17",
                "API_PROVIDER_XIYOU_TIMEOUT_SECONDS": "3.5",
                "API_PROVIDER_XIYOU_MAX_ATTEMPTS": "2",
                "XIYOU_API_KEY": TEST_CREDENTIAL,
            },
        )
        self.assertTrue(config.enabled)
        self.assertEqual(config.priority, 17)
        self.assertEqual(config.timeout_seconds, 3.5)
        self.assertEqual(config.max_attempts, 2)
        self.assertNotIn(TEST_CREDENTIAL, repr(config))


class ProviderFetchAndResolutionTests(unittest.TestCase):
    def test_xiyou_fetch_reuses_canonical_provenance_and_raw_values(self) -> None:
        transport = StubTransport({"asin_info": load_fixture("xiyou_asin_info.json")})
        provider = XiYouProvider(
            transport,
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        result = provider.fetch(provider_request(), configuration("xiyou"))
        self.assertEqual(result.status, ProviderFetchStatus.RETURNED)
        self.assertEqual(len(result.observations), 1)
        observation = result.observations[0]
        self.assertEqual(observation.value.raw_value, "18.99")
        self.assertEqual(observation.value.normalized_value, 18.99)
        self.assertEqual(observation.provenance.provider, "xiyou")
        self.assertEqual(observation.provenance.source_field, "data.entities[0].price")
        self.assertEqual(observation.provenance.retrieved_at, RETRIEVED_AT)
        self.assertEqual(result.provenance, (observation.provenance,))
        safe_request = transport.requests[0].to_safe_dict()
        self.assertNotIn(TEST_CREDENTIAL, repr(transport.requests[0]))
        self.assertNotIn(TEST_CREDENTIAL, repr(safe_request))
        self.assertEqual(safe_request["credential"]["value"], "<redacted>")

    def test_sorftime_fetch_uses_existing_adapter_and_provenance(self) -> None:
        provider = SorftimeProvider(
            StubTransport({"product_detail": load_fixture("sorftime_product_detail.json")}),
            environment={"TEST_SORFTIME_CREDENTIAL": TEST_CREDENTIAL},
        )
        result = provider.fetch(
            provider_request("product.brand"),
            configuration("sorftime"),
        )
        self.assertEqual(result.status, ProviderFetchStatus.RETURNED)
        self.assertEqual(result.observations[0].value.normalized_value, "SKLSSVF")
        self.assertEqual(result.observations[0].provenance.provider, "sorftime")
        self.assertEqual(result.observations[0].provenance.source_field, "data.brand")

    def test_missing_credentials_is_recognizable_configuration_error(self) -> None:
        provider = XiYouProvider(StubTransport({"asin_info": {}}), environment={})
        with self.assertRaises(ProviderConnectorError) as caught:
            provider.fetch(provider_request(), configuration("xiyou"))
        self.assertEqual(caught.exception.code, ProviderErrorCode.CONFIGURATION)
        self.assertIn("TEST_XIYOU_CREDENTIAL", str(caught.exception))

    def test_disabled_provider_is_rejected_before_credentials_or_transport(self) -> None:
        transport = StubTransport({"asin_info": load_fixture("xiyou_asin_info.json")})
        provider = XiYouProvider(transport, environment={})
        with self.assertRaises(ProviderConnectorError) as caught:
            provider.fetch(provider_request(), configuration("xiyou", enabled=False))
        self.assertEqual(caught.exception.code, ProviderErrorCode.PROVIDER_UNAVAILABLE)
        self.assertFalse(transport.requests)

    def test_fallback_uses_second_provider_after_primary_failure(self) -> None:
        xiyou = XiYouProvider(
            StubTransport({"asin_info": TransportResponse(status_code=503, payload={})}),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        sorftime = SorftimeProvider(
            StubTransport({"product_detail": load_fixture("sorftime_product_detail.json")}),
            environment={"TEST_SORFTIME_CREDENTIAL": TEST_CREDENTIAL},
        )
        registry = build_registry(
            (
                (xiyou, configuration("xiyou", priority=10)),
                (sorftime, configuration("sorftime", priority=20)),
            )
        )
        resolution = ProviderResolver(registry).resolve(provider_request())
        self.assertEqual(resolution.selected_provider_id, "sorftime")
        self.assertEqual(
            tuple(item.status for item in resolution.attempts),
            (ProviderAttemptStatus.FAILED, ProviderAttemptStatus.SELECTED),
        )
        self.assertEqual(resolution.attempts[0].error_code, ProviderErrorCode.PROVIDER_UNAVAILABLE)

    def test_fallback_uses_second_provider_when_field_is_missing(self) -> None:
        xiyou_payload = load_fixture("xiyou_asin_info.json")
        del xiyou_payload["data"]["entities"][0]["price"]
        xiyou = XiYouProvider(
            StubTransport({"asin_info": xiyou_payload}),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        sorftime = SorftimeProvider(
            StubTransport({"product_detail": load_fixture("sorftime_product_detail.json")}),
            environment={"TEST_SORFTIME_CREDENTIAL": TEST_CREDENTIAL},
        )
        resolution = ProviderResolver(
            build_registry(
                (
                    (xiyou, configuration("xiyou", priority=10)),
                    (sorftime, configuration("sorftime", priority=20)),
                )
            )
        ).resolve(provider_request())
        self.assertEqual(resolution.selected_provider_id, "sorftime")
        self.assertEqual(resolution.attempts[0].status, ProviderAttemptStatus.FIELD_MISSING)

    def test_disabled_primary_is_skipped_by_resolver(self) -> None:
        xiyou_transport = StubTransport({"asin_info": AssertionError("disabled provider was called")})
        xiyou = XiYouProvider(xiyou_transport, environment={})
        sorftime = SorftimeProvider(
            StubTransport({"product_detail": load_fixture("sorftime_product_detail.json")}),
            environment={"TEST_SORFTIME_CREDENTIAL": TEST_CREDENTIAL},
        )
        resolution = ProviderResolver(
            build_registry(
                (
                    (xiyou, configuration("xiyou", enabled=False, priority=1)),
                    (sorftime, configuration("sorftime", enabled=True, priority=2)),
                )
            )
        ).resolve(provider_request())
        self.assertEqual(resolution.selected_provider_id, "sorftime")
        self.assertFalse(xiyou_transport.requests)

    def test_explicit_empty_query_is_selected_evidence_not_failure(self) -> None:
        provider = XiYouProvider(
            StubTransport(
                {"keyword_asin_analysis": load_fixture("xiyou_keyword_forward_empty.json")}
            ),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        resolution = ProviderResolver(
            build_registry(((provider, configuration("xiyou")),))
        ).resolve(
            provider_request(
                "relationship.keyword_to_product",
                parameters={"keyword": "1/2 ball valve"},
            )
        )
        self.assertEqual(resolution.result.status, ProviderFetchStatus.EMPTY)
        self.assertEqual(resolution.attempts[-1].status, ProviderAttemptStatus.EMPTY_SELECTED)

    def test_forward_and_reverse_relationship_capabilities_select_distinct_operations(self) -> None:
        transport = StubTransport(
            {
                "keyword_asin_analysis": load_fixture("xiyou_keyword_forward_populated.json"),
                "asin_keywords": load_fixture("xiyou_asin_keywords_reverse.json"),
            }
        )
        provider = XiYouProvider(
            transport,
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        config = configuration("xiyou")
        forward = provider.fetch(
            provider_request(
                "relationship.keyword_to_product",
                parameters={"keyword": "plastic spoons"},
            ),
            config,
        )
        reverse = provider.fetch(
            provider_request(
                "relationship.product_to_keyword",
                parameters={"asin": "B0G2VV4RBW"},
            ),
            config,
        )
        self.assertEqual(forward.capability.operation, "keyword_asin_analysis")
        self.assertEqual(reverse.capability.operation, "asin_keywords")
        self.assertNotEqual(
            forward.observations[0].direction,
            reverse.observations[0].direction,
        )

    def test_rate_limit_and_timeout_use_unified_error_codes(self) -> None:
        rate_limited = XiYouProvider(
            StubTransport(
                {
                    "asin_info": TransportResponse(
                        status_code=429,
                        payload={},
                        metadata={"retry_after_seconds": 2},
                    )
                }
            ),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        with self.assertRaises(ProviderConnectorError) as rate_error:
            rate_limited.fetch(provider_request(), configuration("xiyou"))
        self.assertEqual(rate_error.exception.code, ProviderErrorCode.RATE_LIMIT)
        self.assertEqual(rate_error.exception.details["retry_after_seconds"], 2)

        timed_out = XiYouProvider(
            StubTransport({"asin_info": TimeoutError("provider-specific detail")}),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        with self.assertRaises(ProviderConnectorError) as timeout_error:
            timed_out.fetch(provider_request(), configuration("xiyou"))
        self.assertEqual(timeout_error.exception.code, ProviderErrorCode.TIMEOUT)

    def test_authentication_and_schema_failures_use_unified_error_codes(self) -> None:
        unauthorized = XiYouProvider(
            StubTransport({"asin_info": TransportResponse(status_code=401, payload={})}),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        with self.assertRaises(ProviderConnectorError) as auth_error:
            unauthorized.fetch(provider_request(), configuration("xiyou"))
        self.assertEqual(auth_error.exception.code, ProviderErrorCode.AUTHENTICATION)

        malformed = XiYouProvider(
            StubTransport({"asin_info": {"status": 200, "data": []}}),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        with self.assertRaises(ProviderConnectorError) as schema_error:
            malformed.fetch(provider_request(), configuration("xiyou"))
        self.assertEqual(schema_error.exception.code, ProviderErrorCode.SCHEMA_MISMATCH)

    def test_unknown_and_unavailable_capabilities_cannot_execute(self) -> None:
        provider = XiYouProvider(StubTransport({}), environment={})
        for canonical_field, expected_status in (
            ("product.seller", CapabilityStatus.UNKNOWN),
            ("keyword.locale", CapabilityStatus.UNAVAILABLE),
        ):
            with self.subTest(canonical_field=canonical_field):
                with self.assertRaises(ProviderConnectorError) as caught:
                    provider.fetch(
                        provider_request(canonical_field),
                        configuration("xiyou"),
                    )
                self.assertEqual(caught.exception.code, ProviderErrorCode.FIELD_UNAVAILABLE)
                self.assertEqual(
                    caught.exception.details["capability_status"],
                    expected_status.value,
                )

    def test_retry_extension_is_bounded_by_configuration(self) -> None:
        transport = StubTransport(
            {
                "asin_info": [
                    TransportResponse(status_code=429, payload={}),
                    load_fixture("xiyou_asin_info.json"),
                ]
            }
        )
        provider = XiYouProvider(
            transport,
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
            retry_policy=RetryRetryableOnce(),
        )
        result = provider.fetch(
            provider_request(),
            configuration("xiyou", max_attempts=2),
        )
        self.assertEqual(result.status, ProviderFetchStatus.RETURNED)
        self.assertEqual(len(transport.requests), 2)

    def test_all_candidates_exhausted_has_auditable_attempt_summary(self) -> None:
        provider = XiYouProvider(
            StubTransport({"asin_info": TransportResponse(status_code=503, payload={})}),
            environment={"TEST_XIYOU_CREDENTIAL": TEST_CREDENTIAL},
        )
        resolver = ProviderResolver(build_registry(((provider, configuration("xiyou")),)))
        with self.assertRaises(ProviderConnectorError) as caught:
            resolver.resolve(provider_request())
        self.assertEqual(caught.exception.code, ProviderErrorCode.RESOLUTION_EXHAUSTED)
        self.assertEqual(caught.exception.details["attempts"][0]["provider_id"], "xiyou")


if __name__ == "__main__":
    unittest.main()
