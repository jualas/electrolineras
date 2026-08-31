import { describe, expect, it } from 'vitest'

import { distancePointToRouteKm, isOffRoute } from './routeDeviation'

describe('routeDeviation', () => {
  const geometry = {
    type: 'LineString' as const,
    coordinates: [
      [-1.0, 37.6],
      [-1.1, 37.65],
      [-1.2, 37.7],
    ] as [number, number][],
  }

  it('punto sobre la ruta tiene desvío bajo', () => {
    const km = distancePointToRouteKm({ lat: 37.65, lon: -1.1 }, geometry)
    expect(km).not.toBeNull()
    expect(km!).toBeLessThan(0.5)
    expect(isOffRoute({ lat: 37.65, lon: -1.1 }, geometry)).toBe(false)
  })

  it('punto lejos marca desvío', () => {
    expect(isOffRoute({ lat: 38.5, lon: -1.1 }, geometry)).toBe(true)
  })
})
