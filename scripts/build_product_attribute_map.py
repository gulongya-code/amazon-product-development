"""Build Product Attribute Map V1.0 from a local SellerSprite export."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from amazon_product_intelligence.listing_attribute_map import (
    CategoryRulePackError,
    ListingAttributeMapError,
    build_product_attribute_map,
    load_category_rule_pack,
)
from amazon_product_intelligence.sellersprite_import import (
    ImportContext,
    SellerSpriteImportError,
    import_sellersprite_file,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", required=True, help="local SellerSprite .xlsx or UTF-8 .csv"
    )
    parser.add_argument("--rule-pack", required=True)
    parser.add_argument("--marketplace", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--observed-date")
    parser.add_argument("--sheet")
    parser.add_argument(
        "--imported-at",
        help="RFC 3339 timestamp; defaults to current UTC",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="new .json file; existing files are never overwritten",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    imported_at = args.imported_at or datetime.now(
        timezone.utc
    ).isoformat().replace("+00:00", "Z")
    try:
        output = Path(args.output)
        if output.suffix.casefold() != ".json":
            raise ListingAttributeMapError(
                "UNSAFE_OUTPUT_NAME", "output must use a .json suffix"
            )
        resolved_output = output.resolve()
        if resolved_output in {
            Path(args.input).resolve(), Path(args.rule_pack).resolve()
        }:
            raise ListingAttributeMapError(
                "OUTPUT_NOT_ISOLATED",
                "output must be separate from input and rule pack",
            )
        dataset = import_sellersprite_file(
            args.input,
            context=ImportContext(
                marketplace=args.marketplace,
                category=args.category,
                imported_at=imported_at,
                observed_date=args.observed_date,
                sheet_name=args.sheet,
            ),
        )
        rule_pack = load_category_rule_pack(args.rule_pack)
        attribute_map = build_product_attribute_map(
            dataset, rule_pack=rule_pack
        )
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(attribute_map.to_json())
            handle.write("\n")
        summary = {
            "conflict_count": attribute_map.conflict_count,
            "dataset_id": attribute_map.dataset_id,
            "listing_count": attribute_map.listing_count,
            "mapped_listing_count": attribute_map.mapped_listing_count,
            "private_real_listing_replay": "NOT_RUN",
            "review_required_count": attribute_map.review_required_count,
            "rule_pack": (
                f"{attribute_map.rule_pack_id}@"
                f"{attribute_map.rule_pack_version}"
            ),
            "semantic_fingerprint":
                attribute_map.semantic_fingerprint,
            "source_basename": dataset.source_basename,
            "status": "SUCCEEDED",
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except FileExistsError:
        error = "OUTPUT_ALREADY_EXISTS: output file already exists"
    except OSError:
        error = "LOCAL_FILE_IO_FAILED: local file operation failed"
    except (
        CategoryRulePackError,
        ListingAttributeMapError,
        SellerSpriteImportError,
        ValueError,
    ) as exc:
        error = str(exc)
    print(json.dumps(
        {"status": "FAILED", "error": error},
        ensure_ascii=False,
        sort_keys=True,
    ))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
