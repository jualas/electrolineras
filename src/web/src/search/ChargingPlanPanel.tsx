import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { fetchChargingPlan } from '../api/chargingPlan'
import type { ChargingPlanResponse, GeocodeResult, Station } from '../api/types'
import { geocodePlace } from '../api/route'
import { VehicleTelemetryStrip } from '../components/vehicle/VehicleTelemetryStrip'
import type { VehiclePresetId } from '../vehicle/vehiclePresets'
import { getTerrainFactor } from '../vehicle/vehiclePresets'
import { VehicleProfilePanel } from '../components/vehicle/VehicleProfilePanel'
import { VehicleProfileFields } from '../components/vehicle/VehicleProfileFields'
import { useDeviceLocation } from '../hooks/useDeviceLocation'
import { TELEMETRY_POLL_INTERVAL_MS, useVehicleTelemetry } from '../hooks/useVehicleTelemetry'
import { LoginPanel } from '../auth/LoginPanel'
import type { VehicleProfile } from '../vehicle/vehicleProfile'
import { vehicleProfileToChargingPlanQuery } from '../vehicle/vehicleProfile'
import {
  carOriginFromTelemetry,
  telemetryToChargingPlanQuery,
} from '../vehicle/telemetryProfile'
import { RoutePreferenceFields } from './RoutePreferenceFields'
import { HOME_LOCATION } from './homeLocation'
import {
  ItineraryFields,
  createEmptyStop,
  type ItineraryPoint,
  type ItineraryStopDraft,
} from './ItineraryFields'
import { revePlanningForPreset, type RevePlanningOptions } from './RevePlanningFields'
import { DEFAULT_CHARGING_PREFERENCES } from '../charging/chargingPreferences'
import { buildPlanSearchKey } from '../charging/planSearchKey'
import { clampTripProgress } from '../charging/activeTrip'
import { routeChargingStops } from '../charging/planRouteStops'
import {
  isOriginOnlySearchKeyChange,
  shouldThrottleAutoReplan,
  type AutoReplanSnapshot,
} from '../charging/replanThrottle'
import { distancePointToRouteKm } from '../charging/routeDeviation'
import { useActiveTrip } from '../hooks/useActiveTrip'
import { ActiveTripBanner } from '../components/trip/ActiveTripBanner'
import { ActiveTripProgressBar } from '../components/trip/ActiveTripProgressBar'
import { ChargingPlanResults } from './ChargingPlanResults'
import { ReplanOnRouteBar } from './ReplanOnRouteBar'
import type { RoutePreference } from '../api/types'

type SearchStatus = 'idle' | 'loading' | 'ready' | 'error'
type OriginMode = 'car' | 'gps' | 'simulation'

type ChargingPlanPanelProps = {
  vehicleProfile: VehicleProfile
  onVehiclePresetChange: (presetId: VehiclePresetId) => void
  onVehicleSocChange: (socPercent: number) => void
  onVehicleConsumptionChange: (consumptionWhPerKm: number) => void
  minKw?: number
  maxKw?: number
  onResults: (response: ChargingPlanResponse | null) => void
  onSelectStation?: (station: Station | null) => void
  onSearchStateChange?: (status: SearchStatus) => void
  selectedStationId?: string | null
}

export function ChargingPlanPanel({
  vehicleProfile,
  onVehiclePresetChange,
  onVehicleSocChange,
  onVehicleConsumptionChange,
  minKw,
  maxKw,
  onResults,
  onSelectStation,
  onSearchStateChange,
  selectedStationId,
}: ChargingPlanPanelProps) {
  const [originMode, setOriginMode] = useState<OriginMode>('simulation')
  const originModeTouchedRef = useRef(false)
  const [stops, setStops] = useState<ItineraryStopDraft[]>(() => [createEmptyStop()])
  const [emergencyMode, setEmergencyMode] = useState(false)
  const [corridorKm, setCorridorKm] = useState(10)
  const [routePreference, setRoutePreference] = useState<RoutePreference>('shortest')
  const [avoidTolls, setAvoidTolls] = useState(true)
  const [revePlanning, setRevePlanning] = useState<RevePlanningOptions>(() =>
    revePlanningForPreset(vehicleProfile.presetId),
  )
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastResponse, setLastResponse] = useState<ChargingPlanResponse | null>(null)
  const [manualOriginText, setManualOriginText] = useState(HOME_LOCATION.label)
  const [manualOriginPoint, setManualOriginPoint] = useState<{ label: string; lat: number; lon: number } | null>(
    HOME_LOCATION,
  )
  const lastSearchKeyRef = useRef<string | null>(null)
  const lastAutoReplanRef = useRef<AutoReplanSnapshot | null>(null)
  const recalcOnPreferenceRef = useRef(false)
  const tripRestoredRef = useRef(false)
  const { activeTrip, enMarchaSettings, saveActiveTrip, clearActiveTrip, setAutoFollow, setGpsEnabled, markStopCompleted } =
    useActiveTrip()

  const {
    vehicle: carTelemetry,
    loading: carTelemetryLoading,
    error: carTelemetryError,
    refresh: refreshCarTelemetry,
    available: carTelemetryAvailable,
    authenticated,
    privateStackEnabled,
    loginEnabled,
    authLoading,
  } = useVehicleTelemetry({
    syncSoc: true,
    currentSocPercent: vehicleProfile.socPercent,
    onSocChange: onVehicleSocChange,
    pollIntervalMs: TELEMETRY_POLL_INTERVAL_MS,
  })

  const simulationMode = originMode === 'simulation'
  const useCarOrigin = originMode === 'car' && carTelemetryAvailable

  useEffect(() => {
    setRevePlanning((prev) => ({
      ...prev,
      maxChargePowerKw: revePlanningForPreset(vehicleProfile.presetId).maxChargePowerKw,
    }))
  }, [vehicleProfile.presetId])

  useEffect(() => {
    if (!carTelemetryAvailable || originModeTouchedRef.current) {
      return
    }
    setOriginMode('car')
  }, [carTelemetryAvailable])

  useEffect(() => {
    if (tripRestoredRef.current || !activeTrip) {
      return
    }
    const hasDestination = stops.some((stop) => stop.point != null || stop.text.trim().length > 0)
    if (hasDestination) {
      return
    }
    tripRestoredRef.current = true
    const viaStops = activeTrip.waypoints.map((waypoint) => ({
      id: createEmptyStop().id,
      text: waypoint.label,
      point: {
        label: waypoint.label,
        lat: waypoint.lat,
        lon: waypoint.lon,
      },
    }))
    setStops([
      ...viaStops,
      {
        id: createEmptyStop().id,
        text: activeTrip.destination.label,
        point: {
          label: activeTrip.destination.label,
          lat: activeTrip.destination.lat,
          lon: activeTrip.destination.lon,
        },
      },
    ])
    setCorridorKm(activeTrip.corridorKm)
    setRoutePreference(activeTrip.routePreference)
    setAvoidTolls(activeTrip.avoidTolls)
    if (carTelemetryAvailable && activeTrip.originMode === 'car') {
      setOriginMode('car')
    } else if (enMarchaSettings.gpsEnabled) {
      setOriginMode('gps')
    } else if (activeTrip.originMode === 'gps') {
      setOriginMode('gps')
    }
  }, [activeTrip, carTelemetryAvailable, enMarchaSettings.gpsEnabled, stops])

  useEffect(() => {
    onSearchStateChange?.(status)
  }, [status, onSearchStateChange])

  const {
    location: gpsLocation,
    status: gpsStatus,
    error: gpsError,
    isGpsActive,
    refreshGps,
    setManualLocation,
    clearManualOverride,
  } = useDeviceLocation({ autoStart: originMode === 'gps', watch: originMode === 'gps' })

  const resolveVehicleQuery = useCallback(() => {
    const terrain = getTerrainFactor(vehicleProfile.terrainFactorId)
    if (carTelemetryAvailable && carTelemetry) {
      return telemetryToChargingPlanQuery(
        carTelemetry,
        terrain.factor,
        undefined,
        undefined,
        vehicleProfile.presetId,
      )
    }
    return vehicleProfileToChargingPlanQuery(vehicleProfile)
  }, [carTelemetry, carTelemetryAvailable, vehicleProfile])

  const resolveSimulationOrigin = useCallback(async () => {
    if (manualOriginPoint) {
      return manualOriginPoint
    }
    const trimmed = manualOriginText.trim()
    if (!trimmed) {
      throw new Error('Indica origen en modo simulación')
    }
    const geocoded = await geocodePlace(trimmed)
    const point = { label: geocoded.label, lat: geocoded.lat, lon: geocoded.lon }
    setManualOriginPoint(point)
    setManualOriginText(geocoded.label)
    setManualLocation(point)
    return point
  }, [manualOriginPoint, manualOriginText, setManualLocation])

  const destinationPoint = stops[stops.length - 1]?.point ?? null

  const resolveStops = useCallback(async (): Promise<ItineraryPoint[]> => {
    const resolved: ItineraryPoint[] = []
    const nextStops = [...stops]
    for (let index = 0; index < nextStops.length; index += 1) {
      const stop = nextStops[index]
      if (stop.point) {
        resolved.push(stop.point)
        continue
      }
      const trimmed = stop.text.trim()
      if (!trimmed) {
        if (index === nextStops.length - 1) {
          throw new Error('Indica al menos un destino')
        }
        continue
      }
      const geocoded = await geocodePlace(trimmed)
      const point = { label: geocoded.label, lat: geocoded.lat, lon: geocoded.lon }
      nextStops[index] = { ...stop, text: geocoded.label, point }
      resolved.push(point)
    }
    setStops(nextStops)
    if (resolved.length === 0) {
      throw new Error('Indica destino o activa modo emergencia')
    }
    return resolved
  }, [stops])

  const runPlan = useCallback(async () => {
    setStatus('loading')
    setError(null)
    onSelectStation?.(null)

    try {
      let origin: { lat: number; lon: number; label: string; source?: string }
      if (useCarOrigin && carTelemetry) {
        origin = carOriginFromTelemetry(carTelemetry)
      } else if (simulationMode) {
        const resolved = await resolveSimulationOrigin()
        origin = resolved
      } else {
        if (!gpsLocation) {
          throw new Error('Esperando GPS del teléfono o indica origen manual')
        }
        origin = gpsLocation
      }

      let destination: ItineraryPoint | null = null
      let viaPoints: ItineraryPoint[] = []
      if (!emergencyMode) {
        const resolvedStops = await resolveStops()
        destination = resolvedStops[resolvedStops.length - 1] ?? null
        viaPoints = resolvedStops.slice(0, -1)
      }

      if (!emergencyMode && !destination) {
        throw new Error('Indica destino o activa modo emergencia')
      }

      const vehicleQuery = resolveVehicleQuery()
      const response = await fetchChargingPlan({
        originLat: origin.lat,
        originLon: origin.lon,
        destLat: emergencyMode ? undefined : destination!.lat,
        destLon: emergencyMode ? undefined : destination!.lon,
        viaPoints: emergencyMode
          ? undefined
          : viaPoints.map((point) => ({ lat: point.lat, lon: point.lon })),
        socPercent: vehicleQuery.soc_percent,
        usableCapacityKwh: vehicleQuery.usable_capacity_kwh,
        consumptionWhPerKm: vehicleQuery.consumption_wh_per_km,
        terrainFactor: vehicleQuery.terrain_factor,
        reserveSocPercent: vehicleQuery.reserve_soc_percent,
        minKw,
        maxKw,
        corridorKm: emergencyMode ? undefined : corridorKm,
        limit: 15,
        routePreference: emergencyMode ? undefined : routePreference,
        avoidHighways: emergencyMode ? undefined : avoidTolls,
        vehiclePresetId: vehicleQuery.vehicle_preset_id,
        preferredOperators: DEFAULT_CHARGING_PREFERENCES.preferredOperators,
        maxPriceEurKwh: DEFAULT_CHARGING_PREFERENCES.maxPriceEurKwh,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
        consumptionKwhPer100km: revePlanning.consumptionKwhPer100km,
      })

      const searchKey = buildPlanSearchKey({
        originMode,
        origin,
        dest: emergencyMode ? null : destination!,
        vehicleQuery,
        minKw,
        maxKw,
        corridorKm,
        emergencyMode,
        routePreference,
        avoidTolls,
        chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
      })
      lastSearchKeyRef.current = searchKey
      lastAutoReplanRef.current = {
        at: Date.now(),
        lat: origin.lat,
        lon: origin.lon,
        soc: vehicleQuery.soc_percent,
      }
      setLastResponse(response)
      setStatus('ready')
      onResults(response)
      if (!emergencyMode && destination) {
        const chargingStops = routeChargingStops(response)
        const progress = clampTripProgress(
          activeTrip?.progress ?? { completedStopOrders: [], currentLegIndex: 0 },
          chargingStops.length,
        )
        saveActiveTrip({
          version: 2,
          destination: {
            label: destination.label,
            lat: destination.lat,
            lon: destination.lon,
          },
          waypoints: viaPoints.map((point) => ({
            label: point.label,
            lat: point.lat,
            lon: point.lon,
          })),
          lastPlan: {
            stopIds: (response.planned_stops ?? []).map((stop) => stop.station.id),
            routeDistanceKm: response.route_distance_km,
            computedAt: Date.now(),
          },
          progress,
          corridorKm,
          routePreference,
          avoidTolls,
          chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
          originMode,
          updatedAt: Date.now(),
        })
      } else if (emergencyMode) {
        clearActiveTrip()
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al calcular el plan'
      setError(message)
      setStatus('error')
      setLastResponse(null)
      onResults(null)
    }
  }, [
    carTelemetry,
    corridorKm,
    emergencyMode,
    routePreference,
    avoidTolls,
    gpsLocation,
    maxKw,
    minKw,
    onResults,
    onSelectStation,
    resolveSimulationOrigin,
    resolveStops,
    resolveVehicleQuery,
    simulationMode,
    originMode,
    clearActiveTrip,
    saveActiveTrip,
    useCarOrigin,
    activeTrip,
    revePlanning,
  ])

  useEffect(() => {
    if (originMode !== 'gps' || !enMarchaSettings.autoFollow) {
      return
    }
    if (gpsStatus !== 'active' || !gpsLocation) {
      return
    }
    if (status === 'loading') {
      return
    }
    if (!lastSearchKeyRef.current) {
      return
    }
    if (!emergencyMode && !destinationPoint) {
      return
    }
    const vehicleQuery = resolveVehicleQuery()
    const searchKey = buildPlanSearchKey({
      originMode,
      origin: gpsLocation,
      dest: emergencyMode ? null : destinationPoint,
      vehicleQuery,
      minKw,
      maxKw,
      corridorKm,
      emergencyMode,
      routePreference,
      avoidTolls,
      chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
    })
    if (searchKey === lastSearchKeyRef.current) {
      return
    }
    if (
      isOriginOnlySearchKeyChange(lastSearchKeyRef.current, searchKey) &&
      shouldThrottleAutoReplan({
        last: lastAutoReplanRef.current,
        origin: gpsLocation,
        soc: vehicleQuery.soc_percent,
      })
    ) {
      return
    }
    void runPlan()
  }, [
    avoidTolls,
    corridorKm,
    destinationPoint,
    emergencyMode,
    enMarchaSettings.autoFollow,
    gpsLocation,
    gpsStatus,
    minKw,
    maxKw,
    originMode,
    resolveVehicleQuery,
    routePreference,
    runPlan,
    status,
  ])

  useEffect(() => {
    if (!useCarOrigin || !carTelemetry || !enMarchaSettings.autoFollow) {
      return
    }
    if (status === 'loading') {
      return
    }
    if (!lastSearchKeyRef.current) {
      return
    }
    if (!emergencyMode && !destinationPoint) {
      return
    }
    const origin = carOriginFromTelemetry(carTelemetry)
    const vehicleQuery = resolveVehicleQuery()
    const searchKey = buildPlanSearchKey({
      originMode,
      origin,
      dest: emergencyMode ? null : destinationPoint,
      vehicleQuery,
      minKw,
      maxKw,
      corridorKm,
      emergencyMode,
      routePreference,
      avoidTolls,
      chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
    })
    if (searchKey === lastSearchKeyRef.current) {
      return
    }
    if (
      isOriginOnlySearchKeyChange(lastSearchKeyRef.current, searchKey) &&
      shouldThrottleAutoReplan({
        last: lastAutoReplanRef.current,
        origin,
        soc: vehicleQuery.soc_percent,
      })
    ) {
      return
    }
    void runPlan()
  }, [
    avoidTolls,
    carTelemetry,
    corridorKm,
    destinationPoint,
    emergencyMode,
    enMarchaSettings.autoFollow,
    maxKw,
    minKw,
    originMode,
    resolveVehicleQuery,
    routePreference,
    runPlan,
    status,
    useCarOrigin,
  ])

  useEffect(() => {
    if (!recalcOnPreferenceRef.current || emergencyMode) {
      return
    }
    if (status === 'loading') {
      return
    }
    recalcOnPreferenceRef.current = false
    void runPlan()
  }, [routePreference, avoidTolls, revePlanning, emergencyMode, runPlan, status])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    void runPlan()
  }

  const handleManualOriginSelect = (place: GeocodeResult) => {
    const point = { label: place.label, lat: place.lat, lon: place.lon }
    setManualOriginText(place.label)
    setManualOriginPoint(point)
    setManualLocation(point)
    lastSearchKeyRef.current = null
  }

  const handleManualOriginChange = (value: string) => {
    setManualOriginText(value)
    setManualOriginPoint(null)
    lastSearchKeyRef.current = null
  }

  const handleStopChange = (id: string, text: string) => {
    setStops((prev) => prev.map((stop) => (stop.id === id ? { ...stop, text, point: null } : stop)))
    lastSearchKeyRef.current = null
  }

  const handleStopSelect = (id: string, place: GeocodeResult) => {
    setStops((prev) =>
      prev.map((stop) =>
        stop.id === id
          ? {
              ...stop,
              text: place.label,
              point: { label: place.label, lat: place.lat, lon: place.lon },
            }
          : stop,
      ),
    )
    lastSearchKeyRef.current = null
  }

  const handleAddStop = () => {
    setStops((prev) => [...prev, createEmptyStop()])
    lastSearchKeyRef.current = null
  }

  const handleRemoveStop = (id: string) => {
    setStops((prev) => {
      if (prev.length <= 1) {
        return prev
      }
      return prev.filter((stop) => stop.id !== id)
    })
    lastSearchKeyRef.current = null
  }

  const vehicleOriginPoint =
    carTelemetryAvailable && carTelemetry ? carOriginFromTelemetry(carTelemetry) : null
  const gpsOriginPoint = gpsLocation
    ? { label: gpsLocation.label, lat: gpsLocation.lat, lon: gpsLocation.lon }
    : null
  const itineraryOriginSource = useCarOrigin ? 'car' : simulationMode ? 'manual' : 'gps'
  const itineraryOriginPoint = useCarOrigin
    ? vehicleOriginPoint
    : simulationMode
      ? manualOriginPoint
      : gpsOriginPoint

  const originLabel = useCarOrigin && carTelemetry
    ? carOriginFromTelemetry(carTelemetry).label
    : simulationMode
      ? manualOriginPoint?.label ?? (manualOriginText.trim() || 'Indica origen')
      : (gpsLocation?.label ?? (gpsStatus === 'loading' ? 'Obteniendo GPS…' : 'Sin ubicación'))
  const showGpsBanner = originMode === 'gps' && (isGpsActive || gpsStatus === 'loading')
  const hasDestinationInput = stops.some((stop) => stop.point != null || stop.text.trim().length > 0)
  const canSubmit =
    (useCarOrigin && carTelemetry
      ? true
      : simulationMode
        ? manualOriginText.trim().length > 0
        : Boolean(gpsLocation)) &&
    (emergencyMode || hasDestinationInput)
  const telemetrySocLocked = carTelemetryAvailable
  const liveOriginMode = useCarOrigin || originMode === 'gps'
  const replanDestination = destinationPoint ?? activeTrip?.destination ?? null
  const showReplanBar =
    !emergencyMode && Boolean(replanDestination) && Boolean(lastResponse) && liveOriginMode
  const resolveVehicleQueryForDisplay = resolveVehicleQuery()
  const chargingStopCount = lastResponse ? routeChargingStops(lastResponse).length : 0
  const liveTrackingPoint = useCarOrigin && carTelemetry
    ? { lat: carTelemetry.lat, lon: carTelemetry.lon }
    : gpsLocation
      ? { lat: gpsLocation.lat, lon: gpsLocation.lon }
      : null
  const routeDeviationKm = useMemo(() => {
    if (!lastResponse?.route_geometry || !liveTrackingPoint) {
      return null
    }
    return distancePointToRouteKm(liveTrackingPoint, lastResponse.route_geometry)
  }, [lastResponse, liveTrackingPoint])

  const handleGpsEnabledChange = (enabled: boolean) => {
    setGpsEnabled(enabled)
    originModeTouchedRef.current = true
    if (enabled) {
      setOriginMode('gps')
      lastSearchKeyRef.current = null
    } else if (!useCarOrigin) {
      setOriginMode('simulation')
    }
  }

  const handleMarkStopCompleted = (stopOrder: number) => {
    if (!lastResponse) {
      return
    }
    markStopCompleted(stopOrder, routeChargingStops(lastResponse).length)
  }
  const viaLabels = stops
    .slice(0, -1)
    .map((stop) => stop.point?.label ?? stop.text.trim())
    .filter(Boolean)

  return (
    <section className="panel search-panel charge-panel" aria-labelledby="charge-plan-heading">
      <h2 id="charge-plan-heading">Plan de carga</h2>

      {activeTrip && !emergencyMode ? (
        <ActiveTripBanner
          destinationLabel={activeTrip.destination.label}
          waypointCount={activeTrip.waypoints.length}
          gpsEnabled={enMarchaSettings.gpsEnabled}
          gpsActive={isGpsActive}
          gpsLoading={gpsStatus === 'loading'}
          showGpsToggle={!useCarOrigin}
          onGpsEnabledChange={handleGpsEnabledChange}
          onEndTrip={clearActiveTrip}
        />
      ) : null}

      {privateStackEnabled && loginEnabled && !authLoading && !authenticated && (
        <details className="telemetry-login">
          <summary>SOC en vivo desde TeslaMate (requiere sesión)</summary>
          <p className="panel-hint">
            Tras iniciar sesión, el planificador usará SOC y posición del coche vía MQTT sin entrada manual.
          </p>
          <LoginPanel />
        </details>
      )}

      <VehicleProfilePanel
        className="charge-panel__vehicle"
        variant="compact"
        profile={vehicleProfile}
        onPresetChange={onVehiclePresetChange}
        onSocChange={onVehicleSocChange}
        onConsumptionChange={onVehicleConsumptionChange}
        socReadOnly={telemetrySocLocked}
        socSourceLabel={telemetrySocLocked ? 'TeslaMate en vivo' : undefined}
      />

      {privateStackEnabled && authenticated && (
        <VehicleTelemetryStrip
          vehicle={carTelemetry}
          loading={carTelemetryLoading}
          error={carTelemetryError}
          onRefresh={() => void refreshCarTelemetry()}
          compact
        />
      )}

      {!carTelemetryAvailable && (
        <details className="vehicle-advanced">
          <summary>Consumo (avanzado)</summary>
          <div className="vehicle-advanced__body">
            <VehicleProfileFields
              profile={vehicleProfile}
              onPresetChange={onVehiclePresetChange}
              onSocChange={onVehicleSocChange}
              onConsumptionChange={onVehicleConsumptionChange}
              variant="advanced"
            />
          </div>
        </details>
      )}

      <p className="panel-hint charge-panel__hint">
        {useCarOrigin
          ? 'Origen y SOC desde TeslaMate. El plan se recalcula al cambiar batería o posición.'
          : simulationMode
            ? carTelemetryAvailable
              ? 'Simulación manual. Puedes usar origen del coche arriba; el SOC sigue sincronizado con TeslaMate.'
              : 'Simula un viaje: origen y destino manuales, SOC y estrategias sin GPS en vivo.'
            : 'Origen: GPS del teléfono (Android Auto). Indica destino y pulsa calcular.'}
      </p>

      {showGpsBanner && (
        <div className={`gps-banner ${isGpsActive ? 'gps-banner--active' : 'gps-banner--loading'}`} role="status">
          <span className="gps-banner__dot" aria-hidden />
          {isGpsActive ? 'GPS activo' : 'Localizando…'}
          {gpsLocation?.accuracyM != null && isGpsActive && (
            <span className="gps-banner__accuracy">±{Math.round(gpsLocation.accuracyM)} m</span>
          )}
        </div>
      )}

      {(gpsError || (error && !gpsError)) && (
        <p className="route-message route-message--error" role="alert">
          {gpsError ?? error}
        </p>
      )}

      <form className="route-form" onSubmit={handleSubmit}>
        <ItineraryFields
          originText={manualOriginText}
          originPoint={itineraryOriginPoint}
          originAnchorLabel={HOME_LOCATION.label}
          vehicleOrigin={vehicleOriginPoint}
          gpsOrigin={gpsOriginPoint}
          originSource={itineraryOriginSource}
          onOriginChange={(value) => {
            originModeTouchedRef.current = true
            setOriginMode('simulation')
            handleManualOriginChange(value)
          }}
          onOriginSelect={(place) => {
            originModeTouchedRef.current = true
            setOriginMode('simulation')
            handleManualOriginSelect(place)
          }}
          onUseVehicleOrigin={
            carTelemetryAvailable
              ? () => {
                  originModeTouchedRef.current = true
                  setOriginMode('car')
                  lastSearchKeyRef.current = null
                  setStatus('idle')
                  setError(null)
                  setLastResponse(null)
                  onResults(null)
                }
              : undefined
          }
          onUseGpsOrigin={() => {
            originModeTouchedRef.current = true
            setOriginMode('gps')
            lastSearchKeyRef.current = null
            setStatus('idle')
            setError(null)
            setLastResponse(null)
            onResults(null)
          }}
          onUseHomeOrigin={() => {
            originModeTouchedRef.current = true
            setOriginMode('simulation')
            setManualOriginText(HOME_LOCATION.label)
            setManualOriginPoint(HOME_LOCATION)
            setManualLocation(HOME_LOCATION)
            lastSearchKeyRef.current = null
          }}
          onEditOriginManual={() => {
            originModeTouchedRef.current = true
            setOriginMode('simulation')
            const seed = itineraryOriginPoint?.label ?? ''
            setManualOriginText(seed)
            setManualOriginPoint(itineraryOriginPoint)
            lastSearchKeyRef.current = null
          }}
          stops={stops}
          onStopChange={handleStopChange}
          onStopSelect={handleStopSelect}
          onAddStop={handleAddStop}
          onRemoveStop={handleRemoveStop}
          disabled={status === 'loading'}
          hideDestination={emergencyMode}
        />

        {originMode === 'gps' && (
          <div className="charge-origin-actions">
            <button type="button" className="btn btn--secondary" onClick={refreshGps}>
              Actualizar GPS
            </button>
            {gpsLocation?.source === 'manual' && (
              <button type="button" className="btn btn--ghost" onClick={clearManualOverride}>
                Volver a GPS
              </button>
            )}
          </div>
        )}

        <label className="field field--checkbox">
          <input
            type="checkbox"
            checked={emergencyMode}
            onChange={(event) => {
              setEmergencyMode(event.target.checked)
              lastSearchKeyRef.current = null
            }}
          />
          <span>Solo emergencia (cargador más cercano, sin destino)</span>
        </label>

        {!emergencyMode && (
          <>
            {viaLabels.length > 0 && (
              <p className="panel-hint">
                Itinerario: {originLabel}
                {viaLabels.map((label) => ` → ${label}`).join('')}
                {` → ${stops[stops.length - 1]?.point?.label ?? (stops[stops.length - 1]?.text || 'destino')}`}
                . La ruta pasa por todas las paradas.
              </p>
            )}

            <label className="field">
              <span className="field__label">Corredor (km)</span>
              <select
                value={corridorKm}
                onChange={(event) => setCorridorKm(Number(event.target.value))}
              >
                <option value={5}>5 km</option>
                <option value={10}>10 km</option>
                <option value={15}>15 km</option>
                <option value={20}>20 km</option>
              </select>
            </label>

            <RoutePreferenceFields
              routePreference={routePreference}
              avoidTolls={avoidTolls}
              onRoutePreferenceChange={(value) => {
                setRoutePreference(value)
                if (status === 'ready' && lastResponse && !emergencyMode) {
                  recalcOnPreferenceRef.current = true
                } else {
                  lastSearchKeyRef.current = null
                }
              }}
              onAvoidTollsChange={(value) => {
                setAvoidTolls(value)
                if (status === 'ready' && lastResponse && !emergencyMode) {
                  recalcOnPreferenceRef.current = true
                } else {
                  lastSearchKeyRef.current = null
                }
              }}
              disabled={status === 'loading'}
            />
          </>
        )}

        <div className="route-form__actions">
          <button type="submit" className="btn btn--primary" disabled={status === 'loading' || !canSubmit}>
            {status === 'loading'
              ? 'Calculando plan…'
              : useCarOrigin
                ? 'Calcular plan desde el coche'
                : simulationMode
                  ? 'Simular plan de carga'
                  : 'Calcular plan de carga'}
          </button>
        </div>
      </form>

      {activeTrip && destinationPoint && status === 'idle' && !emergencyMode ? (
        <p className="panel-hint active-trip-restore" role="status">
          Calcula o recalcula el plan con tu posición y SOC actuales.
        </p>
      ) : null}

      {showReplanBar && replanDestination && lastResponse ? (
        <ReplanOnRouteBar
          destinationLabel={replanDestination.label}
          originLabel={originLabel}
          socPercent={resolveVehicleQueryForDisplay.soc_percent}
          socSourceLabel={telemetrySocLocked ? 'TeslaMate' : undefined}
          loading={status === 'loading'}
          autoFollow={enMarchaSettings.autoFollow}
          onAutoFollowChange={setAutoFollow}
          onReplan={() => void runPlan()}
          onRefreshOrigin={
            useCarOrigin
              ? () => void refreshCarTelemetry()
              : originMode === 'gps'
                ? refreshGps
                : undefined
          }
          canReplan={canSubmit && Boolean(replanDestination)}
          lastUpdatedAt={activeTrip?.updatedAt ?? null}
          showAutoFollow={liveOriginMode}
          routeDeviationKm={routeDeviationKm}
        />
      ) : null}

      {activeTrip && lastResponse && chargingStopCount > 0 && !emergencyMode ? (
        <ActiveTripProgressBar
          plan={lastResponse}
          progress={activeTrip.progress}
          userLocation={liveTrackingPoint}
          onMarkStopCompleted={handleMarkStopCompleted}
          onReplan={() => void runPlan()}
          replanLoading={status === 'loading'}
        />
      ) : null}

      {status === 'ready' && lastResponse ? (
        <>
          <ChargingPlanResults
            plan={lastResponse}
            selectedStationId={selectedStationId}
            onSelectStation={onSelectStation}
            originLabel={originLabel}
            destinationLabel={emergencyMode ? undefined : destinationPoint?.label ?? replanDestination?.label}
            currentLegIndex={activeTrip?.progress.currentLegIndex}
          />

          {activeTrip && !emergencyMode ? (
            <button type="button" className="btn btn--ghost replan-bar__clear" onClick={clearActiveTrip}>
              Finalizar viaje activo
            </button>
          ) : null}
        </>
      ) : null}
    </section>
  )
}
