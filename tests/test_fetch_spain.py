from __future__ import annotations

import gzip
import json
from pathlib import Path

import httpx
import pytest

from ingest.config import IngestSettings
from ingest.fetch_common import extract_publication_time
from ingest.fetch_spain import fetch_spain_nap as fetch_spain_entry

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<d2:payload xmlns:com="http://datex2.eu/schema/3/common">
  <com:publicationTime>2026-06-23T10:19:29.666+02:00</com:publicationTime>
  <egi:energyInfrastructureSite id="TEST"/>
</d2:payload>
"""


def test_extract_publication_time() -> None:
    assert extract_publication_time(SAMPLE_XML) == "2026-06-23T10:19:29.666+02:00"


def test_fetch_spain_writes_manifest_and_xml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingest_settings = IngestSettings(
        nap_es_url="https://example.test/electrolineras.xml",
        data_raw_dir=tmp_path / "data" / "raw",
        fetch_max_retries=1,
    )
    monkeypatch.setattr("ingest.fetch_spain.settings", ingest_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("Electrolineras/")
        return httpx.Response(200, content=SAMPLE_XML, headers={"etag": 'W/"test"'})

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "stream",
        lambda *args, **kwargs: httpx.Client(transport=transport).stream(*args, **kwargs),
    )

    result = fetch_spain_entry()
    assert result.bytes_written == len(SAMPLE_XML)
    assert result.publication_time == "2026-06-23T10:19:29.666+02:00"
    assert result.output_path.exists()
    assert result.output_path.read_bytes() == SAMPLE_XML

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"] == "es-nap-dgt"
    assert manifest["sha256"] == result.sha256
    assert manifest["file"] == result.output_path.name
    assert manifest["etag"] == 'W/"test"'


def test_fetch_spain_retries_on_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ingest_settings = IngestSettings(
        nap_es_url="https://example.test/electrolineras.xml",
        data_raw_dir=tmp_path / "data" / "raw",
        fetch_max_retries=2,
        fetch_retry_backoff_seconds=0.01,
    )
    monkeypatch.setattr("ingest.fetch_spain.settings", ingest_settings)

    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] == 1:
            return httpx.Response(503)
        return httpx.Response(200, content=SAMPLE_XML)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "stream",
        lambda *args, **kwargs: httpx.Client(transport=transport).stream(*args, **kwargs),
    )

    result = fetch_spain_entry()
    assert attempts["count"] == 2
    assert result.http_status == 200


def test_fetch_spain_accepts_gzip_content_length_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Content-Length comprimido vs cuerpo descomprimido por httpx (regresión DGT NAP)."""
    ingest_settings = IngestSettings(
        nap_es_url="https://example.test/electrolineras.xml",
        data_raw_dir=tmp_path / "data" / "raw",
        fetch_max_retries=1,
    )
    monkeypatch.setattr("ingest.fetch_spain.settings", ingest_settings)

    def handler(request: httpx.Request) -> httpx.Response:
        compressed = gzip.compress(SAMPLE_XML)
        return httpx.Response(
            200,
            content=compressed,
            headers={
                "content-encoding": "gzip",
                "content-length": str(len(compressed)),
            },
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "stream",
        lambda *args, **kwargs: httpx.Client(transport=transport).stream(*args, **kwargs),
    )

    result = fetch_spain_entry()
    assert result.bytes_written == len(SAMPLE_XML)
    assert result.output_path.read_bytes() == SAMPLE_XML


@pytest.mark.integration
def test_fetch_spain_live() -> None:
    """Descarga real opcional: pytest -m integration"""
    from pathlib import Path

    result = fetch_spain_entry()
    assert result.output_path.is_file()
    assert Path("data/raw/es").resolve() in result.output_path.resolve().parents
    assert result.bytes_written > 1000
