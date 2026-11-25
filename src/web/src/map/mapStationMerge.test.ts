import { describe, expect, it } from 'vitest'

import { shouldFetchStations } from './mapStationMerge'
import type { MapBounds } from '../api/types'

const coverage: MapBounds = { west: -10, south: 35, east: 4, north: 44 }
const inside: MapBounds = { west: -2.6, south: 38.5, east: -2.3, north: 38.8 }

describe('shouldFetchStations', () => {
  it('no recarga al acercar si la cobertura estaba completa', () => {
    expect(shouldFetchStations(coverage, inside, 5.8, 14, false)).toBe(false)
  })

  it('recarga al acercar si la página anterior venía cortada por el límite', () => {
    expect(shouldFetchStations(coverage, inside, 5.8, 14, true)).toBe(true)
  })

  it('acumula acercamientos pequeños respecto al zoom de la descarga', () => {
    expect(shouldFetchStations(coverage, inside, 5.8, 6.1, true)).toBe(false)
    expect(shouldFetchStations(coverage, inside, 5.8, 6.4, true)).toBe(true)
  })

  it('sigue recargando al salir de la zona ya pedida', () => {
    const outside: MapBounds = { west: 10, south: 50, east: 12, north: 52 }
    expect(shouldFetchStations(coverage, outside, 5.8, 5.8, false)).toBe(true)
  })

  it('recarga al alejar aunque la página estuviera completa', () => {
    expect(shouldFetchStations(coverage, inside, 8, 6, false)).toBe(true)
  })
})
