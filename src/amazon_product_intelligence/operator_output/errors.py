"""Operator Output Layer V0.1 error hierarchy."""

from __future__ import annotations


class OperatorOutputError(Exception):
    """Base error for the Operator Output Layer."""


class OperatorOutputValidationError(OperatorOutputError, ValueError):
    """Raised when operator output violates a V0.1 invariant."""


class OperatorOutputSerializationError(OperatorOutputValidationError):
    """Raised when strict Operator Output serialization fails."""


__all__ = (
    "OperatorOutputError",
    "OperatorOutputValidationError",
    "OperatorOutputSerializationError",
)
