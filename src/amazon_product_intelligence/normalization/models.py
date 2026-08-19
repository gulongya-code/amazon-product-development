"""Immutable contracts for Canonical field normalization V0.1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import math
import re
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.contracts import (
    CanonicalObservation,
    DataQualityIssue,
    NormalizationStatus,
    PresenceStatus,
    Provenance,
    SemanticStatus,
    SubjectRef,
    Unit,
)
from amazon_product_intelligence.provider_capabilities import CapabilityStatus


NORMALIZATION_RULESET_VERSION = "canonical-normalization-v0.1"
_CANONICAL_FIELD = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class NormalizationIssueCode(StrEnum):
    INVALID_FORMAT = "INVALID_FORMAT"
    MISSING_VALUE = "MISSING_VALUE"
    EXPLICIT_NULL_VALUE = "EXPLICIT_NULL_VALUE"
    UNKNOWN_VALUE = "UNKNOWN_VALUE"
    EMPTY_VALUE = "EMPTY_VALUE"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    UNSUPPORTED_UNIT = "UNSUPPORTED_UNIT"
    AMBIGUOUS_CURRENCY = "AMBIGUOUS_CURRENCY"
    CURRENCY_CONFLICT = "CURRENCY_CONFLICT"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    INVALID_MEMBER = "INVALID_MEMBER"
    DUPLICATE_MEMBER = "DUPLICATE_MEMBER"
    CONTROL_CHARACTER_REMOVED = "CONTROL_CHARACTER_REMOVED"
    TIMEZONE_MISSING = "TIMEZONE_MISSING"
    NORMALIZATION_FAILED = "NORMALIZATION_FAILED"
    UNSUPPORTED_FIELD = "UNSUPPORTED_FIELD"
    CAPABILITY_UNAVAILABLE = "CAPABILITY_UNAVAILABLE"
    CAPABILITY_UNKNOWN = "CAPABILITY_UNKNOWN"


def _validate_datetime(name: str, value: str) -> None:
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone")


def _freeze(value: Any, path: str = "value") -> Any:
    if value is None or type(value) in {str, bool, int, date, datetime, Decimal}:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{path} must be finite")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"{path} keys must be text")
            frozen[key] = _freeze(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item, f"{path}[]") for item in value)
    raise ValueError(f"{path} has unsupported type {type(value).__name__}")


def json_value(value: Any) -> Any:
    """Return a deterministic JSON-compatible representation."""

    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {key: json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [json_value(item) for item in value]
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizationContext:
    normalization_run_id: str
    normalized_at: str
    normalization_version: str = NORMALIZATION_RULESET_VERSION

    def __post_init__(self) -> None:
        for name in ("normalization_run_id", "normalization_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        _validate_datetime("normalized_at", self.normalized_at)


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizationInput:
    canonical_field: str
    raw_value: Any
    mapped_value: Any
    presence_status: PresenceStatus
    semantic_status: SemanticStatus
    unit: Unit | None
    capability_status: CapabilityStatus
    subject: SubjectRef
    provenance: Provenance
    evidence_reference: str

    def __post_init__(self) -> None:
        if not _CANONICAL_FIELD.fullmatch(self.canonical_field):
            raise ValueError("canonical_field must be a dotted lowercase identifier")
        if not isinstance(self.evidence_reference, str) or not self.evidence_reference.strip():
            raise ValueError("evidence_reference must be non-empty text")
        if not isinstance(self.presence_status, PresenceStatus):
            raise TypeError("presence_status must be PresenceStatus")
        if not isinstance(self.semantic_status, SemanticStatus):
            raise TypeError("semantic_status must be SemanticStatus")
        if not isinstance(self.capability_status, CapabilityStatus):
            raise TypeError("capability_status must be CapabilityStatus")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise TypeError("unit must be Canonical Unit or None")
        if not isinstance(self.subject, SubjectRef):
            raise TypeError("subject must be Canonical SubjectRef")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Canonical Provenance")
        object.__setattr__(self, "raw_value", _freeze(self.raw_value, "raw_value"))
        object.__setattr__(self, "mapped_value", _freeze(self.mapped_value, "mapped_value"))
        if self.presence_status is not PresenceStatus.PRESENT and (
            self.raw_value is not None or self.mapped_value is not None
        ):
            raise ValueError("non-present input must not carry raw or mapped values")
        if self.presence_status is PresenceStatus.PRESENT and self.raw_value is None and self.mapped_value is None:
            raise ValueError("present input requires raw or mapped value")

    @classmethod
    def from_observation(
        cls,
        observation: CanonicalObservation,
        *,
        canonical_field: str,
        capability_status: CapabilityStatus,
    ) -> "NormalizationInput":
        value = observation.value
        mapped = value.normalized_value if value.normalized_value is not None else value.raw_value
        return cls(
            canonical_field=canonical_field,
            raw_value=value.raw_value,
            mapped_value=mapped,
            presence_status=value.presence_status,
            semantic_status=value.semantic_status,
            unit=value.unit,
            capability_status=capability_status,
            subject=observation.subject,
            provenance=observation.provenance,
            evidence_reference=observation.observation_id,
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizationRuleApplication:
    rule_id: str
    rule_version: str
    normalization_version: str
    normalization_run_id: str
    normalized_at: str
    input_evidence_reference: str
    input_fingerprint: str
    output_fingerprint: str
    transformations: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "rule_id",
            "rule_version",
            "normalization_version",
            "normalization_run_id",
            "input_evidence_reference",
            "input_fingerprint",
            "output_fingerprint",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty text")
        _validate_datetime("normalized_at", self.normalized_at)
        transformations = tuple(self.transformations)
        if any(not isinstance(item, str) or not item.strip() for item in transformations):
            raise ValueError("transformations must contain non-empty text")
        object.__setattr__(self, "transformations", transformations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "normalization_version": self.normalization_version,
            "normalization_run_id": self.normalization_run_id,
            "normalized_at": self.normalized_at,
            "input_evidence_reference": self.input_evidence_reference,
            "input_fingerprint": self.input_fingerprint,
            "output_fingerprint": self.output_fingerprint,
            "transformations": list(self.transformations),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizationResult:
    canonical_field: str
    raw_value: Any
    mapped_value: Any
    normalized_value: Any
    presence_status: PresenceStatus
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    unit: Unit | None
    capability_status: CapabilityStatus
    issues: tuple[DataQualityIssue, ...]
    application: NormalizationRuleApplication | None
    provenance: Provenance

    def __post_init__(self) -> None:
        if not _CANONICAL_FIELD.fullmatch(self.canonical_field):
            raise ValueError("canonical_field must be a dotted lowercase identifier")
        for name in ("raw_value", "mapped_value", "normalized_value"):
            object.__setattr__(self, name, _freeze(getattr(self, name), name))
        object.__setattr__(self, "issues", tuple(self.issues))
        if not isinstance(self.presence_status, PresenceStatus):
            raise TypeError("presence_status must be PresenceStatus")
        if not isinstance(self.normalization_status, NormalizationStatus):
            raise TypeError("normalization_status must be NormalizationStatus")
        if not isinstance(self.semantic_status, SemanticStatus):
            raise TypeError("semantic_status must be SemanticStatus")
        if not isinstance(self.capability_status, CapabilityStatus):
            raise TypeError("capability_status must be CapabilityStatus")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise TypeError("unit must be Canonical Unit or None")
        if any(not isinstance(issue, DataQualityIssue) for issue in self.issues):
            raise TypeError("issues must contain Canonical DataQualityIssue records")
        if self.application is not None and not isinstance(self.application, NormalizationRuleApplication):
            raise TypeError("application must be NormalizationRuleApplication or None")
        if not isinstance(self.provenance, Provenance):
            raise TypeError("provenance must be Canonical Provenance")

    def to_dict(self) -> dict[str, Any]:
        return {
            "canonical_field": self.canonical_field,
            "raw_value": json_value(self.raw_value),
            "mapped_value": json_value(self.mapped_value),
            "normalized_value": json_value(self.normalized_value),
            "presence_status": self.presence_status.value,
            "normalization_status": self.normalization_status.value,
            "semantic_status": self.semantic_status.value,
            "unit": None if self.unit is None else self.unit.to_dict(),
            "capability_status": self.capability_status.value,
            "issues": [issue.to_dict() for issue in self.issues],
            "application": None if self.application is None else self.application.to_dict(),
            "provenance": self.provenance.to_dict(),
        }


__all__ = (
    "NORMALIZATION_RULESET_VERSION",
    "NormalizationContext",
    "NormalizationInput",
    "NormalizationIssueCode",
    "NormalizationResult",
    "NormalizationRuleApplication",
    "json_value",
)
