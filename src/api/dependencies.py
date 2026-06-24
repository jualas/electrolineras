from __future__ import annotations

from collections.abc import Generator

from db.repository import StationRepository


def get_repository() -> Generator[StationRepository, None, None]:
    repo = StationRepository()
    try:
        yield repo
    finally:
        repo.close()
