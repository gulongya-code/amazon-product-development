"""Buyer Need Map errors V0.1."""


class BuyerNeedMapError(ValueError):
    """Base error for Buyer Need Map operations."""


class BuyerNeedMapValidationError(BuyerNeedMapError):
    """Raised when a Buyer Need Map contract violates an invariant."""


class BuyerNeedMapSerializationError(BuyerNeedMapError):
    """Raised when strict Buyer Need Map deserialization fails."""


__all__ = (
    "BuyerNeedMapError",
    "BuyerNeedMapSerializationError",
    "BuyerNeedMapValidationError",
)
