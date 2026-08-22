import { X } from 'lucide-react'

import type { GeocodeResult } from '../api/types'
import { PlaceAutocomplete } from '../search/PlaceAutocomplete'

type MapFloatingSearchProps = {
  value: string
  focusPlace: GeocodeResult | null
  onChange: (value: string) => void
  onSelect: (place: GeocodeResult) => void
  onClear: () => void
}

export function MapFloatingSearch({
  value,
  focusPlace,
  onChange,
  onSelect,
  onClear,
}: MapFloatingSearchProps) {
  return (
    <div className="map-floating-search" role="search">
      <PlaceAutocomplete
        id="map-floating-place-search"
        label="Buscar lugar"
        variant="floating"
        value={value}
        placeholder="Ciudad, dirección o lugar…"
        onChange={onChange}
        onSelect={onSelect}
      />
      {(focusPlace || value.trim()) && (
        <button
          type="button"
          className="map-floating-search__clear"
          onClick={onClear}
          aria-label="Limpiar búsqueda"
        >
          <X size={16} aria-hidden />
        </button>
      )}
    </div>
  )
}
