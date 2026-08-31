import { describe, expect, it } from 'vitest'

import { googleMapsRouteUrl, routeShareText } from './externalMaps'

describe('externalMaps export', () => {
  const route = {
    origin: { lat: 37.63, lon: -0.99 },
    destination: { lat: 43.34, lon: -1.79 },
    waypoints: [
      { lat: 37.49, lon: -2.77 },
      { lat: 38.99, lon: -1.86 },
      { lat: 40.63, lon: -3.58 },
    ],
    title: 'Viaje test',
  }

  it('googleMapsRouteUrl con 3 waypoints cabe en límite razonable', () => {
    const url = googleMapsRouteUrl({ ...route, maxWaypoints: 8 })
    expect(url.length).toBeLessThan(2000)
    expect(url).toContain('waypoints=')
  })

  it('routeShareText next_stop usa el índice de parada', () => {
    const text = routeShareText(route, 'next_stop', 2)
    expect(text).toContain('Parada de carga 3')
    expect(text).toContain('40.63')
  })
})
