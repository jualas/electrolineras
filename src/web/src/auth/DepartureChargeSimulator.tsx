import {
  chargingReachFromNominal,
  planningRangeFromNominal,
} from '../vehicle/telemetryProfile'
import { DEFAULT_RESERVE_SOC_PERCENT } from '../vehicle/vehicleProfile'

type DepartureChargeSimulatorProps = {
  liveSocPercent: number
  departureSocPercent: number
  simulateDeparture: boolean
  nominalKm: number | null
  disabled?: boolean
  onSimulateChange: (enabled: boolean) => void
  onDepartureSocChange: (socPercent: number) => void
}

const PRESETS = [80, 90, 100] as const

export function DepartureChargeSimulator({
  liveSocPercent,
  departureSocPercent,
  simulateDeparture,
  nominalKm,
  disabled = false,
  onSimulateChange,
  onDepartureSocChange,
}: DepartureChargeSimulatorProps) {
  const liveSoc = Math.round(liveSocPercent)
  const minSoc = Math.max(5, liveSoc)
  const planKm =
    nominalKm != null
      ? planningRangeFromNominal(nominalKm, departureSocPercent, DEFAULT_RESERVE_SOC_PERCENT)
      : null
  const reachKm =
    nominalKm != null ? chargingReachFromNominal(nominalKm, departureSocPercent) : null
  const simulated = simulateDeparture && Math.abs(departureSocPercent - liveSoc) >= 1

  return (
    <fieldset className="departure-charge" disabled={disabled}>
      <legend className="field__label">Carga antes de salir</legend>
      <label className="field field--checkbox">
        <input
          type="checkbox"
          checked={simulateDeparture}
          onChange={(event) => onSimulateChange(event.target.checked)}
        />
        <span>Simular carga previa al viaje</span>
      </label>

      {simulateDeparture && (
        <>
          <p className="departure-charge__live">
            Ahora en el coche: <strong>{liveSoc} %</strong>
            {simulated && (
              <>
                {' '}
                → al salir: <strong>{Math.round(departureSocPercent)} %</strong>
              </>
            )}
          </p>
          <div className="custom-range vehicle-panel__soc" aria-label="SOC al salir">
            <div className="custom-range__row">
              <label htmlFor="assistant-departure-soc">SOC al salir</label>
              <input
                id="assistant-departure-soc"
                type="range"
                min={minSoc}
                max={100}
                step={1}
                value={Math.max(departureSocPercent, minSoc)}
                onChange={(event) => onDepartureSocChange(Number(event.target.value))}
              />
              <span className="custom-range__value">{Math.round(departureSocPercent)} %</span>
            </div>
          </div>
          <div className="chip-row departure-charge__presets" role="list" aria-label="Presets de carga">
            {PRESETS.filter((preset) => preset >= minSoc).map((preset) => (
              <button
                key={preset}
                type="button"
                role="listitem"
                className={`chip ${Math.round(departureSocPercent) === preset ? 'chip--active' : ''}`}
                onClick={() => onDepartureSocChange(preset)}
              >
                {preset} %
              </button>
            ))}
          </div>
          {planKm != null && (
            <p className="departure-charge__meta">
              Autonomía al salir: plan ~{planKm} km
              {reachKm != null && <> · hasta cargador ≥5 %: ~{reachKm} km</>}
            </p>
          )}
        </>
      )}
    </fieldset>
  )
}

export function departureSocQueryParam(
  simulateDeparture: boolean,
  liveSocPercent: number,
  departureSocPercent: number,
): number | undefined {
  if (!simulateDeparture) {
    return undefined
  }
  if (Math.abs(departureSocPercent - liveSocPercent) < 1) {
    return undefined
  }
  return Math.round(departureSocPercent)
}
