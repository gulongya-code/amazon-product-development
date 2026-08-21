"""Explicit-live command for TASK-SP-032B."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .capture import XiYouLiveCaptureClient
from .pilot import OrganicBuyerNeedDiscoveryPilot
from .report import render_organic_discovery_report
from .runner import CreditApprovalRequired


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="organic-keyword-discovery-v0.1")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--asin-count", type=int, default=20)
    parser.add_argument("--page-size", type=int, default=20)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--credit-gate", type=int, default=30)
    parser.add_argument("--prior-live-request-count", type=int, default=0)
    parser.add_argument("--prior-live-credits-accounted", type=int, default=0)
    parser.add_argument("--prior-live-usage-note")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.live:
        raise SystemExit("--live is required; this runner never performs implicit provider requests")
    pilot = OrganicBuyerNeedDiscoveryPilot(
        XiYouLiveCaptureClient(environment=os.environ),
        baseline_commit=args.baseline_commit,
        asin_count=args.asin_count,
        page_size=args.page_size,
        max_pages=args.max_pages,
        credit_gate=args.credit_gate,
        prior_live_request_count=args.prior_live_request_count,
        prior_live_credits_accounted=args.prior_live_credits_accounted,
        prior_live_usage_note=args.prior_live_usage_note,
    )
    try:
        result = pilot.run()
    except CreditApprovalRequired as exc:
        print(f"TASK-SP-032B BLOCKED — {exc}")
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(render_organic_discovery_report(result), encoding="utf-8")
    args.snapshot.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "run_id": result.run_id,
                "asin_count": len(result.cohort.asins),
                "request_count": result.request_count,
                "known_credits": result.known_credits,
                "unknown_credit_call_count": result.unknown_credit_call_count,
                "raw_relations": result.discovery.corpus.asin_keyword_relation_count,
                "unique_keywords": result.discovery.corpus.unique_keyword_count,
                "classification": result.classification_summary(),
                "cluster_count": len(result.clustering.clusters),
                "success_criteria": dict(result.success_criteria),
                "report": str(args.report),
                "snapshot": str(args.snapshot),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
