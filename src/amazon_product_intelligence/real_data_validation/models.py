"""Immutable contracts for Real Data Validation V0.1.

These contracts record what a validation run observed.  They do not change,
calibrate, or reinterpret any upstream intelligence or scoring model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from amazon_product_intelligence.contracts import JsonContract, deterministic_id


REAL_DATA_VALIDATION_VERSION = "real-data-validation-v0.1"


class ValidationContractError(ValueError):
    """Raised when a validation artifact is internally inconsistent."""


class ValidationStageStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    BLOCKED = "BLOCKED"


class ValidationIssueCategory(StrEnum):
    DATA_QUALITY = "DATA_QUALITY"
    EXTRACTION_RULE = "EXTRACTION_RULE"
    TAXONOMY = "TAXONOMY"
    DEMAND_MODEL = "DEMAND_MODEL"
    COMPETITION = "COMPETITION"
    SCORING = "SCORING"
    OTHER = "OTHER"


class ValidationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    BLOCKING = "BLOCKING"


class AttributeAuditOutcome(StrEnum):
    CORRECT = "CORRECT"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValidationContractError(f"{name} must be non-empty text")


def _count(value: int, name: str) -> None:
    if type(value) is not int or value < 0:
        raise ValidationContractError(f"{name} must be a non-negative integer")


def _ratio(value: str, name: str) -> None:
    try:
        numeric = float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationContractError(f"{name} must be a decimal ratio") from exc
    if numeric < 0.0 or numeric > 1.0:
        raise ValidationContractError(f"{name} must be between zero and one")


def ratio_text(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0.0000"
    return f"{numerator / denominator:.4f}"


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationCategoryScope(JsonContract):
    category: str
    subcategory: str
    cohort_query: str
    inclusion_rule: str

    def __post_init__(self) -> None:
        for name in ("category", "subcategory", "cohort_query", "inclusion_rule"):
            _text(getattr(self, name), f"category_scope.{name}")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationAnalysisWindow(JsonContract):
    period_label: str
    period_start: str | None
    period_end: str | None
    retrieved_at: str

    def __post_init__(self) -> None:
        _text(self.period_label, "analysis_window.period_label")
        _text(self.retrieved_at, "analysis_window.retrieved_at")
        if (self.period_start is None) != (self.period_end is None):
            raise ValidationContractError("analysis window bounds must be known together")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationDataSource(JsonContract):
    provider: str
    operation: str
    source_reference: str
    live_request: bool

    def __post_init__(self) -> None:
        for name in ("provider", "operation", "source_reference"):
            _text(getattr(self, name), f"data_source.{name}")
        if type(self.live_request) is not bool:
            raise ValidationContractError("data_source.live_request must be boolean")


@dataclass(frozen=True, slots=True, kw_only=True)
class ModuleVersion(JsonContract):
    module: str
    version: str

    def __post_init__(self) -> None:
        _text(self.module, "module_version.module")
        _text(self.version, "module_version.version")


@dataclass(frozen=True, slots=True, kw_only=True)
class StageCoverage(JsonContract):
    stage: str
    input_count: int
    output_count: int
    failure_count: int
    unknown_count: int
    coverage: str
    unknown_rate: str
    status: ValidationStageStatus
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _text(self.stage, "stage_coverage.stage")
        for name in ("input_count", "output_count", "failure_count", "unknown_count"):
            _count(getattr(self, name), f"stage_coverage.{name}")
        _ratio(self.coverage, "stage_coverage.coverage")
        _ratio(self.unknown_rate, "stage_coverage.unknown_rate")
        if not isinstance(self.status, ValidationStageStatus):
            raise ValidationContractError("stage coverage status is invalid")
        notes = tuple(self.notes)
        if any(not isinstance(item, str) or not item.strip() for item in notes):
            raise ValidationContractError("stage coverage notes require non-empty text")
        object.__setattr__(self, "notes", tuple(sorted(set(notes))))


def build_stage_coverage(
    *,
    stage: str,
    input_count: int,
    output_count: int,
    failure_count: int,
    unknown_count: int,
    covered_count: int | None = None,
    notes: tuple[str, ...] = (),
) -> StageCoverage:
    for name, value in (
        ("input_count", input_count),
        ("output_count", output_count),
        ("failure_count", failure_count),
        ("unknown_count", unknown_count),
    ):
        _count(value, name)
    covered = output_count if covered_count is None else covered_count
    _count(covered, "covered_count")
    if input_count and covered > input_count:
        raise ValidationContractError("covered_count cannot exceed input_count")
    status = (
        ValidationStageStatus.BLOCKED
        if input_count > 0 and output_count == 0
        else ValidationStageStatus.PARTIAL
        if failure_count or unknown_count or covered < input_count
        else ValidationStageStatus.COMPLETE
    )
    return StageCoverage(
        stage=stage,
        input_count=input_count,
        output_count=output_count,
        failure_count=failure_count,
        unknown_count=unknown_count,
        coverage=ratio_text(covered, input_count),
        unknown_rate=ratio_text(unknown_count, input_count),
        status=status,
        notes=notes,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationDiagnostic(JsonContract):
    code: str
    severity: ValidationSeverity
    stage: str
    message: str
    related_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("code", "stage", "message"):
            _text(getattr(self, name), f"diagnostic.{name}")
        if not isinstance(self.severity, ValidationSeverity):
            raise ValidationContractError("diagnostic severity is invalid")
        related = tuple(self.related_ids)
        if any(not isinstance(item, str) or not item.strip() for item in related):
            raise ValidationContractError("diagnostic related ids require text")
        object.__setattr__(self, "related_ids", tuple(sorted(set(related))))


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationIssue(JsonContract):
    issue_id: str
    category: ValidationIssueCategory
    severity: ValidationSeverity
    title: str
    problem: str
    affected_modules: tuple[str, ...]
    recommended_fix: str
    evidence_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.category, ValidationIssueCategory):
            raise ValidationContractError("issue category is invalid")
        if not isinstance(self.severity, ValidationSeverity):
            raise ValidationContractError("issue severity is invalid")
        for name in ("title", "problem", "recommended_fix"):
            _text(getattr(self, name), f"issue.{name}")
        modules = tuple(self.affected_modules)
        evidence = tuple(self.evidence_references)
        if not modules or any(not isinstance(item, str) or not item.strip() for item in modules):
            raise ValidationContractError("issue affected_modules require text")
        if any(not isinstance(item, str) or not item.strip() for item in evidence):
            raise ValidationContractError("issue evidence_references require text")
        object.__setattr__(self, "affected_modules", tuple(sorted(set(modules))))
        object.__setattr__(self, "evidence_references", tuple(sorted(set(evidence))))
        material = self.to_dict()
        material.pop("issue_id")
        if self.issue_id != deterministic_id("validation-issue", material):
            raise ValidationContractError("issue_id does not match issue content")


def build_validation_issue(
    *,
    category: ValidationIssueCategory,
    severity: ValidationSeverity,
    title: str,
    problem: str,
    affected_modules: tuple[str, ...],
    recommended_fix: str,
    evidence_references: tuple[str, ...] = (),
) -> ValidationIssue:
    material: dict[str, Any] = {
        "category": category,
        "severity": severity,
        "title": title,
        "problem": problem,
        "affected_modules": tuple(sorted(set(affected_modules))),
        "recommended_fix": recommended_fix,
        "evidence_references": tuple(sorted(set(evidence_references))),
    }
    return ValidationIssue(
        issue_id=deterministic_id("validation-issue", material),
        **material,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationIssueLog(JsonContract):
    log_id: str
    issues: tuple[ValidationIssue, ...]
    version: str = REAL_DATA_VALIDATION_VERSION

    def __post_init__(self) -> None:
        if self.version != REAL_DATA_VALIDATION_VERSION:
            raise ValidationContractError("issue log version is invalid")
        issues = tuple(self.issues)
        if any(not isinstance(item, ValidationIssue) for item in issues):
            raise ValidationContractError("issue log contains a wrong type")
        if len({item.issue_id for item in issues}) != len(issues):
            raise ValidationContractError("issue log ids must be unique")
        object.__setattr__(self, "issues", tuple(sorted(issues, key=lambda item: item.issue_id)))
        material = self.to_dict()
        material.pop("log_id")
        if self.log_id != deterministic_id("validation-issue-log", material):
            raise ValidationContractError("log_id does not match issue log content")


def build_validation_issue_log(issues: tuple[ValidationIssue, ...]) -> ValidationIssueLog:
    ordered = tuple(sorted(issues, key=lambda item: item.issue_id))
    material = {"issues": ordered, "version": REAL_DATA_VALIDATION_VERSION}
    return ValidationIssueLog(
        log_id=deterministic_id("validation-issue-log", material),
        **material,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeDimensionAccuracy(JsonContract):
    dimension: str
    correct_count: int
    error_count: int
    unknown_count: int
    sample_count: int
    accuracy: str
    known_coverage: str

    def __post_init__(self) -> None:
        _text(self.dimension, "attribute_accuracy.dimension")
        for name in ("correct_count", "error_count", "unknown_count", "sample_count"):
            _count(getattr(self, name), f"attribute_accuracy.{name}")
        if self.correct_count + self.error_count + self.unknown_count != self.sample_count:
            raise ValidationContractError("attribute accuracy counts must equal sample_count")
        _ratio(self.accuracy, "attribute_accuracy.accuracy")
        _ratio(self.known_coverage, "attribute_accuracy.known_coverage")


@dataclass(frozen=True, slots=True, kw_only=True)
class AttributeAccuracyReport(JsonContract):
    report_id: str
    sample_size: int
    population_size: int
    sampling_method: str
    evidence_basis: str
    dimensions: tuple[AttributeDimensionAccuracy, ...]
    limitations: tuple[str, ...]
    version: str = REAL_DATA_VALIDATION_VERSION

    def __post_init__(self) -> None:
        for name in ("sample_size", "population_size"):
            _count(getattr(self, name), f"attribute_report.{name}")
        if self.sample_size > self.population_size:
            raise ValidationContractError("attribute sample cannot exceed population")
        for name in ("sampling_method", "evidence_basis"):
            _text(getattr(self, name), f"attribute_report.{name}")
        dimensions = tuple(self.dimensions)
        if not dimensions or any(not isinstance(item, AttributeDimensionAccuracy) for item in dimensions):
            raise ValidationContractError("attribute report requires dimension results")
        if len({item.dimension for item in dimensions}) != len(dimensions):
            raise ValidationContractError("attribute report dimensions must be unique")
        if any(item.sample_count != self.sample_size for item in dimensions):
            raise ValidationContractError("each attribute dimension must cover the declared sample")
        limitations = tuple(self.limitations)
        if any(not isinstance(item, str) or not item.strip() for item in limitations):
            raise ValidationContractError("attribute report limitations require text")
        object.__setattr__(self, "dimensions", tuple(sorted(dimensions, key=lambda item: item.dimension)))
        object.__setattr__(self, "limitations", tuple(sorted(set(limitations))))
        material = self.to_dict()
        material.pop("report_id")
        if self.report_id != deterministic_id("attribute-accuracy-report", material):
            raise ValidationContractError("attribute report id does not match content")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationRunSnapshot(JsonContract):
    run_id: str
    category_scope: ValidationCategoryScope
    marketplace: str
    analysis_window: ValidationAnalysisWindow
    data_source: tuple[ValidationDataSource, ...]
    pipeline_version: str
    module_versions: tuple[ModuleVersion, ...]
    coverage: tuple[StageCoverage, ...]
    limitations: tuple[str, ...]
    diagnostics: tuple[ValidationDiagnostic, ...]
    issue_log: ValidationIssueLog
    version: str = REAL_DATA_VALIDATION_VERSION

    def __post_init__(self) -> None:
        if self.marketplace != self.marketplace.strip().upper() or not self.marketplace:
            raise ValidationContractError("validation marketplace must be uppercase")
        if not isinstance(self.category_scope, ValidationCategoryScope):
            raise ValidationContractError("validation category_scope is invalid")
        if not isinstance(self.analysis_window, ValidationAnalysisWindow):
            raise ValidationContractError("validation analysis_window is invalid")
        _text(self.pipeline_version, "validation pipeline_version")
        if self.version != REAL_DATA_VALIDATION_VERSION:
            raise ValidationContractError("validation version is invalid")
        for name, expected, key in (
            ("data_source", ValidationDataSource, lambda item: (item.provider, item.operation)),
            ("module_versions", ModuleVersion, lambda item: item.module),
            ("coverage", StageCoverage, lambda item: item.stage),
            ("diagnostics", ValidationDiagnostic, lambda item: (item.code, item.stage)),
        ):
            values = tuple(getattr(self, name))
            if any(not isinstance(item, expected) for item in values):
                raise ValidationContractError(f"validation {name} contains a wrong type")
            ordered = tuple(sorted(values, key=key))
            if len({key(item) for item in ordered}) != len(ordered):
                raise ValidationContractError(f"validation {name} keys must be unique")
            object.__setattr__(self, name, ordered)
        limitations = tuple(self.limitations)
        if any(not isinstance(item, str) or not item.strip() for item in limitations):
            raise ValidationContractError("validation limitations require text")
        object.__setattr__(self, "limitations", tuple(sorted(set(limitations))))
        if not isinstance(self.issue_log, ValidationIssueLog):
            raise ValidationContractError("validation issue_log is invalid")
        material = self.to_dict()
        material.pop("run_id")
        if self.run_id != deterministic_id("real-data-validation-run", material):
            raise ValidationContractError("run_id does not match validation content")


def build_validation_run_snapshot(**values: Any) -> ValidationRunSnapshot:
    normalized = dict(values)
    normalized["data_source"] = tuple(
        sorted(normalized["data_source"], key=lambda item: (item.provider, item.operation))
    )
    normalized["module_versions"] = tuple(
        sorted(normalized["module_versions"], key=lambda item: item.module)
    )
    normalized["coverage"] = tuple(
        sorted(normalized["coverage"], key=lambda item: item.stage)
    )
    normalized["diagnostics"] = tuple(
        sorted(normalized["diagnostics"], key=lambda item: (item.code, item.stage))
    )
    normalized["limitations"] = tuple(sorted(set(normalized["limitations"])))
    material: Mapping[str, Any] = {
        **normalized,
        "version": REAL_DATA_VALIDATION_VERSION,
    }
    return ValidationRunSnapshot(
        run_id=deterministic_id("real-data-validation-run", material),
        **material,
    )


__all__ = (
    "REAL_DATA_VALIDATION_VERSION",
    "AttributeAccuracyReport",
    "AttributeAuditOutcome",
    "AttributeDimensionAccuracy",
    "ModuleVersion",
    "StageCoverage",
    "ValidationAnalysisWindow",
    "ValidationCategoryScope",
    "ValidationContractError",
    "ValidationDataSource",
    "ValidationDiagnostic",
    "ValidationIssue",
    "ValidationIssueCategory",
    "ValidationIssueLog",
    "ValidationRunSnapshot",
    "ValidationSeverity",
    "ValidationStageStatus",
    "build_stage_coverage",
    "build_validation_issue",
    "build_validation_issue_log",
    "build_validation_run_snapshot",
    "ratio_text",
)
