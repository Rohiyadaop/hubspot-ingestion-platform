from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.config import DATABASE_URL


class ActiveJobExists(Exception):
    """Raised when a second non-terminal ingestion job is requested."""


class JobStore:
    """Small PostgreSQL repository for ingestion job state."""

    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def ensure_schema(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_jobs (
                    job_id UUID PRIMARY KEY,
                    status TEXT NOT NULL CHECK (status IN
                        ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')),
                    resources JSONB NOT NULL,
                    checkpoints JSONB NOT NULL DEFAULT '{}'::jsonb,
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    started_at TIMESTAMPTZ,
                    finished_at TIMESTAMPTZ
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ingestion_jobs_created_idx "
                "ON ingestion_jobs (created_at DESC)"
            )
            connection.execute(
                """CREATE TABLE IF NOT EXISTS api_request_nonces (
                    request_id UUID PRIMARY KEY,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )"""
            )

    @staticmethod
    def _serialize(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        for key in ("job_id",):
            row[key] = str(row[key])
        for key in ("created_at", "updated_at", "started_at", "finished_at"):
            if row.get(key) is not None:
                row[key] = row[key].isoformat()
        return row

    def create(self, resources: list[str]) -> dict[str, Any]:
        job_id = uuid4()
        with self._connect() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(831704219)")
            active = connection.execute(
                "SELECT 1 FROM ingestion_jobs WHERE status = ANY(%s) LIMIT 1",
                (["queued", "running", "paused"],),
            ).fetchone()
            if active:
                raise ActiveJobExists("An ingestion job is already active")
            row = connection.execute(
                """INSERT INTO ingestion_jobs (job_id, status, resources)
                   VALUES (%s, 'queued', %s) RETURNING *""",
                (job_id, Jsonb(resources)),
            ).fetchone()
        return self._serialize(row)  # type: ignore[return-value]

    def get(self, job_id: str | UUID) -> dict[str, Any] | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM ingestion_jobs WHERE job_id = %s", (UUID(str(job_id)),)
            ).fetchone()
        return self._serialize(row)

    def list(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM ingestion_jobs ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset),
            ).fetchall()
        return [self._serialize(row) for row in rows]  # type: ignore[misc]

    def set_status(
        self,
        job_id: str | UUID,
        status: str,
        *,
        error: str | None = None,
        expected_statuses: list[str] | None = None,
    ) -> dict[str, Any] | None:
        where = "job_id = %s"
        parameters: list[Any] = [status, error, status, status, UUID(str(job_id))]
        if expected_statuses is not None:
            where += " AND status = ANY(%s)"
            parameters.append(expected_statuses)
        with self._connect() as connection:
            row = connection.execute(
                f"""UPDATE ingestion_jobs
                   SET status = %s, error = %s, updated_at = NOW(),
                       started_at = CASE WHEN %s = 'running' AND started_at IS NULL
                                         THEN NOW() ELSE started_at END,
                       finished_at = CASE WHEN %s IN ('completed', 'failed', 'cancelled')
                                          THEN NOW() ELSE NULL END
                   WHERE {where} RETURNING *""",
                parameters,
            ).fetchone()
        return self._serialize(row)

    def save_checkpoint(
        self, job_id: str | UUID, resource: str, cursor: str | None
    ) -> dict[str, Any] | None:
        with self._connect() as connection:
            if cursor is None:
                row = connection.execute(
                    """UPDATE ingestion_jobs
                       SET checkpoints = checkpoints - %s, updated_at = NOW()
                       WHERE job_id = %s RETURNING *""",
                    (resource, UUID(str(job_id))),
                ).fetchone()
            else:
                row = connection.execute(
                    """UPDATE ingestion_jobs
                       SET checkpoints = jsonb_set(checkpoints, ARRAY[%s], to_jsonb(%s::text), true),
                           updated_at = NOW()
                       WHERE job_id = %s RETURNING *""",
                    (resource, cursor, UUID(str(job_id))),
                ).fetchone()
        return self._serialize(row)

    def recover_interrupted(self) -> list[dict[str, Any]]:
        """Requeue jobs whose worker was lost when the service stopped."""
        with self._connect() as connection:
            rows = connection.execute(
                """UPDATE ingestion_jobs SET status = 'queued', updated_at = NOW()
                   WHERE status = 'running' RETURNING *"""
            ).fetchall()
        return [self._serialize(row) for row in rows]  # type: ignore[misc]

    def ping(self) -> bool:
        with self._connect() as connection:
            connection.execute("SELECT 1")
        return True

    def consume_request_id(self, request_id: UUID) -> bool:
        """Persist a signed request ID once; prevents replay across processes/restarts."""
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM api_request_nonces WHERE created_at < NOW() - INTERVAL '1 day'"
            )
            row = connection.execute(
                """INSERT INTO api_request_nonces (request_id) VALUES (%s)
                   ON CONFLICT DO NOTHING RETURNING request_id""",
                (request_id,),
            ).fetchone()
        return row is not None