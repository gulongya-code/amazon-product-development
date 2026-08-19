"""Stable business-facing errors for Calculation Engine Foundation V0.1."""


class CalculationError(ValueError):
    """Base error for calculation contracts, planning, and evaluation."""


class DuplicateCalculatedFieldError(CalculationError):
    """Raised when a field is registered more than once."""


class UnknownCalculatedFieldError(CalculationError):
    """Raised when a requested calculated field is not registered."""


class UnknownCalculationDependencyError(CalculationError):
    """Raised when a calculated dependency is not registered."""


class CalculationDependencyCycleError(CalculationError):
    """Raised when the calculated-field graph contains a cycle."""


class InvalidCalculationInputError(CalculationError):
    """Raised when an input violates the explicit calculation contract."""


class CalculationEvaluationError(CalculationError):
    """Base error intentionally raised by a calculation function."""


class CalculationDivisionByZeroError(CalculationEvaluationError):
    """Raised when a declared ratio has a zero denominator."""


class CalculationUnitMismatchError(CalculationEvaluationError):
    """Raised when input units are incompatible."""


class CalculationCurrencyMismatchError(CalculationEvaluationError):
    """Raised when monetary inputs use incompatible currencies."""


__all__ = (
    "CalculationCurrencyMismatchError",
    "CalculationDependencyCycleError",
    "CalculationDivisionByZeroError",
    "CalculationError",
    "CalculationEvaluationError",
    "CalculationUnitMismatchError",
    "DuplicateCalculatedFieldError",
    "InvalidCalculationInputError",
    "UnknownCalculatedFieldError",
    "UnknownCalculationDependencyError",
)
