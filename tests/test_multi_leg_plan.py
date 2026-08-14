from __future__ import annotations

from api.multi_leg_plan_service import (
    MultiLegStopInput,
    _can_assume_overnight_charge,
    _compact_multi_leg_warnings,
    _departure_soc_after_stop,
    apply_return_home_overnight,
    required_arrival_soc_without_overnight,
)
from api.routing.trip_metrics import format_duration_minutes
from api.schemas import (
    ChargingPlanResponse,
    DestinationChargingBandsResult,
    DestinationStayAdviceResult,
    RouteEndpoint,
    VehicleEnergyInput,
)


def _plan_with_stay(stay: DestinationStayAdviceResult, arrival: float = 13.0) -> ChargingPlanResponse:
    return ChargingPlanResponse(
        mode="route",
        vehicle=VehicleEnergyInput(
            soc_percent=71,
            usable_capacity_kwh=50,
            consumption_wh_per_km=160,
            terrain_factor=1.0,
            reserve_soc_percent=10,
        ),
        range_km=200,
        charging_reach_km=220,
        origin=RouteEndpoint(lat=37.6, lon=-1.0),
        destination=RouteEndpoint(lat=38.2, lon=-2.6),
        soc_at_destination_pct=arrival,
        projected_soc_at_destination_with_plan=arrival,
        reachable_without_stop=False,
        stops=[],
        strategies=[],
        warnings=[],
        candidates_in_bbox=2,
        destination_stay=stay,
    )


def test_required_arrival_soc_without_overnight_covers_first_charger() -> None:
    # 50 kWh, 160 Wh/km → 90 km ≈ 28.8 % + reserva 10 + buffer 5 ≈ 44 %
    needed = required_arrival_soc_without_overnight(
        usable_capacity_kwh=50,
        consumption_wh_per_km=160,
        reserve_soc_percent=10,
        min_destination_soc_pct=10,
        first_charger_km=90,
    )
    assert 40 <= needed <= 50
    assert needed == 50 or needed >= 43


def test_format_duration_minutes_hours_and_mins() -> None:
    assert format_duration_minutes(559) == "9 h 19 min"
    assert format_duration_minutes(60) == "1 h"
    assert format_duration_minutes(45) == "45 min"
    assert format_duration_minutes(0) == ""
    assert format_duration_minutes(None) == ""


def test_apply_return_home_overnight_forces_destination() -> None:
    origin_lat, origin_lon = 37.625, -0.996
    stops = [
        MultiLegStopInput(
            lat=38.218348,
            lon=-2.6170991,
            label="Camping Garrote Gordo",
            overnight=False,
            nights=None,
        ),
        MultiLegStopInput(
            lat=origin_lat,
            lon=origin_lon,
            label="Casa",
            overnight=False,
            nights=None,
        ),
    ]
    updated, notes = apply_return_home_overnight(
        stops,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
    )
    assert updated[0].overnight is True
    assert updated[0].nights == 1
    assert updated[1].overnight is False
    assert notes == []


def test_overnight_not_assumed_when_charger_far() -> None:
    stay = DestinationStayAdviceResult(
        radius_km=10,
        local_mobility_km=40,
        local_soc_needed_pct=10,
        recommended_soc_at_arrival_pct=50,
        minimum_soc_at_arrival_pct=20,
        projected_soc_at_arrival_pct=13,
        bands=DestinationChargingBandsResult(
            ac_slow=2,
            ac_fast=0,
            dc_fast=0,
            hpc=0,
            total=2,
            best_max_kw=22,
            nearest_km=10.0,
        ),
        infrastructure_level="ac_slow",
        charge_time_hint="",
        summary="2 AC lentos",
    )
    plan = _plan_with_stay(stay)
    assert _can_assume_overnight_charge(plan) == (False, 10.0)
    departure, note = _departure_soc_after_stop(plan, overnight=True, max_charge_soc_pct=80)
    assert departure == 13
    assert note is not None
    assert "10.0 km" in note
    assert "no se asume" in note.lower()


def test_overnight_assumed_when_short_drive_to_charger() -> None:
    stay = DestinationStayAdviceResult(
        radius_km=10,
        local_mobility_km=40,
        local_soc_needed_pct=10,
        recommended_soc_at_arrival_pct=50,
        minimum_soc_at_arrival_pct=20,
        projected_soc_at_arrival_pct=40,
        bands=DestinationChargingBandsResult(
            ac_slow=1,
            ac_fast=0,
            dc_fast=0,
            hpc=0,
            total=1,
            best_max_kw=11,
            nearest_km=2.3,
        ),
        infrastructure_level="ac_slow",
        charge_time_hint="",
        summary="1 AC",
    )
    plan = _plan_with_stay(stay, arrival=40.0)
    departure, note = _departure_soc_after_stop(plan, overnight=True, max_charge_soc_pct=80)
    assert departure == 80
    assert note is not None
    assert "2.3 km" in note
    assert "desplazar" in note.lower()


def test_overnight_assumed_when_charger_onsite() -> None:
    stay = DestinationStayAdviceResult(
        radius_km=10,
        local_mobility_km=40,
        local_soc_needed_pct=10,
        recommended_soc_at_arrival_pct=50,
        minimum_soc_at_arrival_pct=20,
        projected_soc_at_arrival_pct=13,
        bands=DestinationChargingBandsResult(
            ac_slow=1,
            ac_fast=0,
            dc_fast=0,
            hpc=0,
            total=1,
            best_max_kw=7,
            nearest_km=0.3,
        ),
        infrastructure_level="ac_slow",
        charge_time_hint="",
        summary="1 AC",
    )
    plan = _plan_with_stay(stay)
    departure, note = _departure_soc_after_stop(plan, overnight=True, max_charge_soc_pct=80)
    assert departure == 80
    assert note is not None
    assert "0.3 km" in note


def test_compact_multi_leg_warnings_drops_noise() -> None:
    compact = _compact_multi_leg_warnings(
        [
            "Sin paradas en ruta agotarías la batería antes del destino.",
            "Ruta larga (247 km): autonomía sin parar ~217 km.",
            "Pernocta: cargador más cercano a ~10.0 km; no se asume overnight. Salida ~13 %.",
            "Con el plan actual llegarías con ~11 %; recomendamos ≥20 % para moverte en la zona.",
            "Sin paradas en ruta agotarías la batería antes del destino.",
        ]
    )
    assert len(compact) == 2
    assert all("Sin paradas" not in w for w in compact)


def test_apply_return_home_overnight_skips_one_way() -> None:
    stops = [
        MultiLegStopInput(lat=38.2, lon=-2.6, label="Camping", overnight=False),
        MultiLegStopInput(lat=40.4, lon=-3.7, label="Madrid", overnight=False),
    ]
    updated, notes = apply_return_home_overnight(
        stops,
        origin_lat=37.6,
        origin_lon=-1.0,
    )
    assert updated[0].overnight is False
    assert notes == []
