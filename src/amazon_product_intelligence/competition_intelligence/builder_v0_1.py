"""Evidence-preserving Competition Intelligence V0.1 builder."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    KeywordIdentity,
    PresenceStatus,
    ProductFactObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    ReviewObservation,
    SemanticStatus,
    Severity,
    SubjectType,
    canonical_json,
    deterministic_id,
    product_id,
)

from .errors import CompetitionIdentityCollisionError, CompetitionIntelligenceValidationError
from .models import (
    COMPETITION_INTELLIGENCE_RULESET_VERSION,
    CompetitionCoverageSummary,
    CompetitionDiagnostic,
    CompetitionEvidenceGraph,
    CompetitionEvidenceGraphEdge,
    CompetitionEvidenceGraphNode,
    CompetitionIntelligenceRequest,
    CompetitionIntelligenceSnapshotV0_1,
    CompetitionKeywordEvidence,
    CompetitionLineageReference,
    CompetitionProductEvidence,
    CompetitionQualityIssueReference,
    CompetitionRelationshipEvidence,
    CompetitionSourceRecordType,
    CompetitionVariationEvidence,
    EvidenceClassification,
    EvidenceGraphEdgeType,
    bundle_fingerprint,
    observation_revision_content,
)


_VARIATION_DIMENSIONS = {"child_product_relationship", "parent_product_relationship"}


@dataclass(slots=True)
class _Emission:
    observation: CanonicalObservation
    bundle_fingerprints: set[str]


@dataclass(slots=True)
class _IndexedRecord:
    record: Any
    bundle_fingerprints: set[str]


class _RecordIndex:
    """Collision-safe index of canonical records and their source bundles."""

    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(bundle_fingerprint(item) for item in bundles))
        self.observation_revisions: dict[str, str] = {}
        self.observations: dict[str, dict[str, _Emission]] = defaultdict(dict)
        self.runs: dict[str, _IndexedRecord] = {}
        self.issues: dict[str, _IndexedRecord] = {}
        self.raw_fingerprints: dict[str, set[str]] = defaultdict(set)
        self.product_identities: dict[str, ProductIdentity] = {}
        self.keyword_identities: dict[str, KeywordIdentity] = {}
        self._generic: dict[tuple[str, str], str] = {}
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
            raise CompetitionIdentityCollisionError(f"{kind} identity collision: {identity}")
        if current is None:
            index[identity] = _IndexedRecord(record=record, bundle_fingerprints={fingerprint})
        else:
            current.bundle_fingerprints.add(fingerprint)

    @staticmethod
    def _merge_identity(index: dict[str, Any], identity: str, value: Any, kind: str) -> None:
        current = index.get(identity)
        if current is not None and current != value:
            raise CompetitionIdentityCollisionError(f"{kind} identity collision: {identity}")
        index.setdefault(identity, value)

    def add_product(self, product: ProductIdentity) -> None:
        self._merge_identity(self.product_identities, product.product_id, product, "product")

    def add_keyword(self, keyword: KeywordIdentity) -> None:
        self._merge_identity(self.keyword_identities, keyword.keyword_id, keyword, "keyword")

    def _consume_bundle(self, bundle: CanonicalEvidenceBundle, fingerprint: str) -> None:
        for raw_id in bundle.raw_evidence_references:
            self.raw_fingerprints[raw_id].add(fingerprint)
        for run in bundle.transformation_runs:
            self._merge_record(
                self.runs, run.transformation_run_id, run, fingerprint, "transformation run"
            )
        for observation in bundle.observations:
            revision = canonical_json(observation_revision_content(observation))
            prior = self.observation_revisions.get(observation.observation_id)
            if prior is not None and prior != revision:
                raise CompetitionIdentityCollisionError(
                    f"observation identity collision: {observation.observation_id}"
                )
            self.observation_revisions[observation.observation_id] = revision
            run_id = observation.provenance.transformation.transformation_run_id
            current = self.observations[observation.observation_id].get(run_id)
            if current is not None and canonical_json(current.observation) != canonical_json(observation):
                raise CompetitionIdentityCollisionError(
                    f"observation emission collision: {observation.observation_id}"
                )
            if current is None:
                self.observations[observation.observation_id][run_id] = _Emission(
                    observation=observation, bundle_fingerprints={fingerprint}
                )
            else:
                current.bundle_fingerprints.add(fingerprint)
            if isinstance(observation, ProductKeywordRelationshipObservation):
                self.add_product(observation.product)
                self.add_keyword(observation.keyword)
            elif isinstance(observation, ReviewObservation):
                self.add_product(observation.product)
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
                    raise CompetitionIdentityCollisionError(f"{kind} identity collision: {identity}")
                self._generic[key] = content

    def representatives(self) -> tuple[CanonicalObservation, ...]:
        return tuple(
            min(emissions.values(), key=lambda item: canonical_json(item.observation)).observation
            for _, emissions in sorted(self.observations.items())
        )

    def lineages(
        self, observation_id: str, source_record_type: CompetitionSourceRecordType
    ) -> tuple[CompetitionLineageReference, ...]:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise CompetitionIntelligenceValidationError(f"orphan observation: {observation_id}")
        references: list[CompetitionLineageReference] = []
        for run_id, emission in sorted(emissions.items()):
            observation = emission.observation
            transformation = observation.provenance.transformation
            run_entry = self.runs.get(run_id)
            if run_entry is None:
                raise CompetitionIntelligenceValidationError(f"orphan transformation run: {run_id}")
            run = run_entry.record
            raw_id = transformation.raw_evidence_reference
            if raw_id not in self.raw_fingerprints or raw_id not in run.input_raw_evidence_references:
                raise CompetitionIntelligenceValidationError(f"orphan raw evidence: {raw_id}")
            if run.collection_run_id != transformation.collection_run_id or run.mapping_version != transformation.mapping_version:
                raise CompetitionIntelligenceValidationError(
                    f"mapping or collection mismatch for {observation_id}"
                )
            references.append(
                CompetitionLineageReference(
                    observation_id=observation.observation_id,
                    semantic_observation_id=observation.semantic_observation_id,
                    observation_kind=observation.observation_kind,
                    source_record_type=source_record_type,
                    transformation_run_id=run_id,
                    mapping_version=transformation.mapping_version,
                    raw_evidence_id=raw_id,
                    collection_run_id=transformation.collection_run_id,
                    provider=observation.provenance.provider,
                    source_tool=observation.provenance.source_tool,
                    source_field=observation.provenance.source_field,
                    source_bundle_fingerprints=tuple(sorted(emission.bundle_fingerprints)),
                )
            )
        return tuple(sorted(references, key=canonical_json))


class CompetitionIntelligenceBuilderV0_1:
    """Build an evidence inventory without identifying or ranking competitors."""

    def build(
        self, request: CompetitionIntelligenceRequest
    ) -> CompetitionIntelligenceSnapshotV0_1:
        if not isinstance(request, CompetitionIntelligenceRequest):
            raise CompetitionIntelligenceValidationError(
                "request must be CompetitionIntelligenceRequest"
            )
        snapshot = self._build_snapshot(request)
        return snapshot.validate_against_bundles(request.canonical_bundles)

    def _build_snapshot(
        self, request: CompetitionIntelligenceRequest
    ) -> CompetitionIntelligenceSnapshotV0_1:
        index = _RecordIndex(request.canonical_bundles)
        observations = index.representatives()
        diagnostics: list[CompetitionDiagnostic] = []

        relationships = tuple(
            item for item in observations if isinstance(item, ProductKeywordRelationshipObservation)
        )
        direct_relationships = tuple(
            self._relationship(item, index) for item in relationships
        )

        variation_by_observation: dict[str, CompetitionVariationEvidence] = {}
        for observation in observations:
            if not isinstance(observation, ProductFactObservation) or observation.dimension not in _VARIATION_DIMENSIONS:
                continue
            variation = self._variation(observation, index, diagnostics)
            if variation is not None:
                variation_by_observation[observation.observation_id] = variation
                index.add_product(variation.parent_product_identity)
                index.add_product(variation.child_product_identity)
        variations = tuple(
            variation_by_observation[key] for key in sorted(variation_by_observation)
        )

        product_sources: dict[str, dict[str, CanonicalObservation]] = defaultdict(dict)
        for observation in observations:
            product = self._observation_product(observation)
            if product is not None:
                index.add_product(product)
                product_sources[product.product_id][observation.observation_id] = observation
        for variation in variations:
            observation = self._representative(index, variation.observation_id)
            product_sources[variation.parent_product_identity.product_id][observation.observation_id] = observation
            product_sources[variation.child_product_identity.product_id][observation.observation_id] = observation

        inventory = self._product_inventory(product_sources, index, relationships)
        keyword_evidence = self._keyword_evidence(direct_relationships)
        graph = self._graph(inventory, direct_relationships, variations, diagnostics)

        if not direct_relationships:
            diagnostics.append(self._diagnostic(
                "NO_KEYWORD_RELATIONSHIP_EVIDENCE", Severity.INFO, (),
                "No canonical keyword-product relationship observations were supplied.",
            ))
        if not variations:
            diagnostics.append(self._diagnostic(
                "NO_CONFIRMED_VARIATION_EVIDENCE", Severity.INFO, (),
                "No present confirmed variation relationship observations were supplied.",
            ))
        direct_ids = {item.observation_id for item in direct_relationships} | {
            item.observation_id for item in variations
        }
        non_relationship_ids = tuple(sorted(
            {
                observation_id
                for sources in product_sources.values()
                for observation_id in sources
                if observation_id not in direct_ids
            }
        ))
        if non_relationship_ids:
            diagnostics.append(self._diagnostic(
                "NON_RELATIONSHIP_PRODUCT_EVIDENCE_INVENTORIED", Severity.INFO,
                non_relationship_ids,
                "Product subjects are inventoried as observed endpoints without creating relationship edges.",
            ))

        diagnostics = sorted(
            {item.diagnostic_id: item for item in diagnostics}.values(),
            key=lambda item: item.diagnostic_id,
        )
        quality_refs = tuple(
            CompetitionQualityIssueReference(
                issue_id=entry.record.issue_id,
                issue_code=entry.record.issue_code,
                severity=entry.record.severity,
                source_references=entry.record.source_references,
                source_bundle_fingerprints=tuple(sorted(entry.bundle_fingerprints)),
            )
            for _, entry in sorted(index.issues.items())
        )
        lineages: dict[str, CompetitionLineageReference] = {}
        for collection in (
            direct_relationships,
            variations,
            inventory,
            keyword_evidence,
            graph.nodes,
            graph.edges,
        ):
            for item in collection:
                for lineage in item.lineage_references:
                    lineages[canonical_json(lineage)] = lineage

        coverage = self._coverage(
            index=index,
            observations=observations,
            inventory=inventory,
            keyword_evidence=keyword_evidence,
            relationships=direct_relationships,
            variations=variations,
            graph=graph,
            diagnostics=diagnostics,
        )
        payload = {
            "ruleset_version": COMPETITION_INTELLIGENCE_RULESET_VERSION,
            "source_bundle_fingerprints": index.bundle_fingerprints,
            "observed_product_inventory": tuple(sorted(
                inventory, key=lambda item: item.product_evidence_id
            )),
            "relationship_evidence_graph": graph,
            "variation_evidence": tuple(sorted(
                variations, key=lambda item: item.variation_evidence_id
            )),
            "keyword_relationship_evidence": direct_relationships,
            "keyword_evidence": tuple(sorted(
                keyword_evidence, key=lambda item: item.keyword_evidence_id
            )),
            "coverage": coverage,
            "quality_issue_references": quality_refs,
            "diagnostics": tuple(diagnostics),
            "lineage_index": tuple(lineages[key] for key in sorted(lineages)),
        }
        return CompetitionIntelligenceSnapshotV0_1(
            snapshot_id=deterministic_id("competition-snapshot", payload), **payload
        )

    @staticmethod
    def _representative(index: _RecordIndex, observation_id: str) -> CanonicalObservation:
        emissions = index.observations[observation_id]
        return min(emissions.values(), key=lambda item: canonical_json(item.observation)).observation

    @staticmethod
    def _source_type(observation: CanonicalObservation) -> CompetitionSourceRecordType:
        if isinstance(observation, ProductKeywordRelationshipObservation):
            return CompetitionSourceRecordType.KEYWORD_PRODUCT_RELATIONSHIP
        if (
            isinstance(observation, ProductFactObservation)
            and observation.dimension in _VARIATION_DIMENSIONS
            and observation.value.presence_status is PresenceStatus.PRESENT
            and observation.value.semantic_status is SemanticStatus.CONFIRMED
        ):
            return CompetitionSourceRecordType.VARIATION_RELATIONSHIP
        return CompetitionSourceRecordType.PRODUCT_OBSERVATION

    @staticmethod
    def _identity_from_subject(observation: CanonicalObservation) -> ProductIdentity | None:
        subject = observation.subject
        if subject.subject_type is not SubjectType.PRODUCT:
            return None
        parts = subject.subject_id.split(":")
        if len(parts) != 3 or parts[0] != "product" or parts[1] != subject.marketplace:
            raise CompetitionIntelligenceValidationError(
                f"invalid product subject identity: {subject.subject_id}"
            )
        expected = product_id(subject.marketplace, parts[2])
        if expected != subject.subject_id:
            raise CompetitionIntelligenceValidationError(
                f"product subject identity mismatch: {subject.subject_id}"
            )
        return ProductIdentity(
            product_id=expected,
            marketplace=subject.marketplace,
            asin=parts[2],
            parent_asin=None,
            identity_status="CONFIRMED",
        )

    @classmethod
    def _observation_product(cls, observation: CanonicalObservation) -> ProductIdentity | None:
        if isinstance(observation, ProductKeywordRelationshipObservation):
            return observation.product
        if isinstance(observation, ReviewObservation):
            return observation.product
        return cls._identity_from_subject(observation)

    @staticmethod
    def _identity_from_asin(marketplace: str, asin: Any) -> ProductIdentity:
        if type(asin) is not str:
            raise CompetitionIntelligenceValidationError("variation endpoint must be an ASIN string")
        identity = product_id(marketplace, asin)
        return ProductIdentity(
            product_id=identity,
            marketplace=marketplace,
            asin=asin.strip().upper(),
            parent_asin=None,
            identity_status="CONFIRMED",
        )

    def _variation(
        self,
        observation: ProductFactObservation,
        index: _RecordIndex,
        diagnostics: list[CompetitionDiagnostic],
    ) -> CompetitionVariationEvidence | None:
        if (
            observation.value.presence_status is not PresenceStatus.PRESENT
            or observation.value.semantic_status is not SemanticStatus.CONFIRMED
        ):
            diagnostics.append(self._diagnostic(
                "UNCONFIRMED_VARIATION_RELATIONSHIP_EXCLUDED", Severity.INFO,
                (observation.observation_id,),
                "Only present confirmed variation relationships enter the evidence graph.",
            ))
            return None
        subject = self._identity_from_subject(observation)
        if subject is None:
            raise CompetitionIntelligenceValidationError(
                f"variation relationship has non-product subject: {observation.observation_id}"
            )
        related = self._identity_from_asin(
            observation.subject.marketplace, observation.value.normalized_value
        )
        if observation.dimension == "child_product_relationship":
            parent, child = subject, related
        else:
            parent, child = related, subject
        payload = {
            "observation_id": observation.observation_id,
            "semantic_observation_id": observation.semantic_observation_id,
            "classification": EvidenceClassification.DIRECT_EVIDENCE,
            "parent_product_identity": parent,
            "child_product_identity": child,
            "source_dimension": observation.dimension,
            "evidence_type": observation.evidence_type,
            "value": observation.value,
            "scope": observation.scope,
            "time": observation.time,
            "result_status": observation.result_status,
            "provider_semantic": observation.provider_semantic,
            "provider": observation.provenance.provider,
            "source_tool": observation.provenance.source_tool,
            "lineage_references": index.lineages(
                observation.observation_id,
                CompetitionSourceRecordType.VARIATION_RELATIONSHIP,
            ),
        }
        return CompetitionVariationEvidence(
            variation_evidence_id=deterministic_id("competition-variation", payload), **payload
        )

    @staticmethod
    def _relationship(
        observation: ProductKeywordRelationshipObservation, index: _RecordIndex
    ) -> CompetitionRelationshipEvidence:
        return CompetitionRelationshipEvidence(
            observation_id=observation.observation_id,
            semantic_observation_id=observation.semantic_observation_id,
            classification=EvidenceClassification.DIRECT_EVIDENCE,
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
            lineage_references=index.lineages(
                observation.observation_id,
                CompetitionSourceRecordType.KEYWORD_PRODUCT_RELATIONSHIP,
            ),
        )

    def _product_inventory(
        self,
        product_sources: dict[str, dict[str, CanonicalObservation]],
        index: _RecordIndex,
        relationships: tuple[ProductKeywordRelationshipObservation, ...],
    ) -> tuple[CompetitionProductEvidence, ...]:
        result: list[CompetitionProductEvidence] = []
        for product_id_value in sorted(product_sources):
            product = index.product_identities[product_id_value]
            sources = product_sources[product_id_value]
            related = [item for item in relationships if item.product.product_id == product_id_value]
            lineages: dict[str, CompetitionLineageReference] = {}
            for observation_id, observation in sorted(sources.items()):
                source_type = self._source_type(observation)
                for lineage in index.lineages(observation_id, source_type):
                    lineages[canonical_json(lineage)] = lineage
            payload = {
                "classification": EvidenceClassification.DERIVED_EVIDENCE,
                "product_identity": product,
                "source_observation_ids": tuple(sorted(sources)),
                "keywords": tuple(sorted(
                    {item.keyword.keyword_id: item.keyword for item in related}.values(),
                    key=canonical_json,
                )),
                "directions": tuple(sorted({item.direction for item in related}, key=lambda item: item.value)),
                "channels": tuple(sorted({item.channel for item in related}, key=lambda item: item.value)),
                "providers": tuple(sorted({item.provenance.provider for item in sources.values()})),
                "source_tools": tuple(sorted({item.provenance.source_tool for item in sources.values()})),
                "lineage_references": tuple(lineages[key] for key in sorted(lineages)),
            }
            result.append(CompetitionProductEvidence(
                product_evidence_id=deterministic_id("competition-product-evidence", payload),
                **payload,
            ))
        return tuple(result)

    @staticmethod
    def _keyword_evidence(
        relationships: tuple[CompetitionRelationshipEvidence, ...]
    ) -> tuple[CompetitionKeywordEvidence, ...]:
        groups: dict[str, list[CompetitionRelationshipEvidence]] = defaultdict(list)
        for relationship in relationships:
            groups[canonical_json(relationship.keyword_identity)].append(relationship)
        result: list[CompetitionKeywordEvidence] = []
        for key in sorted(groups):
            records = groups[key]
            lineages = {
                canonical_json(lineage): lineage
                for record in records
                for lineage in record.lineage_references
            }
            payload = {
                "classification": EvidenceClassification.DERIVED_EVIDENCE,
                "keyword_identity": records[0].keyword_identity,
                "product_identities": tuple(sorted(
                    {item.product_identity.product_id: item.product_identity for item in records}.values(),
                    key=lambda item: item.product_id,
                )),
                "relationship_observation_ids": tuple(sorted(item.observation_id for item in records)),
                "directions": tuple(sorted({item.direction for item in records}, key=lambda item: item.value)),
                "channels": tuple(sorted({item.channel for item in records}, key=lambda item: item.value)),
                "providers": tuple(sorted({item.provider for item in records})),
                "lineage_references": tuple(lineages[item] for item in sorted(lineages)),
            }
            result.append(CompetitionKeywordEvidence(
                keyword_evidence_id=deterministic_id("competition-keyword-evidence", payload),
                **payload,
            ))
        return tuple(result)

    def _graph(
        self,
        inventory: tuple[CompetitionProductEvidence, ...],
        relationships: tuple[CompetitionRelationshipEvidence, ...],
        variations: tuple[CompetitionVariationEvidence, ...],
        diagnostics: list[CompetitionDiagnostic],
    ) -> CompetitionEvidenceGraph:
        nodes: list[CompetitionEvidenceGraphNode] = []
        for item in inventory:
            payload = {
                "classification": EvidenceClassification.DERIVED_EVIDENCE,
                "product_identity": item.product_identity,
                "source_observation_ids": item.source_observation_ids,
                "lineage_references": item.lineage_references,
            }
            nodes.append(CompetitionEvidenceGraphNode(
                graph_node_id=deterministic_id("competition-graph-node", payload), **payload
            ))
        edges: list[CompetitionEvidenceGraphEdge] = []
        for relationship in relationships:
            payload = {
                "classification": EvidenceClassification.DERIVED_EVIDENCE,
                "edge_type": EvidenceGraphEdgeType.KEYWORD_OBSERVED_RELATIONSHIP,
                "endpoint_product_identities": (relationship.product_identity,),
                "keyword_identity": relationship.keyword_identity,
                "variation_parent_product_identity": None,
                "variation_child_product_identity": None,
                "source_observation_ids": (relationship.observation_id,),
                "providers": (relationship.provider,),
                "lineage_references": relationship.lineage_references,
            }
            edges.append(CompetitionEvidenceGraphEdge(
                graph_edge_id=deterministic_id("competition-graph-edge", payload), **payload
            ))
        grouped: dict[tuple[str, str], list[CompetitionVariationEvidence]] = defaultdict(list)
        for variation in variations:
            grouped[(
                variation.parent_product_identity.product_id,
                variation.child_product_identity.product_id,
            )].append(variation)
        for key in sorted(grouped):
            records = grouped[key]
            lineages = {
                canonical_json(lineage): lineage
                for record in records
                for lineage in record.lineage_references
            }
            payload = {
                "classification": EvidenceClassification.DERIVED_EVIDENCE,
                "edge_type": EvidenceGraphEdgeType.VARIATION_RELATIONSHIP,
                "endpoint_product_identities": tuple(sorted(
                    (
                        records[0].parent_product_identity,
                        records[0].child_product_identity,
                    ),
                    key=lambda item: item.product_id,
                )),
                "keyword_identity": None,
                "variation_parent_product_identity": records[0].parent_product_identity,
                "variation_child_product_identity": records[0].child_product_identity,
                "source_observation_ids": tuple(sorted(item.observation_id for item in records)),
                "providers": tuple(sorted({item.provider for item in records})),
                "lineage_references": tuple(lineages[item] for item in sorted(lineages)),
            }
            edges.append(CompetitionEvidenceGraphEdge(
                graph_edge_id=deterministic_id("competition-graph-edge", payload), **payload
            ))
        children_by_parent: dict[str, list[CompetitionVariationEvidence]] = defaultdict(list)
        for variation in variations:
            children_by_parent[variation.parent_product_identity.product_id].append(variation)
        for records in children_by_parent.values():
            if len({item.child_product_identity.product_id for item in records}) > 1:
                diagnostics.append(self._diagnostic(
                    "SIBLING_COMPETITION_NOT_INFERRED", Severity.INFO,
                    (item.observation_id for item in records),
                    "Products sharing a confirmed parent remain variation endpoints; no sibling competition edge is created.",
                ))
        return CompetitionEvidenceGraph(nodes=tuple(nodes), edges=tuple(edges))

    @staticmethod
    def _diagnostic(
        code: str, severity: Severity, related_observation_ids: Iterable[str], message: str
    ) -> CompetitionDiagnostic:
        payload = {
            "code": code,
            "severity": severity,
            "related_observation_ids": tuple(sorted(set(related_observation_ids))),
            "message": message,
        }
        return CompetitionDiagnostic(
            diagnostic_id=deterministic_id("competition-diagnostic", payload), **payload
        )

    @staticmethod
    def _coverage(
        *,
        index: _RecordIndex,
        observations: tuple[CanonicalObservation, ...],
        inventory: tuple[CompetitionProductEvidence, ...],
        keyword_evidence: tuple[CompetitionKeywordEvidence, ...],
        relationships: tuple[CompetitionRelationshipEvidence, ...],
        variations: tuple[CompetitionVariationEvidence, ...],
        graph: CompetitionEvidenceGraph,
        diagnostics: list[CompetitionDiagnostic],
    ) -> CompetitionCoverageSummary:
        keyword_edges = sum(
            item.edge_type is EvidenceGraphEdgeType.KEYWORD_OBSERVED_RELATIONSHIP
            for item in graph.edges
        )
        variation_edges = sum(
            item.edge_type is EvidenceGraphEdgeType.VARIATION_RELATIONSHIP
            for item in graph.edges
        )
        return CompetitionCoverageSummary(
            source_bundle_count=len(index.bundle_fingerprints),
            raw_evidence_reference_count=len(index.raw_fingerprints),
            transformation_run_count=len(index.runs),
            observed_product_identity_count=len(inventory),
            observed_keyword_identity_count=len(keyword_evidence),
            relationship_observation_count=len(relationships),
            variation_observation_count=len(variations),
            keyword_graph_edge_count=keyword_edges,
            variation_graph_edge_count=variation_edges,
            provider_count=len({item.provenance.provider for item in observations}),
            source_tool_count=len({item.provenance.source_tool for item in observations}),
            channel_counts=dict(sorted(Counter(item.channel.value for item in relationships).items())),
            direction_counts=dict(sorted(Counter(item.direction.value for item in relationships).items())),
            quality_issue_count=len(index.issues),
            diagnostic_count=len(diagnostics),
        )


__all__ = ("CompetitionIntelligenceBuilderV0_1",)
