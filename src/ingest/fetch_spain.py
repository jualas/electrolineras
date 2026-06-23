from __future__ import annotations

import logging
import sys

from ingest.config import settings
from ingest.fetch_common import FetchResult, download_to_file

logger = logging.getLogger(__name__)

SOURCE = "es-nap-dgt"
FILENAME_PREFIX = "electrolineras"


def fetch_spain_nap() -> FetchResult:
    return download_to_file(
        source=SOURCE,
        url=settings.nap_es_url,
        output_dir=settings.nap_es_raw_dir,
        filename_prefix=FILENAME_PREFIX,
        settings=settings,
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    try:
        result = fetch_spain_nap()
    except Exception:
        logger.exception("No se pudo descargar el feed NAP España")
        return 1

    print(f"Guardado: {result.output_path}")
    print(f"Manifiesto: {result.manifest_path}")
    print(f"publication_time={result.publication_time}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
