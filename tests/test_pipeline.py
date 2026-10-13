from pathlib import Path

import pandas as pd

from app.pipeline import persist_resource_page


def test_persist_resource_page_upserts_by_id(tmp_path: Path):
    persist_resource_page("contacts", [{"id": "1", "email": "old@example.com"}], tmp_path)
    persist_resource_page(
        "contacts",
        [{"id": "1", "email": "new@example.com"}, {"id": "2", "email": "two@example.com"}],
        tmp_path,
    )

    snapshot = pd.read_parquet(tmp_path / "contacts" / "snapshot.parquet")
    assert len(snapshot) == 2
    assert snapshot.set_index("id").loc["1", "email"] == "new@example.com"
    assert list((tmp_path / "contacts").glob("*.parquet")) == [tmp_path / "contacts" / "snapshot.parquet"]
