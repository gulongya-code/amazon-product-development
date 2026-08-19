"""Safe, provider-neutral persistence for raw API response snapshots."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from amazon_product_intelligence.schemas import APIResponse


_UNSAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _filename_part(value: str) -> str:
    candidate = _UNSAFE_FILENAME.sub("-", value).strip("-.")
    return candidate[:120] or "snapshot"


class SnapshotWriter:
    """Write one immutable JSON file for each normalized provider response."""

    def __init__(self, output_directory: str | os.PathLike[str]) -> None:
        self.output_directory = Path(output_directory)
        if self.output_directory.exists() and not self.output_directory.is_dir():
            raise ValueError("output_directory must be a directory path")

    def write(
        self,
        response: APIResponse,
        *,
        snapshot_id: str | None = None,
        timestamp: str | None = None,
    ) -> Path:
        """Persist a response without transforming or filtering its payload."""

        if not isinstance(response, APIResponse):
            raise TypeError("response must be APIResponse")
        resolved_snapshot_id = snapshot_id or uuid4().hex
        resolved_timestamp = timestamp or _utc_timestamp()
        record = response.to_snapshot(
            snapshot_id=resolved_snapshot_id,
            timestamp=resolved_timestamp,
        )
        serialized = json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        ) + "\n"

        self.output_directory.mkdir(parents=True, exist_ok=True)
        filename = f"{response.source}_{_filename_part(resolved_snapshot_id)}.json"
        destination = self.output_directory / filename
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        descriptor = os.open(destination, flags, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
        except BaseException:
            destination.unlink(missing_ok=True)
            raise
        return destination


__all__ = ("SnapshotWriter",)
