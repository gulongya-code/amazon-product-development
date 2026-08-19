from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from amazon_product_intelligence.opportunity_scoring.engine_contracts import (
    CompletenessLevel,
    ConfidenceLevel,
    InputQuality,
    MetricInput,
    MetricInputStatus,
    OpportunityDimension,
    OpportunityScoringEngineInput,
    ProductIdentityInput,
    ProvenanceReference,
    ScoringState,
)
from amazon_product_intelligence.opportunity_scoring.errors import (
    OpportunityScoringValidationError,
)
from amazon_product_intelligence.opportunity_scoring.evaluators import (
    CompetitionAccessibilityEvaluator,
    DemandPotentialEvaluator,
    DimensionEvaluationResult,
    EconomicsReadinessEvaluator,
)


TIMESTAMP = "2026-08-19T03:00:00Z"


def engine_input(
    dimension: OpportunityDimension,
    values: dict[str, Any],
    *,
    sources: dict[str, str] | None = None,
    statuses: dict[str, MetricInputStatus] | None = None,
    conflict_ids: tuple[str, ...] = (),
    limitations: tuple[str, ...] = (),
) -> OpportunityScoringEngineInput:
    sources = sources or {}
    statuses = statuses or {}
    metrics: dict[str, MetricInput] = {}
    provenance: list[ProvenanceReference] = []
    for index, (metric_id, value) in enumerate(values.items(), start=1):
        source = sources.get(metric_id, "fixture")
        provenance_id = f"provenance:{metric_id}:{index}"
        status = statuses.get(metric_id, MetricInputStatus.AVAILABLE)
        metric = MetricInput(
            metric_id=metric_id,
            dimension=dimension,
            value=value,
            status=status,
            source=source,
            snapshot_id=f"snapshot-{index:03d}",
            timestamp=TIMESTAMP,
            confidence=ConfidenceLevel.HIGH,
            completeness=(
                CompletenessLevel.CONFLICT
                if status is MetricInputStatus.CONFLICT
                else CompletenessLevel.COMPLETE
            ),
            provenance_id=provenance_id,
        )
        metrics[metric_id] = metric
        provenance.append(
            ProvenanceReference(
                provenance_id=provenance_id,
                canonical_field=metric_id,
                source=source,
                snapshot_id=metric.snapshot_id,
                timestamp=TIMESTAMP,
                source_field=f"fixture.{metric_id}",
            )
        )
    return OpportunityScoringEngineInput(
        product_identity=ProductIdentityInput(
            product_id="product:US:B0G2VV4RBW",
            asin="B0G2VV4RBW",
            marketplace="US",
        ),
        metrics=metrics,
        provenance=tuple(provenance),
        quality=InputQuality(
            confidence=ConfidenceLevel.HIGH,
            completeness=(
                CompletenessLevel.CONFLICT
                if conflict_ids
                else CompletenessLevel.COMPLETE
            ),
            conflict_ids=conflict_ids,
            limitations=limitations,
        ),
    )


def supported_values(evaluator: Any) -> dict[str, Any]:
    return {
        metric_id: index
        for index, metric_id in enumerate(evaluator.supported_metrics, start=1)
    }


def test_demand_complete_input_is_ready_without_inferring_growth() -> None:
    evaluator = DemandPotentialEvaluator()
    result = evaluator.evaluate(
        engine_input(evaluator.dimension, supported_values(evaluator))
    )

    assert isinstance(result, DimensionEvaluationResult)
    assert result.status is ScoringState.READY
    assert result.dimension_name is OpportunityDimension.DEMAND_POTENTIAL
    assert result.missing_inputs == ()
    assert len(result.evidence) == 6
    assert "does not infer growth" in result.explanation.summary


def test_demand_with_volume_but_without_trend_is_partial() -> None:
    evaluator = DemandPotentialEvaluator()
    values = supported_values(evaluator)
    del values["keyword_trend"]

    result = evaluator.evaluate(engine_input(evaluator.dimension, values))

    assert result.status is ScoringState.PARTIAL
    assert "keyword_volume" in result.completeness.available_inputs
    assert "keyword_trend" in result.missing_inputs
    assert not any(
        "is growing" in item.casefold()
        for item in result.explanation.positive_evidence
    )


def test_competition_without_brand_data_is_partial_and_neutral() -> None:
    evaluator = CompetitionAccessibilityEvaluator()
    values = supported_values(evaluator)
    del values["brand_concentration"]

    result = evaluator.evaluate(engine_input(evaluator.dimension, values))

    assert result.status is ScoringState.PARTIAL
    assert "brand_concentration" in result.missing_inputs
    assert "no high/low classification" not in result.explanation.summary
    assert "required context is missing" in result.explanation.summary


def test_competition_detects_source_conflict_without_selecting_a_value() -> None:
    evaluator = CompetitionAccessibilityEvaluator()
    values = supported_values(evaluator)
    del values["top_asin_review"]
    values["top_asin_review"] = 1200
    values["metric.review_count"] = 1800

    result = evaluator.evaluate(
        engine_input(
            evaluator.dimension,
            values,
            sources={
                "top_asin_review": "xiyou",
                "metric.review_count": "sorftime",
            },
            conflict_ids=("conflict:review-count:001",),
        )
    )

    assert result.status is ScoringState.CONFLICT
    assert result.conflict_ids == ("conflict:review-count:001",)
    review_evidence = {
        item.source: item.value
        for item in result.evidence
        if item.metric in {"top_asin_review", "metric.review_count"}
    }
    assert review_evidence == {"xiyou": 1200, "sorftime": 1800}
    assert any(risk.code == "SOURCE_CONFLICT" for risk in result.risks)


def test_economics_without_product_and_logistics_cost_is_insufficient() -> None:
    evaluator = EconomicsReadinessEvaluator()
    values = supported_values(evaluator)
    del values["product_cost"]
    del values["logistics_cost"]

    result = evaluator.evaluate(engine_input(evaluator.dimension, values))

    assert result.status is ScoringState.INSUFFICIENT_DATA
    assert "product_cost" in result.missing_inputs
    assert "logistics_cost" in result.missing_inputs
    assert "required cost evidence" in result.explanation.summary
    assert result.score_value is None


def test_metric_value_and_full_provenance_are_preserved() -> None:
    evaluator = DemandPotentialEvaluator()
    result = evaluator.evaluate(
        engine_input(evaluator.dimension, supported_values(evaluator))
    )
    evidence = result.evidence[0]
    reference = next(
        item
        for item in result.provenance
        if item.provenance_id == evidence.provenance_id
    )

    assert evidence.metric == "keyword_volume"
    assert evidence.value == 1
    assert evidence.source == "fixture"
    assert evidence.snapshot_id == "snapshot-001"
    assert evidence.timestamp == TIMESTAMP
    assert evidence.confidence is ConfidenceLevel.HIGH
    assert reference.canonical_field == evidence.metric


def test_dimension_result_schema_round_trips_rich_evidence() -> None:
    evaluator = DemandPotentialEvaluator()
    result = evaluator.evaluate(
        engine_input(evaluator.dimension, supported_values(evaluator))
    )

    restored = DimensionEvaluationResult.from_dict(result.to_dict())

    assert restored == result
    assert restored.evidence[0].value == 1
    assert restored.explanation.evidence == restored.evidence


def test_evaluator_never_outputs_a_business_score() -> None:
    evaluator = DemandPotentialEvaluator()
    result = evaluator.evaluate(
        engine_input(evaluator.dimension, supported_values(evaluator))
    )
    payload = result.to_dict()

    assert result.score_value is None
    assert payload["score_value"] is None
    assert "score" not in payload
    with pytest.raises(OpportunityScoringValidationError, match="score"):
        replace(result, score_value=80)


def test_explanation_has_positive_missing_and_risk_sections() -> None:
    evaluator = CompetitionAccessibilityEvaluator()
    values = supported_values(evaluator)
    del values["brand_concentration"]
    result = evaluator.evaluate(
        engine_input(
            evaluator.dimension,
            values,
            limitations=("TOP cohort coverage is incomplete.",),
        )
    )

    assert result.explanation.positive_evidence
    assert any(
        "brand_concentration" in item
        for item in result.explanation.missing_evidence
    )
    assert result.explanation.risk
    assert result.explanation.evidence == result.evidence


@pytest.mark.parametrize(
    ("evaluator", "wrong_dimension"),
    (
        (DemandPotentialEvaluator(), OpportunityDimension.COMPETITION_ACCESSIBILITY),
        (
            CompetitionAccessibilityEvaluator(),
            OpportunityDimension.PRODUCT_ECONOMICS_READINESS,
        ),
        (
            EconomicsReadinessEvaluator(),
            OpportunityDimension.DEMAND_POTENTIAL,
        ),
    ),
)
def test_evaluators_share_engine_compatible_interface_and_reject_wrong_dimension(
    evaluator: Any,
    wrong_dimension: OpportunityDimension,
) -> None:
    request = engine_input(evaluator.dimension, supported_values(evaluator))
    assert evaluator.evaluate(request, evaluator.dimension).dimension is evaluator.dimension
    with pytest.raises(OpportunityScoringValidationError, match="only evaluates"):
        evaluator.evaluate(request, wrong_dimension)
