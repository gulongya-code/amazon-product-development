"""Evidence Policy Framework V0.1 error hierarchy."""

from __future__ import annotations


class EvidencePolicyError(Exception):
    """Base error for Evidence Policy."""


class EvidencePolicyValidationError(EvidencePolicyError, ValueError):
    """Raised when policy evidence violates a V0.1 invariant."""


class EvidencePolicySerializationError(EvidencePolicyValidationError):
    """Raised when strict Evidence Policy serialization fails."""


__all__ = (
    "EvidencePolicyError",
    "EvidencePolicyValidationError",
    "EvidencePolicySerializationError",
)
