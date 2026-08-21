"""Buyer Need Analysis errors V0.1."""


class BuyerNeedAnalysisError(ValueError):
    """Base error for Buyer Need Analysis operations."""


class BuyerNeedValidationError(BuyerNeedAnalysisError):
    """Raised when a Buyer Need contract violates an invariant."""


class BuyerNeedSerializationError(BuyerNeedAnalysisError):
    """Raised when strict Buyer Need deserialization fails."""


__all__ = (
    "BuyerNeedAnalysisError",
    "BuyerNeedValidationError",
    "BuyerNeedSerializationError",
)
