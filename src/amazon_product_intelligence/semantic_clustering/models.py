"""Immutable, evidence-first Semantic Clustering contracts V0.1."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
import math
from typing import Any, Mapping, Self

from amazon_product_intelligence.buyer_need_analysis import (
    BuyerNeedCandidateStatus,
    BuyerNeedEvidence,
    BuyerNeedType,
)
from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    Severity,
    deterministic_id,
)
from amazon_product_intelligence.normalization import normalize_keyword_text

from .errors import (
    SemanticClusteringSerializationError,
    SemanticClusteringValidationError,
)


SEMANTIC_CLUSTERING_CONTRACT_VERSION = "semantic-clustering-contract-v0.1"
SEMANTIC_CLUSTERING_RULESET_VERSION = "semantic-normalization-rules-v0.1"


class SemanticSimilarityMethod(StrEnum):
    LEXICAL = "LEXICAL"
    SEMANTIC = "SEMANTIC"


class SemanticClusterMethod(StrEnum):
    LEXICAL_THRESHOLD = "LEXICAL_THRESHOLD"
    SEMANTIC_THRESHOLD = "SEMANTIC_THRESHOLD"


class SemanticConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise SemanticClusteringValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _tuple(value: Sequence[Any], path: str) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise SemanticClusteringValidationError(f"{path} must be a sequence")
    return tuple(value)


def _ratio(value: str, path: str) -> Decimal:
    if type(value) is not str or not value.strip():
        raise SemanticClusteringValidationError(f"{path} must be decimal ratio text")
    try:
        ratio = Decimal(value)
    except InvalidOperation as exc:
        raise SemanticClusteringValidationError(
            f"{path} must be decimal ratio text"
        ) from exc
    if not ratio.is_finite() or ratio < 0 or ratio > 1:
        raise SemanticClusteringValidationError(f"{path} must be between zero and one")
    return ratio


def ratio_text(value: Decimal | float | int) -> str:
    """Render a finite [0, 1] score as stable JSON-safe decimal text."""

    try:
        ratio = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise SemanticClusteringValidationError("score must be numeric") from exc
    if not ratio.is_finite() or ratio < 0 or ratio > 1:
        raise SemanticClusteringValidationError("score must be between zero and one")
    rendered = format(ratio.quantize(Decimal("0.000001")), "f")
    rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def _identity(prefix: str, model: JsonContract, field_name: str) -> str:
    payload = model.to_dict()
    payload.pop(field_name)
    return deterministic_id(prefix, payload)


def semantic_cluster_id(
    *,
    source_need_ids: Sequence[str],
    cluster_method: SemanticClusterMethod,
    model_version: str,
    threshold: str,
    normalization_rule_version: str,
) -> str:
    """Build cluster identity without creating a membership/cluster ID cycle."""

    return deterministic_id(
        "semantic-cluster",
        {
            "source_need_ids": tuple(sorted(source_need_ids)),
            "cluster_method": cluster_method,
            "model_version": model_version,
            "threshold": threshold,
            "normalization_rule_version": normalization_rule_version,
        },
    )


class _SemanticClusteringModel(JsonContract):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except SemanticClusteringValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise SemanticClusteringSerializationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticClusteringConfig(_SemanticClusteringModel):
    lexical_threshold: str = "0.84"
    ruleset_version: str = SEMANTIC_CLUSTERING_RULESET_VERSION

    def __post_init__(self) -> None:
        _ratio(self.lexical_threshold, "SemanticClusteringConfig.lexical_threshold")
        _text(self.ruleset_version, "SemanticClusteringConfig.ruleset_version")


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticConfidence(_SemanticClusteringModel):
    level: SemanticConfidenceLevel
    score: str | None
    basis: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.level, SemanticConfidenceLevel):
            raise SemanticClusteringValidationError("semantic confidence level is invalid")
        if self.score is not None:
            _ratio(self.score, "SemanticConfidence.score")
        basis = _tuple(self.basis, "SemanticConfidence.basis")
        if not basis or any(type(item) is not str or not item.strip() for item in basis):
            raise SemanticClusteringValidationError(
                "semantic confidence requires an explicit textual basis"
            )
        if len(set(basis)) != len(basis):
            raise SemanticClusteringValidationError("confidence basis must be unique")
        if self.level is SemanticConfidenceLevel.UNKNOWN and self.score is not None:
            raise SemanticClusteringValidationError("UNKNOWN confidence cannot claim a score")
        if self.level is not SemanticConfidenceLevel.UNKNOWN and self.score is None:
            raise SemanticClusteringValidationError("known confidence requires a score")
        object.__setattr__(self, "basis", tuple(sorted(basis)))


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticClusterDiagnostic(_SemanticClusteringModel):
    diagnostic_id: str
    code: str
    severity: Severity
    message: str
    need_ids: tuple[str, ...]
    cluster_id: str | None

    def __post_init__(self) -> None:
        _text(self.code, "SemanticClusterDiagnostic.code")
        if not isinstance(self.severity, Severity):
            raise SemanticClusteringValidationError("diagnostic severity is invalid")
        _text(self.message, "SemanticClusterDiagnostic.message")
        _optional_text(self.cluster_id, "SemanticClusterDiagnostic.cluster_id")
        need_ids = _tuple(self.need_ids, "SemanticClusterDiagnostic.need_ids")
        if any(type(item) is not str or not item.strip() for item in need_ids):
            raise SemanticClusteringValidationError("diagnostic need_ids require text")
        if len(set(need_ids)) != len(need_ids):
            raise SemanticClusteringValidationError("diagnostic need_ids must be unique")
        object.__setattr__(self, "need_ids", tuple(sorted(need_ids)))
        if self.diagnostic_id != _identity(
            "semantic-cluster-diagnostic", self, "diagnostic_id"
        ):
            raise SemanticClusteringValidationError(
                "diagnostic_id does not match diagnostic content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticSimilarityEvidence(_SemanticClusteringModel):
    similarity_id: str
    source_need_id: str
    target_need_id: str
    method: SemanticSimilarityMethod
    score: str
    model_version: str
    evidence_reference: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.source_need_id, "SemanticSimilarityEvidence.source_need_id")
        _text(self.target_need_id, "SemanticSimilarityEvidence.target_need_id")
        if self.source_need_id >= self.target_need_id:
            raise SemanticClusteringValidationError(
                "similarity pair must contain two distinct, canonically ordered need ids"
            )
        if not isinstance(self.method, SemanticSimilarityMethod):
            raise SemanticClusteringValidationError("similarity method is invalid")
        _ratio(self.score, "SemanticSimilarityEvidence.score")
        _text(self.model_version, "SemanticSimilarityEvidence.model_version")
        references = _tuple(
            self.evidence_reference,
            "SemanticSimilarityEvidence.evidence_reference",
        )
        if not references or any(
            type(item) is not str or not item.strip() for item in references
        ):
            raise SemanticClusteringValidationError(
                "similarity evidence requires source evidence references"
            )
        if len(set(references)) != len(references):
            raise SemanticClusteringValidationError(
                "similarity evidence references must be unique"
            )
        object.__setattr__(self, "evidence_reference", tuple(sorted(references)))
        if self.similarity_id != _identity(
            "semantic-similarity", self, "similarity_id"
        ):
            raise SemanticClusteringValidationError(
                "similarity_id does not match similarity evidence content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticClusterMembership(_SemanticClusteringModel):
    membership_id: str
    cluster_id: str
    need_id: str
    similarity_score: str
    confidence: SemanticConfidence
    evidence_reference: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.cluster_id, "SemanticClusterMembership.cluster_id")
        _text(self.need_id, "SemanticClusterMembership.need_id")
        _ratio(self.similarity_score, "SemanticClusterMembership.similarity_score")
        if not isinstance(self.confidence, SemanticConfidence):
            raise SemanticClusteringValidationError("membership confidence has a wrong type")
        references = _tuple(
            self.evidence_reference,
            "SemanticClusterMembership.evidence_reference",
        )
        if not references or any(
            type(item) is not str or not item.strip() for item in references
        ):
            raise SemanticClusteringValidationError(
                "cluster membership requires Buyer Need evidence references"
            )
        if len(set(references)) != len(references):
            raise SemanticClusteringValidationError(
                "membership evidence references must be unique"
            )
        object.__setattr__(self, "evidence_reference", tuple(sorted(references)))
        if self.membership_id != _identity(
            "semantic-cluster-membership", self, "membership_id"
        ):
            raise SemanticClusteringValidationError(
                "membership_id does not match membership content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticClusterSnapshot(_SemanticClusteringModel):
    cluster_id: str
    cluster_label: str
    cluster_members: tuple[SemanticClusterMembership, ...]
    source_need_ids: tuple[str, ...]
    cluster_method: SemanticClusterMethod
    model_version: str
    confidence: SemanticConfidence
    evidence_count: int
    diagnostics: tuple[SemanticClusterDiagnostic, ...]
    threshold: str
    normalization_rule_version: str
    source_needs: tuple[BuyerNeedEvidence, ...]
    similarity_evidence: tuple[SemanticSimilarityEvidence, ...]

    def __post_init__(self) -> None:
        _text(self.cluster_label, "SemanticClusterSnapshot.cluster_label")
        if not isinstance(self.cluster_method, SemanticClusterMethod):
            raise SemanticClusteringValidationError("cluster method is invalid")
        _text(self.model_version, "SemanticClusterSnapshot.model_version")
        if not isinstance(self.confidence, SemanticConfidence):
            raise SemanticClusteringValidationError("cluster confidence has a wrong type")
        if type(self.evidence_count) is not int or self.evidence_count <= 0:
            raise SemanticClusteringValidationError("evidence_count must be a positive integer")
        _ratio(self.threshold, "SemanticClusterSnapshot.threshold")
        _text(
            self.normalization_rule_version,
            "SemanticClusterSnapshot.normalization_rule_version",
        )

        source_needs = _tuple(self.source_needs, "SemanticClusterSnapshot.source_needs")
        if not source_needs or any(
            not isinstance(item, BuyerNeedEvidence) for item in source_needs
        ):
            raise SemanticClusteringValidationError(
                "cluster requires source BuyerNeedEvidence records"
            )
        if any(
            item.status is BuyerNeedCandidateStatus.UNKNOWN
            or item.need_type is BuyerNeedType.UNKNOWN
            for item in source_needs
        ):
            raise SemanticClusteringValidationError("UNKNOWN Buyer Need cannot enter a cluster")
        if len({item.need_id for item in source_needs}) != len(source_needs):
            raise SemanticClusteringValidationError("cluster source needs must be unique")
        source_needs = tuple(sorted(source_needs, key=lambda item: item.need_id))
        expected_need_ids = tuple(item.need_id for item in source_needs)

        source_need_ids = _tuple(
            self.source_need_ids,
            "SemanticClusterSnapshot.source_need_ids",
        )
        if tuple(sorted(source_need_ids)) != expected_need_ids:
            raise SemanticClusteringValidationError(
                "source_need_ids must exactly identify embedded source needs"
            )

        members = _tuple(
            self.cluster_members,
            "SemanticClusterSnapshot.cluster_members",
        )
        if not members or any(
            not isinstance(item, SemanticClusterMembership) for item in members
        ):
            raise SemanticClusteringValidationError("cluster requires memberships")
        if len({item.membership_id for item in members}) != len(members):
            raise SemanticClusteringValidationError("cluster memberships must be unique")
        if {item.need_id for item in members} != set(expected_need_ids):
            raise SemanticClusteringValidationError(
                "cluster memberships must exactly cover source_need_ids"
            )
        if any(item.cluster_id != self.cluster_id for item in members):
            raise SemanticClusteringValidationError("membership cluster_id mismatch")

        similarities = _tuple(
            self.similarity_evidence,
            "SemanticClusterSnapshot.similarity_evidence",
        )
        if any(not isinstance(item, SemanticSimilarityEvidence) for item in similarities):
            raise SemanticClusteringValidationError(
                "cluster similarity evidence contains a wrong type"
            )
        if len({item.similarity_id for item in similarities}) != len(similarities):
            raise SemanticClusteringValidationError("cluster similarity evidence must be unique")
        if any(
            item.source_need_id not in expected_need_ids
            or item.target_need_id not in expected_need_ids
            for item in similarities
        ):
            raise SemanticClusteringValidationError(
                "cluster similarity evidence must reference cluster members"
            )

        diagnostics = _tuple(
            self.diagnostics,
            "SemanticClusterSnapshot.diagnostics",
        )
        if any(not isinstance(item, SemanticClusterDiagnostic) for item in diagnostics):
            raise SemanticClusteringValidationError("cluster diagnostics contain a wrong type")
        if len({item.diagnostic_id for item in diagnostics}) != len(diagnostics):
            raise SemanticClusteringValidationError("cluster diagnostics must be unique")
        if any(item.cluster_id not in {None, self.cluster_id} for item in diagnostics):
            raise SemanticClusteringValidationError("cluster diagnostic cluster_id mismatch")

        evidence_ids = {
            evidence.text_id
            for need in source_needs
            for evidence in need.source_evidence
        }
        if self.evidence_count != len(evidence_ids):
            raise SemanticClusteringValidationError(
                "evidence_count must equal unique embedded Buyer Need evidence count"
            )
        if any(
            not set(item.evidence_reference).issubset(evidence_ids)
            for item in members + similarities
        ):
            raise SemanticClusteringValidationError(
                "cluster references evidence not embedded in source Buyer Needs"
            )

        object.__setattr__(self, "source_needs", source_needs)
        object.__setattr__(self, "source_need_ids", expected_need_ids)
        object.__setattr__(
            self,
            "cluster_members",
            tuple(sorted(members, key=lambda item: item.need_id)),
        )
        object.__setattr__(
            self,
            "similarity_evidence",
            tuple(sorted(similarities, key=lambda item: item.similarity_id)),
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
        )
        expected_cluster_id = semantic_cluster_id(
            source_need_ids=expected_need_ids,
            cluster_method=self.cluster_method,
            model_version=self.model_version,
            threshold=self.threshold,
            normalization_rule_version=self.normalization_rule_version,
        )
        if self.cluster_id != expected_cluster_id:
            raise SemanticClusteringValidationError(
                "cluster_id does not match cluster identity inputs"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticClusteringResult(_SemanticClusteringModel):
    result_id: str
    clusters: tuple[SemanticClusterSnapshot, ...]
    source_needs: tuple[BuyerNeedEvidence, ...]
    similarity_evidence: tuple[SemanticSimilarityEvidence, ...]
    excluded_unknown_need_ids: tuple[str, ...]
    config: SemanticClusteringConfig
    diagnostics: tuple[SemanticClusterDiagnostic, ...]
    contract_version: str = SEMANTIC_CLUSTERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _text(self.contract_version, "SemanticClusteringResult.contract_version")
        if self.contract_version != SEMANTIC_CLUSTERING_CONTRACT_VERSION:
            raise SemanticClusteringValidationError("semantic clustering contract version mismatch")
        if not isinstance(self.config, SemanticClusteringConfig):
            raise SemanticClusteringValidationError("clustering config has a wrong type")
        source_needs = _tuple(self.source_needs, "SemanticClusteringResult.source_needs")
        if any(not isinstance(item, BuyerNeedEvidence) for item in source_needs):
            raise SemanticClusteringValidationError("result source needs contain a wrong type")
        if len({item.need_id for item in source_needs}) != len(source_needs):
            raise SemanticClusteringValidationError("result source needs must be unique")
        source_needs = tuple(sorted(source_needs, key=lambda item: item.need_id))
        all_ids = {item.need_id for item in source_needs}
        expected_unknown_ids = tuple(
            item.need_id
            for item in source_needs
            if item.status is BuyerNeedCandidateStatus.UNKNOWN
            or item.need_type is BuyerNeedType.UNKNOWN
        )
        excluded = tuple(
            sorted(
                _tuple(
                    self.excluded_unknown_need_ids,
                    "SemanticClusteringResult.excluded_unknown_need_ids",
                )
            )
        )
        if excluded != expected_unknown_ids:
            raise SemanticClusteringValidationError(
                "excluded_unknown_need_ids must exactly preserve UNKNOWN source needs"
            )

        clusters = _tuple(self.clusters, "SemanticClusteringResult.clusters")
        if any(not isinstance(item, SemanticClusterSnapshot) for item in clusters):
            raise SemanticClusteringValidationError("result clusters contain a wrong type")
        if len({item.cluster_id for item in clusters}) != len(clusters):
            raise SemanticClusteringValidationError("result cluster ids must be unique")
        clustered_ids = [need_id for item in clusters for need_id in item.source_need_ids]
        eligible_ids = all_ids - set(excluded)
        if len(clustered_ids) != len(set(clustered_ids)) or set(clustered_ids) != eligible_ids:
            raise SemanticClusteringValidationError(
                "clusters must cover each non-UNKNOWN source need exactly once"
            )
        source_by_id = {item.need_id: item for item in source_needs}
        if any(
            source_by_id[need.need_id] != need
            for cluster in clusters
            for need in cluster.source_needs
        ):
            raise SemanticClusteringValidationError(
                "cluster source needs must be the original result inputs"
            )

        similarities = _tuple(
            self.similarity_evidence,
            "SemanticClusteringResult.similarity_evidence",
        )
        if any(not isinstance(item, SemanticSimilarityEvidence) for item in similarities):
            raise SemanticClusteringValidationError("result similarity evidence has a wrong type")
        if len({item.similarity_id for item in similarities}) != len(similarities):
            raise SemanticClusteringValidationError("result similarity evidence must be unique")
        if any(
            item.source_need_id not in eligible_ids or item.target_need_id not in eligible_ids
            for item in similarities
        ):
            raise SemanticClusteringValidationError(
                "similarity evidence cannot reference UNKNOWN or absent needs"
            )

        diagnostics = _tuple(self.diagnostics, "SemanticClusteringResult.diagnostics")
        if any(not isinstance(item, SemanticClusterDiagnostic) for item in diagnostics):
            raise SemanticClusteringValidationError("result diagnostics contain a wrong type")
        if len({item.diagnostic_id for item in diagnostics}) != len(diagnostics):
            raise SemanticClusteringValidationError("result diagnostics must be unique")

        object.__setattr__(self, "source_needs", source_needs)
        object.__setattr__(self, "excluded_unknown_need_ids", excluded)
        object.__setattr__(
            self,
            "clusters",
            tuple(sorted(clusters, key=lambda item: item.cluster_id)),
        )
        object.__setattr__(
            self,
            "similarity_evidence",
            tuple(sorted(similarities, key=lambda item: item.similarity_id)),
        )
        object.__setattr__(
            self,
            "diagnostics",
            tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
        )
        if self.result_id != _identity("semantic-clustering-result", self, "result_id"):
            raise SemanticClusteringValidationError(
                "result_id does not match clustering result content"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SemanticEmbeddingResult(_SemanticClusteringModel):
    normalized_text: str
    vector: tuple[float, ...]
    provider: str
    model_name: str
    model_version: str

    def __post_init__(self) -> None:
        _text(self.normalized_text, "SemanticEmbeddingResult.normalized_text")
        if normalize_keyword_text(self.normalized_text) != self.normalized_text:
            raise SemanticClusteringValidationError(
                "embedding input must already use canonical text normalization"
            )
        vector = _tuple(self.vector, "SemanticEmbeddingResult.vector")
        if not vector or any(type(item) is not float or not math.isfinite(item) for item in vector):
            raise SemanticClusteringValidationError(
                "embedding vector requires finite float values"
            )
        _text(self.provider, "SemanticEmbeddingResult.provider")
        _text(self.model_name, "SemanticEmbeddingResult.model_name")
        _text(self.model_version, "SemanticEmbeddingResult.model_version")
        object.__setattr__(self, "vector", vector)


__all__ = (
    "SEMANTIC_CLUSTERING_CONTRACT_VERSION",
    "SEMANTIC_CLUSTERING_RULESET_VERSION",
    "SemanticClusterDiagnostic",
    "SemanticClusterMembership",
    "SemanticClusterMethod",
    "SemanticClusterSnapshot",
    "SemanticClusteringConfig",
    "SemanticClusteringResult",
    "SemanticConfidence",
    "SemanticConfidenceLevel",
    "SemanticEmbeddingResult",
    "SemanticSimilarityEvidence",
    "SemanticSimilarityMethod",
    "ratio_text",
    "semantic_cluster_id",
)
