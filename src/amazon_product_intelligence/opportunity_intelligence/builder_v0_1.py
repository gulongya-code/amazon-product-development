"""Evidence-preserving Opportunity Intelligence V0.1 builder."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    ContractValidationError,
    DirectionalQueryExecutionRecord,
    EvidenceType,
    KeywordIdentity,
    KeywordMetricObservation,
    MetricObservation,
    ObservedAtStatus,
    PeriodType,
    PresenceStatus,
    ProductFactObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    QueryExecutionOutcome,
    ReviewObservation,
    SemanticStatus,
    Severity,
    SubjectType,
    canonical_json,
    deterministic_id,
    product_id,
)

from .errors import OpportunityIdentityCollisionError, OpportunityValidationError
from .models import (
    OPPORTUNITY_INTELLIGENCE_RULESET_VERSION,
    MissingEvidenceInventory,
    OpportunityCoverageSummary,
    OpportunityDiagnostic,
    OpportunityIntelligenceRequest,
    OpportunityIntelligenceSnapshotV0_1,
    OpportunityLineageReference,
    OpportunityMissingEvidence,
    OpportunityMissingEvidenceKind,
    OpportunityQualityIssueReference,
    OpportunityRiskEvidence,
    OpportunityRiskType,
    OpportunitySignalClassification,
    OpportunitySignalEvidence,
    OpportunitySignalType,
    OpportunitySourceRecordType,
    bundle_fingerprint,
    observation_revision_content,
)


_VARIATION_DIMENSIONS = {"child_product_relationship", "parent_product_relationship"}
_PRICE_METRICS = {"price", "sale_price", "list_price"}


@dataclass(slots=True)
class _Emission:
    record: CanonicalObservation | DirectionalQueryExecutionRecord
    bundle_fingerprints: set[str]


@dataclass(slots=True)
class _IndexedRecord:
    record: Any
    bundle_fingerprints: set[str]


class _RecordIndex:
    """Collision-safe canonical record index with replayable lineage."""

    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(bundle_fingerprint(item) for item in bundles))
        self.observation_revisions: dict[str, str] = {}
        self.observations: dict[str, dict[str, _Emission]] = defaultdict(dict)
        self.queries: dict[str, dict[str, _Emission]] = defaultdict(dict)
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
        index: dict[str, _IndexedRecord], identity: str, record: Any, fingerprint: str, kind: str
    ) -> None:
        current = index.get(identity)
        if current is not None and canonical_json(current.record) != canonical_json(record):
            raise OpportunityIdentityCollisionError(f"{kind} identity collision: {identity}")
        if current is None:
            index[identity] = _IndexedRecord(record=record, bundle_fingerprints={fingerprint})
        else:
            current.bundle_fingerprints.add(fingerprint)

    def _record_namespace(self, identity: str, namespace: str) -> None:
        current = self._record_namespaces.get(identity)
        if current is not None and current != namespace:
            raise OpportunityIdentityCollisionError(
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
                raise OpportunityIdentityCollisionError(
                    f"observation identity collision: {observation.observation_id}"
                )
            self.observation_revisions[observation.observation_id] = revision
            run_id = observation.provenance.transformation.transformation_run_id
            current = self.observations[observation.observation_id].get(run_id)
            if current is not None and canonical_json(current.record) != canonical_json(observation):
                raise OpportunityIdentityCollisionError(
                    f"observation emission collision: {observation.observation_id}"
                )
            if current is None:
                self.observations[observation.observation_id][run_id] = _Emission(
                    record=observation, bundle_fingerprints={fingerprint}
                )
            else:
                current.bundle_fingerprints.add(fingerprint)
        for query in bundle.query_execution_records:
            self._record_namespace(query.query_execution_id, "query execution")
            run_id = query.provenance.transformation.transformation_run_id
            current = self.queries[query.query_execution_id].get(run_id)
            if current is not None and canonical_json(current.record) != canonical_json(query):
                raise OpportunityIdentityCollisionError(
                    f"query execution identity collision: {query.query_execution_id}"
                )
            if current is None:
                self.queries[query.query_execution_id][run_id] = _Emission(
                    record=query, bundle_fingerprints={fingerprint}
                )
            else:
                current.bundle_fingerprints.add(fingerprint)
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
                    raise OpportunityIdentityCollisionError(f"{kind} identity collision: {identity}")
                self._generic[key] = content

    @staticmethod
    def _representatives(
        index: dict[str, dict[str, _Emission]],
    ) -> tuple[CanonicalObservation | DirectionalQueryExecutionRecord, ...]:
        return tuple(
            min(emissions.values(), key=lambda item: canonical_json(item.record)).record
            for _, emissions in sorted(index.items())
        )

    def observation_representatives(self) -> tuple[CanonicalObservation, ...]:
        return tuple(self._representatives(self.observations))  # type: ignore[return-value]

    def query_representatives(self) -> tuple[DirectionalQueryExecutionRecord, ...]:
        return tuple(self._representatives(self.queries))  # type: ignore[return-value]

    def lineages(
        self, source_record_id: str, source_record_type: OpportunitySourceRecordType
    ) -> tuple[OpportunityLineageReference, ...]:
        collection = (
            self.queries
            if source_record_type is OpportunitySourceRecordType.QUERY_EXECUTION
            else self.observations
        )
        emissions = collection.get(source_record_id)
        if not emissions:
            raise OpportunityValidationError(f"orphan canonical source: {source_record_id}")
        references: list[OpportunityLineageReference] = []
        for run_id, emission in sorted(emissions.items()):
            record = emission.record
            transformation = record.provenance.transformation
            run_entry = self.runs.get(run_id)
            if run_entry is None:
                raise OpportunityValidationError(f"orphan transformation run: {run_id}")
            run = run_entry.record
            raw_id = transformation.raw_evidence_reference
            if raw_id not in self.raw_fingerprints or raw_id not in run.input_raw_evidence_references:
                raise OpportunityValidationError(f"orphan raw evidence: {raw_id}")
            if (
                run.collection_run_id != transformation.collection_run_id
                or run.mapping_version != transformation.mapping_version
            ):
                raise OpportunityValidationError(
                    f"mapping or collection mismatch for {source_record_id}"
                )
            if isinstance(record, DirectionalQueryExecutionRecord):
                semantic_id = None
                observation_kind = None
            else:
                semantic_id = record.semantic_observation_id
                observation_kind = record.observation_kind
            references.append(OpportunityLineageReference(
                source_record_id=source_record_id,
                source_record_type=source_record_type,
                semantic_observation_id=semantic_id,
                observation_kind=observation_kind,
                transformation_run_id=run_id,
                mapping_version=transformation.mapping_version,
                raw_evidence_id=raw_id,
                collection_run_id=transformation.collection_run_id,
                provider=record.provenance.provider,
                source_tool=record.provenance.source_tool,
                source_field=record.provenance.source_field,
                source_bundle_fingerprints=tuple(sorted(emission.bundle_fingerprints)),
            ))
        return tuple(sorted(references, key=canonical_json))


class OpportunityIntelligenceBuilderV0_1:
    """Build opportunity evidence availability without a business conclusion."""

    def build(
        self, request: OpportunityIntelligenceRequest
    ) -> OpportunityIntelligenceSnapshotV0_1:
        if not isinstance(request, OpportunityIntelligenceRequest):
            raise OpportunityValidationError("request must be OpportunityIntelligenceRequest")
        snapshot = self._build_snapshot(request)
        return snapshot.validate_against_bundles(request.canonical_bundles)

    def _build_snapshot(
        self, request: OpportunityIntelligenceRequest
    ) -> OpportunityIntelligenceSnapshotV0_1:
        index = _RecordIndex(request.canonical_bundles)
        observations = index.observation_representatives()
        queries = index.query_representatives()
        observed = tuple(
            self._observed_signal(record, index)
            for record in (*observations, *queries)
        )
        observed = tuple(sorted(observed, key=lambda item: item.signal_id))
        derived = self._derived_signals(observed)
        missing = self._missing_evidence(
            observations, queries, index.bundle_fingerprints
        )
        risk = self._risk_evidence(observations, queries, observed, missing)
        diagnostics = self._diagnostics(observed, missing, risk)
        quality_refs = tuple(
            OpportunityQualityIssueReference(
                issue_id=entry.record.issue_id,
                issue_code=entry.record.issue_code,
                severity=entry.record.severity,
                source_references=entry.record.source_references,
                source_bundle_fingerprints=tuple(sorted(entry.bundle_fingerprints)),
            )
            for _, entry in sorted(index.issues.items())
        )
        lineages: dict[str, OpportunityLineageReference] = {}
        for collection in (observed, derived, risk):
            for item in collection:
                for lineage in item.lineage_references:
                    lineages[canonical_json(lineage)] = lineage
        coverage = self._coverage(
            index=index,
            observations=observations,
            queries=queries,
            observed=observed,
            derived=derived,
            missing=missing,
            risk=risk,
            diagnostics=diagnostics,
        )
        payload = {
            "ruleset_version": OPPORTUNITY_INTELLIGENCE_RULESET_VERSION,
            "source_bundle_fingerprints": index.bundle_fingerprints,
            "observed_signals": observed,
            "derived_signals": derived,
            "missing_evidence": missing,
            "risk_evidence": risk,
            "coverage": coverage,
            "quality_issue_references": quality_refs,
            "diagnostics": diagnostics,
            "lineage_index": tuple(lineages[key] for key in sorted(lineages)),
        }
        return OpportunityIntelligenceSnapshotV0_1(
            snapshot_id=deterministic_id("opportunity-snapshot", payload), **payload
        )

    @staticmethod
    def _source_type(
        record: CanonicalObservation | DirectionalQueryExecutionRecord,
    ) -> OpportunitySourceRecordType:
        if isinstance(record, ProductFactObservation):
            return OpportunitySourceRecordType.PRODUCT_FACT
        if isinstance(record, MetricObservation):
            return OpportunitySourceRecordType.PRODUCT_METRIC
        if isinstance(record, KeywordMetricObservation):
            return OpportunitySourceRecordType.KEYWORD_METRIC
        if isinstance(record, ProductKeywordRelationshipObservation):
            return OpportunitySourceRecordType.KEYWORD_PRODUCT_RELATIONSHIP
        if isinstance(record, ReviewObservation):
            return OpportunitySourceRecordType.REVIEW
        if isinstance(record, DirectionalQueryExecutionRecord):
            return OpportunitySourceRecordType.QUERY_EXECUTION
        raise OpportunityValidationError(f"unsupported canonical source type: {type(record).__name__}")

    @staticmethod
    def _identity_from_subject(observation: CanonicalObservation) -> ProductIdentity | None:
        subject = observation.subject
        if subject.subject_type is not SubjectType.PRODUCT:
            return None
        parts = subject.subject_id.split(":")
        if len(parts) != 3 or parts[0] != "product" or parts[1] != subject.marketplace:
            raise OpportunityValidationError(
                f"invalid product subject identity: {subject.subject_id}"
            )
        expected = product_id(subject.marketplace, parts[2])
        if expected != subject.subject_id:
            raise OpportunityValidationError(
                f"product subject identity mismatch: {subject.subject_id}"
            )
        return ProductIdentity(
            product_id=expected,
            marketplace=subject.marketplace,
            asin=parts[2],
            parent_asin=None,
            identity_status="CONFIRMED",
        )

    @staticmethod
    def _identity_from_asin(marketplace: str, asin: Any) -> ProductIdentity:
        if type(asin) is not str:
            raise OpportunityValidationError("variation endpoint must be an ASIN string")
        normalized = asin.strip().upper()
        try:
            return ProductIdentity(
                product_id=product_id(marketplace, normalized),
                marketplace=marketplace,
                asin=normalized,
                parent_asin=None,
                identity_status="CONFIRMED",
            )
        except ContractValidationError as exc:
            raise OpportunityValidationError(
                f"invalid variation endpoint identity: {asin}"
            ) from exc

    def _confirmed_variation(
        self, observation: CanonicalObservation,
    ) -> tuple[ProductIdentity, ProductIdentity] | None:
        if (
            not isinstance(observation, ProductFactObservation)
            or observation.dimension not in _VARIATION_DIMENSIONS
            or observation.value.presence_status is not PresenceStatus.PRESENT
            or observation.value.semantic_status is not SemanticStatus.CONFIRMED
        ):
            return None
        subject = self._identity_from_subject(observation)
        if subject is None:
            raise OpportunityValidationError(
                f"variation relationship has non-product subject: {observation.observation_id}"
            )
        related = self._identity_from_asin(
            observation.subject.marketplace, observation.value.normalized_value
        )
        if observation.dimension == "child_product_relationship":
            parent, child = subject, related
        else:
            parent, child = related, subject
        if parent.product_id == child.product_id:
            raise OpportunityValidationError("variation relationship cannot be a self-loop")
        return parent, child

    def _record_identities(
        self, record: CanonicalObservation | DirectionalQueryExecutionRecord,
    ) -> tuple[tuple[ProductIdentity, ...], tuple[KeywordIdentity, ...]]:
        products: dict[str, ProductIdentity] = {}
        keywords: dict[str, KeywordIdentity] = {}
        if isinstance(record, ProductKeywordRelationshipObservation):
            products[canonical_json(record.product)] = record.product
            keywords[canonical_json(record.keyword)] = record.keyword
        elif isinstance(record, ReviewObservation):
            products[canonical_json(record.product)] = record.product
        elif isinstance(record, KeywordMetricObservation):
            keywords[canonical_json(record.keyword)] = record.keyword
        elif isinstance(record, DirectionalQueryExecutionRecord):
            if record.query_product is not None:
                products[canonical_json(record.query_product)] = record.query_product
            if record.query_keyword is not None:
                keywords[canonical_json(record.query_keyword)] = record.query_keyword
        else:
            product = self._identity_from_subject(record)
            if product is not None:
                products[canonical_json(product)] = product
        variation = self._confirmed_variation(record)
        if variation is not None:
            for product in variation:
                products[canonical_json(product)] = product
        return (
            tuple(products[key] for key in sorted(products)),
            tuple(keywords[key] for key in sorted(keywords)),
        )

    def _signal_type(
        self, record: CanonicalObservation | DirectionalQueryExecutionRecord,
    ) -> OpportunitySignalType:
        if self._confirmed_variation(record) is not None:
            return OpportunitySignalType.VARIATION_RELATIONSHIP_OBSERVED
        if isinstance(record, ProductFactObservation):
            return OpportunitySignalType.PRODUCT_FACT_OBSERVED
        if isinstance(record, MetricObservation):
            return OpportunitySignalType.PRODUCT_METRIC_OBSERVED
        if isinstance(record, KeywordMetricObservation):
            return OpportunitySignalType.KEYWORD_METRIC_OBSERVED
        if isinstance(record, ProductKeywordRelationshipObservation):
            return OpportunitySignalType.KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED
        if isinstance(record, ReviewObservation):
            return OpportunitySignalType.REVIEW_OBSERVED
        if isinstance(record, DirectionalQueryExecutionRecord):
            return OpportunitySignalType.QUERY_EXECUTION_OBSERVED
        raise OpportunityValidationError(f"unsupported canonical source type: {type(record).__name__}")

    @staticmethod
    def _attributes(
        record: CanonicalObservation | DirectionalQueryExecutionRecord,
        variation: tuple[ProductIdentity, ProductIdentity] | None,
    ) -> dict[str, Any]:
        if isinstance(record, DirectionalQueryExecutionRecord):
            return {
                "direction": record.direction.value,
                "outcome": record.outcome.value,
                "related_relationship_observation_count": len(
                    record.related_relationship_observation_ids
                ),
                "quality_issue_ids": record.quality_issue_ids,
            }
        attributes: dict[str, Any] = {
            "evidence_type": record.evidence_type.value,
            "result_status": record.result_status.value,
            "presence_status": record.value.presence_status.value,
            "semantic_status": record.value.semantic_status.value,
            "scope": record.scope.to_dict(),
            "time": record.time.to_dict(),
        }
        if isinstance(record, ProductFactObservation):
            attributes.update({
                "dimension": record.dimension,
                "fact_group": record.fact_group.value,
                "provider_semantic": record.provider_semantic,
            })
            if variation is not None:
                attributes.update({
                    "variation_parent_product_id": variation[0].product_id,
                    "variation_child_product_id": variation[1].product_id,
                    "variation_source_dimension": record.dimension,
                })
        elif isinstance(record, MetricObservation):
            attributes.update({
                "metric": record.metric,
                "metric_semantic": record.metric_semantic,
                "measurement_type": record.measurement_type.value,
                "currency": record.currency,
                "rank_context": record.rank_context,
                "unit": record.value.unit.to_dict() if record.value.unit is not None else None,
            })
        elif isinstance(record, KeywordMetricObservation):
            attributes.update({
                "metric": record.metric,
                "metric_semantic": record.metric_semantic,
                "estimate_method_status": record.estimate_method_status.value,
                "range": record.range,
                "unit": record.value.unit.to_dict() if record.value.unit is not None else None,
            })
        elif isinstance(record, ProductKeywordRelationshipObservation):
            attributes.update({
                "direction": record.direction.value,
                "relationship_type": record.relationship_type.value,
                "channel": record.channel.value,
                "query_result_status": record.query_result_status.value,
                "rank": record.rank,
                "traffic": record.traffic.to_dict() if record.traffic is not None else None,
            })
        elif isinstance(record, ReviewObservation):
            attributes.update({
                "review_observation_id": record.review_observation_id,
                "rating_presence_status": record.rating.presence_status.value,
                "review_date_presence_status": record.review_date.presence_status.value,
                "helpful_votes_presence_status": record.helpful_votes.presence_status.value,
                "variant_presence_status": record.variant.presence_status.value,
            })
        return attributes

    def _observed_signal(
        self,
        record: CanonicalObservation | DirectionalQueryExecutionRecord,
        index: _RecordIndex,
    ) -> OpportunitySignalEvidence:
        source_type = self._source_type(record)
        source_id = (
            record.query_execution_id
            if isinstance(record, DirectionalQueryExecutionRecord)
            else record.observation_id
        )
        lineages = index.lineages(source_id, source_type)
        products, keywords = self._record_identities(record)
        variation = self._confirmed_variation(record)
        payload = {
            "classification": OpportunitySignalClassification.OBSERVED_SIGNAL,
            "signal_type": self._signal_type(record),
            "product_identities": products,
            "keyword_identities": keywords,
            "source_record_ids": (source_id,),
            "supporting_signal_ids": (),
            "providers": tuple(sorted({item.provider for item in lineages})),
            "source_tools": tuple(sorted({item.source_tool for item in lineages})),
            "evidence_attributes": self._attributes(record, variation),
            "lineage_references": lineages,
        }
        return OpportunitySignalEvidence(
            signal_id=deterministic_id("opportunity-signal", payload), **payload
        )

    @staticmethod
    def _derived_signal(
        signal_type: OpportunitySignalType,
        supporting: Iterable[OpportunitySignalEvidence],
        *,
        products: Iterable[ProductIdentity] = (),
        keywords: Iterable[KeywordIdentity] = (),
        attributes: dict[str, Any],
    ) -> OpportunitySignalEvidence:
        records = tuple(sorted(supporting, key=lambda item: item.signal_id))
        if not records:
            raise OpportunityValidationError("derived signal requires observed support")
        lineages = {
            canonical_json(lineage): lineage
            for item in records
            for lineage in item.lineage_references
        }
        product_map = {canonical_json(item): item for item in products}
        keyword_map = {canonical_json(item): item for item in keywords}
        payload = {
            "classification": OpportunitySignalClassification.DERIVED_SIGNAL,
            "signal_type": signal_type,
            "product_identities": tuple(product_map[key] for key in sorted(product_map)),
            "keyword_identities": tuple(keyword_map[key] for key in sorted(keyword_map)),
            "source_record_ids": tuple(sorted({
                source_id for item in records for source_id in item.source_record_ids
            })),
            "supporting_signal_ids": tuple(item.signal_id for item in records),
            "providers": tuple(sorted({
                lineage.provider for lineage in lineages.values()
            })),
            "source_tools": tuple(sorted({
                lineage.source_tool for lineage in lineages.values()
            })),
            "evidence_attributes": attributes,
            "lineage_references": tuple(lineages[key] for key in sorted(lineages)),
        }
        return OpportunitySignalEvidence(
            signal_id=deterministic_id("opportunity-signal", payload), **payload
        )

    def _derived_signals(
        self, observed: tuple[OpportunitySignalEvidence, ...]
    ) -> tuple[OpportunitySignalEvidence, ...]:
        result: list[OpportunitySignalEvidence] = []
        product_groups: dict[str, list[OpportunitySignalEvidence]] = defaultdict(list)
        product_values: dict[str, ProductIdentity] = {}
        keyword_groups: dict[str, list[OpportunitySignalEvidence]] = defaultdict(list)
        keyword_values: dict[str, KeywordIdentity] = {}
        relationship_groups: dict[tuple[str, str], list[OpportunitySignalEvidence]] = defaultdict(list)
        variation_groups: dict[tuple[str, str], list[OpportunitySignalEvidence]] = defaultdict(list)
        for signal in observed:
            for product in signal.product_identities:
                key = canonical_json(product)
                product_values[key] = product
                product_groups[key].append(signal)
            for keyword in signal.keyword_identities:
                key = canonical_json(keyword)
                keyword_values[key] = keyword
                keyword_groups[key].append(signal)
            if signal.signal_type is OpportunitySignalType.KEYWORD_PRODUCT_RELATIONSHIP_OBSERVED:
                relationship_groups[(
                    signal.evidence_attributes["direction"],
                    signal.evidence_attributes["channel"],
                )].append(signal)
            if signal.signal_type is OpportunitySignalType.VARIATION_RELATIONSHIP_OBSERVED:
                variation_groups[(
                    signal.evidence_attributes["variation_parent_product_id"],
                    signal.evidence_attributes["variation_child_product_id"],
                )].append(signal)
        for key in sorted(product_groups):
            records = product_groups[key]
            result.append(self._derived_signal(
                OpportunitySignalType.PRODUCT_EVIDENCE_PRESENT,
                records,
                products=(product_values[key],),
                attributes={"supporting_observed_signal_count": len(records)},
            ))
        for key in sorted(keyword_groups):
            records = keyword_groups[key]
            result.append(self._derived_signal(
                OpportunitySignalType.KEYWORD_EVIDENCE_PRESENT,
                records,
                keywords=(keyword_values[key],),
                attributes={"supporting_observed_signal_count": len(records)},
            ))
        for (direction, channel), records in sorted(relationship_groups.items()):
            result.append(self._derived_signal(
                OpportunitySignalType.RELATIONSHIP_EVIDENCE_PRESENT,
                records,
                products=(item for record in records for item in record.product_identities),
                keywords=(item for record in records for item in record.keyword_identities),
                attributes={
                    "direction": direction,
                    "channel": channel,
                    "supporting_observed_signal_count": len(records),
                },
            ))
        for (parent_id, child_id), records in sorted(variation_groups.items()):
            product_values_for_group = {
                product.product_id: product
                for record in records
                for product in record.product_identities
            }
            result.append(self._derived_signal(
                OpportunitySignalType.CONFIRMED_VARIATION_EVIDENCE_PRESENT,
                records,
                products=(product_values_for_group[parent_id], product_values_for_group[child_id]),
                attributes={
                    "variation_parent_product_id": parent_id,
                    "variation_child_product_id": child_id,
                    "supporting_observed_signal_count": len(records),
                },
            ))
        return tuple(sorted(result, key=lambda item: item.signal_id))

    def _missing_evidence(
        self,
        observations: tuple[CanonicalObservation, ...],
        queries: tuple[DirectionalQueryExecutionRecord, ...],
        fingerprints: tuple[str, ...],
    ) -> MissingEvidenceInventory:
        confirmed_variations = tuple(
            item for item in observations if self._confirmed_variation(item) is not None
        )
        relationships = tuple(
            item for item in observations if isinstance(item, ProductKeywordRelationshipObservation)
        )
        has_keyword_identity = any(
            isinstance(item, (KeywordMetricObservation, ProductKeywordRelationshipObservation))
            for item in observations
        ) or any(item.query_keyword is not None for item in queries)
        present = {
            OpportunityMissingEvidenceKind.PRODUCT_FACT_EVIDENCE:
                any(isinstance(item, ProductFactObservation) for item in observations),
            OpportunityMissingEvidenceKind.PRODUCT_METRIC_EVIDENCE:
                any(isinstance(item, MetricObservation) for item in observations),
            OpportunityMissingEvidenceKind.KEYWORD_EVIDENCE: has_keyword_identity,
            OpportunityMissingEvidenceKind.KEYWORD_PRODUCT_RELATIONSHIP_EVIDENCE:
                bool(relationships),
            OpportunityMissingEvidenceKind.QUERY_EXECUTION_EVIDENCE: bool(queries),
            OpportunityMissingEvidenceKind.COMPETITION_RELATED_EVIDENCE:
                bool(relationships or confirmed_variations),
            OpportunityMissingEvidenceKind.VARIATION_EVIDENCE: bool(confirmed_variations),
            OpportunityMissingEvidenceKind.REVIEW_EVIDENCE:
                any(isinstance(item, ReviewObservation) for item in observations),
            OpportunityMissingEvidenceKind.PRICE_EVIDENCE:
                any(
                    isinstance(item, MetricObservation)
                    and item.metric.casefold() in _PRICE_METRICS
                    for item in observations
                ),
        }
        basis = {
            OpportunityMissingEvidenceKind.PRODUCT_FACT_EVIDENCE:
                "No canonical ProductFactObservation was supplied.",
            OpportunityMissingEvidenceKind.PRODUCT_METRIC_EVIDENCE:
                "No canonical MetricObservation was supplied.",
            OpportunityMissingEvidenceKind.KEYWORD_EVIDENCE:
                "No canonical keyword identity appeared in metric, relationship, or query evidence.",
            OpportunityMissingEvidenceKind.KEYWORD_PRODUCT_RELATIONSHIP_EVIDENCE:
                "No canonical ProductKeywordRelationshipObservation was supplied.",
            OpportunityMissingEvidenceKind.QUERY_EXECUTION_EVIDENCE:
                "No canonical DirectionalQueryExecutionRecord was supplied.",
            OpportunityMissingEvidenceKind.COMPETITION_RELATED_EVIDENCE:
                "No canonical keyword-product or confirmed variation relationship evidence was supplied.",
            OpportunityMissingEvidenceKind.VARIATION_EVIDENCE:
                "No present confirmed canonical variation relationship was supplied.",
            OpportunityMissingEvidenceKind.REVIEW_EVIDENCE:
                "No canonical ReviewObservation was supplied.",
            OpportunityMissingEvidenceKind.PRICE_EVIDENCE:
                "No canonical price, sale_price, or list_price MetricObservation was supplied.",
        }
        items: list[OpportunityMissingEvidence] = []
        for kind in sorted(OpportunityMissingEvidenceKind, key=lambda item: item.value):
            if present[kind]:
                continue
            payload = {
                "classification": OpportunitySignalClassification.MISSING_EVIDENCE_SIGNAL,
                "evidence_kind": kind,
                "basis": basis[kind],
                "source_bundle_fingerprints": fingerprints,
            }
            items.append(OpportunityMissingEvidence(
                missing_evidence_id=deterministic_id("opportunity-missing-evidence", payload),
                **payload,
            ))
        return MissingEvidenceInventory(
            evaluated_evidence_kinds=tuple(OpportunityMissingEvidenceKind),
            items=tuple(items),
            interpretation="MISSING_EVIDENCE_IS_NOT_NEGATIVE_EVIDENCE",
        )

    @staticmethod
    def _risk(
        risk_type: OpportunityRiskType,
        source_record_ids: Iterable[str],
        missing_evidence_ids: Iterable[str],
        observed_by_source: dict[str, OpportunitySignalEvidence],
        message: str,
    ) -> OpportunityRiskEvidence:
        source_ids = tuple(sorted(set(source_record_ids)))
        missing_ids = tuple(sorted(set(missing_evidence_ids)))
        lineages = {
            canonical_json(lineage): lineage
            for source_id in source_ids
            for lineage in observed_by_source[source_id].lineage_references
        }
        payload = {
            "classification": OpportunitySignalClassification.RISK_EVIDENCE,
            "risk_type": risk_type,
            "source_record_ids": source_ids,
            "missing_evidence_ids": missing_ids,
            "providers": tuple(sorted({item.provider for item in lineages.values()})),
            "source_tools": tuple(sorted({item.source_tool for item in lineages.values()})),
            "message": message,
            "lineage_references": tuple(lineages[key] for key in sorted(lineages)),
        }
        return OpportunityRiskEvidence(
            risk_evidence_id=deterministic_id("opportunity-risk-evidence", payload), **payload
        )

    def _risk_evidence(
        self,
        observations: tuple[CanonicalObservation, ...],
        queries: tuple[DirectionalQueryExecutionRecord, ...],
        observed: tuple[OpportunitySignalEvidence, ...],
        missing: MissingEvidenceInventory,
    ) -> tuple[OpportunityRiskEvidence, ...]:
        observed_by_source = {
            item.source_record_ids[0]: item for item in observed
        }
        result: list[OpportunityRiskEvidence] = []
        unknown_period = {
            item.observation_id for item in observations
            if item.time.period_type is PeriodType.UNKNOWN
        }
        if unknown_period:
            result.append(self._risk(
                OpportunityRiskType.UNKNOWN_PERIOD, unknown_period, (), observed_by_source,
                "These canonical observations do not declare a known evidence period.",
            ))
        unknown_time = {
            item.observation_id for item in observations
            if item.time.observed_at_status is ObservedAtStatus.UNKNOWN
        }
        if unknown_time:
            result.append(self._risk(
                OpportunityRiskType.UNKNOWN_OBSERVATION_TIME, unknown_time, (), observed_by_source,
                "These canonical observations do not declare a known observation timestamp.",
            ))
        method_undeclared = {
            item.observation_id for item in observations
            if item.evidence_type is EvidenceType.PROVIDER_ESTIMATE
            and item.provenance.provider_method is None
        }
        if method_undeclared:
            result.append(self._risk(
                OpportunityRiskType.PROVIDER_METHOD_UNDECLARED,
                method_undeclared, (), observed_by_source,
                "These provider estimates do not carry a declared provider method.",
            ))
        limited_queries = {
            item.query_execution_id for item in queries
            if item.outcome is not QueryExecutionOutcome.RESULTS_RETURNED
        }
        if limited_queries:
            result.append(self._risk(
                OpportunityRiskType.QUERY_OUTCOME_LIMITATION,
                limited_queries, (), observed_by_source,
                "These canonical query executions did not return a populated result set.",
            ))
        all_source_ids = tuple(observed_by_source)
        providers = {
            lineage.provider for item in observed for lineage in item.lineage_references
        }
        if len(providers) == 1 and all_source_ids:
            result.append(self._risk(
                OpportunityRiskType.SINGLE_PROVIDER_EVIDENCE,
                all_source_ids, (), observed_by_source,
                "All supplied canonical signal records originate from one provider.",
            ))
        review_missing = next((
            item for item in missing.items
            if item.evidence_kind is OpportunityMissingEvidenceKind.REVIEW_EVIDENCE
        ), None)
        if review_missing is not None:
            result.append(self._risk(
                OpportunityRiskType.REVIEW_EVIDENCE_ABSENT,
                (), (review_missing.missing_evidence_id,), observed_by_source,
                "No canonical review sample is available in the supplied evidence.",
            ))
        return tuple(sorted(result, key=lambda item: item.risk_evidence_id))

    @staticmethod
    def _diagnostic(
        code: str,
        related_source_record_ids: Iterable[str],
        related_evidence_ids: Iterable[str],
        message: str,
    ) -> OpportunityDiagnostic:
        payload = {
            "code": code,
            "severity": Severity.INFO,
            "related_source_record_ids": tuple(sorted(set(related_source_record_ids))),
            "related_evidence_ids": tuple(sorted(set(related_evidence_ids))),
            "message": message,
        }
        return OpportunityDiagnostic(
            diagnostic_id=deterministic_id("opportunity-diagnostic", payload), **payload
        )

    def _diagnostics(
        self,
        observed: tuple[OpportunitySignalEvidence, ...],
        missing: MissingEvidenceInventory,
        risk: tuple[OpportunityRiskEvidence, ...],
    ) -> tuple[OpportunityDiagnostic, ...]:
        result: list[OpportunityDiagnostic] = []
        if not observed:
            result.append(self._diagnostic(
                "NO_CANONICAL_SIGNAL_RECORDS", (), (),
                "The supplied bundles contain no canonical observations or query executions.",
            ))
        if missing.items:
            result.append(self._diagnostic(
                "MISSING_EVIDENCE_NOT_NEGATIVE",
                (), (item.missing_evidence_id for item in missing.items),
                "Missing evidence records absence only and is not negative evidence.",
            ))
        if risk:
            result.append(self._diagnostic(
                "RISK_EVIDENCE_IS_LIMITATION_ONLY",
                (source_id for item in risk for source_id in item.source_record_ids),
                (item.risk_evidence_id for item in risk),
                "Risk evidence records limitations only and does not express a business conclusion.",
            ))
        return tuple(sorted(result, key=lambda item: item.diagnostic_id))

    def _coverage(
        self,
        *,
        index: _RecordIndex,
        observations: tuple[CanonicalObservation, ...],
        queries: tuple[DirectionalQueryExecutionRecord, ...],
        observed: tuple[OpportunitySignalEvidence, ...],
        derived: tuple[OpportunitySignalEvidence, ...],
        missing: MissingEvidenceInventory,
        risk: tuple[OpportunityRiskEvidence, ...],
        diagnostics: tuple[OpportunityDiagnostic, ...],
    ) -> OpportunityCoverageSummary:
        product_keys = {
            canonical_json(product)
            for item in observed
            for product in item.product_identities
        }
        keyword_keys = {
            canonical_json(keyword)
            for item in observed
            for keyword in item.keyword_identities
        }
        confirmed_variations = sum(
            self._confirmed_variation(item) is not None for item in observations
        )
        relationships = sum(
            isinstance(item, ProductKeywordRelationshipObservation) for item in observations
        )
        all_signals = observed + derived
        providers = {
            item.provenance.provider for item in (*observations, *queries)
        }
        source_tools = {
            item.provenance.source_tool for item in (*observations, *queries)
        }
        return OpportunityCoverageSummary(
            source_bundle_count=len(index.bundle_fingerprints),
            raw_evidence_reference_count=len(index.raw_fingerprints),
            transformation_run_count=len(index.runs),
            observed_signal_count=len(observed),
            derived_signal_count=len(derived),
            missing_evidence_count=len(missing.items),
            risk_evidence_count=len(risk),
            product_identity_count=len(product_keys),
            keyword_identity_count=len(keyword_keys),
            product_fact_observation_count=sum(
                isinstance(item, ProductFactObservation) for item in observations
            ),
            product_metric_observation_count=sum(
                isinstance(item, MetricObservation) for item in observations
            ),
            keyword_metric_observation_count=sum(
                isinstance(item, KeywordMetricObservation) for item in observations
            ),
            relationship_observation_count=relationships,
            query_execution_record_count=len(queries),
            review_observation_count=sum(
                isinstance(item, ReviewObservation) for item in observations
            ),
            confirmed_variation_observation_count=confirmed_variations,
            competition_related_evidence_count=relationships + confirmed_variations,
            provider_count=len(providers),
            source_tool_count=len(source_tools),
            signal_type_counts=dict(sorted(Counter(
                item.signal_type.value for item in all_signals
            ).items())),
            query_outcome_counts=dict(sorted(Counter(
                item.outcome.value for item in queries
            ).items())),
            quality_issue_count=len(index.issues),
            diagnostic_count=len(diagnostics),
        )


__all__ = ("OpportunityIntelligenceBuilderV0_1",)
