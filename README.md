# HubSpot Ingestion Service

An API-driven HubSpot CRM ingestion service. FastAPI accepts and controls jobs, PostgreSQL stores durable job state, and resource data is written as ID-upserted Parquet snapshots. A local HubSpot-compatible mock is included for development; production mode calls the HubSpot API with a private-app access token.

## Run with Docker Compose

1. Copy `.env.example` to `.env` and set unique, high-entropy values for `API_KEY`, `HMAC_SECRET`, and `POSTGRES_PASSWORD`.
2. Run `docker compose --profile mock up --build` for local development.
3. The API is available at `http://localhost:8080`; interactive schema docs are at `/docs`. The mock source is at `http://localhost:8000`.
4. Confirm service readiness with `GET /health` (health is intentionally unsigned).

PostgreSQL stores the `ingestion_jobs` and replay-protection tables; the `postgres-data` volume survives container restarts. PostgreSQL is not published on the host. `ingestion-data` holds the Parquet snapshots and local checkpoint metadata. ClickHouse and MinIO are optional and available under the `analytics` Compose profile.

For a local Python run, install `requirements.txt`, start PostgreSQL, configure `DATABASE_URL`, `API_KEY`, and `HMAC_SECRET`, then run `python main.py serve`. For the included mock, set `HUBSPOT_API_MODE=mock` and `HUBSPOT_BASE_URL=http://127.0.0.1:8000`; start it separately with `python main.py mock`.

## HubSpot configuration

The example environment selects the mock and the mock Compose profile. For production, set:

```dotenv
HUBSPOT_API_MODE=hubspot
HUBSPOT_BASE_URL=https://api.hubapi.com
HUBSPOT_ACCESS_TOKEN=<HubSpot private-app token>
```

Do not enable the `mock` Compose profile in production. The mock has no dependency on the API service and is not exposed unless that profile is explicitly enabled.

Keep the token in environment/secret storage, never in source control or API request bodies. Credential validation makes a lightweight authenticated HubSpot request and does not return or log the token. The client uses bearer authentication, paginates resource endpoints, retries HTTP 429 and transient 5xx responses, and honors both numeric and HTTP-date `Retry-After` headers. Retry count and request timeout are configurable using `HUBSPOT_MAX_RETRIES` and `HUBSPOT_TIMEOUT_SECONDS`.

## API

All routes except `GET /health` require HMAC authentication. Send `X-API-Key`, `X-Timestamp` (Unix seconds), and `X-Signature` (lowercase hex HMAC-SHA256). The signed UTF-8 message is:

```text
<timestamp>\n<HTTP method uppercase>\n<path plus raw query string>\n<request UUID>\n<SHA256 hex digest of exact request body>
```

The signature is `HMAC-SHA256(HMAC_SECRET, message)`. Timestamps outside `HMAC_MAX_CLOCK_SKEW_SECONDS` (default 300 seconds) are rejected. Every request must have a fresh unique UUID in `X-Request-Id`; used request IDs are stored in PostgreSQL and rejected on replay across restarts. Compare signatures in constant time. Use HTTPS in deployed environments and rotate both API key and signing secret. Example signature generation:

```python
import hashlib, hmac, time, uuid

timestamp = str(int(time.time()))
request_id = str(uuid.uuid4())
body = b'{"resources":["contacts","deals"]}'
path = "/jobs"
message = f"{timestamp}\nPOST\n{path}\n{request_id}\n{hashlib.sha256(body).hexdigest()}".encode()
signature = hmac.new(b"YOUR_HMAC_SECRET", message, hashlib.sha256).hexdigest()
```

Include `X-Request-Id: <request_id>` with the other signature headers.

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | API and PostgreSQL readiness |
| `POST` | `/jobs` | Start an ingestion job; optional body `{"resources":["contacts"]}`; defaults to all resources |
| `GET` | `/jobs` | List jobs; supports `limit` and `offset` |
| `GET` | `/jobs/{job_id}` | Job details, resources, checkpoints, timestamps, and error |
| `GET` | `/jobs/{job_id}/status` | Current status |
| `POST` | `/jobs/{job_id}/pause` | Pause at a resource page boundary |
| `POST` | `/jobs/{job_id}/resume` | Continue from persisted cursors |
| `POST` | `/jobs/{job_id}/cancel` | Cancel at a safe page boundary |
| `POST` | `/validate-credentials` | Validate configured source credentials without disclosing them |

Job statuses are `queued`, `running`, `paused`, `completed`, `failed`, and `cancelled`. Only one non-terminal job is accepted at a time. A service restart requeues interrupted `running` jobs; `paused` jobs remain paused until explicitly resumed.

## Checkpointing and idempotency

Each resource is fetched independently using the parallel resource runner. After a page is fetched, records are merged by `id` into that resource's `snapshot.parquet` using a temporary file and atomic replace; only then is the opaque source cursor saved to PostgreSQL and `data/pipeline_state.json`. If a crash occurs between data commit and cursor commit, the page is replayed and the ID upsert prevents duplicate records. Pause and cancel are observed at page boundaries. A completed full traversal clears its cursor, so the next job scans again and updates existing IDs instead of appending duplicates.

## Development and tests

Run tests with `pytest`. Tests mock external APIs and storage; an integration run requires the Compose services. Set `HUBSPOT_BASE_URL` to the mock service hostname inside Compose (`http://mock-hubspot:8000`), not loopback. Resource results are stored under `data/parquet/hubspot_data/<resource>/snapshot.parquet`.

The helper scripts for optional analytics remain available: `python main.py minio` and `python main.py clickhouse`.