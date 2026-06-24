from __future__ import annotations

from api.access_filters import classify_access, passes_access_filters
from models.station import Connector, Station, StationLocation


def _station(
    site_name: str | None = None,
    address: str | None = None,
    access: str | None = "public",
    payment_methods: list[str] | None = None,
) -> Station:
    return Station(
        id="test-1",
        source="es-nap-dgt",
        country="ES",
        site_name=site_name,
        location=StationLocation(lat=40.4, lon=-3.7, address=address),
        connectors=[Connector(connector_type="iec62196T2", power_kw=22.0)],
        max_power_kw=22.0,
        access=access,
        payment_methods=payment_methods or [],
        raw_ref="test-1",
    )


def test_classify_commercial_from_name() -> None:
    station = _station(site_name="Centro Comercial Nevada")
    assert classify_access(station) == "commercial_parking"


def test_classify_public_open() -> None:
    station = _station(site_name="Calle Mayor", access="public")
    assert classify_access(station) == "public_open"


def test_exclude_commercial_filter() -> None:
    commercial = _station(site_name="Shopping Xanadú")
    public = _station(site_name="Plaza del Carmen")
    assert passes_access_filters(commercial, exclude_commercial=True) is False
    assert passes_access_filters(public, exclude_commercial=True) is True


def test_ad_hoc_only_filter() -> None:
    app_only = _station(payment_methods=["app"])
    card = _station(payment_methods=["card"])
    assert passes_access_filters(app_only, ad_hoc_only=True) is False
    assert passes_access_filters(card, ad_hoc_only=True) is True
