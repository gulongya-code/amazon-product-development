"""Opportunity Scoring Framework V0.1 error hierarchy."""

from __future__ import annotations


class OpportunityScoringError(Exception):
    """Base error for Opportunity Scoring Framework."""


class OpportunityScoringValidationError(OpportunityScoringError, ValueError):
    """Raised when score evidence violates a V0.1 invariant."""


class OpportunityScoringSerializationError(OpportunityScoringValidationError):
    """Raised when strict Opportunity Scoring serialization fails."""


__all__ = (
    "OpportunityScoringError",
    "OpportunityScoringValidationError",
    "OpportunityScoringSerializationError",
)
