from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, TypeVar

from app.config import MAX_RESOURCE_WORKERS

T = TypeVar("T")


def run_resources(
    resources: list[str], worker: Callable[[str], T], max_workers: int = MAX_RESOURCE_WORKERS
) -> dict[str, T]:
    """Run independent resource syncs concurrently and preserve keyed results."""
    if not resources:
        return {}
    results: dict[str, T] = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(resources)))) as executor:
        futures = {executor.submit(worker, resource): resource for resource in resources}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return results