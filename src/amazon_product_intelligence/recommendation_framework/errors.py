"""Recommendation Framework V0.1 error hierarchy."""

from __future__ import annotations


class RecommendationFrameworkError(Exception):
    """Base error for Recommendation Framework."""


class RecommendationFrameworkValidationError(
    RecommendationFrameworkError, ValueError
):
    """Raised when recommendation evidence violates a V0.1 invariant."""


class RecommendationFrameworkSerializationError(
    RecommendationFrameworkValidationError
):
    """Raised when strict Recommendation Framework serialization fails."""


__all__ = (
    "RecommendationFrameworkError",
    "RecommendationFrameworkValidationError",
    "RecommendationFrameworkSerializationError",
)
