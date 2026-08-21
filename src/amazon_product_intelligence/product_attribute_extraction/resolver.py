"""Conservative, evidence-preserving Attribute Conflict Resolver V0.1."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence

from amazon_product_intelligence.contracts import canonical_json, deterministic_id

from .errors import ProductAttributeContractError
from .models import (
    AttributeAssertionStatus,
    AttributeCardinality,
    AttributeDimension,
    AttributeDimensionRegistry,
    AttributeExtractionMethod,
    AttributeResolutionStatus,
    AttributeState,
    CanonicalAttributeAssertion,
    CanonicalAttributeConflict,
    CanonicalAttributeSlot,
)
from .registry import ATTRIBUTE_DIMENSION_REGISTRY_V0_1


ATTRIBUTE_CONFLICT_RESOLVER_VERSION = "attribute-conflict-resolver-v0.1"


class AttributeConflictResolver:
    """Resolve exact agreement and expose disagreement without confidence voting."""

    version = ATTRIBUTE_CONFLICT_RESOLVER_VERSION

    def __init__(self, registry: AttributeDimensionRegistry = ATTRIBUTE_DIMENSION_REGISTRY_V0_1) -> None:
        if not isinstance(registry, AttributeDimensionRegistry):
            raise ProductAttributeContractError("conflict resolver requires AttributeDimensionRegistry")
        self._registry = registry

    def resolve(
        self,
        assertions: Sequence[CanonicalAttributeAssertion],
    ) -> tuple[CanonicalAttributeSlot, ...]:
        if isinstance(assertions, (str, bytes)) or not isinstance(assertions, Sequence):
            raise ProductAttributeContractError("conflict resolver assertions must be a sequence")
        indexed: dict[str, CanonicalAttributeAssertion] = {}
        by_dimension: dict[AttributeDimension, list[CanonicalAttributeAssertion]] = defaultdict(list)
        for item in assertions:
            if not isinstance(item, CanonicalAttributeAssertion):
                raise ProductAttributeContractError("conflict resolver received a wrong assertion type")
            current = indexed.get(item.assertion_id)
            if current is not None and canonical_json(current) != canonical_json(item):
                raise ProductAttributeContractError(f"attribute assertion identity collision: {item.assertion_id}")
            indexed[item.assertion_id] = item
        for item in indexed.values():
            if item.status is AttributeAssertionStatus.REJECTED or item.canonical_value is None:
                continue
            by_dimension[item.canonical_value.dimension].append(item)
        return tuple(
            self._resolve_dimension(definition.dimension, by_dimension.get(definition.dimension, []))
            for definition in self._registry.dimensions
        )

    def _resolve_dimension(
        self,
        dimension: AttributeDimension,
        assertions: list[CanonicalAttributeAssertion],
    ) -> CanonicalAttributeSlot:
        ordered = tuple(sorted(assertions, key=lambda item: item.assertion_id))
        if not ordered:
            return CanonicalAttributeSlot(
                dimension=dimension,
                state=AttributeState.UNKNOWN,
                resolved_value=(),
                assertions=(),
                conflicts=(),
                resolution_status=AttributeResolutionStatus.NOT_REQUIRED,
            )
        confirmed = tuple(
            item for item in ordered if item.status is AttributeAssertionStatus.CONFIRMED
        )
        if not confirmed:
            return CanonicalAttributeSlot(
                dimension=dimension,
                state=AttributeState.AMBIGUOUS,
                resolved_value=(),
                assertions=ordered,
                conflicts=(),
                resolution_status=AttributeResolutionStatus.UNRESOLVED,
            )
        distinct_values = {
            item.canonical_value.value_id: item.canonical_value
            for item in confirmed
            if item.canonical_value is not None
        }
        definition = self._registry.definition_for(dimension)
        reason_code: str | None = None
        description: str | None = None
        if definition.cardinality is AttributeCardinality.SINGLE and len(distinct_values) > 1:
            reason_code = "SINGLE_VALUE_DISAGREEMENT"
            description = "Confirmed assertions publish different values for a single-value dimension."
        elif dimension is AttributeDimension.MATERIAL:
            structured = {
                item.canonical_value.value_id
                for item in confirmed
                if item.extraction_method is AttributeExtractionMethod.EXPLICIT_STRUCTURED
                and item.canonical_value is not None
            }
            textual = {
                item.canonical_value.value_id
                for item in confirmed
                if item.extraction_method is not AttributeExtractionMethod.EXPLICIT_STRUCTURED
                and item.canonical_value is not None
            }
            if structured and textual and not textual <= structured:
                reason_code = "STRUCTURED_TEXT_DISAGREEMENT"
                description = (
                    "Structured and text evidence publish different material values; "
                    "confidence does not override the conflict."
                )
        if reason_code is not None and description is not None:
            conflict_payload = {
                "assertion_ids": tuple(sorted(item.assertion_id for item in confirmed)),
                "reason_code": reason_code,
                "description": description,
            }
            conflict = CanonicalAttributeConflict(
                conflict_id=deterministic_id("attribute-conflict", conflict_payload),
                **conflict_payload,
            )
            return CanonicalAttributeSlot(
                dimension=dimension,
                state=AttributeState.CONFLICTED,
                resolved_value=(),
                assertions=ordered,
                conflicts=(conflict,),
                resolution_status=AttributeResolutionStatus.BLOCKED_BY_CONFLICT,
            )
        return CanonicalAttributeSlot(
            dimension=dimension,
            state=AttributeState.PRESENT,
            resolved_value=tuple(distinct_values.values()),
            assertions=ordered,
            conflicts=(),
            resolution_status=AttributeResolutionStatus.RESOLVED,
        )


__all__ = ("ATTRIBUTE_CONFLICT_RESOLVER_VERSION", "AttributeConflictResolver")
