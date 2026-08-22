from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

from api.config import settings
from api.integrations.grafana_client import GrafanaError, grafana_configured, grafana_query_sql
from api.integrations.teslamate_cache import teslamate_query_cache

logger = logging.getLogger(__name__)

ChargeCurveSource = Literal["historical", "preset"]

MIN_CALIBRATION_SAMPLES = 80
MIN_CALIBRATION_SESSIONS = 3

CHARGE_POWER_SQL = """
SELECT
  width_bucket(ch.battery_level, 0, 100, 10) AS soc_bucket,
  AVG(ch.charger_power) AS avg_kw,
  COUNT(*) AS samples
FROM charges ch
JOIN charging_processes cp ON cp.id = ch.charging_process_id
WHERE cp.car_id = {car_id}
  AND ch.fast_charger_present = true
  AND ch.charger_power > 10
  AND ch.battery_level IS NOT NULL
GROUP BY 1
ORDER BY 1
"""

SESSION_COUNT_SQL = """
SELECT COUNT(DISTINCT cp.id) AS sessions
FROM charging_processes cp
WHERE cp.car_id = {car_id}
  AND cp.charge_energy_added > 5
  AND cp.duration_min > 3
  AND EXISTS (
    SELECT 1 FROM charges ch
    WHERE ch.charging_process_id = cp.id
      AND ch.fast_charger_present = true
    LIMIT 1
  )
"""


@dataclass(frozen=True)
class ChargeCurvePoint:
    soc_pct: float
    avg_power_kw: float
    sample_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "soc_pct": self.soc_pct,
            "avg_power_kw": round(self.avg_power_kw, 1),
            "sample_count": self.sample_count,
        }


@dataclass(frozen=True)
class CalibratedChargeCurve:
    car_id: int | None
    available: bool
    session_count: int
    sample_count: int
    source: ChargeCurveSource
    points: tuple[tuple[float, float], ...]
    detailed_points: tuple[ChargeCurvePoint, ...] = ()
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "car_id": self.car_id,
            "available": self.available,
            "session_count": self.session_count,
            "sample_count": self.sample_count,
            "source": self.source,
            "note": self.note,
            "points": [ChargeCurvePoint(soc, kw, 0).as_dict() for soc, kw in self.points],
        }


def _soc_mid_from_bucket(bucket: int) -> float:
    return max(5.0, min(95.0, (int(bucket) - 1) * 10 + 5))


def _rows_to_curve_points(rows: list[dict[str, Any]]) -> tuple[tuple[tuple[float, float], ...], tuple[ChargeCurvePoint, ...]]:
    curve_points: list[tuple[float, float]] = []
    detailed: list[ChargeCurvePoint] = []
    for row in rows:
        try:
            bucket = int(row.get("soc_bucket") or 0)
            avg_kw = float(row.get("avg_kw") or 0.0)
            samples = int(row.get("samples") or 0)
        except (TypeError, ValueError):
            continue
        if bucket <= 0 or avg_kw <= 0:
            continue
        soc = _soc_mid_from_bucket(bucket)
        curve_points.append((soc, avg_kw))
        detailed.append(ChargeCurvePoint(soc_pct=soc, avg_power_kw=avg_kw, sample_count=samples))
    ordered = tuple(sorted(curve_points, key=lambda item: item[0]))
    detailed_ordered = tuple(sorted(detailed, key=lambda item: item.soc_pct))
    return ordered, detailed_ordered


def interpolate_calibrated_power(
    soc_pct: float,
    points: tuple[tuple[float, float], ...],
) -> float:
    if not points:
        return 0.0
    soc = max(0.0, min(100.0, soc_pct))
    if soc <= points[0][0]:
        return points[0][1]
    if soc >= points[-1][0]:
        return points[-1][1]
    for index in range(len(points) - 1):
        soc_low, power_low = points[index]
        soc_high, power_high = points[index + 1]
        if soc_low <= soc <= soc_high:
            span = max(soc_high - soc_low, 1e-6)
            blend = (soc - soc_low) / span
            return power_low + blend * (power_high - power_low)
    return points[-1][1]


def _fetch_charge_curve_uncached(*, car_id: int | None = None) -> CalibratedChargeCurve:
    resolved_car_id = car_id if car_id is not None else settings.teslamate_car_id
    if not grafana_configured():
        return CalibratedChargeCurve(
            car_id=resolved_car_id,
            available=False,
            session_count=0,
            sample_count=0,
            source="preset",
            points=(),
            note="Grafana no configurada",
        )
    car_sql_id = int(resolved_car_id or 1)
    try:
        power_rows = grafana_query_sql(
            CHARGE_POWER_SQL.format(car_id=car_sql_id),
            lookback="now-20y",
        )
        session_rows = grafana_query_sql(
            SESSION_COUNT_SQL.format(car_id=car_sql_id),
            lookback="now-20y",
        )
    except GrafanaError as exc:
        logger.warning("charge curve grafana error: %s", exc)
        return CalibratedChargeCurve(
            car_id=resolved_car_id,
            available=False,
            session_count=0,
            sample_count=0,
            source="preset",
            points=(),
            note=f"Curva DC no disponible: {exc}",
        )

    points, detailed_points = _rows_to_curve_points(power_rows)
    sample_count = sum(int(row.get("samples") or 0) for row in power_rows)
    session_count = 0
    if session_rows:
        try:
            session_count = int(session_rows[0].get("sessions") or 0)
        except (TypeError, ValueError):
            session_count = 0

    available = (
        len(points) >= 4
        and sample_count >= MIN_CALIBRATION_SAMPLES
        and session_count >= MIN_CALIBRATION_SESSIONS
    )
    if available:
        note = (
            f"Curva DC calibrada · {session_count} sesiones HPC · "
            f"{sample_count} muestras TeslaMate"
        )
        return CalibratedChargeCurve(
            car_id=resolved_car_id,
            available=True,
            session_count=session_count,
            sample_count=sample_count,
            source="historical",
            points=points,
            detailed_points=detailed_points,
            note=note,
        )
    return CalibratedChargeCurve(
        car_id=resolved_car_id,
        available=False,
        session_count=session_count,
        sample_count=sample_count,
        source="preset",
        points=points,
        detailed_points=detailed_points,
        note=(
            f"Datos DC insuficientes ({session_count} sesiones, {sample_count} muestras); "
            "usando preset del vehículo"
        ),
    )


def fetch_charge_curve(*, car_id: int | None = None) -> CalibratedChargeCurve:
    resolved_car_id = car_id if car_id is not None else settings.teslamate_car_id
    cache_key = f"charge_curve:{resolved_car_id}"
    cached = teslamate_query_cache.get(cache_key)
    if cached is not None:
        return cached  # type: ignore[return-value]
    curve = _fetch_charge_curve_uncached(car_id=car_id)
    teslamate_query_cache.set(cache_key, curve)
    return curve


def fetch_charge_curve_points(*, car_id: int | None = None) -> tuple[tuple[float, float], ...] | None:
    curve = fetch_charge_curve(car_id=car_id)
    if curve.available:
        return curve.points
    return None
