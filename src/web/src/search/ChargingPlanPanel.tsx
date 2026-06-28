import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchChargingPlan } from '../api/chargingPlan'
import type { ChargingPlanResponse, GeocodeResult, Station } from '../api/types'
import { geocodePlace } from '../api/route'
import {
  classificationClassName,
  formatClassificationLabel,
} from '../charging/classificationDisplay'
import type { TerrainFactorId, VehiclePresetId } from '../vehicle/vehiclePresets'
import { VehicleProfilePanel } from '../components/vehicle/VehicleProfilePanel'
import { VehicleProfileFields } from '../components/vehicle/VehicleProfileFields'
import { useDeviceLocation } from '../hooks/useDeviceLocation'
import type { VehicleProfile } from '../vehicle/vehicleProfile'
import { vehicleProfileToChargingPlanQuery } from '../vehicle/vehicleProfile'
import { ChargingStopList } from './ChargingStopList'
import { PlaceAutocomplete } from './PlaceAutocomplete'

type SearchStatus = 'idle' | 'loading' | 'ready' | 'error'

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
  const [simulationMode, setSimulationMode] = useState(true)
  const [destText, setDestText] = useState('')
  const [destPoint, setDestPoint] = useState<{ label: string; lat: number; lon: number } | null>(null)
  const [emergencyMode, setEmergencyMode] = useState(false)
  const [corridorKm, setCorridorKm] = useState(10)
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastResponse, setLastResponse] = useState<ChargingPlanResponse | null>(null)
  const [manualOriginText, setManualOriginText] = useState('')
  const [manualOriginPoint, setManualOriginPoint] = useState<{ label: string; lat: number; lon: number } | null>(
    null,
  )
  const lastSearchKeyRef = useRef<string | null>(null)

  const locationSearchKey = useCallback(
    (point: { lat: number; lon: number; source?: string }) =>
      `${point.lat.toFixed(3)},${point.lon.toFixed(3)},${point.source ?? 'gps'}`,
    [],
  )

  const {
    location: gpsLocation,
    status: gpsStatus,
    error: gpsError,
    isGpsActive,
    refreshGps,
    setManualLocation,
    clearManualOverride,
  } = useDeviceLocation({ autoStart: !simulationMode, watch: !simulationMode })

  useEffect(() => {
    onSearchStateChange?.(status)
  }, [status, onSearchStateChange])

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
      if (simulationMode) {
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

      const vehicleQuery = vehicleProfileToChargingPlanQuery(vehicleProfile)
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
      })

      const searchKey = JSON.stringify({
        simulationMode,
        origin: locationSearchKey(origin),
        dest: emergencyMode ? null : destination,
        vehicleQuery,
        minKw,
        maxKw,
        corridorKm,
        emergencyMode,
      })
      lastSearchKeyRef.current = searchKey
      setLastResponse(response)
      setStatus('ready')
      onResults(response)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al calcular el plan'
      setError(message)
      setStatus('error')
      setLastResponse(null)
      onResults(null)
    }
  }, [
    corridorKm,
    destPoint,
    destText,
    emergencyMode,
    gpsLocation,
    locationSearchKey,
    maxKw,
    minKw,
    onResults,
    onSelectStation,
    resolveSimulationOrigin,
    simulationMode,
    vehicleProfile,
  ])

  useEffect(() => {
    if (simulationMode) {
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
    const vehicleQuery = vehicleProfileToChargingPlanQuery(vehicleProfile)
    const searchKey = JSON.stringify({
      simulationMode,
      origin: locationSearchKey(gpsLocation),
      dest: emergencyMode ? null : destPoint,
      vehicleQuery,
      minKw,
      maxKw,
      corridorKm,
      emergencyMode,
    })
    if (searchKey === lastSearchKeyRef.current) {
      return
    }
    void runPlan()
  }, [
    corridorKm,
    destPoint,
    emergencyMode,
    gpsLocation,
    gpsStatus,
    minKw,
    maxKw,
    runPlan,
    simulationMode,
    status,
    vehicleProfile,
    locationSearchKey,
  ])

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

  const handleSimulationToggle = (enabled: boolean) => {
    setSimulationMode(enabled)
    lastSearchKeyRef.current = null
    setStatus('idle')
    setError(null)
    setLastResponse(null)
    onResults(null)
  }

  const originLabel = simulationMode
    ? manualOriginPoint?.label ?? (manualOriginText.trim() || 'Indica origen')
    : (gpsLocation?.label ?? (gpsStatus === 'loading' ? 'Obteniendo GPS…' : 'Sin ubicación'))
  const showGpsBanner = !simulationMode && (isGpsActive || gpsStatus === 'loading')
  const canSubmit = simulationMode ? manualOriginText.trim().length > 0 : Boolean(gpsLocation)

  return (
    <section className="panel search-panel charge-panel" aria-labelledby="charge-plan-heading">
      <h2 id="charge-plan-heading">Plan de carga</h2>

      <VehicleProfilePanel
        className="charge-panel__vehicle"
        variant="compact"
        profile={vehicleProfile}
        onPresetChange={onVehiclePresetChange}
        onSocChange={onVehicleSocChange}
        onConsumptionChange={onVehicleConsumptionChange}
        onTerrainChange={onVehicleTerrainChange}
      />

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
        {simulationMode
          ? 'Simula un viaje: origen y destino manuales, SOC y estrategias sin GPS en vivo.'
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
        <label className="field field--checkbox">
          <input
            type="checkbox"
            checked={simulationMode}
            onChange={(event) => handleSimulationToggle(event.target.checked)}
          />
          <span>Modo simulación (planificar sin GPS en vivo)</span>
        </label>

        {simulationMode ? (
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
          </>
        )}

        <div className="route-form__actions">
          <button type="submit" className="btn btn--primary" disabled={status === 'loading' || !canSubmit}>
            {status === 'loading' ? 'Calculando plan…' : simulationMode ? 'Simular plan de carga' : 'Calcular plan de carga'}
          </button>
        </div>
      </form>

      {status === 'ready' && lastResponse && (
        <>
          {lastResponse.warnings.length > 0 && (
            <ul className="charge-warnings" aria-label="Alertas del plan">
              {lastResponse.warnings.map((warning) => (
                <li key={warning}>{warning}</li>
              ))}
            </ul>
          )}

          <div className="charge-summary">
            <p className="route-summary__meta">
              {lastResponse.mode === 'emergency' ? (
                <>
                  Modo emergencia · hasta cargador {lastResponse.charging_reach_km} km
                  {lastResponse.route_distance_km != null && (
                    <> · ruta al más cercano {lastResponse.route_distance_km.toFixed(1)} km</>
                  )}
                </>
              ) : (
                <>
                  Ruta {lastResponse.route_distance_km?.toFixed(0)} km · hasta cargador {lastResponse.charging_reach_km} km
                  {lastResponse.range_km < lastResponse.charging_reach_km && (
                    <> · plan reserva {lastResponse.range_km} km</>
                  )}
                  {lastResponse.reachable_without_stop ? ' · llegas sin parar' : ''}
                  {lastResponse.soc_at_destination_pct != null && !lastResponse.reachable_without_stop && (
                    <> · ~{lastResponse.soc_at_destination_pct.toFixed(0)} % SOC al destino</>
                  )}
                </>
              )}
            </p>
          </div>

          <div className="charge-strategies" aria-label="Estrategias recomendadas">
            {lastResponse.strategies.map((strategy) => (
              <article
                key={strategy.id}
                className={`charge-strategy ${strategy.station_id ? '' : 'charge-strategy--empty'}`}
              >
                <h3 className="charge-strategy__title">{strategy.label}</h3>
                <p className="charge-strategy__summary">{strategy.summary}</p>
                {strategy.classification && (
                  <span className={classificationClassName(strategy.classification, 'charging-class')}>
                    {formatClassificationLabel(strategy.classification)}
                    {strategy.soc_arrival_pct != null && <> · {strategy.soc_arrival_pct.toFixed(0)} % SOC</>}
                  </span>
                )}
              </article>
            ))}
          </div>

          {lastResponse.mode === 'emergency' ? (
            <>
              {lastResponse.stops.some((stop) => stop.classification !== 'unreachable') ? (
                <>
                  <h3 className="charge-section-title">Alcanzables desde tu posición</h3>
                  <ChargingStopList
                    stops={lastResponse.stops.filter((stop) => stop.classification !== 'unreachable')}
                    selectedStationId={selectedStationId}
                    onSelectStation={onSelectStation}
                    ariaLabel="Cargadores alcanzables"
                    showRouteDeviation={false}
                    distanceLabel={(item) => `${item.distance_from_origin_km.toFixed(1)} km desde la salida`}
                  />
                </>
              ) : null}
              {lastResponse.stops.some((stop) => stop.classification === 'unreachable') ? (
                <>
                  <h3 className="charge-section-title">
                    {lastResponse.stops.some((stop) => stop.classification !== 'unreachable')
                      ? 'Otros cercanos'
                      : 'Más cercanos (fuera de alcance actual)'}
                  </h3>
                  <p className="panel-hint charge-section-hint">
                    Tu alcance hasta cargador es {lastResponse.charging_reach_km} km. Los listados están más lejos;
                    la ruta en el mapa muestra el camino al más cercano.
                  </p>
                  <ChargingStopList
                    stops={lastResponse.stops.filter((stop) => stop.classification === 'unreachable')}
                    selectedStationId={selectedStationId}
                    onSelectStation={onSelectStation}
                    ariaLabel="Cargadores fuera de alcance"
                    showRouteDeviation={false}
                    distanceLabel={(item) => `${item.distance_from_origin_km.toFixed(1)} km desde la salida`}
                  />
                </>
              ) : null}
            </>
          ) : (
            <>
              {lastResponse.origin_stops.length > 0 && (
                <>
                  <h3 className="charge-section-title">Desde tu salida (por distancia)</h3>
                  <p className="panel-hint charge-section-hint">
                    Cargadores alcanzables desde el origen con tu SOC actual. Útiles si no llegas a los de la ruta.
                  </p>
                  <ChargingStopList
                    stops={lastResponse.origin_stops}
                    selectedStationId={selectedStationId}
                    onSelectStation={onSelectStation}
                    ariaLabel="Cargadores desde el origen"
                    showRouteDeviation={false}
                    distanceLabel={(item) => `${item.distance_from_origin_km.toFixed(1)} km desde la salida`}
                  />
                </>
              )}

              <h3 className="charge-section-title">En la ruta (corredor)</h3>
              {lastResponse.stops.length === 0 ? (
                <p className="route-message">
                  No hay paradas en el corredor alcanzables con el SOC actual. Revisa la sección anterior o baja el
                  filtro de kW.
                </p>
              ) : (
                <ChargingStopList
                  stops={lastResponse.stops}
                  selectedStationId={selectedStationId}
                  onSelectStation={onSelectStation}
                  ariaLabel="Paradas en la ruta"
                  showRouteDeviation
                />
              )}
            </>
          )}
        </>
      )}
    </section>
  )
}
