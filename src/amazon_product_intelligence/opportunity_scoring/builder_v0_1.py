"""Deterministic Opportunity Scoring Framework V0.1 builder."""

from __future__ import annotations

from collections.abc import Iterable, Mapping as MappingABC
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

from .errors import OpportunityScoringValidationError
from .models import (
    OPPORTUNITY_SCORING_RULESET_VERSION,
    OpportunityScoringRequest,
    OpportunityScoringSnapshotV0_1,
    ScoreCalculationRecord,
    ScoreComponentRecord,
    ScoreDiagnostic,
    ScoreExplanationRecord,
    ScoreFactorDefinition,
    ScoreLineageReference,
    bundle_fingerprint,
    coverage_from_records,
    observation_revision_content,
)


_EVALUATION_SUPPORT_FIELDS = {
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
_EVIDENCE_LINEAGE_FIELDS = {
    "observation_id",
    "semantic_observation_id",
    "observation_kind",
    "transformation_run_id",
    "mapping_version",
    "raw_evidence_id",
    "collection_run_id",
    "provider",
    "source_tool",
    "source_field",
    "source_bundle_fingerprints",
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
_POLICY_AUDIT_FIELDS = {
    "policy_audit_id",
    "policy_id",
    "policy_version",
    "policy_applicability_id",
    "policy_evaluation_id",
    "condition_type",
    "condition_observations",
    "evaluation_result",
    "source_evaluation_snapshot_id",
    "source_conflict_resolution_snapshot_id",
}
_POLICY_LINEAGE_FIELDS = {
    "policy_lineage_id",
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
_DECISION_AUDIT_FIELDS = {
    "decision_audit_id",
    "rule_id",
    "rule_version",
    "decision_applicability_id",
    "decision_evaluation_id",
    "condition_type",
    "condition_observations",
    "applicability_result",
    "evaluation_result",
    "source_evaluation_snapshot_id",
    "source_conflict_resolution_snapshot_id",
    "source_policy_snapshot_id",
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
_RESULT_BY_APPLICABILITY = {
    "NOT_APPLICABLE": "RULE_NOT_APPLICABLE",
    "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
    "APPLICABLE": "RULE_ANALYSIS_RECORDED",
    "BLOCKED_BY_POLICY": "RULE_ANALYSIS_BLOCKED_BY_POLICY",
}
_EXPLANATION_TEMPLATE = (
    "Explain the factor rule, evidence references, calculation method, version, "
    "process status, and bounded interpretation."
)
_COMPONENT_EXPLANATION_BY_STATUS = {
    "CALCULATED": (
        "Upstream decision rule analysis is available for a versioned process calculation."
    ),
    "CALCULATED_WITH_CONFLICT_VISIBLE": (
        "Upstream decision rule analysis is available; unresolved conflicts remain visible."
    ),
    "BLOCKED_BY_POLICY": (
        "Upstream policy makes this component unavailable without rejecting a product."
    ),
    "EXCLUDED_MISSING_EVIDENCE": (
        "Required evidence is missing; this component is excluded without a numeric zero."
    ),
    "NOT_APPLICABLE": (
        "The upstream decision rule is not applicable; this component has no numeric result."
    ),
}


@dataclass(frozen=True, slots=True)
class _DecisionEvaluation:
    record: Mapping[str, Any]
    condition_type: str


class _CanonicalIndex:
    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(
            bundle_fingerprint(bundle) for bundle in bundles
        ))
        self.observations: dict[str, CanonicalObservation] = {}
        self.emissions: dict[str, tuple[Mapping[str, Any], ...]] = {}
        revisions: dict[str, str] = {}
        emission_payloads: dict[str, list[Mapping[str, Any]]] = {}
        runs: dict[str, Any] = {}
        raw_ids: set[str] = set()
        fingerprints_by_emission: dict[tuple[str, str], set[str]] = {}
        for bundle in bundles:
            fingerprint = bundle_fingerprint(bundle)
            raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise OpportunityScoringValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                revision = canonical_json(observation_revision_content(observation))
                prior = revisions.get(observation.observation_id)
                if prior is not None and prior != revision:
                    raise OpportunityScoringValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                revisions[observation.observation_id] = revision
                self.observations.setdefault(observation.observation_id, observation)
                run_id = observation.provenance.transformation.transformation_run_id
                fingerprints_by_emission.setdefault(
                    (observation.observation_id, run_id), set()
                ).add(fingerprint)
        for observation_id, observation in self.observations.items():
            for (candidate_id, run_id), fingerprints in fingerprints_by_emission.items():
                if candidate_id != observation_id:
                    continue
                emitted = next(
                    item
                    for bundle in bundles
                    for item in bundle.observations
                    if item.observation_id == observation_id
                    and item.provenance.transformation.transformation_run_id == run_id
                )
                transformation = emitted.provenance.transformation
                run = runs.get(run_id)
                if (
                    run is None
                    or transformation.raw_evidence_reference not in raw_ids
                    or transformation.raw_evidence_reference
                    not in run.input_raw_evidence_references
                    or observation_id not in run.output_observation_ids
                ):
                    raise OpportunityScoringValidationError(
                        f"broken canonical transformation lineage: {observation_id}"
                    )
                payload = {
                    "observation_id": observation_id,
                    "semantic_observation_id": emitted.semantic_observation_id,
                    "observation_kind": emitted.observation_kind.value,
                    "transformation_run_id": run_id,
                    "mapping_version": transformation.mapping_version,
                    "raw_evidence_id": transformation.raw_evidence_reference,
                    "collection_run_id": transformation.collection_run_id,
                    "provider": emitted.provenance.provider,
                    "source_tool": emitted.provenance.source_tool,
                    "source_field": emitted.provenance.source_field,
                    "source_bundle_fingerprints": tuple(sorted(fingerprints)),
                }
                emission_payloads.setdefault(observation_id, []).append(
                    MappingProxyType(payload)
                )
        self.emissions = {
            observation_id: tuple(sorted(values, key=canonical_json))
            for observation_id, values in emission_payloads.items()
        }


def _exact_fields(record: Any, fields: set[str], path: str) -> Mapping[str, Any]:
    if not isinstance(record, MappingABC) or set(record) != fields:
        actual = set(record) if isinstance(record, MappingABC) else set()
        raise OpportunityScoringValidationError(
            f"invalid {path} fields; missing={sorted(fields - actual)}, "
            f"extra={sorted(actual - fields)}"
        )
    return record


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OpportunityScoringValidationError(f"{path} must be non-empty text")
    return value


def _texts(value: Any, path: str, *, minimum: int = 0) -> tuple[str, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, tuple):
        raise OpportunityScoringValidationError(f"{path} must be an array")
    if len(value) < minimum or any(
        type(item) is not str or not item.strip() for item in value
    ):
        raise OpportunityScoringValidationError(f"{path} contains invalid text")
    if len(set(value)) != len(value) or tuple(sorted(value)) != value:
        raise OpportunityScoringValidationError(
            f"{path} must contain sorted unique text"
        )
    return value


def _identity(
    record: Mapping[str, Any], field: str, prefix: str, path: str
) -> str:
    value = _text(record[field], f"{path}.{field}")
    payload = dict(record)
    payload.pop(field)
    if value != deterministic_id(prefix, payload):
        raise OpportunityScoringValidationError(f"{path} identity mismatch")
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
        raise OpportunityScoringValidationError(f"{path} must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for index, value in enumerate(records):
        record = _exact_fields(value, fields, f"{path}[{index}]")
        identity = _identity(record, id_field, prefix, f"{path}[{index}]")
        if identity in result:
            raise OpportunityScoringValidationError(f"duplicate {path} identity")
        result[identity] = record
    return result


class _SourceIndex:
    def __init__(self, request: OpportunityScoringRequest) -> None:
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
        evaluation = request.evidence_evaluation_snapshot
        conflict = request.conflict_resolution_snapshot
        policy = request.evidence_policy_snapshot
        decision = request.decision_framework_snapshot
        self.supports = _unique_records(
            evaluation["support_records"],
            fields=_EVALUATION_SUPPORT_FIELDS,
            id_field="support_record_id",
            prefix="evidence-support",
            path="support_records",
        )
        self.evaluation_conflicts = _unique_records(
            evaluation["conflict_records"],
            fields=_EVALUATION_CONFLICT_FIELDS,
            id_field="conflict_record_id",
            prefix="evidence-conflict",
            path="conflict_records",
        )
        self._validate_evaluation_records()
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
        self._validate_conflict_records()
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
            path="policy_applicability_records",
        )
        self.policy_evaluations = _unique_records(
            policy["policy_evaluations"],
            fields=_POLICY_EVALUATION_FIELDS,
            id_field="policy_evaluation_id",
            prefix="policy-evaluation",
            path="policy_evaluations",
        )
        self.policy_audits = _unique_records(
            policy["audit_records"],
            fields=_POLICY_AUDIT_FIELDS,
            id_field="policy_audit_id",
            prefix="policy-audit",
            path="policy_audit_records",
        )
        self.policy_lineages = self._policy_lineages(policy["lineage_index"])
        self._validate_policy_records()
        self.rules = _unique_records(
            decision["rule_definitions"],
            fields=_DECISION_RULE_FIELDS,
            id_field="rule_id",
            prefix="decision-rule",
            path="decision_rule_definitions",
        )
        self.decision_applicability = _unique_records(
            decision["applicability_records"],
            fields=_DECISION_APPLICABILITY_FIELDS,
            id_field="decision_applicability_id",
            prefix="decision-applicability",
            path="decision_applicability_records",
        )
        raw_evaluations = _unique_records(
            decision["decision_evaluations"],
            fields=_DECISION_EVALUATION_FIELDS,
            id_field="decision_evaluation_id",
            prefix="decision-evaluation",
            path="decision_evaluations",
        )
        self.decision_audits = _unique_records(
            decision["audit_records"],
            fields=_DECISION_AUDIT_FIELDS,
            id_field="decision_audit_id",
            prefix="decision-audit",
            path="decision_audit_records",
        )
        self.decision_lineages = self._decision_lineages(
            decision["lineage_index"]
        )
        self.decision_evaluations = self._validate_decision_records(
            raw_evaluations
        )

    def _validate_evaluation_records(self) -> None:
        for support_id, support in self.supports.items():
            observation_ids = _texts(
                support["supporting_observation_ids"],
                f"support {support_id} observations",
                minimum=1,
            )
            if any(item not in self.canonical.observations for item in observation_ids):
                raise OpportunityScoringValidationError(
                    "support record references an orphan observation"
                )
            lineage = support["lineage_references"]
            if not isinstance(lineage, tuple):
                raise OpportunityScoringValidationError(
                    "support lineage_references must be an array"
                )
            observed_ids: set[str] = set()
            for index, value in enumerate(lineage):
                record = _exact_fields(
                    value,
                    _EVIDENCE_LINEAGE_FIELDS,
                    f"support lineage {support_id}[{index}]",
                )
                observation_id = record["observation_id"]
                emissions = self.canonical.emissions.get(observation_id, ())
                if canonical_json(record) not in {
                    canonical_json(item) for item in emissions
                }:
                    raise OpportunityScoringValidationError(
                        "support lineage does not replay canonical evidence"
                    )
                observed_ids.add(observation_id)
            if observed_ids != set(observation_ids):
                raise OpportunityScoringValidationError(
                    "support lineage does not cover supporting observations"
                )
        for conflict_id, conflict in self.evaluation_conflicts.items():
            support = self.supports.get(conflict["support_record_id"])
            candidates = _texts(
                conflict["candidate_observation_ids"],
                f"evaluation conflict {conflict_id} candidates",
                minimum=2,
            )
            if support is None or not set(candidates) <= set(
                support["supporting_observation_ids"]
            ):
                raise OpportunityScoringValidationError(
                    "evaluation conflict does not belong to its support record"
                )

    def _validate_conflict_records(self) -> None:
        analyses_by_source: dict[str, Mapping[str, Any]] = {}
        candidate_ids: set[str] = set()
        for analysis_id, analysis in self.analyses.items():
            source_id = analysis["source_evaluation_conflict_id"]
            source = self.evaluation_conflicts.get(source_id)
            if source is None or source_id in analyses_by_source:
                raise OpportunityScoringValidationError(
                    "conflict analysis source is orphaned or duplicated"
                )
            analyses_by_source[source_id] = analysis
            candidates = analysis["candidates"]
            if not isinstance(candidates, tuple) or not candidates:
                raise OpportunityScoringValidationError(
                    "conflict analysis requires candidates"
                )
            current_ids: set[str] = set()
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
                    candidate_id in candidate_ids
                    or candidate["source_evaluation_conflict_id"] != source_id
                    or candidate["observation_id"]
                    not in source["candidate_observation_ids"]
                ):
                    raise OpportunityScoringValidationError(
                        "conflict candidate identity or source mismatch"
                    )
                candidate_ids.add(candidate_id)
                current_ids.add(candidate_id)
            if current_ids != set(analysis["candidate_ids"]):
                raise OpportunityScoringValidationError(
                    "conflict analysis candidate IDs mismatch"
                )
        if set(analyses_by_source) != set(self.evaluation_conflicts):
            raise OpportunityScoringValidationError(
                "conflict analyses do not cover evaluation conflicts"
            )
        for attempt in self.attempts.values():
            analysis = self.analyses.get(attempt["conflict_analysis_id"])
            if analysis is None or set(attempt["candidate_ids"]) != set(
                analysis["candidate_ids"]
            ):
                raise OpportunityScoringValidationError(
                    "resolution attempt does not match conflict analysis"
                )

    def _policy_lineages(
        self, values: Any
    ) -> dict[str, tuple[Mapping[str, Any], ...]]:
        if not isinstance(values, tuple):
            raise OpportunityScoringValidationError(
                "policy lineage_index must be an array"
            )
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        identities: set[str] = set()
        for index, value in enumerate(values):
            record = _exact_fields(
                value, _POLICY_LINEAGE_FIELDS, f"policy lineage[{index}]"
            )
            identity = _identity(
                record,
                "policy_lineage_id",
                "policy-lineage",
                f"policy lineage[{index}]",
            )
            if identity in identities:
                raise OpportunityScoringValidationError(
                    "duplicate policy lineage identity"
                )
            identities.add(identity)
            grouped.setdefault(record["policy_evaluation_id"], []).append(record)
        return {
            key: tuple(sorted(items, key=lambda item: item["policy_lineage_id"]))
            for key, items in grouped.items()
        }

    def _validate_policy_records(self) -> None:
        audits_by_evaluation = {
            item["policy_evaluation_id"]: item
            for item in self.policy_audits.values()
        }
        for evaluation_id, evaluation in self.policy_evaluations.items():
            definition = self.policy_definitions.get(evaluation["policy_id"])
            applicability = self.policy_applicability.get(
                evaluation["policy_applicability_id"]
            )
            audit = audits_by_evaluation.get(evaluation_id)
            if (
                definition is None
                or applicability is None
                or audit is None
                or applicability["policy_id"] != evaluation["policy_id"]
                or audit["policy_id"] != evaluation["policy_id"]
                or audit["policy_applicability_id"]
                != evaluation["policy_applicability_id"]
                or audit["evaluation_result"] != evaluation["evaluation_result"]
            ):
                raise OpportunityScoringValidationError(
                    "policy evaluation audit continuity mismatch"
                )
            evidence_ids = _texts(
                evaluation["input_evidence_ids"],
                f"policy evaluation {evaluation_id} evidence",
                minimum=1,
            )
            conflict_ids = _texts(
                evaluation["conflict_ids"],
                f"policy evaluation {evaluation_id} conflicts",
            )
            if not set(evidence_ids) <= set(self.supports) or not set(
                conflict_ids
            ) <= set(self.evaluation_conflicts):
                raise OpportunityScoringValidationError(
                    "policy evaluation contains orphan evidence"
                )
            lineages = self.policy_lineages.get(evaluation_id, ())
            if {item["support_record_id"] for item in lineages} != set(
                evidence_ids
            ) or {
                item["conflict_record_id"]
                for item in lineages
                if item["conflict_record_id"] is not None
            } != set(conflict_ids):
                raise OpportunityScoringValidationError(
                    "policy lineage does not cover evaluation inputs"
                )
            for lineage in lineages:
                if lineage["policy_id"] != evaluation["policy_id"]:
                    raise OpportunityScoringValidationError(
                        "policy lineage policy mismatch"
                    )
                self._validate_policy_lineage(lineage)

    def _validate_policy_lineage(self, lineage: Mapping[str, Any]) -> None:
        support = self.supports.get(lineage["support_record_id"])
        observation_id = lineage["observation_id"]
        if (
            support is None
            or observation_id not in support["supporting_observation_ids"]
        ):
            raise OpportunityScoringValidationError(
                "policy lineage contains orphan support evidence"
            )
        source_payload = {
            key: lineage[key]
            for key in _EVIDENCE_LINEAGE_FIELDS
        }
        if canonical_json(source_payload) not in {
            canonical_json(item) for item in self.canonical.emissions[observation_id]
        }:
            raise OpportunityScoringValidationError(
                "policy lineage does not replay canonical evidence"
            )
        observation = self.canonical.observations[observation_id]
        if (
            lineage["observation_kind"] != observation.observation_kind.value
            or lineage["evidence_type"] != observation.evidence_type.value
        ):
            raise OpportunityScoringValidationError(
                "policy lineage canonical type mismatch"
            )
        conflict_id = lineage["conflict_record_id"]
        conflict_values = (
            conflict_id,
            lineage["conflict_analysis_id"],
            lineage["conflict_candidate_id"],
        )
        if any(item is None for item in conflict_values) != all(
            item is None for item in conflict_values
        ):
            raise OpportunityScoringValidationError(
                "policy conflict lineage must be complete"
            )
        if conflict_id is not None:
            source_conflict = self.evaluation_conflicts.get(conflict_id)
            analysis = self.analyses.get(lineage["conflict_analysis_id"])
            if (
                source_conflict is None
                or analysis is None
                or analysis["source_evaluation_conflict_id"] != conflict_id
                or lineage["conflict_candidate_id"] not in analysis["candidate_ids"]
                or observation_id not in source_conflict["candidate_observation_ids"]
                or not set(lineage["resolution_attempt_ids"]) <= set(self.attempts)
            ):
                raise OpportunityScoringValidationError(
                    "policy conflict lineage does not replay conflict process"
                )

    def _decision_lineages(
        self, values: Any
    ) -> dict[str, tuple[Mapping[str, Any], ...]]:
        if not isinstance(values, tuple):
            raise OpportunityScoringValidationError(
                "decision lineage_index must be an array"
            )
        grouped: dict[str, list[Mapping[str, Any]]] = {}
        identities: set[str] = set()
        policy_payloads = {
            canonical_json({
                key: lineage[key]
                for key in _POLICY_LINEAGE_FIELDS
                if key != "policy_lineage_id"
            })
            for lineages in self.policy_lineages.values()
            for lineage in lineages
        }
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
                raise OpportunityScoringValidationError(
                    "duplicate decision lineage identity"
                )
            identities.add(identity)
            upstream = {
                key: record[key]
                for key in _POLICY_LINEAGE_FIELDS
                if key != "policy_lineage_id"
            }
            if canonical_json(upstream) not in policy_payloads:
                raise OpportunityScoringValidationError(
                    "decision lineage does not replay policy lineage"
                )
            grouped.setdefault(record["decision_evaluation_id"], []).append(record)
        return {
            key: tuple(sorted(items, key=lambda item: item["decision_lineage_id"]))
            for key, items in grouped.items()
        }

    def _validate_decision_records(
        self, raw: Mapping[str, Mapping[str, Any]]
    ) -> tuple[_DecisionEvaluation, ...]:
        conditions: dict[str, str] = {}
        for rule_id, rule in self.rules.items():
            conditions_payload = rule["conditions"]
            if not isinstance(conditions_payload, MappingABC):
                raise OpportunityScoringValidationError(
                    "decision rule conditions must be an object"
                )
            condition = conditions_payload.get("condition_type")
            if condition not in {
                "EVIDENCE_INVENTORY",
                "CONFLICT_FREE_EVIDENCE",
                "KEYWORD_EVIDENCE",
                "CONFLICT_CONTEXT",
            } or condition in conditions.values():
                raise OpportunityScoringValidationError(
                    "decision rules do not contain the fixed V0.1 conditions"
                )
            conditions[rule_id] = condition
        if set(conditions.values()) != {
            "EVIDENCE_INVENTORY",
            "CONFLICT_FREE_EVIDENCE",
            "KEYWORD_EVIDENCE",
            "CONFLICT_CONTEXT",
        }:
            raise OpportunityScoringValidationError(
                "decision rules do not cover fixed V0.1 conditions"
            )
        applicability_by_rule = {
            item["rule_id"]: item for item in self.decision_applicability.values()
        }
        audits_by_evaluation = {
            item["decision_evaluation_id"]: item
            for item in self.decision_audits.values()
        }
        results: list[_DecisionEvaluation] = []
        seen_rules: set[str] = set()
        for evaluation_id, evaluation in raw.items():
            rule_id = evaluation["rule_id"]
            applies = applicability_by_rule.get(rule_id)
            audit = audits_by_evaluation.get(evaluation_id)
            if (
                rule_id not in self.rules
                or rule_id in seen_rules
                or applies is None
                or audit is None
                or evaluation["decision_applicability_id"]
                != applies["decision_applicability_id"]
                or evaluation["evaluation_result"]
                != _RESULT_BY_APPLICABILITY.get(applies["applicability_result"])
                or audit["rule_id"] != rule_id
                or audit["decision_applicability_id"]
                != applies["decision_applicability_id"]
                or audit["evaluation_result"] != evaluation["evaluation_result"]
            ):
                raise OpportunityScoringValidationError(
                    "decision evaluation, applicability, or audit continuity mismatch"
                )
            seen_rules.add(rule_id)
            evidence_ids = _texts(
                evaluation["input_evidence_ids"],
                f"decision evaluation {evaluation_id} evidence",
                minimum=1,
            )
            policy_ids = _texts(
                evaluation["policy_evaluation_ids"],
                f"decision evaluation {evaluation_id} policies",
                minimum=1,
            )
            conflict_ids = _texts(
                evaluation["conflict_ids"],
                f"decision evaluation {evaluation_id} conflicts",
            )
            if (
                not set(evidence_ids) <= set(self.supports)
                or not set(policy_ids) <= set(self.policy_evaluations)
                or not set(conflict_ids) <= set(self.evaluation_conflicts)
                or policy_ids != applies["policy_evaluation_ids"]
            ):
                raise OpportunityScoringValidationError(
                    "decision evaluation contains orphan upstream references"
                )
            analysis = evaluation["analysis_output"]
            if not isinstance(analysis, MappingABC) or set(analysis) != {
                "record_type",
                "applicability_result",
                "process_interpretation",
            } or analysis["record_type"] != "DECISION_RULE_ANALYSIS" or analysis[
                "applicability_result"
            ] != applies["applicability_result"] or analysis[
                "process_interpretation"
            ] != "ANALYSIS_RECORD_ONLY_NO_BUSINESS_CONCLUSION":
                raise OpportunityScoringValidationError(
                    "decision analysis output does not match applicability"
                )
            blocked = any(
                self.policy_evaluations[item]["evaluation_result"]
                == "ACTION_BLOCKED"
                for item in policy_ids
            )
            if (
                evaluation["evaluation_result"]
                == "RULE_ANALYSIS_BLOCKED_BY_POLICY"
            ) != blocked and applies["applicability_result"] != "INSUFFICIENT_EVIDENCE":
                raise OpportunityScoringValidationError(
                    "decision policy-block result does not replay policy evaluations"
                )
            lineages = self.decision_lineages.get(evaluation_id, ())
            if {item["policy_evaluation_id"] for item in lineages} != set(
                policy_ids
            ) or {item["support_record_id"] for item in lineages} != set(
                evidence_ids
            ) or {
                item["conflict_record_id"]
                for item in lineages
                if item["conflict_record_id"] is not None
            } != set(conflict_ids):
                raise OpportunityScoringValidationError(
                    "decision lineage does not cover evaluation inputs"
                )
            if any(
                item["rule_id"] != rule_id for item in lineages
            ):
                raise OpportunityScoringValidationError(
                    "decision lineage rule mismatch"
                )
            results.append(_DecisionEvaluation(
                record=evaluation,
                condition_type=conditions[rule_id],
            ))
        if seen_rules != set(self.rules):
            raise OpportunityScoringValidationError(
                "every decision rule requires exactly one evaluation"
            )
        return tuple(sorted(
            results,
            key=lambda item: item.record["decision_evaluation_id"],
        ))


def _factor(
    name: str, description: str, condition_type: str
) -> ScoreFactorDefinition:
    payload = {
        "factor_version": "0.1",
        "name": name,
        "description": description,
        "input_requirements": {
            "decision_condition_type": condition_type,
            "source_record_type": "DECISION_EVALUATION",
        },
        "calculation_rule": {
            "calculation_method": "FIXED_PROCESS_RULE_RESULT_V0_1",
            "conflict_behavior": "PRESERVE_AND_MARK_VISIBLE",
            "missing_evidence_behavior": "EXCLUDE_WITHOUT_NUMERIC_RESULT",
            "policy_block_behavior": "UNAVAILABLE_WITHOUT_NUMERIC_RESULT",
        },
        "explanation_template": _EXPLANATION_TEMPLATE,
        "expected_behavior": "NUMERIC_PROCESS_RESULT_ONLY_NO_RECOMMENDATION",
    }
    return ScoreFactorDefinition(
        factor_id=deterministic_id("score-factor", payload), **payload
    )


def _default_factors() -> tuple[ScoreFactorDefinition, ...]:
    return tuple(sorted((
        _factor(
            "Evidence Availability Factor",
            "Records a versioned numeric process result only when the evidence-inventory decision analysis is available.",
            "EVIDENCE_INVENTORY",
        ),
        _factor(
            "Conflict-Free Analysis Factor",
            "Records whether conflict-free analysis is calculable under upstream policy without selecting evidence candidates.",
            "CONFLICT_FREE_EVIDENCE",
        ),
        _factor(
            "Keyword Evidence Factor",
            "Records keyword-evidence rule availability while keeping missing evidence distinct from a zero result.",
            "KEYWORD_EVIDENCE",
        ),
        _factor(
            "Conflict Context Factor",
            "Records a numeric process result with conflicts visible and without resolving or ranking candidates.",
            "CONFLICT_CONTEXT",
        ),
    ), key=lambda item: item.factor_id))


class OpportunityScoringBuilderV0_1:
    """Build auditable numeric rule results without making a business decision."""

    def build(
        self, request: OpportunityScoringRequest
    ) -> OpportunityScoringSnapshotV0_1:
        if not isinstance(request, OpportunityScoringRequest):
            raise OpportunityScoringValidationError(
                "request must be OpportunityScoringRequest"
            )
        source = _SourceIndex(request)
        factors = _default_factors()
        factors_by_condition = {
            item.input_requirements["decision_condition_type"]: item
            for item in factors
        }
        components: list[ScoreComponentRecord] = []
        calculations: list[ScoreCalculationRecord] = []
        explanations: list[ScoreExplanationRecord] = []
        lineages: list[ScoreLineageReference] = []
        for decision in source.decision_evaluations:
            factor = factors_by_condition[decision.condition_type]
            state = self._state(decision.record)
            component = self._component(factor, decision.record, state)
            calculation = self._calculation(
                factor,
                component,
                decision.record,
                tuple(
                    item["decision_lineage_id"]
                    for item in source.decision_lineages[
                        decision.record["decision_evaluation_id"]
                    ]
                ),
                state,
            )
            explanation = self._explanation(
                factor, component, calculation, state
            )
            components.append(component)
            calculations.append(calculation)
            explanations.append(explanation)
            lineages.extend(self._lineages(
                factor, component, calculation, decision.record, source
            ))
        ordered_components = tuple(sorted(
            components, key=lambda item: item.component_id
        ))
        ordered_calculations = tuple(sorted(
            calculations, key=lambda item: item.calculation_id
        ))
        ordered_explanations = tuple(sorted(
            explanations, key=lambda item: item.explanation_id
        ))
        ordered_lineages = tuple(sorted(
            lineages, key=lambda item: item.score_lineage_id
        ))
        diagnostics = self._diagnostics(
            factors, ordered_components, ordered_calculations
        )
        coverage = coverage_from_records(
            bundle_count=len(source.canonical.bundle_fingerprints),
            factors=factors,
            components=ordered_components,
            calculations=ordered_calculations,
            explanations=ordered_explanations,
            diagnostics=diagnostics,
            lineage=ordered_lineages,
        )
        payload = {
            "ruleset_version": OPPORTUNITY_SCORING_RULESET_VERSION,
            "source_evaluation_snapshot_id": source.evaluation_snapshot_id,
            "source_conflict_resolution_snapshot_id": source.conflict_snapshot_id,
            "source_policy_snapshot_id": source.policy_snapshot_id,
            "source_decision_snapshot_id": source.decision_snapshot_id,
            "source_bundle_fingerprints": source.canonical.bundle_fingerprints,
            "score_factors": factors,
            "components": ordered_components,
            "calculations": ordered_calculations,
            "explanations": ordered_explanations,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": ordered_lineages,
        }
        snapshot = OpportunityScoringSnapshotV0_1(
            snapshot_id=deterministic_id(
                "opportunity-scoring-snapshot", payload
            ),
            **payload,
        )
        return snapshot.validate_against_bundles(request.canonical_bundles)

    @staticmethod
    def _state(decision: Mapping[str, Any]) -> Mapping[str, Any]:
        result = decision["evaluation_result"]
        if result == "RULE_ANALYSIS_RECORDED":
            if decision["conflict_ids"]:
                status = "CALCULATED_WITH_CONFLICT_VISIBLE"
                reasons = (
                    "CONFLICT_PRESENT_AND_VISIBLE_NO_WINNER_SELECTED",
                    "DECISION_RULE_ANALYSIS_RECORDED",
                )
            else:
                status = "CALCULATED"
                reasons = ("DECISION_RULE_ANALYSIS_RECORDED",)
            value: int | None = 25
        elif result == "RULE_ANALYSIS_BLOCKED_BY_POLICY":
            status = "BLOCKED_BY_POLICY"
            value = None
            reasons = ("UPSTREAM_POLICY_BLOCKS_COMPONENT_NOT_PRODUCT",)
        elif result == "INSUFFICIENT_EVIDENCE":
            status = "EXCLUDED_MISSING_EVIDENCE"
            value = None
            reasons = ("MISSING_EVIDENCE_EXCLUDED_NOT_ZERO",)
        elif result == "RULE_NOT_APPLICABLE":
            status = "NOT_APPLICABLE"
            value = None
            reasons = ("DECISION_RULE_NOT_APPLICABLE",)
        else:
            raise OpportunityScoringValidationError(
                "unsupported decision evaluation result"
            )
        method_by_status = {
            "CALCULATED": "FIXED_PROCESS_RULE_RESULT_V0_1",
            "CALCULATED_WITH_CONFLICT_VISIBLE": (
                "FIXED_PROCESS_RULE_RESULT_WITH_CONFLICT_VISIBLE_V0_1"
            ),
            "BLOCKED_BY_POLICY": "NO_NUMERIC_RESULT_POLICY_BLOCKED_V0_1",
            "EXCLUDED_MISSING_EVIDENCE": (
                "NO_NUMERIC_RESULT_MISSING_EVIDENCE_V0_1"
            ),
            "NOT_APPLICABLE": "NO_NUMERIC_RESULT_NOT_APPLICABLE_V0_1",
        }
        return MappingProxyType({
            "status": status,
            "result_value": value,
            "calculation_method": method_by_status[status],
            "component_explanation": _COMPONENT_EXPLANATION_BY_STATUS[status],
            "reason_codes": reasons,
        })

    @staticmethod
    def _component(
        factor: ScoreFactorDefinition,
        decision: Mapping[str, Any],
        state: Mapping[str, Any],
    ) -> ScoreComponentRecord:
        payload = {
            "factor_id": factor.factor_id,
            "decision_evaluation_id": decision["decision_evaluation_id"],
            "input_evidence_ids": decision["input_evidence_ids"],
            "policy_evaluation_ids": decision["policy_evaluation_ids"],
            "conflict_ids": decision["conflict_ids"],
            "component_status": state["status"],
            "component_explanation": state["component_explanation"],
            "reason_codes": state["reason_codes"],
        }
        return ScoreComponentRecord(
            component_id=deterministic_id("score-component", payload), **payload
        )

    @staticmethod
    def _calculation(
        factor: ScoreFactorDefinition,
        component: ScoreComponentRecord,
        decision: Mapping[str, Any],
        decision_lineage_ids: tuple[str, ...],
        state: Mapping[str, Any],
    ) -> ScoreCalculationRecord:
        payload = {
            "factor_id": factor.factor_id,
            "component_id": component.component_id,
            "calculation_method": state["calculation_method"],
            "input_components": (component.component_id,),
            "result_value": state["result_value"],
            "result_status": state["status"],
            "version": "0.1",
            "decision_evaluation_ids": (decision["decision_evaluation_id"],),
            "decision_lineage_ids": decision_lineage_ids,
            "policy_evaluation_ids": decision["policy_evaluation_ids"],
            "conflict_ids": decision["conflict_ids"],
            "evidence_ids": decision["input_evidence_ids"],
            "process_interpretation": (
                "RULE_NUMERIC_RESULT_ONLY_NO_RECOMMENDATION_OR_DECISION"
            ),
        }
        return ScoreCalculationRecord(
            calculation_id=deterministic_id("score-calculation", payload), **payload
        )

    @staticmethod
    def _explanation(
        factor: ScoreFactorDefinition,
        component: ScoreComponentRecord,
        calculation: ScoreCalculationRecord,
        state: Mapping[str, Any],
    ) -> ScoreExplanationRecord:
        interpretations = {
            "CALCULATED": (
                "The current V0.1 rule produced a process numeric result; it is not a recommendation, truth claim, or decision."
            ),
            "CALCULATED_WITH_CONFLICT_VISIBLE": (
                "The current V0.1 rule produced a process numeric result while preserving unresolved conflict; no candidate was selected."
            ),
            "BLOCKED_BY_POLICY": (
                "Upstream policy made this score component unavailable; no product or market was rejected."
            ),
            "EXCLUDED_MISSING_EVIDENCE": (
                "Required evidence was missing, so this component has no numeric result and missing was not treated as zero."
            ),
            "NOT_APPLICABLE": (
                "The upstream decision rule was not applicable, so this component has no numeric result."
            ),
        }
        payload = {
            "factor_id": factor.factor_id,
            "component_id": component.component_id,
            "calculation_id": calculation.calculation_id,
            "factor_explanation": factor.description,
            "calculation_rule": calculation.calculation_method,
            "version": calculation.version,
            "evidence_ids": calculation.evidence_ids,
            "decision_evaluation_ids": calculation.decision_evaluation_ids,
            "policy_evaluation_ids": calculation.policy_evaluation_ids,
            "conflict_ids": calculation.conflict_ids,
            "result_interpretation": interpretations[state["status"]],
        }
        return ScoreExplanationRecord(
            explanation_id=deterministic_id("score-explanation", payload), **payload
        )

    @staticmethod
    def _lineages(
        factor: ScoreFactorDefinition,
        component: ScoreComponentRecord,
        calculation: ScoreCalculationRecord,
        decision: Mapping[str, Any],
        source: _SourceIndex,
    ) -> tuple[ScoreLineageReference, ...]:
        result: list[ScoreLineageReference] = []
        for upstream in source.decision_lineages[
            decision["decision_evaluation_id"]
        ]:
            payload = {
                "factor_id": factor.factor_id,
                "component_id": component.component_id,
                "calculation_id": calculation.calculation_id,
                "rule_id": upstream["rule_id"],
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
            result.append(ScoreLineageReference(
                score_lineage_id=deterministic_id("score-lineage", payload),
                **payload,
            ))
        return tuple(sorted(result, key=lambda item: item.score_lineage_id))

    @staticmethod
    def _diagnostic(
        code: str,
        factor: ScoreFactorDefinition,
        component: ScoreComponentRecord,
        calculation: ScoreCalculationRecord,
        message: str,
    ) -> ScoreDiagnostic:
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_factor_ids": (factor.factor_id,),
            "related_component_ids": (component.component_id,),
            "related_calculation_ids": (calculation.calculation_id,),
            "message": message,
        }
        return ScoreDiagnostic(
            diagnostic_id=deterministic_id("score-diagnostic", payload), **payload
        )

    def _diagnostics(
        self,
        factors: tuple[ScoreFactorDefinition, ...],
        components: tuple[ScoreComponentRecord, ...],
        calculations: tuple[ScoreCalculationRecord, ...],
    ) -> tuple[ScoreDiagnostic, ...]:
        factors_by_id = {item.factor_id: item for item in factors}
        calculations_by_factor = {item.factor_id: item for item in calculations}
        messages = {
            "CALCULATED_WITH_CONFLICT_VISIBLE": (
                "CONFLICT_VISIBLE_IN_NUMERIC_PROCESS_RESULT",
                "Unresolved conflict remains visible in the calculation and no candidate was selected.",
            ),
            "BLOCKED_BY_POLICY": (
                "SCORE_COMPONENT_BLOCKED_BY_POLICY",
                "Policy blocked this component without rejecting a product or market.",
            ),
            "EXCLUDED_MISSING_EVIDENCE": (
                "MISSING_EVIDENCE_EXCLUDED_NOT_ZERO",
                "Missing evidence was explicitly excluded and did not become a zero result.",
            ),
            "NOT_APPLICABLE": (
                "SCORE_COMPONENT_NOT_APPLICABLE",
                "The decision rule was not applicable and no numeric result was produced.",
            ),
        }
        diagnostics: list[ScoreDiagnostic] = []
        for component in components:
            details = messages.get(component.component_status)
            if details is None:
                continue
            diagnostics.append(self._diagnostic(
                details[0],
                factors_by_id[component.factor_id],
                component,
                calculations_by_factor[component.factor_id],
                details[1],
            ))
        return tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id))


__all__ = ("OpportunityScoringBuilderV0_1",)
