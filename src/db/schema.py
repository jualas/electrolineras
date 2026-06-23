from __future__ import annotations

import sqlite3

SCHEMA_VERSION = 1

MIGRATIONS: dict[int, list[str]] = {
    1: [
        """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ingest_run (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            source_version TEXT,
            records_upserted INTEGER,
            status TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS station (
            id TEXT PRIMARY KEY,
            source TEXT NOT NULL,
            country TEXT NOT NULL,
            site_name TEXT,
            operator TEXT,
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            address TEXT,
            max_power_kw REAL NOT NULL DEFAULT 0,
            access TEXT,
            payment_methods TEXT,
            opening_hours TEXT,
            raw_ref TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            source_version TEXT,
            dynamic_status TEXT,
            dynamic_price REAL,
            dynamic_updated_at TEXT,
            UNIQUE (source, raw_ref)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS connector (
            id INTEGER PRIMARY KEY,
            station_id TEXT NOT NULL REFERENCES station(id) ON DELETE CASCADE,
            connector_type TEXT,
            power_kw REAL NOT NULL,
            voltage_v REAL,
            current_a REAL,
            charging_mode TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_station_country ON station(country)",
        "CREATE INDEX IF NOT EXISTS idx_station_max_power ON station(max_power_kw)",
        "CREATE INDEX IF NOT EXISTS idx_station_lat_lon ON station(lat, lon)",
        "CREATE INDEX IF NOT EXISTS idx_station_operator ON station(operator)",
        "CREATE INDEX IF NOT EXISTS idx_station_source ON station(source)",
        "CREATE INDEX IF NOT EXISTS idx_connector_station ON connector(station_id)",
        "CREATE INDEX IF NOT EXISTS idx_connector_power ON connector(power_kw)",
    ],
}


def current_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    ).fetchone()
    if row is None:
        return 0
    version_row = connection.execute("SELECT MAX(version) FROM schema_version").fetchone()
    if version_row is None or version_row[0] is None:
        return 0
    return int(version_row[0])


def apply_migrations(connection: sqlite3.Connection) -> int:
    current = current_schema_version(connection)
    for version in range(current + 1, SCHEMA_VERSION + 1):
        statements = MIGRATIONS[version]
        for statement in statements:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_version(version) VALUES (?)", (version,))
        current = version
    connection.commit()
    return current


def init_schema(connection: sqlite3.Connection) -> int:
    return apply_migrations(connection)
