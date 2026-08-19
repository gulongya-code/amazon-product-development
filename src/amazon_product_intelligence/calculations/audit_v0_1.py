"""Mechanical 99-field calculated coverage audit for Workbook V0.2.

The coverage matrix calls every system-produced Workbook projection
``CALCULATED``.  That label is not an instruction to duplicate existing
Intelligence, Scoring, Recommendation, Export, or presentation logic here.
Only entries with an explicit mathematical definition are marked ready.
"""

from __future__ import annotations

import re

from .functions import (
    calculate_observed_share,
    count_unique_canonical_identifiers,
    project_member_product_ids,
)
from .models import (
    CalculatedFieldSpec,
    CalculationDependency,
    CalculationTier,
    DependencyType,
    FormulaConfidence,
    FormulaStatus,
    ImplementationStatus,
    MissingPolicy,
)
from .registry import CalculatedFieldRegistry


_SHEET_META = {
    "01_市场概览": ("market_overview", CalculationTier.MARKET_DERIVED, "Market overview"),
    "02_产品数据库": ("product_database", CalculationTier.BASE_DETERMINISTIC, "Product intelligence"),
    "03_TOP产品分析": ("top_products", CalculationTier.BASE_DETERMINISTIC, "Rank evidence presentation"),
    "04_关键词需求分析": ("keyword_demand", CalculationTier.KEYWORD_DERIVED, "Demand intelligence"),
    "05_市场竞争证据": ("competition_evidence", CalculationTier.COMPETITION_DERIVED, "Competition intelligence"),
    "06_产品结构分析": ("product_structure", CalculationTier.MARKET_DERIVED, "Product structure"),
    "07_机会分析": ("opportunity_analysis", CalculationTier.COMPOSITE_SCORE, "Opportunity and scoring"),
    "08_行动建议": ("action_recommendations", CalculationTier.AI_DECISION, "Recommendation output"),
    "09_数据审计": ("data_audit", CalculationTier.OTHER, "Export and lineage metadata"),
}


# Every tuple is copied from a CALCULATED row in
# docs/integration/API_FIELD_COVERAGE_MATRIX_V0.1.md.
_AUDITED_FIELDS: dict[str, tuple[tuple[str, str], ...]] = {
    "01_市场概览": (
        ("Observed Product Count", "Snapshot aggregation of validated product identities"),
        ("Data Sources", "Provenance providers"),
        ("Evidence-backed Trend", "Opportunity projection from dated trend observations"),
        ("Risk Alerts", "Quality and risk diagnostics"),
        ("Evidence Quality", "Evidence evaluation classification"),
        ("Analysis Limitations", "Diagnostic and limitation codes"),
        ("Snapshot ID", "Opportunity snapshot identity"),
    ),
    "02_产品数据库": (
        ("Title State", "Product title candidate and presence state"),
        ("Price State", "Price metric candidate and presence state"),
        ("Rating State", "Rating metric candidate and conflict state"),
        ("Sales Evidence Type", "EvidenceType and metric semantic"),
        ("Child Count", "Explicit variation relationship aggregation"),
        ("Data Sources", "Provenance providers"),
        ("Data State", "Product evidence presence and quality state"),
        ("Conflict State", "Conflict evaluation state"),
        ("Time / Period Status", "Observation time and period quality"),
        ("Product Snapshot ID", "Product Intelligence snapshot identity"),
        ("Output Row ID", "Operator Output row identity"),
    ),
    "03_TOP产品分析": (
        ("Rank Provider", "Rank observation provenance provider"),
        ("Rank Status", "Rank evidence state"),
        ("Data Limitations", "Rank limitation codes"),
        ("Rank Observation ID", "Canonical rank observation identity"),
    ),
    "04_关键词需求分析": (
        ("Search Volume State", "Search-volume presence state"),
        ("CPC State", "CPC presence state"),
        ("ABA Rank State", "ABA-rank presence state"),
        ("Difficulty State", "Difficulty presence state"),
        ("Related Product Count", "Directional relationship aggregation"),
        ("Query Direction", "QueryDirection"),
        ("Query Status", "QueryExecutionRecord result status"),
        ("Provider", "Query evidence provenance provider"),
        ("Period Status", "Demand period quality state"),
        ("Limitations", "Demand limitation codes"),
        ("Demand Snapshot ID", "Demand snapshot identity"),
    ),
    "05_市场竞争证据": (
        ("Relationship Direction", "ProductKeywordRelationship direction"),
        ("Observed Relationship", "Validated product-keyword relationship observation"),
        ("Observed Relationship Type", "Relationship type"),
        ("Provider", "Relationship evidence provenance provider"),
        ("Evidence Count", "Relationship evidence aggregation"),
        ("Evidence Classification", "Evidence semantic class"),
        ("Variation Evidence Count", "Variation relationship aggregation"),
        ("Query Status", "Query execution status"),
        ("Limitations", "Competition limitation codes"),
        ("Competition Output Row ID", "Operator Output row identity"),
    ),
    "06_产品结构分析": (
        ("Product Count", "Exact-group product identity aggregation"),
        ("Observed Share", "Exact-group observed share"),
        ("Sales Evidence Summary", "Sales metric presentation projection"),
        ("Minimum Comparable Price", "Comparable price aggregation"),
        ("Maximum Comparable Price", "Comparable price aggregation"),
        ("Data State", "Structure evidence state"),
        ("Provider Count", "Group provenance aggregation"),
        ("Limitations", "Structure limitation codes"),
        ("Member Product IDs", "Exact group membership"),
    ),
    "07_机会分析": (
        ("Demand Signal", "Opportunity demand evidence projection"),
        ("Competition Signal", "Opportunity competition evidence projection"),
        ("Product Signal", "Opportunity product evidence projection"),
        ("Signal Classification", "Opportunity signal class"),
        ("Missing Evidence", "Missing-evidence inventory"),
        ("Risk Evidence", "Risk-evidence inventory"),
        ("Score Factor", "Opportunity scoring factor identity"),
        ("Rule Process Score", "Existing Opportunity Scoring result"),
        ("Score Status", "Scoring process status"),
        ("Score Reference", "Score calculation identity"),
        ("Score Interpretation", "Existing score explanation"),
        ("Explanation Reference", "Explanation record identity"),
        ("Limitations", "Opportunity and scoring limitation codes"),
        ("Opportunity Output Row ID", "Operator Output row identity"),
    ),
    "08_行动建议": (
        ("Recommendation Type", "Recommendation Framework output"),
        ("Recommendation Display Label", "Workbook presentation label"),
        ("Reason", "Recommendation rule explanation"),
        ("Rule Reference", "Recommendation rule identity"),
        ("Policy Status", "Evidence policy status"),
        ("Conflict Status", "Conflict-resolution status"),
        ("Missing Requirements", "Recommendation missing-input inventory"),
        ("Evidence References", "Canonical and evaluation references"),
        ("Evidence Count", "Recommendation evidence-reference aggregation"),
        ("Limitations", "Recommendation limitation codes"),
        ("Recommendation Record ID", "Recommendation record identity"),
        ("Source Snapshot ID", "Recommendation source snapshot identity"),
        ("Operator Output Row ID", "Operator Output row identity"),
    ),
    "09_数据审计": (
        ("Audit Record ID", "Audit presentation identity"),
        ("Source Sheet", "Workbook presentation metadata"),
        ("Display Row Key", "Workbook presentation identity"),
        ("Excel Row", "XLSX row location metadata"),
        ("Display Field", "Workbook presentation metadata"),
        ("Excel Cell", "XLSX cell location metadata"),
        ("Export Row ID", "Operator Export identity"),
        ("Output Row ID", "Operator Output identity"),
        ("Evidence ID", "Canonical evidence identity"),
        ("Provider", "Canonical provenance provider"),
        ("Source Tool", "Canonical provenance source tool"),
        ("Source Field", "Canonical provenance source field"),
        ("Raw Evidence Reference", "Raw evidence identity"),
        ("Collection Run ID", "Collection-run identity"),
        ("Transformation Run ID", "Transformation-run identity"),
        ("Mapping Version", "Transformation mapping version"),
        ("Canonical Reference ID", "Canonical observation or query identity"),
        ("Lineage ID", "Serialized lineage identity"),
        ("Source Snapshot ID", "Intelligence source snapshot identity"),
        ("Source Bundle Fingerprint", "Canonical bundle content fingerprint"),
    ),
}


def _slug(display_name: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", display_name.casefold())).strip("_")


def _field_id(sheet: str, display_name: str) -> str:
    return f"workbook.{_SHEET_META[sheet][0]}.{_slug(display_name)}"


_DEFINED: dict[str, dict[str, object]] = {
    "workbook.market_overview.observed_product_count": {
        "dependencies": (("canonical.snapshot_product_identities", DependencyType.CANONICAL_INPUT),),
        "formula": "Count distinct validated ProductIdentity values inside the explicit snapshot scope.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.observed_product_count",
    },
    "workbook.product_database.child_count": {
        "dependencies": (("canonical.explicit_child_relationships", DependencyType.CANONICAL_INPUT),),
        "formula": "Count distinct valid explicit child edges for the exact parent and marketplace.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.child_count",
    },
    "workbook.keyword_demand.related_product_count": {
        "dependencies": (("canonical.directional_product_keyword_relationships", DependencyType.CANONICAL_INPUT),),
        "formula": "Count distinct product identities in valid relationships for the exact query direction and scope.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.related_product_count",
    },
    "workbook.competition_evidence.evidence_count": {
        "dependencies": (("canonical.grouped_relationship_evidence", DependencyType.CANONICAL_INPUT),),
        "formula": "Count validated relationship-evidence records in the exact relationship group.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.competition_evidence_count",
    },
    "workbook.competition_evidence.variation_evidence_count": {
        "dependencies": (("canonical.grouped_variation_relationships", DependencyType.CANONICAL_INPUT),),
        "formula": "Count validated explicit variation edges in the exact evidence group.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.variation_evidence_count",
    },
    "workbook.product_structure.product_count": {
        "dependencies": (("canonical.group_product_identities", DependencyType.CANONICAL_INPUT),),
        "formula": "Count distinct validated product identities in the exact product-type group.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.structure_product_count",
    },
    "workbook.product_structure.observed_share": {
        "dependencies": (
            ("workbook.product_structure.product_count", DependencyType.CALCULATED_FIELD),
            ("workbook.market_overview.observed_product_count", DependencyType.CALCULATED_FIELD),
            ("canonical.group_product_identities", DependencyType.CANONICAL_INPUT),
            ("canonical.snapshot_product_identities", DependencyType.CANONICAL_INPUT),
        ),
        "formula": "Exact-group Product Count divided by Observed Product Count; this is observed-set share, never market share.",
        "unit": "ratio",
        "output_type": "decimal",
        "rule": "calculation.observed_set_share",
    },
    "workbook.product_structure.minimum_comparable_price": {
        "dependencies": (("canonical.comparable_price_observations", DependencyType.CANONICAL_INPUT),),
        "formula": "Minimum resolved price among inputs with identical explicit currency, scope, and period semantics.",
        "unit": "explicit input currency",
        "output_type": "decimal",
        "rule": "calculation.minimum_comparable_price",
    },
    "workbook.product_structure.maximum_comparable_price": {
        "dependencies": (("canonical.comparable_price_observations", DependencyType.CANONICAL_INPUT),),
        "formula": "Maximum resolved price among inputs with identical explicit currency, scope, and period semantics.",
        "unit": "explicit input currency",
        "output_type": "decimal",
        "rule": "calculation.maximum_comparable_price",
    },
    "workbook.product_structure.provider_count": {
        "dependencies": (("canonical.group_evidence_provenance", DependencyType.CANONICAL_INPUT),),
        "formula": "Count distinct provider identities retained by Canonical provenance for the exact group.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.structure_provider_count",
    },
    "workbook.product_structure.member_product_ids": {
        "dependencies": (("canonical.group_product_identities", DependencyType.CANONICAL_INPUT),),
        "formula": "Return sorted distinct validated product IDs in the exact product-type group.",
        "unit": "not applicable",
        "output_type": "array[string]",
        "rule": "calculation.structure_member_product_ids",
    },
    "workbook.action_recommendations.evidence_count": {
        "dependencies": (("recommendation.evidence_references", DependencyType.SYSTEM_RECORD),),
        "formula": "Count distinct evidence references already attached to the exact recommendation record.",
        "unit": "count",
        "output_type": "integer",
        "rule": "calculation.recommendation_evidence_count",
        "tier": CalculationTier.BASE_DETERMINISTIC,
    },
}


D2A_IMPLEMENTED_FIELD_IDS = (
    "workbook.action_recommendations.evidence_count",
    "workbook.competition_evidence.evidence_count",
    "workbook.keyword_demand.related_product_count",
    "workbook.market_overview.observed_product_count",
    "workbook.product_database.child_count",
    "workbook.product_structure.product_count",
    "workbook.product_structure.provider_count",
)

D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS = (
    "workbook.competition_evidence.variation_evidence_count",
)

D2A_DEFERRED_FIELD_IDS = (
    "workbook.product_structure.maximum_comparable_price",
    "workbook.product_structure.member_product_ids",
    "workbook.product_structure.minimum_comparable_price",
    "workbook.product_structure.observed_share",
)

# D2A_DEFERRED_FIELD_IDS remains the immutable history of the D2A batch.
# D2C promotes exactly two of those fields without rewriting that prior disposition.
D2C_IMPLEMENTED_FIELD_IDS = (
    "workbook.product_structure.member_product_ids",
    "workbook.product_structure.observed_share",
)

D2_IMPLEMENTED_FIELD_IDS = D2A_IMPLEMENTED_FIELD_IDS + D2C_IMPLEMENTED_FIELD_IDS

D2_CURRENT_DEFERRED_FIELD_IDS = (
    "workbook.product_structure.maximum_comparable_price",
    "workbook.product_structure.minimum_comparable_price",
)


_DEFAULT_DEPENDENCY = {
    "01_市场概览": ("intelligence.opportunity_snapshot", DependencyType.SYSTEM_RECORD),
    "02_产品数据库": ("intelligence.product_snapshot", DependencyType.SYSTEM_RECORD),
    "03_TOP产品分析": ("operator_output.top_product_row", DependencyType.SYSTEM_RECORD),
    "04_关键词需求分析": ("intelligence.demand_snapshot", DependencyType.SYSTEM_RECORD),
    "05_市场竞争证据": ("intelligence.competition_snapshot", DependencyType.SYSTEM_RECORD),
    "06_产品结构分析": ("intelligence.product_snapshot", DependencyType.SYSTEM_RECORD),
    "07_机会分析": ("scoring.opportunity_scoring_record", DependencyType.SYSTEM_RECORD),
    "08_行动建议": ("recommendation.recommendation_record", DependencyType.SYSTEM_RECORD),
    "09_数据审计": ("operator_export.lineage_record", DependencyType.METADATA),
}


def _output_contract(display_name: str) -> tuple[str, str]:
    if display_name.endswith("Count") or display_name == "Excel Row":
        return "integer", "count"
    if display_name in {"Observed Share"}:
        return "decimal", "ratio"
    if display_name in {"Minimum Comparable Price", "Maximum Comparable Price"}:
        return "decimal", "explicit input currency"
    if display_name == "Rule Process Score":
        return "decimal", "score"
    if display_name in {
        "Data Sources",
        "Risk Alerts",
        "Analysis Limitations",
        "Data Limitations",
        "Limitations",
        "Missing Evidence",
        "Risk Evidence",
        "Missing Requirements",
        "Evidence References",
        "Member Product IDs",
    }:
        return "array[string]", "not applicable"
    return "string", "not applicable"


def _make_spec(sheet: str, display_name: str, canonical_field: str) -> CalculatedFieldSpec:
    field_id = _field_id(sheet, display_name)
    sheet_key, default_tier, category = _SHEET_META[sheet]
    del sheet_key
    output_type, unit = _output_contract(display_name)
    defined = _DEFINED.get(field_id)
    if defined is not None:
        if field_id in D2A_IMPLEMENTED_FIELD_IDS:
            implementation_status = ImplementationStatus.IMPLEMENTED
            calculation_version = "v0.1-count-formula"
            zero_semantics = (
                "Zero and False are present data; an explicitly present empty collection "
                "has count zero."
            )
            quality_implication = (
                "Deterministic count of an authoritative unique identity collection; "
                "count is not confidence, demand, competition strength, or market size."
            )
            notes = (
                "Production evaluator verifies the upstream collection contract, rejects "
                "duplicates or malformed identifiers, and does not establish a second dedupe authority."
            )
        elif field_id == "workbook.product_structure.member_product_ids":
            implementation_status = ImplementationStatus.IMPLEMENTED
            calculation_version = "v0.1-member-product-ids-formula"
            zero_semantics = (
                "A present empty authoritative group remains an empty member collection; "
                "missing and unknown do not become empty."
            )
            quality_implication = (
                "Projects only validated Canonical ProductIdentity IDs from the exact group; "
                "it does not derive, repair, deduplicate, or reorder identities."
            )
            notes = (
                "Production evaluator requires unique, canonical product:<marketplace>:<ASIN> "
                "identifiers in the deterministic order established upstream."
            )
        elif field_id == "workbook.product_structure.observed_share":
            implementation_status = ImplementationStatus.IMPLEMENTED
            calculation_version = "v0.1-observed-share-formula"
            zero_semantics = (
                "A zero group count is valid when the same-scope denominator is positive; "
                "a zero denominator returns DIVISION_BY_ZERO and never zero share."
            )
            quality_implication = (
                "Ratio is bounded to the explicit observed snapshot set and cannot be "
                "interpreted as real market share."
            )
            notes = (
                "Production evaluator calculates from the two governed count results, requires "
                "canonical count units, and validates marketplace and subset scope against their "
                "authoritative ProductIdentity collections."
            )
        elif field_id in D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS:
            implementation_status = ImplementationStatus.BLOCKED_BY_SEMANTIC_AMBIGUITY
            calculation_version = "v0.1-specification"
            zero_semantics = (
                "Zero and False are present data; no zero behavior is executable until the "
                "counting grain is accepted."
            )
            quality_implication = (
                "Blocked because counting explicit variation edges is not interchangeable "
                "with counting competition variation-evidence records."
            )
            notes = (
                "Canonical variation-edge identity and the current exact Workbook evidence-group "
                "record identity do not yet define one shared counting boundary."
            )
        else:
            implementation_status = ImplementationStatus.READY_FOR_IMPLEMENTATION
            calculation_version = "v0.1-specification"
            zero_semantics = (
                "Zero and False are present data; present empty inputs remain distinct from "
                "missing and require formula-specific handling."
            )
            quality_implication = (
                "Eligible for a later deterministic implementation after its separately deferred "
                "compatibility and business semantics are accepted."
            )
            notes = (
                "Definition source: API Field Coverage Matrix V0.1 plus the approved formula; "
                "no production evaluator is registered in this batch."
            )
        dependencies = tuple(
            CalculationDependency(field_id=dependency, dependency_type=dependency_type)
            for dependency, dependency_type in defined["dependencies"]
        )
        return CalculatedFieldSpec(
            field_id=field_id,
            workbook_sheet=sheet,
            display_name=display_name,
            canonical_field=canonical_field,
            category=category,
            calculation_tier=defined.get("tier", default_tier),
            output_type=str(defined.get("output_type", output_type)),
            unit=str(defined.get("unit", unit)),
            dependencies=dependencies,
            formula_status=FormulaStatus.DEFINED,
            formula_reference=str(defined["formula"]),
            missing_policy=MissingPolicy.REQUIRE_ALL,
            zero_semantics=zero_semantics,
            invalid_input_policy="Block this field on unresolved, ambiguous, semantically unconfirmed, invalid, or blocking-quality inputs.",
            partial_input_policy="No partial execution; every declared dependency must be usable.",
            calculation_version=calculation_version,
            calculation_rule_id=str(defined["rule"]),
            provenance_requirement="Retain all resolved Canonical input values, evidence references, Provenance records, quality issue IDs, and fingerprints.",
            formula_confidence=FormulaConfidence.CONFIRMED,
            quality_implication=quality_implication,
            implementation_status=implementation_status,
            notes=notes,
        )

    dependency_id, dependency_type = _DEFAULT_DEPENDENCY[sheet]
    formula_missing = field_id == "workbook.market_overview.evidence_backed_trend"
    if formula_missing:
        dependency_id = "canonical.dated_trend_observations"
        dependency_type = DependencyType.CANONICAL_INPUT
    return CalculatedFieldSpec(
        field_id=field_id,
        workbook_sheet=sheet,
        display_name=display_name,
        canonical_field=canonical_field,
        category=category,
        calculation_tier=default_tier,
        output_type=output_type,
        unit=unit,
        dependencies=(CalculationDependency(field_id=dependency_id, dependency_type=dependency_type),),
        formula_status=(
            FormulaStatus.FORMULA_UNSPECIFIED
            if formula_missing
            else FormulaStatus.CLASSIFICATION_REVIEW_REQUIRED
        ),
        formula_reference=(
            "Dated trend evidence exists, but no approved rule defines the projected human-readable trend."
            if formula_missing
            else "Existing downstream-layer or presentation projection; no generic Calculation Engine formula is approved."
        ),
        missing_policy=MissingPolicy.REQUIRE_ALL,
        zero_semantics="Preserve zero, False, and present empty collections exactly; never substitute them for missing or unknown.",
        invalid_input_policy="Do not execute in the generic engine; preserve the existing owning layer and its validation boundary.",
        partial_input_policy="No generic partial-input behavior is authorized until classification and ownership are accepted.",
        calculation_version="v0.1-specification",
        calculation_rule_id=None,
        provenance_requirement="Existing owning-layer lineage must remain authoritative; any future migration must retain all Canonical evidence.",
        formula_confidence=(FormulaConfidence.UNSPECIFIED if formula_missing else FormulaConfidence.NOT_APPLICABLE),
        quality_implication=(
            "Blocked until a documented deterministic trend algorithm is approved."
            if formula_missing
            else "Classification review prevents duplicate or semantically incorrect calculation logic."
        ),
        implementation_status=(
            ImplementationStatus.FORMULA_MISSING
            if formula_missing
            else ImplementationStatus.CLASSIFICATION_REVIEW
        ),
        notes=(
            "Field name and source time series are insufficient to define a trend algorithm."
            if formula_missing
            else "Coverage-matrix CALCULATED means system-produced; this field remains owned by its current Intelligence, Scoring, Recommendation, Output, Export, or Workbook layer."
        ),
    )


CALCULATED_FIELD_SPECS = tuple(
    _make_spec(sheet, display_name, canonical_field)
    for sheet, fields in _AUDITED_FIELDS.items()
    for display_name, canonical_field in fields
)

AUDITED_CALCULATED_FIELDS = tuple(
    (spec.workbook_sheet, spec.display_name) for spec in CALCULATED_FIELD_SPECS
)

D2_READY_FIELD_IDS = tuple(spec.field_id for spec in CALCULATED_FIELD_SPECS if spec.field_id in _DEFINED)


def build_audited_registry() -> CalculatedFieldRegistry:
    """Return all 99 specs and the nine accepted D2A/D2C evaluators."""

    registry = CalculatedFieldRegistry()
    evaluators = {
        **{
            field_id: count_unique_canonical_identifiers
            for field_id in D2A_IMPLEMENTED_FIELD_IDS
        },
        "workbook.product_structure.member_product_ids": project_member_product_ids,
        "workbook.product_structure.observed_share": calculate_observed_share,
    }
    for specification in CALCULATED_FIELD_SPECS:
        registry.register(specification, evaluators.get(specification.field_id))
    registry.validate()
    return registry


if len(CALCULATED_FIELD_SPECS) != 99:
    raise RuntimeError("Workbook V0.2 calculated-field audit must contain exactly 99 specifications")
if len({spec.field_id for spec in CALCULATED_FIELD_SPECS}) != 99:
    raise RuntimeError("Workbook V0.2 calculated-field audit contains duplicate field IDs")
if set(D2_READY_FIELD_IDS) != set(_DEFINED):
    raise RuntimeError("D2-ready field set must exactly match approved definitions")
if set(D2A_IMPLEMENTED_FIELD_IDS) & set(D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS):
    raise RuntimeError("D2A implemented and ambiguous field sets must not overlap")
if (
    set(D2A_IMPLEMENTED_FIELD_IDS)
    | set(D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS)
    | set(D2A_DEFERRED_FIELD_IDS)
) != set(_DEFINED):
    raise RuntimeError("D2A disposition must cover every D1-defined candidate exactly once")
if not set(D2C_IMPLEMENTED_FIELD_IDS) < set(D2A_DEFERRED_FIELD_IDS):
    raise RuntimeError("D2C fields must be a strict subset of the historical D2A deferred set")
if (
    set(D2_IMPLEMENTED_FIELD_IDS)
    | set(D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS)
    | set(D2_CURRENT_DEFERRED_FIELD_IDS)
) != set(_DEFINED):
    raise RuntimeError("current D2 disposition must cover every D1-defined candidate exactly once")
if len(set(D2_IMPLEMENTED_FIELD_IDS)) != len(D2_IMPLEMENTED_FIELD_IDS):
    raise RuntimeError("current D2 implemented field set contains duplicates")


__all__ = (
    "AUDITED_CALCULATED_FIELDS",
    "CALCULATED_FIELD_SPECS",
    "D2A_DEFERRED_FIELD_IDS",
    "D2A_IMPLEMENTED_FIELD_IDS",
    "D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS",
    "D2C_IMPLEMENTED_FIELD_IDS",
    "D2_CURRENT_DEFERRED_FIELD_IDS",
    "D2_IMPLEMENTED_FIELD_IDS",
    "D2_READY_FIELD_IDS",
    "build_audited_registry",
)
