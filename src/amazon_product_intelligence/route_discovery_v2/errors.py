"""Route Discovery V2 domain errors."""

from __future__ import annotations


class RouteDiscoveryV2Error(ValueError):
    """A stable-code error raised at a governed Route V2 boundary."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


__all__ = ("RouteDiscoveryV2Error",)
