from __future__ import annotations

from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import unittest

from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1, XiYouAdapterV0_1
from amazon_product_intelligence.connectors import ProviderConfig, SORFTIME_CAPABILITIES, XIYOU_CAPABILITIES
from amazon_product_intelligence.contracts import (
    CodeVersionScheme,
    NormalizationStatus,
    PresenceStatus,
    Provenance,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    SemanticStatus,
    SubjectRef,
    SubjectType,
    TransformationCodeVersion,
    TransformationProvenance,
    TransformationStatus,
    Unit,
    VersionStatus,
    product_id,
)
from amazon_product_intelligence.normalization import (
    CanonicalNormalizationPipeline,
    NormalizationContext,
    NormalizationInput,
    NormalizationIssueCode,
    NormalizationRule,
    NormalizerRegistry,
    RuleOutcome,
    build_default_registry,
)
from amazon_product_intelligence.provider_capabilities import CapabilityStatus


NORMALIZED_AT = "2026-08-19T08:00:00+08:00"
FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"


def context() -> NormalizationContext:
    return NormalizationContext(
        normalization_run_id="normalization:test:001",
        normalized_at=NORMALIZED_AT,
    )


def provenance(provider: str = "fake_a", source_field: str = "payload.value") -> Provenance:
    return Provenance(
        provider=provider,
        source_tool="fixture_operation",
        source_field=source_field,
        source_record_identity=f"{provider}:record:1",
        retrieved_at="2026-08-19T00:00:00Z",
        transformation=TransformationProvenance(
            collection_run_id=f"collection:{provider}:1",
            provider_schema_version=ProviderSchemaVersion(
                status=VersionStatus.UNKNOWN,
                value=None,
                source=ProviderSchemaSource.UNKNOWN,
            ),
            mapping_version=f"{provider}-mapping-v0.1",
            transformation_run_id=f"transform:{provider}:1",
            transformation_code_version=TransformationCodeVersion(
                status=VersionStatus.KNOWN,
                value="test-version",
                scheme=CodeVersionScheme.BUILD_VERSION,
            ),
            raw_evidence_reference=f"raw:{provider}:1",
            transformed_at="2026-08-19T00:00:01Z",
            transformation_status=TransformationStatus.SUCCESS,
        ),
        semantic_validation_status=SemanticStatus.CONFIRMED,
    )


def item(
    field: str,
    value=0,
    *,
    provider: str = "fake_a",
    presence: PresenceStatus = PresenceStatus.PRESENT,
    semantic: SemanticStatus = SemanticStatus.CONFIRMED,
    capability: CapabilityStatus = CapabilityStatus.AVAILABLE,
    unit: Unit | None = None,
    evidence_reference: str | None = None,
) -> NormalizationInput:
    absent = presence is not PresenceStatus.PRESENT
    raw = None if absent else value
    return NormalizationInput(
        canonical_field=field,
        raw_value=raw,
        mapped_value=raw,
        presence_status=presence,
        semantic_status=semantic,
        unit=unit,
        capability_status=capability,
        subject=SubjectRef(
            subject_type=SubjectType.PRODUCT,
            subject_id=product_id("US", "B0G2Q22W6D"),
            marketplace="US",
        ),
        provenance=provenance(provider),
        evidence_reference=evidence_reference or f"obs:{provider}:1",
    )


class NumericNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CanonicalNormalizationPipeline.with_defaults()

    def test_numeric_strings_commas_whitespace_and_zero(self) -> None:
        for value, expected in (("1,234", 1234), (" 123 ", 123), (0, 0), (Decimal("12.0"), 12)):
            with self.subTest(value=value):
                result = self.pipeline.normalize(item("metric.review_count", value), context())
                self.assertEqual(result.normalized_value, expected)
                self.assertEqual(result.normalization_status, NormalizationStatus.NORMALIZED)

    def test_negative_count_is_invalid_but_zero_is_valid(self) -> None:
        negative = self.pipeline.normalize(item("metric.review_count", -1), context())
        zero = self.pipeline.normalize(item("metric.review_count", 0), context())
        self.assertIsNone(negative.normalized_value)
        self.assertEqual(negative.normalization_status, NormalizationStatus.FAILED)
        self.assertEqual(negative.issues[0].issue_code, NormalizationIssueCode.OUT_OF_RANGE)
        self.assertEqual(zero.normalized_value, 0)

    def test_fractional_and_invalid_counts_fail(self) -> None:
        for value in ("12.5", "not-a-number", True):
            with self.subTest(value=value):
                result = self.pipeline.normalize(item("keyword.search_volume", value), context())
                self.assertEqual(result.normalization_status, NormalizationStatus.FAILED)
                self.assertIsNone(result.normalized_value)


class MoneyPercentageAndRankTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CanonicalNormalizationPipeline.with_defaults()
        self.usd = Unit(dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217")

    def test_money_supported_formats_use_decimal(self) -> None:
        for value in ("$19.99", "USD 19.99", "US$19.99", Decimal("19.99"), "1,234.50"):
            with self.subTest(value=value):
                result = self.pipeline.normalize(item("metric.price", value, unit=self.usd), context())
                self.assertEqual(result.normalized_value, Decimal("19.99") if value != "1,234.50" else Decimal("1234.50"))
                self.assertEqual(result.normalization_status, NormalizationStatus.NORMALIZED)

    def test_missing_currency_is_ambiguous_not_guessed(self) -> None:
        result = self.pipeline.normalize(item("metric.price", "19.99"), context())
        self.assertEqual(result.normalized_value, Decimal("19.99"))
        self.assertEqual(result.normalization_status, NormalizationStatus.AMBIGUOUS)
        self.assertIsNone(result.unit)
        self.assertEqual(result.issues[0].issue_code, NormalizationIssueCode.AMBIGUOUS_CURRENCY)

    def test_explicit_usd_can_establish_unit_and_conflict_is_visible(self) -> None:
        explicit = self.pipeline.normalize(item("metric.price", "USD 19.99"), context())
        eur = Unit(dimension="CURRENCY", unit_code="EUR", unit_system="ISO_4217")
        conflict = self.pipeline.normalize(item("metric.price", "USD 19.99", unit=eur), context())
        self.assertEqual(explicit.unit.unit_code, "USD")
        self.assertEqual(conflict.normalization_status, NormalizationStatus.AMBIGUOUS)
        self.assertEqual(conflict.issues[0].issue_code, NormalizationIssueCode.CURRENCY_CONFLICT)

    def test_invalid_or_negative_money_fails(self) -> None:
        for value in ("free", -1):
            with self.subTest(value=value):
                result = self.pipeline.normalize(item("keyword.cpc", value, unit=self.usd), context())
                self.assertEqual(result.normalization_status, NormalizationStatus.FAILED)

    def test_money_rejects_incompatible_unit_dimension(self) -> None:
        count_unit = Unit(dimension="COUNT", unit_code="units", unit_system="DOMAIN")
        result = self.pipeline.normalize(item("metric.price", "19.99", unit=count_unit), context())
        self.assertEqual(result.normalization_status, NormalizationStatus.FAILED)
        self.assertEqual(result.issues[0].issue_code, NormalizationIssueCode.UNSUPPORTED_UNIT)

    def test_percentage_is_field_aware_and_never_globally_divides(self) -> None:
        explicit = self.pipeline.normalize(item("metric.traffic_ratio", "15%"), context())
        ratio = self.pipeline.normalize(item("metric.traffic_ratio", Decimal("0.15")), context())
        bare = self.pipeline.normalize(item("metric.traffic_ratio", 15), context())
        self.assertEqual(explicit.normalized_value, Decimal("0.15"))
        self.assertEqual(ratio.normalized_value, Decimal("0.15"))
        self.assertEqual(bare.normalization_status, NormalizationStatus.FAILED)
        self.assertIsNone(bare.normalized_value)

    def test_rank_formats_and_invalid_values(self) -> None:
        for value, expected in (("#1", 1), ("#1,234", 1234), ("1", 1)):
            with self.subTest(value=value):
                self.assertEqual(self.pipeline.normalize(item("metric.bsr", value), context()).normalized_value, expected)
        for value in (0, "-", "N/A", -1):
            with self.subTest(value=value):
                self.assertEqual(
                    self.pipeline.normalize(item("metric.bsr", value), context()).normalization_status,
                    NormalizationStatus.FAILED,
                )

    def test_rating_has_only_contractual_range_not_arbitrary_outlier_cap(self) -> None:
        valid = self.pipeline.normalize(item("metric.rating", "4.8"), context())
        invalid = self.pipeline.normalize(item("metric.rating", "5.1"), context())
        self.assertEqual(valid.normalized_value, Decimal("4.8"))
        self.assertEqual(invalid.issues[0].issue_code, NormalizationIssueCode.OUT_OF_RANGE)


class TextIdentityBooleanAndTimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CanonicalNormalizationPipeline.with_defaults()

    def test_text_is_conservative_unicode_normalized_and_case_preserving(self) -> None:
        result = self.pipeline.normalize(item("product.brand", "  A\u0301pple   Pro\tSeries  "), context())
        self.assertEqual(result.normalized_value, "Ápple Pro Series")
        self.assertNotEqual(result.normalized_value, result.normalized_value.casefold())
        self.assertIn(NormalizationIssueCode.CONTROL_CHARACTER_REMOVED, {issue.issue_code for issue in result.issues})

    def test_empty_text_is_invalid(self) -> None:
        result = self.pipeline.normalize(item("product.title", "  \t  "), context())
        self.assertEqual(result.normalization_status, NormalizationStatus.FAILED)
        self.assertEqual(result.issues[0].issue_code, NormalizationIssueCode.EMPTY_VALUE)

    def test_asin_trim_uppercase_validation_and_missing(self) -> None:
        valid = self.pipeline.normalize(item("product.asin", " b0g2q22w6d "), context())
        invalid = self.pipeline.normalize(item("product.asin", "invalid"), context())
        missing = self.pipeline.normalize(item("product.asin", presence=PresenceStatus.MISSING), context())
        self.assertEqual(valid.normalized_value, "B0G2Q22W6D")
        self.assertEqual(invalid.issues[0].issue_code, NormalizationIssueCode.INVALID_IDENTIFIER)
        self.assertIsNone(missing.normalized_value)

    def test_keyword_spacing_unicode_casefold_and_punctuation_preservation(self) -> None:
        result = self.pipeline.normalize(item("keyword.text", "  Café   MUG-Pro  "), context())
        self.assertEqual(result.raw_value, "  Café   MUG-Pro  ")
        self.assertEqual(result.normalized_value, "café mug-pro")

    def test_boolean_only_accepts_explicit_vocabulary(self) -> None:
        cases = ((True, True), (False, False), (1, True), (0, False), ("yes", True), ("no", False))
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIs(
                    self.pipeline.normalize(item("product.a_plus", value), context()).normalized_value,
                    expected,
                )
        self.assertEqual(
            self.pipeline.normalize(item("product.a_plus", "unknown"), context()).normalization_status,
            NormalizationStatus.FAILED,
        )

    def test_dates_and_timezone_aware_datetimes(self) -> None:
        date_result = self.pipeline.normalize(item("product.first_available_date", "2026-08-19"), context())
        aware = self.pipeline.normalize(item("observation.observed_at", "2026-08-19T10:00:00+08:00"), context())
        self.assertEqual(date_result.normalized_value, date(2026, 8, 19))
        self.assertEqual(aware.normalized_value.utcoffset().total_seconds(), 28800)

    def test_naive_datetime_is_not_silently_assumed_utc(self) -> None:
        result = self.pipeline.normalize(item("observation.observed_at", "2026-08-19T10:00:00"), context())
        self.assertEqual(result.normalization_status, NormalizationStatus.AMBIGUOUS)
        self.assertIsNone(result.normalized_value.tzinfo)
        self.assertEqual(result.issues[0].issue_code, NormalizationIssueCode.TIMEZONE_MISSING)

    def test_invalid_datetime_fails(self) -> None:
        result = self.pipeline.normalize(item("observation.observed_at", "not-a-date"), context())
        self.assertEqual(result.normalization_status, NormalizationStatus.FAILED)


class MissingCollectionsAndCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CanonicalNormalizationPipeline.with_defaults()

    def test_missing_null_unknown_empty_query_and_not_applicable_remain_distinct(self) -> None:
        statuses = (
            PresenceStatus.MISSING,
            PresenceStatus.EXPLICIT_NULL,
            PresenceStatus.UNKNOWN,
            PresenceStatus.QUERY_RETURNED_EMPTY,
            PresenceStatus.NOT_APPLICABLE,
        )
        results = [self.pipeline.normalize(item("metric.review_count", presence=status), context()) for status in statuses]
        self.assertEqual([result.presence_status for result in results], list(statuses))
        self.assertTrue(all(result.normalized_value is None for result in results))
        self.assertEqual(results[-1].normalization_status, NormalizationStatus.NOT_APPLICABLE)

    def test_none_cannot_be_present_and_is_never_converted_to_zero(self) -> None:
        with self.assertRaises(ValueError):
            item("metric.review_count", None)
        missing = self.pipeline.normalize(item("metric.review_count", presence=PresenceStatus.MISSING), context())
        self.assertIsNone(missing.normalized_value)
        self.assertNotEqual(missing.normalized_value, 0)

    def test_unknown_boolean_does_not_become_false(self) -> None:
        result = self.pipeline.normalize(item("product.a_plus", presence=PresenceStatus.UNKNOWN), context())
        self.assertIsNone(result.normalized_value)
        self.assertIsNot(result.normalized_value, False)

    def test_empty_collection_is_distinct_from_missing_collection(self) -> None:
        empty = self.pipeline.normalize(item("product.child_asins", []), context())
        missing = self.pipeline.normalize(item("product.child_asins", presence=PresenceStatus.MISSING), context())
        self.assertEqual(empty.normalized_value, ())
        self.assertIsNone(missing.normalized_value)
        self.assertEqual(empty.presence_status, PresenceStatus.PRESENT)
        self.assertEqual(missing.presence_status, PresenceStatus.MISSING)

    def test_collection_deduplication_key_is_validated_asin_and_order_is_deterministic(self) -> None:
        result = self.pipeline.normalize(
            item("product.child_asins", ["B0G2Q22W6E", "b0g2q22w6d", "B0G2Q22W6E"]),
            context(),
        )
        self.assertEqual(result.normalized_value, ("B0G2Q22W6D", "B0G2Q22W6E"))
        self.assertEqual(result.issues[0].issue_code, NormalizationIssueCode.DUPLICATE_MEMBER)

    def test_invalid_collection_members_leave_partial_clean_value_and_raw_evidence(self) -> None:
        source = ["B0G2Q22W6D", "bad"]
        result = self.pipeline.normalize(item("product.child_asins", source), context())
        self.assertEqual(result.raw_value, tuple(source))
        self.assertEqual(result.normalized_value, ("B0G2Q22W6D",))
        self.assertEqual(result.normalization_status, NormalizationStatus.AMBIGUOUS)
        self.assertEqual(result.issues[0].issue_code, NormalizationIssueCode.INVALID_MEMBER)

    def test_partial_capability_is_preserved_after_successful_cleaning(self) -> None:
        result = self.pipeline.normalize(
            item("metric.price", "USD 19.99", capability=CapabilityStatus.PARTIAL),
            context(),
        )
        self.assertEqual(result.normalized_value, Decimal("19.99"))
        self.assertEqual(result.capability_status, CapabilityStatus.PARTIAL)

    def test_unknown_and_unavailable_are_never_promoted(self) -> None:
        for status, code in (
            (CapabilityStatus.UNKNOWN, NormalizationIssueCode.CAPABILITY_UNKNOWN),
            (CapabilityStatus.UNAVAILABLE, NormalizationIssueCode.CAPABILITY_UNAVAILABLE),
        ):
            with self.subTest(status=status):
                result = self.pipeline.normalize(item("product.seller", "seller", capability=status), context())
                self.assertIsNone(result.normalized_value)
                self.assertEqual(result.capability_status, status)
                self.assertEqual(result.normalization_status, NormalizationStatus.NOT_ATTEMPTED)
                self.assertEqual(result.issues[0].issue_code, code)

    def test_capability_vocabulary_has_no_calculated(self) -> None:
        self.assertNotIn("CALCULATED", {status.value for status in CapabilityStatus})

    def test_p0_capability_coverage_audit_matches_documented_boundary(self) -> None:
        capabilities = XIYOU_CAPABILITIES + SORFTIME_CAPABILITIES
        available_or_partial = {
            capability.canonical_field
            for capability in capabilities
            if capability.capability_status in {CapabilityStatus.AVAILABLE, CapabilityStatus.PARTIAL}
        }
        p0 = available_or_partial - {"review.raw"}
        supported = p0 & set(self.pipeline.registry.fields)
        not_required = p0 - supported
        blocked = {
            capability.canonical_field
            for capability in capabilities
            if capability.capability_status in {CapabilityStatus.UNKNOWN, CapabilityStatus.UNAVAILABLE}
        }
        self.assertEqual(len(available_or_partial), 25)
        self.assertEqual(len(p0), 24)
        self.assertEqual(len(supported), 20)
        self.assertEqual(
            not_required,
            {
                "metric.bsr_context",
                "product.attributes",
                "product.marketplace",
                "product.variation",
            },
        )
        self.assertEqual(
            blocked,
            {
                "keyword.estimate_method_status",
                "keyword.locale",
                "product.seller",
                "workflow.manual_review_status",
            },
        )


class LineageDeterminismAndExtensibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipeline = CanonicalNormalizationPipeline.with_defaults()

    def test_raw_normalized_provider_source_rule_and_versions_are_traceable(self) -> None:
        result = self.pipeline.normalize(
            item("metric.price", "$19.99", provider="fake_a", unit=Unit(dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217")),
            context(),
        )
        self.assertEqual(result.raw_value, "$19.99")
        self.assertEqual(result.normalized_value, Decimal("19.99"))
        self.assertEqual(result.provenance.provider, "fake_a")
        self.assertEqual(result.provenance.source_field, "payload.value")
        self.assertEqual(result.application.rule_id, "canonical.money")
        self.assertEqual(result.application.rule_version, "0.1")
        self.assertEqual(result.application.normalization_version, "canonical-normalization-v0.1")
        self.assertEqual(result.application.input_evidence_reference, "obs:fake_a:1")

    def test_quality_issue_reuses_canonical_model_and_mapping_lineage(self) -> None:
        result = self.pipeline.normalize(item("metric.review_count", "bad"), context())
        issue = result.issues[0]
        self.assertEqual(issue.dimension, "metric.review_count")
        self.assertEqual(issue.collection_run_id, "collection:fake_a:1")
        self.assertEqual(issue.transformation_run_id, "transform:fake_a:1")
        self.assertEqual(issue.mapping_version, "fake_a-mapping-v0.1")
        self.assertEqual(issue.source_references, ("obs:fake_a:1",))

    def test_same_input_context_is_deterministic(self) -> None:
        source = item("metric.review_count", "1,234")
        first = self.pipeline.normalize(source, context()).to_dict()
        second = self.pipeline.normalize(source, context()).to_dict()
        self.assertEqual(first, second)

    def test_core_normalizers_are_idempotent(self) -> None:
        cases = (
            ("metric.review_count", " 1,234 "),
            ("metric.price", "USD 19.99"),
            ("metric.traffic_ratio", "15%"),
            ("metric.bsr", "#1,234"),
            ("product.asin", " b0g2q22w6d "),
            ("keyword.text", "  Café   MUG "),
        )
        for field, value in cases:
            with self.subTest(field=field):
                first = self.pipeline.normalize(item(field, value), context())
                second = self.pipeline.normalize(item(field, first.normalized_value, unit=first.unit), context())
                self.assertEqual(first.normalized_value, second.normalized_value)
                self.assertEqual(first.normalization_status, second.normalization_status)

    def test_provider_neutrality_uses_same_rule_for_same_canonical_field(self) -> None:
        usd = Unit(dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217")
        a = self.pipeline.normalize(item("metric.price", "$19.99", provider="fake_a", unit=usd), context())
        b = self.pipeline.normalize(item("metric.price", "$19.99", provider="fake_b", unit=usd), context())
        self.assertEqual(a.normalized_value, b.normalized_value)
        self.assertEqual(a.application.rule_id, b.application.rule_id)
        self.assertEqual(a.application.transformations, b.application.transformations)
        self.assertNotEqual(a.provenance.provider, b.provenance.provider)

    def test_provider_replacement_enable_disable_does_not_change_cleaning(self) -> None:
        configurations = (
            (ProviderConfig(provider_id="xiyou", enabled=False, priority=1, credential_env=None), "sorftime"),
            (ProviderConfig(provider_id="sorftime", enabled=False, priority=1, credential_env=None), "xiyou"),
        )
        results = []
        for disabled, active in configurations:
            self.assertFalse(disabled.enabled)
            results.append(self.pipeline.normalize(item("metric.rating", "4.5", provider=active), context()))
        self.assertEqual(results[0].normalized_value, results[1].normalized_value)
        self.assertEqual(results[0].application.rule_id, results[1].application.rule_id)

    def test_real_adapter_observations_enter_one_provider_neutral_contract(self) -> None:
        configurations = (
            ("xiyou", "asin_info", "get_asin_info", "xiyou_asin_info.json", XiYouAdapterV0_1()),
            ("sorftime", "product_detail", "product_detail", "sorftime_product_detail.json", SorftimeAdapterV0_1()),
        )
        results = []
        for provider, payload_kind, source_tool, filename, adapter in configurations:
            payload = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
            adapted = adapter.adapt(
                payload,
                AdaptationContext(
                    provider=provider,
                    payload_kind=payload_kind,
                    source_tool=source_tool,
                    marketplace="US",
                    locale="en-us",
                    retrieved_at="2026-08-14T09:00:00Z",
                    transformed_at="2026-08-14T09:01:00Z",
                    collection_run_id=f"collection:{provider}:normalization-integration",
                    sanitized_request={"asin": "B0G2VV4RBW"},
                    currency="USD",
                ),
            )
            observation = next(item for item in adapted.bundle.observations if getattr(item, "metric", None) == "price")
            normalized_input = NormalizationInput.from_observation(
                observation,
                canonical_field="metric.price",
                capability_status=CapabilityStatus.AVAILABLE,
            )
            results.append(self.pipeline.normalize(normalized_input, context()))
        self.assertEqual([result.normalized_value for result in results], [Decimal("18.99"), Decimal("18.99")])
        self.assertEqual({result.application.rule_id for result in results}, {"canonical.money"})
        self.assertEqual([result.provenance.provider for result in results], ["xiyou", "sorftime"])

    def test_future_provider_uses_existing_rule_without_core_change(self) -> None:
        result = self.pipeline.normalize(item("metric.rating", "4.2", provider="fake_provider_c"), context())
        self.assertEqual(result.normalized_value, Decimal("4.2"))
        self.assertEqual(result.provenance.provider, "fake_provider_c")

    def test_registry_extends_future_canonical_field_without_pipeline_change(self) -> None:
        registry = build_default_registry()
        registry.register(
            NormalizationRule(
                rule_id="future.identity",
                rule_version="test",
                canonical_fields=("future.identifier",),
                normalize=lambda value, unit: RuleOutcome(
                    normalized_value=str(value).strip(),
                    normalization_status=NormalizationStatus.NORMALIZED,
                    semantic_status=SemanticStatus.CONFIRMED,
                    unit=unit,
                    transformations=("trim",),
                ),
            )
        )
        result = CanonicalNormalizationPipeline(registry).normalize(item("future.identifier", " value "), context())
        self.assertEqual(result.normalized_value, "value")

    def test_failure_isolation_preserves_sibling_fields(self) -> None:
        results = self.pipeline.normalize_many(
            (
                item("product.asin", "B0G2Q22W6D", evidence_reference="obs:1"),
                item("metric.review_count", "bad", evidence_reference="obs:2"),
                item("product.title", " Valid title ", evidence_reference="obs:3"),
            ),
            context(),
        )
        self.assertEqual(results[0].normalized_value, "B0G2Q22W6D")
        self.assertEqual(results[1].normalization_status, NormalizationStatus.FAILED)
        self.assertEqual(results[2].normalized_value, "Valid title")

    def test_extension_rule_exception_isolated_and_credential_free(self) -> None:
        registry = NormalizerRegistry()

        def broken(value, unit):
            raise RuntimeError("fixture failure without sensitive data")

        registry.register(
            NormalizationRule(
                rule_id="test.broken",
                rule_version="test",
                canonical_fields=("test.broken",),
                normalize=broken,
            )
        )
        result = CanonicalNormalizationPipeline(registry).normalize(item("test.broken", "value"), context())
        self.assertEqual(result.normalization_status, NormalizationStatus.FAILED)
        self.assertEqual(result.issues[0].issue_code, NormalizationIssueCode.NORMALIZATION_FAILED)
        self.assertNotIn("value", result.issues[0].message)

    def test_conflicting_provider_candidates_are_cleaned_independently_not_resolved(self) -> None:
        usd = Unit(dimension="CURRENCY", unit_code="USD", unit_system="ISO_4217")
        results = self.pipeline.normalize_many(
            (
                item("metric.price", "$19.99", provider="xiyou", unit=usd, evidence_reference="obs:x"),
                item("metric.price", "20.49", provider="sorftime", unit=usd, evidence_reference="obs:s"),
            ),
            context(),
        )
        self.assertEqual([result.normalized_value for result in results], [Decimal("19.99"), Decimal("20.49")])
        self.assertEqual([result.provenance.provider for result in results], ["xiyou", "sorftime"])


if __name__ == "__main__":
    unittest.main()
