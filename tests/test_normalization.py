from __future__ import annotations

import pytest

from amazon_product_intelligence.adapters import SorftimeAdapter, XiyouAdapter
from amazon_product_intelligence.normalization import (
    ProductNormalizer,
    merge_canonical_entities,
    normalize_iso8601,
    normalize_keyword_text,
    normalize_monthly_sales,
    normalize_price,
    normalize_product_text,
    normalize_review_count,
    normalize_search_volume,
)
from amazon_product_intelligence.schemas import (
    CanonicalFieldStatus,
    MappingConfidence,
)


def product_snapshot(source: str, price: str, snapshot_id: str):
    if source == "sorftime":
        operation = "product_detail"
        payload = {
            "data": {
                "asin": "B0G2VV4RBW",
                "title": "Valve",
                "category": "Ball Valves",
                "brand": "Acme",
                "price": price,
                "review_count": "1.5K",
                "star_rating": "4.8",
                "monthly_sales_volume": "1.2K",
            }
        }
    else:
        operation = "asin_info"
        payload = {
            "data": {
                "entities": [
                    {
                        "asin": "B0G2VV4RBW",
                        "title": "Valve",
                        "currency": "USD",
                        "price": price,
                        "ratings": "1.5K",
                        "stars": "4.8",
                    }
                ]
            }
        }
    return {
        "source": source,
        "snapshot_id": snapshot_id,
        "timestamp": "2026-08-19T03:00:00Z",
        "request_metadata": {"operation": operation, "currency": "USD"},
        "payload": payload,
    }


def test_price_review_sales_keyword_and_date_normalizers() -> None:
    assert normalize_price("$39.99", currency="USD") == 39.99
    assert normalize_review_count("1.5K") == 1500
    assert normalize_monthly_sales("1.2K") == 1200
    assert normalize_keyword_text("  Plastic   SPOONS ") == "plastic spoons"
    assert normalize_search_volume("41.9K") == 41900
    assert normalize_iso8601("20260819") == "2026-08-19"
    assert normalize_iso8601("2026-08-19T10:00:00+08:00") == "2026-08-19T10:00:00+08:00"


def test_text_normalization_handles_empty_whitespace_and_control_characters() -> None:
    assert normalize_product_text("  Café\t  Valve\x00 ") == "Café Valve"
    with pytest.raises(ValueError):
        normalize_product_text(" \t ")


@pytest.mark.parametrize("alias", ("sales", "estimated_sales", "sale_num"))
def test_sales_aliases_normalize_to_existing_canonical_monthly_sales_field(alias: str) -> None:
    raw = product_snapshot("sorftime", "$39.99", f"snapshot-{alias}")
    data = raw["payload"]["data"]
    data.pop("monthly_sales_volume")
    data[alias] = "2.5K"

    canonical = ProductNormalizer().normalize(SorftimeAdapter().adapt(raw)[0])
    monthly_sales = canonical.fields["metric.estimated_monthly_sales"]
    assert monthly_sales.value == 2500
    assert monthly_sales.source_field == f"data.{alias}"


def test_missing_statuses_are_distinct_and_not_collapsed_to_not_available() -> None:
    raw = product_snapshot("xiyou", "18.99", "xiyou-missing")
    del raw["payload"]["data"]["entities"][0]["title"]
    canonical = ProductNormalizer().normalize(XiyouAdapter().adapt(raw)[0])

    assert canonical.fields["product.brand"].status is CanonicalFieldStatus.NOT_AVAILABLE
    assert canonical.fields["product.title"].status is CanonicalFieldStatus.UNKNOWN
    assert canonical.fields["product.category"].status is CanonicalFieldStatus.PENDING
    assert canonical.fields["metric.price"].status is CanonicalFieldStatus.PRESENT


def test_source_snapshot_timestamp_confidence_and_currency_survive_normalization() -> None:
    canonical = ProductNormalizer().normalize(
        SorftimeAdapter().adapt(product_snapshot("sorftime", "$39.99", "sorftime-001"))[0]
    )
    price = canonical.fields["metric.price"]

    assert price.value == 39.99
    assert price.source == "sorftime"
    assert price.snapshot_id == "sorftime-001"
    assert price.timestamp == "2026-08-19T03:00:00Z"
    assert price.confidence is MappingConfidence.HIGH
    assert price.currency == "USD"
    assert price.source_field == "data.price"
    assert price.transform_rule == "normalize_price"
    assert price.to_dict()["confidence"] == "high"


def test_conflicting_source_values_are_marked_conflict_with_source_evidence() -> None:
    sorftime = ProductNormalizer().normalize(
        SorftimeAdapter().adapt(product_snapshot("sorftime", "$39.99", "sorftime-001"))[0]
    )
    xiyou = ProductNormalizer().normalize(
        XiyouAdapter().adapt(product_snapshot("xiyou", "41.99", "xiyou-001"))[0]
    )

    merged = merge_canonical_entities(sorftime, xiyou)
    price = merged.fields["metric.price"]

    assert price.status is CanonicalFieldStatus.CONFLICT
    assert price.value is None
    assert price.source == "sorftime|xiyou"
    assert price.snapshot_id == "sorftime-001|xiyou-001"
    assert len(price.quality) == 2


def test_canonical_output_is_never_flattened_to_a_bare_value() -> None:
    canonical = ProductNormalizer().normalize(
        SorftimeAdapter().adapt(product_snapshot("sorftime", "$39.99", "sorftime-001"))[0]
    )
    output = canonical.to_dict()
    monthly_sales = output["fields"]["metric.estimated_monthly_sales"]

    assert monthly_sales == {
        "value": 1200,
        "source": "sorftime",
        "snapshot_id": "sorftime-001",
        "timestamp": "2026-08-19T03:00:00Z",
        "confidence": "medium",
        "status": "PRESENT",
        "currency": None,
        "observed_at": None,
        "source_field": "data.monthly_sales_volume",
        "transform_rule": "normalize_monthly_sales",
        "quality": [],
    }
