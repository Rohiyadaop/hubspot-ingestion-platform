# HubSpot Ingestion Platform

This project builds a lightweight HubSpot ingestion and analytics flow that pulls CRM data from a local mock API, stores it in parquet files using `dlt`, and prepares it for downstream storage or BI consumption.

## What is included

- Mock HubSpot API for local testing
- Incremental ingestion pipeline using `dlt`
- Parquet storage in `data/parquet/hubspot_data`
- State management for pause/resume checkpoints
- Parallel resource fetching for faster ingestion
- MinIO upload helper
- ClickHouse loading helper
- SQL view for pipeline-level deal analysis

## Quick start

1. Create and activate the virtual environment if needed.
2. Install dependencies:
   python -m pip install -r requirements.txt
3. Start the mock API:
   python main.py mock
4. In a second terminal, run the pipeline:
   python main.py pipeline
5. Check saved state:
   python main.py status

## Optional downstream storage

Upload parquet files to MinIO:

python main.py minio

Load the parquet tables into ClickHouse:

python main.py clickhouse

## Project layout

- `app/` - ingestion and orchestration modules
- `mock_hubspot/` - local development API used during testing
- `data/` - generated parquet output and preview CSVs
- `views/` - analytical SQL definitions
- `main.py` - command entry point

## Submission status

The project is functional and ready for end-to-end validation with the local mock HubSpot source. The generated parquet output is already compatible with downstream analytics workloads and can be used for demo, project submission, or further extension.
