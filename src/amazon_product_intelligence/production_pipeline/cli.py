"""Non-interactive operator CLI for Production Pipeline V0.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence, TextIO

from amazon_product_intelligence.batch_product_selection import (
    BatchProductSelectionOrchestrator,
    BatchSelectionError,
    BatchStatus,
    parse_batch_request,
)

from .errors import ProductionPipelineError
from .models import (
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunStatus,
    ProviderCreditSemantics,
)
from .orchestrator import ProductionPipelineOrchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amazon-intel")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run one explicit ASIN cohort")
    run.add_argument("--market", required=True)
    run.add_argument("--asin", action="append", default=[])
    run.add_argument("--asin-file", type=Path)
    run.add_argument("--seed-keyword")
    run.add_argument("--provider", default="xiyou")
    run.add_argument("--provider-config-ref", default="environment")
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--run-id")
    run.add_argument("--mode", choices=tuple(item.value for item in ProductionRunMode), default="fixture")
    run.add_argument("--category-name")
    run.add_argument(
        "--resume-from",
        type=Path,
        help="read compatible checkpoints from a prior failed run; output-dir must be fresh",
    )
    batch = subparsers.add_parser(
        "batch", help="run multiple explicit candidate cohorts sequentially"
    )
    batch.add_argument("--batch-file", required=True, type=Path)
    batch.add_argument("--output-dir", required=True, type=Path)
    batch.add_argument(
        "--resume-from",
        type=Path,
        help="read compatible candidate artifacts/checkpoints from an immutable prior batch",
    )
    return parser


def _asin_file(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    return tuple(
        line.strip().upper()
        for line in path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    orchestrator: ProductionPipelineOrchestrator | None = None,
    batch_orchestrator: BatchProductSelectionOrchestrator | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = stdout or sys.stdout
    stderr = stderr or sys.stderr
    try:
        args = build_parser().parse_args(argv)
        if args.command == "batch":
            payload = json.loads(args.batch_file.read_text(encoding="utf-8-sig"))
            request = parse_batch_request(
                payload,
                output_directory=args.output_dir,
                resume_from=args.resume_from,
            )
            result = (batch_orchestrator or BatchProductSelectionOrchestrator()).run(
                request
            )
            stream = stdout if result.status is BatchStatus.SUCCEEDED else stderr
            print(
                f"batch {result.batch_id} {result.status.value.lower()}: "
                f"{result.succeeded_count}/{result.candidate_count} candidates succeeded",
                file=stream,
            )
            for name, path in sorted(result.batch_artifact_paths.items()):
                print(f"{name}: {path}", file=stream)
            credits = (
                "unavailable"
                if result.usage.current_run_observed_credits is None
                else str(result.usage.current_run_observed_credits)
            )
            print(
                f"provider logical operations: {result.usage.total_logical_operations}; "
                f"new transport attempts: {result.usage.new_transport_attempts}; "
                f"checkpoint replayed: {result.usage.checkpoint_replayed_operations}; "
                f"source reused: {result.usage.reused_source_operations}; "
                f"credits: {credits}; {result.usage.credit_semantics}; "
                f"{result.usage.billing_note}",
                file=stream,
            )
            return 0 if result.status is BatchStatus.SUCCEEDED else 1
        asins = tuple(value.strip().upper() for value in args.asin) + _asin_file(args.asin_file)
        request = ProductionRunRequest(
            marketplace=args.market.strip().upper(),
            asins=asins,
            asin_file=args.asin_file,
            seed_keyword=args.seed_keyword,
            provider_preference=args.provider,
            provider_config_reference=args.provider_config_ref,
            output_directory=args.output_dir,
            run_id=args.run_id,
            mode=ProductionRunMode(args.mode),
            category_name=args.category_name,
            resume_from=args.resume_from,
        )
    except (OSError, json.JSONDecodeError, ValueError, ProductionPipelineError) as exc:
        code = (
            exc.code.value
            if isinstance(exc, (ProductionPipelineError, BatchSelectionError))
            else "INVALID_INPUT"
        )
        command = "batch" if "args" in locals() and args.command == "batch" else "run"
        print(f"{command} failed [{code}]: {exc}", file=stderr)
        return 2

    result = (orchestrator or ProductionPipelineOrchestrator()).run(request)
    if result.status is ProductionRunStatus.FAILED:
        error = result.error or {"code": "UNKNOWN", "message": "run failed"}
        print(f"run failed [{error['code']}]: {error['message']}", file=stderr)
        manifest = result.artifact_paths.get("run_manifest")
        if manifest is None:
            print("no artifacts written for this failed run", file=stderr)
        else:
            print(f"manifest: {manifest}", file=stderr)
        return 1

    print(
        f"run {result.run_id} succeeded: "
        f"{result.resolved_asin_count}/{result.requested_asin_count} ASINs",
        file=stdout,
    )
    for name, path in sorted(result.artifact_paths.items()):
        print(f"{name}: {path}", file=stdout)
    if result.provider_summary is not None:
        credits = (
            "unavailable"
            if result.provider_summary.credits is None
            else str(result.provider_summary.credits)
        )
        if result.provider_summary.credit_semantics is ProviderCreditSemantics.FIXTURE_REFERENCE:
            credit_text = f"fixture reference credits: {credits} (not billed)"
        else:
            credit_text = f"live provider-reported credits: {credits}"
        print(
            f"provider operations: {result.provider_summary.operation_count}; "
            f"transport attempts: {result.provider_summary.transport_attempt_count}; "
            f"replayed: {result.provider_summary.replayed_operation_count}; {credit_text}",
            file=stdout,
        )
    return 0


__all__ = ("build_parser", "main")
