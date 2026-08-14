from __future__ import annotations

from datetime import UTC, datetime
import re
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

# Para el estado del emplazamiento, priorizar EVSE DC (≥ semi-rápido).
_DC_STATUS_MIN_KW = 43.0


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


def _connector_format(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = raw.strip().upper()
    if normalized in {"CABLE", "SOCKET"}:
        return normalized
    return normalized


def _energy_price_eur_kwh(connector: dict[str, Any]) -> float | None:
    """Precio ENERGY publicado por REVE/OCPI (misma cifra que muestra mapareve).

    No se descuenta el IVA: el campo ``price`` + etiqueta humana de REVE coinciden
    con lo que ve el usuario (p. ej. 0.44 EUR/kWh).
    """
    prices: list[float] = []
    for tariff_wrap in connector.get("tariffs") or []:
        if not isinstance(tariff_wrap, dict):
            continue
        # Preferir etiqueta humana cuando exista ("0.44 EUR/kWh").
        for human in tariff_wrap.get("human") or []:
            if not isinstance(human, str):
                continue
            match = re.search(r"(\d+(?:[.,]\d+)?)\s*EUR", human, flags=re.IGNORECASE)
            if match:
                human_price = _parse_float(match.group(1).replace(",", "."))
                if human_price is not None:
                    prices.append(human_price)
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
                    prices.append(price)
    if not prices:
        return None
    return min(prices)


def _evse_max_power_kw(evse: dict[str, Any]) -> float:
    powers: list[float] = []
    for connector in evse.get("connectors") or []:
        if not isinstance(connector, dict):
            continue
        power_w = _parse_float(connector.get("max_electric_power"))
        if power_w is not None:
            powers.append(power_w / 1000.0)
    return max(powers) if powers else 0.0


def _aggregate_status(evses: list[dict[str, Any]]) -> str | None:
    """Estado del sitio alineado con carga útil (DC), no con un AC libre residual."""
    statuses: list[tuple[float, str]] = []
    for evse in evses:
        status = evse.get("status")
        if isinstance(status, str) and status:
            statuses.append((_evse_max_power_kw(evse), status.upper()))
    if not statuses:
        return None
    max_kw = max(power_kw for power_kw, _ in statuses)
    relevant = (
        [status for power_kw, status in statuses if power_kw >= _DC_STATUS_MIN_KW]
        if max_kw >= _DC_STATUS_MIN_KW
        else [status for _, status in statuses]
    )
    if not relevant:
        relevant = [status for _, status in statuses]
    return min(relevant, key=lambda item: _STATUS_PRIORITY.get(item, 99))


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
    prices_by_power: list[tuple[float, float]] = []
    for evse in evses:
        if not isinstance(evse, dict):
            continue
        evse_status = evse.get("status")
        status = evse_status.upper() if isinstance(evse_status, str) and evse_status else None
        evse_id = evse.get("evse_id") if isinstance(evse.get("evse_id"), str) else None
        physical_reference = (
            evse.get("physical_reference")
            if isinstance(evse.get("physical_reference"), str)
            else None
        )
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
                    connector_format=_connector_format(connector.get("format")),
                    status=status,
                    evse_id=evse_id,
                    physical_reference=physical_reference,
                )
            )
            price = _energy_price_eur_kwh(connector)
            if price is not None:
                prices_by_power.append((power_kw, price))

    max_power_kw = max((connector.power_kw for connector in connectors), default=0.0)
    dynamic_status = _aggregate_status(evses)
    # Precio del emplazamiento: el de los conectores DC/rápidos (como muestra REVE al mirar CCS),
    # no el mínimo del AC lento del mismo parking.
    if any(power_kw >= _DC_STATUS_MIN_KW for power_kw, _ in prices_by_power):
        dynamic_price = min(
            price for power_kw, price in prices_by_power if power_kw >= _DC_STATUS_MIN_KW
        )
    else:
        dynamic_price = min((price for _, price in prices_by_power), default=None)
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
