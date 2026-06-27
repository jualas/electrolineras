from __future__ import annotations

import sqlite3
from pathlib import Path
from urllib.parse import urlparse

from api.config import settings
from ingest.config import repo_root


def database_path_from_url(database_url: str | None = None) -> Path:
    url = database_url or settings.database_url
    parsed = urlparse(url)
    if parsed.scheme not in {"sqlite", "sqlite3"}:
        msg = f"Esquema de base de datos no soportado: {parsed.scheme}"
        raise ValueError(msg)

    raw_path = parsed.path
    if not raw_path or raw_path == "/":
        return _default_database_path()

    # sqlite:////abs/path.db → ruta absoluta (cuatro barras)
    if raw_path.startswith("//"):
        return Path(raw_path[1:])

    # sqlite:///data/db/stations.db → relativa al repo o cwd (Docker /app)
    relative_path = raw_path.lstrip("/")
    cwd_path = Path.cwd() / relative_path
    if cwd_path.exists() or cwd_path.parent.exists():
        return cwd_path
    return repo_root() / relative_path


def _default_database_path() -> Path:
    cwd_path = Path.cwd() / "data" / "db" / "stations.db"
    if cwd_path.exists():
        return cwd_path
    return repo_root() / "data" / "db" / "stations.db"


def connect(database_url: str | None = None) -> sqlite3.Connection:
    db_path = database_path_from_url(database_url)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection
