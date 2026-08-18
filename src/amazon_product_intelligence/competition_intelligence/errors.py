"""Failure types for the Competition Intelligence V0.1 boundary."""

from __future__ import annotations


class CompetitionIntelligenceError(Exception):
    """Base class for Competition Intelligence failures."""


class CompetitionIntelligenceValidationError(CompetitionIntelligenceError, ValueError):
    """Raised when canonical evidence cannot safely form a competition evidence view."""


class CompetitionIdentityCollisionError(CompetitionIntelligenceValidationError):
    """Raised when one canonical identity is associated with different content."""


class CompetitionSerializationError(CompetitionIntelligenceValidationError):
    """Raised when serialized Competition Intelligence data is not strict or consistent."""


__all__ = (
    "CompetitionIntelligenceError",
    "CompetitionIntelligenceValidationError",
    "CompetitionIdentityCollisionError",
    "CompetitionSerializationError",
)
