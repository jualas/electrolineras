import { useCallback, useEffect, useState } from 'react'

import {
  apiQueryFromFilter,
  loadStoredPowerFilter,
  presetToFilter,
  storePowerFilter,
  type PowerFilter,
  type PowerPresetId,
} from '../filters/powerPresets'

export function usePowerFilter(initialPreset: PowerPresetId = 'all') {
  const [filter, setFilterState] = useState<PowerFilter>(() => {
    const stored = loadStoredPowerFilter()
    return stored ?? presetToFilter(initialPreset)
  })

  useEffect(() => {
    storePowerFilter(filter)
  }, [filter])

  const setPreset = useCallback((presetId: PowerPresetId) => {
    if (presetId === 'custom') {
      setFilterState((current: PowerFilter) =>
        presetToFilter('custom', {
          minKw: current.minKw ?? 22,
          maxKw: current.maxKw ?? 150,
        }),
      )
      return
    }
    setFilterState(presetToFilter(presetId))
  }, [])

  const setCustomRange = useCallback((minKw: number, maxKw: number) => {
    const safeMin = Math.min(minKw, maxKw)
    const safeMax = Math.max(minKw, maxKw)
    setFilterState({
      presetId: 'custom',
      minKw: safeMin,
      maxKw: safeMax,
    })
  }, [])

  return {
    filter,
    setPreset,
    setCustomRange,
    apiQuery: apiQueryFromFilter(filter),
  }
}
