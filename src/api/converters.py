from __future__ import annotations

import json
from collections import Counter, OrderedDict
from typing import Any

from models.station import Station

_STATUS_PRIORITY = {
    "AVAILABLE": 0,
    "RESERVED": 1,
    "CHARGING": 2,
    "BLOCKED": 3,
    "INOPERATIVE": 4,
    "OUTOFORDER": 5,
    "UNKNOWN": 6,
    "PLANNED": 7,
    "REMOVED": 8,
}
_DC_STATUS_MIN_KW = 43.0


def _summarize_connectors(station: Station) -> str:
    counts: Counter[int] = Counter()
    for connector in station.connectors:
        counts[int(round(connector.power_kw))] += 1
    parts: list[str] = []
    for power_kw in sorted(counts.keys(), reverse=True):
        count = counts[power_kw]
        parts.append(f"{count}×{power_kw} kW" if count > 1 else f"{power_kw} kW")
    return ", ".join(parts) if parts else "—"


def _connector_power_summary(connectors: list[dict[str, Any]]) -> str:
    counts: Counter[tuple[str, int]] = Counter()
    for connector in connectors:
        counts[(str(connector["connector_type"]), int(round(float(connector["power_kw"]))))] += 1
    parts: list[str] = []
    for (connector_type, power_kw), count in sorted(
        counts.items(),
        key=lambda item: (-item[0][1], item[0][0]),
    ):
        label = f"{connector_type} {power_kw} kW"
        parts.append(f"{count}×{label}" if count > 1 else label)
    return ", ".join(parts) if parts else "—"


def _cable_note(connector_format: str | None) -> str | None:
    if not connector_format:
        return None
    normalized = connector_format.upper()
    if normalized == "SOCKET":
        return "Lleva tu cable"
    if normalized == "CABLE":
        return "Cable fijo"
    return None


def effective_dynamic_status(station: Station) -> str | None:
    """Recalcula estado del pin desde conectores (prioriza DC si el sitio tiene DC)."""
    statuses: list[tuple[float, str]] = []
    for connector in station.connectors:
        if not connector.status:
            continue
        statuses.append((float(connector.power_kw), connector.status.upper()))
    if not statuses:
        return station.dynamic_status
    max_kw = max(power_kw for power_kw, _ in statuses)
    relevant = (
        [status for power_kw, status in statuses if power_kw >= _DC_STATUS_MIN_KW]
        if max_kw >= _DC_STATUS_MIN_KW
        else [status for _, status in statuses]
    )
    if not relevant:
        relevant = [status for _, status in statuses]
    return min(relevant, key=lambda item: _STATUS_PRIORITY.get(item, 99))


def charging_points_from_station(station: Station) -> list[dict[str, Any]]:
    """Agrupa conectores por EVSE (punto físico) cuando hay datos OCPI/REVE."""
    groups: OrderedDict[str, dict[str, Any]] = OrderedDict()
    for index, connector in enumerate(station.connectors, start=1):
        key = connector.evse_id or f"connector-{index}"
        group = groups.get(key)
        if group is None:
            groups[key] = {
                "evse_id": connector.evse_id,
                "physical_reference": connector.physical_reference,
                "status": connector.status,
                "connector_format": connector.connector_format,
                "connectors": [],
            }
            group = groups[key]
        elif group.get("status") is None and connector.status:
            group["status"] = connector.status
        if group.get("connector_format") is None and connector.connector_format:
            group["connector_format"] = connector.connector_format
        group["connectors"].append(
            {
                "connector_type": connector.connector_type,
                "power_kw": connector.power_kw,
                "connector_format": connector.connector_format,
            }
        )

    points: list[dict[str, Any]] = []
    used_labels: dict[str, int] = {}
    for order, group in enumerate(groups.values(), start=1):
        physical = group.get("physical_reference")
        base_label = (
            str(physical).strip() if isinstance(physical, str) and physical.strip() else f"Punto {order}"
        )
        seen = used_labels.get(base_label, 0)
        used_labels[base_label] = seen + 1
        label = base_label if seen == 0 else f"{base_label} ({seen + 1})"
        connectors = group["connectors"]
        points.append(
            {
                "label": label,
                "evse_id": group.get("evse_id"),
                "status": group.get("status"),
                "connector_format": group.get("connector_format"),
                "cable_note": _cable_note(group.get("connector_format")),
                "summary": _connector_power_summary(connectors),
                "connectors": connectors,
            }
        )
    return points


def station_to_feature(station: Station) -> dict[str, Any]:
    charging_points = charging_points_from_station(station)
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
            "charging_point_count": len(charging_points),
            "charging_points": json.dumps(charging_points, ensure_ascii=False),
            "address": station.location.address,
            "fetched_at": station.fetched_at.isoformat() if station.fetched_at else None,
            "source_version": station.source_version,
            "dynamic_status": effective_dynamic_status(station),
            "dynamic_price_eur_kwh": station.dynamic_price_eur_kwh,
            "dynamic_updated_at": (
                station.dynamic_updated_at.isoformat() if station.dynamic_updated_at else None
            ),
            "external_rating_avg": station.external_rating_avg,
            "external_rating_count": station.external_rating_count,
            "ocm_poi_id": station.ocm_poi_id,
            "external_comments": json.dumps(
                [
                    {
                        "rating": comment.rating,
                        "comment": comment.comment,
                        "username": comment.username,
                        "created_at": comment.created_at.isoformat() if comment.created_at else None,
                        "checkin_label": comment.checkin_label,
                    }
                    for comment in station.external_comments[:3]
                ]
            ),
        },
    }


def stations_to_geojson(stations: list[Station]) -> list[dict[str, Any]]:
    return [station_to_feature(station) for station in stations]
