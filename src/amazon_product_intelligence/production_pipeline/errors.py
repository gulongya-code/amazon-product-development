"""Typed, credential-safe failures for the production pipeline."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Mapping


class ProductionPipelineErrorCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    OUTPUT_ARTIFACT_CONFLICT = "OUTPUT_ARTIFACT_CONFLICT"
    INCOMPATIBLE_RESUME_SOURCE = "INCOMPATIBLE_RESUME_SOURCE"
    CHECKPOINT_INTEGRITY_FAILURE = "CHECKPOINT_INTEGRITY_FAILURE"
    UNSUPPORTED_CHECKPOINT_VERSION = "UNSUPPORTED_CHECKPOINT_VERSION"
    UNSAFE_CHECKPOINT_CONTENT = "UNSAFE_CHECKPOINT_CONTENT"
    BOUNDED_RETRY_EXHAUSTED = "BOUNDED_RETRY_EXHAUSTED"
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


class OutputArtifactConflictError(ProductionPipelineError):
    def __init__(self, managed_artifacts: tuple[str, ...]) -> None:
        super().__init__(
            ProductionPipelineErrorCode.OUTPUT_ARTIFACT_CONFLICT,
            "output directory already contains managed production artifacts",
            stage="input_validation",
            details={"conflicting_managed_artifacts": list(managed_artifacts)},
        )


class RecoveryContractError(ProductionPipelineError):
    """Typed, secret-safe recovery/checkpoint contract failure."""

    def __init__(
        self,
        code: ProductionPipelineErrorCode,
        message: str,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(code, message, stage="input_validation", details=details)


__all__ = (
    "ProductionPipelineError",
    "ProductionPipelineErrorCode",
    "ProductionRunValidationError",
    "RecoveryContractError",
    "OutputArtifactConflictError",
    "UnsupportedCapabilityError",
)
