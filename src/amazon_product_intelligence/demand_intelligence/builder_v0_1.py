"""Evidence-preserving Demand Intelligence V0.1 builder."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    Channel,
    DirectionalQueryExecutionRecord,
    KeywordIdentity,
    KeywordMetricObservation,
    ObservationKind,
    PresenceStatus,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    QueryExecutionOutcome,
    RelationshipDirection,
    Severity,
    canonical_json,
    deterministic_id,
)

from .errors import (
    DemandIdentityCollisionError,
    DemandIntelligenceValidationError,
    DemandSubjectNotFoundError,
)
from .models import (
    DEMAND_INTELLIGENCE_RULESET_VERSION,
    DemandEvidenceCoverage,
    DemandIntelligenceDiagnostic,
    DemandIntelligenceRequest,
    DemandIntelligenceSnapshotV0_1,
    DemandLineageReference,
    DemandQualityIssueReference,
    DemandSourceRecordType,
    KeywordMetricCandidate,
    KeywordMetricEvidenceSet,
    MetricCandidateState,
    OutOfScopeEvidenceReference,
    QueryExecutionEvidenceItem,
    RelatedProductEvidence,
    RelationshipEvidenceGroup,
    RelationshipEvidenceItem,
    bundle_fingerprint,
    observation_revision_content,
)


@dataclass(slots=True)
class _Emission:
    record: Any
    bundle_fingerprints: set[str]


@dataclass(slots=True)
class _IndexedRecord:
    record: Any
    bundle_fingerprints: set[str]


class _RecordIndex:
    """Collision-safe canonical record index for deterministic organization."""

    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(bundle_fingerprint(item) for item in bundles))
        self.observation_revisions: dict[str, str] = {}
        self.observations: dict[str, dict[str, _Emission]] = defaultdict(dict)
        self.query_executions: dict[str, _IndexedRecord] = {}
        self.runs: dict[str, _IndexedRecord] = {}
        self.issues: dict[str, _IndexedRecord] = {}
        self.raw_fingerprints: dict[str, set[str]] = defaultdict(set)
        self.keyword_identities: dict[str, KeywordIdentity] = {}
        self.product_identities: dict[str, ProductIdentity] = {}
        self._generic: dict[tuple[str, str], str] = {}
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
            raise DemandIdentityCollisionError(f"{kind} identity collision: {identity}")
        if current is None:
            index[identity] = _IndexedRecord(record=record, bundle_fingerprints={fingerprint})
        else:
            current.bundle_fingerprints.add(fingerprint)

    @staticmethod
    def _merge_identity(index: dict[str, Any], identity: str, value: Any, kind: str) -> None:
        current = index.get(identity)
        if current is not None and current != value:
            raise DemandIdentityCollisionError(f"{kind} identity collision: {identity}")
        index.setdefault(identity, value)

    def _index_keyword(self, keyword: KeywordIdentity | None) -> None:
        if keyword is not None:
            self._merge_identity(
                self.keyword_identities, keyword.keyword_id, keyword, "keyword"
            )

    def _index_product(self, product: ProductIdentity | None) -> None:
        if product is not None:
            self._merge_identity(
                self.product_identities, product.product_id, product, "product"
            )

    def _consume_bundle(self, bundle: CanonicalEvidenceBundle, fingerprint: str) -> None:
        for raw_id in bundle.raw_evidence_references:
            self.raw_fingerprints[raw_id].add(fingerprint)
        for run in bundle.transformation_runs:
            self._merge_record(
                self.runs,
                run.transformation_run_id,
                run,
                fingerprint,
                "transformation run",
            )
        for observation in bundle.observations:
            revision = canonical_json(observation_revision_content(observation))
            current_revision = self.observation_revisions.get(observation.observation_id)
            if current_revision is not None and current_revision != revision:
                raise DemandIdentityCollisionError(
                    f"observation identity collision: {observation.observation_id}"
                )
            self.observation_revisions[observation.observation_id] = revision
            run_id = observation.provenance.transformation.transformation_run_id
            current = self.observations[observation.observation_id].get(run_id)
            if current is not None and canonical_json(current.record) != canonical_json(observation):
                raise DemandIdentityCollisionError(
                    f"observation emission collision: {observation.observation_id}"
                )
            if current is None:
                self.observations[observation.observation_id][run_id] = _Emission(
                    record=observation, bundle_fingerprints={fingerprint}
                )
            else:
                current.bundle_fingerprints.add(fingerprint)
            if isinstance(observation, KeywordMetricObservation):
                self._index_keyword(observation.keyword)
            elif isinstance(observation, ProductKeywordRelationshipObservation):
                self._index_keyword(observation.keyword)
                self._index_product(observation.product)
        for query in bundle.query_execution_records:
            self._merge_record(
                self.query_executions,
                query.query_execution_id,
                query,
                fingerprint,
                "query execution",
            )
            self._index_keyword(query.query_keyword)
            self._index_product(query.query_product)
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
                    raise DemandIdentityCollisionError(f"{kind} identity collision: {identity}")
                self._generic[key] = content

    def observation_representatives(self) -> tuple[CanonicalObservation, ...]:
        return tuple(
            min(emissions.values(), key=lambda item: canonical_json(item.record)).record
            for _, emissions in sorted(self.observations.items())
        )

    def query_representatives(self) -> tuple[DirectionalQueryExecutionRecord, ...]:
        return tuple(
            entry.record for _, entry in sorted(self.query_executions.items())
        )

    def observation_lineages(
        self,
        observation_id: str,
        source_record_type: DemandSourceRecordType,
    ) -> tuple[DemandLineageReference, ...]:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise DemandIntelligenceValidationError(f"orphan observation: {observation_id}")
        references: list[DemandLineageReference] = []
        for run_id, emission in sorted(emissions.items()):
            observation = emission.record
            references.append(
                self._lineage(
                    record=observation,
                    record_id=observation_id,
                    source_record_type=source_record_type,
                    semantic_observation_id=observation.semantic_observation_id,
                    observation_kind=observation.observation_kind,
                    run_id=run_id,
                    source_fingerprints=emission.bundle_fingerprints,
                )
            )
        return tuple(sorted(references, key=canonical_json))

    def query_lineages(self, query_execution_id: str) -> tuple[DemandLineageReference, ...]:
        entry = self.query_executions.get(query_execution_id)
        if entry is None:
            raise DemandIntelligenceValidationError(
                f"orphan query execution: {query_execution_id}"
            )
        record = entry.record
        return (
            self._lineage(
                record=record,
                record_id=query_execution_id,
                source_record_type=DemandSourceRecordType.DIRECTIONAL_QUERY_EXECUTION_RECORD,
                semantic_observation_id=None,
                observation_kind=None,
                run_id=record.provenance.transformation.transformation_run_id,
                source_fingerprints=entry.bundle_fingerprints,
            ),
        )

    def _lineage(
        self,
        *,
        record: Any,
        record_id: str,
        source_record_type: DemandSourceRecordType,
        semantic_observation_id: str | None,
        observation_kind: ObservationKind | None,
        run_id: str,
        source_fingerprints: set[str],
    ) -> DemandLineageReference:
        transformation = record.provenance.transformation
        run_entry = self.runs.get(run_id)
        if run_entry is None:
            raise DemandIntelligenceValidationError(f"orphan transformation run: {run_id}")
        run = run_entry.record
        raw_id = transformation.raw_evidence_reference
        if raw_id not in self.raw_fingerprints or raw_id not in run.input_raw_evidence_references:
            raise DemandIntelligenceValidationError(f"orphan raw evidence: {raw_id}")
        if (
            run.collection_run_id != transformation.collection_run_id
            or run.mapping_version != transformation.mapping_version
        ):
            raise DemandIntelligenceValidationError(f"mapping or collection mismatch for {record_id}")
        return DemandLineageReference(
            source_record_id=record_id,
            source_record_type=source_record_type,
            semantic_observation_id=semantic_observation_id,
            observation_kind=observation_kind,
            transformation_run_id=run_id,
            mapping_version=transformation.mapping_version,
            raw_evidence_id=raw_id,
            collection_run_id=transformation.collection_run_id,
            provider=record.provenance.provider,
            source_tool=record.provenance.source_tool,
            source_field=record.provenance.source_field,
            source_bundle_fingerprints=tuple(sorted(source_fingerprints)),
        )


class DemandIntelligenceBuilderV0_1:
    """Build a deterministic keyword evidence view without demand inference."""

    def build(self, request: DemandIntelligenceRequest) -> DemandIntelligenceSnapshotV0_1:
        """Validate, organize and return one auditable V0.1 snapshot."""

        if not isinstance(request, DemandIntelligenceRequest):
            raise DemandIntelligenceValidationError(
                "request must be DemandIntelligenceRequest"
            )
        snapshot = self._build_snapshot(request)
        return snapshot.validate_against_bundles(request.canonical_bundles)

    def _build_snapshot(
        self, request: DemandIntelligenceRequest
    ) -> DemandIntelligenceSnapshotV0_1:
        index = _RecordIndex(request.canonical_bundles)
        observations = index.observation_representatives()
        queries = index.query_representatives()
        target = request.target_keyword_identity
        diagnostics: list[DemandIntelligenceDiagnostic] = []

        metric_observations = tuple(
            item
            for item in observations
            if isinstance(item, KeywordMetricObservation) and item.keyword == target
        )
        relationship_observations = tuple(
            item
            for item in observations
            if isinstance(item, ProductKeywordRelationshipObservation) and item.keyword == target
        )
        target_relationship_ids = {item.observation_id for item in relationship_observations}
        target_relationship_ids_by_product: dict[str, set[str]] = defaultdict(set)
        for relationship in relationship_observations:
            target_relationship_ids_by_product[relationship.product.product_id].add(
                relationship.observation_id
            )
        query_records = tuple(
            item
            for item in queries
            if (
                item.direction is RelationshipDirection.KEYWORD_TO_PRODUCT
                and item.query_keyword == target
            )
            or (
                item.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
                and item.query_product is not None
                and (
                    bool(
                        set(item.related_relationship_observation_ids)
                        & target_relationship_ids
                    )
                    or item.query_product.product_id in target_relationship_ids_by_product
                )
            )
        )
        if not metric_observations and not relationship_observations and not query_records:
            raise DemandSubjectNotFoundError(
                f"target keyword has no exact canonical evidence: {target.keyword_id}"
            )

        metric_sets = self._metric_sets(metric_observations, index, diagnostics)
        relationship_groups, relationship_items = self._relationship_groups(
            relationship_observations, index
        )
        query_evidence = self._query_evidence(
            query_records,
            target_relationship_ids,
            target_relationship_ids_by_product,
            index,
            diagnostics,
        )
        related_products = self._related_products(relationship_items)

        included_observation_ids = {
            item.observation_id for item in metric_observations
        } | {item.observation_id for item in relationship_observations}
        included_query_ids = {item.query_execution_id for item in query_records}
        out_of_scope: list[OutOfScopeEvidenceReference] = []
        for observation in observations:
            if observation.observation_id in included_observation_ids:
                continue
            if isinstance(observation, KeywordMetricObservation):
                reason = "UNRELATED_KEYWORD_METRIC_EXCLUDED"
            elif isinstance(observation, ProductKeywordRelationshipObservation):
                reason = "UNRELATED_KEYWORD_RELATIONSHIP_EXCLUDED"
            else:
                reason = f"{observation.observation_kind.value}_OUT_OF_DEMAND_SCOPE"
            out_of_scope.append(
                OutOfScopeEvidenceReference(
                    source_record_id=observation.observation_id,
                    source_record_type=DemandSourceRecordType.OUT_OF_SCOPE_OBSERVATION,
                    observation_kind=observation.observation_kind,
                    reason_code=reason,
                    lineage_references=index.observation_lineages(
                        observation.observation_id,
                        DemandSourceRecordType.OUT_OF_SCOPE_OBSERVATION,
                    ),
                )
            )
        for query in queries:
            if query.query_execution_id in included_query_ids:
                continue
            out_of_scope.append(
                OutOfScopeEvidenceReference(
                    source_record_id=query.query_execution_id,
                    source_record_type=DemandSourceRecordType.DIRECTIONAL_QUERY_EXECUTION_RECORD,
                    observation_kind=None,
                    reason_code="UNRELATED_DIRECTIONAL_QUERY_EXCLUDED",
                    lineage_references=index.query_lineages(query.query_execution_id),
                )
            )

        non_keyword_out_of_scope = tuple(
            item.source_record_id
            for item in out_of_scope
            if item.observation_kind
            in {ObservationKind.PRODUCT_FACT, ObservationKind.METRIC, ObservationKind.REVIEW}
        )
        if non_keyword_out_of_scope:
            diagnostics.append(
                self._diagnostic(
                    "NON_KEYWORD_OBSERVATIONS_OUT_OF_SCOPE",
                    Severity.INFO,
                    non_keyword_out_of_scope,
                    "Product facts, product metrics, and reviews are inventoried but not used for demand inference.",
                )
            )
        unrelated = tuple(
            item.source_record_id
            for item in out_of_scope
            if item.reason_code.startswith("UNRELATED_")
        )
        if unrelated:
            diagnostics.append(
                self._diagnostic(
                    "UNRELATED_CANONICAL_EVIDENCE_EXCLUDED",
                    Severity.INFO,
                    unrelated,
                    "Canonical records that do not exactly match the target keyword are explicitly excluded.",
                )
            )

        diagnostics = sorted(
            {item.diagnostic_id: item for item in diagnostics}.values(),
            key=lambda item: item.diagnostic_id,
        )
        quality_refs = self._quality_references(index)
        lineage: dict[str, DemandLineageReference] = {}
        for collection in (
            tuple(candidate for item in metric_sets for candidate in item.candidates),
            tuple(relationship_items),
            tuple(query_evidence),
            tuple(out_of_scope),
        ):
            for item in collection:
                for reference in item.lineage_references:
                    lineage[canonical_json(reference)] = reference

        coverage = self._coverage(
            index=index,
            observations=observations,
            queries=queries,
            metric_observations=metric_observations,
            relationship_observations=relationship_observations,
            query_records=query_records,
            out_of_scope=out_of_scope,
            diagnostics=diagnostics,
        )
        payload = {
            "ruleset_version": DEMAND_INTELLIGENCE_RULESET_VERSION,
            "target_keyword_identity": target,
            "source_bundle_fingerprints": index.bundle_fingerprints,
            "keyword_metric_evidence_sets": tuple(
                sorted(metric_sets, key=lambda item: item.metric_evidence_set_id)
            ),
            "relationship_evidence_groups": tuple(
                sorted(relationship_groups, key=lambda item: item.relationship_group_id)
            ),
            "query_execution_evidence": tuple(
                sorted(query_evidence, key=lambda item: item.query_execution_id)
            ),
            "related_product_evidence_inventory": tuple(
                sorted(related_products, key=lambda item: item.inventory_item_id)
            ),
            "evidence_coverage": coverage,
            "quality_issue_references": quality_refs,
            "out_of_scope_evidence_references": tuple(
                sorted(
                    out_of_scope,
                    key=lambda item: (item.source_record_type.value, item.source_record_id),
                )
            ),
            "diagnostics": tuple(diagnostics),
            "lineage_index": tuple(lineage[key] for key in sorted(lineage)),
        }
        return DemandIntelligenceSnapshotV0_1(
            snapshot_id=deterministic_id("demand-snapshot", payload), **payload
        )

    @staticmethod
    def _diagnostic(
        code: str,
        severity: Severity,
        related_record_ids: Iterable[str],
        message: str,
    ) -> DemandIntelligenceDiagnostic:
        payload = {
            "code": code,
            "severity": severity,
            "related_record_ids": tuple(sorted(set(related_record_ids))),
            "message": message,
        }
        return DemandIntelligenceDiagnostic(
            diagnostic_id=deterministic_id("demand-diagnostic", payload), **payload
        )

    def _metric_sets(
        self,
        observations: tuple[KeywordMetricObservation, ...],
        index: _RecordIndex,
        diagnostics: list[DemandIntelligenceDiagnostic],
    ) -> tuple[KeywordMetricEvidenceSet, ...]:
        groups: dict[str, list[KeywordMetricObservation]] = defaultdict(list)
        for observation in observations:
            key = canonical_json(
                {
                    "keyword_identity": observation.keyword,
                    "marketplace": observation.keyword.marketplace,
                    "locale": observation.keyword.locale,
                    "metric": observation.metric,
                    "metric_semantic": observation.metric_semantic,
                    "unit": observation.value.unit,
                    "period_type": observation.time.period_type,
                    "period_start": observation.time.period_start,
                    "period_end": observation.time.period_end,
                    "observed_at_status": observation.time.observed_at_status,
                    "timezone": observation.time.timezone,
                    "scope": observation.scope,
                    "evidence_type": observation.evidence_type,
                    "provider_semantic": observation.provenance.provider_semantic,
                }
            )
            groups[key].append(observation)
        result: list[KeywordMetricEvidenceSet] = []
        for key in sorted(groups):
            group = groups[key]
            candidates = tuple(
                sorted(
                    (self._metric_candidate(item, index) for item in group),
                    key=lambda item: item.observation_id,
                )
            )
            present_values = {
                canonical_json(
                    {
                        "raw_value": item.value.raw_value,
                        "normalized_value": item.value.normalized_value,
                        "unit": item.value.unit,
                        "range": item.range,
                    }
                )
                for item in candidates
                if item.value.presence_status is PresenceStatus.PRESENT
            }
            state = (
                MetricCandidateState.NO_PRESENT_CANDIDATE
                if not present_values
                else MetricCandidateState.ONE_DISTINCT_PRESENT_VALUE
                if len(present_values) == 1
                else MetricCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES
            )
            first = group[0]
            payload = {
                "keyword_identity": first.keyword,
                "metric": first.metric,
                "metric_semantic": first.metric_semantic,
                "unit": first.value.unit,
                "period_type": first.time.period_type,
                "period_start": first.time.period_start,
                "period_end": first.time.period_end,
                "observed_at_status": first.time.observed_at_status,
                "timezone": first.time.timezone,
                "scope": first.scope,
                "evidence_type": first.evidence_type,
                "provider_semantic": first.provenance.provider_semantic,
                "candidate_state": state,
                "distinct_present_value_count": len(present_values),
                "candidate_count": len(candidates),
                "presence_counts": dict(
                    sorted(Counter(item.value.presence_status.value for item in candidates).items())
                ),
                "candidates": candidates,
            }
            evidence_set = KeywordMetricEvidenceSet(
                metric_evidence_set_id=deterministic_id("demand-metric-set", payload),
                **payload,
            )
            result.append(evidence_set)
            if state is MetricCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES:
                diagnostics.append(
                    self._diagnostic(
                        "MULTIPLE_DISTINCT_KEYWORD_METRIC_VALUES",
                        Severity.WARNING,
                        (item.observation_id for item in group),
                        "Distinct present metric values remain unresolved candidates.",
                    )
                )
            elif state is MetricCandidateState.NO_PRESENT_CANDIDATE:
                diagnostics.append(
                    self._diagnostic(
                        "NON_PRESENT_ONLY_KEYWORD_METRIC_CANDIDATES",
                        Severity.INFO,
                        (item.observation_id for item in group),
                        "The metric evidence set contains only non-present candidates.",
                    )
                )
        return tuple(result)

    @staticmethod
    def _metric_candidate(
        observation: KeywordMetricObservation, index: _RecordIndex
    ) -> KeywordMetricCandidate:
        return KeywordMetricCandidate(
            observation_id=observation.observation_id,
            semantic_observation_id=observation.semantic_observation_id,
            keyword_identity=observation.keyword,
            metric=observation.metric,
            metric_semantic=observation.metric_semantic,
            estimate_method_status=observation.estimate_method_status,
            range=observation.range,
            evidence_type=observation.evidence_type,
            value=observation.value,
            scope=observation.scope,
            time=observation.time,
            provider_semantic=observation.provenance.provider_semantic,
            result_status=observation.result_status,
            provider=observation.provenance.provider,
            source_tool=observation.provenance.source_tool,
            lineage_references=index.observation_lineages(
                observation.observation_id,
                DemandSourceRecordType.KEYWORD_METRIC_OBSERVATION,
            ),
        )

    def _relationship_groups(
        self,
        observations: tuple[ProductKeywordRelationshipObservation, ...],
        index: _RecordIndex,
    ) -> tuple[tuple[RelationshipEvidenceGroup, ...], tuple[RelationshipEvidenceItem, ...]]:
        groups: dict[tuple[RelationshipDirection, Channel], list[RelationshipEvidenceItem]] = defaultdict(list)
        for observation in observations:
            item = RelationshipEvidenceItem(
                observation_id=observation.observation_id,
                semantic_observation_id=observation.semantic_observation_id,
                relationship_id=observation.relationship_id,
                product_identity=observation.product,
                keyword_identity=observation.keyword,
                direction=observation.direction,
                relationship_type=observation.relationship_type,
                channel=observation.channel,
                query_result_status=observation.query_result_status,
                rank=observation.rank,
                traffic=observation.traffic,
                evidence_type=observation.evidence_type,
                value=observation.value,
                scope=observation.scope,
                time=observation.time,
                result_status=observation.result_status,
                provider_semantic=observation.provenance.provider_semantic,
                provider=observation.provenance.provider,
                source_tool=observation.provenance.source_tool,
                lineage_references=index.observation_lineages(
                    observation.observation_id,
                    DemandSourceRecordType.PRODUCT_KEYWORD_RELATIONSHIP_OBSERVATION,
                ),
            )
            groups[(item.direction, item.channel)].append(item)
        result: list[RelationshipEvidenceGroup] = []
        for direction, channel in sorted(groups, key=lambda item: (item[0].value, item[1].value)):
            records = tuple(sorted(groups[(direction, channel)], key=lambda item: item.observation_id))
            payload = {
                "keyword_identity": records[0].keyword_identity,
                "direction": direction,
                "channel": channel,
                "records": records,
            }
            result.append(
                RelationshipEvidenceGroup(
                    relationship_group_id=deterministic_id(
                        "demand-relationship-group", payload
                    ),
                    **payload,
                )
            )
        items = tuple(
            sorted((item for records in groups.values() for item in records), key=lambda item: item.observation_id)
        )
        return tuple(result), items

    def _query_evidence(
        self,
        records: tuple[DirectionalQueryExecutionRecord, ...],
        target_relationship_ids: set[str],
        target_relationship_ids_by_product: dict[str, set[str]],
        index: _RecordIndex,
        diagnostics: list[DemandIntelligenceDiagnostic],
    ) -> tuple[QueryExecutionEvidenceItem, ...]:
        result: list[QueryExecutionEvidenceItem] = []
        for record in records:
            target_related = tuple(
                sorted(set(record.related_relationship_observation_ids) & target_relationship_ids)
            )
            if (
                record.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
                and not target_related
                and record.query_product is not None
            ):
                target_related = tuple(
                    sorted(
                        target_relationship_ids_by_product.get(
                            record.query_product.product_id, set()
                        )
                    )
                )
            item = QueryExecutionEvidenceItem(
                query_execution_id=record.query_execution_id,
                query_keyword=record.query_keyword,
                query_product=record.query_product,
                direction=record.direction,
                outcome=record.outcome,
                related_relationship_observation_ids=record.related_relationship_observation_ids,
                target_related_relationship_observation_ids=target_related,
                provenance=record.provenance,
                quality_issue_ids=record.quality_issue_ids,
                lineage_references=index.query_lineages(record.query_execution_id),
            )
            result.append(item)
            if record.outcome is QueryExecutionOutcome.EXPLICIT_EMPTY:
                diagnostics.append(
                    self._diagnostic(
                        "EXPLICIT_EMPTY_QUERY_RETAINED",
                        Severity.INFO,
                        (record.query_execution_id,),
                        "An explicit empty query outcome is retained and is not interpreted as zero demand or no related products.",
                    )
                )
            elif record.outcome in {
                QueryExecutionOutcome.OUTCOME_UNKNOWN,
                QueryExecutionOutcome.EXECUTION_FAILED,
            }:
                diagnostics.append(
                    self._diagnostic(
                        f"QUERY_{record.outcome.value}_RETAINED",
                        Severity.WARNING,
                        (record.query_execution_id,),
                        "The non-result query outcome is retained without demand inference.",
                    )
                )
        forward_empty = [
            item
            for item in result
            if item.direction is RelationshipDirection.KEYWORD_TO_PRODUCT
            and item.outcome is QueryExecutionOutcome.EXPLICIT_EMPTY
        ]
        reverse_results = [
            item
            for item in result
            if item.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
            and item.outcome is QueryExecutionOutcome.RESULTS_RETURNED
        ]
        reverse_empty = [
            item
            for item in result
            if item.direction is RelationshipDirection.PRODUCT_TO_KEYWORD
            and item.outcome is QueryExecutionOutcome.EXPLICIT_EMPTY
        ]
        forward_results = [
            item
            for item in result
            if item.direction is RelationshipDirection.KEYWORD_TO_PRODUCT
            and item.outcome is QueryExecutionOutcome.RESULTS_RETURNED
        ]
        asymmetric = forward_empty + reverse_results if forward_empty and reverse_results else []
        if reverse_empty and forward_results:
            asymmetric += reverse_empty + forward_results
        if asymmetric:
            diagnostics.append(
                self._diagnostic(
                    "DIRECTIONAL_QUERY_ASYMMETRY",
                    Severity.INFO,
                    (item.query_execution_id for item in asymmetric),
                    "Forward and reverse query evidence differs; directions remain separate and no demand conclusion is inferred.",
                )
            )
        return tuple(sorted(result, key=lambda item: item.query_execution_id))

    @staticmethod
    def _related_products(
        relationships: tuple[RelationshipEvidenceItem, ...]
    ) -> tuple[RelatedProductEvidence, ...]:
        groups: dict[str, list[RelationshipEvidenceItem]] = defaultdict(list)
        for relationship in relationships:
            groups[relationship.product_identity.product_id].append(relationship)
        result: list[RelatedProductEvidence] = []
        for product_id in sorted(groups):
            records = groups[product_id]
            lineages = {
                canonical_json(reference): reference
                for record in records
                for reference in record.lineage_references
            }
            payload = {
                "product_identity": records[0].product_identity,
                "relationship_observation_ids": tuple(
                    sorted(item.observation_id for item in records)
                ),
                "directions": tuple(
                    sorted({item.direction for item in records}, key=lambda item: item.value)
                ),
                "channels": tuple(
                    sorted({item.channel for item in records}, key=lambda item: item.value)
                ),
                "providers": tuple(sorted({item.provider for item in records})),
                "lineage_references": tuple(lineages[key] for key in sorted(lineages)),
            }
            result.append(
                RelatedProductEvidence(
                    inventory_item_id=deterministic_id(
                        "related-product-evidence", payload
                    ),
                    **payload,
                )
            )
        return tuple(result)

    @staticmethod
    def _quality_references(index: _RecordIndex) -> tuple[DemandQualityIssueReference, ...]:
        return tuple(
            DemandQualityIssueReference(
                issue_id=entry.record.issue_id,
                issue_code=entry.record.issue_code,
                severity=entry.record.severity,
                source_references=entry.record.source_references,
                collection_run_id=entry.record.collection_run_id,
                transformation_run_id=entry.record.transformation_run_id,
                mapping_version=entry.record.mapping_version,
                source_bundle_fingerprints=tuple(sorted(entry.bundle_fingerprints)),
            )
            for _, entry in sorted(index.issues.items())
        )

    @staticmethod
    def _coverage(
        *,
        index: _RecordIndex,
        observations: tuple[CanonicalObservation, ...],
        queries: tuple[DirectionalQueryExecutionRecord, ...],
        metric_observations: tuple[KeywordMetricObservation, ...],
        relationship_observations: tuple[ProductKeywordRelationshipObservation, ...],
        query_records: tuple[DirectionalQueryExecutionRecord, ...],
        out_of_scope: list[OutOfScopeEvidenceReference],
        diagnostics: list[DemandIntelligenceDiagnostic],
    ) -> DemandEvidenceCoverage:
        all_metrics = [item for item in observations if isinstance(item, KeywordMetricObservation)]
        all_relationships = [
            item for item in observations if isinstance(item, ProductKeywordRelationshipObservation)
        ]
        provider_records = Counter(item.provenance.provider for item in observations)
        provider_records.update(item.provenance.provider for item in queries)
        return DemandEvidenceCoverage(
            source_bundle_count=len(index.bundle_fingerprints),
            raw_evidence_reference_count=len(index.raw_fingerprints),
            transformation_run_count=len(index.runs),
            keyword_metric_observation_count=len(all_metrics),
            relationship_observation_count=len(all_relationships),
            query_execution_record_count=len(queries),
            included_keyword_metric_count=len(metric_observations),
            included_relationship_count=len(relationship_observations),
            included_query_execution_count=len(query_records),
            out_of_scope_record_count=len(out_of_scope),
            relationship_direction_counts=dict(
                sorted(Counter(item.direction.value for item in all_relationships).items())
            ),
            query_direction_counts=dict(
                sorted(Counter(item.direction.value for item in queries).items())
            ),
            channel_counts=dict(
                sorted(Counter(item.channel.value for item in all_relationships).items())
            ),
            query_outcome_counts=dict(
                sorted(Counter(item.outcome.value for item in queries).items())
            ),
            providers=tuple(sorted(provider_records)),
            provider_record_counts=dict(sorted(provider_records.items())),
            quality_issue_count=len(index.issues),
            diagnostic_count=len(diagnostics),
        )


__all__ = ("DemandIntelligenceBuilderV0_1",)
