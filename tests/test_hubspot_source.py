from __future__ import annotations

from unittest.mock import Mock

import requests

from app.hubspot_source import HubSpotClient


class FakeResponse:
    def __init__(self, status_code: int, payload: dict, headers: dict | None = None):
        self.status_code = status_code
        self.payload = payload
        self.headers = headers or {}

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            error = requests.HTTPError(f"HTTP {self.status_code}")
            error.response = self
            raise error


def test_mock_pagination_uses_after_cursor():
    session = Mock()
    session.get.return_value = FakeResponse(
        200, {"results": [{"id": "a"}], "paging": {"next": {"after": "a"}}}
    )
    client = HubSpotClient(base_url="http://mock", api_mode="mock", session=session)

    records, cursor = client.fetch_page("contacts")

    assert records == [{"id": "a"}]
    assert cursor == "a"
    assert session.get.call_args.kwargs["params"]["limit"] > 0


def test_retries_429_and_honors_retry_after(monkeypatch):
    session = Mock()
    session.get.side_effect = [
        FakeResponse(429, {}, {"Retry-After": "0"}),
        FakeResponse(200, {"results": [{"id": "1"}], "paging": {"next": None}}),
    ]
    sleeps: list[float] = []
    monkeypatch.setattr("app.hubspot_source.time.sleep", sleeps.append)
    client = HubSpotClient(
        base_url="https://api.hubapi.com",
        access_token="test-token",
        api_mode="hubspot",
        session=session,
        max_retries=1,
    )

    rows, cursor = client.fetch_page("contacts")

    assert rows == [{"id": "1"}]
    assert cursor is None
    assert sleeps == [0.0]
    assert session.get.call_args.kwargs["headers"]["Authorization"] == "Bearer test-token"


def test_retries_transient_connection_errors(monkeypatch):
    session = Mock()
    session.get.side_effect = [
        requests.ConnectionError("temporary network failure"),
        FakeResponse(200, {"results": [{"id": "1"}], "paging": {"next": None}}),
    ]
    sleeps: list[float] = []
    monkeypatch.setattr("app.hubspot_source.time.sleep", sleeps.append)
    client = HubSpotClient(
        base_url="https://api.hubapi.com",
        access_token="test-token",
        session=session,
        max_retries=1,
    )

    rows, cursor = client.fetch_page("contacts")

    assert rows == [{"id": "1"}]
    assert cursor is None
    assert sleeps == [1.0]
    assert session.get.call_count == 2


def test_http_date_retry_after_is_parsed():
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    from app.hubspot_source import HubSpotClient

    response = FakeResponse(429, {}, {"Retry-After": format_datetime(datetime.now(timezone.utc) + timedelta(seconds=12))})
    delay = HubSpotClient._retry_after(response, 0)
    assert 0 <= delay <= 12


def test_legacy_engagement_response_is_normalized():
    session = Mock()
    session.get.return_value = FakeResponse(
        200,
        {
            "results": [
                {
                    "engagement": {"id": 42, "type": "CALL", "timestamp": 123},
                    "associations": {"contactIds": [7]},
                    "metadata": {"subject": "Discovery"},
                }
            ],
            "hasMore": True,
            "offset": 81,
        },
    )
    client = HubSpotClient(base_url="https://api.hubapi.com", access_token="token", session=session)

    records, cursor = client.fetch_page("engagements")

    assert records[0]["id"] == "42"
    assert records[0]["type"] == "CALL"
    assert cursor == "81"
