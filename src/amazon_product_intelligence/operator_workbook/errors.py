"""Errors raised by Operator Workbook V0.2."""


class OperatorWorkbookError(Exception):
    """Base error for the workbook presentation boundary."""


class OperatorWorkbookValidationError(OperatorWorkbookError):
    """Raised when workbook input or output violates the V0.2 contract."""


class OperatorWorkbookSerializationError(OperatorWorkbookError):
    """Raised when strict workbook contract reconstruction fails."""


__all__ = (
    "OperatorWorkbookError",
    "OperatorWorkbookSerializationError",
    "OperatorWorkbookValidationError",
)
