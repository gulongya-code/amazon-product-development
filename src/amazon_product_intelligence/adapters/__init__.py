"""Public provider adapter API V0.1."""

from .base import (
    ADAPTER_RULESET_VERSION,
    AdaptationContext,
    AdaptationResult,
    AdaptationStatistics,
    AdapterContextError,
    AdapterDiagnostic,
    AdapterError,
    AdapterFailure,
    AdapterFailureLevel,
    MappingDisposition,
    MappingSpecification,
    ProviderAdapter,
)
from .sorftime_v0_1 import SorftimeAdapterV0_1
from .xiyou_v0_1 import XiYouAdapterV0_1


__all__ = (
    "ADAPTER_RULESET_VERSION",
    "AdapterError",
    "AdapterContextError",
    "MappingDisposition",
    "AdapterFailureLevel",
    "MappingSpecification",
    "AdaptationContext",
    "AdapterDiagnostic",
    "AdapterFailure",
    "AdaptationStatistics",
    "AdaptationResult",
    "ProviderAdapter",
    "XiYouAdapterV0_1",
    "SorftimeAdapterV0_1",
)
