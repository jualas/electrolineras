import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchNearestLive, type NearestLiveResponse } from '../api/nearestLive'
import { useDeviceLocation } from './useDeviceLocation'

const MOVE_THRESHOLD_M = 150
const MIN_REFETCH_MS = 12_000

function haversineM(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLon = toRad(b.lon - a.lon)
  const lat1 = toRad(a.lat)
  const lat2 = toRad(b.lat)
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2
  return 2 * 6371000 * Math.asin(Math.min(1, Math.sqrt(h)))
}

export type LiveNearestStatus = 'idle' | 'locating' | 'loading' | 'ready' | 'empty' | 'error'

type UseLiveNearestChargerOptions = {
  active: boolean
  /** Potencia mínima del panel (undefined = usar default API ~100 kW; 0 = sin mínimo). */
  minKw?: number
  maxKw?: number
  radiusM?: number
  adHocOnly?: boolean
  excludeParking?: boolean
}

export function useLiveNearestCharger({
  active,
  minKw,
  maxKw,
  radiusM = 50_000,
  adHocOnly = false,
  excludeParking = false,
}: UseLiveNearestChargerOptions) {
  const {
    location,
    status: gpsStatus,
    error: gpsError,
    refreshGps,
  } = useDeviceLocation({
    autoStart: active,
    watch: active,
    gpsLabel: 'Mi posición (Más cercano)',
  })

  const [result, setResult] = useState<NearestLiveResponse | null>(null)
  const [status, setStatus] = useState<LiveNearestStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const lastFetchRef = useRef<{ lat: number; lon: number; at: number } | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const clear = useCallback(() => {
    abortRef.current?.abort()
    abortRef.current = null
    lastFetchRef.current = null
    setResult(null)
    setStatus('idle')
    setError(null)
  }, [])

  // Si cambia el filtro de potencia/acceso, forzar nueva búsqueda.
  useEffect(() => {
    lastFetchRef.current = null
  }, [minKw, maxKw, radiusM, adHocOnly, excludeParking])

  const fetchFor = useCallback(
    async (lat: number, lon: number, force = false) => {
      const prev = lastFetchRef.current
      if (
        !force &&
        prev &&
        haversineM(prev, { lat, lon }) < MOVE_THRESHOLD_M &&
        Date.now() - prev.at < MIN_REFETCH_MS
      ) {
        return
      }

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      setStatus((prevStatus) => (prevStatus === 'ready' || prevStatus === 'empty' ? prevStatus : 'loading'))
      setError(null)

      try {
        const payload = await fetchNearestLive(
          {
            lat,
            lon,
            // "Todo" → 0 explícito para no caer en el default 100 del API
            minKw: minKw === undefined ? 0 : minKw,
            maxKw,
            radiusM,
            publicOpenOnly: true,
            adHocOnly,
            excludeParking,
          },
          { signal: controller.signal },
        )
        if (controller.signal.aborted) {
          return
        }
        lastFetchRef.current = { lat, lon, at: Date.now() }
        setResult(payload)
        setStatus(payload.station ? 'ready' : 'empty')
      } catch (err) {
        if (controller.signal.aborted) {
          return
        }
        const message = err instanceof Error ? err.message : 'No se pudo buscar el cargador cercano'
        setError(message)
        setStatus('error')
      }
    },
    [minKw, maxKw, radiusM, adHocOnly, excludeParking],
  )

  useEffect(() => {
    if (!active) {
      clear()
      return
    }
    if (gpsStatus === 'unsupported' || gpsStatus === 'error') {
      setStatus('error')
      setError(gpsError ?? 'GPS no disponible')
      return
    }
    if (!location) {
      setStatus('locating')
      return
    }
    void fetchFor(location.lat, location.lon)
  }, [active, clear, fetchFor, gpsError, gpsStatus, location])

  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  return {
    location,
    result,
    station: result?.station ?? null,
    distanceKm: result?.distance_km ?? null,
    distanceM: result?.distance_m ?? null,
    usedMinKw: result?.used_min_kw ?? null,
    status,
    error: error ?? (active ? gpsError : null),
    refresh: () => {
      if (location) {
        void fetchFor(location.lat, location.lon, true)
      } else {
        refreshGps()
      }
    },
  }
}
