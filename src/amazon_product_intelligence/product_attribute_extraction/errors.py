"""Errors raised by Product Attribute Extraction contracts V0.1."""


class ProductAttributeContractError(ValueError):
    """Raised when an attribute contract violates a V0.1 invariant."""


class ProductAttributeSerializationError(ProductAttributeContractError):
    """Raised when strict attribute-contract deserialization fails."""


class AttributeEvidenceValidationError(ProductAttributeContractError):
    """Raised when an attribute evidence reference cannot be replayed."""


class AttributeTaxonomyValidationError(ProductAttributeContractError):
    """Raised when a profile or registry violates its taxonomy contract."""


__all__ = (
    "ProductAttributeContractError",
    "ProductAttributeSerializationError",
    "AttributeEvidenceValidationError",
    "AttributeTaxonomyValidationError",
)
