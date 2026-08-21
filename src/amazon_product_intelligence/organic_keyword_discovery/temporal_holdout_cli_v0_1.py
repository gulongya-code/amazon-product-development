"""Explicit TASK-SP-032F live/replay command."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .capture import XiYouLiveCaptureClient
from .holdout_v0_1 import load_json_object
from .runner import CreditApprovalRequired
from .temporal_holdout_report_v0_1 import render_temporal_holdout_report
from .temporal_holdout_v0_1 import (
    InsufficientIndependentAsins,
    OrganicTemporalHoldoutLiveCaptureV0_1,
    analyze_temporal_holdout,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="organic-temporal-holdout-v0.1")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--baseline-commit", required=True)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--sp032e-checkpoint", required=True, type=Path)
    parser.add_argument("--sp032e-analysis", required=True, type=Path)
    parser.add_argument("--sp032e-annotations", type=Path)
    parser.add_argument("--credit-gate", type=int, default=150)
    parser.add_argument("--min-request-interval", type=float, default=1.5)
    return parser


def run(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    sp032e_checkpoint = load_json_object(args.sp032e_checkpoint)
    if args.live:
        retrieved_at = None
        if args.checkpoint.exists():
            retrieved_at = str(load_json_object(args.checkpoint)["retrieved_at"])

        def progress(completed: int, total: int) -> None:
            if completed % 10 == 0 or completed == total:
                print(f"reverse capture progress: {completed}/{total}", flush=True)

        runner = OrganicTemporalHoldoutLiveCaptureV0_1(
            XiYouLiveCaptureClient(environment=os.environ, retrieved_at=retrieved_at),
            baseline_commit=args.baseline_commit,
            checkpoint_path=args.checkpoint,
            sp032e_checkpoint=sp032e_checkpoint,
            credit_gate=args.credit_gate,
            min_request_interval_seconds=args.min_request_interval,
            progress=progress,
        )
        try:
            checkpoint = runner.run()
        except CreditApprovalRequired as exc:
            print(f"TASK-SP-032F BLOCKED — {exc}")
            return 2
        except InsufficientIndependentAsins as exc:
            print(f"TASK-SP-032F BLOCKED — INSUFFICIENT INDEPENDENT ASINS: {exc}")
            return 3
    else:
        checkpoint = load_json_object(args.checkpoint)
    if checkpoint.get("baseline_commit") != args.baseline_commit:
        raise SystemExit("checkpoint baseline does not match --baseline-commit")

    annotations = load_json_object(args.annotations) if args.annotations else None
    result = analyze_temporal_holdout(
        checkpoint,
        annotations=annotations,
        reference_annotations=(
            load_json_object(args.sp032e_annotations)
            if args.sp032e_annotations
            else None
        ),
        sp032e_analysis=load_json_object(args.sp032e_analysis),
    )
    args.analysis.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.analysis.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.report.write_text(render_temporal_holdout_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "analysis_id": result["analysis_id"],
                "cohort_count": len(result["cohort"]),
                "historical_overlap_count": result["historical_overlap_count"],
                "request_count": result["credit_audit"]["request_count"],
                "known_credits": result["credit_audit"]["known_credits"],
                "raw_relations": result["corpus"]["raw_relation_count"],
                "unique_keywords": result["corpus"]["unique_keyword_count"],
                "decision": result["overfit_replication_decision"],
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
