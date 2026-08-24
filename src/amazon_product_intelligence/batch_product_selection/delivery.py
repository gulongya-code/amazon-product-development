"""Deterministic aggregate JSON, XLSX, and Markdown delivery."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import zipfile

from amazon_product_intelligence.market_report.delivery.excel_renderer import (
    ExcelReportRenderer,
    OperatorReportExcelError,
)
from amazon_product_intelligence.production_pipeline.artifacts import write_json_atomic

from .errors import BatchSelectionError, BatchSelectionErrorCode
from .models import BatchCandidateSummary, BatchSelectionResult


BATCH_JSON_FILENAME = "batch_selection_result.json"
BATCH_XLSX_FILENAME = "batch_selection_summary.xlsx"
BATCH_MARKDOWN_FILENAME = "batch_selection_summary.md"


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _display(value: object) -> str:
    if value is None:
        return "null / UNAVAILABLE"
    if isinstance(value, dict):
        if isinstance(value.get("share"), (int, float)):
            return f"{float(value['share']):.1%} ASIN coverage"
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return str(value)


def _candidate_action(candidate: BatchCandidateSummary) -> str:
    return candidate.operator_action or "UNAVAILABLE — candidate failed"


def _opportunity(candidate: BatchCandidateSummary) -> str:
    status = candidate.opportunity_score_status or "UNAVAILABLE"
    value = "null" if candidate.opportunity_score_value is None else str(
        candidate.opportunity_score_value
    )
    return f"{status}; value={value}"


def _recovery_guidance(candidate: BatchCandidateSummary) -> str:
    if candidate.recovery_disposition.value == "CHECKPOINT_RESUME_AVAILABLE":
        return "Checkpoint resume available; use batch --resume-from with this immutable source batch."
    if candidate.recovery_disposition.value == "FRESH_EXECUTION_REQUIRED":
        return (
            "No safe checkpoint is available; candidate will require a fresh execution "
            "in the next compatible batch run."
        )
    return "No recovery action is required."


class BatchSummaryMarkdownRenderer:
    def render(self, result: BatchSelectionResult) -> str:
        action_counts = Counter(_candidate_action(item) for item in result.candidates)
        gaps = Counter(
            str(gap.get("label", "UNAVAILABLE"))
            for candidate in result.candidates
            for gap in candidate.top_missing_evidence
        )
        lines = [
            "# Batch Operator Brief",
            "",
            "| Field | Value |",
            "|---|---|",
            f"| Batch status | **{result.status.value}** |",
            f"| Candidates | {result.candidate_count} total; {result.succeeded_count} succeeded; {result.failed_count} failed |",
            f"| Ranking | **{result.ranking_status}** — deterministic candidate-ID order is workflow organization, not opportunity attractiveness |",
            f"| Provider usage | logical={result.usage.total_logical_operations}; new attempts={result.usage.new_transport_attempts}; executed={result.usage.executed_operations}; checkpoint replayed={result.usage.checkpoint_replayed_operations}; source reused={result.usage.reused_source_operations} |",
            f"| Credits | {_display(result.usage.current_run_observed_credits)}; `{result.usage.credit_semantics}`; {result.usage.billing_note} |",
            f"| Semantic fingerprint | `{result.semantic_fingerprint}` |",
            "",
            "## Action Distribution",
            "",
        ]
        lines.extend(
            f"- `{action}`: {count} candidate(s)"
            for action, count in sorted(action_counts.items())
        )
        lines.extend(("", "## Candidates by Operator Action", ""))
        for action, grouped in sorted(
            (
                action,
                tuple(
                    item.candidate_id
                    for item in result.candidates
                    if _candidate_action(item) == action
                ),
            )
            for action in action_counts
        ):
            lines.append(f"- `{action}`: {', '.join(grouped)}")
        lines.extend(("", "## Shared Evidence Gaps", ""))
        if gaps:
            lines.extend(
                f"- {label}: {count} candidate(s)"
                for label, count in sorted(gaps.items(), key=lambda item: (-item[1], item[0]))
            )
        else:
            lines.append("- No shared evidence gap can be established from completed candidates.")
        failures = tuple(
            item for item in result.candidates if item.production_run_status == "FAILED"
        )
        lines.extend(("", "## Failures Requiring Rerun or Resume", ""))
        if failures:
            for item in failures:
                code = item.error.get("code", "UNKNOWN") if item.error else "UNKNOWN"
                lines.append(
                    f"- **{item.candidate_id}** — `{code}`; {_recovery_guidance(item)}"
                )
        else:
            lines.append("- None.")
        lines.extend(("", "## Candidate Details", ""))
        for candidate in result.candidates:
            lines.extend(
                (
                    f"### {candidate.candidate_id}",
                    "",
                    f"- Run status: `{candidate.production_run_status}`",
                    f"- Execution source: `{candidate.execution_source.value}`",
                    f"- Recovery disposition: `{candidate.recovery_disposition.value}` — {_recovery_guidance(candidate)}",
                    f"- Operator action: `{_candidate_action(candidate)}`",
                    f"- Evidence readiness: `{candidate.evidence_readiness or 'UNAVAILABLE'}`",
                    f"- Why: {candidate.action_reason or 'Candidate failed before operator workflow delivery.'}",
                    f"- Opportunity score: {_opportunity(candidate)}",
                    f"- Comparable numeric ranking: `{candidate.ranking_status}`",
                    f"- Competition status: `{candidate.competition_status or 'UNAVAILABLE'}`",
                    "- Top buyer-need themes:",
                )
            )
            if candidate.top_buyer_need_themes:
                lines.extend(
                    f"  - {item.get('label', 'UNAVAILABLE')} [`{item.get('status', 'UNAVAILABLE')}`]: {_display(item.get('value'))}"
                    for item in candidate.top_buyer_need_themes
                )
            else:
                lines.append("  - UNAVAILABLE")
            lines.append("- Top missing evidence:")
            if candidate.top_missing_evidence:
                lines.extend(
                    f"  - {item.get('label', 'UNAVAILABLE')} [`{item.get('status', 'UNAVAILABLE')}`]"
                    for item in candidate.top_missing_evidence
                )
            else:
                lines.append("  - UNAVAILABLE")
            lines.append("- Next checks:")
            if candidate.next_actions:
                lines.extend(
                    f"  - [P{item.get('priority', 'UNAVAILABLE')}] {item.get('action', 'UNAVAILABLE')}"
                    for item in candidate.next_actions
                )
            else:
                lines.append("  - UNAVAILABLE")
            lines.append("- Per-candidate artifacts:")
            if candidate.artifact_paths:
                lines.extend(
                    f"  - {name}: `{path}`"
                    for name, path in sorted(candidate.artifact_paths.items())
                )
            else:
                lines.append("  - No normal report artifacts were attributed to this failed candidate.")
            lines.extend(
                (
                    f"- Audit lineage: {', '.join(candidate.lineage_reference_ids) or 'UNAVAILABLE'}",
                    "",
                )
            )
        lines.extend(
            (
                "## Semantic Boundary",
                "",
                "This brief groups explicit candidate cohorts by existing operator action and evidence readiness. It does not create a profitability estimate, market-entry decision, or numeric opportunity ranking.",
                "",
            )
        )
        return "\n".join(lines)


class BatchSummaryExcelRenderer:
    def __init__(
        self,
        *,
        node_executable: str | Path | None = None,
        node_modules_path: str | Path | None = None,
    ) -> None:
        self._runtime = ExcelReportRenderer(
            node_executable=node_executable,
            node_modules_path=node_modules_path,
        )

    def render(
        self,
        result: BatchSelectionResult,
        destination: Path,
        *,
        preview_directory: Path | None = None,
    ) -> Path:
        node = self._runtime._resolve_node()
        modules = self._runtime._resolve_node_modules()
        template = Path(__file__).parent / "templates" / "batch_selection_summary.mjs"
        if not template.is_file():
            raise BatchSelectionError(
                BatchSelectionErrorCode.BATCH_DELIVERY_FAILURE,
                "batch XLSX renderer template is missing",
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(prefix="batch-selection-summary-") as directory:
            workdir = Path(directory)
            self._runtime._link_node_modules(workdir / "node_modules", modules)
            source = workdir / "batch_selection_result.json"
            rendered = workdir / BATCH_XLSX_FILENAME
            executable = workdir / template.name
            shutil.copyfile(template, executable)
            source.write_text(
                json.dumps(
                    result.to_dict(),
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            command = [str(node), str(executable), str(source), str(rendered)]
            if preview_directory is not None:
                command.append(str(preview_directory.resolve()))
            completed = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            expected_previews = tuple(
                (preview_directory / filename)
                for filename in (
                    "batch_summary.png",
                    "candidate_actions.png",
                    "evidence_gaps.png",
                    "run_health.png",
                    "audit_lineage.png",
                )
            ) if preview_directory is not None else ()
            preview_contract_complete = bool(expected_previews) and all(
                path.is_file() for path in expected_previews
            )
            if not rendered.is_file() or (
                completed.returncode != 0 and not preview_contract_complete
            ):
                detail = (completed.stderr or completed.stdout or "unknown error").strip()
                raise BatchSelectionError(
                    BatchSelectionErrorCode.BATCH_DELIVERY_FAILURE,
                    f"artifact-tool batch XLSX rendering failed: {detail}",
                )
            try:
                self._runtime._canonicalize_package(rendered)
                self._canonicalize_table_relationships(rendered)
            except OperatorReportExcelError as exc:
                raise BatchSelectionError(
                    BatchSelectionErrorCode.BATCH_DELIVERY_FAILURE,
                    "batch XLSX canonicalization failed",
                ) from exc
            rendered.replace(destination)
        return destination

    @staticmethod
    def _canonicalize_table_relationships(path: Path) -> None:
        """Normalize artifact-tool table relationship IDs without changing cells."""

        with zipfile.ZipFile(path, "r") as source:
            members = {name: source.read(name) for name in source.namelist()}
        relationship_names = sorted(
            name
            for name in members
            if re.fullmatch(r"xl/worksheets/_rels/sheet\d+\.xml\.rels", name)
        )
        for relationship_name in relationship_names:
            sheet_number = re.search(r"sheet(\d+)\.xml\.rels$", relationship_name).group(1)
            sheet_name = f"xl/worksheets/sheet{sheet_number}.xml"
            relationship_xml = members[relationship_name].decode("utf-8-sig")
            sheet_xml = members[sheet_name].decode("utf-8-sig")
            matches = sorted(
                re.findall(
                    r'<Relationship\b(?=[^>]*\bTarget="(/xl/tables/table\d+\.xml)")'
                    r'[^>]*\bId="([^"]+)"[^>]*/>',
                    relationship_xml,
                ),
                key=lambda item: int(re.search(r"table(\d+)\.xml$", item[0]).group(1)),
            )
            for index, (_target, volatile_id) in enumerate(matches, start=1):
                stable_id = f"rId{index}"
                relationship_xml = relationship_xml.replace(
                    f'Id="{volatile_id}"', f'Id="{stable_id}"'
                )
                sheet_xml = sheet_xml.replace(
                    f'r:id="{volatile_id}"', f'r:id="{stable_id}"'
                )
            members[relationship_name] = relationship_xml.encode("utf-8")
            members[sheet_name] = sheet_xml.encode("utf-8")
        canonical = path.with_suffix(".tables-canonical.xlsx")
        with zipfile.ZipFile(
            canonical, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as output:
            for name in sorted(members):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                output.writestr(info, members[name], compresslevel=9)
        canonical.replace(path)


@dataclass(frozen=True, slots=True, kw_only=True)
class BatchSummaryDeliveryResult:
    json_path: Path
    xlsx_path: Path
    markdown_path: Path
    json_sha256: str
    xlsx_sha256: str
    markdown_sha256: str


class BatchSummaryDelivery:
    def __init__(
        self,
        *,
        excel_renderer: BatchSummaryExcelRenderer | None = None,
        markdown_renderer: BatchSummaryMarkdownRenderer | None = None,
    ) -> None:
        self._excel_renderer = excel_renderer or BatchSummaryExcelRenderer()
        self._markdown_renderer = markdown_renderer or BatchSummaryMarkdownRenderer()

    def deliver(
        self,
        result: BatchSelectionResult,
        output_directory: Path,
        *,
        preview_directory: Path | None = None,
    ) -> BatchSummaryDeliveryResult:
        json_path = output_directory / BATCH_JSON_FILENAME
        xlsx_path = output_directory / BATCH_XLSX_FILENAME
        markdown_path = output_directory / BATCH_MARKDOWN_FILENAME
        markdown = self._markdown_renderer.render(result)
        temporary_markdown = markdown_path.with_name(f".{markdown_path.name}.tmp")
        temporary_markdown.write_text(markdown, encoding="utf-8", newline="\n")
        temporary_markdown.replace(markdown_path)
        self._excel_renderer.render(
            result,
            xlsx_path,
            preview_directory=preview_directory,
        )
        write_json_atomic(json_path, result.to_dict())
        return BatchSummaryDeliveryResult(
            json_path=json_path,
            xlsx_path=xlsx_path,
            markdown_path=markdown_path,
            json_sha256=_sha256(json_path),
            xlsx_sha256=_sha256(xlsx_path),
            markdown_sha256=_sha256(markdown_path),
        )


__all__ = (
    "BATCH_JSON_FILENAME",
    "BATCH_MARKDOWN_FILENAME",
    "BATCH_XLSX_FILENAME",
    "BatchSummaryDelivery",
    "BatchSummaryDeliveryResult",
    "BatchSummaryExcelRenderer",
    "BatchSummaryMarkdownRenderer",
)
