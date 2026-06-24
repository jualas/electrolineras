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
