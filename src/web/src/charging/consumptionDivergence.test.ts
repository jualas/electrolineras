import { describe, expect, it } from 'vitest'

import {
  consumptionDivergencePct,
  effectiveConsumptionWhPerKm,
  isConsumptionDivergent,
} from './consumptionDivergence'

describe('consumptionDivergence', () => {
  it('calcula Wh/km efectivo con terreno', () => {
    expect(effectiveConsumptionWhPerKm({ consumption_wh_per_km: 160, terrain_factor: 1.1 })).toBe(176)
  })

  it('marca divergencia >15%', () => {
    expect(isConsumptionDivergent(160, 190)).toBe(true)
    expect(consumptionDivergencePct(160, 176)).toBeCloseTo(10, 0)
    expect(isConsumptionDivergent(160, 176)).toBe(false)
  })
})
