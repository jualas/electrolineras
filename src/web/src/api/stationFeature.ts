import type { Station, StationFeature } from './types'

export function stationToFeature(station: Station): StationFeature {
  return {
    type: 'Feature',
    id: station.id,
    geometry: {
      type: 'Point',
      coordinates: [station.location.lon, station.location.lat],
    },
    properties: {
      id: station.id,
      source: station.source,
      country: station.country,
      site_name: station.site_name,
      operator: station.operator,
      max_power_kw: station.max_power_kw,
      access: station.access,
      connector_count: station.connectors.length,
      address: station.location.address ?? null,
    },
  }
}
