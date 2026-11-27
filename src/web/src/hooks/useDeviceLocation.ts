import { Capacitor } from '@capacitor/core'
import { Geolocation } from '@capacitor/geolocation'
import { useCallback, useEffect, useRef, useState } from 'react'

export type DeviceLocationSource = 'gps' | 'manual'

export type DeviceLocationSnapshot = {
  lat: number
  lon: number
  accuracyM: number | null
  label: string
  source: DeviceLocationSource
  updatedAt: number
}

export type DeviceLocationStatus = 'idle' | 'loading' | 'active' | 'error' | 'unsupported'

type UseDeviceLocationOptions = {
  /** Solicitar posición al montar (modo conducción / Android Auto). */
  autoStart?: boolean
  /** Seguimiento continuo con watchPosition mientras el panel está activo. */
  watch?: boolean
  /** Etiqueta cuando el origen es GPS del dispositivo. */
  gpsLabel?: string
}

type UseDeviceLocationResult = {
  location: DeviceLocationSnapshot | null
  status: DeviceLocationStatus
  error: string | null
  isGpsActive: boolean
  refreshGps: () => void
  setManualLocation: (point: { lat: number; lon: number; label: string }) => void
  clearManualOverride: () => void
}

const DEFAULT_GPS_LABEL = 'Mi ubicación (GPS)'

function formatGpsLabel(base: string, accuracyM: number | null): string {
  if (accuracyM == null || !Number.isFinite(accuracyM)) {
    return base
  }
  if (accuracyM < 1000) {
    return `${base} · ±${Math.round(accuracyM)} m`
  }
  return `${base} · ±${(accuracyM / 1000).toFixed(1)} km`
}

export function useDeviceLocation(options: UseDeviceLocationOptions = {}): UseDeviceLocationResult {
  const { autoStart = false, watch = false, gpsLabel = DEFAULT_GPS_LABEL } = options
  const [location, setLocation] = useState<DeviceLocationSnapshot | null>(null)
  const [status, setStatus] = useState<DeviceLocationStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const manualOverrideRef = useRef(false)
  const watchIdRef = useRef<string | number | null>(null)
  const native = Capacitor.isNativePlatform()

  const applyGpsCoords = useCallback(
    (lat: number, lon: number, accuracy: number | null, timestamp: number) => {
      if (manualOverrideRef.current) {
        return
      }
      const label = formatGpsLabel(gpsLabel, accuracy)
      setLocation({
        lat,
        lon,
        accuracyM: accuracy,
        label,
        source: 'gps',
        updatedAt: timestamp,
      })
      setStatus('active')
      setError(null)
    },
    [gpsLabel],
  )

  const handleErrorText = useCallback((message: string) => {
    setError(message)
    setStatus('error')
  }, [])

  const handleBrowserGpsError = useCallback(
    (geoError: GeolocationPositionError) => {
      const message =
        geoError.code === geoError.PERMISSION_DENIED
          ? 'Permiso de ubicación denegado. Actívalo en el teléfono (Android Auto usa el GPS del móvil).'
          : geoError.code === geoError.TIMEOUT
            ? 'Tiempo agotado al obtener GPS. Reintenta en zona con mejor señal.'
            : 'No se pudo obtener la ubicación GPS'
      handleErrorText(message)
    },
    [handleErrorText],
  )

  const stopWatch = useCallback(() => {
    const id = watchIdRef.current
    if (id == null) {
      return
    }
    watchIdRef.current = null
    if (native && typeof id === 'string') {
      void Geolocation.clearWatch({ id })
    } else if (typeof id === 'number' && typeof navigator !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.clearWatch(id)
    }
  }, [native])

  const startWatch = useCallback(() => {
    stopWatch()
    setStatus('loading')
    setError(null)

    if (native) {
      void (async () => {
        try {
          const perm = await Geolocation.requestPermissions()
          if (perm.location === 'denied') {
            handleErrorText('Permiso de ubicación denegado. Actívalo en Ajustes.')
            return
          }
          const id = await Geolocation.watchPosition(
            { enableHighAccuracy: true, timeout: 20_000 },
            (position, err) => {
              if (err || !position) {
                handleErrorText(err?.message ?? 'No se pudo obtener GPS')
                return
              }
              applyGpsCoords(
                position.coords.latitude,
                position.coords.longitude,
                position.coords.accuracy ?? null,
                position.timestamp,
              )
            },
          )
          watchIdRef.current = id
        } catch (err) {
          handleErrorText(err instanceof Error ? err.message : 'GPS no disponible')
        }
      })()
      return
    }

    if (!navigator.geolocation) {
      setStatus('unsupported')
      setError('Geolocalización no disponible en este navegador')
      return
    }
    watchIdRef.current = navigator.geolocation.watchPosition(
      (position) =>
        applyGpsCoords(
          position.coords.latitude,
          position.coords.longitude,
          position.coords.accuracy,
          position.timestamp,
        ),
      handleBrowserGpsError,
      {
        enableHighAccuracy: true,
        maximumAge: 15_000,
        timeout: 20_000,
      },
    )
  }, [applyGpsCoords, handleBrowserGpsError, handleErrorText, native, stopWatch])

  const refreshGps = useCallback(() => {
    manualOverrideRef.current = false
    setStatus('loading')
    setError(null)

    if (native) {
      void (async () => {
        try {
          const perm = await Geolocation.requestPermissions()
          if (perm.location === 'denied') {
            handleErrorText('Permiso de ubicación denegado. Actívalo en Ajustes.')
            return
          }
          const position = await Geolocation.getCurrentPosition({
            enableHighAccuracy: true,
            timeout: 20_000,
          })
          applyGpsCoords(
            position.coords.latitude,
            position.coords.longitude,
            position.coords.accuracy ?? null,
            position.timestamp,
          )
          if (watch) {
            startWatch()
          }
        } catch (err) {
          handleErrorText(err instanceof Error ? err.message : 'GPS no disponible')
        }
      })()
      return
    }

    if (!navigator.geolocation) {
      setStatus('unsupported')
      setError('Geolocalización no disponible en este navegador')
      return
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        applyGpsCoords(
          position.coords.latitude,
          position.coords.longitude,
          position.coords.accuracy,
          position.timestamp,
        )
        if (watch) {
          startWatch()
        }
      },
      handleBrowserGpsError,
      { enableHighAccuracy: true, maximumAge: 0, timeout: 20_000 },
    )
  }, [applyGpsCoords, handleBrowserGpsError, handleErrorText, native, startWatch, watch])

  const setManualLocation = useCallback(
    (point: { lat: number; lon: number; label: string }) => {
      manualOverrideRef.current = true
      stopWatch()
      setLocation({
        lat: point.lat,
        lon: point.lon,
        accuracyM: null,
        label: point.label,
        source: 'manual',
        updatedAt: Date.now(),
      })
      setStatus('active')
      setError(null)
    },
    [stopWatch],
  )

  const clearManualOverride = useCallback(() => {
    manualOverrideRef.current = false
    refreshGps()
  }, [refreshGps])

  useEffect(() => {
    if (!autoStart) {
      stopWatch()
      return undefined
    }
    if (watch) {
      startWatch()
    } else {
      refreshGps()
    }
    return () => {
      stopWatch()
    }
  }, [autoStart, watch, refreshGps, startWatch, stopWatch])

  return {
    location,
    status,
    error,
    isGpsActive: location?.source === 'gps' && status === 'active',
    refreshGps,
    setManualLocation,
    clearManualOverride,
  }
}
