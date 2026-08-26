"""#6140: la UI debe mostrar duración de Directa y Rápida para no confundir km con tiempo."""

from __future__ import annotations


def _format_duration_minutes(minutes: float | None) -> str:
    if minutes is None or minutes <= 0:
        return ""
    rounded = round(minutes)
    hours, mins = divmod(rounded, 60)
    if hours > 0:
        return f"{hours} h {mins} min" if mins else f"{hours} h"
    return f"{mins} min"


def format_route_alternatives_km(plan: dict) -> str:
    """Espejo de formatRouteAlternativesKm (TS) para regresión sin Node."""
    parts: list[str] = []
    shortest = plan.get("route_shortest_distance_km")
    if shortest is None:
        shortest = plan.get("route_distance_km")
    fastest = plan.get("route_fastest_distance_km")
    if fastest is None:
        fastest = plan.get("route_distance_km")

    if shortest is not None:
        short_dur = plan.get("route_shortest_duration_minutes")
        if short_dur is None and plan.get("route_preference") == "shortest":
            short_dur = plan.get("route_duration_minutes")
        duration = _format_duration_minutes(short_dur)
        parts.append(f"Directa: {shortest:.0f} km" + (f" · {duration}" if duration else ""))
    if fastest is not None:
        fast_dur = plan.get("route_fastest_duration_minutes")
        if fast_dur is None and plan.get("route_preference") == "fastest":
            fast_dur = plan.get("route_duration_minutes")
        duration = _format_duration_minutes(fast_dur)
        parts.append(f"Rápida: {fastest:.0f} km" + (f" · {duration}" if duration else ""))
    return " · ".join(parts)


def test_format_shows_both_durations_even_when_fastest_has_more_km() -> None:
    label = format_route_alternatives_km(
        {
            "route_preference": "shortest",
            "route_distance_km": 748.0,
            "route_duration_minutes": 699.0,
            "route_shortest_distance_km": 748.0,
            "route_fastest_distance_km": 903.0,
            "route_shortest_duration_minutes": 699.0,
            "route_fastest_duration_minutes": 593.0,
        }
    )
    assert "Directa: 748 km · 11 h 39 min" in label
    assert "Rápida: 903 km · 9 h 53 min" in label
