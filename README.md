# HubSpot Data Ingestion Service

FastAPI control plane and resumable worker for importing HubSpot CRM resources into per-resource Parquet snapshots. PostgreSQL stores job status and page cursors. The API supports authenticated job creation, status/listing, pause, resume, cancellation, credential validation, and health checks.

## Run locally with Docker

Requirements: Docker Desktop / Docker Engine with Compose.

1. Copy `.env.example` to `.env`; replace `API_KEY`, `HMAC_SECRET`, and `POSTGRES_PASSWORD` with unique values. Keep `HUBSPOT_API_MODE=mock` for local development.
2. Start the service and mock HubSpot API:

   ```sh
   docker compose --profile mock up --build
   ```

3. Check `http://localhost:8080/health`; interactive API documentation is at `http://localhost:8080/docs`.
4. Stop with Ctrl+C, then run `docker compose --profile mock down`. Persistent PostgreSQL and Parquet data are held in named volumes.

To connect to a real HubSpot private app, set `HUBSPOT_API_MODE=hubspot`, `HUBSPOT_BASE_URL=https://api.hubapi.com`, and `HUBSPOT_ACCESS_TOKEN` in `.env`, then start without the mock profile. Grant the token the CRM scopes required for the selected resources. Do not commit `.env` or expose the token.

## API

Control-plane endpoints require `X-API-Key`, `X-Timestamp`, `X-Request-Id`, and `X-Signature`. `X-Signature` is the lowercase hex HMAC-SHA256 of this UTF-8 message, using `HMAC_SECRET` as the key:

```text
timestamp + "\n" + uppercase_method + "\n" + path_and_query + "\n" + request_id + "\n" + lowercase_hex_sha256(raw_request_body)
```

For an empty body, hash the empty byte string. The timestamp is Unix seconds and must be within `HMAC_MAX_CLOCK_SKEW_SECONDS`; each UUID request ID is accepted only once. The unauthenticated `/health` endpoint is intended for container health checks. See `app/security.py` for the canonical signing implementation.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/jobs` | Start an ingestion job; optional JSON body `{"resources":["contacts","deals"]}`. Omit resources to ingest all supported resources. Returns `202`. |
| `GET` | `/jobs` | List jobs; supports `limit` and `offset`. |
| `GET` | `/jobs/{job_id}` | Get job details including resource checkpoints. |
| `GET` | `/jobs/{job_id}/status` | Get job status and error, if any. |
| `POST` | `/jobs/{job_id}/pause` | Pause at a page boundary. |
| `POST` | `/jobs/{job_id}/resume` | Resume from the saved cursor. |
| `POST` | `/jobs/{job_id}/cancel` | Cancel an active job. |
| `POST` | `/validate-credentials` | Check the configured HubSpot credentials. |
| `GET` | `/health` | Report service/PostgreSQL health and HubSpot configuration. |

Jobs are single-active-job per service database. Invalid resources return `422`; missing jobs return `404`; conflicting state transitions return `409`. Control requests with missing/invalid/replayed signatures are rejected.

## Ingestion behavior

- Supported resources: contacts, companies, deals, tickets, line items, engagements, pipelines, and owners.
- HubSpot requests use bearer-token authentication. HTTP `429` honors numeric or HTTP-date `Retry-After`; transient `5xx`, connection, and timeout failures use bounded exponential backoff.
- Each successful page is merged into `data/parquet/hubspot_data/<resource>/snapshot.parquet`, deduplicated by record ID, and atomically replaced. Re-running a job therefore updates records instead of appending duplicates.
- PostgreSQL persists job state and per-resource cursors. Pages are written before their next cursor is committed, so a crash may safely replay a page; ID-based upsert makes that replay idempotent. Interrupted `running` jobs are requeued on service startup.
- Resources are processed concurrently, bounded by `MAX_RESOURCE_WORKERS`. Pause takes effect between page requests/commits; resume uses durable PostgreSQL checkpoints.

## Configuration

See `.env.example` for the Docker environment. Important settings include `DATABASE_URL`, `API_KEY`, `HMAC_SECRET`, `HMAC_MAX_CLOCK_SKEW_SECONDS`, `HUBSPOT_API_MODE`, `HUBSPOT_BASE_URL`, `HUBSPOT_ACCESS_TOKEN`, `HUBSPOT_MAX_RETRIES`, `HUBSPOT_TIMEOUT_SECONDS`, `HUBSPOT_RESOURCE_LIMIT`, `MAX_RESOURCE_WORKERS`, and `DATA_DIR`.

## Tests

Install the platform-independent dependencies in `requirements.txt`, then run `pytest`. Tests cover API authentication and job controls, retry behavior, cursor persistence, and Parquet upsert semantics. PostgreSQL integration and real HubSpot access require their respective services/credentials; the unit tests use fakes and temporary storage.