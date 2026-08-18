"""Deterministic Recommendation Framework V0.1 builder."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    EvidenceType,
    ObservationKind,
    Severity,
    canonical_json,
    deterministic_id,
)

from .errors import RecommendationFrameworkValidationError
from .models import (
    RECOMMENDATION_FRAMEWORK_RULESET_VERSION,
    RecommendationApplicabilityRecord,
    RecommendationDiagnostic,
    RecommendationExplanationRecord,
    RecommendationFrameworkRequest,
    RecommendationFrameworkSnapshotV0_1,
    RecommendationGenerationRecord,
    RecommendationLineageReference,
    RecommendationRuleDefinition,
    bundle_fingerprint,
    coverage_from_records,
    observation_revision_content,
)


_SUPPORT_FIELDS = {
    "support_record_id",
    "semantic_field_id",
    "subject",
    "observation_kind",
    "dimension",
    "supporting_observation_ids",
    "providers",
    "sources",
    "provider_count",
    "source_count",
    "lineage_completeness",
    "semantic_statuses",
    "presence_statuses",
    "lineage_references",
}
_EVALUATION_CONFLICT_FIELDS = {
    "conflict_record_id",
    "support_record_id",
    "semantic_field_id",
    "subject",
    "observation_kind",
    "dimension",
    "candidate_observation_ids",
    "candidate_values",
    "providers",
    "sources",
    "conflict_status",
    "lineage_references",
}
_CONFLICT_ANALYSIS_FIELDS = {
    "conflict_analysis_id",
    "source_evaluation_conflict_id",
    "semantic_field_id",
    "subject",
    "observation_kind",
    "dimension",
    "candidate_ids",
    "candidates",
    "analysis_status",
    "source_bundle_fingerprints",
}
_CONFLICT_CANDIDATE_FIELDS = {
    "candidate_id",
    "source_evaluation_conflict_id",
    "observation_id",
    "value",
    "provider",
    "source",
    "lineage_references",
}
_RESOLUTION_ATTEMPT_FIELDS = {
    "resolution_attempt_id",
    "conflict_analysis_id",
    "attempted_method",
    "candidate_ids",
    "available_evidence_candidate_ids",
    "result_status",
    "produced_candidate_id",
    "process_evidence",
}
_POLICY_DEFINITION_FIELDS = {
    "policy_id",
    "policy_version",
    "description",
    "applicable_evidence_types",
    "conditions",
    "expected_behavior",
}
_POLICY_APPLICABILITY_FIELDS = {
    "policy_applicability_id",
    "policy_id",
    "applicability_status",
    "matched_evidence_ids",
    "matched_conflict_ids",
    "reason_codes",
}
_POLICY_EVALUATION_FIELDS = {
    "policy_evaluation_id",
    "policy_id",
    "policy_applicability_id",
    "input_evidence_ids",
    "conflict_ids",
    "evaluation_result",
    "expected_behavior",
    "audit_metadata",
}
_DECISION_RULE_FIELDS = {
    "rule_id",
    "rule_version",
    "description",
    "input_evidence_requirements",
    "conditions",
    "expected_behavior",
}
_DECISION_APPLICABILITY_FIELDS = {
    "decision_applicability_id",
    "rule_id",
    "available_evidence_ids",
    "missing_evidence_requirements",
    "conflict_status",
    "policy_status",
    "policy_evaluation_ids",
    "applicability_result",
    "reason_codes",
}
_DECISION_EVALUATION_FIELDS = {
    "decision_evaluation_id",
    "rule_id",
    "decision_applicability_id",
    "input_evidence_ids",
    "policy_evaluation_ids",
    "conflict_ids",
    "evaluation_result",
    "analysis_output",
    "audit_metadata",
}
_DECISION_LINEAGE_FIELDS = {
    "decision_lineage_id",
    "rule_id",
    "decision_evaluation_id",
    "policy_id",
    "policy_evaluation_id",
    "support_record_id",
    "conflict_record_id",
    "conflict_analysis_id",
    "conflict_candidate_id",
    "resolution_attempt_ids",
    "observation_id",
    "semantic_observation_id",
    "observation_kind",
    "evidence_type",
    "transformation_run_id",
    "mapping_version",
    "raw_evidence_id",
    "collection_run_id",
    "provider",
    "source_tool",
    "source_field",
    "source_bundle_fingerprints",
}
_SCORE_FACTOR_FIELDS = {
    "factor_id",
    "factor_version",
    "name",
    "description",
    "input_requirements",
    "calculation_rule",
    "explanation_template",
    "expected_behavior",
}
_SCORE_COMPONENT_FIELDS = {
    "component_id",
    "factor_id",
    "decision_evaluation_id",
    "input_evidence_ids",
    "policy_evaluation_ids",
    "conflict_ids",
    "component_status",
    "component_explanation",
    "reason_codes",
}
_SCORE_CALCULATION_FIELDS = {
    "calculation_id",
    "factor_id",
    "component_id",
    "calculation_method",
    "input_components",
    "result_value",
    "result_status",
    "version",
    "decision_evaluation_ids",
    "decision_lineage_ids",
    "policy_evaluation_ids",
    "conflict_ids",
    "evidence_ids",
    "process_interpretation",
}
_SCORE_EXPLANATION_FIELDS = {
    "explanation_id",
    "factor_id",
    "component_id",
    "calculation_id",
    "factor_explanation",
    "calculation_rule",
    "version",
    "evidence_ids",
    "decision_evaluation_ids",
    "policy_evaluation_ids",
    "conflict_ids",
    "result_interpretation",
}
_SCORE_LINEAGE_FIELDS = {
    "score_lineage_id",
    "factor_id",
    "component_id",
    "calculation_id",
    "rule_id",
    "decision_evaluation_id",
    "decision_lineage_id",
    "policy_id",
    "policy_evaluation_id",
    "support_record_id",
    "conflict_record_id",
    "conflict_analysis_id",
    "conflict_candidate_id",
    "resolution_attempt_ids",
    "observation_id",
    "semantic_observation_id",
    "observation_kind",
    "evidence_type",
    "transformation_run_id",
    "mapping_version",
    "raw_evidence_id",
    "collection_run_id",
    "provider",
    "source_tool",
    "source_field",
    "source_bundle_fingerprints",
}
_SCORE_STATUSES = {
    "CALCULATED",
    "CALCULATED_WITH_CONFLICT_VISIBLE",
    "BLOCKED_BY_POLICY",
    "EXCLUDED_MISSING_EVIDENCE",
    "NOT_APPLICABLE",
}
_NUMERIC_SCORE_STATUSES = {"CALCULATED", "CALCULATED_WITH_CONFLICT_VISIBLE"}
_LIMITATIONS = (
    "CURRENT_RULE_AND_EVIDENCE_ONLY",
    "NO_AUTOMATIC_SELECTION",
    "NO_FACTUAL_TRUTH_CLAIM",
    "NO_GUARANTEE_OR_FORECAST",
    "NO_MARKET_OR_INVESTMENT_DECISION",
)


@dataclass(frozen=True, slots=True)
class _ScoreEntry:
    condition_type: str
    factor: Mapping[str, Any]
    component: Mapping[str, Any]
    calculation: Mapping[str, Any]
    explanation: Mapping[str, Any]


class _CanonicalIndex:
    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(
            bundle_fingerprint(bundle) for bundle in bundles
        ))
        self.observations: dict[str, CanonicalObservation] = {}
        self.emissions: dict[str, tuple[Mapping[str, Any], ...]] = {}
        revisions: dict[str, str] = {}
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        fingerprints_by_emission: dict[tuple[str, str], set[str]] = {}
        all_observations: dict[tuple[str, str], CanonicalObservation] = {}
        for bundle in bundles:
            fingerprint = bundle_fingerprint(bundle)
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise RecommendationFrameworkValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                revision = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != revision:
                    raise RecommendationFrameworkValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = revision
                self.observations.setdefault(observation.observation_id, observation)
                run_id = observation.provenance.transformation.transformation_run_id
                key = (observation.observation_id, run_id)
                existing = all_observations.get(key)
                if existing is not None and canonical_json(existing) != canonical_json(
                    observation
                ):
                    raise RecommendationFrameworkValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                all_observations[key] = observation
                fingerprints_by_emission.setdefault(key, set()).add(fingerprint)
        emissions: dict[str, list[Mapping[str, Any]]] = {}
        for (observation_id, run_id), observation in all_observations.items():
            transformation = observation.provenance.transformation
            run = runs.get(run_id)
            if (
                run is None
                or transformation.raw_evidence_reference not in raw_ids
                or transformation.raw_evidence_reference
                not in run.input_raw_evidence_references
                or observation_id not in run.output_observation_ids
            ):
                raise RecommendationFrameworkValidationError(
                    f"broken canonical transformation lineage: {observation_id}"
                )
            payload = MappingProxyType({
                "observation_id": observation_id,
                "semantic_observation_id": observation.semantic_observation_id,
                "observation_kind": observation.observation_kind.value,
                "transformation_run_id": run_id,
                "mapping_version": transformation.mapping_version,
                "raw_evidence_id": transformation.raw_evidence_reference,
                "collection_run_id": transformation.collection_run_id,
                "provider": observation.provenance.provider,
                "source_tool": observation.provenance.source_tool,
                "source_field": observation.provenance.source_field,
                "source_bundle_fingerprints": tuple(sorted(
                    fingerprints_by_emission[(observation_id, run_id)]
                )),
            })
            emissions.setdefault(observation_id, []).append(payload)
        self.emissions = {
            key: tuple(sorted(values, key=canonical_json))
            for key, values in emissions.items()
        }


def _exact_fields(record: Any, fields: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(record, MappingABC) or set(record) != fields:
        actual = set(record) if isinstance(record, MappingABC) else set()
        raise RecommendationFrameworkValidationError(
            f"invalid {path} fields; missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)}"
        )
    return record


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise RecommendationFrameworkValidationError(
            f"{path} must be non-empty text"
        )
    return value


def _texts(value: Any, path: str, *, minimum: int = 0) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise RecommendationFrameworkValidationError(f"{path} must be an array")
    if len(value) < minimum or any(
        type(item) is not str or not item.strip() for item in value
    ):
        raise RecommendationFrameworkValidationError(f"{path} contains invalid text")
    if len(set(value)) != len(value) or tuple(sorted(value)) != value:
        raise RecommendationFrameworkValidationError(
            f"{path} must contain sorted unique text"
        )
    return value


def _identity(
    record: Mapping[str, Any], field: str, prefix: str, path: str
) -> str:
    value = _text(record[field], f"{path}.{field}")
    content = dict(record)
    content.pop(field)
    if value != deterministic_id(prefix, content):
        raise RecommendationFrameworkValidationError(f"{path} identity mismatch")
    return value


def _unique_records(
    records: Any,
    *,
    fields: set[str],
    id_field: str,
    prefix: str,
    path: str,
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(records, tuple):
        raise RecommendationFrameworkValidationError(f"{path} must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(records):
        record = _exact_fields(value, fields, f"{path}[{index}]")
        identity = _identity(record, id_field, prefix, f"{path}[{index}]")
        if identity in result:
            raise RecommendationFrameworkValidationError(
                f"duplicate {path} identity"
            )
        result[identity] = record
    return result


class _SourceIndex:
    def __init__(self, request: RecommendationFrameworkRequest) -> None:
        self.canonical = _CanonicalIndex(request.canonical_bundles)
        self.evaluation_snapshot_id = request.evidence_evaluation_snapshot[
            "snapshot_id"
        ]
        self.conflict_snapshot_id = request.conflict_resolution_snapshot[
            "snapshot_id"
        ]
        self.policy_snapshot_id = request.evidence_policy_snapshot["snapshot_id"]
        self.decision_snapshot_id = request.decision_framework_snapshot[
            "snapshot_id"
        ]
        self.scoring_snapshot_id = request.opportunity_scoring_snapshot[
            "snapshot_id"
        ]
        evaluation = request.evidence_evaluation_snapshot
        conflict = request.conflict_resolution_snapshot
        policy = request.evidence_policy_snapshot
        decision = request.decision_framework_snapshot
        scoring = request.opportunity_scoring_snapshot

        self.supports = _unique_records(
            evaluation["support_records"],
            fields=_SUPPORT_FIELDS,
            id_field="support_record_id",
            prefix="evidence-support",
            path="support_records",
        )
        self.evaluation_conflicts = _unique_records(
            evaluation["conflict_records"],
            fields=_EVALUATION_CONFLICT_FIELDS,
            id_field="conflict_record_id",
            prefix="evidence-conflict",
            path="evaluation_conflicts",
        )
        self.analyses = _unique_records(
            conflict["conflict_analyses"],
            fields=_CONFLICT_ANALYSIS_FIELDS,
            id_field="conflict_analysis_id",
            prefix="conflict-analysis",
            path="conflict_analyses",
        )
        self.attempts = _unique_records(
            conflict["resolution_attempts"],
            fields=_RESOLUTION_ATTEMPT_FIELDS,
            id_field="resolution_attempt_id",
            prefix="resolution-attempt",
            path="resolution_attempts",
        )
        self._validate_conflict_sources()

        self.policy_definitions = _unique_records(
            policy["policy_definitions"],
            fields=_POLICY_DEFINITION_FIELDS,
            id_field="policy_id",
            prefix="evidence-policy",
            path="policy_definitions",
        )
        self.policy_applicability = _unique_records(
            policy["policy_applicability_records"],
            fields=_POLICY_APPLICABILITY_FIELDS,
            id_field="policy_applicability_id",
            prefix="policy-applicability",
            path="policy_applicability",
        )
        self.policy_evaluations = _unique_records(
            policy["policy_evaluations"],
            fields=_POLICY_EVALUATION_FIELDS,
            id_field="policy_evaluation_id",
            prefix="policy-evaluation",
            path="policy_evaluations",
        )
        self._validate_policy_sources()

        self.decision_rules = _unique_records(
            decision["rule_definitions"],
            fields=_DECISION_RULE_FIELDS,
            id_field="rule_id",
            prefix="decision-rule",
            path="decision_rules",
        )
        self.decision_applicability = _unique_records(
            decision["applicability_records"],
            fields=_DECISION_APPLICABILITY_FIELDS,
            id_field="decision_applicability_id",
            prefix="decision-applicability",
            path="decision_applicability",
        )
        self.decision_evaluations = _unique_records(
            decision["decision_evaluations"],
            fields=_DECISION_EVALUATION_FIELDS,
            id_field="decision_evaluation_id",
            prefix="decision-evaluation",
            path="decision_evaluations",
        )
        self.decision_lineages = self._decision_lineages(
            decision["lineage_index"]
        )
        self._validate_decision_sources()

        self.score_factors = _unique_records(
            scoring["score_factors"],
            fields=_SCORE_FACTOR_FIELDS,
            id_field="factor_id",
            prefix="score-factor",
            path="score_factors",
        )
        self.score_components = _unique_records(
            scoring["components"],
            fields=_SCORE_COMPONENT_FIELDS,
            id_field="component_id",
            prefix="score-component",
            path="score_components",
        )
        self.score_calculations = _unique_records(
            scoring["calculations"],
            fields=_SCORE_CALCULATION_FIELDS,
            id_field="calculation_id",
            prefix="score-calculation",
            path="score_calculations",
        )
        self.score_explanations = _unique_records(
            scoring["explanations"],
            fields=_SCORE_EXPLANATION_FIELDS,
            id_field="explanation_id",
            prefix="score-explanation",
            path="score_explanations",
        )
        self.score_lineages = self._score_lineages(scoring["lineage_index"])
        self.score_entries = self._validate_scoring_sources()

    def _validate_conflict_sources(self) -> None:
        covered: set[str] = set()
        for analysis_id, analysis in self.analyses.items():
            source_id = analysis["source_evaluation_conflict_id"]
            source = self.evaluation_conflicts.get(source_id)
            if source is None or source_id in covered:
                raise RecommendationFrameworkValidationError(
                    "conflict analysis source is orphaned or duplicated"
                )
            covered.add(source_id)
            candidates = analysis["candidates"]
            if not isinstance(candidates, tuple) or not candidates:
                raise RecommendationFrameworkValidationError(
                    "conflict analysis requires candidates"
                )
            candidate_ids: set[str] = set()
            for index, value in enumerate(candidates):
                candidate = _exact_fields(
                    value,
                    _CONFLICT_CANDIDATE_FIELDS,
                    f"conflict candidate {analysis_id}[{index}]",
                )
                candidate_id = _identity(
                    candidate,
                    "candidate_id",
                    "conflict-candidate",
                    f"conflict candidate {analysis_id}[{index}]",
                )
                if (
                    candidate["source_evaluation_conflict_id"] != source_id
                    or candidate["observation_id"]
                    not in source["candidate_observation_ids"]
                ):
                    raise RecommendationFrameworkValidationError(
                        "conflict candidate source mismatch"
                    )
                candidate_ids.add(candidate_id)
            if candidate_ids != set(analysis["candidate_ids"]):
                raise RecommendationFrameworkValidationError(
                    "conflict analysis candidate IDs mismatch"
                )
        if covered != set(self.evaluation_conflicts):
            raise RecommendationFrameworkValidationError(
                "conflict analyses do not cover evaluation conflicts"
            )
        for attempt in self.attempts.values():
            analysis = self.analyses.get(attempt["conflict_analysis_id"])
            if analysis is None or set(attempt["candidate_ids"]) != set(
                analysis["candidate_ids"]
            ):
                raise RecommendationFrameworkValidationError(
                    "resolution attempt does not match conflict analysis"
                )

    def _validate_policy_sources(self) -> None:
        for evaluation in self.policy_evaluations.values():
            if (
                evaluation["policy_id"] not in self.policy_definitions
                or evaluation["policy_applicability_id"]
                not in self.policy_applicability
                or not set(evaluation["input_evidence_ids"]) <= set(self.supports)
                or not set(evaluation["conflict_ids"])
                <= set(self.evaluation_conflicts)
                or evaluation["evaluation_result"]
                not in {
                    "ACTION_ALLOWED",
                    "ACTION_BLOCKED",
                    "APPLICABLE_NO_ACTION",
                    "NOT_APPLICABLE",
                }
            ):
                raise RecommendationFrameworkValidationError(
                    "policy evaluation contains orphan or invalid process state"
                )

    def _decision_lineages(
        self, values: Any
    ) -> dict[str, tuple[Mapping[str, Any], ...]]:
        if not isinstance(values, tuple):
            raise RecommendationFrameworkValidationError(
                "decision lineage_index must be an array"
            )
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        identities: set[str] = set()
        for index, value in enumerate(values):
            record = _exact_fields(
                value, _DECISION_LINEAGE_FIELDS, f"decision lineage[{index}]"
            )
            identity = _identity(
                record,
                "decision_lineage_id",
                "decision-lineage",
                f"decision lineage[{index}]",
            )
            if identity in identities:
                raise RecommendationFrameworkValidationError(
                    "duplicate decision lineage identity"
                )
            identities.add(identity)
            grouped.setdefault(record["decision_evaluation_id"], []).append(record)
        return {
            key: tuple(sorted(values, key=lambda item: item["decision_lineage_id"]))
            for key, values in grouped.items()
        }

    def _validate_decision_sources(self) -> None:
        applicability_by_rule = {
            item["rule_id"]: item for item in self.decision_applicability.values()
        }
        conditions: set[str] = set()
        for rule in self.decision_rules.values():
            condition_payload = rule["conditions"]
            if not isinstance(condition_payload, MappingABC):
                raise RecommendationFrameworkValidationError(
                    "decision rule conditions must be an object"
                )
            condition = condition_payload.get("condition_type")
            if condition not in {
                "EVIDENCE_INVENTORY",
                "CONFLICT_FREE_EVIDENCE",
                "KEYWORD_EVIDENCE",
                "CONFLICT_CONTEXT",
            } or condition in conditions:
                raise RecommendationFrameworkValidationError(
                    "decision rule condition mismatch"
                )
            conditions.add(condition)
        if len(conditions) != 4:
            raise RecommendationFrameworkValidationError(
                "decision rules do not cover V0.1 conditions"
            )
        seen_rules: set[str] = set()
        for evaluation_id, evaluation in self.decision_evaluations.items():
            rule_id = evaluation["rule_id"]
            applicability = applicability_by_rule.get(rule_id)
            if (
                rule_id not in self.decision_rules
                or rule_id in seen_rules
                or applicability is None
                or evaluation["decision_applicability_id"]
                != applicability["decision_applicability_id"]
                or not set(evaluation["input_evidence_ids"]) <= set(self.supports)
                or not set(evaluation["policy_evaluation_ids"])
                <= set(self.policy_evaluations)
                or not set(evaluation["conflict_ids"])
                <= set(self.evaluation_conflicts)
            ):
                raise RecommendationFrameworkValidationError(
                    "decision evaluation continuity mismatch"
                )
            seen_rules.add(rule_id)
            lineages = self.decision_lineages.get(evaluation_id, ())
            if {item["support_record_id"] for item in lineages} != set(
                evaluation["input_evidence_ids"]
            ) or {item["policy_evaluation_id"] for item in lineages} != set(
                evaluation["policy_evaluation_ids"]
            ) or {
                item["conflict_record_id"]
                for item in lineages
                if item["conflict_record_id"] is not None
            } != set(evaluation["conflict_ids"]):
                raise RecommendationFrameworkValidationError(
                    "decision lineage does not cover evaluation inputs"
                )
        if seen_rules != set(self.decision_rules):
            raise RecommendationFrameworkValidationError(
                "every decision rule requires an evaluation"
            )

    def _score_lineages(
        self, values: Any
    ) -> dict[str, tuple[Mapping[str, Any], ...]]:
        if not isinstance(values, tuple):
            raise RecommendationFrameworkValidationError(
                "score lineage_index must be an array"
            )
        decision_payloads = {
            canonical_json(lineage)
            for lineages in self.decision_lineages.values()
            for lineage in lineages
        }
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        identities: set[str] = set()
        for index, value in enumerate(values):
            record = _exact_fields(
                value, _SCORE_LINEAGE_FIELDS, f"score lineage[{index}]"
            )
            identity = _identity(
                record,
                "score_lineage_id",
                "score-lineage",
                f"score lineage[{index}]",
            )
            if identity in identities:
                raise RecommendationFrameworkValidationError(
                    "duplicate score lineage identity"
                )
            identities.add(identity)
            upstream = {
                key: record[key]
                for key in _DECISION_LINEAGE_FIELDS
            }
            if canonical_json(upstream) not in decision_payloads:
                raise RecommendationFrameworkValidationError(
                    "score lineage does not replay decision lineage"
                )
            self._validate_canonical_score_lineage(record)
            grouped.setdefault(record["calculation_id"], []).append(record)
        return {
            key: tuple(sorted(values, key=lambda item: item["score_lineage_id"]))
            for key, values in grouped.items()
        }

    def _validate_canonical_score_lineage(self, record: Mapping[str, Any]) -> None:
        observation_id = record["observation_id"]
        source = {
            "observation_id": observation_id,
            "semantic_observation_id": record["semantic_observation_id"],
            "observation_kind": record["observation_kind"],
            "transformation_run_id": record["transformation_run_id"],
            "mapping_version": record["mapping_version"],
            "raw_evidence_id": record["raw_evidence_id"],
            "collection_run_id": record["collection_run_id"],
            "provider": record["provider"],
            "source_tool": record["source_tool"],
            "source_field": record["source_field"],
            "source_bundle_fingerprints": record["source_bundle_fingerprints"],
        }
        if canonical_json(source) not in {
            canonical_json(item)
            for item in self.canonical.emissions.get(observation_id, ())
        }:
            raise RecommendationFrameworkValidationError(
                "score lineage does not replay canonical evidence"
            )
        observation = self.canonical.observations[observation_id]
        if (
            record["evidence_type"] != observation.evidence_type.value
            or record["support_record_id"] not in self.supports
        ):
            raise RecommendationFrameworkValidationError(
                "score lineage evidence type or support mismatch"
            )

    def _validate_scoring_sources(self) -> tuple[_ScoreEntry, ...]:
        factors_by_condition: dict[str, Mapping[str, Any]] = {}
        for factor in self.score_factors.values():
            requirements = factor["input_requirements"]
            if not isinstance(requirements, MappingABC):
                raise RecommendationFrameworkValidationError(
                    "score factor input requirements must be an object"
                )
            condition = requirements.get("decision_condition_type")
            if condition not in {
                "EVIDENCE_INVENTORY",
                "CONFLICT_FREE_EVIDENCE",
                "KEYWORD_EVIDENCE",
                "CONFLICT_CONTEXT",
            } or condition in factors_by_condition:
                raise RecommendationFrameworkValidationError(
                    "score factors do not contain fixed conditions"
                )
            factors_by_condition[condition] = factor
        if len(factors_by_condition) != 4:
            raise RecommendationFrameworkValidationError(
                "score factors do not cover fixed conditions"
            )
        components_by_factor = {
            item["factor_id"]: item for item in self.score_components.values()
        }
        calculations_by_factor = {
            item["factor_id"]: item for item in self.score_calculations.values()
        }
        explanations_by_factor = {
            item["factor_id"]: item for item in self.score_explanations.values()
        }
        if not (
            set(self.score_factors)
            == set(components_by_factor)
            == set(calculations_by_factor)
            == set(explanations_by_factor)
        ):
            raise RecommendationFrameworkValidationError(
                "every score factor requires component, calculation, and explanation"
            )
        entries: list[_ScoreEntry] = []
        for condition, factor in factors_by_condition.items():
            factor_id = factor["factor_id"]
            component = components_by_factor[factor_id]
            calculation = calculations_by_factor[factor_id]
            explanation = explanations_by_factor[factor_id]
            status = calculation["result_status"]
            if (
                status not in _SCORE_STATUSES
                or component["component_status"] != status
                or calculation["component_id"] != component["component_id"]
                or explanation["component_id"] != component["component_id"]
                or explanation["calculation_id"] != calculation["calculation_id"]
                or calculation["decision_evaluation_ids"]
                != (component["decision_evaluation_id"],)
                or calculation["policy_evaluation_ids"]
                != component["policy_evaluation_ids"]
                or calculation["conflict_ids"] != component["conflict_ids"]
                or calculation["evidence_ids"] != component["input_evidence_ids"]
                or component["decision_evaluation_id"]
                not in self.decision_evaluations
                or not set(component["policy_evaluation_ids"])
                <= set(self.policy_evaluations)
                or not set(component["conflict_ids"])
                <= set(self.evaluation_conflicts)
                or not set(component["input_evidence_ids"]) <= set(self.supports)
            ):
                raise RecommendationFrameworkValidationError(
                    "score factor record continuity mismatch"
                )
            if status in _NUMERIC_SCORE_STATUSES:
                value = calculation["result_value"]
                if type(value) is not int or not 0 <= value <= 100:
                    raise RecommendationFrameworkValidationError(
                        "calculated score result is invalid"
                    )
            elif calculation["result_value"] is not None:
                raise RecommendationFrameworkValidationError(
                    "unavailable score calculation contains a numeric result"
                )
            lineages = self.score_lineages.get(calculation["calculation_id"], ())
            if (
                {item["score_lineage_id"] for item in lineages}
                == set()
                or {item["decision_lineage_id"] for item in lineages}
                != set(calculation["decision_lineage_ids"])
                or {item["support_record_id"] for item in lineages}
                != set(calculation["evidence_ids"])
                or {item["policy_evaluation_id"] for item in lineages}
                != set(calculation["policy_evaluation_ids"])
                or {
                    item["conflict_record_id"]
                    for item in lineages
                    if item["conflict_record_id"] is not None
                }
                != set(calculation["conflict_ids"])
            ):
                raise RecommendationFrameworkValidationError(
                    "score lineage does not cover calculation inputs"
                )
            entries.append(_ScoreEntry(
                condition_type=condition,
                factor=factor,
                component=component,
                calculation=calculation,
                explanation=explanation,
            ))
        return tuple(sorted(entries, key=lambda item: item.condition_type))


def _rule(
    description: str, condition_type: str
) -> RecommendationRuleDefinition:
    payload = {
        "rule_version": "0.1",
        "description": description,
        "input_requirements": {
            "decision_condition_type": condition_type,
            "required_source_records": (
                "DECISION_EVALUATION",
                "SCORE_CALCULATION",
            ),
        },
        "conditions": {
            "calculated_behavior": "RULE_CONDITIONS_SATISFIED",
            "conflict_visible_behavior": "FURTHER_REVIEW_RECOMMENDED",
            "missing_evidence_behavior": "EVIDENCE_COLLECTION_RECOMMENDED",
            "policy_blocked_behavior": "RECOMMENDATION_BLOCKED_BY_POLICY",
            "not_applicable_behavior": "RULE_NOT_APPLICABLE",
        },
        "expected_recommendation_behavior": (
            "AUDITABLE_RULE_OUTPUT_NO_AUTOMATIC_SELECTION"
        ),
    }
    return RecommendationRuleDefinition(
        rule_id=deterministic_id("recommendation-rule", payload), **payload
    )


def _default_rules() -> tuple[RecommendationRuleDefinition, ...]:
    return tuple(sorted((
        _rule(
            "Generate a bounded evidence-inventory advisory without selecting a product.",
            "EVIDENCE_INVENTORY",
        ),
        _rule(
            "Generate a policy-governed conflict-free advisory without overriding evidence.",
            "CONFLICT_FREE_EVIDENCE",
        ),
        _rule(
            "Generate a bounded keyword-evidence advisory without predicting demand.",
            "KEYWORD_EVIDENCE",
        ),
        _rule(
            "Generate a further-review advisory while preserving unresolved conflict.",
            "CONFLICT_CONTEXT",
        ),
    ), key=lambda item: item.rule_id))


class RecommendationFrameworkBuilderV0_1:
    """Build auditable advisory records without automatic selection."""

    def build(
        self, request: RecommendationFrameworkRequest
    ) -> RecommendationFrameworkSnapshotV0_1:
        if not isinstance(request, RecommendationFrameworkRequest):
            raise RecommendationFrameworkValidationError(
                "request must be RecommendationFrameworkRequest"
            )
        source = _SourceIndex(request)
        rules = _default_rules()
        rules_by_condition = {
            item.input_requirements["decision_condition_type"]: item
            for item in rules
        }
        applicability: list[RecommendationApplicabilityRecord] = []
        generations: list[RecommendationGenerationRecord] = []
        explanations: list[RecommendationExplanationRecord] = []
        lineages: list[RecommendationLineageReference] = []
        for entry in source.score_entries:
            rule = rules_by_condition[entry.condition_type]
            state = self._state(entry, source)
            applies = self._applicability(rule, entry, state)
            explanation = self._explanation(rule, entry, state)
            generation = self._generation(
                rule, entry, applies, explanation, state
            )
            applicability.append(applies)
            explanations.append(explanation)
            generations.append(generation)
            lineages.extend(self._lineages(
                rule, applies, generation, explanation, entry, source
            ))
        ordered_applicability = tuple(sorted(
            applicability,
            key=lambda item: item.recommendation_applicability_id,
        ))
        ordered_generations = tuple(sorted(
            generations,
            key=lambda item: item.recommendation_generation_id,
        ))
        ordered_explanations = tuple(sorted(
            explanations, key=lambda item: item.explanation_id
        ))
        ordered_lineages = tuple(sorted(
            lineages, key=lambda item: item.recommendation_lineage_id
        ))
        diagnostics = self._diagnostics(ordered_generations)
        coverage = coverage_from_records(
            bundle_count=len(source.canonical.bundle_fingerprints),
            rules=rules,
            applicability=ordered_applicability,
            generations=ordered_generations,
            explanations=ordered_explanations,
            diagnostics=diagnostics,
            lineage=ordered_lineages,
        )
        payload = {
            "ruleset_version": RECOMMENDATION_FRAMEWORK_RULESET_VERSION,
            "source_evaluation_snapshot_id": source.evaluation_snapshot_id,
            "source_conflict_resolution_snapshot_id": source.conflict_snapshot_id,
            "source_policy_snapshot_id": source.policy_snapshot_id,
            "source_decision_snapshot_id": source.decision_snapshot_id,
            "source_scoring_snapshot_id": source.scoring_snapshot_id,
            "source_bundle_fingerprints": source.canonical.bundle_fingerprints,
            "recommendation_rules": rules,
            "applicability_records": ordered_applicability,
            "generation_records": ordered_generations,
            "explanations": ordered_explanations,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": ordered_lineages,
        }
        snapshot = RecommendationFrameworkSnapshotV0_1(
            snapshot_id=deterministic_id(
                "recommendation-framework-snapshot", payload
            ),
            **payload,
        )
        return snapshot.validate_against_bundles(request.canonical_bundles)

    @staticmethod
    def _state(entry: _ScoreEntry, source: _SourceIndex) -> Mapping[str, Any]:
        calculation = entry.calculation
        policy_evaluations = tuple(
            source.policy_evaluations[item]
            for item in calculation["policy_evaluation_ids"]
        )
        policy_blocked = any(
            item["evaluation_result"] == "ACTION_BLOCKED"
            for item in policy_evaluations
        )
        if policy_blocked:
            policy_status = "POLICY_BLOCKED"
        elif any(
            item["evaluation_result"]
            in {"ACTION_ALLOWED", "APPLICABLE_NO_ACTION"}
            for item in policy_evaluations
        ):
            policy_status = "POLICY_ALLOWED"
        else:
            policy_status = "POLICY_NOT_APPLICABLE"
        conflict_status = (
            "CONFLICT_PRESENT" if calculation["conflict_ids"] else "NO_CONFLICT"
        )
        score_status = calculation["result_status"]
        missing = (
            ("UPSTREAM_SCORE_EXCLUDED_MISSING_EVIDENCE",)
            if score_status == "EXCLUDED_MISSING_EVIDENCE"
            else ()
        )
        if policy_blocked:
            applicability = "BLOCKED_BY_POLICY"
            recommendation_type = "RECOMMENDATION_BLOCKED_BY_POLICY"
            reasons = ("UPSTREAM_POLICY_BLOCKS_RECOMMENDATION_NOT_PRODUCT",)
        elif missing:
            applicability = "INSUFFICIENT_EVIDENCE"
            recommendation_type = "EVIDENCE_COLLECTION_RECOMMENDED"
            reasons = ("MISSING_EVIDENCE_REQUIRES_COLLECTION_NOT_ZERO_INFERENCE",)
        elif score_status == "NOT_APPLICABLE":
            applicability = "NOT_APPLICABLE"
            recommendation_type = "RULE_NOT_APPLICABLE"
            reasons = ("UPSTREAM_SCORE_RULE_NOT_APPLICABLE",)
        elif score_status in {"CALCULATED", "CALCULATED_WITH_CONFLICT_VISIBLE"}:
            applicability = "APPLICABLE"
            if conflict_status == "CONFLICT_PRESENT":
                recommendation_type = "FURTHER_REVIEW_RECOMMENDED"
                reasons = ("UNRESOLVED_CONFLICT_REQUIRES_FURTHER_REVIEW",)
            else:
                recommendation_type = "RULE_CONDITIONS_SATISFIED"
                reasons = ("CURRENT_RULE_CONDITIONS_SATISFIED",)
        else:
            raise RecommendationFrameworkValidationError(
                "score state cannot generate a V0.1 recommendation record"
            )
        return MappingProxyType({
            "policy_status": policy_status,
            "conflict_status": conflict_status,
            "missing": missing,
            "applicability": applicability,
            "recommendation_type": recommendation_type,
            "reason_codes": reasons,
        })

    @staticmethod
    def _applicability(
        rule: RecommendationRuleDefinition,
        entry: _ScoreEntry,
        state: Mapping[str, Any],
    ) -> RecommendationApplicabilityRecord:
        component = entry.component
        calculation = entry.calculation
        payload = {
            "rule_id": rule.rule_id,
            "available_evidence_ids": calculation["evidence_ids"],
            "missing_evidence_requirements": state["missing"],
            "score_component_ids": (component["component_id"],),
            "score_calculation_ids": (calculation["calculation_id"],),
            "policy_status": state["policy_status"],
            "conflict_status": state["conflict_status"],
            "applicability_result": state["applicability"],
            "reason_codes": state["reason_codes"],
        }
        return RecommendationApplicabilityRecord(
            recommendation_applicability_id=deterministic_id(
                "recommendation-applicability", payload
            ),
            **payload,
        )

    @staticmethod
    def _explanation(
        rule: RecommendationRuleDefinition,
        entry: _ScoreEntry,
        state: Mapping[str, Any],
    ) -> RecommendationExplanationRecord:
        calculation = entry.calculation
        payload = {
            "rule_id": rule.rule_id,
            "recommendation_type": state["recommendation_type"],
            "rule_explanation": rule.description,
            "evidence_ids": calculation["evidence_ids"],
            "decision_evaluation_ids": calculation["decision_evaluation_ids"],
            "score_component_ids": (entry.component["component_id"],),
            "score_calculation_ids": (calculation["calculation_id"],),
            "policy_evaluation_ids": calculation["policy_evaluation_ids"],
            "conflict_ids": calculation["conflict_ids"],
            "limitations": _LIMITATIONS,
        }
        return RecommendationExplanationRecord(
            explanation_id=deterministic_id(
                "recommendation-explanation", payload
            ),
            **payload,
        )

    @staticmethod
    def _generation(
        rule: RecommendationRuleDefinition,
        entry: _ScoreEntry,
        applicability: RecommendationApplicabilityRecord,
        explanation: RecommendationExplanationRecord,
        state: Mapping[str, Any],
    ) -> RecommendationGenerationRecord:
        calculation = entry.calculation
        payload = {
            "rule_id": rule.rule_id,
            "recommendation_applicability_id": (
                applicability.recommendation_applicability_id
            ),
            "input_evidence_ids": calculation["evidence_ids"],
            "decision_evaluation_ids": calculation["decision_evaluation_ids"],
            "score_component_ids": (entry.component["component_id"],),
            "score_calculation_ids": (calculation["calculation_id"],),
            "policy_evaluation_ids": calculation["policy_evaluation_ids"],
            "conflict_ids": calculation["conflict_ids"],
            "recommendation_type": state["recommendation_type"],
            "explanation_id": explanation.explanation_id,
            "process_interpretation": (
                "RULE_GENERATED_ADVISORY_RECORD_NOT_FACTUAL_TRUTH_OR_FINAL_DECISION"
            ),
        }
        return RecommendationGenerationRecord(
            recommendation_generation_id=deterministic_id(
                "recommendation-generation", payload
            ),
            **payload,
        )

    @staticmethod
    def _lineages(
        rule: RecommendationRuleDefinition,
        applicability: RecommendationApplicabilityRecord,
        generation: RecommendationGenerationRecord,
        explanation: RecommendationExplanationRecord,
        entry: _ScoreEntry,
        source: _SourceIndex,
    ) -> tuple[RecommendationLineageReference, ...]:
        result: list[RecommendationLineageReference] = []
        for upstream in source.score_lineages[entry.calculation["calculation_id"]]:
            payload = {
                "recommendation_rule_id": rule.rule_id,
                "recommendation_applicability_id": (
                    applicability.recommendation_applicability_id
                ),
                "recommendation_generation_id": (
                    generation.recommendation_generation_id
                ),
                "explanation_id": explanation.explanation_id,
                "score_factor_id": upstream["factor_id"],
                "score_component_id": upstream["component_id"],
                "score_calculation_id": upstream["calculation_id"],
                "score_lineage_id": upstream["score_lineage_id"],
                "decision_rule_id": upstream["rule_id"],
                "decision_evaluation_id": upstream["decision_evaluation_id"],
                "decision_lineage_id": upstream["decision_lineage_id"],
                "policy_id": upstream["policy_id"],
                "policy_evaluation_id": upstream["policy_evaluation_id"],
                "support_record_id": upstream["support_record_id"],
                "conflict_record_id": upstream["conflict_record_id"],
                "conflict_analysis_id": upstream["conflict_analysis_id"],
                "conflict_candidate_id": upstream["conflict_candidate_id"],
                "resolution_attempt_ids": upstream["resolution_attempt_ids"],
                "observation_id": upstream["observation_id"],
                "semantic_observation_id": upstream["semantic_observation_id"],
                "observation_kind": ObservationKind(upstream["observation_kind"]),
                "evidence_type": EvidenceType(upstream["evidence_type"]),
                "transformation_run_id": upstream["transformation_run_id"],
                "mapping_version": upstream["mapping_version"],
                "raw_evidence_id": upstream["raw_evidence_id"],
                "collection_run_id": upstream["collection_run_id"],
                "provider": upstream["provider"],
                "source_tool": upstream["source_tool"],
                "source_field": upstream["source_field"],
                "source_bundle_fingerprints": upstream[
                    "source_bundle_fingerprints"
                ],
            }
            result.append(RecommendationLineageReference(
                recommendation_lineage_id=deterministic_id(
                    "recommendation-lineage", payload
                ),
                **payload,
            ))
        return tuple(sorted(
            result, key=lambda item: item.recommendation_lineage_id
        ))

    @staticmethod
    def _diagnostic(
        code: str,
        generation: RecommendationGenerationRecord,
        message: str,
    ) -> RecommendationDiagnostic:
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_rule_ids": (generation.rule_id,),
            "related_recommendation_generation_ids": (
                generation.recommendation_generation_id,
            ),
            "message": message,
        }
        return RecommendationDiagnostic(
            diagnostic_id=deterministic_id(
                "recommendation-diagnostic", payload
            ),
            **payload,
        )

    def _diagnostics(
        self,
        generations: tuple[RecommendationGenerationRecord, ...],
    ) -> tuple[RecommendationDiagnostic, ...]:
        messages = {
            "FURTHER_REVIEW_RECOMMENDED": (
                "UNRESOLVED_CONFLICT_REQUIRES_FURTHER_REVIEW",
                "Further review was recorded because conflict remains visible; no candidate was selected.",
            ),
            "EVIDENCE_COLLECTION_RECOMMENDED": (
                "MISSING_EVIDENCE_REQUIRES_COLLECTION",
                "Evidence collection was recorded without treating missing evidence as a negative conclusion.",
            ),
            "RECOMMENDATION_BLOCKED_BY_POLICY": (
                "RECOMMENDATION_BLOCKED_BY_POLICY",
                "Policy blocked recommendation generation without rejecting a product or market.",
            ),
            "RULE_NOT_APPLICABLE": (
                "RECOMMENDATION_RULE_NOT_APPLICABLE",
                "The recommendation rule did not apply and no business conclusion was produced.",
            ),
        }
        diagnostics = [
            self._diagnostic(
                messages[item.recommendation_type][0],
                item,
                messages[item.recommendation_type][1],
            )
            for item in generations
            if item.recommendation_type in messages
        ]
        return tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id))


__all__ = ("RecommendationFrameworkBuilderV0_1",)
