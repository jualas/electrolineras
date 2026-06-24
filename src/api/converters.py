from __future__ import annotations

from typing import Any

from models.station import Station


def station_to_feature(station: Station) -> dict[str, Any]:
    return {
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
            "fetched_at": station.fetched_at.isoformat() if station.fetched_at else None,
            "source_version": station.source_version,
        },
    }


def stations_to_geojson(stations: list[Station]) -> list[dict[str, Any]]:
    return [station_to_feature(station) for station in stations]
