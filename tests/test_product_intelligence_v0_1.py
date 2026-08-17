from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

import amazon_product_intelligence.product_intelligence as product_intelligence
from amazon_product_intelligence.adapters import (
    AdaptationContext,
    SorftimeAdapterV0_1,
    XiYouAdapterV0_1,
)
from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    EvidenceType,
    NormalizationStatus,
    ObservationKind,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    ProductIdentity,
    Scope,
    ScopeStatus,
    ScopeType,
    SemanticStatus,
    SubjectRef,
    SubjectType,
    TimeWindow,
    ValueEnvelope,
    ValueType,
    canonical_json,
    deterministic_id,
    product_id,
)
from amazon_product_intelligence.product_intelligence import (
    FactCandidateState,
    ProductIdentityCollisionError,
    ProductIntelligenceBuilderV0_1,
    ProductIntelligenceRequest,
    ProductIntelligenceSnapshotV0_1,
    ProductIntelligenceValidationError,
    ProductScope,
    ProductSubjectNotFoundError,
    ProductTopologyError,
    SnapshotSerializationError,
)


SYNTHETIC_CANONICAL_TEST_INPUT = "SYNTHETIC_CANONICAL_TEST_INPUT"
FIXTURES = Path(__file__).parent / "fixtures" / "provider_adapters" / "v0_1"
RETRIEVED_AT = "2026-08-14T09:00:00Z"
TRANSFORMED_AT = "2026-08-14T09:01:00Z"
TARGET_ASIN = "B0G2VV4RBW"
PARENT_ASIN = "B0G2VVX3ML"

CASES = {
    ("xiyou", "asin_info"): ("xiyou_asin_info.json", "get_asin_info"),
    ("xiyou", "asin_variations"): ("xiyou_asin_variations.json", "get_asin_variations"),
    ("xiyou", "asin_orders_last_30_days"): ("xiyou_asin_orders.json", "get_asin_orders_last_30_days"),
    ("xiyou", "asin_bsr_trends"): ("xiyou_asin_bsr.json", "get_asin_bsr_trends"),
    ("xiyou", "keyword_info"): ("xiyou_keyword_info.json", "get_keyword_info"),
    ("xiyou", "keyword_asin_analysis"): ("xiyou_keyword_forward_populated.json", "get_keyword_asin_analysis"),
    ("xiyou", "asin_keywords"): ("xiyou_asin_keywords_reverse.json", "get_asin_keywords"),
    ("sorftime", "product_detail"): ("sorftime_product_detail.json", "product_detail"),
    ("sorftime", "product_variations"): ("sorftime_product_variations.json", "product_variations"),
    ("sorftime", "product_reviews"): ("sorftime_product_reviews.json", "product_reviews"),
}


def target(asin: str = TARGET_ASIN, marketplace: str = "US") -> ProductIdentity:
    return ProductIdentity(
        product_id=product_id(marketplace, asin),
        marketplace=marketplace,
        asin=asin,
        parent_asin=PARENT_ASIN if asin == TARGET_ASIN and marketplace == "US" else None,
        identity_status="CONFIRMED",
    )


def adapt(provider: str, kind: str) -> CanonicalEvidenceBundle:
    fixture, source_tool = CASES[(provider, kind)]
    payload = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
    request: dict[str, object] = {}
    if kind in {"product_detail", "product_variations", "product_reviews", "asin_keywords"}:
        request["asin"] = TARGET_ASIN
    if kind == "keyword_asin_analysis":
        request["keyword"] = "plastic spoons"
    context = AdaptationContext(
        provider=provider,
        payload_kind=kind,
        source_tool=source_tool,
        marketplace="US",
        locale="en-us",
        retrieved_at=RETRIEVED_AT,
        transformed_at=TRANSFORMED_AT,
        collection_run_id=f"collection:{provider}:{kind}:product-intelligence-test",
        sanitized_request=request,
        currency="USD",
    )
    adapter = XiYouAdapterV0_1() if provider == "xiyou" else SorftimeAdapterV0_1()
    result = adapter.adapt(payload, context)
    result.bundle.validate()
    return result.bundle


def build(*bundles: CanonicalEvidenceBundle, scope: ProductScope = ProductScope.EXACT_PRODUCT, identity=None):
    return ProductIntelligenceBuilderV0_1().build(ProductIntelligenceRequest(
        target_product_identity=identity or target(),
        scope=scope,
        canonical_bundles=bundles,
    ))


def merge_bundles(*bundles: CanonicalEvidenceBundle) -> CanonicalEvidenceBundle:
    merged = CanonicalEvidenceBundle(
        transformation_runs=tuple(item for bundle in bundles for item in bundle.transformation_runs),
        observations=tuple(item for bundle in bundles for item in bundle.observations),
        conflicts=tuple(item for bundle in bundles for item in bundle.conflicts),
        resolutions=tuple(item for bundle in bundles for item in bundle.resolutions),
        quality_issues=tuple(item for bundle in bundles for item in bundle.quality_issues),
        raw_evidence_references=tuple(item for bundle in bundles for item in bundle.raw_evidence_references),
    )
    return merged.validate()


def replace_observations(
    bundle: CanonicalEvidenceBundle,
    replacements: dict[str, object],
    additions: tuple[object, ...] = (),
) -> CanonicalEvidenceBundle:
    """Create SYNTHETIC_CANONICAL_TEST_INPUT; never captured Provider evidence."""

    observations = tuple(replacements.get(item.observation_id, item) for item in bundle.observations) + additions
    old_to_new = {old: item.observation_id for old, item in replacements.items()}
    added_ids = tuple(item.observation_id for item in additions)
    runs = tuple(replace(
        run,
        output_observation_ids=tuple(old_to_new.get(item, item) for item in run.output_observation_ids) + added_ids,
    ) for run in bundle.transformation_runs)
    return replace(bundle, observations=observations, transformation_runs=runs).validate()


def relation_rows(bundle: CanonicalEvidenceBundle) -> list[ProductFactObservation]:
    return [
        item for item in bundle.observations
        if isinstance(item, ProductFactObservation)
        and item.dimension in {"child_product_relationship", "parent_product_relationship"}
    ]


def refresh_snapshot_id(payload: dict[str, object]) -> None:
    """Reproduce model canonical ordering after a synthetic serialized mutation."""

    sequence_keys = {
        "included_product_identities": lambda item: item["product_id"],
        "product_fact_evidence_sets": lambda item: item["fact_set_id"],
        "product_metric_series": lambda item: item["metric_series_id"],
        "quality_issue_references": lambda item: item["issue_id"],
        "out_of_scope_observation_references": lambda item: item["observation_id"],
        "lineage_index": canonical_json,
        "diagnostics": lambda item: item["diagnostic_id"],
    }
    for name, key in sequence_keys.items():
        payload[name] = sorted(payload[name], key=key)
    payload["source_bundle_fingerprints"] = sorted(payload["source_bundle_fingerprints"])
    topology = payload["variation_topology"]
    topology["nodes"] = sorted(topology["nodes"], key=lambda item: item["product_id"])
    topology["edges"] = sorted(topology["edges"], key=lambda item: item["variation_edge_id"])
    topology["diagnostic_ids"] = sorted(set(topology["diagnostic_ids"]))
    payload["snapshot_id"] = deterministic_id(
        "snapshot", {key: value for key, value in payload.items() if key != "snapshot_id"}
    )


class PublicApiAndRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.detail = adapt("sorftime", "product_detail")

    def test_public_api_is_explicit_and_has_no_private_or_import_leaks(self) -> None:
        expected = {
            "PRODUCT_INTELLIGENCE_RULESET_VERSION", "ProductScope", "FactCandidateState",
            "ProductIntelligenceRequest", "ProductIntelligenceSnapshotV0_1",
            "ProductIntelligenceBuilderV0_1", "ProductIntelligenceError",
            "ProductIntelligenceValidationError", "ProductSubjectNotFoundError",
            "ProductTopologyError", "ProductIdentityCollisionError", "SnapshotSerializationError",
            "EvidenceCandidate", "ProductFactEvidenceSet", "ProductMetricSeries",
            "VariationTopology", "VariationEdge", "ReviewEvidenceSummary",
            "EvidenceCoverageSummary", "LineageReference", "QualityIssueReference",
            "OutOfScopeObservationReference", "ProductIntelligenceDiagnostic",
        }
        self.assertEqual(expected, set(product_intelligence.__all__))
        self.assertFalse(any(name.startswith("_") for name in product_intelligence.__all__))
        self.assertNotIn("dataclass", product_intelligence.__all__)
        self.assertNotIn("CanonicalEvidenceBundle", product_intelligence.__all__)

    def test_source_boundary_does_not_import_adapters(self) -> None:
        source_root = Path(product_intelligence.__file__).parent
        for path in source_root.glob("*.py"):
            self.assertNotIn("amazon_product_intelligence.adapters", path.read_text(encoding="utf-8"))

    def test_import_has_no_build_side_effect(self) -> None:
        self.assertEqual(product_intelligence.PRODUCT_INTELLIGENCE_RULESET_VERSION, "product-intelligence-v0.1")

    def test_request_rejects_empty_wrong_bundle_target_and_scope(self) -> None:
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceRequest(target_product_identity=target(), scope=ProductScope.EXACT_PRODUCT, canonical_bundles=())
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceRequest(target_product_identity=target(), scope=ProductScope.EXACT_PRODUCT, canonical_bundles=(object(),))
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceRequest(target_product_identity="not-a-product", scope=ProductScope.EXACT_PRODUCT, canonical_bundles=(self.detail,))
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceRequest(target_product_identity=target(), scope="UNKNOWN", canonical_bundles=(self.detail,))

    def test_request_rejects_duplicate_bundle_fingerprint_even_when_reordered(self) -> None:
        reordered = replace(
            self.detail,
            observations=tuple(reversed(self.detail.observations)),
            quality_issues=tuple(reversed(self.detail.quality_issues)),
        )
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceRequest(
                target_product_identity=target(), scope=ProductScope.EXACT_PRODUCT,
                canonical_bundles=(self.detail, reordered),
            )

    def test_request_is_deeply_detached_and_bundle_order_independent(self) -> None:
        reviews = adapt("sorftime", "product_reviews")
        caller = [self.detail, reviews]
        request = ProductIntelligenceRequest(
            target_product_identity=target(), scope=ProductScope.EXACT_PRODUCT, canonical_bundles=caller
        )
        before = tuple(caller)
        caller.clear()
        self.assertEqual(len(request.canonical_bundles), 2)
        self.assertEqual(before, (self.detail, reviews))
        first = build(self.detail, reviews)
        second = build(reviews, self.detail)
        self.assertEqual(first.to_dict(), second.to_dict())


class ExactScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.detail = adapt("sorftime", "product_detail")
        cls.variations = adapt("sorftime", "product_variations")
        cls.reviews = adapt("sorftime", "product_reviews")
        cls.xiyou_relations = adapt("xiyou", "asin_variations")
        cls.snapshot = build(cls.detail, cls.variations, cls.reviews, cls.xiyou_relations)

    def test_target_facts_metrics_and_reviews_are_included(self) -> None:
        self.assertTrue(self.snapshot.product_fact_evidence_sets)
        self.assertTrue(self.snapshot.product_metric_series)
        self.assertEqual(self.snapshot.review_evidence_summary.review_observation_count, 1)
        self.assertEqual(
            {item.subject_product_identity.product_id for item in self.snapshot.product_fact_evidence_sets},
            {target().product_id},
        )

    def test_unrelated_child_evidence_is_explicitly_excluded(self) -> None:
        excluded = self.snapshot.out_of_scope_observation_references
        self.assertTrue(any(item.reason_code == "UNRELATED_PRODUCT_EVIDENCE_EXCLUDED" for item in excluded))
        self.assertTrue(any(item.code == "UNRELATED_PRODUCT_EVIDENCE_EXCLUDED" for item in self.snapshot.diagnostics))

    def test_exact_scope_never_expands_fact_scope_through_direct_relation(self) -> None:
        self.assertEqual(self.snapshot.included_product_identities, (target(),))
        edge = next(
            item for item in self.snapshot.variation_topology.edges
            if item.parent_product_identity.asin == PARENT_ASIN and item.child_product_identity.asin == TARGET_ASIN
        )
        self.assertEqual(edge.child_product_identity.asin, TARGET_ASIN)
        self.assertFalse(any(
            item.subject_product_identity.asin == PARENT_ASIN
            for item in self.snapshot.product_fact_evidence_sets
        ))

    def test_same_title_or_brand_does_not_define_membership(self) -> None:
        dimensions = {item.dimension for item in self.snapshot.product_fact_evidence_sets}
        self.assertIn("title", dimensions)
        self.assertIn("brand", dimensions)
        self.assertEqual(len(self.snapshot.included_product_identities), 1)

    def test_different_marketplace_does_not_match_target(self) -> None:
        with self.assertRaises(ProductSubjectNotFoundError):
            build(self.detail, identity=target(marketplace="CA"))


class CorrectedVariationTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.xiyou = adapt("xiyou", "asin_variations")
        cls.detail = adapt("sorftime", "product_detail")

    def test_two_directions_normalize_to_one_multi_source_edge(self) -> None:
        snapshot = build(
            self.xiyou, self.detail, scope=ProductScope.EXPLICIT_VARIATION_FAMILY
        )
        edge = next(item for item in snapshot.variation_topology.edges if (
            item.parent_product_identity.asin, item.child_product_identity.asin
        ) == (PARENT_ASIN, TARGET_ASIN))
        self.assertEqual(set(edge.evidence_dimensions), {"child_product_relationship", "parent_product_relationship"})
        self.assertEqual(edge.evidence_count, 2)
        self.assertEqual(set(edge.providers), {"xiyou", "sorftime"})
        self.assertEqual(len(edge.lineage_references), 2)
        self.assertTrue(any(item.code == "MULTI_SOURCE_VARIATION_EDGE" for item in snapshot.diagnostics))

    def test_parent_and_child_targets_expand_the_same_multi_child_family(self) -> None:
        parent_snapshot = build(
            self.xiyou, self.detail, scope=ProductScope.EXPLICIT_VARIATION_FAMILY,
            identity=target(PARENT_ASIN),
        )
        child_snapshot = build(
            self.xiyou, self.detail, scope=ProductScope.EXPLICIT_VARIATION_FAMILY
        )
        expected = {PARENT_ASIN, TARGET_ASIN, "B0G2VZSWRN"}
        self.assertEqual({item.asin for item in parent_snapshot.included_product_identities}, expected)
        self.assertEqual({item.asin for item in child_snapshot.included_product_identities}, expected)

    def test_sorftime_variation_rows_do_not_infer_relationship(self) -> None:
        variation_rows = adapt("sorftime", "product_variations")
        snapshot = build(variation_rows, scope=ProductScope.EXPLICIT_VARIATION_FAMILY)
        self.assertEqual(snapshot.variation_topology.edges, ())
        self.assertEqual(snapshot.included_product_identities, (target(),))
        self.assertTrue(any(item.code == "NO_CONFIRMED_VARIATION_RELATIONSHIP" for item in snapshot.diagnostics))

    def test_target_connected_confirmed_self_loop_is_rejected(self) -> None:
        row = relation_rows(self.xiyou)[0]
        value = replace(row.value, raw_value=PARENT_ASIN, normalized_value=PARENT_ASIN)
        mutated = replace_observations(self.xiyou, {row.observation_id: replace(row, value=value)})
        with self.assertRaises(ProductTopologyError):
            build(mutated, scope=ProductScope.EXPLICIT_VARIATION_FAMILY, identity=target(PARENT_ASIN))

    def test_target_connected_cycle_is_rejected(self) -> None:
        first, second = relation_rows(self.xiyou)
        reverse_subject = SubjectRef(
            subject_type=SubjectType.PRODUCT, subject_id=product_id("US", TARGET_ASIN), marketplace="US"
        )
        reverse_value = replace(second.value, raw_value=PARENT_ASIN, normalized_value=PARENT_ASIN)
        reverse = replace(second, subject=reverse_subject, value=reverse_value)
        mutated = replace_observations(self.xiyou, {second.observation_id: reverse})
        with self.assertRaises(ProductTopologyError):
            build(mutated, scope=ProductScope.EXPLICIT_VARIATION_FAMILY, identity=target(PARENT_ASIN))

    def test_target_connected_multiple_parent_ambiguity_is_rejected(self) -> None:
        first, second = relation_rows(self.xiyou)
        other_parent = "B0G2VQJVW2"
        subject = SubjectRef(
            subject_type=SubjectType.PRODUCT, subject_id=product_id("US", other_parent), marketplace="US"
        )
        value = replace(second.value, raw_value=TARGET_ASIN, normalized_value=TARGET_ASIN)
        competing = replace(second, subject=subject, value=value)
        mutated = replace_observations(self.xiyou, {second.observation_id: competing})
        with self.assertRaises(ProductTopologyError):
            build(mutated, scope=ProductScope.EXPLICIT_VARIATION_FAMILY)

    def test_target_connected_marketplace_mismatch_is_rejected(self) -> None:
        row = relation_rows(self.xiyou)[0]
        subject = replace(row.subject, marketplace="CA")
        mutated = replace_observations(self.xiyou, {row.observation_id: replace(row, subject=subject)})
        with self.assertRaises(ProductTopologyError):
            build(mutated, scope=ProductScope.EXPLICIT_VARIATION_FAMILY, identity=target(PARENT_ASIN))

    def test_target_connected_relation_endpoint_wrong_type_is_rejected(self) -> None:
        row = relation_rows(self.xiyou)[0]
        malformed = replace(
            row.value,
            raw_value={"asin": TARGET_ASIN},
            normalized_value={"asin": TARGET_ASIN},
            value_type=ValueType.OBJECT,
        )
        mutated = replace_observations(self.xiyou, {row.observation_id: replace(row, value=malformed)})
        with self.assertRaises(ProductTopologyError):
            build(mutated, scope=ProductScope.EXPLICIT_VARIATION_FAMILY, identity=target(PARENT_ASIN))

    def test_target_connected_unparseable_relation_direction_is_rejected(self) -> None:
        row = relation_rows(self.xiyou)[0]
        unknown_direction = replace(row, dimension="sibling_product_relationship")
        mutated = replace_observations(self.xiyou, {row.observation_id: unknown_direction})
        with self.assertRaises(ProductTopologyError):
            build(mutated, scope=ProductScope.EXPLICIT_VARIATION_FAMILY, identity=target(PARENT_ASIN))


class FactsMetricsReviewsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.detail = adapt("sorftime", "product_detail")
        cls.info = adapt("xiyou", "asin_info")

    def test_fact_candidates_preserve_distinct_units_and_no_resolution_fields(self) -> None:
        snapshot = build(self.detail)
        pressure = [item for item in snapshot.product_fact_evidence_sets if item.dimension == "maximum_operating_pressure"]
        self.assertEqual(len(pressure), 3)
        self.assertEqual({item.unit.unit_code for item in pressure}, {"Pa", "WOG", "psi"})
        serialized = canonical_json(snapshot)
        for forbidden in ("preferred_value", "resolved_value", "average", "latest_value"):
            self.assertNotIn(forbidden, serialized)
        self.assertTrue(any(item.code == "NON_COMPARABLE_UNITS" for item in snapshot.diagnostics))

    def test_same_value_different_observation_ids_are_retained(self) -> None:
        title = next(item for item in self.detail.observations if getattr(item, "dimension", None) == "title")
        duplicate = replace(
            title,
            observation_id=title.observation_id + ":synthetic-same-value",
            semantic_observation_id=title.semantic_observation_id + ":synthetic-same-value",
        )
        bundle = replace_observations(self.detail, {}, (duplicate,))
        fact_set = next(item for item in build(bundle).product_fact_evidence_sets if item.dimension == "title")
        self.assertEqual(len(fact_set.candidates), 2)
        self.assertEqual(fact_set.candidate_state, FactCandidateState.ONE_DISTINCT_PRESENT_VALUE)

    def test_divergent_missing_null_zero_and_empty_fact_candidates_are_preserved(self) -> None:
        title = next(item for item in self.detail.observations if getattr(item, "dimension", None) == "title")
        values = (
            ValueEnvelope(presence_status=PresenceStatus.PRESENT, raw_value="", normalized_value="", value_type=ValueType.STRING, unit=None, normalization_status=NormalizationStatus.NORMALIZED, semantic_status=SemanticStatus.CONFIRMED),
            ValueEnvelope(presence_status=PresenceStatus.PRESENT, raw_value=0, normalized_value=0, value_type=ValueType.INTEGER, unit=None, normalization_status=NormalizationStatus.NORMALIZED, semantic_status=SemanticStatus.CONFIRMED),
            ValueEnvelope(presence_status=PresenceStatus.MISSING, raw_value=None, normalized_value=None, value_type=ValueType.STRING, unit=None, normalization_status=NormalizationStatus.NOT_APPLICABLE, semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED),
            ValueEnvelope(presence_status=PresenceStatus.EXPLICIT_NULL, raw_value=None, normalized_value=None, value_type=ValueType.STRING, unit=None, normalization_status=NormalizationStatus.NOT_APPLICABLE, semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED),
            ValueEnvelope(presence_status=PresenceStatus.UNKNOWN, raw_value=None, normalized_value=None, value_type=ValueType.STRING, unit=None, normalization_status=NormalizationStatus.NOT_APPLICABLE, semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED),
        )
        additions = tuple(replace(
            title, observation_id=f"{title.observation_id}:synthetic:{index}",
            semantic_observation_id=f"{title.semantic_observation_id}:synthetic:{index}", value=value,
        ) for index, value in enumerate(values))
        fact_set = next(item for item in build(replace_observations(self.detail, {}, additions)).product_fact_evidence_sets if item.dimension == "title")
        self.assertEqual(fact_set.candidate_state, FactCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES)
        self.assertEqual(
            {item.presence_status for item in fact_set.candidates},
            {PresenceStatus.PRESENT, PresenceStatus.MISSING, PresenceStatus.EXPLICIT_NULL, PresenceStatus.UNKNOWN},
        )
        self.assertTrue(any(item.normalized_value == 0 for item in fact_set.candidates))
        self.assertTrue(any(item.normalized_value == "" for item in fact_set.candidates))

    def test_observed_and_estimated_metrics_with_changed_semantics_are_separate(self) -> None:
        price = next(item for item in self.detail.observations if getattr(item, "metric", None) == "price")
        estimate = replace(
            price,
            observation_id=price.observation_id + ":synthetic-estimate",
            semantic_observation_id=price.semantic_observation_id + ":synthetic-estimate",
            evidence_type=EvidenceType.PROVIDER_ESTIMATE,
            measurement_type=EvidenceType.PROVIDER_ESTIMATE,
        )
        snapshot = build(replace_observations(self.detail, {}, (estimate,)))
        price_series = [item for item in snapshot.product_metric_series if item.metric == "price"]
        self.assertEqual({item.evidence_type for item in price_series}, {EvidenceType.OBSERVED, EvidenceType.PROVIDER_ESTIMATE})

    def test_metric_period_category_and_retrieval_boundaries_are_preserved(self) -> None:
        bsr = build(adapt("xiyou", "asin_bsr_trends"))
        rank_series = [item for item in bsr.product_metric_series if item.metric == "bsr"]
        self.assertGreaterEqual(len({canonical_json(item.rank_context) for item in rank_series}), 2)
        for series in rank_series:
            for candidate in series.candidates:
                if candidate.time.observed_at_status.value == "UNKNOWN":
                    self.assertIsNone(candidate.time.observed_at)
                self.assertNotEqual(candidate.time.observed_at, candidate.time.retrieved_at)

    def test_unknown_metric_period_is_not_filled_or_converted(self) -> None:
        snapshot = build(self.detail)
        monthly = next(item for item in snapshot.product_metric_series if item.metric == "estimated_monthly_sales")
        self.assertIsNone(monthly.period_start)
        self.assertIsNone(monthly.period_end)
        self.assertEqual(monthly.currency, None)
        self.assertTrue(any(item.code == "UNKNOWN_METRIC_PERIOD" for item in snapshot.diagnostics))
        serialized = canonical_json(snapshot)
        self.assertNotIn("revenue", serialized)
        self.assertNotIn("converted", serialized)

    def test_review_summary_is_descriptive_and_does_not_copy_analysis_fields(self) -> None:
        snapshot = build(adapt("sorftime", "product_reviews"))
        summary = snapshot.review_evidence_summary
        self.assertEqual(summary.review_observation_count, 1)
        self.assertEqual(summary.exact_unique_review_identity_count, 1)
        self.assertEqual(sum(summary.present_rating_histogram.values()), 1)
        self.assertEqual(summary.helpful_votes_missing_count, 1)
        self.assertEqual(summary.known_date_count + summary.unknown_date_count, 1)
        payload = summary.to_dict()
        for forbidden in ("sentiment", "pain_points", "themes", "body", "fuzzy"):
            self.assertNotIn(forbidden, payload)

    def test_same_review_text_with_different_identity_is_retained(self) -> None:
        reviews = adapt("sorftime", "product_reviews")
        row = reviews.observations[0]
        duplicate = replace(
            row, observation_id=row.observation_id + ":synthetic-review",
            semantic_observation_id=row.semantic_observation_id + ":synthetic-review",
            review_observation_id=row.review_observation_id + ":synthetic-review",
            provider_review_identity=(row.provider_review_identity or "review") + ":synthetic-review",
        )
        snapshot = build(replace_observations(reviews, {}, (duplicate,)))
        self.assertEqual(snapshot.review_evidence_summary.review_observation_count, 2)
        self.assertEqual(snapshot.review_evidence_summary.exact_unique_review_identity_count, 2)

    def test_review_missing_rating_helpful_zero_and_unknown_date_remain_distinct(self) -> None:
        reviews = adapt("sorftime", "product_reviews")
        row = reviews.observations[0]
        absent = ValueEnvelope(
            presence_status=PresenceStatus.MISSING,
            raw_value=None,
            normalized_value=None,
            value_type=ValueType.NUMBER,
            unit=None,
            normalization_status=NormalizationStatus.NOT_APPLICABLE,
            semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
        )
        zero = ValueEnvelope(
            presence_status=PresenceStatus.PRESENT,
            raw_value=0,
            normalized_value=0,
            value_type=ValueType.INTEGER,
            unit=None,
            normalization_status=NormalizationStatus.NORMALIZED,
            semantic_status=SemanticStatus.CONFIRMED,
        )
        duplicate = replace(
            row,
            observation_id=row.observation_id + ":synthetic-states",
            semantic_observation_id=row.semantic_observation_id + ":synthetic-states",
            review_observation_id=row.review_observation_id + ":synthetic-states",
            provider_review_identity=(row.provider_review_identity or "review") + ":synthetic-states",
            rating=absent,
            review_date=replace(absent, value_type=ValueType.DATE),
            helpful_votes=zero,
        )
        summary = build(replace_observations(reviews, {}, (duplicate,))).review_evidence_summary
        self.assertEqual(summary.rating_presence_counts["MISSING"], 1)
        self.assertEqual(summary.helpful_votes_missing_count, 1)
        self.assertEqual(summary.helpful_votes_zero_count, 1)
        self.assertEqual(summary.known_date_count, 1)
        self.assertEqual(summary.unknown_date_count, 1)

    def test_same_review_identity_dedupes_same_content_and_rejects_different_content(self) -> None:
        reviews = adapt("sorftime", "product_reviews")
        row = reviews.observations[0]
        same = replace(
            row,
            observation_id=row.observation_id + ":synthetic-same-review",
            semantic_observation_id=row.semantic_observation_id + ":synthetic-same-review",
        )
        summary = build(replace_observations(reviews, {}, (same,))).review_evidence_summary
        self.assertEqual(summary.review_observation_count, 1)
        self.assertEqual(len(summary.lineage_references), 2)
        changed_body = replace(row.body, raw_value="different body", normalized_value="different body")
        changed = replace(
            row,
            observation_id=row.observation_id + ":synthetic-review-collision",
            semantic_observation_id=row.semantic_observation_id + ":synthetic-review-collision",
            body=changed_body,
        )
        with self.assertRaises(ProductIdentityCollisionError):
            build(replace_observations(reviews, {}, (changed,)))


class KeywordCoverageLineageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.detail = adapt("sorftime", "product_detail")
        cls.keyword_metric = adapt("xiyou", "keyword_info")
        cls.relationship = adapt("xiyou", "keyword_asin_analysis")
        cls.snapshot = build(cls.detail, cls.keyword_metric, cls.relationship)

    def test_keyword_observations_are_inventoried_but_not_product_evidence(self) -> None:
        keyword_ids = {
            item.observation_id for bundle in (self.keyword_metric, self.relationship)
            for item in bundle.observations
            if item.observation_kind in {ObservationKind.KEYWORD_METRIC, ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP}
        }
        referenced = {item.observation_id for item in self.snapshot.out_of_scope_observation_references}
        self.assertTrue(keyword_ids <= referenced)
        self.assertFalse(any(item.metric.startswith("keyword") for item in self.snapshot.product_metric_series))
        self.assertEqual(self.snapshot.evidence_coverage_summary.out_of_scope_keyword_observation_count, len(keyword_ids))
        self.assertTrue(any(item.code == "OUT_OF_SCOPE_KEYWORD_OBSERVATION" for item in self.snapshot.diagnostics))
        serialized = canonical_json(self.snapshot)
        for forbidden in ("demand_score", "competition_score", "market_size", "opportunity_score"):
            self.assertNotIn(forbidden, serialized)

    def test_coverage_is_an_inventory_not_a_score(self) -> None:
        coverage = self.snapshot.evidence_coverage_summary
        self.assertGreater(coverage.source_bundle_count, 1)
        self.assertIn("PRODUCT_FACT", coverage.observation_counts_by_type)
        self.assertIn("PRESENT", coverage.presence_state_counts)
        self.assertIn("OBSERVED", coverage.evidence_type_counts)
        self.assertEqual(coverage.quality_issue_count, len(self.snapshot.quality_issue_references))
        self.assertEqual(coverage.product_intelligence_diagnostic_count, len(self.snapshot.diagnostics))
        payload = coverage.to_dict()
        for forbidden in ("completeness_percentage", "trust_score", "provider_ranking", "confidence_score"):
            self.assertNotIn(forbidden, payload)

    def test_every_snapshot_item_lineage_replays_to_mapping_raw_and_collection(self) -> None:
        self.snapshot.validate_against_bundles((self.detail, self.keyword_metric, self.relationship))
        for lineage in self.snapshot.lineage_index:
            self.assertTrue(lineage.transformation_run_id)
            self.assertTrue(lineage.mapping_version)
            self.assertTrue(lineage.raw_evidence_id.startswith("raw:"))
            self.assertTrue(lineage.collection_run_id.startswith("collection:"))
            self.assertTrue(lineage.source_bundle_fingerprints)

    def test_against_bundles_rejects_wrong_type_missing_bundle_and_orphan_lineage(self) -> None:
        with self.assertRaises(ProductIntelligenceValidationError):
            self.snapshot.validate_against_bundles((object(),))
        with self.assertRaises(ProductIntelligenceValidationError):
            self.snapshot.validate_against_bundles((self.detail,))
        payload = self.snapshot.to_dict()
        payload["lineage_index"][0]["raw_evidence_id"] = "raw:orphan"
        refresh_snapshot_id(payload)
        tampered = ProductIntelligenceSnapshotV0_1.from_dict(payload)
        with self.assertRaises(ProductIntelligenceValidationError):
            tampered.validate_against_bundles((self.detail, self.keyword_metric, self.relationship))

    def test_lineage_fields_fingerprint_and_exact_index_fail_closed(self) -> None:
        bundles = (self.detail, self.keyword_metric, self.relationship)
        mutations = {
            "observation_id": "obs:orphan",
            "transformation_run_id": "transform:orphan",
            "mapping_version": "mapping:orphan",
            "raw_evidence_id": "raw:orphan",
            "collection_run_id": "collection:orphan",
            "source_bundle_fingerprints": ["0" * 64],
        }
        for field, value in mutations.items():
            with self.subTest(field=field):
                payload = self.snapshot.to_dict()
                payload["lineage_index"][0][field] = value
                refresh_snapshot_id(payload)
                tampered = ProductIntelligenceSnapshotV0_1.from_dict(payload)
                with self.assertRaises(ProductIntelligenceValidationError):
                    tampered.validate_against_bundles(bundles)

        missing = self.snapshot.to_dict()
        missing["lineage_index"].pop()
        refresh_snapshot_id(missing)
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceSnapshotV0_1.from_dict(missing).validate_against_bundles(bundles)

        extra = self.snapshot.to_dict()
        invented = deepcopy(extra["lineage_index"][0])
        invented["source_field"] += ".invented"
        extra["lineage_index"].append(invented)
        refresh_snapshot_id(extra)
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceSnapshotV0_1.from_dict(extra).validate_against_bundles(bundles)

    def test_quality_issue_and_relation_lineage_orphans_fail_closed(self) -> None:
        bundles = (self.detail, self.keyword_metric, self.relationship)
        self.assertTrue(self.snapshot.quality_issue_references)
        issue_payload = self.snapshot.to_dict()
        issue_payload["quality_issue_references"][0]["issue_id"] = "issue:orphan"
        refresh_snapshot_id(issue_payload)
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceSnapshotV0_1.from_dict(issue_payload).validate_against_bundles(bundles)

        relation_bundle = adapt("xiyou", "asin_variations")
        family = build(relation_bundle, scope=ProductScope.EXPLICIT_VARIATION_FAMILY)
        relation_payload = family.to_dict()
        edge = relation_payload["variation_topology"]["edges"][0]
        edge["lineage_references"][0]["raw_evidence_id"] = "raw:orphan-relation"
        edge["variation_edge_id"] = deterministic_id(
            "variation-edge", {key: value for key, value in edge.items() if key != "variation_edge_id"}
        )
        refresh_snapshot_id(relation_payload)
        with self.assertRaises(ProductIntelligenceValidationError):
            ProductIntelligenceSnapshotV0_1.from_dict(relation_payload).validate_against_bundles((relation_bundle,))


class IdentityDeterminismSerializationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.detail = adapt("sorftime", "product_detail")
        cls.reviews = adapt("sorftime", "product_reviews")
        cls.snapshot = build(cls.detail, cls.reviews)

    def test_same_id_same_content_dedupes_across_distinct_bundles(self) -> None:
        merged = merge_bundles(self.detail, self.reviews)
        snapshot = build(self.detail, merged)
        title = next(item for item in snapshot.product_fact_evidence_sets if item.dimension == "title")
        self.assertEqual(len(title.candidates), 1)
        self.assertEqual(len(title.candidates[0].lineage_references[0].source_bundle_fingerprints), 2)

    def test_same_id_different_content_fails_closed(self) -> None:
        title = next(item for item in self.detail.observations if getattr(item, "dimension", None) == "title")
        changed_value = replace(title.value, raw_value="different", normalized_value="different")
        changed = replace_observations(self.detail, {title.observation_id: replace(title, value=changed_value)})
        with self.assertRaises(ProductIdentityCollisionError):
            build(self.detail, changed)

    def test_replay_bundle_order_and_record_order_are_deterministic(self) -> None:
        first = build(self.detail, self.reviews)
        second = build(self.reviews, self.detail)
        reordered_detail = replace(
            self.detail,
            observations=tuple(reversed(self.detail.observations)),
            quality_issues=tuple(reversed(self.detail.quality_issues)),
        )
        third = build(reordered_detail, self.reviews)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.to_dict(), third.to_dict())

    def test_snapshot_round_trip_is_strict_and_replayable(self) -> None:
        payload = self.snapshot.to_dict()
        restored = ProductIntelligenceSnapshotV0_1.from_dict(deepcopy(payload))
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(restored.snapshot_id, self.snapshot.snapshot_id)
        restored.validate_against_bundles((self.detail, self.reviews))

    def test_round_trip_replays_all_required_provider_and_scope_modes(self) -> None:
        xiyou_info = adapt("xiyou", "asin_info")
        xiyou_relations = adapt("xiyou", "asin_variations")
        sorftime_detail = adapt("sorftime", "product_detail")
        cases = (
            (build(xiyou_info), (xiyou_info,)),
            (build(xiyou_relations, scope=ProductScope.EXPLICIT_VARIATION_FAMILY), (xiyou_relations,)),
            (build(sorftime_detail), (sorftime_detail,)),
            (
                build(xiyou_relations, sorftime_detail, scope=ProductScope.EXPLICIT_VARIATION_FAMILY),
                (xiyou_relations, sorftime_detail),
            ),
        )
        for snapshot, bundles in cases:
            with self.subTest(snapshot_id=snapshot.snapshot_id):
                restored = ProductIntelligenceSnapshotV0_1.from_dict(snapshot.to_dict())
                self.assertEqual(restored.to_dict(), snapshot.to_dict())
                restored.validate_against_bundles(bundles)

    def test_replay_rejects_tampered_derived_candidate_and_coverage(self) -> None:
        candidate_payload = self.snapshot.to_dict()
        fact_set = next(
            item for item in candidate_payload["product_fact_evidence_sets"] if item["dimension"] == "title"
        )
        fact_set["candidates"][0]["raw_value"] = "forged title"
        fact_set["candidates"][0]["normalized_value"] = "forged title"
        fact_set["fact_set_id"] = deterministic_id(
            "fact-set", {key: value for key, value in fact_set.items() if key != "fact_set_id"}
        )
        refresh_snapshot_id(candidate_payload)
        forged = ProductIntelligenceSnapshotV0_1.from_dict(candidate_payload)
        with self.assertRaises(ProductIntelligenceValidationError):
            forged.validate_against_bundles((self.detail, self.reviews))

        coverage_payload = self.snapshot.to_dict()
        coverage_payload["evidence_coverage_summary"]["included_observation_count"] += 1
        refresh_snapshot_id(coverage_payload)
        forged = ProductIntelligenceSnapshotV0_1.from_dict(coverage_payload)
        with self.assertRaises(ProductIntelligenceValidationError):
            forged.validate_against_bundles((self.detail, self.reviews))

    def test_unknown_missing_invalid_enum_and_identity_mismatch_are_rejected(self) -> None:
        unknown = self.snapshot.to_dict()
        unknown["unexpected"] = True
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(unknown)
        missing = self.snapshot.to_dict()
        del missing["scope"]
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(missing)
        invalid = self.snapshot.to_dict()
        invalid["scope"] = "UNKNOWN"
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(invalid)
        invalid_period = self.snapshot.to_dict()
        invalid_period["product_metric_series"][0]["period_type"] = "INVENTED"
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(invalid_period)
        mismatch = self.snapshot.to_dict()
        mismatch["snapshot_id"] = "snapshot:" + "0" * 64
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(mismatch)

    def test_bool_as_int_nan_and_non_string_mapping_key_are_rejected(self) -> None:
        boolean = self.snapshot.to_dict()
        boolean["evidence_coverage_summary"]["source_bundle_count"] = True
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(boolean)
        nan_payload = self.snapshot.to_dict()
        nan_payload["product_fact_evidence_sets"][0]["candidates"][0]["normalized_value"] = float("nan")
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(nan_payload)
        non_string = self.snapshot.to_dict()
        non_string["evidence_coverage_summary"]["presence_state_counts"] = {1: 1}
        with self.assertRaises(SnapshotSerializationError):
            ProductIntelligenceSnapshotV0_1.from_dict(non_string)

    def test_snapshot_and_request_are_deeply_immutable(self) -> None:
        with self.assertRaises((TypeError, AttributeError)):
            self.snapshot.evidence_coverage_summary.presence_state_counts["PRESENT"] = 0
        with self.assertRaises((TypeError, AttributeError)):
            self.snapshot.product_fact_evidence_sets += ()
        candidate = self.snapshot.product_fact_evidence_sets[0].candidates[0]
        if hasattr(candidate.normalized_value, "__setitem__"):
            with self.assertRaises((TypeError, AttributeError)):
                candidate.normalized_value["x"] = 1

    def test_fresh_process_replay_identity(self) -> None:
        code = r'''
import json
from pathlib import Path
from amazon_product_intelligence.adapters import AdaptationContext, SorftimeAdapterV0_1
from amazon_product_intelligence.contracts import ProductIdentity, product_id
from amazon_product_intelligence.product_intelligence import ProductIntelligenceBuilderV0_1, ProductIntelligenceRequest, ProductScope
root=Path("tests/fixtures/provider_adapters/v0_1")
def one(kind,name):
 p=json.loads((root/name).read_text(encoding="utf-8")); c=AdaptationContext(provider="sorftime",payload_kind=kind,source_tool=kind,marketplace="US",locale="en-us",retrieved_at="2026-08-14T09:00:00Z",transformed_at="2026-08-14T09:01:00Z",collection_run_id=f"collection:sorftime:{kind}:product-intelligence-test",sanitized_request={"asin":"B0G2VV4RBW"},currency="USD"); return SorftimeAdapterV0_1().adapt(p,c).bundle
t=ProductIdentity(product_id=product_id("US","B0G2VV4RBW"),marketplace="US",asin="B0G2VV4RBW",parent_asin="B0G2VVX3ML",identity_status="CONFIRMED")
s=ProductIntelligenceBuilderV0_1().build(ProductIntelligenceRequest(target_product_identity=t,scope=ProductScope.EXACT_PRODUCT,canonical_bundles=(one("product_detail","sorftime_product_detail.json"),one("product_reviews","sorftime_product_reviews.json"))))
print(s.snapshot_id)
'''
        environment = dict(os.environ)
        environment["PYTHONPATH"] = "src"
        observed = subprocess.check_output(
            [sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1], env=environment, text=True
        ).strip()
        self.assertEqual(observed, self.snapshot.snapshot_id)


class RealAdapterIntegrationTests(unittest.TestCase):
    def test_xiyou_asin_info_builds_exact_snapshot(self) -> None:
        snapshot = build(adapt("xiyou", "asin_info"))
        self.assertTrue(any(item.dimension == "title" for item in snapshot.product_fact_evidence_sets))
        snapshot.validate_against_bundles((adapt("xiyou", "asin_info"),))

    def test_xiyou_variations_builds_confirmed_family_topology(self) -> None:
        bundle = adapt("xiyou", "asin_variations")
        snapshot = build(bundle, scope=ProductScope.EXPLICIT_VARIATION_FAMILY)
        self.assertEqual(len(snapshot.variation_topology.edges), 2)
        self.assertIn((PARENT_ASIN, TARGET_ASIN), {
            (item.parent_product_identity.asin, item.child_product_identity.asin)
            for item in snapshot.variation_topology.edges
        })

    def test_sorftime_detail_variations_and_reviews_preserve_separate_semantics(self) -> None:
        detail = adapt("sorftime", "product_detail")
        variations = adapt("sorftime", "product_variations")
        reviews = adapt("sorftime", "product_reviews")
        snapshot = build(detail, variations, reviews)
        self.assertTrue(any(item.metric == "estimated_sales_volume" for item in snapshot.product_metric_series))
        self.assertFalse(any(
            item.dimension in {"child_product_relationship", "parent_product_relationship"}
            for item in snapshot.product_fact_evidence_sets
        ))
        self.assertEqual(snapshot.review_evidence_summary.review_observation_count, 1)

    def test_single_provider_is_valid_and_not_diagnosed_as_failure(self) -> None:
        snapshot = build(adapt("sorftime", "product_detail"))
        self.assertEqual(snapshot.evidence_coverage_summary.provider_count, 1)
        self.assertFalse(any("SINGLE_PROVIDER" in item.code for item in snapshot.diagnostics))


if __name__ == "__main__":
    unittest.main()
