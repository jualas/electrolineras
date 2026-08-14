export type ExternalUserComment = {
  rating?: number | null
  comment?: string | null
  username?: string | null
  created_at?: string | null
  checkin_label?: string | null
}

export type ChargingPointInfo = {
  label: string
  evse_id?: string | null
  status?: string | null
  connector_format?: string | null
  cable_note?: string | null
  summary: string
  connectors: { connector_type: string; power_kw: number; connector_format?: string | null }[]
}

export type StationFeatureProperties = {
  id: string
  source: string
  country: string
  site_name: string | null
  operator: string | null
  max_power_kw: number
  access: string | null
  connector_count: number
  connector_summary?: string | null
  charging_point_count?: number | null
  charging_points?: string | ChargingPointInfo[] | null
  address: string | null
  dynamic_status?: string | null
  dynamic_price_eur_kwh?: number | null
  dynamic_updated_at?: string | null
  external_rating_avg?: number | null
  external_rating_count?: number | null
  external_comments?: ExternalUserComment[] | null
  ocm_poi_id?: number | null
  charging_classification?: string | null
  soc_arrival_pct?: number | null
  planned_stop_order?: number | null
  soc_departure_pct?: number | null
  charge_minutes?: number | null
}

export type StationFeature = {
  type: 'Feature'
  id: string
  geometry: {
    type: 'Point'
    coordinates: [number, number]
  }
  properties: StationFeatureProperties
}

export type GeoJSONStationCollection = {
  type: 'FeatureCollection'
  features: StationFeature[]
  pagination: {
    total: number
    limit: number
    offset: number
    has_more: boolean
  }
}

export type MapBounds = {
  west: number
  south: number
  east: number
  north: number
}

export type StationQuery = {
  bbox: MapBounds
  minKw?: number
  maxKw?: number
  country?: string
  limit?: number
  publicOpenOnly?: boolean
  excludeCommercial?: boolean
  adHocOnly?: boolean
  availableOnly?: boolean
  maxPriceEurKwh?: number | null
  connectorTypes?: string[]
}

export type LatLon = {
  lat: number
  lon: number
}

export type Station = {
  id: string
  source: string
  country: string
  site_name: string | null
  operator: string | null
  location: LatLon & { address?: string | null }
  connectors: {
    connector_type: string
    power_kw: number
    connector_format?: string | null
    status?: string | null
    evse_id?: string | null
    physical_reference?: string | null
  }[]
  max_power_kw: number
  access: string | null
  raw_ref: string
  dynamic_status?: string | null
  dynamic_price_eur_kwh?: number | null
  dynamic_updated_at?: string | null
  external_rating_avg?: number | null
  external_rating_count?: number | null
  external_comments?: ExternalUserComment[]
  ocm_poi_id?: number | null
}

export type AlongRouteStationResult = {
  station: Station
  deviation_km: number
  route_distance_km: number
  extra_minutes: number
  wrong_side: boolean
}

export type RouteLineGeometry = {
  type: 'LineString'
  coordinates: [number, number][]
}

export type AlongRouteResponse = {
  origin: LatLon
  destination: LatLon
  corridor_km: number
  behind_margin_km: number
  route_distance_km: number
  route_duration_minutes: number
  geodesic_distance_km?: number | null
  route_shortest_distance_km?: number | null
  route_fastest_distance_km?: number | null
  route_conventional_distance_km?: number | null
  route_conventional_duration_minutes?: number | null
  shortest_excess_km?: number | null
  route_variants_approximate?: boolean
  route_geometry: RouteLineGeometry | null
  route_shortest_geometry?: RouteLineGeometry | null
  route_fastest_geometry?: RouteLineGeometry | null
  route_conventional_geometry?: RouteLineGeometry | null
  route_preference?: RoutePreference
  avoid_highways?: boolean
  results: AlongRouteStationResult[]
  candidates_in_bbox: number
  route_variant_results?: Partial<Record<RoutePreference, RouteVariantAlongRouteSnapshot>> | null
}

export type NearbyStationResult = {
  station: Station
  distance_m: number
  distance_km: number
  access_class: string
}

export type NearbyResponse = {
  reference: LatLon
  reference_label: string | null
  radius_m: number | null
  bbox: number[] | null
  results: NearbyStationResult[]
}

export type GeocodeResult = {
  lat: number
  lon: number
  label: string
}

export type NearbyReferenceResponse = {
  reference: LatLon
  reference_label: string | null
}

export type ChargingClassification = 'safe' | 'adjusted' | 'critical' | 'unreachable'

export type ChargingPlanStopResult = {
  station: Station
  deviation_km: number
  route_distance_km: number
  extra_minutes: number
  wrong_side: boolean
  distance_from_origin_km: number
  soc_arrival_pct: number
  classification: ChargingClassification
}

export type PlannedRouteStopResult = ChargingPlanStopResult & {
  order: number
  leg_distance_km: number
  leg_driving_minutes?: number
  soc_departure_pct: number
  charge_minutes: number
  leg_energy_kwh?: number | null
  recommended_charge_from_pct?: number | null
  recommended_charge_to_pct?: number | null
  effective_charge_power_kw?: number | null
  estimated_charge_cost_eur?: number | null
  operator?: string | null
}

export type RouteTripSummaryResult = {
  total_duration_minutes: number
  driving_duration_minutes: number
  total_charge_minutes: number
  total_energy_kwh: number
  estimated_charge_cost_eur?: number | null
  projected_destination_soc_pct?: number | null
  stop_count: number
}

export type ChargingPlanStrategyResult = {
  id: string
  label: string
  station_id: string | null
  soc_arrival_pct: number | null
  classification: ChargingClassification | null
  summary: string
}

export type RoutePreference = 'fastest' | 'shortest' | 'conventional'

export type VehicleEnergyInput = {
  soc_percent: number
  usable_capacity_kwh: number
  consumption_wh_per_km: number
  terrain_factor?: number
  reserve_soc_percent?: number
  vehicle_preset_id?: string | null
  max_charge_power_kw?: number
  min_destination_soc_pct?: number
  min_stop_arrival_soc_pct?: number
  max_charge_soc_pct?: number
  consumption_kwh_per_100km?: number | null
}

export type ChargingPlanResponse = {
  mode: 'route' | 'emergency'
  vehicle: VehicleEnergyInput
  range_km: number
  charging_reach_km: number
  origin: LatLon
  destination: LatLon | null
  corridor_km: number | null
  geodesic_distance_km?: number | null
  route_distance_km: number | null
  route_duration_minutes: number | null
  route_shortest_distance_km?: number | null
  route_fastest_distance_km?: number | null
  route_conventional_distance_km?: number | null
  route_conventional_duration_minutes?: number | null
  shortest_excess_km?: number | null
  route_variants_approximate?: boolean
  soc_at_destination_pct: number | null
  reachable_without_stop: boolean
  route_geometry: RouteLineGeometry | null
  route_shortest_geometry?: RouteLineGeometry | null
  route_fastest_geometry?: RouteLineGeometry | null
  route_conventional_geometry?: RouteLineGeometry | null
  preview_route_geometry?: RouteLineGeometry | null
  route_preference?: RoutePreference | null
  avoid_highways?: boolean
  exclude_slow_chargers?: boolean
  preferred_operators?: string[]
  max_price_eur_kwh?: number | null
  stops: ChargingPlanStopResult[]
  origin_stops: ChargingPlanStopResult[]
  planned_stops?: PlannedRouteStopResult[]
  projected_soc_at_destination_with_plan?: number | null
  route_trip_summary?: RouteTripSummaryResult | null
  strategies: ChargingPlanStrategyResult[]
  warnings: string[]
  candidates_in_bbox: number
  destination_stay?: DestinationStayAdviceResult | null
  route_variant_plans?: Partial<Record<RoutePreference, RouteVariantChargingPlanSnapshot>> | null
  consumption_source?: 'historical' | 'telemetry' | 'preset' | 'hybrid' | null
  consumption_kwh_per_100km?: number | null
  consumption_confidence?: 'low' | 'medium' | 'high' | null
  consumption_note?: string | null
  consumption_bin?: 'highway' | 'mixed' | 'conventional' | 'mountain' | null
}

export type RouteVariantChargingPlanSnapshot = {
  route_distance_km: number
  route_duration_minutes: number
  soc_at_destination_pct: number | null
  reachable_without_stop: boolean
  stops: ChargingPlanStopResult[]
  origin_stops: ChargingPlanStopResult[]
  planned_stops?: PlannedRouteStopResult[]
  projected_soc_at_destination_with_plan?: number | null
  route_trip_summary?: RouteTripSummaryResult | null
  strategies: ChargingPlanStrategyResult[]
  warnings: string[]
  destination_stay?: DestinationStayAdviceResult | null
  candidates_in_bbox: number
}

export type RouteVariantAlongRouteSnapshot = {
  route_distance_km: number
  route_duration_minutes: number
  results: AlongRouteStationResult[]
  candidates_in_bbox: number
}

export type DestinationStayAdviceResult = {
  radius_km: number
  local_mobility_km: number
  local_soc_needed_pct: number
  recommended_soc_at_arrival_pct: number
  minimum_soc_at_arrival_pct: number
  projected_soc_at_arrival_pct?: number | null
  arrival_gap_pct?: number | null
  infrastructure_level: string
  charge_time_hint: string
  summary: string
  warnings: string[]
  bands: {
    ac_slow: number
    ac_fast: number
    dc_fast: number
    hpc: number
    total: number
    best_max_kw: number
    nearest_km?: number | null
  }
  nearest_chargers?: DestinationChargerOption[]
}

export type DestinationChargerOption = {
  station_id: string
  label: string
  operator?: string | null
  max_power_kw: number
  distance_km: number
  lat: number
  lon: number
  power_band: string
}

export type TripGuideContext = {
  destination_label?: string | null
  cultural_poi_enabled: boolean
  user_note?: string | null
  poi_hints: string[]
  nearest_destination_chargers: DestinationChargerOption[]
  charging_while_visiting_hint?: string | null
  vehicle_snapshot: Record<string, unknown>
  plan_snapshot: Record<string, unknown>
  consumption_profile?: ConsumptionProfileResponse | null
  consumption_source?: 'historical' | 'telemetry' | 'preset' | 'hybrid' | null
  consumption_kwh_per_100km?: number | null
  consumption_confidence?: 'low' | 'medium' | 'high' | null
  consumption_note?: string | null
  consumption_bin?: 'highway' | 'mixed' | 'conventional' | 'mountain' | null
}

export type VehicleTelemetryResult = {
  car_id: number
  display_name: string | null
  state: string | null
  lat: number
  lon: number
  battery_level_pct: number
  usable_battery_level_pct?: number | null
  est_battery_range_km?: number | null
  rated_battery_range_km?: number | null
  ideal_battery_range_km?: number | null
  model?: string | null
  trim_badging?: string | null
  car_model_label?: string | null
  version?: string | null
  charging_state?: string | null
  inside_temp_c?: number | null
  outside_temp_c?: number | null
  odometer_km?: number | null
  source?: string
}

export type ConsumptionBinResult = {
  bin: 'highway' | 'mixed' | 'conventional' | 'mountain'
  wh_per_km?: number | null
  kwh_per_100km?: number | null
  sample_count: number
  total_distance_km: number
}

export type ConsumptionProfileResponse = {
  available: boolean
  source: 'historical' | 'telemetry' | 'preset' | 'hybrid'
  lookback_days: number
  min_distance_km?: number
  drive_count?: number
  car_id?: number | null
  note?: string | null
  bins: Record<string, ConsumptionBinResult>
}

export type TripAdviceResponse = {
  plan: ChargingPlanResponse
  agent_summary: string
  agent_bullets: string[]
  vehicle?: VehicleTelemetryResult | null
  live_soc_percent?: number | null
  departure_soc_percent?: number | null
  soc_source?: 'live' | 'simulated' | null
  consumption_source?: 'historical' | 'telemetry' | 'preset' | 'hybrid' | null
  consumption_kwh_per_100km?: number | null
  consumption_confidence?: 'low' | 'medium' | 'high' | null
  consumption_note?: string | null
  consumption_bin?: 'highway' | 'mixed' | 'conventional' | 'mountain' | null
  consumption_profile?: ConsumptionProfileResponse | null
  live_consumption_kwh_per_100km?: number | null
  consumption_divergence_pct?: number | null
  consumption_divergence_alert?: boolean
}

export type TripGuideResponse = TripAdviceResponse & {
  guide_text: string
  guide_source: 'deterministic' | 'dify'
  context: TripGuideContext
}

export type ItineraryPlaceResult = {
  order: number
  raw: string
  label: string
  lat: number
  lon: number
  overnight: boolean
  nights?: number | null
  is_home: boolean
  confidence: string
}

export type ParseItineraryResponse = {
  departure_soc_percent?: number | null
  return_home: boolean
  stops: ItineraryPlaceResult[]
  warnings: string[]
}

export type MultiLegPlanLegResult = {
  order: number
  from_label: string
  to_label: string
  overnight: boolean
  nights?: number | null
  departure_soc_pct: number
  arrival_soc_pct: number
  next_departure_soc_pct?: number | null
  plan: ChargingPlanResponse
}

export type MultiLegAggregate = {
  total_route_km: number
  total_driving_minutes: number
  total_charge_minutes: number
  final_soc_pct?: number | null
  all_planned_stops: PlannedRouteStopResult[]
  origin: { lat: number; lon: number }
  final_destination: { lat: number; lon: number }
}

export type MultiLegChargingPlanResponse = {
  legs: MultiLegPlanLegResult[]
  aggregate: MultiLegAggregate
  warnings: string[]
  agent_summary: string
  agent_bullets: string[]
}

export type AuthConfigResponse = {
  private_stack_enabled: boolean
  login_enabled: boolean
  login_username?: string | null
  token_fallback_enabled: boolean
}

export type AuthSessionResponse = {
  authenticated: boolean
  private_stack_enabled: boolean
  login_enabled: boolean
}
