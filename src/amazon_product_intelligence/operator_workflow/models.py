"""Versioned operator-first workflow contracts for Production Pipeline output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    deterministic_id,
)
from amazon_product_intelligence.market_report.models import MarketReportSnapshot


OPERATOR_WORKFLOW_RULESET_VERSION = "operator-workflow-v0.1"


class OperatorWorkflowValidationError(ContractValidationError):
    """Raised when an operator workflow violates its presentation contract."""


class OperatorActionType(StrEnum):
    """Conservative operator triage actions; never market-entry decisions."""

    ADVANCE_REVIEW = "ADVANCE_REVIEW"
    COLLECT_EVIDENCE = "COLLECT_EVIDENCE"
    FURTHER_REVIEW = "FURTHER_REVIEW"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


def _text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise OperatorWorkflowValidationError(f"{path} must be non-empty text")
    return value


def _optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        _text(value, path)
    return value


def _texts(values: tuple[str, ...], path: str, *, allow_empty: bool = True) -> tuple[str, ...]:
    normalized = tuple(sorted(values))
    if (not allow_empty and not normalized) or any(
        type(item) is not str or not item.strip() for item in normalized
    ):
        raise OperatorWorkflowValidationError(f"{path} contains invalid text")
    if len(set(normalized)) != len(normalized):
        raise OperatorWorkflowValidationError(f"{path} must contain unique values")
    return normalized


def _freeze_json(value: Any, path: str) -> Any:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise OperatorWorkflowValidationError(f"{path} keys must be text")
            result[key] = _freeze_json(item, f"{path}.{key}")
        return MappingProxyType(result)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze_json(item, f"{path}[]") for item in value)
    if value is None or type(value) in {str, bool, int, float}:
        return value
    raise OperatorWorkflowValidationError(
        f"{path} contains unsupported value {type(value).__name__}"
    )


def _without_id(model: JsonContract, field_name: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field_name)
    return payload


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorClaim(JsonContract):
    claim_id: str
    label: str
    value: Any
    status: str
    reason: str
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("claim_id", "label", "status", "reason"):
            _text(getattr(self, name), f"OperatorClaim.{name}")
        object.__setattr__(self, "value", _freeze_json(self.value, "OperatorClaim.value"))
        object.__setattr__(self, "evidence_ids", _texts(self.evidence_ids, "claim evidence"))
        object.__setattr__(
            self,
            "provenance_reference_ids",
            _texts(self.provenance_reference_ids, "claim provenance", allow_empty=False),
        )
        if self.claim_id != deterministic_id(
            "operator-workflow-claim", _without_id(self, "claim_id")
        ):
            raise OperatorWorkflowValidationError("claim_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorNextAction(JsonContract):
    action_id: str
    priority: int
    action: str
    reason: str
    trigger_status: str
    evidence_ids: tuple[str, ...]
    provenance_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in ("action_id", "action", "reason", "trigger_status"):
            _text(getattr(self, name), f"OperatorNextAction.{name}")
        if type(self.priority) is not int or not 1 <= self.priority <= 5:
            raise OperatorWorkflowValidationError("next action priority must be 1..5")
        object.__setattr__(self, "evidence_ids", _texts(self.evidence_ids, "action evidence"))
        object.__setattr__(
            self,
            "provenance_reference_ids",
            _texts(self.provenance_reference_ids, "action provenance", allow_empty=False),
        )
        if self.action_id != deterministic_id(
            "operator-workflow-next-action", _without_id(self, "action_id")
        ):
            raise OperatorWorkflowValidationError("action_id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorRunHealth(JsonContract):
    status: str
    retried: bool
    resumed: bool
    provider_id: str
    logical_operation_count: int
    transport_attempt_count: int
    executed_operation_count: int
    replayed_operation_count: int
    credits: float | None
    credit_semantics: str
    resume_source_run_id: str | None

    def __post_init__(self) -> None:
        for name in ("status", "provider_id", "credit_semantics"):
            _text(getattr(self, name), f"OperatorRunHealth.{name}")
        for name in (
            "logical_operation_count",
            "transport_attempt_count",
            "executed_operation_count",
            "replayed_operation_count",
        ):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise OperatorWorkflowValidationError(f"run health {name} is invalid")
        if self.credits is not None and (
            type(self.credits) not in {int, float} or isinstance(self.credits, bool)
        ):
            raise OperatorWorkflowValidationError("run health credits must be numeric or null")
        _optional_text(self.resume_source_run_id, "run health resume_source_run_id")
        if self.resumed != (self.resume_source_run_id is not None):
            raise OperatorWorkflowValidationError("resume status and lineage disagree")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorWorkflowRequest:
    report: MarketReportSnapshot
    run_id: str
    run_status: str
    provider_summary: Mapping[str, Any] | None = None
    recovery: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.report, MarketReportSnapshot):
            raise OperatorWorkflowValidationError("request report must be MarketReportSnapshot")
        self.report.validate()
        _text(self.run_id, "OperatorWorkflowRequest.run_id")
        _text(self.run_status, "OperatorWorkflowRequest.run_status")
        if self.provider_summary is not None and not isinstance(self.provider_summary, Mapping):
            raise OperatorWorkflowValidationError("provider_summary must be a mapping or null")
        if self.recovery is not None and not isinstance(self.recovery, Mapping):
            raise OperatorWorkflowValidationError("recovery must be a mapping or null")


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorWorkflowSnapshotV0_1(JsonContract):
    snapshot_id: str
    semantic_fingerprint: str
    ruleset_version: str
    run_id: str
    market_report_id: str
    market_report_version: str
    operator_action: OperatorActionType
    recommendation_type: str
    action_reason: str
    evidence_readiness: str
    framework_integration: Mapping[str, Any]
    supporting_evidence: tuple[OperatorClaim, ...]
    missing_evidence: tuple[OperatorClaim, ...]
    top_buyer_need_themes: tuple[OperatorClaim, ...]
    competition_summary: tuple[OperatorClaim, ...]
    opportunity_summary: tuple[OperatorClaim, ...]
    risks_and_limitations: tuple[OperatorClaim, ...]
    next_actions: tuple[OperatorNextAction, ...]
    run_health: OperatorRunHealth
    lineage_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "snapshot_id",
            "semantic_fingerprint",
            "run_id",
            "market_report_id",
            "market_report_version",
            "recommendation_type",
            "action_reason",
            "evidence_readiness",
        ):
            _text(getattr(self, name), f"OperatorWorkflowSnapshotV0_1.{name}")
        if self.ruleset_version != OPERATOR_WORKFLOW_RULESET_VERSION:
            raise OperatorWorkflowValidationError("unsupported operator workflow ruleset")
        if not isinstance(self.operator_action, OperatorActionType):
            raise OperatorWorkflowValidationError("operator_action is invalid")
        object.__setattr__(
            self,
            "framework_integration",
            _freeze_json(self.framework_integration, "framework_integration"),
        )
        for name, expected in (
            ("supporting_evidence", OperatorClaim),
            ("missing_evidence", OperatorClaim),
            ("top_buyer_need_themes", OperatorClaim),
            ("competition_summary", OperatorClaim),
            ("opportunity_summary", OperatorClaim),
            ("risks_and_limitations", OperatorClaim),
            ("next_actions", OperatorNextAction),
        ):
            if expected is OperatorNextAction:
                values = tuple(
                    sorted(getattr(self, name), key=lambda item: (item.priority, item.action_id))
                )
            else:
                values = tuple(
                    sorted(getattr(self, name), key=lambda item: item.claim_id)
                )
            if any(not isinstance(item, expected) for item in values):
                raise OperatorWorkflowValidationError(f"{name} contains invalid records")
            object.__setattr__(self, name, values)
        if not isinstance(self.run_health, OperatorRunHealth):
            raise OperatorWorkflowValidationError("run_health is invalid")
        object.__setattr__(
            self,
            "lineage_reference_ids",
            _texts(self.lineage_reference_ids, "workflow lineage", allow_empty=False),
        )
        semantic = self.to_dict()
        semantic.pop("snapshot_id")
        semantic.pop("semantic_fingerprint")
        semantic.pop("run_id")
        semantic.pop("run_health")
        expected_semantic = deterministic_id("operator-workflow-semantic", semantic)
        if self.semantic_fingerprint != expected_semantic:
            raise OperatorWorkflowValidationError("semantic_fingerprint does not match content")
        expected_snapshot = deterministic_id(
            "operator-workflow-snapshot", _without_id(self, "snapshot_id")
        )
        if self.snapshot_id != expected_snapshot:
            raise OperatorWorkflowValidationError("snapshot_id does not match content")


__all__ = (
    "OPERATOR_WORKFLOW_RULESET_VERSION",
    "OperatorActionType",
    "OperatorClaim",
    "OperatorNextAction",
    "OperatorRunHealth",
    "OperatorWorkflowRequest",
    "OperatorWorkflowSnapshotV0_1",
    "OperatorWorkflowValidationError",
)
