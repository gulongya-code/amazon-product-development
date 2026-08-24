"""Artifact-tool backed XLSX renderer for operator Market Reports."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from tempfile import TemporaryDirectory
import zipfile

from amazon_product_intelligence.market_report.models import MarketReportSnapshot
from amazon_product_intelligence.operator_workflow import (
    OperatorWorkflowSnapshotV0_1,
    build_standalone_operator_workflow,
)


class OperatorReportExcelError(RuntimeError):
    """Raised when the external XLSX authoring runtime cannot complete."""


class ExcelReportRenderer:
    """Render XLSX through the governed artifact-tool JavaScript runtime."""

    def __init__(
        self,
        *,
        node_executable: str | Path | None = None,
        node_modules_path: str | Path | None = None,
    ) -> None:
        configured_node = node_executable or os.environ.get(
            "MARKET_REPORT_NODE_EXECUTABLE"
        )
        configured_modules = node_modules_path or os.environ.get(
            "MARKET_REPORT_NODE_MODULES"
        )
        self.node_executable = Path(configured_node) if configured_node else None
        self.node_modules_path = (
            Path(configured_modules) if configured_modules else None
        )

    def render(
        self,
        report: MarketReportSnapshot,
        destination: str | Path,
        *,
        operator_workflow: OperatorWorkflowSnapshotV0_1 | None = None,
        preview_directory: str | Path | None = None,
    ) -> Path:
        report.validate()
        workflow = operator_workflow or build_standalone_operator_workflow(report)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        node = self._resolve_node()
        modules = self._resolve_node_modules()
        template = Path(__file__).parent / "templates" / "operator_market_report.mjs"
        if not template.is_file():
            raise OperatorReportExcelError(f"XLSX renderer template is missing: {template}")

        with TemporaryDirectory(prefix="operator-market-report-") as directory:
            workdir = Path(directory)
            self._link_node_modules(workdir / "node_modules", modules)
            source = workdir / "market_report.json"
            rendered = workdir / "operator_market_report.xlsx"
            executable_template = workdir / template.name
            shutil.copyfile(template, executable_template)
            source.write_text(
                json.dumps(
                    {
                        "report": report.to_dict(),
                        "operator_workflow": workflow.to_dict(),
                    },
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            command = [
                str(node),
                str(executable_template),
                str(source),
                str(rendered),
            ]
            completed = subprocess.run(
                command,
                cwd=workdir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            if completed.returncode != 0 or not rendered.exists():
                detail = (completed.stderr or completed.stdout or "unknown error").strip()
                artifacts = ", ".join(
                    sorted(path.name for path in workdir.iterdir())
                )
                raise OperatorReportExcelError(
                    f"artifact-tool XLSX rendering failed: {detail}; "
                    f"workdir artifacts: {artifacts or 'none'}"
                )
            self._canonicalize_package(rendered)
            rendered.replace(target)
            if preview_directory is not None:
                previews = Path(preview_directory)
                previews.mkdir(parents=True, exist_ok=True)
                preview_command = [
                    str(node),
                    str(executable_template),
                    str(source),
                    str(workdir / "preview-render.xlsx"),
                    str(previews.resolve()),
                ]
                previewed = subprocess.run(
                    preview_command,
                    cwd=workdir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                expected_previews = tuple(
                    previews / name
                    for name in (
                        "operator_summary.png",
                        "market_overview.png",
                        "buyer_need_analysis.png",
                        "competition_analysis.png",
                        "opportunity_analysis.png",
                    )
                )
                # The Windows artifact runtime can report a non-zero teardown code
                # after writing every requested PNG.  The files are the preview
                # contract, so treat their complete presence as success.
                if not all(path.is_file() for path in expected_previews):
                    detail = (
                        previewed.stderr or previewed.stdout or "unknown error"
                    ).strip()
                    raise OperatorReportExcelError(
                        f"artifact-tool preview rendering failed: {detail}"
                    )
        return target

    def _resolve_node(self) -> Path:
        candidate = self.node_executable
        if candidate is None:
            discovered = shutil.which("node")
            candidate = Path(discovered) if discovered else None
        if candidate is None or not candidate.is_file():
            raise OperatorReportExcelError(
                "Node.js is unavailable; configure MARKET_REPORT_NODE_EXECUTABLE"
            )
        return candidate.resolve()

    def _resolve_node_modules(self) -> Path:
        if self.node_modules_path is None or not self.node_modules_path.is_dir():
            raise OperatorReportExcelError(
                "artifact-tool node_modules is unavailable; configure "
                "MARKET_REPORT_NODE_MODULES"
            )
        return self.node_modules_path.resolve()

    @staticmethod
    def _link_node_modules(link: Path, target: Path) -> None:
        if os.name != "nt":
            link.symlink_to(target, target_is_directory=True)
            return
        command = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            (
                "& { param($linkPath, $targetPath) "
                "New-Item -ItemType Junction -Path $linkPath "
                "-Target $targetPath | Out-Null }"
            ),
            str(link),
            str(target),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0 or not link.is_dir():
            detail = (completed.stderr or completed.stdout or "unknown error").strip()
            raise OperatorReportExcelError(
                f"cannot prepare artifact-tool dependency junction: {detail}"
            )

    @staticmethod
    def _canonicalize_package(path: Path) -> None:
        """Remove volatile relationship IDs and ZIP timestamps from an XLSX."""

        with zipfile.ZipFile(path, "r") as source:
            members = {name: source.read(name) for name in source.namelist()}

        relationship_name = "xl/_rels/workbook.xml.rels"
        workbook_name = "xl/workbook.xml"
        relationship_xml = members[relationship_name].decode("utf-8-sig")
        replacements: dict[str, str] = {}
        stable_targets = {
            "/xl/styles.xml": "rId1",
            "/xl/theme/theme1.xml": "rId2",
            "/xl/sharedStrings.xml": "rId3",
        }
        worksheet_targets = sorted(
            (
                target
                for target in re.findall(r'\bTarget="([^"]+)"', relationship_xml)
                if target.startswith("/xl/worksheets/sheet") and target.endswith(".xml")
            ),
            key=lambda value: int(re.search(r"sheet(\d+)\.xml$", value).group(1)),
        )
        stable_targets.update(
            {target: f"rId{index}" for index, target in enumerate(worksheet_targets, start=4)}
        )
        for target, stable_id in stable_targets.items():
            match = re.search(
                rf'<Relationship\b(?=[^>]*\bTarget="{re.escape(target)}")'
                r'[^>]*\bId="([^"]+)"[^>]*/>',
                relationship_xml,
            )
            if match is None:
                raise OperatorReportExcelError(
                    f"XLSX relationship is missing for {target}"
                )
            replacements[match.group(1)] = stable_id

        for volatile_id, stable_id in replacements.items():
            relationship_xml = relationship_xml.replace(
                f'Id="{volatile_id}"', f'Id="{stable_id}"'
            )
        workbook_xml = members[workbook_name].decode("utf-8-sig")
        for volatile_id, stable_id in replacements.items():
            workbook_xml = workbook_xml.replace(
                f'r:id="{volatile_id}"', f'r:id="{stable_id}"'
            )

        root_relationships = members["_rels/.rels"].decode("utf-8-sig")
        root_relationships = re.sub(
            r'\bId="[^"]+"', 'Id="rId1"', root_relationships
        )
        members[relationship_name] = relationship_xml.encode("utf-8")
        members[workbook_name] = workbook_xml.encode("utf-8")
        members["_rels/.rels"] = root_relationships.encode("utf-8")

        canonical = path.with_suffix(".canonical.xlsx")
        with zipfile.ZipFile(
            canonical, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as output:
            for name in sorted(members):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                output.writestr(info, members[name], compresslevel=9)
        canonical.replace(path)


__all__ = ("ExcelReportRenderer", "OperatorReportExcelError")
