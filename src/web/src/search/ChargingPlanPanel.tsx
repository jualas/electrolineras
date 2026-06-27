import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchChargingPlan, stationLabel } from '../api/chargingPlan'
import type { ChargingPlanResponse, GeocodeResult, Station } from '../api/types'
import { geocodePlace } from '../api/route'
import {
  classificationClassName,
  formatClassificationLabel,
} from '../charging/classificationDisplay'
import { StationNavActions } from '../components/navigation/StationNavActions'
import type { TerrainFactorId, VehiclePresetId } from '../vehicle/vehiclePresets'
import { VehicleProfilePanel } from '../components/vehicle/VehicleProfilePanel'
import { VehicleProfileFields } from '../components/vehicle/VehicleProfileFields'
import { useDeviceLocation } from '../hooks/useDeviceLocation'
import { StationDynamicBadge } from '../stations/StationDynamicBadge'
import type { VehicleProfile } from '../vehicle/vehicleProfile'
import { vehicleProfileToChargingPlanQuery } from '../vehicle/vehicleProfile'
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
  const [destText, setDestText] = useState('')
  const [destPoint, setDestPoint] = useState<{ label: string; lat: number; lon: number } | null>(null)
  const [emergencyMode, setEmergencyMode] = useState(false)
  const [corridorKm, setCorridorKm] = useState(10)
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastResponse, setLastResponse] = useState<ChargingPlanResponse | null>(null)
  const [manualOriginText, setManualOriginText] = useState('')
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
  } = useDeviceLocation({ autoStart: true, watch: true })

  useEffect(() => {
    onSearchStateChange?.(status)
  }, [status, onSearchStateChange])

  const runPlan = useCallback(async () => {
    const origin = gpsLocation
    if (!origin) {
      setError('Esperando GPS del teléfono o indica origen manual')
      setStatus('error')
      onResults(null)
      return
    }

    setStatus('loading')
    setError(null)
    onSelectStation?.(null)

    try {
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
      if (gpsLocation) {
        lastSearchKeyRef.current = JSON.stringify({
          origin: locationSearchKey(gpsLocation),
          failed: message,
        })
      }
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
    vehicleProfile,
  ])

  useEffect(() => {
    if (gpsStatus !== 'active' || !gpsLocation) {
      return
    }
    if (status === 'loading') {
      return
    }
    const vehicleQuery = vehicleProfileToChargingPlanQuery(vehicleProfile)
    const searchKey = JSON.stringify({
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
    if (!emergencyMode && !destPoint && !destText.trim()) {
      return
    }
    void runPlan()
  }, [
    corridorKm,
    destPoint,
    destText,
    emergencyMode,
    gpsLocation,
    gpsStatus,
    minKw,
    maxKw,
    runPlan,
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
  }

  const handleManualOriginSelect = (place: GeocodeResult) => {
    setManualOriginText(place.label)
    setManualLocation({ lat: place.lat, lon: place.lon, label: place.label })
  }

  const originLabel = gpsLocation?.label ?? (gpsStatus === 'loading' ? 'Obteniendo GPS…' : 'Sin ubicación')
  const showGpsBanner = isGpsActive || gpsStatus === 'loading'

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
        Origen: GPS del teléfono (Android Auto). Indica destino y pulsa calcular.
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
          onChange={setManualOriginText}
          onSelect={handleManualOriginSelect}
          disabled={status === 'loading'}
        />

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
              disabled={status === 'loading'}
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
          <button type="submit" className="btn btn--primary" disabled={status === 'loading' || !gpsLocation}>
            {status === 'loading' ? 'Calculando plan…' : 'Calcular plan de carga'}
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
                <>Modo emergencia · alcance {lastResponse.range_km} km</>
              ) : (
                <>
                  Ruta {lastResponse.route_distance_km?.toFixed(0)} km · alcance {lastResponse.range_km} km
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

          {lastResponse.stops.length === 0 ? (
            <p className="route-message">No hay paradas viables con el SOC y filtros actuales.</p>
          ) : (
            <ol className="route-results" aria-label="Paradas del plan de carga">
              {lastResponse.stops.map((item, index) => (
                <li key={item.station.id} className="route-result-card">
                  <button
                    type="button"
                    className={`route-result ${selectedStationId === item.station.id ? 'route-result--active' : ''}`}
                    onClick={() => onSelectStation?.(item.station)}
                  >
                    <div className="route-result__head">
                      <span className="route-result__rank">{index + 1}</span>
                      <div>
                        <p className="route-result__title">{stationLabel(item.station)}</p>
                        <p className="route-result__operator">{item.station.operator ?? '—'}</p>
                      </div>
                    </div>
                    <span className={classificationClassName(item.classification, 'charging-class')}>
                      {formatClassificationLabel(item.classification)} · {item.soc_arrival_pct.toFixed(0)} % SOC
                    </span>
                    <p className="route-result__meta">
                      <strong>{item.station.max_power_kw.toFixed(0)} kW</strong>
                      · +{item.deviation_km.toFixed(1)} km desvío
                      {item.extra_minutes > 0 && <> · +{item.extra_minutes.toFixed(0)} min</>}
                    </p>
                    <StationDynamicBadge
                      status={item.station.dynamic_status}
                      priceEurKwh={item.station.dynamic_price_eur_kwh}
                      className="route-result__dynamic station-dynamic"
                    />
                    <p className="route-result__dist">
                      A {item.distance_from_origin_km.toFixed(0)} km desde el origen
                    </p>
                  </button>
                  <StationNavActions
                    lat={item.station.location.lat}
                    lon={item.station.location.lon}
                    label={stationLabel(item.station)}
                    compact
                  />
                </li>
              ))}
            </ol>
          )}
        </>
      )}
    </section>
  )
}
