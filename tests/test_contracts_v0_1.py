from __future__ import annotations

import json
import math
import unittest
from dataclasses import replace

from amazon_product_intelligence.contracts.v0_1 import (
    BlockingScope,
    CanonicalEvidenceBundle,
    Channel,
    CheckStatus,
    CodeVersionScheme,
    Comparability,
    ConflictRecord,
    ConflictStatus,
    ContractValidationError,
    DataQualityIssue,
    EstimateMethodStatus,
    EvidenceType,
    FactGroup,
    KeywordIdentity,
    KeywordMetricObservation,
    MetricObservation,
    NormalizationStatus,
    ObservationKind,
    ObservedAtStatus,
    OriginStage,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    Provenance,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    RelationshipDirection,
    RelationshipType,
    ResolutionLineage,
    ResolutionStatus,
    ResolvedEvidence,
    ResultStatus,
    ReviewObservation,
    Scope,
    ScopeStatus,
    ScopeType,
    SemanticStatus,
    Severity,
    SubjectRef,
    SubjectType,
    TimeWindow,
    TransformationCodeVersion,
    TransformationProvenance,
    TransformationRunRecord,
    TransformationStatus,
    Unit,
    ValueEnvelope,
    ValueType,
    VersionStatus,
    canonical_json,
    conflict_record_id,
    deterministic_id,
    keyword_id,
    observation_revision_id,
    product_id,
    resolution_record_id,
    semantic_observation_id,
)


RETRIEVED_AT = "2026-08-14T08:19:21.656Z"
TRANSFORMED_AT = "2026-08-14T08:30:00Z"
RAW_ID = "raw:sorftime:product:B0G2Q22W6D"


def unknown_schema() -> ProviderSchemaVersion:
    return ProviderSchemaVersion(
        status=VersionStatus.UNKNOWN,
        value=None,
        source=ProviderSchemaSource.UNKNOWN,
    )


def known_code() -> TransformationCodeVersion:
    return TransformationCodeVersion(
        status=VersionStatus.KNOWN,
        value="517cfecba43cc6765fc743b90b9cc7c77841b38d",
        scheme=CodeVersionScheme.GIT_COMMIT,
    )


def subject() -> SubjectRef:
    return SubjectRef(
        subject_type=SubjectType.PRODUCT,
        subject_id=product_id("US", "B0G2Q22W6D"),
        marketplace="US",
    )


def time_window() -> TimeWindow:
    return TimeWindow(
        observed_at=None,
        observed_at_status=ObservedAtStatus.UNKNOWN,
        retrieved_at=RETRIEVED_AT,
        period_start=None,
        period_end=None,
        period_type=PeriodType.INSTANT,
        timezone=None,
    )


def present_number(value: float, *, unit_code: str = "stars_5") -> ValueEnvelope:
    return ValueEnvelope(
        presence_status=PresenceStatus.PRESENT,
        raw_value=value,
        normalized_value=value,
        value_type=ValueType.NUMBER,
        unit=Unit(dimension="RATING", unit_code=unit_code, unit_system="DOMAIN"),
        normalization_status=NormalizationStatus.NORMALIZED,
        semantic_status=SemanticStatus.CONFIRMED,
    )


def unknown_number() -> ValueEnvelope:
    return ValueEnvelope(
        presence_status=PresenceStatus.UNKNOWN,
        raw_value=None,
        normalized_value=None,
        value_type=ValueType.NUMBER,
        unit=Unit(dimension="RATING", unit_code="stars_5", unit_system="DOMAIN"),
        normalization_status=NormalizationStatus.NOT_ATTEMPTED,
        semantic_status=SemanticStatus.CONFIRMED,
    )


def make_metric(
    *,
    run_id: str = "transform:sorftime:T1",
    mapping_version: str = "sorftime_product_mapping_v1",
    value: float = 4.1,
    evidence_type: EvidenceType = EvidenceType.OBSERVED,
) -> MetricObservation:
    item_subject = subject()
    item_time = time_window()
    item_value = present_number(value)
    semantic_id = semantic_observation_id(
        provider="sorftime",
        source_tool="get_product_detail",
        subject=item_subject,
        observation_kind=ObservationKind.METRIC,
        dimension="rating",
        source_record_identity="US:B0G2Q22W6D",
        observed_at=None,
        period_identity={"period_type": "INSTANT", "start": None, "end": None},
    )
    revision_id = observation_revision_id(
        semantic_id,
        {
            "value": item_value,
            "evidence_type": evidence_type,
            "scope": {"type": "ASIN", "subject": item_subject.subject_id},
            "period": "INSTANT",
            "metric": "rating",
        },
    )
    transformation = TransformationProvenance(
        collection_run_id="collection:sorftime:C1",
        provider_schema_version=unknown_schema(),
        mapping_version=mapping_version,
        transformation_run_id=run_id,
        transformation_code_version=known_code(),
        raw_evidence_reference=RAW_ID,
        transformed_at=TRANSFORMED_AT,
        transformation_status=TransformationStatus.SUCCESS,
    )
    return MetricObservation(
        semantic_observation_id=semantic_id,
        observation_id=revision_id,
        observation_kind=ObservationKind.METRIC,
        subject=item_subject,
        metric="rating",
        measurement_type=evidence_type,
        metric_semantic="Displayed ASIN rating on a five-star scale",
        evidence_type=evidence_type,
        value=item_value,
        scope=Scope(
            scope_type=ScopeType.ASIN,
            scope_status=ScopeStatus.CONFIRMED,
            scope_subject_id=item_subject.subject_id,
        ),
        time=item_time,
        provenance=Provenance(
            provider="sorftime",
            source_tool="get_product_detail",
            source_field="rating",
            source_record_identity="US:B0G2Q22W6D",
            retrieved_at=RETRIEVED_AT,
            transformation=transformation,
            provider_semantic="Displayed ASIN rating",
            semantic_validation_status=SemanticStatus.CONFIRMED,
        ),
        quality_issue_ids=(),
        result_status=ResultStatus.POPULATED,
    )


def make_run(observation: MetricObservation) -> TransformationRunRecord:
    transform = observation.provenance.transformation
    return TransformationRunRecord(
        provider=observation.provenance.provider,
        collection_run_id=transform.collection_run_id,
        provider_schema_version=transform.provider_schema_version,
        mapping_version=transform.mapping_version,
        transformation_run_id=transform.transformation_run_id,
        transformation_code_version=transform.transformation_code_version,
        started_at="2026-08-14T08:29:59Z",
        completed_at=TRANSFORMED_AT,
        status=TransformationStatus.SUCCESS,
        input_raw_evidence_references=(RAW_ID,),
        output_observation_ids=(observation.observation_id,),
        quality_issue_ids=(),
    )


class VersionAndPresenceTests(unittest.TestCase):
    def test_unknown_provider_schema_is_explicit(self) -> None:
        self.assertEqual(
            unknown_schema().to_dict(),
            {"status": "UNKNOWN", "value": None, "source": "UNKNOWN"},
        )

    def test_known_version_cannot_use_unknown_source(self) -> None:
        with self.assertRaises(ContractValidationError):
            ProviderSchemaVersion(
                status=VersionStatus.KNOWN,
                value="v1",
                source=ProviderSchemaSource.UNKNOWN,
            )

    def test_zero_is_present_but_missing_cannot_carry_zero(self) -> None:
        zero = ValueEnvelope(
            presence_status=PresenceStatus.PRESENT,
            raw_value=0,
            normalized_value=0,
            value_type=ValueType.INTEGER,
            unit=None,
            normalization_status=NormalizationStatus.NORMALIZED,
            semantic_status=SemanticStatus.CONFIRMED,
        )
        self.assertEqual(zero.normalized_value, 0)
        with self.assertRaises(ContractValidationError):
            ValueEnvelope(
                presence_status=PresenceStatus.MISSING,
                raw_value=None,
                normalized_value=0,
                value_type=ValueType.INTEGER,
                unit=None,
                normalization_status=NormalizationStatus.NOT_ATTEMPTED,
                semantic_status=SemanticStatus.CONFIRMED,
            )

    def test_missing_null_and_unknown_remain_distinct_after_serialization(self) -> None:
        payloads = []
        for status in (PresenceStatus.MISSING, PresenceStatus.EXPLICIT_NULL, PresenceStatus.UNKNOWN):
            value = ValueEnvelope(
                presence_status=status,
                raw_value=None,
                normalized_value=None,
                value_type=ValueType.STRING,
                unit=None,
                normalization_status=NormalizationStatus.NOT_ATTEMPTED,
                semantic_status=SemanticStatus.CONFIRMED,
            )
            restored = ValueEnvelope.from_dict(value.to_dict())
            self.assertEqual(restored, value)
            payloads.append(restored.to_dict())
        self.assertEqual({item["presence_status"] for item in payloads}, {"MISSING", "EXPLICIT_NULL", "UNKNOWN"})

    def test_explicit_empty_values_remain_present(self) -> None:
        for raw, value_type in (("", ValueType.STRING), ([], ValueType.LIST)):
            with self.subTest(raw=raw):
                value = ValueEnvelope(
                    presence_status=PresenceStatus.PRESENT,
                    raw_value=raw,
                    normalized_value=raw,
                    value_type=value_type,
                    unit=None,
                    normalization_status=NormalizationStatus.NOT_APPLICABLE,
                    semantic_status=SemanticStatus.CONFIRMED,
                )
                restored = ValueEnvelope.from_dict(value.to_dict())
                self.assertEqual(restored.presence_status, PresenceStatus.PRESENT)
                self.assertEqual(restored.to_dict()["normalized_value"], raw)

    def test_retrieval_time_never_fills_unknown_observation_time(self) -> None:
        with self.assertRaises(ContractValidationError):
            TimeWindow(
                observed_at=RETRIEVED_AT,
                observed_at_status=ObservedAtStatus.UNKNOWN,
                retrieved_at=RETRIEVED_AT,
                period_start=None,
                period_end=None,
                period_type=PeriodType.INSTANT,
                timezone=None,
            )


class IdentityTests(unittest.TestCase):
    def test_product_and_keyword_identity_are_deterministic(self) -> None:
        self.assertEqual(product_id("us", "b0g2q22w6d"), "product:US:B0G2Q22W6D")
        first = keyword_id("US", "en-US", "  Ball   Valve ")
        second = keyword_id("us", "en-us", "ball valve")
        self.assertEqual(first, second)

    def test_reprocessing_same_content_keeps_both_ids(self) -> None:
        first = make_metric(run_id="transform:T1", mapping_version="mapping_v1")
        second = make_metric(run_id="transform:T2", mapping_version="mapping_v2")
        self.assertEqual(first.semantic_observation_id, second.semantic_observation_id)
        self.assertEqual(first.observation_id, second.observation_id)
        self.assertNotEqual(
            first.provenance.transformation.transformation_run_id,
            second.provenance.transformation.transformation_run_id,
        )

    def test_mapping_fix_changes_revision_not_semantic_identity(self) -> None:
        first = make_metric(value=4.1)
        fixed = make_metric(value=4.6, run_id="transform:T2", mapping_version="mapping_v2")
        self.assertEqual(first.semantic_observation_id, fixed.semantic_observation_id)
        self.assertNotEqual(first.observation_id, fixed.observation_id)

    def test_canonical_identity_is_stable_across_mapping_order(self) -> None:
        first = {"subject": "product:US:B0G2Q22W6D", "value": 0, "status": "PRESENT"}
        second = {"status": "PRESENT", "value": 0, "subject": "product:US:B0G2Q22W6D"}
        self.assertEqual(canonical_json(first), canonical_json(second))
        self.assertEqual(deterministic_id("fixture", first), deterministic_id("fixture", second))

    def test_identity_material_rejects_non_json_and_ambiguous_values(self) -> None:
        for invalid in ({"set": {"a", "b"}}, {1: "numeric-key"}, {"number": math.nan}):
            with self.subTest(invalid=repr(invalid)):
                with self.assertRaises(ContractValidationError):
                    deterministic_id("fixture", invalid)

    def test_conflict_and_resolution_ids_ignore_candidate_order(self) -> None:
        candidates = ("obs:a", "obs:b")
        self.assertEqual(
            conflict_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=candidates,
                conflict_status=ConflictStatus.CONSISTENT,
            ),
            conflict_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=tuple(reversed(candidates)),
                conflict_status=ConflictStatus.CONSISTENT,
            ),
        )
        self.assertEqual(
            resolution_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=candidates,
                resolution_policy="policy:v1",
            ),
            resolution_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=tuple(reversed(candidates)),
                resolution_policy="policy:v1",
            ),
        )


class ObservationShapeTests(unittest.TestCase):
    def common(self, kind: ObservationKind) -> dict[str, object]:
        metric = make_metric()
        return {
            "semantic_observation_id": f"obss:test:{kind.value.lower()}",
            "observation_id": f"obs:test:{kind.value.lower()}",
            "observation_kind": kind,
            "subject": metric.subject,
            "evidence_type": metric.evidence_type,
            "value": metric.value,
            "scope": metric.scope,
            "time": metric.time,
            "provenance": metric.provenance,
            "quality_issue_ids": (),
            "result_status": ResultStatus.POPULATED,
        }

    def keyword(self) -> KeywordIdentity:
        return KeywordIdentity(
            keyword_id=keyword_id("US", "en-us", "ball valve"),
            marketplace="US",
            locale="en-us",
            normalized_text="ball valve",
            raw_text="Ball Valve",
        )

    def product(self) -> ProductIdentity:
        return ProductIdentity(
            product_id=product_id("US", "B0G2Q22W6D"),
            marketplace="US",
            asin="B0G2Q22W6D",
            parent_asin=None,
            identity_status="CONFIRMED",
        )

    def test_all_five_observation_kinds_are_json_compatible(self) -> None:
        fact = ProductFactObservation(
            **self.common(ObservationKind.PRODUCT_FACT),
            dimension="maximum_operating_pressure",
            fact_group=FactGroup.TECHNICAL,
            provider_semantic="Maximum operating pressure attribute",
        )
        metric = make_metric()
        keyword_metric = KeywordMetricObservation(
            **self.common(ObservationKind.KEYWORD_METRIC),
            keyword=self.keyword(),
            metric="search_volume",
            metric_semantic="Provider-estimated query volume",
            estimate_method_status=EstimateMethodStatus.PARTIALLY_DOCUMENTED,
        )
        relationship = ProductKeywordRelationshipObservation(
            **self.common(ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP),
            relationship_id="rel:test:ball-valve",
            product=self.product(),
            keyword=self.keyword(),
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
            relationship_type=RelationshipType.RANK,
            channel=Channel.ORGANIC,
            query_result_status=ResultStatus.POPULATED,
            rank={"rank": 12},
        )
        missing_text = ValueEnvelope(
            presence_status=PresenceStatus.MISSING,
            raw_value=None,
            normalized_value=None,
            value_type=ValueType.STRING,
            unit=None,
            normalization_status=NormalizationStatus.NOT_ATTEMPTED,
            semantic_status=SemanticStatus.CONFIRMED,
        )
        review = ReviewObservation(
            **self.common(ObservationKind.REVIEW),
            review_observation_id="review:test:1",
            product=self.product(),
            provider_review_identity=None,
            rating=present_number(5),
            title=missing_text,
            body=missing_text,
            review_date=missing_text,
            variant=missing_text,
            helpful_votes=ValueEnvelope(
                presence_status=PresenceStatus.UNKNOWN,
                raw_value=None,
                normalized_value=None,
                value_type=ValueType.INTEGER,
                unit=None,
                normalization_status=NormalizationStatus.NOT_ATTEMPTED,
                semantic_status=SemanticStatus.CONFIRMED,
            ),
        )
        kinds = [fact, metric, keyword_metric, relationship, review]
        self.assertEqual(
            {item.to_dict()["observation_kind"] for item in kinds},
            {kind.value for kind in ObservationKind},
        )
        for item in kinds:
            json.dumps(item.to_dict())

    def test_metric_measurement_type_must_match_evidence_type(self) -> None:
        metric = make_metric()
        with self.assertRaises(ContractValidationError):
            MetricObservation(
                semantic_observation_id=metric.semantic_observation_id,
                observation_id=metric.observation_id,
                observation_kind=metric.observation_kind,
                subject=metric.subject,
                metric=metric.metric,
                measurement_type=EvidenceType.PROVIDER_ESTIMATE,
                metric_semantic=metric.metric_semantic,
                evidence_type=EvidenceType.OBSERVED,
                value=metric.value,
                scope=metric.scope,
                time=metric.time,
                provenance=metric.provenance,
                quality_issue_ids=(),
                result_status=ResultStatus.POPULATED,
            )

    def test_caller_owned_mapping_cannot_mutate_contract_state(self) -> None:
        rank = {"rank": 12, "context": {"page": 1}}
        relationship = ProductKeywordRelationshipObservation(
            **self.common(ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP),
            relationship_id="rel:test:immutable",
            product=self.product(),
            keyword=self.keyword(),
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
            relationship_type=RelationshipType.RANK,
            channel=Channel.ORGANIC,
            query_result_status=ResultStatus.POPULATED,
            rank=rank,
        )
        rank["rank"] = 99
        rank["context"]["page"] = 9
        self.assertEqual(relationship.to_dict()["rank"], {"rank": 12, "context": {"page": 1}})


class ProvenanceTests(unittest.TestCase):
    def test_failed_transform_cannot_be_embedded_in_observation(self) -> None:
        with self.assertRaises(ContractValidationError):
            TransformationProvenance(
                collection_run_id="collection:C1",
                provider_schema_version=unknown_schema(),
                mapping_version="mapping_v1",
                transformation_run_id="transform:T1",
                transformation_code_version=known_code(),
                raw_evidence_reference=RAW_ID,
                transformed_at=TRANSFORMED_AT,
                transformation_status=TransformationStatus.FAILED,
            )

    def test_failed_run_has_no_fake_output(self) -> None:
        run = TransformationRunRecord(
            provider="sorftime",
            collection_run_id="collection:C1",
            provider_schema_version=unknown_schema(),
            mapping_version="mapping_v1",
            transformation_run_id="transform:failed",
            transformation_code_version=known_code(),
            started_at="2026-08-14T08:29:59Z",
            completed_at=TRANSFORMED_AT,
            status=TransformationStatus.FAILED,
            input_raw_evidence_references=(RAW_ID,),
            output_observation_ids=(),
            quality_issue_ids=("dqi:transform-failed",),
        )
        self.assertEqual(run.output_observation_ids, ())

    def test_mapping_issue_requires_full_lineage(self) -> None:
        with self.assertRaises(ContractValidationError):
            DataQualityIssue(
                issue_id="dqi:mapping",
                issue_code="MAPPING_ERROR",
                severity=Severity.MATERIAL,
                subject=subject(),
                dimension="rating",
                message="Mapping changed the value",
                blocking=True,
                blocking_scope=BlockingScope.FIELD,
                source_references=(RAW_ID,),
                created_at=TRANSFORMED_AT,
                origin_stage=OriginStage.MAPPING,
                collection_run_id="collection:C1",
                transformation_run_id=None,
                mapping_version="mapping_v1",
            )


class BundleTests(unittest.TestCase):
    def test_valid_bundle_serializes_to_provider_neutral_json(self) -> None:
        observation = make_metric()
        bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(RAW_ID,),
            transformation_runs=(make_run(observation),),
            observations=(observation,),
            conflicts=(),
            resolutions=(),
            quality_issues=(),
        )
        payload = bundle.to_dict()
        self.assertEqual(payload["schema_version"], "0.1")
        self.assertEqual(payload["observations"][0]["measurement_type"], "OBSERVED")
        json.dumps(payload)

    def test_reprocessing_preserves_two_runs_for_one_revision(self) -> None:
        first = make_metric(run_id="transform:T1", mapping_version="mapping_v1")
        second = make_metric(run_id="transform:T2", mapping_version="mapping_v2")
        bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(RAW_ID,),
            transformation_runs=(make_run(first), make_run(second)),
            observations=(first, second),
            conflicts=(),
            resolutions=(),
            quality_issues=(),
        )
        self.assertEqual(len(bundle.transformation_runs), 2)
        self.assertEqual(len({item.observation_id for item in bundle.observations}), 1)

    def test_bundle_rejects_orphan_transformation_lineage(self) -> None:
        observation = make_metric()
        with self.assertRaisesRegex(ContractValidationError, "no transformation run"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(),
                observations=(observation,),
                conflicts=(),
                resolutions=(),
                quality_issues=(),
            )

    def test_bundle_rejects_unknown_raw_input(self) -> None:
        observation = make_metric()
        with self.assertRaisesRegex(ContractValidationError, "unknown raw evidence"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(),
                transformation_runs=(make_run(observation),),
                observations=(observation,),
                conflicts=(),
                resolutions=(),
                quality_issues=(),
            )

    def test_bundle_round_trip_is_strict_and_stable(self) -> None:
        observation = make_metric()
        original = CanonicalEvidenceBundle(
            raw_evidence_references=(RAW_ID,),
            transformation_runs=(make_run(observation),),
            observations=(observation,),
            conflicts=(),
            resolutions=(),
            quality_issues=(),
        )
        payload = original.to_dict()
        restored = CanonicalEvidenceBundle.from_dict(json.loads(json.dumps(payload)))
        self.assertEqual(restored.to_dict(), payload)
        self.assertEqual(canonical_json(restored), canonical_json(original))

        payload["unexpected"] = True
        with self.assertRaisesRegex(ContractValidationError, "unknown fields"):
            CanonicalEvidenceBundle.from_dict(payload)

    def test_bundle_rejects_duplicate_run_identity(self) -> None:
        observation = make_metric()
        run = make_run(observation)
        with self.assertRaisesRegex(ContractValidationError, "duplicate transformation_run_id"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(run, run),
                observations=(observation,),
                conflicts=(),
                resolutions=(),
                quality_issues=(),
            )

    def test_same_revision_id_cannot_hide_different_content(self) -> None:
        first = make_metric(value=4.1, run_id="transform:T1")
        changed = make_metric(value=4.6, run_id="transform:T2")
        forged = replace(changed, observation_id=first.observation_id)
        with self.assertRaisesRegex(ContractValidationError, "conflicting canonical content"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(make_run(first), make_run(forged)),
                observations=(first, forged),
                conflicts=(),
                resolutions=(),
                quality_issues=(),
            )


class ConflictAndResolutionTests(unittest.TestCase):
    def test_material_difference_remains_unresolved_without_averaging(self) -> None:
        first = make_metric(value=4.1, run_id="transform:T1")
        second = make_metric(value=4.6, run_id="transform:T2")
        comparability = Comparability(
            identity=CheckStatus.PASS,
            dimension=CheckStatus.PASS,
            semantic=CheckStatus.PASS,
            scope=CheckStatus.PASS,
            period=CheckStatus.PASS,
            unit=CheckStatus.PASS,
            direction=CheckStatus.NOT_APPLICABLE,
        )
        conflict = ConflictRecord(
            conflict_id=conflict_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=(first.observation_id, second.observation_id),
                conflict_status=ConflictStatus.MATERIAL_DIFFERENCE,
            ),
            subject=subject(),
            dimension="rating",
            candidate_observation_ids=(first.observation_id, second.observation_id),
            conflict_status=ConflictStatus.MATERIAL_DIFFERENCE,
            comparability=comparability,
            difference={"absolute": 0.5, "unit_code": "stars_5"},
            severity=Severity.MATERIAL,
            blocking=True,
            blocking_scope=BlockingScope.FIELD,
            resolution_status=ResolutionStatus.UNRESOLVED,
            explanation="Comparable ratings differ materially; no averaging policy exists.",
        )
        resolution = ResolvedEvidence(
            resolution_id=resolution_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=(first.observation_id, second.observation_id),
                resolution_policy=None,
            ),
            subject=subject(),
            dimension="rating",
            candidate_observation_ids=(first.observation_id, second.observation_id),
            conflict_id=conflict.conflict_id,
            conflict_status=ConflictStatus.MATERIAL_DIFFERENCE,
            resolution_status=ResolutionStatus.UNRESOLVED,
            value=unknown_number(),
            resolution_method="COMPARABILITY_AND_THRESHOLD_ASSESSMENT",
            resolution_policy=None,
            quality_issue_ids=(),
            lineage=ResolutionLineage(
                observation_ids=(first.observation_id, second.observation_id),
                raw_evidence_ids=(RAW_ID,),
            ),
        )
        self.assertIsNone(resolution.value.normalized_value)

    def test_unresolved_resolution_cannot_publish_present_value(self) -> None:
        observation = make_metric()
        with self.assertRaises(ContractValidationError):
            ResolvedEvidence(
                resolution_id=resolution_record_id(
                    subject=subject(),
                    dimension="rating",
                    candidate_observation_ids=(observation.observation_id,),
                    resolution_policy=None,
                ),
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=(observation.observation_id,),
                conflict_id=None,
                conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
                resolution_status=ResolutionStatus.UNRESOLVED,
                value=present_number(4.1),
                resolution_method="NO_POLICY",
                resolution_policy=None,
                quality_issue_ids=(),
                lineage=ResolutionLineage(
                    observation_ids=(observation.observation_id,),
                    raw_evidence_ids=(RAW_ID,),
                ),
            )

    def test_one_source_conflict_can_resolve_only_under_named_policy(self) -> None:
        observation = make_metric()
        candidates = (observation.observation_id,)
        policy = "single-source-acceptance:v1"
        comparability = Comparability(
            identity=CheckStatus.PASS,
            dimension=CheckStatus.PASS,
            semantic=CheckStatus.PASS,
            scope=CheckStatus.PASS,
            period=CheckStatus.PASS,
            unit=CheckStatus.PASS,
            direction=CheckStatus.NOT_APPLICABLE,
        )
        conflict = ConflictRecord(
            conflict_id=conflict_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=candidates,
                conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
            ),
            subject=subject(),
            dimension="rating",
            candidate_observation_ids=candidates,
            conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
            comparability=comparability,
            difference=None,
            severity=Severity.INFO,
            blocking=False,
            blocking_scope=BlockingScope.NONE,
            resolution_status=ResolutionStatus.RESOLVED_BY_POLICY,
            explanation="A versioned policy accepts this non-critical single-source rating.",
        )
        resolution = ResolvedEvidence(
            resolution_id=resolution_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=candidates,
                resolution_policy=policy,
            ),
            subject=subject(),
            dimension="rating",
            candidate_observation_ids=candidates,
            conflict_id=conflict.conflict_id,
            conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
            resolution_status=ResolutionStatus.RESOLVED_BY_POLICY,
            value=observation.value,
            resolution_method="SINGLE_SOURCE_ACCEPTANCE",
            resolution_policy=policy,
            quality_issue_ids=(),
            lineage=ResolutionLineage(observation_ids=candidates, raw_evidence_ids=(RAW_ID,)),
        )
        bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(RAW_ID,),
            transformation_runs=(make_run(observation),),
            observations=(observation,),
            conflicts=(conflict,),
            resolutions=(resolution,),
            quality_issues=(),
        )
        self.assertEqual(bundle.resolutions[0].value.normalized_value, 4.1)

    def test_bundle_rejects_wrong_type_conflict_candidate(self) -> None:
        observation = make_metric()
        candidates = (RAW_ID,)
        conflict = ConflictRecord(
            conflict_id=conflict_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=candidates,
                conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
            ),
            subject=subject(),
            dimension="rating",
            candidate_observation_ids=candidates,
            conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
            comparability=Comparability(
                identity=CheckStatus.UNKNOWN,
                dimension=CheckStatus.UNKNOWN,
                semantic=CheckStatus.UNKNOWN,
                scope=CheckStatus.UNKNOWN,
                period=CheckStatus.UNKNOWN,
                unit=CheckStatus.UNKNOWN,
                direction=CheckStatus.NOT_APPLICABLE,
            ),
            difference=None,
            severity=Severity.WARNING,
            blocking=False,
            blocking_scope=BlockingScope.NONE,
            resolution_status=ResolutionStatus.UNRESOLVED,
            explanation="Fixture uses the wrong artifact type as a candidate.",
        )
        with self.assertRaisesRegex(ContractValidationError, "unknown observation"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(make_run(observation),),
                observations=(observation,),
                conflicts=(conflict,),
                resolutions=(),
                quality_issues=(),
            )

    def test_bundle_rejects_resolution_that_disagrees_with_conflict(self) -> None:
        observation = make_metric()
        candidates = (observation.observation_id,)
        conflict = ConflictRecord(
            conflict_id=conflict_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=candidates,
                conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
            ),
            subject=subject(),
            dimension="rating",
            candidate_observation_ids=candidates,
            conflict_status=ConflictStatus.ONE_SOURCE_ONLY,
            comparability=Comparability(
                identity=CheckStatus.PASS,
                dimension=CheckStatus.PASS,
                semantic=CheckStatus.PASS,
                scope=CheckStatus.PASS,
                period=CheckStatus.PASS,
                unit=CheckStatus.PASS,
                direction=CheckStatus.NOT_APPLICABLE,
            ),
            difference=None,
            severity=Severity.INFO,
            blocking=False,
            blocking_scope=BlockingScope.NONE,
            resolution_status=ResolutionStatus.UNRESOLVED,
            explanation="Single source remains unresolved.",
        )
        resolution = ResolvedEvidence(
            resolution_id=resolution_record_id(
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=candidates,
                resolution_policy=None,
            ),
            subject=subject(),
            dimension="rating",
            candidate_observation_ids=candidates,
            conflict_id=conflict.conflict_id,
            conflict_status=ConflictStatus.MINOR_DIFFERENCE,
            resolution_status=ResolutionStatus.UNRESOLVED,
            value=unknown_number(),
            resolution_method="INVALID_TARGET_FIXTURE",
            resolution_policy=None,
            quality_issue_ids=(),
            lineage=ResolutionLineage(observation_ids=candidates, raw_evidence_ids=(RAW_ID,)),
        )
        with self.assertRaisesRegex(ContractValidationError, "status does not match conflict"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(make_run(observation),),
                observations=(observation,),
                conflicts=(conflict,),
                resolutions=(resolution,),
                quality_issues=(),
            )

    def test_bundle_rejects_quality_issue_with_orphan_run(self) -> None:
        observation = make_metric()
        issue = DataQualityIssue(
            issue_id="dqi:orphan-run",
            issue_code="MAPPING_ERROR",
            severity=Severity.MATERIAL,
            subject=subject(),
            dimension="rating",
            message="Mapping issue references a transformation that is not in the bundle.",
            blocking=True,
            blocking_scope=BlockingScope.FIELD,
            source_references=(RAW_ID,),
            created_at=TRANSFORMED_AT,
            origin_stage=OriginStage.MAPPING,
            collection_run_id="collection:sorftime:C1",
            transformation_run_id="transform:missing",
            mapping_version="sorftime_product_mapping_v1",
        )
        run = replace(make_run(observation), quality_issue_ids=(issue.issue_id,))
        with self.assertRaisesRegex(ContractValidationError, "unknown transformation run"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(run,),
                observations=(observation,),
                conflicts=(),
                resolutions=(),
                quality_issues=(issue,),
            )

    def test_material_conflict_cannot_claim_resolved_status(self) -> None:
        observation = make_metric()
        with self.assertRaisesRegex(ContractValidationError, "cannot be represented as resolved"):
            ConflictRecord(
                conflict_id=conflict_record_id(
                    subject=subject(),
                    dimension="rating",
                    candidate_observation_ids=(observation.observation_id,),
                    conflict_status=ConflictStatus.MATERIAL_DIFFERENCE,
                ),
                subject=subject(),
                dimension="rating",
                candidate_observation_ids=(observation.observation_id,),
                conflict_status=ConflictStatus.MATERIAL_DIFFERENCE,
                comparability=Comparability(
                    identity=CheckStatus.PASS,
                    dimension=CheckStatus.PASS,
                    semantic=CheckStatus.PASS,
                    scope=CheckStatus.PASS,
                    period=CheckStatus.PASS,
                    unit=CheckStatus.PASS,
                    direction=CheckStatus.NOT_APPLICABLE,
                ),
                difference={"absolute": 1.0},
                severity=Severity.MATERIAL,
                blocking=True,
                blocking_scope=BlockingScope.FIELD,
                resolution_status=ResolutionStatus.RESOLVED_DETERMINISTIC,
                explanation="Unsafe fixture.",
            )


if __name__ == "__main__":
    unittest.main()
