"""Semantic Clustering errors V0.1."""


class SemanticClusteringError(ValueError):
    """Base error for Semantic Clustering operations."""


class SemanticClusteringValidationError(SemanticClusteringError):
    """Raised when a Semantic Clustering contract violates an invariant."""


class SemanticClusteringSerializationError(SemanticClusteringError):
    """Raised when strict Semantic Clustering deserialization fails."""


__all__ = (
    "SemanticClusteringError",
    "SemanticClusteringSerializationError",
    "SemanticClusteringValidationError",
)
