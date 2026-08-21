"""Quantity candidates and a deterministic unit-normalization adapter V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Protocol, runtime_checkable

from amazon_product_intelligence.contracts import JsonContract, Unit, deterministic_id

from .errors import ProductAttributeContractError
from .models import (
    AttributeAssertionStatus,
    AttributeConfidence,
    AttributeDimension,
    AttributeExtractionMethod,
    AttributeSourceEvidence,
)


ATTRIBUTE_UNIT_NORMALIZER_VERSION = "attribute-unit-normalizer-v0.1"


def _decimal(text: str, path: str) -> Decimal:
    if type(text) is not str or not text.strip():
        raise ProductAttributeContractError(f"{path} must be non-empty decimal text")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise ProductAttributeContractError(f"{path} must be decimal text") from exc
    if not value.is_finite() or value <= 0:
        raise ProductAttributeContractError(f"{path} must be finite and greater than zero")
    return value


def _text(value: str, path: str) -> None:
    if type(value) is not str or not value.strip():
        raise ProductAttributeContractError(f"{path} must be non-empty text")


def _decimal_text(value: Decimal) -> str:
    rendered = format(value.normalize(), "f")
    return rendered.rstrip("0").rstrip(".") if "." in rendered else rendered


@dataclass(frozen=True, slots=True, kw_only=True)
class QuantityCandidate(JsonContract):
    """Unresolved quantity found in evidence; never a canonical attribute by itself."""

    quantity_candidate_id: str
    dimension: AttributeDimension
    raw_value: str
    magnitude: str
    original_unit: str
    source_evidence: tuple[AttributeSourceEvidence, ...]
    extraction_method: AttributeExtractionMethod
    extractor_version: str
    confidence: AttributeConfidence
    assertion_status: AttributeAssertionStatus

    def __post_init__(self) -> None:
        if self.dimension not in {
            AttributeDimension.CAPACITY,
            AttributeDimension.DIMENSION,
            AttributeDimension.PACKAGE_QUANTITY,
        }:
            raise ProductAttributeContractError("quantity candidate has an unsupported attribute dimension")
        _text(self.raw_value, "QuantityCandidate.raw_value")
        _decimal(self.magnitude, "QuantityCandidate.magnitude")
        _text(self.original_unit, "QuantityCandidate.original_unit")
        _text(self.extractor_version, "QuantityCandidate.extractor_version")
        if not isinstance(self.extraction_method, AttributeExtractionMethod):
            raise ProductAttributeContractError("quantity candidate extraction method is invalid")
        if not isinstance(self.confidence, AttributeConfidence):
            raise ProductAttributeContractError("quantity candidate confidence is invalid")
        if not isinstance(self.assertion_status, AttributeAssertionStatus):
            raise ProductAttributeContractError("quantity candidate assertion status is invalid")
        evidence = tuple(self.source_evidence)
        if not evidence or any(not isinstance(item, AttributeSourceEvidence) for item in evidence):
            raise ProductAttributeContractError("quantity candidates require source evidence")
        if len({item.source_evidence_id for item in evidence}) != len(evidence):
            raise ProductAttributeContractError("quantity candidate source evidence must be unique")
        object.__setattr__(
            self,
            "source_evidence",
            tuple(sorted(evidence, key=lambda item: item.source_evidence_id)),
        )
        material = self.to_dict()
        material.pop("quantity_candidate_id")
        if self.quantity_candidate_id != deterministic_id("quantity-candidate", material):
            raise ProductAttributeContractError("quantity_candidate_id does not match candidate content")


@dataclass(frozen=True, slots=True, kw_only=True)
class NormalizedQuantity(JsonContract):
    """Auditable output from an AttributeUnitNormalizer implementation."""

    normalized_quantity_id: str
    quantity_candidate_id: str
    dimension: AttributeDimension
    original_magnitude: str
    original_unit: str
    canonical_magnitude: int | float
    canonical_magnitude_text: str
    canonical_unit: Unit
    transformations: tuple[str, ...]
    normalizer_version: str

    def __post_init__(self) -> None:
        _text(self.quantity_candidate_id, "NormalizedQuantity.quantity_candidate_id")
        _decimal(self.original_magnitude, "NormalizedQuantity.original_magnitude")
        _text(self.original_unit, "NormalizedQuantity.original_unit")
        if type(self.canonical_magnitude) not in {int, float} or self.canonical_magnitude <= 0:
            raise ProductAttributeContractError("canonical quantity must be a positive JSON number")
        canonical_decimal = _decimal(
            self.canonical_magnitude_text,
            "NormalizedQuantity.canonical_magnitude_text",
        )
        if Decimal(str(self.canonical_magnitude)) != canonical_decimal:
            raise ProductAttributeContractError("canonical numeric and text magnitudes disagree")
        if not isinstance(self.canonical_unit, Unit):
            raise ProductAttributeContractError("normalized quantity requires a canonical Unit")
        transformations = tuple(self.transformations)
        if not transformations or any(type(item) is not str or not item.strip() for item in transformations):
            raise ProductAttributeContractError("normalized quantity requires transformation explanations")
        if len(set(transformations)) != len(transformations):
            raise ProductAttributeContractError("quantity transformations must be unique")
        _text(self.normalizer_version, "NormalizedQuantity.normalizer_version")
        object.__setattr__(self, "transformations", transformations)
        material = self.to_dict()
        material.pop("normalized_quantity_id")
        if self.normalized_quantity_id != deterministic_id("normalized-quantity", material):
            raise ProductAttributeContractError("normalized_quantity_id does not match content")


@runtime_checkable
class AttributeUnitNormalizer(Protocol):
    """Replaceable boundary; third-party parsers cannot publish canonical attributes."""

    version: str

    def normalize(self, candidate: QuantityCandidate) -> NormalizedQuantity | None:
        """Return a supported deterministic conversion or None without guessing."""


class DeterministicAttributeUnitNormalizerV0_1:
    """Small reviewed conversion table for the explicitly approved V0.1 units."""

    version = ATTRIBUTE_UNIT_NORMALIZER_VERSION

    _CAPACITY_FACTORS_L = {
        "ml": Decimal("0.001"),
        "milliliter": Decimal("0.001"),
        "milliliters": Decimal("0.001"),
        "l": Decimal("1"),
        "liter": Decimal("1"),
        "liters": Decimal("1"),
        "litre": Decimal("1"),
        "litres": Decimal("1"),
        "oz": Decimal("0.0295735295625"),
        "fl oz": Decimal("0.0295735295625"),
        "floz": Decimal("0.0295735295625"),
    }
    _DIMENSION_FACTORS_CM = {
        "cm": Decimal("1"),
        "centimeter": Decimal("1"),
        "centimeters": Decimal("1"),
        "in": Decimal("2.54"),
        "inch": Decimal("2.54"),
        "inches": Decimal("2.54"),
    }
    _COUNT_UNITS = {"pack", "count", "unit", "units", "piece", "pieces"}

    def normalize(self, candidate: QuantityCandidate) -> NormalizedQuantity | None:
        if not isinstance(candidate, QuantityCandidate):
            raise ProductAttributeContractError("unit normalizer requires QuantityCandidate")
        magnitude = _decimal(candidate.magnitude, "QuantityCandidate.magnitude")
        unit_key = " ".join(candidate.original_unit.casefold().replace(".", "").split())
        if candidate.dimension is AttributeDimension.CAPACITY:
            factor = self._CAPACITY_FACTORS_L.get(unit_key)
            if factor is None:
                return None
            canonical_decimal = magnitude * factor
            canonical_unit = Unit(dimension="VOLUME", unit_code="L", unit_system="SI")
            transformation = f"multiply_by_{_decimal_text(factor)}_to_liters"
        elif candidate.dimension is AttributeDimension.DIMENSION:
            factor = self._DIMENSION_FACTORS_CM.get(unit_key)
            if factor is None:
                return None
            canonical_decimal = magnitude * factor
            canonical_unit = Unit(dimension="LENGTH", unit_code="cm", unit_system="SI")
            transformation = f"multiply_by_{_decimal_text(factor)}_to_centimeters"
        else:
            if unit_key not in self._COUNT_UNITS or magnitude != magnitude.to_integral_value():
                return None
            canonical_decimal = magnitude
            canonical_unit = Unit(dimension="COUNT", unit_code="COUNT", unit_system="DOMAIN")
            transformation = "validate_positive_integral_package_count"
        canonical_text = _decimal_text(canonical_decimal)
        canonical_number: int | float = (
            int(canonical_decimal)
            if canonical_decimal == canonical_decimal.to_integral_value()
            else float(canonical_text)
        )
        payload = {
            "quantity_candidate_id": candidate.quantity_candidate_id,
            "dimension": candidate.dimension,
            "original_magnitude": candidate.magnitude,
            "original_unit": candidate.original_unit,
            "canonical_magnitude": canonical_number,
            "canonical_magnitude_text": canonical_text,
            "canonical_unit": canonical_unit,
            "transformations": (transformation,),
            "normalizer_version": self.version,
        }
        return NormalizedQuantity(
            normalized_quantity_id=deterministic_id("normalized-quantity", payload),
            **payload,
        )


def quantity_candidate_id(material: dict[str, object]) -> str:
    """Public helper used by reviewed extractors to build a stable candidate id."""

    return deterministic_id("quantity-candidate", material)


__all__ = (
    "ATTRIBUTE_UNIT_NORMALIZER_VERSION",
    "QuantityCandidate",
    "NormalizedQuantity",
    "AttributeUnitNormalizer",
    "DeterministicAttributeUnitNormalizerV0_1",
    "quantity_candidate_id",
)
