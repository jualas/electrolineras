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

PUBLICATION_TIME_RE = re.compile(
    r"<(?:com:)?publicationTime>([^<]+)</(?:com:)?publicationTime>"
)


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
    resumed_from_bytes: int = 0


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


def hash_existing_file(path: Path, chunk_size: int) -> tuple[hashlib._Hash, int]:
    digest = hashlib.sha256()
    bytes_read = 0
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
            bytes_read += len(chunk)
    return digest, bytes_read


def validate_xml_file(
    path: Path,
    *,
    expected_bytes: int | None,
    min_bytes: int | None,
) -> None:
    size = path.stat().st_size
    if min_bytes is not None and size < min_bytes:
        msg = f"Archivo demasiado pequeño: {size} bytes (mínimo {min_bytes})"
        raise ValueError(msg)
    if expected_bytes is not None and size != expected_bytes:
        msg = f"Tamaño distinto de Content-Length: {size} != {expected_bytes}"
        raise ValueError(msg)

    with path.open("rb") as handle:
        head = handle.read(128)
        if not head.startswith(b"<?xml"):
            raise ValueError("Cabecera XML inválida")

        handle.seek(max(0, size - 512))
        tail = handle.read()
        stripped = tail.rstrip()
        if b"</" not in tail or not stripped.endswith(b">"):
            raise ValueError("Cierre XML inválido o truncado")


def download_to_file(
    *,
    source: str,
    url: str,
    output_dir: Path,
    filename_prefix: str,
    settings: IngestSettings,
    headers: dict[str, str] | None = None,
    timeout_seconds: float | None = None,
    min_bytes: int | None = None,
    allow_resume: bool = False,
    log_progress_mb: int | None = None,
) -> FetchResult:
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    fetched_at = datetime.now(UTC)
    output_name = f"{filename_prefix}_{utc_timestamp(fetched_at)}.xml"
    output_path = output_dir / output_name
    temp_path = output_path.with_suffix(".xml.tmp")
    manifest_path = output_dir / "manifest.json"
    chunk_size = settings.fetch_stream_chunk_size
    timeout = timeout_seconds or settings.fetch_timeout_seconds

    request_headers = {
        "User-Agent": settings.fetch_user_agent,
        # Evita gzip: httpx descomprime el cuerpo pero Content-Length suele ser el comprimido.
        "Accept-Encoding": "identity",
    }
    if headers:
        request_headers.update(headers)

    last_error: Exception | None = None
    response: httpx.Response | None = None
    resumed_from_bytes = 0
    expected_total_bytes: int | None = None

    for attempt in range(1, settings.fetch_max_retries + 1):
        expected_total_bytes = None
        try:
            resume_from = 0
            if allow_resume and temp_path.exists():
                resume_from = temp_path.stat().st_size
                if resume_from > 0:
                    request_headers["Range"] = f"bytes={resume_from}-"
                    resumed_from_bytes = resume_from
                    logger.info("Reanudando descarga desde byte %d", resume_from)
            elif "Range" in request_headers:
                request_headers.pop("Range", None)
                resumed_from_bytes = 0

            logger.info("Descargando %s (intento %d/%d)", url, attempt, settings.fetch_max_retries)
            with httpx.stream(
                "GET",
                url,
                headers=request_headers,
                timeout=timeout,
                follow_redirects=True,
            ) as stream:
                response = stream
                stream.raise_for_status()

                if resume_from and response.status_code == 200:
                    logger.warning("Servidor ignoró Range; reiniciando descarga completa")
                    temp_path.unlink(missing_ok=True)
                    resume_from = 0
                    resumed_from_bytes = 0
                elif resume_from and response.status_code == 416:
                    logger.warning("Range no satisfactorio; reiniciando descarga completa")
                    temp_path.unlink(missing_ok=True)
                    resume_from = 0
                    resumed_from_bytes = 0

                content_encoding = response.headers.get("content-encoding")
                content_length = response.headers.get("content-length")
                if content_length is not None and not content_encoding:
                    declared = int(content_length)
                    if response.status_code == 206:
                        expected_total_bytes = resume_from + declared
                    else:
                        expected_total_bytes = declared
                elif content_encoding:
                    logger.warning(
                        "Respuesta con Content-Encoding=%s; omitiendo validación Content-Length",
                        content_encoding,
                    )
                    expected_total_bytes = None

                sha256: hashlib._Hash | None = None
                if resume_from:
                    sha256, hashed_bytes = hash_existing_file(temp_path, chunk_size)
                    if hashed_bytes != resume_from:
                        raise ValueError("Tamaño parcial inconsistente antes de reanudar")
                    file_mode = "ab"
                else:
                    sha256 = hashlib.sha256()
                    file_mode = "wb"

                bytes_written = resume_from
                publication_time: str | None = None
                head_buffer = bytearray()
                last_progress_bucket = -1

                with temp_path.open(file_mode) as handle:
                    for chunk in stream.iter_bytes(chunk_size):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        sha256.update(chunk)
                        bytes_written += len(chunk)
                        if len(head_buffer) < 8192:
                            remaining = 8192 - len(head_buffer)
                            head_buffer.extend(chunk[:remaining])

                        if log_progress_mb:
                            bucket = bytes_written // (log_progress_mb * 1024 * 1024)
                            if bucket > last_progress_bucket:
                                logger.info("Progreso: %.1f MB", bytes_written / (1024 * 1024))
                                last_progress_bucket = bucket

                if resume_from == 0:
                    publication_time = extract_publication_time(bytes(head_buffer))
                elif not head_buffer and temp_path.exists():
                    publication_time = extract_publication_time(temp_path.read_bytes()[:8192])

            validate_xml_file(
                temp_path,
                expected_bytes=expected_total_bytes,
                min_bytes=min_bytes,
            )

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
                "resumed_from_bytes": resumed_from_bytes,
                "expected_bytes": expected_total_bytes,
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
                resumed_from_bytes=resumed_from_bytes,
            )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            last_error = exc
            if attempt >= settings.fetch_max_retries:
                if temp_path.exists() and allow_resume:
                    logger.error(
                        "Descarga fallida; conservando parcial %s (%d bytes) para reintento",
                        temp_path.name,
                        temp_path.stat().st_size,
                    )
                elif temp_path.exists():
                    temp_path.unlink()
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
