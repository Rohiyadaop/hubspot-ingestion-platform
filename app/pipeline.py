from __future__ import annotations

import os
import json
import threading
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import PARQUET_DIR
from app.hubspot_source import HubSpotClient, RESOURCES

_resource_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(resource: str) -> threading.Lock:
    with _locks_guard:
        return _resource_locks.setdefault(resource, threading.Lock())


def persist_resource_page(
    resource_name: str,
    records: list[dict[str, Any]],
    output_dir: str | Path = PARQUET_DIR,
) -> int:
    """Atomically merge one fetched page into a per-resource Parquet snapshot."""
    if not records:
        return 0
    if any("id" not in record for record in records):
        raise ValueError(f"Every {resource_name} record must include an id")

    normalized_records: list[dict[str, Any]] = []
    for record in records:
        properties = record.get("properties")
        normalized = {key: value for key, value in record.items() if key != "properties"}
        if isinstance(properties, dict):
            normalized.update(properties)
        for key, value in list(normalized.items()):
            if isinstance(value, (dict, list)):
                normalized[key] = json.dumps(value, sort_keys=True, default=str)
        normalized_records.append(normalized)

    directory = Path(output_dir) / resource_name
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = directory / "snapshot.parquet"
    temporary = directory / f".snapshot-{uuid.uuid4().hex}.tmp.parquet"

    with _lock_for(f"{Path(output_dir).resolve()}:{resource_name}"):
        parquet_files = sorted(directory.glob("*.parquet"))
        frames = [pd.read_parquet(path) for path in parquet_files]
        frames.append(pd.DataFrame.from_records(normalized_records))
        combined = pd.concat(frames, ignore_index=True, sort=False)
        combined["id"] = combined["id"].astype(str)
        combined = combined.drop_duplicates(subset=["id"], keep="last")
        try:
            combined.to_parquet(temporary, index=False)
            os.replace(temporary, snapshot)
        finally:
            if temporary.exists():
                temporary.unlink()

        # Older dlt outputs are folded into the new snapshot before removal.
        for path in parquet_files:
            if path != snapshot and path.exists():
                path.unlink()
    return len(records)


def run_pipeline(resources: list[str] | None = None) -> dict[str, int]:
    """Run a one-shot full extraction for local/manual use."""
    client = HubSpotClient()
    counts: dict[str, int] = {}
    for resource in resources or list(RESOURCES):
        cursor = None
        count = 0
        while True:
            page, next_cursor = client.fetch_page(resource, cursor)
            persist_resource_page(resource, page)
            count += len(page)
            if not next_cursor:
                break
            cursor = next_cursor
        counts[resource] = count
    return counts