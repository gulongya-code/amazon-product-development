"""Immutable versioned contracts for one production pipeline run."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
import re
from typing import Any, Mapping

from .errors import ProductionRunValidationError


PRODUCTION_RUN_CONTRACT_VERSION = "production-run-v0.1"
PRODUCTION_PIPELINE_VERSION = "production-pipeline-v0.1"

_ASIN = re.compile(r"^[A-Z0-9]{10}$")
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ProductionRunMode(StrEnum):
    FIXTURE = "fixture"
    LIVE = "live"


class ProductionRunStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class StageStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PipelineStage(StrEnum):
    INPUT_VALIDATION = "input_validation"
    PROVIDER_RESOLUTION = "provider_resolution"
    ACQUISITION = "acquisition"
    DATA_CLEANING = "data_cleaning"
    CATEGORY_COMPETITION = "category_competition"
    BUYER_NEED = "buyer_need_v0_3"
    OPPORTUNITY = "opportunity_intelligence_scoring"
    MARKET_REPORT = "market_report"
    SCHEMA_VALIDATION = "schema_validation"
    DELIVERY = "operator_delivery"
    MANIFEST = "run_manifest"


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionRunRequest:
    marketplace: str
    asins: tuple[str, ...]
    output_directory: Path
    provider_preference: str = "xiyou"
    provider_config_reference: str = "environment"
    run_id: str | None = None
    mode: ProductionRunMode = ProductionRunMode.FIXTURE
    asin_file: Path | None = None
    seed_keyword: str | None = None
    category_name: str | None = None
    contract_version: str = PRODUCTION_RUN_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != PRODUCTION_RUN_CONTRACT_VERSION:
            raise ProductionRunValidationError(
                f"contract_version must be {PRODUCTION_RUN_CONTRACT_VERSION}"
            )
        if not isinstance(self.mode, ProductionRunMode):
            raise ProductionRunValidationError("mode must be fixture or live")
        market = self.marketplace.strip().upper() if isinstance(self.marketplace, str) else ""
        if not market or market != self.marketplace:
            raise ProductionRunValidationError("marketplace must be normalized uppercase text")
        asins = tuple(sorted(set(self.asins)))
        if any(not isinstance(value, str) or _ASIN.fullmatch(value) is None for value in asins):
            raise ProductionRunValidationError("every ASIN must be a normalized 10-character identifier")
        if not asins and not (isinstance(self.seed_keyword, str) and self.seed_keyword.strip()):
            raise ProductionRunValidationError("at least one ASIN or a seed keyword is required")
        if not isinstance(self.output_directory, Path):
            raise ProductionRunValidationError("output_directory must be a pathlib.Path")
        if not self.provider_preference.strip():
            raise ProductionRunValidationError("provider_preference must be non-empty text")
        if not self.provider_config_reference.strip():
            raise ProductionRunValidationError("provider_config_reference must be non-empty text")
        if self.run_id is not None and _RUN_ID.fullmatch(self.run_id) is None:
            raise ProductionRunValidationError("run_id contains unsupported characters")
        if self.category_name is not None and not self.category_name.strip():
            raise ProductionRunValidationError("category_name must be non-empty when supplied")
        object.__setattr__(self, "asins", asins)


@dataclass(frozen=True, slots=True, kw_only=True)
class StageResult:
    stage: PipelineStage
    status: StageStatus
    detail: str
    evidence_ids: tuple[str, ...] = ()
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "detail": self.detail,
            "evidence_ids": list(self.evidence_ids),
            "error_code": self.error_code,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ProviderOperationSummary:
    provider_id: str
    operations: tuple[str, ...]
    operation_count: int
    credits: float | None
    provenance_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "operations": list(self.operations),
            "operation_count": self.operation_count,
            "credits": self.credits,
            "provenance_ids": list(self.provenance_ids),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductionRunResult:
    run_id: str
    status: ProductionRunStatus
    requested_asin_count: int
    resolved_asin_count: int
    stages: tuple[StageResult, ...]
    artifact_paths: Mapping[str, str]
    market_report_version: str
    provider_summary: ProviderOperationSummary | None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    unavailable_evidence: tuple[str, ...] = field(default_factory=tuple)
    error: Mapping[str, Any] | None = None
    contract_version: str = PRODUCTION_RUN_CONTRACT_VERSION
    pipeline_version: str = PRODUCTION_PIPELINE_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "pipeline_version": self.pipeline_version,
            "run_id": self.run_id,
            "status": self.status.value,
            "requested_asin_count": self.requested_asin_count,
            "resolved_asin_count": self.resolved_asin_count,
            "stages": [item.to_dict() for item in self.stages],
            "artifact_paths": dict(sorted(self.artifact_paths.items())),
            "market_report_version": self.market_report_version,
            "provider_summary": (
                self.provider_summary.to_dict() if self.provider_summary is not None else None
            ),
            "warnings": list(self.warnings),
            "unavailable_evidence": list(self.unavailable_evidence),
            "error": dict(self.error) if self.error is not None else None,
        }


__all__ = (
    "PRODUCTION_PIPELINE_VERSION",
    "PRODUCTION_RUN_CONTRACT_VERSION",
    "PipelineStage",
    "ProductionRunMode",
    "ProductionRunRequest",
    "ProductionRunResult",
    "ProductionRunStatus",
    "ProviderOperationSummary",
    "StageResult",
    "StageStatus",
)
