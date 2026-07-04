import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchVehicleState } from '../api/auth'
import type { VehicleTelemetryResult } from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { syncSocToVehicleProfile } from '../vehicle/telemetryProfile'

export const TELEMETRY_POLL_INTERVAL_MS = 60_000

type UseVehicleTelemetryOptions = {
  enabled?: boolean
  pollIntervalMs?: number
  syncSoc?: boolean
  currentSocPercent?: number
  onSocChange?: (socPercent: number) => void
}

export function useVehicleTelemetry(options: UseVehicleTelemetryOptions = {}) {
  const { authenticated, privateStackEnabled, loginEnabled, loading: authLoading } = useAuth()
  const enabled =
    (options.enabled ?? true) && !authLoading && authenticated && privateStackEnabled

  const [vehicle, setVehicle] = useState<VehicleTelemetryResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const initialLoadRef = useRef(false)

  const applySocSync = useCallback(
    (telemetry: VehicleTelemetryResult) => {
      if (!options.syncSoc || options.onSocChange == null || options.currentSocPercent == null) {
        return
      }
      syncSocToVehicleProfile(telemetry, options.currentSocPercent, options.onSocChange)
    },
    [options.syncSoc, options.onSocChange, options.currentSocPercent],
  )

  const refresh = useCallback(async () => {
    if (!enabled) {
      return
    }
    setLoading(true)
    setError(null)
    try {
      const state = await fetchVehicleState()
      setVehicle(state)
      applySocSync(state)
    } catch (err) {
      setVehicle(null)
      setError(err instanceof Error ? err.message : 'No se pudo leer el vehículo')
    } finally {
      setLoading(false)
    }
  }, [applySocSync, enabled])

  useEffect(() => {
    if (!enabled) {
      initialLoadRef.current = false
      setVehicle(null)
      setError(null)
      return
    }
    if (initialLoadRef.current) {
      return
    }
    initialLoadRef.current = true
    void refresh()
  }, [enabled, refresh])

  useEffect(() => {
    if (!enabled || options.pollIntervalMs == null || options.pollIntervalMs <= 0) {
      return
    }
    const timer = window.setInterval(() => {
      void refresh()
    }, options.pollIntervalMs)
    return () => window.clearInterval(timer)
  }, [enabled, options.pollIntervalMs, refresh])

  return {
    vehicle,
    loading,
    error,
    refresh,
    available: enabled && vehicle != null,
    enabled,
    authenticated,
    privateStackEnabled,
    loginEnabled,
    authLoading,
  }
}
