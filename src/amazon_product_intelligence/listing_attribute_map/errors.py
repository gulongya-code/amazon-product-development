"""Typed fail-closed errors for Product Attribute Map V1."""


class ListingAttributeMapError(ValueError):
    """Base error with a stable operator-facing code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class DetailedParameterParseError(ListingAttributeMapError):
    """Structured detailed-parameter input has the wrong outer type."""


class CategoryRulePackError(ListingAttributeMapError):
    """A CategoryRulePack is absent, invalid, or mismatched."""


__all__ = (
    "CategoryRulePackError",
    "DetailedParameterParseError",
    "ListingAttributeMapError",
)
