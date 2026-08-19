"""Competition Analysis V1 errors."""


class CompetitionAnalysisError(ValueError):
    """Base Competition Analysis error."""


class CompetitionAnalysisValidationError(CompetitionAnalysisError):
    """Raised when a Competition Analysis contract is invalid."""


__all__ = ("CompetitionAnalysisError", "CompetitionAnalysisValidationError")
