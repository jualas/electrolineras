import { useEffect, useRef, useState } from 'react'

import { fetchGeocodeSuggestions } from '../api/route'
import type { GeocodeResult } from '../api/types'

type PlaceAutocompleteProps = {
  id: string
  label: string
  value: string
  placeholder?: string
  onChange: (value: string) => void
  onSelect: (place: GeocodeResult) => void
  disabled?: boolean
  variant?: 'default' | 'floating'
  /** Si `value` coincide con esta etiqueta (p. ej. "Mi casa"), ya apunta a un punto fijo
   *  resuelto de antemano: no busca sugerencias hasta que el usuario escriba otra cosa. */
  anchorLabel?: string
}

export function PlaceAutocomplete({
  id,
  label,
  value,
  placeholder,
  onChange,
  onSelect,
  disabled = false,
  variant = 'default',
  anchorLabel,
}: PlaceAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<GeocodeResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const debounceRef = useRef<number | null>(null)
  const blurTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current)
    }

    const trimmed = value.trim()
    if (trimmed.length < 2 || trimmed === anchorLabel) {
      setSuggestions([])
      setOpen(false)
      setLoading(false)
      setError(null)
      return
    }

    setLoading(true)
    setError(null)
    debounceRef.current = window.setTimeout(() => {
      void fetchGeocodeSuggestions(trimmed)
        .then((results) => {
          setSuggestions(results)
          setOpen(results.length > 0)
          setError(results.length > 0 ? null : 'No se encontraron lugares para esa búsqueda.')
        })
        .catch((caught: unknown) => {
          setSuggestions([])
          setOpen(false)
          const message =
            caught instanceof Error && caught.message
              ? caught.message
              : 'No se pudo buscar la ubicación. Comprueba la conexión con la API.'
          setError(message)
        })
        .finally(() => setLoading(false))
    }, 320)

    return () => {
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current)
      }
    }
  }, [value, anchorLabel])

  const handleBlur = () => {
    blurTimeoutRef.current = window.setTimeout(() => setOpen(false), 150)
  }

  const handleFocus = () => {
    if (blurTimeoutRef.current !== null) {
      window.clearTimeout(blurTimeoutRef.current)
    }
    if (suggestions.length > 0) {
      setOpen(true)
    }
  }

  const handlePick = (place: GeocodeResult) => {
    onChange(place.label)
    onSelect(place)
    setOpen(false)
    setError(null)
  }

  return (
    <div className={`place-autocomplete${variant === 'floating' ? ' place-autocomplete--floating' : ''}`}>
      {variant === 'default' && (
        <label className="field" htmlFor={id}>
          <span className="field__label">{label}</span>
          <input
            id={id}
            type="search"
            className="place-autocomplete__input"
            value={value}
            placeholder={placeholder}
            autoComplete="off"
            disabled={disabled}
            onChange={(event) => onChange(event.target.value)}
            onFocus={handleFocus}
            onBlur={handleBlur}
            aria-autocomplete="list"
            aria-expanded={open}
            aria-controls={`${id}-suggestions`}
          />
        </label>
      )}
      {variant === 'floating' && (
        <input
          id={id}
          type="search"
          className="place-autocomplete__input place-autocomplete__input--floating"
          value={value}
          placeholder={placeholder ?? label}
          autoComplete="off"
          disabled={disabled}
          onChange={(event) => onChange(event.target.value)}
          onFocus={handleFocus}
          onBlur={handleBlur}
          aria-label={label}
          aria-autocomplete="list"
          aria-expanded={open}
          aria-controls={`${id}-suggestions`}
        />
      )}
      {loading && <span className="place-autocomplete__hint">Buscando…</span>}
      {!loading && error && !open && (
        <span className="place-autocomplete__error" role="alert">
          {error}
        </span>
      )}
      {open && suggestions.length > 0 && (
        <ul
          id={`${id}-suggestions`}
          className={`place-suggestions${variant === 'floating' ? ' place-suggestions--floating' : ''}`}
          role="listbox"
        >
          {suggestions.map((place) => (
            <li key={`${place.lat},${place.lon},${place.label}`} role="option">
              <button
                type="button"
                className="place-suggestion"
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => handlePick(place)}
              >
                {place.label}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
