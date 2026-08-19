from __future__ import annotations

import json

from amazon_product_intelligence.adapters import SorftimeAdapter, XiyouAdapter
from amazon_product_intelligence.normalization import KeywordNormalizer, ProductNormalizer
from amazon_product_intelligence.schemas import (
    CanonicalFieldStatus,
    EntityType,
    P0_FIELD_MAPPINGS,
    mappings_for,
)


def snapshot(
    source: str,
    operation: str,
    payload,
    *,
    snapshot_id: str = "snapshot-001",
    currency: str | None = "USD",
):
    metadata = {"operation": operation}
    if currency is not None:
        metadata["currency"] = currency
    return {
        "source": source,
        "snapshot_id": snapshot_id,
        "timestamp": "2026-08-19T02:03:04Z",
        "request_metadata": metadata,
        "payload": payload,
    }


def test_mock_sorftime_snapshot_maps_and_normalizes_product_p0_fields() -> None:
    raw = snapshot(
        "sorftime",
        "product_detail",
        {
            "data": {
                "asin": " b0g2vv4rbw ",
                "title": "  Stainless\t Steel   Valve  ",
                "category": "  Ball   Valves ",
                "brand": "  Acme  ",
                "price": "$39.99",
                "review_count": "1.5K",
                "star_rating": "4.8",
                "estimated_sales": "1.2K",
            }
        },
    )

    mapped = SorftimeAdapter().adapt(raw)
    assert len(mapped) == 1
    assert mapped[0].entity_type is EntityType.PRODUCT
    assert mapped[0].fields["metric.estimated_monthly_sales"].mapping.source_field == "data.estimated_sales"

    canonical = ProductNormalizer().normalize(mapped[0])
    assert canonical.identity == "B0G2VV4RBW"
    assert canonical.fields["product.title"].value == "Stainless Steel Valve"
    assert canonical.fields["metric.price"].value == 39.99
    assert canonical.fields["metric.price"].currency == "USD"
    assert canonical.fields["metric.review_count"].value == 1500
    assert canonical.fields["metric.estimated_monthly_sales"].value == 1200
    assert canonical.fields["metric.bsr"].status is CanonicalFieldStatus.NOT_AVAILABLE


def test_mock_xiyou_snapshot_maps_product_fields_without_network() -> None:
    raw = snapshot(
        "xiyou",
        "asin_info",
        {
            "status": 200,
            "data": {
                "entities": [
                    {
                        "asin": "B0G2VV4RBW",
                        "title": "  Ball   Valve ",
                        "currency": "USD",
                        "price": "18.99",
                        "ratings": "1.5K",
                        "stars": "4.8",
                    }
                ]
            },
        },
    )

    canonical = ProductNormalizer().normalize(XiyouAdapter().adapt(raw)[0])
    assert canonical.fields["product.asin"].value == "B0G2VV4RBW"
    assert canonical.fields["product.title"].value == "Ball Valve"
    assert canonical.fields["metric.price"].value == 18.99
    assert canonical.fields["metric.review_count"].value == 1500
    assert canonical.fields["metric.rating"].value == 4.8
    assert canonical.fields["product.brand"].status is CanonicalFieldStatus.NOT_AVAILABLE
    assert canonical.fields["product.category"].status is CanonicalFieldStatus.PENDING


def test_raw_snapshot_can_be_read_from_snapshot_writer_json_shape(tmp_path) -> None:
    path = tmp_path / "xiyou_keyword.json"
    path.write_text(
        json.dumps(
            snapshot(
                "xiyou",
                "keyword_info",
                {
                    "data": {
                        "list": [
                            {
                                "searchTerm": "  Plastic   SPOONS ",
                                "abaReport": {
                                    "reportFromDate": "2026-08-02",
                                    "reportToDate": "2026-08-08",
                                    "weeklySearchVolume": "41.9K",
                                },
                            }
                        ]
                    }
                },
                currency=None,
            ),
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    mapped = XiyouAdapter().adapt(path)
    canonical = KeywordNormalizer().normalize(mapped[0])

    assert canonical.entity_type is EntityType.KEYWORD
    assert canonical.identity == "plastic spoons"
    assert canonical.fields["keyword.search_volume"].value == 41900
    trend = canonical.fields["keyword.trend"]
    assert trend.status is CanonicalFieldStatus.PENDING
    assert trend.observed_at == "2026-08-08"


def test_field_mapping_registry_has_required_metadata_and_correct_p0_routes() -> None:
    assert len(P0_FIELD_MAPPINGS) == 24
    for mapping in P0_FIELD_MAPPINGS:
        serialized = mapping.to_dict()
        assert set(serialized) == {
            "source",
            "source_field",
            "canonical_field",
            "transform_rule",
            "confidence",
            "notes",
        }
        assert all(serialized.values())

    sorftime_sales = {
        mapping.source_field
        for mapping in mappings_for("sorftime", "product_detail", EntityType.PRODUCT)
        if mapping.canonical_field == "metric.estimated_monthly_sales"
    }
    assert sorftime_sales == {
        "data.monthly_sales_volume",
        "data.estimated_sales",
        "data.sales",
        "data.sale_num",
    }
    xiyou_orders = mappings_for("xiyou", "asin_orders_last_30_days", EntityType.PRODUCT)
    assert any(mapping.canonical_field == "metric.orders" for mapping in xiyou_orders)
    assert all(mapping.canonical_field != "metric.estimated_monthly_sales" for mapping in xiyou_orders)


def test_xiyou_bsr_snapshot_maps_leaf_category_latest_rank_and_date() -> None:
    raw = snapshot(
        "xiyou",
        "asin_bsr_trends",
        {
            "data": {
                "asin": "B0G2VV4RBW",
                "categoryTree": [
                    {"categoryId": "root", "name": "Industrial", "root": True},
                    {"categoryId": "leaf", "name": "Ball Valves", "root": False},
                ],
                "trends": [
                    {"date": "2026-08-18", "values": [{"categoryId": "leaf", "rank": 25}]},
                    {"date": "2026-08-19", "values": [{"categoryId": "leaf", "rank": 24}]},
                ],
            }
        },
    )

    canonical = ProductNormalizer().normalize(XiyouAdapter().adapt(raw)[0])
    assert canonical.fields["product.category"].value == "Ball Valves"
    assert canonical.fields["metric.bsr"].value == 24
    assert canonical.fields["metric.bsr"].observed_at == "2026-08-19"
