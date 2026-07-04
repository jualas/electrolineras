import { useCallback, useEffect, useState } from 'react'

import {
  ACTIVE_TRIP_STORAGE_KEY,
  DEFAULT_EN_MARCHA_SETTINGS,
  EN_MARCHA_SETTINGS_STORAGE_KEY,
  parseActiveTrip,
  parseEnMarchaSettings,
  type ActiveTripState,
  type EnMarchaSettings,
} from '../charging/activeTrip'

export function useActiveTrip() {
  const [activeTrip, setActiveTripState] = useState<ActiveTripState | null>(() => {
    if (typeof window === 'undefined') {
      return null
    }
    return parseActiveTrip(sessionStorage.getItem(ACTIVE_TRIP_STORAGE_KEY))
  })

  const [enMarchaSettings, setEnMarchaSettingsState] = useState<EnMarchaSettings>(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_EN_MARCHA_SETTINGS
    }
    return parseEnMarchaSettings(sessionStorage.getItem(EN_MARCHA_SETTINGS_STORAGE_KEY))
  })

  useEffect(() => {
    if (activeTrip) {
      sessionStorage.setItem(ACTIVE_TRIP_STORAGE_KEY, JSON.stringify(activeTrip))
    } else {
      sessionStorage.removeItem(ACTIVE_TRIP_STORAGE_KEY)
    }
  }, [activeTrip])

  useEffect(() => {
    sessionStorage.setItem(EN_MARCHA_SETTINGS_STORAGE_KEY, JSON.stringify(enMarchaSettings))
  }, [enMarchaSettings])

  const saveActiveTrip = useCallback((trip: ActiveTripState) => {
    setActiveTripState({ ...trip, updatedAt: Date.now() })
  }, [])

  const clearActiveTrip = useCallback(() => {
    setActiveTripState(null)
  }, [])

  const setAutoFollow = useCallback((autoFollow: boolean) => {
    setEnMarchaSettingsState({ autoFollow })
  }, [])

  return {
    activeTrip,
    enMarchaSettings,
    saveActiveTrip,
    clearActiveTrip,
    setAutoFollow,
  }
}
