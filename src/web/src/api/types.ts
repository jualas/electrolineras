export type StationFeatureProperties = {
  id: string
  source: string
  country: string
  site_name: string | null
  operator: string | null
  max_power_kw: number
  access: string | null
  connector_count: number
  address: string | null
  dynamic_status?: string | null
  dynamic_price_eur_kwh?: number | null
  dynamic_updated_at?: string | null
  charging_classification?: string | null
  soc_arrival_pct?: number | null
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
  connectors: { connector_type: string; power_kw: number }[]
  max_power_kw: number
  access: string | null
  raw_ref: string
  dynamic_status?: string | null
  dynamic_price_eur_kwh?: number | null
  dynamic_updated_at?: string | null
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
  route_geometry: RouteLineGeometry | null
  results: AlongRouteStationResult[]
  candidates_in_bbox: number
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

export type ChargingPlanStrategyResult = {
  id: string
  label: string
  station_id: string | null
  soc_arrival_pct: number | null
  classification: ChargingClassification | null
  summary: string
}

export type ChargingPlanResponse = {
  mode: 'route' | 'emergency'
  range_km: number
  origin: LatLon
  destination: LatLon | null
  corridor_km: number | null
  route_distance_km: number | null
  route_duration_minutes: number | null
  soc_at_destination_pct: number | null
  reachable_without_stop: boolean
  route_geometry: RouteLineGeometry | null
  stops: ChargingPlanStopResult[]
  strategies: ChargingPlanStrategyResult[]
  warnings: string[]
  candidates_in_bbox: number
}
