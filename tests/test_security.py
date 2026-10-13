from __future__ import annotations

import time
from uuid import uuid4

from fastapi.testclient import TestClient

from app import api
from app.config import API_KEY
from app.security import build_signature


class FakeStore:
    def __init__(self):
        self.job = {
            "job_id": "11111111-1111-4111-8111-111111111111",
            "status": "running",
            "resources": ["contacts"],
            "checkpoints": {},
            "error": None,
        }
        self.request_ids = set()

    def ensure_schema(self):
        pass

    def recover_interrupted(self):
        return []

    def ping(self):
        return True

    def consume_request_id(self, request_id):
        if request_id in self.request_ids:
            return False
        self.request_ids.add(request_id)
        return True

    def get(self, job_id):
        return dict(self.job) if str(job_id) == self.job["job_id"] else None

    def list(self, limit=50, offset=0):
        return [dict(self.job)][offset : offset + limit]

    def set_status(self, job_id, status, error=None, expected_statuses=None):
        if expected_statuses and self.job["status"] not in expected_statuses:
            return None
        self.job["status"] = status
        self.job["error"] = error
        return dict(self.job)


class FakeManager:
    def __init__(self, store):
        self.store = store
        self.submitted = []

    def start(self, resources=None):
        self.store.job["status"] = "queued"
        self.store.job["resources"] = resources or ["contacts"]
        return dict(self.store.job)

    def submit(self, job):
        self.submitted.append(job)


def signed_headers(method: str, path: str, body: bytes = b"") -> dict[str, str]:
    timestamp = str(int(time.time()))
    request_id = str(uuid4())
    return {
        "X-API-Key": API_KEY,
        "X-Timestamp": timestamp,
        "X-Request-Id": request_id,
        "X-Signature": build_signature(method, path, timestamp, request_id, body),
    }


def test_unsigned_control_request_is_rejected(monkeypatch):
    fake_store = FakeStore()
    monkeypatch.setattr(api, "store", fake_store)
    monkeypatch.setattr(api.app.state, "job_store", fake_store)
    client = TestClient(api.app)

    response = client.get("/jobs")

    assert response.status_code == 401


def test_signed_list_jobs_succeeds(monkeypatch):
    fake_store = FakeStore()
    monkeypatch.setattr(api, "store", fake_store)
    monkeypatch.setattr(api.app.state, "job_store", fake_store)
    client = TestClient(api.app)
    headers = signed_headers("GET", "/jobs")

    response = client.get("/jobs", headers=headers)

    assert response.status_code == 200
    assert response.json()["jobs"][0]["status"] == "running"


def test_bad_signature_is_rejected(monkeypatch):
    monkeypatch.setattr(api, "store", FakeStore())
    monkeypatch.setattr(api.app.state, "job_store", api.store)
    client = TestClient(api.app)
    headers = signed_headers("GET", "/jobs")
    headers["X-Signature"] = "0" * 64

    response = client.get("/jobs", headers=headers)

    assert response.status_code == 401


def test_health_is_unsigned_and_reports_database(monkeypatch):
    monkeypatch.setattr(api, "store", FakeStore())
    monkeypatch.setattr(api.app.state, "job_store", api.store)
    response = TestClient(api.app).get("/health")

    assert response.status_code == 200
    assert response.json()["checks"]["postgres"] == "ok"


def test_start_job_accepts_signed_request(monkeypatch):
    fake_store = FakeStore()
    fake_store.job["status"] = "completed"
    manager = FakeManager(fake_store)
    monkeypatch.setattr(api, "store", fake_store)
    monkeypatch.setattr(api.app.state, "job_store", fake_store)
    monkeypatch.setattr(api, "job_manager", manager)
    monkeypatch.setattr(api, "HUBSPOT_API_MODE", "mock")
    body = b'{"resources":["contacts"]}'
    response = TestClient(api.app).post(
        "/jobs", content=body,
        headers={**signed_headers("POST", "/jobs", body), "Content-Type": "application/json"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_job_pause_resume_cancel_and_status_routes(monkeypatch):
    fake_store = FakeStore()
    manager = FakeManager(fake_store)
    monkeypatch.setattr(api, "store", fake_store)
    monkeypatch.setattr(api.app.state, "job_store", fake_store)
    monkeypatch.setattr(api, "job_manager", manager)
    client = TestClient(api.app)
    job_id = fake_store.job["job_id"]

    response = client.post(f"/jobs/{job_id}/pause", headers=signed_headers("POST", f"/jobs/{job_id}/pause"))
    assert response.status_code == 200 and response.json()["status"] == "paused"
    response = client.post(f"/jobs/{job_id}/resume", headers=signed_headers("POST", f"/jobs/{job_id}/resume"))
    assert response.status_code == 200 and response.json()["status"] == "running"
    assert len(manager.submitted) == 1
    response = client.get(f"/jobs/{job_id}/status", headers=signed_headers("GET", f"/jobs/{job_id}/status"))
    assert response.status_code == 200 and response.json()["status"] == "running"
    response = client.post(f"/jobs/{job_id}/cancel", headers=signed_headers("POST", f"/jobs/{job_id}/cancel"))
    assert response.status_code == 200 and response.json()["status"] == "cancelled"


def test_validate_credentials_route(monkeypatch):
    class ValidClient:
        def validate_credentials(self):
            return True

    monkeypatch.setattr(api, "HubSpotClient", ValidClient)
    response = TestClient(api.app).post(
        "/validate-credentials", headers=signed_headers("POST", "/validate-credentials")
    )

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_replayed_request_id_is_rejected(monkeypatch):
    fake_store = FakeStore()
    monkeypatch.setattr(api, "store", fake_store)
    monkeypatch.setattr(api.app.state, "job_store", fake_store)
    client = TestClient(api.app)
    headers = signed_headers("GET", "/jobs")

    assert client.get("/jobs", headers=headers).status_code == 200
    assert client.get("/jobs", headers=headers).status_code == 401
