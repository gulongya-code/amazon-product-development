"""Offline Raw Snapshot reader and shared business-adapter mapping flow."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping

from amazon_product_intelligence.schemas.canonical_mapping import (
    CanonicalFieldStatus,
    EntityType,
    EXPLICITLY_UNAVAILABLE_FIELDS,
    MappedEntity,
    MappedField,
    P0_KEYWORD_FIELDS,
    P0_PRODUCT_FIELDS,
    mappings_for,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class RawSnapshot:
    source: str
    snapshot_id: str
    timestamp: str
    request_metadata: Mapping[str, Any]
    payload: Any

    @classmethod
    def load(cls, value: Mapping[str, Any] | str | Path) -> "RawSnapshot":
        if isinstance(value, (str, Path)):
            with Path(value).open("r", encoding="utf-8") as handle:
                document = json.load(handle)
        else:
            document = value
        if not isinstance(document, MappingABC):
            raise ValueError("Raw Snapshot must be a JSON object")
        required = {"source", "snapshot_id", "timestamp", "request_metadata", "payload"}
        missing = required - document.keys()
        if missing:
            raise ValueError(f"Raw Snapshot is missing required fields: {sorted(missing)!r}")
        source = document["source"]
        snapshot_id = document["snapshot_id"]
        timestamp = document["timestamp"]
        metadata = document["request_metadata"]
        if not isinstance(source, str) or not source.strip():
            raise ValueError("Raw Snapshot source must be non-empty text")
        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise ValueError("Raw Snapshot snapshot_id must be non-empty text")
        if not isinstance(timestamp, str) or not timestamp.strip():
            raise ValueError("Raw Snapshot timestamp must be non-empty text")
        candidate = timestamp[:-1] + "+00:00" if timestamp.endswith("Z") else timestamp
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("Raw Snapshot timestamp must use ISO-8601") from exc
        if parsed.tzinfo is None:
            raise ValueError("Raw Snapshot timestamp must include a timezone")
        if not isinstance(metadata, MappingABC):
            raise ValueError("Raw Snapshot request_metadata must be an object")
        return cls(
            source=source.strip().casefold(),
            snapshot_id=snapshot_id.strip(),
            timestamp=timestamp,
            request_metadata=dict(metadata),
            payload=document["payload"],
        )


class SnapshotBusinessAdapter:
    """Map a validated snapshot into raw Canonical field candidates only."""

    source: str

    def adapt(self, value: Mapping[str, Any] | str | Path) -> tuple[MappedEntity, ...]:
        snapshot = RawSnapshot.load(value)
        if snapshot.source != self.source:
            raise ValueError(
                f"snapshot source {snapshot.source!r} does not match adapter {self.source!r}"
            )
        operation = snapshot.request_metadata.get("operation")
        if operation is not None and (not isinstance(operation, str) or not operation.strip()):
            raise ValueError("snapshot operation must be non-empty text when supplied")
        resolved_operation, entity_type, records = self._records(
            snapshot.payload,
            operation.strip() if isinstance(operation, str) else None,
        )
        if not records:
            return ()
        return tuple(
            self._map_record(snapshot, resolved_operation, entity_type, record)
            for record in records
        )

    def _records(
        self,
        payload: Any,
        operation: str | None,
    ) -> tuple[str, EntityType, tuple[Mapping[str, Any], ...]]:
        raise NotImplementedError

    def _map_record(
        self,
        snapshot: RawSnapshot,
        operation: str,
        entity_type: EntityType,
        record: Mapping[str, Any],
    ) -> MappedEntity:
        expected_fields = P0_PRODUCT_FIELDS if entity_type is EntityType.PRODUCT else P0_KEYWORD_FIELDS
        operation_mappings = mappings_for(self.source, operation, entity_type)
        source_mappings = mappings_for(self.source, entity_type=entity_type)
        fields: dict[str, MappedField] = {}
        currency = self._currency(record, snapshot.request_metadata)
        observed_at = record.get("observed_at") if isinstance(record.get("observed_at"), str) else None

        for canonical_field in expected_fields:
            candidates = tuple(
                mapping
                for mapping in operation_mappings
                if mapping.canonical_field == canonical_field
            )
            selected = next(
                (mapping for mapping in candidates if mapping.record_field in record),
                None,
            )
            if selected is not None:
                raw_value = record[selected.record_field]
                if raw_value is None:
                    status = CanonicalFieldStatus.UNKNOWN
                elif selected.transform_rule == "defer_trend_analysis":
                    status = CanonicalFieldStatus.PENDING
                else:
                    status = CanonicalFieldStatus.PRESENT
                fields[canonical_field] = MappedField(
                    canonical_field=canonical_field,
                    raw_value=raw_value,
                    status=status,
                    mapping=selected,
                    currency=currency if canonical_field == "metric.price" else None,
                    observed_at=self._observed_at(selected.record_field, raw_value, observed_at),
                )
                continue

            source_supports_field = any(
                mapping.canonical_field == canonical_field for mapping in source_mappings
            )
            if candidates:
                status = CanonicalFieldStatus.UNKNOWN
            elif source_supports_field:
                status = CanonicalFieldStatus.PENDING
            elif canonical_field in EXPLICITLY_UNAVAILABLE_FIELDS.get(self.source, frozenset()):
                status = CanonicalFieldStatus.NOT_AVAILABLE
            else:
                status = CanonicalFieldStatus.UNKNOWN
            fields[canonical_field] = MappedField(
                canonical_field=canonical_field,
                raw_value=None,
                status=status,
                mapping=None,
            )

        identity_field = "product.asin" if entity_type is EntityType.PRODUCT else "keyword.text"
        identity_value = fields[identity_field].raw_value
        identity_hint = str(identity_value) if identity_value is not None else None
        return MappedEntity(
            source=snapshot.source,
            snapshot_id=snapshot.snapshot_id,
            timestamp=snapshot.timestamp,
            entity_type=entity_type,
            identity_hint=identity_hint,
            fields=fields,
        )

    @staticmethod
    def _currency(record: Mapping[str, Any], metadata: Mapping[str, Any]) -> str | None:
        candidate = record.get("currency", metadata.get("currency"))
        if not isinstance(candidate, str) or not candidate.strip():
            return None
        normalized = candidate.strip().upper()
        return normalized if len(normalized) == 3 and normalized.isalpha() else None

    @staticmethod
    def _observed_at(record_field: str, raw_value: Any, fallback: str | None) -> str | None:
        if record_field == "abaReport" and isinstance(raw_value, MappingABC):
            candidate = raw_value.get("reportToDate") or raw_value.get("reportFromDate")
            return candidate if isinstance(candidate, str) else fallback
        return fallback


def unwrap_data(payload: Any) -> Mapping[str, Any]:
    if not isinstance(payload, MappingABC):
        raise ValueError("snapshot payload must be an object")
    data = payload.get("data")
    return data if isinstance(data, MappingABC) else payload


def mapping_records(value: Any, name: str) -> tuple[Mapping[str, Any], ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{name} must be an array")
    records = tuple(item for item in value if isinstance(item, MappingABC))
    if len(records) != len(value):
        raise ValueError(f"{name} must contain only objects")
    return records


__all__ = (
    "RawSnapshot",
    "SnapshotBusinessAdapter",
    "mapping_records",
    "unwrap_data",
)
