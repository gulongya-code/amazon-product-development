"""Qualitative, evidence-preserving Evaluation Foundation V0.1 builder."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    PresenceStatus,
    Severity,
    canonical_json,
    deterministic_id,
)

from .errors import EvidenceValidationError
from .models import (
    EVIDENCE_EVALUATION_RULESET_VERSION,
    EvidenceConflictRecord,
    EvidenceDiagnostic,
    EvidenceEvaluationRequest,
    EvidenceEvaluationSnapshotV0_1,
    EvidenceLineageReference,
    EvidenceQualityProfile,
    EvidenceSupportRecord,
    bundle_fingerprint,
    coverage_from_records,
    observation_dimension,
    observation_revision_content,
    qualitative_dimensions,
    semantic_field_material,
)


@dataclass(slots=True)
class _Emission:
    observation: CanonicalObservation
    bundle_fingerprints: set[str]


@dataclass(slots=True)
class _IndexedRecord:
    record: Any
    bundle_fingerprints: set[str]


class _RecordIndex:
    """Collision-safe canonical observation index with replayable lineage."""

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
            raise EvidenceValidationError(f"{kind} identity collision: {identity}")
        if current is None:
            index[identity] = _IndexedRecord(record=record, bundle_fingerprints={fingerprint})
        else:
            current.bundle_fingerprints.add(fingerprint)

    def _record_namespace(self, identity: str, namespace: str) -> None:
        current = self._record_namespaces.get(identity)
        if current is not None and current != namespace:
            raise EvidenceValidationError(
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
                raise EvidenceValidationError(
                    f"observation identity collision: {observation.observation_id}"
                )
            self.observation_revisions[observation.observation_id] = revision
            run_id = observation.provenance.transformation.transformation_run_id
            current = self.observations[observation.observation_id].get(run_id)
            if current is not None and canonical_json(current.observation) != canonical_json(
                observation
            ):
                raise EvidenceValidationError(
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
                raise EvidenceValidationError(
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
                    raise EvidenceValidationError(f"{kind} identity collision: {identity}")
                self._generic[key] = content

    def representatives(self) -> tuple[CanonicalObservation, ...]:
        return tuple(
            min(emissions.values(), key=lambda item: canonical_json(item.observation)).observation
            for _, emissions in sorted(self.observations.items())
        )

    def lineages(self, observation_id: str) -> tuple[EvidenceLineageReference, ...]:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise EvidenceValidationError(f"orphan canonical observation: {observation_id}")
        references: list[EvidenceLineageReference] = []
        for run_id, emission in sorted(emissions.items()):
            observation = emission.observation
            transformation = observation.provenance.transformation
            run_entry = self.runs.get(run_id)
            if run_entry is None:
                raise EvidenceValidationError(f"orphan transformation run: {run_id}")
            run = run_entry.record
            raw_id = transformation.raw_evidence_reference
            if raw_id not in self.raw_fingerprints or raw_id not in run.input_raw_evidence_references:
                raise EvidenceValidationError(f"orphan raw evidence: {raw_id}")
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
                or run.provider != observation.provenance.provider
                or observation_id not in run.output_observation_ids
            ):
                raise EvidenceValidationError(
                    f"mapping or collection mismatch for {observation_id}"
                )
            references.append(EvidenceLineageReference(
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


class EvidenceEvaluationBuilderV0_1:
    """Build qualitative evidence attributes without a numeric weight or decision."""

    def build(
        self, request: EvidenceEvaluationRequest
    ) -> EvidenceEvaluationSnapshotV0_1:
        if not isinstance(request, EvidenceEvaluationRequest):
            raise EvidenceValidationError("request must be EvidenceEvaluationRequest")
        snapshot = self._build_snapshot(request)
        return snapshot.validate_against_bundles(request.canonical_bundles)

    def _build_snapshot(
        self, request: EvidenceEvaluationRequest
    ) -> EvidenceEvaluationSnapshotV0_1:
        index = _RecordIndex(request.canonical_bundles)
        observations = index.representatives()
        groups: dict[str, list[CanonicalObservation]] = defaultdict(list)
        materials: dict[str, dict[str, Any]] = {}
        for observation in observations:
            material = semantic_field_material(observation)
            key = canonical_json(material)
            groups[key].append(observation)
            materials[key] = material
        supports: list[EvidenceSupportRecord] = []
        profiles: list[EvidenceQualityProfile] = []
        conflicts: list[EvidenceConflictRecord] = []
        all_lineages: dict[str, EvidenceLineageReference] = {}
        for key in sorted(groups):
            records = tuple(sorted(groups[key], key=lambda item: item.observation_id))
            lineages = tuple(sorted(
                (lineage for item in records for lineage in index.lineages(item.observation_id)),
                key=canonical_json,
            ))
            for lineage in lineages:
                all_lineages[canonical_json(lineage)] = lineage
            support = self._support_record(materials[key], records, lineages)
            profile = self._quality_profile(support, records)
            supports.append(support)
            profiles.append(profile)
            if profile.consistency == "CONFLICT_PRESENT":
                conflicts.append(self._conflict_record(support, records, lineages))
        ordered_supports = tuple(sorted(supports, key=lambda item: item.support_record_id))
        ordered_profiles = tuple(sorted(profiles, key=lambda item: item.profile_id))
        ordered_conflicts = tuple(sorted(conflicts, key=lambda item: item.conflict_record_id))
        diagnostics = self._diagnostics(ordered_supports, ordered_profiles, ordered_conflicts)
        coverage = coverage_from_records(
            bundle_count=len(index.bundle_fingerprints),
            observations=observations,
            profiles=ordered_profiles,
            supports=ordered_supports,
            conflicts=ordered_conflicts,
            quality_issue_count=len(index.issues),
            diagnostics=diagnostics,
        )
        payload = {
            "ruleset_version": EVIDENCE_EVALUATION_RULESET_VERSION,
            "source_bundle_fingerprints": index.bundle_fingerprints,
            "evidence_quality_profiles": ordered_profiles,
            "support_records": ordered_supports,
            "conflict_records": ordered_conflicts,
            "coverage": coverage,
            "diagnostics": diagnostics,
            "lineage_index": tuple(all_lineages[key] for key in sorted(all_lineages)),
        }
        return EvidenceEvaluationSnapshotV0_1(
            snapshot_id=deterministic_id("evidence-evaluation-snapshot", payload), **payload
        )

    @staticmethod
    def _support_record(
        material: dict[str, Any],
        records: tuple[CanonicalObservation, ...],
        lineages: tuple[EvidenceLineageReference, ...],
    ) -> EvidenceSupportRecord:
        providers = tuple(sorted({item.provenance.provider for item in records}))
        sources = tuple(sorted({
            f"{item.provenance.provider}::{item.provenance.source_tool}" for item in records
        }))
        payload = {
            "semantic_field_id": deterministic_id("evidence-field", material),
            "subject": records[0].subject,
            "observation_kind": records[0].observation_kind,
            "dimension": observation_dimension(records[0]),
            "supporting_observation_ids": tuple(item.observation_id for item in records),
            "providers": providers,
            "sources": sources,
            "provider_count": len(providers),
            "source_count": len(sources),
            "lineage_completeness": "COMPLETE_LINEAGE",
            "semantic_statuses": tuple(sorted(
                {item.value.semantic_status for item in records}, key=lambda item: item.value
            )),
            "presence_statuses": tuple(sorted(
                {item.value.presence_status for item in records}, key=lambda item: item.value
            )),
            "lineage_references": lineages,
        }
        return EvidenceSupportRecord(
            support_record_id=deterministic_id("evidence-support", payload), **payload
        )

    @staticmethod
    def _quality_profile(
        support: EvidenceSupportRecord, records: tuple[CanonicalObservation, ...]
    ) -> EvidenceQualityProfile:
        dimensions = qualitative_dimensions(records)
        payload = {
            "support_record_id": support.support_record_id,
            "semantic_field_id": support.semantic_field_id,
            **dimensions,
            "qualitative_attributes": tuple(sorted(set(dimensions.values()))),
        }
        return EvidenceQualityProfile(
            profile_id=deterministic_id("evidence-quality-profile", payload), **payload
        )

    @staticmethod
    def _conflict_record(
        support: EvidenceSupportRecord,
        records: tuple[CanonicalObservation, ...],
        lineages: tuple[EvidenceLineageReference, ...],
    ) -> EvidenceConflictRecord:
        candidates = tuple(
            item for item in records if item.value.presence_status is PresenceStatus.PRESENT
        )
        candidate_ids = {item.observation_id for item in candidates}
        conflict_lineages = tuple(
            item for item in lineages if item.observation_id in candidate_ids
        )
        providers = tuple(sorted({item.provenance.provider for item in candidates}))
        sources = tuple(sorted({
            f"{item.provenance.provider}::{item.provenance.source_tool}" for item in candidates
        }))
        payload = {
            "support_record_id": support.support_record_id,
            "semantic_field_id": support.semantic_field_id,
            "subject": support.subject,
            "observation_kind": support.observation_kind,
            "dimension": support.dimension,
            "candidate_observation_ids": tuple(item.observation_id for item in candidates),
            "candidate_values": {
                item.observation_id: item.value for item in candidates
            },
            "providers": providers,
            "sources": sources,
            "conflict_status": "CONFLICT_PRESENT",
            "lineage_references": conflict_lineages,
        }
        return EvidenceConflictRecord(
            conflict_record_id=deterministic_id("evidence-conflict", payload), **payload
        )

    @staticmethod
    def _diagnostic(
        code: str,
        supports: Iterable[EvidenceSupportRecord],
        conflicts: Iterable[EvidenceConflictRecord],
        message: str,
    ) -> EvidenceDiagnostic:
        support_records = tuple(supports)
        conflict_records = tuple(conflicts)
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_support_record_ids": tuple(sorted({
                item.support_record_id for item in support_records
            })),
            "related_conflict_record_ids": tuple(sorted({
                item.conflict_record_id for item in conflict_records
            })),
            "related_observation_ids": tuple(sorted({
                observation_id
                for item in support_records
                for observation_id in item.supporting_observation_ids
            })),
            "message": message,
        }
        return EvidenceDiagnostic(
            diagnostic_id=deterministic_id("evidence-diagnostic", payload), **payload
        )

    def _diagnostics(
        self,
        supports: tuple[EvidenceSupportRecord, ...],
        profiles: tuple[EvidenceQualityProfile, ...],
        conflicts: tuple[EvidenceConflictRecord, ...],
    ) -> tuple[EvidenceDiagnostic, ...]:
        result: list[EvidenceDiagnostic] = []
        profile_by_support = {item.support_record_id: item for item in profiles}
        if not supports:
            result.append(self._diagnostic(
                "NO_CANONICAL_OBSERVATIONS",
                (),
                (),
                "The supplied bundles contain no canonical observations to evaluate.",
            ))
        categories = (
            (
                "MULTI_PROVIDER_SUPPORT_PRESENT",
                lambda item: item.source_diversity == "MULTI_PROVIDER_SUPPORT",
                "At least one semantic field has independent support from multiple providers.",
            ),
            (
                "SINGLE_PROVIDER_SUPPORT_PRESENT",
                lambda item: item.source_diversity == "SINGLE_PROVIDER",
                "At least one semantic field has evidence from only one provider.",
            ),
            (
                "UNKNOWN_OBSERVATION_TIME_PRESENT",
                lambda item: item.observation_recency == "UNKNOWN_OBSERVATION_TIME",
                "At least one evidence field has no known observation timestamp.",
            ),
            (
                "UNKNOWN_PERIOD_PRESENT",
                lambda item: item.period_status == "UNKNOWN_PERIOD",
                "At least one evidence field has an unknown observation period.",
            ),
            (
                "NON_PRESENT_EVIDENCE_NOT_NEGATIVE",
                lambda item: item.completeness != "ALL_VALUES_PRESENT",
                "Non-present evidence is recorded as absence or unknown and is not negative evidence.",
            ),
        )
        for code, predicate, message in categories:
            selected = tuple(
                support
                for support in supports
                if predicate(profile_by_support[support.support_record_id])
            )
            if selected:
                result.append(self._diagnostic(code, selected, (), message))
        if conflicts:
            conflict_support_ids = {item.support_record_id for item in conflicts}
            result.append(self._diagnostic(
                "CONFLICTS_DESCRIBED_NOT_RESOLVED",
                (item for item in supports if item.support_record_id in conflict_support_ids),
                conflicts,
                "Conflicting values are described as candidates; no winner or truth value is selected.",
            ))
        return tuple(sorted(result, key=lambda item: item.diagnostic_id))


__all__ = ("EvidenceEvaluationBuilderV0_1",)
