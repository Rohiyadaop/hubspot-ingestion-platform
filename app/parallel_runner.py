from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import requests

from app.config import HUBSPOT_BASE_URL, HUBSPOT_RESOURCE_LIMIT


def fetch_resource(resource_name: str, base_url: str = HUBSPOT_BASE_URL, limit: int = HUBSPOT_RESOURCE_LIMIT) -> list[dict[str, Any]]:
    """Fetch all records for one HubSpot resource with paging."""
    records: list[dict[str, Any]] = []
    after: str | None = None

    while True:
        params = {"limit": limit}
        if after:
            params["after"] = after

        response = requests.get(f"{base_url}/{resource_name}", params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()

        batch = payload.get("results", [])
        records.extend(batch)

        next_cursor = payload.get("paging", {}).get("next")
        if not next_cursor:
            break
        after = next_cursor.get("after")

    return records


def fetch_all_resources(resource_names: list[str] | None = None, max_workers: int = 4) -> dict[str, list[dict[str, Any]]]:
    """Fetch resources in parallel and return results keyed by resource name."""
    resources = resource_names or [
        "contacts",
        "companies",
        "deals",
        "tickets",
        "line_items",
        "engagements",
        "pipelines",
        "owners",
    ]

    results: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(fetch_resource, resource_name): resource_name for resource_name in resources
        }
        for future in as_completed(future_map):
            resource_name = future_map[future]
            results[resource_name] = future.result()
    return results
