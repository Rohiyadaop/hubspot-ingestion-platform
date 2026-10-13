from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from app.config import MAX_RESOURCE_WORKERS
from app.hubspot_source import HubSpotClient, RESOURCES
from app.job_store import JobStore
from app.parallel_runner import run_resources
from app.pause_resume import PauseResumeManager
from app.pipeline import persist_resource_page


class JobManager:
    """Coordinates asynchronous ingestion jobs backed by PostgreSQL state."""

    def __init__(
        self,
        store: JobStore | None = None,
        pause_manager: PauseResumeManager | None = None,
        *,
        max_workers: int = MAX_RESOURCE_WORKERS,
        poll_interval: float = 0.5,
    ):
        self.store = store or JobStore()
        self.pause_manager = pause_manager or PauseResumeManager()
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ingestion-job")
        self._submitted: set[str] = set()
        self._lock = threading.Lock()

    def start(self, resources: list[str] | None = None) -> dict[str, Any]:
        job = self.store.create(resources or list(RESOURCES))
        self.submit(job)
        return job

    def submit(self, job: dict[str, Any]) -> None:
        job_id = str(job["job_id"])
        with self._lock:
            if job_id in self._submitted:
                return
            self._submitted.add(job_id)
        self._executor.submit(self._run, job_id)

    def recover(self) -> None:
        self.store.recover_interrupted()
        for job in self.store.list(limit=1000):
            if job["status"] == "queued":
                self.submit(job)

    def _active(self, job_id: str) -> bool:
        """Wait through pause; return false for cancellation or terminal states."""
        while True:
            job = self.store.get(job_id)
            if job is None or job["status"] in {"cancelled", "failed", "completed"}:
                return False
            if job["status"] == "paused":
                time.sleep(self.poll_interval)
                continue
            return job["status"] in {"queued", "running"}

    def _sync_resource(self, job_id: str, resource: str) -> int:
        current = self.store.get(job_id)
        if current is None:
            return 0
        cursor = current.get("checkpoints", {}).get(resource)
        if cursor is None:
            cursor = self.pause_manager.resume_from_checkpoint(resource)

        client = HubSpotClient()
        records_written = 0
        while self._active(job_id):
            page, next_cursor = client.fetch_page(resource, cursor)
            # A cancel/pause received during the request takes effect before commit.
            if not self._active(job_id):
                return records_written
            persist_resource_page(resource, page)
            records_written += len(page)
            self.store.save_checkpoint(job_id, resource, next_cursor)
            self.pause_manager.checkpoint(resource, next_cursor, job_id=job_id)
            if next_cursor is None:
                break
            cursor = next_cursor
        return records_written

    def _run(self, job_id: str) -> None:
        try:
            job = self.store.get(job_id)
            if job is None or job["status"] in {"cancelled", "failed", "completed"}:
                return
            if job["status"] == "queued":
                self.store.set_status(job_id, "running", expected_statuses=["queued"])
            resources = list(job["resources"])
            run_resources(
                resources,
                lambda resource: self._sync_resource(job_id, resource),
                self.max_workers,
            )
            self.store.set_status(job_id, "completed", expected_statuses=["running"])
        except Exception as exc:
            latest = self.store.get(job_id)
            if latest and latest["status"] not in {"cancelled", "failed", "completed"}:
                self.store.set_status(
                    job_id,
                    "failed",
                    error=f"{type(exc).__name__}: {exc}",
                    expected_statuses=[latest["status"]],
                )
        finally:
            with self._lock:
                self._submitted.discard(job_id)
            # If resume raced the current worker's final status check, ensure a
            # fresh worker picks up the now-running job after deregistration.
            latest = self.store.get(job_id)
            if latest and latest["status"] in {"queued", "running"}:
                self.submit(latest)