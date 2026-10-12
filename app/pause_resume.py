from __future__ import annotations

from app.state_manager import StateManager


class PauseResumeManager:
    """Very small checkpoint helper for incremental ingestion jobs."""

    def __init__(self, state_manager: StateManager | None = None):
        self.state_manager = state_manager or StateManager()

    def checkpoint(self, resource_name: str, cursor: str | None = None, **extra) -> None:
        self.state_manager.set_resource_state(resource_name, cursor=cursor, **extra)

    def get_checkpoint(self, resource_name: str) -> dict[str, object]:
        return self.state_manager.get_resource_state(resource_name)

    def resume_from_checkpoint(self, resource_name: str) -> str | None:
        checkpoint = self.get_checkpoint(resource_name)
        return checkpoint.get("cursor")
