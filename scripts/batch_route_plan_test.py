#!/usr/bin/env python3
"""Prueba batch: destinos × tipos de ruta + visibilidad UI de paradas."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite:////app/data/db/stations.db")

from api.charging_plan_service import build_charging_plan
from api.integrations.telemetry_energy import vehicle_energy_from_telemetry
from api.integrations.vehicle_telemetry import fetch_vehicle_telemetry
from api.routing.nominatim import geocode_address
from db.repository import StationRepository

DESTINATIONS = [
    "Cerro Muriano, Córdoba, España",
    "Porto, Portugal",
    "Madrid, España",
    "Barcelona, España",
    "Sevilla, España",
    "Valencia, España",
    "Bilbao, España",
    "Zaragoza, España",
    "Granada, España",
    "Lisboa, Portugal",
    "Salamanca, España",
    "Gijón, España",
]
PREFS = ["shortest", "fastest", "conventional"]


def min_km_ui(*, route_km: float | None, duration_min: float | None, soc: float, reach_km: float) -> float:
    route_km = route_km or 0
    duration_min = duration_min or 0
    avg = route_km / (duration_min / 60) if route_km > 0 and duration_min > 0 else 90
    target_leg = avg * 2
    if soc < 10:
        return 0.0
    exclusion = max(40.0, target_leg)
    if reach_km > 0:
        exclusion = min(exclusion, max(0.0, reach_km - 30.0))
    return exclusion


def ui_visible_count(comp, *, route_km, duration_min, soc) -> int:
    if comp.planned_stops:
        return len(comp.planned_stops)
    sorted_stops = [s for s in comp.stops if s.classification != "unreachable"]
    sorted_stops.sort(key=lambda s: s.route_distance_km)
    mk = min_km_ui(route_km=route_km, duration_min=duration_min, soc=soc, reach_km=comp.charging_reach_km)
    filtered = [s for s in sorted_stops if s.route_distance_km >= mk - 1e-6]
    pool = filtered if filtered else sorted_stops
    return min(len(pool), 8)


def main() -> int:
    tel = fetch_vehicle_telemetry()
    soc, cap, wh, reserve = vehicle_energy_from_telemetry(
        tel,
        terrain_factor=1.15,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    print(f"Origin {tel.lat:.3f},{tel.lon:.3f} SOC={soc}%\n")
    print(f"{'Destino':<22} {'Ruta':<12} {'Paradas':>7} {'TrasUI':>7} {'Dest%':>6} {'1a km':>6} {'minUI':>6}")
    print("-" * 80)

    map_empty: list[tuple[str, str, int, float, float | None]] = []
    incomplete: list[tuple[str, str, int, float | None]] = []

    for dest_q in DESTINATIONS:
        try:
            dlat, dlon, label = geocode_address(dest_q)
        except Exception as exc:
            print(f"{dest_q[:22]:<22} GEO FAIL {exc}")
            continue
        short = label.split(",")[0][:20]
        for pref in PREFS:
            with StationRepository() as repo:
                built = build_charging_plan(
                    repo,
                    origin_lat=tel.lat,
                    origin_lon=tel.lon,
                    soc_percent=soc,
                    usable_capacity_kwh=cap,
                    consumption_wh_per_km=wh,
                    terrain_factor=1.15,
                    reserve_soc_percent=reserve,
                    dest_lat=dlat,
                    dest_lon=dlon,
                    min_kw=100,
                    route_preference=pref,
                    max_charge_power_kw=170,
                    min_destination_soc_pct=10,
                    min_stop_arrival_soc_pct=10,
                    max_charge_soc_pct=80,
                    exclude_slow_chargers=True,
                    vehicle_preset_id="tesla-model3-sr-2023",
                )
            comp = built.computation
            n = len(comp.planned_stops)
            mk = min_km_ui(
                route_km=built.route_distance_km,
                duration_min=built.route_duration_minutes,
                soc=soc,
                reach_km=comp.charging_reach_km,
            )
            visible = ui_visible_count(
                comp,
                route_km=built.route_distance_km,
                duration_min=built.route_duration_minutes,
                soc=soc,
            )
            proj = comp.projected_soc_at_destination_with_plan
            first_km = comp.planned_stops[0].route_distance_km if comp.planned_stops else None
            destpct = f"{proj:.0f}" if proj is not None else "-"
            flag = ""
            if visible == 0 and not comp.reachable_without_stop:
                flag = " *** MAPA VACIO ***"
                map_empty.append((short, pref, n, mk, first_km))
            elif n == 0 or proj is None or proj < 10:
                flag = " INCOMPLETO"
                incomplete.append((short, pref, n, proj))
            print(f"{short:<22} {pref:<12} {n:>7} {visible:>7} {destpct:>6} {str(first_km or '-'):>6} {mk:>6.0f}{flag}")

    print("\n=== Mapa vacio (sin paradas visibles en UI) ===")
    for row in map_empty:
        print(row)
    print(f"\nTotal mapa vacio: {len(map_empty)}")
    print(f"Total incompleto/sin paradas: {len(incomplete)}")
    return 1 if map_empty else 0


if __name__ == "__main__":
    sys.exit(main())
