"""Two real governed runs, downstream report analysis and private-only delivery."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from amazon_product_intelligence.contracts import canonical_json
from amazon_product_intelligence.market_report.integrated import run_final_market_intelligence
from amazon_product_intelligence.market_report.v0_3 import ReportEvidenceContext, ReportProfile, build_operator_market_report, load_report_profile
from amazon_product_intelligence.market_report.v0_3.delivery import deliver
from amazon_product_intelligence.market_report.v0_3.presentation import markdown, workbook_spec
from amazon_product_intelligence.route_discovery_input import RouteDiscoveryInputContext
from amazon_product_intelligence.route_discovery_v2 import load_route_discovery_v2_config
from amazon_product_intelligence.semantic_engine_v2 import load_category_semantic_profile
from amazon_product_intelligence.sellersprite_import import ImportContext, build_sellersprite_canonical_evidence, import_sellersprite_file


def outside(path, repository):
    path = Path(path).resolve()
    if path == repository or repository in path.parents:
        raise ValueError("private input/output must be outside Git repository")
    return path


def run(args):
    repo = Path(__file__).resolve().parents[1]
    output = outside(args.output_root, repo)
    manifest_path = outside(args.manifest, repo)
    entries = json.loads(manifest_path.read_text(encoding="utf-8"))["categories"]
    if len({e["category_key"] for e in entries}) != len(entries):
        raise ValueError("duplicate categories")
    output.mkdir(parents=True, exist_ok=True)
    summaries = []
    for entry in entries:
        key = entry["category_key"]
        if not re.fullmatch(r"[A-Z0-9_]+", key):
            raise ValueError("unsafe category output key")
        raw = import_sellersprite_file(outside(entry["input"], repo), context=ImportContext(marketplace=entry["marketplace"], category=entry["category"], imported_at=entry["imported_at"], observed_date=entry["observed_date"], sheet_name=entry["sheet"]))
        canonical = build_sellersprite_canonical_evidence(raw)
        context = RouteDiscoveryInputContext(marketplace=entry["marketplace"], category=entry["category"], imported_at=entry["imported_at"], normalization_run_id=f"sp-043a:{key.casefold()}", normalized_at=entry["imported_at"], observed_date=entry["observed_date"])
        policy_path = repo / "config" / "market_report" / (Path(entry["route_config"]).stem.split(".")[0] + ".v0_3.json")
        policy = load_report_profile(policy_path) if policy_path.exists() else ReportProfile()
        runs = []
        for number in (1, 2):
            print(f"{key}: governed generation {number}/2", flush=True)
            integrated = run_final_market_intelligence(canonical_bundles=(canonical,), input_context=context, semantic_profile=load_category_semantic_profile(repo / entry["profile"]), route_config=load_route_discovery_v2_config(repo / entry["route_config"]), generated_at=entry["generated_at"])
            report = build_operator_market_report(integrated, profile=policy, evidence_context=ReportEvidenceContext(**entry.get("report_evidence_context", {})))
            runs.append(report)
        if runs[0].to_json() != runs[1].to_json():
            raise ValueError("report generation is nondeterministic")
        report = runs[0]
        data = report.to_dict()
        checks = {"report_json": True}
        for field in ("families", "routes", "mechanism_groups"):
            checks[field] = runs[0].to_dict()[field] == runs[1].to_dict()[field]
        for field in ("price_bands", "review_bands", "new_products"):
            checks[field] = [r[field] for r in runs[0].to_dict()["routes"]] == [r[field] for r in runs[1].to_dict()["routes"]]
        for locale in ("zh-CN", "en-US"):
            checks[locale + "_markdown"] = markdown(runs[0], locale) == markdown(runs[1], locale)
        category_dir = outside(output / key, repo)
        print(f"{key}: render and round-trip verify", flush=True)
        first = deliver(report, category_dir, node_executable=args.node, renderer_runtime=args.renderer_runtime, qa_directory=output / "qa" / key)
        with TemporaryDirectory(prefix="determinism-", dir=output) as temporary:
            second = deliver(runs[1], temporary, node_executable=args.node, renderer_runtime=args.renderer_runtime)
        for field in ("json_sha256", "markdown_sha256", "workbook_content_sha256", "spec_sha256"):
            checks[field] = first[field] == second[field]
        if not all(checks.values()):
            raise ValueError("report delivery determinism failed")
        (category_dir / "operator_market_report_en_us.md").write_text(markdown(report, "en-US"), encoding="utf-8", newline="\n")
        summaries.append({"category_key": key, "counts": data["coverage_counts"], "route_count": len(data["routes"]), "family_count": len(data["families"]), "source_lineage": data["source_lineage"], "report_fingerprint": report.semantic_fingerprint, "decision_readiness": data["decision_readiness"], "checks": checks, "delivery": first, "raw_xlsx_equal": first["workbook_raw_sha256"] == second["workbook_raw_sha256"]})
        (output / "SP_043B_PRIVATE_REPORT_MANIFEST.json").write_text(json.dumps({"categories": summaries}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{key}: complete; {len(data['routes'])} Routes / {len(data['families'])} families", flush=True)
    return summaries


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--node", required=True, type=Path)
    parser.add_argument("--renderer-runtime", required=True, type=Path)
    run(parser.parse_args())
