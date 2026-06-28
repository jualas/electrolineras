import { useState } from 'react'

import type { GeocodeResult } from '../api/types'
import { PlaceAutocomplete } from './PlaceAutocomplete'

type MapSearchPanelProps = {
  onFocusPlace: (place: GeocodeResult | null) => void
}

export function MapSearchPanel({ onFocusPlace }: MapSearchPanelProps) {
  const [placeText, setPlaceText] = useState('')
  const [selectedPlace, setSelectedPlace] = useState<GeocodeResult | null>(null)

  const handleSelect = (place: GeocodeResult) => {
    setSelectedPlace(place)
    onFocusPlace(place)
  }

  const handleClear = () => {
    setPlaceText('')
    setSelectedPlace(null)
    onFocusPlace(null)
  }

  return (
    <section className="panel search-panel" aria-labelledby="map-search-heading">
      <h2 id="map-search-heading">Mapa peninsular</h2>

      <PlaceAutocomplete
        id="map-place-search"
        label="Buscar lugar"
        value={placeText}
        placeholder="Ciudad, dirección o punto de interés"
        onChange={(value) => {
          setPlaceText(value)
          if (selectedPlace && value.trim() !== selectedPlace.label.trim()) {
            setSelectedPlace(null)
            onFocusPlace(null)
          }
        }}
        onSelect={handleSelect}
      />

      {selectedPlace && (
        <div className="map-place-readout">
          <p className="map-place-readout__label" title={selectedPlace.label}>
            {selectedPlace.label}
          </p>
          <button type="button" className="btn btn--ghost" onClick={handleClear}>
            Quitar marcador
          </button>
        </div>
      )}

      <p className="panel-hint">
        Busca un lugar para centrar el mapa o desplázate manualmente para ver cargadores en la vista actual.
      </p>
    </section>
  )
}
