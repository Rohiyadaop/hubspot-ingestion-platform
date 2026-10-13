from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
PARQUET_DIR = DATA_DIR / "parquet" / "hubspot_data"
STATE_FILE = DATA_DIR / "pipeline_state.json"

DATABASE_URL = os.getenv(
	"DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/hubspot_ingestion"
)
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8080"))
API_KEY = os.getenv("API_KEY", "")
HMAC_SECRET = os.getenv("HMAC_SECRET", "")
HMAC_MAX_CLOCK_SKEW_SECONDS = int(os.getenv("HMAC_MAX_CLOCK_SKEW_SECONDS", "300"))

HUBSPOT_BASE_URL = os.getenv("HUBSPOT_BASE_URL", "https://api.hubapi.com").rstrip("/")
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN", "")
HUBSPOT_API_MODE = os.getenv("HUBSPOT_API_MODE", "hubspot").lower()
HUBSPOT_RESOURCE_LIMIT = int(os.getenv("HUBSPOT_RESOURCE_LIMIT", "100"))
HUBSPOT_MAX_RETRIES = int(os.getenv("HUBSPOT_MAX_RETRIES", "8"))
HUBSPOT_TIMEOUT_SECONDS = float(os.getenv("HUBSPOT_TIMEOUT_SECONDS", "30"))
MAX_RESOURCE_WORKERS = int(os.getenv("MAX_RESOURCE_WORKERS", "4"))

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "127.0.0.1")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "hubspot")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "hubspot-data")
