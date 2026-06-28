from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest.ocm_export import iter_pois_from_export


def test_iter_pois_from_export_reads_country_batches(tmp_path: Path) -> None:
    es_dir = tmp_path / "ES"
    es_dir.mkdir()
    (es_dir / "OCM-1.json").write_text(
        json.dumps({"ID": 1, "AddressInfo": {"Latitude": 40.0, "Longitude": -3.0}}),
        encoding="utf-8",
    )
    (es_dir / "OCM-2.json").write_text(
        json.dumps({"ID": 2, "AddressInfo": {"Latitude": 41.0, "Longitude": -4.0}}),
        encoding="utf-8",
    )

    batches = list(
        iter_pois_from_export(tmp_path, countries=["ES"], batch_size=1, max_batches_per_country=2)
    )
    assert len(batches) == 2
    assert batches[0][0] == "ES"
    assert len(batches[0][1]) == 1
    assert batches[0][1][0]["ID"] == 1
