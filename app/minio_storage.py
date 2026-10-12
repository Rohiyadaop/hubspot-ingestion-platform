from __future__ import annotations

from pathlib import Path

from minio import Minio

from app.config import MINIO_ACCESS_KEY, MINIO_BUCKET, MINIO_ENDPOINT, MINIO_SECRET_KEY


def get_client() -> Minio:
    return Minio(
        endpoint=MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False,
    )


def ensure_bucket(bucket_name: str = MINIO_BUCKET) -> None:
    client = get_client()
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)


def upload_directory(local_dir: str | Path, bucket_name: str = MINIO_BUCKET, prefix: str = "hubspot/") -> list[str]:
    directory = Path(local_dir)
    if not directory.exists():
        raise FileNotFoundError(f"Directory does not exist: {directory}")

    ensure_bucket(bucket_name)
    client = get_client()
    object_names: list[str] = []

    for file_path in sorted(directory.rglob("*.parquet")):
        object_name = f"{prefix}{file_path.relative_to(directory).as_posix()}"
        client.fput_object(bucket_name, object_name, str(file_path))
        object_names.append(object_name)

    return object_names
