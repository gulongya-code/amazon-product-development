"""Conflict Resolution Foundation V0.1 error hierarchy."""

from __future__ import annotations


class ConflictResolutionError(Exception):
    """Base error for Conflict Resolution."""


class ConflictValidationError(ConflictResolutionError, ValueError):
    """Raised when conflict-resolution evidence violates a V0.1 invariant."""


class ConflictSerializationError(ConflictValidationError):
    """Raised when strict Conflict Resolution serialization fails."""


__all__ = (
    "ConflictResolutionError",
    "ConflictValidationError",
    "ConflictSerializationError",
)
