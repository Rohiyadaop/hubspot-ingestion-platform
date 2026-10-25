from __future__ import annotations

from pathlib import Path

from app.job_manager import JobManager
from app.pause_resume import PauseResumeManager
from app.state_manager import StateManager


class FakeStore:
    def __init__(self):
        self.job = {"job_id": "job-1", "status": "running", "checkpoints": {}}

    def get(self, job_id):
        return {
            **self.job,
            "checkpoints": dict(self.job["checkpoints"]),
        }

    def save_checkpoint(self, job_id, resource, cursor):
        if cursor is None:
            self.job["checkpoints"].pop(resource, None)
        else:
            self.job["checkpoints"][resource] = cursor
        return self.get(job_id)


class FakeHubSpotClient:
    def __init__(self):
        self.calls = []

    def fetch_page(self, resource, cursor):
        self.calls.append((resource, cursor))
        if cursor is None:
            return ([{"id": "1"}], "next-page")
        return ([{"id": "2"}], None)


def test_resource_sync_saves_then_clears_resume_cursor(tmp_path: Path, monkeypatch):
    fake_store = FakeStore()
    fake_client = FakeHubSpotClient()
    written = []
    monkeypatch.setattr("app.job_manager.HubSpotClient", lambda: fake_client)
    monkeypatch.setattr(
        "app.job_manager.persist_resource_page",
        lambda resource, page: written.extend((resource, row["id"]) for row in page),
    )
    pause_manager = PauseResumeManager(StateManager(tmp_path / "state.json"))
    manager = JobManager(store=fake_store, pause_manager=pause_manager, poll_interval=0)

    count = manager._sync_resource("job-1", "contacts")

    assert count == 2
    assert fake_client.calls == [("contacts", None), ("contacts", "next-page")]
    assert written == [("contacts", "1"), ("contacts", "2")]
    assert fake_store.job["checkpoints"] == {}
    assert pause_manager.resume_from_checkpoint("contacts") is None
    manager._executor.shutdown(wait=True)


def test_checkpoint_state_is_scoped_to_job(tmp_path: Path):
    pause_manager = PauseResumeManager(StateManager(tmp_path / "state.json"))

    pause_manager.checkpoint("contacts", "cursor-job-a", job_id="job-a")
    pause_manager.checkpoint("contacts", "cursor-job-b", job_id="job-b")

    assert pause_manager.resume_from_checkpoint("contacts", job_id="job-a") == "cursor-job-a"
    assert pause_manager.resume_from_checkpoint("contacts", job_id="job-b") == "cursor-job-b"
    assert pause_manager.resume_from_checkpoint("contacts", job_id="job-c") is None


def test_sync_restores_persisted_job_cursor_when_store_has_none(tmp_path: Path, monkeypatch):
    fake_store = FakeStore()
    fake_client = FakeHubSpotClient()
    monkeypatch.setattr("app.job_manager.HubSpotClient", lambda: fake_client)
    monkeypatch.setattr("app.job_manager.persist_resource_page", lambda resource, page: len(page))
    pause_manager = PauseResumeManager(StateManager(tmp_path / "state.json"))
    pause_manager.checkpoint("contacts", "next-page", job_id="job-1")
    manager = JobManager(store=fake_store, pause_manager=pause_manager, poll_interval=0)

    count = manager._sync_resource("job-1", "contacts")

    assert count == 1
    assert fake_client.calls == [("contacts", "next-page")]
    assert pause_manager.resume_from_checkpoint("contacts", job_id="job-1") is None
    manager._executor.shutdown(wait=True)
