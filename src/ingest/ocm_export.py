from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

from ingest.config import settings

logger = logging.getLogger(__name__)


class OcmExportError(Exception):
    pass


def resolve_export_dir(export_dir: Path | None = None) -> Path:
    root = export_dir or settings.ocm_export_dir
    if not root.is_dir():
        msg = f"Directorio OCM export no encontrado: {root}"
        raise OcmExportError(msg)
    return root


def iter_pois_from_export(
    export_dir: Path | None = None,
    *,
    countries: list[str],
    batch_size: int | None = None,
    max_batches_per_country: int | None = None,
) -> Iterator[tuple[str, list[dict]]]:
    """Lee POIs desde openchargemap/ocm-export (data/ES, data/PT, …)."""
    root = resolve_export_dir(export_dir)
    page_size = batch_size or settings.ocm_sync_page_size

    for country in countries:
        country_code = country.upper()
        country_dir = root / country_code
        if not country_dir.is_dir():
            logger.warning("OCM export: sin carpeta para %s en %s", country_code, root)
            continue

        batch: list[dict] = []
        batches = 0
        files = sorted(country_dir.glob("*.json"))
        logger.info("OCM export %s: %d archivos en %s", country_code, len(files), country_dir)

        for path in files:
            try:
                poi = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("OCM export: no se pudo leer %s (%s)", path.name, exc)
                continue
            if not isinstance(poi, dict):
                continue
            batch.append(poi)
            if len(batch) >= page_size:
                yield country_code, batch
                batches += 1
                batch = []
                if max_batches_per_country is not None and batches >= max_batches_per_country:
                    break

        if batch and (
            max_batches_per_country is None or batches < max_batches_per_country
        ):
            yield country_code, batch
