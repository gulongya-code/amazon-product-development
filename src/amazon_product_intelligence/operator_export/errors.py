"""Operator Export Foundation V0.1 error hierarchy."""

from __future__ import annotations


class OperatorExportError(Exception):
    """Base error for Operator Export."""


class OperatorExportValidationError(OperatorExportError, ValueError):
    """Raised when export data violates a V0.1 invariant."""


class OperatorExportSerializationError(OperatorExportValidationError):
    """Raised when strict Operator Export serialization fails."""


__all__ = (
    "OperatorExportError",
    "OperatorExportValidationError",
    "OperatorExportSerializationError",
)
