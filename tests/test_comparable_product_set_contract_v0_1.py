from __future__ import annotations

from dataclasses import fields
from pathlib import Path
import unittest

from amazon_product_intelligence.calculations import build_audited_registry
from amazon_product_intelligence.contracts import Comparability


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "intelligence" / "COMPARABLE_PRODUCT_SET_CONTRACT_V0.1.md"
MATRIX = ROOT / "docs" / "intelligence" / "FIELD_SEMANTIC_RESPONSIBILITY_MATRIX_V0.1.md"
CALCULATION_SPEC = ROOT / "docs" / "intelligence" / "CALCULATED_FIELD_SPECIFICATION_V0.1.md"

MINIMUM_PRICE_FIELD = "workbook.product_structure.minimum_comparable_price"
MAXIMUM_PRICE_FIELD = "workbook.product_structure.maximum_comparable_price"


def contract_text() -> str:
    return CONTRACT.read_text(encoding="utf-8")


def matrix_row(ordinal: str) -> tuple[str, ...]:
    prefix = f"| {ordinal} |"
    matches = tuple(
        line for line in MATRIX.read_text(encoding="utf-8").splitlines()
        if line.startswith(prefix)
    )
    if len(matches) != 1:
        raise AssertionError(f"expected one matrix row for {ordinal}, found {len(matches)}")
    return tuple(item.strip().strip("`") for item in matches[0].strip().strip("|").split("|"))


class ComparableProductSetContractV01Tests(unittest.TestCase):
    def test_contract_version_owner_and_execution_status_are_explicit(self) -> None:
        text = contract_text()
        self.assertIn("comparable_product_set_contract_version = comparable-product-set-v0.1", text)
        self.assertIn("| Owner | Business / Intelligence domain |", text)
        self.assertIn("| Membership execution | `BLOCKED_BY_MEMBERSHIP_SOURCE` |", text)
        self.assertIn("P0 BUSINESS DECISION REQUIRED", text)

    def test_canonical_comparability_is_not_product_comparability(self) -> None:
        self.assertEqual(
            ("identity", "dimension", "semantic", "scope", "period", "unit", "direction"),
            tuple(field.name for field in fields(Comparability)),
        )
        text = contract_text()
        self.assertIn("Canonical `Comparability`", text)
        self.assertIn("Canonical Comparability != Comparable Product relationship", text)
        self.assertNotIn("target_product_identity", {field.name for field in fields(Comparability)})
        self.assertNotIn("candidate_product_identity", {field.name for field in fields(Comparability)})

    def test_structural_eligibility_is_explicit_and_insufficient(self) -> None:
        text = contract_text()
        for clause in (
            "CPS-IDENTITY-001",
            "CPS-MARKETPLACE-001",
            "CPS-CONTEXT-001",
            "CPS-TARGET-001",
            "CPS-STRUCTURE-001",
            "CPS-AUTHORITY-001",
        ):
            with self.subTest(clause=clause):
                self.assertIn(f"`{clause}`", text)
        self.assertIn("structural eligibility alone sufficient? NO", text)
        self.assertIn("Final membership requires a governed comparability assertion", text)

    def test_same_marketplace_and_target_exclusion_are_versioned(self) -> None:
        text = contract_text()
        self.assertIn("cross-market comparability = NOT_SUPPORTED", text)
        self.assertIn("target_in_peer_comparable_set = false", text)
        self.assertIn("The target is allowed in the candidate universe", text)
        self.assertIn("This policy is part of `comparable-product-set-v0.1`", text)

    def test_related_keyword_variation_and_provider_membership_are_insufficient(self) -> None:
        text = contract_text()
        for statement in (
            "related product != comparable product",
            "Same keyword, co-occurrence, or related-product status does not create membership",
            "Parent/child, sibling, or same family does not create membership",
            "Same Provider response, result page, or dataset does not create membership",
            "Same type does not mean comparable",
            "Same broad Amazon category does not create membership",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, text)

    def test_product_evidence_roles_do_not_become_automatic_authority(self) -> None:
        text = contract_text()
        for evidence in (
            "Product type",
            "Category",
            "Keyword relationship",
            "Variation relationship",
            "Brand",
            "Attributes/features",
        ):
            with self.subTest(evidence=evidence):
                self.assertIn(f"| {evidence} |", text)
        self.assertIn("supporting evidence only", text)
        self.assertIn("Price, sales, BSR, review count, rating, and revenue", text)

    def test_missing_empty_not_comparable_and_unresolved_remain_distinct(self) -> None:
        text = contract_text()
        for distinction in (
            "missing input != empty comparable set",
            "unknown/unresolved != empty comparable set",
            "explicit NOT_COMPARABLE != unresolved",
            "valid evaluated zero-member set != unable to evaluate",
        ):
            with self.subTest(distinction=distinction):
                self.assertIn(distinction, text)
        self.assertIn("Valid empty Comparable Product Set", text)
        self.assertIn("An unqualified `[]` cannot express all of these states", text)

    def test_governed_assertion_and_result_are_auditable(self) -> None:
        text = contract_text()
        for decision in ("`COMPARABLE`", "`NOT_COMPARABLE`", "`UNRESOLVED`"):
            self.assertIn(decision, text)
        for item in (
            "membership assertions",
            "evidence references",
            "contract version",
            "quality issues",
            "provenance",
        ):
            with self.subTest(item=item):
                self.assertIn(item, text)
        self.assertIn("A Boolean alone is insufficient", text)

    def test_provider_neutrality_and_lineage_are_both_preserved(self) -> None:
        text = contract_text()
        self.assertIn("XiYou, Sorftime, and any future Provider", text)
        self.assertIn("None defines comparability", text)
        self.assertIn("Provider lineage is retained below the system-governed assertion", text)
        self.assertIn("supporting evidence references", text)
        self.assertIn("Canonical observations", text)

    def test_price_is_downstream_and_not_membership_authority(self) -> None:
        text = contract_text()
        self.assertIn("CPS-PRICE-001", text)
        self.assertIn("Price does not flow backward to define", text)
        self.assertIn("a target-relative price threshold would create a circular contract", text)
        self.assertIn("governed Comparable Product Set", text)
        self.assertIn("COMPARABLE members only", text)
        self.assertIn("minimum_comparable_price / maximum_comparable_price", text)

    def test_comparable_price_fields_have_no_registered_evaluator(self) -> None:
        registry = build_audited_registry()
        self.assertIsNone(registry.function(MINIMUM_PRICE_FIELD))
        self.assertIsNone(registry.function(MAXIMUM_PRICE_FIELD))
        text = contract_text()
        self.assertIn(
            "minimum_comparable_price ready? NO — BLOCKED BY MEMBERSHIP SOURCE", text
        )
        self.assertIn(
            "maximum_comparable_price ready? NO — BLOCKED BY MEMBERSHIP SOURCE", text
        )
        self.assertIn("No evaluator is registered or implemented", text)

    def test_semantic_matrix_records_the_governed_dependency_and_p0_block(self) -> None:
        for ordinal, field_id in (
            ("F100", MINIMUM_PRICE_FIELD),
            ("F101", MAXIMUM_PRICE_FIELD),
        ):
            with self.subTest(field_id=field_id):
                row = matrix_row(ordinal)
                self.assertEqual(14, len(row))
                self.assertEqual(field_id, row[1])
                self.assertEqual("BUSINESS_RULE_BLOCKED", row[11])
                self.assertEqual("P0_MEMBERSHIP_SOURCE", row[12])
                self.assertIn("Comparable Product Set", row[8])
                self.assertIn("BLOCKED BY MEMBERSHIP SOURCE", row[13])

    def test_calculation_spec_preserves_membership_first_dependency(self) -> None:
        text = CALCULATION_SPEC.read_text(encoding="utf-8")
        self.assertIn("COMPARABLE_PRODUCT_SET_CONTRACT_V0.1.md", text)
        self.assertIn("Governed Comparable Product Set `COMPARABLE` members", text)
        self.assertIn("`BLOCKED_BY_MEMBERSHIP_SOURCE`; no evaluator", text)
        self.assertIn("ordinary candidate inventory", text)
        self.assertIn("NO — BLOCKED BY MEMBERSHIP SOURCE", text)

    def test_membership_source_options_are_documented_without_selection(self) -> None:
        text = contract_text()
        for option in (
            "| A | Deterministic rule set |",
            "| B | Manual/operator confirmation |",
            "| C | AI-assisted assertion |",
            "| D | Hybrid hard gates plus AI/operator assertion |",
        ):
            with self.subTest(option=option):
                self.assertIn(option, text)
        self.assertIn("V0.1 does not select A, B, C, or D", text)


if __name__ == "__main__":
    unittest.main()
