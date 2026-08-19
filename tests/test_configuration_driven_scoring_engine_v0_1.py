from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from typing import Any

import pytest

from amazon_product_intelligence.opportunity_scoring.engine_contracts import (
    BUSINESS_DECISION_REQUIRED,
    CompletenessLevel,
    ConfidenceLevel,
    InputQuality,
    MetricInput,
    MetricInputStatus,
    OpportunityScoringEngineInput,
    ProductIdentityInput,
    ProvenanceReference,
)
from amazon_product_intelligence.opportunity_scoring.evaluators import (
    CompetitionAccessibilityEvaluator,
    DemandPotentialEvaluator,
    EconomicsReadinessEvaluator,
)
from amazon_product_intelligence.opportunity_scoring.result_aggregator import (
    OpportunityResultAggregator,
)
from amazon_product_intelligence.opportunity_scoring.scoring import (
    ConfigurationLoadError,
    ConfigurationValidationError,
    ConfigurationValidator,
    OpportunityScoreResult,
    ScoreCalculator,
    ScoreStatus,
    ScoringConfigurationLoader,
)


TIMESTAMP = "2026-08-19T05:30:00Z"
TEST_CONFIGURATION_ID = "test-only:opportunity-scoring:configuration:v0.1"
FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "opportunity_scoring"
    / "test_only_scoring_configuration_v0_1.json"
)


def configuration_payload() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_configuration(payload: dict[str, Any] | None = None):
    loader = ScoringConfigurationLoader()
    if payload is None:
        return loader.load(FIXTURE, configuration_id=TEST_CONFIGURATION_ID)
    return loader.load_mapping(
        payload,
        configuration_id=payload["configuration_id"],
    )


def evaluated_dimension(evaluator: Any):
    metrics: dict[str, MetricInput] = {}
    provenance: list[ProvenanceReference] = []
    for index, metric_id in enumerate(evaluator.supported_metrics, start=1):
        provenance_id = f"provenance:{evaluator.dimension.value}:{metric_id}"
        snapshot_id = f"snapshot:{evaluator.dimension.value}:{index}"
        metrics[metric_id] = MetricInput(
            metric_id=metric_id,
            dimension=evaluator.dimension,
            value=index,
            status=MetricInputStatus.AVAILABLE,
            source="test-fixture",
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
                source="test-fixture",
                snapshot_id=snapshot_id,
                timestamp=TIMESTAMP,
                source_field=f"test_fixture.{metric_id}",
                raw_evidence_id=f"raw:test-only:{evaluator.dimension.value}:{index}",
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
        ),
    )
    return evaluator.evaluate(request)


def opportunity_result():
    return OpportunityResultAggregator().aggregate(
        (
            evaluated_dimension(DemandPotentialEvaluator()),
            evaluated_dimension(CompetitionAccessibilityEvaluator()),
            evaluated_dimension(EconomicsReadinessEvaluator()),
        )
    )


def test_valid_explicit_test_configuration_calculates_expected_score() -> None:
    configuration = load_configuration()
    result = ScoreCalculator(allow_test_config=True).calculate(
        opportunity_result(), configuration
    )

    assert result.score_status is ScoreStatus.CALCULATED
    assert result.score_value == 80.0
    assert len(result.calculation_trace) == 3
    assert tuple(item.score_value for item in result.calculation_trace) == (
        80.0,
        70.0,
        90.0,
    )


def test_missing_configuration_returns_pending_without_estimated_score() -> None:
    result = ScoreCalculator().calculate(opportunity_result(), None)

    assert result.score_status is ScoreStatus.PENDING_CONFIGURATION
    assert result.score_value is None
    assert result.configuration_id == BUSINESS_DECISION_REQUIRED
    assert result.score_version == BUSINESS_DECISION_REQUIRED
    assert "SCORING_CONFIGURATION" in result.missing_inputs


def test_loader_rejects_missing_or_implicit_configuration_identity() -> None:
    payload = configuration_payload()
    del payload["configuration_id"]
    with pytest.raises(ConfigurationLoadError, match="invalid scoring configuration"):
        ScoringConfigurationLoader().load_mapping(
            payload,
            configuration_id=TEST_CONFIGURATION_ID,
        )

    with pytest.raises(ConfigurationLoadError, match="latest"):
        ScoringConfigurationLoader().load(FIXTURE, configuration_id="latest")


def test_missing_score_version_and_illegal_lifecycle_are_rejected() -> None:
    payload = configuration_payload()
    del payload["score_version"]
    with pytest.raises(ConfigurationLoadError, match="invalid scoring configuration"):
        ScoringConfigurationLoader().load_mapping(
            payload,
            configuration_id=TEST_CONFIGURATION_ID,
        )

    payload = configuration_payload()
    payload["lifecycle_status"] = "UNRECOGNIZED"
    with pytest.raises(ConfigurationLoadError, match="invalid scoring configuration"):
        load_configuration(payload)


def test_unapproved_and_test_only_configuration_are_rejected_for_production() -> None:
    payload = configuration_payload()
    payload["lifecycle_status"] = "DRAFT"
    draft = load_configuration(payload)
    with pytest.raises(ConfigurationValidationError, match="APPROVED or ACTIVE"):
        ScoreCalculator(allow_test_config=True).calculate(
            opportunity_result(), draft
        )

    approved_test_configuration = load_configuration()
    with pytest.raises(ConfigurationValidationError, match="test-only"):
        ScoreCalculator().calculate(
            opportunity_result(), approved_test_configuration
        )


def test_validator_rejects_illegal_weight_and_unknown_metric() -> None:
    payload = configuration_payload()
    payload["dimensions"]["DEMAND_POTENTIAL"]["weight"] = "0.4"
    with pytest.raises(ConfigurationLoadError, match="finite number"):
        load_configuration(payload)

    payload = configuration_payload()
    payload["dimensions"]["DEMAND_POTENTIAL"]["rules"][0][
        "metric_id"
    ] = "unknown_metric"
    configuration = load_configuration(payload)
    with pytest.raises(ConfigurationValidationError, match="unknown metric"):
        ConfigurationValidator().validate(
            configuration, allow_test_config=True
        )


def test_configuration_and_evidence_provenance_are_preserved() -> None:
    configuration = load_configuration()
    source = opportunity_result()
    result = ScoreCalculator(allow_test_config=True).calculate(source, configuration)

    assert result.configuration_id == TEST_CONFIGURATION_ID
    assert result.score_version == "test-only:opportunity-score:v0.1"
    assert result.configuration is not None
    assert result.configuration.configuration_fingerprint == (
        "test-only:not-for-production"
    )
    assert result.provenance == source.provenance
    assert {
        provenance_id
        for dimension in result.calculation_trace
        for rule in dimension.rule_traces
        for provenance_id in rule.evidence_provenance_ids
    } <= {item.provenance_id for item in result.provenance}


def test_business_weights_are_read_from_configuration_not_source_defaults() -> None:
    original = ScoreCalculator(allow_test_config=True).calculate(
        opportunity_result(), load_configuration()
    )
    payload = deepcopy(configuration_payload())
    payload["configuration_id"] = (
        "test-only:opportunity-scoring:configuration:alternative"
    )
    payload["score_version"] = "test-only:opportunity-score:alternative"
    payload["audit"]["configuration_fingerprint"] = "test-only:alternative"
    payload["dimensions"]["DEMAND_POTENTIAL"]["weight"] = 0.1
    payload["dimensions"]["COMPETITION_ACCESSIBILITY"]["weight"] = 0.1
    payload["dimensions"]["PRODUCT_ECONOMICS_READINESS"]["weight"] = 0.8
    alternative = load_configuration(payload)

    changed = ScoreCalculator(allow_test_config=True).calculate(
        opportunity_result(), alternative
    )

    assert original.score_value == 80.0
    assert changed.score_value == 87.0
    assert changed.score_version == "test-only:opportunity-score:alternative"


def test_score_result_serializes_and_round_trips_without_recommendation() -> None:
    result = ScoreCalculator(allow_test_config=True).calculate(
        opportunity_result(), load_configuration()
    )
    restored = OpportunityScoreResult.from_dict(result.to_dict())
    serialized = json.dumps(restored.to_dict(), ensure_ascii=False).casefold()

    assert restored == result
    assert restored.score_value == 80.0
    assert "值得开发" not in serialized
    assert "worth developing" not in serialized
    assert "recommendation" not in serialized
