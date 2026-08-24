"""Isolated SP-039B foundation for Market Report V0.2 contracts.

This package intentionally contains no top-level report, renderer, delivery, or
production-pipeline integration.
"""

from . import adapters, models
from .version import (
    COMPETITOR_STRUCTURE_CONTRACT_VERSION,
    MARKET_REPORT_V0_2_FOUNDATION_VERSION,
    MARKET_REPORT_V0_2_VERSION,
    MARKET_SIZE_CONTRACT_VERSION,
    METRIC_CONTEXT_CONTRACT_VERSION,
    SCOPE_CONTEXT_CONTRACT_VERSION,
    TRUE_COMPETITOR_SET_CONTRACT_VERSION,
)

__all__ = (
    "COMPETITOR_STRUCTURE_CONTRACT_VERSION",
    "MARKET_REPORT_V0_2_FOUNDATION_VERSION",
    "MARKET_REPORT_V0_2_VERSION",
    "MARKET_SIZE_CONTRACT_VERSION",
    "METRIC_CONTEXT_CONTRACT_VERSION",
    "SCOPE_CONTEXT_CONTRACT_VERSION",
    "TRUE_COMPETITOR_SET_CONTRACT_VERSION",
    "adapters",
    "models",
)
