from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.access_filters import classify_access, passes_access_filters
from api.config import settings
from api.dependencies import get_repository
from api.query_params import parse_bbox, parse_country_list
from api.routing.nominatim import GeocodingError, geocode_address
from api.schemas import (
    DEFAULT_NEARBY_LIMIT,
    MAX_NEARBY_LIMIT,
    NearbyResponse,
    NearbyStationResult,
    NearestLiveResponse,
    RouteEndpoint,
)
from db.repository import StationRepository
from db.spatial import haversine_m
from models.station import Station

router = APIRouter(prefix="/api/v1", tags=["city-search"])


def _validate_kw_range(min_kw: float | None, max_kw: float | None) -> None:
    if min_kw is not None and max_kw is not None and min_kw > max_kw:
        raise HTTPException(status_code=422, detail="min_kw no puede ser mayor que max_kw")


def _rank_by_distance(
    stations: list[Station],
    lat: float,
    lon: float,
    *,
    radius_m: float | None,
    limit: int,
) -> list[tuple[float, Station]]:
    ranked = sorted(
        (
            (haversine_m(lat, lon, station.location.lat, station.location.lon), station)
            for station in stations
        ),
        key=lambda item: item[0],
    )
    if radius_m is not None:
        ranked = [(distance, station) for distance, station in ranked if distance <= radius_m]
    return ranked[:limit]


def _apply_access_filters(
    ranked: list[tuple[float, Station]],
    *,
    public_open_only: bool,
    exclude_commercial: bool,
    exclude_parking: bool,
    ad_hoc_only: bool,
) -> list[tuple[float, Station]]:
    return [
        (distance, station)
        for distance, station in ranked
        if passes_access_filters(
            station,
            public_open_only=public_open_only,
            exclude_commercial=exclude_commercial,
            exclude_parking=exclude_parking,
            ad_hoc_only=ad_hoc_only,
        )
    ]


@router.get("/stations/nearby")
def stations_nearby(
    repo: Annotated[StationRepository, Depends(get_repository)],
    lat: Annotated[
        float | None,
        Query(ge=-90, le=90, description="Latitud de referencia"),
    ] = None,
    lon: Annotated[
        float | None,
        Query(ge=-180, le=180, description="Longitud de referencia"),
    ] = None,
    q: Annotated[
        str | None,
        Query(min_length=2, description="Dirección o lugar a geocodificar"),
    ] = None,
    bbox: Annotated[str | None, Query(description="west,south,east,north (zona mapa)")] = None,
    radius_m: Annotated[
        float | None,
        Query(gt=0, le=settings.nearby_radius_m_max, description="Radio en metros"),
    ] = None,
    min_kw: Annotated[float | None, Query(ge=0, description="Potencia mínima (kW)")] = None,
    max_kw: Annotated[float | None, Query(ge=0, description="Potencia máxima (kW)")] = None,
    country: Annotated[str | None, Query(description="Países ISO (ES,PT)")] = None,
    public_open_only: Annotated[
        bool,
        Query(description="Solo acceso público abierto (excluye CC e interior)"),
    ] = False,
    exclude_commercial: Annotated[
        bool,
        Query(description="Excluir centros comerciales (heurística)"),
    ] = False,
    exclude_parking: Annotated[
        bool,
        Query(description="Excluir parkings/garajes (heurística por nombre/dirección)"),
    ] = False,
    ad_hoc_only: Annotated[
        bool,
        Query(description="Solo pago ad-hoc (tarjeta/NFC)"),
    ] = False,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_NEARBY_LIMIT, description="Máximo de resultados"),
    ] = DEFAULT_NEARBY_LIMIT,
) -> NearbyResponse:
    _validate_kw_range(min_kw, max_kw)
    countries = parse_country_list(country)
    reference_label: str | None = None
    parsed_bbox = parse_bbox(bbox)
    bbox_values: list[float] | None = None

    if parsed_bbox is not None:
        west, south, east, north = parsed_bbox
        bbox_values = [west, south, east, north]
        ref_lat = (south + north) / 2
        ref_lon = (west + east) / 2
        search_radius_m = None
        stations = repo.search(
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
    elif q is not None:
        try:
            ref_lat, ref_lon, reference_label = geocode_address(q)
        except GeocodingError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        effective_radius = radius_m or settings.nearby_radius_m_default
        stations = repo.nearby(
            lat=ref_lat,
            lon=ref_lon,
            radius_m=effective_radius,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
            limit=max(limit * 5, 500),
        )
        search_radius_m = effective_radius
    elif lat is not None and lon is not None:
        ref_lat, ref_lon = lat, lon
        effective_radius = radius_m or settings.nearby_radius_m_default
        stations = repo.nearby(
            lat=ref_lat,
            lon=ref_lon,
            radius_m=effective_radius,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
            limit=max(limit * 5, 500),
        )
        search_radius_m = effective_radius
    else:
        raise HTTPException(
            status_code=422,
            detail="Indique lat+lon, q (dirección) o bbox para la búsqueda en ciudad",
        )

    ranked = _rank_by_distance(
        stations,
        ref_lat,
        ref_lon,
        radius_m=search_radius_m,
        limit=limit * 3,
    )
    filtered = _apply_access_filters(
        ranked,
        public_open_only=public_open_only,
        exclude_commercial=exclude_commercial,
        exclude_parking=exclude_parking,
        ad_hoc_only=ad_hoc_only,
    )[:limit]

    results = [
        NearbyStationResult(
            station=station,
            distance_m=round(distance, 1),
            distance_km=round(distance / 1000.0, 3),
            access_class=classify_access(station),
        )
        for distance, station in filtered
    ]

    return NearbyResponse(
        reference=RouteEndpoint(lat=ref_lat, lon=ref_lon),
        reference_label=reference_label,
        radius_m=search_radius_m,
        bbox=bbox_values,
        results=results,
    )


def _nearest_in_radius(
    repo: StationRepository,
    *,
    lat: float,
    lon: float,
    radius_m: float,
    min_kw: float,
    max_kw: float | None,
    countries: list[str] | None,
    public_open_only: bool,
    exclude_commercial: bool,
    exclude_parking: bool,
    ad_hoc_only: bool,
) -> tuple[float, Station] | None:
    stations = repo.nearby(
        lat=lat,
        lon=lon,
        radius_m=radius_m,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        limit=500,
    )
    ranked = _rank_by_distance(stations, lat, lon, radius_m=radius_m, limit=200)
    filtered = _apply_access_filters(
        ranked,
        public_open_only=public_open_only,
        exclude_commercial=exclude_commercial,
        exclude_parking=exclude_parking,
        ad_hoc_only=ad_hoc_only,
    )
    if not filtered:
        return None
    # Entre candidatas del filtro de potencia: la más cercana al GPS.
    return filtered[0]


@router.get("/stations/nearest-live")
def stations_nearest_live(
    repo: Annotated[StationRepository, Depends(get_repository)],
    lat: Annotated[float, Query(ge=-90, le=90, description="Latitud GPS")],
    lon: Annotated[float, Query(ge=-180, le=180, description="Longitud GPS")],
    radius_m: Annotated[
        float | None,
        Query(gt=0, le=settings.live_nearest_radius_m_max, description="Radio de búsqueda (m)"),
    ] = None,
    min_kw: Annotated[
        float | None,
        Query(ge=0, description="Potencia mínima (kW); 0 = sin mínimo"),
    ] = None,
    max_kw: Annotated[
        float | None,
        Query(ge=0, description="Potencia máxima (kW)"),
    ] = None,
    country: Annotated[str | None, Query(description="Países ISO (ES,PT)")] = None,
    public_open_only: Annotated[
        bool,
        Query(description="Solo acceso público abierto"),
    ] = True,
    exclude_commercial: Annotated[bool, Query(description="Excluir centros comerciales")] = False,
    exclude_parking: Annotated[
        bool,
        Query(description="Excluir parkings/garajes"),
    ] = False,
    ad_hoc_only: Annotated[bool, Query(description="Solo pago ad-hoc")] = False,
) -> NearestLiveResponse:
    """Cargador más cercano a la posición según el filtro de potencia (modo En vivo).

    Usa min_kw/max_kw del cliente (panel de potencia). Si no se indica min_kw,
    aplica el umbral por defecto (100 kW). Si no hay resultados con un mínimo
    alto, reintenta con el umbral de respaldo (50 kW) manteniendo max_kw.
    """
    _validate_kw_range(min_kw, max_kw)
    countries = parse_country_list(country)
    effective_radius = radius_m or settings.live_nearest_radius_m_default
    preferred_min = settings.live_nearest_min_kw if min_kw is None else min_kw
    fallback_min = settings.live_nearest_fallback_min_kw

    pick = _nearest_in_radius(
        repo,
        lat=lat,
        lon=lon,
        radius_m=effective_radius,
        min_kw=preferred_min,
        max_kw=max_kw,
        countries=countries,
        public_open_only=public_open_only,
        exclude_commercial=exclude_commercial,
        exclude_parking=exclude_parking,
        ad_hoc_only=ad_hoc_only,
    )
    used_min = preferred_min
    if pick is None and preferred_min > fallback_min:
        pick = _nearest_in_radius(
            repo,
            lat=lat,
            lon=lon,
            radius_m=effective_radius,
            min_kw=fallback_min,
            max_kw=max_kw,
            countries=countries,
            public_open_only=public_open_only,
            exclude_commercial=exclude_commercial,
            exclude_parking=exclude_parking,
            ad_hoc_only=ad_hoc_only,
        )
        used_min = fallback_min

    if pick is None:
        return NearestLiveResponse(
            reference=RouteEndpoint(lat=lat, lon=lon),
            radius_m=effective_radius,
            min_kw=preferred_min,
            used_min_kw=preferred_min,
        )

    distance, station = pick
    return NearestLiveResponse(
        reference=RouteEndpoint(lat=lat, lon=lon),
        radius_m=effective_radius,
        min_kw=preferred_min,
        used_min_kw=used_min,
        station=station,
        distance_m=round(distance, 1),
        distance_km=round(distance / 1000.0, 3),
        access_class=classify_access(station),
    )
