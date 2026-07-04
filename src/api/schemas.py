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


RoutePreference = Literal["fastest", "shortest", "conventional"]


class AlongRouteResponse(BaseModel):
    origin: RouteEndpoint
    destination: RouteEndpoint
    corridor_km: float
    behind_margin_km: float
    geodesic_distance_km: float | None = None
    route_distance_km: float
    route_duration_minutes: float
    route_shortest_distance_km: float | None = None
    route_fastest_distance_km: float | None = None
    route_conventional_distance_km: float | None = None
    route_conventional_duration_minutes: float | None = None
    shortest_excess_km: float | None = None
    route_variants_approximate: bool = False
    route_geometry: dict[str, Any] | None = None
    route_shortest_geometry: dict[str, Any] | None = None
    route_fastest_geometry: dict[str, Any] | None = None
    route_conventional_geometry: dict[str, Any] | None = None
    route_preference: RoutePreference = "fastest"
    avoid_highways: bool = False
    results: list[AlongRouteStationResult]
    candidates_in_bbox: int


ChargingClassification = Literal["safe", "adjusted", "critical", "unreachable"]


class VehicleEnergyInput(BaseModel):
    soc_percent: float
    usable_capacity_kwh: float
    consumption_wh_per_km: float
    terrain_factor: float = 1.0
    reserve_soc_percent: float = 10.0
    vehicle_preset_id: str | None = None


class ChargingPlanStopResult(BaseModel):
    station: Station
    deviation_km: float
    route_distance_km: float
    extra_minutes: float
    wrong_side: bool
    distance_from_origin_km: float
    soc_arrival_pct: float
    classification: ChargingClassification


class PlannedRouteStopResult(BaseModel):
    order: int
    station: Station
    deviation_km: float
    route_distance_km: float
    extra_minutes: float
    wrong_side: bool
    distance_from_origin_km: float
    leg_distance_km: float
    soc_arrival_pct: float
    soc_departure_pct: float
    charge_minutes: float
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


class DestinationChargerOption(BaseModel):
    station_id: str
    label: str
    operator: str | None = None
    max_power_kw: float
    distance_km: float
    lat: float
    lon: float
    power_band: str


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
    nearest_chargers: list[DestinationChargerOption] = Field(default_factory=list)


class ChargingPlanResponse(BaseModel):
    mode: Literal["route", "emergency"]
    vehicle: VehicleEnergyInput
    range_km: float
    charging_reach_km: float
    origin: RouteEndpoint
    destination: RouteEndpoint | None = None
    corridor_km: float | None = None
    geodesic_distance_km: float | None = None
    route_distance_km: float | None = None
    route_duration_minutes: float | None = None
    route_shortest_distance_km: float | None = None
    route_fastest_distance_km: float | None = None
    route_conventional_distance_km: float | None = None
    route_conventional_duration_minutes: float | None = None
    shortest_excess_km: float | None = None
    route_variants_approximate: bool = False
    soc_at_destination_pct: float | None = None
    reachable_without_stop: bool
    route_geometry: dict[str, Any] | None = None
    route_shortest_geometry: dict[str, Any] | None = None
    route_fastest_geometry: dict[str, Any] | None = None
    route_conventional_geometry: dict[str, Any] | None = None
    preview_route_geometry: dict[str, Any] | None = None
    route_preference: RoutePreference | None = None
    avoid_highways: bool = False
    preferred_operators: list[str] = Field(default_factory=list)
    max_price_eur_kwh: float | None = None
    stops: list[ChargingPlanStopResult]
    origin_stops: list[ChargingPlanStopResult] = Field(default_factory=list)
    planned_stops: list[PlannedRouteStopResult] = Field(default_factory=list)
    projected_soc_at_destination_with_plan: float | None = None
    strategies: list[ChargingPlanStrategyResult]
    warnings: list[str]
    candidates_in_bbox: int
    destination_stay: DestinationStayAdviceResult | None = None


class VehicleTelemetryResult(BaseModel):
    car_id: int
    display_name: str | None = None
    state: str | None = None
    lat: float
    lon: float
    battery_level_pct: float
    usable_battery_level_pct: float | None = None
    est_battery_range_km: float | None = None
    rated_battery_range_km: float | None = None
    ideal_battery_range_km: float | None = None
    model: str | None = None
    trim_badging: str | None = None
    car_model_label: str | None = None
    version: str | None = None
    charging_state: str | None = None
    inside_temp_c: float | None = None
    outside_temp_c: float | None = None
    odometer_km: float | None = None
    source: str = "teslamateapi"


class TripAdviceResponse(BaseModel):
    """Respuesta enriquecida para agentes (Dify / Cursor CLI)."""

    plan: ChargingPlanResponse
    agent_summary: str
    agent_bullets: list[str] = Field(default_factory=list)
    vehicle: VehicleTelemetryResult | None = None
    live_soc_percent: float | None = None
    departure_soc_percent: float | None = Field(
        default=None,
        description="SOC usado en el plan (simulación de carga previa si difiere del vivo)",
    )


class TripGuideContext(BaseModel):
    """Contexto estructurado para workflow Dify (no inventar SOC/estaciones)."""

    destination_label: str | None = None
    cultural_poi_enabled: bool = False
    user_note: str | None = None
    poi_hints: list[str] = Field(default_factory=list)
    nearest_destination_chargers: list[DestinationChargerOption] = Field(default_factory=list)
    charging_while_visiting_hint: str | None = None
    vehicle_snapshot: dict[str, Any] = Field(default_factory=dict)
    plan_snapshot: dict[str, Any] = Field(default_factory=dict)


class TripGuideResponse(TripAdviceResponse):
    guide_text: str
    guide_source: Literal["deterministic", "dify"]
    context: TripGuideContext


class PrivateStackStatusResult(BaseModel):
    private_stack_enabled: bool
    token_required: bool
    teslamate_configured: bool
    charging_agent_enabled: bool
    login_enabled: bool = False
    mqtt_configured: bool = False
    teslamate_api_configured: bool = False
    dify_trip_guide_configured: bool = False


class AuthConfigResponse(BaseModel):
    private_stack_enabled: bool
    login_enabled: bool
    token_fallback_enabled: bool


class AuthSessionResponse(BaseModel):
    authenticated: bool
    private_stack_enabled: bool
    login_enabled: bool


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
