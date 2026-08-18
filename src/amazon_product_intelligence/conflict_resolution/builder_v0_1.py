"""Auditable, non-automatic Conflict Resolution V0.1 builder."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    ObservationKind,
    Severity,
    SubjectRef,
    ValueEnvelope,
    canonical_json,
    deterministic_id,
)

from .errors import ConflictValidationError
from .models import (
    CONFLICT_RESOLUTION_RULESET_VERSION,
    ConflictAnalysisRecord,
    ConflictCandidate,
    ConflictDiagnostic,
    ConflictLineageReference,
    ConflictResolutionRequest,
    ConflictResolutionSnapshotV0_1,
    ResolutionAttemptRecord,
    bundle_fingerprint,
    coverage_from_records,
    observation_revision_content,
    semantic_field_material,
)


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


@dataclass(slots=True)
class _Emission:
    observation: CanonicalObservation
    bundle_fingerprints: set[str]


@dataclass(slots=True)
class _IndexedRecord:
    record: Any
    bundle_fingerprints: set[str]


class _RecordIndex:
    """Collision-safe canonical index used to rebuild candidate lineage."""

    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(bundle_fingerprint(item) for item in bundles))
        self.observation_revisions: dict[str, str] = {}
        self.observations: dict[str, dict[str, _Emission]] = defaultdict(dict)
        self.runs: dict[str, _IndexedRecord] = {}
        self.issues: dict[str, _IndexedRecord] = {}
        self.raw_fingerprints: dict[str, set[str]] = defaultdict(set)
        self._generic: dict[tuple[str, str], str] = {}
        self._record_namespaces: dict[str, str] = {}
        for fingerprint, bundle in sorted(
            ((bundle_fingerprint(item), item) for item in bundles), key=lambda item: item[0]
        ):
            self._consume_bundle(bundle, fingerprint)

    @staticmethod
    def _merge_record(
        index: dict[str, _IndexedRecord],
        identity: str,
        record: Any,
        fingerprint: str,
        kind: str,
    ) -> None:
        current = index.get(identity)
        if current is not None and canonical_json(current.record) != canonical_json(record):
            raise ConflictValidationError(f"{kind} identity collision: {identity}")
        if current is None:
            index[identity] = _IndexedRecord(record=record, bundle_fingerprints={fingerprint})
        else:
            current.bundle_fingerprints.add(fingerprint)

    def _record_namespace(self, identity: str, namespace: str) -> None:
        current = self._record_namespaces.get(identity)
        if current is not None and current != namespace:
            raise ConflictValidationError(
                f"canonical source identity crosses namespaces: {identity}"
            )
        self._record_namespaces.setdefault(identity, namespace)

    def _consume_bundle(self, bundle: CanonicalEvidenceBundle, fingerprint: str) -> None:
        for raw_id in bundle.raw_evidence_references:
            self.raw_fingerprints[raw_id].add(fingerprint)
        for run in bundle.transformation_runs:
            self._merge_record(
                self.runs, run.transformation_run_id, run, fingerprint, "transformation run"
            )
        for observation in bundle.observations:
            self._record_namespace(observation.observation_id, "observation")
            revision = canonical_json(observation_revision_content(observation))
            prior = self.observation_revisions.get(observation.observation_id)
            if prior is not None and prior != revision:
                raise ConflictValidationError(
                    f"observation identity collision: {observation.observation_id}"
                )
            self.observation_revisions[observation.observation_id] = revision
            run_id = observation.provenance.transformation.transformation_run_id
            current = self.observations[observation.observation_id].get(run_id)
            if current is not None and canonical_json(current.observation) != canonical_json(
                observation
            ):
                raise ConflictValidationError(
                    f"observation emission collision: {observation.observation_id}"
                )
            if current is None:
                self.observations[observation.observation_id][run_id] = _Emission(
                    observation=observation, bundle_fingerprints={fingerprint}
                )
            else:
                current.bundle_fingerprints.add(fingerprint)
        for query in bundle.query_execution_records:
            self._record_namespace(query.query_execution_id, "query execution")
            key = ("query execution", query.query_execution_id)
            content = canonical_json(query)
            if key in self._generic and self._generic[key] != content:
                raise ConflictValidationError(
                    f"query execution identity collision: {query.query_execution_id}"
                )
            self._generic[key] = content
        for issue in bundle.quality_issues:
            self._merge_record(self.issues, issue.issue_id, issue, fingerprint, "quality issue")
        for kind, records, field in (
            ("conflict", bundle.conflicts, "conflict_id"),
            ("resolution", bundle.resolutions, "resolution_id"),
        ):
            for record in records:
                identity = getattr(record, field)
                content = canonical_json(record)
                key = (kind, identity)
                if key in self._generic and self._generic[key] != content:
                    raise ConflictValidationError(f"{kind} identity collision: {identity}")
                self._generic[key] = content

    def representative(self, observation_id: str) -> CanonicalObservation:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise ConflictValidationError(f"orphan conflict candidate: {observation_id}")
        return min(
            emissions.values(), key=lambda item: canonical_json(item.observation)
        ).observation

    def lineages(self, observation_id: str) -> tuple[ConflictLineageReference, ...]:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise ConflictValidationError(f"orphan conflict candidate: {observation_id}")
        references: list[ConflictLineageReference] = []
        for run_id, emission in sorted(emissions.items()):
            observation = emission.observation
            transformation = observation.provenance.transformation
            run_entry = self.runs.get(run_id)
            if run_entry is None:
                raise ConflictValidationError(f"orphan transformation run: {run_id}")
            run = run_entry.record
            raw_id = transformation.raw_evidence_reference
            if raw_id not in self.raw_fingerprints or raw_id not in run.input_raw_evidence_references:
                raise ConflictValidationError(f"orphan raw evidence: {raw_id}")
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or observation_id not in run.output_observation_ids
            ):
                raise ConflictValidationError(
                    f"mapping or collection mismatch for {observation_id}"
                )
            references.append(ConflictLineageReference(
                observation_id=observation_id,
                semantic_observation_id=observation.semantic_observation_id,
                observation_kind=observation.observation_kind,
                transformation_run_id=run_id,
                mapping_version=transformation.mapping_version,
                raw_evidence_id=raw_id,
                collection_run_id=transformation.collection_run_id,
                provider=observation.provenance.provider,
                source_tool=observation.provenance.source_tool,
                source_field=observation.provenance.source_field,
                source_bundle_fingerprints=tuple(sorted(emission.bundle_fingerprints)),
            ))
        return tuple(sorted(references, key=canonical_json))


class ConflictResolutionBuilderV0_1:
    """Analyze conflicts and record explicit attempts without automatic selection."""

    def build(
        self, request: ConflictResolutionRequest
    ) -> ConflictResolutionSnapshotV0_1:
        if not isinstance(request, ConflictResolutionRequest):
            raise ConflictValidationError("request must be ConflictResolutionRequest")
        snapshot = self._build_snapshot(request)
        return snapshot.validate_against_bundles(request.canonical_bundles)

    def _build_snapshot(
        self, request: ConflictResolutionRequest
    ) -> ConflictResolutionSnapshotV0_1:
        index = _RecordIndex(request.canonical_bundles)
        evaluation = request.evidence_evaluation_snapshot
        analyses = tuple(sorted(
            (
                self._analysis_from_evaluation(record, index)
                for record in evaluation["conflict_records"]
            ),
            key=lambda item: item.conflict_analysis_id,
        ))
        attempts = self._attempts(analyses, request.resolution_attempts)
        diagnostics = self._diagnostics(analyses, attempts)
        lineage_map = {
            canonical_json(lineage): lineage
            for analysis in analyses
            for candidate in analysis.candidates
            for lineage in candidate.lineage_references
        }
        coverage = coverage_from_records(
            bundle_count=len(index.bundle_fingerprints),
            analyses=analyses,
            attempts=attempts,
            diagnostics=diagnostics,
        )
        payload = {
            "ruleset_version": CONFLICT_RESOLUTION_RULESET_VERSION,
            "source_evaluation_snapshot_id": evaluation["snapshot_id"],
            "source_bundle_fingerprints": index.bundle_fingerprints,
            "conflict_analyses": analyses,
            "resolution_attempts": attempts,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": tuple(lineage_map[key] for key in sorted(lineage_map)),
        }
        return ConflictResolutionSnapshotV0_1(
            snapshot_id=deterministic_id("conflict-resolution-snapshot", payload), **payload
        )

    @staticmethod
    def _require_mapping(value: Any, path: str) -> Mapping[str, Any]:
        if not isinstance(value, Mapping):
            raise ConflictValidationError(f"{path} must be an object")
        return value

    @staticmethod
    def _require_unique_texts(
        value: Any, path: str, *, minimum: int = 0
    ) -> tuple[str, ...]:
        if not isinstance(value, tuple):
            raise ConflictValidationError(f"{path} must be an array")
        if len(value) < minimum:
            raise ConflictValidationError(f"{path} requires at least {minimum} values")
        if any(type(item) is not str or not item.strip() for item in value):
            raise ConflictValidationError(f"{path} must contain non-empty text")
        if len(set(value)) != len(value):
            raise ConflictValidationError(f"{path} must contain unique values")
        return value

    def _analysis_from_evaluation(
        self, record: Any, index: _RecordIndex
    ) -> ConflictAnalysisRecord:
        conflict = self._require_mapping(record, "evaluation conflict")
        if set(conflict) != _EVALUATION_CONFLICT_FIELDS:
            raise ConflictValidationError("evaluation conflict fields do not match V0.1")
        if conflict["conflict_status"] != "CONFLICT_PRESENT":
            raise ConflictValidationError("evaluation conflict must be CONFLICT_PRESENT")
        source_conflict_id = conflict["conflict_record_id"]
        if type(source_conflict_id) is not str or not source_conflict_id.strip():
            raise ConflictValidationError("evaluation conflict ID must be non-empty text")
        for field in ("support_record_id", "semantic_field_id"):
            value = conflict[field]
            if type(value) is not str or not value.strip():
                raise ConflictValidationError(f"evaluation conflict {field} must be text")
        identity_payload = dict(conflict)
        identity_payload.pop("conflict_record_id")
        if source_conflict_id != deterministic_id("evidence-conflict", identity_payload):
            raise ConflictValidationError("evaluation conflict identity mismatch")
        try:
            subject = SubjectRef.from_dict(conflict["subject"])
            observation_kind = ObservationKind(conflict["observation_kind"])
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise ConflictValidationError(f"invalid evaluation conflict identity: {exc}") from exc
        dimension = conflict["dimension"]
        if type(dimension) is not str or not dimension.strip():
            raise ConflictValidationError("evaluation conflict dimension must be text")
        candidate_observation_ids = self._require_unique_texts(
            conflict["candidate_observation_ids"],
            "evaluation candidate_observation_ids",
            minimum=2,
        )
        candidate_values = self._require_mapping(
            conflict["candidate_values"], "evaluation candidate_values"
        )
        if set(candidate_values) != set(candidate_observation_ids):
            raise ConflictValidationError("evaluation candidate values do not match IDs")
        candidates: list[ConflictCandidate] = []
        candidate_observations: list[CanonicalObservation] = []
        for observation_id in sorted(candidate_observation_ids):
            if type(observation_id) is not str or not observation_id:
                raise ConflictValidationError("candidate observation ID must be text")
            observation = index.representative(observation_id)
            try:
                value = ValueEnvelope.from_dict(candidate_values[observation_id])
            except ContractValidationError as exc:
                raise ConflictValidationError(f"invalid evaluation candidate value: {exc}") from exc
            if canonical_json(value) != canonical_json(observation.value):
                raise ConflictValidationError("evaluation candidate value mismatch")
            if (
                observation.subject != subject
                or observation.observation_kind is not observation_kind
            ):
                raise ConflictValidationError("evaluation candidate semantic identity mismatch")
            candidate_observations.append(observation)
            lineages = index.lineages(observation_id)
            provider = observation.provenance.provider
            source = f"{provider}::{observation.provenance.source_tool}"
            payload = {
                "source_evaluation_conflict_id": source_conflict_id,
                "observation_id": observation_id,
                "value": value,
                "provider": provider,
                "source": source,
                "lineage_references": lineages,
            }
            candidates.append(ConflictCandidate(
                candidate_id=deterministic_id("conflict-candidate", payload), **payload
            ))
        field_materials = {
            canonical_json(semantic_field_material(item)) for item in candidate_observations
        }
        if len(field_materials) != 1:
            raise ConflictValidationError(
                "evaluation conflict combines non-comparable semantic fields"
            )
        expected_field_id = deterministic_id(
            "evidence-field", semantic_field_material(candidate_observations[0])
        )
        if conflict["semantic_field_id"] != expected_field_id:
            raise ConflictValidationError("evaluation semantic field identity mismatch")
        providers = self._require_unique_texts(
            conflict["providers"], "evaluation conflict providers", minimum=1
        )
        sources = self._require_unique_texts(
            conflict["sources"], "evaluation conflict sources", minimum=1
        )
        if set(providers) != {item.provider for item in candidates}:
            raise ConflictValidationError("evaluation conflict providers do not match candidates")
        if set(sources) != {item.source for item in candidates}:
            raise ConflictValidationError("evaluation conflict sources do not match candidates")
        evaluation_lineages = conflict["lineage_references"]
        if not isinstance(evaluation_lineages, tuple):
            raise ConflictValidationError("evaluation conflict lineage must be an array")
        if len({canonical_json(item) for item in evaluation_lineages}) != len(
            evaluation_lineages
        ):
            raise ConflictValidationError("evaluation conflict lineage must be unique")
        expected_lineages = {
            canonical_json(lineage)
            for candidate in candidates
            for lineage in candidate.lineage_references
        }
        if {canonical_json(item) for item in evaluation_lineages} != expected_lineages:
            raise ConflictValidationError("evaluation conflict lineage mismatch")
        ordered_candidates = tuple(sorted(candidates, key=lambda item: item.candidate_id))
        analysis_payload = {
            "source_evaluation_conflict_id": source_conflict_id,
            "semantic_field_id": conflict["semantic_field_id"],
            "subject": subject,
            "observation_kind": observation_kind,
            "dimension": dimension,
            "candidate_ids": tuple(sorted(item.candidate_id for item in ordered_candidates)),
            "candidates": ordered_candidates,
            "analysis_status": "CONFLICT_PRESENT",
            "source_bundle_fingerprints": tuple(sorted({
                fingerprint
                for candidate in ordered_candidates
                for lineage in candidate.lineage_references
                for fingerprint in lineage.source_bundle_fingerprints
            })),
        }
        return ConflictAnalysisRecord(
            conflict_analysis_id=deterministic_id("conflict-analysis", analysis_payload),
            **analysis_payload,
        )

    @staticmethod
    def _default_attempt(analysis: ConflictAnalysisRecord) -> ResolutionAttemptRecord:
        payload = {
            "conflict_analysis_id": analysis.conflict_analysis_id,
            "attempted_method": "NOT_ATTEMPTED",
            "candidate_ids": analysis.candidate_ids,
            "available_evidence_candidate_ids": analysis.candidate_ids,
            "result_status": "NOT_ATTEMPTED",
            "produced_candidate_id": None,
            "process_evidence": {
                "interpretation": "NO_RESOLUTION_RULE_WAS_APPLIED",
            },
        }
        return ResolutionAttemptRecord(
            resolution_attempt_id=deterministic_id("resolution-attempt", payload), **payload
        )

    def _attempts(
        self,
        analyses: tuple[ConflictAnalysisRecord, ...],
        requested: tuple[ResolutionAttemptRecord, ...],
    ) -> tuple[ResolutionAttemptRecord, ...]:
        analysis_by_id = {item.conflict_analysis_id: item for item in analyses}
        requested_by_analysis: dict[str, list[ResolutionAttemptRecord]] = defaultdict(list)
        for attempt in requested:
            analysis = analysis_by_id.get(attempt.conflict_analysis_id)
            if analysis is None:
                raise ConflictValidationError("requested attempt references an absent analysis")
            if set(attempt.candidate_ids) != set(analysis.candidate_ids):
                raise ConflictValidationError("requested attempt does not preserve candidates")
            requested_by_analysis[attempt.conflict_analysis_id].append(attempt)
        result = [
            attempt
            for analysis in analyses
            for attempt in (
                requested_by_analysis.get(analysis.conflict_analysis_id)
                or [self._default_attempt(analysis)]
            )
        ]
        return tuple(sorted(result, key=lambda item: item.resolution_attempt_id))

    @staticmethod
    def _diagnostic(
        code: str,
        analyses: Iterable[ConflictAnalysisRecord],
        attempts: Iterable[ResolutionAttemptRecord],
        message: str,
    ) -> ConflictDiagnostic:
        analysis_values = tuple(analyses)
        attempt_values = tuple(attempts)
        candidate_ids = tuple(sorted({
            candidate.candidate_id
            for analysis in analysis_values
            for candidate in analysis.candidates
        }))
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_conflict_analysis_ids": tuple(sorted({
                item.conflict_analysis_id for item in analysis_values
            })),
            "related_resolution_attempt_ids": tuple(sorted({
                item.resolution_attempt_id for item in attempt_values
            })),
            "related_candidate_ids": candidate_ids,
            "message": message,
        }
        return ConflictDiagnostic(
            diagnostic_id=deterministic_id("conflict-diagnostic", payload), **payload
        )

    def _diagnostics(
        self,
        analyses: tuple[ConflictAnalysisRecord, ...],
        attempts: tuple[ResolutionAttemptRecord, ...],
    ) -> tuple[ConflictDiagnostic, ...]:
        result: list[ConflictDiagnostic] = []
        if not analyses:
            result.append(self._diagnostic(
                "NO_EVALUATION_CONFLICTS",
                (),
                (),
                "The supplied Evidence Evaluation snapshot contains no conflict records.",
            ))
        not_produced = tuple(
            item for item in attempts if item.result_status != "RESOLUTION_PRODUCED"
        )
        if not_produced:
            result.append(self._diagnostic(
                "CONFLICTS_PRESERVED_WITHOUT_AUTOMATIC_SELECTION",
                (
                    analysis
                    for analysis in analyses
                    if any(
                        attempt.conflict_analysis_id == analysis.conflict_analysis_id
                        for attempt in not_produced
                    )
                ),
                not_produced,
                "Conflict candidates remain preserved; no automatic candidate was selected.",
            ))
        produced = tuple(
            item for item in attempts if item.result_status == "RESOLUTION_PRODUCED"
        )
        if produced:
            result.append(self._diagnostic(
                "PRODUCED_CANDIDATE_IS_RULE_OUTPUT_NOT_TRUTH",
                (
                    analysis
                    for analysis in analyses
                    if any(
                        attempt.conflict_analysis_id == analysis.conflict_analysis_id
                        for attempt in produced
                    )
                ),
                produced,
                "An explicit rule produced a candidate; this is not a canonical truth claim.",
            ))
        return tuple(sorted(result, key=lambda item: item.diagnostic_id))


__all__ = ("ConflictResolutionBuilderV0_1",)
