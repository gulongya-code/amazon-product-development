"""Isolated CLI for SellerSprite local file import; prints sanitized metadata."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from amazon_product_intelligence.sellersprite_import import (
    ImportContext,
    SellerSpriteImportError,
    import_sellersprite_file,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="local .xlsx or UTF-8 .csv export")
    parser.add_argument("--marketplace", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--observed-date")
    parser.add_argument("--sheet")
    parser.add_argument("--imported-at", help="RFC 3339 timestamp; defaults to current UTC")
    parser.add_argument("--output", help="new governed JSON file; existing files are never overwritten")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    imported_at = args.imported_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    try:
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
        if args.output:
            output = Path(args.output)
            if output.suffix.casefold() != ".json":
                raise SellerSpriteImportError("UNSAFE_OUTPUT_NAME", "output must use a .json suffix")
            with output.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(dataset.to_json())
                handle.write("\n")
        summary = {
            "accepted_listing_count": dataset.accepted_listing_count,
            "dataset_id": dataset.dataset_id,
            "duplicate_row_count": dataset.duplicate_row_count,
            "quarantined_row_count": dataset.quarantined_row_count,
            "rejected_row_count": dataset.rejected_row_count,
            "semantic_fingerprint": dataset.semantic_fingerprint,
            "source_basename": dataset.source_basename,
            "source_row_count": dataset.source_row_count,
        }
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0
    except FileExistsError:
        print(json.dumps({"status": "FAILED", "error": "OUTPUT_ALREADY_EXISTS: output file already exists"}))
        return 2
    except OSError:
        print(json.dumps({"status": "FAILED", "error": "LOCAL_FILE_IO_FAILED: local file operation failed"}))
        return 2
    except (SellerSpriteImportError, ValueError) as exc:
        print(json.dumps({"status": "FAILED", "error": str(exc)}, ensure_ascii=False, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
