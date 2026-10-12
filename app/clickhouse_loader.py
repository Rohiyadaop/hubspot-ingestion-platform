from __future__ import annotations

from pathlib import Path

import clickhouse_connect
import pandas as pd

from app.config import CLICKHOUSE_DATABASE, CLICKHOUSE_HOST, CLICKHOUSE_PASSWORD, CLICKHOUSE_PORT, CLICKHOUSE_USER, PARQUET_DIR


def get_client():
    return clickhouse_connect.get_client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD,
        database=CLICKHOUSE_DATABASE,
    )


def _column_type(series: pd.Series) -> str:
    if pd.api.types.is_integer_dtype(series):
        return "Nullable(Int64)"
    if pd.api.types.is_float_dtype(series):
        return "Nullable(Float64)"
    if pd.api.types.is_bool_dtype(series):
        return "Nullable(Bool)"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "Nullable(DateTime64(3))"
    return "Nullable(String)"


def _safe_name(column_name: str) -> str:
    return str(column_name).replace("-", "_").replace(" ", "_").replace(".", "_")


def load_resource(resource_name: str, client=None) -> int:
    resource_dir = PARQUET_DIR / resource_name
    if not resource_dir.exists():
        return 0

    files = sorted(resource_dir.glob("*.parquet"))
    if not files:
        return 0

    frames = [pd.read_parquet(file) for file in files]
    df = pd.concat(frames, ignore_index=True)

    if "id" in df.columns:
        df = df.drop_duplicates(subset=["id"], keep="last")

    if client is None:
        client = get_client()

    columns_sql = ", ".join(
        f"`{_safe_name(column)}` {_column_type(df[column])}" for column in df.columns
    )
    table_name = resource_name
    client.command(
        f"CREATE TABLE IF NOT EXISTS {CLICKHOUSE_DATABASE}.{table_name} ({columns_sql}) ENGINE = MergeTree ORDER BY tuple()"
    )

    client.insert(
        database=CLICKHOUSE_DATABASE,
        table=table_name,
        data=df.to_dict(orient="records"),
    )
    return len(df)


def load_all_resources(resource_names: list[str] | None = None) -> dict[str, int]:
    names = resource_names or [
        "contacts",
        "companies",
        "deals",
        "tickets",
        "line_items",
        "engagements",
        "pipelines",
        "owners",
    ]
    client = get_client()
    results: dict[str, int] = {}
    for resource_name in names:
        results[resource_name] = load_resource(resource_name, client=client)
    return results
