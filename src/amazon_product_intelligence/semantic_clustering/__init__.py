"""Stable public API for Semantic Clustering V0.1."""

from .builder_v0_1 import SemanticClusterBuilder, SemanticClusterBuilderV0_1
from .embedding import SemanticEmbeddingProvider
from .errors import (
    SemanticClusteringError,
    SemanticClusteringSerializationError,
    SemanticClusteringValidationError,
)
from .models import (
    SEMANTIC_CLUSTERING_CONTRACT_VERSION,
    SEMANTIC_CLUSTERING_RULESET_VERSION,
    SemanticClusterDiagnostic,
    SemanticClusterMembership,
    SemanticClusterMethod,
    SemanticClusterSnapshot,
    SemanticClusteringConfig,
    SemanticClusteringResult,
    SemanticConfidence,
    SemanticConfidenceLevel,
    SemanticEmbeddingResult,
    SemanticSimilarityEvidence,
    SemanticSimilarityMethod,
    ratio_text,
    semantic_cluster_id,
)
from .rules import (
    SEMANTIC_NORMALIZATION_REGISTRY_V0_1,
    SEMANTIC_NORMALIZATION_RULE_VERSION,
    SemanticNormalizationRegistry,
    SemanticNormalizationResult,
    SemanticNormalizationRule,
    build_semantic_normalization_registry_v0_1,
    normalize_for_similarity,
)
from .similarity import RapidFuzzLexicalSimilarity

__all__ = (
    "SEMANTIC_CLUSTERING_CONTRACT_VERSION",
    "SEMANTIC_CLUSTERING_RULESET_VERSION",
    "SEMANTIC_NORMALIZATION_REGISTRY_V0_1",
    "SEMANTIC_NORMALIZATION_RULE_VERSION",
    "RapidFuzzLexicalSimilarity",
    "SemanticClusterBuilder",
    "SemanticClusterBuilderV0_1",
    "SemanticClusterDiagnostic",
    "SemanticClusterMembership",
    "SemanticClusterMethod",
    "SemanticClusterSnapshot",
    "SemanticClusteringConfig",
    "SemanticClusteringError",
    "SemanticClusteringResult",
    "SemanticClusteringSerializationError",
    "SemanticClusteringValidationError",
    "SemanticConfidence",
    "SemanticConfidenceLevel",
    "SemanticEmbeddingProvider",
    "SemanticEmbeddingResult",
    "SemanticNormalizationRegistry",
    "SemanticNormalizationResult",
    "SemanticNormalizationRule",
    "SemanticSimilarityEvidence",
    "SemanticSimilarityMethod",
    "build_semantic_normalization_registry_v0_1",
    "normalize_for_similarity",
    "ratio_text",
    "semantic_cluster_id",
)
