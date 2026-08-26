"""Safe exact quantity parsing with Decimal-based canonical units."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re

from .rule_pack import MeasurementScope, QuantityKind


MEASUREMENT_PARSER_VERSION = "measurement-parser-v1.0"
_NUMBER = r"(?:0|[1-9]\d*)(?:\.\d+)?"
_UNIT = r"[a-zA-Z]+(?:\s*oz)?"
_COUNT_BOUNDARIES = ("pocket", "pockets", "tier", "tiers", "shelf", "shelves", "layer", "layers")


@dataclass(frozen=True, slots=True)
class ParsedMeasurement:
    quantity_kind: QuantityKind
    original_text: str
    original_values: tuple[str, ...]
    original_unit: str | None
    canonical_values: tuple[str, ...]
    canonical_unit: str
    scope: MeasurementScope

    def to_dict(self) -> dict[str, object]:
        return {
            "quantity_kind": self.quantity_kind.value,
            "original_text": self.original_text,
            "original_values": list(self.original_values),
            "original_unit": self.original_unit,
            "canonical_values": list(self.canonical_values),
            "canonical_unit": self.canonical_unit,
            "scope": self.scope.value,
        }


@dataclass(frozen=True, slots=True)
class MeasurementParseResult:
    measurement: ParsedMeasurement | None
    issue_code: str | None


def _decimal(value: str) -> Decimal:
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("invalid decimal") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("measurement must be finite and non-negative")
    return result


def _canonical(value: Decimal) -> str:
    result = format(value.normalize(), "f")
    if "." in result:
        result = result.rstrip("0").rstrip(".")
    return "0" if result in {"", "-0"} else result


_LENGTH_FACTORS = {
    "mm": Decimal("0.1"),
    "millimeter": Decimal("0.1"),
    "millimeters": Decimal("0.1"),
    "cm": Decimal("1"),
    "centimeter": Decimal("1"),
    "centimeters": Decimal("1"),
    "m": Decimal("100"),
    "meter": Decimal("100"),
    "meters": Decimal("100"),
    "in": Decimal("2.54"),
    "inch": Decimal("2.54"),
    "inches": Decimal("2.54"),
    "ft": Decimal("30.48"),
    "foot": Decimal("30.48"),
    "feet": Decimal("30.48"),
}
_MASS_FACTORS = {
    "g": Decimal("1"),
    "gram": Decimal("1"),
    "grams": Decimal("1"),
    "kg": Decimal("1000"),
    "kilogram": Decimal("1000"),
    "kilograms": Decimal("1000"),
    "oz": Decimal("28.349523125"),
    "ounce": Decimal("28.349523125"),
    "ounces": Decimal("28.349523125"),
    "lb": Decimal("453.59237"),
    "lbs": Decimal("453.59237"),
    "pound": Decimal("453.59237"),
    "pounds": Decimal("453.59237"),
}
_VOLUME_FACTORS = {
    "ml": Decimal("0.001"),
    "milliliter": Decimal("0.001"),
    "milliliters": Decimal("0.001"),
    "l": Decimal("1"),
    "liter": Decimal("1"),
    "liters": Decimal("1"),
    "fl oz": Decimal("0.0295735295625"),
    "fluid ounce": Decimal("0.0295735295625"),
    "fluid ounces": Decimal("0.0295735295625"),
}


def _single(
    text: str,
    *,
    kind: QuantityKind,
    factors: dict[str, Decimal],
    canonical_unit: str,
    scope: MeasurementScope,
) -> MeasurementParseResult:
    match = re.fullmatch(
        rf"\s*({_NUMBER})\s*({_UNIT})\s*", text, flags=re.IGNORECASE
    )
    if not match:
        return MeasurementParseResult(None, "MEASUREMENT_FORMAT_UNRESOLVED")
    raw_number, raw_unit = match.groups()
    unit = " ".join(raw_unit.casefold().split())
    if kind is QuantityKind.VOLUME and unit in {
        "oz", "ounce", "ounces"
    }:
        return MeasurementParseResult(None, "AMBIGUOUS_OUNCE_UNIT")
    factor = factors.get(unit)
    if factor is None:
        return MeasurementParseResult(None, "UNIT_UNSUPPORTED_OR_AMBIGUOUS")
    canonical = _canonical(_decimal(raw_number) * factor)
    return MeasurementParseResult(
        ParsedMeasurement(
            quantity_kind=kind,
            original_text=" ".join(text.split()),
            original_values=(raw_number,),
            original_unit=unit,
            canonical_values=(canonical,),
            canonical_unit=canonical_unit,
            scope=scope,
        ),
        None,
    )


def _dimensions(
    text: str, scope: MeasurementScope
) -> MeasurementParseResult:
    match = re.fullmatch(
        rf"\s*({_NUMBER})\s*[x?]\s*({_NUMBER})\s*[x?]\s*"
        rf"({_NUMBER})\s*({_UNIT})\s*",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return MeasurementParseResult(None, "DIMENSIONS_FORMAT_UNRESOLVED")
    *numbers, raw_unit = match.groups()
    unit = " ".join(raw_unit.casefold().split())
    factor = _LENGTH_FACTORS.get(unit)
    if factor is None:
        return MeasurementParseResult(None, "UNIT_UNSUPPORTED_OR_AMBIGUOUS")
    canonical = tuple(
        _canonical(_decimal(number) * factor) for number in numbers
    )
    return MeasurementParseResult(
        ParsedMeasurement(
            quantity_kind=QuantityKind.DIMENSIONS,
            original_text=" ".join(text.split()),
            original_values=tuple(numbers),
            original_unit=unit,
            canonical_values=canonical,
            canonical_unit="cm",
            scope=scope,
        ),
        None,
    )


def _count(
    text: str, scope: MeasurementScope, allow_bare_count: bool
) -> MeasurementParseResult:
    normalized = " ".join(text.casefold().split())
    if any(
        re.search(rf"\b{re.escape(term)}\b", normalized)
        for term in _COUNT_BOUNDARIES
    ):
        return MeasurementParseResult(None, "NON_PACK_COUNT_BOUNDARY")
    patterns = (
        rf"({_NUMBER})\s*(?:pack|packs|pk|piece|pieces|pc|pcs|set|sets)",
        rf"(?:pack|set)\s+of\s+({_NUMBER})",
    )
    match = next(
        (
            candidate
            for pattern in patterns
            if (candidate := re.fullmatch(pattern, normalized))
        ),
        None,
    )
    if match is None and allow_bare_count:
        match = re.fullmatch(rf"({_NUMBER})", normalized)
    if match is None:
        return MeasurementParseResult(None, "COUNT_FORMAT_UNRESOLVED")
    raw_number = match.group(1)
    number = _decimal(raw_number)
    if number != number.to_integral_value():
        return MeasurementParseResult(None, "COUNT_NOT_INTEGER")
    canonical = _canonical(number)
    return MeasurementParseResult(
        ParsedMeasurement(
            quantity_kind=QuantityKind.COUNT,
            original_text=" ".join(text.split()),
            original_values=(raw_number,),
            original_unit=None,
            canonical_values=(canonical,),
            canonical_unit="count",
            scope=scope,
        ),
        None,
    )


def parse_measurement(
    text: str,
    *,
    quantity_kind: QuantityKind,
    scope: MeasurementScope,
    allow_bare_count: bool = False,
) -> MeasurementParseResult:
    if not isinstance(text, str) or not text.strip():
        return MeasurementParseResult(None, "MEASUREMENT_BLANK")
    if quantity_kind is QuantityKind.COUNT:
        return _count(text, scope, allow_bare_count)
    if quantity_kind is QuantityKind.DIMENSIONS:
        return _dimensions(text, scope)
    if quantity_kind is QuantityKind.LENGTH:
        return _single(
            text, kind=quantity_kind, factors=_LENGTH_FACTORS,
            canonical_unit="cm", scope=scope,
        )
    if quantity_kind is QuantityKind.MASS:
        return _single(
            text, kind=quantity_kind, factors=_MASS_FACTORS,
            canonical_unit="g", scope=scope,
        )
    return _single(
        text, kind=quantity_kind, factors=_VOLUME_FACTORS,
        canonical_unit="L", scope=scope,
    )


__all__ = (
    "MEASUREMENT_PARSER_VERSION", "MeasurementParseResult",
    "ParsedMeasurement", "parse_measurement",
)
