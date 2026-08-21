"""Supply/Demand Gap Analysis V0.1 errors."""


class SupplyDemandGapError(ValueError):
    """Base error for Supply/Demand Gap contracts and classification."""


class SupplyDemandGapValidationError(SupplyDemandGapError):
    """Raised when a gap input or invariant is invalid."""


class SupplyDemandGapSerializationError(SupplyDemandGapError):
    """Raised when JSON-safe reconstruction fails."""


__all__ = (
    "SupplyDemandGapError",
    "SupplyDemandGapSerializationError",
    "SupplyDemandGapValidationError",
)
