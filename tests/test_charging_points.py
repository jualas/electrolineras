from __future__ import annotations

import json

from api.converters import charging_points_from_station, station_to_feature
from models.station import Connector, Station, StationLocation


def _station(connectors: list[Connector]) -> Station:
    return Station(
        id="es-reve-test",
        source="es-reve-public",
        country="ES",
        site_name="ALDI Cartagena",
        operator="Test",
        location=StationLocation(lat=37.62, lon=-0.95, address="Cartagena"),
        connectors=connectors,
        max_power_kw=max((item.power_kw for item in connectors), default=0.0),
        access="public",
        payment_methods=[],
        raw_ref="test",
        dynamic_status="AVAILABLE",
    )


def test_charging_points_group_by_evse_with_individual_status() -> None:
    station = _station(
        [
            Connector(
                connector_type="CCS2",
                power_kw=100.0,
                status="AVAILABLE",
                evse_id="EVSE-1",
                physical_reference="A1",
            ),
            Connector(
                connector_type="CCS2",
                power_kw=100.0,
                status="CHARGING",
                evse_id="EVSE-2",
                physical_reference="A2",
            ),
        ]
    )
    points = charging_points_from_station(station)
    assert len(points) == 2
    assert points[0]["label"] == "A1"
    assert points[0]["status"] == "AVAILABLE"
    assert points[1]["label"] == "A2"
    assert points[1]["status"] == "CHARGING"

    feature = station_to_feature(station)
    payload = json.loads(feature["properties"]["charging_points"])
    assert feature["properties"]["charging_point_count"] == 2
    assert payload[1]["status"] == "CHARGING"


def test_charging_points_without_evse_metadata_are_sequential() -> None:
    station = _station(
        [
            Connector(connector_type="CCS2", power_kw=100.0),
            Connector(connector_type="CCS2", power_kw=100.0),
        ]
    )
    points = charging_points_from_station(station)
    assert [point["label"] for point in points] == ["Punto 1", "Punto 2"]


def test_charging_points_include_cable_note_for_socket() -> None:
    station = _station(
        [
            Connector(
                connector_type="CCS2",
                power_kw=49.0,
                status="AVAILABLE",
                evse_id="DC-1",
                connector_format="CABLE",
            ),
            Connector(
                connector_type="Type2",
                power_kw=22.0,
                status="AVAILABLE",
                evse_id="AC-1",
                connector_format="SOCKET",
            ),
        ]
    )
    points = charging_points_from_station(station)
    assert points[0]["cable_note"] == "Cable fijo"
    assert points[1]["cable_note"] == "Lleva tu cable"


def test_effective_status_ignores_free_ac_when_dc_busy() -> None:
    from api.converters import effective_dynamic_status

    station = _station(
        [
            Connector(connector_type="Type2", power_kw=22.0, status="AVAILABLE", evse_id="AC-1"),
            Connector(
                connector_type="CCS2",
                power_kw=49.0,
                status="CHARGING",
                evse_id="ES*ERA*E250621*1",
            ),
            Connector(
                connector_type="CCS2",
                power_kw=49.0,
                status="CHARGING",
                evse_id="ES*ERA*E250622*2",
            ),
        ]
    )
    assert effective_dynamic_status(station) == "CHARGING"
    feature = station_to_feature(station)
    assert feature["properties"]["dynamic_status"] == "CHARGING"
