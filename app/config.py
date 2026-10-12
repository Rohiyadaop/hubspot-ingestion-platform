from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PARQUET_DIR = DATA_DIR / "parquet" / "hubspot_data"
STATE_FILE = DATA_DIR / "pipeline_state.json"

HUBSPOT_BASE_URL = os.getenv("HUBSPOT_BASE_URL", "http://127.0.0.1:8000")
HUBSPOT_RESOURCE_LIMIT = int(os.getenv("HUBSPOT_RESOURCE_LIMIT", "100"))

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "127.0.0.1")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", "8123"))
CLICKHOUSE_USER = os.getenv("CLICKHOUSE_USER", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "hubspot")

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "127.0.0.1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "hubspot-data")
