from __future__ import annotations

from dataclasses import dataclass

from api.routing.charging_plan import (
    ChargingStrategyOption,
    STRATEGY_CHARGE_NOW,
    VehicleEnergyProfile,
    effective_consumption_wh_per_km,
)
from models.station import Station

STRATEGY_ARRIVE_WITH_BUFFER = "arrive_with_buffer"

POWER_BAND_AC_SLOW = "ac_slow"
POWER_BAND_AC_FAST = "ac_fast"
POWER_BAND_DC = "dc_fast"
POWER_BAND_HPC = "hpc"


@dataclass(frozen=True)
class DestinationChargingBands:
    ac_slow: int
    ac_fast: int
    dc_fast: int
    hpc: int
    total: int
    best_max_kw: float
    nearest_km: float | None


@dataclass(frozen=True)
class DestinationStayAdvice:
    radius_km: float
    local_mobility_km: float
    local_soc_needed_pct: float
    recommended_soc_at_arrival_pct: float
    minimum_soc_at_arrival_pct: float
    projected_soc_at_arrival_pct: float | None
    arrival_gap_pct: float | None
    bands: DestinationChargingBands
    infrastructure_level: str
    charge_time_hint: str
    summary: str
    warnings: list[str]


def classify_power_band(max_kw: float) -> str:
    if max_kw >= 150:
        return POWER_BAND_HPC
    if max_kw >= 43:
        return POWER_BAND_DC
    if max_kw > 22:
        return POWER_BAND_AC_FAST
    return POWER_BAND_AC_SLOW


def _band_counts(stations: list[Station]) -> DestinationChargingBands:
    counts = {POWER_BAND_AC_SLOW: 0, POWER_BAND_AC_FAST: 0, POWER_BAND_DC: 0, POWER_BAND_HPC: 0}
    best_kw = 0.0
    for station in stations:
        band = classify_power_band(station.max_power_kw)
        counts[band] += 1
        best_kw = max(best_kw, station.max_power_kw)
    return DestinationChargingBands(
        ac_slow=counts[POWER_BAND_AC_SLOW],
        ac_fast=counts[POWER_BAND_AC_FAST],
        dc_fast=counts[POWER_BAND_DC],
        hpc=counts[POWER_BAND_HPC],
        total=len(stations),
        best_max_kw=round(best_kw, 1),
        nearest_km=None,
    )


def analyze_destination_stay(
    stations_with_distance: list[tuple[Station, float]],
    *,
    profile: VehicleEnergyProfile,
    radius_km: float,
    local_mobility_km: float = 40.0,
    projected_soc_at_arrival_pct: float | None = None,
) -> DestinationStayAdvice:
    stations = [station for station, _ in stations_with_distance]
    bands = _band_counts(stations)
    if stations_with_distance:
        nearest_km = min(distance_km for _, distance_km in stations_with_distance)
        bands = DestinationChargingBands(
            ac_slow=bands.ac_slow,
            ac_fast=bands.ac_fast,
            dc_fast=bands.dc_fast,
            hpc=bands.hpc,
            total=bands.total,
            best_max_kw=bands.best_max_kw,
            nearest_km=round(nearest_km, 2),
        )

    consumption_kwh_per_km = effective_consumption_wh_per_km(profile) / 1000.0
    local_soc_needed = 0.0
    if profile.usable_capacity_kwh > 0 and local_mobility_km > 0:
        local_energy_kwh = local_mobility_km * consumption_kwh_per_km
        local_soc_needed = (local_energy_kwh / profile.usable_capacity_kwh) * 100.0

    minimum_soc = profile.reserve_soc_percent + local_soc_needed
    warnings: list[str] = []

    if bands.total == 0:
        infrastructure_level = "none"
        recommended_soc = min(85.0, max(minimum_soc + 25.0, 50.0))
        charge_time_hint = (
            "Sin cargadores públicos en el radio analizado: llega con mucha batería "
            "o planifica una parada de carga antes del último tramo."
        )
        warnings.append("No hay cargadores detectados cerca del destino en el radio analizado.")
    elif bands.best_max_kw >= 100:
        infrastructure_level = "hpc"
        recommended_soc = max(minimum_soc, 20.0)
        charge_time_hint = (
            "HPC/DC rápido disponible: puedes llegar con menos batería y recuperar movilidad local en ~30–45 min."
        )
    elif bands.best_max_kw >= 43:
        infrastructure_level = "dc"
        recommended_soc = max(minimum_soc, 30.0)
        charge_time_hint = "DC disponible: cuenta 45–90 min de carga para movilidad local cómoda."
    elif bands.best_max_kw > 22:
        infrastructure_level = "ac_fast"
        recommended_soc = max(minimum_soc, 40.0)
        charge_time_hint = "Solo AC rápido (22–43 kW): la recarga local puede llevar varias horas."
    else:
        infrastructure_level = "ac_slow"
        recommended_soc = max(minimum_soc, 50.0)
        charge_time_hint = (
            "Infraestructura lenta (≤22 kW): prioriza llegar con más SOC o carga en ruta antes del destino."
        )

    recommended_soc = min(95.0, round(recommended_soc, 1))
    minimum_soc = min(95.0, round(minimum_soc, 1))
    local_soc_needed = round(local_soc_needed, 1)

    arrival_gap = None
    if projected_soc_at_arrival_pct is not None:
        arrival_gap = round(recommended_soc - projected_soc_at_arrival_pct, 1)
        if arrival_gap > 5:
            warnings.append(
                f"Con el plan actual llegarías con ~{projected_soc_at_arrival_pct:.0f} %; "
                f"recomendamos ≥{recommended_soc:.0f} % para moverte en la zona."
            )

    summary_parts = [
        f"{bands.total} cargadores en {radius_km:.0f} km",
        f"mejor potencia {bands.best_max_kw:.0f} kW",
        f"recomendado llegar con ≥{recommended_soc:.0f} %",
    ]
    if bands.nearest_km is not None:
        summary_parts.insert(1, f"más cercano {bands.nearest_km:.1f} km")

    return DestinationStayAdvice(
        radius_km=radius_km,
        local_mobility_km=local_mobility_km,
        local_soc_needed_pct=local_soc_needed,
        recommended_soc_at_arrival_pct=recommended_soc,
        minimum_soc_at_arrival_pct=minimum_soc,
        projected_soc_at_arrival_pct=projected_soc_at_arrival_pct,
        arrival_gap_pct=arrival_gap,
        bands=bands,
        infrastructure_level=infrastructure_level,
        charge_time_hint=charge_time_hint,
        summary=" · ".join(summary_parts),
        warnings=warnings,
    )


def build_destination_buffer_strategy(advice: DestinationStayAdvice) -> ChargingStrategyOption | None:
    if advice.projected_soc_at_arrival_pct is None:
        return None
    if advice.arrival_gap_pct is None or advice.arrival_gap_pct <= 3:
        return None
    return ChargingStrategyOption(
        id=STRATEGY_ARRIVE_WITH_BUFFER,
        label="Llegar con margen en destino",
        station_id=None,
        soc_arrival_pct=advice.recommended_soc_at_arrival_pct,
        classification=None,
        summary=(
            f"Objetivo {advice.recommended_soc_at_arrival_pct:.0f} % al llegar "
            f"(ahora estimas {advice.projected_soc_at_arrival_pct:.0f} %). "
            f"{advice.charge_time_hint}"
        ),
    )


def append_destination_strategy(
    strategies: list[ChargingStrategyOption],
    advice: DestinationStayAdvice,
) -> list[ChargingStrategyOption]:
    extra = build_destination_buffer_strategy(advice)
    if extra is None:
        return strategies
    return [extra, *strategies]
