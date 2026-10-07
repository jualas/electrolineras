from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.access_filters import passes_access_filters
from api.converters import stations_to_geojson
from api.dependencies import get_repository
from api.query_params import (
    expand_connector_types_for_sql,
    operators_limit_query,
    parse_bbox,
    parse_connector_types,
    parse_country_list,
    stations_limit_query,
    stations_offset_query,
)
from api.routing.nominatim import GeocodingError, search_places
from api.schemas import (
    MAX_STATIONS_LIMIT,
    CountryStats,
    GeocodeResultItem,
    GeoJSONStationCollection,
    MetaOcmResponse,
    MetaOperatorsResponse,
    MetaStatsResponse,
    OperatorCount,
    Pagination,
    PowerBandStats,
    StationListResponse,
)
from db.repository import StationRepository
from ingest.config import settings as ingest_settings
from ingest.ocm_parser import OCM_SOURCE
from models.station import Station

router = APIRouter(prefix="/api/v1", tags=["stations"])


def _validate_kw_range(min_kw: float | None, max_kw: float | None) -> None:
    if min_kw is not None and max_kw is not None and min_kw > max_kw:
        raise HTTPException(status_code=422, detail="min_kw no puede ser mayor que max_kw")


def _search_stations(
    repo: StationRepository,
    *,
    west: float | None,
    south: float | None,
    east: float | None,
    north: float | None,
    min_kw: float | None,
    max_kw: float | None,
    countries: list[str] | None,
    available_only: bool,
    max_price_eur_kwh: float | None,
    connector_types: list[str] | None,
    limit: int,
    offset: int,
    order_by: str = "power",
) -> tuple[list[Station], Pagination]:
    _validate_kw_range(min_kw, max_kw)
    total = repo.count_matching(
        west=west,
        south=south,
        east=east,
        north=north,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        available_only=available_only,
        max_price_eur_kwh=max_price_eur_kwh,
        connector_types=connector_types,
    )
    stations = repo.search(
        west=west,
        south=south,
        east=east,
        north=north,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        available_only=available_only,
        max_price_eur_kwh=max_price_eur_kwh,
        connector_types=connector_types,
        limit=limit,
        offset=offset,
        order_by=order_by,
    )
    pagination = Pagination(
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + len(stations) < total,
    )
    return stations, pagination


def _apply_access_filters_to_stations(
    stations: list[Station],
    *,
    public_open_only: bool,
    exclude_commercial: bool,
    exclude_parking: bool,
    ad_hoc_only: bool,
) -> list[Station]:
    if not public_open_only and not exclude_commercial and not exclude_parking and not ad_hoc_only:
        return stations
    return [
        station
        for station in stations
        if passes_access_filters(
            station,
            public_open_only=public_open_only,
            exclude_commercial=exclude_commercial,
            exclude_parking=exclude_parking,
            ad_hoc_only=ad_hoc_only,
        )
    ]


def _search_stations_respecting_access_filters(
    repo: StationRepository,
    *,
    west: float | None,
    south: float | None,
    east: float | None,
    north: float | None,
    min_kw: float | None,
    max_kw: float | None,
    countries: list[str] | None,
    available_only: bool,
    max_price_eur_kwh: float | None,
    connector_types: list[str] | None,
    limit: int,
    offset: int,
    public_open_only: bool,
    exclude_commercial: bool,
    exclude_parking: bool,
    ad_hoc_only: bool,
    order_by: str = "power",
) -> tuple[list[Station], Pagination]:
    use_access_filters = public_open_only or exclude_commercial or exclude_parking or ad_hoc_only
    if not use_access_filters:
        return _search_stations(
            repo,
            west=west,
            south=south,
            east=east,
            north=north,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
            available_only=available_only,
            max_price_eur_kwh=max_price_eur_kwh,
            connector_types=connector_types,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )

    total_unfiltered = repo.count_matching(
        west=west,
        south=south,
        east=east,
        north=north,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        available_only=available_only,
        max_price_eur_kwh=max_price_eur_kwh,
        connector_types=connector_types,
    )
    batch_size = min(max(limit * 4, limit), MAX_STATIONS_LIMIT)
    collected: list[Station] = []
    scan_offset = 0

    while len(collected) < offset + limit and scan_offset < total_unfiltered:
        batch = repo.search(
            west=west,
            south=south,
            east=east,
            north=north,
            min_kw=min_kw,
            max_kw=max_kw,
            countries=countries,
            available_only=available_only,
            max_price_eur_kwh=max_price_eur_kwh,
            connector_types=connector_types,
            limit=batch_size,
            offset=scan_offset,
            order_by=order_by,
        )
        if not batch:
            break
        collected.extend(
            _apply_access_filters_to_stations(
                batch,
                public_open_only=public_open_only,
                exclude_commercial=exclude_commercial,
                exclude_parking=exclude_parking,
                ad_hoc_only=ad_hoc_only,
            )
        )
        scan_offset += len(batch)

    page = collected[offset : offset + limit]
    exhausted = scan_offset >= total_unfiltered
    filtered_total = len(collected) if exhausted else max(len(collected), offset + len(page))
    pagination = Pagination(
        total=filtered_total,
        limit=limit,
        offset=offset,
        has_more=not exhausted and len(collected) >= offset + limit,
    )
    return page, pagination


@router.get("/stations")
def list_stations(
    repo: Annotated[StationRepository, Depends(get_repository)],
    min_kw: Annotated[
        float | None,
        Query(ge=0, description="Potencia mínima (kW) del emplazamiento"),
    ] = None,
    max_kw: Annotated[
        float | None,
        Query(ge=0, description="Potencia máxima (kW) del emplazamiento"),
    ] = None,
    country: Annotated[str | None, Query(description="Países ISO (ES,PT)")] = None,
    bbox: Annotated[str | None, Query(description="west,south,east,north")] = None,
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
    available_only: Annotated[
        bool,
        Query(description="Solo puntos con disponibilidad AVAILABLE (REVE)"),
    ] = False,
    max_price_eur_kwh: Annotated[
        float | None,
        Query(ge=0, description="Precio máximo €/kWh (incluye sin tarifa conocida)"),
    ] = None,
    connector_types: Annotated[
        str | None,
        Query(description="Tipos de conector separados por coma (CCS2,Type2,CHAdeMO,…)"),
    ] = None,
    format: Annotated[
        Literal["json", "geojson"],
        Query(description="Formato de respuesta"),
    ] = "json",
    limit: Annotated[int, Depends(stations_limit_query)] = 100,
    offset: Annotated[int, Depends(stations_offset_query)] = 0,
) -> StationListResponse | GeoJSONStationCollection:
    countries = parse_country_list(country)
    parsed_bbox = parse_bbox(bbox)
    west, south, east, north = parsed_bbox or (None, None, None, None)
    order_by = "id" if parsed_bbox is not None and format == "geojson" else "power"
    parsed_connector_types = expand_connector_types_for_sql(parse_connector_types(connector_types))

    stations, pagination = _search_stations_respecting_access_filters(
        repo,
        west=west,
        south=south,
        east=east,
        north=north,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        available_only=available_only,
        max_price_eur_kwh=max_price_eur_kwh,
        connector_types=parsed_connector_types,
        limit=limit,
        offset=offset,
        public_open_only=public_open_only,
        exclude_commercial=exclude_commercial,
        exclude_parking=exclude_parking,
        ad_hoc_only=ad_hoc_only,
        order_by=order_by,
    )

    if format == "geojson":
        return GeoJSONStationCollection(
            features=stations_to_geojson(stations),
            pagination=pagination,
        )

    return StationListResponse(stations=stations, pagination=pagination)


@router.get("/stations/{station_id}")
def get_station(
    station_id: str,
    repo: Annotated[StationRepository, Depends(get_repository)],
) -> Station:
    station = repo.get_by_id(station_id)
    if station is None:
        raise HTTPException(status_code=404, detail=f"Estación no encontrada: {station_id}")
    return station


@router.get("/meta/stats", tags=["meta"])
def meta_stats(
    repo: Annotated[StationRepository, Depends(get_repository)],
) -> MetaStatsResponse:
    by_country = [
        CountryStats(
            country=row["country"],
            count=row["count"],
            max_kw=row["max_kw"],
        )
        for row in repo.stats_by_country()
    ]
    by_power_band = [
        PowerBandStats(
            country=row["country"],
            total=row["total"],
            slow_ac=row["slow_ac"],
            ac_fast=row["ac_fast"],
            dc_fast=row["dc_fast"],
            hpc=row["hpc"],
            ultra_fast=row["ultra_fast"],
        )
        for row in repo.stats_by_power()
    ]
    return MetaStatsResponse(
        total_stations=repo.count_stations(),
        by_country=by_country,
        by_power_band=by_power_band,
    )


@router.get("/meta/ocm", tags=["meta"])
def meta_ocm(
    repo: Annotated[StationRepository, Depends(get_repository)],
) -> MetaOcmResponse:
    last_run = repo.last_ingest_run(OCM_SOURCE)
    return MetaOcmResponse(
        configured=bool(ingest_settings.ocm_api_key),
        stations_with_ratings=repo.count_external_ratings(),
        last_sync_status=last_run["status"] if last_run else None,
        last_sync_finished_at=last_run["finished_at"] if last_run else None,
        last_sync_enriched=int(last_run["records_upserted"])
        if last_run and last_run["records_upserted"] is not None
        else None,
    )


@router.get("/meta/operators", tags=["meta"])
def meta_operators(
    repo: Annotated[StationRepository, Depends(get_repository)],
    country: Annotated[str | None, Query(description="Filtrar por país ISO")] = None,
    limit: Annotated[int, Depends(operators_limit_query)] = 10,
) -> MetaOperatorsResponse:
    countries = parse_country_list(country)
    country_filter = countries[0] if countries and len(countries) == 1 else None
    if countries and len(countries) > 1:
        raise HTTPException(
            status_code=422,
            detail="meta/operators admite un solo país; use country=ES o country=PT",
        )

    operators = [
        OperatorCount(operator=row["operator"], count=row["count"])
        for row in repo.top_operators(country=country_filter, limit=limit)
    ]
    return MetaOperatorsResponse(operators=operators, country=country_filter, limit=limit)


@router.get("/meta/geocode", tags=["meta"])
def meta_geocode(
    q: Annotated[str, Query(min_length=2, description="Lugar o dirección a buscar")],
    limit: Annotated[int, Query(ge=1, le=10, description="Máximo de sugerencias")] = 5,
) -> list[GeocodeResultItem]:
    try:
        hits = search_places(q, limit=limit)
    except GeocodingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [GeocodeResultItem(lat=lat, lon=lon, label=label) for lat, lon, label in hits]
