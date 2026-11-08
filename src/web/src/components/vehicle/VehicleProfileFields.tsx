import { useState } from 'react'

import { useVehicleGarage } from '../../hooks/useVehicleProfile'
import {
  DEFAULT_RESERVE_SOC_PERCENT,
  estimateChargingReachKm,
  estimateDisplayedRangeKm,
  estimatePlanningRangeKm,
  formatConsumptionBreakdown,
  formatVehicleSummary,
  SOC_MAX,
  SOC_MIN,
  type VehicleProfile,
} from '../../vehicle/vehicleProfile'
import { GarageEditor } from './GarageEditor'

type VehicleProfileFieldsProps = {
  profile: VehicleProfile
  onSocChange: (socPercent: number) => void
  variant?: 'full' | 'compact' | 'advanced' | 'assistant'
  socReadOnly?: boolean
  socSourceLabel?: string
}

export function VehicleProfileFields({
  profile,
  onSocChange,
  variant = 'full',
  socReadOnly = false,
  socSourceLabel,
}: VehicleProfileFieldsProps) {
  const { garage, selectVehicle } = useVehicleGarage()
  const [garageOpen, setGarageOpen] = useState(false)
  const displayedRangeKm = estimateDisplayedRangeKm(profile)
  const planningRangeKm = estimatePlanningRangeKm(profile)
  const chargingReachKm = estimateChargingReachKm(profile)
  const summary = formatVehicleSummary(profile)
  const compact = variant === 'compact'
  const advanced = variant === 'advanced'
  const assistant = variant === 'assistant'

  const consumptionHint = (
    <p className="vehicle-panel__hint">
      {formatConsumptionBreakdown(profile)} · {profile.usableCapacityKwh} kWh útil · {profile.peakDcKw} kW DC
    </p>
  )

  if (advanced) {
    return (
      <>
        {consumptionHint}
        {garageOpen ? (
          <GarageEditor onClose={() => setGarageOpen(false)} />
        ) : (
          <button type="button" className="btn btn--ghost btn--compact" onClick={() => setGarageOpen(true)}>
            Editar vehículos y perfil de conducción
          </button>
        )}
      </>
    )
  }

  return (
    <>
      {!compact && !assistant && (
        <p className="vehicle-panel__summary" title={summary}>
          {summary}
        </p>
      )}
      {!compact && !assistant && (
        <p className="panel-hint">
          Total ~{displayedRangeKm} km · plan reserva {DEFAULT_RESERVE_SOC_PERCENT} % (~{planningRangeKm} km) · hasta
          cargador ≥5 % (~{chargingReachKm} km).
        </p>
      )}

      {assistant && (
        <p className="panel-hint">
          SOC y posición desde TeslaMate (arriba). Aquí eliges el vehículo y su consumo para el cálculo.
        </p>
      )}

      {compact && (
        <p className="charge-vehicle-summary" title={summary}>
          ~{displayedRangeKm} km · hasta cargador ~{chargingReachKm} km
        </p>
      )}

      <div className="field">
        <label className="field__label" htmlFor="vehicle-select">
          Vehículo
        </label>
        <div className="vehicle-select-row">
          <select
            id="vehicle-select"
            value={profile.vehicleId}
            onChange={(event) => selectVehicle(event.target.value)}
          >
            {garage.vehicles.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name} · {item.usableCapacityKwh} kWh
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn--ghost btn--compact"
            aria-expanded={garageOpen}
            onClick={() => setGarageOpen((open) => !open)}
          >
            Garaje
          </button>
        </div>
      </div>

      {garageOpen && <GarageEditor onClose={() => setGarageOpen(false)} />}

      <div className="custom-range vehicle-panel__soc" aria-label="Estado de carga">
        {!assistant && socReadOnly ? (
          <p className="vehicle-panel__live-soc">
            Batería: <strong>{profile.socPercent} %</strong>
            {socSourceLabel ? (
              <span className="vehicle-panel__live-soc-source"> · {socSourceLabel}</span>
            ) : null}
          </p>
        ) : (
          !assistant && (
            <div className="custom-range__row">
              <label htmlFor="vehicle-soc">Batería (SOC)</label>
              <input
                id="vehicle-soc"
                type="range"
                min={SOC_MIN}
                max={SOC_MAX}
                step={1}
                value={profile.socPercent}
                onChange={(event) => onSocChange(Number(event.target.value))}
              />
              <span className="custom-range__value">{profile.socPercent} %</span>
            </div>
          )
        )}
      </div>

      {!compact && consumptionHint}
    </>
  )
}
