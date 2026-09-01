import { describe, expect, it } from 'vitest'

import { haversineMeters, shouldRecenterMapOnUserMove } from './mapFollowUser'

describe('mapFollowUser', () => {
  it('recentra en el primer punto', () => {
    expect(shouldRecenterMapOnUserMove(null, { lat: 40.4, lon: -3.7 })).toBe(true)
  })

  it('no recentra si el movimiento es pequeño', () => {
    const prev = { lat: 40.4, lon: -3.7 }
    const next = { lat: 40.4003, lon: -3.7003 }
    expect(haversineMeters(prev, next)).toBeLessThan(80)
    expect(shouldRecenterMapOnUserMove(prev, next)).toBe(false)
  })

  it('recentra si el movimiento supera el umbral', () => {
    const prev = { lat: 40.4, lon: -3.7 }
    const next = { lat: 40.41, lon: -3.7 }
    expect(shouldRecenterMapOnUserMove(prev, next)).toBe(true)
  })
})
