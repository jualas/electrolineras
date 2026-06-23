from __future__ import annotations

import logging
import sys

from ingest.config import settings
from ingest.fetch_common import FetchResult, download_to_file

logger = logging.getLogger(__name__)

SOURCE = "pt-nap-mobie"
FILENAME_PREFIX = "ev_charging_infra"
MIN_BYTES = 50_000_000


def fetch_portugal_nap() -> FetchResult:
    return download_to_file(
        source=SOURCE,
        url=settings.nap_pt_url,
        output_dir=settings.nap_pt_raw_dir,
        filename_prefix=FILENAME_PREFIX,
        settings=settings,
        timeout_seconds=settings.fetch_pt_timeout_seconds,
        min_bytes=MIN_BYTES,
        allow_resume=True,
        log_progress_mb=25,
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    try:
        result = fetch_portugal_nap()
    except Exception:
        logger.exception("No se pudo descargar el feed NAP Portugal (MOBI.E)")
        return 1

    print(f"Guardado: {result.output_path}")
    print(f"Manifiesto: {result.manifest_path}")
    print(f"publication_time={result.publication_time}")
    print(f"bytes={result.bytes_written:,}")
    if result.resumed_from_bytes:
        print(f"reanudado_desde={result.resumed_from_bytes:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
