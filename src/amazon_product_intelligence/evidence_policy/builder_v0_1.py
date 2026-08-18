"""Auditable, declarative Evidence Policy V0.1 builder."""

from __future__ import annotations

from collections import Counter, defaultdict
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
    PresenceStatus,
    ProductFactObservation,
    ProductKeywordRelationshipObservation,
    ReviewObservation,
    SemanticStatus,
    Severity,
    SubjectRef,
    ValueEnvelope,
    canonical_json,
    deterministic_id,
)

from .errors import EvidencePolicyValidationError
from .models import (
    EVIDENCE_POLICY_RULESET_VERSION,
    EvidencePolicyRequest,
    EvidencePolicySnapshotV0_1,
    PolicyApplicabilityRecord,
    PolicyAuditRecord,
    PolicyDefinition,
    PolicyDiagnostic,
    PolicyEvaluationRecord,
    PolicyLineageReference,
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
_QUALITY_PROFILE_FIELDS = {
    "profile_id",
    "support_record_id",
    "semantic_field_id",
    "source_diversity",
    "observation_recency",
    "period_status",
    "completeness",
    "lineage_completeness",
    "consistency",
    "qualitative_attributes",
}
_EVALUATION_DIAGNOSTIC_FIELDS = {
    "diagnostic_id",
    "code",
    "severity",
    "related_support_record_ids",
    "related_conflict_record_ids",
    "related_observation_ids",
    "message",
}
_EVALUATION_COVERAGE_FIELDS = {
    "source_bundle_count",
    "canonical_observation_count",
    "support_record_count",
    "conflict_record_count",
    "quality_profile_count",
    "provider_count",
    "source_count",
    "complete_lineage_record_count",
    "single_provider_support_count",
    "multi_provider_support_count",
    "known_observation_time_profile_count",
    "unknown_observation_time_profile_count",
    "unknown_period_profile_count",
    "conflict_profile_count",
    "present_observation_count",
    "non_present_observation_count",
    "quality_issue_count",
    "diagnostic_count",
    "observation_kind_counts",
    "semantic_status_counts",
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
_CONFLICT_DIAGNOSTIC_FIELDS = {
    "diagnostic_id",
    "code",
    "severity",
    "related_conflict_analysis_ids",
    "related_resolution_attempt_ids",
    "related_candidate_ids",
    "message",
}
_CONFLICT_COVERAGE_FIELDS = {
    "source_bundle_count",
    "source_evaluation_conflict_count",
    "conflict_analysis_count",
    "candidate_count",
    "resolution_attempt_count",
    "provider_count",
    "source_count",
    "diagnostic_count",
    "attempt_status_counts",
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
    semantic_field_id: str
    observation_ids: tuple[str, ...]
    providers: tuple[str, ...]
    sources: tuple[str, ...]
    provider_count: int
    lineage_completeness: str


@dataclass(frozen=True, slots=True)
class _EvaluationConflict:
    record: Mapping[str, Any]
    conflict_record_id: str
    support_record_id: str
    candidate_observation_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Profile:
    record: Mapping[str, Any]
    support_record_id: str
    source_diversity: str
    observation_recency: str
    period_status: str
    consistency: str


@dataclass(frozen=True, slots=True)
class _Analysis:
    record: Mapping[str, Any]
    conflict_analysis_id: str
    source_conflict_id: str
    candidate_by_observation: Mapping[str, str]
    attempt_ids: tuple[str, ...]


class _CanonicalIndex:
    """Collision-safe index over existing canonical identities and lineage."""

    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(bundle_fingerprint(item) for item in bundles))
        self.observation_revisions: dict[str, str] = {}
        self.observations: dict[str, dict[str, _Emission]] = defaultdict(dict)
        self.runs: dict[str, Any] = {}
        self.raw_ids: set[str] = set()
        self.quality_issue_ids: set[str] = set()
        for fingerprint, bundle in sorted(
            ((bundle_fingerprint(item), item) for item in bundles), key=lambda item: item[0]
        ):
            self.raw_ids.update(bundle.raw_evidence_references)
            self.quality_issue_ids.update(item.issue_id for item in bundle.quality_issues)
            for run in bundle.transformation_runs:
                current = self.runs.get(run.transformation_run_id)
                if current is not None and canonical_json(current) != canonical_json(run):
                    raise EvidencePolicyValidationError(
                        f"transformation run identity collision: {run.transformation_run_id}"
                    )
                self.runs[run.transformation_run_id] = run
            for observation in bundle.observations:
                revision = canonical_json(observation_revision_content(observation))
                prior = self.observation_revisions.get(observation.observation_id)
                if prior is not None and prior != revision:
                    raise EvidencePolicyValidationError(
                        f"observation identity collision: {observation.observation_id}"
                    )
                self.observation_revisions[observation.observation_id] = revision
                run_id = observation.provenance.transformation.transformation_run_id
                current = self.observations[observation.observation_id].get(run_id)
                if current is not None and canonical_json(current.observation) != canonical_json(
                    observation
                ):
                    raise EvidencePolicyValidationError(
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
            raise EvidencePolicyValidationError(f"orphan evidence: {observation_id}")
        return min(
            emissions.values(), key=lambda item: canonical_json(item.observation)
        ).observation

    def lineage_payloads(self, observation_id: str) -> tuple[Mapping[str, Any], ...]:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise EvidencePolicyValidationError(f"orphan evidence: {observation_id}")
        result: list[Mapping[str, Any]] = []
        for run_id, emission in sorted(emissions.items()):
            observation = emission.observation
            transformation = observation.provenance.transformation
            run = self.runs.get(run_id)
            raw_id = transformation.raw_evidence_reference
            if run is None:
                raise EvidencePolicyValidationError(f"orphan transformation run: {run_id}")
            if (
                raw_id not in self.raw_ids
                or raw_id not in run.input_raw_evidence_references
                or run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or observation_id not in run.output_observation_ids
            ):
                raise EvidencePolicyValidationError(
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
    raise EvidencePolicyValidationError(
        f"unsupported canonical observation type: {type(observation).__name__}"
    )


def _semantic_field_material(observation: CanonicalObservation) -> dict[str, Any]:
    material: dict[str, Any] = {
        "subject": observation.subject,
        "observation_kind": observation.observation_kind,
        "dimension": _observation_dimension(observation),
        "scope": observation.scope,
        "time_context": {
            "observed_at": observation.time.observed_at,
            "observed_at_status": observation.time.observed_at_status,
            "period_start": observation.time.period_start,
            "period_end": observation.time.period_end,
            "period_type": observation.time.period_type,
            "timezone": observation.time.timezone,
        },
        "evidence_type": observation.evidence_type,
        "unit": observation.value.unit,
    }
    if isinstance(observation, MetricObservation):
        material.update({
            "currency": observation.currency,
            "rank_context": observation.rank_context,
        })
    elif isinstance(observation, KeywordMetricObservation):
        material["keyword"] = observation.keyword
    elif isinstance(observation, ProductKeywordRelationshipObservation):
        material.update({
            "product": observation.product,
            "keyword": observation.keyword,
            "direction": observation.direction,
            "relationship_type": observation.relationship_type,
            "channel": observation.channel,
        })
    elif isinstance(observation, ReviewObservation):
        material.update({
            "product": observation.product,
            "review_identity": observation.provider_review_identity
            or observation.semantic_observation_id,
        })
    elif (
        isinstance(observation, ProductFactObservation)
        and observation.dimension == "child_product_relationship"
    ):
        material["relationship_value"] = observation.value.normalized_value
    return material


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, MappingABC):
        raise EvidencePolicyValidationError(f"{path} must be an object")
    return value


def _exact_fields(record: Mapping[str, Any], fields: set[str], path: str) -> None:
    if set(record) != fields:
        raise EvidencePolicyValidationError(f"{path} fields do not match V0.1")


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise EvidencePolicyValidationError(f"{path} must be non-empty text")
    return value


def _texts(
    value: Any, path: str, *, minimum: int = 0
) -> tuple[str, ...]:
    if not isinstance(value, tuple):
        raise EvidencePolicyValidationError(f"{path} must be an array")
    if len(value) < minimum:
        raise EvidencePolicyValidationError(f"{path} requires at least {minimum} values")
    if any(type(item) is not str or not item.strip() for item in value):
        raise EvidencePolicyValidationError(f"{path} must contain non-empty text")
    if len(set(value)) != len(value):
        raise EvidencePolicyValidationError(f"{path} must contain unique values")
    return tuple(sorted(value))


def _identity(record: Mapping[str, Any], field: str, prefix: str, path: str) -> str:
    identity = _text(record[field], f"{path}.{field}")
    content = dict(record)
    content.pop(field)
    if identity != deterministic_id(prefix, content):
        raise EvidencePolicyValidationError(f"{path} identity mismatch")
    return identity


def _reject_forbidden_process_fields(value: Any, path: str) -> None:
    if isinstance(value, MappingABC):
        for key, child in value.items():
            normalized = re.sub(r"[^A-Z0-9]+", "_", key.upper()).strip("_")
            if set(normalized.split("_")) & _FORBIDDEN_PROCESS_FIELD_TOKENS:
                raise EvidencePolicyValidationError(
                    f"{path}.{key} uses a forbidden preference field"
                )
            _reject_forbidden_process_fields(child, f"{path}.{key}")
    elif isinstance(value, tuple):
        for index, child in enumerate(value):
            _reject_forbidden_process_fields(child, f"{path}[{index}]")


def _lineage_set(
    value: Any, path: str, observation_ids: Iterable[str], index: _CanonicalIndex
) -> set[str]:
    if not isinstance(value, tuple):
        raise EvidencePolicyValidationError(f"{path} must be an array")
    actual: list[str] = []
    for item in value:
        record = _mapping(item, path)
        _exact_fields(record, _SOURCE_LINEAGE_FIELDS, path)
        actual.append(canonical_json(record))
    if len(set(actual)) != len(actual):
        raise EvidencePolicyValidationError(f"{path} must contain unique lineage")
    expected = {
        canonical_json(lineage)
        for observation_id in observation_ids
        for lineage in index.lineage_payloads(observation_id)
    }
    if set(actual) != expected:
        raise EvidencePolicyValidationError(f"{path} does not replay canonical lineage")
    return set(actual)


class _EvaluationIndex:
    def __init__(self, payload: Mapping[str, Any], canonical: _CanonicalIndex) -> None:
        self.snapshot_id = payload["snapshot_id"]
        self.supports: dict[str, _Support] = {}
        self.conflicts: dict[str, _EvaluationConflict] = {}
        self.conflict_by_support: dict[str, _EvaluationConflict] = {}
        profiles: list[_Profile] = []
        for raw in payload["support_records"]:
            support = self._support(_mapping(raw, "evaluation support"), canonical)
            if support.support_record_id in self.supports:
                raise EvidencePolicyValidationError("duplicate evaluation support record")
            self.supports[support.support_record_id] = support
        if len({item.semantic_field_id for item in self.supports.values()}) != len(
            self.supports
        ):
            raise EvidencePolicyValidationError("duplicate evaluation semantic field")
        expected_observation_ids = set(canonical.observations)
        actual_observation_ids = {
            observation_id
            for support in self.supports.values()
            for observation_id in support.observation_ids
        }
        if actual_observation_ids != expected_observation_ids:
            raise EvidencePolicyValidationError(
                "evaluation support inventory does not cover canonical observations"
            )
        for raw in payload["conflict_records"]:
            conflict = self._conflict(
                _mapping(raw, "evaluation conflict"), canonical
            )
            if conflict.conflict_record_id in self.conflicts:
                raise EvidencePolicyValidationError("duplicate evaluation conflict")
            if conflict.support_record_id in self.conflict_by_support:
                raise EvidencePolicyValidationError("support has duplicate conflicts")
            self.conflicts[conflict.conflict_record_id] = conflict
            self.conflict_by_support[conflict.support_record_id] = conflict
        for raw in payload["evidence_quality_profiles"]:
            profile = self._profile(_mapping(raw, "evaluation profile"))
            support = self.supports.get(profile.support_record_id)
            if support is None or profile.record["semantic_field_id"] != support.semantic_field_id:
                raise EvidencePolicyValidationError("quality profile support mismatch")
            profiles.append(profile)
        if {item.support_record_id for item in profiles} != set(self.supports) or len(
            profiles
        ) != len(self.supports):
            raise EvidencePolicyValidationError(
                "quality profiles must cover every support record once"
            )
        if {
            item.support_record_id for item in profiles if item.consistency == "CONFLICT_PRESENT"
        } != set(self.conflict_by_support):
            raise EvidencePolicyValidationError(
                "quality conflict profiles do not match conflicts"
            )
        expected_lineages = {
            canonical_json(lineage)
            for support in self.supports.values()
            for observation_id in support.observation_ids
            for lineage in canonical.lineage_payloads(observation_id)
        }
        snapshot_lineages = payload["lineage_index"]
        if not isinstance(snapshot_lineages, tuple):
            raise EvidencePolicyValidationError("evaluation lineage_index must be an array")
        actual_lineages = {canonical_json(item) for item in snapshot_lineages}
        if len(actual_lineages) != len(snapshot_lineages) or actual_lineages != expected_lineages:
            raise EvidencePolicyValidationError("evaluation lineage index mismatch")
        diagnostics = self._validate_diagnostics(payload["diagnostics"])
        self._validate_coverage(
            payload["coverage"], canonical, tuple(profiles), len(diagnostics)
        )

    def _support(
        self, record: Mapping[str, Any], canonical: _CanonicalIndex
    ) -> _Support:
        _exact_fields(record, _SUPPORT_FIELDS, "evaluation support")
        support_id = _identity(
            record, "support_record_id", "evidence-support", "evaluation support"
        )
        semantic_field_id = _text(
            record["semantic_field_id"], "support semantic_field_id"
        )
        observation_ids = _texts(
            record["supporting_observation_ids"],
            "support observation IDs",
            minimum=1,
        )
        providers = _texts(record["providers"], "support providers", minimum=1)
        sources = _texts(record["sources"], "support sources", minimum=1)
        if type(record["provider_count"]) is not int or record["provider_count"] < 1:
            raise EvidencePolicyValidationError("support provider_count must be positive")
        if type(record["source_count"]) is not int or record["source_count"] < 1:
            raise EvidencePolicyValidationError("support source_count must be positive")
        if record["provider_count"] != len(providers) or record["source_count"] != len(
            sources
        ):
            raise EvidencePolicyValidationError("support provider/source count mismatch")
        if record["lineage_completeness"] != "COMPLETE_LINEAGE":
            raise EvidencePolicyValidationError(
                "Evidence Evaluation V0.1 requires complete lineage"
            )
        try:
            subject = SubjectRef.from_dict(record["subject"])
            observation_kind = ObservationKind(record["observation_kind"])
            semantic_statuses = {
                SemanticStatus(item)
                for item in _texts(
                    record["semantic_statuses"],
                    "support semantic_statuses",
                    minimum=1,
                )
            }
            presence_statuses = {
                PresenceStatus(item)
                for item in _texts(
                    record["presence_statuses"],
                    "support presence_statuses",
                    minimum=1,
                )
            }
        except (TypeError, ValueError) as exc:
            raise EvidencePolicyValidationError(f"invalid support identity: {exc}") from exc
        observations = tuple(canonical.representative(item) for item in observation_ids)
        materials = {canonical_json(_semantic_field_material(item)) for item in observations}
        if len(materials) != 1 or semantic_field_id != deterministic_id(
            "evidence-field", _semantic_field_material(observations[0])
        ):
            raise EvidencePolicyValidationError("support semantic field identity mismatch")
        if (
            any(item.subject != subject for item in observations)
            or any(item.observation_kind is not observation_kind for item in observations)
            or record["dimension"] != _observation_dimension(observations[0])
        ):
            raise EvidencePolicyValidationError("support semantic field replay mismatch")
        lineage_values = [
            lineage
            for observation_id in observation_ids
            for lineage in canonical.lineage_payloads(observation_id)
        ]
        if {item["provider"] for item in lineage_values} != set(providers) or {
            f"{item['provider']}::{item['source_tool']}" for item in lineage_values
        } != set(sources):
            raise EvidencePolicyValidationError("support provider/source replay mismatch")
        if {item.value.semantic_status for item in observations} != semantic_statuses or {
            item.value.presence_status for item in observations
        } != presence_statuses:
            raise EvidencePolicyValidationError("support value status replay mismatch")
        _lineage_set(
            record["lineage_references"],
            "support lineage",
            observation_ids,
            canonical,
        )
        return _Support(
            record=record,
            support_record_id=support_id,
            semantic_field_id=semantic_field_id,
            observation_ids=observation_ids,
            providers=providers,
            sources=sources,
            provider_count=record["provider_count"],
            lineage_completeness=record["lineage_completeness"],
        )

    def _conflict(
        self, record: Mapping[str, Any], canonical: _CanonicalIndex
    ) -> _EvaluationConflict:
        _exact_fields(record, _EVALUATION_CONFLICT_FIELDS, "evaluation conflict")
        conflict_id = _identity(
            record,
            "conflict_record_id",
            "evidence-conflict",
            "evaluation conflict",
        )
        support_id = _text(record["support_record_id"], "conflict support_record_id")
        support = self.supports.get(support_id)
        if support is None:
            raise EvidencePolicyValidationError("conflict references unknown support")
        for field in ("semantic_field_id", "subject", "observation_kind", "dimension"):
            if canonical_json(record[field]) != canonical_json(support.record[field]):
                raise EvidencePolicyValidationError("conflict semantic field mismatch")
        candidates = _texts(
            record["candidate_observation_ids"],
            "evaluation conflict candidates",
            minimum=2,
        )
        if not set(candidates) <= set(support.observation_ids):
            raise EvidencePolicyValidationError("conflict candidate missing from support")
        values = _mapping(record["candidate_values"], "conflict candidate_values")
        if set(values) != set(candidates):
            raise EvidencePolicyValidationError("conflict values do not match candidates")
        observed_values: set[str] = set()
        for observation_id in candidates:
            try:
                value = ValueEnvelope.from_dict(values[observation_id])
            except (TypeError, ValueError) as exc:
                raise EvidencePolicyValidationError(
                    f"invalid conflict candidate value: {exc}"
                ) from exc
            observation = canonical.representative(observation_id)
            if value.presence_status is not PresenceStatus.PRESENT or canonical_json(
                value
            ) != canonical_json(observation.value):
                raise EvidencePolicyValidationError("conflict candidate value mismatch")
            selected = value.normalized_value
            if selected is None:
                selected = value.raw_value
            observed_values.add(canonical_json({
                "value_type": value.value_type,
                "value": selected,
            }))
        if len(observed_values) < 2:
            raise EvidencePolicyValidationError("conflict requires different candidate values")
        providers = _texts(record["providers"], "conflict providers", minimum=1)
        sources = _texts(record["sources"], "conflict sources", minimum=1)
        lineages = [
            lineage
            for observation_id in candidates
            for lineage in canonical.lineage_payloads(observation_id)
        ]
        if {item["provider"] for item in lineages} != set(providers) or {
            f"{item['provider']}::{item['source_tool']}" for item in lineages
        } != set(sources):
            raise EvidencePolicyValidationError("conflict provider/source replay mismatch")
        _lineage_set(
            record["lineage_references"], "conflict lineage", candidates, canonical
        )
        if record["conflict_status"] != "CONFLICT_PRESENT":
            raise EvidencePolicyValidationError("invalid evaluation conflict status")
        return _EvaluationConflict(
            record=record,
            conflict_record_id=conflict_id,
            support_record_id=support_id,
            candidate_observation_ids=candidates,
        )

    @staticmethod
    def _profile(record: Mapping[str, Any]) -> _Profile:
        _exact_fields(record, _QUALITY_PROFILE_FIELDS, "evaluation profile")
        _identity(record, "profile_id", "evidence-quality-profile", "evaluation profile")
        support_id = _text(record["support_record_id"], "profile support_record_id")
        allowed = {
            "source_diversity": {"SINGLE_PROVIDER", "MULTI_PROVIDER_SUPPORT"},
            "observation_recency": {
                "KNOWN_OBSERVATION_TIME",
                "UNKNOWN_OBSERVATION_TIME",
                "MIXED_OBSERVATION_TIME",
            },
            "period_status": {"KNOWN_PERIOD", "UNKNOWN_PERIOD", "MIXED_PERIOD"},
            "completeness": {
                "ALL_VALUES_PRESENT",
                "NO_PRESENT_VALUE",
                "MIXED_VALUE_PRESENCE",
            },
            "lineage_completeness": {"COMPLETE_LINEAGE"},
            "consistency": {
                "SINGLE_VALUE",
                "SAME_VALUE",
                "CONFLICT_PRESENT",
                "NO_PRESENT_VALUE",
            },
        }
        for field, choices in allowed.items():
            if record[field] not in choices:
                raise EvidencePolicyValidationError(f"invalid profile {field}")
        attributes = _texts(
            record["qualitative_attributes"], "profile qualitative_attributes", minimum=1
        )
        if set(attributes) != {record[field] for field in allowed}:
            raise EvidencePolicyValidationError("profile qualitative attributes mismatch")
        return _Profile(
            record=record,
            support_record_id=support_id,
            source_diversity=record["source_diversity"],
            observation_recency=record["observation_recency"],
            period_status=record["period_status"],
            consistency=record["consistency"],
        )

    def _validate_diagnostics(self, values: Any) -> tuple[Mapping[str, Any], ...]:
        if not isinstance(values, tuple):
            raise EvidencePolicyValidationError("evaluation diagnostics must be an array")
        result: list[Mapping[str, Any]] = []
        identities: set[str] = set()
        for value in values:
            record = _mapping(value, "evaluation diagnostic")
            _exact_fields(record, _EVALUATION_DIAGNOSTIC_FIELDS, "evaluation diagnostic")
            identity = _identity(
                record, "diagnostic_id", "evidence-diagnostic", "evaluation diagnostic"
            )
            if identity in identities:
                raise EvidencePolicyValidationError("duplicate evaluation diagnostic")
            identities.add(identity)
            try:
                Severity(record["severity"])
            except (TypeError, ValueError) as exc:
                raise EvidencePolicyValidationError("invalid diagnostic severity") from exc
            support_ids = _texts(
                record["related_support_record_ids"], "diagnostic support IDs"
            )
            conflict_ids = _texts(
                record["related_conflict_record_ids"], "diagnostic conflict IDs"
            )
            observation_ids = _texts(
                record["related_observation_ids"], "diagnostic observation IDs"
            )
            if not set(support_ids) <= set(self.supports) or not set(conflict_ids) <= set(
                self.conflicts
            ) or not set(observation_ids) <= {
                item for support in self.supports.values() for item in support.observation_ids
            }:
                raise EvidencePolicyValidationError("orphan evaluation diagnostic reference")
            result.append(record)
        return tuple(result)

    def _validate_coverage(
        self,
        value: Any,
        canonical: _CanonicalIndex,
        profiles: tuple[_Profile, ...],
        diagnostic_count: int,
    ) -> None:
        coverage = _mapping(value, "evaluation coverage")
        _exact_fields(coverage, _EVALUATION_COVERAGE_FIELDS, "evaluation coverage")
        observations = tuple(
            canonical.representative(item) for item in sorted(canonical.observations)
        )
        expected = {
            "source_bundle_count": len(canonical.bundle_fingerprints),
            "canonical_observation_count": len(observations),
            "support_record_count": len(self.supports),
            "conflict_record_count": len(self.conflicts),
            "quality_profile_count": len(profiles),
            "provider_count": len({item.provenance.provider for item in observations}),
            "source_count": len({
                f"{item.provenance.provider}::{item.provenance.source_tool}"
                for item in observations
            }),
            "complete_lineage_record_count": len(self.supports),
            "single_provider_support_count": sum(
                item.source_diversity == "SINGLE_PROVIDER" for item in profiles
            ),
            "multi_provider_support_count": sum(
                item.source_diversity == "MULTI_PROVIDER_SUPPORT" for item in profiles
            ),
            "known_observation_time_profile_count": sum(
                item.observation_recency == "KNOWN_OBSERVATION_TIME" for item in profiles
            ),
            "unknown_observation_time_profile_count": sum(
                item.observation_recency == "UNKNOWN_OBSERVATION_TIME" for item in profiles
            ),
            "unknown_period_profile_count": sum(
                item.period_status == "UNKNOWN_PERIOD" for item in profiles
            ),
            "conflict_profile_count": sum(
                item.consistency == "CONFLICT_PRESENT" for item in profiles
            ),
            "present_observation_count": sum(
                item.value.presence_status is PresenceStatus.PRESENT for item in observations
            ),
            "non_present_observation_count": sum(
                item.value.presence_status is not PresenceStatus.PRESENT
                for item in observations
            ),
            "quality_issue_count": len(canonical.quality_issue_ids),
            "diagnostic_count": diagnostic_count,
            "observation_kind_counts": dict(sorted(Counter(
                item.observation_kind.value for item in observations
            ).items())),
            "semantic_status_counts": dict(sorted(Counter(
                item.value.semantic_status.value for item in observations
            ).items())),
        }
        if canonical_json(coverage) != canonical_json(expected):
            raise EvidencePolicyValidationError("evaluation coverage replay mismatch")


class _ConflictIndex:
    def __init__(
        self,
        payload: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        canonical: _CanonicalIndex,
    ) -> None:
        self.snapshot_id = payload["snapshot_id"]
        self.analyses: dict[str, _Analysis] = {}
        self.analysis_by_source: dict[str, _Analysis] = {}
        raw_analyses: dict[str, tuple[Mapping[str, Any], Mapping[str, str]]] = {}
        source_ids: set[str] = set()
        for raw in payload["conflict_analyses"]:
            record = _mapping(raw, "conflict analysis")
            analysis_id, source_id, candidate_map = self._analysis(
                record, evaluation, canonical
            )
            if analysis_id in raw_analyses or source_id in source_ids:
                raise EvidencePolicyValidationError("duplicate conflict analysis")
            raw_analyses[analysis_id] = (record, candidate_map)
            source_ids.add(source_id)
        attempts_by_analysis = self._attempts(payload["resolution_attempts"], raw_analyses)
        for analysis_id, (record, candidate_map) in raw_analyses.items():
            source_id = record["source_evaluation_conflict_id"]
            attempt_ids = tuple(sorted(
                item["resolution_attempt_id"] for item in attempts_by_analysis[analysis_id]
            ))
            analysis = _Analysis(
                record=record,
                conflict_analysis_id=analysis_id,
                source_conflict_id=source_id,
                candidate_by_observation=candidate_map,
                attempt_ids=attempt_ids,
            )
            self.analyses[analysis_id] = analysis
            self.analysis_by_source[source_id] = analysis
        if set(self.analysis_by_source) != set(evaluation.conflicts):
            raise EvidencePolicyValidationError(
                "Conflict Resolution analyses do not cover Evaluation conflicts"
            )
        expected_lineages = {
            canonical_json(lineage)
            for analysis in self.analyses.values()
            for candidate in analysis.record["candidates"]
            for lineage in candidate["lineage_references"]
        }
        snapshot_lineages = payload["lineage_index"]
        if not isinstance(snapshot_lineages, tuple):
            raise EvidencePolicyValidationError("conflict lineage_index must be an array")
        actual_lineages = {canonical_json(item) for item in snapshot_lineages}
        if len(actual_lineages) != len(snapshot_lineages) or actual_lineages != expected_lineages:
            raise EvidencePolicyValidationError("conflict lineage index mismatch")
        diagnostics = self._validate_diagnostics(
            payload["diagnostics"], attempts_by_analysis
        )
        self._validate_coverage(
            payload["coverage"],
            attempts_by_analysis,
            diagnostics,
            len(canonical.bundle_fingerprints),
        )

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
            raise EvidencePolicyValidationError("analysis references unknown Evaluation conflict")
        for field in ("semantic_field_id", "subject", "observation_kind", "dimension"):
            if canonical_json(record[field]) != canonical_json(source.record[field]):
                raise EvidencePolicyValidationError("analysis semantic field mismatch")
        if record["analysis_status"] != "CONFLICT_PRESENT":
            raise EvidencePolicyValidationError("invalid conflict analysis status")
        candidate_ids = _texts(
            record["candidate_ids"], "analysis candidate IDs", minimum=2
        )
        candidates = record["candidates"]
        if not isinstance(candidates, tuple) or len(candidates) != len(candidate_ids):
            raise EvidencePolicyValidationError("analysis candidate inventory mismatch")
        candidate_map: dict[str, str] = {}
        parsed_ids: set[str] = set()
        for raw in candidates:
            candidate = _mapping(raw, "conflict candidate")
            _exact_fields(candidate, _CANDIDATE_FIELDS, "conflict candidate")
            candidate_id = _identity(
                candidate, "candidate_id", "conflict-candidate", "conflict candidate"
            )
            observation_id = _text(
                candidate["observation_id"], "candidate observation_id"
            )
            if candidate["source_evaluation_conflict_id"] != source_id or observation_id not in set(
                source.candidate_observation_ids
            ):
                raise EvidencePolicyValidationError("candidate source conflict mismatch")
            observation = canonical.representative(observation_id)
            try:
                value = ValueEnvelope.from_dict(candidate["value"])
            except (TypeError, ValueError) as exc:
                raise EvidencePolicyValidationError("invalid conflict candidate value") from exc
            provider = observation.provenance.provider
            expected_source = f"{provider}::{observation.provenance.source_tool}"
            if (
                canonical_json(value) != canonical_json(observation.value)
                or candidate["provider"] != provider
                or candidate["source"] != expected_source
            ):
                raise EvidencePolicyValidationError("conflict candidate replay mismatch")
            _lineage_set(
                candidate["lineage_references"],
                "conflict candidate lineage",
                (observation_id,),
                canonical,
            )
            if observation_id in candidate_map or candidate_id in parsed_ids:
                raise EvidencePolicyValidationError("duplicate conflict candidate")
            candidate_map[observation_id] = candidate_id
            parsed_ids.add(candidate_id)
        if parsed_ids != set(candidate_ids) or set(candidate_map) != set(
            source.candidate_observation_ids
        ):
            raise EvidencePolicyValidationError("analysis candidates do not preserve conflict")
        fingerprints = _texts(
            record["source_bundle_fingerprints"],
            "analysis bundle fingerprints",
            minimum=1,
        )
        expected_fingerprints = {
            fingerprint
            for candidate in candidates
            for lineage in candidate["lineage_references"]
            for fingerprint in lineage["source_bundle_fingerprints"]
        }
        if set(fingerprints) != expected_fingerprints:
            raise EvidencePolicyValidationError("analysis fingerprint mismatch")
        return analysis_id, source_id, MappingProxyType(dict(sorted(candidate_map.items())))

    @staticmethod
    def _attempts(
        values: Any,
        analyses: Mapping[str, tuple[Mapping[str, Any], Mapping[str, str]]],
    ) -> dict[str, list[Mapping[str, Any]]]:
        if not isinstance(values, tuple):
            raise EvidencePolicyValidationError("resolution_attempts must be an array")
        result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        identities: set[str] = set()
        for raw in values:
            attempt = _mapping(raw, "resolution attempt")
            _exact_fields(attempt, _ATTEMPT_FIELDS, "resolution attempt")
            attempt_id = _identity(
                attempt,
                "resolution_attempt_id",
                "resolution-attempt",
                "resolution attempt",
            )
            if attempt_id in identities:
                raise EvidencePolicyValidationError("duplicate resolution attempt")
            identities.add(attempt_id)
            analysis_id = _text(
                attempt["conflict_analysis_id"], "attempt conflict_analysis_id"
            )
            analysis_entry = analyses.get(analysis_id)
            if analysis_entry is None:
                raise EvidencePolicyValidationError("attempt references unknown analysis")
            candidate_ids = _texts(
                attempt["candidate_ids"], "attempt candidate IDs", minimum=2
            )
            available_ids = _texts(
                attempt["available_evidence_candidate_ids"],
                "attempt available candidate IDs",
            )
            analysis_candidate_ids = set(analysis_entry[0]["candidate_ids"])
            if set(candidate_ids) != analysis_candidate_ids or not set(
                available_ids
            ) <= analysis_candidate_ids:
                raise EvidencePolicyValidationError("attempt candidate preservation mismatch")
            status = attempt["result_status"]
            if status not in _ATTEMPT_STATUSES:
                raise EvidencePolicyValidationError("invalid resolution attempt status")
            method = _text(attempt["attempted_method"], "attempt attempted_method")
            normalized_method = re.sub(r"[^A-Z0-9]+", "_", method.upper()).strip("_")
            if status == "NOT_ATTEMPTED":
                if normalized_method != "NOT_ATTEMPTED":
                    raise EvidencePolicyValidationError(
                        "NOT_ATTEMPTED requires attempted_method=NOT_ATTEMPTED"
                    )
            else:
                if normalized_method == "NOT_ATTEMPTED":
                    raise EvidencePolicyValidationError(
                        "an attempted status requires an explicit method"
                    )
                if any(token in normalized_method for token in _FORBIDDEN_METHOD_TOKENS):
                    raise EvidencePolicyValidationError(
                        "attempted_method uses a forbidden preference rule"
                    )
            produced = attempt["produced_candidate_id"]
            if status == "RESOLUTION_PRODUCED":
                if produced not in set(available_ids):
                    raise EvidencePolicyValidationError("produced candidate is not available")
            elif produced is not None:
                raise EvidencePolicyValidationError("non-produced attempt selects a candidate")
            process_evidence = attempt["process_evidence"]
            if not isinstance(process_evidence, MappingABC):
                raise EvidencePolicyValidationError("attempt process evidence must be an object")
            _reject_forbidden_process_fields(process_evidence, "attempt process_evidence")
            if status == "RESOLUTION_PRODUCED" and not process_evidence:
                raise EvidencePolicyValidationError(
                    "produced resolution requires process evidence"
                )
            result[analysis_id].append(attempt)
        if set(result) != set(analyses):
            raise EvidencePolicyValidationError(
                "every conflict analysis requires resolution process evidence"
            )
        return result

    def _validate_diagnostics(
        self,
        values: Any,
        attempts: Mapping[str, list[Mapping[str, Any]]],
    ) -> int:
        if not isinstance(values, tuple):
            raise EvidencePolicyValidationError("conflict diagnostics must be an array")
        identities: set[str] = set()
        analysis_ids = set(self.analyses) if self.analyses else set()
        attempt_ids = {
            item["resolution_attempt_id"]
            for records in attempts.values()
            for item in records
        }
        candidate_ids = {
            candidate["candidate_id"]
            for analysis in self.analyses.values()
            for candidate in analysis.record["candidates"]
        }
        for raw in values:
            record = _mapping(raw, "conflict diagnostic")
            _exact_fields(record, _CONFLICT_DIAGNOSTIC_FIELDS, "conflict diagnostic")
            identity = _identity(
                record,
                "diagnostic_id",
                "conflict-diagnostic",
                "conflict diagnostic",
            )
            if identity in identities:
                raise EvidencePolicyValidationError("duplicate conflict diagnostic")
            identities.add(identity)
            _text(record["code"], "conflict diagnostic code")
            _text(record["message"], "conflict diagnostic message")
            try:
                Severity(record["severity"])
            except (TypeError, ValueError) as exc:
                raise EvidencePolicyValidationError("invalid conflict diagnostic severity") from exc
            related_analyses = set(_texts(
                record["related_conflict_analysis_ids"], "diagnostic analysis IDs"
            ))
            related_attempts = set(_texts(
                record["related_resolution_attempt_ids"], "diagnostic attempt IDs"
            ))
            related_candidates = set(_texts(
                record["related_candidate_ids"], "diagnostic candidate IDs"
            ))
            if not related_analyses <= analysis_ids:
                raise EvidencePolicyValidationError("orphan conflict diagnostic analysis")
            if not related_attempts <= attempt_ids or not related_candidates <= candidate_ids:
                raise EvidencePolicyValidationError("orphan conflict diagnostic evidence")
        return len(identities)

    def _validate_coverage(
        self,
        value: Any,
        attempts: Mapping[str, list[Mapping[str, Any]]],
        diagnostic_count: int,
        bundle_count: int,
    ) -> None:
        coverage = _mapping(value, "conflict coverage")
        _exact_fields(coverage, _CONFLICT_COVERAGE_FIELDS, "conflict coverage")
        candidates = [
            candidate
            for analysis in self.analyses.values()
            for candidate in analysis.record["candidates"]
        ]
        all_attempts = [item for values in attempts.values() for item in values]
        expected = {
            "source_bundle_count": bundle_count,
            "source_evaluation_conflict_count": len(self.analyses),
            "conflict_analysis_count": len(self.analyses),
            "candidate_count": len(candidates),
            "resolution_attempt_count": len(all_attempts),
            "provider_count": len({item["provider"] for item in candidates}),
            "source_count": len({item["source"] for item in candidates}),
            "diagnostic_count": diagnostic_count,
            "attempt_status_counts": dict(sorted(Counter(
                item["result_status"] for item in all_attempts
            ).items())),
        }
        if canonical_json(coverage) != canonical_json(expected):
            raise EvidencePolicyValidationError("conflict coverage replay mismatch")


def _definition(
    description: str,
    conditions: Mapping[str, Any],
    expected_behavior: str,
) -> PolicyDefinition:
    payload = {
        "policy_version": "0.1",
        "description": description,
        "applicable_evidence_types": (
            EvidenceType.OBSERVED,
            EvidenceType.PROVIDER_ESTIMATE,
        ),
        "conditions": conditions,
        "expected_behavior": expected_behavior,
    }
    return PolicyDefinition(
        policy_id=deterministic_id("evidence-policy", payload), **payload
    )


def _default_definitions() -> tuple[PolicyDefinition, ...]:
    definitions = (
        _definition(
            "Record multi-provider support as context without increasing confidence.",
            {
                "condition_type": "MINIMUM_PROVIDER_COUNT",
                "minimum_provider_count": 2,
            },
            "RECORD_SUPPORT_CONTEXT_WITHOUT_ACTION",
        ),
        _definition(
            "Allow an interpretation process only when evidence lineage is complete.",
            {
                "condition_type": "LINEAGE_COMPLETENESS_REQUIRED",
                "required_status": "COMPLETE_LINEAGE",
            },
            "ALLOW_PROCESS_ONLY_WITH_COMPLETE_LINEAGE",
        ),
        _definition(
            "Block automatic interpretation when a conflict requires explicit review.",
            {"condition_type": "CONFLICT_PRESENT"},
            "BLOCK_AUTOMATIC_INTERPRETATION_AND_REQUIRE_REVIEW",
        ),
    )
    return tuple(sorted(definitions, key=lambda item: item.policy_id))


class EvidencePolicyBuilderV0_1:
    """Evaluate declarative process policy without selecting evidence or truth."""

    def build(self, request: EvidencePolicyRequest) -> EvidencePolicySnapshotV0_1:
        if not isinstance(request, EvidencePolicyRequest):
            raise EvidencePolicyValidationError("request must be EvidencePolicyRequest")
        canonical = _CanonicalIndex(request.canonical_bundles)
        evaluation = _EvaluationIndex(request.evidence_evaluation_snapshot, canonical)
        conflict = _ConflictIndex(
            request.conflict_resolution_snapshot, evaluation, canonical
        )
        definitions = _default_definitions()
        applicability: list[PolicyApplicabilityRecord] = []
        evaluations: list[PolicyEvaluationRecord] = []
        audits: list[PolicyAuditRecord] = []
        lineages: list[PolicyLineageReference] = []
        for policy in definitions:
            state = self._evaluate_policy(policy, evaluation, canonical)
            applicability_record = self._applicability(policy, state)
            evaluation_record = self._evaluation_record(
                policy, applicability_record, state, evaluation, conflict
            )
            audit_record = self._audit_record(
                policy,
                applicability_record,
                evaluation_record,
                state,
                evaluation,
                conflict,
            )
            applicability.append(applicability_record)
            evaluations.append(evaluation_record)
            audits.append(audit_record)
            lineages.extend(self._lineages(
                policy,
                evaluation_record,
                evaluation,
                conflict,
                canonical,
            ))
        ordered_applicability = tuple(sorted(
            applicability, key=lambda item: item.policy_applicability_id
        ))
        ordered_evaluations = tuple(sorted(
            evaluations, key=lambda item: item.policy_evaluation_id
        ))
        ordered_audits = tuple(sorted(audits, key=lambda item: item.policy_audit_id))
        ordered_lineages = tuple(sorted(lineages, key=lambda item: item.policy_lineage_id))
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
            "ruleset_version": EVIDENCE_POLICY_RULESET_VERSION,
            "source_evaluation_snapshot_id": evaluation.snapshot_id,
            "source_conflict_resolution_snapshot_id": conflict.snapshot_id,
            "source_bundle_fingerprints": canonical.bundle_fingerprints,
            "policy_definitions": definitions,
            "policy_applicability_records": ordered_applicability,
            "policy_evaluations": ordered_evaluations,
            "audit_records": ordered_audits,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": ordered_lineages,
        }
        snapshot = EvidencePolicySnapshotV0_1(
            snapshot_id=deterministic_id("evidence-policy-snapshot", payload),
            **payload,
        )
        return snapshot.validate_against_bundles(request.canonical_bundles)

    @staticmethod
    def _considered_supports(
        policy: PolicyDefinition,
        evaluation: _EvaluationIndex,
        canonical: _CanonicalIndex,
    ) -> tuple[_Support, ...]:
        allowed = set(policy.applicable_evidence_types)
        return tuple(sorted(
            (
                support
                for support in evaluation.supports.values()
                if any(
                    canonical.representative(observation_id).evidence_type in allowed
                    for observation_id in support.observation_ids
                )
            ),
            key=lambda item: item.support_record_id,
        ))

    def _evaluate_policy(
        self,
        policy: PolicyDefinition,
        evaluation: _EvaluationIndex,
        canonical: _CanonicalIndex,
    ) -> Mapping[str, Any]:
        considered = self._considered_supports(policy, evaluation, canonical)
        condition_type = policy.conditions["condition_type"]
        conflicts = tuple(sorted(
            (
                evaluation.conflict_by_support[item.support_record_id]
                for item in considered
                if item.support_record_id in evaluation.conflict_by_support
            ),
            key=lambda item: item.conflict_record_id,
        ))
        if condition_type == "MINIMUM_PROVIDER_COUNT":
            minimum = policy.conditions["minimum_provider_count"]
            matched = tuple(item for item in considered if item.provider_count >= minimum)
            applicable = bool(matched)
            result = "APPLICABLE_NO_ACTION" if applicable else "NOT_APPLICABLE"
            reasons = (
                "MULTI_PROVIDER_SUPPORT_RECORDED"
                if applicable
                else "MINIMUM_PROVIDER_COUNT_NOT_MET",
            )
        elif condition_type == "LINEAGE_COMPLETENESS_REQUIRED":
            matched = considered
            applicable = bool(considered)
            complete = all(
                item.lineage_completeness == policy.conditions["required_status"]
                for item in considered
            )
            result = (
                "NOT_APPLICABLE"
                if not applicable
                else "ACTION_ALLOWED"
                if complete
                else "ACTION_BLOCKED"
            )
            reasons = (
                "NO_APPLICABLE_EVIDENCE"
                if not applicable
                else "COMPLETE_LINEAGE_PROCESS_ALLOWED"
                if complete
                else "INCOMPLETE_LINEAGE_PROCESS_BLOCKED",
            )
        else:
            matched = tuple(
                item
                for item in considered
                if item.support_record_id in evaluation.conflict_by_support
            )
            applicable = bool(conflicts)
            result = "ACTION_BLOCKED" if applicable else "NOT_APPLICABLE"
            reasons = (
                "CONFLICT_REQUIRES_EXPLICIT_REVIEW"
                if applicable
                else "NO_CONFLICT_PRESENT",
            )
        return MappingProxyType({
            "condition_type": condition_type,
            "considered": considered,
            "matched": matched,
            "conflicts": conflicts,
            "applicable": applicable,
            "evaluation_result": result,
            "reason_codes": reasons,
        })

    @staticmethod
    def _applicability(
        policy: PolicyDefinition, state: Mapping[str, Any]
    ) -> PolicyApplicabilityRecord:
        matched_support_ids = {
            item.support_record_id for item in state["matched"]
        }
        payload = {
            "policy_id": policy.policy_id,
            "applicability_status": (
                "APPLICABLE" if state["applicable"] else "NOT_APPLICABLE"
            ),
            "matched_evidence_ids": tuple(
                item.support_record_id for item in state["matched"]
            ) if state["applicable"] else (),
            "matched_conflict_ids": tuple(
                item.conflict_record_id
                for item in state["conflicts"]
                if item.support_record_id in matched_support_ids
            ) if state["applicable"] else (),
            "reason_codes": state["reason_codes"],
        }
        return PolicyApplicabilityRecord(
            policy_applicability_id=deterministic_id(
                "policy-applicability", payload
            ),
            **payload,
        )

    @staticmethod
    def _evaluation_record(
        policy: PolicyDefinition,
        applicability: PolicyApplicabilityRecord,
        state: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        conflict: _ConflictIndex,
    ) -> PolicyEvaluationRecord:
        input_ids = tuple(item.support_record_id for item in state["considered"])
        related_conflicts = tuple(
            item.conflict_record_id for item in state["conflicts"]
        )
        payload = {
            "policy_id": policy.policy_id,
            "policy_applicability_id": applicability.policy_applicability_id,
            "input_evidence_ids": input_ids,
            "conflict_ids": related_conflicts,
            "evaluation_result": state["evaluation_result"],
            "expected_behavior": policy.expected_behavior,
            "audit_metadata": {
                "source_evaluation_snapshot_id": evaluation.snapshot_id,
                "source_conflict_resolution_snapshot_id": conflict.snapshot_id,
                "condition_type": state["condition_type"],
                "process_interpretation": "POLICY_RESULT_IS_PROCESS_PERMISSION_ONLY",
            },
        }
        return PolicyEvaluationRecord(
            policy_evaluation_id=deterministic_id("policy-evaluation", payload),
            **payload,
        )

    @staticmethod
    def _audit_record(
        policy: PolicyDefinition,
        applicability: PolicyApplicabilityRecord,
        evaluation_record: PolicyEvaluationRecord,
        state: Mapping[str, Any],
        evaluation: _EvaluationIndex,
        conflict: _ConflictIndex,
    ) -> PolicyAuditRecord:
        incomplete_count = sum(
            item.lineage_completeness != "COMPLETE_LINEAGE"
            for item in state["considered"]
        )
        payload = {
            "policy_id": policy.policy_id,
            "policy_version": policy.policy_version,
            "policy_applicability_id": applicability.policy_applicability_id,
            "policy_evaluation_id": evaluation_record.policy_evaluation_id,
            "condition_type": state["condition_type"],
            "condition_observations": {
                "considered_evidence_count": len(state["considered"]),
                "matched_evidence_count": len(state["matched"]),
                "related_conflict_count": len(state["conflicts"]),
                "incomplete_lineage_count": incomplete_count,
            },
            "evaluation_result": evaluation_record.evaluation_result,
            "source_evaluation_snapshot_id": evaluation.snapshot_id,
            "source_conflict_resolution_snapshot_id": conflict.snapshot_id,
        }
        return PolicyAuditRecord(
            policy_audit_id=deterministic_id("policy-audit", payload), **payload
        )

    @staticmethod
    def _lineages(
        policy: PolicyDefinition,
        evaluation_record: PolicyEvaluationRecord,
        evaluation: _EvaluationIndex,
        conflict: _ConflictIndex,
        canonical: _CanonicalIndex,
    ) -> tuple[PolicyLineageReference, ...]:
        result: list[PolicyLineageReference] = []
        for support_id in evaluation_record.input_evidence_ids:
            support = evaluation.supports[support_id]
            evaluation_conflict = evaluation.conflict_by_support.get(support_id)
            analysis = (
                conflict.analysis_by_source.get(evaluation_conflict.conflict_record_id)
                if evaluation_conflict is not None
                else None
            )
            for observation_id in support.observation_ids:
                candidate_id = (
                    analysis.candidate_by_observation.get(observation_id)
                    if analysis is not None
                    else None
                )
                for source_lineage in canonical.lineage_payloads(observation_id):
                    observation = canonical.representative(observation_id)
                    has_conflict_lineage = candidate_id is not None
                    payload = {
                        "policy_id": policy.policy_id,
                        "policy_evaluation_id": evaluation_record.policy_evaluation_id,
                        "support_record_id": support_id,
                        "conflict_record_id": (
                            evaluation_conflict.conflict_record_id
                            if has_conflict_lineage and evaluation_conflict is not None
                            else None
                        ),
                        "conflict_analysis_id": (
                            analysis.conflict_analysis_id
                            if has_conflict_lineage and analysis is not None
                            else None
                        ),
                        "conflict_candidate_id": candidate_id,
                        "resolution_attempt_ids": (
                            analysis.attempt_ids
                            if has_conflict_lineage and analysis is not None
                            else ()
                        ),
                        "observation_id": observation_id,
                        "semantic_observation_id": source_lineage[
                            "semantic_observation_id"
                        ],
                        "observation_kind": observation.observation_kind,
                        "evidence_type": observation.evidence_type,
                        "transformation_run_id": source_lineage[
                            "transformation_run_id"
                        ],
                        "mapping_version": source_lineage["mapping_version"],
                        "raw_evidence_id": source_lineage["raw_evidence_id"],
                        "collection_run_id": source_lineage["collection_run_id"],
                        "provider": source_lineage["provider"],
                        "source_tool": source_lineage["source_tool"],
                        "source_field": source_lineage["source_field"],
                        "source_bundle_fingerprints": source_lineage[
                            "source_bundle_fingerprints"
                        ],
                    }
                    result.append(PolicyLineageReference(
                        policy_lineage_id=deterministic_id(
                            "policy-lineage", payload
                        ),
                        **payload,
                    ))
        return tuple(sorted(result, key=lambda item: item.policy_lineage_id))

    @staticmethod
    def _diagnostic(
        code: str,
        evaluations: Iterable[PolicyEvaluationRecord],
        message: str,
    ) -> PolicyDiagnostic:
        values = tuple(evaluations)
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_policy_ids": tuple(sorted({item.policy_id for item in values})),
            "related_policy_evaluation_ids": tuple(sorted({
                item.policy_evaluation_id for item in values
            })),
            "message": message,
        }
        return PolicyDiagnostic(
            diagnostic_id=deterministic_id("policy-diagnostic", payload), **payload
        )

    def _diagnostics(
        self, evaluations: tuple[PolicyEvaluationRecord, ...]
    ) -> tuple[PolicyDiagnostic, ...]:
        messages = {
            "ACTION_ALLOWED": (
                "PROCESS_ALLOWED_IS_NOT_TRUTH",
                "A policy allowed an audited process; no truth or value was established.",
            ),
            "ACTION_BLOCKED": (
                "PROCESS_BLOCKED_WITHOUT_BUSINESS_CONCLUSION",
                "A policy blocked a process without selecting evidence or making a business conclusion.",
            ),
            "APPLICABLE_NO_ACTION": (
                "CONTEXT_RECORDED_WITHOUT_ACTION",
                "Applicable evidence context was recorded without producing an action.",
            ),
            "NOT_APPLICABLE": (
                "POLICY_NOT_APPLICABLE",
                "A declarative policy did not apply to the supplied evidence.",
            ),
        }
        result = []
        for status, (code, message) in messages.items():
            selected = tuple(item for item in evaluations if item.evaluation_result == status)
            if selected:
                result.append(self._diagnostic(code, selected, message))
        return tuple(sorted(result, key=lambda item: item.diagnostic_id))


__all__ = ("EvidencePolicyBuilderV0_1",)
