import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchAlongRoute, geocodePlace, stationLabel } from '../api/route'
import type { AlongRouteResponse, GeocodeResult, Station } from '../api/types'
import { StationNavActions } from '../components/navigation/StationNavActions'
import { StationDynamicBadge } from '../stations/StationDynamicBadge'
import { googleMapsRouteUrl } from '../navigation/externalMaps'
import { PlaceAutocomplete } from './PlaceAutocomplete'

export type RouteEndpointInput = {
  label: string
  lat: number | null
  lon: number | null
}

type RouteSearchPanelProps = {
  minKw?: number
  maxKw?: number
  onResults: (response: AlongRouteResponse | null) => void
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
  minKw,
  maxKw,
  onResults,
  onSelectStation,
  onSearchStateChange,
  selectedStationId,
}: RouteSearchPanelProps) {
  const [originText, setOriginText] = useState('')
  const [destText, setDestText] = useState('')
  const [originPoint, setOriginPoint] = useState<RouteEndpointInput | null>(null)
  const [destPoint, setDestPoint] = useState<RouteEndpointInput | null>(null)
  const [corridorKm, setCorridorKm] = useState(10)
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastResponse, setLastResponse] = useState<AlongRouteResponse | null>(null)
  const [gpsLoading, setGpsLoading] = useState(false)
  const lastEndpointsRef = useRef<{ origin: RouteEndpointInput; dest: RouteEndpointInput } | null>(null)

  useEffect(() => {
    onSearchStateChange?.(status)
  }, [status, onSearchStateChange])

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
        })

        setLastResponse(response)
        setOriginText(origin.label)
        setDestText(destination.label)
        setOriginPoint(origin)
        setDestPoint(destination)
        lastEndpointsRef.current = { origin, dest: destination }
        setStatus('ready')
        onResults(response)
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Error en la búsqueda'
        setError(message)
        setStatus('error')
        setLastResponse(null)
        onResults(null)
      }
    },
    [corridorKm, destPoint, maxKw, minKw, onResults, onSelectStation, originPoint, resolveEndpoint],
  )

  useEffect(() => {
    const endpoints = lastEndpointsRef.current
    if (!endpoints || endpoints.origin.lat == null || endpoints.dest.lat == null) {
      return
    }
    void runSearch(endpoints.origin.label, endpoints.dest.label, endpoints.origin, endpoints.dest)
    // Solo re-buscar al cambiar filtros/corredor tras una búsqueda previa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [minKw, maxKw, corridorKm])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    void runSearch(originText, destText)
  }

  const handleOriginSelect = (place: GeocodeResult) => {
    setOriginPoint({ label: place.label, lat: place.lat, lon: place.lon })
  }

  const handleDestSelect = (place: GeocodeResult) => {
    setDestPoint({ label: place.label, lat: place.lat, lon: place.lon })
  }

  const handleOriginChange = (value: string) => {
    setOriginText(value)
    setOriginPoint(null)
  }

  const handleDestChange = (value: string) => {
    setDestText(value)
    setDestPoint(null)
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
        void runSearch(label, destText, point)
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
    void runSearch(EXAMPLE_ROUTE.origin, EXAMPLE_ROUTE.destination)
  }

  return (
    <section className="panel search-panel route-panel" aria-labelledby="route-search-heading">
      <h2 id="route-search-heading">En ruta</h2>
      <p className="panel-hint">
        Cargadores en el corredor, ordenados por menor desvío. Para planificar con batería (SOC), usa la pestaña{' '}
        <strong>Plan carga</strong>.
      </p>

      <form className="route-form" onSubmit={handleSubmit}>
        <PlaceAutocomplete
          id="route-origin"
          label="Origen"
          value={originText}
          placeholder="GPS o ciudad"
          onChange={handleOriginChange}
          onSelect={handleOriginSelect}
          disabled={status === 'loading'}
        />
        <button
          type="button"
          className="btn btn--secondary"
          onClick={handleUseGps}
          disabled={gpsLoading || status === 'loading'}
        >
          {gpsLoading ? 'Obteniendo GPS…' : 'Usar mi ubicación'}
        </button>

        <PlaceAutocomplete
          id="route-dest"
          label="Destino"
          value={destText}
          placeholder="Ciudad o dirección"
          onChange={handleDestChange}
          onSelect={handleDestSelect}
          disabled={status === 'loading'}
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

        <div className="route-form__actions">
          <button type="submit" className="btn btn--primary" disabled={status === 'loading'}>
            {status === 'loading' ? 'Calculando…' : 'Buscar cargadores'}
          </button>
          <button type="button" className="btn btn--ghost" onClick={handleExample} disabled={status === 'loading'}>
            Ejemplo Granada → Cartagena
          </button>
        </div>
      </form>

      {status === 'error' && error && (
        <p className="route-message route-message--error" role="alert">
          {error}
        </p>
      )}

      {status === 'ready' && lastResponse && (
        <div className="route-summary">
          <p className="route-summary__meta">
            Ruta {lastResponse.route_distance_km.toFixed(0)} km · ~
            {lastResponse.route_duration_minutes.toFixed(0)} min · {lastResponse.results.length} cargadores
          </p>
        </div>
      )}

      {status === 'ready' && lastResponse?.results.length === 0 && (
        <p className="route-message">
          No hay cargadores en el corredor con esos filtros. Prueba ampliar corredor o bajar kW.
        </p>
      )}

      {status === 'ready' && lastResponse && lastResponse.results.length > 0 && (
        <div className="route-export">
          <a
            className="btn btn--ghost"
            href={googleMapsRouteUrl({
              origin: lastResponse.origin,
              destination: lastResponse.destination,
              waypoints: lastResponse.results.map((item) => item.station.location),
            })}
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir paradas en Google Maps
          </a>
        </div>
      )}

      {lastResponse && lastResponse.results.length > 0 && (
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
                  <strong>{item.station.max_power_kw.toFixed(0)} kW</strong>
                  · +{item.deviation_km.toFixed(1)} km desvío
                  {item.extra_minutes > 0 && <> · +{item.extra_minutes.toFixed(0)} min</>}
                  {item.wrong_side && <span className="route-result__warn"> · sentido contrario</span>}
                </p>
                <StationDynamicBadge
                  status={item.station.dynamic_status}
                  priceEurKwh={item.station.dynamic_price_eur_kwh}
                  className="route-result__dynamic station-dynamic"
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
      )}
    </section>
  )
}
