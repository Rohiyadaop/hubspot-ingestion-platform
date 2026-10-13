from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
import requests

from app.config import API_HOST, API_PORT, HUBSPOT_ACCESS_TOKEN, HUBSPOT_API_MODE
from app.hubspot_source import HubSpotClient, RESOURCES
from app.job_manager import JobManager
from app.job_store import ActiveJobExists, JobStore
from app.security import verify_hmac

store = JobStore()
job_manager = JobManager(store=store)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.ensure_schema()
    app.state.job_store = store
    job_manager.recover()
    yield


app = FastAPI(
    title="HubSpot Ingestion Service",
    description="Authenticated control plane for resumable HubSpot ingestion jobs.",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.job_store = store


class StartJobRequest(BaseModel):
    resources: list[str] | None = None

    @field_validator("resources")
    @classmethod
    def validate_resources(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return values
        if not values:
            raise ValueError("resources must contain at least one resource")
        unsupported = sorted(set(values) - set(RESOURCES))
        if unsupported:
            raise ValueError(f"unsupported resources: {', '.join(unsupported)}")
        return list(dict.fromkeys(values))


def _get_job_or_404(job_id: UUID) -> dict[str, Any]:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/health")
def health() -> JSONResponse:
    try:
        store.ping()
    except Exception:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "checks": {"postgres": "unavailable"}},
        )
    return JSONResponse(
        content={
            "status": "ok",
            "checks": {"postgres": "ok"},
            "hubspot_mode": HUBSPOT_API_MODE,
            "hubspot_configured": HUBSPOT_API_MODE == "mock" or bool(HUBSPOT_ACCESS_TOKEN),
        }
    )


@app.post("/jobs", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(verify_hmac)])
def start_job(payload: StartJobRequest) -> dict[str, Any]:
    active = [job for job in store.list(limit=1000) if job["status"] in {"queued", "running", "paused"}]
    if active:
        raise HTTPException(status_code=409, detail="An ingestion job is already active")
    if HUBSPOT_API_MODE != "mock" and not HUBSPOT_ACCESS_TOKEN:
        raise HTTPException(status_code=503, detail="HubSpot access token is not configured")
    try:
        job = job_manager.start(payload.resources)
    except ActiveJobExists as exc:
        raise HTTPException(status_code=409, detail="An ingestion job is already active") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Could not start ingestion job") from exc
    return job


@app.get("/jobs", dependencies=[Depends(verify_hmac)])
def list_jobs(
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0)
) -> dict[str, Any]:
    jobs = store.list(limit=limit, offset=offset)
    return {"jobs": jobs, "limit": limit, "offset": offset}


@app.get("/jobs/{job_id}", dependencies=[Depends(verify_hmac)])
def get_job(job_id: UUID) -> dict[str, Any]:
    return _get_job_or_404(job_id)


@app.get("/jobs/{job_id}/status", dependencies=[Depends(verify_hmac)])
def get_job_status(job_id: UUID) -> dict[str, Any]:
    job = _get_job_or_404(job_id)
    return {"job_id": job["job_id"], "status": job["status"], "error": job["error"]}


@app.post("/jobs/{job_id}/pause", dependencies=[Depends(verify_hmac)])
def pause_job(job_id: UUID) -> dict[str, Any]:
    job = _get_job_or_404(job_id)
    if job["status"] not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail=f"Cannot pause a {job['status']} job")
    changed = store.set_status(job_id, "paused", expected_statuses=[job["status"]])
    if changed is None:
        raise HTTPException(status_code=409, detail="Job state changed; retry the request")
    return changed


@app.post("/jobs/{job_id}/resume", dependencies=[Depends(verify_hmac)])
def resume_job(job_id: UUID) -> dict[str, Any]:
    job = _get_job_or_404(job_id)
    if job["status"] != "paused":
        raise HTTPException(status_code=409, detail=f"Cannot resume a {job['status']} job")
    resumed = store.set_status(job_id, "running", expected_statuses=["paused"])
    if resumed is None:
        raise HTTPException(status_code=409, detail="Job state changed; retry the request")
    job_manager.submit(resumed)
    return resumed


@app.post("/jobs/{job_id}/cancel", dependencies=[Depends(verify_hmac)])
def cancel_job(job_id: UUID) -> dict[str, Any]:
    job = _get_job_or_404(job_id)
    if job["status"] not in {"queued", "running", "paused"}:
        raise HTTPException(status_code=409, detail=f"Cannot cancel a {job['status']} job")
    changed = store.set_status(job_id, "cancelled", expected_statuses=[job["status"]])
    if changed is None:
        raise HTTPException(status_code=409, detail="Job state changed; retry the request")
    return changed


@app.post("/validate-credentials", dependencies=[Depends(verify_hmac)])
def validate_credentials() -> dict[str, Any]:
    try:
        valid = HubSpotClient().validate_credentials()
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else 502
        if code == 401 or code == 403:
            return {"valid": False, "message": "HubSpot rejected the configured access token"}
        raise HTTPException(status_code=502, detail="HubSpot credential validation failed") from exc
    except (requests.RequestException, RuntimeError):
        raise HTTPException(status_code=502, detail="HubSpot credential validation failed") from None
    return {"valid": valid, "message": "HubSpot credentials are valid" if valid else "No access token configured"}


def run() -> None:
    import uvicorn

    uvicorn.run("app.api:app", host=API_HOST, port=API_PORT, reload=False)