"""Versioned contracts for deterministic batch operator triage."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
import re
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.contracts import JsonContract, deterministic_id
from amazon_product_intelligence.operator_workflow import OPERATOR_WORKFLOW_RULESET_VERSION
from amazon_product_intelligence.production_pipeline import ProductionRunMode

from .errors import BatchInputValidationError


BATCH_INPUT_CONTRACT_VERSION = "product-selection-batch-v0.1"
BATCH_RESULT_CONTRACT_VERSION = "batch-selection-result-v0.1"
BATCH_PIPELINE_VERSION = "batch-product-selection-v0.1"
BATCH_RANKING_STATUS = "UNAVAILABLE"

_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ASIN = re.compile(r"^[A-Z0-9]{10}$")


class BatchStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class CandidateExecutionSource(StrEnum):
    NEW_EXECUTION = "NEW_EXECUTION"
    CHECKPOINT_RESUME = "CHECKPOINT_RESUME"
    REUSED_SUCCESS = "REUSED_SUCCESS"


class CandidateRecoveryDisposition(StrEnum):
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CHECKPOINT_RESUME_AVAILABLE = "CHECKPOINT_RESUME_AVAILABLE"
    FRESH_EXECUTION_REQUIRED = "FRESH_EXECUTION_REQUIRED"


def _text(value: Any, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise BatchInputValidationError(f"{field_name} must be non-empty text")
    return value


def _identifier(value: Any, field_name: str) -> str:
    text = _text(value, field_name)
    if _IDENTIFIER.fullmatch(text) is None:
        raise BatchInputValidationError(
            f"{field_name} must be a lowercase path-safe identifier"
        )
    return text


def _freeze_json(value: Any, field_name: str) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise BatchInputValidationError(f"{field_name} keys must be text")
            frozen[key] = _freeze_json(item, f"{field_name}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item, f"{field_name}[]") for item in value)
    if value is None or type(value) in {str, bool, int, float}:
        return value
    raise BatchInputValidationError(
        f"{field_name} contains unsupported value {type(value).__name__}"
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchCandidateDefinition(JsonContract):
    candidate_id: str
    asins: tuple[str, ...]

    def __post_init__(self) -> None:
        _identifier(self.candidate_id, "candidate_id")
        if not self.asins:
            raise BatchInputValidationError("each candidate must contain at least one ASIN")
        if tuple(sorted(self.asins)) != self.asins:
            raise BatchInputValidationError("candidate ASINs must use deterministic sorted order")
        if len(set(self.asins)) != len(self.asins):
            raise BatchInputValidationError("candidate ASINs must be unique")
        if any(type(asin) is not str or _ASIN.fullmatch(asin) is None for asin in self.asins):
            raise BatchInputValidationError(
                "every candidate ASIN must be a normalized 10-character identifier"
            )

    def fingerprint_material(self) -> dict[str, Any]:
        return {"candidate_id": self.candidate_id, "asins": list(self.asins)}


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchSelectionRequest(JsonContract):
    batch_id: str
    marketplace: str
    category_name: str
    mode: ProductionRunMode
    candidates: tuple[BatchCandidateDefinition, ...]
    output_directory: Path
    resume_from: Path | None = None
    provider_preference: str = "xiyou"
    provider_config_reference: str = "environment"
    contract_version: str = BATCH_INPUT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != BATCH_INPUT_CONTRACT_VERSION:
            raise BatchInputValidationError(
                f"contract_version must be {BATCH_INPUT_CONTRACT_VERSION}"
            )
        _identifier(self.batch_id, "batch_id")
        if type(self.marketplace) is not str or self.marketplace != self.marketplace.upper():
            raise BatchInputValidationError("marketplace must be normalized uppercase text")
        _text(self.marketplace, "marketplace")
        _text(self.category_name, "category_name")
        if self.category_name.casefold() != "dog water bottle":
            raise BatchInputValidationError(
                "Batch V0.1 is validated only for the dog water bottle category"
            )
        if not isinstance(self.mode, ProductionRunMode):
            raise BatchInputValidationError("mode must be fixture or live")
        if not isinstance(self.output_directory, Path):
            raise BatchInputValidationError("output_directory must be a pathlib.Path")
        if self.resume_from is not None and not isinstance(self.resume_from, Path):
            raise BatchInputValidationError("resume_from must be a pathlib.Path when supplied")
        if self.provider_preference != "xiyou":
            raise BatchInputValidationError("provider_preference must be xiyou")
        if self.provider_config_reference != "environment":
            raise BatchInputValidationError(
                "provider_config_reference must be the credential-safe environment reference"
            )
        if not self.candidates:
            raise BatchInputValidationError("batch must contain at least one candidate")
        if tuple(sorted(self.candidates, key=lambda item: item.candidate_id)) != self.candidates:
            raise BatchInputValidationError("candidates must use deterministic candidate-ID order")
        candidate_ids = tuple(item.candidate_id for item in self.candidates)
        if len(set(candidate_ids)) != len(candidate_ids):
            raise BatchInputValidationError("candidate_id values must be unique")
        cohorts = tuple(item.asins for item in self.candidates)
        if len(set(cohorts)) != len(cohorts):
            raise BatchInputValidationError("duplicate candidate ASIN cohorts are not allowed")

    @property
    def input_fingerprint(self) -> str:
        return deterministic_id("product-selection-batch-input", self.semantic_material())

    def semantic_material(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "batch_id": self.batch_id,
            "marketplace": self.marketplace,
            "category_name": self.category_name,
            "mode": self.mode.value,
            "provider_preference": self.provider_preference,
            "provider_config_reference": self.provider_config_reference,
            "candidates": [item.fingerprint_material() for item in self.candidates],
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.semantic_material(), "input_fingerprint": self.input_fingerprint}


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchCandidateSummary(JsonContract):
    candidate_id: str
    candidate_fingerprint: str
    execution_source: CandidateExecutionSource
    production_run_status: str
    requested_asin_count: int
    resolved_asin_count: int
    market_report_id: str | None
    market_report_version: str | None
    operator_workflow_ruleset_version: str | None
    operator_semantic_fingerprint: str | None
    operator_action: str | None
    recommendation_type: str | None
    evidence_readiness: str | None
    action_reason: str | None
    top_buyer_need_themes: tuple[Mapping[str, Any], ...]
    competition_status: str | None
    missing_evidence_count: int | None
    top_missing_evidence: tuple[Mapping[str, Any], ...]
    opportunity_score_status: str | None
    opportunity_score_value: float | None
    ranking_status: str
    next_actions: tuple[Mapping[str, Any], ...]
    run_health: Mapping[str, Any] | None
    provider_usage: Mapping[str, Any]
    artifact_paths: Mapping[str, str]
    artifact_hashes: Mapping[str, str]
    lineage_reference_ids: tuple[str, ...]
    error: Mapping[str, Any] | None = None
    recovery_disposition: CandidateRecoveryDisposition = (
        CandidateRecoveryDisposition.NOT_APPLICABLE
    )

    def __post_init__(self) -> None:
        _identifier(self.candidate_id, "candidate summary candidate_id")
        _text(self.candidate_fingerprint, "candidate_fingerprint")
        if not isinstance(self.execution_source, CandidateExecutionSource):
            raise BatchInputValidationError("candidate execution_source is invalid")
        if not isinstance(self.recovery_disposition, CandidateRecoveryDisposition):
            raise BatchInputValidationError("candidate recovery_disposition is invalid")
        if self.production_run_status not in {"SUCCEEDED", "FAILED"}:
            raise BatchInputValidationError("candidate production_run_status is invalid")
        for name in ("requested_asin_count", "resolved_asin_count"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise BatchInputValidationError(f"{name} must be a non-negative integer")
        if self.ranking_status != BATCH_RANKING_STATUS:
            raise BatchInputValidationError("batch ranking must remain UNAVAILABLE")
        if self.opportunity_score_value is not None and type(
            self.opportunity_score_value
        ) not in {int, float}:
            raise BatchInputValidationError("opportunity score value must be numeric or null")
        if self.opportunity_score_status == "PENDING_DATA" and self.opportunity_score_value is not None:
            raise BatchInputValidationError("PENDING_DATA opportunity score must remain null")
        if self.production_run_status == "SUCCEEDED":
            if self.recovery_disposition is not CandidateRecoveryDisposition.NOT_APPLICABLE:
                raise BatchInputValidationError(
                    "successful candidate recovery_disposition must be NOT_APPLICABLE"
                )
            if self.operator_workflow_ruleset_version != OPERATOR_WORKFLOW_RULESET_VERSION:
                raise BatchInputValidationError("successful candidate ruleset is incompatible")
            for name in (
                "market_report_id",
                "market_report_version",
                "operator_semantic_fingerprint",
                "operator_action",
                "recommendation_type",
                "evidence_readiness",
                "action_reason",
            ):
                _text(getattr(self, name), f"candidate {name}")
        object.__setattr__(
            self,
            "top_buyer_need_themes",
            tuple(_freeze_json(item, "top_buyer_need_themes") for item in self.top_buyer_need_themes),
        )
        object.__setattr__(
            self,
            "next_actions",
            tuple(_freeze_json(item, "next_actions") for item in self.next_actions),
        )
        object.__setattr__(
            self,
            "top_missing_evidence",
            tuple(
                _freeze_json(item, "top_missing_evidence")
                for item in self.top_missing_evidence
            ),
        )
        object.__setattr__(
            self,
            "run_health",
            None if self.run_health is None else _freeze_json(self.run_health, "run_health"),
        )
        object.__setattr__(self, "provider_usage", _freeze_json(self.provider_usage, "provider_usage"))
        object.__setattr__(self, "artifact_paths", _freeze_json(self.artifact_paths, "artifact_paths"))
        object.__setattr__(self, "artifact_hashes", _freeze_json(self.artifact_hashes, "artifact_hashes"))
        object.__setattr__(
            self,
            "lineage_reference_ids",
            tuple(sorted(set(self.lineage_reference_ids))),
        )
        object.__setattr__(
            self,
            "error",
            None if self.error is None else _freeze_json(self.error, "candidate error"),
        )

    def semantic_view(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "candidate_fingerprint": self.candidate_fingerprint,
            "production_run_status": self.production_run_status,
            "requested_asin_count": self.requested_asin_count,
            "resolved_asin_count": self.resolved_asin_count,
            "market_report_id": self.market_report_id,
            "market_report_version": self.market_report_version,
            "operator_workflow_ruleset_version": self.operator_workflow_ruleset_version,
            "operator_semantic_fingerprint": self.operator_semantic_fingerprint,
            "operator_action": self.operator_action,
            "recommendation_type": self.recommendation_type,
            "evidence_readiness": self.evidence_readiness,
            "action_reason": self.action_reason,
            "top_buyer_need_themes": [dict(item) for item in self.top_buyer_need_themes],
            "competition_status": self.competition_status,
            "missing_evidence_count": self.missing_evidence_count,
            "top_missing_evidence": [dict(item) for item in self.top_missing_evidence],
            "opportunity_score_status": self.opportunity_score_status,
            "opportunity_score_value": self.opportunity_score_value,
            "ranking_status": self.ranking_status,
            "next_actions": [dict(item) for item in self.next_actions],
            "lineage_reference_ids": [
                value
                for value in self.lineage_reference_ids
                if not value.startswith("operator-workflow-snapshot:")
            ],
            "error_code": self.error.get("code") if self.error is not None else None,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchUsageSummary(JsonContract):
    total_logical_operations: int
    new_transport_attempts: int
    executed_operations: int
    checkpoint_replayed_operations: int
    reused_source_operations: int
    current_run_observed_credits: float | None
    credit_semantics: str
    billing_note: str
    per_candidate_semantics: Mapping[str, str]

    def __post_init__(self) -> None:
        for name in (
            "total_logical_operations",
            "new_transport_attempts",
            "executed_operations",
            "checkpoint_replayed_operations",
            "reused_source_operations",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise BatchInputValidationError(f"usage {name} is invalid")
        _text(self.credit_semantics, "batch credit_semantics")
        _text(self.billing_note, "batch billing_note")
        object.__setattr__(
            self,
            "per_candidate_semantics",
            _freeze_json(self.per_candidate_semantics, "per_candidate_semantics"),
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchSelectionResult(JsonContract):
    batch_id: str
    input_contract_version: str
    input_fingerprint: str
    semantic_fingerprint: str
    status: BatchStatus
    candidate_count: int
    succeeded_count: int
    failed_count: int
    candidates: tuple[BatchCandidateSummary, ...]
    usage: BatchUsageSummary
    batch_artifact_paths: Mapping[str, str]
    source_batch_directory: str | None = None
    contract_version: str = BATCH_RESULT_CONTRACT_VERSION
    pipeline_version: str = BATCH_PIPELINE_VERSION
    ranking_status: str = BATCH_RANKING_STATUS
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.contract_version != BATCH_RESULT_CONTRACT_VERSION:
            raise BatchInputValidationError("unsupported batch result contract")
        if self.input_contract_version != BATCH_INPUT_CONTRACT_VERSION:
            raise BatchInputValidationError("batch result input contract is incompatible")
        if self.pipeline_version != BATCH_PIPELINE_VERSION:
            raise BatchInputValidationError("unsupported batch pipeline version")
        _identifier(self.batch_id, "result batch_id")
        if not isinstance(self.status, BatchStatus):
            raise BatchInputValidationError("batch status is invalid")
        if self.ranking_status != BATCH_RANKING_STATUS:
            raise BatchInputValidationError("batch ranking must remain UNAVAILABLE")
        ordered = tuple(sorted(self.candidates, key=lambda item: item.candidate_id))
        if ordered != self.candidates:
            raise BatchInputValidationError("candidate summaries are not deterministic")
        if self.candidate_count != len(self.candidates):
            raise BatchInputValidationError("candidate_count does not match summaries")
        if self.succeeded_count + self.failed_count != self.candidate_count:
            raise BatchInputValidationError("batch candidate status counts do not reconcile")
        if self.succeeded_count != sum(
            item.production_run_status == "SUCCEEDED" for item in self.candidates
        ):
            raise BatchInputValidationError("succeeded_count does not match summaries")
        expected_status = (
            BatchStatus.SUCCEEDED
            if self.failed_count == 0
            else BatchStatus.FAILED
            if self.succeeded_count == 0
            else BatchStatus.PARTIAL
        )
        if self.status is not expected_status:
            raise BatchInputValidationError("batch status does not match candidate outcomes")
        object.__setattr__(
            self,
            "batch_artifact_paths",
            _freeze_json(self.batch_artifact_paths, "batch_artifact_paths"),
        )
        object.__setattr__(self, "warnings", tuple(sorted(set(self.warnings))))
        expected_fingerprint = deterministic_id(
            "batch-selection-semantic",
            {
                "input_fingerprint": self.input_fingerprint,
                "status": self.status.value,
                "candidates": [item.semantic_view() for item in self.candidates],
            },
        )
        if self.semantic_fingerprint != expected_fingerprint:
            raise BatchInputValidationError("batch semantic_fingerprint does not match content")


def parse_batch_request(
    payload: Mapping[str, Any],
    *,
    output_directory: Path,
    resume_from: Path | None = None,
) -> BatchSelectionRequest:
    """Normalize a strict JSON payload before any candidate/provider access."""

    if not isinstance(payload, Mapping):
        raise BatchInputValidationError("batch file root must be a JSON object")
    allowed = {
        "contract_version",
        "batch_id",
        "marketplace",
        "category_name",
        "mode",
        "provider_preference",
        "provider_config_reference",
        "candidates",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise BatchInputValidationError(
            "batch file contains unsupported fields", details={"fields": unknown}
        )
    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, Sequence) or isinstance(raw_candidates, (str, bytes)):
        raise BatchInputValidationError("candidates must be a JSON array")
    candidates: list[BatchCandidateDefinition] = []
    for index, raw in enumerate(raw_candidates):
        if not isinstance(raw, Mapping):
            raise BatchInputValidationError(f"candidates[{index}] must be an object")
        if set(raw) != {"candidate_id", "asins"}:
            raise BatchInputValidationError(
                f"candidates[{index}] must contain only candidate_id and asins"
            )
        raw_asins = raw.get("asins")
        if not isinstance(raw_asins, Sequence) or isinstance(raw_asins, (str, bytes)):
            raise BatchInputValidationError(f"candidates[{index}].asins must be an array")
        if any(type(value) is not str for value in raw_asins):
            raise BatchInputValidationError(
                f"candidates[{index}].asins must contain only text identifiers"
            )
        if type(raw.get("candidate_id")) is not str:
            raise BatchInputValidationError(
                f"candidates[{index}].candidate_id must be text"
            )
        normalized_asins = tuple(value.strip().upper() for value in raw_asins)
        if len(set(normalized_asins)) != len(normalized_asins):
            raise BatchInputValidationError(
                f"candidates[{index}].asins contains duplicate normalized ASINs"
            )
        candidates.append(
            BatchCandidateDefinition(
                candidate_id=raw.get("candidate_id", "").strip(),
                asins=tuple(sorted(normalized_asins)),
            )
        )
    try:
        mode = ProductionRunMode(str(payload.get("mode", "")))
    except ValueError as exc:
        raise BatchInputValidationError("mode must be fixture or live") from exc
    return BatchSelectionRequest(
        contract_version=str(payload.get("contract_version", "")),
        batch_id=str(payload.get("batch_id", "")).strip(),
        marketplace=str(payload.get("marketplace", "")).strip().upper(),
        category_name=str(payload.get("category_name", "")).strip(),
        mode=mode,
        provider_preference=str(payload.get("provider_preference", "xiyou")).strip(),
        provider_config_reference=str(
            payload.get("provider_config_reference", "environment")
        ).strip(),
        candidates=tuple(sorted(candidates, key=lambda item: item.candidate_id)),
        output_directory=output_directory,
        resume_from=resume_from,
    )


__all__ = (
    "BATCH_INPUT_CONTRACT_VERSION",
    "BATCH_PIPELINE_VERSION",
    "BATCH_RANKING_STATUS",
    "BATCH_RESULT_CONTRACT_VERSION",
    "BatchCandidateDefinition",
    "BatchCandidateSummary",
    "BatchSelectionRequest",
    "BatchSelectionResult",
    "BatchStatus",
    "BatchUsageSummary",
    "CandidateExecutionSource",
    "parse_batch_request",
)
