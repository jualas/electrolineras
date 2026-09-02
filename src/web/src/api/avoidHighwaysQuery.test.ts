import { describe, expect, it, vi } from 'vitest'

vi.mock('./client', () => ({
  fetchApi: vi.fn(async (path: string) => ({ path })),
}))

import { fetchApi } from './client'
import { fetchChargingPlan } from './chargingPlan'
import { fetchAlongRoute } from './route'

describe('avoid_highways query param', () => {
  it('envía avoid_highways=false cuando se permiten peajes', async () => {
    await fetchChargingPlan({
      originLat: 41.387,
      originLon: 2.17,
      destLat: 39.47,
      destLon: -0.376,
      socPercent: 80,
      usableCapacityKwh: 60,
      consumptionWhPerKm: 170,
      terrainFactor: 1,
      routePreference: 'fastest',
      avoidHighways: false,
    })
    const path = String(vi.mocked(fetchApi).mock.calls.at(-1)?.[0] ?? '')
    expect(path).toContain('avoid_highways=false')
  })

  it('envía avoid_highways=true cuando se evitan peajes', async () => {
    await fetchChargingPlan({
      originLat: 41.387,
      originLon: 2.17,
      destLat: 39.47,
      destLon: -0.376,
      socPercent: 80,
      usableCapacityKwh: 60,
      consumptionWhPerKm: 170,
      terrainFactor: 1,
      routePreference: 'fastest',
      avoidHighways: true,
    })
    const path = String(vi.mocked(fetchApi).mock.calls.at(-1)?.[0] ?? '')
    expect(path).toContain('avoid_highways=true')
  })

  it('along-route también envía false explícito', async () => {
    await fetchAlongRoute({
      originLat: 41.387,
      originLon: 2.17,
      destLat: 39.47,
      destLon: -0.376,
      minKw: 100,
      avoidHighways: false,
    })
    const path = String(vi.mocked(fetchApi).mock.calls.at(-1)?.[0] ?? '')
    expect(path).toContain('avoid_highways=false')
  })
})
