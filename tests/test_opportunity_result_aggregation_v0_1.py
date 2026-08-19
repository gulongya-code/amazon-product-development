from __future__ import annotations

import json
from typing import Any

import pytest

from amazon_product_intelligence.opportunity_scoring.engine_contracts import (
    BUSINESS_DECISION_REQUIRED,
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
    EconomicsReadinessEvaluator,
)
from amazon_product_intelligence.opportunity_scoring.result_aggregator import (
    OpportunityResult,
    OpportunityResultAggregator,
)


TIMESTAMP = "2026-08-19T04:00:00Z"


def evaluator_result(
    evaluator: Any,
    *,
    missing: tuple[str, ...] = (),
    conflict_review: bool = False,
    limitation: str | None = None,
):
    values = {
        metric_id: index
        for index, metric_id in enumerate(evaluator.supported_metrics, start=1)
        if metric_id not in missing
    }
    sources: dict[str, str] = {}
    if conflict_review:
        values.pop("top_asin_review", None)
        values["top_asin_review"] = 1200
        values["metric.review_count"] = 1800
        sources = {
            "top_asin_review": "xiyou",
            "metric.review_count": "sorftime",
        }

    metrics: dict[str, MetricInput] = {}
    provenance: list[ProvenanceReference] = []
    for index, (metric_id, value) in enumerate(values.items(), start=1):
        source = sources.get(metric_id, "fixture")
        provenance_id = f"provenance:{evaluator.dimension.value}:{metric_id}:{index}"
        snapshot_id = f"snapshot:{evaluator.dimension.value}:{index}"
        metrics[metric_id] = MetricInput(
            metric_id=metric_id,
            dimension=evaluator.dimension,
            value=value,
            status=MetricInputStatus.AVAILABLE,
            source=source,
            snapshot_id=snapshot_id,
            timestamp=TIMESTAMP,
            confidence=ConfidenceLevel.HIGH,
            completeness=CompletenessLevel.COMPLETE,
            provenance_id=provenance_id,
        )
        provenance.append(
            ProvenanceReference(
                provenance_id=provenance_id,
                canonical_field=metric_id,
                source=source,
                snapshot_id=snapshot_id,
                timestamp=TIMESTAMP,
                source_field=f"fixture.{metric_id}",
                raw_evidence_id=f"raw:{evaluator.dimension.value}:{index}",
            )
        )
    request = OpportunityScoringEngineInput(
        product_identity=ProductIdentityInput(
            product_id="product:US:B0G2VV4RBW",
            asin="B0G2VV4RBW",
            marketplace="US",
        ),
        metrics=metrics,
        provenance=tuple(provenance),
        quality=InputQuality(
            confidence=ConfidenceLevel.HIGH,
            completeness=CompletenessLevel.COMPLETE,
            conflict_ids=("conflict:review-count:001",) if conflict_review else (),
            limitations=(limitation,) if limitation else (),
        ),
    )
    return evaluator.evaluate(request)


def aggregate(*results):
    return OpportunityResultAggregator().aggregate(*results)


def test_three_dimensions_aggregate_in_canonical_order() -> None:
    demand = evaluator_result(DemandPotentialEvaluator())
    competition = evaluator_result(
        CompetitionAccessibilityEvaluator(),
        missing=("brand_concentration",),
    )
    economics = evaluator_result(
        EconomicsReadinessEvaluator(),
        missing=("product_cost", "logistics_cost"),
    )

    result = aggregate(economics, demand, competition)

    assert result.result_status is ScoringState.PARTIAL
    assert tuple(item.dimension for item in result.dimension_results) == tuple(
        OpportunityDimension
    )
    assert tuple(item.result_status for item in result.dimension_results) == (
        ScoringState.READY,
        ScoringState.PARTIAL,
        ScoringState.INSUFFICIENT_DATA,
    )


def test_conflict_status_propagates_to_opportunity_result() -> None:
    result = aggregate(
        evaluator_result(DemandPotentialEvaluator()),
        evaluator_result(
            CompetitionAccessibilityEvaluator(), conflict_review=True
        ),
        evaluator_result(EconomicsReadinessEvaluator()),
    )

    assert result.result_status is ScoringState.CONFLICT
    assert "conflict:review-count:001" in result.completeness.conflict_ids
    assert any(item.code == "SOURCE_CONFLICT" for item in result.risks)


def test_insufficient_data_propagates_when_no_dimension_is_partial() -> None:
    result = aggregate(
        evaluator_result(DemandPotentialEvaluator()),
        evaluator_result(CompetitionAccessibilityEvaluator()),
        evaluator_result(
            EconomicsReadinessEvaluator(),
            missing=("product_cost", "logistics_cost"),
        ),
    )

    assert result.result_status is ScoringState.INSUFFICIENT_DATA
    economics = result.dimension_results[2]
    assert economics.result_status is ScoringState.INSUFFICIENT_DATA
    assert "product_cost" in result.missing_inputs
    assert "logistics_cost" in result.missing_inputs


def test_missing_inputs_are_preserved_without_filling_values() -> None:
    result = aggregate(
        evaluator_result(
            DemandPotentialEvaluator(), missing=("keyword_trend", "seasonality")
        ),
        evaluator_result(
            CompetitionAccessibilityEvaluator(),
            missing=("brand_concentration",),
        ),
        evaluator_result(EconomicsReadinessEvaluator()),
    )

    assert result.result_status is ScoringState.PARTIAL
    assert result.missing_inputs == (
        "keyword_trend",
        "seasonality",
        "brand_concentration",
    )
    assert all(
        metric_id not in dimension.completeness.available_inputs
        for metric_id in result.missing_inputs
        for dimension in result.dimension_results
        if metric_id in dimension.missing_inputs
    )


def test_risks_and_explanations_are_aggregated_unchanged() -> None:
    dimensions = (
        evaluator_result(
            DemandPotentialEvaluator(),
            missing=("keyword_trend",),
            limitation="Demand observation window is incomplete.",
        ),
        evaluator_result(
            CompetitionAccessibilityEvaluator(),
            missing=("brand_concentration",),
        ),
        evaluator_result(EconomicsReadinessEvaluator()),
    )

    result = aggregate(*dimensions)

    expected_risk_ids = {
        risk.risk_id for dimension in dimensions for risk in dimension.risks
    }
    assert {risk.risk_id for risk in result.risks} == expected_risk_ids
    assert result.explanations == tuple(item.explanation for item in dimensions)


def test_final_provenance_retains_evidence_metric_snapshot_and_api_source_chain() -> None:
    result = aggregate(
        evaluator_result(DemandPotentialEvaluator()),
        evaluator_result(CompetitionAccessibilityEvaluator()),
        evaluator_result(EconomicsReadinessEvaluator()),
    )
    provenance = {item.provenance_id: item for item in result.provenance}

    for dimension in result.dimension_results:
        for evidence in dimension.evidence:
            reference = provenance[evidence.provenance_id]
            assert reference.canonical_field == evidence.metric
            assert reference.source == evidence.source
            assert reference.snapshot_id == evidence.snapshot_id
            assert reference.timestamp == evidence.timestamp
            assert reference.raw_evidence_id is not None


def test_opportunity_result_contract_round_trips_with_null_score_and_configuration() -> None:
    result = aggregate(
        evaluator_result(DemandPotentialEvaluator()),
        evaluator_result(CompetitionAccessibilityEvaluator()),
        evaluator_result(EconomicsReadinessEvaluator()),
    )
    restored = OpportunityResult.from_dict(result.to_dict())

    assert restored == result
    assert restored.score_value is None
    assert restored.score_version == BUSINESS_DECISION_REQUIRED
    assert set(restored.configuration.to_dict().values()) == {
        BUSINESS_DECISION_REQUIRED
    }


def test_aggregator_does_not_generate_recommendation_conclusions() -> None:
    result = aggregate(
        evaluator_result(DemandPotentialEvaluator()),
        evaluator_result(CompetitionAccessibilityEvaluator()),
        evaluator_result(EconomicsReadinessEvaluator()),
    )
    serialized = json.dumps(result.to_dict(), ensure_ascii=False).casefold()

    assert "值得开发" not in serialized
    assert "worth developing" not in serialized
    assert "recommended product" not in serialized
    assert "recommendation" not in serialized


def test_aggregator_requires_each_dimension_exactly_once() -> None:
    demand = evaluator_result(DemandPotentialEvaluator())
    competition = evaluator_result(CompetitionAccessibilityEvaluator())

    with pytest.raises(OpportunityScoringValidationError, match="exactly three"):
        aggregate(demand, competition)
    with pytest.raises(OpportunityScoringValidationError, match="exactly once"):
        aggregate(demand, demand, competition)
