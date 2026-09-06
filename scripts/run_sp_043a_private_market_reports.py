"""Generate deterministic aggregate SP-043A reports from an external manifest.

Private inputs and outputs are required to remain outside the repository.  This
orchestrator selects the acquisition adapter; the intelligence pipeline itself
receives only Canonical evidence and contains no provider or category branch.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any

from openpyxl import load_workbook

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report.integrated import (
    IntegratedMarketReportDelivery,
    run_final_market_intelligence,
)
from amazon_product_intelligence.route_discovery_input import RouteDiscoveryInputContext
from amazon_product_intelligence.route_discovery_v2 import load_route_discovery_v2_config
from amazon_product_intelligence.semantic_engine_v2 import load_category_semantic_profile
from amazon_product_intelligence.sellersprite_import import (
    ImportContext,
    build_sellersprite_canonical_evidence,
    import_sellersprite_file,
)


_ASIN = re.compile(r"(?<![A-Z0-9])B0[A-Z0-9]{8}(?![A-Z0-9])")


def _outside_repo(path: Path, repo_root: Path, name: str) -> Path:
    resolved = path.resolve(strict=False)
    if resolved == repo_root or repo_root in resolved.parents:
        raise ValueError(f"{name} must remain outside the repository")
    return resolved


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("categories"), list):
        raise ValueError("manifest must contain a categories list")
    entries = payload["categories"]
    required = {
        "category_key", "input", "sheet", "marketplace", "category",
        "observed_date", "imported_at", "generated_at", "profile", "route_config",
    }
    if len(entries) < 2 or any(not isinstance(item, dict) or set(item) < required for item in entries):
        raise ValueError("manifest requires at least two complete category entries")
    keys = [item["category_key"] for item in entries]
    if len(keys) != len(set(keys)):
        raise ValueError("manifest category_key values must be unique")
    return entries


def _validate_human_review_blank(path: Path) -> None:
    workbook = load_workbook(path, read_only=True, data_only=False)
    try:
        sheet = workbook["Business Value Review"]
        questions = [
            row for row in sheet.iter_rows(min_row=5, max_col=3, values_only=True)
            if row[0] is not None
        ]
        if len(questions) != 8:
            raise ValueError("business value review must contain exactly eight questions")
        if any(row[1] is not None or row[2] is not None for row in questions):
            raise ValueError("business value human fields must remain blank")
    finally:
        workbook.close()


def _deliver_twice(report, output_root: Path) -> tuple[Any, dict[str, bool]]:
    delivery = IntegratedMarketReportDelivery()
    with TemporaryDirectory(prefix="sp043a-a-", dir=output_root) as first_dir, TemporaryDirectory(
        prefix="sp043a-b-", dir=output_root
    ) as second_dir:
        first = delivery.deliver(report, Path(first_dir))
        second = delivery.deliver(report, Path(second_dir))
        checks = {
            "report_json": first.json_sha256 == second.json_sha256,
            "markdown": first.markdown_sha256 == second.markdown_sha256,
            "xlsx_ooxml_content": first.xlsx_package_content_sha256 == second.xlsx_package_content_sha256,
            "xlsx_semantic_content": first.xlsx_semantic_sha256 == second.xlsx_semantic_sha256,
            "business_value_review": first.business_value_review_sha256 == second.business_value_review_sha256,
        }
        raw_container_equal = first.xlsx_sha256 == second.xlsx_sha256
    if not all(checks.values()):
        raise ValueError(f"delivery determinism failed: {checks}")
    return delivery, {**checks, "xlsx_raw_container_equal": raw_container_equal}


def run(manifest_path: Path, output_root: Path) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    manifest_path = _outside_repo(manifest_path, repo_root, "manifest")
    output_root = _outside_repo(output_root, repo_root, "output root")
    entries = _load_manifest(manifest_path)
    output_root.mkdir(parents=True, exist_ok=True)
    summaries = []
    for entry in entries:
        input_path = _outside_repo(Path(entry["input"]), repo_root, "private input")
        if not input_path.is_file():
            raise ValueError(f"private input does not exist for {entry['category_key']}")
        profile_path = (repo_root / entry["profile"]).resolve()
        route_config_path = (repo_root / entry["route_config"]).resolve()
        dataset = import_sellersprite_file(
            input_path,
            context=ImportContext(
                marketplace=entry["marketplace"],
                category=entry["category"],
                imported_at=entry["imported_at"],
                observed_date=entry["observed_date"],
                sheet_name=entry["sheet"],
            ),
        )
        canonical = build_sellersprite_canonical_evidence(dataset)
        context = RouteDiscoveryInputContext(
            marketplace=entry["marketplace"],
            category=entry["category"],
            imported_at=entry["imported_at"],
            normalization_run_id=f"sp-043a:{entry['category_key'].casefold()}",
            normalized_at=entry["imported_at"],
            observed_date=entry["observed_date"],
        )
        profile = load_category_semantic_profile(profile_path)
        route_config = load_route_discovery_v2_config(route_config_path)
        run_arguments = dict(
            canonical_bundles=(canonical,),
            input_context=context,
            semantic_profile=profile,
            route_config=route_config,
            generated_at=entry["generated_at"],
        )
        first = run_final_market_intelligence(**run_arguments)
        second = run_final_market_intelligence(**run_arguments)
        pipeline_checks = {
            "semantic_result": first.semantic_result.to_json() == second.semantic_result.to_json(),
            "route_result": first.route_result.to_json() == second.route_result.to_json(),
            "market_report": first.market_report.to_json() == second.market_report.to_json(),
        }
        if not all(pipeline_checks.values()):
            raise ValueError(f"pipeline determinism failed for {entry['category_key']}: {pipeline_checks}")
        delivery, delivery_checks = _deliver_twice(first.market_report, output_root)
        category_directory = output_root / entry["category_key"]
        final = delivery.deliver(first.market_report, category_directory)
        _validate_human_review_blank(final.xlsx_path)
        aggregate_text = final.json_path.read_text(encoding="utf-8") + final.markdown_path.read_text(encoding="utf-8")
        if _ASIN.search(aggregate_text.upper()):
            raise ValueError("listing-grain ASIN leaked into aggregate report outputs")
        route_result = first.route_result
        overview = first.market_report.market_overview
        summaries.append({
            "category_key": entry["category_key"],
            "category": entry["category"],
            "marketplace": entry["marketplace"],
            "counts": {
                "accepted": route_result.listing_count,
                "primary_cohort": route_result.primary_cohort_eligible_count,
                "assigned": route_result.assigned_count,
                "unclassified": route_result.unclassified_count,
                "review_required": route_result.review_required_count,
                "routes": len(route_result.routes),
                "candidates": len(route_result.candidates),
            },
            "market_metrics": {
                "monthly_sales": overview["monthly_sales"],
                "monthly_revenue": overview["monthly_revenue"],
                "median_price": overview["price_distribution"],
                "median_reviews": overview["review_count_distribution"],
            },
            "fingerprints": {
                "governed_dataset": first.route_input.dataset.semantic_fingerprint,
                "route_input": first.route_input.semantic_fingerprint,
                "semantic_result": first.semantic_result.semantic_fingerprint,
                "semantic_profile": first.semantic_result.profile_fingerprint,
                "route_result": first.route_result.semantic_fingerprint,
                "route_config": first.route_result.route_config_fingerprint,
                "market_report": first.market_report.semantic_fingerprint,
                "report_json_sha256": final.json_sha256,
                "markdown_sha256": final.markdown_sha256,
                "xlsx_sha256": final.xlsx_sha256,
                "xlsx_ooxml_content_sha256": final.xlsx_package_content_sha256,
                "xlsx_semantic_sha256": final.xlsx_semantic_sha256,
                "business_value_review_sha256": final.business_value_review_sha256,
            },
            "determinism": {**pipeline_checks, **delivery_checks},
            "buyer_need_availability": first.market_report.buyer_needs["availability"],
            "business_value_human_review": "PENDING",
            "output_files": [
                final.json_path.name,
                final.markdown_path.name,
                final.xlsx_path.name,
                final.business_value_review_path.name,
            ],
        })
    payload = {
        "task": "SP-043A",
        "technical_generation_status": "PASS",
        "business_value_human_review": "PENDING",
        "categories": summaries,
    }
    payload["manifest_semantic_fingerprint"] = sha256(
        canonical_json(payload).encode("utf-8")
    ).hexdigest()
    destination = output_root / "SP_043A_PRIVATE_REPORT_MANIFEST.json"
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, allow_nan=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(destination)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    arguments = parser.parse_args()
    result = run(arguments.manifest, arguments.output_root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
