import { useEffect, useMemo, useState } from 'react'

import { fetchTopOperators } from '../api/meta'
import {
  FALLBACK_OPERATOR_CHIPS,
  formatChargingPreferencesSummary,
  type ChargingPreferencesState,
} from '../charging/chargingPreferences'

type ChargingPreferenceFieldsProps = {
  preferences: ChargingPreferencesState
  onToggleOperator: (operator: string) => void
  onMaxPriceChange: (value: number | null) => void
  disabled?: boolean
}

export function ChargingPreferenceFields({
  preferences,
  onToggleOperator,
  onMaxPriceChange,
  disabled = false,
}: ChargingPreferenceFieldsProps) {
  const [operatorChips, setOperatorChips] = useState<string[]>([...FALLBACK_OPERATOR_CHIPS])

  useEffect(() => {
    let cancelled = false
    fetchTopOperators('ES', 12)
      .then((response) => {
        if (cancelled) {
          return
        }
        const fromApi = response.operators.map((row) => row.operator).filter(Boolean)
        if (fromApi.length > 0) {
          setOperatorChips(fromApi)
        }
      })
      .catch(() => {
        /* fallback chips */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const summary = useMemo(() => formatChargingPreferencesSummary(preferences), [preferences])
  const maxPriceInput =
    preferences.maxPriceEurKwh != null ? String(preferences.maxPriceEurKwh) : ''

  return (
    <fieldset className="charging-preferences" disabled={disabled}>
      <legend className="field__label">Preferencias de carga</legend>
      <p className="charging-preferences__hint">
        Pesos blandos: no descartan paradas, solo priorizan operador y precio REVE en el ranking.
      </p>

      <div className="charging-preferences__operators">
        <span className="field__label">Operador preferido</span>
        <div className="charging-preferences__chips" role="group" aria-label="Operadores preferidos">
          {operatorChips.map((operator) => {
            const selected = preferences.preferredOperators.some(
              (item) => item.toLowerCase() === operator.toLowerCase(),
            )
            return (
              <button
                key={operator}
                type="button"
                className={`charging-preferences__chip${selected ? ' charging-preferences__chip--active' : ''}`}
                aria-pressed={selected}
                onClick={() => onToggleOperator(operator)}
              >
                {operator}
              </button>
            )
          })}
        </div>
      </div>

      <label className="field charging-preferences__price">
        <span className="field__label">Precio máximo preferido (€/kWh)</span>
        <input
          type="number"
          min={0.1}
          max={2}
          step={0.01}
          inputMode="decimal"
          placeholder="Sin límite"
          value={maxPriceInput}
          onChange={(event) => {
            const raw = event.target.value.trim()
            if (!raw) {
              onMaxPriceChange(null)
              return
            }
            const parsed = Number(raw)
            onMaxPriceChange(Number.isFinite(parsed) ? parsed : null)
          }}
        />
      </label>

      {summary ? (
        <p className="charging-preferences__summary" role="status">
          Activo: {summary}
        </p>
      ) : null}
    </fieldset>
  )
}
