import { peakDcKwForPreset, type VehiclePresetId } from '../vehicle/vehiclePresets'

export type RevePlanningOptions = {
  maxChargePowerKw: number
  minDestinationSocPct: number
  minStopArrivalSocPct: number
  maxChargeSocPct: number
  excludeSlowChargers: boolean
  consumptionKwhPer100km: number | null
}

export const DEFAULT_REVE_PLANNING: RevePlanningOptions = {
  maxChargePowerKw: peakDcKwForPreset(undefined),
  minDestinationSocPct: 10,
  minStopArrivalSocPct: 10,
  maxChargeSocPct: 80,
  excludeSlowChargers: true,
  consumptionKwhPer100km: null,
}

export function revePlanningForPreset(presetId?: VehiclePresetId): RevePlanningOptions {
  return {
    ...DEFAULT_REVE_PLANNING,
    maxChargePowerKw: peakDcKwForPreset(presetId),
  }
}

type RevePlanningFieldsProps = {
  options: RevePlanningOptions
  consumptionWhPerKm: number
  onChange: (options: RevePlanningOptions) => void
  disabled?: boolean
}

export function RevePlanningFields({
  options,
  consumptionWhPerKm,
  onChange,
  disabled = false,
}: RevePlanningFieldsProps) {
  const displayConsumption =
    options.consumptionKwhPer100km ?? Math.round((consumptionWhPerKm / 10) * 10) / 10

  return (
    <details className="reve-planning" open>
      <summary className="reve-planning__summary">Ajustes del plan (estilo REVE)</summary>
      <div className="reve-planning__grid">
        <label className="field">
          <span className="field__label">Consumo (kWh/100 km)</span>
          <input
            type="number"
            min={8}
            max={50}
            step={0.1}
            value={displayConsumption}
            disabled={disabled}
            onChange={(event) => {
              const value = Number(event.target.value)
              onChange({
                ...options,
                consumptionKwhPer100km: Number.isFinite(value) ? value : null,
              })
            }}
          />
        </label>
        <label className="field">
          <span className="field__label">Potencia máx. carga (kW)</span>
          <input
            type="number"
            min={11}
            max={350}
            step={1}
            value={options.maxChargePowerKw}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...options, maxChargePowerKw: Number(event.target.value) })
            }
          />
        </label>
        <label className="field">
          <span className="field__label">SOC salida objetivo destino (%)</span>
          <input
            type="number"
            min={0}
            max={50}
            step={1}
            value={options.minDestinationSocPct}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...options, minDestinationSocPct: Number(event.target.value) })
            }
          />
        </label>
        <label className="field">
          <span className="field__label">SOC mín. al llegar a parada (%)</span>
          <input
            type="number"
            min={0}
            max={50}
            step={1}
            value={options.minStopArrivalSocPct}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...options, minStopArrivalSocPct: Number(event.target.value) })
            }
          />
        </label>
        <label className="field">
          <span className="field__label">SOC máx. carga DC (%)</span>
          <input
            type="number"
            min={20}
            max={100}
            step={1}
            value={options.maxChargeSocPct}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...options, maxChargeSocPct: Number(event.target.value) })
            }
          />
        </label>
        <label className="field field--checkbox reve-planning__checkbox">
          <input
            type="checkbox"
            checked={options.excludeSlowChargers}
            disabled={disabled}
            onChange={(event) =>
              onChange({ ...options, excludeSlowChargers: event.target.checked })
            }
          />
          <span>Excluir carga lenta (AC / &lt;50 kW) del plan</span>
        </label>
      </div>
      <p className="panel-hint reve-planning__hint">
        Valores por defecto alineados con mapareve.es: destino 10 %, paradas desde 10 %, carga hasta 80 %.
        La potencia máx. se toma del preset del vehículo (pico DC).
      </p>
    </details>
  )
}

export function revePlanningToQueryParams(options: RevePlanningOptions): Record<string, string> {
  const params: Record<string, string> = {
    max_charge_power_kw: String(options.maxChargePowerKw),
    min_destination_soc_pct: String(options.minDestinationSocPct),
    min_stop_arrival_soc_pct: String(options.minStopArrivalSocPct),
    max_charge_soc_pct: String(options.maxChargeSocPct),
  }
  if (options.excludeSlowChargers) {
    params.exclude_slow_chargers = 'true'
  }
  if (options.consumptionKwhPer100km != null) {
    params.consumption_kwh_per_100km = String(options.consumptionKwhPer100km)
  }
  return params
}
