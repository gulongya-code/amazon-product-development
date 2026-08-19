from __future__ import annotations

import json

import pytest

from amazon_product_intelligence.ingestion import SnapshotWriter
from amazon_product_intelligence.schemas import APIResponse


def test_snapshot_generation_records_source_request_and_unmodified_payload(tmp_path) -> None:
    payload = {
        "data": {
            "title": "原始标题",
            "nullable": None,
            "items": [3, 2, 1],
        }
    }
    response = APIResponse(
        source="xiyou",
        status_code=200,
        request_metadata={
            "operation": "fixture_product",
            "method": "POST",
            "endpoint": "/mock/product",
            "parameters": {"asin": "B0MOCK"},
            "status_code": 200,
        },
        payload=payload,
    )

    path = SnapshotWriter(tmp_path / "raw").write(
        response,
        snapshot_id="fixture-snapshot-001",
        timestamp="2026-08-19T02:03:04Z",
    )
    saved = json.loads(path.read_text(encoding="utf-8"))

    assert path.name == "xiyou_fixture-snapshot-001.json"
    assert saved == {
        "source": "xiyou",
        "snapshot_id": "fixture-snapshot-001",
        "timestamp": "2026-08-19T02:03:04Z",
        "request_metadata": {
            "operation": "fixture_product",
            "method": "POST",
            "endpoint": "/mock/product",
            "parameters": {"asin": "B0MOCK"},
            "status_code": 200,
        },
        "payload": payload,
    }
    assert response.payload is payload


@pytest.mark.parametrize("source", ("xiyou", "sorftime"))
def test_snapshot_preserves_each_data_source(tmp_path, source: str) -> None:
    response = APIResponse(
        source=source,
        status_code=200,
        request_metadata={"operation": "mock"},
        payload={"provider": source},
    )

    path = SnapshotWriter(tmp_path).write(
        response,
        snapshot_id=f"{source}-snapshot",
        timestamp="2026-08-19T00:00:00+00:00",
    )

    assert json.loads(path.read_text(encoding="utf-8"))["source"] == source


def test_snapshot_writer_never_overwrites_an_existing_snapshot(tmp_path) -> None:
    response = APIResponse(
        source="sorftime",
        status_code=200,
        request_metadata={},
        payload={"raw": True},
    )
    writer = SnapshotWriter(tmp_path)
    writer.write(
        response,
        snapshot_id="immutable",
        timestamp="2026-08-19T00:00:00Z",
    )

    with pytest.raises(FileExistsError):
        writer.write(
            response,
            snapshot_id="immutable",
            timestamp="2026-08-19T00:00:01Z",
        )


def test_snapshot_rejects_non_json_payload_before_creating_file(tmp_path) -> None:
    with pytest.raises(ValueError, match="payload must be JSON serializable"):
        APIResponse(
            source="xiyou",
            status_code=200,
            request_metadata={},
            payload={"unsupported": object()},
        )

    assert list(tmp_path.iterdir()) == []


def test_snapshot_schema_rejects_api_keys_in_request_metadata() -> None:
    with pytest.raises(ValueError, match="credential field"):
        APIResponse(
            source="xiyou",
            status_code=200,
            request_metadata={"headers": {"X-Api-Key": "must-not-enter"}},
            payload={"ok": True},
        )
