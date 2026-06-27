import { useCallback, useEffect, useRef, useState } from 'react'

import { fetchNearbyStations, formatDistanceKm } from '../api/nearby'
import { stationLabel } from '../api/route'
import type { MapBounds, NearbyResponse, Station } from '../api/types'
import { StationNavActions } from '../components/navigation/StationNavActions'
import { StationDynamicBadge } from '../stations/StationDynamicBadge'
import { PlaceAutocomplete } from './PlaceAutocomplete'

export type CityLocationMode = 'gps' | 'address' | 'map_bbox' | 'map_pin'

type CityPin = {
  label: string
  lat: number
  lon: number
}

type CitySearchPanelProps = {
  minKw?: number
  maxKw?: number
  onResults: (response: NearbyResponse | null) => void
  onSelectStation?: (station: Station | null) => void
  onSearchStateChange?: (status: SearchStatus) => void
  onPickModeChange?: (active: boolean) => void
  onRequestMapBounds?: () => MapBounds | null
  mapPin?: CityPin | null
  selectedStationId?: string | null
}

type SearchStatus = 'idle' | 'loading' | 'ready' | 'error'

const RADIUS_OPTIONS = [
  { value: 500, label: '500 m' },
  { value: 1000, label: '1 km' },
  { value: 2000, label: '2 km' },
  { value: 5000, label: '5 km' },
]

export function CitySearchPanel({
  minKw,
  maxKw,
  onResults,
  onSelectStation,
  onSearchStateChange,
  onPickModeChange,
  onRequestMapBounds,
  mapPin,
  selectedStationId,
}: CitySearchPanelProps) {
  const [locationMode, setLocationMode] = useState<CityLocationMode>('address')
  const [addressText, setAddressText] = useState('')
  const [addressPoint, setAddressPoint] = useState<CityPin | null>(null)
  const [radiusM, setRadiusM] = useState(1000)
  const [publicOpenOnly, setPublicOpenOnly] = useState(false)
  const [excludeCommercial, setExcludeCommercial] = useState(false)
  const [adHocOnly, setAdHocOnly] = useState(false)
  const [status, setStatus] = useState<SearchStatus>('idle')
  const [error, setError] = useState<string | null>(null)
  const [lastResponse, setLastResponse] = useState<NearbyResponse | null>(null)
  const lastSearchRef = useRef<{
    locationMode: CityLocationMode
    addressText: string
    addressPoint: CityPin | null
    pin: CityPin | null
  } | null>(null)

  useEffect(() => {
    onSearchStateChange?.(status)
  }, [status, onSearchStateChange])

  useEffect(() => {
    onPickModeChange?.(locationMode === 'map_pin')
  }, [locationMode, onPickModeChange])

  const runSearch = useCallback(
    async (
      mode: CityLocationMode,
      options?: {
        addressText?: string
        addressPoint?: CityPin | null
        pin?: CityPin | null
      },
    ) => {
      setStatus('loading')
      setError(null)
      onSelectStation?.(null)

      const effectiveAddressText = options?.addressText ?? addressText
      const effectiveAddressPoint = options?.addressPoint ?? addressPoint
      const effectivePin = options?.pin ?? mapPin ?? null

      try {
        const query = {
          minKw,
          maxKw,
          publicOpenOnly,
          excludeCommercial,
          adHocOnly,
          limit: 30,
        }

        let response: NearbyResponse

        if (mode === 'gps') {
          if (!navigator.geolocation) {
            throw new Error('Geolocalización no disponible')
          }
          const position = await new Promise<GeolocationPosition>((resolve, reject) => {
            navigator.geolocation.getCurrentPosition(resolve, reject, {
              enableHighAccuracy: true,
              timeout: 15000,
            })
          })
          response = await fetchNearbyStations({
            ...query,
            lat: position.coords.latitude,
            lon: position.coords.longitude,
            radiusM,
          })
        } else if (mode === 'address') {
          if (effectiveAddressPoint) {
            response = await fetchNearbyStations({
              ...query,
              lat: effectiveAddressPoint.lat,
              lon: effectiveAddressPoint.lon,
              radiusM,
            })
          } else {
            const trimmed = effectiveAddressText.trim()
            if (!trimmed) {
              throw new Error('Indica una dirección o lugar')
            }
            response = await fetchNearbyStations({
              ...query,
              q: trimmed,
              radiusM,
            })
          }
        } else if (mode === 'map_bbox') {
          const bounds = onRequestMapBounds?.()
          if (!bounds) {
            throw new Error('El mapa no está listo; espera un momento e inténtalo de nuevo')
          }
          response = await fetchNearbyStations({
            ...query,
            bbox: bounds,
            limit: 40,
          })
        } else if (mode === 'map_pin') {
          if (!effectivePin) {
            throw new Error('Marca un punto en el mapa')
          }
          response = await fetchNearbyStations({
            ...query,
            lat: effectivePin.lat,
            lon: effectivePin.lon,
            radiusM,
          })
        } else {
          throw new Error('Modo de ubicación no válido')
        }

        setLastResponse(response)
        lastSearchRef.current = {
          locationMode: mode,
          addressText: effectiveAddressText,
          addressPoint: effectiveAddressPoint,
          pin: effectivePin,
        }
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
    [
      addressPoint,
      addressText,
      adHocOnly,
      excludeCommercial,
      mapPin,
      maxKw,
      minKw,
      onRequestMapBounds,
      onResults,
      onSelectStation,
      publicOpenOnly,
      radiusM,
    ],
  )

  useEffect(() => {
    const last = lastSearchRef.current
    if (!last) {
      return
    }
    void runSearch(last.locationMode, {
      addressText: last.addressText,
      addressPoint: last.addressPoint,
      pin: last.pin,
    })
  }, [minKw, maxKw, radiusM, publicOpenOnly, excludeCommercial, adHocOnly, runSearch])

  useEffect(() => {
    if (locationMode === 'map_pin' && mapPin) {
      void runSearch('map_pin', { pin: mapPin })
    }
  }, [mapPin, locationMode, runSearch])

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    void runSearch(locationMode)
  }

  const handleUseGps = () => {
    setLocationMode('gps')
    void runSearch('gps')
  }

  const handleLocationModeChange = (mode: CityLocationMode) => {
    setLocationMode(mode)
    setError(null)
  }

  return (
    <section className="panel search-panel city-panel" aria-labelledby="city-search-heading">
      <h2 id="city-search-heading">En ciudad</h2>
      <p className="panel-hint">Potencia + ubicación + radio. Por defecto 1 km y carga lenta (AC).</p>

      <form className="city-form" onSubmit={handleSubmit}>
        <fieldset className="location-modes" aria-label="Ubicación">
          <legend className="field__label">Ubicación</legend>
          <div className="location-mode-row">
            <label className="location-mode">
              <input
                type="radio"
                name="city-location"
                value="gps"
                checked={locationMode === 'gps'}
                onChange={() => handleLocationModeChange('gps')}
              />
              Cerca de mí
            </label>
            <label className="location-mode">
              <input
                type="radio"
                name="city-location"
                value="address"
                checked={locationMode === 'address'}
                onChange={() => handleLocationModeChange('address')}
              />
              Dirección
            </label>
            <label className="location-mode">
              <input
                type="radio"
                name="city-location"
                value="map_bbox"
                checked={locationMode === 'map_bbox'}
                onChange={() => handleLocationModeChange('map_bbox')}
              />
              Zona mapa
            </label>
            <label className="location-mode">
              <input
                type="radio"
                name="city-location"
                value="map_pin"
                checked={locationMode === 'map_pin'}
                onChange={() => handleLocationModeChange('map_pin')}
              />
              Marcar mapa
            </label>
          </div>
        </fieldset>

        {locationMode === 'address' && (
          <PlaceAutocomplete
            id="city-address"
            label="Dirección o lugar"
            value={addressText}
            placeholder="Hotel, plaza, ciudad…"
            onChange={(value) => {
              setAddressText(value)
              setAddressPoint(null)
            }}
            onSelect={(place) => {
              setAddressPoint({ label: place.label, lat: place.lat, lon: place.lon })
            }}
            disabled={status === 'loading'}
          />
        )}

        {locationMode === 'gps' && (
          <button
            type="button"
            className="btn btn--secondary"
            onClick={handleUseGps}
            disabled={status === 'loading'}
          >
            Buscar cerca de mi ubicación
          </button>
        )}

        {locationMode === 'map_bbox' && (
          <p className="panel-hint">Mueve el mapa a la zona deseada y pulsa buscar.</p>
        )}

        {locationMode === 'map_pin' && (
          <p className="panel-hint">
            {mapPin
              ? `Punto marcado: ${mapPin.label}`
              : 'Toca el mapa para marcar el punto de búsqueda.'}
          </p>
        )}

        <fieldset className="radius-row" aria-label="Radio de búsqueda">
          <legend className="field__label">Radio</legend>
          <div className="chip-row">
            {RADIUS_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={`chip ${radiusM === option.value ? 'chip--active' : ''}`}
                onClick={() => setRadiusM(option.value)}
                disabled={locationMode === 'map_bbox'}
              >
                {option.label}
              </button>
            ))}
          </div>
          {locationMode === 'map_bbox' && (
            <p className="panel-hint">En zona mapa el radio no aplica; se usa el rectángulo visible.</p>
          )}
        </fieldset>

        <fieldset className="access-filters" aria-label="Filtros de acceso">
          <legend className="field__label">Acceso (opcional)</legend>
          <label className="check-row">
            <input
              type="checkbox"
              checked={excludeCommercial}
              onChange={(event) => setExcludeCommercial(event.target.checked)}
            />
            Excluir centros comerciales
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={publicOpenOnly}
              onChange={(event) => setPublicOpenOnly(event.target.checked)}
            />
            Solo acceso abierto
          </label>
          <label className="check-row">
            <input
              type="checkbox"
              checked={adHocOnly}
              onChange={(event) => setAdHocOnly(event.target.checked)}
            />
            Solo pago ad-hoc (tarjeta/NFC)
          </label>
        </fieldset>

        <div className="route-form__actions">
          <button type="submit" className="btn btn--primary" disabled={status === 'loading'}>
            {status === 'loading' ? 'Buscando…' : 'Buscar cargadores'}
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
            {lastResponse.reference_label ?? 'Ubicación seleccionada'}
            {lastResponse.radius_m !== null && ` · radio ${lastResponse.radius_m / 1000} km`}
            · {lastResponse.results.length} cargadores
          </p>
        </div>
      )}

      {status === 'ready' && lastResponse?.results.length === 0 && (
        <p className="route-message">No hay cargadores con esos filtros. Prueba ampliar radio o bajar potencia.</p>
      )}

      {lastResponse && lastResponse.results.length > 0 && (
        <ol className="route-results" aria-label="Cargadores cercanos">
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
                  · {formatDistanceKm(item.distance_km, item.distance_m)}
                  {item.access_class && <> · {item.access_class}</>}
                </p>
                <StationDynamicBadge
                  status={item.station.dynamic_status}
                  priceEurKwh={item.station.dynamic_price_eur_kwh}
                  className="route-result__dynamic station-dynamic"
                />
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
