from __future__ import annotations

from api.routing.nominatim import GeocodingError, search_places
from db.spatial import haversine_m


def _area_hint_from_label(label: str) -> str:
    parts = [part.strip() for part in label.split(",") if part.strip()]
    if not parts:
        return label.strip()
    if len(parts) >= 2:
        return f"{parts[0]}, {parts[1]}"
    return parts[0]


def fetch_destination_poi_hints(
    lat: float,
    lon: float,
    dest_label: str | None,
    *,
    max_distance_km: float = 35.0,
    limit_per_query: int = 3,
) -> list[str]:
    """Ideas de visitas y gastronomía vía Nominatim (orientativo para el agente IA)."""
    area = _area_hint_from_label(dest_label or f"{lat:.4f}, {lon:.4f}")
    queries = [
        ("Cultura", f"museo {area}"),
        ("Gastronomía", f"restaurante {area}"),
        ("Visitas", f"monumento {area}"),
    ]
    hints: list[str] = []
    seen: set[str] = set()
    max_m = max_distance_km * 1000.0

    for category, query in queries:
        try:
            places = search_places(query, limit=limit_per_query)
        except GeocodingError:
            continue
        for place_lat, place_lon, place_label in places:
            if haversine_m(lat, lon, place_lat, place_lon) > max_m:
                continue
            key = place_label.lower()
            if key in seen:
                continue
            seen.add(key)
            hints.append(f"{category}: {place_label}")

    return hints[:12]
