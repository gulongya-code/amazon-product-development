"""Versioned, atomic and secret-safe provider-operation recovery checkpoints."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping

from amazon_product_intelligence.adapters.base import ADAPTER_RULESET_VERSION
from amazon_product_intelligence.connectors import (
    ProviderRequest,
    TransportRequest,
    TransportResponse,
)
from amazon_product_intelligence.connectors.xiyou_v0_1 import XIYOU_OPERATIONS
from amazon_product_intelligence.contracts import canonical_json, deterministic_id

from .artifacts import write_json_atomic
from .errors import (
    ProductionPipelineErrorCode,
    RecoveryContractError,
)
from .models import ProductionRunRequest


RECOVERY_CONTRACT_VERSION = "production-recovery-v0.1"
CHECKPOINT_CONTRACT_VERSION = "production-provider-checkpoint-v0.1"
PROVIDER_REQUEST_CONTRACT_VERSION = "production-provider-request-contract-v0.1"

_CREDENTIAL_KEY_SUFFIXES = (
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "env",
    "environment",
    "password",
    "secret",
    "token",
)
_SAFE_METADATA_KEYS = frozenset({"cost_credits"})
_XIYOU_OPERATION_INDEX = {item.operation: item for item in XIYOU_OPERATIONS}
_RECOVERY_OPERATIONS = ("asin_info", "asin_keywords")


def _hash(value: Mapping[str, Any]) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _json_copy(value: Any) -> Any:
    return json.loads(canonical_json(value))


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def reject_unsafe_content(value: Any, *, path: str = "checkpoint") -> None:
    """Recursively reject credential-like keys and non-JSON values."""

    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _unsafe(path)
        return
    if isinstance(value, MappingABC):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _unsafe(path)
            normalized = _normalized_key(key)
            if any(normalized.endswith(suffix) for suffix in _CREDENTIAL_KEY_SUFFIXES):
                raise _unsafe(f"{path}.{key}")
            reject_unsafe_content(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            reject_unsafe_content(item, path=f"{path}[{index}]")
        return
    raise _unsafe(path)


def _unsafe(path: str) -> RecoveryContractError:
    return RecoveryContractError(
        ProductionPipelineErrorCode.UNSAFE_CHECKPOINT_CONTENT,
        "checkpoint contains unsafe or unsupported content",
        details={"content_path": path},
    )


def _operation_contract(operation: str) -> dict[str, Any]:
    definition = _XIYOU_OPERATION_INDEX[operation]
    return {
        "operation": definition.operation,
        "payload_kind": definition.payload_kind,
        "source_tool": definition.source_tool,
        "method": definition.method,
        "endpoint": definition.endpoint,
        "public_headers": dict(sorted(definition.public_headers.items())),
        "adapter_ruleset_version": ADAPTER_RULESET_VERSION,
    }


def run_request_fingerprint(request: ProductionRunRequest) -> str:
    material = {
        "contract_version": PROVIDER_REQUEST_CONTRACT_VERSION,
        "marketplace": request.marketplace,
        "asins": list(request.asins),
        "provider_preference": request.provider_preference,
        "provider_config_reference": request.provider_config_reference,
        "mode": request.mode.value,
        "category_name": request.category_name,
        "provider_operations": [
            _operation_contract(operation) for operation in _RECOVERY_OPERATIONS
        ],
    }
    return _hash(material)


def logical_operation_id(operation: str, request: ProviderRequest) -> str:
    material = {
        "provider_id": "xiyou",
        "operation_contract": _operation_contract(operation),
        "canonical_field": request.canonical_field,
        "marketplace": request.marketplace,
        "parameters": dict(request.parameters),
    }
    return deterministic_id("production-provider-operation", material)


@dataclass(frozen=True, slots=True)
class ProviderCheckpoint:
    payload: Mapping[str, Any]
    source_path: Path | None = None

    @property
    def checkpoint_id(self) -> str:
        return str(self.payload["checkpoint_id"])

    @property
    def logical_operation_id(self) -> str:
        return str(self.payload["logical_operation_id"])

    @property
    def operation(self) -> str:
        return str(self.payload["operation"])

    @property
    def response(self) -> TransportResponse:
        response = self.payload["provider_response"]
        return TransportResponse(
            status_code=int(response["status_code"]),
            payload=deepcopy(response["payload"]),
            metadata=deepcopy(response["metadata"]),
        )

    def replay_request(self, current: ProviderRequest) -> ProviderRequest:
        context = self.payload["adaptation_context"]
        return ProviderRequest(
            canonical_field=current.canonical_field,
            parameters=current.parameters,
            marketplace=current.marketplace,
            locale=str(context["locale"]),
            retrieved_at=str(context["retrieved_at"]),
            transformed_at=str(context["transformed_at"]),
            collection_run_id=str(context["collection_run_id"]),
            currency=(str(context["currency"]) if context["currency"] is not None else None),
        )


class CheckpointReplayTransport:
    """One-response transport used only after checkpoint integrity validation."""

    def __init__(self, checkpoint: ProviderCheckpoint) -> None:
        self._checkpoint = checkpoint
        self.execute_count = 0
        self.network_call_count = 0

    def execute(self, request: TransportRequest) -> TransportResponse:
        if request.provider_id != "xiyou" or request.operation != self._checkpoint.operation:
            raise RecoveryContractError(
                ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
                "checkpoint operation does not match the replay request",
            )
        expected = self._checkpoint.payload["normalized_request_parameters"]
        if canonical_json(dict(request.parameters)) != canonical_json(expected):
            raise RecoveryContractError(
                ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
                "checkpoint parameters do not match the replay request",
            )
        self.execute_count += 1
        return self._checkpoint.response


class CheckpointStore:
    def __init__(self, output_directory: Path, *, run_id: str, request_fingerprint: str) -> None:
        self.directory = output_directory / "checkpoints"
        self.run_id = run_id
        self.request_fingerprint = request_fingerprint
        self._checkpoint_ids: list[str] = []

    @property
    def checkpoint_ids(self) -> tuple[str, ...]:
        return tuple(self._checkpoint_ids)

    def write_success(
        self,
        *,
        operation: str,
        request: ProviderRequest,
        response: TransportResponse,
        provenance_id: str,
        replayed_from: str | None = None,
    ) -> ProviderCheckpoint:
        operation_id = logical_operation_id(operation, request)
        identity = {
            "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
            "provider_id": "xiyou",
            "logical_operation_id": operation_id,
            "source_request_fingerprint": self.request_fingerprint,
            "operation_contract": _operation_contract(operation),
            "provenance_raw_evidence_id": provenance_id,
        }
        checkpoint_id = deterministic_id("production-provider-checkpoint", identity)
        metadata = {
            key: deepcopy(value)
            for key, value in response.metadata.items()
            if key in _SAFE_METADATA_KEYS
        }
        payload: dict[str, Any] = {
            "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
            "checkpoint_id": checkpoint_id,
            "owner_run_id": self.run_id,
            "provider_id": "xiyou",
            "operation": operation,
            "canonical_field": request.canonical_field,
            "logical_operation_id": operation_id,
            "normalized_request_parameters": _json_copy(request.parameters),
            "marketplace": request.marketplace,
            "source_request_fingerprint": self.request_fingerprint,
            "operation_contract": _operation_contract(operation),
            "adaptation_context": {
                "locale": request.locale,
                "retrieved_at": request.retrieved_at,
                "transformed_at": request.transformed_at,
                "collection_run_id": request.collection_run_id,
                "currency": request.currency,
            },
            "provider_response": {
                "status_code": response.status_code,
                "payload": _json_copy(response.payload),
                "metadata": metadata,
            },
            "provenance_raw_evidence_id": provenance_id,
            "replayed_from_checkpoint_id": replayed_from,
        }
        reject_unsafe_content(payload)
        payload["integrity_sha256"] = _hash(payload)
        checkpoint = validate_checkpoint(payload, expected_request_fingerprint=self.request_fingerprint)
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / f"{checkpoint_id.split(':', 1)[-1]}.json"
        write_json_atomic(destination, payload)
        if checkpoint_id not in self._checkpoint_ids:
            self._checkpoint_ids.append(checkpoint_id)
        return ProviderCheckpoint(payload=payload, source_path=destination)


@dataclass(frozen=True, slots=True)
class ResumeCheckpointSet:
    source_directory: Path
    source_run_id: str
    request_fingerprint: str
    checkpoints: Mapping[str, ProviderCheckpoint]

    def find(self, operation: str, request: ProviderRequest) -> ProviderCheckpoint | None:
        operation_id = logical_operation_id(operation, request)
        return self.checkpoints.get(operation_id)


def validate_checkpoint(
    payload: Any, *, expected_request_fingerprint: str
) -> ProviderCheckpoint:
    if not isinstance(payload, MappingABC):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint must be a JSON object",
        )
    reject_unsafe_content(payload)
    if payload.get("checkpoint_contract_version") != CHECKPOINT_CONTRACT_VERSION:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.UNSUPPORTED_CHECKPOINT_VERSION,
            "checkpoint contract version is unsupported",
        )
    integrity = payload.get("integrity_sha256")
    body = {key: deepcopy(value) for key, value in payload.items() if key != "integrity_sha256"}
    if not isinstance(integrity, str) or integrity != _hash(body):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint integrity validation failed",
        )
    if payload.get("source_request_fingerprint") != expected_request_fingerprint:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "checkpoint request fingerprint does not match the current run",
        )
    operation = payload.get("operation")
    if operation not in _RECOVERY_OPERATIONS:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "checkpoint operation is not part of the production recovery contract",
        )
    if payload.get("operation_contract") != _operation_contract(str(operation)):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "checkpoint provider/adaptation contract does not match the current runtime",
        )
    required_text = (
        "checkpoint_id",
        "owner_run_id",
        "provider_id",
        "canonical_field",
        "logical_operation_id",
        "marketplace",
        "provenance_raw_evidence_id",
    )
    if any(not isinstance(payload.get(key), str) or not payload[key] for key in required_text):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint is incomplete",
        )
    response = payload.get("provider_response")
    context = payload.get("adaptation_context")
    parameters = payload.get("normalized_request_parameters")
    if (
        payload.get("provider_id") != "xiyou"
        or not isinstance(response, MappingABC)
        or not isinstance(context, MappingABC)
        or not isinstance(parameters, MappingABC)
    ):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint response or adaptation context is incomplete",
        )
    metadata = response.get("metadata")
    status_code = response.get("status_code")
    if (
        not isinstance(status_code, int)
        or not 200 <= status_code <= 299
        or not isinstance(metadata, MappingABC)
        or any(key not in _SAFE_METADATA_KEYS for key in metadata)
        or "payload" not in response
    ):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint does not contain a successful safe provider response",
        )
    try:
        reconstructed = ProviderRequest(
            canonical_field=str(payload["canonical_field"]),
            parameters=parameters,
            marketplace=str(payload["marketplace"]),
            locale=str(context["locale"]),
            retrieved_at=str(context["retrieved_at"]),
            transformed_at=str(context["transformed_at"]),
            collection_run_id=str(context["collection_run_id"]),
            currency=(str(context["currency"]) if context.get("currency") is not None else None),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint adaptation context is invalid",
        ) from exc
    expected_operation_id = logical_operation_id(str(operation), reconstructed)
    if payload["logical_operation_id"] != expected_operation_id:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint logical operation identity is invalid",
        )
    identity = {
        "checkpoint_contract_version": CHECKPOINT_CONTRACT_VERSION,
        "provider_id": "xiyou",
        "logical_operation_id": expected_operation_id,
        "source_request_fingerprint": expected_request_fingerprint,
        "operation_contract": _operation_contract(str(operation)),
        "provenance_raw_evidence_id": payload["provenance_raw_evidence_id"],
    }
    if payload["checkpoint_id"] != deterministic_id("production-provider-checkpoint", identity):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "checkpoint identity is invalid",
        )
    return ProviderCheckpoint(payload=deepcopy(dict(payload)))


def load_resume_source(
    source_directory: Path, *, expected_request_fingerprint: str
) -> ResumeCheckpointSet:
    manifest_path = source_directory / "run_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "resume source does not contain a readable failure manifest",
        ) from exc
    reject_unsafe_content(manifest, path="resume_manifest")
    recovery = manifest.get("recovery") if isinstance(manifest, MappingABC) else None
    if manifest.get("status") != "FAILED" or not isinstance(recovery, MappingABC):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "resume source must contain a compatible failed production run",
        )
    if recovery.get("contract_version") != RECOVERY_CONTRACT_VERSION:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "resume source recovery contract is incompatible",
        )
    if recovery.get("request_fingerprint") != expected_request_fingerprint:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "resume source request fingerprint does not match the current run",
        )
    expected_ids = recovery.get("checkpoint_ids")
    if not isinstance(expected_ids, list) or any(not isinstance(item, str) for item in expected_ids):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "resume source checkpoint inventory is invalid",
        )
    checkpoint_directory = source_directory / "checkpoints"
    paths = sorted(checkpoint_directory.glob("*.json")) if checkpoint_directory.is_dir() else []
    checkpoints: dict[str, ProviderCheckpoint] = {}
    found_ids: list[str] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise RecoveryContractError(
                ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
                "checkpoint is unreadable or corrupted",
                details={"checkpoint_file": path.name},
            ) from exc
        checkpoint = validate_checkpoint(
            payload, expected_request_fingerprint=expected_request_fingerprint
        )
        checkpoint = ProviderCheckpoint(payload=checkpoint.payload, source_path=path)
        if checkpoint.logical_operation_id in checkpoints:
            raise RecoveryContractError(
                ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
                "resume source contains duplicate logical operation checkpoints",
            )
        checkpoints[checkpoint.logical_operation_id] = checkpoint
        found_ids.append(checkpoint.checkpoint_id)
    if sorted(found_ids) != sorted(expected_ids):
        raise RecoveryContractError(
            ProductionPipelineErrorCode.CHECKPOINT_INTEGRITY_FAILURE,
            "resume source checkpoint inventory does not match the failure manifest",
        )
    source_run_id = manifest.get("run_id")
    if not isinstance(source_run_id, str) or not source_run_id:
        raise RecoveryContractError(
            ProductionPipelineErrorCode.INCOMPATIBLE_RESUME_SOURCE,
            "resume source run identity is missing",
        )
    return ResumeCheckpointSet(
        source_directory=source_directory,
        source_run_id=source_run_id,
        request_fingerprint=expected_request_fingerprint,
        checkpoints=checkpoints,
    )


__all__ = (
    "CHECKPOINT_CONTRACT_VERSION",
    "PROVIDER_REQUEST_CONTRACT_VERSION",
    "RECOVERY_CONTRACT_VERSION",
    "CheckpointReplayTransport",
    "CheckpointStore",
    "ProviderCheckpoint",
    "ResumeCheckpointSet",
    "load_resume_source",
    "logical_operation_id",
    "reject_unsafe_content",
    "run_request_fingerprint",
    "validate_checkpoint",
)
