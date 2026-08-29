"""Fail-closed errors for Semantic Engine V2."""


class SemanticEngineV2Error(ValueError):
    """Raised when semantic evidence or profile contracts are unsafe."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


__all__ = ("SemanticEngineV2Error",)
