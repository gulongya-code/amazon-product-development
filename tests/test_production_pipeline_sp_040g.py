from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import zipfile

import pytest

from amazon_product_intelligence.market_report.v0_2 import market_report_v0_2_from_dict
from amazon_product_intelligence.market_report.v0_2.delivery import SHEET_NAMES
import amazon_product_intelligence.production_pipeline.orchestrator as orchestrator
from amazon_product_intelligence.production_pipeline import (
    ProductionRunMode,
    ProductionRunRequest,
    ProductionRunStatus,
    ProductionRunValidationError,
    ProviderUsageSemantics,
    ProviderUsageUnit,
)
from amazon_product_intelligence.production_pipeline.orchestrator import (
    ProductionPipelineOrchestrator,
)
from amazon_product_intelligence.production_pipeline.planner import build_acquisition_plan
from amazon_product_intelligence.production_pipeline.providers import FixtureTransport
from tests.test_production_pipeline_sp_040e import (
    ASIN,
    SORFTIME_FIXTURE,
    sorftime_runtime,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCT_CENSUS = (
    ROOT
    / "tests"
    / "fixtures"
    / "sorftime_dtos"
    / "v0_1"
    / "product_request_r3_structural_census.json"
)
KEYWORD_CENSUS = (
    ROOT
    / "tests"
    / "fixtures"
    / "sorftime_dtos"
    / "v0_1"
    / "asin_request_keyword_r5_structural_census.json"
)
V0_2_GATE = (
    "amazon_product_intelligence.production_pipeline.orchestrator."
    "_SORFTIME_V0_2_LIVE_RELEASE_ENABLED"
)


def request(output: Path, **overrides) -> ProductionRunRequest:
    values = {
        "marketplace": "US",
        "asins": (ASIN,),
        "output_directory": output,
        "provider_preference": "sorftime",
        "provider_config_reference": "environment",
        "run_id": "sp040g-offline",
        "mode": ProductionRunMode.LIVE,
        "category_name": "dog water bottle",
        "report_version": "market-report-v0.2",
    }
    values.update(overrides)
    return ProductionRunRequest(**values)


def mapping_keys(value) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(str(key) for key in value)
        for child in value.values():
            found.update(mapping_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(mapping_keys(child))
    return found


def test_v0_1_and_accepted_v0_2_release_gates_are_enabled():
    assert orchestrator._SORFTIME_V0_1_LIVE_RELEASE_ENABLED is True
    assert orchestrator._SORFTIME_V0_2_LIVE_RELEASE_ENABLED is True


def test_disabled_v0_2_gate_precedes_runtime_and_credential_construction():
    calls: list[str] = []
    with patch(V0_2_GATE, False), TemporaryDirectory() as directory:
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=lambda _: calls.append("constructed"),  # type: ignore[arg-type]
        ).run(request(Path(directory)))
    assert result.status is ProductionRunStatus.FAILED
    assert calls == []
    assert "market-report-v0.2 live release remains blocked" in result.error["message"]


def test_xiyou_v0_2_live_remains_rejected_at_request_boundary():
    with TemporaryDirectory() as directory, pytest.raises(
        ProductionRunValidationError, match="explicit Sorftime"
    ):
        request(Path(directory), provider_preference="xiyou")


def test_enabled_injected_v0_2_live_pipeline_is_strict_and_capture_neutral():
    fixture = json.loads(SORFTIME_FIXTURE.read_text(encoding="utf-8"))
    transport = FixtureTransport(fixture)
    with patch(V0_2_GATE, True), TemporaryDirectory(dir=ROOT / "outputs") as directory:
        output = Path(directory)
        result = ProductionPipelineOrchestrator(
            provider_runtime_factory=lambda _: sorftime_runtime(
                transport,
                usage_semantics=ProviderUsageSemantics.LIVE_PROVIDER_REPORTED,
            )
        ).run(request(output))

        assert result.status is ProductionRunStatus.SUCCEEDED
        report_payload = json.loads(
            (output / "market_report.json").read_text(encoding="utf-8")
        )
        report = market_report_v0_2_from_dict(report_payload)
        assert report.metadata.report_version == "market-report-v0.2"
        with zipfile.ZipFile(output / "operator_market_report.xlsx") as package:
            workbook_xml = package.read("xl/workbook.xml").decode("utf-8-sig")
        assert tuple(
            name for name in SHEET_NAMES if f'name="{name}"' in workbook_xml
        ) == SHEET_NAMES

    summary = result.provider_summary
    assert summary is not None and summary.provider_usage is not None
    assert summary.operations == ("ProductRequest", "ASINRequestKeyword")
    assert summary.executed_operation_count == 2
    assert summary.replayed_operation_count == 0
    assert summary.transport_attempt_count == 2
    assert summary.provider_usage.unit is ProviderUsageUnit.REQUEST
    assert (
        summary.provider_usage.semantics
        is ProviderUsageSemantics.LIVE_PROVIDER_REPORTED
    )
    assert summary.provider_usage.consumed == 2
    assert summary.credits is None and summary.credit_semantics is None
    assert transport.network_call_count == 0

    product_census = json.loads(PRODUCT_CENSUS.read_text(encoding="utf-8"))
    product_capture = {
        name
        for group in product_census["field_groups"]
        if group["status"].startswith("CAPTURED_")
        for name in group["field_names"]
    }
    keyword_census = json.loads(KEYWORD_CENSUS.read_text(encoding="utf-8"))
    keyword_capture = {
        name
        for names in keyword_census["nested_capture_only_fields"].values()
        for name in names
    }
    keys = mapping_keys(report_payload)
    assert not (product_capture & keys)
    assert not (keyword_capture & keys)
    serialized = json.dumps(report_payload, sort_keys=True)
    assert "ProductVariations" not in serialized
    assert "sponsored" not in serialized.casefold()


def test_enabled_v0_2_live_scope_stays_exact_and_pre_runtime():
    cases = (
        {"asins": ("B09TSGDJLD",)},
        {"marketplace": "CA"},
        {"resume_from": Path("offline-source")},
    )
    for overrides in cases:
        calls: list[str] = []
        with patch(V0_2_GATE, True), TemporaryDirectory() as directory:
            result = ProductionPipelineOrchestrator(
                provider_runtime_factory=lambda _: calls.append("constructed"),  # type: ignore[arg-type]
            ).run(request(Path(directory), **overrides))
        assert result.status is ProductionRunStatus.FAILED
        assert calls == []


def test_defaults_batch_boundary_and_sorftime_plan_remain_unchanged():
    with TemporaryDirectory() as directory:
        default = ProductionRunRequest(
            marketplace="US",
            asins=("B0DWB00001",),
            output_directory=Path(directory),
        )
    assert default.provider_preference == "xiyou"
    assert default.report_version == "market-report-v0.1"
    plan = build_acquisition_plan(
        provider_id="sorftime", marketplace="US", asins=(ASIN,)
    )
    assert tuple(item.operation for item in plan.steps) == (
        "ProductRequest",
        "ASINRequestKeyword",
    )
    assert dict(plan.steps[0].parameters) == {"ASIN": ASIN, "Trend": 2}
    assert dict(plan.steps[1].parameters) == {
        "ASIN": ASIN,
        "PageIndex": 1,
        "PageSize": 20,
    }
