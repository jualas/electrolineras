import { MapPin, Navigation, Plus, Trash2 } from 'lucide-react'

import type { GeocodeResult } from '../api/types'
import { PlaceAutocomplete } from './PlaceAutocomplete'

export type ItineraryPoint = {
  label: string
  lat: number
  lon: number
}

export type ItineraryStopDraft = {
  id: string
  text: string
  point: ItineraryPoint | null
}

type ItineraryFieldsProps = {
  originText: string
  originPoint: ItineraryPoint | null
  originAnchorLabel?: string
  vehicleOrigin?: ItineraryPoint | null
  gpsOrigin?: ItineraryPoint | null
  originSource: 'car' | 'gps' | 'manual'
  onOriginChange: (text: string) => void
  onOriginSelect: (place: GeocodeResult) => void
  onUseVehicleOrigin?: () => void
  onUseGpsOrigin?: () => void
  onUseHomeOrigin?: () => void
  onEditOriginManual?: () => void
  stops: ItineraryStopDraft[]
  onStopChange: (id: string, text: string) => void
  onStopSelect: (id: string, place: GeocodeResult) => void
  onAddStop: () => void
  onRemoveStop: (id: string) => void
  disabled?: boolean
  hideDestination?: boolean
}

function newStopId(): string {
  return `stop-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

export function createEmptyStop(): ItineraryStopDraft {
  return { id: newStopId(), text: '', point: null }
}

export function ItineraryFields({
  originText,
  originPoint,
  originAnchorLabel,
  vehicleOrigin,
  gpsOrigin,
  originSource,
  onOriginChange,
  onOriginSelect,
  onUseVehicleOrigin,
  onUseGpsOrigin,
  onUseHomeOrigin,
  onEditOriginManual,
  stops,
  onStopChange,
  onStopSelect,
  onAddStop,
  onRemoveStop,
  disabled = false,
  hideDestination = false,
}: ItineraryFieldsProps) {
  const originReadOnly = originSource === 'car' || originSource === 'gps'
  const originDisplay =
    originSource === 'car' && vehicleOrigin
      ? vehicleOrigin.label
      : originSource === 'gps' && gpsOrigin
        ? gpsOrigin.label
        : originText

  return (
    <div className="itinerary-fields" aria-label="Itinerario del viaje">
      <div className="itinerary-fields__row">
        <span className="itinerary-fields__badge" aria-hidden>
          A
        </span>
        <div className="itinerary-fields__body">
          {originReadOnly ? (
            <div className="field">
              <span className="field__label">Inicio</span>
              <p className="itinerary-fields__readout" title={originDisplay}>
                {originDisplay}
                {originPoint && (
                  <span className="itinerary-fields__coords">
                    {' '}
                    · {originPoint.lat.toFixed(4)}, {originPoint.lon.toFixed(4)}
                  </span>
                )}
              </p>
            </div>
          ) : (
            <PlaceAutocomplete
              id="itinerary-origin"
              label="Inicio"
              value={originText}
              placeholder="Ciudad, dirección o punto de salida"
              onChange={onOriginChange}
              onSelect={onOriginSelect}
              disabled={disabled}
              anchorLabel={originAnchorLabel}
            />
          )}
          <div className="itinerary-fields__shortcuts" role="group" aria-label="Origen rápido">
            {onUseVehicleOrigin && vehicleOrigin && (
              <button
                type="button"
                className={`chip chip--compact ${originSource === 'car' ? 'chip--active' : ''}`}
                aria-pressed={originSource === 'car'}
                disabled={disabled}
                onClick={onUseVehicleOrigin}
                title="Usar posición actual del vehículo (TeslaMate)"
              >
                <Navigation size={14} aria-hidden /> Ubicación del vehículo
              </button>
            )}
            {onUseGpsOrigin && (
              <button
                type="button"
                className={`chip chip--compact ${originSource === 'gps' ? 'chip--active' : ''}`}
                aria-pressed={originSource === 'gps'}
                disabled={disabled}
                onClick={onUseGpsOrigin}
              >
                <MapPin size={14} aria-hidden /> GPS
              </button>
            )}
            {onUseHomeOrigin && (
              <button
                type="button"
                className={`chip chip--compact ${originSource === 'manual' && originText === originAnchorLabel ? 'chip--active' : ''}`}
                aria-pressed={originSource === 'manual' && originText === originAnchorLabel}
                disabled={disabled}
                onClick={onUseHomeOrigin}
              >
                Mi casa
              </button>
            )}
            {originSource !== 'manual' && onEditOriginManual && (
              <button type="button" className="chip chip--compact" disabled={disabled} onClick={onEditOriginManual}>
                Escribir dirección
              </button>
            )}
          </div>
        </div>
      </div>

      {!hideDestination &&
        stops.map((stop, index) => {
          const isLast = index === stops.length - 1
          const label = isLast && stops.length === 1 ? 'Destino' : isLast ? `Destino final` : `Parada ${index + 1}`
          const badge = String.fromCharCode(66 + index) // B, C, D…
          return (
            <div key={stop.id} className="itinerary-fields__row">
              <span className="itinerary-fields__badge" aria-hidden>
                {badge}
              </span>
              <div className="itinerary-fields__body itinerary-fields__body--stop">
                <PlaceAutocomplete
                  id={`itinerary-stop-${stop.id}`}
                  label={label}
                  value={stop.text}
                  placeholder={isLast ? 'Ciudad o dirección de destino' : 'Ciudad o dirección de paso'}
                  onChange={(text) => onStopChange(stop.id, text)}
                  onSelect={(place) => onStopSelect(stop.id, place)}
                  disabled={disabled}
                />
                {stops.length > 1 && (
                  <button
                    type="button"
                    className="itinerary-fields__remove"
                    aria-label={`Quitar ${label.toLowerCase()}`}
                    disabled={disabled}
                    onClick={() => onRemoveStop(stop.id)}
                  >
                    <Trash2 size={16} aria-hidden />
                  </button>
                )}
              </div>
            </div>
          )
        })}

      {!hideDestination && (
        <button
          type="button"
          className="itinerary-fields__add"
          disabled={disabled}
          onClick={onAddStop}
        >
          <Plus size={16} aria-hidden /> Añadir parada
        </button>
      )}
    </div>
  )
}
