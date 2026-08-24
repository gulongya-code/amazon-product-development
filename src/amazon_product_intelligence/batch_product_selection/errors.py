"""Typed, secret-safe failures for Batch Product Selection V0.1."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping


class BatchSelectionErrorCode(StrEnum):
    INVALID_BATCH_INPUT = "INVALID_BATCH_INPUT"
    BATCH_OUTPUT_CONFLICT = "BATCH_OUTPUT_CONFLICT"
    INCOMPATIBLE_BATCH_RESUME = "INCOMPATIBLE_BATCH_RESUME"
    BATCH_ARTIFACT_INTEGRITY = "BATCH_ARTIFACT_INTEGRITY"
    BATCH_DELIVERY_FAILURE = "BATCH_DELIVERY_FAILURE"


class BatchSelectionError(ValueError):
    """A bounded machine-readable batch error that never carries credentials."""

    def __init__(
        self,
        code: BatchSelectionErrorCode,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.details = dict(details or {})
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code.value,
            "message": self.message,
            "details": dict(sorted(self.details.items())),
        }


class BatchInputValidationError(BatchSelectionError):
    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(BatchSelectionErrorCode.INVALID_BATCH_INPUT, message, details=details)


__all__ = (
    "BatchInputValidationError",
    "BatchSelectionError",
    "BatchSelectionErrorCode",
)
