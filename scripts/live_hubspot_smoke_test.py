"""Validate HubSpot credentials and run a signed contacts-only ingestion smoke test."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid

import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8080").rstrip("/")
API_KEY = os.environ["API_KEY"]
HMAC_SECRET = os.environ["HMAC_SECRET"].encode("utf-8")


def signed_request(method: str, path: str, body: bytes = b"") -> requests.Response:
    timestamp = str(int(time.time()))
    request_id = str(uuid.uuid4())
    body_digest = hashlib.sha256(body).hexdigest()
    message = f"{timestamp}\n{method.upper()}\n{path}\n{request_id}\n{body_digest}".encode()
    signature = hmac.new(HMAC_SECRET, message, hashlib.sha256).hexdigest()
    return requests.request(
        method,
        f"{API_BASE_URL}{path}",
        data=body,
        headers={
            "X-API-Key": API_KEY,
            "X-Timestamp": timestamp,
            "X-Request-Id": request_id,
            "X-Signature": signature,
            "Content-Type": "application/json",
        },
        timeout=30,
    )


def main() -> None:
    health = requests.get(f"{API_BASE_URL}/health", timeout=10)
    health.raise_for_status()
    print(f"Service health: {health.json()}")

    validation = signed_request("POST", "/validate-credentials")
    validation.raise_for_status()
    result = validation.json()
    print(f"HubSpot credential check: {result['message']}")
    if not result.get("valid"):
        raise SystemExit("Credential check failed; verify the private-app token and scopes.")

    body = json.dumps({"resources": ["contacts"]}, separators=(",", ":")).encode()
    started = signed_request("POST", "/jobs", body)
    started.raise_for_status()
    job = started.json()
    job_id = job["job_id"]
    print(f"Started contacts-only job: {job_id}")

    deadline = time.monotonic() + 1800
    while time.monotonic() < deadline:
        time.sleep(2)
        response = signed_request("GET", f"/jobs/{job_id}/status")
        response.raise_for_status()
        status = response.json()
        print(f"Job status: {status['status']}")
        if status["status"] == "completed":
            print("Smoke test passed. Contacts were ingested successfully.")
            return
        if status["status"] in {"failed", "cancelled"}:
            raise SystemExit(f"Smoke test did not complete: {status.get('error') or status['status']}")

    raise SystemExit("Timed out waiting for the ingestion job to finish.")


if __name__ == "__main__":
    main()
