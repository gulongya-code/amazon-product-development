"""Provider-neutral production formulas and numeric safety helpers."""

from __future__ import annotations

from decimal import Context, Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from typing import Any, Iterable

from amazon_product_intelligence.contracts import ContractValidationError, Unit, product_id

from .errors import (
    CalculationCurrencyMismatchError,
    CalculationDivisionByZeroError,
    CalculationEvaluationError,
    CalculationUnitMismatchError,
)
from .models import CalculationEvaluationContext, CalculationOutcome


COUNT_UNIT = Unit(dimension="COUNT", unit_code="COUNT", unit_system=None)
RATIO_UNIT = Unit(dimension="RATIO", unit_code="RATIO", unit_system=None)

_OBSERVED_SHARE_PRECISION = 28


def _authoritative_identifier_collection(
    context: CalculationEvaluationContext,
    *,
    formula_name: str,
) -> tuple[str, ...]:
    dependency_ids = tuple(item.field_id for item in context.spec.dependencies)
    if len(dependency_ids) != 1 or tuple(context.values) != dependency_ids:
        raise CalculationEvaluationError(
            f"{formula_name} requires exactly its one declared resolved dependency"
        )
    return _validated_identifier_collection(
        context.values[dependency_ids[0]],
        formula_name=formula_name,
    )


def _validated_identifier_collection(
    members: Any,
    *,
    formula_name: str,
) -> tuple[str, ...]:
    if not isinstance(members, tuple):
        raise CalculationEvaluationError(
            f"{formula_name} dependency must be an authoritative Canonical identity collection"
        )
    if any(type(member) is not str or not member.strip() for member in members):
        raise CalculationEvaluationError(
            f"{formula_name} collection must contain only non-empty canonical identifiers"
        )
    if len(members) != len(set(members)):
        raise CalculationEvaluationError(
            f"{formula_name} collection violates upstream canonical uniqueness"
        )
    if members != tuple(sorted(members)):
        raise CalculationEvaluationError(
            f"{formula_name} collection violates upstream canonical ordering"
        )
    return members


def _canonical_product_identity_marketplaces(
    members: tuple[str, ...],
    *,
    formula_name: str,
) -> frozenset[str]:
    marketplaces: set[str] = set()
    for member in members:
        parts = member.split(":")
        try:
            expected = product_id(parts[1], parts[2]) if len(parts) == 3 else None
        except ContractValidationError as exc:
            raise CalculationEvaluationError(
                f"{formula_name} contains a non-canonical ProductIdentity"
            ) from exc
        if (
            len(parts) != 3
            or parts[0] != "product"
            or not parts[1]
            or expected != member
        ):
            raise CalculationEvaluationError(
                f"{formula_name} contains a non-canonical ProductIdentity"
            )
        marketplaces.add(parts[1])
    return frozenset(marketplaces)


def count_unique_canonical_identifiers(
    context: CalculationEvaluationContext,
) -> CalculationOutcome:
    """Count one authoritative Canonical identity collection without re-deduping it.

    The owning Canonical or governed system-record contract defines member identity,
    scope, validation, ordering, and uniqueness.  This boundary only verifies that
    the resolved dependency is that already-normalized collection.  Rejecting
    duplicates is intentional: silently deduplicating here would create a second
    identity authority in the Calculation layer.
    """

    members = _authoritative_identifier_collection(context, formula_name="count formula")
    return CalculationOutcome(value=len(members), unit=COUNT_UNIT)


def project_member_product_ids(
    context: CalculationEvaluationContext,
) -> CalculationOutcome:
    """Project one authoritative exact-group ProductIdentity collection.

    The Canonical owner has already established identity, group membership,
    uniqueness, and ordering.  This evaluator verifies that every member is the
    deterministic ``product:<MARKETPLACE>:<ASIN>`` identity defined by the
    Canonical contract and returns the collection unchanged.  It never derives
    identity from a title, label, row, provider key, or presentation position.
    """

    members = _authoritative_identifier_collection(
        context,
        formula_name="member product IDs formula",
    )
    _canonical_product_identity_marketplaces(
        members,
        formula_name="member product IDs collection",
    )
    return CalculationOutcome(value=members, unit=None)


def calculate_observed_share(
    context: CalculationEvaluationContext,
) -> CalculationOutcome:
    """Return exact-group count divided by the same-scope observed-set count."""

    expected_dependencies = (
        "workbook.product_structure.product_count",
        "workbook.market_overview.observed_product_count",
        "canonical.group_product_identities",
        "canonical.snapshot_product_identities",
    )
    if (
        tuple(item.field_id for item in context.spec.dependencies) != expected_dependencies
        or tuple(context.values) != expected_dependencies
        or tuple(context.units) != expected_dependencies
    ):
        raise CalculationEvaluationError(
            "observed share requires its exact ordered count and identity-scope dependencies"
        )
    count_dependencies = expected_dependencies[:2]
    identity_dependencies = expected_dependencies[2:]
    if any(context.units[field_id] != COUNT_UNIT for field_id in count_dependencies):
        raise CalculationUnitMismatchError(
            "observed share dependencies must use the canonical count unit"
        )
    if any(context.units[field_id] is not None for field_id in identity_dependencies):
        raise CalculationUnitMismatchError(
            "observed share identity-scope dependencies must not declare a unit"
        )
    numerator = context.values[count_dependencies[0]]
    denominator = context.values[count_dependencies[1]]
    if any(type(value) is not int or value < 0 for value in (numerator, denominator)):
        raise CalculationEvaluationError(
            "observed share dependencies must be non-negative integer counts"
        )
    if denominator == 0:
        raise CalculationDivisionByZeroError("ratio denominator is zero")

    group_members = _validated_identifier_collection(
        context.values[identity_dependencies[0]],
        formula_name="observed share group scope",
    )
    snapshot_members = _validated_identifier_collection(
        context.values[identity_dependencies[1]],
        formula_name="observed share snapshot scope",
    )
    if numerator != len(group_members) or denominator != len(snapshot_members):
        raise CalculationEvaluationError(
            "observed share counts do not match their authoritative identity collections"
        )
    group_marketplaces = _canonical_product_identity_marketplaces(
        group_members,
        formula_name="observed share group scope",
    )
    snapshot_marketplaces = _canonical_product_identity_marketplaces(
        snapshot_members,
        formula_name="observed share snapshot scope",
    )
    if len(group_marketplaces) > 1 or len(snapshot_marketplaces) != 1:
        raise CalculationEvaluationError(
            "observed share requires one explicit marketplace scope"
        )
    if group_marketplaces and group_marketplaces != snapshot_marketplaces:
        raise CalculationEvaluationError(
            "observed share group and snapshot marketplace scopes do not match"
        )
    if not set(group_members).issubset(snapshot_members):
        raise CalculationEvaluationError(
            "observed share group is not contained in the explicit snapshot scope"
        )
    if numerator > denominator:
        raise CalculationEvaluationError(
            "observed share group count cannot exceed the same-scope observed-set count"
        )
    with localcontext(
        Context(prec=_OBSERVED_SHARE_PRECISION, rounding=ROUND_HALF_EVEN)
    ):
        ratio = safe_decimal_ratio(numerator, denominator)
    return CalculationOutcome(value=ratio, unit=RATIO_UNIT)


def decimal_value(value: Any) -> Decimal:
    """Convert an explicit numeric value to a finite Decimal without guessing."""

    if isinstance(value, bool):
        raise CalculationEvaluationError("boolean is not a decimal input")
    try:
        if isinstance(value, Decimal):
            result = value
        elif isinstance(value, int):
            result = Decimal(value)
        elif isinstance(value, float):
            result = Decimal(str(value))
        elif isinstance(value, str) and value.strip():
            result = Decimal(value.strip())
        else:
            raise InvalidOperation
    except (InvalidOperation, ValueError) as exc:
        raise CalculationEvaluationError("input is not a finite decimal") from exc
    if not result.is_finite():
        raise CalculationEvaluationError("input is not a finite decimal")
    return result


def safe_decimal_ratio(numerator: Any, denominator: Any) -> Decimal:
    """Calculate an exact ratio; zero denominator is an explicit domain error."""

    top = decimal_value(numerator)
    bottom = decimal_value(denominator)
    if bottom == 0:
        raise CalculationDivisionByZeroError("ratio denominator is zero")
    return top / bottom


def require_compatible_units(units: Iterable[Unit | None]) -> Unit | None:
    """Return the common unit or fail; no conversion or unit guessing occurs."""

    present = tuple(unit for unit in units if unit is not None)
    if not present:
        return None
    first = present[0]
    if any(unit != first for unit in present[1:]):
        raise CalculationUnitMismatchError("calculation inputs use incompatible units")
    return first


def require_compatible_currencies(units: Iterable[Unit | None]) -> Unit:
    """Require one explicit ISO currency across every monetary input."""

    values = tuple(units)
    if not values or any(unit is None for unit in values):
        raise CalculationCurrencyMismatchError("every monetary input requires a currency")
    if any(unit.dimension != "CURRENCY" or not unit.unit_code for unit in values if unit is not None):
        raise CalculationCurrencyMismatchError("monetary input has no valid currency unit")
    first = values[0]
    if any(unit != first for unit in values[1:]):
        raise CalculationCurrencyMismatchError("calculation inputs use different currencies")
    return first


__all__ = (
    "COUNT_UNIT",
    "RATIO_UNIT",
    "calculate_observed_share",
    "count_unique_canonical_identifiers",
    "decimal_value",
    "project_member_product_ids",
    "require_compatible_currencies",
    "require_compatible_units",
    "safe_decimal_ratio",
)
