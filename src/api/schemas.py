from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

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


class MetaOcmResponse(BaseModel):
    configured: bool
    stations_with_ratings: int
    last_sync_status: str | None = None
    last_sync_finished_at: str | None = None
    last_sync_enriched: int | None = None


class GeocodeResultItem(BaseModel):
    lat: float
    lon: float
    label: str


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


ChargingClassification = Literal["safe", "adjusted", "critical", "unreachable"]


class VehicleEnergyInput(BaseModel):
    soc_percent: float
    usable_capacity_kwh: float
    consumption_wh_per_km: float
    terrain_factor: float = 1.0
    reserve_soc_percent: float = 10.0


class ChargingPlanStopResult(BaseModel):
    station: Station
    deviation_km: float
    route_distance_km: float
    extra_minutes: float
    wrong_side: bool
    distance_from_origin_km: float
    soc_arrival_pct: float
    classification: ChargingClassification


class ChargingPlanStrategyResult(BaseModel):
    id: str
    label: str
    station_id: str | None
    soc_arrival_pct: float | None
    classification: ChargingClassification | None
    summary: str


class DestinationChargingBandsResult(BaseModel):
    ac_slow: int
    ac_fast: int
    dc_fast: int
    hpc: int
    total: int
    best_max_kw: float
    nearest_km: float | None = None


class DestinationStayAdviceResult(BaseModel):
    radius_km: float
    local_mobility_km: float
    local_soc_needed_pct: float
    recommended_soc_at_arrival_pct: float
    minimum_soc_at_arrival_pct: float
    projected_soc_at_arrival_pct: float | None = None
    arrival_gap_pct: float | None = None
    bands: DestinationChargingBandsResult
    infrastructure_level: str
    charge_time_hint: str
    summary: str
    warnings: list[str] = Field(default_factory=list)


class ChargingPlanResponse(BaseModel):
    mode: Literal["route", "emergency"]
    vehicle: VehicleEnergyInput
    range_km: float
    charging_reach_km: float
    origin: RouteEndpoint
    destination: RouteEndpoint | None = None
    corridor_km: float | None = None
    route_distance_km: float | None = None
    route_duration_minutes: float | None = None
    soc_at_destination_pct: float | None = None
    reachable_without_stop: bool
    route_geometry: dict[str, Any] | None = None
    preview_route_geometry: dict[str, Any] | None = None
    stops: list[ChargingPlanStopResult]
    origin_stops: list[ChargingPlanStopResult] = Field(default_factory=list)
    strategies: list[ChargingPlanStrategyResult]
    warnings: list[str]
    candidates_in_bbox: int
    destination_stay: DestinationStayAdviceResult | None = None


class TripAdviceResponse(BaseModel):
    """Respuesta enriquecida para agentes (Dify / Cursor CLI)."""

    plan: ChargingPlanResponse
    agent_summary: str
    agent_bullets: list[str] = Field(default_factory=list)


class NearbyStationResult(BaseModel):
    station: Station
    distance_m: float
    distance_km: float
    access_class: str


class NearbyResponse(BaseModel):
    reference: RouteEndpoint
    reference_label: str | None = None
    radius_m: float | None = None
    bbox: list[float] | None = None
    results: list[NearbyStationResult]


DEFAULT_NEARBY_LIMIT = 50
MAX_NEARBY_LIMIT = 200


DEFAULT_STATIONS_LIMIT = 100
MAX_STATIONS_LIMIT = 5000
MAX_OPERATORS_LIMIT = 100
MAX_ROUTE_RESULTS_LIMIT = 50
MAX_CORRIDOR_KM = 50.0
