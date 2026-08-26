from __future__ import annotations

import csv
from pathlib import Path

import pytest

from amazon_product_intelligence.sellersprite_import import (
    ImportContext,
    SellerSpriteImportError,
    import_sellersprite_file,
)
from amazon_product_intelligence.sellersprite_import.schema_v1 import MAX_LISTING_ROWS


HEADERS = ["ASIN", "商品标题", "价格($)", "月销量", "评分"]
CONTEXT = ImportContext(
    marketplace="US",
    category="synthetic-category",
    imported_at="2026-08-26T12:00:00Z",
)


def _write(path: Path, rows: list[list[object]], headers: list[str] = HEADERS) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


def test_target_scale_of_1500_rows_is_supported(tmp_path: Path) -> None:
    source = tmp_path / "scale.csv"
    rows = [[f"SYN{i:07d}", "title", "10.25", i, "4.5"] for i in range(MAX_LISTING_ROWS)]
    _write(source, rows)

    dataset = import_sellersprite_file(source, context=CONTEXT)

    assert dataset.source_row_count == MAX_LISTING_ROWS
    assert dataset.accepted_listing_count == MAX_LISTING_ROWS
    assert dataset.unique_asin_count == MAX_LISTING_ROWS


def test_parent_asin_is_relationship_only_and_children_are_not_collapsed(tmp_path: Path) -> None:
    source = tmp_path / "family.csv"
    headers = HEADERS + ["父ASIN"]
    _write(
        source,
        [
            ["SYNTH00001", "child one", 10, 1, 4, "PARENT0001"],
            ["SYNTH00002", "child two", 11, 2, 5, "PARENT0001"],
        ],
        headers,
    )

    dataset = import_sellersprite_file(source, context=CONTEXT)

    assert [(record.asin, record.parent_asin) for record in dataset.records] == [
        ("SYNTH00001", "PARENT0001"),
        ("SYNTH00002", "PARENT0001"),
    ]


def test_header_scan_is_bounded_to_first_20_rows(tmp_path: Path) -> None:
    source = tmp_path / "late-header.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        for index in range(20):
            writer.writerow([f"preamble-{index}"])
        writer.writerow(HEADERS)
        writer.writerow(["SYNTH00001", "title", 10, 1, 4])

    with pytest.raises(SellerSpriteImportError, match="HEADER_SCHEMA_MISMATCH"):
        import_sellersprite_file(source, context=CONTEXT)


def test_nonblank_cells_beyond_header_width_reject_only_that_row(tmp_path: Path) -> None:
    source = tmp_path / "wide.csv"
    _write(
        source,
        [
            ["SYNTH00001", "wide", 10, 1, 4, "unexpected"],
            ["SYNTH00002", "valid", 11, 2, 5],
        ],
    )

    dataset = import_sellersprite_file(source, context=CONTEXT)

    assert [record.asin for record in dataset.records] == ["SYNTH00002"]
    assert dataset.rejected_row_count == 1
    assert dataset.row_outcomes[0].disposition.value == "REJECTED_MALFORMED_ROW"
