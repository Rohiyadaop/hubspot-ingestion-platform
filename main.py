from __future__ import annotations

import argparse


def start_mock_api() -> None:
    import uvicorn

    from mock_hubspot.server import app

    uvicorn.run(app, host="127.0.0.1", port=8000)


def run_pipeline() -> None:
    from app.pipeline import run_pipeline as execute_pipeline

    execute_pipeline()


def load_clickhouse() -> None:
    from app.clickhouse_loader import load_all_resources

    print(load_all_resources())


def load_minio() -> None:
    from app.minio_storage import upload_directory

    from app.config import PARQUET_DIR

    print(upload_directory(PARQUET_DIR, prefix="hubspot/"))


def show_status() -> None:
    from app.config import STATE_FILE

    print(f"State file: {STATE_FILE}")
    if STATE_FILE.exists():
        print(STATE_FILE.read_text(encoding="utf-8"))
    else:
        print("No pipeline state file generated yet.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HubSpot ingestion platform control panel")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("mock", help="Start the local mock HubSpot API")
    subparsers.add_parser("pipeline", help="Run the dlt ingestion pipeline")
    subparsers.add_parser("clickhouse", help="Load parquet files into ClickHouse")
    subparsers.add_parser("minio", help="Upload parquet files into MinIO")
    subparsers.add_parser("status", help="Inspect the pipeline state file")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    if args.command == "mock":
        start_mock_api()
    elif args.command == "pipeline":
        run_pipeline()
    elif args.command == "clickhouse":
        load_clickhouse()
    elif args.command == "minio":
        load_minio()
    elif args.command == "status":
        show_status()


if __name__ == "__main__":
    main()
