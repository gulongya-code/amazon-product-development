"""Provider-neutral API response envelope used by raw-data ingestion."""

from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
from types import MappingProxyType
from typing import Any, Mapping


_SOURCE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_SENSITIVE_KEYS = {
    "api-key",
    "api_key",
    "apikey",
    "access-token",
    "access_token",
    "authorization",
    "cookie",
    "password",
    "proxy-authorization",
    "secret",
    "token",
    "x-api-key",
}


def _require_json(name: str, value: Any) -> None:
    """Reject values that cannot be persisted without transforming them."""

    try:
        json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be JSON serializable") from exc


def _sensitive_key(value: Any) -> str | None:
    if isinstance(value, MappingABC):
        for key, item in value.items():
            if str(key).strip().casefold() in _SENSITIVE_KEYS:
                return str(key)
            nested = _sensitive_key(item)
            if nested is not None:
                return nested
    elif isinstance(value, (list, tuple)):
        for item in value:
            nested = _sensitive_key(item)
            if nested is not None:
                return nested
    return None


def _require_timestamp(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("timestamp must be non-empty text")
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("timestamp must be an RFC 3339 date-time") from exc
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")


@dataclass(frozen=True, slots=True, kw_only=True)
class APIResponse:
    """A normalized response that retains the provider payload unchanged.

    Authentication material is deliberately absent. ``request_metadata`` is
    the sanitized acquisition context assembled by ``BaseAPIClient``.
    """

    source: str
    status_code: int
    request_metadata: Mapping[str, Any] = field(default_factory=dict)
    payload: Any

    def __post_init__(self) -> None:
        if not isinstance(self.source, str) or not _SOURCE_ID.fullmatch(self.source):
            raise ValueError("source must be a lowercase machine-readable identifier")
        if not isinstance(self.status_code, int) or not 100 <= self.status_code <= 599:
            raise ValueError("status_code must be a valid HTTP-style status")
        if not isinstance(self.request_metadata, MappingABC):
            raise ValueError("request_metadata must be a mapping")
        metadata = dict(self.request_metadata)
        sensitive_key = _sensitive_key(metadata)
        if sensitive_key is not None:
            raise ValueError(
                f"request_metadata must not contain credential field {sensitive_key!r}"
            )
        _require_json("request_metadata", metadata)
        _require_json("payload", self.payload)
        object.__setattr__(self, "request_metadata", MappingProxyType(metadata))

    def to_snapshot(
        self,
        *,
        snapshot_id: str,
        timestamp: str,
    ) -> dict[str, Any]:
        """Return the stable raw snapshot record without altering ``payload``."""

        if not isinstance(snapshot_id, str) or not snapshot_id.strip():
            raise ValueError("snapshot_id must be non-empty text")
        _require_timestamp(timestamp)
        return {
            "source": self.source,
            "snapshot_id": snapshot_id,
            "timestamp": timestamp,
            "request_metadata": dict(self.request_metadata),
            "payload": self.payload,
        }


__all__ = ("APIResponse",)
