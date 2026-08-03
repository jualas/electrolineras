from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from api.config import settings
from api.integrations.grafana_client import GrafanaError, grafana_configured, grafana_query_sql

logger = logging.getLogger(__name__)

ConsumptionBin = Literal["highway", "mixed", "conventional", "mountain"]
ConsumptionSource = Literal["historical", "telemetry", "preset", "hybrid"]
ConsumptionConfidence = Literal["low", "medium", "high"]

# Umbrales empíricos sobre drives TeslaMate (velocidad media km/h, ascent m).
HIGHWAY_AVG_SPEED_KMH = 95.0
CONVENTIONAL_AVG_SPEED_KMH = 70.0
MOUNTAIN_ASCENT_M = 400.0
# Por defecto excluimos ciudad / trayectos cortos (el histórico TeslaMate está dominado por ellos).
DEFAULT_MIN_DRIVE_DISTANCE_KM = 20.0


@dataclass(frozen=True)
class ConsumptionBinStats:
    bin: ConsumptionBin
    wh_per_km: float | None
    kwh_per_100km: float | None
    sample_count: int
    total_distance_km: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "bin": self.bin,
            "wh_per_km": self.wh_per_km,
            "kwh_per_100km": self.kwh_per_100km,
            "sample_count": self.sample_count,
            "total_distance_km": round(self.total_distance_km, 1),
        }


@dataclass(frozen=True)
class ConsumptionProfile:
    bins: dict[ConsumptionBin, ConsumptionBinStats]
    lookback_days: int
    car_id: int | None
    source: ConsumptionSource
    available: bool
    note: str | None = None
    min_distance_km: float = DEFAULT_MIN_DRIVE_DISTANCE_KM
    drive_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "source": self.source,
            "lookback_days": self.lookback_days,
            "min_distance_km": self.min_distance_km,
            "drive_count": self.drive_count,
            "car_id": self.car_id,
            "note": self.note,
            "bins": {key: stats.as_dict() for key, stats in self.bins.items()},
        }


@dataclass(frozen=True)
class ResolvedConsumption:
    wh_per_km: float
    kwh_per_100km: float
    source: ConsumptionSource
    confidence: ConsumptionConfidence
    bin: ConsumptionBin
    note: str
    sample_count: int


DRIVES_SQL = """
SELECT
  d.distance,
  d.duration_min,
  d.ascent,
  GREATEST(0, (d.start_rated_range_km - d.end_rated_range_km) * c.efficiency) AS energy_kwh
FROM drives d
JOIN cars c ON c.id = d.car_id
WHERE d.car_id = {car_id}
  {date_filter}
  AND d.distance >= {min_distance}
  AND d.duration_min > 0
  AND d.start_rated_range_km IS NOT NULL
  AND d.end_rated_range_km IS NOT NULL
  AND c.efficiency IS NOT NULL
  AND c.efficiency > 0
ORDER BY d.start_date DESC
LIMIT 5000
"""


def classify_drive(
    *,
    distance_km: float,
    duration_min: float,
    ascent_m: float | None,
) -> ConsumptionBin:
    if distance_km <= 0 or duration_min <= 0:
        return "mixed"
    avg_speed = distance_km / (duration_min / 60.0)
    ascent = float(ascent_m or 0.0)
    if ascent >= MOUNTAIN_ASCENT_M and avg_speed < HIGHWAY_AVG_SPEED_KMH:
        return "mountain"
    if avg_speed >= HIGHWAY_AVG_SPEED_KMH:
        return "highway"
    if avg_speed <= CONVENTIONAL_AVG_SPEED_KMH:
        return "conventional"
    return "mixed"


def bin_for_route_preference(
    route_preference: str | None,
    *,
    avoid_highways: bool = False,
) -> ConsumptionBin:
    if avoid_highways or route_preference == "conventional":
        return "conventional"
    if route_preference == "shortest":
        return "mixed"
    if route_preference == "fastest":
        return "highway"
    return "mixed"


def _empty_bins() -> dict[ConsumptionBin, ConsumptionBinStats]:
    return {
        key: ConsumptionBinStats(
            bin=key,
            wh_per_km=None,
            kwh_per_100km=None,
            sample_count=0,
            total_distance_km=0.0,
        )
        for key in ("highway", "mixed", "conventional", "mountain")
    }


def profile_min_distance_km() -> float:
    return max(20.0, float(settings.consumption_profile_min_distance_km))


def aggregate_drive_rows(
    rows: list[dict[str, Any]],
    *,
    min_distance_km: float | None = None,
) -> dict[ConsumptionBin, ConsumptionBinStats]:
    min_distance = (
        DEFAULT_MIN_DRIVE_DISTANCE_KM if min_distance_km is None else float(min_distance_km)
    )
    buckets: dict[ConsumptionBin, list[tuple[float, float]]] = {
        "highway": [],
        "mixed": [],
        "conventional": [],
        "mountain": [],
    }
    for row in rows:
        try:
            distance = float(row.get("distance") or 0.0)
            duration = float(row.get("duration_min") or 0.0)
            energy_kwh = float(row.get("energy_kwh") or 0.0)
            ascent = row.get("ascent")
            ascent_m = float(ascent) if ascent is not None else None
        except (TypeError, ValueError):
            continue
        if distance < min_distance or energy_kwh <= 0:
            continue
        wh_per_km = energy_kwh * 1000.0 / distance
        if wh_per_km < 80 or wh_per_km > 350:
            continue
        bin_name = classify_drive(
            distance_km=distance,
            duration_min=duration,
            ascent_m=ascent_m,
        )
        # Viajes más largos pesan más (cuadrático suave) frente a muchos trayectos medios.
        weight = distance * (1.0 + distance / 200.0)
        buckets[bin_name].append((wh_per_km, weight, distance))

    result = _empty_bins()
    for bin_name, samples in buckets.items():
        if not samples:
            continue
        total_weight = sum(weight for _, weight, _ in samples)
        total_distance = sum(distance for _, _, distance in samples)
        if total_weight <= 0:
            continue
        weighted = sum(wh * weight for wh, weight, _ in samples) / total_weight
        result[bin_name] = ConsumptionBinStats(
            bin=bin_name,
            wh_per_km=round(weighted, 2),
            kwh_per_100km=round(weighted / 10.0, 2),
            sample_count=len(samples),
            total_distance_km=total_distance,
        )
    return result


def fetch_consumption_profile(*, car_id: int | None = None) -> ConsumptionProfile:
    # 0 = todo el histórico TeslaMate/Grafana (recomendado: pocos viajes largos).
    lookback = max(0, int(settings.consumption_profile_lookback_days))
    min_distance = profile_min_distance_km()
    resolved_car_id = car_id if car_id is not None else settings.teslamate_car_id
    if not grafana_configured():
        return ConsumptionProfile(
            bins=_empty_bins(),
            lookback_days=lookback,
            car_id=resolved_car_id,
            source="historical",
            available=False,
            note="Grafana no configurada",
            min_distance_km=min_distance,
        )
    if lookback > 0:
        date_filter = f"AND d.start_date >= NOW() - INTERVAL '{lookback} days'"
        grafana_from = f"now-{lookback}d"
        window_label = f"últimos {lookback} días"
    else:
        date_filter = ""
        grafana_from = "now-20y"
        window_label = "todo el histórico"
    sql = DRIVES_SQL.format(
        car_id=int(resolved_car_id or 1),
        date_filter=date_filter,
        min_distance=min_distance,
    )
    try:
        rows = grafana_query_sql(sql, lookback=grafana_from)
    except GrafanaError as exc:
        logger.warning("consumption profile grafana error: %s", exc)
        return ConsumptionProfile(
            bins=_empty_bins(),
            lookback_days=lookback,
            car_id=resolved_car_id,
            source="historical",
            available=False,
            note=f"Histórico no disponible: {exc}",
            min_distance_km=min_distance,
        )
    bins = aggregate_drive_rows(rows, min_distance_km=min_distance)
    drive_count = sum(stats.sample_count for stats in bins.values())
    available = drive_count > 0
    if available:
        note = (
            f"Solo viajes ≥{min_distance:.0f} km (excluye ciudad); "
            f"{drive_count} trayectos · {window_label}"
        )
    else:
        note = (
            f"Sin viajes ≥{min_distance:.0f} km en {window_label} "
            "(el histórico urbano no se usa para planificar)"
        )
    return ConsumptionProfile(
        bins=bins,
        lookback_days=lookback,
        car_id=resolved_car_id,
        source="historical",
        available=available,
        note=note,
        min_distance_km=min_distance,
        drive_count=drive_count,
    )


def _confidence(sample_count: int) -> ConsumptionConfidence:
    # Pocos viajes largos reales: umbrales más bajos que con histórico urbano.
    if sample_count >= 8:
        return "high"
    if sample_count >= 3:
        return "medium"
    return "low"


_BIN_LABELS: dict[ConsumptionBin, str] = {
    "highway": "vía rápida",
    "mixed": "mixto",
    "conventional": "vía convencional",
    "mountain": "montaña",
}


def resolve_consumption_for_route(
    profile: ConsumptionProfile,
    *,
    route_preference: str | None,
    avoid_highways: bool = False,
    fallback_wh_per_km: float,
    fallback_source: ConsumptionSource = "telemetry",
) -> ResolvedConsumption:
    preferred = bin_for_route_preference(route_preference, avoid_highways=avoid_highways)
    fallback_order: list[ConsumptionBin] = [preferred, "mixed", "highway", "conventional", "mountain"]
    chosen_bin = preferred
    stats: ConsumptionBinStats | None = None
    for candidate in fallback_order:
        candidate_stats = profile.bins.get(candidate)
        if candidate_stats and candidate_stats.wh_per_km is not None and candidate_stats.sample_count > 0:
            chosen_bin = candidate
            stats = candidate_stats
            break

    if stats is None or stats.wh_per_km is None:
        kwh100 = round(fallback_wh_per_km / 10.0, 2)
        return ResolvedConsumption(
            wh_per_km=round(fallback_wh_per_km, 2),
            kwh_per_100km=kwh100,
            source=fallback_source,
            confidence="low",
            bin=preferred,
            note="Sin histórico; usando autonomía nominal",
            sample_count=0,
        )

    label = _BIN_LABELS.get(chosen_bin, chosen_bin)
    min_km = profile.min_distance_km
    note = (
        f"Histórico {label} {stats.kwh_per_100km:.1f} kWh/100 km · "
        f"{stats.sample_count} viajes ≥{min_km:.0f} km"
    )
    source: ConsumptionSource = "historical" if chosen_bin == preferred else "hybrid"
    return ResolvedConsumption(
        wh_per_km=float(stats.wh_per_km),
        kwh_per_100km=float(stats.kwh_per_100km or stats.wh_per_km / 10.0),
        source=source,
        confidence=_confidence(stats.sample_count),
        bin=chosen_bin,
        note=note,
        sample_count=stats.sample_count,
    )
