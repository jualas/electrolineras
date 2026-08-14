from __future__ import annotations

from api.access_filters import classify_access, passes_access_filters
from models.station import Connector, Station, StationLocation


def _station(
    site_name: str | None = None,
    address: str | None = None,
    access: str | None = "public",
    payment_methods: list[str] | None = None,
    max_power_kw: float = 22.0,
) -> Station:
    return Station(
        id="test-1",
        source="es-nap-dgt",
        country="ES",
        site_name=site_name,
        location=StationLocation(lat=40.4, lon=-3.7, address=address),
        connectors=[Connector(connector_type="iec62196T2", power_kw=max_power_kw)],
        max_power_kw=max_power_kw,
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


def test_public_open_only_keeps_official_inventory() -> None:
    """Alineado con REVE/NAP: no ocultar tiendas ni interiores del inventario oficial."""
    mercadona_slow = _station(site_name="Mercadona Centro", max_power_kw=22.0)
    cc_fast = _station(site_name="CC Mazarrón Park", max_power_kw=90.0)
    indoor = _station(site_name="Parking sotano hotel", access="restricted", max_power_kw=22.0)
    assert passes_access_filters(mercadona_slow, public_open_only=True) is True
    assert passes_access_filters(cc_fast, public_open_only=True) is True
    assert passes_access_filters(indoor, public_open_only=True) is True


def test_consum_restricted_classified_commercial_and_shown() -> None:
    """DATEX marca muchos Consum como restricted/inBuilding; siguen en mapa y plan."""
    consum_dc = _station(
        site_name="CONSUM VILLAREAL CALVARIO",
        access="restricted",
        max_power_kw=80.0,
    )
    consum_cartagena = _station(
        site_name="Supermercado Consum 1084 - Cartagena",
        access="public",
        max_power_kw=100.0,
    )
    consum_slow = _station(
        site_name="Consum Parking",
        access="public",
        max_power_kw=22.0,
    )
    assert classify_access(consum_dc) == "commercial_parking"
    assert classify_access(consum_cartagena) == "commercial_parking"
    assert passes_access_filters(consum_dc, public_open_only=True) is True
    assert passes_access_filters(consum_cartagena, public_open_only=True) is True
    assert passes_access_filters(consum_slow, public_open_only=True) is True


def test_exclude_commercial_still_drops_all_commercial() -> None:
    cc_fast = _station(site_name="CC Mazarrón Park", max_power_kw=90.0)
    assert passes_access_filters(cc_fast, exclude_commercial=True) is False
