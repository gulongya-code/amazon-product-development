"""Listing-grain join of SP-041B market facts and SP-041C attributes."""

from __future__ import annotations

from datetime import date
from hashlib import sha256
from typing import Any

from amazon_product_intelligence.contracts import canonical_json, deterministic_id
from amazon_product_intelligence.listing_attribute_map.models import (
    AttributeSlotStatus,
    ProductAttributeMapV1,
)
from amazon_product_intelligence.market_report.v0_2.models.common import Availability
from amazon_product_intelligence.normalization.models import json_value
from amazon_product_intelligence.sellersprite_import.models import (
    GovernedMarketDatasetV1,
    ImportValueStatus,
    ListingRecordV1,
)

from .config import RouteDiscoveryConfig, validate_category
from .errors import ProductRouteOpportunityError
from .models import ProductMapField, ProductMapRecord, RouteAttribute


_FIELD_HEADERS = {
    "monthly_sales": "\u6708\u9500\u91cf",
    "monthly_revenue_usd": "\u6708\u9500\u552e\u989d($)",
    "price_usd": "\u4ef7\u683c($)",
    "rating": "\u8bc4\u5206",
    "review_count": "\u8bc4\u5206\u6570",
    "listing_date": "\u4e0a\u67b6\u65f6\u95f4",
    "listing_age_days": "\u4e0a\u67b6\u5929\u6570",
    "brand": "\u54c1\u724c",
    "seller": "BuyBox\u5356\u5bb6",
    "mom_growth": "\u9500\u91cf\u73af\u6bd4\u589e\u957f\u7387",
    "yoy_growth": "\u9500\u91cf\u540c\u6bd4\u589e\u957f\u7387",
    "category_rank": "\u5927\u7c7bBSR",
    "subcategory_rank": "\u5c0f\u7c7bBSR",
}


def _hash(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _field(record: ListingRecordV1, name: str, header: str) -> ProductMapField:
    source = next((item for item in record.fields if item.header == header), None)
    available = (
        source is not None
        and source.import_status is ImportValueStatus.NORMALIZED
        and source.value is not None
    )
    material = {
        "name": name, "header": header, "record": record.record_fingerprint,
        "status": None if source is None else source.import_status.value,
        "value": None if not available else json_value(source.value),
    }
    return ProductMapField(
        field_id=deterministic_id("product-map-field", material),
        name=name,
        source_header=header,
        availability=Availability.AVAILABLE if available else Availability.UNAVAILABLE,
        value=None if not available else json_value(source.value),
        evidence_semantics=(
            "UNKNOWN" if source is None else source.evidence_semantics.value
        ),
        upstream_record_fingerprint=record.record_fingerprint,
        issue_codes=() if source is None else tuple(sorted(source.issue_codes)),
    )


def _age_from_date(
    fields: list[ProductMapField], observed_date: str | None
) -> ProductMapField | None:
    age = next(item for item in fields if item.name == "listing_age_days")
    listing_date = next(item for item in fields if item.name == "listing_date")
    if age.availability is Availability.AVAILABLE:
        return None
    if listing_date.availability is Availability.UNAVAILABLE or observed_date is None:
        return None
    try:
        days = (date.fromisoformat(observed_date) - date.fromisoformat(str(listing_date.value))).days
    except (TypeError, ValueError):
        return None
    if days < 0:
        return None
    material = {
        "name": "listing_age_days", "method": "OBSERVED_DATE_MINUS_LISTING_DATE",
        "listing_date_field_id": listing_date.field_id, "observed_date": observed_date,
        "value": days,
    }
    return ProductMapField(
        field_id=deterministic_id("product-map-field", material),
        name="listing_age_days", source_header="\u4e0a\u67b6\u65f6\u95f4",
        availability=Availability.AVAILABLE, value=days,
        evidence_semantics="DERIVED_RULE",
        upstream_record_fingerprint=listing_date.upstream_record_fingerprint,
        issue_codes=("DERIVED_FROM_LISTING_DATE_AND_OBSERVED_DATE",),
    )


def build_product_map_records(
    dataset: GovernedMarketDatasetV1,
    attribute_map: ProductAttributeMapV1,
    *,
    config: RouteDiscoveryConfig,
) -> tuple[ProductMapRecord, ...]:
    """Join accepted upstream contracts without parent collapse or guessed values."""

    validate_category(config, dataset.category)
    if attribute_map.upstream_dataset_id != dataset.dataset_id:
        raise ProductRouteOpportunityError(
            "UPSTREAM_ID_MISMATCH", "attribute map does not reference the governed dataset"
        )
    if attribute_map.upstream_semantic_fingerprint != dataset.semantic_fingerprint:
        raise ProductRouteOpportunityError(
            "UPSTREAM_FINGERPRINT_MISMATCH", "attribute map fingerprint link is invalid"
        )
    listings = {item.asin: item for item in dataset.records}
    attributes = {item.asin: item for item in attribute_map.records}
    if set(listings) != set(attributes):
        raise ProductRouteOpportunityError(
            "LISTING_GRAIN_JOIN_MISMATCH", "SP-041B and SP-041C listing sets differ"
        )

    result: list[ProductMapRecord] = []
    for asin in sorted(listings):
        listing = listings[asin]
        mapped = attributes[asin]
        fields = [_field(listing, name, header) for name, header in _FIELD_HEADERS.items()]
        replacement = _age_from_date(fields, dataset.observed_date)
        if replacement is not None:
            fields = [replacement if item.name == "listing_age_days" else item for item in fields]

        route_attributes = tuple(
            RouteAttribute(
                dimension=slot.dimension,
                status=slot.status.value,
                values=tuple(json_value(value.value) for value in slot.values),
                evidence_ids=tuple(sorted({
                    evidence_id for value in slot.values for evidence_id in value.evidence_ids
                })),
                conflict_ids=tuple(sorted(item.conflict_id for item in slot.conflicts)),
                limitations=tuple(sorted(slot.limitations)),
            )
            for slot in sorted(mapped.attributes, key=lambda item: item.dimension)
        )
        age_field = next(item for item in fields if item.name == "listing_age_days")
        new_flag = None
        if age_field.availability is Availability.AVAILABLE:
            new_flag = int(age_field.value) <= config.new_product_max_age_days
        limitations = list(mapped.record_limitations)
        if mapped.conflict_count:
            limitations.append("UPSTREAM_ATTRIBUTE_CONFLICTS_PRESERVED")
        if new_flag is None:
            limitations.append("NEW_PRODUCT_FLAG_UNAVAILABLE_MISSING_AGE")
        parent_evidence_id = deterministic_id(
            "product-map-parent-evidence",
            {"record": listing.record_fingerprint, "parent_asin": listing.parent_asin},
        )
        logical = {
            "asin": asin, "parent_asin": listing.parent_asin,
            "parent_evidence_id": parent_evidence_id,
            "upstream_listing_fingerprint": listing.record_fingerprint,
            "attribute_record_id": mapped.record_id,
            "attribute_record_fingerprint": mapped.semantic_fingerprint,
            "attributes": [item.to_dict() for item in route_attributes],
            "fields": [item.to_dict() for item in sorted(fields, key=lambda item: item.name)],
            "flags": {"is_new_product": new_flag},
            "limitations": sorted(set(limitations)),
        }
        semantic_fingerprint = _hash(logical)
        result.append(ProductMapRecord(
            record_id=deterministic_id("product-map-record", logical),
            semantic_fingerprint=semantic_fingerprint,
            asin=asin, parent_asin=listing.parent_asin,
            parent_evidence_id=parent_evidence_id,
            upstream_listing_fingerprint=listing.record_fingerprint,
            attribute_record_id=mapped.record_id,
            attribute_record_fingerprint=mapped.semantic_fingerprint,
            attributes=route_attributes,
            fields=tuple(sorted(fields, key=lambda item: item.name)),
            flags=(("is_new_product", new_flag),),
            limitations=tuple(sorted(set(limitations))),
        ))
    return tuple(result)


def structural_signature(
    record: ProductMapRecord, config: RouteDiscoveryConfig
) -> tuple[tuple[str, str], ...] | None:
    """Return known structural signals only; missing slots never become equality."""

    signature: list[tuple[str, str]] = []
    for dimension in config.core_dimensions:
        attribute = record.attribute(dimension)
        if attribute.status != AttributeSlotStatus.AVAILABLE.value or not attribute.values:
            continue
        value_key = canonical_json(sorted(
            (json_value(item) for item in attribute.values),
            key=canonical_json,
        ))
        signature.append((dimension, value_key))
    if len(signature) < config.min_known_core_dimensions:
        return None
    return tuple(signature)


__all__ = ("build_product_map_records", "structural_signature")
