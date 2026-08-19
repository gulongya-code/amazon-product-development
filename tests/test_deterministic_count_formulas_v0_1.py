from __future__ import annotations

import ast
from pathlib import Path
import unittest

from amazon_product_intelligence.calculations import (
    CALCULATED_FIELD_SPECS,
    COUNT_UNIT,
    D2A_DEFERRED_FIELD_IDS,
    D2A_IMPLEMENTED_FIELD_IDS,
    D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS,
    D2C_IMPLEMENTED_FIELD_IDS,
    D2_CURRENT_DEFERRED_FIELD_IDS,
    D2_IMPLEMENTED_FIELD_IDS,
    CalculationContext,
    CalculationEngine,
    CalculationInput,
    CalculationStatus,
    FormulaStatus,
    ImplementationStatus,
    InputResolutionStatus,
    build_audited_registry,
    count_unique_canonical_identifiers,
)
from amazon_product_intelligence.contracts import (
    CodeVersionScheme,
    NormalizationStatus,
    PresenceStatus,
    Provenance,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    SemanticStatus,
    TransformationCodeVersion,
    TransformationProvenance,
    TransformationStatus,
    VersionStatus,
)


ROOT = Path(__file__).resolve().parents[1]


def provenance(provider: str) -> Provenance:
    return Provenance(
        provider=provider,
        source_tool="fixture_operation",
        source_field="normalized.identity_collection",
        source_record_identity=f"{provider}:record:1",
        retrieved_at="2026-08-19T00:00:00Z",
        transformation=TransformationProvenance(
            collection_run_id=f"collection:{provider}:1",
            provider_schema_version=ProviderSchemaVersion(
                status=VersionStatus.UNKNOWN,
                value=None,
                source=ProviderSchemaSource.UNKNOWN,
            ),
            mapping_version=f"{provider}-mapping-v0.1",
            transformation_run_id=f"transform:{provider}:1",
            transformation_code_version=TransformationCodeVersion(
                status=VersionStatus.KNOWN,
                value="test-version",
                scheme=CodeVersionScheme.BUILD_VERSION,
            ),
            raw_evidence_reference=f"raw:{provider}:1",
            transformed_at="2026-08-19T00:00:01Z",
            transformation_status=TransformationStatus.SUCCESS,
        ),
        semantic_validation_status=SemanticStatus.CONFIRMED,
    )


def calculation_context() -> CalculationContext:
    return CalculationContext(
        calculation_run_id="calculation-run:d2a:1",
        configuration_version="calculation-config:v0.1",
    )


class DeterministicCountFormulaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = build_audited_registry()
        self.engine = CalculationEngine(self.registry)

    def input_for(
        self,
        target_field: str,
        members: tuple[str, ...] | None,
        *,
        providers: tuple[str, ...] = ("provider_alpha",),
        presence_status: PresenceStatus = PresenceStatus.PRESENT,
        normalization_status: NormalizationStatus = NormalizationStatus.NORMALIZED,
        semantic_status: SemanticStatus = SemanticStatus.CONFIRMED,
        resolution_status: InputResolutionStatus = InputResolutionStatus.RESOLVED,
        reverse_lineage: bool = False,
    ) -> CalculationInput:
        dependency = self.registry.get(target_field).dependencies[0].field_id
        source_provenances = tuple(provenance(provider) for provider in providers)
        evidence_references = tuple(f"evidence:{provider}:1" for provider in providers)
        if reverse_lineage:
            source_provenances = tuple(reversed(source_provenances))
            evidence_references = tuple(reversed(evidence_references))
        if presence_status is not PresenceStatus.PRESENT:
            members = None
            normalization_status = NormalizationStatus.NOT_APPLICABLE
        return CalculationInput(
            field_id=dependency,
            value=members,
            presence_status=presence_status,
            normalization_status=normalization_status,
            semantic_status=semantic_status,
            unit=None,
            resolution_status=resolution_status,
            evidence_references=evidence_references,
            provenances=source_provenances,
        )

    def calculate(self, target_field: str, item: CalculationInput):
        return self.engine.calculate(
            (target_field,),
            {item.field_id: item},
            calculation_context(),
        ).get(target_field)

    def test_registry_exposes_exactly_seven_governed_count_formulas(self) -> None:
        self.assertEqual(7, len(D2A_IMPLEMENTED_FIELD_IDS))
        self.assertEqual(tuple(sorted(D2_IMPLEMENTED_FIELD_IDS)), self.registry.executable_field_ids)
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                spec = self.registry.get(field_id)
                self.assertIs(FormulaStatus.DEFINED, spec.formula_status)
                self.assertIs(ImplementationStatus.IMPLEMENTED, spec.implementation_status)
                self.assertEqual("v0.1-count-formula", spec.calculation_version)
                self.assertIsNotNone(spec.calculation_rule_id)
                self.assertIs(count_unique_canonical_identifiers, self.registry.function(field_id))

    def test_each_formula_counts_a_present_non_empty_canonical_collection(self) -> None:
        members = ("canonical:identity:1", "canonical:identity:2", "canonical:identity:3")
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                result = self.calculate(field_id, self.input_for(field_id, members))
                self.assertIs(CalculationStatus.CALCULATED, result.status)
                self.assertEqual(3, result.value)
                self.assertEqual(COUNT_UNIT, result.unit)

    def test_each_formula_preserves_present_empty_as_zero(self) -> None:
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                result = self.calculate(field_id, self.input_for(field_id, ()))
                self.assertIs(CalculationStatus.CALCULATED, result.status)
                self.assertEqual(0, result.value)

    def test_each_formula_never_turns_missing_or_unknown_into_zero(self) -> None:
        cases = (
            (PresenceStatus.MISSING, CalculationStatus.MISSING_INPUT),
            (PresenceStatus.UNKNOWN, CalculationStatus.UNKNOWN_INPUT),
        )
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            for presence, expected in cases:
                with self.subTest(field_id=field_id, presence=presence):
                    result = self.calculate(
                        field_id,
                        self.input_for(field_id, None, presence_status=presence),
                    )
                    self.assertIs(expected, result.status)
                    self.assertIsNone(result.value)

    def test_each_formula_blocks_failed_normalization(self) -> None:
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                result = self.calculate(
                    field_id,
                    self.input_for(
                        field_id,
                        ("canonical:identity:1",),
                        normalization_status=NormalizationStatus.FAILED,
                    ),
                )
                self.assertIs(CalculationStatus.INVALID_INPUT, result.status)
                self.assertIsNone(result.value)

    def test_each_formula_rejects_duplicate_or_noncanonical_collection_boundaries(self) -> None:
        invalid_collections = (
            ("canonical:identity:1", "canonical:identity:1"),
            ("canonical:identity:2", "canonical:identity:1"),
            ("canonical:identity:1", ""),
        )
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            for members in invalid_collections:
                with self.subTest(field_id=field_id, members=members):
                    result = self.calculate(field_id, self.input_for(field_id, members))
                    self.assertIs(CalculationStatus.FAILED, result.status)
                    self.assertIsNone(result.value)
                    self.assertEqual("CALCULATION_FAILED", result.issues[0].code)

    def test_each_formula_is_deterministic_including_lineage_ordering(self) -> None:
        members = ("canonical:identity:1", "canonical:identity:2")
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                forward = self.input_for(
                    field_id,
                    members,
                    providers=("provider_alpha", "provider_beta"),
                )
                reversed_lineage = self.input_for(
                    field_id,
                    members,
                    providers=("provider_alpha", "provider_beta"),
                    reverse_lineage=True,
                )
                first = self.calculate(field_id, forward).to_dict()
                second = self.calculate(field_id, reversed_lineage).to_dict()
                repeat = self.calculate(field_id, forward).to_dict()
                self.assertEqual(first, second)
                self.assertEqual(first, repeat)

    def test_each_formula_retains_every_input_provenance_and_raw_reference(self) -> None:
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                result = self.calculate(
                    field_id,
                    self.input_for(
                        field_id,
                        ("canonical:identity:1",),
                        providers=("provider_alpha", "provider_beta"),
                    ),
                )
                lineage = result.provenance.input_lineage[0]
                self.assertEqual(
                    {"provider_alpha", "provider_beta"},
                    {item.provider for item in lineage.provenances},
                )
                self.assertEqual(
                    {"raw:provider_alpha:1", "raw:provider_beta:1"},
                    {
                        item.transformation.raw_evidence_reference
                        for item in lineage.provenances
                    },
                )
                self.assertEqual(self.registry.get(field_id).calculation_rule_id, result.calculation_rule_id)

    def test_provider_identity_cannot_change_formula_output(self) -> None:
        members = ("canonical:identity:1", "canonical:identity:2")
        for field_id in D2A_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                alpha = self.calculate(
                    field_id,
                    self.input_for(field_id, members, providers=("provider_alpha",)),
                )
                beta = self.calculate(
                    field_id,
                    self.input_for(field_id, members, providers=("provider_beta",)),
                )
                self.assertEqual(alpha.value, beta.value)
                self.assertEqual(alpha.status, beta.status)
                self.assertEqual(alpha.unit, beta.unit)
                self.assertEqual(alpha.calculation_rule_id, beta.calculation_rule_id)
                self.assertEqual(alpha.calculation_version, beta.calculation_version)
                self.assertEqual(
                    alpha.provenance.output_fingerprint,
                    beta.provenance.output_fingerprint,
                )

    def test_one_formula_failure_does_not_affect_an_independent_success(self) -> None:
        bad_field, good_field = D2A_IMPLEMENTED_FIELD_IDS[:2]
        bad = self.input_for(
            bad_field,
            ("canonical:identity:1", "canonical:identity:1"),
        )
        good = self.input_for(good_field, ("canonical:identity:1", "canonical:identity:2"))
        batch = self.engine.calculate(
            (bad_field, good_field),
            {bad.field_id: bad, good.field_id: good},
            calculation_context(),
        )
        self.assertIs(CalculationStatus.FAILED, batch.get(bad_field).status)
        self.assertIs(CalculationStatus.CALCULATED, batch.get(good_field).status)
        self.assertEqual(2, batch.get(good_field).value)

    def test_ambiguous_and_currently_deferred_fields_have_no_evaluator(self) -> None:
        self.assertEqual(
            ("workbook.competition_evidence.variation_evidence_count",),
            D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS,
        )
        self.assertEqual(4, len(D2A_DEFERRED_FIELD_IDS))
        self.assertEqual(2, len(D2C_IMPLEMENTED_FIELD_IDS))
        self.assertTrue(set(D2C_IMPLEMENTED_FIELD_IDS) < set(D2A_DEFERRED_FIELD_IDS))
        for field_id in D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS:
            self.assertIs(
                ImplementationStatus.BLOCKED_BY_SEMANTIC_AMBIGUITY,
                self.registry.get(field_id).implementation_status,
            )
        for field_id in D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS + D2_CURRENT_DEFERRED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                self.assertIsNone(self.registry.function(field_id))

    def test_99_field_audit_statuses_remain_conservative(self) -> None:
        formula_counts = {
            status: sum(spec.formula_status is status for spec in CALCULATED_FIELD_SPECS)
            for status in FormulaStatus
        }
        self.assertEqual(99, len(CALCULATED_FIELD_SPECS))
        self.assertEqual(99, len({spec.field_id for spec in CALCULATED_FIELD_SPECS}))
        self.assertEqual(12, formula_counts[FormulaStatus.DEFINED])
        self.assertEqual(1, formula_counts[FormulaStatus.FORMULA_UNSPECIFIED])
        self.assertEqual(86, formula_counts[FormulaStatus.CLASSIFICATION_REVIEW_REQUIRED])
        self.assertEqual(99, sum(formula_counts.values()))

        implementation_counts = {
            status: sum(spec.implementation_status is status for spec in CALCULATED_FIELD_SPECS)
            for status in ImplementationStatus
        }
        self.assertEqual(9, implementation_counts[ImplementationStatus.IMPLEMENTED])
        self.assertEqual(
            1,
            implementation_counts[ImplementationStatus.BLOCKED_BY_SEMANTIC_AMBIGUITY],
        )
        self.assertEqual(2, implementation_counts[ImplementationStatus.READY_FOR_IMPLEMENTATION])
        self.assertEqual(1, implementation_counts[ImplementationStatus.FORMULA_MISSING])
        self.assertEqual(86, implementation_counts[ImplementationStatus.CLASSIFICATION_REVIEW])
        self.assertEqual(99, sum(implementation_counts.values()))

    def test_production_formula_module_has_no_impure_runtime_imports_or_calls(self) -> None:
        path = ROOT / "src" / "amazon_product_intelligence" / "calculations" / "functions.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        forbidden_imports = {"os", "pathlib", "random", "subprocess", "time", "urllib"}
        imported_roots = {
            alias.name.split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".", 1)[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.level == 0
        }
        self.assertTrue(forbidden_imports.isdisjoint(imported_roots))
        called_names = {
            node.func.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        self.assertTrue({"open", "exec", "eval"}.isdisjoint(called_names))


if __name__ == "__main__":
    unittest.main()
