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
}

export function PlaceAutocomplete({
  id,
  label,
  value,
  placeholder,
  onChange,
  onSelect,
  disabled = false,
}: PlaceAutocompleteProps) {
  const [suggestions, setSuggestions] = useState<GeocodeResult[]>([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const debounceRef = useRef<number | null>(null)
  const blurTimeoutRef = useRef<number | null>(null)

  useEffect(() => {
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current)
    }

    const trimmed = value.trim()
    if (trimmed.length < 2) {
      setSuggestions([])
      setOpen(false)
      setLoading(false)
      return
    }

    setLoading(true)
    debounceRef.current = window.setTimeout(() => {
      void fetchGeocodeSuggestions(trimmed)
        .then((results) => {
          setSuggestions(results)
          setOpen(results.length > 0)
        })
        .catch(() => {
          setSuggestions([])
          setOpen(false)
        })
        .finally(() => setLoading(false))
    }, 320)

    return () => {
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current)
      }
    }
  }, [value])

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
  }

  return (
    <div className="place-autocomplete">
      <label className="field" htmlFor={id}>
        <span className="field__label">{label}</span>
        <input
          id={id}
          type="text"
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
      {loading && <span className="place-autocomplete__hint">Buscando…</span>}
      {open && suggestions.length > 0 && (
        <ul id={`${id}-suggestions`} className="place-suggestions" role="listbox">
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
