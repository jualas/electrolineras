from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from models.station import Connector, Station, StationLocation

REVE_SOURCE = "es-reve-public"

_CONNECTOR_STANDARD: dict[str, str] = {
    "IEC_62196_T2_COMBO": "CCS2",
    "IEC_62196_T2": "Type2",
    "CHADEMO": "CHAdeMO",
    "TESLA_S": "Tesla",
    "TESLA_R": "Tesla",
}

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


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _connector_type(standard: str | None) -> str:
    if not standard:
        return "unknown"
    return _CONNECTOR_STANDARD.get(standard, standard)


def _energy_price_eur_kwh(connector: dict[str, Any]) -> float | None:
    prices: list[float] = []
    for tariff_wrap in connector.get("tariffs") or []:
        if not isinstance(tariff_wrap, dict):
            continue
        tariff = tariff_wrap.get("tariff")
        if not isinstance(tariff, dict):
            continue
        for element in tariff.get("elements") or []:
            if not isinstance(element, dict):
                continue
            for component in element.get("price_components") or []:
                if not isinstance(component, dict):
                    continue
                if component.get("type") != "ENERGY":
                    continue
                price = _parse_float(component.get("price"))
                if price is not None:
                    vat = _parse_float(component.get("vat"))
                    if vat is not None and vat > 0:
                        price = price / (1.0 + vat / 100.0)
                    prices.append(price)
    if not prices:
        return None
    return min(prices)


def _aggregate_status(evses: list[dict[str, Any]]) -> str | None:
    statuses: list[str] = []
    for evse in evses:
        status = evse.get("status")
        if isinstance(status, str) and status:
            statuses.append(status.upper())
    if not statuses:
        return None
    return min(statuses, key=lambda item: _STATUS_PRIORITY.get(item, 99))


def _parse_updated_at(evses: list[dict[str, Any]]) -> datetime | None:
    timestamps: list[datetime] = []
    for evse in evses:
        for key in ("status_updated_at", "last_updated"):
            raw = evse.get(key)
            if not isinstance(raw, str):
                continue
            try:
                timestamps.append(datetime.fromisoformat(raw.replace("Z", "+00:00")))
            except ValueError:
                continue
    if not timestamps:
        return None
    return max(timestamps).astimezone(UTC)


def _payment_methods(evses: list[dict[str, Any]]) -> list[str]:
    methods: list[str] = []
    seen: set[str] = set()
    for evse in evses:
        for method in evse.get("payment_methods") or []:
            if not isinstance(method, str):
                continue
            normalized = method.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            methods.append(normalized)
    return methods


def location_to_station(location: dict[str, Any], *, fetched_at: datetime | None = None) -> Station:
    location_id = str(location["id"])
    coords = location.get("coordinates") or {}
    lat = _parse_float(coords.get("latitude"))
    lon = _parse_float(coords.get("longitude"))
    if lat is None or lon is None:
        msg = f"REVE location sin coordenadas: {location_id}"
        raise ValueError(msg)

    owner = location.get("owner") or {}
    operator = owner.get("name") if isinstance(owner, dict) else None
    address_parts = [location.get("address"), location.get("postal_code")]
    address = (
        ", ".join(part for part in address_parts if isinstance(part, str) and part.strip()) or None
    )

    evses = location.get("evses") or []
    connectors: list[Connector] = []
    prices: list[float] = []
    for evse in evses:
        if not isinstance(evse, dict):
            continue
        for connector in evse.get("connectors") or []:
            if not isinstance(connector, dict):
                continue
            power_w = _parse_float(connector.get("max_electric_power"))
            power_kw = (power_w / 1000.0) if power_w else 0.0
            connectors.append(
                Connector(
                    connector_type=_connector_type(connector.get("standard")),
                    power_kw=power_kw,
                    charging_mode="mode4DC" if power_kw >= 43 else "mode3AC3p",
                )
            )
            price = _energy_price_eur_kwh(connector)
            if price is not None:
                prices.append(price)

    max_power_kw = max((connector.power_kw for connector in connectors), default=0.0)
    dynamic_status = _aggregate_status(evses)
    dynamic_price = min(prices) if prices else None
    dynamic_updated_at = _parse_updated_at(evses)

    opening = location.get("opening_times") or {}
    opening_hours = "24/7" if isinstance(opening, dict) and opening.get("twentyfourseven") else None

    now = fetched_at or datetime.now(UTC)
    return Station(
        id=f"es-reve-{location_id}",
        source=REVE_SOURCE,
        country="ES",
        site_name=location.get("name"),
        operator=operator,
        location=StationLocation(lat=lat, lon=lon, address=address),
        connectors=connectors,
        max_power_kw=max_power_kw,
        access="public",
        payment_methods=_payment_methods(evses),
        opening_hours=opening_hours,
        raw_ref=location_id,
        fetched_at=now,
        source_version="reve-public-api",
        dynamic_status=dynamic_status,
        dynamic_price_eur_kwh=dynamic_price,
        dynamic_updated_at=dynamic_updated_at,
    )
