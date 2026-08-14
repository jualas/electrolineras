from api.routing.itinerary_parse import (
    extract_departure_soc,
    parse_and_geocode_itinerary,
    split_itinerary_segments,
)


def test_extract_departure_soc_percent():
    assert extract_departure_soc("Salgo de casa al 100 %. Viernes a Comillas.") == 100.0
    assert extract_departure_soc("partida al 90%") == 90.0
    assert extract_departure_soc("sin porcentaje") is None


def test_split_arrow_itinerary():
    hints = split_itinerary_segments("Santillana del Mar (2 noches) → Comillas → casa")
    assert len(hints) >= 2
    assert any(h.overnight for h in hints)
    assert any(h.is_home for h in hints)


def test_parse_appends_home(monkeypatch):
    def fake_geocode(query: str, **_kwargs):
        q = query.lower()
        if "santillana" in q:
            return 43.39, -4.10, "Santillana del Mar"
        if "comillas" in q:
            return 43.38, -4.29, "Comillas"
        raise AssertionError(f"unexpected geocode: {query}")

    monkeypatch.setattr("api.routing.itinerary_parse.geocode_address", fake_geocode)

    parsed = parse_and_geocode_itinerary(
        "Salgo al 100%. Santillana del Mar 2 noches. Luego Comillas. Domingo vuelta a casa.",
        home_lat=43.26,
        home_lon=-2.92,
        home_label="Casa",
    )
    assert parsed.departure_soc_percent == 100.0
    assert parsed.return_home
    assert len(parsed.stops) >= 2
    assert parsed.stops[-1].is_home
    assert any(s.overnight for s in parsed.stops)


def test_parse_empty_warns():
    parsed = parse_and_geocode_itinerary("   ")
    assert parsed.stops == []
    assert parsed.warnings


def test_parse_natural_weekend_camping(monkeypatch):
    def fake_geocode(query: str, **_kwargs):
        assert "garrote" in query.lower() or "camping" in query.lower()
        assert "viernes" not in query.lower()
        assert "tarde" not in query.lower()
        return 38.218, -2.617, "Camping Garrote Gordo"

    monkeypatch.setattr("api.routing.itinerary_parse.geocode_address", fake_geocode)
    text = (
        "Vamos sabado a camping garrote gordo y volvemos a casa el domingo "
        "(en principio salimos cargados al 100%)"
    )
    parsed = parse_and_geocode_itinerary(
        text,
        home_lat=43.26,
        home_lon=-2.92,
        home_label="Casa",
    )
    assert parsed.departure_soc_percent == 100.0
    assert len(parsed.stops) == 2
    assert "Garrote" in parsed.stops[0].label
    assert parsed.stops[0].overnight
    assert parsed.stops[1].is_home


def test_parse_day_after_place_and_instruction_tail(monkeypatch):
    """«vamos a X viernes tarde y volvemos…, genera un plan…» no debe geocodificar el día."""
    from api.routing.itinerary_parse import _place_query_from_hint, split_itinerary_segments

    text = (
        "vamos a camping garrote gordo viernes tarde y volvemos a casa domingo, "
        "genera un plan de carga fiable para poder volver a casa"
    )
    place = _place_query_from_hint("camping garrote gordo viernes tarde")
    assert place.lower() == "camping garrote gordo"

    hints = split_itinerary_segments(text)
    non_home = [h for h in hints if not h.is_home]
    assert len(non_home) == 1
    assert "garrote" in non_home[0].raw.lower()
    assert "viernes" not in non_home[0].raw.lower()
    assert "tarde" not in non_home[0].raw.lower()
    assert any(h.is_home for h in hints)

    def fake_geocode(query: str, **_kwargs):
        assert query.lower().strip() == "camping garrote gordo"
        return 38.218, -2.617, "Camping Garrote Gordo"

    monkeypatch.setattr("api.routing.itinerary_parse.geocode_address", fake_geocode)
    parsed = parse_and_geocode_itinerary(
        text,
        home_lat=37.625,
        home_lon=-0.996,
        home_label="Casa",
    )
    assert len(parsed.stops) == 2
    assert parsed.stops[0].overnight
    assert parsed.stops[1].is_home
