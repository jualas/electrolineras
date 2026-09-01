import { useMemo } from 'react'

import { useDeviceLocation } from './useDeviceLocation'
import { useActiveTrip } from './useActiveTrip'
import { TELEMETRY_POLL_INTERVAL_MS, useVehicleTelemetry } from './useVehicleTelemetry'

export type ActiveTripMapLocation = {
  lat: number
  lon: number
  accuracyM: number | null
  label: string
  source: 'gps' | 'car'
}

/**
 * Posición en mapa durante viaje activo: GPS móvil o TeslaMate según originMode del viaje.
 */
export function useActiveTripMapLocation() {
  const { activeTrip, enMarchaSettings } = useActiveTrip()
  const trackingActive = Boolean(activeTrip)

  const useGps =
    trackingActive &&
    activeTrip?.originMode === 'gps' &&
    enMarchaSettings.gpsEnabled
  const useCar = trackingActive && activeTrip?.originMode === 'car'

  const {
    location: gpsLocation,
    status: gpsStatus,
    isGpsActive,
  } = useDeviceLocation({
    autoStart: useGps,
    watch: useGps,
  })

  const { vehicle: carTelemetry } = useVehicleTelemetry({
    enabled: useCar,
    pollIntervalMs: TELEMETRY_POLL_INTERVAL_MS,
    syncSoc: false,
  })

  const location = useMemo((): ActiveTripMapLocation | null => {
    if (!trackingActive) {
      return null
    }
    if (useCar && carTelemetry) {
      return {
        lat: carTelemetry.lat,
        lon: carTelemetry.lon,
        accuracyM: null,
        label: carTelemetry.display_name?.trim() || 'Ubicación del vehículo',
        source: 'car',
      }
    }
    if (useGps && gpsLocation) {
      return {
        lat: gpsLocation.lat,
        lon: gpsLocation.lon,
        accuracyM: gpsLocation.accuracyM,
        label: gpsLocation.label,
        source: 'gps',
      }
    }
    return null
  }, [trackingActive, useCar, carTelemetry, useGps, gpsLocation])

  return {
    activeTrip,
    trackingActive,
    location,
    gpsStatus: useGps ? gpsStatus : 'idle',
    isGpsActive: useGps && isGpsActive,
    centerOnMe: enMarchaSettings.centerOnMe,
  }
}
