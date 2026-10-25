from __future__ import annotations

from app.state_manager import StateManager


class PauseResumeManager:
    """Very small checkpoint helper for incremental ingestion jobs."""

    def __init__(self, state_manager: StateManager | None = None):
        self.state_manager = state_manager or StateManager()

    def checkpoint(
        self,
        resource_name: str,
        cursor: str | None = None,
        *,
        job_id: str | None = None,
        **extra: object,
    ) -> None:
        if cursor is None:
            extra["clear_cursor"] = True
        self.state_manager.set_resource_state(
            resource_name, cursor=cursor, job_id=job_id, **extra
        )

    def get_checkpoint(
        self, resource_name: str, *, job_id: str | None = None
    ) -> dict[str, object]:
        return self.state_manager.get_resource_state(resource_name, job_id=job_id)

    def resume_from_checkpoint(
        self, resource_name: str, *, job_id: str | None = None
    ) -> str | None:
        checkpoint = self.get_checkpoint(resource_name, job_id=job_id)
        return checkpoint.get("cursor")
