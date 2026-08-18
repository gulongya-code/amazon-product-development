"""Evidence Evaluation Foundation V0.1 error hierarchy."""

from __future__ import annotations


class EvidenceEvaluationError(Exception):
    """Base error for Evidence Evaluation."""


class EvidenceValidationError(EvidenceEvaluationError, ValueError):
    """Raised when evidence evaluation violates a V0.1 invariant."""


class EvidenceSerializationError(EvidenceValidationError):
    """Raised when strict Evidence Evaluation serialization fails."""


__all__ = (
    "EvidenceEvaluationError",
    "EvidenceValidationError",
    "EvidenceSerializationError",
)
