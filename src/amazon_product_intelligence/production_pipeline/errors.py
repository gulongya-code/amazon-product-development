"""Typed, credential-safe failures for the production pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping


class ProductionPipelineErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    PROVIDER_FAILURE = "PROVIDER_FAILURE"
    INTELLIGENCE_FAILURE = "INTELLIGENCE_FAILURE"
    SCHEMA_VALIDATION_FAILURE = "SCHEMA_VALIDATION_FAILURE"
    DELIVERY_FAILURE = "DELIVERY_FAILURE"
    INTERNAL_FAILURE = "INTERNAL_FAILURE"


class ProductionPipelineError(RuntimeError):
    """One stable failure boundary; details must remain secret-free."""

    def __init__(
        self,
        code: ProductionPipelineErrorCode,
        message: str,
        *,
        stage: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.details = dict(details or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": str(self),
            "stage": self.stage,
            "details": dict(self.details),
        }


class ProductionRunValidationError(ProductionPipelineError):
    def __init__(self, message: str) -> None:
        super().__init__(ProductionPipelineErrorCode.INVALID_INPUT, message, stage="input_validation")


class UnsupportedCapabilityError(ProductionPipelineError):
    def __init__(self, message: str) -> None:
        super().__init__(
            ProductionPipelineErrorCode.UNSUPPORTED_CAPABILITY,
            message,
            stage="input_validation",
        )


__all__ = (
    "ProductionPipelineError",
    "ProductionPipelineErrorCode",
    "ProductionRunValidationError",
    "UnsupportedCapabilityError",
)
