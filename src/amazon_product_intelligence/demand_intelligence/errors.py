"""Failure types for the Demand Intelligence V0.1 boundary."""

from __future__ import annotations


class DemandIntelligenceError(Exception):
    """Base class for Demand Intelligence failures."""


class DemandIntelligenceValidationError(DemandIntelligenceError, ValueError):
    """Raised when canonical evidence cannot safely form a demand snapshot."""


class DemandSubjectNotFoundError(DemandIntelligenceValidationError):
    """Raised when the requested keyword has no exact canonical evidence."""


class DemandIdentityCollisionError(DemandIntelligenceValidationError):
    """Raised when one canonical identity is associated with different content."""


class DemandSerializationError(DemandIntelligenceValidationError):
    """Raised when serialized Demand Intelligence data is not strict or consistent."""


__all__ = (
    "DemandIntelligenceError",
    "DemandIntelligenceValidationError",
    "DemandSubjectNotFoundError",
    "DemandIdentityCollisionError",
    "DemandSerializationError",
)
