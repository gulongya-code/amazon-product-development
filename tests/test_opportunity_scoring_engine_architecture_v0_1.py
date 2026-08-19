from __future__ import annotations

from dataclasses import replace

import pytest

from amazon_product_intelligence.opportunity_scoring import (
    BUSINESS_DECISION_REQUIRED,
    CompletenessLevel,
    CompletenessResult,
    ConfidenceLevel,
    ConfidenceResult,
    DimensionResult,
    EvidenceReference,
    ExplanationRecord,
    InputQuality,
    MetricInput,
    MetricInputStatus,
    OpportunityDimension,
    OpportunityScoringEngineInput,
    OpportunityScoringEngineResult,
    OpportunityScoringValidationError,
    ProductIdentityInput,
    ProvenanceReference,
    ScoringConfigurationStatus,
    ScoringEngine,
    ScoringState,
)


TIMESTAMP = "2026-08-19T04:00:00Z"


def provenance() -> ProvenanceReference:
    return ProvenanceReference(
        provenance_id="provenance:review-count:001",
        canonical_field="metric.review_count",
        source="sorftime",
        snapshot_id="snapshot-001",
        timestamp=TIMESTAMP,
        source_field="data.review_count",
        raw_evidence_id="raw:sorftime:001",
    )


def evidence() -> EvidenceReference:
    return EvidenceReference(
        metric_id="metric.review_count",
        source="sorftime",
        snapshot_id="snapshot-001",
        timestamp=TIMESTAMP,
        provenance_id="provenance:review-count:001",
    )


def engine_input() -> OpportunityScoringEngineInput:
    metric = MetricInput(
        metric_id="metric.review_count",
        dimension=OpportunityDimension.COMPETITION_ACCESSIBILITY,
        value=1500,
        status=MetricInputStatus.AVAILABLE,
        source="sorftime",
        snapshot_id="snapshot-001",
        timestamp=TIMESTAMP,
        confidence=ConfidenceLevel.HIGH,
        completeness=CompletenessLevel.COMPLETE,
        provenance_id="provenance:review-count:001",
    )
    return OpportunityScoringEngineInput(
        product_identity=ProductIdentityInput(
            product_id="product:US:B0G2VV4RBW",
            asin="B0G2VV4RBW",
            marketplace="US",
        ),
        metrics={metric.metric_id: metric},
        provenance=(provenance(),),
        quality=InputQuality(
            confidence=ConfidenceLevel.MEDIUM,
            completeness=CompletenessLevel.PARTIAL,
            missing_inputs=("TOP_PRODUCT_COHORT",),
            limitations=("Observed products are not a governed TOP cohort.",),
        ),
    )


def dimension_results(*, conflict: bool = False) -> tuple[DimensionResult, ...]:
    return (
        DimensionResult(
            dimension=OpportunityDimension.DEMAND_POTENTIAL,
            result_status=ScoringState.PENDING,
            evidence=(),
            missing_inputs=("DEMAND_CONFIGURATION",),
            risks=(),
            conflict_ids=(),
        ),
        DimensionResult(
            dimension=OpportunityDimension.COMPETITION_ACCESSIBILITY,
            result_status=ScoringState.CONFLICT if conflict else ScoringState.PARTIAL,
            evidence=(evidence(),),
            missing_inputs=() if conflict else ("TOP_PRODUCT_COHORT",),
            risks=(),
            conflict_ids=("conflict:rating:001",) if conflict else (),
        ),
        DimensionResult(
            dimension=OpportunityDimension.PRODUCT_ECONOMICS_READINESS,
            result_status=ScoringState.INSUFFICIENT_DATA,
            evidence=(),
            missing_inputs=("PROFITABILITY_INPUTS",),
            risks=(),
            conflict_ids=(),
        ),
    )


def explanations() -> tuple[ExplanationRecord, ...]:
    return (
        ExplanationRecord(
            explanation_id="explanation:demand:001",
            dimension=OpportunityDimension.DEMAND_POTENTIAL,
            summary="Demand evidence awaits governed configuration and compatible inputs.",
            evidence=(),
            positive_factors=(),
            negative_factors=(),
            risks=("DEMAND_CONFIGURATION",),
        ),
        ExplanationRecord(
            explanation_id="explanation:competition:001",
            dimension=OpportunityDimension.COMPETITION_ACCESSIBILITY,
            summary="Review evidence is present but the TOP product cohort is unresolved.",
            evidence=(evidence(),),
            positive_factors=(),
            negative_factors=("High incumbent review evidence is visible as context only.",),
            risks=("TOP_PRODUCT_COHORT",),
        ),
        ExplanationRecord(
            explanation_id="explanation:economics:001",
            dimension=OpportunityDimension.PRODUCT_ECONOMICS_READINESS,
            summary="Economic readiness cannot be evaluated without governed cost inputs.",
            evidence=(),
            positive_factors=(),
            negative_factors=(),
            risks=("PROFITABILITY_INPUTS",),
        ),
    )


def engine_result(*, conflict: bool = False) -> OpportunityScoringEngineResult:
    return OpportunityScoringEngineResult(
        result_status=ScoringState.CONFLICT if conflict else ScoringState.PENDING,
        score_version=BUSINESS_DECISION_REQUIRED,
        dimension_results=dimension_results(conflict=conflict),
        confidence=ConfidenceResult(
            level=ConfidenceLevel.LOW,
            reasons=("Required inputs and business configuration remain unresolved.",),
        ),
        completeness=CompletenessResult(
            level=CompletenessLevel.CONFLICT if conflict else CompletenessLevel.PARTIAL,
            available_inputs=("metric.review_count",),
            missing_inputs=("PROFITABILITY_INPUTS",),
            pending_inputs=("SCORING_CONFIGURATION",),
            conflict_ids=("conflict:rating:001",) if conflict else (),
        ),
        risks=(),
        missing_inputs=("SCORING_CONFIGURATION", "PROFITABILITY_INPUTS"),
        provenance=(provenance(),),
        explanations=explanations(),
        configuration=ScoringConfigurationStatus(),
        score_value=None,
    )


def test_input_schema_validates_and_round_trips_product_metrics_quality_and_provenance() -> None:
    request = engine_input()
    restored = OpportunityScoringEngineInput.from_dict(request.to_dict())

    assert restored.product_identity.asin == "B0G2VV4RBW"
    assert restored.metrics["metric.review_count"].value == 1500
    assert restored.metrics["metric.review_count"].confidence is ConfidenceLevel.HIGH
    assert restored.provenance[0].snapshot_id == "snapshot-001"


def test_input_schema_rejects_missing_source_and_mismatched_provenance() -> None:
    payload = engine_input().to_dict()
    del payload["metrics"]["metric.review_count"]["source"]
    with pytest.raises(OpportunityScoringValidationError):
        OpportunityScoringEngineInput.from_dict(payload)

    metric = engine_input().metrics["metric.review_count"]
    with pytest.raises(OpportunityScoringValidationError, match="provenance"):
        OpportunityScoringEngineInput(
            product_identity=engine_input().product_identity,
            metrics={metric.metric_id: replace(metric, snapshot_id="different")},
            provenance=(provenance(),),
            quality=engine_input().quality,
        )


def test_output_schema_requires_three_dimensions_and_preserves_provenance() -> None:
    result = engine_result()
    restored = OpportunityScoringEngineResult.from_dict(result.to_dict())

    assert restored.result_status is ScoringState.PENDING
    assert restored.score_value is None
    assert restored.score_version == BUSINESS_DECISION_REQUIRED
    assert len(restored.dimension_results) == 3
    assert restored.provenance[0] == provenance()
    assert restored.to_dict()["provenance"][0]["source"] == "sorftime"


def test_missing_states_require_explicit_missing_inputs_and_never_zero_fill() -> None:
    with pytest.raises(OpportunityScoringValidationError, match="requires missing inputs"):
        DimensionResult(
            dimension=OpportunityDimension.PRODUCT_ECONOMICS_READINESS,
            result_status=ScoringState.INSUFFICIENT_DATA,
            evidence=(),
            missing_inputs=(),
            risks=(),
            conflict_ids=(),
        )
    with pytest.raises(OpportunityScoringValidationError, match="must not contain a selected value"):
        MetricInput(
            metric_id="metric.price",
            dimension=OpportunityDimension.PRODUCT_ECONOMICS_READINESS,
            value=0,
            status=MetricInputStatus.MISSING,
            source="xiyou",
            snapshot_id="snapshot-002",
            timestamp=TIMESTAMP,
            confidence=ConfidenceLevel.UNKNOWN,
            completeness=CompletenessLevel.INSUFFICIENT,
            provenance_id="provenance:price:002",
        )


def test_conflict_state_requires_conflict_references_and_survives_output() -> None:
    with pytest.raises(OpportunityScoringValidationError, match="requires conflict_ids"):
        DimensionResult(
            dimension=OpportunityDimension.COMPETITION_ACCESSIBILITY,
            result_status=ScoringState.CONFLICT,
            evidence=(evidence(),),
            missing_inputs=(),
            risks=(),
            conflict_ids=(),
        )

    result = engine_result(conflict=True)
    competition = next(
        item
        for item in result.dimension_results
        if item.dimension is OpportunityDimension.COMPETITION_ACCESSIBILITY
    )
    assert result.result_status is ScoringState.CONFLICT
    assert competition.conflict_ids == ("conflict:rating:001",)


def test_output_rejects_numeric_score_or_missing_explanations() -> None:
    with pytest.raises(OpportunityScoringValidationError, match="final score"):
        replace(engine_result(), score_value=80)
    with pytest.raises(OpportunityScoringValidationError, match="without explanations"):
        replace(engine_result(), explanations=())


def test_configuration_rejects_weights_thresholds_and_formulas() -> None:
    assert ScoringConfigurationStatus().to_dict() == {
        "score_version": BUSINESS_DECISION_REQUIRED,
        "dimension_weights": BUSINESS_DECISION_REQUIRED,
        "thresholds": BUSINESS_DECISION_REQUIRED,
        "aggregation_formula": BUSINESS_DECISION_REQUIRED,
        "normalization_parameters": BUSINESS_DECISION_REQUIRED,
    }
    with pytest.raises(OpportunityScoringValidationError, match="dimension_weights"):
        ScoringConfigurationStatus(dimension_weights={"demand": 0.5})


class StubDimensionEvaluator:
    def evaluate(self, request, dimension):
        return next(item for item in dimension_results() if item.dimension is dimension)


class StubQualityEvaluator:
    def evaluate(self, request, dimensions):
        return (
            ConfidenceResult(
                level=ConfidenceLevel.LOW,
                reasons=("Business configuration remains unresolved.",),
            ),
            CompletenessResult(
                level=CompletenessLevel.PARTIAL,
                available_inputs=("metric.review_count",),
                missing_inputs=("PROFITABILITY_INPUTS",),
                pending_inputs=(),
                conflict_ids=(),
            ),
        )


class StubRiskEvaluator:
    def evaluate(self, request, dimensions):
        return ()


class StubExplanationBuilder:
    def build(self, request, dimensions, risks):
        return explanations()


def test_engine_only_orchestrates_and_keeps_business_score_non_executable() -> None:
    result = ScoringEngine(
        dimension_evaluator=StubDimensionEvaluator(),
        quality_evaluator=StubQualityEvaluator(),
        risk_evaluator=StubRiskEvaluator(),
        explanation_builder=StubExplanationBuilder(),
    ).evaluate(engine_input())

    assert result.result_status is ScoringState.PENDING
    assert result.score_value is None
    assert result.score_version == BUSINESS_DECISION_REQUIRED
    assert result.missing_inputs == (
        "TOP_PRODUCT_COHORT",
        "PROFITABILITY_INPUTS",
        "SCORING_CONFIGURATION",
    )
