from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from models.station import Station


class Pagination(BaseModel):
    total: int
    limit: int
    offset: int
    has_more: bool


class StationListResponse(BaseModel):
    stations: list[Station]
    pagination: Pagination


class GeoJSONStationCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[dict[str, Any]]
    pagination: Pagination


class CountryStats(BaseModel):
    country: str
    count: int
    max_kw: float | None = None


class PowerBandStats(BaseModel):
    country: str
    total: int
    slow_ac: int
    ac_fast: int
    dc_fast: int
    hpc: int
    ultra_fast: int


class MetaStatsResponse(BaseModel):
    total_stations: int
    by_country: list[CountryStats]
    by_power_band: list[PowerBandStats]


class OperatorCount(BaseModel):
    operator: str
    count: int


class MetaOperatorsResponse(BaseModel):
    operators: list[OperatorCount]
    country: str | None = None
    limit: int


class RouteEndpoint(BaseModel):
    lat: float
    lon: float


class AlongRouteStationResult(BaseModel):
    station: Station
    deviation_km: float
    route_distance_km: float
    extra_minutes: float
    wrong_side: bool


class AlongRouteResponse(BaseModel):
    origin: RouteEndpoint
    destination: RouteEndpoint
    corridor_km: float
    behind_margin_km: float
    route_distance_km: float
    route_duration_minutes: float
    route_geometry: dict[str, Any] | None = None
    results: list[AlongRouteStationResult]
    candidates_in_bbox: int


DEFAULT_STATIONS_LIMIT = 100
MAX_STATIONS_LIMIT = 5000
MAX_OPERATORS_LIMIT = 100
MAX_ROUTE_RESULTS_LIMIT = 50
MAX_CORRIDOR_KM = 50.0
