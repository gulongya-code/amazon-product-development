"""Stable artifact layout and atomic JSON writes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True, kw_only=True)
class RunArtifactLayout:
    output_directory: Path

    @property
    def market_report(self) -> Path:
        return self.output_directory / "market_report.json"

    @property
    def operator_xlsx(self) -> Path:
        return self.output_directory / "operator_market_report.xlsx"

    @property
    def operator_markdown(self) -> Path:
        return self.output_directory / "operator_market_report.md"

    @property
    def manifest(self) -> Path:
        return self.output_directory / "run_manifest.json"

    def existing(self) -> dict[str, str]:
        candidates = {
            "market_report_json": self.market_report,
            "operator_xlsx": self.operator_xlsx,
            "operator_markdown": self.operator_markdown,
            "run_manifest": self.manifest,
        }
        return {
            name: str(path.resolve())
            for name, path in candidates.items()
            if path.is_file()
        }


def write_json_atomic(destination: Path, payload: Mapping[str, Any]) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp")
    temporary.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination


__all__ = ("RunArtifactLayout", "write_json_atomic")
