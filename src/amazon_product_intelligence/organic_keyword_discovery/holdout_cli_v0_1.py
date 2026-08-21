"""Explicit TASK-SP-032E live/replay command."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .capture import XiYouLiveCaptureClient
from .holdout_report_v0_1 import render_holdout_report
from .holdout_v0_1 import (
    OrganicHoldoutLiveCaptureV0_1,
    analyze_holdout_checkpoint,
    load_json_object,
)
from .runner import CreditApprovalRequired


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="organic-holdout-100-v0.1")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--pilot-snapshot", type=Path)
    parser.add_argument("--credit-gate", type=int, default=150)
    parser.add_argument("--skip-enrichment", action="store_true")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.live:
        runner = OrganicHoldoutLiveCaptureV0_1(
            XiYouLiveCaptureClient(environment=os.environ),
            baseline_commit=args.baseline_commit,
            checkpoint_path=args.checkpoint,
            include_enrichment=not args.skip_enrichment,
            credit_gate=args.credit_gate,
        )
        try:
            checkpoint = runner.run()
        except CreditApprovalRequired as exc:
            print(f"TASK-SP-032E BLOCKED — {exc}")
            return 2
    else:
        checkpoint = load_json_object(args.checkpoint)
    if checkpoint.get("baseline_commit") != args.baseline_commit:
        raise SystemExit("checkpoint baseline does not match --baseline-commit")

    annotations = load_json_object(args.annotations) if args.annotations else None
    pilot = load_json_object(args.pilot_snapshot) if args.pilot_snapshot else None
    result = analyze_holdout_checkpoint(
        checkpoint,
        annotations=annotations,
        pilot_snapshot=pilot,
    )
    args.analysis.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.analysis.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.report.write_text(render_holdout_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "analysis_id": result["analysis_id"],
                "cohort_count": len(result["cohort"]),
                "request_count": result["credit_audit"]["request_count"],
                "known_credits": result["credit_audit"]["known_credits"],
                "raw_relations": result["corpus"]["raw_relation_count"],
                "unique_keywords": result["corpus"]["unique_keyword_count"],
                "manual_audit_complete": result["success_criteria"]["manual_audit_complete"],
                "generalization_judgement": result["generalization_judgement"],
                "analysis": str(args.analysis),
                "report": str(args.report),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
