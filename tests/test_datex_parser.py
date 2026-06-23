from __future__ import annotations

from pathlib import Path

import pytest

from ingest.datex_parser import parse_datex_file, parse_latest_raw_feed

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_spain_fixture() -> None:
    result = parse_datex_file(FIXTURES / "datex_es_sample.xml")
    assert result.country == "ES"
    assert result.source == "es-nap-dgt"
    assert result.stats.sites_parsed == 1
    assert result.stats.sites_skipped == 1
    assert result.stats.skip_reasons["missing_coordinates"] == 1

    station = result.stations[0]
    assert station.id == "es-dgt-SITE-ES-1"
    assert station.site_name == "Estación Test ES"
    assert station.operator == "Operador Test"
    assert station.location.lat == pytest.approx(40.4168)
    assert station.max_power_kw == pytest.approx(150.0)
    assert station.access == "public"
    assert station.connectors[0].connector_type == "iec62196T2COMBO"
    assert "card" in station.payment_methods


def test_parse_portugal_fixture() -> None:
    result = parse_datex_file(FIXTURES / "datex_pt_sample.xml")
    assert result.country == "PT"
    assert result.source == "pt-nap-mobie"
    assert result.stats.sites_parsed == 1

    station = result.stations[0]
    assert station.id == "pt-mobie-SITE-PT-1"
    assert station.site_name == "Posto Teste PT"
    assert station.max_power_kw == pytest.approx(50.0)
    assert len(station.connectors) == 2
    assert station.access == "public"
    assert "rfid" in station.payment_methods


@pytest.mark.integration
def test_parse_latest_spain_raw() -> None:
    result = parse_latest_raw_feed("ES")
    assert result.stats.sites_parsed > 10_000
    assert all(station.country == "ES" for station in result.stations)
    assert all(station.max_power_kw > 0 for station in result.stations)


@pytest.mark.integration
def test_parse_latest_portugal_raw() -> None:
    result = parse_latest_raw_feed("PT")
    assert result.stats.sites_parsed > 5_000
    assert all(station.country == "PT" for station in result.stations)
