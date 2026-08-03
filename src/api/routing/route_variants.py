from __future__ import annotations

from api.routing.corridor import RoutePolyline, rank_stations_along_route
from api.routing.osrm import OsrmRoute, RoutePreference
from db.repository import StationRepository
from models.station import Station


def union_route_search_bbox(
    variant_routes: dict[RoutePreference, OsrmRoute],
    corridor_km: float,
) -> tuple[float, float, float, float]:
    west = south = float("inf")
    east = north = float("-inf")
    for route in variant_routes.values():
        polyline = RoutePolyline(route.coordinates)
        route_west, route_south, route_east, route_north = polyline.bbox_expanded(corridor_km * 1000)
        west = min(west, route_west)
        south = min(south, route_south)
        east = max(east, route_east)
        north = max(north, route_north)
    return west, south, east, north


def rank_stations_for_route_variant(
    osrm_route: OsrmRoute,
    candidates: list[Station],
    *,
    origin_lat: float,
    origin_lon: float,
    corridor_km: float,
    behind_margin_km: float,
    wrong_side_penalty_m: float,
    limit: int,
):
    polyline = RoutePolyline(osrm_route.coordinates)
    return rank_stations_along_route(
        polyline,
        candidates,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        corridor_m=corridor_km * 1000,
        behind_margin_m=behind_margin_km * 1000,
        wrong_side_penalty_m=wrong_side_penalty_m,
        average_speed_mps=osrm_route.average_speed_mps,
        limit=limit,
    )
