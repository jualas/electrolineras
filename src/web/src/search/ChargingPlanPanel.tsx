import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchChargingPlan } from '../api/chargingPlan'
import type { ChargingPlanResponse, GeocodeResult, Station } from '../api/types'
import { geocodePlace } from '../api/route'
import { VehicleTelemetryStrip } from '../components/vehicle/VehicleTelemetryStrip'
import type { TerrainFactorId, VehiclePresetId } from '../vehicle/vehiclePresets'
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
import { PlaceAutocomplete } from './PlaceAutocomplete'
import { RoutePreferenceFields } from './RoutePreferenceFields'
import { RevePlanningFields, revePlanningForPreset, type RevePlanningOptions } from './RevePlanningFields'
import { DEFAULT_CHARGING_PREFERENCES } from '../charging/chargingPreferences'
import { buildPlanSearchKey } from '../charging/planSearchKey'
import { useActiveTrip } from '../hooks/useActiveTrip'
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
  onVehicleTerrainChange: (terrainFactorId: TerrainFactorId) => void
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
  onVehicleTerrainChange,
  minKw,
  maxKw,
  onResults,
  onSelectStation,
  onSearchStateChange,
  selectedStationId,
}: ChargingPlanPanelProps) {
  const [originMode, setOriginMode] = useState<OriginMode>('simulation')
  const originModeTouchedRef = useRef(false)
  const [destText, setDestText] = useState('')
  const [destPoint, setDestPoint] = useState<{ label: string; lat: number; lon: number } | null>(null)
  const [emergencyMode, setEmergencyMode] = useState(false)
  const [corridorKm, setCorridorKm] = useState(10)
  const [routePreference, setRoutePreference] = useState<RoutePreference>('shortest')
  const [avoidTolls, setAvoidTolls] = useState(false)
  const [revePlanning, setRevePlanning] = useState<RevePlanningOptions>(() =>
    revePlanningForPreset(vehicleProfile.presetId),
  )
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastResponse, setLastResponse] = useState<ChargingPlanResponse | null>(null)
  const [manualOriginText, setManualOriginText] = useState('')
  const [manualOriginPoint, setManualOriginPoint] = useState<{ label: string; lat: number; lon: number } | null>(
    null,
  )
  const lastSearchKeyRef = useRef<string | null>(null)
  const recalcOnPreferenceRef = useRef(false)
  const tripRestoredRef = useRef(false)
  const { activeTrip, enMarchaSettings, saveActiveTrip, clearActiveTrip, setAutoFollow } = useActiveTrip()

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
    if (tripRestoredRef.current || !activeTrip || destPoint) {
      return
    }
    tripRestoredRef.current = true
    setDestPoint(activeTrip.destination)
    setDestText(activeTrip.destination.label)
    setCorridorKm(activeTrip.corridorKm)
    setRoutePreference(activeTrip.routePreference)
    setAvoidTolls(activeTrip.avoidTolls)
    if (carTelemetryAvailable && activeTrip.originMode === 'car') {
      setOriginMode('car')
    } else if (activeTrip.originMode === 'gps') {
      setOriginMode('gps')
    }
  }, [activeTrip, carTelemetryAvailable, destPoint])

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

      let destination = destPoint
      if (!emergencyMode && !destination && destText.trim()) {
        const geocoded = await geocodePlace(destText.trim())
        destination = { label: geocoded.label, lat: geocoded.lat, lon: geocoded.lon }
        setDestPoint(destination)
        setDestText(geocoded.label)
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
      setLastResponse(response)
      setStatus('ready')
      onResults(response)
      if (!emergencyMode && destination) {
        saveActiveTrip({
          destination: {
            label: destination.label,
            lat: destination.lat,
            lon: destination.lon,
          },
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
    destPoint,
    destText,
    emergencyMode,
    routePreference,
    avoidTolls,
    gpsLocation,
    maxKw,
    minKw,
    onResults,
    onSelectStation,
    resolveSimulationOrigin,
    resolveVehicleQuery,
    simulationMode,
    originMode,
    clearActiveTrip,
    saveActiveTrip,
    useCarOrigin,
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
    if (!emergencyMode && !destPoint) {
      return
    }
    const vehicleQuery = resolveVehicleQuery()
    const searchKey = buildPlanSearchKey({
      originMode,
      origin: gpsLocation,
      dest: emergencyMode ? null : destPoint,
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
    void runPlan()
  }, [
    avoidTolls,
    corridorKm,
    destPoint,
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
    if (!emergencyMode && !destPoint) {
      return
    }
    const origin = carOriginFromTelemetry(carTelemetry)
    const vehicleQuery = resolveVehicleQuery()
    const searchKey = buildPlanSearchKey({
      originMode,
      origin,
      dest: emergencyMode ? null : destPoint,
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
    void runPlan()
  }, [
    avoidTolls,
    carTelemetry,
    corridorKm,
    destPoint,
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

  const handleDestSelect = (place: GeocodeResult) => {
    setDestPoint({ label: place.label, lat: place.lat, lon: place.lon })
    setDestText(place.label)
    lastSearchKeyRef.current = null
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

  const handleOriginModeChange = (nextMode: OriginMode) => {
    originModeTouchedRef.current = true
    setOriginMode(nextMode)
    lastSearchKeyRef.current = null
    setStatus('idle')
    setError(null)
    setLastResponse(null)
    onResults(null)
  }

  const handleSimulationToggle = (enabled: boolean) => {
    handleOriginModeChange(enabled ? 'simulation' : carTelemetryAvailable ? 'car' : 'gps')
  }

  const originLabel = useCarOrigin && carTelemetry
    ? carOriginFromTelemetry(carTelemetry).label
    : simulationMode
      ? manualOriginPoint?.label ?? (manualOriginText.trim() || 'Indica origen')
      : (gpsLocation?.label ?? (gpsStatus === 'loading' ? 'Obteniendo GPS…' : 'Sin ubicación'))
  const showGpsBanner = originMode === 'gps' && (isGpsActive || gpsStatus === 'loading')
  const canSubmit =
    useCarOrigin && carTelemetry
      ? true
      : simulationMode
        ? manualOriginText.trim().length > 0
        : Boolean(gpsLocation)
  const telemetrySocLocked = carTelemetryAvailable
  const liveOriginMode = useCarOrigin || originMode === 'gps'
  const replanDestination = destPoint ?? activeTrip?.destination ?? null
  const showReplanBar =
    !emergencyMode && Boolean(replanDestination) && Boolean(lastResponse) && liveOriginMode
  const resolveVehicleQueryForDisplay = resolveVehicleQuery()

  return (
    <section className="panel search-panel charge-panel" aria-labelledby="charge-plan-heading">
      <h2 id="charge-plan-heading">Plan de carga</h2>

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
        onTerrainChange={onVehicleTerrainChange}
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

      <details className="vehicle-advanced">
        <summary>Consumo y terreno (avanzado)</summary>
        <div className="vehicle-advanced__body">
          <VehicleProfileFields
            profile={vehicleProfile}
            onPresetChange={onVehiclePresetChange}
            onSocChange={onVehicleSocChange}
            onConsumptionChange={onVehicleConsumptionChange}
            onTerrainChange={onVehicleTerrainChange}
            variant="advanced"
          />
        </div>
      </details>

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
        {carTelemetryAvailable && (
          <fieldset className="origin-mode" aria-label="Origen del plan">
            <span className="field__label">Origen</span>
            <div className="chip-row" role="list">
              <button
                type="button"
                role="listitem"
                className={`chip ${originMode === 'car' ? 'chip--active' : ''}`}
                aria-pressed={originMode === 'car'}
                onClick={() => handleOriginModeChange('car')}
              >
                Coche (TeslaMate)
              </button>
              <button
                type="button"
                role="listitem"
                className={`chip ${originMode === 'gps' ? 'chip--active' : ''}`}
                aria-pressed={originMode === 'gps'}
                onClick={() => handleOriginModeChange('gps')}
              >
                GPS móvil
              </button>
              <button
                type="button"
                role="listitem"
                className={`chip ${originMode === 'simulation' ? 'chip--active' : ''}`}
                aria-pressed={originMode === 'simulation'}
                onClick={() => handleOriginModeChange('simulation')}
              >
                Simulación
              </button>
            </div>
          </fieldset>
        )}

        {!carTelemetryAvailable && (
          <label className="field field--checkbox">
            <input
              type="checkbox"
              checked={simulationMode}
              onChange={(event) => handleSimulationToggle(event.target.checked)}
            />
            <span>Modo simulación (planificar sin GPS en vivo)</span>
          </label>
        )}

        {useCarOrigin && carTelemetry ? (
          <div className="field">
            <span className="field__label">Origen (coche)</span>
            <p className="charge-origin-readout" title={originLabel}>
              {originLabel} · {carTelemetry.lat.toFixed(4)}, {carTelemetry.lon.toFixed(4)}
            </p>
          </div>
        ) : simulationMode ? (
          <PlaceAutocomplete
            id="charge-origin-sim"
            label="Origen"
            value={manualOriginText}
            placeholder="Ciudad o dirección de salida"
            onChange={handleManualOriginChange}
            onSelect={handleManualOriginSelect}
          />
        ) : (
          <>
            <div className="field">
              <span className="field__label">Origen (GPS)</span>
              <p className="charge-origin-readout" title={originLabel}>
                {originLabel}
              </p>
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
            </div>

            <PlaceAutocomplete
              id="charge-origin-manual"
              label="Origen manual (fallback)"
              value={manualOriginText}
              placeholder="Solo si el GPS falla"
              onChange={handleManualOriginChange}
              onSelect={handleManualOriginSelect}
            />
          </>
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
            <PlaceAutocomplete
              id="charge-dest"
              label="Destino"
              value={destText}
              placeholder="Ciudad o dirección"
              onChange={(value) => {
                setDestText(value)
                setDestPoint(null)
                lastSearchKeyRef.current = null
              }}
              onSelect={handleDestSelect}
            />

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
              comparisonPlan={status === 'ready' ? lastResponse : null}
            />

            <RevePlanningFields
              options={revePlanning}
              consumptionWhPerKm={vehicleProfile.consumptionWhPerKm}
              disabled={status === 'loading'}
              onChange={(value) => {
                setRevePlanning(value)
                if (status === 'ready' && lastResponse && !emergencyMode) {
                  recalcOnPreferenceRef.current = true
                } else {
                  lastSearchKeyRef.current = null
                }
              }}
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

      {activeTrip && destPoint && status === 'idle' && !emergencyMode ? (
        <p className="panel-hint active-trip-restore" role="status">
          Viaje activo a {activeTrip.destination.label}. Calcula o recalcula el plan con tu posición y SOC actuales.
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
        />
      ) : null}

      {status === 'ready' && lastResponse ? (
        <>
          <ChargingPlanResults
            plan={lastResponse}
            selectedStationId={selectedStationId}
            onSelectStation={onSelectStation}
            originLabel={originLabel}
            destinationLabel={emergencyMode ? undefined : destPoint?.label ?? replanDestination?.label}
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
