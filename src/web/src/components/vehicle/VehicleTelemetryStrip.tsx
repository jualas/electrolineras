import type { VehicleTelemetryResult } from '../../api/types'
import {
  currentRangeFromNominal,
  formatTelemetrySummary,
  nominalRangeKm,
} from '../../vehicle/telemetryProfile'
import { DEFAULT_RESERVE_SOC_PERCENT } from '../../vehicle/vehicleProfile'

type VehicleTelemetryStripProps = {
  vehicle: VehicleTelemetryResult | null
  loading?: boolean
  error?: string | null
  onRefresh?: () => void
  compact?: boolean
}

export function VehicleTelemetryStrip({
  vehicle,
  loading = false,
  error = null,
  onRefresh,
  compact = false,
}: VehicleTelemetryStripProps) {
  const summary =
    vehicle != null ? formatTelemetrySummary(vehicle, DEFAULT_RESERVE_SOC_PERCENT) : null
  const nominalKm = vehicle != null ? nominalRangeKm(vehicle) : null
  const currentKm = vehicle != null ? currentRangeFromNominal(vehicle) : null

  return (
    <div className={`telemetry-strip${compact ? ' telemetry-strip--compact' : ''}`} role="status">
      <div className="telemetry-strip__header">
        <span className="telemetry-strip__badge">TeslaMate</span>
        {vehicle && (
          <span className="telemetry-strip__title">
            {vehicle.display_name ?? `Coche ${vehicle.car_id}`}
            {vehicle.car_model_label ? ` · ${vehicle.car_model_label}` : ''}
          </span>
        )}
        {onRefresh && (
          <button
            type="button"
            className="telemetry-strip__refresh btn btn--ghost"
            onClick={onRefresh}
            disabled={loading}
          >
            {loading ? 'Actualizando…' : 'Actualizar'}
          </button>
        )}
      </div>

      {error && <p className="telemetry-strip__error">{error}</p>}

      {vehicle && (
        <ul className="telemetry-strip__stats">
          <li>
            <strong>{vehicle.battery_level_pct.toFixed(0)} %</strong> SOC
          </li>
          {currentKm != null && (
            <li>
              ~{Math.round(currentKm)} km ahora
            </li>
          )}
          {nominalKm != null && !compact && (
            <li className="telemetry-strip__muted">Nominal 100 %: ~{Math.round(nominalKm)} km</li>
          )}
          {vehicle.charging_state && (
            <li className="telemetry-strip__muted">Carga: {vehicle.charging_state}</li>
          )}
        </ul>
      )}

      {summary && !compact && (
        <p className="telemetry-strip__summary" title={summary}>
          {summary}
        </p>
      )}

      {loading && !vehicle && !error && (
        <p className="telemetry-strip__muted">Leyendo telemetría MQTT…</p>
      )}
    </div>
  )
}
