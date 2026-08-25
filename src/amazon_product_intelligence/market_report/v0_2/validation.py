"""Exact-version V0.2 JSON validation surface."""

from __future__ import annotations

from typing import Any, Mapping

from .models import MarketReportV0_2ValidationError
from .models.report_snapshot import MarketReportSnapshotV0_2
from .version import MARKET_REPORT_V0_2_VERSION


def market_report_v0_2_from_dict(payload: Mapping[str, Any]) -> MarketReportSnapshotV0_2:
    if not isinstance(payload, Mapping):
        raise MarketReportV0_2ValidationError("Market Report V0.2 payload must be an object")
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping) or metadata.get("report_version") != MARKET_REPORT_V0_2_VERSION:
        raise MarketReportV0_2ValidationError("exact market-report-v0.2 metadata version is required")
    return MarketReportSnapshotV0_2.from_dict(payload)


__all__ = ("market_report_v0_2_from_dict",)
