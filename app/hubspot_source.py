from __future__ import annotations

import email.utils
import time
from datetime import datetime, timezone
from typing import Any

import requests

from app.config import (
    HUBSPOT_ACCESS_TOKEN,
    HUBSPOT_API_MODE,
    HUBSPOT_BASE_URL,
    HUBSPOT_MAX_RETRIES,
    HUBSPOT_RESOURCE_LIMIT,
    HUBSPOT_TIMEOUT_SECONDS,
)

RESOURCES = (
    "contacts",
    "companies",
    "deals",
    "tickets",
    "line_items",
    "engagements",
    "pipelines",
    "owners",
)

HUBSPOT_PATHS = {
    "contacts": "/crm/v3/objects/contacts",
    "companies": "/crm/v3/objects/companies",
    "deals": "/crm/v3/objects/deals",
    "tickets": "/crm/v3/objects/tickets",
    "line_items": "/crm/v3/objects/line_items",
    "engagements": "/engagements/v1/engagements/paged",
    "pipelines": "/crm/v3/pipelines/deals",
    "owners": "/crm/v3/owners",
}


class HubSpotClient:
    """Small HubSpot API client; each page is committed by the job worker."""

    def __init__(
        self,
        *,
        base_url: str = HUBSPOT_BASE_URL,
        access_token: str = HUBSPOT_ACCESS_TOKEN,
        api_mode: str = HUBSPOT_API_MODE,
        session: requests.Session | None = None,
        max_retries: int = HUBSPOT_MAX_RETRIES,
        timeout: float = HUBSPOT_TIMEOUT_SECONDS,
    ):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.api_mode = api_mode
        self.session = session or requests.Session()
        self.max_retries = max_retries
        self.timeout = timeout

    def _path(self, resource: str) -> str:
        if resource not in RESOURCES:
            raise ValueError(f"Unsupported HubSpot resource: {resource}")
        if self.api_mode == "mock":
            return f"/{resource}"
        return HUBSPOT_PATHS[resource]

    @staticmethod
    def _retry_after(response: requests.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return max(0.0, float(value))
            except ValueError:
                try:
                    retry_at = email.utils.parsedate_to_datetime(value)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=timezone.utc)
                    return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(2**attempt, 60.0)

    def _get(self, path: str, params: dict[str, Any] | None = None) -> requests.Response:
        headers = {"Accept": "application/json"}
        if self.api_mode != "mock":
            if not self.access_token:
                raise RuntimeError("HUBSPOT_ACCESS_TOKEN is required for HubSpot API mode")
            headers["Authorization"] = f"Bearer {self.access_token}"

        for attempt in range(self.max_retries + 1):
            response = self.session.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt < self.max_retries:
                    time.sleep(self._retry_after(response, attempt))
                    continue
            response.raise_for_status()
            return response
        raise RuntimeError("HubSpot retry loop ended unexpectedly")

    def fetch_page(self, resource: str, after: str | None = None) -> tuple[list[dict[str, Any]], str | None]:
        path = self._path(resource)
        if self.api_mode == "mock":
            params: dict[str, Any] = {"limit": min(HUBSPOT_RESOURCE_LIMIT, 100)}
            if after:
                params["after"] = after
        elif resource == "engagements":
            params = {"limit": min(HUBSPOT_RESOURCE_LIMIT, 250)}
            if after:
                params["offset"] = after
        elif resource == "pipelines":
            params = {}
        else:
            params = {"limit": min(HUBSPOT_RESOURCE_LIMIT, 100)}
            if after:
                params["after"] = after

        payload = self._get(path, params).json()
        results = payload.get("results", [])
        if resource == "engagements":
            normalized = []
            for result in results:
                engagement = result.get("engagement", result)
                if not isinstance(engagement, dict):
                    continue
                item = dict(engagement)
                item["id"] = str(engagement.get("id", result.get("id", "")))
                for key in ("associations", "metadata"):
                    if key in result:
                        item[key] = result[key]
                normalized.append(item)
            results = normalized
        if resource == "pipelines" and isinstance(results, list):
            # Pipeline metadata is a complete small collection, not cursor paged.
            return results, None
        next_page = payload.get("paging", {}).get("next")
        cursor = next_page.get("after") if isinstance(next_page, dict) else None
        if resource == "engagements" and payload.get("hasMore"):
            cursor = str(payload.get("offset", "")) or None
        return results, str(cursor) if cursor is not None else None

    def validate_credentials(self) -> bool:
        if self.api_mode == "mock":
            self._get("/health")
        else:
            if not self.access_token:
                return False
            self._get("/crm/v3/objects/contacts", {"limit": 1})
        return True