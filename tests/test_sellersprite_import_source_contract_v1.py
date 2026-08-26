from __future__ import annotations

import csv
from pathlib import Path

from amazon_product_intelligence.sellersprite_import import ImportContext, import_sellersprite_file


def test_governed_source_type_is_distinct_from_file_format(tmp_path: Path) -> None:
    source = tmp_path / "source.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ASIN", "商品标题", "价格($)", "月销量", "评分"])
        writer.writerow(["SYNTH00001", "title", 10, 1, 4])

    dataset = import_sellersprite_file(
        source,
        context=ImportContext(
            marketplace="US",
            category="synthetic-category",
            imported_at="2026-08-26T12:00:00Z",
        ),
    )

    assert dataset.source_kind == "SELLERSPRITE_MANUAL_IMPORT"
    assert dataset.source_format == "CSV"
    assert dataset.to_dict()["source"]["type"] == "SELLERSPRITE_MANUAL_IMPORT"
    assert dataset.to_dict()["source"]["format"] == "CSV"
