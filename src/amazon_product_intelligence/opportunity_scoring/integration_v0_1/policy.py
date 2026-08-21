"""Explicit policy loading and validation for Candidate opportunity scores."""

from __future__ import annotations

from collections.abc import Mapping
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any

from amazon_product_intelligence.contracts import canonical_json

from .models import (
    OpportunityScoreDimension,
    OpportunityScoreMissingDataPolicy,
    OpportunityScorePolicy,
    OpportunityScoreRoundingMode,
    OpportunityScoreRoundingPolicy,
    OpportunityScoringIntegrationValidationError,
)


POLICY_FIELDS = {
    "policy_version",
    "dimension_weights",
    "thresholds",
    "missing_data_policy",
    "rounding_policy",
    "confidence_rules",
    "policy_fingerprint",
}

EXPECTED_METRICS = {
    OpportunityScoreDimension.DEMAND_STRENGTH: (
        "demand.search_demand_share",
        "demand.review_mention_share",
        "demand.confidence",
    ),
    OpportunityScoreDimension.SUPPLY_GAP: (
        "supply_gap.gap_type",
        "supply_gap.gap_strength",
    ),
    OpportunityScoreDimension.COMPETITION_FAVORABILITY: (
        "competition.market_concentration",
        "competition.brand_concentration",
        "competition.review_barrier",
        "competition.price_competition",
    ),
    OpportunityScoreDimension.ECONOMIC_EVIDENCE: (
        "economic.price_band",
        "economic.sales_availability",
        "economic.revenue_availability",
    ),
    OpportunityScoreDimension.EVIDENCE_CONFIDENCE: (
        "evidence_confidence.demand",
        "evidence_confidence.supply",
        "evidence_confidence.gap",
        "evidence_confidence.competition",
        "evidence_confidence.economic",
    ),
}


class OpportunityScorePolicyLoadError(
    OpportunityScoringIntegrationValidationError
):
    """Raised when an explicitly selected policy cannot be loaded."""


def calculate_policy_fingerprint(payload: Mapping[str, Any]) -> str:
    """Return the content fingerprint, excluding any supplied fingerprint field."""

    if not isinstance(payload, Mapping):
        raise OpportunityScorePolicyLoadError("policy payload must be an object")
    material = dict(payload)
    material.pop("policy_fingerprint", None)
    digest = sha256(canonical_json(material).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class OpportunityScorePolicyLoader:
    """Load one explicitly named JSON policy; no implicit default or latest lookup."""

    def load(
        self, path: str | Path, *, policy_version: str
    ) -> OpportunityScorePolicy:
        if not isinstance(policy_version, str) or not policy_version.strip():
            raise OpportunityScorePolicyLoadError(
                "policy_version must be explicitly supplied"
            )
        if policy_version.casefold() == "latest":
            raise OpportunityScorePolicyLoadError(
                "automatic latest policy selection is prohibited"
            )
        candidate = Path(path)
        if candidate.suffix.casefold() != ".json":
            raise OpportunityScorePolicyLoadError(
                "Opportunity Score policies must use JSON"
            )
        try:
            payload = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise OpportunityScorePolicyLoadError(
                f"cannot load Opportunity Score policy {candidate}"
            ) from exc
        policy = self.load_mapping(payload)
        if policy.policy_version != policy_version:
            raise OpportunityScorePolicyLoadError(
                "loaded policy_version does not match requested version"
            )
        return policy

    def load_mapping(self, payload: Mapping[str, Any]) -> OpportunityScorePolicy:
        if not isinstance(payload, Mapping):
            raise OpportunityScorePolicyLoadError("policy must be an object")
        if set(payload) != POLICY_FIELDS:
            missing = sorted(POLICY_FIELDS - set(payload))
            extra = sorted(set(payload) - POLICY_FIELDS)
            raise OpportunityScorePolicyLoadError(
                f"invalid policy fields; missing={missing}, extra={extra}"
            )
        rounding = payload["rounding_policy"]
        if not isinstance(rounding, Mapping) or set(rounding) != {
            "mode",
            "decimal_places",
        }:
            raise OpportunityScorePolicyLoadError(
                "rounding_policy must contain mode and decimal_places"
            )
        try:
            policy = OpportunityScorePolicy(
                policy_version=payload["policy_version"],
                dimension_weights=payload["dimension_weights"],
                thresholds=payload["thresholds"],
                missing_data_policy=OpportunityScoreMissingDataPolicy(
                    payload["missing_data_policy"]
                ),
                rounding_policy=OpportunityScoreRoundingPolicy(
                    mode=OpportunityScoreRoundingMode(rounding["mode"]),
                    decimal_places=rounding["decimal_places"],
                ),
                confidence_rules=payload["confidence_rules"],
                policy_fingerprint=payload["policy_fingerprint"],
            )
            OpportunityScorePolicyValidator().validate(policy)
        except (ValueError, TypeError) as exc:
            if isinstance(exc, OpportunityScorePolicyLoadError):
                raise
            raise OpportunityScorePolicyLoadError(
                f"invalid Opportunity Score policy: {exc}"
            ) from exc
        return policy


class OpportunityScorePolicyValidator:
    """Validate declared scoring behavior without supplying missing parameters."""

    def validate(self, policy: OpportunityScorePolicy) -> None:
        if not isinstance(policy, OpportunityScorePolicy):
            raise TypeError("policy must be OpportunityScorePolicy")
        expected_dimensions = {item.value for item in OpportunityScoreDimension}
        if set(policy.dimension_weights) != expected_dimensions:
            raise OpportunityScoringIntegrationValidationError(
                "dimension_weights must contain all five dimensions exactly once"
            )
        weights = tuple(float(value) for value in policy.dimension_weights.values())
        if any(not math.isfinite(value) or value <= 0 for value in weights):
            raise OpportunityScoringIntegrationValidationError(
                "every dimension weight must be positive"
            )
        if not math.isclose(sum(weights), 100.0, abs_tol=1e-9):
            raise OpportunityScoringIntegrationValidationError(
                "dimension weights must sum to 100"
            )

        expected_metrics = {
            metric_id
            for metrics in EXPECTED_METRICS.values()
            for metric_id in metrics
        }
        if set(policy.thresholds) != expected_metrics:
            raise OpportunityScoringIntegrationValidationError(
                "thresholds must contain every Candidate scoring metric exactly once"
            )
        for dimension, metric_ids in EXPECTED_METRICS.items():
            total_metric_weight = 0.0
            for metric_id in metric_ids:
                rule = policy.thresholds[metric_id]
                self._validate_rule(metric_id, rule)
                total_metric_weight += float(rule["metric_weight"])
            if total_metric_weight <= 0:
                raise OpportunityScoringIntegrationValidationError(
                    f"{dimension.value} requires a positive metric weight"
                )

        confidence_rules = policy.confidence_rules
        if set(confidence_rules) != {"strategy", "score_multiplier"}:
            raise OpportunityScoringIntegrationValidationError(
                "confidence_rules must declare strategy and score_multiplier"
            )
        if confidence_rules["strategy"] != "PRESERVE_CANDIDATE_CONFIDENCE":
            raise OpportunityScoringIntegrationValidationError(
                "V0.1 confidence strategy must preserve Candidate confidence"
            )
        if confidence_rules["score_multiplier"] is not False:
            raise OpportunityScoringIntegrationValidationError(
                "V0.1 confidence must not multiply Opportunity Score"
            )
        if policy.fingerprint_for_content() != policy.policy_fingerprint:
            raise OpportunityScoringIntegrationValidationError(
                "policy fingerprint mismatch"
            )

    @staticmethod
    def _validate_rule(metric_id: str, rule: Any) -> None:
        if not isinstance(rule, Mapping):
            raise OpportunityScoringIntegrationValidationError(
                f"threshold rule {metric_id} must be an object"
            )
        rule_type = rule.get("rule_type")
        if rule_type == "NUMERIC_RANGE":
            expected = {
                "rule_type",
                "metric_weight",
                "minimum",
                "maximum",
                "direction",
            }
            if set(rule) != expected:
                raise OpportunityScoringIntegrationValidationError(
                    f"NUMERIC_RANGE rule {metric_id} has invalid fields"
                )
            minimum = _finite_rule_number(rule["minimum"], metric_id)
            maximum = _finite_rule_number(rule["maximum"], metric_id)
            if minimum >= maximum:
                raise OpportunityScoringIntegrationValidationError(
                    f"NUMERIC_RANGE rule {metric_id} requires minimum < maximum"
                )
            if rule["direction"] not in {
                "HIGHER_IS_FAVORABLE",
                "LOWER_IS_FAVORABLE",
            }:
                raise OpportunityScoringIntegrationValidationError(
                    f"NUMERIC_RANGE rule {metric_id} has invalid direction"
                )
        elif rule_type == "CATEGORY_MAP":
            expected = {"rule_type", "metric_weight", "scores"}
            if set(rule) != expected or not isinstance(rule["scores"], Mapping):
                raise OpportunityScoringIntegrationValidationError(
                    f"CATEGORY_MAP rule {metric_id} has invalid fields"
                )
            if not rule["scores"]:
                raise OpportunityScoringIntegrationValidationError(
                    f"CATEGORY_MAP rule {metric_id} requires scores"
                )
            for category, score in rule["scores"].items():
                if not isinstance(category, str) or not category.strip():
                    raise OpportunityScoringIntegrationValidationError(
                        f"CATEGORY_MAP rule {metric_id} has invalid category"
                    )
                _score(score, metric_id)
        elif rule_type == "PRESENCE":
            expected = {"rule_type", "metric_weight", "present_score"}
            if set(rule) != expected:
                raise OpportunityScoringIntegrationValidationError(
                    f"PRESENCE rule {metric_id} has invalid fields"
                )
            _score(rule["present_score"], metric_id)
        else:
            raise OpportunityScoringIntegrationValidationError(
                f"threshold rule {metric_id} has unsupported rule_type"
            )
        weight = _finite_rule_number(rule["metric_weight"], metric_id)
        if weight < 0:
            raise OpportunityScoringIntegrationValidationError(
                f"threshold rule {metric_id} has negative metric_weight"
            )


def _finite_rule_number(value: Any, metric_id: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise OpportunityScoringIntegrationValidationError(
            f"rule {metric_id} requires finite numeric parameters"
        )
    resolved = float(value)
    if not math.isfinite(resolved):
        raise OpportunityScoringIntegrationValidationError(
            f"rule {metric_id} requires finite numeric parameters"
        )
    return resolved


def _score(value: Any, metric_id: str) -> float:
    score = _finite_rule_number(value, metric_id)
    if not 0 <= score <= 100:
        raise OpportunityScoringIntegrationValidationError(
            f"rule {metric_id} score must be between 0 and 100"
        )
    return score


__all__ = (
    "EXPECTED_METRICS",
    "OpportunityScorePolicyLoadError",
    "OpportunityScorePolicyLoader",
    "OpportunityScorePolicyValidator",
    "calculate_policy_fingerprint",
)
