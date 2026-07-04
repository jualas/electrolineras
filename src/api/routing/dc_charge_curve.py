from __future__ import annotations

import math
from dataclasses import dataclass

# Pérdidas cabo + BMS → batería (DC rápido).
DEFAULT_DC_EFFICIENCY = 0.88

# Tiempo fijo por sesión (conexión, negociación, ramp-up inicial).
CHARGE_SESSION_OVERHEAD_MIN = 3.0

# Paso de integración (% SOC); 0.5 % equilibra precisión y coste.
SOC_INTEGRATION_STEP = 0.5


@dataclass(frozen=True)
class DcChargeProfile:
    """Curva DC simplificada por preset (pico + zonas de taper)."""

    id: str
    peak_dc_kw: float
    usable_capacity_kwh: float
    taper_start_soc: float = 55.0
    taper_mid_soc: float = 80.0
    ramp_end_soc: float = 18.0
    efficiency: float = DEFAULT_DC_EFFICIENCY


def _profiles_by_id() -> dict[str, DcChargeProfile]:
    return {
        "tesla-model3-sr-2023": DcChargeProfile(
            id="tesla-model3-sr-2023",
            peak_dc_kw=170.0,
            usable_capacity_kwh=57.0,
            taper_start_soc=42.0,
            taper_mid_soc=78.0,
            ramp_end_soc=22.0,
        ),
        "tesla-model-y-lr": DcChargeProfile(
            id="tesla-model-y-lr",
            peak_dc_kw=250.0,
            usable_capacity_kwh=75.0,
            taper_start_soc=55.0,
        ),
        "vw-id3-pro": DcChargeProfile(
            id="vw-id3-pro",
            peak_dc_kw=125.0,
            usable_capacity_kwh=58.0,
            taper_start_soc=50.0,
        ),
        "hyundai-kona-64": DcChargeProfile(
            id="hyundai-kona-64",
            peak_dc_kw=100.0,
            usable_capacity_kwh=64.0,
            taper_start_soc=48.0,
        ),
        "renault-megane-etech": DcChargeProfile(
            id="renault-megane-etech",
            peak_dc_kw=130.0,
            usable_capacity_kwh=60.0,
            taper_start_soc=50.0,
        ),
        "bmw-i4-edrive40": DcChargeProfile(
            id="bmw-i4-edrive40",
            peak_dc_kw=205.0,
            usable_capacity_kwh=81.0,
            taper_start_soc=55.0,
        ),
        "mg4-standard": DcChargeProfile(
            id="mg4-standard",
            peak_dc_kw=135.0,
            usable_capacity_kwh=51.0,
            taper_start_soc=50.0,
        ),
        "nissan-leaf-62": DcChargeProfile(
            id="nissan-leaf-62",
            peak_dc_kw=100.0,
            usable_capacity_kwh=59.0,
            taper_start_soc=45.0,
            taper_mid_soc=75.0,
        ),
    }


GENERIC_DC_PROFILE = DcChargeProfile(
    id="generic-ev",
    peak_dc_kw=120.0,
    usable_capacity_kwh=60.0,
)


def resolve_dc_profile(
    vehicle_preset_id: str | None,
    usable_capacity_kwh: float,
) -> DcChargeProfile:
    profiles = _profiles_by_id()
    if vehicle_preset_id and vehicle_preset_id in profiles:
        return profiles[vehicle_preset_id]

    best: DcChargeProfile | None = None
    best_delta = float("inf")
    for profile in profiles.values():
        delta = abs(profile.usable_capacity_kwh - usable_capacity_kwh)
        if delta < best_delta:
            best_delta = delta
            best = profile
    if best is not None and best_delta <= 4.0:
        return best
    return GENERIC_DC_PROFILE


def dc_power_kw(
    soc_pct: float,
    *,
    profile: DcChargeProfile,
    station_max_kw: float,
) -> float:
    """Potencia instantánea (kW) entregada a la batería en un SOC dado."""
    if station_max_kw <= 0 or profile.peak_dc_kw <= 0:
        return 0.0

    cap_kw = min(profile.peak_dc_kw, station_max_kw) * profile.efficiency
    soc = max(0.0, min(100.0, soc_pct))

    if soc < profile.ramp_end_soc:
        ramp = 0.55 + 0.45 * (soc / max(profile.ramp_end_soc, 1.0))
        return cap_kw * ramp

    if soc < profile.taper_start_soc:
        return cap_kw

    if soc < profile.taper_mid_soc:
        span = max(profile.taper_mid_soc - profile.taper_start_soc, 1.0)
        taper = 1.0 - 0.72 * ((soc - profile.taper_start_soc) / span)
        return cap_kw * max(0.10, taper)

    span = max(100.0 - profile.taper_mid_soc, 1.0)
    tail = 0.28 - 0.20 * ((soc - profile.taper_mid_soc) / span)
    return cap_kw * max(0.06, tail)


def estimate_dc_charge_minutes(
    arrival_soc_pct: float,
    departure_soc_pct: float,
    *,
    usable_capacity_kwh: float,
    station_max_kw: float,
    profile: DcChargeProfile | None = None,
    vehicle_preset_id: str | None = None,
) -> float:
    """Integra la curva DC entre arrival y departure (minutos)."""
    if departure_soc_pct <= arrival_soc_pct + 0.5:
        return 0.0

    resolved = profile or resolve_dc_profile(vehicle_preset_id, usable_capacity_kwh)
    capacity = usable_capacity_kwh if usable_capacity_kwh > 0 else resolved.usable_capacity_kwh
    station_kw = max(station_max_kw, 11.0)

    minutes = 0.0
    soc = arrival_soc_pct
    while soc < departure_soc_pct - 1e-6:
        next_soc = min(departure_soc_pct, soc + SOC_INTEGRATION_STEP)
        mid_soc = (soc + next_soc) / 2.0
        power_kw = dc_power_kw(mid_soc, profile=resolved, station_max_kw=station_kw)
        if power_kw <= 0:
            break
        kwh = capacity * (next_soc - soc) / 100.0
        minutes += (kwh / power_kw) * 60.0
        soc = next_soc

    if minutes > 0:
        minutes += CHARGE_SESSION_OVERHEAD_MIN

    return float(math.ceil(minutes)) if minutes > 0 else 0.0


def estimate_linear_charge_minutes(
    arrival_soc_pct: float,
    departure_soc_pct: float,
    *,
    usable_capacity_kwh: float,
    max_power_kw: float,
    efficiency: float = 0.72,
) -> float:
    """Estimación lineal legacy (referencia en tests)."""
    if departure_soc_pct <= arrival_soc_pct + 0.5:
        return 0.0
    kwh_needed = usable_capacity_kwh * (departure_soc_pct - arrival_soc_pct) / 100.0
    effective_kw = max(11.0, max_power_kw * efficiency)
    return round((kwh_needed / effective_kw) * 60.0, 0)
