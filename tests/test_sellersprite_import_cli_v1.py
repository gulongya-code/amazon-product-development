from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


def _load_cli():
    path = Path(__file__).parents[1] / "scripts" / "import_sellersprite_market.py"
    spec = importlib.util.spec_from_file_location("import_sellersprite_market", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_prints_only_sanitized_summary_and_never_overwrites(tmp_path: Path, capsys) -> None:
    source = tmp_path / "cli-source.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["ASIN", "商品标题", "价格($)", "月销量", "评分"])
        writer.writerow(["SYNTH00001", "scalar-must-not-reach-summary", "10.50", 2, 4.5])
    output = tmp_path / "dataset.json"
    cli = _load_cli()
    args = [
        "--input",
        str(source),
        "--marketplace",
        "US",
        "--category",
        "synthetic-category",
        "--imported-at",
        "2026-08-26T12:00:00Z",
        "--output",
        str(output),
    ]

    assert cli.main(args) == 0
    summary = capsys.readouterr().out
    assert "scalar-must-not-reach-summary" not in summary
    assert "SYNTH00001" not in summary
    assert json.loads(summary)["accepted_listing_count"] == 1
    assert output.is_file()

    assert cli.main(args) == 2
    failure = json.loads(capsys.readouterr().out)
    assert failure["status"] == "FAILED"
    assert "exist" in failure["error"].casefold()
