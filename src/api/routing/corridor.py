from __future__ import annotations

import math
from dataclasses import dataclass

from db.spatial import haversine_m
from models.station import Station

# Espaciado mínimo entre vértices al proyectar estaciones sobre la ruta (~1,5 km).
_CORRIDOR_MATCHING_VERTEX_SPACING_M = 1500.0


@dataclass(frozen=True)
class RouteProjection:
    distance_m: float
    route_position_m: float
    segment_index: int
    segment_fraction: float
    route_lat: float
    route_lon: float


@dataclass(frozen=True)
class CorridorMatch:
    station: Station
    deviation_m: float
    route_position_m: float
    extra_minutes: float
    behind_route: bool
    wrong_side: bool


@dataclass(frozen=True)
class CorridorRankingResult:
    planning: list[CorridorMatch]
    display: list[CorridorMatch]


@dataclass(frozen=True)
class _SegmentBound:
    index: int
    south: float
    west: float
    north: float
    east: float


class RoutePolyline:
    def __init__(self, coordinates: list[tuple[float, float]]) -> None:
        if len(coordinates) < 2:
            msg = "La polilínea de ruta requiere al menos 2 puntos"
            raise ValueError(msg)
        self.coordinates = coordinates
        self._segment_lengths_m: list[float] = []
        self._cumulative_m: list[float] = [0.0]
        for index in range(len(coordinates) - 1):
            lon_a, lat_a = coordinates[index]
            lon_b, lat_b = coordinates[index + 1]
            length = haversine_m(lat_a, lon_a, lat_b, lon_b)
            self._segment_lengths_m.append(length)
            self._cumulative_m.append(self._cumulative_m[-1] + length)
        self._matching_polyline: RoutePolyline | None = None

    @property
    def length_m(self) -> float:
        return self._cumulative_m[-1]

    def simplified_for_matching(
        self,
        min_spacing_m: float = _CORRIDOR_MATCHING_VERTEX_SPACING_M,
    ) -> RoutePolyline:
        """Polilínea con menos vértices para proyección en corredor (misma longitud aprox.)."""
        if self._matching_polyline is not None:
            return self._matching_polyline
        if len(self.coordinates) <= 2:
            return self

        simplified: list[tuple[float, float]] = [self.coordinates[0]]
        dist_since_last = 0.0
        for index in range(1, len(self.coordinates)):
            lon_a, lat_a = self.coordinates[index - 1]
            lon_b, lat_b = self.coordinates[index]
            dist_since_last += haversine_m(lat_a, lon_a, lat_b, lon_b)
            is_last = index == len(self.coordinates) - 1
            if dist_since_last >= min_spacing_m or is_last:
                if simplified[-1] != self.coordinates[index]:
                    simplified.append(self.coordinates[index])
                dist_since_last = 0.0

        if len(simplified) < 2:
            return self

        self._matching_polyline = RoutePolyline(simplified)
        return self._matching_polyline

    def bbox_expanded(self, margin_m: float) -> tuple[float, float, float, float]:
        lons = [lon for lon, _lat in self.coordinates]
        lats = [lat for _lon, lat in self.coordinates]
        south = min(lats)
        north = max(lats)
        west = min(lons)
        east = max(lons)
        lat_pad = margin_m / 111_320.0
        mid_lat = (south + north) / 2
        cos_lat = math.cos(math.radians(mid_lat)) or 1e-9
        lon_pad = margin_m / (111_320.0 * cos_lat)
        return west - lon_pad, south - lat_pad, east + lon_pad, north + lat_pad

    def project_point(self, lat: float, lon: float) -> RouteProjection:
        return _CorridorRouteIndex(self).project_point(lat, lon)

    def segment_bearing_deg(self, segment_index: int) -> float:
        lon_a, lat_a = self.coordinates[segment_index]
        lon_b, lat_b = self.coordinates[segment_index + 1]
        return _bearing_deg(lat_a, lon_a, lat_b, lon_b)


class _CorridorRouteIndex:
    """Índice espacial sobre polilínea simplificada para proyección rápida."""

    def __init__(self, route: RoutePolyline) -> None:
        self.route = route.simplified_for_matching()
        self._bounds = self._build_bounds()

    @classmethod
    def from_route(cls, route: RoutePolyline) -> _CorridorRouteIndex:
        return cls(route)

    def _build_bounds(self) -> list[_SegmentBound]:
        bounds: list[_SegmentBound] = []
        for index in range(len(self.route._segment_lengths_m)):
            lon_a, lat_a = self.route.coordinates[index]
            lon_b, lat_b = self.route.coordinates[index + 1]
            bounds.append(
                _SegmentBound(
                    index=index,
                    south=min(lat_a, lat_b),
                    west=min(lon_a, lon_b),
                    north=max(lat_a, lat_b),
                    east=max(lon_a, lon_b),
                )
            )
        return bounds

    def project_point(self, lat: float, lon: float) -> RouteProjection:
        best_distance = float("inf")
        best_position = 0.0
        best_segment = 0
        best_fraction = 0.0
        best_lat = self.route.coordinates[0][1]
        best_lon = self.route.coordinates[0][0]

        for bound in self._bounds:
            bbox_distance = _point_to_bbox_min_distance_m(
                lat,
                lon,
                bound.south,
                bound.west,
                bound.north,
                bound.east,
            )
            if bbox_distance >= best_distance:
                continue

            index = bound.index
            length_m = self.route._segment_lengths_m[index]
            lon_a, lat_a = self.route.coordinates[index]
            lon_b, lat_b = self.route.coordinates[index + 1]
            fraction, proj_lat, proj_lon = _project_on_segment(lat_a, lon_a, lat_b, lon_b, lat, lon)
            distance_m = haversine_m(lat, lon, proj_lat, proj_lon)
            position_m = self.route._cumulative_m[index] + fraction * length_m

            if distance_m < best_distance:
                best_distance = distance_m
                best_position = position_m
                best_segment = index
                best_fraction = fraction
                best_lat = proj_lat
                best_lon = proj_lon

        return RouteProjection(
            distance_m=best_distance,
            route_position_m=best_position,
            segment_index=best_segment,
            segment_fraction=best_fraction,
            route_lat=best_lat,
            route_lon=best_lon,
        )


def _point_to_bbox_min_distance_m(
    lat: float,
    lon: float,
    south: float,
    west: float,
    north: float,
    east: float,
) -> float:
    clamp_lat = min(max(lat, south), north)
    clamp_lon = min(max(lon, west), east)
    return haversine_m(lat, lon, clamp_lat, clamp_lon)


def _bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0


def _angle_diff_deg(a: float, b: float) -> float:
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def _project_on_segment(
    lat_a: float,
    lon_a: float,
    lat_b: float,
    lon_b: float,
    lat: float,
    lon: float,
) -> tuple[float, float, float]:
    ax, ay = lon_a, lat_a
    bx, by = lon_b, lat_b
    px, py = lon, lat
    dx = bx - ax
    dy = by - ay
    if dx == 0 and dy == 0:
        return 0.0, lat_a, lon_a

    fraction = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    fraction = max(0.0, min(1.0, fraction))
    proj_lon = ax + fraction * dx
    proj_lat = ay + fraction * dy
    return fraction, proj_lat, proj_lon


def _collect_corridor_matches(
    route: RoutePolyline,
    stations: list[Station],
    *,
    origin_lat: float,
    origin_lon: float,
    corridor_m: float,
    behind_margin_m: float,
    wrong_side_penalty_m: float,
    average_speed_mps: float,
    route_index: _CorridorRouteIndex | None = None,
) -> list[CorridorMatch]:
    index = route_index or _CorridorRouteIndex.from_route(route)
    origin_projection = index.project_point(origin_lat, origin_lon)
    origin_position_m = origin_projection.route_position_m
    matches: list[CorridorMatch] = []

    for station in stations:
        projection = index.project_point(station.location.lat, station.location.lon)
        behind_route = projection.route_position_m < origin_position_m - behind_margin_m
        if behind_route:
            continue

        if projection.distance_m > corridor_m:
            continue

        segment_bearing = index.route.segment_bearing_deg(projection.segment_index)
        to_station_bearing = _bearing_deg(
            projection.route_lat,
            projection.route_lon,
            station.location.lat,
            station.location.lon,
        )
        wrong_side = _angle_diff_deg(segment_bearing, to_station_bearing) > 90.0

        effective_deviation_m = projection.distance_m
        if wrong_side:
            effective_deviation_m += wrong_side_penalty_m

        speed_mps = average_speed_mps if average_speed_mps > 0 else 22.0
        extra_minutes = (effective_deviation_m * 2 / speed_mps) / 60.0

        matches.append(
            CorridorMatch(
                station=station,
                deviation_m=effective_deviation_m,
                route_position_m=projection.route_position_m,
                extra_minutes=extra_minutes,
                behind_route=False,
                wrong_side=wrong_side,
            )
        )

    return matches


def _match_sort_key(item: CorridorMatch) -> tuple[float, float, float]:
    return (
        item.deviation_m,
        -item.station.max_power_kw,
        item.route_position_m,
    )


def _select_planning_matches(
    matches: list[CorridorMatch],
    *,
    route_distance_km: float,
    segment_km: float,
    per_segment: int,
) -> list[CorridorMatch]:
    """Candidatos repartidos a lo largo de la ruta (evita quedarse solo cerca del origen)."""
    if not matches:
        return []

    bins: dict[int, list[CorridorMatch]] = {}
    for match in matches:
        bin_id = int(match.route_position_m / 1000.0 / max(segment_km, 1.0))
        bins.setdefault(bin_id, []).append(match)

    selected: list[CorridorMatch] = []
    for bin_id in sorted(bins):
        segment_matches = sorted(bins[bin_id], key=_match_sort_key)[:per_segment]
        selected.extend(segment_matches)

    selected.sort(key=lambda item: item.route_position_m)
    min_expected = max(20, int(route_distance_km / max(segment_km, 1.0)))
    if len(selected) < min_expected and len(matches) > len(selected):
        seen_ids = {item.station.id for item in selected}
        for match in sorted(matches, key=_match_sort_key):
            if match.station.id in seen_ids:
                continue
            selected.append(match)
            seen_ids.add(match.station.id)
        selected.sort(key=lambda item: item.route_position_m)
    return selected


def rank_stations_for_charging_plan(
    route: RoutePolyline,
    stations: list[Station],
    *,
    origin_lat: float,
    origin_lon: float,
    corridor_m: float,
    behind_margin_m: float,
    wrong_side_penalty_m: float,
    average_speed_mps: float,
    route_distance_km: float,
    display_limit: int,
    segment_km: float = 45.0,
    per_segment: int = 15,
) -> CorridorRankingResult:
    """Una sola pasada de proyección; deriva listas de planificación y UI."""
    route_index = _CorridorRouteIndex.from_route(route)
    matches = _collect_corridor_matches(
        route,
        stations,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        corridor_m=corridor_m,
        behind_margin_m=behind_margin_m,
        wrong_side_penalty_m=wrong_side_penalty_m,
        average_speed_mps=average_speed_mps,
        route_index=route_index,
    )
    display = sorted(matches, key=_match_sort_key)[:display_limit]
    planning = _select_planning_matches(
        matches,
        route_distance_km=route_distance_km,
        segment_km=segment_km,
        per_segment=per_segment,
    )
    return CorridorRankingResult(planning=planning, display=display)


def rank_stations_along_route(
    route: RoutePolyline,
    stations: list[Station],
    *,
    origin_lat: float,
    origin_lon: float,
    corridor_m: float,
    behind_margin_m: float,
    wrong_side_penalty_m: float,
    average_speed_mps: float,
    limit: int,
) -> list[CorridorMatch]:
    matches = _collect_corridor_matches(
        route,
        stations,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        corridor_m=corridor_m,
        behind_margin_m=behind_margin_m,
        wrong_side_penalty_m=wrong_side_penalty_m,
        average_speed_mps=average_speed_mps,
    )
    matches.sort(key=_match_sort_key)
    return matches[:limit]


def rank_stations_along_route_for_planning(
    route: RoutePolyline,
    stations: list[Station],
    *,
    origin_lat: float,
    origin_lon: float,
    corridor_m: float,
    behind_margin_m: float,
    wrong_side_penalty_m: float,
    average_speed_mps: float,
    route_distance_km: float,
    segment_km: float = 45.0,
    per_segment: int = 15,
) -> list[CorridorMatch]:
    matches = _collect_corridor_matches(
        route,
        stations,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        corridor_m=corridor_m,
        behind_margin_m=behind_margin_m,
        wrong_side_penalty_m=wrong_side_penalty_m,
        average_speed_mps=average_speed_mps,
    )
    return _select_planning_matches(
        matches,
        route_distance_km=route_distance_km,
        segment_km=segment_km,
        per_segment=per_segment,
    )
