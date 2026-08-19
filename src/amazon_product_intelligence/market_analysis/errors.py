"""Controlled errors for Market Analysis V1."""


class MarketAnalysisError(Exception):
    """Base error for the Provider-neutral market-analysis boundary."""


class MarketAnalysisValidationError(MarketAnalysisError, ValueError):
    """Raised when clean inputs or result contracts violate the V1 boundary."""


__all__ = ("MarketAnalysisError", "MarketAnalysisValidationError")
