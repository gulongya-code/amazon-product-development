"""Immutable contracts for calculated-field specifications and execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
import math
import re
from types import MappingProxyType
from typing import Any

from amazon_product_intelligence.contracts import (
    canonical_json,
    DataQualityIssue,
    NormalizationStatus,
    PresenceStatus,
    Provenance,
    SemanticStatus,
    Unit,
)

from .errors import InvalidCalculationInputError


CALCULATION_ENGINE_VERSION = "calculation-engine-foundation-v0.1"
_FIELD_ID = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


class CalculationTier(StrEnum):
    BASE_DETERMINISTIC = "BASE_DETERMINISTIC"
    MARKET_DERIVED = "MARKET_DERIVED"
    COMPETITION_DERIVED = "COMPETITION_DERIVED"
    KEYWORD_DERIVED = "KEYWORD_DERIVED"
    PROFIT_COST_DERIVED = "PROFIT_COST_DERIVED"
    COMPOSITE_SCORE = "COMPOSITE_SCORE"
    AI_DECISION = "AI_DECISION"
    OTHER = "OTHER"


class FormulaStatus(StrEnum):
    DEFINED = "DEFINED"
    PARTIALLY_DEFINED = "PARTIALLY_DEFINED"
    FORMULA_UNSPECIFIED = "FORMULA_UNSPECIFIED"
    BUSINESS_DECISION_REQUIRED = "BUSINESS_DECISION_REQUIRED"
    BLOCKED_BY_SOURCE_FIELD = "BLOCKED_BY_SOURCE_FIELD"
    CLASSIFICATION_REVIEW_REQUIRED = "CLASSIFICATION_REVIEW_REQUIRED"


class FormulaConfidence(StrEnum):
    CONFIRMED = "CONFIRMED"
    DOCUMENTED = "DOCUMENTED"
    UNSPECIFIED = "UNSPECIFIED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class DependencyType(StrEnum):
    CANONICAL_INPUT = "CANONICAL_INPUT"
    CALCULATED_FIELD = "CALCULATED_FIELD"
    SYSTEM_RECORD = "SYSTEM_RECORD"
    METADATA = "METADATA"
    MANUAL = "MANUAL"
    AI_LAYER = "AI_LAYER"


class MissingPolicy(StrEnum):
    REQUIRE_ALL = "REQUIRE_ALL"
    ALLOW_PARTIAL = "ALLOW_PARTIAL"
    IGNORE_MISSING = "IGNORE_MISSING"
    DEFAULT_ONLY_IF_EXPLICIT = "DEFAULT_ONLY_IF_EXPLICIT"
    NOT_APPLICABLE_PROPAGATES = "NOT_APPLICABLE_PROPAGATES"
    UNKNOWN_PROPAGATES = "UNKNOWN_PROPAGATES"


class ImplementationStatus(StrEnum):
    READY_FOR_IMPLEMENTATION = "READY_FOR_IMPLEMENTATION"
    EXISTING_OTHER_LAYER = "EXISTING_OTHER_LAYER"
    BLOCKED_BY_DEPENDENCY = "BLOCKED_BY_DEPENDENCY"
    FORMULA_MISSING = "FORMULA_MISSING"
    BUSINESS_RULE_REQUIRED = "BUSINESS_RULE_REQUIRED"
    CLASSIFICATION_REVIEW = "CLASSIFICATION_REVIEW"
    DEFERRED_TO_AI = "DEFERRED_TO_AI"


class InputResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


class CalculationStatus(StrEnum):
    CALCULATED = "CALCULATED"
    PARTIAL = "PARTIAL"
    MISSING_INPUT = "MISSING_INPUT"
    UNKNOWN_INPUT = "UNKNOWN_INPUT"
    INVALID_INPUT = "INVALID_INPUT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    DEPENDENCY_BLOCKED = "DEPENDENCY_BLOCKED"
    FORMULA_UNDEFINED = "FORMULA_UNDEFINED"
    DIVISION_BY_ZERO = "DIVISION_BY_ZERO"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    CURRENCY_MISMATCH = "CURRENCY_MISMATCH"
    FAILED = "FAILED"


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InvalidCalculationInputError(f"{name} must be non-empty text")
    return value


def _field(name: str, value: str) -> str:
    _text(name, value)
    if _FIELD_ID.fullmatch(value) is None:
        raise InvalidCalculationInputError(f"{name} must be a dotted lowercase identifier")
    return value


def _freeze(value: Any, path: str = "value") -> Any:
    if value is None or type(value) in {str, bool, int, date, datetime, Decimal}:
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise InvalidCalculationInputError(f"{path} must be finite")
        return value
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise InvalidCalculationInputError(f"{path} keys must be text")
            frozen[key] = _freeze(item, f"{path}.{key}")
        return MappingProxyType(frozen)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return tuple(_freeze(item, f"{path}[]") for item in value)
    raise InvalidCalculationInputError(f"{path} has unsupported type {type(value).__name__}")


def json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, Mapping):
        return {key: json_value(item) for key, item in sorted(value.items())}
    if isinstance(value, tuple):
        return [json_value(item) for item in value]
    if hasattr(value, "to_dict"):
        return value.to_dict()
    return value


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationDependency:
    field_id: str
    dependency_type: DependencyType
    required: bool = True

    def __post_init__(self) -> None:
        _field("dependency.field_id", self.field_id)
        if not isinstance(self.dependency_type, DependencyType):
            raise InvalidCalculationInputError("dependency_type must be DependencyType")
        if not isinstance(self.required, bool):
            raise InvalidCalculationInputError("dependency.required must be bool")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "dependency_type": self.dependency_type.value,
            "required": self.required,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculatedFieldSpec:
    field_id: str
    workbook_sheet: str
    display_name: str
    canonical_field: str
    category: str
    calculation_tier: CalculationTier
    output_type: str
    unit: str
    dependencies: tuple[CalculationDependency, ...]
    formula_status: FormulaStatus
    formula_reference: str
    missing_policy: MissingPolicy
    zero_semantics: str
    invalid_input_policy: str
    partial_input_policy: str
    calculation_version: str
    calculation_rule_id: str | None
    provenance_requirement: str
    formula_confidence: FormulaConfidence
    quality_implication: str
    implementation_status: ImplementationStatus
    notes: str

    def __post_init__(self) -> None:
        _field("field_id", self.field_id)
        for name in (
            "workbook_sheet",
            "display_name",
            "canonical_field",
            "category",
            "output_type",
            "unit",
            "formula_reference",
            "zero_semantics",
            "invalid_input_policy",
            "partial_input_policy",
            "calculation_version",
            "provenance_requirement",
            "quality_implication",
            "notes",
        ):
            _text(name, getattr(self, name))
        if self.calculation_rule_id is not None:
            _field("calculation_rule_id", self.calculation_rule_id)
        for name, expected in (
            ("calculation_tier", CalculationTier),
            ("formula_status", FormulaStatus),
            ("missing_policy", MissingPolicy),
            ("formula_confidence", FormulaConfidence),
            ("implementation_status", ImplementationStatus),
        ):
            if not isinstance(getattr(self, name), expected):
                raise InvalidCalculationInputError(f"{name} must be {expected.__name__}")
        dependencies = tuple(self.dependencies)
        if any(not isinstance(item, CalculationDependency) for item in dependencies):
            raise InvalidCalculationInputError("dependencies must contain CalculationDependency")
        ids = tuple(item.field_id for item in dependencies)
        if len(ids) != len(set(ids)):
            raise InvalidCalculationInputError("dependencies must be unique")
        if self.field_id in ids:
            raise InvalidCalculationInputError("field cannot directly depend on itself")
        if self.formula_status is FormulaStatus.DEFINED:
            if self.calculation_rule_id is None:
                raise InvalidCalculationInputError("DEFINED formula requires calculation_rule_id")
            if self.formula_confidence not in {
                FormulaConfidence.CONFIRMED,
                FormulaConfidence.DOCUMENTED,
            }:
                raise InvalidCalculationInputError(
                    "DEFINED formula requires CONFIRMED or DOCUMENTED confidence"
                )
        object.__setattr__(self, "dependencies", dependencies)

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "workbook_sheet": self.workbook_sheet,
            "display_name": self.display_name,
            "canonical_field": self.canonical_field,
            "category": self.category,
            "calculation_tier": self.calculation_tier.value,
            "output_type": self.output_type,
            "unit": self.unit,
            "dependencies": [item.to_dict() for item in self.dependencies],
            "formula_status": self.formula_status.value,
            "formula_reference": self.formula_reference,
            "missing_policy": self.missing_policy.value,
            "zero_semantics": self.zero_semantics,
            "invalid_input_policy": self.invalid_input_policy,
            "partial_input_policy": self.partial_input_policy,
            "calculation_version": self.calculation_version,
            "calculation_rule_id": self.calculation_rule_id,
            "provenance_requirement": self.provenance_requirement,
            "formula_confidence": self.formula_confidence.value,
            "quality_implication": self.quality_implication,
            "implementation_status": self.implementation_status.value,
            "notes": self.notes,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationContext:
    calculation_run_id: str
    configuration_version: str
    engine_version: str = CALCULATION_ENGINE_VERSION

    def __post_init__(self) -> None:
        for name in ("calculation_run_id", "configuration_version", "engine_version"):
            _text(name, getattr(self, name))


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationInput:
    field_id: str
    value: Any
    presence_status: PresenceStatus
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    unit: Unit | None
    resolution_status: InputResolutionStatus
    evidence_references: tuple[str, ...]
    provenances: tuple[Provenance, ...]
    quality_issues: tuple[DataQualityIssue, ...] = ()

    def __post_init__(self) -> None:
        _field("input.field_id", self.field_id)
        object.__setattr__(self, "value", _freeze(self.value, "input.value"))
        for name, expected in (
            ("presence_status", PresenceStatus),
            ("normalization_status", NormalizationStatus),
            ("semantic_status", SemanticStatus),
            ("resolution_status", InputResolutionStatus),
        ):
            if not isinstance(getattr(self, name), expected):
                raise InvalidCalculationInputError(f"{name} must be {expected.__name__}")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise InvalidCalculationInputError("input unit must be Canonical Unit or None")
        references = tuple(self.evidence_references)
        provenances = tuple(self.provenances)
        issues = tuple(self.quality_issues)
        if not references or any(not isinstance(item, str) or not item.strip() for item in references):
            raise InvalidCalculationInputError("input requires evidence references")
        if len(references) != len(set(references)):
            raise InvalidCalculationInputError("input evidence references must be unique")
        if not provenances or any(not isinstance(item, Provenance) for item in provenances):
            raise InvalidCalculationInputError("input requires existing Canonical Provenance")
        if any(not isinstance(item, DataQualityIssue) for item in issues):
            raise InvalidCalculationInputError("quality_issues must contain DataQualityIssue")
        object.__setattr__(self, "evidence_references", tuple(sorted(references)))
        object.__setattr__(
            self,
            "provenances",
            tuple(sorted(provenances, key=canonical_json)),
        )
        object.__setattr__(self, "quality_issues", tuple(sorted(issues, key=lambda item: item.issue_id)))
        if self.presence_status is PresenceStatus.PRESENT and self.value is None:
            raise InvalidCalculationInputError("PRESENT calculation input requires a value")
        if self.presence_status is not PresenceStatus.PRESENT and self.value is not None:
            raise InvalidCalculationInputError("non-present calculation input must not carry a value")
        if (
            self.presence_status is not PresenceStatus.PRESENT
            and self.normalization_status is NormalizationStatus.NORMALIZED
        ):
            raise InvalidCalculationInputError("non-present calculation input cannot be NORMALIZED")

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "value": json_value(self.value),
            "presence_status": self.presence_status.value,
            "normalization_status": self.normalization_status.value,
            "semantic_status": self.semantic_status.value,
            "unit": None if self.unit is None else self.unit.to_dict(),
            "resolution_status": self.resolution_status.value,
            "evidence_references": list(self.evidence_references),
            "provenances": [item.to_dict() for item in self.provenances],
            "quality_issues": [item.to_dict() for item in self.quality_issues],
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationIssue:
    code: str
    message: str
    dependency_field: str | None = None

    def __post_init__(self) -> None:
        _text("issue.code", self.code)
        _text("issue.message", self.message)
        if self.dependency_field is not None:
            _field("issue.dependency_field", self.dependency_field)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "dependency_field": self.dependency_field,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationInputLineage:
    field_id: str
    normalized_value: Any
    presence_status: PresenceStatus
    normalization_status: NormalizationStatus
    semantic_status: SemanticStatus
    resolution_status: InputResolutionStatus
    unit: Unit | None
    evidence_references: tuple[str, ...]
    provenances: tuple[Provenance, ...]
    quality_issue_ids: tuple[str, ...]
    input_fingerprint: str

    def __post_init__(self) -> None:
        _field("lineage.field_id", self.field_id)
        _text("lineage.input_fingerprint", self.input_fingerprint)
        object.__setattr__(self, "normalized_value", _freeze(self.normalized_value, "lineage.normalized_value"))
        for name, expected in (
            ("presence_status", PresenceStatus),
            ("normalization_status", NormalizationStatus),
            ("semantic_status", SemanticStatus),
            ("resolution_status", InputResolutionStatus),
        ):
            if not isinstance(getattr(self, name), expected):
                raise InvalidCalculationInputError(f"lineage {name} has wrong type")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise InvalidCalculationInputError("lineage unit has wrong type")
        object.__setattr__(self, "evidence_references", tuple(sorted(self.evidence_references)))
        object.__setattr__(self, "provenances", tuple(self.provenances))
        object.__setattr__(self, "quality_issue_ids", tuple(sorted(self.quality_issue_ids)))

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_id": self.field_id,
            "normalized_value": json_value(self.normalized_value),
            "presence_status": self.presence_status.value,
            "normalization_status": self.normalization_status.value,
            "semantic_status": self.semantic_status.value,
            "resolution_status": self.resolution_status.value,
            "unit": None if self.unit is None else self.unit.to_dict(),
            "evidence_references": list(self.evidence_references),
            "provenances": [item.to_dict() for item in self.provenances],
            "quality_issue_ids": list(self.quality_issue_ids),
            "input_fingerprint": self.input_fingerprint,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationProvenance:
    calculation_rule_id: str
    calculation_version: str
    calculation_run_id: str
    configuration_version: str
    input_lineage: tuple[CalculationInputLineage, ...]
    calculated_dependency_result_ids: tuple[str, ...]
    input_fingerprint: str
    output_fingerprint: str

    def __post_init__(self) -> None:
        _field("provenance.calculation_rule_id", self.calculation_rule_id)
        for name in (
            "calculation_version",
            "calculation_run_id",
            "configuration_version",
            "input_fingerprint",
            "output_fingerprint",
        ):
            _text(name, getattr(self, name))
        lineage = tuple(sorted(self.input_lineage, key=lambda item: item.field_id))
        if any(not isinstance(item, CalculationInputLineage) for item in lineage):
            raise InvalidCalculationInputError("input_lineage has wrong type")
        dependency_ids = tuple(sorted(self.calculated_dependency_result_ids))
        if len(dependency_ids) != len(set(dependency_ids)):
            raise InvalidCalculationInputError("calculated dependency result IDs must be unique")
        object.__setattr__(self, "input_lineage", lineage)
        object.__setattr__(self, "calculated_dependency_result_ids", dependency_ids)

    def to_dict(self) -> dict[str, Any]:
        return {
            "calculation_rule_id": self.calculation_rule_id,
            "calculation_version": self.calculation_version,
            "calculation_run_id": self.calculation_run_id,
            "configuration_version": self.configuration_version,
            "input_lineage": [item.to_dict() for item in self.input_lineage],
            "calculated_dependency_result_ids": list(self.calculated_dependency_result_ids),
            "input_fingerprint": self.input_fingerprint,
            "output_fingerprint": self.output_fingerprint,
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationOutcome:
    value: Any
    unit: Unit | None
    status: CalculationStatus = CalculationStatus.CALCULATED
    issues: tuple[CalculationIssue, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", _freeze(self.value, "outcome.value"))
        object.__setattr__(self, "issues", tuple(self.issues))
        if self.status not in {CalculationStatus.CALCULATED, CalculationStatus.PARTIAL}:
            raise InvalidCalculationInputError("formula outcome status must be CALCULATED or PARTIAL")
        if self.value is None:
            raise InvalidCalculationInputError("successful formula outcome requires a value")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise InvalidCalculationInputError("outcome unit must be Canonical Unit or None")
        if any(not isinstance(item, CalculationIssue) for item in self.issues):
            raise InvalidCalculationInputError("outcome issues have wrong type")


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationEvaluationContext:
    spec: CalculatedFieldSpec
    values: Mapping[str, Any]
    units: Mapping[str, Unit | None]

    def __post_init__(self) -> None:
        if not isinstance(self.spec, CalculatedFieldSpec):
            raise InvalidCalculationInputError("evaluation spec has wrong type")
        object.__setattr__(self, "values", _freeze(self.values, "evaluation.values"))
        units = dict(self.units)
        if any(value is not None and not isinstance(value, Unit) for value in units.values()):
            raise InvalidCalculationInputError("evaluation units contain wrong type")
        object.__setattr__(self, "units", MappingProxyType(units))


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationResult:
    result_id: str
    field_id: str
    value: Any
    status: CalculationStatus
    unit: Unit | None
    input_fields: tuple[str, ...]
    issues: tuple[CalculationIssue, ...]
    calculation_rule_id: str | None
    calculation_version: str
    provenance: CalculationProvenance | None

    def __post_init__(self) -> None:
        _text("result_id", self.result_id)
        _field("result.field_id", self.field_id)
        object.__setattr__(self, "value", _freeze(self.value, "result.value"))
        object.__setattr__(self, "input_fields", tuple(sorted(self.input_fields)))
        object.__setattr__(self, "issues", tuple(self.issues))
        if not isinstance(self.status, CalculationStatus):
            raise InvalidCalculationInputError("result status has wrong type")
        if self.status in {CalculationStatus.CALCULATED, CalculationStatus.PARTIAL}:
            if self.value is None or self.provenance is None:
                raise InvalidCalculationInputError("successful result requires value and provenance")
        elif self.value is not None:
            raise InvalidCalculationInputError("unsuccessful result cannot contain a value")
        if self.unit is not None and not isinstance(self.unit, Unit):
            raise InvalidCalculationInputError("result unit has wrong type")
        if self.calculation_rule_id is not None:
            _field("result.calculation_rule_id", self.calculation_rule_id)
        _text("result.calculation_version", self.calculation_version)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_id": self.result_id,
            "field_id": self.field_id,
            "value": json_value(self.value),
            "status": self.status.value,
            "unit": None if self.unit is None else self.unit.to_dict(),
            "input_fields": list(self.input_fields),
            "issues": [item.to_dict() for item in self.issues],
            "calculation_rule_id": self.calculation_rule_id,
            "calculation_version": self.calculation_version,
            "provenance": None if self.provenance is None else self.provenance.to_dict(),
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationPlan:
    requested_fields: tuple[str, ...]
    execution_order: tuple[str, ...]
    external_dependencies: tuple[str, ...]
    blocked_fields: Mapping[str, tuple[str, ...]]

    def __post_init__(self) -> None:
        object.__setattr__(self, "requested_fields", tuple(sorted(self.requested_fields)))
        object.__setattr__(self, "execution_order", tuple(self.execution_order))
        object.__setattr__(self, "external_dependencies", tuple(sorted(self.external_dependencies)))
        blocked = {
            field: tuple(sorted(reasons))
            for field, reasons in sorted(self.blocked_fields.items())
        }
        object.__setattr__(self, "blocked_fields", MappingProxyType(blocked))

    def to_dict(self) -> dict[str, Any]:
        return {
            "requested_fields": list(self.requested_fields),
            "execution_order": list(self.execution_order),
            "external_dependencies": list(self.external_dependencies),
            "blocked_fields": {key: list(value) for key, value in self.blocked_fields.items()},
        }


@dataclass(frozen=True, slots=True, kw_only=True)
class CalculationBatchResult:
    plan: CalculationPlan
    results: tuple[CalculationResult, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.plan, CalculationPlan):
            raise InvalidCalculationInputError("batch plan has wrong type")
        results = tuple(self.results)
        if any(not isinstance(item, CalculationResult) for item in results):
            raise InvalidCalculationInputError("batch results have wrong type")
        if len({item.field_id for item in results}) != len(results):
            raise InvalidCalculationInputError("batch results contain duplicate fields")
        object.__setattr__(self, "results", results)

    def get(self, field_id: str) -> CalculationResult:
        for result in self.results:
            if result.field_id == field_id:
                return result
        raise KeyError(field_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan": self.plan.to_dict(),
            "results": [item.to_dict() for item in self.results],
        }


__all__ = (
    "CALCULATION_ENGINE_VERSION",
    "CalculatedFieldSpec",
    "CalculationBatchResult",
    "CalculationContext",
    "CalculationDependency",
    "CalculationEvaluationContext",
    "CalculationInput",
    "CalculationInputLineage",
    "CalculationIssue",
    "CalculationOutcome",
    "CalculationPlan",
    "CalculationProvenance",
    "CalculationResult",
    "CalculationStatus",
    "CalculationTier",
    "DependencyType",
    "FormulaConfidence",
    "FormulaStatus",
    "ImplementationStatus",
    "InputResolutionStatus",
    "MissingPolicy",
    "json_value",
)
