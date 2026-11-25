import { apiUrl } from './client'
import type { StationReliabilityResponse } from './types'

export async function fetchStationReliability(
  stationId: string,
  options?: { verifyGoogle?: boolean; isolationRadiusKm?: number; signal?: AbortSignal },
): Promise<StationReliabilityResponse> {
  const params = new URLSearchParams()
  if (options?.verifyGoogle !== undefined) {
    params.set('verify_google', options.verifyGoogle ? 'true' : 'false')
  }
  if (options?.isolationRadiusKm !== undefined) {
    params.set('isolation_radius_km', String(options.isolationRadiusKm))
  }
  const qs = params.toString()
  const url = apiUrl(`/api/v1/stations/${encodeURIComponent(stationId)}/reliability${qs ? `?${qs}` : ''}`)
  const response = await fetch(url, { signal: options?.signal })
  if (!response.ok) {
    throw new Error(`No se pudo verificar la estación (HTTP ${response.status})`)
  }
  return (await response.json()) as StationReliabilityResponse
}
