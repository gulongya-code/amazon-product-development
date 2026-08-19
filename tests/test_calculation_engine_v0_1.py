from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import re
import unittest

from amazon_product_intelligence.calculations import (
    AUDITED_CALCULATED_FIELDS,
    CALCULATED_FIELD_SPECS,
    D2A_DEFERRED_FIELD_IDS,
    D2A_IMPLEMENTED_FIELD_IDS,
    D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS,
    D2_READY_FIELD_IDS,
    CalculatedFieldRegistry,
    CalculatedFieldSpec,
    CalculationContext,
    CalculationDependency,
    CalculationDependencyCycleError,
    CalculationEngine,
    CalculationEvaluationContext,
    CalculationInput,
    CalculationOutcome,
    CalculationStatus,
    CalculationTier,
    DependencyType,
    DuplicateCalculatedFieldError,
    FormulaConfidence,
    FormulaStatus,
    ImplementationStatus,
    InputResolutionStatus,
    InvalidCalculationInputError,
    MissingPolicy,
    UnknownCalculatedFieldError,
    UnknownCalculationDependencyError,
    build_audited_registry,
    require_compatible_currencies,
    require_compatible_units,
    safe_decimal_ratio,
)
from amazon_product_intelligence.contracts import (
    BlockingScope,
    CodeVersionScheme,
    DataQualityIssue,
    NormalizationStatus,
    OriginStage,
    PresenceStatus,
    Provenance,
    ProviderSchemaSource,
    ProviderSchemaVersion,
    SemanticStatus,
    Severity,
    SubjectRef,
    SubjectType,
    TransformationCodeVersion,
    TransformationProvenance,
    TransformationStatus,
    Unit,
    VersionStatus,
    product_id,
)


ROOT = Path(__file__).resolve().parents[1]


def provenance(provider: str = "fake_a", source_field: str = "payload.value") -> Provenance:
    return Provenance(
        provider=provider,
        source_tool="fixture_operation",
        source_field=source_field,
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


def quality_issue(*, blocking: bool = True) -> DataQualityIssue:
    return DataQualityIssue(
        issue_id="quality:test:1",
        issue_code="TEST_QUALITY",
        severity=Severity.BLOCKING if blocking else Severity.WARNING,
        subject=SubjectRef(
            subject_type=SubjectType.PRODUCT,
            subject_id=product_id("US", "B0G2Q22W6D"),
            marketplace="US",
        ),
        dimension="test.value",
        message="test quality signal",
        blocking=blocking,
        blocking_scope=BlockingScope.FIELD if blocking else BlockingScope.NONE,
        source_references=("evidence:test:1",),
        created_at="2026-08-19T00:00:02Z",
        origin_stage=OriginStage.NORMALIZATION,
        collection_run_id="collection:fake_a:1",
        transformation_run_id="transform:fake_a:1",
        mapping_version="fake_a-mapping-v0.1",
    )


def calculation_input(
    field_id: str,
    value=Decimal("1"),
    *,
    provider: str = "fake_a",
    presence_status: PresenceStatus = PresenceStatus.PRESENT,
    normalization_status: NormalizationStatus = NormalizationStatus.NORMALIZED,
    semantic_status: SemanticStatus = SemanticStatus.CONFIRMED,
    resolution_status: InputResolutionStatus = InputResolutionStatus.RESOLVED,
    unit: Unit | None = None,
    provenances: tuple[Provenance, ...] | None = None,
    issues: tuple[DataQualityIssue, ...] = (),
) -> CalculationInput:
    if presence_status is not PresenceStatus.PRESENT:
        value = None
        normalization_status = NormalizationStatus.NOT_APPLICABLE
    return CalculationInput(
        field_id=field_id,
        value=value,
        presence_status=presence_status,
        normalization_status=normalization_status,
        semantic_status=semantic_status,
        unit=unit,
        resolution_status=resolution_status,
        evidence_references=(f"evidence:{provider}:1",),
        provenances=provenances or (provenance(provider),),
        quality_issues=issues,
    )


def spec(
    field_id: str,
    dependencies: tuple[tuple[str, DependencyType], ...] = (("canonical.input_value", DependencyType.CANONICAL_INPUT),),
    *,
    formula_status: FormulaStatus = FormulaStatus.DEFINED,
    missing_policy: MissingPolicy = MissingPolicy.REQUIRE_ALL,
    version: str = "v0.1",
) -> CalculatedFieldSpec:
    return CalculatedFieldSpec(
        field_id=field_id,
        workbook_sheet="test",
        display_name=field_id,
        canonical_field="Test-only field",
        category="Test-only",
        calculation_tier=CalculationTier.BASE_DETERMINISTIC,
        output_type="decimal",
        unit="test unit",
        dependencies=tuple(
            CalculationDependency(field_id=item, dependency_type=dependency_type)
            for item, dependency_type in dependencies
        ),
        formula_status=formula_status,
        formula_reference="Explicit test-only deterministic formula.",
        missing_policy=missing_policy,
        zero_semantics="Zero and False are data.",
        invalid_input_policy="Block invalid input.",
        partial_input_policy="Follow the declared missing policy.",
        calculation_version=version,
        calculation_rule_id=f"calculation.{field_id.rsplit('.', 1)[-1]}",
        provenance_requirement="Retain every test input provenance.",
        formula_confidence=FormulaConfidence.CONFIRMED,
        quality_implication="Test-only proof.",
        implementation_status=ImplementationStatus.READY_FOR_IMPLEMENTATION,
        notes="Not a production business formula.",
    )


def outcome_first(context: CalculationEvaluationContext) -> CalculationOutcome:
    key = sorted(context.values)[0]
    return CalculationOutcome(value=context.values[key], unit=context.units[key])


def add(context: CalculationEvaluationContext) -> CalculationOutcome:
    return CalculationOutcome(value=sum(context.values.values(), Decimal("0")), unit=None)


def execution_context() -> CalculationContext:
    return CalculationContext(
        calculation_run_id="calculation-run:test:001",
        configuration_version="test-config-v0.1",
    )


class CalculationSpecificationAuditTests(unittest.TestCase):
    def test_matrix_has_exactly_99_calculated_rows(self) -> None:
        text = (ROOT / "docs" / "integration" / "API_FIELD_COVERAGE_MATRIX_V0.1.md").read_text(encoding="utf-8")
        rows = [
            line
            for line in text.splitlines()
            if line.startswith("|")
            and len(line.split("|")) == 8
            and re.search(r"\| CALCULATED \|", line)
        ]
        self.assertEqual(99, len(rows))

    def test_all_matrix_rows_are_in_machine_readable_specs(self) -> None:
        text = (ROOT / "docs" / "integration" / "API_FIELD_COVERAGE_MATRIX_V0.1.md").read_text(encoding="utf-8")
        section = None
        matrix: list[tuple[str, str]] = []
        for line in text.splitlines():
            match = re.match(r"### (\d\d_[^\u2014]+?) \u2014", line)
            if match:
                section = match.group(1).strip()
            if (
                section
                and line.startswith("|")
                and len(line.split("|")) == 8
                and "| CALCULATED |" in line
            ):
                matrix.append((section, line.split("|")[1].strip()))
        self.assertEqual(sorted(matrix), sorted(AUDITED_CALCULATED_FIELDS))
        self.assertEqual(99, len(CALCULATED_FIELD_SPECS))
        self.assertEqual(99, len({item.field_id for item in CALCULATED_FIELD_SPECS}))

    def test_formula_status_counts_are_conservative(self) -> None:
        counts = {
            status: sum(item.formula_status is status for item in CALCULATED_FIELD_SPECS)
            for status in FormulaStatus
        }
        self.assertEqual(12, counts[FormulaStatus.DEFINED])
        self.assertEqual(1, counts[FormulaStatus.FORMULA_UNSPECIFIED])
        self.assertEqual(86, counts[FormulaStatus.CLASSIFICATION_REVIEW_REQUIRED])
        self.assertEqual(99, sum(counts.values()))

    def test_tier_counts_total_99(self) -> None:
        counts = {
            tier: sum(item.calculation_tier is tier for item in CALCULATED_FIELD_SPECS)
            for tier in CalculationTier
        }
        self.assertEqual(16, counts[CalculationTier.BASE_DETERMINISTIC])
        self.assertEqual(16, counts[CalculationTier.MARKET_DERIVED])
        self.assertEqual(10, counts[CalculationTier.COMPETITION_DERIVED])
        self.assertEqual(11, counts[CalculationTier.KEYWORD_DERIVED])
        self.assertEqual(0, counts[CalculationTier.PROFIT_COST_DERIVED])
        self.assertEqual(14, counts[CalculationTier.COMPOSITE_SCORE])
        self.assertEqual(12, counts[CalculationTier.AI_DECISION])
        self.assertEqual(20, counts[CalculationTier.OTHER])
        self.assertEqual(99, sum(counts.values()))

    def test_d2_candidates_are_defined_and_topologically_ordered(self) -> None:
        registry = build_audited_registry()
        order = registry.execution_order(D2_READY_FIELD_IDS)
        self.assertEqual(12, len(order))
        self.assertLess(
            order.index("workbook.product_structure.product_count"),
            order.index("workbook.product_structure.observed_share"),
        )
        self.assertLess(
            order.index("workbook.market_overview.observed_product_count"),
            order.index("workbook.product_structure.observed_share"),
        )

    def test_audited_registry_only_exposes_accepted_d2a_formulas(self) -> None:
        registry = build_audited_registry()
        self.assertEqual(tuple(sorted(D2A_IMPLEMENTED_FIELD_IDS)), registry.executable_field_ids)
        plan = CalculationEngine(registry).plan(D2_READY_FIELD_IDS)
        self.assertEqual(
            set(D2A_DEFERRED_FIELD_IDS) | set(D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS),
            set(plan.blocked_fields),
        )
        self.assertTrue(all("EVALUATOR_NOT_REGISTERED" in reasons for reasons in plan.blocked_fields.values()))


class CalculatedFieldRegistryTests(unittest.TestCase):
    def test_register_lookup_and_dependencies(self) -> None:
        registry = CalculatedFieldRegistry()
        item = spec("test.output")
        registry.register(item, outcome_first)
        self.assertIs(item, registry.get("test.output"))
        self.assertEqual(("canonical.input_value",), registry.dependencies("test.output"))

    def test_duplicate_registration_fails_explicitly(self) -> None:
        registry = CalculatedFieldRegistry()
        item = spec("test.output")
        registry.register(item)
        with self.assertRaises(DuplicateCalculatedFieldError):
            registry.register(item)

    def test_unknown_lookup_fails_explicitly(self) -> None:
        with self.assertRaises(UnknownCalculatedFieldError):
            CalculatedFieldRegistry().get("test.unknown")

    def test_unknown_calculated_dependency_is_detected(self) -> None:
        registry = CalculatedFieldRegistry()
        registry.register(spec("test.output", (("test.missing", DependencyType.CALCULATED_FIELD),)))
        with self.assertRaises(UnknownCalculationDependencyError):
            registry.validate()

    def test_cycle_is_detected_without_recursion_loop(self) -> None:
        registry = CalculatedFieldRegistry()
        registry.register(spec("test.field_a", (("test.field_b", DependencyType.CALCULATED_FIELD),)))
        registry.register(spec("test.field_b", (("test.field_c", DependencyType.CALCULATED_FIELD),)))
        registry.register(spec("test.field_c", (("test.field_a", DependencyType.CALCULATED_FIELD),)))
        with self.assertRaises(CalculationDependencyCycleError):
            registry.validate()

    def test_multi_level_execution_order_is_deterministic(self) -> None:
        registry = CalculatedFieldRegistry()
        registry.register(spec("test.field_c", (("test.field_b", DependencyType.CALCULATED_FIELD),)))
        registry.register(spec("test.field_a"))
        registry.register(spec("test.field_b", (("test.field_a", DependencyType.CALCULATED_FIELD),)))
        self.assertEqual(
            ("test.field_a", "test.field_b", "test.field_c"),
            registry.execution_order(("test.field_c",)),
        )


class CalculationEngineExecutionTests(unittest.TestCase):
    def engine(self, entries: tuple[tuple[CalculatedFieldSpec, object], ...]) -> CalculationEngine:
        registry = CalculatedFieldRegistry()
        for specification, function in entries:
            registry.register(specification, function)
        return CalculationEngine(registry)

    def test_simple_calculation_returns_contract_not_raw_value(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        result = engine.calculate(
            ("test.output",),
            {"canonical.input_value": calculation_input("canonical.input_value", Decimal("2.50"))},
            execution_context(),
        ).get("test.output")
        self.assertEqual(CalculationStatus.CALCULATED, result.status)
        self.assertEqual(Decimal("2.50"), result.value)
        self.assertIsNotNone(result.provenance)

    def test_invalid_input_mapping_fails_with_stable_contract_error(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        with self.assertRaises(InvalidCalculationInputError):
            engine.calculate(("test.output",), {"canonical.input_value": object()}, execution_context())
        item = calculation_input("canonical.input_value")
        with self.assertRaises(InvalidCalculationInputError):
            engine.calculate(("test.output",), {"canonical.wrong_key": item}, execution_context())

    def test_missing_unknown_and_invalid_never_become_zero(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        cases = (
            (calculation_input("canonical.input_value", presence_status=PresenceStatus.MISSING), CalculationStatus.MISSING_INPUT),
            (calculation_input("canonical.input_value", presence_status=PresenceStatus.UNKNOWN), CalculationStatus.UNKNOWN_INPUT),
            (
                calculation_input(
                    "canonical.input_value",
                    Decimal("4"),
                    semantic_status=SemanticStatus.SEMANTICS_UNCONFIRMED,
                ),
                CalculationStatus.INVALID_INPUT,
            ),
        )
        for item, expected in cases:
            with self.subTest(expected=expected):
                result = engine.calculate(("test.output",), {item.field_id: item}, execution_context()).get("test.output")
                self.assertEqual(expected, result.status)
                self.assertIsNone(result.value)

    def test_blocking_data_quality_issue_prevents_calculation(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        item = calculation_input("canonical.input_value", issues=(quality_issue(),))
        result = engine.calculate(("test.output",), {item.field_id: item}, execution_context()).get("test.output")
        self.assertEqual(CalculationStatus.INVALID_INPUT, result.status)

    def test_unresolved_canonical_input_is_blocked(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        item = calculation_input(
            "canonical.input_value",
            resolution_status=InputResolutionStatus.UNRESOLVED,
        )
        result = engine.calculate(("test.output",), {item.field_id: item}, execution_context()).get("test.output")
        self.assertEqual(CalculationStatus.DEPENDENCY_BLOCKED, result.status)

    def test_zero_false_and_empty_collection_remain_present_data(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        for value in (0, False, ()):
            with self.subTest(value=value):
                item = calculation_input("canonical.input_value", value)
                result = engine.calculate(("test.output",), {item.field_id: item}, execution_context()).get("test.output")
                self.assertEqual(CalculationStatus.CALCULATED, result.status)
                self.assertEqual(value, result.value)

    def test_partial_missing_policy_is_field_specific(self) -> None:
        dependencies = (
            ("canonical.input_a", DependencyType.CANONICAL_INPUT),
            ("canonical.input_b", DependencyType.CANONICAL_INPUT),
        )
        engine = self.engine(((spec("test.output", dependencies, missing_policy=MissingPolicy.ALLOW_PARTIAL), add),))
        result = engine.calculate(
            ("test.output",),
            {"canonical.input_a": calculation_input("canonical.input_a", Decimal("2"))},
            execution_context(),
        ).get("test.output")
        self.assertEqual(CalculationStatus.PARTIAL, result.status)
        self.assertEqual(Decimal("2"), result.value)

    def test_division_by_zero_returns_explicit_status(self) -> None:
        def ratio(context: CalculationEvaluationContext) -> CalculationOutcome:
            return CalculationOutcome(
                value=safe_decimal_ratio(context.values["canonical.numerator"], context.values["canonical.denominator"]),
                unit=None,
            )

        dependencies = (
            ("canonical.numerator", DependencyType.CANONICAL_INPUT),
            ("canonical.denominator", DependencyType.CANONICAL_INPUT),
        )
        engine = self.engine(((spec("test.ratio", dependencies), ratio),))
        inputs = {
            "canonical.numerator": calculation_input("canonical.numerator", Decimal("3")),
            "canonical.denominator": calculation_input("canonical.denominator", Decimal("0")),
        }
        result = engine.calculate(("test.ratio",), inputs, execution_context()).get("test.ratio")
        self.assertEqual(CalculationStatus.DIVISION_BY_ZERO, result.status)
        self.assertIsNone(result.value)

    def test_decimal_precision_is_retained(self) -> None:
        def ratio(context: CalculationEvaluationContext) -> CalculationOutcome:
            return CalculationOutcome(value=safe_decimal_ratio(Decimal("1"), Decimal("3")), unit=None)

        engine = self.engine(((spec("test.ratio"), ratio),))
        item = calculation_input("canonical.input_value", Decimal("1"))
        value = engine.calculate(("test.ratio",), {item.field_id: item}, execution_context()).get("test.ratio").value
        self.assertIsInstance(value, Decimal)
        self.assertEqual(Decimal("1") / Decimal("3"), value)

    def test_unit_and_currency_mismatch_are_business_statuses(self) -> None:
        usd = Unit(dimension="CURRENCY", unit_code="USD", unit_system="ISO-4217")
        cny = Unit(dimension="CURRENCY", unit_code="CNY", unit_system="ISO-4217")
        count = Unit(dimension="COUNT", unit_code="COUNT", unit_system=None)

        def currency(context: CalculationEvaluationContext) -> CalculationOutcome:
            unit = require_compatible_currencies(context.units.values())
            return CalculationOutcome(value=Decimal("1"), unit=unit)

        def units(context: CalculationEvaluationContext) -> CalculationOutcome:
            unit = require_compatible_units(context.units.values())
            return CalculationOutcome(value=Decimal("1"), unit=unit)

        dependencies = (
            ("canonical.input_a", DependencyType.CANONICAL_INPUT),
            ("canonical.input_b", DependencyType.CANONICAL_INPUT),
        )
        inputs = {
            "canonical.input_a": calculation_input("canonical.input_a", unit=usd),
            "canonical.input_b": calculation_input("canonical.input_b", unit=cny),
        }
        currency_result = self.engine(((spec("test.currency", dependencies), currency),)).calculate(
            ("test.currency",), inputs, execution_context()
        ).get("test.currency")
        self.assertEqual(CalculationStatus.CURRENCY_MISMATCH, currency_result.status)
        inputs["canonical.input_b"] = calculation_input("canonical.input_b", unit=count)
        unit_result = self.engine(((spec("test.units", dependencies), units),)).calculate(
            ("test.units",), inputs, execution_context()
        ).get("test.units")
        self.assertEqual(CalculationStatus.UNIT_MISMATCH, unit_result.status)

    def test_provenance_retains_all_sources_values_and_quality_references(self) -> None:
        item = calculation_input(
            "canonical.input_value",
            Decimal("7.25"),
            provenances=(provenance("fake_b"), provenance("fake_a")),
            issues=(quality_issue(blocking=False),),
        )
        result = self.engine(((spec("test.output"), outcome_first),)).calculate(
            ("test.output",), {item.field_id: item}, execution_context()
        ).get("test.output")
        lineage = result.provenance.input_lineage[0]
        self.assertEqual(Decimal("7.25"), lineage.normalized_value)
        self.assertEqual({"fake_a", "fake_b"}, {item.provider for item in lineage.provenances})
        self.assertEqual(("quality:test:1",), lineage.quality_issue_ids)
        self.assertTrue(result.provenance.input_fingerprint)
        self.assertTrue(result.provenance.output_fingerprint)

    def test_calculated_dependency_is_traced_by_result_id(self) -> None:
        dependency = spec("test.base")
        derived = spec("test.derived", (("test.base", DependencyType.CALCULATED_FIELD),))
        engine = self.engine(((dependency, outcome_first), (derived, outcome_first)))
        item = calculation_input("canonical.input_value", Decimal("9"))
        batch = engine.calculate(("test.derived",), {item.field_id: item}, execution_context())
        self.assertEqual(
            (batch.get("test.base").result_id,),
            batch.get("test.derived").provenance.calculated_dependency_result_ids,
        )

    def test_formula_version_changes_result_identity(self) -> None:
        item = calculation_input("canonical.input_value", Decimal("5"))
        first = self.engine(((spec("test.output", version="v0.1"), outcome_first),)).calculate(
            ("test.output",), {item.field_id: item}, execution_context()
        ).get("test.output")
        second = self.engine(((spec("test.output", version="v0.2"), outcome_first),)).calculate(
            ("test.output",), {item.field_id: item}, execution_context()
        ).get("test.output")
        self.assertNotEqual(first.result_id, second.result_id)
        self.assertNotEqual(first.provenance.output_fingerprint, second.provenance.output_fingerprint)

    def test_independent_failure_is_isolated_and_descendant_is_blocked(self) -> None:
        def fail(context: CalculationEvaluationContext) -> CalculationOutcome:
            raise RuntimeError("private raw value must not leak")

        bad = spec("test.bad")
        child = spec("test.child", (("test.bad", DependencyType.CALCULATED_FIELD),))
        good = spec("test.good")
        engine = self.engine(((bad, fail), (child, outcome_first), (good, outcome_first)))
        item = calculation_input("canonical.input_value", Decimal("3"))
        batch = engine.calculate(("test.child", "test.good"), {item.field_id: item}, execution_context())
        self.assertEqual(CalculationStatus.FAILED, batch.get("test.bad").status)
        self.assertEqual(CalculationStatus.DEPENDENCY_BLOCKED, batch.get("test.child").status)
        self.assertEqual(CalculationStatus.CALCULATED, batch.get("test.good").status)
        self.assertNotIn("private raw value", str(batch.to_dict()))

    def test_partial_execution_only_includes_requested_dependency_closure(self) -> None:
        base = spec("test.base")
        child = spec("test.child", (("test.base", DependencyType.CALCULATED_FIELD),))
        other = spec("test.other")
        engine = self.engine(((base, outcome_first), (child, outcome_first), (other, outcome_first)))
        item = calculation_input("canonical.input_value", Decimal("1"))
        batch = engine.calculate(("test.child",), {item.field_id: item}, execution_context())
        self.assertEqual(("test.base", "test.child"), tuple(result.field_id for result in batch.results))

    def test_same_input_is_deterministic(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        item = calculation_input("canonical.input_value", Decimal("4.20"))
        first = engine.calculate(("test.output",), {item.field_id: item}, execution_context()).to_dict()
        second = engine.calculate(("test.output",), {item.field_id: item}, execution_context()).to_dict()
        self.assertEqual(first, second)

    def test_provider_identity_never_changes_formula_result(self) -> None:
        engine = self.engine(((spec("test.output"), outcome_first),))
        left = calculation_input("canonical.input_value", Decimal("8"), provider="fake_x")
        right = calculation_input("canonical.input_value", Decimal("8"), provider="fake_s")
        left_result = engine.calculate(("test.output",), {left.field_id: left}, execution_context()).get("test.output")
        right_result = engine.calculate(("test.output",), {right.field_id: right}, execution_context()).get("test.output")
        self.assertEqual(left_result.value, right_result.value)
        self.assertEqual(left_result.status, right_result.status)

    def test_formula_undefined_is_never_guessed_or_executed(self) -> None:
        called = False

        def should_not_run(context: CalculationEvaluationContext) -> CalculationOutcome:
            nonlocal called
            called = True
            return outcome_first(context)

        undefined = spec("test.undefined", formula_status=FormulaStatus.FORMULA_UNSPECIFIED)
        engine = self.engine(((undefined, should_not_run),))
        item = calculation_input("canonical.input_value", Decimal("1"))
        result = engine.calculate(("test.undefined",), {item.field_id: item}, execution_context()).get("test.undefined")
        self.assertEqual(CalculationStatus.FORMULA_UNDEFINED, result.status)
        self.assertFalse(called)

    def test_new_test_formula_requires_no_engine_core_change(self) -> None:
        registry = CalculatedFieldRegistry()
        registry.register(spec("extension.fake_calculated_field"), outcome_first)
        item = calculation_input("canonical.input_value", Decimal("11"))
        result = CalculationEngine(registry).calculate(
            ("extension.fake_calculated_field",), {item.field_id: item}, execution_context()
        ).get("extension.fake_calculated_field")
        self.assertEqual(Decimal("11"), result.value)

    def test_calculation_package_has_no_concrete_provider_import_or_branch(self) -> None:
        package = ROOT / "src" / "amazon_product_intelligence" / "calculations"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package.glob("*.py"))
        self.assertNotRegex(source, r"import\s+.*(?:xiyou|sorftime)")
        self.assertNotRegex(source, r"provider(?:_id)?\s*==")


if __name__ == "__main__":
    unittest.main()
