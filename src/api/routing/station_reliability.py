from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from api.config import settings
from api.integrations.google_places_ev import (
    GooglePlacesEvError,
    GooglePlacesEvSnapshot,
    fetch_google_places_ev_status,
)
from db.repository import StationRepository
from db.spatial import haversine_m
from models.station import Station

logger = logging.getLogger(__name__)

ReliabilityLevel = Literal["high", "medium", "low"]

_REVE_BROKEN_STATUSES = frozenset({"OUTOFORDER", "INOPERATIVE", "REMOVED"})
_REVE_BUSY_STATUSES = frozenset({"CHARGING", "RESERVED", "BLOCKED"})
_REVE_OK_STATUSES = frozenset({"AVAILABLE"})
_STALE_TELEMETRY_MINUTES = 60.0


@dataclass(frozen=True)
class StationReliabilityReport:
    station_id: str
    level: ReliabilityLevel
    score: int
    summary: str
    warnings: list[str] = field(default_factory=list)
    connector_count: int = 0
    single_connector: bool = False
    isolation_radius_km: float = 50.0
    isolated_area: bool = False
    backup_stations_in_radius: int = 0
    backup_station_km: float | None = None
    backup_station_label: str | None = None
    reve_status: str | None = None
    reve_updated_at: datetime | None = None
    reve_age_minutes: float | None = None
    google_checked: bool = False
    google_matched: bool = False
    google_status: str | None = None
    google_available_count: int | None = None
    google_out_of_service_count: int | None = None
    google_total_connectors: int | None = None
    google_last_update: str | None = None
    google_rating: float | None = None
    google_rating_count: int | None = None
    google_maps_uri: str | None = None


def _station_label(station: Station) -> str:
    if station.site_name:
        return station.site_name
    if station.operator:
        return f"{station.operator} ({station.max_power_kw:.0f} kW)"
    return station.id


def _age_minutes(dt: datetime | None, *, now: datetime) -> float | None:
    if dt is None:
        return None
    aware = dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)
    return max(0.0, round((now - aware.astimezone(UTC)).total_seconds() / 60.0, 1))


def _find_backup_stations(
    repo: StationRepository,
    station: Station,
    *,
    radius_km: float,
    min_backup_kw: float,
) -> tuple[int, float | None, str | None]:
    """Busca cargadores alternativos elegibles en SQLite local (0 llamadas externas)."""
    lat = station.location.lat
    lon = station.location.lon
    radius_m = max(1000.0, radius_km * 1000.0)
    lat_pad = radius_m / 111_320.0
    cos_lat = max(0.1, abs(math.cos(math.radians(lat))))
    lon_pad = radius_m / (111_320.0 * cos_lat)

    candidates = repo.search(
        west=lon - lon_pad,
        south=lat - lat_pad,
        east=lon + lon_pad,
        north=lat + lat_pad,
        min_kw=min_backup_kw,
        limit=2000,
        offset=0,
    )

    alternatives: list[tuple[float, Station]] = []
    for cand in candidates:
        if cand.id == station.id:
            continue
        if (cand.dynamic_status or "").upper() in _REVE_BROKEN_STATUSES:
            continue
        dist_m = haversine_m(lat, lon, cand.location.lat, cand.location.lon)
        # Ignorar duplicados o postes del mismo recinto (<300 m): no son un plan B independiente.
        if 300.0 <= dist_m <= radius_m:
            alternatives.append((dist_m / 1000.0, cand))

    if not alternatives:
        return 0, None, None

    alternatives.sort(key=lambda item: item[0])
    nearest_km, nearest_station = alternatives[0]
    return len(alternatives), round(nearest_km, 1), _station_label(nearest_station)


def evaluate_station_reliability(
    station: Station,
    *,
    backup_count: int,
    backup_km: float | None,
    backup_label: str | None,
    isolation_radius_km: float = 50.0,
    google_snapshot: GooglePlacesEvSnapshot | None = None,
    google_checked: bool = False,
    google_error: str | None = None,
    now: datetime | None = None,
) -> StationReliabilityReport:
    """Combina telemetría REVE, Google Places EV y redundancia de zona en un semáforo claro."""
    resolved_now = now or datetime.now(UTC)
    warnings: list[str] = []
    score = 65

    connector_count = len(station.connectors)
    if google_snapshot and google_snapshot.total_connectors:
        connector_count = max(connector_count, google_snapshot.total_connectors)
    single_connector = connector_count <= 1
    isolated_area = backup_count == 0

    reve_status = (station.dynamic_status or "").strip().upper() or None
    reve_age = _age_minutes(station.dynamic_updated_at, now=resolved_now)

    # 1. Evaluación REVE / estado dinámico local
    reve_broken = reve_status in _REVE_BROKEN_STATUSES
    reve_ok = reve_status in _REVE_OK_STATUSES
    reve_busy = reve_status in _REVE_BUSY_STATUSES

    if reve_broken:
        score -= 55
        warnings.append(f"REVE marca la estación como fuera de servicio ({reve_status}).")
    elif reve_ok:
        score += 15
    elif reve_busy:
        score += 0
        warnings.append("REVE indica conectores ocupados o reservados actualmente.")
    else:
        score -= 10
        warnings.append("Sin telemetría REVE en vivo para esta estación.")

    if reve_age is not None and reve_age > _STALE_TELEMETRY_MINUTES:
        score -= 8
        warnings.append(f"Estado REVE antiguo (actualizado hace ~{int(reve_age)} min).")

    # 2. Verificación cruzada Google Places API (New)
    google_broken = False
    google_confirmed_available = False
    google_matched = google_snapshot is not None

    if google_error:
        warnings.append("No se pudo verificar en vivo con Google Places; se muestran datos locales.")
    elif google_snapshot is not None:
        g_status = (google_snapshot.business_status or "").upper() or None
        if g_status in {"CLOSED_TEMPORARILY", "CLOSED_PERMANENTLY"}:
            google_broken = True
            score -= 60
            warnings.append(f"Google Maps indica la estación cerrada ({g_status}).")

        avail = google_snapshot.available_count
        out_svc = google_snapshot.out_of_service_count
        total_g = google_snapshot.total_connectors

        if out_svc is not None and out_svc > 0:
            if total_g is not None and out_svc >= total_g:
                google_broken = True
                score -= 55
                warnings.append(
                    f"Google Places reporta todos los conectores fuera de servicio ({out_svc}/{total_g})."
                )
            else:
                score -= 15
                warnings.append(
                    f"Google Places reporta {out_svc} conector(es) fuera de servicio."
                )

        if avail is not None:
            if avail > 0 and not google_broken:
                google_confirmed_available = True
                score += 15
            elif avail == 0 and not google_broken:
                score -= 15
                warnings.append("Google Places indica 0 conectores libres en este momento.")

        if google_snapshot.rating is not None and google_snapshot.rating < 3.0 and (
            google_snapshot.user_rating_count or 0
        ) >= 3:
            score -= 15
            warnings.append(
                f"Valoración baja en Google Maps ({google_snapshot.rating:.1f}/5 con "
                f"{google_snapshot.user_rating_count} reseñas): revisa comentarios recientes."
            )

    # 3. Redundancia física y aislamiento (caso sierra)
    if single_connector:
        score -= 12
        warnings.append("Estación con un único conector: si falla o está ocupado no hay margen en el sitio.")

    if isolated_area:
        score -= 18
        warnings.append(
            f"Zona aislada: no hay otro cargador rápido alternativo en un radio de "
            f"{isolation_radius_km:.0f} km. Llega con margen o revisa reseñas antes de salir."
        )
    elif backup_km is not None and backup_km >= 25.0:
        score -= 5
        warnings.append(
            f"Alternativa rápida más cercana a {backup_km:.1f} km ({backup_label or 'respaldo'})."
        )

    score = max(0, min(100, score))

    # 4. Clasificación en semáforo
    if reve_broken or google_broken or score < 40:
        level: ReliabilityLevel = "low"
    elif (
        score >= 75
        and not isolated_area
        and not single_connector
        and (reve_ok or google_confirmed_available)
    ):
        level = "high"
    else:
        level = "medium"

    # 5. Resumen corto para el conductor
    if level == "low":
        if google_broken and reve_broken:
            summary = "No fiable: fuera de servicio según REVE y Google."
        elif google_broken:
            summary = "No fiable: Google Maps reporta incidencia o cierre."
        elif reve_broken:
            summary = "No fiable: REVE reporta estación fuera de servicio."
        else:
            summary = "Fiabilidad baja: comprueba reseñas y plan B antes de depender de este punto."
    elif level == "high":
        if reve_ok and google_confirmed_available:
            summary = f"Alta confianza: disponible confirmado (REVE + Google) · {connector_count} conectores."
        elif google_confirmed_available:
            summary = f"Alta confianza: disponible en Google Places · {connector_count} conectores."
        else:
            summary = f"Alta confianza: disponible en REVE · {connector_count} conectores."
    else:
        if isolated_area:
            summary = f"Precaución (zona aislada): único punto rápido en {isolation_radius_km:.0f} km."
        elif single_connector:
            summary = "Precaución: estación de 1 solo conector; verifica antes de apurar batería."
        else:
            summary = "Precaución: verificación parcial; conviene comprobar estado/reseñas."

    fallback_maps_uri = (
        google_snapshot.google_maps_uri
        if google_snapshot and google_snapshot.google_maps_uri
        else f"https://www.google.com/maps/search/?api=1&query={station.location.lat:.6f},{station.location.lon:.6f}"
    )

    return StationReliabilityReport(
        station_id=station.id,
        level=level,
        score=score,
        summary=summary,
        warnings=warnings,
        connector_count=connector_count,
        single_connector=single_connector,
        isolation_radius_km=isolation_radius_km,
        isolated_area=isolated_area,
        backup_stations_in_radius=backup_count,
        backup_station_km=backup_km,
        backup_station_label=backup_label,
        reve_status=reve_status,
        reve_updated_at=station.dynamic_updated_at,
        reve_age_minutes=reve_age,
        google_checked=google_checked,
        google_matched=google_matched,
        google_status=google_snapshot.business_status if google_snapshot else None,
        google_available_count=google_snapshot.available_count if google_snapshot else None,
        google_out_of_service_count=(
            google_snapshot.out_of_service_count if google_snapshot else None
        ),
        google_total_connectors=google_snapshot.total_connectors if google_snapshot else None,
        google_last_update=google_snapshot.availability_last_update if google_snapshot else None,
        google_rating=google_snapshot.rating if google_snapshot else None,
        google_rating_count=google_snapshot.user_rating_count if google_snapshot else None,
        google_maps_uri=fallback_maps_uri,
    )


def inspect_station_reliability(
    repo: StationRepository,
    station: Station,
    *,
    verify_google: bool = True,
    isolation_radius_km: float | None = None,
    min_backup_kw: float | None = None,
) -> StationReliabilityReport:
    """Ejecuta el modelo mixto completo (SQLite local + Google Places EV bajo demanda)."""
    resolved_radius = (
        float(isolation_radius_km)
        if isolation_radius_km is not None
        else settings.reliability_isolation_radius_km
    )
    resolved_min_kw = (
        float(min_backup_kw)
        if min_backup_kw is not None
        else min(settings.reliability_min_backup_kw, max(22.0, station.max_power_kw))
    )

    backup_count, backup_km, backup_label = _find_backup_stations(
        repo,
        station,
        radius_km=resolved_radius,
        min_backup_kw=resolved_min_kw,
    )

    google_snapshot: GooglePlacesEvSnapshot | None = None
    google_checked = False
    google_error: str | None = None

    should_call_google = (
        verify_google
        and settings.google_places_ev_enabled
        and bool(settings.google_maps_api_key.strip())
    )
    if should_call_google:
        google_checked = True
        try:
            google_snapshot = fetch_google_places_ev_status(
                station.location.lat,
                station.location.lon,
            )
        except GooglePlacesEvError as exc:
            logger.warning("Fallo verificando estación %s en Google Places: %s", station.id, exc)
            google_error = str(exc)

    return evaluate_station_reliability(
        station,
        backup_count=backup_count,
        backup_km=backup_km,
        backup_label=backup_label,
        isolation_radius_km=resolved_radius,
        google_snapshot=google_snapshot,
        google_checked=google_checked,
        google_error=google_error,
    )
