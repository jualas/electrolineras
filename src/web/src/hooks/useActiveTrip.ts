import { useCallback, useEffect, useState } from 'react'

import {
  advanceTripProgress,
  clampTripProgress,
  DEFAULT_EN_MARCHA_SETTINGS,
  EN_MARCHA_SETTINGS_STORAGE_KEY,
  loadActiveTripFromStorage,
  loadEnMarchaSettingsFromStorage,
  persistActiveTripToStorage,
  type ActiveTripState,
  type EnMarchaSettings,
} from '../charging/activeTrip'

export function useActiveTrip() {
  const [activeTrip, setActiveTripState] = useState<ActiveTripState | null>(() => {
    if (typeof window === 'undefined') {
      return null
    }
    return loadActiveTripFromStorage()
  })

  const [enMarchaSettings, setEnMarchaSettingsState] = useState<EnMarchaSettings>(() => {
    if (typeof window === 'undefined') {
      return DEFAULT_EN_MARCHA_SETTINGS
    }
    return loadEnMarchaSettingsFromStorage()
  })

  useEffect(() => {
    persistActiveTripToStorage(activeTrip)
  }, [activeTrip])

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(EN_MARCHA_SETTINGS_STORAGE_KEY, JSON.stringify(enMarchaSettings))
    window.sessionStorage.removeItem(EN_MARCHA_SETTINGS_STORAGE_KEY)
  }, [enMarchaSettings])

  const saveActiveTrip = useCallback((trip: ActiveTripState) => {
    setActiveTripState({ ...trip, version: 2, updatedAt: Date.now() })
  }, [])

  const clearActiveTrip = useCallback(() => {
    setActiveTripState(null)
  }, [])

  const setAutoFollow = useCallback((autoFollow: boolean) => {
    setEnMarchaSettingsState((prev) => ({ ...prev, autoFollow }))
  }, [])

  const setGpsEnabled = useCallback((gpsEnabled: boolean) => {
    setEnMarchaSettingsState((prev) => ({ ...prev, gpsEnabled }))
  }, [])

  const markStopCompleted = useCallback((stopOrder: number, totalStops: number) => {
    setActiveTripState((prev) => {
      if (!prev) {
        return null
      }
      return advanceTripProgress(prev, stopOrder, totalStops)
    })
  }, [])

  const updateTripProgress = useCallback(
    (stopCount: number) => {
      setActiveTripState((prev) => {
        if (!prev) {
          return null
        }
        return {
          ...prev,
          progress: clampTripProgress(prev.progress, stopCount),
          updatedAt: Date.now(),
        }
      })
    },
    [],
  )

  return {
    activeTrip,
    enMarchaSettings,
    saveActiveTrip,
    clearActiveTrip,
    setAutoFollow,
    setGpsEnabled,
    markStopCompleted,
    updateTripProgress,
  }
}
