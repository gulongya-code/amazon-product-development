"""Decision Framework V0.1 error hierarchy."""

from __future__ import annotations


class DecisionFrameworkError(Exception):
    """Base error for Decision Framework."""


class DecisionFrameworkValidationError(DecisionFrameworkError, ValueError):
    """Raised when decision evidence violates a V0.1 invariant."""


class DecisionFrameworkSerializationError(DecisionFrameworkValidationError):
    """Raised when strict Decision Framework serialization fails."""


__all__ = (
    "DecisionFrameworkError",
    "DecisionFrameworkValidationError",
    "DecisionFrameworkSerializationError",
)
