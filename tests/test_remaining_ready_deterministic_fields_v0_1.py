from __future__ import annotations

from decimal import Decimal, ROUND_DOWN, localcontext
import unittest

from amazon_product_intelligence.calculations import (
    COUNT_UNIT,
    D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS,
    D2C_IMPLEMENTED_FIELD_IDS,
    D2_CURRENT_DEFERRED_FIELD_IDS,
    D2_IMPLEMENTED_FIELD_IDS,
    RATIO_UNIT,
    CalculationEngine,
    CalculationInput,
    CalculationStatus,
    FormulaStatus,
    ImplementationStatus,
    InputResolutionStatus,
    build_audited_registry,
)
from amazon_product_intelligence.contracts import (
    NormalizationStatus,
    PresenceStatus,
    SemanticStatus,
)
from tests.test_deterministic_count_formulas_v0_1 import calculation_context, provenance


MEMBER_FIELD = "workbook.product_structure.member_product_ids"
SHARE_FIELD = "workbook.product_structure.observed_share"
GROUP_INPUT = "canonical.group_product_identities"
SNAPSHOT_INPUT = "canonical.snapshot_product_identities"

PRODUCT_A = "product:US:B000000001"
PRODUCT_B = "product:US:B000000002"
PRODUCT_C = "product:US:B000000003"
PRODUCT_UK_A = "product:UK:B000000001"


def identity_input(
    field_id: str,
    members: tuple[str, ...] | str | None,
    *,
    providers: tuple[str, ...] = ("provider_alpha",),
    presence_status: PresenceStatus = PresenceStatus.PRESENT,
    normalization_status: NormalizationStatus = NormalizationStatus.NORMALIZED,
    semantic_status: SemanticStatus = SemanticStatus.CONFIRMED,
    resolution_status: InputResolutionStatus = InputResolutionStatus.RESOLVED,
    reverse_lineage: bool = False,
) -> CalculationInput:
    source_provenances = tuple(provenance(provider) for provider in providers)
    evidence_references = tuple(f"evidence:{provider}:1" for provider in providers)
    if reverse_lineage:
        source_provenances = tuple(reversed(source_provenances))
        evidence_references = tuple(reversed(evidence_references))
    if presence_status is not PresenceStatus.PRESENT:
        members = None
        normalization_status = NormalizationStatus.NOT_APPLICABLE
    return CalculationInput(
        field_id=field_id,
        value=members,
        presence_status=presence_status,
        normalization_status=normalization_status,
        semantic_status=semantic_status,
        unit=None,
        resolution_status=resolution_status,
        evidence_references=evidence_references,
        provenances=source_provenances,
    )


class RemainingReadyDeterministicFieldTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = build_audited_registry()
        self.engine = CalculationEngine(self.registry)

    def calculate_members(self, item: CalculationInput):
        return self.engine.calculate(
            (MEMBER_FIELD,),
            {item.field_id: item},
            calculation_context(),
        ).get(MEMBER_FIELD)

    def calculate_share(
        self,
        group: CalculationInput,
        snapshot: CalculationInput,
    ):
        return self.engine.calculate(
            (SHARE_FIELD,),
            {group.field_id: group, snapshot.field_id: snapshot},
            calculation_context(),
        )

    def test_registry_adds_exactly_the_two_d2c_evaluators(self) -> None:
        self.assertEqual((MEMBER_FIELD, SHARE_FIELD), D2C_IMPLEMENTED_FIELD_IDS)
        self.assertEqual(9, len(D2_IMPLEMENTED_FIELD_IDS))
        self.assertEqual(tuple(sorted(D2_IMPLEMENTED_FIELD_IDS)), self.registry.executable_field_ids)
        self.assertEqual(
            (
                "workbook.product_structure.maximum_comparable_price",
                "workbook.product_structure.minimum_comparable_price",
            ),
            D2_CURRENT_DEFERRED_FIELD_IDS,
        )
        for field_id in D2C_IMPLEMENTED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                specification = self.registry.get(field_id)
                self.assertIs(FormulaStatus.DEFINED, specification.formula_status)
                self.assertIs(ImplementationStatus.IMPLEMENTED, specification.implementation_status)
                self.assertIsNotNone(self.registry.function(field_id))
        self.assertEqual("v0.1-member-product-ids-formula", self.registry.get(MEMBER_FIELD).calculation_version)
        self.assertEqual("v0.1-observed-share-formula", self.registry.get(SHARE_FIELD).calculation_version)

    def test_member_product_ids_projects_the_authoritative_collection_unchanged(self) -> None:
        members = (PRODUCT_A, PRODUCT_B, PRODUCT_C)
        result = self.calculate_members(identity_input(GROUP_INPUT, members))
        self.assertIs(CalculationStatus.CALCULATED, result.status)
        self.assertEqual(members, result.value)
        self.assertIsInstance(result.value, tuple)
        self.assertIsNone(result.unit)
        self.assertEqual(list(members), result.to_dict()["value"])
        self.assertEqual((GROUP_INPUT,), result.input_fields)

    def test_member_product_ids_preserves_present_empty_without_inventing_missing(self) -> None:
        empty = self.calculate_members(identity_input(GROUP_INPUT, ()))
        self.assertIs(CalculationStatus.CALCULATED, empty.status)
        self.assertEqual((), empty.value)
        for presence, expected in (
            (PresenceStatus.MISSING, CalculationStatus.MISSING_INPUT),
            (PresenceStatus.UNKNOWN, CalculationStatus.UNKNOWN_INPUT),
        ):
            with self.subTest(presence=presence):
                result = self.calculate_members(
                    identity_input(GROUP_INPUT, None, presence_status=presence)
                )
                self.assertIs(expected, result.status)
                self.assertIsNone(result.value)

    def test_member_product_ids_rejects_noncanonical_duplicate_or_unordered_members(self) -> None:
        invalid = (
            (PRODUCT_A, PRODUCT_A),
            (PRODUCT_B, PRODUCT_A),
            (PRODUCT_A, ""),
            ("B000000001",),
            ("product:us:B000000001",),
            ("product::B000000001",),
            ("product:US:not-an-asin",),
            "not-a-collection",
        )
        for members in invalid:
            with self.subTest(members=members):
                result = self.calculate_members(identity_input(GROUP_INPUT, members))
                self.assertIs(CalculationStatus.FAILED, result.status)
                self.assertIsNone(result.value)
                self.assertEqual("CALCULATION_FAILED", result.issues[0].code)

    def test_member_product_ids_requires_clean_resolved_canonical_input(self) -> None:
        cases = (
            ({"normalization_status": NormalizationStatus.FAILED}, CalculationStatus.INVALID_INPUT),
            ({"semantic_status": SemanticStatus.SEMANTICS_UNCONFIRMED}, CalculationStatus.INVALID_INPUT),
            ({"resolution_status": InputResolutionStatus.UNRESOLVED}, CalculationStatus.DEPENDENCY_BLOCKED),
        )
        for changes, expected in cases:
            with self.subTest(changes=changes):
                result = self.calculate_members(
                    identity_input(GROUP_INPUT, (PRODUCT_A,), **changes)
                )
                self.assertIs(expected, result.status)
                self.assertIsNone(result.value)

    def test_member_product_ids_is_provider_neutral_and_retains_all_lineage(self) -> None:
        members = (PRODUCT_A, PRODUCT_B)
        alpha = self.calculate_members(
            identity_input(GROUP_INPUT, members, providers=("provider_alpha",))
        )
        beta = self.calculate_members(
            identity_input(GROUP_INPUT, members, providers=("provider_beta",))
        )
        combined = self.calculate_members(
            identity_input(
                GROUP_INPUT,
                members,
                providers=("provider_alpha", "provider_beta"),
            )
        )
        self.assertEqual(alpha.value, beta.value)
        self.assertEqual(alpha.provenance.output_fingerprint, beta.provenance.output_fingerprint)
        lineage = combined.provenance.input_lineage[0]
        self.assertEqual(
            {"provider_alpha", "provider_beta"},
            {item.provider for item in lineage.provenances},
        )
        self.assertEqual(
            {"raw:provider_alpha:1", "raw:provider_beta:1"},
            {item.transformation.raw_evidence_reference for item in lineage.provenances},
        )

    def test_observed_share_uses_exact_decimal_and_ratio_unit(self) -> None:
        batch = self.calculate_share(
            identity_input(GROUP_INPUT, (PRODUCT_A,)),
            identity_input(SNAPSHOT_INPUT, (PRODUCT_A, PRODUCT_B, PRODUCT_C)),
        )
        result = batch.get(SHARE_FIELD)
        self.assertIs(CalculationStatus.CALCULATED, result.status)
        self.assertEqual(Decimal(1) / Decimal(3), result.value)
        self.assertIsInstance(result.value, Decimal)
        self.assertEqual(RATIO_UNIT, result.unit)
        self.assertEqual(str(Decimal(1) / Decimal(3)), result.to_dict()["value"])
        self.assertEqual(
            {
                "workbook.product_structure.product_count",
                "workbook.market_overview.observed_product_count",
                GROUP_INPUT,
                SNAPSHOT_INPUT,
            },
            set(result.input_fields),
        )

    def test_observed_share_precision_is_independent_of_process_decimal_context(self) -> None:
        group = identity_input(GROUP_INPUT, (PRODUCT_A,))
        snapshot = identity_input(SNAPSHOT_INPUT, (PRODUCT_A, PRODUCT_B, PRODUCT_C))
        expected = self.calculate_share(group, snapshot).get(SHARE_FIELD).value
        with localcontext() as decimal_context:
            decimal_context.prec = 7
            decimal_context.rounding = ROUND_DOWN
            perturbed = self.calculate_share(group, snapshot).get(SHARE_FIELD).value
        self.assertEqual(Decimal("0.3333333333333333333333333333"), expected)
        self.assertEqual(expected, perturbed)

    def test_observed_share_preserves_zero_numerator_with_positive_denominator(self) -> None:
        result = self.calculate_share(
            identity_input(GROUP_INPUT, ()),
            identity_input(SNAPSHOT_INPUT, (PRODUCT_A,)),
        ).get(SHARE_FIELD)
        self.assertIs(CalculationStatus.CALCULATED, result.status)
        self.assertEqual(Decimal(0), result.value)

    def test_observed_share_boundary_ratios_are_exact(self) -> None:
        snapshot = tuple(f"product:US:B{index:09d}" for index in range(1, 11))
        cases = (
            (snapshot[:2], Decimal("0.2")),
            ((), Decimal("0")),
            (snapshot, Decimal("1")),
        )
        for group_members, expected in cases:
            with self.subTest(group_size=len(group_members)):
                result = self.calculate_share(
                    identity_input(GROUP_INPUT, group_members),
                    identity_input(SNAPSHOT_INPUT, snapshot),
                ).get(SHARE_FIELD)
                self.assertIs(CalculationStatus.CALCULATED, result.status)
                self.assertEqual(expected, result.value)

    def test_observed_share_zero_denominator_is_explicit(self) -> None:
        for group_members in ((), (PRODUCT_A,)):
            with self.subTest(group_members=group_members):
                result = self.calculate_share(
                    identity_input(GROUP_INPUT, group_members),
                    identity_input(SNAPSHOT_INPUT, ()),
                ).get(SHARE_FIELD)
                self.assertIs(CalculationStatus.DIVISION_BY_ZERO, result.status)
                self.assertIsNone(result.value)
                self.assertEqual("DIVISION_BY_ZERO", result.issues[0].code)

    def test_observed_share_rejects_cross_marketplace_or_snapshot_scope(self) -> None:
        cases = (
            ((PRODUCT_A,), (PRODUCT_UK_A,)),
            ((PRODUCT_A,), (PRODUCT_B,)),
            ((), tuple(sorted((PRODUCT_A, PRODUCT_UK_A)))),
        )
        for group_members, snapshot_members in cases:
            with self.subTest(group=group_members, snapshot=snapshot_members):
                result = self.calculate_share(
                    identity_input(GROUP_INPUT, group_members),
                    identity_input(SNAPSHOT_INPUT, snapshot_members),
                ).get(SHARE_FIELD)
                self.assertIs(CalculationStatus.FAILED, result.status)
                self.assertIsNone(result.value)
                self.assertEqual("CALCULATION_FAILED", result.issues[0].code)

    def test_observed_share_rejects_group_count_above_observed_set(self) -> None:
        result = self.calculate_share(
            identity_input(GROUP_INPUT, (PRODUCT_A, PRODUCT_B)),
            identity_input(SNAPSHOT_INPUT, (PRODUCT_A,)),
        ).get(SHARE_FIELD)
        self.assertIs(CalculationStatus.FAILED, result.status)
        self.assertIsNone(result.value)
        self.assertEqual("CALCULATION_FAILED", result.issues[0].code)

    def test_observed_share_propagates_calculated_dependency_failure(self) -> None:
        result = self.calculate_share(
            identity_input(GROUP_INPUT, None, presence_status=PresenceStatus.MISSING),
            identity_input(SNAPSHOT_INPUT, (PRODUCT_A,)),
        ).get(SHARE_FIELD)
        self.assertIs(CalculationStatus.DEPENDENCY_BLOCKED, result.status)
        self.assertIsNone(result.value)
        self.assertEqual("CALCULATED_DEPENDENCY_BLOCKED", result.issues[0].code)
        self.assertEqual(
            "workbook.product_structure.product_count",
            result.issues[0].dependency_field,
        )

    def test_observed_share_is_deterministic_and_traces_both_count_results(self) -> None:
        inputs_forward = {
            GROUP_INPUT: identity_input(
                GROUP_INPUT,
                (PRODUCT_A, PRODUCT_B),
                providers=("provider_alpha", "provider_beta"),
            ),
            SNAPSHOT_INPUT: identity_input(
                SNAPSHOT_INPUT,
                (PRODUCT_A, PRODUCT_B, PRODUCT_C),
                providers=("provider_alpha", "provider_beta"),
            ),
        }
        inputs_reverse = {
            SNAPSHOT_INPUT: identity_input(
                SNAPSHOT_INPUT,
                (PRODUCT_A, PRODUCT_B, PRODUCT_C),
                providers=("provider_alpha", "provider_beta"),
                reverse_lineage=True,
            ),
            GROUP_INPUT: identity_input(
                GROUP_INPUT,
                (PRODUCT_A, PRODUCT_B),
                providers=("provider_alpha", "provider_beta"),
                reverse_lineage=True,
            ),
        }
        first = self.engine.calculate((SHARE_FIELD,), inputs_forward, calculation_context())
        second = self.engine.calculate((SHARE_FIELD,), inputs_reverse, calculation_context())
        repeat = self.engine.calculate((SHARE_FIELD,), inputs_forward, calculation_context())
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.to_dict(), repeat.to_dict())
        share = first.get(SHARE_FIELD)
        self.assertEqual(2, len(share.provenance.calculated_dependency_result_ids))
        self.assertEqual(
            {
                first.get("workbook.product_structure.product_count").result_id,
                first.get("workbook.market_overview.observed_product_count").result_id,
            },
            set(share.provenance.calculated_dependency_result_ids),
        )

    def test_member_and_share_share_one_deterministic_dependency_closure(self) -> None:
        batch = self.engine.calculate(
            (MEMBER_FIELD, SHARE_FIELD),
            {
                GROUP_INPUT: identity_input(GROUP_INPUT, (PRODUCT_A, PRODUCT_B)),
                SNAPSHOT_INPUT: identity_input(
                    SNAPSHOT_INPUT, (PRODUCT_A, PRODUCT_B, PRODUCT_C)
                ),
            },
            calculation_context(),
        )
        self.assertEqual((PRODUCT_A, PRODUCT_B), batch.get(MEMBER_FIELD).value)
        self.assertEqual(Decimal(2) / Decimal(3), batch.get(SHARE_FIELD).value)
        self.assertEqual(4, len(batch.results))
        self.assertEqual(4, len({item.field_id for item in batch.results}))

    def test_blocked_fields_remain_unregistered(self) -> None:
        for field_id in D2A_SEMANTICALLY_AMBIGUOUS_FIELD_IDS + D2_CURRENT_DEFERRED_FIELD_IDS:
            with self.subTest(field_id=field_id):
                self.assertIsNone(self.registry.function(field_id))


if __name__ == "__main__":
    unittest.main()
