"""Category Product Map errors V0.1."""


class CategoryProductMapError(ValueError):
    """Base error for Category Product Map operations."""


class CategoryProductMapValidationError(CategoryProductMapError):
    """Raised when a map contract or request violates an invariant."""


class CategoryProductMapSerializationError(CategoryProductMapError):
    """Raised when strict map deserialization fails."""


__all__ = (
    "CategoryProductMapError",
    "CategoryProductMapValidationError",
    "CategoryProductMapSerializationError",
)
