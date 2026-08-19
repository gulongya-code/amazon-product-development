"""Public pluggable Provider Connector Foundation V0.1."""

from .base import AdapterBackedProvider, DataProvider
from .errors import ProviderConnectorError, ProviderErrorCode
from .models import (
    CanonicalSelector,
    CapabilityStatus,
    ProviderCapability,
    ProviderConfig,
    ProviderFetchResult,
    ProviderFetchStatus,
    ProviderRequest,
)
from .registry import ProviderCandidate, ProviderRegistry, build_registry
from .resolver import (
    ProviderAttempt,
    ProviderAttemptStatus,
    ProviderResolution,
    ProviderResolver,
)
from .sorftime_v0_1 import SORFTIME_CAPABILITIES, SORFTIME_OPERATIONS, SorftimeProvider
from .transport import (
    BoundedTransientRetryPolicy,
    HttpJsonTransport,
    NoRetryPolicy,
    ProviderCredential,
    ProviderOperation,
    ProviderTransport,
    RetryPolicy,
    TransportRequest,
    TransportResponse,
)
from .xiyou_v0_1 import XIYOU_CAPABILITIES, XIYOU_OPERATIONS, XiYouProvider


__all__ = (
    "AdapterBackedProvider",
    "BoundedTransientRetryPolicy",
    "CanonicalSelector",
    "CapabilityStatus",
    "DataProvider",
    "HttpJsonTransport",
    "NoRetryPolicy",
    "ProviderAttempt",
    "ProviderAttemptStatus",
    "ProviderCandidate",
    "ProviderCapability",
    "ProviderConfig",
    "ProviderConnectorError",
    "ProviderCredential",
    "ProviderErrorCode",
    "ProviderFetchResult",
    "ProviderFetchStatus",
    "ProviderOperation",
    "ProviderRegistry",
    "ProviderRequest",
    "ProviderResolution",
    "ProviderResolver",
    "ProviderTransport",
    "RetryPolicy",
    "SORFTIME_CAPABILITIES",
    "SORFTIME_OPERATIONS",
    "SorftimeProvider",
    "TransportRequest",
    "TransportResponse",
    "XIYOU_CAPABILITIES",
    "XIYOU_OPERATIONS",
    "XiYouProvider",
    "build_registry",
)
