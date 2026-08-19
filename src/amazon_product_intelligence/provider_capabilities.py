"""Provider-neutral capability vocabulary shared across pipeline stages."""

from enum import StrEnum


class CapabilityStatus(StrEnum):
    """Provider API capability; CALCULATED intentionally does not exist."""

    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"
    UNKNOWN = "UNKNOWN"


__all__ = ("CapabilityStatus",)
