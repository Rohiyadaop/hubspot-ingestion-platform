from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any

from app.config import STATE_FILE


class StateManager:
    """Persist small pipeline metadata and resumable checkpoints."""

    def __init__(self, state_file: str | Path = STATE_FILE):
        self.state_file = Path(state_file)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        if not self.state_file.exists():
            return {}

        try:
            with self.state_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
                return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, payload: dict[str, Any]) -> None:
        with self._lock:
            current = self.load()
            current.update(payload)
            fd, temporary_name = tempfile.mkstemp(
                prefix=f"{self.state_file.name}.", suffix=".tmp", dir=self.state_file.parent
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as file:
                    json.dump(current, file, indent=2, sort_keys=True)
                    file.write("\n")
                os.replace(temporary_name, self.state_file)
            finally:
                if os.path.exists(temporary_name):
                    os.unlink(temporary_name)

    def set_resource_state(self, resource_name: str, cursor: str | None = None, **extra: Any) -> None:
        with self._lock:
            state = self.load()
            resource_state = state.setdefault("resources", {}).setdefault(resource_name, {})
            if cursor is not None:
                resource_state["cursor"] = cursor
            if extra.pop("clear_cursor", False):
                resource_state.pop("cursor", None)
            resource_state.update(extra)
            self.save(state)

    def get_resource_state(self, resource_name: str) -> dict[str, Any]:
        return self.load().get("resources", {}).get(resource_name, {})

    def clear(self) -> None:
        if self.state_file.exists():
            self.state_file.unlink()
