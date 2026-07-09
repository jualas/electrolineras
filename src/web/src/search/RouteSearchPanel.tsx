import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchChargingPlan } from '../api/chargingPlan'
import { fetchAlongRoute, geocodePlace, stationLabel } from '../api/route'
import type { AlongRouteResponse, ChargingPlanResponse, GeocodeResult, Station } from '../api/types'
import { RouteExportActions } from '../components/navigation/RouteExportActions'
import { routeExportSpecFromChargingPlan } from '../charging/planRouteStops'
import { StationNavActions } from '../components/navigation/StationNavActions'
import { StationDynamicBadge } from '../stations/StationDynamicBadge'
import { StationExternalReviews } from '../stations/StationExternalReviews'
import { summarizeConnectors } from '../stations/connectorDisplay'
import type { VehicleProfile } from '../vehicle/vehicleProfile'
import { vehicleProfileToChargingPlanQuery } from '../vehicle/vehicleProfile'
import { ChargingPlanResults } from './ChargingPlanResults'
import { PlaceAutocomplete } from './PlaceAutocomplete'
import { formatRouteAlternativesKm, RoutePreferenceFields } from './RoutePreferenceFields'
import { ChargingPreferenceFields } from './ChargingPreferenceFields'
import { useChargingPreferences } from '../hooks/useChargingPreferences'
import type { RoutePreference } from '../api/types'

export type RouteEndpointInput = {
  label: string
  lat: number | null
  lon: number | null
}

type RouteSearchPanelProps = {
  vehicleProfile: VehicleProfile
  minKw?: number
  maxKw?: number
  onResults: (response: AlongRouteResponse | null) => void
  onChargePlanResults?: (response: ChargingPlanResponse | null) => void
  onSelectStation?: (station: Station | null) => void
  onSearchStateChange?: (status: SearchStatus) => void
  selectedStationId?: string | null
}

type SearchStatus = 'idle' | 'loading' | 'ready' | 'error'

const EXAMPLE_ROUTE = {
  origin: 'Granada, España',
  destination: 'Cartagena, España',
}

export function RouteSearchPanel({
  vehicleProfile,
  minKw,
  maxKw,
  onResults,
  onChargePlanResults,
  onSelectStation,
  onSearchStateChange,
  selectedStationId,
}: RouteSearchPanelProps) {
  const [simulationMode, setSimulationMode] = useState(true)
  const [originText, setOriginText] = useState('')
  const [destText, setDestText] = useState('')
  const [originPoint, setOriginPoint] = useState<RouteEndpointInput | null>(null)
  const [destPoint, setDestPoint] = useState<RouteEndpointInput | null>(null)
  const [corridorKm, setCorridorKm] = useState(10)
  const [routePreference, setRoutePreference] = useState<RoutePreference>('shortest')
  const [avoidTolls, setAvoidTolls] = useState(false)
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastResponse, setLastResponse] = useState<AlongRouteResponse | null>(null)
  const [chargePlan, setChargePlan] = useState<ChargingPlanResponse | null>(null)
  const [gpsLoading, setGpsLoading] = useState(false)
  const lastEndpointsRef = useRef<{ origin: RouteEndpointInput; dest: RouteEndpointInput } | null>(null)
  const hasSuccessfulSearchRef = useRef(false)
  const recalcOnPreferenceRef = useRef(false)
  const { preferences: chargingPreferences, toggleOperator, setMaxPriceEurKwh } = useChargingPreferences()

  useEffect(() => {
    onSearchStateChange?.(status)
  }, [status, onSearchStateChange])

  const invalidateCachedSearch = useCallback(() => {
    lastEndpointsRef.current = null
    hasSuccessfulSearchRef.current = false
  }, [])

  const resolveEndpoint = useCallback(
    async (text: string, point?: RouteEndpointInput | null): Promise<RouteEndpointInput> => {
      if (point?.lat != null && point.lon != null) {
        return point
      }
      const trimmed = text.trim()
      if (!trimmed) {
        throw new Error('Indica origen y destino')
      }
      const geocoded = await geocodePlace(trimmed)
      return { label: geocoded.label, lat: geocoded.lat, lon: geocoded.lon }
    },
    [],
  )

  const runSearch = useCallback(
    async (
      originInput: string,
      destInput: string,
      originResolved?: RouteEndpointInput | null,
      destResolved?: RouteEndpointInput | null,
    ) => {
      setStatus('loading')
      setError(null)
      onSelectStation?.(null)
      setChargePlan(null)
      onChargePlanResults?.(null)

      try {
        const origin = await resolveEndpoint(originInput, originResolved ?? originPoint)
        const destination = await resolveEndpoint(destInput, destResolved ?? destPoint)

        const response = await fetchAlongRoute({
          originLat: origin.lat!,
          originLon: origin.lon!,
          destLat: destination.lat!,
          destLon: destination.lon!,
          minKw,
          maxKw,
          corridorKm,
          limit: 15,
          routePreference,
          avoidHighways: avoidTolls,
        })

        let plan: ChargingPlanResponse | null = null
        try {
          const vehicleQuery = vehicleProfileToChargingPlanQuery(vehicleProfile)
          plan = await fetchChargingPlan({
            originLat: origin.lat!,
            originLon: origin.lon!,
            destLat: destination.lat!,
            destLon: destination.lon!,
            socPercent: vehicleQuery.soc_percent,
            usableCapacityKwh: vehicleQuery.usable_capacity_kwh,
            consumptionWhPerKm: vehicleQuery.consumption_wh_per_km,
            terrainFactor: vehicleQuery.terrain_factor,
            reserveSocPercent: vehicleQuery.reserve_soc_percent,
            minKw,
            maxKw,
            corridorKm,
            limit: 15,
            routePreference,
            avoidHighways: avoidTolls,
            vehiclePresetId: vehicleQuery.vehicle_preset_id,
            preferredOperators: chargingPreferences.preferredOperators,
            maxPriceEurKwh: chargingPreferences.maxPriceEurKwh,
          })
        } catch {
          plan = null
        }

        setLastResponse(response)
        setChargePlan(plan)
        onChargePlanResults?.(plan)
        setOriginText(origin.label)
        setDestText(destination.label)
        setOriginPoint(origin)
        setDestPoint(destination)
        lastEndpointsRef.current = { origin, dest: destination }
        hasSuccessfulSearchRef.current = true
        setStatus('ready')
        onResults(response)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Error en la búsqueda'
        setError(message)
        setStatus('error')
        setLastResponse(null)
        setChargePlan(null)
        onChargePlanResults?.(null)
        onResults(null)
      }
    },
    [
      avoidTolls,
      corridorKm,
      destPoint,
      maxKw,
      minKw,
      onChargePlanResults,
      onResults,
      onSelectStation,
      originPoint,
      resolveEndpoint,
      routePreference,
      vehicleProfile,
      chargingPreferences,
    ],
  )

  useEffect(() => {
    if (simulationMode || !hasSuccessfulSearchRef.current) {
      return
    }
    const endpoints = lastEndpointsRef.current
    if (!endpoints || endpoints.origin.lat == null || endpoints.dest.lat == null) {
      return
    }
    void runSearch(endpoints.origin.label, endpoints.dest.label, endpoints.origin, endpoints.dest)
    // Solo re-buscar al cambiar filtros/corredor tras una búsqueda previa en modo conducción.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minKw, maxKw, corridorKm, routePreference, avoidTolls, chargingPreferences, simulationMode])

  useEffect(() => {
    if (!recalcOnPreferenceRef.current) {
      return
    }
    if (status === 'loading') {
      return
    }
    const endpoints = lastEndpointsRef.current
    if (!endpoints || endpoints.origin.lat == null || endpoints.dest.lat == null) {
      recalcOnPreferenceRef.current = false
      return
    }
    recalcOnPreferenceRef.current = false
    void runSearch(endpoints.origin.label, endpoints.dest.label, endpoints.origin, endpoints.dest)
  }, [routePreference, avoidTolls, chargingPreferences, runSearch, status])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    void runSearch(originText, destText)
  }

  const handleOriginSelect = (place: GeocodeResult) => {
    setOriginPoint({ label: place.label, lat: place.lat, lon: place.lon })
    setOriginText(place.label)
    invalidateCachedSearch()
  }

  const handleDestSelect = (place: GeocodeResult) => {
    setDestPoint({ label: place.label, lat: place.lat, lon: place.lon })
    setDestText(place.label)
    invalidateCachedSearch()
  }

  const handleOriginChange = (value: string) => {
    setOriginText(value)
    setOriginPoint(null)
    invalidateCachedSearch()
  }

  const handleDestChange = (value: string) => {
    setDestText(value)
    setDestPoint(null)
    invalidateCachedSearch()
  }

  const handleSimulationToggle = (enabled: boolean) => {
    setSimulationMode(enabled)
    invalidateCachedSearch()
    setStatus('idle')
    setError(null)
    setLastResponse(null)
    onResults(null)
    setChargePlan(null)
    onChargePlanResults?.(null)
  }

  const handleUseGps = () => {
    if (!navigator.geolocation) {
      setError('Geolocalización no disponible en este navegador')
      setStatus('error')
      return
    }
    setGpsLoading(true)
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setGpsLoading(false)
        const label = 'Mi ubicación'
        const point = {
          label,
          lat: position.coords.latitude,
          lon: position.coords.longitude,
        }
        setOriginText(label)
        setOriginPoint(point)
        invalidateCachedSearch()
        if (!simulationMode && destPoint) {
          void runSearch(label, destText, point, destPoint)
        }
      },
      () => {
        setGpsLoading(false)
        setError('No se pudo obtener la ubicación GPS')
        setStatus('error')
      },
      { enableHighAccuracy: true, timeout: 15000 },
    )
  }

  const handleExample = () => {
    setOriginText(EXAMPLE_ROUTE.origin)
    setDestText(EXAMPLE_ROUTE.destination)
    setOriginPoint(null)
    setDestPoint(null)
    invalidateCachedSearch()
    void runSearch(EXAMPLE_ROUTE.origin, EXAMPLE_ROUTE.destination)
  }

  return (
    <section className="panel search-panel route-panel" aria-labelledby="route-search-heading">
      <h2 id="route-search-heading">En ruta</h2>
      <p className="panel-hint">
        {simulationMode
          ? 'Simula una ruta con origen y destino manuales. Para plan de carga con batería (SOC), usa la pestaña Asistente.'
          : 'Cargadores en el corredor, ordenados por menor desvío. Para planificar con SOC y paradas, usa la pestaña Asistente.'}
      </p>

      <form className="route-form" onSubmit={handleSubmit}>
        <label className="field field--checkbox">
          <input
            type="checkbox"
            checked={simulationMode}
            onChange={(event) => handleSimulationToggle(event.target.checked)}
          />
          <span>Modo simulación (sin GPS automático)</span>
        </label>

        <PlaceAutocomplete
          id="route-origin"
          label="Origen"
          value={originText}
          placeholder={simulationMode ? 'Ciudad o dirección de salida' : 'GPS o ciudad'}
          onChange={handleOriginChange}
          onSelect={handleOriginSelect}
        />

        {!simulationMode && (
          <button
            type="button"
            className="btn btn--secondary"
            onClick={handleUseGps}
            disabled={gpsLoading}
          >
            {gpsLoading ? 'Obteniendo GPS…' : 'Usar mi ubicación'}
          </button>
        )}

        <PlaceAutocomplete
          id="route-dest"
          label="Destino"
          value={destText}
          placeholder="Ciudad o dirección"
          onChange={handleDestChange}
          onSelect={handleDestSelect}
        />

        <label className="field">
          <span className="field__label">Corredor (km)</span>
          <select value={corridorKm} onChange={(event) => setCorridorKm(Number(event.target.value))}>
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
            if (status === 'ready' && lastResponse) {
              recalcOnPreferenceRef.current = true
            } else {
              invalidateCachedSearch()
            }
          }}
          onAvoidTollsChange={(value) => {
            setAvoidTolls(value)
            if (status === 'ready' && lastResponse) {
              recalcOnPreferenceRef.current = true
            } else {
              invalidateCachedSearch()
            }
          }}
          disabled={status === 'loading'}
          comparisonPlan={status === 'ready' ? lastResponse : null}
        />

        <ChargingPreferenceFields
          preferences={chargingPreferences}
          onToggleOperator={(operator) => {
            toggleOperator(operator)
            if (status === 'ready' && lastResponse) {
              recalcOnPreferenceRef.current = true
            } else {
              invalidateCachedSearch()
            }
          }}
          onMaxPriceChange={(value) => {
            setMaxPriceEurKwh(value)
            if (status === 'ready' && lastResponse) {
              recalcOnPreferenceRef.current = true
            } else {
              invalidateCachedSearch()
            }
          }}
          disabled={status === 'loading'}
        />

        <div className="route-form__actions">
          <button type="submit" className="btn btn--primary" disabled={status === 'loading'}>
            {status === 'loading' ? 'Calculando…' : simulationMode ? 'Simular ruta' : 'Buscar cargadores'}
          </button>
          <button type="button" className="btn btn--ghost" onClick={handleExample} disabled={status === 'loading'}>
            Ejemplo Granada → Cartagena
          </button>
        </div>
      </form>

      {status === 'loading' && (
        <p className="route-message route-message--loading" role="status">
          Calculando ruta… puedes seguir editando origen y destino.
        </p>
      )}

      {status === 'error' && error && (
        <p className="route-message route-message--error" role="alert">
          {error}
        </p>
      )}

      {status === 'ready' && lastResponse && (
        <div className="route-summary">
          <p className="route-summary__meta">
            {formatRouteAlternativesKm(lastResponse)} · ~
            {lastResponse.route_duration_minutes.toFixed(0)} min · {lastResponse.results.length} cargadores
          </p>
        </div>
      )}

      {status === 'ready' && lastResponse?.results.length === 0 && (
        <p className="route-message">
          No hay cargadores en el corredor con esos filtros. Prueba ampliar corredor o bajar kW.
        </p>
      )}

      {status === 'ready' && lastResponse && (() => {
        const routeExport =
          chargePlan != null
            ? routeExportSpecFromChargingPlan(chargePlan)
            : {
                origin: lastResponse.origin,
                destination: lastResponse.destination,
                waypoints: lastResponse.results.map((item) => item.station.location),
                title: 'Ruta Electrolineras',
              }
        return routeExport ? <RouteExportActions route={routeExport} /> : null
      })()}

      {chargePlan && (
        <ChargingPlanResults
          plan={chargePlan}
          selectedStationId={selectedStationId}
          onSelectStation={onSelectStation}
        />
      )}

      {status === 'ready' &&
        lastResponse &&
        lastResponse.results.length > 0 &&
        !(chargePlan?.planned_stops?.length) &&
        !chargePlan?.reachable_without_stop && (
        <>
          <h3 className="charge-section-title">En el corredor de la ruta</h3>
          <ol className="route-results" aria-label="Cargadores en ruta">
            {lastResponse.results.map((item, index) => (
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
                  <p className="route-result__meta">
                    <strong>{summarizeConnectors(item.station.connectors)}</strong>
                    · +{item.deviation_km.toFixed(1)} km desvío
                    {item.extra_minutes > 0 && <> · +{item.extra_minutes.toFixed(0)} min</>}
                    {item.wrong_side && <span className="route-result__warn"> · sentido contrario</span>}
                  </p>
                <StationDynamicBadge
                  status={item.station.dynamic_status}
                  priceEurKwh={item.station.dynamic_price_eur_kwh}
                  className="route-result__dynamic station-dynamic"
                />
                <StationExternalReviews
                  ratingAvg={item.station.external_rating_avg}
                  ratingCount={item.station.external_rating_count}
                  comments={item.station.external_comments}
                  compact
                />
                  <p className="route-result__dist">A {item.route_distance_km.toFixed(0)} km desde el origen</p>
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
        </>
      )}
    </section>
  )
}
