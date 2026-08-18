"""Opportunity Intelligence V0.1 error hierarchy."""

from __future__ import annotations


class OpportunityIntelligenceError(Exception):
    """Base error for Opportunity Intelligence."""


class OpportunityValidationError(OpportunityIntelligenceError, ValueError):
    """Raised when opportunity evidence violates a V0.1 invariant."""


class OpportunitySerializationError(OpportunityValidationError):
    """Raised when strict Opportunity serialization fails."""


class OpportunityIdentityCollisionError(OpportunityValidationError):
    """Raised when one canonical identity carries conflicting content."""


__all__ = (
    "OpportunityIntelligenceError",
    "OpportunityValidationError",
    "OpportunitySerializationError",
    "OpportunityIdentityCollisionError",
)
