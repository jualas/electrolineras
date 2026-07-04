import { useCallback, useEffect, useState } from 'react'

import {
  CHARGING_PREFERENCES_STORAGE_KEY,
  DEFAULT_CHARGING_PREFERENCES,
  parseStoredChargingPreferences,
  toggleOperatorSelection,
  type ChargingPreferencesState,
} from '../charging/chargingPreferences'

export function useChargingPreferences() {
  const [preferences, setPreferences] = useState<ChargingPreferencesState>(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_CHARGING_PREFERENCES
    }
    return parseStoredChargingPreferences(localStorage.getItem(CHARGING_PREFERENCES_STORAGE_KEY))
  })

  useEffect(() => {
    localStorage.setItem(CHARGING_PREFERENCES_STORAGE_KEY, JSON.stringify(preferences))
  }, [preferences])

  const toggleOperator = useCallback((operator: string) => {
    setPreferences((current) => ({
      ...current,
      preferredOperators: toggleOperatorSelection(current.preferredOperators, operator),
    }))
  }, [])

  const setMaxPriceEurKwh = useCallback((value: number | null) => {
    setPreferences((current) => ({
      ...current,
      maxPriceEurKwh: value != null && value > 0 ? value : null,
    }))
  }, [])

  const clearPreferences = useCallback(() => {
    setPreferences(DEFAULT_CHARGING_PREFERENCES)
  }, [])

  return {
    preferences,
    toggleOperator,
    setMaxPriceEurKwh,
    clearPreferences,
  }
}
