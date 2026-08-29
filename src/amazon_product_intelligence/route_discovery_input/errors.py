"""Stable failures for the provider-neutral Route Discovery input boundary."""

from __future__ import annotations


class RouteDiscoveryInputError(ValueError):
    """Fail-closed boundary error with a machine-readable code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


__all__ = ("RouteDiscoveryInputError",)
