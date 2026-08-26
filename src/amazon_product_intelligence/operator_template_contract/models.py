"""Immutable contracts for the frozen 11+4 Operator Template V1."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Any

from amazon_product_intelligence.contracts import JsonContract, canonical_json

from .errors import OperatorTemplateContractValidationError


OPERATOR_TEMPLATE_RULESET_VERSION = "operator-template-contract-v1.0"


class SheetVisibility(StrEnum):
    VISIBLE = "VISIBLE"
    HIDDEN = "HIDDEN"


class RawHeaderRequirement(StrEnum):
    CORE = "CORE"
    OPTIONAL = "OPTIONAL"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class FormulaDisposition(StrEnum):
    REUSE_AS_FORMULA = "REUSE_AS_FORMULA"
    MOVE_TO_CONFIG = "MOVE_TO_CONFIG"
    IMPLEMENT_IN_CODE_AND_MIRROR_IN_EXCEL = (
        "IMPLEMENT_IN_CODE_AND_MIRROR_IN_EXCEL"
    )
    DEPRECATED = "DEPRECATED"


@dataclass(frozen=True, slots=True, kw_only=True)
class SheetContract(JsonContract):
    name: str
    ordinal: int
    visibility: SheetVisibility

    def __post_init__(self) -> None:
        if type(self.name) is not str or not self.name.strip():
            raise OperatorTemplateContractValidationError(
                "sheet name must be non-empty text"
            )
        if type(self.ordinal) is not int or self.ordinal < 1:
            raise OperatorTemplateContractValidationError(
                "sheet ordinal must be a positive integer"
            )
        if not isinstance(self.visibility, SheetVisibility):
            raise OperatorTemplateContractValidationError(
                "sheet visibility is invalid"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class RawHeaderContract(JsonContract):
    name: str
    requirement: RawHeaderRequirement
    semantic_note: str

    def __post_init__(self) -> None:
        if type(self.name) is not str or not self.name.strip():
            raise OperatorTemplateContractValidationError(
                "raw header name must be non-empty text"
            )
        if not isinstance(self.requirement, RawHeaderRequirement):
            raise OperatorTemplateContractValidationError(
                "raw header requirement is invalid"
            )
        if type(self.semantic_note) is not str or not self.semantic_note.strip():
            raise OperatorTemplateContractValidationError(
                f"raw header {self.name} requires a semantic note"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class FormulaPolicy(JsonContract):
    sheet_name: str
    range_ref: str
    disposition: FormulaDisposition
    numeric_literals_to_config: bool
    rationale: str

    def __post_init__(self) -> None:
        for path, value in (
            ("formula policy sheet_name", self.sheet_name),
            ("formula policy range_ref", self.range_ref),
            ("formula policy rationale", self.rationale),
        ):
            if type(value) is not str or not value.strip():
                raise OperatorTemplateContractValidationError(
                    f"{path} must be non-empty text"
                )
        if not isinstance(self.disposition, FormulaDisposition):
            raise OperatorTemplateContractValidationError(
                "formula disposition is invalid"
            )
        if type(self.numeric_literals_to_config) is not bool:
            raise OperatorTemplateContractValidationError(
                "numeric_literals_to_config must be boolean"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class FormulaCensusReference(JsonContract):
    sheet_name: str
    approximate_count: int

    def __post_init__(self) -> None:
        if type(self.sheet_name) is not str or not self.sheet_name.strip():
            raise OperatorTemplateContractValidationError(
                "formula census sheet_name must be non-empty text"
            )
        if type(self.approximate_count) is not int or self.approximate_count < 0:
            raise OperatorTemplateContractValidationError(
                "formula census count must be a non-negative integer"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class DependencyRequirement(JsonContract):
    kind: str
    name: str
    sheet_name: str | None
    required: bool

    def __post_init__(self) -> None:
        if self.kind not in {"NAMED_RANGE", "AUTO_FILTER"}:
            raise OperatorTemplateContractValidationError(
                "dependency kind must be NAMED_RANGE or AUTO_FILTER"
            )
        if type(self.name) is not str or not self.name.strip():
            raise OperatorTemplateContractValidationError(
                "dependency name must be non-empty text"
            )
        if self.sheet_name is not None and (
            type(self.sheet_name) is not str or not self.sheet_name.strip()
        ):
            raise OperatorTemplateContractValidationError(
                "dependency sheet_name must be non-empty text or null"
            )
        if type(self.required) is not bool:
            raise OperatorTemplateContractValidationError(
                "dependency required must be boolean"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ThresholdRule(JsonContract):
    rule_id: str
    source: str
    frozen_value: str
    value_verified: bool
    disposition: FormulaDisposition
    rationale: str

    def __post_init__(self) -> None:
        for path, value in (
            ("threshold rule_id", self.rule_id),
            ("threshold source", self.source),
            ("threshold frozen_value", self.frozen_value),
            ("threshold rationale", self.rationale),
        ):
            if type(value) is not str or not value.strip():
                raise OperatorTemplateContractValidationError(
                    f"{path} must be non-empty text"
                )
        if type(self.value_verified) is not bool:
            raise OperatorTemplateContractValidationError(
                "threshold value_verified must be boolean"
            )
        if not isinstance(self.disposition, FormulaDisposition):
            raise OperatorTemplateContractValidationError(
                "threshold disposition is invalid"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductSelectionSemantic(JsonContract):
    sheet_name: str
    before_direction_locked: str
    after_direction_locked: str
    direct_competitor_label_allowed_before_lock: bool

    def __post_init__(self) -> None:
        for path, value in (
            ("semantic sheet_name", self.sheet_name),
            ("before_direction_locked", self.before_direction_locked),
            ("after_direction_locked", self.after_direction_locked),
        ):
            if type(value) is not str or not value.strip():
                raise OperatorTemplateContractValidationError(
                    f"{path} must be non-empty text"
                )
        if type(self.direct_competitor_label_allowed_before_lock) is not bool:
            raise OperatorTemplateContractValidationError(
                "direct competitor pre-lock flag must be boolean"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class OperatorTemplateContractV1(JsonContract):
    ruleset_version: str
    sheets: tuple[SheetContract, ...]
    raw_headers: tuple[RawHeaderContract, ...]
    formula_policies: tuple[FormulaPolicy, ...]
    formula_census_reference: tuple[FormulaCensusReference, ...]
    dependencies: tuple[DependencyRequirement, ...]
    threshold_rules: tuple[ThresholdRule, ...]
    product_selection_semantics: tuple[ProductSelectionSemantic, ...]
    raw_header_mapping_policy: str
    numeric_missing_policy: str
    provider_gross_margin_semantics: str
    external_network_calls_allowed: bool

    def __post_init__(self) -> None:
        if self.ruleset_version != OPERATOR_TEMPLATE_RULESET_VERSION:
            raise OperatorTemplateContractValidationError(
                "unsupported operator template ruleset"
            )
        for field_name in (
            "sheets",
            "raw_headers",
            "formula_policies",
            "formula_census_reference",
            "dependencies",
            "threshold_rules",
            "product_selection_semantics",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if len(self.sheets) != 15:
            raise OperatorTemplateContractValidationError(
                "template must define exactly 15 sheets"
            )
        if [sheet.ordinal for sheet in self.sheets] != list(range(1, 16)):
            raise OperatorTemplateContractValidationError(
                "sheet ordinals must be contiguous and ordered"
            )
        if len({sheet.name for sheet in self.sheets}) != 15:
            raise OperatorTemplateContractValidationError(
                "sheet names must be unique"
            )
        visible = tuple(
            sheet for sheet in self.sheets
            if sheet.visibility is SheetVisibility.VISIBLE
        )
        hidden = tuple(
            sheet for sheet in self.sheets
            if sheet.visibility is SheetVisibility.HIDDEN
        )
        if len(visible) != 11 or len(hidden) != 4:
            raise OperatorTemplateContractValidationError(
                "template must define 11 visible and 4 hidden sheets"
            )
        if len(self.raw_headers) != 66:
            raise OperatorTemplateContractValidationError(
                "raw source must define exactly 66 headers"
            )
        if len({header.name for header in self.raw_headers}) != 66:
            raise OperatorTemplateContractValidationError(
                "raw header names must be unique"
            )
        if tuple(
            header.name for header in self.raw_headers
            if header.requirement is RawHeaderRequirement.OUT_OF_SCOPE
        ) != ("LQS", "SP广告"):
            raise OperatorTemplateContractValidationError(
                "only LQS and SP广告 are out-of-scope raw headers"
            )
        if self.raw_header_mapping_policy != "BY_EXACT_HEADER_NAME_NOT_COLUMN_INDEX":
            raise OperatorTemplateContractValidationError(
                "raw headers must be mapped by exact name"
            )
        if self.numeric_missing_policy != "MISSING_BLANK_NA_PARSE_FAILURE_NEVER_ZERO":
            raise OperatorTemplateContractValidationError(
                "numeric missingness policy is not fail-closed"
            )
        if self.provider_gross_margin_semantics != "REFERENCE_ONLY_NOT_PROCUREMENT_TRUTH":
            raise OperatorTemplateContractValidationError(
                "provider gross margin must remain reference only"
            )
        if self.external_network_calls_allowed is not False:
            raise OperatorTemplateContractValidationError(
                "template contract must forbid external network calls"
            )
        policy_sheets = {item.sheet_name for item in self.formula_policies}
        if not policy_sheets <= {sheet.name for sheet in self.sheets}:
            raise OperatorTemplateContractValidationError(
                "formula policy references an unknown sheet"
            )
        if sum(item.approximate_count for item in self.formula_census_reference) != 26738:
            raise OperatorTemplateContractValidationError(
                "reference formula census must total approximately 26,738"
            )
        semantic_sheets = {
            "产品初步筛选范围", "样品类型", "竞品收集"
        }
        if {item.sheet_name for item in self.product_selection_semantics} != semantic_sheets:
            raise OperatorTemplateContractValidationError(
                "product-selection semantic sheets are incomplete"
            )
        if any(
            item.direct_competitor_label_allowed_before_lock
            for item in self.product_selection_semantics
        ):
            raise OperatorTemplateContractValidationError(
                "Direct Competitor labels are forbidden before DIRECTION_LOCKED"
            )


@dataclass(frozen=True, slots=True, kw_only=True)
class SheetStateAudit(JsonContract):
    name: str
    state: str


@dataclass(frozen=True, slots=True, kw_only=True)
class FormulaCellAudit(JsonContract):
    sheet_name: str
    coordinate: str
    formula: str
    token_signature: tuple[str, ...]
    disposition: FormulaDisposition


@dataclass(frozen=True, slots=True, kw_only=True)
class FormulaSheetAudit(JsonContract):
    sheet_name: str
    formula_count: int
    formula_fingerprint: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DefinedNameAudit(JsonContract):
    name: str
    refers_to: str
    local_sheet_id: int | None


@dataclass(frozen=True, slots=True, kw_only=True)
class SheetRangeAudit(JsonContract):
    sheet_name: str
    kind: str
    name: str
    range_ref: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ThresholdLiteralAudit(JsonContract):
    sheet_name: str
    coordinate: str
    token_index: int
    value: str
    disposition: FormulaDisposition


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkbookTemplateAuditSnapshot(JsonContract):
    schema_fingerprint: str
    sheet_states: tuple[SheetStateAudit, ...]
    raw_headers: tuple[str, ...]
    formula_cells: tuple[FormulaCellAudit, ...]
    formula_sheets: tuple[FormulaSheetAudit, ...]
    defined_names: tuple[DefinedNameAudit, ...]
    sheet_ranges: tuple[SheetRangeAudit, ...]
    threshold_literals: tuple[ThresholdLiteralAudit, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "sheet_states",
            "raw_headers",
            "formula_cells",
            "formula_sheets",
            "defined_names",
            "sheet_ranges",
            "threshold_literals",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        if len(self.schema_fingerprint) != 64:
            raise OperatorTemplateContractValidationError(
                "schema fingerprint must be SHA-256 hex"
            )


def canonical_sha256(value: Any) -> str:
    """Return a stable SHA-256 over the repository's canonical JSON format."""

    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def template_schema_fingerprint(contract: OperatorTemplateContractV1) -> str:
    if not isinstance(contract, OperatorTemplateContractV1):
        raise OperatorTemplateContractValidationError(
            "schema fingerprint input must be OperatorTemplateContractV1"
        )
    return canonical_sha256(contract)


def workbook_audit_fingerprint(snapshot: WorkbookTemplateAuditSnapshot) -> str:
    if not isinstance(snapshot, WorkbookTemplateAuditSnapshot):
        raise OperatorTemplateContractValidationError(
            "audit fingerprint input must be WorkbookTemplateAuditSnapshot"
        )
    return canonical_sha256(snapshot)


__all__ = (
    "OPERATOR_TEMPLATE_RULESET_VERSION",
    "DefinedNameAudit",
    "DependencyRequirement",
    "FormulaCellAudit",
    "FormulaCensusReference",
    "FormulaDisposition",
    "FormulaPolicy",
    "FormulaSheetAudit",
    "OperatorTemplateContractV1",
    "ProductSelectionSemantic",
    "RawHeaderContract",
    "RawHeaderRequirement",
    "SheetContract",
    "SheetRangeAudit",
    "SheetStateAudit",
    "SheetVisibility",
    "ThresholdLiteralAudit",
    "ThresholdRule",
    "WorkbookTemplateAuditSnapshot",
    "canonical_sha256",
    "template_schema_fingerprint",
    "workbook_audit_fingerprint",
)
