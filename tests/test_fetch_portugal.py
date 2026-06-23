from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from ingest.config import IngestSettings
from ingest.fetch_common import download_to_file, extract_publication_time, validate_xml_file
from ingest.fetch_portugal import fetch_portugal_nap as fetch_portugal_entry

SAMPLE_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<ns7:payload xmlns="http://datex2.eu/schema/3/common">
  <publicationTime>2026-06-23T03:00:05.160Z</publicationTime>
  <ns6:energyInfrastructureSite id="TEST"/>
</ns7:payload>
"""

FIXED_TS = "20260101T120000Z"


def test_extract_publication_time_portugal_format() -> None:
    assert extract_publication_time(SAMPLE_XML) == "2026-06-23T03:00:05.160Z"


def test_validate_xml_file_rejects_truncated(tmp_path: Path) -> None:
    bad = tmp_path / "bad.xml"
    bad.write_bytes(b"<?xml version='1.0'?><root><item>")
    with pytest.raises(ValueError, match="Cierre XML"):
        validate_xml_file(bad, expected_bytes=None, min_bytes=None)


def test_fetch_portugal_writes_manifest_and_xml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingest_settings = IngestSettings(
        nap_pt_url="https://example.test/evChargingInfra",
        data_raw_dir=tmp_path / "data" / "raw",
        fetch_max_retries=1,
        fetch_stream_chunk_size=64,
    )
    monkeypatch.setattr("ingest.fetch_portugal.settings", ingest_settings)
    monkeypatch.setattr("ingest.fetch_portugal.MIN_BYTES", 1)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"].startswith("Electrolineras/")
        return httpx.Response(
            200,
            content=SAMPLE_XML,
            headers={"content-length": str(len(SAMPLE_XML)), "etag": 'W/"pt-test"'},
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "stream",
        lambda *args, **kwargs: httpx.Client(transport=transport).stream(*args, **kwargs),
    )

    result = fetch_portugal_entry()
    assert result.bytes_written == len(SAMPLE_XML)
    assert result.publication_time == "2026-06-23T03:00:05.160Z"
    assert result.output_path.exists()
    assert result.output_path.read_bytes() == SAMPLE_XML

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["source"] == "pt-nap-mobie"
    assert manifest["sha256"] == result.sha256
    assert manifest["expected_bytes"] == len(SAMPLE_XML)


def test_download_resumes_with_range_header(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ingest_settings = IngestSettings(
        fetch_max_retries=1,
        fetch_stream_chunk_size=8,
    )
    monkeypatch.setattr("ingest.fetch_common.utc_timestamp", lambda _dt=None: FIXED_TS)

    partial = SAMPLE_XML[:20]
    remainder = SAMPLE_XML[20:]
    output_dir = tmp_path / "pt"
    temp_path = output_dir / f"ev_charging_infra_{FIXED_TS}.xml.tmp"
    output_dir.mkdir(parents=True)
    temp_path.write_bytes(partial)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("Range") == f"bytes={len(partial)}-"
        return httpx.Response(
            206,
            content=remainder,
            headers={"content-length": str(len(remainder))},
        )

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        httpx,
        "stream",
        lambda *args, **kwargs: httpx.Client(transport=transport).stream(*args, **kwargs),
    )

    result = download_to_file(
        source="pt-nap-mobie",
        url="https://example.test/evChargingInfra",
        output_dir=output_dir,
        filename_prefix="ev_charging_infra",
        settings=ingest_settings,
        min_bytes=1,
        allow_resume=True,
    )
    assert result.resumed_from_bytes == len(partial)
    assert result.bytes_written == len(SAMPLE_XML)
    assert result.output_path.read_bytes() == SAMPLE_XML


@pytest.mark.integration
def test_fetch_portugal_live() -> None:
    """Descarga real opcional: pytest -m integration"""
    from ingest.fetch_portugal import MIN_BYTES

    result = fetch_portugal_entry()
    assert result.output_path.is_file()
    assert Path("data/raw/pt").resolve() in result.output_path.resolve().parents
    assert result.bytes_written >= MIN_BYTES
