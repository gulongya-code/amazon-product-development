"""Build deterministic Semantic Engine V2 facts from a local governed export."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from amazon_product_intelligence.semantic_engine_v2 import (
    SemanticEngineV2Error,
    build_semantic_engine_v2_result,
    load_category_semantic_profile,
)
from amazon_product_intelligence.sellersprite_import import (
    ImportContext,
    SellerSpriteImportError,
    import_sellersprite_file,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="local SellerSprite .xlsx or UTF-8 .csv")
    parser.add_argument("--profile", required=True, help="Category Semantic Profile V1.1 JSON")
    parser.add_argument("--marketplace", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--observed-date")
    parser.add_argument("--sheet")
    parser.add_argument("--imported-at", help="RFC 3339 timestamp; defaults to current UTC")
    parser.add_argument("--output", required=True, help="new isolated JSON; never overwritten")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        output = Path(args.output)
        if output.suffix.casefold() != ".json":
            raise SemanticEngineV2Error("UNSAFE_OUTPUT_NAME", "output must use .json")
        if output.exists():
            raise FileExistsError(output)
        if output.resolve() in {Path(args.input).resolve(), Path(args.profile).resolve()}:
            raise SemanticEngineV2Error("OUTPUT_NOT_ISOLATED", "output must be isolated")
        imported_at = args.imported_at or datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
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
        profile = load_category_semantic_profile(args.profile)
        result = build_semantic_engine_v2_result(dataset, profile=profile)
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(result.to_json())
            handle.write("\n")
        print(json.dumps({
            "status": "SUCCEEDED",
            "result_id": result.result_id,
            "semantic_fingerprint": result.semantic_fingerprint,
            "profile": f"{result.profile_id}@{result.profile_version}",
            "profile_fingerprint": result.profile_fingerprint,
            "listing_count": result.listing_count,
            "review_listing_count": result.review_listing_count,
            "unknown_identity_count": result.unknown_identity_count,
            "network_calls": 0,
            "llm_authoritative_decisions": 0,
        }, ensure_ascii=False, sort_keys=True))
        return 0
    except FileExistsError:
        error = "OUTPUT_ALREADY_EXISTS: output file already exists"
    except OSError:
        error = "LOCAL_FILE_IO_FAILED: local file operation failed"
    except (SemanticEngineV2Error, SellerSpriteImportError, ValueError) as exc:
        error = str(exc)
    print(json.dumps({"status": "FAILED", "error": error}, ensure_ascii=False, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
