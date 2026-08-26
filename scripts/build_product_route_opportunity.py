"""Run the local SP-041B -> SP-041C -> SP-041D governed chain."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

from amazon_product_intelligence.listing_attribute_map import (
    CategoryRulePackError,
    ListingAttributeMapError,
    build_product_attribute_map,
    load_category_rule_pack,
)
from amazon_product_intelligence.product_route_opportunity import (
    ProductRouteOpportunityError,
    build_product_route_opportunity,
    load_route_discovery_config,
)
from amazon_product_intelligence.sellersprite_import import (
    ImportContext,
    SellerSpriteImportError,
    import_sellersprite_file,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="local SellerSprite .xlsx or UTF-8 .csv")
    parser.add_argument("--rule-pack", required=True)
    parser.add_argument("--route-config", required=True)
    parser.add_argument("--marketplace", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--observed-date")
    parser.add_argument("--sheet")
    parser.add_argument("--imported-at", help="RFC 3339 timestamp; defaults to current UTC")
    parser.add_argument("--output", help="new .json file; existing files are never overwritten")
    parser.add_argument(
        "--sanitized-replay-only", action="store_true",
        help="run fully in memory and print sanitized acceptance statistics only",
    )
    return parser


def _summary(dataset, attribute_map, result, runtime_seconds: float) -> dict[str, object]:
    availability_counts: dict[str, int] = {}
    coverage: list[float] = []
    for route in result.routes:
        for name, metric in route.metrics:
            key = f"{name}:{metric.availability.value}"
            availability_counts[key] = availability_counts.get(key, 0) + 1
            if metric.coverage is not None:
                coverage.append(metric.coverage)
    return {
        "status": "SUCCEEDED",
        "source_row_count": dataset.source_row_count,
        "accepted_listing_count": dataset.accepted_listing_count,
        "attribute_map": {
            "mapped_count": attribute_map.mapped_listing_count,
            "review_required_count": attribute_map.review_required_count,
            "fingerprint": attribute_map.semantic_fingerprint,
        },
        "membership_counts": {
            "assigned": result.assigned_count,
            "unclassified": result.unclassified_count,
            "review_required": result.review_required_count,
        },
        "route_count": len(result.routes),
        "candidate_count": len(result.candidates),
        "candidate_status": result.candidate_selection_status.value,
        "route_size_distribution": sorted(route.member_count for route in result.routes),
        "metric_availability_counts": dict(sorted(availability_counts.items())),
        "metric_coverage_summary": {
            "count": len(coverage),
            "minimum": min(coverage) if coverage else None,
            "maximum": max(coverage) if coverage else None,
        },
        "dataset_fingerprint": dataset.semantic_fingerprint,
        "route_result_fingerprint": result.semantic_fingerprint,
        "runtime_seconds": round(runtime_seconds, 6),
        "private_values_printed": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    imported_at = args.imported_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    started = perf_counter()
    try:
        if args.sanitized_replay_only and args.output:
            raise ProductRouteOpportunityError(
                "REPLAY_OUTPUT_FORBIDDEN", "sanitized replay cannot persist the detailed result"
            )
        if not args.sanitized_replay_only and not args.output:
            raise ProductRouteOpportunityError(
                "OUTPUT_REQUIRED", "provide --output or --sanitized-replay-only"
            )
        output = Path(args.output) if args.output else None
        if output is not None:
            if output.suffix.casefold() != ".json":
                raise ProductRouteOpportunityError("UNSAFE_OUTPUT_NAME", "output must use .json")
            resolved_output = output.resolve()
            protected = {
                Path(args.input).resolve(), Path(args.rule_pack).resolve(),
                Path(args.route_config).resolve(),
            }
            if resolved_output in protected:
                raise ProductRouteOpportunityError(
                    "OUTPUT_NOT_ISOLATED", "output must be separate from all inputs"
                )
        dataset = import_sellersprite_file(
            args.input,
            context=ImportContext(
                marketplace=args.marketplace, category=args.category,
                imported_at=imported_at, observed_date=args.observed_date,
                sheet_name=args.sheet,
            ),
        )
        attribute_map = build_product_attribute_map(
            dataset, rule_pack=load_category_rule_pack(args.rule_pack)
        )
        result = build_product_route_opportunity(
            dataset, attribute_map,
            config=load_route_discovery_config(args.route_config),
        )
        if output is not None:
            with output.open("x", encoding="utf-8", newline="\n") as handle:
                json.dump(
                    result.to_dict(), handle, ensure_ascii=False, sort_keys=True,
                    separators=(",", ":"), allow_nan=False,
                )
                handle.write("\n")
        print(json.dumps(
            _summary(dataset, attribute_map, result, perf_counter() - started),
            ensure_ascii=False, sort_keys=True,
        ))
        return 0
    except FileExistsError:
        error = "OUTPUT_ALREADY_EXISTS: output file already exists"
    except OSError:
        error = "LOCAL_FILE_IO_FAILED: local file operation failed"
    except (
        CategoryRulePackError, ListingAttributeMapError,
        ProductRouteOpportunityError, SellerSpriteImportError, ValueError,
    ) as exc:
        error = str(exc)
    print(json.dumps({"status": "FAILED", "error": error}, ensure_ascii=False, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
