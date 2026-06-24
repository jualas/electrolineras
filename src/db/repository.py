from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from db.connection import connect
from db.schema import init_schema
from db.spatial import bbox_sql, haversine_m
from models.station import Connector, Station, StationLocation


def _iso_datetime(value: datetime | None) -> str:
    if value is None:
        return datetime.now(UTC).isoformat()
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC).isoformat()
    return value.astimezone(UTC).isoformat()


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _row_to_station(row: sqlite3.Row, connectors: list[Connector]) -> Station:
    payment_methods_raw = row["payment_methods"]
    payment_methods = json.loads(payment_methods_raw) if payment_methods_raw else []
    return Station(
        id=row["id"],
        source=row["source"],
        country=row["country"],
        site_name=row["site_name"],
        operator=row["operator"],
        location=StationLocation(
            lat=row["lat"],
            lon=row["lon"],
            address=row["address"],
        ),
        connectors=connectors,
        max_power_kw=row["max_power_kw"],
        access=row["access"],
        payment_methods=payment_methods,
        opening_hours=row["opening_hours"],
        raw_ref=row["raw_ref"],
        fetched_at=_parse_datetime(row["fetched_at"]),
        source_version=row["source_version"],
    )


class StationRepository:
    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self._owns_connection = connection is None
        self.connection = connection or connect()
        init_schema(self.connection)

    def close(self) -> None:
        if self._owns_connection:
            self.connection.close()

    def __enter__(self) -> StationRepository:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def _load_connectors(self, station_ids: list[str]) -> dict[str, list[Connector]]:
        if not station_ids:
            return {}
        placeholders = ",".join("?" for _ in station_ids)
        rows = self.connection.execute(
            f"""
            SELECT station_id, connector_type, power_kw, voltage_v, current_a, charging_mode
            FROM connector
            WHERE station_id IN ({placeholders})
            ORDER BY station_id, id
            """,
            station_ids,
        ).fetchall()
        grouped: dict[str, list[Connector]] = {station_id: [] for station_id in station_ids}
        for row in rows:
            grouped[row["station_id"]].append(
                Connector(
                    connector_type=row["connector_type"] or "unknown",
                    power_kw=row["power_kw"],
                    voltage_v=row["voltage_v"],
                    current_a=row["current_a"],
                    charging_mode=row["charging_mode"],
                )
            )
        return grouped

    def upsert_stations(self, stations: list[Station]) -> int:
        if not stations:
            return 0

        upserted = 0
        with self.connection:
            for station in stations:
                fetched_at = _iso_datetime(station.fetched_at)
                payment_methods = json.dumps(station.payment_methods, ensure_ascii=False)
                self.connection.execute(
                    """
                    INSERT INTO station (
                        id, source, country, site_name, operator, lat, lon, address,
                        max_power_kw, access, payment_methods, opening_hours, raw_ref,
                        fetched_at, source_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        source = excluded.source,
                        country = excluded.country,
                        site_name = excluded.site_name,
                        operator = excluded.operator,
                        lat = excluded.lat,
                        lon = excluded.lon,
                        address = excluded.address,
                        max_power_kw = excluded.max_power_kw,
                        access = excluded.access,
                        payment_methods = excluded.payment_methods,
                        opening_hours = excluded.opening_hours,
                        raw_ref = excluded.raw_ref,
                        fetched_at = excluded.fetched_at,
                        source_version = excluded.source_version
                    """,
                    (
                        station.id,
                        station.source,
                        station.country,
                        station.site_name,
                        station.operator,
                        station.location.lat,
                        station.location.lon,
                        station.location.address,
                        station.max_power_kw,
                        station.access,
                        payment_methods,
                        station.opening_hours,
                        station.raw_ref,
                        fetched_at,
                        station.source_version,
                    ),
                )
                self.connection.execute(
                    "DELETE FROM connector WHERE station_id = ?",
                    (station.id,),
                )
                self.connection.executemany(
                    """
                    INSERT INTO connector (
                        station_id, connector_type, power_kw, voltage_v, current_a, charging_mode
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            station.id,
                            connector.connector_type,
                            connector.power_kw,
                            connector.voltage_v,
                            connector.current_a,
                            connector.charging_mode,
                        )
                        for connector in station.connectors
                    ],
                )
                upserted += 1
        return upserted

    def get_by_id(self, station_id: str) -> Station | None:
        row = self.connection.execute(
            "SELECT * FROM station WHERE id = ?",
            (station_id,),
        ).fetchone()
        if row is None:
            return None
        connectors = self._load_connectors([station_id])[station_id]
        return _row_to_station(row, connectors)

    def _search_clauses(
        self,
        *,
        west: float | None = None,
        south: float | None = None,
        east: float | None = None,
        north: float | None = None,
        min_kw: float | None = None,
        max_kw: float | None = None,
        countries: list[str] | None = None,
    ) -> tuple[list[str], list[Any]]:
        clauses = ["1 = 1"]
        params: list[Any] = []

        if west is not None and east is not None:
            clauses.append("lon BETWEEN ? AND ?")
            params.extend([west, east])
        if south is not None and north is not None:
            clauses.append("lat BETWEEN ? AND ?")
            params.extend([south, north])
        if min_kw is not None:
            clauses.append("max_power_kw >= ?")
            params.append(min_kw)
        if max_kw is not None:
            clauses.append("max_power_kw <= ?")
            params.append(max_kw)
        if countries:
            placeholders = ",".join("?" for _ in countries)
            clauses.append(f"country IN ({placeholders})")
            params.extend(countries)

        return clauses, params

    def count_matching(
        self,
        *,
        west: float | None = None,
        south: float | None = None,
        east: float | None = None,
        north: float | None = None,
        min_kw: float | None = None,
        max_kw: float | None = None,
        countries: list[str] | None = None,
    ) -> int:
        clauses, params = self._search_clauses(
            west=west,
            south=south,
            east=east,
            north=north,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
        )
        row = self.connection.execute(
            f"SELECT COUNT(*) FROM station WHERE {' AND '.join(clauses)}",
            params,
        ).fetchone()
        return int(row[0]) if row else 0

    def search(
        self,
        *,
        west: float | None = None,
        south: float | None = None,
        east: float | None = None,
        north: float | None = None,
        min_kw: float | None = None,
        max_kw: float | None = None,
        countries: list[str] | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[Station]:
        clauses, params = self._search_clauses(
            west=west,
            south=south,
            east=east,
            north=north,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
        )

        params.extend([limit, offset])
        rows = self.connection.execute(
            f"""
            SELECT * FROM station
            WHERE {' AND '.join(clauses)}
            ORDER BY max_power_kw DESC, id
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        station_ids = [row["id"] for row in rows]
        connectors_by_station = self._load_connectors(station_ids)
        return [_row_to_station(row, connectors_by_station[row["id"]]) for row in rows]

    def nearby(
        self,
        *,
        lat: float,
        lon: float,
        radius_m: float = 1000.0,
        min_kw: float | None = None,
        max_kw: float | None = None,
        countries: list[str] | None = None,
        limit: int = 100,
    ) -> list[Station]:
        south, north, west, east = bbox_sql(lat, lon, radius_m)
        candidates = self.search(
            west=west,
            south=south,
            east=east,
            north=north,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
            limit=max(limit * 5, 500),
            offset=0,
        )
        ranked = sorted(
            (
                (haversine_m(lat, lon, station.location.lat, station.location.lon), station)
                for station in candidates
            ),
            key=lambda item: item[0],
        )
        return [station for distance, station in ranked if distance <= radius_m][:limit]

    def delete_by_source(self, source: str) -> int:
        with self.connection:
            cursor = self.connection.execute(
                "DELETE FROM station WHERE source = ?",
                (source,),
            )
        return cursor.rowcount

    def count_stations(self, *, countries: list[str] | None = None) -> int:
        if countries:
            placeholders = ",".join("?" for _ in countries)
            row = self.connection.execute(
                f"SELECT COUNT(*) FROM station WHERE country IN ({placeholders})",
                countries,
            ).fetchone()
        else:
            row = self.connection.execute("SELECT COUNT(*) FROM station").fetchone()
        return int(row[0]) if row else 0

    def stats_by_country(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT country, COUNT(*) AS count, MAX(max_power_kw) AS max_kw
            FROM station
            GROUP BY country
            ORDER BY country
            """
        ).fetchall()
        return [
            {"country": row["country"], "count": row["count"], "max_kw": row["max_kw"]}
            for row in rows
        ]

    def export_geojson(
        self,
        *,
        countries: list[str] | None = None,
        min_kw: float | None = None,
    ) -> dict[str, Any]:
        stations = self.search(
            countries=countries,
            min_kw=min_kw,
            limit=100_000,
            offset=0,
        )
        features = []
        for station in stations:
            features.append(
                {
                    "type": "Feature",
                    "id": station.id,
                    "geometry": {
                        "type": "Point",
                        "coordinates": [station.location.lon, station.location.lat],
                    },
                    "properties": {
                        "id": station.id,
                        "source": station.source,
                        "country": station.country,
                        "site_name": station.site_name,
                        "operator": station.operator,
                        "max_power_kw": station.max_power_kw,
                        "access": station.access,
                        "connector_count": len(station.connectors),
                        "address": station.location.address,
                    },
                }
            )
        return {"type": "FeatureCollection", "features": features}

    def start_ingest_run(self, source: str, *, started_at: datetime | None = None) -> int:
        started = _iso_datetime(started_at)
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO ingest_run (source, started_at, status)
                VALUES (?, ?, 'running')
                """,
                (source, started),
            )
        return int(cursor.lastrowid)

    def finish_ingest_run(
        self,
        run_id: int,
        *,
        status: str,
        records_upserted: int | None = None,
        source_version: str | None = None,
        finished_at: datetime | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE ingest_run
                SET finished_at = ?, source_version = ?, records_upserted = ?, status = ?
                WHERE id = ?
                """,
                (
                    _iso_datetime(finished_at),
                    source_version,
                    records_upserted,
                    status,
                    run_id,
                ),
            )

    def stats_by_power(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """
            SELECT
                country,
                COUNT(*) AS total,
                SUM(CASE WHEN max_power_kw < 22 THEN 1 ELSE 0 END) AS slow_ac,
                SUM(CASE WHEN max_power_kw >= 22 AND max_power_kw < 43
                    THEN 1 ELSE 0 END) AS ac_fast,
                SUM(CASE WHEN max_power_kw >= 43 AND max_power_kw < 100
                    THEN 1 ELSE 0 END) AS dc_fast,
                SUM(CASE WHEN max_power_kw >= 100 AND max_power_kw < 150
                    THEN 1 ELSE 0 END) AS hpc,
                SUM(CASE WHEN max_power_kw >= 150 THEN 1 ELSE 0 END) AS ultra_fast
            FROM station
            GROUP BY country
            ORDER BY country
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def top_operators(self, *, country: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        if country:
            rows = self.connection.execute(
                """
                SELECT operator, COUNT(*) AS count
                FROM station
                WHERE country = ? AND operator IS NOT NULL AND operator != ''
                GROUP BY operator
                ORDER BY count DESC
                LIMIT ?
                """,
                (country, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT operator, COUNT(*) AS count
                FROM station
                WHERE operator IS NOT NULL AND operator != ''
                GROUP BY operator
                ORDER BY count DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [{"operator": row["operator"], "count": row["count"]} for row in rows]
