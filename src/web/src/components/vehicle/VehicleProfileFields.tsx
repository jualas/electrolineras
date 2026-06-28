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
  TERRAIN_FACTORS,
  VEHICLE_PRESETS,
  type TerrainFactorId,
  type VehiclePresetId,
} from '../../vehicle/vehiclePresets'

type VehicleProfileFieldsProps = {
  profile: VehicleProfile
  onPresetChange: (presetId: VehiclePresetId) => void
  onSocChange: (socPercent: number) => void
  onConsumptionChange: (consumptionWhPerKm: number) => void
  onTerrainChange: (terrainFactorId: TerrainFactorId) => void
  variant?: 'full' | 'compact' | 'advanced'
}

export function VehicleProfileFields({
  profile,
  onPresetChange,
  onSocChange,
  onConsumptionChange,
  onTerrainChange,
  variant = 'full',
}: VehicleProfileFieldsProps) {
  const preset = getVehiclePreset(profile.presetId)
  const displayedRangeKm = estimateDisplayedRangeKm(profile, preset)
  const planningRangeKm = estimatePlanningRangeKm(profile, preset)
  const chargingReachKm = estimateChargingReachKm(profile, preset)
  const summary = formatVehicleSummary(profile)
  const compact = variant === 'compact'
  const advanced = variant === 'advanced'

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

        <div className="vehicle-panel__terrain">
          <span className="field__label">Terreno</span>
          <div className="chip-row" role="list" aria-label="Factor de terreno">
            {TERRAIN_FACTORS.map((terrain) => (
              <button
                key={terrain.id}
                type="button"
                role="listitem"
                className={`chip ${profile.terrainFactorId === terrain.id ? 'chip--active' : ''}`}
                onClick={() => onTerrainChange(terrain.id)}
                aria-pressed={profile.terrainFactorId === terrain.id}
                title={terrain.hint}
              >
                {terrain.label}
              </button>
            ))}
          </div>
        </div>
      </>
    )
  }

  return (
    <>
      {!compact && (
        <p className="vehicle-panel__summary" title={summary}>
          {summary}
        </p>
      )}
      {!compact && (
        <p className="panel-hint">
          Cuadro ~{displayedRangeKm} km · plan reserva {DEFAULT_RESERVE_SOC_PERCENT} % (~{planningRangeKm} km) · hasta
          cargador ≥5 % (~{chargingReachKm} km).
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

          <div className="vehicle-panel__terrain">
            <span className="field__label">Terreno</span>
            <div className="chip-row" role="list" aria-label="Factor de terreno">
              {TERRAIN_FACTORS.map((terrain) => (
                <button
                  key={terrain.id}
                  type="button"
                  role="listitem"
                  className={`chip ${profile.terrainFactorId === terrain.id ? 'chip--active' : ''}`}
                  onClick={() => onTerrainChange(terrain.id)}
                  aria-pressed={profile.terrainFactorId === terrain.id}
                  title={terrain.hint}
                >
                  {terrain.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </>
  )
}
