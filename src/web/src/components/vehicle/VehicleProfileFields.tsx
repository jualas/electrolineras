import {
  DEFAULT_RESERVE_SOC_PERCENT,
  estimateChargingReachKm,
  estimateDisplayedRangeKm,
  estimatePlanningRangeKm,
  formatVehicleSummary,
  SOC_MAX,
  SOC_MIN,
  type VehicleProfile,
} from '../../vehicle/vehicleProfile'
import {
  getVehiclePreset,
  VEHICLE_PRESETS,
  type VehiclePresetId,
} from '../../vehicle/vehiclePresets'

type VehicleProfileFieldsProps = {
  profile: VehicleProfile
  onPresetChange: (presetId: VehiclePresetId) => void
  onSocChange: (socPercent: number) => void
  onConsumptionChange: (consumptionWhPerKm: number) => void
  variant?: 'full' | 'compact' | 'advanced' | 'assistant'
  socReadOnly?: boolean
  socSourceLabel?: string
}

export function VehicleProfileFields({
  profile,
  onPresetChange,
  onSocChange,
  onConsumptionChange,
  variant = 'full',
  socReadOnly = false,
  socSourceLabel,
}: VehicleProfileFieldsProps) {
  const preset = getVehiclePreset(profile.presetId)
  const displayedRangeKm = estimateDisplayedRangeKm(profile, preset)
  const planningRangeKm = estimatePlanningRangeKm(profile, preset)
  const chargingReachKm = estimateChargingReachKm(profile, preset)
  const summary = formatVehicleSummary(profile)
  const compact = variant === 'compact'
  const advanced = variant === 'advanced'
  const assistant = variant === 'assistant'

  if (advanced) {
    return (
      <>
        <div className="field">
          <label className="field__label" htmlFor="vehicle-consumption-adv">
            Consumo (Wh/km)
          </label>
          <input
            id="vehicle-consumption-adv"
            type="number"
            min={80}
            max={350}
            step={1}
            value={profile.consumptionWhPerKm}
            onChange={(event) => onConsumptionChange(Number(event.target.value))}
          />
          <p className="vehicle-panel__hint">
            Referencia {preset.referenceWhPerKm} Wh/km · {preset.ratedRangeKm} km al 100 % ·{' '}
            {preset.usableCapacityKwh} kWh útil
          </p>
        </div>
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
          Cuadro ~{displayedRangeKm} km · plan reserva {DEFAULT_RESERVE_SOC_PERCENT} % (~{planningRangeKm} km) · hasta
          cargador ≥5 % (~{chargingReachKm} km).
        </p>
      )}

      {assistant && (
        <p className="panel-hint">
          SOC y posición desde TeslaMate (arriba). Aquí ajustas modelo y consumo para el cálculo.
        </p>
      )}

      {compact && (
        <p className="charge-vehicle-summary" title={summary}>
          ~{displayedRangeKm} km · hasta cargador ~{chargingReachKm} km
        </p>
      )}

      <div className="field">
        <label className="field__label" htmlFor="vehicle-preset">
          Modelo
        </label>
        <select
          id="vehicle-preset"
          value={profile.presetId}
          onChange={(event) => onPresetChange(event.target.value as VehiclePresetId)}
        >
          {VEHICLE_PRESETS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label} · {item.ratedRangeKm} km · {item.usableCapacityKwh} kWh
            </option>
          ))}
        </select>
      </div>

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

      {!compact && (
        <>
          <div className="field">
            <label className="field__label" htmlFor="vehicle-consumption">
              Consumo (Wh/km)
            </label>
            <input
              id="vehicle-consumption"
              type="number"
              min={80}
              max={350}
              step={1}
              value={profile.consumptionWhPerKm}
              onChange={(event) => onConsumptionChange(Number(event.target.value))}
            />
            <p className="vehicle-panel__hint">
              Referencia {preset.referenceWhPerKm} Wh/km · {preset.ratedRangeKm} km al 100 % ·{' '}
              {preset.usableCapacityKwh} kWh útil
            </p>
          </div>
        </>
      )}
    </>
  )
}
