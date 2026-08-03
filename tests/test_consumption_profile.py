from api.integrations.consumption_profile_service import (
    aggregate_drive_rows,
    bin_for_route_preference,
    classify_drive,
    resolve_consumption_for_route,
)
from api.integrations.consumption_profile_service import ConsumptionProfile
from api.integrations.grafana_client import _rows_from_frame


def test_classify_drive_bins():
    assert classify_drive(distance_km=120, duration_min=70, ascent_m=50) == "highway"
    assert classify_drive(distance_km=80, duration_min=90, ascent_m=20) == "conventional"
    assert classify_drive(distance_km=100, duration_min=75, ascent_m=40) == "mixed"
    assert classify_drive(distance_km=90, duration_min=80, ascent_m=500) == "mountain"


def test_bin_for_route_preference():
    assert bin_for_route_preference("fastest") == "highway"
    assert bin_for_route_preference("conventional") == "conventional"
    assert bin_for_route_preference("shortest") == "mixed"
    assert bin_for_route_preference("fastest", avoid_highways=True) == "conventional"


def test_aggregate_drive_rows_weighted():
    rows = [
        {"distance": 100, "duration_min": 55, "ascent": 20, "energy_kwh": 14.0},
        {"distance": 100, "duration_min": 55, "ascent": 10, "energy_kwh": 12.0},
        {"distance": 90, "duration_min": 100, "ascent": 30, "energy_kwh": 12.0},
        # Ciudad: se ignora con mínimo 80 km
        {"distance": 12, "duration_min": 25, "ascent": 10, "energy_kwh": 2.0},
    ]
    bins = aggregate_drive_rows(rows, min_distance_km=20)
    assert bins["highway"].sample_count == 2
    # Peso = distance * (1 + distance/200): ambos 100 km → mismo peso → media 130
    assert bins["highway"].wh_per_km == 130.0
    assert bins["highway"].kwh_per_100km == 13.0
    assert bins["conventional"].sample_count == 1
    assert bins["conventional"].wh_per_km == round(12000 / 90, 2)


def test_aggregate_ignores_city_trips():
    rows = [
        {"distance": 8, "duration_min": 20, "ascent": 5, "energy_kwh": 1.5},
        {"distance": 12, "duration_min": 25, "ascent": 10, "energy_kwh": 2.0},
    ]
    bins = aggregate_drive_rows(rows, min_distance_km=20)
    assert all(stats.sample_count == 0 for stats in bins.values())


def test_resolve_falls_back_to_telemetry():
    profile = ConsumptionProfile(
        bins=aggregate_drive_rows([]),
        lookback_days=180,
        car_id=1,
        source="historical",
        available=False,
        note="Sin datos",
    )
    resolved = resolve_consumption_for_route(
        profile,
        route_preference="fastest",
        fallback_wh_per_km=145.0,
        fallback_source="telemetry",
    )
    assert resolved.source == "telemetry"
    assert resolved.wh_per_km == 145.0
    assert "nominal" in resolved.note.lower() or "histórico" in resolved.note.lower()


def test_resolve_uses_highway_bin():
    rows = [
        {"distance": 120, "duration_min": 65, "ascent": 40, "energy_kwh": 16.2},
        {"distance": 110, "duration_min": 60, "ascent": 20, "energy_kwh": 14.5},
        {"distance": 100, "duration_min": 58, "ascent": 10, "energy_kwh": 13.0},
        {"distance": 130, "duration_min": 70, "ascent": 30, "energy_kwh": 17.0},
        {"distance": 105, "duration_min": 62, "ascent": 15, "energy_kwh": 14.0},
    ]
    profile = ConsumptionProfile(
        bins=aggregate_drive_rows(rows),
        lookback_days=180,
        car_id=1,
        source="historical",
        available=True,
    )
    resolved = resolve_consumption_for_route(
        profile,
        route_preference="fastest",
        fallback_wh_per_km=160.0,
    )
    assert resolved.source == "historical"
    assert resolved.bin == "highway"
    assert resolved.sample_count == 5
    assert resolved.confidence == "medium"
    assert "Histórico" in resolved.note
    assert "≥50" in resolved.note or "viajes" in resolved.note


def test_rows_from_grafana_frame():
    frame = {
        "schema": {
            "fields": [
                {"name": "distance"},
                {"name": "duration_min"},
                {"name": "energy_kwh"},
            ]
        },
        "data": {"values": [[100.0, 80.0], [60.0, 50.0], [14.0, 10.0]]},
    }
    rows = _rows_from_frame(frame)
    assert rows == [
        {"distance": 100.0, "duration_min": 60.0, "energy_kwh": 14.0},
        {"distance": 80.0, "duration_min": 50.0, "energy_kwh": 10.0},
    ]
