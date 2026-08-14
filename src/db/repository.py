from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from db.connection import connect
from db.schema import init_schema
from db.spatial import bbox_sql, haversine_m
from models.station import Connector, ExternalUserComment, Station, StationLocation


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


def _parse_external_comments(raw: str | None) -> list[ExternalUserComment]:
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    comments: list[ExternalUserComment] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        comments.append(
            ExternalUserComment(
                rating=item.get("rating"),
                comment=item.get("comment"),
                username=item.get("username"),
                created_at=_parse_datetime(item.get("created_at")),
                checkin_label=item.get("checkin_label"),
            )
        )
    return comments


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
        dynamic_status=row["dynamic_status"],
        dynamic_price_eur_kwh=row["dynamic_price"],
        dynamic_updated_at=_parse_datetime(row["dynamic_updated_at"]),
        external_rating_avg=row["external_rating_avg"],
        external_rating_count=int(row["external_rating_count"] or 0),
        external_comments=_parse_external_comments(row["external_comments_json"]),
        external_rating_updated_at=_parse_datetime(row["external_rating_updated_at"]),
        ocm_poi_id=row["ocm_poi_id"],
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
            SELECT station_id, connector_type, power_kw, voltage_v, current_a, charging_mode,
                   connector_format, status, evse_id, physical_reference
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
                    connector_format=row["connector_format"],
                    status=row["status"],
                    evse_id=row["evse_id"],
                    physical_reference=row["physical_reference"],
                )
            )
        return grouped

    @staticmethod
    def _connector_insert_rows(station_id: str, connectors: list[Connector]) -> list[tuple]:
        return [
            (
                station_id,
                connector.connector_type,
                connector.power_kw,
                connector.voltage_v,
                connector.current_a,
                connector.charging_mode,
                connector.connector_format,
                connector.status,
                connector.evse_id,
                connector.physical_reference,
            )
            for connector in connectors
        ]
    def upsert_stations(self, stations: list[Station]) -> int:
        if not stations:
            return 0

        upserted = 0
        with self.connection:
            for station in stations:
                fetched_at = _iso_datetime(station.fetched_at)
                payment_methods = json.dumps(station.payment_methods, ensure_ascii=False)
                existing = self.connection.execute(
                    "SELECT ocpi_live_at FROM station WHERE id = ?",
                    (station.id,),
                ).fetchone()
                preserve_ocpi_profile = (
                    existing is not None
                    and existing["ocpi_live_at"]
                    and station.source == "es-nap-dgt"
                )

                if preserve_ocpi_profile:
                    self.connection.execute(
                        """
                        UPDATE station SET
                            source = ?,
                            country = ?,
                            site_name = ?,
                            operator = ?,
                            lat = ?,
                            lon = ?,
                            address = ?,
                            access = ?,
                            opening_hours = ?,
                            raw_ref = ?,
                            fetched_at = ?,
                            source_version = ?
                        WHERE id = ?
                        """,
                        (
                            station.source,
                            station.country,
                            station.site_name,
                            station.operator,
                            station.location.lat,
                            station.location.lon,
                            station.location.address,
                            station.access,
                            station.opening_hours,
                            station.raw_ref,
                            fetched_at,
                            station.source_version,
                            station.id,
                        ),
                    )
                    upserted += 1
                    continue

                self.connection.execute(
                    """
                    INSERT INTO station (
                        id, source, country, site_name, operator, lat, lon, address,
                        max_power_kw, access, payment_methods, opening_hours, raw_ref,
                        fetched_at, source_version, dynamic_status, dynamic_price,
                        dynamic_updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        source_version = excluded.source_version,
                        dynamic_status = COALESCE(excluded.dynamic_status, station.dynamic_status),
                        dynamic_price = COALESCE(excluded.dynamic_price, station.dynamic_price),
                        dynamic_updated_at = COALESCE(
                            excluded.dynamic_updated_at, station.dynamic_updated_at
                        )
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
                        station.dynamic_status,
                        station.dynamic_price_eur_kwh,
                        _iso_datetime(station.dynamic_updated_at),
                    ),
                )
                self.connection.execute(
                    "DELETE FROM connector WHERE station_id = ?",
                    (station.id,),
                )
                self.connection.executemany(
                    """
                    INSERT INTO connector (
                        station_id, connector_type, power_kw, voltage_v, current_a, charging_mode,
                        connector_format, status, evse_id, physical_reference
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._connector_insert_rows(station.id, station.connectors),
                )
                upserted += 1
        return upserted

    def find_nearby_station_id(
        self,
        lat: float,
        lon: float,
        *,
        radius_m: float,
        country: str,
    ) -> str | None:
        south, north, west, east = bbox_sql(lat, lon, radius_m)
        rows = self.connection.execute(
            """
            SELECT id, lat, lon
            FROM station
            WHERE country = ? AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
            """,
            (country, south, north, west, east),
        ).fetchall()
        best_id: str | None = None
        best_distance = radius_m
        for row in rows:
            distance = haversine_m(lat, lon, row["lat"], row["lon"])
            if distance <= radius_m and distance < best_distance:
                best_distance = distance
                best_id = row["id"]
        return best_id

    def find_nap_match_for_reve(
        self,
        lat: float,
        lon: float,
        *,
        site_name: str | None,
        country: str = "ES",
        radius_m: float = 350.0,
        name_radius_m: float = 500.0,
    ) -> str | None:
        """Empareja un emplazamiento REVE con un NAP cercano (no con otro es-reve-*).

        Prioridad: NAP a ≤ radius_m; si no, mismo ``site_name`` a ≤ name_radius_m.
        """
        search_radius = max(radius_m, name_radius_m)
        south, north, west, east = bbox_sql(lat, lon, search_radius)
        rows = self.connection.execute(
            """
            SELECT id, site_name, lat, lon
            FROM station
            WHERE country = ?
              AND source = 'es-nap-dgt'
              AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
            """,
            (country, south, north, west, east),
        ).fetchall()
        name_norm = (site_name or "").strip().lower()
        best: tuple[int, float, str] | None = None
        for row in rows:
            distance = haversine_m(lat, lon, row["lat"], row["lon"])
            same_name = bool(name_norm) and (row["site_name"] or "").strip().lower() == name_norm
            if distance <= radius_m:
                priority = 0
            elif same_name and distance <= name_radius_m:
                priority = 1
            else:
                continue
            candidate = (priority, distance, row["id"])
            if best is None or candidate < best:
                best = candidate
        return best[2] if best else None

    def find_reve_duplicate(
        self,
        *,
        site_name: str | None,
        lat: float,
        lon: float,
        radius_m: float = 500.0,
        exclude_station_id: str | None = None,
    ) -> str | None:
        """Localiza un duplicado es-reve-* del mismo nombre cerca de un NAP ya enriquecido."""
        name_norm = (site_name or "").strip().lower()
        if not name_norm:
            return None
        south, north, west, east = bbox_sql(lat, lon, radius_m)
        rows = self.connection.execute(
            """
            SELECT id, site_name, lat, lon
            FROM station
            WHERE source = 'es-reve-public'
              AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?
            """,
            (south, north, west, east),
        ).fetchall()
        best_id: str | None = None
        best_distance = radius_m
        for row in rows:
            if exclude_station_id and row["id"] == exclude_station_id:
                continue
            if (row["site_name"] or "").strip().lower() != name_norm:
                continue
            distance = haversine_m(lat, lon, row["lat"], row["lon"])
            if distance <= radius_m and distance < best_distance:
                best_distance = distance
                best_id = row["id"]
        return best_id

    def delete_station(self, station_id: str) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM connector WHERE station_id = ?", (station_id,))
            self.connection.execute("DELETE FROM station WHERE id = ?", (station_id,))

    def update_dynamic_fields(
        self,
        station_id: str,
        *,
        dynamic_status: str | None,
        dynamic_price_eur_kwh: float | None,
        dynamic_updated_at: datetime | None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE station
                SET dynamic_status = ?, dynamic_price = ?, dynamic_updated_at = ?
                WHERE id = ?
                """,
                (
                    dynamic_status,
                    dynamic_price_eur_kwh,
                    _iso_datetime(dynamic_updated_at),
                    station_id,
                ),
            )

    def enrich_from_reve(self, station_id: str, station: Station) -> None:
        """Aplica perfil operativo OCPI/REVE sobre una estación NAP existente."""
        now = _iso_datetime(station.dynamic_updated_at or station.fetched_at)
        payment_methods = json.dumps(station.payment_methods, ensure_ascii=False)
        with self.connection:
            self.connection.execute(
                """
                UPDATE station
                SET max_power_kw = ?,
                    payment_methods = ?,
                    dynamic_status = ?,
                    dynamic_price = ?,
                    dynamic_updated_at = ?,
                    ocpi_live_at = ?
                WHERE id = ?
                """,
                (
                    station.max_power_kw,
                    payment_methods,
                    station.dynamic_status,
                    station.dynamic_price_eur_kwh,
                    _iso_datetime(station.dynamic_updated_at),
                    now,
                    station_id,
                ),
            )
            self.connection.execute(
                "DELETE FROM connector WHERE station_id = ?",
                (station_id,),
            )
            self.connection.executemany(
                """
                INSERT INTO connector (
                    station_id, connector_type, power_kw, voltage_v, current_a, charging_mode,
                    connector_format, status, evse_id, physical_reference
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                self._connector_insert_rows(station_id, station.connectors),
            )

    def enrich_from_ocm(
        self,
        station_id: str,
        *,
        ocm_poi_id: int,
        rating_avg: float | None,
        rating_count: int,
        comments_json: str | None,
        updated_at: datetime | None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE station
                SET ocm_poi_id = ?,
                    external_rating_avg = ?,
                    external_rating_count = ?,
                    external_comments_json = ?,
                    external_rating_updated_at = ?
                WHERE id = ?
                """,
                (
                    ocm_poi_id,
                    rating_avg,
                    rating_count,
                    comments_json,
                    _iso_datetime(updated_at),
                    station_id,
                ),
            )

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
        available_only: bool = False,
        max_price_eur_kwh: float | None = None,
        connector_types: list[str] | None = None,
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
        if available_only:
            clauses.append("UPPER(COALESCE(dynamic_status, '')) = 'AVAILABLE'")
        if max_price_eur_kwh is not None:
            clauses.append("(dynamic_price IS NULL OR dynamic_price <= ?)")
            params.append(max_price_eur_kwh)
        if connector_types:
            placeholders = ",".join("?" for _ in connector_types)
            clauses.append(
                f"""
                EXISTS (
                    SELECT 1 FROM connector c
                    WHERE c.station_id = station.id
                      AND UPPER(c.connector_type) IN ({placeholders})
                )
                """.strip()
            )
            params.extend(connector_types)

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
        available_only: bool = False,
        max_price_eur_kwh: float | None = None,
        connector_types: list[str] | None = None,
    ) -> int:
        clauses, params = self._search_clauses(
            west=west,
            south=south,
            east=east,
            north=north,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
            available_only=available_only,
            max_price_eur_kwh=max_price_eur_kwh,
            connector_types=connector_types,
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
        available_only: bool = False,
        max_price_eur_kwh: float | None = None,
        connector_types: list[str] | None = None,
        limit: int = 500,
        offset: int = 0,
        order_by: str = "power",
    ) -> list[Station]:
        clauses, params = self._search_clauses(
            west=west,
            south=south,
            east=east,
            north=north,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
            available_only=available_only,
            max_price_eur_kwh=max_price_eur_kwh,
            connector_types=connector_types,
        )

        params.extend([limit, offset])
        order_clause = "max_power_kw DESC, id" if order_by != "id" else "id"
        rows = self.connection.execute(
            f"""
            SELECT * FROM station
            WHERE {' AND '.join(clauses)}
            ORDER BY {order_clause}
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

    def count_external_ratings(self) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM station WHERE external_rating_count > 0"
        ).fetchone()
        return int(row[0]) if row else 0

    def last_ingest_run(self, source: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            """
            SELECT id, source, started_at, finished_at, source_version, records_upserted, status
            FROM ingest_run
            WHERE source = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (source,),
        ).fetchone()
        return dict(row) if row else None

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
