"""Errors raised by the Operator Template Contract V1."""


class OperatorTemplateContractError(Exception):
    """Base exception for template-contract operations."""


class OperatorTemplateContractValidationError(
    OperatorTemplateContractError, ValueError
):
    """Raised when a template contract or workbook fails closed."""


__all__ = (
    "OperatorTemplateContractError",
    "OperatorTemplateContractValidationError",
)
