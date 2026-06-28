from __future__ import annotations

from collections import Counter
from typing import Any

from models.station import Station


def _summarize_connectors(station: Station) -> str:
    counts: Counter[int] = Counter()
    for connector in station.connectors:
        counts[int(round(connector.power_kw))] += 1
    parts: list[str] = []
    for power_kw in sorted(counts.keys(), reverse=True):
        count = counts[power_kw]
        parts.append(f"{count}×{power_kw} kW" if count > 1 else f"{power_kw} kW")
    return ", ".join(parts) if parts else "—"


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
            "connector_summary": _summarize_connectors(station),
            "address": station.location.address,
            "fetched_at": station.fetched_at.isoformat() if station.fetched_at else None,
            "source_version": station.source_version,
            "dynamic_status": station.dynamic_status,
            "dynamic_price_eur_kwh": station.dynamic_price_eur_kwh,
            "dynamic_updated_at": (
                station.dynamic_updated_at.isoformat() if station.dynamic_updated_at else None
            ),
            "external_rating_avg": station.external_rating_avg,
            "external_rating_count": station.external_rating_count,
            "ocm_poi_id": station.ocm_poi_id,
            "external_comments": [
                {
                    "rating": comment.rating,
                    "comment": comment.comment,
                    "username": comment.username,
                    "created_at": comment.created_at.isoformat() if comment.created_at else None,
                    "checkin_label": comment.checkin_label,
                }
                for comment in station.external_comments[:3]
            ],
        },
    }


def stations_to_geojson(stations: list[Station]) -> list[dict[str, Any]]:
    return [station_to_feature(station) for station in stations]
