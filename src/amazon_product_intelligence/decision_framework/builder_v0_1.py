"""Auditable, declarative Decision Framework V0.1 builder."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    EvidenceType,
    KeywordMetricObservation,
    MetricObservation,
    ObservationKind,
    ProductFactObservation,
    ProductKeywordRelationshipObservation,
    ReviewObservation,
    Severity,
    SubjectRef,
    canonical_json,
    deterministic_id,
)

from .errors import DecisionFrameworkValidationError
from .models import (
    DECISION_FRAMEWORK_RULESET_VERSION,
    DecisionApplicabilityRecord,
    DecisionAuditRecord,
    DecisionDiagnostic,
    DecisionEvaluationRecord,
    DecisionFrameworkRequest,
    DecisionFrameworkSnapshotV0_1,
    DecisionLineageReference,
    DecisionRuleDefinition,
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
_SOURCE_LINEAGE_FIELDS = {
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
_ANALYSIS_FIELDS = {
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
_CANDIDATE_FIELDS = {
    "candidate_id",
    "source_evaluation_conflict_id",
    "observation_id",
    "value",
    "provider",
    "source",
    "lineage_references",
}
_ATTEMPT_FIELDS = {
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
_POLICY_CONDITION_BEHAVIORS = {
    "MINIMUM_PROVIDER_COUNT": "RECORD_SUPPORT_CONTEXT_WITHOUT_ACTION",
    "LINEAGE_COMPLETENESS_REQUIRED": "ALLOW_PROCESS_ONLY_WITH_COMPLETE_LINEAGE",
    "CONFLICT_PRESENT": "BLOCK_AUTOMATIC_INTERPRETATION_AND_REQUIRE_REVIEW",
}
_POLICY_RESULTS = {
    "NOT_APPLICABLE",
    "APPLICABLE_NO_ACTION",
    "ACTION_ALLOWED",
    "ACTION_BLOCKED",
}
_ATTEMPT_STATUSES = {
    "NOT_ATTEMPTED",
    "INSUFFICIENT_EVIDENCE",
    "AMBIGUOUS",
    "RESOLUTION_PRODUCED",
}
_FORBIDDEN_METHOD_TOKENS = {
    "PROVIDER_PRIORITY",
    "LATEST",
    "HIGHEST",
    "LOWEST",
    "AVERAGE",
    "MEDIAN",
    "MAJORITY",
    "CONFIDENCE",
    "TRUST",
    "SCORE",
    "RANKING",
    "WEIGHT",
    "PROBABILITY",
    "RECOMMENDATION",
    "PROVIDER",
    "PREFERRED",
    "WINNER",
    "WINS",
}
_FORBIDDEN_PROCESS_FIELD_TOKENS = {
    "WINNER",
    "SCORE",
    "CONFIDENCE",
    "TRUST",
    "RECOMMENDATION",
    "RANKING",
    "WEIGHT",
    "PROBABILITY",
    "PREFERRED",
    "PRIORITY",
    "TRUTH",
}


@dataclass(slots=True)
class _Emission:
    observation: CanonicalObservation
    bundle_fingerprints: set[str]


@dataclass(frozen=True, slots=True)
class _Support:
    record: Mapping[str, Any]
    support_record_id: str
    observation_ids: tuple[str, ...]
    observation_kind: ObservationKind
    lineage_completeness: str


@dataclass(frozen=True, slots=True)
class _EvaluationConflict:
    record: Mapping[str, Any]
    conflict_record_id: str
    support_record_id: str
    candidate_observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Analysis:
    record: Mapping[str, Any]
    conflict_analysis_id: str
    source_conflict_id: str
    candidate_by_observation: Mapping[str, str]
    attempt_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _PolicyEvaluation:
    record: Mapping[str, Any]
    policy_id: str
    policy_evaluation_id: str
    condition_type: str
    evaluation_result: str
    input_evidence_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...]


class _CanonicalIndex:
    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(bundle_fingerprint(item) for item in bundles))
        self.observation_revisions: dict[str, str] = {}
        self.observations: dict[str, dict[str, _Emission]] = defaultdict(dict)
        self.runs: dict[str, Any] = {}
        self.raw_ids: set[str] = set()
        for fingerprint, bundle in sorted(
            ((bundle_fingerprint(item), item) for item in bundles), key=lambda item: item[0]
        ):
            self.raw_ids.update(bundle.raw_evidence_references)
            for run in bundle.transformation_runs:
                current = self.runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise DecisionFrameworkValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                self.runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                revision = canonical_json(observation_revision_content(observation))
                prior = self.observation_revisions.get(observation.observation_id)
                if prior is not None and prior != revision:
                    raise DecisionFrameworkValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                self.observation_revisions[observation.observation_id] = revision
                run_id = observation.provenance.transformation.transformation_run_id
                current = self.observations[observation.observation_id].get(run_id)
                if current is not None and canonical_json(current.observation) != canonical_json(
                    observation
                ):
                    raise DecisionFrameworkValidationError(
                        f"observation emission collision: {observation.observation_id}"
                    )
                if current is None:
                    self.observations[observation.observation_id][run_id] = _Emission(
                        observation=observation,
                        bundle_fingerprints={fingerprint},
                    )
                else:
                    current.bundle_fingerprints.add(fingerprint)

    def representative(self, observation_id: str) -> CanonicalObservation:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise DecisionFrameworkValidationError(f"orphan evidence: {observation_id}")
        return min(
            emissions.values(), key=lambda item: canonical_json(item.observation)
        ).observation

    def lineage_payloads(self, observation_id: str) -> tuple[Mapping[str, Any], ...]:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise DecisionFrameworkValidationError(f"orphan evidence: {observation_id}")
        result: list[Mapping[str, Any]] = []
        for run_id, emission in sorted(emissions.items()):
            observation = emission.observation
            transformation = observation.provenance.transformation
            run = self.runs.get(run_id)
            raw_id = transformation.raw_evidence_reference
            if run is None:
                raise DecisionFrameworkValidationError(f"orphan transformation run: {run_id}")
            if (
                raw_id not in self.raw_ids
                or raw_id not in run.input_raw_evidence_references
                or run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or observation_id not in run.output_observation_ids
            ):
                raise DecisionFrameworkValidationError(
                    f"broken canonical lineage: {observation_id}"
                )
            result.append({
                "observation_id": observation_id,
                "semantic_observation_id": observation.semantic_observation_id,
                "observation_kind": observation.observation_kind,
                "transformation_run_id": run_id,
                "mapping_version": transformation.mapping_version,
                "raw_evidence_id": raw_id,
                "collection_run_id": transformation.collection_run_id,
                "provider": observation.provenance.provider,
                "source_tool": observation.provenance.source_tool,
                "source_field": observation.provenance.source_field,
                "source_bundle_fingerprints": tuple(sorted(emission.bundle_fingerprints)),
            })
        return tuple(sorted(result, key=canonical_json))


def _observation_dimension(observation: CanonicalObservation) -> str:
    if isinstance(observation, ProductFactObservation):
        return observation.dimension
    if isinstance(observation, MetricObservation):
        return observation.metric
    if isinstance(observation, KeywordMetricObservation):
        return observation.metric
    if isinstance(observation, ProductKeywordRelationshipObservation):
        return ":".join((
            "relationship",
            observation.direction.value,
            observation.relationship_type.value,
            observation.channel.value,
        ))
    if isinstance(observation, ReviewObservation):
        return "review"
    raise DecisionFrameworkValidationError(
        f"unsupported canonical observation type: {type(observation).__name__}"
    )


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise DecisionFrameworkValidationError(f"{path} must be an object")
    return value


def _exact_fields(record: Mapping[str, Any], fields: set[str], path: str) -> None:
    if set(record) != fields:
        raise DecisionFrameworkValidationError(f"{path} fields do not match V0.1")


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise DecisionFrameworkValidationError(f"{path} must be non-empty text")
    return value


def _texts(value: Any, path: str, *, minimum: int = 0) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise DecisionFrameworkValidationError(f"{path} must be an array")
    if len(value) < minimum:
        raise DecisionFrameworkValidationError(f"{path} requires at least {minimum} values")
    if any(type(item) is not str or not item.strip() for item in value):
        raise DecisionFrameworkValidationError(f"{path} must contain non-empty text")
    if len(set(value)) != len(value):
        raise DecisionFrameworkValidationError(f"{path} must contain unique values")
    return tuple(sorted(value))


def _identity(record: Mapping[str, Any], field: str, prefix: str, path: str) -> str:
    identity = _text(record[field], f"{path}.{field}")
    content = dict(record)
    content.pop(field)
    if identity != deterministic_id(prefix, content):
        raise DecisionFrameworkValidationError(f"{path} identity mismatch")
    return identity


def _lineage_set(
    value: Any, path: str, observation_ids: Iterable[str], index: _CanonicalIndex
) -> set[str]:
    if not isinstance(value, tuple):
        raise DecisionFrameworkValidationError(f"{path} must be an array")
    actual: list[str] = []
    for item in value:
        record = _mapping(item, path)
        _exact_fields(record, _SOURCE_LINEAGE_FIELDS, path)
        actual.append(canonical_json(record))
    if len(set(actual)) != len(actual):
        raise DecisionFrameworkValidationError(f"{path} must contain unique lineage")
    expected = {
        canonical_json(lineage)
        for observation_id in observation_ids
        for lineage in index.lineage_payloads(observation_id)
    }
    if set(actual) != expected:
        raise DecisionFrameworkValidationError(f"{path} does not replay canonical lineage")
    return set(actual)


def _reject_forbidden_process_fields(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, child in value.items():
            normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")
            if set(normalized.split("_")) & _FORBIDDEN_PROCESS_FIELD_TOKENS:
                raise DecisionFrameworkValidationError(
                    f"{path}.{key} uses a forbidden preference field"
                )
            _reject_forbidden_process_fields(child, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, child in enumerate(value):
            _reject_forbidden_process_fields(child, f"{path}[{index}]")


class _EvaluationIndex:
    def __init__(self, payload: Mapping[str, Any], canonical: _CanonicalIndex) -> None:
        self.snapshot_id = payload["snapshot_id"]
        self.supports: dict[str, _Support] = {}
        self.conflicts: dict[str, _EvaluationConflict] = {}
        self.conflict_by_support: dict[str, _EvaluationConflict] = {}
        for raw in payload["support_records"]:
            support = self._support(_mapping(raw, "evaluation support"), canonical)
            if support.support_record_id in self.supports:
                raise DecisionFrameworkValidationError("duplicate evaluation support record")
            self.supports[support.support_record_id] = support
        if not self.supports:
            raise DecisionFrameworkValidationError("Decision Framework requires support evidence")
        actual_observations = {
            observation_id
            for support in self.supports.values()
            for observation_id in support.observation_ids
        }
        if actual_observations != set(canonical.observations):
            raise DecisionFrameworkValidationError(
                "evaluation supports do not cover canonical observations"
            )
        for raw in payload["conflict_records"]:
            conflict = self._conflict(_mapping(raw, "evaluation conflict"), canonical)
            if conflict.conflict_record_id in self.conflicts:
                raise DecisionFrameworkValidationError("duplicate evaluation conflict")
            if conflict.support_record_id in self.conflict_by_support:
                raise DecisionFrameworkValidationError("support has duplicate conflicts")
            self.conflicts[conflict.conflict_record_id] = conflict
            self.conflict_by_support[conflict.support_record_id] = conflict
        expected_lineages = {
            canonical_json(lineage)
            for support in self.supports.values()
            for observation_id in support.observation_ids
            for lineage in canonical.lineage_payloads(observation_id)
        }
        snapshot_lineages = payload["lineage_index"]
        actual_lineages = {canonical_json(item) for item in snapshot_lineages}
        if len(actual_lineages) != len(snapshot_lineages) or actual_lineages != expected_lineages:
            raise DecisionFrameworkValidationError("evaluation lineage index mismatch")

    def _support(
        self, record: Mapping[str, Any], canonical: _CanonicalIndex
    ) -> _Support:
        _exact_fields(record, _SUPPORT_FIELDS, "evaluation support")
        support_id = _identity(
            record, "support_record_id", "evidence-support", "evaluation support"
        )
        observation_ids = _texts(
            record["supporting_observation_ids"], "support observation IDs", minimum=1
        )
        providers = _texts(record["providers"], "support providers", minimum=1)
        sources = _texts(record["sources"], "support sources", minimum=1)
        if (
            type(record["provider_count"]) is not int
            or record["provider_count"] != len(providers)
            or type(record["source_count"]) is not int
            or record["source_count"] != len(sources)
        ):
            raise DecisionFrameworkValidationError("support provider/source count mismatch")
        if record["lineage_completeness"] != "COMPLETE_LINEAGE":
            raise DecisionFrameworkValidationError(
                "Decision Framework requires complete upstream lineage"
            )
        try:
            subject = SubjectRef.from_dict(record["subject"])
            observation_kind = ObservationKind(record["observation_kind"])
        except (TypeError, ValueError) as exc:
            raise DecisionFrameworkValidationError("invalid support identity") from exc
        observations = tuple(canonical.representative(item) for item in observation_ids)
        if (
            any(item.subject != subject for item in observations)
            or any(item.observation_kind is not observation_kind for item in observations)
            or record["dimension"] != _observation_dimension(observations[0])
            or any(_observation_dimension(item) != record["dimension"] for item in observations)
        ):
            raise DecisionFrameworkValidationError("support semantic replay mismatch")
        lineages = [
            lineage
            for observation_id in observation_ids
            for lineage in canonical.lineage_payloads(observation_id)
        ]
        if {item["provider"] for item in lineages} != set(providers) or {
            f"{item['provider']}::{item['source_tool']}" for item in lineages
        } != set(sources):
            raise DecisionFrameworkValidationError("support provider/source replay mismatch")
        _lineage_set(record["lineage_references"], "support lineage", observation_ids, canonical)
        return _Support(
            record=record,
            support_record_id=support_id,
            observation_ids=observation_ids,
            observation_kind=observation_kind,
            lineage_completeness=record["lineage_completeness"],
        )

    def _conflict(
        self, record: Mapping[str, Any], canonical: _CanonicalIndex
    ) -> _EvaluationConflict:
        _exact_fields(record, _EVALUATION_CONFLICT_FIELDS, "evaluation conflict")
        conflict_id = _identity(
            record, "conflict_record_id", "evidence-conflict", "evaluation conflict"
        )
        support_id = _text(record["support_record_id"], "conflict support_record_id")
        support = self.supports.get(support_id)
        if support is None:
            raise DecisionFrameworkValidationError("conflict references unknown support")
        for field in ("semantic_field_id", "subject", "observation_kind", "dimension"):
            if canonical_json(record[field]) != canonical_json(support.record[field]):
                raise DecisionFrameworkValidationError("conflict semantic field mismatch")
        candidates = _texts(
            record["candidate_observation_ids"], "conflict candidates", minimum=2
        )
        if not set(candidates) <= set(support.observation_ids):
            raise DecisionFrameworkValidationError("conflict candidate missing from support")
        if record["conflict_status"] != "CONFLICT_PRESENT":
            raise DecisionFrameworkValidationError("invalid evaluation conflict status")
        _lineage_set(record["lineage_references"], "conflict lineage", candidates, canonical)
        return _EvaluationConflict(
            record=record,
            conflict_record_id=conflict_id,
            support_record_id=support_id,
            candidate_observation_ids=candidates,
        )


class _ConflictIndex:
    def __init__(
        self,
        payload: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        canonical: _CanonicalIndex,
    ) -> None:
        self.snapshot_id = payload["snapshot_id"]
        raw_analyses: dict[str, tuple[Mapping[str, Any], str, Mapping[str, str]]] = {}
        source_ids: set[str] = set()
        for raw in payload["conflict_analyses"]:
            record = _mapping(raw, "conflict analysis")
            analysis_id, source_id, candidate_map = self._analysis(
                record, evaluation, canonical
            )
            if analysis_id in raw_analyses or source_id in source_ids:
                raise DecisionFrameworkValidationError("duplicate conflict analysis")
            raw_analyses[analysis_id] = (record, source_id, candidate_map)
            source_ids.add(source_id)
        attempts = self._attempts(payload["resolution_attempts"], raw_analyses)
        self.analyses: dict[str, _Analysis] = {}
        self.analysis_by_source: dict[str, _Analysis] = {}
        for analysis_id, (record, source_id, candidate_map) in raw_analyses.items():
            analysis = _Analysis(
                record=record,
                conflict_analysis_id=analysis_id,
                source_conflict_id=source_id,
                candidate_by_observation=candidate_map,
                attempt_ids=tuple(sorted(
                    item["resolution_attempt_id"] for item in attempts[analysis_id]
                )),
            )
            self.analyses[analysis_id] = analysis
            self.analysis_by_source[source_id] = analysis
        if set(self.analysis_by_source) != set(evaluation.conflicts):
            raise DecisionFrameworkValidationError(
                "Conflict Resolution analyses do not cover Evaluation conflicts"
            )
        expected_lineages = {
            canonical_json(lineage)
            for analysis in self.analyses.values()
            for candidate in analysis.record["candidates"]
            for lineage in candidate["lineage_references"]
        }
        actual = {canonical_json(item) for item in payload["lineage_index"]}
        if len(actual) != len(payload["lineage_index"]) or actual != expected_lineages:
            raise DecisionFrameworkValidationError("conflict lineage index mismatch")

    def _analysis(
        self,
        record: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        canonical: _CanonicalIndex,
    ) -> tuple[str, str, Mapping[str, str]]:
        _exact_fields(record, _ANALYSIS_FIELDS, "conflict analysis")
        analysis_id = _identity(
            record, "conflict_analysis_id", "conflict-analysis", "conflict analysis"
        )
        source_id = _text(
            record["source_evaluation_conflict_id"], "analysis source conflict ID"
        )
        source = evaluation.conflicts.get(source_id)
        if source is None:
            raise DecisionFrameworkValidationError(
                "analysis references unknown Evaluation conflict"
            )
        if record["analysis_status"] != "CONFLICT_PRESENT":
            raise DecisionFrameworkValidationError("invalid conflict analysis status")
        candidate_ids = _texts(record["candidate_ids"], "analysis candidates", minimum=2)
        candidates = record["candidates"]
        if not isinstance(candidates, tuple) or len(candidates) != len(candidate_ids):
            raise DecisionFrameworkValidationError("analysis candidate inventory mismatch")
        candidate_map: dict[str, str] = {}
        parsed_ids: set[str] = set()
        for raw in candidates:
            candidate = _mapping(raw, "conflict candidate")
            _exact_fields(candidate, _CANDIDATE_FIELDS, "conflict candidate")
            candidate_id = _identity(
                candidate, "candidate_id", "conflict-candidate", "conflict candidate"
            )
            observation_id = _text(candidate["observation_id"], "candidate observation_id")
            if (
                candidate["source_evaluation_conflict_id"] != source_id
                or observation_id not in set(source.candidate_observation_ids)
            ):
                raise DecisionFrameworkValidationError("candidate source conflict mismatch")
            observation = canonical.representative(observation_id)
            provider = observation.provenance.provider
            if (
                candidate["provider"] != provider
                or candidate["source"]
                != f"{provider}::{observation.provenance.source_tool}"
                or canonical_json(candidate["value"]) != canonical_json(observation.value)
            ):
                raise DecisionFrameworkValidationError("conflict candidate replay mismatch")
            _lineage_set(
                candidate["lineage_references"],
                "conflict candidate lineage",
                (observation_id,),
                canonical,
            )
            if observation_id in candidate_map or candidate_id in parsed_ids:
                raise DecisionFrameworkValidationError("duplicate conflict candidate")
            candidate_map[observation_id] = candidate_id
            parsed_ids.add(candidate_id)
        if parsed_ids != set(candidate_ids) or set(candidate_map) != set(
            source.candidate_observation_ids
        ):
            raise DecisionFrameworkValidationError(
                "analysis candidates do not preserve Evaluation conflict"
            )
        return analysis_id, source_id, MappingProxyType(dict(sorted(candidate_map.items())))

    @staticmethod
    def _attempts(
        values: Any,
        analyses: Mapping[str, tuple[Mapping[str, Any], str, Mapping[str, str]]],
    ) -> dict[str, list[Mapping[str, Any]]]:
        if not isinstance(values, tuple):
            raise DecisionFrameworkValidationError("resolution_attempts must be an array")
        result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        identities: set[str] = set()
        for raw in values:
            attempt = _mapping(raw, "resolution attempt")
            _exact_fields(attempt, _ATTEMPT_FIELDS, "resolution attempt")
            attempt_id = _identity(
                attempt, "resolution_attempt_id", "resolution-attempt", "resolution attempt"
            )
            if attempt_id in identities:
                raise DecisionFrameworkValidationError("duplicate resolution attempt")
            identities.add(attempt_id)
            analysis_id = _text(
                attempt["conflict_analysis_id"], "attempt conflict_analysis_id"
            )
            entry = analyses.get(analysis_id)
            if entry is None:
                raise DecisionFrameworkValidationError("attempt references unknown analysis")
            candidates = _texts(attempt["candidate_ids"], "attempt candidates", minimum=2)
            available = _texts(
                attempt["available_evidence_candidate_ids"], "attempt available candidates"
            )
            if set(candidates) != set(entry[0]["candidate_ids"]) or not set(
                available
            ) <= set(candidates):
                raise DecisionFrameworkValidationError("attempt candidate preservation mismatch")
            status = attempt["result_status"]
            if status not in _ATTEMPT_STATUSES:
                raise DecisionFrameworkValidationError("invalid resolution attempt status")
            method = _text(attempt["attempted_method"], "attempt attempted_method")
            normalized = re.sub(r"[^A-Z0-9]+", "_", method.upper()).strip("_")
            if status == "NOT_ATTEMPTED":
                if normalized != "NOT_ATTEMPTED":
                    raise DecisionFrameworkValidationError(
                        "NOT_ATTEMPTED requires attempted_method=NOT_ATTEMPTED"
                    )
            else:
                if normalized == "NOT_ATTEMPTED" or any(
                    token in normalized for token in _FORBIDDEN_METHOD_TOKENS
                ):
                    raise DecisionFrameworkValidationError(
                        "resolution attempt uses an invalid or forbidden method"
                    )
            produced = attempt["produced_candidate_id"]
            if status == "RESOLUTION_PRODUCED":
                if produced not in set(available):
                    raise DecisionFrameworkValidationError(
                        "produced candidate is not available evidence"
                    )
            elif produced is not None:
                raise DecisionFrameworkValidationError(
                    "non-produced attempt selects a candidate"
                )
            process_evidence = attempt["process_evidence"]
            if not isinstance(process_evidence, MappingABC):
                raise DecisionFrameworkValidationError(
                    "attempt process_evidence must be an object"
                )
            _reject_forbidden_process_fields(process_evidence, "attempt process_evidence")
            if status == "RESOLUTION_PRODUCED" and not process_evidence:
                raise DecisionFrameworkValidationError(
                    "produced resolution requires process evidence"
                )
            result[analysis_id].append(attempt)
        if set(result) != set(analyses):
            raise DecisionFrameworkValidationError(
                "every conflict analysis requires resolution process evidence"
            )
        return result


class _PolicyIndex:
    def __init__(
        self,
        payload: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        conflict: _ConflictIndex,
        canonical: _CanonicalIndex,
    ) -> None:
        self.snapshot_id = payload["snapshot_id"]
        definitions: dict[str, tuple[str, str, Mapping[str, Any]]] = {}
        for raw in payload["policy_definitions"]:
            record = _mapping(raw, "policy definition")
            _exact_fields(record, _POLICY_DEFINITION_FIELDS, "policy definition")
            policy_id = _identity(record, "policy_id", "evidence-policy", "policy definition")
            conditions = _mapping(record["conditions"], "policy conditions")
            condition_type = conditions.get("condition_type")
            if condition_type not in _POLICY_CONDITION_BEHAVIORS:
                raise DecisionFrameworkValidationError("unknown Evidence Policy condition")
            if record["policy_version"] != "0.1" or record[
                "expected_behavior"
            ] != _POLICY_CONDITION_BEHAVIORS[condition_type]:
                raise DecisionFrameworkValidationError("invalid policy definition metadata")
            expected_condition_fields = {
                "MINIMUM_PROVIDER_COUNT": {
                    "condition_type",
                    "minimum_provider_count",
                },
                "LINEAGE_COMPLETENESS_REQUIRED": {
                    "condition_type",
                    "required_status",
                },
                "CONFLICT_PRESENT": {"condition_type"},
            }[condition_type]
            if set(conditions) != expected_condition_fields:
                raise DecisionFrameworkValidationError(
                    "policy condition fields do not match V0.1"
                )
            if condition_type == "MINIMUM_PROVIDER_COUNT" and (
                type(conditions["minimum_provider_count"]) is not int
                or conditions["minimum_provider_count"] < 2
            ):
                raise DecisionFrameworkValidationError(
                    "invalid minimum provider policy condition"
                )
            if (
                condition_type == "LINEAGE_COMPLETENESS_REQUIRED"
                and conditions["required_status"] != "COMPLETE_LINEAGE"
            ):
                raise DecisionFrameworkValidationError(
                    "invalid lineage policy condition"
                )
            evidence_types = _texts(
                record["applicable_evidence_types"],
                "policy applicable evidence types",
                minimum=1,
            )
            try:
                tuple(EvidenceType(item) for item in evidence_types)
            except ValueError as exc:
                raise DecisionFrameworkValidationError(
                    "policy contains an invalid evidence type"
                ) from exc
            if policy_id in definitions:
                raise DecisionFrameworkValidationError("duplicate policy definition")
            definitions[policy_id] = (
                condition_type,
                record["expected_behavior"],
                record,
            )
        if {value[0] for value in definitions.values()} != set(
            _POLICY_CONDITION_BEHAVIORS
        ) or len(definitions) != len(_POLICY_CONDITION_BEHAVIORS):
            raise DecisionFrameworkValidationError(
                "Evidence Policy definitions do not match V0.1"
            )
        applicability: dict[str, Mapping[str, Any]] = {}
        for raw in payload["policy_applicability_records"]:
            record = _mapping(raw, "policy applicability")
            _exact_fields(record, _POLICY_APPLICABILITY_FIELDS, "policy applicability")
            identity = _identity(
                record,
                "policy_applicability_id",
                "policy-applicability",
                "policy applicability",
            )
            policy_id = _text(record["policy_id"], "policy applicability policy_id")
            if policy_id not in definitions or policy_id in applicability:
                raise DecisionFrameworkValidationError(
                    "policy applicability references an unknown or duplicate policy"
                )
            if record["applicability_status"] not in {
                "APPLICABLE",
                "NOT_APPLICABLE",
            }:
                raise DecisionFrameworkValidationError("invalid policy applicability status")
            _texts(record["matched_evidence_ids"], "policy matched evidence")
            _texts(record["matched_conflict_ids"], "policy matched conflicts")
            _texts(record["reason_codes"], "policy reason codes", minimum=1)
            applicability[policy_id] = record
        if set(applicability) != set(definitions):
            raise DecisionFrameworkValidationError("policy applicability inventory mismatch")
        self.evaluations: dict[str, _PolicyEvaluation] = {}
        self.evaluation_by_condition: dict[str, _PolicyEvaluation] = {}
        for raw in payload["policy_evaluations"]:
            record = _mapping(raw, "policy evaluation")
            _exact_fields(record, _POLICY_EVALUATION_FIELDS, "policy evaluation")
            evaluation_id = _identity(
                record, "policy_evaluation_id", "policy-evaluation", "policy evaluation"
            )
            policy_id = _text(record["policy_id"], "policy evaluation policy_id")
            definition = definitions.get(policy_id)
            applies = applicability.get(policy_id)
            if definition is None or applies is None:
                raise DecisionFrameworkValidationError(
                    "policy evaluation references an unknown policy"
                )
            if record["policy_applicability_id"] != applies["policy_applicability_id"]:
                raise DecisionFrameworkValidationError(
                    "policy evaluation references wrong applicability"
                )
            inputs = _texts(record["input_evidence_ids"], "policy input evidence", minimum=1)
            conflicts = _texts(record["conflict_ids"], "policy conflicts")
            allowed_evidence_types = set(definition[2]["applicable_evidence_types"])
            expected_inputs = {
                support.support_record_id
                for support in evaluation.supports.values()
                if any(
                    canonical.representative(observation_id).evidence_type.value
                    in allowed_evidence_types
                    for observation_id in support.observation_ids
                )
            }
            expected_conflicts = {
                conflict_id
                for conflict_id, conflict_record in evaluation.conflicts.items()
                if conflict_record.support_record_id in expected_inputs
            }
            if set(inputs) != expected_inputs or set(conflicts) != expected_conflicts:
                raise DecisionFrameworkValidationError(
                    "policy evaluation input inventory mismatch"
                )
            if (
                record["evaluation_result"] not in _POLICY_RESULTS
                or record["expected_behavior"] != definition[1]
            ):
                raise DecisionFrameworkValidationError("invalid policy evaluation result")
            if definition[0] == "MINIMUM_PROVIDER_COUNT":
                minimum = definition[2]["conditions"]["minimum_provider_count"]
                matched_support_ids = {
                    support_id
                    for support_id in expected_inputs
                    if evaluation.supports[support_id].record["provider_count"] >= minimum
                }
                expected_result = (
                    "APPLICABLE_NO_ACTION"
                    if matched_support_ids
                    else "NOT_APPLICABLE"
                )
            elif definition[0] == "LINEAGE_COMPLETENESS_REQUIRED":
                matched_support_ids = set(expected_inputs)
                expected_result = (
                    "ACTION_ALLOWED" if expected_inputs else "NOT_APPLICABLE"
                )
            else:
                matched_support_ids = {
                    conflict_record.support_record_id
                    for conflict_record in evaluation.conflicts.values()
                    if conflict_record.support_record_id in expected_inputs
                }
                expected_result = (
                    "ACTION_BLOCKED" if expected_conflicts else "NOT_APPLICABLE"
                )
            expected_matched_conflicts = {
                conflict_id
                for conflict_id in expected_conflicts
                if evaluation.conflicts[conflict_id].support_record_id
                in matched_support_ids
            }
            expected_applicability = (
                "APPLICABLE" if matched_support_ids else "NOT_APPLICABLE"
            )
            if (
                applies["applicability_status"] != expected_applicability
                or set(applies["matched_evidence_ids"]) != matched_support_ids
                or set(applies["matched_conflict_ids"])
                != expected_matched_conflicts
                or record["evaluation_result"] != expected_result
            ):
                raise DecisionFrameworkValidationError(
                    "policy applicability/result does not replay upstream evidence"
                )
            item = _PolicyEvaluation(
                record=record,
                policy_id=policy_id,
                policy_evaluation_id=evaluation_id,
                condition_type=definition[0],
                evaluation_result=record["evaluation_result"],
                input_evidence_ids=inputs,
                conflict_ids=conflicts,
            )
            if evaluation_id in self.evaluations or definition[0] in self.evaluation_by_condition:
                raise DecisionFrameworkValidationError("duplicate policy evaluation")
            self.evaluations[evaluation_id] = item
            self.evaluation_by_condition[definition[0]] = item
        if set(self.evaluation_by_condition) != set(_POLICY_CONDITION_BEHAVIORS):
            raise DecisionFrameworkValidationError("policy evaluation inventory mismatch")
        audits: set[str] = set()
        for raw in payload["audit_records"]:
            record = _mapping(raw, "policy audit")
            _exact_fields(record, _POLICY_AUDIT_FIELDS, "policy audit")
            audit_id = _identity(record, "policy_audit_id", "policy-audit", "policy audit")
            evaluation_item = self.evaluations.get(record["policy_evaluation_id"])
            if (
                audit_id in audits
                or evaluation_item is None
                or record["policy_id"] != evaluation_item.policy_id
                or record["condition_type"] != evaluation_item.condition_type
                or record["evaluation_result"] != evaluation_item.evaluation_result
                or record["source_evaluation_snapshot_id"] != evaluation.snapshot_id
                or record["source_conflict_resolution_snapshot_id"] != conflict.snapshot_id
            ):
                raise DecisionFrameworkValidationError("policy audit trail mismatch")
            audits.add(audit_id)
        if len(audits) != len(self.evaluations):
            raise DecisionFrameworkValidationError("policy audit inventory mismatch")
        self.lineages_by_evaluation: dict[str, tuple[Mapping[str, Any], ...]] = {}
        grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        identities: set[str] = set()
        for raw in payload["lineage_index"]:
            record = _mapping(raw, "policy lineage")
            _exact_fields(record, _POLICY_LINEAGE_FIELDS, "policy lineage")
            lineage_id = _identity(
                record, "policy_lineage_id", "policy-lineage", "policy lineage"
            )
            if lineage_id in identities:
                raise DecisionFrameworkValidationError("duplicate policy lineage")
            identities.add(lineage_id)
            policy_evaluation = self.evaluations.get(record["policy_evaluation_id"])
            support = evaluation.supports.get(record["support_record_id"])
            if (
                policy_evaluation is None
                or support is None
                or record["policy_id"] != policy_evaluation.policy_id
                or record["support_record_id"] not in policy_evaluation.input_evidence_ids
                or record["observation_id"] not in support.observation_ids
            ):
                raise DecisionFrameworkValidationError("orphan policy lineage")
            analysis = None
            conflict_record_id = record["conflict_record_id"]
            conflict_values = (
                conflict_record_id,
                record["conflict_analysis_id"],
                record["conflict_candidate_id"],
            )
            if any(item is None for item in conflict_values) != all(
                item is None for item in conflict_values
            ):
                raise DecisionFrameworkValidationError(
                    "policy conflict lineage identities are incomplete"
                )
            attempts = _texts(record["resolution_attempt_ids"], "policy attempt IDs")
            if conflict_record_id is None:
                if attempts:
                    raise DecisionFrameworkValidationError(
                        "non-conflict policy lineage has resolution attempts"
                    )
            else:
                source_conflict = evaluation.conflicts.get(conflict_record_id)
                analysis = conflict.analysis_by_source.get(conflict_record_id)
                if (
                    source_conflict is None
                    or analysis is None
                    or source_conflict.support_record_id != support.support_record_id
                    or record["conflict_analysis_id"] != analysis.conflict_analysis_id
                    or record["conflict_candidate_id"]
                    != analysis.candidate_by_observation.get(record["observation_id"])
                    or attempts != analysis.attempt_ids
                ):
                    raise DecisionFrameworkValidationError(
                        "policy conflict lineage does not replay Conflict Resolution"
                    )
            self._validate_canonical_lineage(record, canonical)
            grouped[policy_evaluation.policy_evaluation_id].append(record)
        for evaluation_id, policy_evaluation in self.evaluations.items():
            lineages = tuple(sorted(grouped.get(evaluation_id, []), key=canonical_json))
            if {item["support_record_id"] for item in lineages} != set(
                policy_evaluation.input_evidence_ids
            ) or {
                item["conflict_record_id"]
                for item in lineages
                if item["conflict_record_id"] is not None
            } != set(policy_evaluation.conflict_ids):
                raise DecisionFrameworkValidationError(
                    "policy lineage does not cover evaluation evidence"
                )
            self.lineages_by_evaluation[evaluation_id] = lineages

    @staticmethod
    def _validate_canonical_lineage(
        record: Mapping[str, Any], canonical: _CanonicalIndex
    ) -> None:
        observation_id = record["observation_id"]
        matching = {
            canonical_json(item)
            for item in canonical.lineage_payloads(observation_id)
            if item["transformation_run_id"] == record["transformation_run_id"]
        }
        source_payload = {
            key: record[key]
            for key in _SOURCE_LINEAGE_FIELDS
        }
        if canonical_json(source_payload) not in matching:
            raise DecisionFrameworkValidationError(
                "policy lineage does not replay canonical evidence"
            )
        observation = canonical.representative(observation_id)
        if (
            record["evidence_type"] != observation.evidence_type.value
            or record["observation_kind"] != observation.observation_kind.value
        ):
            raise DecisionFrameworkValidationError(
                "policy lineage canonical type mismatch"
            )


def _definition(
    description: str,
    condition_type: str,
    required_kinds: tuple[str, ...],
    conflict_requirement: str,
    required_policies: tuple[str, ...],
    expected_behavior: str,
) -> DecisionRuleDefinition:
    payload = {
        "rule_version": "0.1",
        "description": description,
        "input_evidence_requirements": {
            "minimum_support_record_count": 1,
            "required_observation_kinds": required_kinds,
        },
        "conditions": {
            "condition_type": condition_type,
            "conflict_requirement": conflict_requirement,
            "required_lineage_status": "COMPLETE_LINEAGE",
            "required_policy_condition_types": required_policies,
        },
        "expected_behavior": expected_behavior,
    }
    return DecisionRuleDefinition(
        rule_id=deterministic_id("decision-rule", payload), **payload
    )


def _default_definitions() -> tuple[DecisionRuleDefinition, ...]:
    definitions = (
        _definition(
            "Record whether auditable evidence is available without making a conclusion.",
            "EVIDENCE_INVENTORY",
            (),
            "ANY",
            ("LINEAGE_COMPLETENESS_REQUIRED",),
            "RECORD_EVIDENCE_AVAILABILITY_WITHOUT_CONCLUSION",
        ),
        _definition(
            "Record whether conflict-free analysis is permitted by evidence policy.",
            "CONFLICT_FREE_EVIDENCE",
            (),
            "ABSENT",
            ("CONFLICT_PRESENT", "LINEAGE_COMPLETENESS_REQUIRED"),
            "RECORD_ANALYSIS_ONLY_WHEN_CONFLICT_POLICY_ALLOWS",
        ),
        _definition(
            "Record keyword evidence availability without selecting a keyword or product.",
            "KEYWORD_EVIDENCE",
            (
                ObservationKind.KEYWORD_METRIC.value,
                ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP.value,
            ),
            "ABSENT",
            ("CONFLICT_PRESENT", "LINEAGE_COMPLETENESS_REQUIRED"),
            "RECORD_KEYWORD_EVIDENCE_AVAILABILITY_WITHOUT_RECOMMENDATION",
        ),
        _definition(
            "Record conflict context for review without resolving or selecting candidates.",
            "CONFLICT_CONTEXT",
            (),
            "PRESENT",
            ("LINEAGE_COMPLETENESS_REQUIRED",),
            "RECORD_CONFLICT_CONTEXT_WITHOUT_RESOLUTION",
        ),
    )
    return tuple(sorted(definitions, key=lambda item: item.rule_id))


class DecisionFrameworkBuilderV0_1:
    """Evaluate declarative analysis rules without making a business decision."""

    def build(
        self, request: DecisionFrameworkRequest
    ) -> DecisionFrameworkSnapshotV0_1:
        if not isinstance(request, DecisionFrameworkRequest):
            raise DecisionFrameworkValidationError(
                "request must be DecisionFrameworkRequest"
            )
        canonical = _CanonicalIndex(request.canonical_bundles)
        evaluation = _EvaluationIndex(request.evidence_evaluation_snapshot, canonical)
        conflict = _ConflictIndex(
            request.conflict_resolution_snapshot, evaluation, canonical
        )
        policy = _PolicyIndex(
            request.evidence_policy_snapshot, evaluation, conflict, canonical
        )
        definitions = _default_definitions()
        applicability: list[DecisionApplicabilityRecord] = []
        evaluations: list[DecisionEvaluationRecord] = []
        audits: list[DecisionAuditRecord] = []
        lineages: list[DecisionLineageReference] = []
        for rule in definitions:
            state = self._evaluate_rule(rule, evaluation, policy)
            applicability_record = self._applicability(rule, state)
            evaluation_record = self._evaluation_record(
                rule, applicability_record, state, evaluation, conflict, policy
            )
            audit_record = self._audit_record(
                rule,
                applicability_record,
                evaluation_record,
                state,
                evaluation,
                conflict,
                policy,
            )
            applicability.append(applicability_record)
            evaluations.append(evaluation_record)
            audits.append(audit_record)
            lineages.extend(self._lineages(rule, evaluation_record, policy))
        ordered_applicability = tuple(sorted(
            applicability, key=lambda item: item.decision_applicability_id
        ))
        ordered_evaluations = tuple(sorted(
            evaluations, key=lambda item: item.decision_evaluation_id
        ))
        ordered_audits = tuple(sorted(audits, key=lambda item: item.decision_audit_id))
        ordered_lineages = tuple(sorted(lineages, key=lambda item: item.decision_lineage_id))
        diagnostics = self._diagnostics(ordered_evaluations)
        coverage = coverage_from_records(
            bundle_count=len(canonical.bundle_fingerprints),
            definitions=definitions,
            applicability=ordered_applicability,
            evaluations=ordered_evaluations,
            audits=ordered_audits,
            diagnostics=diagnostics,
            lineage=ordered_lineages,
        )
        payload = {
            "ruleset_version": DECISION_FRAMEWORK_RULESET_VERSION,
            "source_evaluation_snapshot_id": evaluation.snapshot_id,
            "source_conflict_resolution_snapshot_id": conflict.snapshot_id,
            "source_policy_snapshot_id": policy.snapshot_id,
            "source_bundle_fingerprints": canonical.bundle_fingerprints,
            "rule_definitions": definitions,
            "applicability_records": ordered_applicability,
            "decision_evaluations": ordered_evaluations,
            "audit_records": ordered_audits,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": ordered_lineages,
        }
        snapshot = DecisionFrameworkSnapshotV0_1(
            snapshot_id=deterministic_id("decision-framework-snapshot", payload),
            **payload,
        )
        return snapshot.validate_against_bundles(request.canonical_bundles)

    @staticmethod
    def _evaluate_rule(
        rule: DecisionRuleDefinition,
        evaluation: _EvaluationIndex,
        policy: _PolicyIndex,
    ) -> Mapping[str, Any]:
        considered = tuple(sorted(
            evaluation.supports.values(), key=lambda item: item.support_record_id
        ))
        required_kinds = set(
            rule.input_evidence_requirements["required_observation_kinds"]
        )
        available = tuple(
            item
            for item in considered
            if not required_kinds or item.observation_kind.value in required_kinds
        )
        minimum = rule.input_evidence_requirements["minimum_support_record_count"]
        missing = (
            ("REQUIRED_EVIDENCE_KIND_MISSING",)
            if len(available) < minimum
            else ()
        )
        required_policy_evaluations = tuple(
            policy.evaluation_by_condition[condition]
            for condition in rule.conditions["required_policy_condition_types"]
        )
        blocked = tuple(
            item
            for item in required_policy_evaluations
            if item.evaluation_result == "ACTION_BLOCKED"
        )
        if blocked:
            policy_status = "POLICY_BLOCKED"
        elif any(
            item.evaluation_result in {"ACTION_ALLOWED", "APPLICABLE_NO_ACTION"}
            for item in required_policy_evaluations
        ):
            policy_status = "POLICY_ALLOWED"
        else:
            policy_status = "POLICY_NOT_APPLICABLE"
        conflict_status = (
            "CONFLICT_PRESENT" if evaluation.conflicts else "NO_CONFLICT"
        )
        requirement = rule.conditions["conflict_requirement"]
        conflict_matches = (
            requirement == "ANY"
            or requirement == "PRESENT" and conflict_status == "CONFLICT_PRESENT"
            or requirement == "ABSENT" and conflict_status == "NO_CONFLICT"
        )
        if missing:
            result = "INSUFFICIENT_EVIDENCE"
            reasons = ("MISSING_REQUIRED_EVIDENCE_IS_NOT_NEGATIVE_CONCLUSION",)
        elif blocked:
            result = "BLOCKED_BY_POLICY"
            reasons = ("UPSTREAM_POLICY_BLOCKS_RULE_ANALYSIS",)
        elif not conflict_matches:
            result = "NOT_APPLICABLE"
            reasons = ("RULE_CONFLICT_CONDITION_NOT_MET",)
        else:
            result = "APPLICABLE"
            reasons = ("DECLARATIVE_RULE_ANALYSIS_RECORDED",)
        return MappingProxyType({
            "considered": considered,
            "available": available,
            "missing": missing,
            "policy_evaluations": required_policy_evaluations,
            "blocked": blocked,
            "policy_status": policy_status,
            "conflict_status": conflict_status,
            "applicability_result": result,
            "reason_codes": reasons,
        })

    @staticmethod
    def _applicability(
        rule: DecisionRuleDefinition, state: Mapping[str, Any]
    ) -> DecisionApplicabilityRecord:
        payload = {
            "rule_id": rule.rule_id,
            "available_evidence_ids": tuple(
                item.support_record_id for item in state["available"]
            ),
            "missing_evidence_requirements": state["missing"],
            "conflict_status": state["conflict_status"],
            "policy_status": state["policy_status"],
            "policy_evaluation_ids": tuple(sorted(
                item.policy_evaluation_id for item in state["policy_evaluations"]
            )),
            "applicability_result": state["applicability_result"],
            "reason_codes": state["reason_codes"],
        }
        return DecisionApplicabilityRecord(
            decision_applicability_id=deterministic_id(
                "decision-applicability", payload
            ),
            **payload,
        )

    @staticmethod
    def _evaluation_record(
        rule: DecisionRuleDefinition,
        applicability: DecisionApplicabilityRecord,
        state: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        conflict: _ConflictIndex,
        policy: _PolicyIndex,
    ) -> DecisionEvaluationRecord:
        result_by_applicability = {
            "NOT_APPLICABLE": "RULE_NOT_APPLICABLE",
            "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
            "APPLICABLE": "RULE_ANALYSIS_RECORDED",
            "BLOCKED_BY_POLICY": "RULE_ANALYSIS_BLOCKED_BY_POLICY",
        }
        payload = {
            "rule_id": rule.rule_id,
            "decision_applicability_id": applicability.decision_applicability_id,
            "input_evidence_ids": tuple(
                item.support_record_id for item in state["considered"]
            ),
            "policy_evaluation_ids": applicability.policy_evaluation_ids,
            "conflict_ids": tuple(sorted(evaluation.conflicts)),
            "evaluation_result": result_by_applicability[
                applicability.applicability_result
            ],
            "analysis_output": {
                "record_type": "DECISION_RULE_ANALYSIS",
                "applicability_result": applicability.applicability_result,
                "process_interpretation": (
                    "ANALYSIS_RECORD_ONLY_NO_BUSINESS_CONCLUSION"
                ),
            },
            "audit_metadata": {
                "condition_type": rule.conditions["condition_type"],
                "source_evaluation_snapshot_id": evaluation.snapshot_id,
                "source_conflict_resolution_snapshot_id": conflict.snapshot_id,
                "source_policy_snapshot_id": policy.snapshot_id,
            },
        }
        return DecisionEvaluationRecord(
            decision_evaluation_id=deterministic_id(
                "decision-evaluation", payload
            ),
            **payload,
        )

    @staticmethod
    def _audit_record(
        rule: DecisionRuleDefinition,
        applicability: DecisionApplicabilityRecord,
        evaluation_record: DecisionEvaluationRecord,
        state: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        conflict: _ConflictIndex,
        policy: _PolicyIndex,
    ) -> DecisionAuditRecord:
        payload = {
            "rule_id": rule.rule_id,
            "rule_version": rule.rule_version,
            "decision_applicability_id": applicability.decision_applicability_id,
            "decision_evaluation_id": evaluation_record.decision_evaluation_id,
            "condition_type": rule.conditions["condition_type"],
            "condition_observations": {
                "considered_evidence_count": len(state["considered"]),
                "available_evidence_count": len(state["available"]),
                "missing_requirement_count": len(state["missing"]),
                "conflict_count": len(evaluation.conflicts),
                "blocking_policy_count": len(state["blocked"]),
            },
            "applicability_result": applicability.applicability_result,
            "evaluation_result": evaluation_record.evaluation_result,
            "source_evaluation_snapshot_id": evaluation.snapshot_id,
            "source_conflict_resolution_snapshot_id": conflict.snapshot_id,
            "source_policy_snapshot_id": policy.snapshot_id,
        }
        return DecisionAuditRecord(
            decision_audit_id=deterministic_id("decision-audit", payload),
            **payload,
        )

    @staticmethod
    def _lineages(
        rule: DecisionRuleDefinition,
        evaluation_record: DecisionEvaluationRecord,
        policy: _PolicyIndex,
    ) -> tuple[DecisionLineageReference, ...]:
        result: list[DecisionLineageReference] = []
        for policy_evaluation_id in evaluation_record.policy_evaluation_ids:
            for upstream in policy.lineages_by_evaluation[policy_evaluation_id]:
                payload = {
                    "rule_id": rule.rule_id,
                    "decision_evaluation_id": evaluation_record.decision_evaluation_id,
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
                result.append(DecisionLineageReference(
                    decision_lineage_id=deterministic_id(
                        "decision-lineage", payload
                    ),
                    **payload,
                ))
        return tuple(sorted(result, key=lambda item: item.decision_lineage_id))

    @staticmethod
    def _diagnostic(
        code: str,
        evaluations: Iterable[DecisionEvaluationRecord],
        message: str,
    ) -> DecisionDiagnostic:
        values = tuple(evaluations)
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_rule_ids": tuple(sorted({item.rule_id for item in values})),
            "related_decision_evaluation_ids": tuple(sorted({
                item.decision_evaluation_id for item in values
            })),
            "message": message,
        }
        return DecisionDiagnostic(
            diagnostic_id=deterministic_id("decision-diagnostic", payload),
            **payload,
        )

    def _diagnostics(
        self, evaluations: tuple[DecisionEvaluationRecord, ...]
    ) -> tuple[DecisionDiagnostic, ...]:
        messages = {
            "RULE_ANALYSIS_RECORDED": (
                "ANALYSIS_RECORDED_WITHOUT_BUSINESS_CONCLUSION",
                "A declarative rule analysis was recorded without a recommendation or selection.",
            ),
            "RULE_ANALYSIS_BLOCKED_BY_POLICY": (
                "RULE_ANALYSIS_BLOCKED_BY_POLICY",
                "Evidence policy blocked rule analysis without rejecting a product or market.",
            ),
            "INSUFFICIENT_EVIDENCE": (
                "MISSING_EVIDENCE_IS_NOT_NEGATIVE_CONCLUSION",
                "Required evidence was missing; no negative business conclusion was produced.",
            ),
            "RULE_NOT_APPLICABLE": (
                "RULE_NOT_APPLICABLE",
                "A declarative rule condition did not apply to the supplied evidence.",
            ),
        }
        result = []
        for status, (code, message) in messages.items():
            selected = tuple(item for item in evaluations if item.evaluation_result == status)
            if selected:
                result.append(self._diagnostic(code, selected, message))
        return tuple(sorted(result, key=lambda item: item.diagnostic_id))


__all__ = ("DecisionFrameworkBuilderV0_1",)
