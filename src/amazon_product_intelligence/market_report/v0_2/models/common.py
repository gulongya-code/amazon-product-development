"""Shared strict primitives for the Market Report V0.2 foundation."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
import json
import math
import re
from types import MappingProxyType
from typing import Any, Mapping, Self

from amazon_product_intelligence.contracts import (
    ContractValidationError,
    JsonContract,
    canonical_json,
    deterministic_id,
)


_CURRENCY = re.compile(r"^[A-Z]{3}$")


class MarketReportV0_2ValidationError(ContractValidationError):
    """Raised when a V0.2 foundation contract violates frozen semantics."""


class Availability(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


class PresenceStatus(StrEnum):
    PRESENT = "PRESENT"
    EXPLICIT_NULL = "EXPLICIT_NULL"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"
    QUERY_RETURNED_EMPTY = "QUERY_RETURNED_EMPTY"


class EvidenceSemantics(StrEnum):
    OBSERVED = "OBSERVED"
    PROVIDER_ESTIMATE = "PROVIDER_ESTIMATE"
    RESOLVED = "RESOLVED"
    DERIVED = "DERIVED"
    UNKNOWN = "UNKNOWN"


class CompletenessStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"
    UNRESOLVED = "UNRESOLVED"


class ReferenceKind(StrEnum):
    REPORT_LOCAL = "REPORT_LOCAL"
    EXTERNAL_PROVENANCE = "EXTERNAL_PROVENANCE"


def text(value: Any, path: str) -> str:
    if type(value) is not str or not value.strip():
        raise MarketReportV0_2ValidationError(f"{path} must be non-empty text")
    return value


def optional_text(value: Any, path: str) -> str | None:
    if value is not None:
        text(value, path)
    return value


def count(value: Any, path: str) -> int:
    if type(value) is not int or value < 0:
        raise MarketReportV0_2ValidationError(f"{path} must be a non-negative integer")
    return value


def share(value: Any, path: str) -> float:
    if type(value) not in {int, float} or isinstance(value, bool):
        raise MarketReportV0_2ValidationError(f"{path} must be numeric")
    normalized = float(value)
    if not math.isfinite(normalized) or not 0.0 <= normalized <= 1.0:
        raise MarketReportV0_2ValidationError(f"{path} must be finite and between zero and one")
    return normalized


def texts(
    values: Sequence[str] | Iterable[str],
    path: str,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise MarketReportV0_2ValidationError(f"{path} must be a collection of text")
    normalized = tuple(values)
    if any(type(item) is not str or not item.strip() for item in normalized):
        raise MarketReportV0_2ValidationError(f"{path} must contain non-empty text")
    if len(set(normalized)) != len(normalized):
        raise MarketReportV0_2ValidationError(f"{path} must contain unique values")
    if not allow_empty and not normalized:
        raise MarketReportV0_2ValidationError(f"{path} must not be empty")
    return tuple(sorted(normalized))


def policy_pair(
    policy_id: str | None,
    policy_version: str | None,
    path: str,
    *,
    required: bool = False,
) -> tuple[str | None, str | None]:
    if (policy_id is None) != (policy_version is None):
        raise MarketReportV0_2ValidationError(
            f"{path} policy id and version must be both present or both null"
        )
    if required and policy_id is None:
        raise MarketReportV0_2ValidationError(f"{path} requires a governed policy id/version")
    optional_text(policy_id, f"{path}.policy_id")
    optional_text(policy_version, f"{path}.policy_version")
    return policy_id, policy_version


def currency(value: str | None, path: str) -> str | None:
    if value is not None and not _CURRENCY.fullmatch(value):
        raise MarketReportV0_2ValidationError(f"{path} must be a three-letter uppercase currency")
    return value


def freeze_json(value: Any, path: str) -> Any:
    try:
        normalized = json.loads(canonical_json(value))
    except (ContractValidationError, TypeError, ValueError) as exc:
        raise MarketReportV0_2ValidationError(
            f"{path} must contain finite JSON-compatible data: {exc}"
        ) from exc

    def freeze(item: Any) -> Any:
        if isinstance(item, dict):
            return MappingProxyType({key: freeze(child) for key, child in item.items()})
        if isinstance(item, list):
            return tuple(freeze(child) for child in item)
        return item

    return freeze(normalized)


def without_id(model: JsonContract, field_name: str) -> dict[str, Any]:
    payload = model.to_dict()
    payload.pop(field_name)
    return payload


def identity(prefix: str, model: JsonContract, field_name: str) -> str:
    return deterministic_id(prefix, without_id(model, field_name))


class V0_2Contract(JsonContract):
    """Strict JSON contract that normalizes decode failures to the V0.2 error."""

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> Self:
        try:
            return super().from_dict(payload)
        except MarketReportV0_2ValidationError:
            raise
        except (ContractValidationError, TypeError, ValueError) as exc:
            raise MarketReportV0_2ValidationError(
                f"invalid {cls.__name__}: {exc}"
            ) from exc


@dataclass(frozen=True, slots=True, kw_only=True)
class ContractReference(V0_2Contract):
    reference_id: str
    kind: ReferenceKind
    namespace: str
    target_id: str
    target_version: str | None
    content_fingerprint: str | None
    provenance_reference_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ReferenceKind):
            raise MarketReportV0_2ValidationError("reference kind is invalid")
        for name in ("namespace", "target_id"):
            text(getattr(self, name), f"ContractReference.{name}")
        optional_text(self.target_version, "ContractReference.target_version")
        optional_text(self.content_fingerprint, "ContractReference.content_fingerprint")
        provenance = texts(
            self.provenance_reference_ids,
            "ContractReference.provenance_reference_ids",
            allow_empty=self.kind is ReferenceKind.REPORT_LOCAL,
        )
        if self.kind is ReferenceKind.EXTERNAL_PROVENANCE and self.target_version is None:
            raise MarketReportV0_2ValidationError(
                "external reference requires an explicit target version"
            )
        object.__setattr__(self, "provenance_reference_ids", provenance)
        if self.reference_id != identity("market-report-v0.2-reference", self, "reference_id"):
            raise MarketReportV0_2ValidationError("reference_id does not match reference content")


def build_reference(
    *,
    kind: ReferenceKind,
    namespace: str,
    target_id: str,
    target_version: str | None,
    content_fingerprint: str | None = None,
    provenance_reference_ids: Iterable[str] = (),
) -> ContractReference:
    content = {
        "kind": kind,
        "namespace": namespace,
        "target_id": target_id,
        "target_version": target_version,
        "content_fingerprint": content_fingerprint,
        "provenance_reference_ids": tuple(sorted(set(provenance_reference_ids))),
    }
    return ContractReference(
        reference_id=deterministic_id("market-report-v0.2-reference", content),
        **content,
    )


def normalize_references(
    values: Sequence[ContractReference],
    path: str,
    *,
    allow_empty: bool = False,
) -> tuple[ContractReference, ...]:
    if isinstance(values, (str, bytes)):
        raise MarketReportV0_2ValidationError(f"{path} must be reference records")
    normalized = tuple(values)
    if any(not isinstance(item, ContractReference) for item in normalized):
        raise MarketReportV0_2ValidationError(f"{path} contains an invalid reference")
    if not allow_empty and not normalized:
        raise MarketReportV0_2ValidationError(f"{path} must not be empty")
    if len({item.reference_id for item in normalized}) != len(normalized):
        raise MarketReportV0_2ValidationError(f"{path} contains duplicate reference IDs")
    return tuple(sorted(normalized, key=lambda item: item.reference_id))


def validate_registered_references(
    referenced_ids: Iterable[str | None],
    references: Sequence[ContractReference],
    path: str,
) -> None:
    requested = {item for item in referenced_ids if item is not None}
    known = {item.reference_id for item in references}
    missing = sorted(requested - known)
    if missing:
        raise MarketReportV0_2ValidationError(f"{path} contains orphan references: {missing}")


__all__ = (
    "Availability",
    "CompletenessStatus",
    "ContractReference",
    "EvidenceSemantics",
    "MarketReportV0_2ValidationError",
    "PresenceStatus",
    "ReferenceKind",
    "V0_2Contract",
    "build_reference",
    "count",
    "currency",
    "freeze_json",
    "identity",
    "normalize_references",
    "optional_text",
    "policy_pair",
    "share",
    "text",
    "texts",
    "validate_registered_references",
    "without_id",
)
