from __future__ import annotations

from api.integrations.charge_curve_service import (
    _rows_to_curve_points,
    interpolate_calibrated_power,
)
from api.routing.dc_charge_curve import estimate_dc_charge_minutes


def test_rows_to_curve_points():
    rows = [
        {"soc_bucket": 3, "avg_kw": 95.0, "samples": 100},
        {"soc_bucket": 5, "avg_kw": 120.0, "samples": 80},
    ]
    points, detailed = _rows_to_curve_points(rows)
    assert points == ((25.0, 95.0), (45.0, 120.0))
    assert detailed[0].sample_count == 100


def test_calibrated_curve_slower_mid_soc_than_preset():
    """Curva real TeslaMate (93 kW @ 40 %) tarda más que preset optimista."""
    real_points = (
        (15.0, 138.0),
        (35.0, 95.0),
        (45.0, 93.0),
        (55.0, 95.0),
        (65.0, 79.0),
        (75.0, 65.0),
    )
    preset = estimate_dc_charge_minutes(
        40.0,
        70.0,
        usable_capacity_kwh=50.0,
        station_max_kw=250.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    calibrated = estimate_dc_charge_minutes(
        40.0,
        70.0,
        usable_capacity_kwh=50.0,
        station_max_kw=250.0,
        vehicle_preset_id="tesla-model3-sr-2023",
        calibrated_points=real_points,
    )
    assert calibrated > preset
    assert interpolate_calibrated_power(45.0, real_points) == 93.0
