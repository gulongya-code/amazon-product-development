"""Failure types for the Product Intelligence V0.1 boundary."""

from __future__ import annotations


class ProductIntelligenceError(Exception):
    """Base class for Product Intelligence failures."""


class ProductIntelligenceValidationError(ProductIntelligenceError, ValueError):
    """Raised when evidence cannot safely form or validate a snapshot."""


class ProductSubjectNotFoundError(ProductIntelligenceValidationError):
    """Raised when the requested product has no direct canonical evidence."""


class ProductTopologyError(ProductIntelligenceValidationError):
    """Raised when target-connected confirmed variation evidence is invalid."""


class ProductIdentityCollisionError(ProductIntelligenceValidationError):
    """Raised when one canonical identity is associated with different content."""


class SnapshotSerializationError(ProductIntelligenceValidationError):
    """Raised when serialized snapshot data is not strict or self-consistent."""


__all__ = (
    "ProductIntelligenceError",
    "ProductIntelligenceValidationError",
    "ProductSubjectNotFoundError",
    "ProductTopologyError",
    "ProductIdentityCollisionError",
    "SnapshotSerializationError",
)
