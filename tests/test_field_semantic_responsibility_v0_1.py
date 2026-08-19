from __future__ import annotations

from collections import Counter
from pathlib import Path
import re
import unittest

from amazon_product_intelligence.calculations import (
    CALCULATED_FIELD_SPECS,
    D2A_IMPLEMENTED_FIELD_IDS,
    FormulaStatus,
    ImplementationStatus,
    build_audited_registry,
)
from amazon_product_intelligence.operator_workbook.schema_v0_2 import SHEET_SPECS


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "intelligence" / "FIELD_SEMANTIC_RESPONSIBILITY_MATRIX_V0.1.md"
COVERAGE = ROOT / "docs" / "integration" / "API_FIELD_COVERAGE_MATRIX_V0.1.md"

LEGAL_CLASSES = {
    "SOURCE",
    "NORMALIZED_SOURCE",
    "AGGREGATION",
    "DETERMINISTIC_CALCULATION",
    "COMPOSITE_SCORE",
    "AI_ANALYSIS",
    "DECISION_OUTPUT",
    "MANUAL_INPUT",
    "SYSTEM_STATUS",
    "METADATA",
    "DISPLAY",
    "EVIDENCE",
    "CONFIGURATION",
    "SEMANTIC_UNRESOLVED",
}

EXPECTED_CLASS_COUNTS = {
    "NORMALIZED_SOURCE": 47,
    "SOURCE": 3,
    "AGGREGATION": 11,
    "DETERMINISTIC_CALCULATION": 1,
    "COMPOSITE_SCORE": 1,
    "AI_ANALYSIS": 0,
    "DECISION_OUTPUT": 2,
    "MANUAL_INPUT": 1,
    "SYSTEM_STATUS": 19,
    "METADATA": 37,
    "DISPLAY": 5,
    "EVIDENCE": 26,
    "CONFIGURATION": 2,
    "SEMANTIC_UNRESOLVED": 2,
}


def _slug(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.casefold())).strip("_")


def _rows() -> tuple[dict[str, str], ...]:
    names = (
        "ordinal",
        "field_id",
        "display_name",
        "acquisition",
        "current_status",
        "semantic_class",
        "confidence",
        "evidence",
        "authoritative_source",
        "owner_layer",
        "requirements",
        "readiness",
        "next_task",
        "notes",
    )
    result = []
    for line in MATRIX.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\| F\d{3} \|", line):
            continue
        values = tuple(item.strip() for item in line.strip().strip("|").split("|"))
        if len(values) != len(names):
            raise AssertionError(f"semantic matrix row has {len(values)} columns: {line}")
        row = dict(zip(names, values, strict=True))
        row["field_id"] = row["field_id"].strip("`")
        result.append(row)
    return tuple(result)


def _coverage_statuses() -> tuple[str, ...]:
    statuses = []
    for line in COVERAGE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        values = tuple(item.strip() for item in line.strip().strip("|").split("|"))
        if len(values) == 6 and values[4] in {
            "AVAILABLE", "PARTIAL", "CALCULATED", "UNAVAILABLE", "UNKNOWN"
        }:
            statuses.append(values[4])
    return tuple(statuses)


def _expected_current_status(field_id: str) -> str:
    specs = {item.field_id: item for item in CALCULATED_FIELD_SPECS}
    specification = specs.get(field_id)
    if specification is None:
        return "NOT_IN_CALC_AUDIT"
    if specification.formula_status is FormulaStatus.CLASSIFICATION_REVIEW_REQUIRED:
        return "CLASSIFICATION_REVIEW_REQUIRED"
    if specification.formula_status is FormulaStatus.FORMULA_UNSPECIFIED:
        return "FORMULA_UNSPECIFIED"
    if specification.implementation_status is ImplementationStatus.IMPLEMENTED:
        return "DEFINED_IMPLEMENTED"
    if specification.implementation_status is ImplementationStatus.READY_FOR_IMPLEMENTATION:
        return "DEFINED_READY"
    if specification.implementation_status is ImplementationStatus.BLOCKED_BY_SEMANTIC_AMBIGUITY:
        return "DEFINED_SEMANTIC_BLOCKED"
    raise AssertionError(f"unmapped calculation status for {field_id}")


class FieldSemanticResponsibilityAuditTests(unittest.TestCase):
    def test_matrix_covers_exactly_the_fixed_157_workbook_fields(self) -> None:
        rows = _rows()
        expected = tuple(
            (f"workbook.{sheet.key}.{_slug(field.english_name)}", field.english_name)
            for sheet in SHEET_SPECS
            for field in sheet.fields
        )
        actual = tuple((row["field_id"], row["display_name"]) for row in rows)
        self.assertEqual(expected, actual)
        self.assertEqual(157, len(rows))
        self.assertEqual(157, len({row["field_id"] for row in rows}))
        self.assertEqual(tuple(f"F{index:03d}" for index in range(1, 158)), tuple(
            row["ordinal"] for row in rows
        ))

    def test_acquisition_axis_is_preserved_without_reclassification(self) -> None:
        rows = _rows()
        coverage_statuses = _coverage_statuses()
        self.assertEqual(157, len(coverage_statuses))
        self.assertEqual(coverage_statuses, tuple(row["acquisition"] for row in rows))
        self.assertEqual(
            Counter({"AVAILABLE": 30, "PARTIAL": 24, "CALCULATED": 99,
                     "UNAVAILABLE": 2, "UNKNOWN": 2}),
            Counter(row["acquisition"] for row in rows),
        )

    def test_current_99_field_audit_status_is_preserved(self) -> None:
        rows = _rows()
        self.assertEqual(
            tuple(_expected_current_status(row["field_id"]) for row in rows),
            tuple(row["current_status"] for row in rows),
        )
        self.assertEqual(
            Counter({
                "NOT_IN_CALC_AUDIT": 58,
                "CLASSIFICATION_REVIEW_REQUIRED": 86,
                "FORMULA_UNSPECIFIED": 1,
                "DEFINED_IMPLEMENTED": 7,
                "DEFINED_READY": 4,
                "DEFINED_SEMANTIC_BLOCKED": 1,
            }),
            Counter(row["current_status"] for row in rows),
        )

    def test_semantic_vocabulary_counts_and_requirements_are_mechanical(self) -> None:
        rows = _rows()
        self.assertEqual(set(EXPECTED_CLASS_COUNTS), LEGAL_CLASSES)
        self.assertEqual(Counter(EXPECTED_CLASS_COUNTS), Counter(
            row["semantic_class"] for row in rows
        ))
        self.assertTrue(all(row["confidence"] in {"HIGH", "MEDIUM", "UNRESOLVED"} for row in rows))
        for row in rows:
            requirements = dict(
                item.split("=", 1) for item in row["requirements"].split(";")
            )
            self.assertEqual({"F", "AI", "M", "P", "A", "B"}, set(requirements))
            self.assertTrue(set(requirements.values()) <= {"Y", "N", "C", "?"})
            self.assertTrue(row["evidence"])
            self.assertTrue(row["authoritative_source"])
            self.assertTrue(row["owner_layer"])
            self.assertTrue(row["readiness"])
            self.assertTrue(row["next_task"])
            self.assertTrue(row["notes"])

    def test_all_86_review_records_are_resolved_once_with_high_confidence(self) -> None:
        rows_by_id = {row["field_id"]: row for row in _rows()}
        review_ids = {
            item.field_id
            for item in CALCULATED_FIELD_SPECS
            if item.formula_status is FormulaStatus.CLASSIFICATION_REVIEW_REQUIRED
        }
        results = tuple(rows_by_id[field_id] for field_id in sorted(review_ids))
        self.assertEqual(86, len(review_ids))
        self.assertEqual(86, len(results))
        self.assertEqual(86, len({row["field_id"] for row in results}))
        self.assertTrue(all(row["confidence"] == "HIGH" for row in results))
        self.assertTrue(all(row["semantic_class"] not in {
            "AI_ANALYSIS", "MANUAL_INPUT", "SEMANTIC_UNRESOLVED"
        } for row in results))
        self.assertEqual(
            Counter({"METADATA": 37, "EVIDENCE": 22, "SYSTEM_STATUS": 19,
                     "DISPLAY": 3, "DECISION_OUTPUT": 2, "CONFIGURATION": 2,
                     "COMPOSITE_SCORE": 1}),
            Counter(row["semantic_class"] for row in results),
        )

    def test_noncalculation_semantics_have_no_calculation_evaluator(self) -> None:
        registry = build_audited_registry()
        noncalculation_classes = {
            "AI_ANALYSIS",
            "MANUAL_INPUT",
            "SYSTEM_STATUS",
            "METADATA",
            "DISPLAY",
            "EVIDENCE",
            "CONFIGURATION",
            "DECISION_OUTPUT",
            "SEMANTIC_UNRESOLVED",
        }
        for row in _rows():
            if row["field_id"] not in registry.field_ids:
                continue
            if row["semantic_class"] in noncalculation_classes or row["readiness"] == "BUSINESS_RULE_BLOCKED":
                with self.subTest(field_id=row["field_id"]):
                    self.assertIsNone(registry.function(row["field_id"]))

    def test_d2a_formula_inventory_remains_seven_counts_only(self) -> None:
        registry = build_audited_registry()
        rows_by_id = {row["field_id"]: row for row in _rows()}
        self.assertEqual(99, len(CALCULATED_FIELD_SPECS))
        self.assertEqual(7, len(D2A_IMPLEMENTED_FIELD_IDS))
        self.assertEqual(tuple(sorted(D2A_IMPLEMENTED_FIELD_IDS)), registry.executable_field_ids)
        self.assertTrue(all(
            rows_by_id[field_id]["semantic_class"] == "AGGREGATION"
            for field_id in registry.executable_field_ids
        ))


if __name__ == "__main__":
    unittest.main()
