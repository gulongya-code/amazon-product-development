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
    DirectionalQueryExecutionRecord,
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
    QueryExecutionOutcome,
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
    query_execution_id,
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


def make_keyword() -> KeywordIdentity:
    text = "plastic spoons"
    return KeywordIdentity(
        keyword_id=keyword_id("US", "en-us", text),
        marketplace="US",
        locale="en-us",
        normalized_text=text,
        raw_text=text,
    )


def make_relationship(
    *, direction: RelationshipDirection = RelationshipDirection.KEYWORD_TO_PRODUCT
) -> ProductKeywordRelationshipObservation:
    metric = make_metric()
    product = ProductIdentity(
        product_id=product_id("US", "B0G2Q22W6D"),
        marketplace="US",
        asin="B0G2Q22W6D",
        parent_asin=None,
        identity_status="CONFIRMED",
    )
    keyword = make_keyword()
    return ProductKeywordRelationshipObservation(
        semantic_observation_id="sem:query-test",
        observation_id="obs:query-test",
        observation_kind=ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP,
        subject=SubjectRef(
            subject_type=SubjectType.PRODUCT_KEYWORD_RELATIONSHIP,
            subject_id="relationship:query-test",
            marketplace="US",
        ),
        evidence_type=EvidenceType.OBSERVED,
        value=present_number(1, unit_code="rank"),
        scope=Scope(
            scope_type=ScopeType.ASIN,
            scope_status=ScopeStatus.CONFIRMED,
            scope_subject_id=product.product_id,
        ),
        time=time_window(),
        provenance=replace(
            metric.provenance,
            source_tool="get_keyword_asin_analysis",
            source_field="data.list[0]",
            source_record_identity="query-test",
        ),
        quality_issue_ids=(),
        result_status=ResultStatus.POPULATED,
        relationship_id="rel:query-test",
        product=product,
        keyword=keyword,
        direction=direction,
        relationship_type=RelationshipType.RANK,
        channel=Channel.ORGANIC,
        query_result_status=ResultStatus.POPULATED,
        rank={"position": 1},
    )


def make_query_execution(
    *,
    outcome: QueryExecutionOutcome,
    relationship: ProductKeywordRelationshipObservation | None = None,
    direction: RelationshipDirection = RelationshipDirection.KEYWORD_TO_PRODUCT,
) -> DirectionalQueryExecutionRecord:
    metric = make_metric()
    keyword = (
        relationship.keyword
        if relationship is not None
        else make_keyword()
    )
    product = (
        relationship.product
        if relationship is not None
        else make_relationship().product
    )
    provenance = (
        relationship.provenance
        if relationship is not None
        else replace(
            metric.provenance,
            source_tool="get_keyword_asin_analysis",
            source_field="data.list",
            source_record_identity=keyword.keyword_id,
        )
    )
    payload = {
        "query_keyword": keyword if direction is RelationshipDirection.KEYWORD_TO_PRODUCT else None,
        "query_product": product if direction is RelationshipDirection.PRODUCT_TO_KEYWORD else None,
        "direction": direction,
        "outcome": outcome,
        "related_relationship_observation_ids": (
            (relationship.observation_id,) if relationship is not None else ()
        ),
        "provenance": provenance,
        "quality_issue_ids": (),
    }
    return DirectionalQueryExecutionRecord(
        query_execution_id=query_execution_id(**payload),
        **payload,
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


class DirectionalQueryExecutionTests(unittest.TestCase):
    def test_explicit_empty_is_first_class_strict_and_legacy_compatible(self) -> None:
        record = make_query_execution(outcome=QueryExecutionOutcome.EXPLICIT_EMPTY)
        run = replace(
            make_run(make_metric()),
            output_observation_ids=(),
            output_query_execution_ids=(record.query_execution_id,),
        )
        bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(RAW_ID,),
            transformation_runs=(run,),
            observations=(),
            conflicts=(),
            resolutions=(),
            quality_issues=(),
            query_execution_records=(record,),
        )
        payload = bundle.to_dict()
        self.assertEqual(payload["query_execution_records"][0]["outcome"], "EXPLICIT_EMPTY")
        self.assertEqual(CanonicalEvidenceBundle.from_dict(payload).to_dict(), payload)

        legacy = json.loads(json.dumps(payload))
        legacy.pop("query_execution_records")
        legacy["transformation_runs"][0].pop("output_query_execution_ids")
        legacy["transformation_runs"][0]["status"] = "PARTIAL"
        restored = CanonicalEvidenceBundle.from_dict(legacy)
        self.assertEqual(restored.query_execution_records, ())
        self.assertEqual(restored.transformation_runs[0].output_query_execution_ids, ())

    def test_populated_query_cross_references_relationship_and_run(self) -> None:
        relationship = make_relationship()
        record = make_query_execution(
            outcome=QueryExecutionOutcome.RESULTS_RETURNED,
            relationship=relationship,
        )
        run = replace(
            make_run(make_metric()),
            output_observation_ids=(relationship.observation_id,),
            output_query_execution_ids=(record.query_execution_id,),
        )
        bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(RAW_ID,),
            transformation_runs=(run,),
            observations=(relationship,),
            conflicts=(),
            resolutions=(),
            quality_issues=(),
            query_execution_records=(record,),
        )
        self.assertIs(bundle.validate(), bundle)

        wrong_direction = replace(
            relationship,
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
        )
        with self.assertRaisesRegex(ContractValidationError, "direction mismatch"):
            replace(bundle, observations=(wrong_direction,))

    def test_outcomes_and_query_subjects_are_strict(self) -> None:
        empty = make_query_execution(outcome=QueryExecutionOutcome.EXPLICIT_EMPTY)
        unknown = make_query_execution(outcome=QueryExecutionOutcome.OUTCOME_UNKNOWN)
        failed = make_query_execution(outcome=QueryExecutionOutcome.EXECUTION_FAILED)
        self.assertEqual(
            {empty.outcome, unknown.outcome, failed.outcome},
            {
                QueryExecutionOutcome.EXPLICIT_EMPTY,
                QueryExecutionOutcome.OUTCOME_UNKNOWN,
                QueryExecutionOutcome.EXECUTION_FAILED,
            },
        )
        with self.assertRaisesRegex(ContractValidationError, "requires relationship observations"):
            replace(empty, outcome=QueryExecutionOutcome.RESULTS_RETURNED)
        with self.assertRaisesRegex(ContractValidationError, "requires only query_keyword"):
            replace(empty, query_product=make_relationship().product)
        with self.assertRaisesRegex(ContractValidationError, "query_execution_id must equal"):
            replace(empty, query_execution_id="query-execution:forged")

        reverse_relationship = make_relationship(
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD
        )
        reverse = make_query_execution(
            outcome=QueryExecutionOutcome.RESULTS_RETURNED,
            relationship=reverse_relationship,
            direction=RelationshipDirection.PRODUCT_TO_KEYWORD,
        )
        self.assertIsNone(reverse.query_keyword)
        self.assertEqual(reverse.query_product, reverse_relationship.product)
        with self.assertRaisesRegex(ContractValidationError, "requires only query_product"):
            replace(reverse, query_product=None)
        with self.assertRaisesRegex(ContractValidationError, "outcome must be"):
            replace(empty, outcome="EXPLICIT_EMPTY")

    def test_query_identity_is_deterministic_and_collections_are_immutable(self) -> None:
        relationship = make_relationship()
        second = replace(relationship, observation_id="obs:query-test-second")
        mutable_related = [second.observation_id, relationship.observation_id]
        mutable_issues = ["issue:second", "issue:first"]
        payload = {
            "query_keyword": relationship.keyword,
            "query_product": None,
            "direction": RelationshipDirection.KEYWORD_TO_PRODUCT,
            "outcome": QueryExecutionOutcome.RESULTS_RETURNED,
            "related_relationship_observation_ids": mutable_related,
            "provenance": relationship.provenance,
            "quality_issue_ids": mutable_issues,
        }
        first = DirectionalQueryExecutionRecord(
            query_execution_id=query_execution_id(**payload),
            **payload,
        )
        reversed_payload = {
            **payload,
            "related_relationship_observation_ids": tuple(reversed(mutable_related)),
            "quality_issue_ids": tuple(reversed(mutable_issues)),
        }
        replay = DirectionalQueryExecutionRecord(
            query_execution_id=query_execution_id(**reversed_payload),
            **reversed_payload,
        )
        self.assertTrue(first.query_execution_id.startswith("qex:"))
        self.assertEqual(first, replay)
        mutable_related.append("obs:caller-mutation")
        mutable_issues.append("issue:caller-mutation")
        self.assertNotIn("obs:caller-mutation", first.related_relationship_observation_ids)
        self.assertNotIn("issue:caller-mutation", first.quality_issue_ids)
        self.assertIsInstance(first.related_relationship_observation_ids, tuple)
        self.assertIsInstance(first.quality_issue_ids, tuple)

        records = [make_query_execution(outcome=QueryExecutionOutcome.EXPLICIT_EMPTY)]
        empty_bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(RAW_ID,),
            transformation_runs=(
                replace(
                    make_run(make_metric()),
                    output_observation_ids=(),
                    output_query_execution_ids=(records[0].query_execution_id,),
                ),
            ),
            observations=(), conflicts=(), resolutions=(), quality_issues=(),
            query_execution_records=records,
        )
        records.clear()
        self.assertEqual(len(empty_bundle.query_execution_records), 1)
        self.assertIsInstance(empty_bundle.query_execution_records, tuple)

    def test_query_serialization_fails_closed(self) -> None:
        record = make_query_execution(outcome=QueryExecutionOutcome.EXPLICIT_EMPTY)
        payload = record.to_dict()
        for key in ("query_execution_id", "direction", "outcome", "provenance"):
            missing = json.loads(json.dumps(payload))
            missing.pop(key)
            with self.assertRaisesRegex(ContractValidationError, "required"):
                DirectionalQueryExecutionRecord.from_dict(missing)

        unknown = json.loads(json.dumps(payload))
        unknown["provider_payload"] = {}
        with self.assertRaisesRegex(ContractValidationError, "unknown fields"):
            DirectionalQueryExecutionRecord.from_dict(unknown)

        invalid_enum = json.loads(json.dumps(payload))
        invalid_enum["outcome"] = "EMPTY_OR_MAYBE_UNKNOWN"
        with self.assertRaisesRegex(ContractValidationError, "invalid value"):
            DirectionalQueryExecutionRecord.from_dict(invalid_enum)

        wrong_primitive = json.loads(json.dumps(payload))
        wrong_primitive["query_keyword"]["raw_text"] = True
        with self.assertRaisesRegex(ContractValidationError, "must be a string"):
            DirectionalQueryExecutionRecord.from_dict(wrong_primitive)

        with self.assertRaises(ContractValidationError):
            query_execution_id(
                query_keyword=record.query_keyword,
                query_product=None,
                direction=record.direction,
                outcome=record.outcome,
                related_relationship_observation_ids=(1,),
                provenance=record.provenance,
                quality_issue_ids=(),
            )

    def test_query_wrong_type_subject_and_outcome_reference_rules(self) -> None:
        empty = make_query_execution(outcome=QueryExecutionOutcome.EXPLICIT_EMPTY)
        with self.assertRaisesRegex(ContractValidationError, "requires only query_keyword"):
            replace(empty, query_keyword=make_relationship().product)
        with self.assertRaisesRegex(ContractValidationError, "cannot reference"):
            replace(
                empty,
                related_relationship_observation_ids=("obs:should-not-exist",),
                query_execution_id=query_execution_id(
                    query_keyword=empty.query_keyword,
                    query_product=None,
                    direction=empty.direction,
                    outcome=empty.outcome,
                    related_relationship_observation_ids=("obs:should-not-exist",),
                    provenance=empty.provenance,
                    quality_issue_ids=(),
                ),
            )

        absent_bundle = CanonicalEvidenceBundle(
            raw_evidence_references=(),
            transformation_runs=(), observations=(), conflicts=(), resolutions=(),
            quality_issues=(), query_execution_records=(),
        )
        self.assertEqual(absent_bundle.query_execution_records, ())
        self.assertNotEqual(empty.outcome, QueryExecutionOutcome.OUTCOME_UNKNOWN)
        self.assertNotEqual(empty.outcome, QueryExecutionOutcome.EXECUTION_FAILED)

    def test_query_cross_reference_orphans_fail_closed(self) -> None:
        record = make_query_execution(outcome=QueryExecutionOutcome.EXPLICIT_EMPTY)
        run = replace(
            make_run(make_metric()),
            output_observation_ids=(),
            output_query_execution_ids=(record.query_execution_id,),
        )
        with self.assertRaisesRegex(ContractValidationError, "no transformation run"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(),
                observations=(), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(record,),
            )
        with self.assertRaisesRegex(ContractValidationError, "does not list query execution"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(
                    replace(
                        run,
                        status=TransformationStatus.PARTIAL,
                        output_query_execution_ids=(),
                    ),
                ),
                observations=(), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(record,),
            )
        with self.assertRaisesRegex(ContractValidationError, "unknown raw evidence"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(),
                transformation_runs=(run,),
                observations=(), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(record,),
            )

    def test_query_cross_reference_types_subjects_and_lineage_fail_closed(self) -> None:
        metric = make_metric()
        wrong_type_payload = {
            "query_keyword": make_keyword(),
            "query_product": None,
            "direction": RelationshipDirection.KEYWORD_TO_PRODUCT,
            "outcome": QueryExecutionOutcome.RESULTS_RETURNED,
            "related_relationship_observation_ids": (metric.observation_id,),
            "provenance": metric.provenance,
            "quality_issue_ids": (),
        }
        wrong_type = DirectionalQueryExecutionRecord(
            query_execution_id=query_execution_id(**wrong_type_payload),
            **wrong_type_payload,
        )
        wrong_type_run = replace(
            make_run(metric),
            output_query_execution_ids=(wrong_type.query_execution_id,),
        )
        with self.assertRaisesRegex(ContractValidationError, "non-relationship observation"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(wrong_type_run,), observations=(metric,),
                conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(wrong_type,),
            )

        orphan_payload = {
            **wrong_type_payload,
            "related_relationship_observation_ids": ("obs:missing-relationship",),
        }
        orphan = DirectionalQueryExecutionRecord(
            query_execution_id=query_execution_id(**orphan_payload),
            **orphan_payload,
        )
        with self.assertRaisesRegex(ContractValidationError, "unknown relationship observation"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(
                    replace(
                        wrong_type_run,
                        output_observation_ids=(),
                        output_query_execution_ids=(orphan.query_execution_id,),
                    ),
                ),
                observations=(), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(orphan,),
            )

        relationship = make_relationship()
        different_keyword_text = "plastic forks"
        different_keyword = KeywordIdentity(
            keyword_id=keyword_id("US", "en-us", different_keyword_text),
            marketplace="US", locale="en-us",
            normalized_text=different_keyword_text,
            raw_text=different_keyword_text,
        )
        subject_payload = {
            "query_keyword": different_keyword,
            "query_product": None,
            "direction": RelationshipDirection.KEYWORD_TO_PRODUCT,
            "outcome": QueryExecutionOutcome.RESULTS_RETURNED,
            "related_relationship_observation_ids": (relationship.observation_id,),
            "provenance": relationship.provenance,
            "quality_issue_ids": (),
        }
        subject_mismatch = DirectionalQueryExecutionRecord(
            query_execution_id=query_execution_id(**subject_payload),
            **subject_payload,
        )
        relationship_run = replace(
            make_run(metric),
            output_observation_ids=(relationship.observation_id,),
            output_query_execution_ids=(subject_mismatch.query_execution_id,),
        )
        with self.assertRaisesRegex(ContractValidationError, "keyword subject mismatch"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,), transformation_runs=(relationship_run,),
                observations=(relationship,), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(subject_mismatch,),
            )

        empty = make_query_execution(outcome=QueryExecutionOutcome.EXPLICIT_EMPTY)
        base_run = replace(
            make_run(metric),
            output_observation_ids=(),
            output_query_execution_ids=(empty.query_execution_id,),
        )
        for field_name, changed_value, message in (
            ("mapping_version", "different_mapping_v2", "mismatched mapping_version"),
            ("collection_run_id", "collection:sorftime:OTHER", "mismatched collection_run_id"),
        ):
            changed_transform = replace(
                empty.provenance.transformation,
                **{field_name: changed_value},
            )
            changed_provenance = replace(empty.provenance, transformation=changed_transform)
            changed_payload = {
                "query_keyword": empty.query_keyword,
                "query_product": None,
                "direction": empty.direction,
                "outcome": empty.outcome,
                "related_relationship_observation_ids": (),
                "provenance": changed_provenance,
                "quality_issue_ids": (),
            }
            changed = DirectionalQueryExecutionRecord(
                query_execution_id=query_execution_id(**changed_payload),
                **changed_payload,
            )
            with self.assertRaisesRegex(ContractValidationError, message):
                CanonicalEvidenceBundle(
                    raw_evidence_references=(RAW_ID,),
                    transformation_runs=(
                        replace(base_run, output_query_execution_ids=(changed.query_execution_id,)),
                    ),
                    observations=(), conflicts=(), resolutions=(), quality_issues=(),
                    query_execution_records=(changed,),
                )

        issue_payload = {
            "query_keyword": empty.query_keyword,
            "query_product": None,
            "direction": empty.direction,
            "outcome": empty.outcome,
            "related_relationship_observation_ids": (),
            "provenance": empty.provenance,
            "quality_issue_ids": ("issue:missing",),
        }
        issue_orphan = DirectionalQueryExecutionRecord(
            query_execution_id=query_execution_id(**issue_payload),
            **issue_payload,
        )
        with self.assertRaisesRegex(ContractValidationError, "unknown quality issue"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(
                    replace(base_run, output_query_execution_ids=(issue_orphan.query_execution_id,)),
                ),
                observations=(), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(issue_orphan,),
            )

        with self.assertRaisesRegex(ContractValidationError, "duplicate query_execution_id"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,), transformation_runs=(base_run,),
                observations=(), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(empty, empty),
            )
        with self.assertRaisesRegex(ContractValidationError, "mismatched transformation_status"):
            CanonicalEvidenceBundle(
                raw_evidence_references=(RAW_ID,),
                transformation_runs=(replace(base_run, status=TransformationStatus.PARTIAL),),
                observations=(), conflicts=(), resolutions=(), quality_issues=(),
                query_execution_records=(empty,),
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
