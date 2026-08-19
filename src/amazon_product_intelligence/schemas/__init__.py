"""Shared schemas for provider acquisition boundaries."""

from .api_response import APIResponse
from .canonical_mapping import (
    CanonicalEntity,
    CanonicalFieldMapping,
    CanonicalFieldStatus,
    CanonicalFieldValue,
    EntityType,
    MappedEntity,
    MappedField,
    MappingConfidence,
    P0_FIELD_MAPPINGS,
    P0_KEYWORD_FIELDS,
    P0_PRODUCT_FIELDS,
    mappings_for,
)


__all__ = (
    "APIResponse",
    "CanonicalEntity",
    "CanonicalFieldMapping",
    "CanonicalFieldStatus",
    "CanonicalFieldValue",
    "EntityType",
    "MappedEntity",
    "MappedField",
    "MappingConfidence",
    "P0_FIELD_MAPPINGS",
    "P0_KEYWORD_FIELDS",
    "P0_PRODUCT_FIELDS",
    "mappings_for",
)
