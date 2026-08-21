"""Optional semantic embedding provider contract; no model implementation V0.1."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import SemanticEmbeddingResult


@runtime_checkable
class SemanticEmbeddingProvider(Protocol):
    """Adapter boundary for a future embedding implementation."""

    @property
    def provider(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    @property
    def model_version(self) -> str: ...

    def embed(self, normalized_text: str) -> SemanticEmbeddingResult: ...


__all__ = ("SemanticEmbeddingProvider",)
