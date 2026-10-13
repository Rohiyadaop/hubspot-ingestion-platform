from __future__ import annotations

import hashlib
import hmac
import time
from uuid import UUID

from fastapi import HTTPException, Request

from app.config import API_KEY, HMAC_MAX_CLOCK_SKEW_SECONDS, HMAC_SECRET


def build_signature(
    method: str, path_and_query: str, timestamp: str, request_id: str, body: bytes
) -> str:
    body_digest = hashlib.sha256(body).hexdigest()
    message = (
        f"{timestamp}\n{method.upper()}\n{path_and_query}\n{request_id}\n{body_digest}"
    ).encode()
    return hmac.new(HMAC_SECRET.encode(), message, hashlib.sha256).hexdigest()


async def verify_hmac(request: Request) -> None:
    """FastAPI dependency enforcing a timestamped, body-bound HMAC."""
    supplied_key = request.headers.get("X-API-Key", "")
    timestamp = request.headers.get("X-Timestamp", "")
    supplied_request_id = request.headers.get("X-Request-Id", "")
    supplied_signature = request.headers.get("X-Signature", "")
    if not API_KEY or not HMAC_SECRET:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    if not hmac.compare_digest(supplied_key, API_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    try:
        timestamp_value = int(timestamp)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid request timestamp") from exc
    if abs(time.time() - timestamp_value) > HMAC_MAX_CLOCK_SKEW_SECONDS:
        raise HTTPException(status_code=401, detail="Request timestamp expired")
    try:
        request_id = UUID(supplied_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid request ID") from exc

    body = await request.body()
    path_and_query = request.url.path
    if request.url.query:
        path_and_query += f"?{request.url.query}"
    expected = build_signature(
        request.method, path_and_query, timestamp, str(request_id), body
    )
    if not supplied_signature or not hmac.compare_digest(supplied_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid request signature")
    job_store = getattr(request.app.state, "job_store", None)
    if job_store is None or not job_store.consume_request_id(request_id):
        raise HTTPException(status_code=401, detail="Request ID was already used")