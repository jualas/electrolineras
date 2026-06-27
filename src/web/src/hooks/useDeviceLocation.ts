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
  const watchIdRef = useRef<number | null>(null)

  const applyGpsPosition = useCallback(
    (position: GeolocationPosition) => {
      if (manualOverrideRef.current) {
        return
      }
      const label = formatGpsLabel(gpsLabel, position.coords.accuracy)
      setLocation({
        lat: position.coords.latitude,
        lon: position.coords.longitude,
        accuracyM: position.coords.accuracy,
        label,
        source: 'gps',
        updatedAt: position.timestamp,
      })
      setStatus('active')
      setError(null)
    },
    [gpsLabel],
  )

  const handleGpsError = useCallback((geoError: GeolocationPositionError) => {
    const message =
      geoError.code === geoError.PERMISSION_DENIED
        ? 'Permiso de ubicación denegado. Actívalo en el teléfono (Android Auto usa el GPS del móvil).'
        : geoError.code === geoError.TIMEOUT
          ? 'Tiempo agotado al obtener GPS. Reintenta en zona con mejor señal.'
          : 'No se pudo obtener la ubicación GPS'
    setError(message)
    setStatus('error')
  }, [])

  const stopWatch = useCallback(() => {
    if (watchIdRef.current != null) {
      navigator.geolocation.clearWatch(watchIdRef.current)
      watchIdRef.current = null
    }
  }, [])

  const startWatch = useCallback(() => {
    if (!navigator.geolocation) {
      setStatus('unsupported')
      setError('Geolocalización no disponible en este navegador')
      return
    }
    stopWatch()
    setStatus('loading')
    setError(null)
    watchIdRef.current = navigator.geolocation.watchPosition(applyGpsPosition, handleGpsError, {
      enableHighAccuracy: true,
      maximumAge: 15_000,
      timeout: 20_000,
    })
  }, [applyGpsPosition, handleGpsError, stopWatch])

  const refreshGps = useCallback(() => {
    if (!navigator.geolocation) {
      setStatus('unsupported')
      setError('Geolocalización no disponible en este navegador')
      return
    }
    manualOverrideRef.current = false
    setStatus('loading')
    setError(null)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        applyGpsPosition(position)
        if (watch) {
          startWatch()
        }
      },
      handleGpsError,
      { enableHighAccuracy: true, maximumAge: 0, timeout: 20_000 },
    )
  }, [applyGpsPosition, handleGpsError, startWatch, watch])

  const setManualLocation = useCallback((point: { lat: number; lon: number; label: string }) => {
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
  }, [stopWatch])

  const clearManualOverride = useCallback(() => {
    manualOverrideRef.current = false
    refreshGps()
  }, [refreshGps])

  useEffect(() => {
    if (!autoStart) {
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
