"""Fail-closed public errors for SellerSprite local imports."""

from __future__ import annotations


class SellerSpriteImportError(ValueError):
    """An import failed without exposing source row scalar values."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


__all__ = ("SellerSpriteImportError",)
