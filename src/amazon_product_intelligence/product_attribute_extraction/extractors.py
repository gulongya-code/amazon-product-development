"""Deterministic structured and text attribute extractors V0.1."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import re
from typing import Any

from amazon_product_intelligence.contracts import PresenceStatus
from amazon_product_intelligence.product_intelligence import ProductIntelligenceSnapshotV0_1

from ._factory import assertion, canonical_value, confidence, quantity_candidate, source_evidence
from .errors import ProductAttributeContractError
from .models import (
    AllowedAttributeValue,
    AttributeAssertionStatus,
    AttributeConfidenceLevel,
    AttributeDimension,
    AttributeDimensionRegistry,
    AttributeExtractionMethod,
    AttributeValueType,
    CanonicalAttributeAssertion,
)
from .quantity import QuantityCandidate
from .registry import ATTRIBUTE_DIMENSION_REGISTRY_V0_1


STRUCTURED_ATTRIBUTE_EXTRACTOR_VERSION = "structured-attribute-extractor-v0.1"
TITLE_ATTRIBUTE_EXTRACTOR_VERSION = "title-attribute-extractor-v0.1"
BULLET_ATTRIBUTE_EXTRACTOR_VERSION = "bullet-attribute-extractor-v0.1"
DESCRIPTION_ATTRIBUTE_EXTRACTOR_VERSION = "description-attribute-extractor-v0.1"


_CAPACITY_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?P<magnitude>[0-9]+(?:\.[0-9]+)?)\s*"
    r"(?P<unit>fl\.?\s*oz|oz|ml|milliliters?|l|liters?|litres?)\b",
    flags=re.IGNORECASE,
)
_DIMENSION_PATTERN = re.compile(
    r"^\s*(?P<magnitude>[0-9]+(?:\.[0-9]+)?)\s*"
    r"(?P<unit>inch(?:es)?|in|centimeters?|cm)\s*$",
    flags=re.IGNORECASE,
)
_PACKAGE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])(?P<magnitude>[1-9][0-9]*)\s*[- ]?packs?\b", re.IGNORECASE),
    re.compile(r"\bpacks?\s+of\s+(?P<magnitude>[1-9][0-9]*)\b", re.IGNORECASE),
)
_STRUCTURED_QUANTITY_PATTERN = re.compile(
    r"^\s*(?P<magnitude>[0-9]+(?:\.[0-9]+)?)\s*(?P<unit>[A-Za-z. ]+)?\s*$"
)


@dataclass(frozen=True, slots=True)
class ExtractionBatch:
    assertions: tuple[CanonicalAttributeAssertion, ...] = ()
    quantity_candidates: tuple[QuantityCandidate, ...] = ()

    def __post_init__(self) -> None:
        if any(not isinstance(item, CanonicalAttributeAssertion) for item in self.assertions):
            raise ProductAttributeContractError("extraction batch assertions contain a wrong type")
        if any(not isinstance(item, QuantityCandidate) for item in self.quantity_candidates):
            raise ProductAttributeContractError("extraction batch quantities contain a wrong type")
        object.__setattr__(
            self,
            "assertions",
            tuple(sorted(self.assertions, key=lambda item: item.assertion_id)),
        )
        object.__setattr__(
            self,
            "quantity_candidates",
            tuple(sorted(self.quantity_candidates, key=lambda item: item.quantity_candidate_id)),
        )

    @classmethod
    def combine(cls, *batches: ExtractionBatch) -> ExtractionBatch:
        assertions = {
            item.assertion_id: item
            for batch in batches
            for item in batch.assertions
        }
        quantities = {
            item.quantity_candidate_id: item
            for batch in batches
            for item in batch.quantity_candidates
        }
        return cls(tuple(assertions.values()), tuple(quantities.values()))


def _normalized_text(value: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())


def _candidate_texts(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        normalized = _normalized_text(value)
        return (normalized,) if normalized else ()
    if isinstance(value, (tuple, list)):
        return tuple(
            normalized
            for item in value
            if isinstance(item, str) and (normalized := _normalized_text(item))
        )
    return ()


def _alias_matches(
    text: str,
    dimension: AttributeDimension,
    registry: AttributeDimensionRegistry,
) -> tuple[tuple[AllowedAttributeValue, str], ...]:
    definition = registry.definition_for(dimension)
    matches: dict[str, tuple[int, AllowedAttributeValue, str]] = {}
    for allowed in definition.allowed_values:
        for alias in sorted(allowed.aliases, key=len, reverse=True):
            pattern = re.compile(
                rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
                flags=re.IGNORECASE,
            )
            match = pattern.search(text)
            if match is None:
                continue
            current = matches.get(allowed.value_id)
            candidate = (match.start(), allowed, match.group(0))
            if current is None or candidate[0] < current[0]:
                matches[allowed.value_id] = candidate
    return tuple((allowed, raw) for _, allowed, raw in sorted(matches.values(), key=lambda item: item[0]))


def _open_text_assertion(
    *,
    raw: Any,
    normalized_text: str,
    dimension: AttributeDimension,
    evidence,
    extractor_version: str,
    level: AttributeConfidenceLevel,
    basis: str,
) -> CanonicalAttributeAssertion:
    normalized = " ".join(normalized_text.split()).casefold()
    value = canonical_value(
        dimension=dimension,
        value_type=AttributeValueType.TEXT,
        value=normalized,
        display_value=" ".join(normalized_text.split()),
        taxonomy_value_id=None,
    )
    return assertion(
        raw_value=raw,
        normalized_value=normalized,
        canonical=value,
        evidence=evidence,
        method=AttributeExtractionMethod.EXPLICIT_STRUCTURED,
        extractor_version=extractor_version,
        confidence_value=confidence(level, basis),
        status=AttributeAssertionStatus.CONFIRMED,
    )


class StructuredAttributeExtractor:
    """Consume only audited structured ProductFact dimensions."""

    version = STRUCTURED_ATTRIBUTE_EXTRACTOR_VERSION
    _DIMENSION_MAP = {
        "material": AttributeDimension.MATERIAL,
        "size": AttributeDimension.SIZE,
        "color": AttributeDimension.COLOR,
        "capacity": AttributeDimension.CAPACITY,
        "volume": AttributeDimension.CAPACITY,
        "item_capacity": AttributeDimension.CAPACITY,
        "dimension": AttributeDimension.DIMENSION,
        "dimensions": AttributeDimension.DIMENSION,
        "item_dimensions": AttributeDimension.DIMENSION,
        "product_dimensions": AttributeDimension.DIMENSION,
        "quantity": AttributeDimension.PACKAGE_QUANTITY,
        "package_quantity": AttributeDimension.PACKAGE_QUANTITY,
        "number_of_pieces": AttributeDimension.PACKAGE_QUANTITY,
    }

    def __init__(self, registry: AttributeDimensionRegistry = ATTRIBUTE_DIMENSION_REGISTRY_V0_1) -> None:
        if not isinstance(registry, AttributeDimensionRegistry):
            raise ProductAttributeContractError("structured extractor requires AttributeDimensionRegistry")
        self._registry = registry

    def extract(self, snapshot: ProductIntelligenceSnapshotV0_1) -> ExtractionBatch:
        if not isinstance(snapshot, ProductIntelligenceSnapshotV0_1):
            raise ProductAttributeContractError("structured extractor requires Product Intelligence snapshot")
        assertions: list[CanonicalAttributeAssertion] = []
        quantities: list[QuantityCandidate] = []
        for evidence_set in snapshot.product_fact_evidence_sets:
            dimension = self._DIMENSION_MAP.get(evidence_set.dimension.casefold())
            if dimension is None:
                continue
            for candidate in evidence_set.candidates:
                if candidate.presence_status is not PresenceStatus.PRESENT:
                    continue
                evidence = source_evidence(snapshot, evidence_set.subject_product_identity, candidate)
                source_value = candidate.normalized_value
                if source_value is None:
                    source_value = candidate.raw_value
                if dimension in {
                    AttributeDimension.CAPACITY,
                    AttributeDimension.DIMENSION,
                    AttributeDimension.PACKAGE_QUANTITY,
                }:
                    quantity = self._quantity_from_structured(
                        dimension=dimension,
                        source_value=source_value,
                        source_unit=candidate.unit.unit_code if candidate.unit else None,
                        evidence=evidence,
                    )
                    if quantity is not None:
                        quantities.append(quantity)
                    continue
                texts = _candidate_texts(source_value)
                if not texts:
                    continue
                text = texts[0]
                if dimension is AttributeDimension.MATERIAL:
                    matches = _alias_matches(text, dimension, self._registry)
                    if matches:
                        for allowed, raw_match in matches:
                            value = canonical_value(
                                dimension=dimension,
                                value_type=AttributeValueType.TEXT,
                                value=allowed.value_id.removeprefix("material."),
                                display_value=allowed.display_value,
                                taxonomy_value_id=allowed.value_id,
                            )
                            assertions.append(assertion(
                                raw_value=candidate.raw_value,
                                normalized_value=value.value,
                                canonical=value,
                                evidence=evidence,
                                method=AttributeExtractionMethod.EXPLICIT_STRUCTURED,
                                extractor_version=self.version,
                                confidence_value=confidence(
                                    AttributeConfidenceLevel.HIGH,
                                    f"structured material alias matched {raw_match!r}",
                                ),
                                status=AttributeAssertionStatus.CONFIRMED,
                            ))
                    else:
                        assertions.append(_open_text_assertion(
                            raw=candidate.raw_value,
                            normalized_text=text,
                            dimension=dimension,
                            evidence=evidence,
                            extractor_version=self.version,
                            level=AttributeConfidenceLevel.HIGH,
                            basis="explicit structured material value",
                        ))
                else:
                    assertions.append(_open_text_assertion(
                        raw=candidate.raw_value,
                        normalized_text=text,
                        dimension=dimension,
                        evidence=evidence,
                        extractor_version=self.version,
                        level=AttributeConfidenceLevel.HIGH,
                        basis=f"explicit structured {dimension.value} value",
                    ))
        return ExtractionBatch(tuple(assertions), tuple(quantities))

    def _quantity_from_structured(
        self,
        *,
        dimension: AttributeDimension,
        source_value: object,
        source_unit: str | None,
        evidence,
    ) -> QuantityCandidate | None:
        if type(source_value) in {int, float} and not isinstance(source_value, bool):
            magnitude = str(source_value)
            unit = source_unit or ("count" if dimension is AttributeDimension.PACKAGE_QUANTITY else "")
            raw = f"{magnitude} {unit}".strip()
        elif isinstance(source_value, str):
            raw = source_value
            pattern = _DIMENSION_PATTERN if dimension is AttributeDimension.DIMENSION else _STRUCTURED_QUANTITY_PATTERN
            match = pattern.fullmatch(source_value)
            if match is None:
                return None
            magnitude = match.group("magnitude")
            unit = (match.groupdict().get("unit") or source_unit or "").strip()
            if dimension is AttributeDimension.PACKAGE_QUANTITY and not unit:
                unit = "count"
        else:
            return None
        if not unit:
            return None
        return quantity_candidate(
            dimension=dimension,
            raw_value=raw,
            magnitude=magnitude,
            original_unit=unit,
            evidence=evidence,
            method=AttributeExtractionMethod.EXPLICIT_STRUCTURED,
            extractor_version=self.version,
            confidence_value=confidence(
                AttributeConfidenceLevel.HIGH,
                f"explicit structured {dimension.value} quantity",
            ),
        )


class _EvidenceTextExtractor:
    source_dimensions: frozenset[str]
    version: str
    confidence_level: AttributeConfidenceLevel
    include_use_case: bool = False

    def __init__(self, registry: AttributeDimensionRegistry = ATTRIBUTE_DIMENSION_REGISTRY_V0_1) -> None:
        if not isinstance(registry, AttributeDimensionRegistry):
            raise ProductAttributeContractError("text extractor requires AttributeDimensionRegistry")
        self._registry = registry

    def extract(self, snapshot: ProductIntelligenceSnapshotV0_1) -> ExtractionBatch:
        if not isinstance(snapshot, ProductIntelligenceSnapshotV0_1):
            raise ProductAttributeContractError("text extractor requires Product Intelligence snapshot")
        assertions: list[CanonicalAttributeAssertion] = []
        quantities: list[QuantityCandidate] = []
        for evidence_set in snapshot.product_fact_evidence_sets:
            if evidence_set.dimension.casefold() not in self.source_dimensions:
                continue
            for candidate in evidence_set.candidates:
                if candidate.presence_status is not PresenceStatus.PRESENT:
                    continue
                evidence = source_evidence(snapshot, evidence_set.subject_product_identity, candidate)
                text_value = candidate.normalized_value
                if text_value is None:
                    text_value = candidate.raw_value
                for text in _candidate_texts(text_value):
                    assertions.extend(self._taxonomy_assertions(text, evidence, AttributeDimension.MATERIAL))
                    assertions.extend(self._taxonomy_assertions(text, evidence, AttributeDimension.FEATURE))
                    if self.include_use_case:
                        assertions.extend(self._taxonomy_assertions(
                            text,
                            evidence,
                            AttributeDimension.USE_CASE,
                            status=AttributeAssertionStatus.CANDIDATE,
                        ))
                    quantities.extend(self._capacity_candidates(text, evidence))
                    quantities.extend(self._package_candidates(text, evidence))
        return ExtractionBatch(tuple(assertions), tuple(quantities))

    def _taxonomy_assertions(
        self,
        text: str,
        evidence,
        dimension: AttributeDimension,
        *,
        status: AttributeAssertionStatus = AttributeAssertionStatus.CONFIRMED,
    ) -> list[CanonicalAttributeAssertion]:
        result: list[CanonicalAttributeAssertion] = []
        for allowed, raw_match in _alias_matches(text, dimension, self._registry):
            normalized = allowed.value_id.split(".", 1)[1]
            value = canonical_value(
                dimension=dimension,
                value_type=AttributeValueType.TEXT,
                value=normalized,
                display_value=allowed.display_value,
                taxonomy_value_id=allowed.value_id,
            )
            result.append(assertion(
                raw_value=raw_match,
                normalized_value=normalized,
                canonical=value,
                evidence=evidence,
                method=AttributeExtractionMethod.EXPLICIT_TEXT,
                extractor_version=self.version,
                confidence_value=confidence(
                    self.confidence_level,
                    f"exact {dimension.value} alias in {self.version}",
                ),
                status=status,
            ))
        return result

    def _capacity_candidates(self, text: str, evidence) -> list[QuantityCandidate]:
        return [
            quantity_candidate(
                dimension=AttributeDimension.CAPACITY,
                raw_value=match.group(0),
                magnitude=match.group("magnitude"),
                original_unit=match.group("unit"),
                evidence=evidence,
                method=AttributeExtractionMethod.EXPLICIT_TEXT,
                extractor_version=self.version,
                confidence_value=confidence(
                    self.confidence_level,
                    f"bounded capacity pattern in {self.version}; oz means US fluid ounce in V0.1",
                ),
            )
            for match in _CAPACITY_PATTERN.finditer(text)
        ]

    def _package_candidates(self, text: str, evidence) -> list[QuantityCandidate]:
        matches: dict[tuple[int, int], re.Match[str]] = {}
        for pattern in _PACKAGE_PATTERNS:
            for match in pattern.finditer(text):
                matches[(match.start(), match.end())] = match
        return [
            quantity_candidate(
                dimension=AttributeDimension.PACKAGE_QUANTITY,
                raw_value=match.group(0),
                magnitude=match.group("magnitude"),
                original_unit="pack",
                evidence=evidence,
                method=AttributeExtractionMethod.EXPLICIT_TEXT,
                extractor_version=self.version,
                confidence_value=confidence(
                    self.confidence_level,
                    f"bounded package quantity pattern in {self.version}",
                ),
            )
            for _, match in sorted(matches.items())
        ]


class TitleAttributeExtractor(_EvidenceTextExtractor):
    source_dimensions = frozenset({"title"})
    version = TITLE_ATTRIBUTE_EXTRACTOR_VERSION
    confidence_level = AttributeConfidenceLevel.MEDIUM


class BulletAttributeExtractor(_EvidenceTextExtractor):
    source_dimensions = frozenset({"bullet", "bullets", "bullet_point", "bullet_points"})
    version = BULLET_ATTRIBUTE_EXTRACTOR_VERSION
    confidence_level = AttributeConfidenceLevel.MEDIUM
    include_use_case = True


class DescriptionAttributeExtractor(_EvidenceTextExtractor):
    source_dimensions = frozenset({"description"})
    version = DESCRIPTION_ATTRIBUTE_EXTRACTOR_VERSION
    confidence_level = AttributeConfidenceLevel.LOW


__all__ = (
    "STRUCTURED_ATTRIBUTE_EXTRACTOR_VERSION",
    "TITLE_ATTRIBUTE_EXTRACTOR_VERSION",
    "BULLET_ATTRIBUTE_EXTRACTOR_VERSION",
    "DESCRIPTION_ATTRIBUTE_EXTRACTOR_VERSION",
    "ExtractionBatch",
    "StructuredAttributeExtractor",
    "TitleAttributeExtractor",
    "BulletAttributeExtractor",
    "DescriptionAttributeExtractor",
)
