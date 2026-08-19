"""Offline Sorftime Raw Snapshot business adapter."""

from __future__ import annotations

from typing import Any, Mapping

from amazon_product_intelligence.schemas import EntityType

from .snapshot_base import SnapshotBusinessAdapter, unwrap_data


class SorftimeAdapter(SnapshotBusinessAdapter):
    """Understand supported Sorftime snapshots without transport or storage."""

    source = "sorftime"

    def _records(
        self,
        payload: Any,
        operation: str | None,
    ) -> tuple[str, EntityType, tuple[Mapping[str, Any], ...]]:
        data = unwrap_data(payload)
        resolved = operation or self._infer_operation(data)
        if resolved != "product_detail":
            raise ValueError(f"unsupported Sorftime business mapping operation {resolved!r}")
        return resolved, EntityType.PRODUCT, (data,)

    @staticmethod
    def _infer_operation(data: Mapping[str, Any]) -> str:
        if any(field in data for field in ("asin", "title", "price", "review_count")):
            return "product_detail"
        raise ValueError("unable to infer Sorftime snapshot operation")


__all__ = ("SorftimeAdapter",)
