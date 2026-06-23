from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from ingest.config import IngestSettings, repo_root

logger = logging.getLogger(__name__)

PUBLICATION_TIME_RE = re.compile(r"<com:publicationTime>([^<]+)</com:publicationTime>")


@dataclass(frozen=True)
class FetchResult:
    source: str
    url: str
    output_path: Path
    manifest_path: Path
    fetched_at: datetime
    sha256: str
    bytes_written: int
    http_status: int
    publication_time: str | None
    etag: str | None
    last_modified: str | None


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else repo_root() / path


def utc_timestamp(dt: datetime | None = None) -> str:
    value = dt or datetime.now(UTC)
    return value.strftime("%Y%m%dT%H%M%SZ")


def extract_publication_time(xml_head: bytes) -> str | None:
    match = PUBLICATION_TIME_RE.search(xml_head.decode("utf-8", errors="replace"))
    return match.group(1) if match else None


def write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = manifest_path.with_suffix(".json.tmp")
    temp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(manifest_path)


def download_to_file(
    *,
    source: str,
    url: str,
    output_dir: Path,
    filename_prefix: str,
    settings: IngestSettings,
    headers: dict[str, str] | None = None,
) -> FetchResult:
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fetched_at = datetime.now(UTC)
    output_name = f"{filename_prefix}_{utc_timestamp(fetched_at)}.xml"
    output_path = output_dir / output_name
    temp_path = output_path.with_suffix(".xml.tmp")
    manifest_path = output_dir / "manifest.json"

    request_headers = {"User-Agent": settings.fetch_user_agent}
    if headers:
        request_headers.update(headers)

    last_error: Exception | None = None
    response: httpx.Response | None = None

    for attempt in range(1, settings.fetch_max_retries + 1):
        try:
            logger.info("Descargando %s (intento %d/%d)", url, attempt, settings.fetch_max_retries)
            with httpx.stream(
                "GET",
                url,
                headers=request_headers,
                timeout=settings.fetch_timeout_seconds,
                follow_redirects=True,
            ) as stream:
                response = stream
                stream.raise_for_status()
                sha256 = hashlib.sha256()
                bytes_written = 0
                publication_time: str | None = None
                head_buffer = bytearray()

                with temp_path.open("wb") as handle:
                    for chunk in stream.iter_bytes():
                        if not chunk:
                            continue
                        handle.write(chunk)
                        sha256.update(chunk)
                        bytes_written += len(chunk)
                        if len(head_buffer) < 8192:
                            remaining = 8192 - len(head_buffer)
                            head_buffer.extend(chunk[:remaining])

                publication_time = extract_publication_time(bytes(head_buffer))

            temp_path.replace(output_path)
            digest = sha256.hexdigest()
            manifest = {
                "source": source,
                "url": url,
                "fetched_at": fetched_at.isoformat(),
                "file": output_name,
                "sha256": digest,
                "bytes": bytes_written,
                "http_status": response.status_code,
                "publication_time": publication_time,
                "etag": response.headers.get("etag"),
                "last_modified": response.headers.get("last-modified"),
            }
            write_manifest(manifest_path, manifest)

            logger.info(
                "Descarga OK: %s (%d bytes, sha256=%s…, publication_time=%s)",
                output_path.name,
                bytes_written,
                digest[:12],
                publication_time,
            )
            return FetchResult(
                source=source,
                url=url,
                output_path=output_path,
                manifest_path=manifest_path,
                fetched_at=fetched_at,
                sha256=digest,
                bytes_written=bytes_written,
                http_status=response.status_code,
                publication_time=publication_time,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
            )
        except (httpx.HTTPError, OSError) as exc:
            last_error = exc
            if temp_path.exists():
                temp_path.unlink()
            if attempt >= settings.fetch_max_retries:
                break
            sleep_seconds = settings.fetch_retry_backoff_seconds * attempt
            logger.warning(
                "Fallo en intento %d: %s — reintento en %.1fs",
                attempt,
                exc,
                sleep_seconds,
            )
            time.sleep(sleep_seconds)

    assert last_error is not None
    logger.error("Descarga fallida tras %d intentos: %s", settings.fetch_max_retries, last_error)
    raise last_error
