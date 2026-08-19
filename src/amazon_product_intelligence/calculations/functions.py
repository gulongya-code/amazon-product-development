"""Provider-neutral production formulas and numeric safety helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from amazon_product_intelligence.contracts import Unit

from .errors import (
    CalculationCurrencyMismatchError,
    CalculationDivisionByZeroError,
    CalculationEvaluationError,
    CalculationUnitMismatchError,
)
from .models import CalculationEvaluationContext, CalculationOutcome


COUNT_UNIT = Unit(dimension="COUNT", unit_code="COUNT", unit_system=None)


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

    dependency_ids = tuple(item.field_id for item in context.spec.dependencies)
    if len(dependency_ids) != 1 or tuple(context.values) != dependency_ids:
        raise CalculationEvaluationError(
            "count formula requires exactly its one declared resolved dependency"
        )
    members = context.values[dependency_ids[0]]
    if not isinstance(members, tuple):
        raise CalculationEvaluationError(
            "count formula dependency must be an authoritative Canonical identity collection"
        )
    if any(type(member) is not str or not member.strip() for member in members):
        raise CalculationEvaluationError(
            "count formula collection must contain only non-empty canonical identifiers"
        )
    if len(members) != len(set(members)):
        raise CalculationEvaluationError(
            "count formula collection violates upstream canonical uniqueness"
        )
    if members != tuple(sorted(members)):
        raise CalculationEvaluationError(
            "count formula collection violates upstream canonical ordering"
        )
    return CalculationOutcome(value=len(members), unit=COUNT_UNIT)


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
    "count_unique_canonical_identifiers",
    "decimal_value",
    "require_compatible_currencies",
    "require_compatible_units",
    "safe_decimal_ratio",
)
