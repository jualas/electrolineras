from __future__ import annotations

from api.routing.charging_plan import (
    VehicleEnergyProfile,
    build_emergency_charging_plan,
    build_route_charging_plan,
)
from api.routing.charging_preferences import (
    ChargingPreferences,
    operator_matches,
    parse_preferred_operators,
    price_preference_rank,
)
from api.routing.corridor import CorridorMatch
from test_charging_plan import sample_station


def test_parse_preferred_operators_deduplicates() -> None:
    assert parse_preferred_operators("Ionity, ionity, Tesla") == ("ionity", "tesla")


def test_operator_matches_partial() -> None:
    assert operator_matches("Ionity España", ("ionity",))
    assert not operator_matches(None, ("ionity",))


def test_price_preference_rank_soft_penalty() -> None:
    assert price_preference_rank(0.45, 0.50) == 0.0
    assert price_preference_rank(0.55, 0.50) > 0.0
    assert price_preference_rank(None, 0.50) == 1.0


def test_build_route_charging_plan_prefers_operator() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=35,
        usable_capacity_kwh=57,
        consumption_wh_per_km=150,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    matches = [
        CorridorMatch(
            station=sample_station("cheap-other", 40.0, 0.2, price=0.40, operator="Repsol"),
            deviation_m=500,
            route_position_m=20_000,
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("ionity-stop", 40.0, 0.25, price=0.55, operator="Ionity"),
            deviation_m=600,
            route_position_m=22_000,
            extra_minutes=2.5,
            behind_route=False,
            wrong_side=False,
        ),
    ]
    prefs = ChargingPreferences(preferred_operators=("ionity",), max_price_eur_kwh=None)
    plan = build_route_charging_plan(
        matches,
        origin_position_km=0.0,
        destination_distance_km=120.0,
        profile=profile,
        limit=5,
        preferences=prefs,
    )
    assert plan.stops[0].station.id == "ionity-stop"
    assert any(strategy.id == "preferred_operator" for strategy in plan.strategies)


def test_build_emergency_plan_prefers_max_price() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=20,
        usable_capacity_kwh=57,
        consumption_wh_per_km=150,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    ranked = [
        (sample_station("expensive", 40.001, 0.001, price=0.65), 5.0),
        (sample_station("affordable", 40.002, 0.002, price=0.42), 6.0),
    ]
    prefs = ChargingPreferences(preferred_operators=(), max_price_eur_kwh=0.50)
    plan = build_emergency_charging_plan(
        ranked,
        profile=profile,
        limit=5,
        preferences=prefs,
    )
    assert plan.stops[0].station.id == "affordable"
