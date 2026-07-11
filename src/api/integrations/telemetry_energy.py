from __future__ import annotations

from api.integrations.teslamate import TeslaMateError, VehicleTelemetry
from api.routing.dc_charge_curve import GENERIC_DC_PROFILE, resolve_dc_profile


def nominal_range_km(telemetry: VehicleTelemetry) -> float | None:
    """Autonomía nominal al 100 % (rated_battery_range_km en TeslaMate)."""
    rated = telemetry.rated_battery_range_km
    if rated is not None and rated > 0:
        return rated
    return None


def current_range_from_nominal(telemetry: VehicleTelemetry) -> float | None:
    """Autonomía instantánea: nominal × SOC (como el cuadro de TeslaMate)."""
    rated = nominal_range_km(telemetry)
    soc = telemetry.battery_level_pct
    if rated is None or soc <= 0:
        return None
    return rated * soc / 100.0


def resolve_telemetry_capacity_kwh(
    *,
    vehicle_preset_id: str | None = None,
    usable_capacity_kwh: float | None = None,
    telemetry: VehicleTelemetry | None = None,
) -> float:
    if usable_capacity_kwh is not None and usable_capacity_kwh > 0:
        return usable_capacity_kwh
    if telemetry is not None:
        from_telemetry = _capacity_kwh_from_telemetry_model(telemetry)
        if from_telemetry is not None:
            return from_telemetry
    if vehicle_preset_id:
        return resolve_dc_profile(vehicle_preset_id, GENERIC_DC_PROFILE.usable_capacity_kwh).usable_capacity_kwh
    return GENERIC_DC_PROFILE.usable_capacity_kwh


def _capacity_kwh_from_telemetry_model(telemetry: VehicleTelemetry) -> float | None:
    """Capacidad útil aproximada según modelo TeslaMate (p. ej. Model 3 50)."""
    label = (telemetry.car_model_label or "").lower()
    trim = (telemetry.trim_badging or "").lower()
    model = (telemetry.model or "").strip()
    if model == "3" or "model 3" in label:
        if "50" in label or trim in {"50", "sr", "standard", "standard range"}:
            return 50.0
        if "lr" in label or "long" in label or trim in {"long range", "lr"}:
            return 75.0
    if model == "y" or "model y" in label:
        if "lr" in label or "long" in label:
            return 75.0
    return None


def vehicle_energy_from_telemetry(
    telemetry: VehicleTelemetry,
    terrain_factor: float = 1.0,
    reserve_soc_percent: float = 10.0,
    departure_soc_percent: float | None = None,
    vehicle_preset_id: str | None = None,
    usable_capacity_kwh: float | None = None,
) -> tuple[float, float, float, float]:
    """
    Perfil de energía desde autonomía nominal TeslaMate (rated_battery_range_km).

    No usa est_battery_range_km: en MQTT puede divergir del valor nominal del cuadro.
    `departure_soc_percent` simula carga previa a la salida (p. ej. cargar en casa).
    """
    rated_km = nominal_range_km(telemetry)
    live_soc = telemetry.battery_level_pct
    soc = live_soc if departure_soc_percent is None else min(100.0, max(5.0, departure_soc_percent))
    if rated_km is None:
        raise TeslaMateError("TeslaMate sin rated_battery_range_km (autonomía nominal)")
    if soc <= 0:
        raise TeslaMateError("SOC inválido en telemetría")

    terrain = max(0.01, min(2.0, terrain_factor))
    capacity = resolve_telemetry_capacity_kwh(
        vehicle_preset_id=vehicle_preset_id,
        usable_capacity_kwh=usable_capacity_kwh,
        telemetry=telemetry,
    )
    # Consumo coherente con capacidad útil y autonomía nominal TeslaMate al 100 %
    consumption_wh_per_km = (capacity * 1000.0 / rated_km) * terrain
    return soc, capacity, consumption_wh_per_km, reserve_soc_percent


def planning_range_km(
    nominal_km: float,
    soc_percent: float,
    reserve_soc_percent: float = 10.0,
) -> float:
    if nominal_km <= 0 or soc_percent <= 0:
        return 0.0
    usable_soc = max(0.0, soc_percent - reserve_soc_percent)
    return nominal_km * usable_soc / 100.0


def charging_reach_km(
    nominal_km: float,
    soc_percent: float,
    min_arrival_soc_percent: float = 5.0,
) -> float:
    if nominal_km <= 0 or soc_percent <= 0:
        return 0.0
    usable_soc = max(0.0, soc_percent - min_arrival_soc_percent)
    return nominal_km * usable_soc / 100.0
