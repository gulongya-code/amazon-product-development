"""Evidence-preserving Product Intelligence V0.1 builder."""

from __future__ import annotations

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from typing import Any, Iterable

from amazon_product_intelligence.contracts import (
    CanonicalEvidenceBundle,
    CanonicalObservation,
    KeywordMetricObservation,
    MetricObservation,
    ObservationKind,
    PresenceStatus,
    ProductFactObservation,
    ProductIdentity,
    ProductKeywordRelationshipObservation,
    ReviewObservation,
    SemanticStatus,
    Severity,
    SubjectRef,
    SubjectType,
    canonical_json,
    deterministic_id,
    product_id,
)

from .errors import (
    ProductIdentityCollisionError,
    ProductIntelligenceValidationError,
    ProductSubjectNotFoundError,
    ProductTopologyError,
)
from .models import (
    PRODUCT_INTELLIGENCE_RULESET_VERSION,
    EvidenceCandidate,
    EvidenceCoverageSummary,
    FactCandidateState,
    LineageReference,
    OutOfScopeObservationReference,
    ProductFactEvidenceSet,
    ProductIntelligenceDiagnostic,
    ProductIntelligenceRequest,
    ProductIntelligenceSnapshotV0_1,
    ProductMetricSeries,
    ProductScope,
    QualityIssueReference,
    ReviewEvidenceSummary,
    VariationEdge,
    VariationTopology,
    bundle_fingerprint,
    observation_revision_content,
)


_RELATION_DIMENSIONS = {"child_product_relationship", "parent_product_relationship"}


def _is_relationship_dimension(dimension: str) -> bool:
    """Recognize the closed variation-relation namespace for fail-closed routing."""

    return dimension.endswith("_product_relationship")


@dataclass(slots=True)
class _ObservationEmission:
    observation: CanonicalObservation
    bundle_fingerprints: set[str]


@dataclass(slots=True)
class _IndexedRecord:
    record: Any
    bundle_fingerprints: set[str]


class _RecordIndex:
    def __init__(self, bundles: tuple[CanonicalEvidenceBundle, ...]) -> None:
        self.bundle_fingerprints = tuple(sorted(bundle_fingerprint(bundle) for bundle in bundles))
        self.observation_revisions: dict[str, str] = {}
        self.observations: dict[str, dict[str, _ObservationEmission]] = defaultdict(dict)
        self.runs: dict[str, _IndexedRecord] = {}
        self.issues: dict[str, _IndexedRecord] = {}
        self.raw_evidence_fingerprints: dict[str, set[str]] = defaultdict(set)
        self.collections: set[str] = set()
        self.mapping_keys: set[tuple[str, str]] = set()
        self.review_revisions: dict[str, str] = {}
        self._generic: dict[tuple[str, str], str] = {}
        for fingerprint, bundle in sorted(
            ((bundle_fingerprint(item), item) for item in bundles), key=lambda item: item[0]
        ):
            self._consume_bundle(bundle, fingerprint)

    @staticmethod
    def _merge_record(index: dict[str, _IndexedRecord], identity: str, record: Any, fingerprint: str, kind: str) -> None:
        current = index.get(identity)
        if current is not None and canonical_json(current.record) != canonical_json(record):
            raise ProductIdentityCollisionError(f"{kind} identity collision: {identity}")
        if current is None:
            index[identity] = _IndexedRecord(record=record, bundle_fingerprints={fingerprint})
        else:
            current.bundle_fingerprints.add(fingerprint)

    def _consume_bundle(self, bundle: CanonicalEvidenceBundle, fingerprint: str) -> None:
        for raw_id in bundle.raw_evidence_references:
            self.raw_evidence_fingerprints[raw_id].add(fingerprint)
        for run in bundle.transformation_runs:
            self._merge_record(self.runs, run.transformation_run_id, run, fingerprint, "transformation run")
            self.collections.add(run.collection_run_id)
            self.mapping_keys.add((run.provider, run.mapping_version))
        for observation in bundle.observations:
            revision = canonical_json(observation_revision_content(observation))
            current_revision = self.observation_revisions.get(observation.observation_id)
            if current_revision is not None and current_revision != revision:
                raise ProductIdentityCollisionError(f"observation identity collision: {observation.observation_id}")
            self.observation_revisions[observation.observation_id] = revision
            if isinstance(observation, ReviewObservation):
                review_revision = self.review_revisions.get(observation.review_observation_id)
                if review_revision is not None and review_revision != revision:
                    raise ProductIdentityCollisionError(
                        f"review observation identity collision: {observation.review_observation_id}"
                    )
                self.review_revisions[observation.review_observation_id] = revision
            run_id = observation.provenance.transformation.transformation_run_id
            current = self.observations[observation.observation_id].get(run_id)
            if current is not None and canonical_json(current.observation) != canonical_json(observation):
                raise ProductIdentityCollisionError(f"observation emission collision: {observation.observation_id}")
            if current is None:
                self.observations[observation.observation_id][run_id] = _ObservationEmission(
                    observation=observation, bundle_fingerprints={fingerprint}
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
                    raise ProductIdentityCollisionError(f"{kind} identity collision: {identity}")
                self._generic[key] = content

    def representatives(self) -> tuple[CanonicalObservation, ...]:
        return tuple(
            min(emissions.values(), key=lambda item: canonical_json(item.observation)).observation
            for _, emissions in sorted(self.observations.items())
        )

    def lineages(self, observation_id: str) -> tuple[LineageReference, ...]:
        emissions = self.observations.get(observation_id)
        if not emissions:
            raise ProductIntelligenceValidationError(f"orphan observation: {observation_id}")
        references: list[LineageReference] = []
        for run_id, emission in sorted(emissions.items()):
            observation = emission.observation
            transformation = observation.provenance.transformation
            run_entry = self.runs.get(run_id)
            if run_entry is None:
                raise ProductIntelligenceValidationError(f"orphan transformation run: {run_id}")
            run = run_entry.record
            raw_id = transformation.raw_evidence_reference
            if raw_id not in self.raw_evidence_fingerprints or raw_id not in run.input_raw_evidence_references:
                raise ProductIntelligenceValidationError(f"orphan raw evidence: {raw_id}")
            if run.collection_run_id != transformation.collection_run_id or run.mapping_version != transformation.mapping_version:
                raise ProductIntelligenceValidationError(f"mapping or collection mismatch for {observation_id}")
            references.append(
                LineageReference(
                    observation_id=observation.observation_id,
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
                )
            )
        return tuple(sorted(references, key=canonical_json))


class ProductIntelligenceBuilderV0_1:
    """Build a deterministic evidence view without resolving competing evidence."""

    def build(self, request: ProductIntelligenceRequest) -> ProductIntelligenceSnapshotV0_1:
        """Validate, organize, and return one auditable V0.1 snapshot."""

        if not isinstance(request, ProductIntelligenceRequest):
            raise ProductIntelligenceValidationError("request must be ProductIntelligenceRequest")
        snapshot = self._build_snapshot(request)
        return snapshot.validate_against_bundles(request.canonical_bundles)

    def _build_snapshot(self, request: ProductIntelligenceRequest) -> ProductIntelligenceSnapshotV0_1:
        """Build the deterministic snapshot used by public source replay validation."""

        if not isinstance(request, ProductIntelligenceRequest):
            raise ProductIntelligenceValidationError("request must be ProductIntelligenceRequest")
        index = _RecordIndex(request.canonical_bundles)
        observations = index.representatives()
        diagnostics: list[ProductIntelligenceDiagnostic] = []
        out_of_scope: list[OutOfScopeObservationReference] = []

        topology, included_products, consumed_relations, invalid_relations = self._build_topology(
            request, observations, index, diagnostics
        )
        included_ids = {item.product_id for item in included_products}
        direct_target = self._target_has_direct_evidence(request.target_product_identity, observations)
        target_endpoint = any(
            request.target_product_identity.product_id
            in {edge.parent_product_identity.product_id, edge.child_product_identity.product_id}
            for edge in topology.edges
        )
        if not direct_target and not target_endpoint:
            raise ProductSubjectNotFoundError(
                f"target product has no direct canonical evidence: {request.target_product_identity.product_id}"
            )

        facts: list[ProductFactObservation] = []
        metrics: list[MetricObservation] = []
        reviews: list[ReviewObservation] = []
        consumed_observation_ids = set(consumed_relations)
        for observation in observations:
            if isinstance(observation, (KeywordMetricObservation, ProductKeywordRelationshipObservation)):
                out_of_scope.append(self._out_ref(observation, "KEYWORD_OBSERVATION_OUT_OF_SCOPE", index))
                continue
            if isinstance(observation, ProductFactObservation) and _is_relationship_dimension(observation.dimension):
                if observation.observation_id not in consumed_relations:
                    reason = (
                        "INVALID_VARIATION_RELATIONSHIP_EXCLUDED"
                        if observation.observation_id in invalid_relations
                        else "UNRELATED_VARIATION_RELATIONSHIP_EXCLUDED"
                    )
                    out_of_scope.append(self._out_ref(observation, reason, index))
                continue
            product_subject_id = self._product_subject_id(observation)
            if product_subject_id not in included_ids:
                out_of_scope.append(self._out_ref(observation, "UNRELATED_PRODUCT_EVIDENCE_EXCLUDED", index))
                continue
            if isinstance(observation, ProductFactObservation):
                facts.append(observation)
            elif isinstance(observation, MetricObservation):
                metrics.append(observation)
            elif isinstance(observation, ReviewObservation):
                reviews.append(observation)

        if any(item.reason_code == "KEYWORD_OBSERVATION_OUT_OF_SCOPE" for item in out_of_scope):
            related = tuple(
                item.observation_id for item in out_of_scope if item.reason_code == "KEYWORD_OBSERVATION_OUT_OF_SCOPE"
            )
            diagnostics.append(self._diagnostic(
                "OUT_OF_SCOPE_KEYWORD_OBSERVATION", Severity.INFO, None, related,
                "Keyword observations are inventoried but are outside Product Intelligence V0.1.",
            ))
        unrelated = tuple(
            item.observation_id for item in out_of_scope if "UNRELATED" in item.reason_code
        )
        if unrelated:
            diagnostics.append(self._diagnostic(
                "UNRELATED_PRODUCT_EVIDENCE_EXCLUDED", Severity.INFO,
                self._subject(request.target_product_identity), unrelated,
                "Canonical evidence outside the requested product scope was explicitly excluded.",
            ))

        fact_sets = self._fact_sets(facts, included_products, index, diagnostics)
        metric_series = self._metric_series(metrics, included_products, index, diagnostics)
        review_summary = self._review_summary(reviews, index)
        quality_refs = self._quality_references(index)

        diagnostics = sorted({item.diagnostic_id: item for item in diagnostics}.values(), key=lambda item: item.diagnostic_id)
        topology_diagnostic_codes = {
            "NO_CONFIRMED_VARIATION_RELATIONSHIP", "MULTI_SOURCE_VARIATION_EDGE",
            "INVALID_UNRELATED_VARIATION_RELATIONSHIP_EXCLUDED", "UNCONFIRMED_VARIATION_RELATIONSHIP_EXCLUDED",
        }
        topology = VariationTopology(
            target_product_identity=topology.target_product_identity,
            scope=topology.scope,
            nodes=topology.nodes,
            edges=topology.edges,
            family_root=topology.family_root,
            diagnostic_ids=tuple(
                item.diagnostic_id for item in diagnostics if item.code in topology_diagnostic_codes
            ),
        )

        referenced_lineages: dict[str, LineageReference] = {}
        for fact_set in fact_sets:
            for candidate in fact_set.candidates:
                for lineage in candidate.lineage_references:
                    referenced_lineages[canonical_json(lineage)] = lineage
                    consumed_observation_ids.add(candidate.observation_id)
        for series in metric_series:
            for candidate in series.candidates:
                for lineage in candidate.lineage_references:
                    referenced_lineages[canonical_json(lineage)] = lineage
                    consumed_observation_ids.add(candidate.observation_id)
        for lineage in review_summary.lineage_references:
            referenced_lineages[canonical_json(lineage)] = lineage
            consumed_observation_ids.add(lineage.observation_id)
        for edge in topology.edges:
            for lineage in edge.lineage_references:
                referenced_lineages[canonical_json(lineage)] = lineage
        for reference in out_of_scope:
            for lineage in reference.lineage_references:
                referenced_lineages[canonical_json(lineage)] = lineage
        for reference in quality_refs:
            for lineage in reference.observation_lineage_references:
                referenced_lineages[canonical_json(lineage)] = lineage

        coverage = self._coverage(
            index=index,
            observations=observations,
            included_ids=consumed_observation_ids,
            out_of_scope=out_of_scope,
            fact_sets=fact_sets,
            metric_series=metric_series,
            review_summary=review_summary,
            topology=topology,
            diagnostics=diagnostics,
        )
        snapshot_payload = {
            "ruleset_version": PRODUCT_INTELLIGENCE_RULESET_VERSION,
            "target_product_identity": request.target_product_identity,
            "scope": request.scope,
            "included_product_identities": tuple(sorted(included_products, key=lambda item: item.product_id)),
            "source_bundle_fingerprints": index.bundle_fingerprints,
            "variation_topology": topology,
            "product_fact_evidence_sets": tuple(sorted(fact_sets, key=lambda item: item.fact_set_id)),
            "product_metric_series": tuple(sorted(metric_series, key=lambda item: item.metric_series_id)),
            "review_evidence_summary": review_summary,
            "evidence_coverage_summary": coverage,
            "quality_issue_references": tuple(sorted(quality_refs, key=lambda item: item.issue_id)),
            "out_of_scope_observation_references": tuple(sorted(out_of_scope, key=lambda item: item.observation_id)),
            "lineage_index": tuple(referenced_lineages[key] for key in sorted(referenced_lineages)),
            "diagnostics": tuple(diagnostics),
        }
        snapshot = ProductIntelligenceSnapshotV0_1(
            snapshot_id=deterministic_id("snapshot", snapshot_payload), **snapshot_payload
        )
        return snapshot

    @staticmethod
    def _subject(product: ProductIdentity) -> SubjectRef:
        return SubjectRef(subject_type=SubjectType.PRODUCT, subject_id=product.product_id, marketplace=product.marketplace)

    @staticmethod
    def _diagnostic(
        code: str,
        severity: Severity,
        subject: SubjectRef | None,
        related_ids: Iterable[str],
        message: str,
    ) -> ProductIntelligenceDiagnostic:
        payload = {
            "code": code,
            "severity": severity,
            "subject": subject,
            "related_observation_ids": tuple(sorted(set(related_ids))),
            "message": message,
        }
        return ProductIntelligenceDiagnostic(
            diagnostic_id=deterministic_id("pi-diagnostic", payload), **payload
        )

    @staticmethod
    def _product_subject_id(observation: CanonicalObservation) -> str | None:
        if observation.subject.subject_type is SubjectType.PRODUCT:
            return observation.subject.subject_id
        if isinstance(observation, ReviewObservation):
            return observation.product.product_id
        if isinstance(observation, ProductKeywordRelationshipObservation):
            return observation.product.product_id
        return None

    @classmethod
    def _target_has_direct_evidence(
        cls, target: ProductIdentity, observations: tuple[CanonicalObservation, ...]
    ) -> bool:
        return any(cls._product_subject_id(observation) == target.product_id for observation in observations)

    @staticmethod
    def _identity_from_subject(subject: SubjectRef, target: ProductIdentity) -> ProductIdentity:
        if subject.subject_type is not SubjectType.PRODUCT:
            raise ProductIntelligenceValidationError("variation relation subject must be PRODUCT")
        parts = subject.subject_id.split(":")
        if len(parts) != 3 or parts[0] != "product" or parts[1] != subject.marketplace:
            raise ProductIntelligenceValidationError("variation relation subject has invalid product identity")
        expected = product_id(subject.marketplace, parts[2])
        if expected != subject.subject_id:
            raise ProductIntelligenceValidationError("variation relation subject identity mismatch")
        if expected == target.product_id:
            return target
        return ProductIdentity(
            product_id=expected,
            marketplace=subject.marketplace,
            asin=parts[2],
            parent_asin=None,
            identity_status="CONFIRMED",
        )

    @staticmethod
    def _identity_from_value(value: Any, marketplace: str, target: ProductIdentity) -> ProductIdentity:
        if type(value) is not str:
            raise ProductIntelligenceValidationError("variation relation endpoint must be an ASIN string")
        identity = product_id(marketplace, value)
        if identity == target.product_id:
            return target
        return ProductIdentity(
            product_id=identity,
            marketplace=marketplace,
            asin=value.strip().upper(),
            parent_asin=None,
            identity_status="CONFIRMED",
        )

    def _build_topology(
        self,
        request: ProductIntelligenceRequest,
        observations: tuple[CanonicalObservation, ...],
        index: _RecordIndex,
        diagnostics: list[ProductIntelligenceDiagnostic],
    ) -> tuple[VariationTopology, tuple[ProductIdentity, ...], set[str], set[str]]:
        edge_evidence: dict[tuple[str, str], list[ProductFactObservation]] = defaultdict(list)
        identities: dict[str, ProductIdentity] = {request.target_product_identity.product_id: request.target_product_identity}
        invalid_ids: set[str] = set()
        for observation in observations:
            if not isinstance(observation, ProductFactObservation) or not _is_relationship_dimension(observation.dimension):
                continue
            if (
                observation.value.presence_status is not PresenceStatus.PRESENT
                or observation.value.semantic_status is not SemanticStatus.CONFIRMED
            ):
                invalid_ids.add(observation.observation_id)
                diagnostics.append(self._diagnostic(
                    "UNCONFIRMED_VARIATION_RELATIONSHIP_EXCLUDED", Severity.INFO, observation.subject,
                    (observation.observation_id,), "Only confirmed present variation relationships expand topology.",
                ))
                continue
            subject_related = observation.subject.subject_id == request.target_product_identity.product_id
            try:
                subject_identity = self._identity_from_subject(observation.subject, request.target_product_identity)
                value_identity = self._identity_from_value(
                    observation.value.normalized_value, observation.subject.marketplace, request.target_product_identity
                )
                if observation.dimension == "child_product_relationship":
                    parent, child = subject_identity, value_identity
                elif observation.dimension == "parent_product_relationship":
                    parent, child = value_identity, subject_identity
                else:
                    raise ProductIntelligenceValidationError("unrecognized relation direction")
                if parent.marketplace != child.marketplace:
                    raise ProductIntelligenceValidationError("variation endpoint marketplace mismatch")
                if parent.product_id == child.product_id:
                    if parent.product_id == request.target_product_identity.product_id:
                        raise ProductTopologyError("target-connected confirmed variation self-loop")
                    raise ProductIntelligenceValidationError("unrelated confirmed variation self-loop")
            except ProductTopologyError:
                raise
            except Exception as exc:
                value_related = observation.value.normalized_value == request.target_product_identity.asin
                if subject_related or value_related:
                    raise ProductTopologyError(
                        f"invalid target-connected variation relation {observation.observation_id}: {exc}"
                    ) from exc
                invalid_ids.add(observation.observation_id)
                diagnostics.append(self._diagnostic(
                    "INVALID_UNRELATED_VARIATION_RELATIONSHIP_EXCLUDED", Severity.WARNING, observation.subject,
                    (observation.observation_id,), "Invalid unrelated confirmed variation evidence was excluded.",
                ))
                continue
            identities[parent.product_id] = parent
            identities[child.product_id] = child
            edge_evidence[(parent.product_id, child.product_id)].append(observation)

        adjacency: dict[str, set[str]] = defaultdict(set)
        for parent_id, child_id in edge_evidence:
            adjacency[parent_id].add(child_id)
            adjacency[child_id].add(parent_id)
        target_id = request.target_product_identity.product_id
        if request.scope is ProductScope.EXACT_PRODUCT:
            selected_keys = {key for key in edge_evidence if target_id in key}
            included_ids = {target_id}
            topology_node_ids = {target_id}
            for key in selected_keys:
                topology_node_ids.update(key)
        else:
            component = {target_id}
            queue = deque((target_id,))
            while queue:
                current = queue.popleft()
                for neighbour in sorted(adjacency.get(current, ())):
                    if neighbour not in component:
                        component.add(neighbour)
                        queue.append(neighbour)
            selected_keys = {key for key in edge_evidence if key[0] in component and key[1] in component}
            included_ids = component
            topology_node_ids = component
            if not selected_keys:
                diagnostics.append(self._diagnostic(
                    "NO_CONFIRMED_VARIATION_RELATIONSHIP", Severity.INFO,
                    self._subject(request.target_product_identity), (),
                    "No confirmed variation relationship was supplied; family scope remains the exact target.",
                ))

        parents_by_child: dict[str, set[str]] = defaultdict(set)
        directed: dict[str, set[str]] = defaultdict(set)
        for parent_id, child_id in selected_keys:
            parents_by_child[child_id].add(parent_id)
            directed[parent_id].add(child_id)
        ambiguous = {child: parents for child, parents in parents_by_child.items() if len(parents) > 1}
        if ambiguous:
            child = sorted(ambiguous)[0]
            raise ProductTopologyError(f"target-connected child has multiple confirmed parents: {child}")
        state: dict[str, int] = {}

        def visit(node: str) -> None:
            if state.get(node) == 1:
                raise ProductTopologyError(f"target-connected confirmed variation cycle at {node}")
            if state.get(node) == 2:
                return
            state[node] = 1
            for child in sorted(directed.get(node, ())):
                visit(child)
            state[node] = 2

        for node in sorted(topology_node_ids):
            visit(node)

        edges: list[VariationEdge] = []
        consumed: set[str] = set()
        for parent_id, child_id in sorted(selected_keys):
            evidence = edge_evidence[(parent_id, child_id)]
            observation_ids = tuple(sorted({item.observation_id for item in evidence}))
            consumed.update(observation_ids)
            lineages = tuple(
                lineage
                for observation_id in observation_ids
                for lineage in index.lineages(observation_id)
            )
            payload = {
                "parent_product_identity": identities[parent_id],
                "child_product_identity": identities[child_id],
                "evidence_observation_ids": observation_ids,
                "evidence_dimensions": tuple(sorted({item.dimension for item in evidence})),
                "providers": tuple(sorted({item.provenance.provider for item in evidence})),
                "source_tools": tuple(sorted({item.provenance.source_tool for item in evidence})),
                "evidence_count": len(observation_ids),
                "lineage_references": tuple(sorted(lineages, key=canonical_json)),
            }
            edge = VariationEdge(
                variation_edge_id=deterministic_id("variation-edge", payload), **payload
            )
            edges.append(edge)
            if len(edge.providers) > 1 or len(edge.source_tools) > 1:
                diagnostics.append(self._diagnostic(
                    "MULTI_SOURCE_VARIATION_EDGE", Severity.INFO, self._subject(identities[parent_id]),
                    observation_ids, "Multiple source observations support the same normalized variation edge.",
                ))
        roots = sorted(topology_node_ids - set(parents_by_child))
        family_root = identities[roots[0]] if len(roots) == 1 else None
        topology = VariationTopology(
            target_product_identity=request.target_product_identity,
            scope=request.scope,
            nodes=tuple(identities[item] for item in sorted(topology_node_ids)),
            edges=tuple(edges),
            family_root=family_root,
            diagnostic_ids=(),
        )
        included = tuple(identities[item] for item in sorted(included_ids))
        return topology, included, consumed, invalid_ids

    @staticmethod
    def _candidate(observation: CanonicalObservation, index: _RecordIndex) -> EvidenceCandidate:
        return EvidenceCandidate(
            observation_id=observation.observation_id,
            semantic_observation_id=observation.semantic_observation_id,
            observation_kind=observation.observation_kind,
            presence_status=observation.value.presence_status,
            raw_value=observation.value.raw_value,
            normalized_value=observation.value.normalized_value,
            value_type=observation.value.value_type,
            unit=observation.value.unit,
            normalization_status=observation.value.normalization_status,
            semantic_status=observation.value.semantic_status,
            evidence_type=observation.evidence_type,
            result_status=observation.result_status,
            scope=observation.scope,
            time=observation.time,
            provider=observation.provenance.provider,
            source_tool=observation.provenance.source_tool,
            lineage_references=index.lineages(observation.observation_id),
        )

    @staticmethod
    def _identity_map(products: tuple[ProductIdentity, ...]) -> dict[str, ProductIdentity]:
        return {item.product_id: item for item in products}

    def _fact_sets(
        self,
        observations: list[ProductFactObservation],
        products: tuple[ProductIdentity, ...],
        index: _RecordIndex,
        diagnostics: list[ProductIntelligenceDiagnostic],
    ) -> tuple[ProductFactEvidenceSet, ...]:
        identities = self._identity_map(products)
        groups: dict[str, list[ProductFactObservation]] = defaultdict(list)
        for observation in observations:
            key = canonical_json({
                "subject": observation.subject,
                "dimension": observation.dimension,
                "fact_group": observation.fact_group,
                "scope": observation.scope,
                "unit": observation.value.unit,
                "provider_semantic": observation.provider_semantic,
            })
            groups[key].append(observation)
        result: list[ProductFactEvidenceSet] = []
        for key in sorted(groups):
            group = groups[key]
            candidates = tuple(sorted((self._candidate(item, index) for item in group), key=lambda item: item.observation_id))
            present_values = {
                canonical_json({"value": item.normalized_value, "unit": item.unit})
                for item in candidates if item.presence_status is PresenceStatus.PRESENT
            }
            state = (
                FactCandidateState.NO_PRESENT_CANDIDATE if not present_values
                else FactCandidateState.ONE_DISTINCT_PRESENT_VALUE if len(present_values) == 1
                else FactCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES
            )
            first = group[0]
            payload = {
                "subject_product_identity": identities[first.subject.subject_id],
                "dimension": first.dimension,
                "fact_group": first.fact_group,
                "scope": first.scope,
                "unit": first.value.unit,
                "provider_semantic": first.provider_semantic,
                "candidate_state": state,
                "distinct_present_value_count": len(present_values),
                "candidates": candidates,
            }
            fact_set = ProductFactEvidenceSet(
                fact_set_id=deterministic_id("fact-set", payload), **payload
            )
            result.append(fact_set)
            if state is FactCandidateState.MULTIPLE_DISTINCT_PRESENT_VALUES:
                diagnostics.append(self._diagnostic(
                    "MULTIPLE_DISTINCT_FACT_VALUES", Severity.WARNING, first.subject,
                    (item.observation_id for item in group),
                    "Multiple distinct present values are retained as unresolved fact candidates.",
                ))
            elif state is FactCandidateState.NO_PRESENT_CANDIDATE:
                diagnostics.append(self._diagnostic(
                    "NON_PRESENT_ONLY_FACT_CANDIDATES", Severity.INFO, first.subject,
                    (item.observation_id for item in group),
                    "The fact evidence set contains only non-present candidates.",
                ))
        by_dimension: dict[tuple[str, str], set[str]] = defaultdict(set)
        for fact_set in result:
            unit = canonical_json(fact_set.unit) if fact_set.unit is not None else "null"
            by_dimension[(fact_set.subject_product_identity.product_id, fact_set.dimension)].add(unit)
        for (subject_id, dimension), units in sorted(by_dimension.items()):
            if len(units) > 1:
                related = tuple(
                    candidate.observation_id
                    for fact_set in result
                    if fact_set.subject_product_identity.product_id == subject_id and fact_set.dimension == dimension
                    for candidate in fact_set.candidates
                )
                diagnostics.append(self._diagnostic(
                    "NON_COMPARABLE_UNITS", Severity.INFO, self._subject(identities[subject_id]), related,
                    "Fact candidates with different units remain in separate evidence sets.",
                ))
        return tuple(result)

    def _metric_series(
        self,
        observations: list[MetricObservation],
        products: tuple[ProductIdentity, ...],
        index: _RecordIndex,
        diagnostics: list[ProductIntelligenceDiagnostic],
    ) -> tuple[ProductMetricSeries, ...]:
        identities = self._identity_map(products)
        groups: dict[str, list[MetricObservation]] = defaultdict(list)
        for observation in observations:
            key = canonical_json({
                "subject": observation.subject,
                "metric": observation.metric,
                "measurement_type": observation.measurement_type,
                "evidence_type": observation.evidence_type,
                "unit": observation.value.unit,
                "scope": observation.scope,
                "period_type": observation.time.period_type,
                "period_start": observation.time.period_start,
                "period_end": observation.time.period_end,
                "observed_at_status": observation.time.observed_at_status,
                "timezone": observation.time.timezone,
                "currency": observation.currency,
                "rank_context": observation.rank_context,
                "metric_semantic": observation.metric_semantic,
            })
            groups[key].append(observation)
        result: list[ProductMetricSeries] = []
        for key in sorted(groups):
            group = groups[key]
            candidates = tuple(sorted((self._candidate(item, index) for item in group), key=lambda item: (
                item.time.observed_at or "", item.time.period_start or "", item.time.period_end or "", item.observation_id
            )))
            first = group[0]
            counts = Counter(item.presence_status.value for item in candidates)
            payload = {
                "subject_product_identity": identities[first.subject.subject_id],
                "metric": first.metric,
                "measurement_type": first.measurement_type,
                "evidence_type": first.evidence_type,
                "unit": first.value.unit,
                "scope": first.scope,
                "period_type": first.time.period_type,
                "period_start": first.time.period_start,
                "period_end": first.time.period_end,
                "observed_at_status": first.time.observed_at_status,
                "timezone": first.time.timezone,
                "currency": first.currency,
                "rank_context": first.rank_context,
                "metric_semantic": first.metric_semantic,
                "candidate_count": len(candidates),
                "presence_counts": dict(sorted(counts.items())),
                "candidates": candidates,
            }
            series = ProductMetricSeries(
                metric_series_id=deterministic_id("metric-series", payload), **payload
            )
            result.append(series)
            if first.time.period_start is None or first.time.period_end is None:
                diagnostics.append(self._diagnostic(
                    "UNKNOWN_METRIC_PERIOD", Severity.INFO, first.subject,
                    (item.observation_id for item in group),
                    "The metric period is unknown and was not inferred from retrieval time.",
                ))
        return tuple(result)

    @staticmethod
    def _review_summary(observations: list[ReviewObservation], index: _RecordIndex) -> ReviewEvidenceSummary:
        grouped: dict[str, list[ReviewObservation]] = defaultdict(list)
        for observation in observations:
            grouped[observation.review_observation_id].append(observation)
        representatives = [
            min(group, key=canonical_json) for _, group in sorted(grouped.items())
        ]
        rating_presence = Counter(item.rating.presence_status.value for item in representatives)
        histogram: Counter[str] = Counter()
        unique_identities: set[str] = set()
        known_dates = 0
        helpful_missing = helpful_zero = helpful_positive = 0
        variant_known = 0
        lineages: list[LineageReference] = []
        for observation in representatives:
            if observation.rating.presence_status is PresenceStatus.PRESENT:
                histogram[canonical_json(observation.rating.normalized_value)] += 1
            identity = observation.provider_review_identity or observation.review_observation_id
            unique_identities.add(canonical_json((observation.provenance.provider, identity)))
            known_dates += int(observation.review_date.presence_status is PresenceStatus.PRESENT)
            if observation.helpful_votes.presence_status is PresenceStatus.MISSING:
                helpful_missing += 1
            elif observation.helpful_votes.presence_status is PresenceStatus.PRESENT:
                value = observation.helpful_votes.normalized_value
                if type(value) in {int, float} and not isinstance(value, bool):
                    if value == 0:
                        helpful_zero += 1
                    elif value > 0:
                        helpful_positive += 1
            variant_known += int(observation.variant.presence_status is PresenceStatus.PRESENT)
        for observation in observations:
            lineages.extend(index.lineages(observation.observation_id))
        return ReviewEvidenceSummary(
            sample_basis="SUPPLIED_EVIDENCE_SAMPLE",
            review_observation_count=len(representatives),
            exact_unique_review_identity_count=len(unique_identities),
            providers=tuple(sorted({item.provenance.provider for item in observations})),
            source_tools=tuple(sorted({item.provenance.source_tool for item in observations})),
            rating_presence_counts=dict(sorted(rating_presence.items())),
            present_rating_histogram=dict(sorted(histogram.items())),
            known_date_count=known_dates,
            unknown_date_count=len(representatives) - known_dates,
            helpful_votes_missing_count=helpful_missing,
            helpful_votes_zero_count=helpful_zero,
            helpful_votes_positive_count=helpful_positive,
            variant_known_count=variant_known,
            variant_unknown_count=len(representatives) - variant_known,
            review_observation_ids=tuple(sorted(item.observation_id for item in representatives)),
            lineage_references=tuple(sorted(lineages, key=canonical_json)),
        )

    @staticmethod
    def _quality_references(index: _RecordIndex) -> tuple[QualityIssueReference, ...]:
        result: list[QualityIssueReference] = []
        for issue_id, entry in sorted(index.issues.items()):
            issue = entry.record
            source_observation_ids = {
                item for item in issue.source_references if item.startswith("obs:")
            }
            source_raw_ids = {
                item for item in issue.source_references if item.startswith("raw:")
            }
            if len(source_observation_ids) + len(source_raw_ids) != len(issue.source_references):
                raise ProductIntelligenceValidationError(
                    f"quality issue has unsupported source reference: {issue_id}"
                )
            observation_lineages = tuple(sorted(
                (
                    lineage
                    for observation_id in sorted(source_observation_ids)
                    for lineage in index.lineages(observation_id)
                ),
                key=canonical_json,
            ))
            raw_ids = source_raw_ids | {item.raw_evidence_id for item in observation_lineages}
            related_runs = {
                run_id: run_entry.record
                for run_id, run_entry in index.runs.items()
                if raw_ids.intersection(run_entry.record.input_raw_evidence_references)
                or run_id == issue.transformation_run_id
            }
            collections = {item.collection_run_id for item in related_runs.values()}
            if issue.collection_run_id is not None:
                collections.add(issue.collection_run_id)
            mappings = {item.mapping_version for item in related_runs.values()}
            if issue.mapping_version is not None:
                mappings.add(issue.mapping_version)
            providers = {item.provider for item in related_runs.values()}
            source_tools = {
                emission.observation.provenance.source_tool
                for emissions in index.observations.values()
                for run_id, emission in emissions.items()
                if run_id in related_runs or emission.observation.observation_id in source_observation_ids
            }
            result.append(QualityIssueReference(
                issue_id=issue_id,
                issue_code=issue.issue_code,
                severity=issue.severity,
                source_references=tuple(sorted(set(issue.source_references))),
                collection_run_id=issue.collection_run_id,
                transformation_run_id=issue.transformation_run_id,
                mapping_version=issue.mapping_version,
                raw_evidence_ids=tuple(sorted(raw_ids)),
                collection_run_ids=tuple(sorted(collections)),
                transformation_run_ids=tuple(sorted(related_runs)),
                mapping_versions=tuple(sorted(mappings)),
                providers=tuple(sorted(providers)),
                source_tools=tuple(sorted(source_tools)),
                observation_lineage_references=observation_lineages,
                source_bundle_fingerprints=tuple(sorted(entry.bundle_fingerprints)),
            ))
        return tuple(result)

    @staticmethod
    def _out_ref(
        observation: CanonicalObservation, reason: str, index: _RecordIndex
    ) -> OutOfScopeObservationReference:
        return OutOfScopeObservationReference(
            observation_id=observation.observation_id,
            observation_kind=observation.observation_kind,
            reason_code=reason,
            lineage_references=index.lineages(observation.observation_id),
        )

    @staticmethod
    def _coverage(
        *,
        index: _RecordIndex,
        observations: tuple[CanonicalObservation, ...],
        included_ids: set[str],
        out_of_scope: list[OutOfScopeObservationReference],
        fact_sets: tuple[ProductFactEvidenceSet, ...],
        metric_series: tuple[ProductMetricSeries, ...],
        review_summary: ReviewEvidenceSummary,
        topology: VariationTopology,
        diagnostics: list[ProductIntelligenceDiagnostic],
    ) -> EvidenceCoverageSummary:
        kinds = Counter(item.observation_kind.value for item in observations)
        evidence = Counter(item.evidence_type.value for item in observations)
        presence = Counter(item.value.presence_status.value for item in observations)
        providers = {item.provenance.provider for item in observations}
        providers.update(entry.record.provider for entry in index.runs.values())
        source_tools = {item.provenance.source_tool for item in observations}
        return EvidenceCoverageSummary(
            source_bundle_count=len(index.bundle_fingerprints),
            collection_count=len(index.collections),
            raw_evidence_record_count=len(index.raw_evidence_fingerprints),
            mapping_count=len(index.mapping_keys),
            transformation_run_count=len(index.runs),
            observation_counts_by_type=dict(sorted(kinds.items())),
            included_observation_count=len(included_ids),
            excluded_observation_count=len(out_of_scope),
            out_of_scope_keyword_observation_count=sum(
                item.observation_kind in {
                    ObservationKind.KEYWORD_METRIC, ObservationKind.PRODUCT_KEYWORD_RELATIONSHIP
                } for item in out_of_scope
            ),
            provider_count=len(providers),
            source_tool_count=len(source_tools),
            payload_kind_count=0,
            evidence_type_counts=dict(sorted(evidence.items())),
            presence_state_counts=dict(sorted(presence.items())),
            fact_dimension_count=len({item.dimension for item in fact_sets}),
            metric_type_count=len({item.metric for item in metric_series}),
            review_evidence_count=review_summary.review_observation_count,
            variation_edge_count=len(topology.edges),
            quality_issue_count=len(index.issues),
            product_intelligence_diagnostic_count=len(diagnostics),
        )


__all__ = ("ProductIntelligenceBuilderV0_1",)
