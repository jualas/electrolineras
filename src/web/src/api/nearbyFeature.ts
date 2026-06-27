import { stationToFeature } from '../api/stationFeature'
import type { NearbyResponse } from '../api/types'

export function nearbyToFeatures(results: NearbyResponse['results']) {
  return results.map((item) => stationToFeature(item.station))
}
