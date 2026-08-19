"""Offline XiYou Raw Snapshot business adapter."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from typing import Any, Mapping

from amazon_product_intelligence.schemas import EntityType

from .snapshot_base import SnapshotBusinessAdapter, mapping_records, unwrap_data


class XiyouAdapter(SnapshotBusinessAdapter):
    """Understand supported XiYou snapshots without transport or credentials."""

    source = "xiyou"

    def _records(
        self,
        payload: Any,
        operation: str | None,
    ) -> tuple[str, EntityType, tuple[Mapping[str, Any], ...]]:
        data = unwrap_data(payload)
        resolved = operation or self._infer_operation(data)
        if resolved in {"asin_info", "asin_info_http_v2"}:
            records = mapping_records(data.get("entities"), "XiYou entities")
            return resolved, EntityType.PRODUCT, records
        if resolved == "asin_orders_last_30_days":
            records = mapping_records(data.get("entities"), "XiYou order entities")
            return resolved, EntityType.PRODUCT, records
        if resolved in {"keyword_info", "keyword_info_http_v2"}:
            records = mapping_records(data.get("list"), "XiYou keyword list")
            prepared = tuple(self._keyword_record(record) for record in records)
            return resolved, EntityType.KEYWORD, prepared
        if resolved in {"asin_bsr_trends", "asin_bsr_trends_http_v2"}:
            return resolved, EntityType.PRODUCT, (self._bsr_record(data),)
        raise ValueError(f"unsupported XiYou business mapping operation {resolved!r}")

    @staticmethod
    def _infer_operation(data: Mapping[str, Any]) -> str:
        if isinstance(data.get("list"), (list, tuple)):
            return "keyword_info"
        if "categoryTree" in data or "trends" in data:
            return "asin_bsr_trends"
        entities = data.get("entities")
        if isinstance(entities, (list, tuple)) and entities:
            first = entities[0]
            if isinstance(first, MappingABC) and "orders" in first and "title" not in first:
                return "asin_orders_last_30_days"
            return "asin_info"
        raise ValueError("unable to infer XiYou snapshot operation")

    @staticmethod
    def _keyword_record(record: Mapping[str, Any]) -> Mapping[str, Any]:
        prepared = dict(record)
        report = record.get("abaReport")
        if isinstance(report, MappingABC):
            prepared["weeklySearchVolume"] = report.get("weeklySearchVolume")
            prepared["observed_at"] = report.get("reportToDate") or report.get("reportFromDate")
        return prepared

    @staticmethod
    def _bsr_record(data: Mapping[str, Any]) -> Mapping[str, Any]:
        category_tree = data.get("categoryTree")
        categories = (
            tuple(item for item in category_tree if isinstance(item, MappingABC))
            if isinstance(category_tree, (list, tuple))
            else ()
        )
        leaf = next(
            (item for item in reversed(categories) if item.get("root") is not True),
            categories[-1] if categories else None,
        )
        category_id = leaf.get("categoryId") if leaf is not None else None
        category_name = leaf.get("name") if leaf is not None else None

        trend_rows = data.get("trends")
        trends = (
            tuple(item for item in trend_rows if isinstance(item, MappingABC))
            if isinstance(trend_rows, (list, tuple))
            else ()
        )
        latest = max(trends, key=lambda item: str(item.get("date", "")), default=None)
        rank = None
        observed_at = None
        if latest is not None:
            observed_at = latest.get("date") if isinstance(latest.get("date"), str) else None
            values = latest.get("values")
            candidates = (
                tuple(item for item in values if isinstance(item, MappingABC))
                if isinstance(values, (list, tuple))
                else ()
            )
            selected = next(
                (item for item in candidates if category_id is not None and item.get("categoryId") == category_id),
                candidates[0] if candidates else None,
            )
            rank = selected.get("rank") if selected is not None else None
        return {
            "asin": data.get("asin"),
            "category": category_name,
            "bsr": rank,
            "observed_at": observed_at,
        }


XiYouBusinessAdapter = XiyouAdapter


__all__ = ("XiYouBusinessAdapter", "XiyouAdapter")
