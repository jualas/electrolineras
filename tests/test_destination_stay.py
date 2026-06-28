from __future__ import annotations

from api.routing.charging_plan import VehicleEnergyProfile
from api.routing.destination_stay import analyze_destination_stay
from models.station import Connector, Station, StationLocation


def _station(id: str, kw: float) -> Station:
    return Station(
        id=id,
        source="test",
        country="ES",
        location=StationLocation(lat=40.0, lon=1.0),
        connectors=[Connector(connector_type="type2", power_kw=kw)],
        max_power_kw=kw,
        raw_ref=id,
    )


def _profile() -> VehicleEnergyProfile:
    return VehicleEnergyProfile(
        soc_percent=50,
        usable_capacity_kwh=57,
        consumption_wh_per_km=150,
        terrain_factor=1.25,
        reserve_soc_percent=10,
    )


def test_destination_stay_recommends_high_soc_for_slow_chargers() -> None:
    ranked = [(_station("slow", 11.0), 2.5), (_station("slow2", 22.0), 4.0)]
    advice = analyze_destination_stay(
        ranked,
        profile=_profile(),
        radius_km=10,
        local_mobility_km=40,
        projected_soc_at_arrival_pct=25,
    )
    assert advice.infrastructure_level == "ac_slow"
    assert advice.recommended_soc_at_arrival_pct >= 50
    assert advice.arrival_gap_pct is not None and advice.arrival_gap_pct > 5
    assert any("llegarías" in warning for warning in advice.warnings)


def test_destination_stay_allows_lower_arrival_with_hpc() -> None:
    ranked = [(_station("hpc", 250.0), 1.2)]
    advice = analyze_destination_stay(
        ranked,
        profile=_profile(),
        radius_km=10,
        projected_soc_at_arrival_pct=35,
    )
    assert advice.infrastructure_level == "hpc"
    assert advice.recommended_soc_at_arrival_pct <= 35
    assert advice.arrival_gap_pct is None or advice.arrival_gap_pct <= 3


def test_destination_stay_none_infrastructure() -> None:
    advice = analyze_destination_stay([], profile=_profile(), radius_km=10)
    assert advice.infrastructure_level == "none"
    assert advice.recommended_soc_at_arrival_pct >= 50
    assert advice.bands.total == 0
