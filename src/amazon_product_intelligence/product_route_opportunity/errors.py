"""Fail-closed errors for Product Route Opportunity V1.0."""


class ProductRouteOpportunityError(ValueError):
    """Raised when governed route discovery cannot safely continue."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


__all__ = ("ProductRouteOpportunityError",)
