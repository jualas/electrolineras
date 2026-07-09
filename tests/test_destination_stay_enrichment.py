from unittest.mock import MagicMock

from api.charging_plan_service import _enrich_with_destination_stay
from api.routing.charging_plan import ChargingPlanComputation, PlannedRouteStop
from test_charging_plan import sample_station


def test_enrich_with_destination_stay_keeps_planned_stops() -> None:
    station = sample_station("mid", 40.0, 0.5, kw=150.0)
    planned = [
        PlannedRouteStop(
            order=1,
            station=station,
            deviation_km=1.0,
            route_distance_km=220.0,
            extra_minutes=3.0,
            wrong_side=False,
            distance_from_origin_km=220.0,
            leg_distance_km=220.0,
            leg_driving_minutes=120.0,
            soc_arrival_pct=12.0,
            soc_departure_pct=72.0,
            charge_minutes=18.0,
            classification="safe",
        )
    ]
    computation = ChargingPlanComputation(
        range_km=300.0,
        charging_reach_km=320.0,
        soc_at_destination_pct=15.0,
        reachable_without_stop=False,
        stops=[],
        origin_stops=[],
        strategies=[],
        warnings=[],
        planned_stops=planned,
        projected_soc_at_destination_with_plan=22.0,
    )
    repo = MagicMock()
    repo.search.return_value = []

    from api.routing.charging_plan import VehicleEnergyProfile

    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=60,
        consumption_wh_per_km=170,
    )
    enriched, _stay = _enrich_with_destination_stay(
        repo,
        dest_lat=43.34,
        dest_lon=-1.79,
        vehicle=profile,
        destination_radius_km=10.0,
        local_mobility_km=40.0,
        countries=None,
        computation=computation,
        projected_soc_at_arrival_pct=15.0,
    )

    assert len(enriched.planned_stops) == 1
    assert enriched.planned_stops[0].station.id == "mid"
    assert enriched.projected_soc_at_destination_with_plan == 22.0
