from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.config import settings
from api.dependencies import get_repository
from api.query_params import parse_country_list
from api.routing.osrm import RoutingError, fetch_osrm_route_with_alternatives
from api.routing.route_variants import rank_stations_for_route_variant, union_route_search_bbox
from api.schemas import (
    MAX_CORRIDOR_KM,
    MAX_ROUTE_RESULTS_LIMIT,
    AlongRouteResponse,
    AlongRouteStationResult,
    RouteEndpoint,
    RoutePreference,
    RouteVariantAlongRouteSnapshot,
)
from db.repository import StationRepository

router = APIRouter(prefix="/api/v1", tags=["route-search"])


@router.get("/stations/along-route")
def stations_along_route(
    repo: Annotated[StationRepository, Depends(get_repository)],
    origin_lat: Annotated[float, Query(ge=-90, le=90, description="Latitud origen")],
    origin_lon: Annotated[float, Query(ge=-180, le=180, description="Longitud origen")],
    dest_lat: Annotated[float, Query(ge=-90, le=90, description="Latitud destino")],
    dest_lon: Annotated[float, Query(ge=-180, le=180, description="Longitud destino")],
    min_kw: Annotated[
        float,
        Query(ge=0, description="Potencia mínima (kW); default viaje ≥100"),
    ] = 100.0,
    max_kw: Annotated[float | None, Query(ge=0, description="Potencia máxima (kW)")] = None,
    country: Annotated[str | None, Query(description="Países ISO (ES,PT)")] = None,
    corridor_km: Annotated[
        float,
        Query(gt=0, le=MAX_CORRIDOR_KM, description="Ancho del corredor en km"),
    ] = settings.route_corridor_km_default,
    behind_margin_km: Annotated[
        float,
        Query(ge=0, le=20, description="Margen anti-retroceso en km"),
    ] = settings.route_behind_margin_km_default,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_ROUTE_RESULTS_LIMIT, description="Máximo de resultados"),
    ] = settings.route_results_limit_default,
    include_route: Annotated[
        bool,
        Query(description="Incluir geometría GeoJSON de la ruta"),
    ] = True,
    route_preference: Annotated[
        RoutePreference,
        Query(
            description=(
                "fastest = menos tiempo; shortest = menos km; "
                "conventional = solo nacionales/secundarias (sin autovía)"
            ),
        ),
    ] = "fastest",
    avoid_highways: Annotated[
        bool,
        Query(description="Evitar autopistas de peaje (OSRM exclude=toll)"),
    ] = False,
) -> AlongRouteResponse:
    if min_kw is not None and max_kw is not None and min_kw > max_kw:
        raise HTTPException(status_code=422, detail="min_kw no puede ser mayor que max_kw")

    countries = parse_country_list(country)

    try:
        osrm_route, route_alternatives, _osrm_warnings, variant_routes = fetch_osrm_route_with_alternatives(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
            route_preference=route_preference,
            avoid_highways=avoid_highways,
        )
    except RoutingError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo calcular la ruta: {exc}",
        ) from exc

    west, south, east, north = union_route_search_bbox(variant_routes, corridor_km)
    candidates = repo.search(
        west=west,
        south=south,
        east=east,
        north=north,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        limit=10_000,
        offset=0,
    )

    wrong_side_penalty_m = settings.route_wrong_side_penalty_km_default * 1000
    route_variant_results: dict[str, RouteVariantAlongRouteSnapshot] = {}
    for preference, variant_route in variant_routes.items():
        matches = rank_stations_for_route_variant(
            variant_route,
            candidates,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            corridor_km=corridor_km,
            behind_margin_km=behind_margin_km,
            wrong_side_penalty_m=wrong_side_penalty_m,
            limit=limit,
        )
        route_variant_results[preference] = RouteVariantAlongRouteSnapshot(
            route_distance_km=round(variant_route.distance_m / 1000.0, 2),
            route_duration_minutes=round(variant_route.duration_s / 60.0, 1),
            results=[
                AlongRouteStationResult(
                    station=match.station,
                    deviation_km=round(match.deviation_m / 1000.0, 2),
                    route_distance_km=round(match.route_position_m / 1000.0, 2),
                    extra_minutes=round(match.extra_minutes, 1),
                    wrong_side=match.wrong_side,
                )
                for match in matches
            ],
            candidates_in_bbox=len(candidates),
        )

    active_variant = route_variant_results.get(route_preference)
    if active_variant is None:
        matches = rank_stations_for_route_variant(
            osrm_route,
            candidates,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            corridor_km=corridor_km,
            behind_margin_km=behind_margin_km,
            wrong_side_penalty_m=wrong_side_penalty_m,
            limit=limit,
        )
        active_variant = RouteVariantAlongRouteSnapshot(
            route_distance_km=round(osrm_route.distance_m / 1000.0, 2),
            route_duration_minutes=round(osrm_route.duration_s / 60.0, 1),
            results=[
                AlongRouteStationResult(
                    station=match.station,
                    deviation_km=round(match.deviation_m / 1000.0, 2),
                    route_distance_km=round(match.route_position_m / 1000.0, 2),
                    extra_minutes=round(match.extra_minutes, 1),
                    wrong_side=match.wrong_side,
                )
                for match in matches
            ],
            candidates_in_bbox=len(candidates),
        )
        route_variant_results[route_preference] = active_variant

    results = active_variant.results

    return AlongRouteResponse(
        origin=RouteEndpoint(lat=origin_lat, lon=origin_lon),
        destination=RouteEndpoint(lat=dest_lat, lon=dest_lon),
        corridor_km=corridor_km,
        behind_margin_km=behind_margin_km,
        geodesic_distance_km=route_alternatives.geodesic_distance_km,
        route_distance_km=active_variant.route_distance_km,
        route_duration_minutes=active_variant.route_duration_minutes,
        route_shortest_distance_km=route_alternatives.shortest_distance_km,
        route_fastest_distance_km=route_alternatives.fastest_distance_km,
        route_conventional_distance_km=route_alternatives.conventional_distance_km,
        route_conventional_duration_minutes=route_alternatives.conventional_duration_minutes,
        shortest_excess_km=route_alternatives.shortest_excess_km,
        route_variants_approximate=route_alternatives.variants_approximate,
        route_geometry=osrm_route.geojson_geometry if include_route else None,
        route_shortest_geometry=(
            variant_routes["shortest"].geojson_geometry
            if include_route and "shortest" in variant_routes
            else None
        ),
        route_fastest_geometry=(
            variant_routes["fastest"].geojson_geometry
            if include_route and "fastest" in variant_routes
            else None
        ),
        route_conventional_geometry=(
            variant_routes["conventional"].geojson_geometry
            if include_route and "conventional" in variant_routes
            else None
        ),
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        results=results,
        candidates_in_bbox=active_variant.candidates_in_bbox,
        route_variant_results=route_variant_results,
    )
