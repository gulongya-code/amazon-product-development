"""Deterministic, explainable threshold clustering over Buyer Need Evidence V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from itertools import combinations

from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedCandidateStatus,
    BuyerNeedEvidence,
    BuyerNeedType,
)
from amazon_product_intelligence.contracts import Severity, deterministic_id

from .errors import SemanticClusteringValidationError
from .models import (
    SEMANTIC_CLUSTERING_CONTRACT_VERSION,
    SemanticClusterDiagnostic,
    SemanticClusterMembership,
    SemanticClusterMethod,
    SemanticClusterSnapshot,
    SemanticClusteringConfig,
    SemanticClusteringResult,
    SemanticConfidence,
    SemanticConfidenceLevel,
    SemanticSimilarityEvidence,
    ratio_text,
    semantic_cluster_id,
)
from .rules import (
    SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
    SemanticNormalizationRegistry,
)
from .similarity import RapidFuzzLexicalSimilarity


class SemanticClusterBuilder:
    """Cluster existing BuyerNeedEvidence without estimating demand or opportunity."""

    method = SemanticClusterMethod.LEXICAL_THRESHOLD

    def __init__(
        self,
        *,
        config: SemanticClusteringConfig | None = None,
        normalization_registry: SemanticNormalizationRegistry = (
            SEMANTIC_NORMALIZATION_REGISTRY_V0_1
        ),
    ) -> None:
        self.config = config or SemanticClusteringConfig()
        if not isinstance(self.config, SemanticClusteringConfig):
            raise SemanticClusteringValidationError(
                "cluster builder requires SemanticClusteringConfig"
            )
        if not isinstance(normalization_registry, SemanticNormalizationRegistry):
            raise SemanticClusteringValidationError(
                "cluster builder requires SemanticNormalizationRegistry"
            )
        if self.config.ruleset_version != normalization_registry.ruleset_version:
            raise SemanticClusteringValidationError(
                "cluster config and normalization registry version mismatch"
            )
        self.normalization_registry = normalization_registry
        self.similarity = RapidFuzzLexicalSimilarity(registry=normalization_registry)

    def build(
        self,
        needs: Sequence[BuyerNeedEvidence],
    ) -> SemanticClusteringResult:
        if isinstance(needs, (str, bytes)) or not isinstance(needs, Sequence):
            raise SemanticClusteringValidationError(
                "clustering input must be a sequence of BuyerNeedEvidence"
            )
        source_needs = tuple(needs)
        if any(not isinstance(item, BuyerNeedEvidence) for item in source_needs):
            raise SemanticClusteringValidationError(
                "clustering input must contain only BuyerNeedEvidence"
            )
        if len({item.need_id for item in source_needs}) != len(source_needs):
            raise SemanticClusteringValidationError(
                "clustering input need_ids must be unique"
            )
        source_needs = tuple(sorted(source_needs, key=lambda item: item.need_id))
        unknown = tuple(
            item
            for item in source_needs
            if item.status is BuyerNeedCandidateStatus.UNKNOWN
            or item.need_type is BuyerNeedType.UNKNOWN
        )
        eligible = tuple(item for item in source_needs if item not in unknown)

        pair_evidence = tuple(
            self.similarity.compare(left, right)
            for left, right in combinations(eligible, 2)
        )
        pair_evidence = tuple(
            sorted(pair_evidence, key=lambda item: item.similarity_id)
        )
        clusters = tuple(
            self._cluster_snapshot(group, pair_evidence)
            for group in self._components(eligible, pair_evidence)
        )
        clusters = tuple(sorted(clusters, key=lambda item: item.cluster_id))
        diagnostics = self._result_diagnostics(unknown)
        payload = {
            "clusters": clusters,
            "source_needs": source_needs,
            "similarity_evidence": pair_evidence,
            "excluded_unknown_need_ids": tuple(item.need_id for item in unknown),
            "config": self.config,
            "diagnostics": diagnostics,
            "contract_version": SEMANTIC_CLUSTERING_CONTRACT_VERSION,
        }
        return SemanticClusteringResult(
            result_id=deterministic_id("semantic-clustering-result", payload),
            **payload,
        )

    def build_clusters(
        self,
        needs: Sequence[BuyerNeedEvidence],
    ) -> tuple[SemanticClusterSnapshot, ...]:
        """Return the requested cluster snapshots while retaining `build` as the full envelope."""

        return self.build(needs).clusters

    def regenerate_label(self, snapshot: SemanticClusterSnapshot) -> str:
        """Regenerate a label from immutable member Needs and similarity evidence."""

        if not isinstance(snapshot, SemanticClusterSnapshot):
            raise SemanticClusteringValidationError(
                "label regeneration requires SemanticClusterSnapshot"
            )
        return self._cluster_label(snapshot.source_needs, snapshot.similarity_evidence)

    def _components(
        self,
        needs: tuple[BuyerNeedEvidence, ...],
        pair_evidence: tuple[SemanticSimilarityEvidence, ...],
    ) -> tuple[tuple[BuyerNeedEvidence, ...], ...]:
        parents = {item.need_id: item.need_id for item in needs}

        def find(need_id: str) -> str:
            while parents[need_id] != need_id:
                parents[need_id] = parents[parents[need_id]]
                need_id = parents[need_id]
            return need_id

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root == right_root:
                return
            first, second = sorted((left_root, right_root))
            parents[second] = first

        threshold = Decimal(self.config.lexical_threshold)
        for evidence in pair_evidence:
            if Decimal(evidence.score) >= threshold:
                union(evidence.source_need_id, evidence.target_need_id)

        grouped: dict[str, list[BuyerNeedEvidence]] = {}
        for need in needs:
            grouped.setdefault(find(need.need_id), []).append(need)
        components = tuple(
            tuple(sorted(group, key=lambda item: item.need_id))
            for group in grouped.values()
        )
        return tuple(sorted(components, key=lambda item: tuple(need.need_id for need in item)))

    def _cluster_snapshot(
        self,
        needs: tuple[BuyerNeedEvidence, ...],
        all_pair_evidence: tuple[SemanticSimilarityEvidence, ...],
    ) -> SemanticClusterSnapshot:
        need_ids = tuple(item.need_id for item in needs)
        need_id_set = set(need_ids)
        similarities = tuple(
            item
            for item in all_pair_evidence
            if item.source_need_id in need_id_set and item.target_need_id in need_id_set
        )
        cluster_id = semantic_cluster_id(
            source_need_ids=need_ids,
            cluster_method=self.method,
            model_version=self.similarity.model_version,
            threshold=self.config.lexical_threshold,
            normalization_rule_version=self.normalization_registry.ruleset_version,
        )
        memberships = tuple(
            self._membership(
                cluster_id=cluster_id,
                need=need,
                cluster_size=len(needs),
                similarities=similarities,
            )
            for need in needs
        )
        confidence = self._cluster_confidence(memberships)
        diagnostics = self._cluster_diagnostics(
            cluster_id=cluster_id,
            need_ids=need_ids,
            similarities=similarities,
        )
        evidence_count = len(
            {
                evidence.text_id
                for need in needs
                for evidence in need.source_evidence
            }
        )
        return SemanticClusterSnapshot(
            cluster_id=cluster_id,
            cluster_label=self._cluster_label(needs, similarities),
            cluster_members=memberships,
            source_need_ids=need_ids,
            cluster_method=self.method,
            model_version=self.similarity.model_version,
            confidence=confidence,
            evidence_count=evidence_count,
            diagnostics=diagnostics,
            threshold=self.config.lexical_threshold,
            normalization_rule_version=self.normalization_registry.ruleset_version,
            source_needs=needs,
            similarity_evidence=similarities,
        )

    def _membership(
        self,
        *,
        cluster_id: str,
        need: BuyerNeedEvidence,
        cluster_size: int,
        similarities: tuple[SemanticSimilarityEvidence, ...],
    ) -> SemanticClusterMembership:
        references = tuple(sorted(item.text_id for item in need.source_evidence))
        if cluster_size == 1:
            similarity_score = "1"
            confidence = SemanticConfidence(
                level=SemanticConfidenceLevel.UNKNOWN,
                score=None,
                basis=(
                    "singleton_cluster_has_no_pairwise_similarity_decision",
                    "similarity_is_not_demand",
                ),
            )
        else:
            scores = [
                Decimal(item.score)
                for item in similarities
                if need.need_id in {item.source_need_id, item.target_need_id}
            ]
            if not scores:
                raise SemanticClusteringValidationError(
                    "non-singleton membership requires pairwise similarity evidence"
                )
            similarity_score = ratio_text(max(scores))
            confidence = self._known_confidence(
                score=Decimal(similarity_score),
                basis=(
                    "maximum_explainable_pairwise_link_for_member",
                    f"threshold:{self.config.lexical_threshold}",
                    f"model:{self.similarity.model_version}",
                    "similarity_is_not_demand",
                ),
            )
        payload = {
            "cluster_id": cluster_id,
            "need_id": need.need_id,
            "similarity_score": similarity_score,
            "confidence": confidence,
            "evidence_reference": references,
        }
        return SemanticClusterMembership(
            membership_id=deterministic_id("semantic-cluster-membership", payload),
            **payload,
        )

    def _cluster_confidence(
        self,
        memberships: tuple[SemanticClusterMembership, ...],
    ) -> SemanticConfidence:
        if len(memberships) == 1:
            return SemanticConfidence(
                level=SemanticConfidenceLevel.UNKNOWN,
                score=None,
                basis=(
                    "singleton_cluster_has_no_grouping_confidence",
                    "similarity_is_not_demand",
                ),
            )
        score = min(Decimal(item.similarity_score) for item in memberships)
        return self._known_confidence(
            score=score,
            basis=(
                "minimum_of_member_best_links",
                f"threshold:{self.config.lexical_threshold}",
                f"model:{self.similarity.model_version}",
                "cluster_confidence_is_not_demand",
            ),
        )

    def _known_confidence(
        self,
        *,
        score: Decimal,
        basis: tuple[str, ...],
    ) -> SemanticConfidence:
        threshold = Decimal(self.config.lexical_threshold)
        if score >= Decimal("0.9"):
            level = SemanticConfidenceLevel.HIGH
        elif score >= threshold:
            level = SemanticConfidenceLevel.MEDIUM
        else:
            level = SemanticConfidenceLevel.LOW
        return SemanticConfidence(level=level, score=ratio_text(score), basis=basis)

    def _cluster_label(
        self,
        needs: tuple[BuyerNeedEvidence, ...],
        similarities: tuple[SemanticSimilarityEvidence, ...],
    ) -> str:
        normalized = {
            item.need_id: self.normalization_registry.normalize(item.need_label)
            for item in needs
        }
        canonical_keys = {item.canonical_key for item in normalized.values()}
        labels = {item.cluster_label for item in normalized.values()}
        if len(canonical_keys) == 1 and len(labels) == 1 and None not in labels:
            return next(iter(labels))  # type: ignore[arg-type]

        score_by_pair = {
            frozenset((item.source_need_id, item.target_need_id)): Decimal(item.score)
            for item in similarities
        }
        ranked = []
        for need in needs:
            total = sum(
                (
                    score_by_pair.get(frozenset((need.need_id, other.need_id)), Decimal("0"))
                    for other in needs
                    if other.need_id != need.need_id
                ),
                Decimal("0"),
            )
            ranked.append((-total, normalized[need.need_id].normalized_text, need.need_id))
        _, medoid_label, _ = min(ranked)
        rendered = medoid_label.title()
        return rendered if rendered.casefold().endswith(" need") else f"{rendered} Need"

    def _cluster_diagnostics(
        self,
        *,
        cluster_id: str,
        need_ids: tuple[str, ...],
        similarities: tuple[SemanticSimilarityEvidence, ...],
    ) -> tuple[SemanticClusterDiagnostic, ...]:
        if len(need_ids) < 3 or all(
            Decimal(item.score) >= Decimal(self.config.lexical_threshold)
            for item in similarities
        ):
            return ()
        payload = {
            "code": "TRANSITIVE_THRESHOLD_CLUSTER",
            "severity": Severity.INFO,
            "message": (
                "At least one member pair is below threshold; membership is explained by "
                "a transitive above-threshold path."
            ),
            "need_ids": need_ids,
            "cluster_id": cluster_id,
        }
        return (
            SemanticClusterDiagnostic(
                diagnostic_id=deterministic_id("semantic-cluster-diagnostic", payload),
                **payload,
            ),
        )

    @staticmethod
    def _result_diagnostics(
        unknown: tuple[BuyerNeedEvidence, ...],
    ) -> tuple[SemanticClusterDiagnostic, ...]:
        if not unknown:
            return ()
        need_ids = tuple(item.need_id for item in unknown)
        payload = {
            "code": "UNKNOWN_BUYER_NEED_EXCLUDED",
            "severity": Severity.INFO,
            "message": (
                "UNKNOWN Buyer Needs remain in source_needs and are excluded from semantic "
                "clustering without forced classification."
            ),
            "need_ids": need_ids,
            "cluster_id": None,
        }
        return (
            SemanticClusterDiagnostic(
                diagnostic_id=deterministic_id("semantic-cluster-diagnostic", payload),
                **payload,
            ),
        )


SemanticClusterBuilderV0_1 = SemanticClusterBuilder


__all__ = ("SemanticClusterBuilder", "SemanticClusterBuilderV0_1")
