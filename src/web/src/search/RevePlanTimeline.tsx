import { Battery, BatteryCharging, Car, Clock, Euro, MapPin, User, Zap } from 'lucide-react'

import { stationLabel } from '../api/chargingPlan'
import type { PlannedRouteStopResult, Station } from '../api/types'
import { formatDurationHm, formatEsNumber } from '../charging/formatTrip'
import { StationNavActions } from '../components/navigation/StationNavActions'
import { ReveStatRow } from './ReveStatRow'

type RevePlanTimelineProps = {
  originLabel: string
  originSocPct?: number | null
  stops: PlannedRouteStopResult[]
  selectedStationId?: string | null
  onSelectStation?: (station: Station | null) => void
}

function legSummary(stop: PlannedRouteStopResult): string {
  const parts = [`${formatEsNumber(stop.leg_distance_km, 2)} km`]
  if (stop.leg_driving_minutes != null && stop.leg_driving_minutes > 0) {
    parts.push(formatDurationHm(stop.leg_driving_minutes))
  }
  if (stop.leg_energy_kwh != null) {
    parts.push(`${formatEsNumber(stop.leg_energy_kwh, 2)} kWh`)
  }
  return parts.join(' - ')
}

export function RevePlanTimeline({
  originLabel,
  originSocPct,
  stops,
  selectedStationId,
  onSelectStation,
}: RevePlanTimelineProps) {
  if (stops.length === 0) {
    return null
  }

  return (
    <ol className="reve-timeline" aria-label="Itinerario del viaje">
      <li className="reve-timeline__origin">
        <span className="reve-timeline__origin-badge" aria-hidden>
          <Car size={16} />
        </span>
        <span className="reve-timeline__origin-label">{originLabel}</span>
        {originSocPct != null && (
          <span className="reve-timeline__origin-soc">
            <Battery size={14} aria-hidden /> {originSocPct.toFixed(0)}%
          </span>
        )}
      </li>
      {stops.map((stop, index) => (
        <li key={`${stop.station.id}-${index}`} className="reve-timeline__segment">
          <p className="reve-timeline__leg">{legSummary(stop)}</p>
          <div
            className={`reve-stop-card ${selectedStationId === stop.station.id ? 'reve-stop-card--active' : ''}`}
            data-station-id={stop.station.id}
          >
            <button
              type="button"
              className="reve-stop-card__button"
              onClick={() => onSelectStation?.(stop.station)}
            >
              <div className="reve-stop-card__head">
                <span className="reve-stop-card__badge">{stop.order ?? index + 1}</span>
                <div className="reve-stop-card__title-group">
                  <p className="reve-stop-card__title">{stationLabel(stop.station)}</p>
                  {stop.station.location.address && (
                    <p className="reve-stop-card__address">
                      <MapPin size={12} aria-hidden /> {stop.station.location.address}
                    </p>
                  )}
                </div>
              </div>

              {(stop.operator ?? stop.station.operator) && (
                <ReveStatRow
                  icon={<User size={14} aria-hidden />}
                  label="Operador"
                  value={stop.operator ?? stop.station.operator ?? '—'}
                />
              )}
              <ReveStatRow
                icon={<Clock size={14} aria-hidden />}
                label="Tiempo de recarga estimado"
                value={`~${stop.charge_minutes.toFixed(0)} min`}
              />
              <ReveStatRow
                icon={<BatteryCharging size={14} aria-hidden />}
                label="Recarga recomendada"
                value={`${(stop.recommended_charge_from_pct ?? stop.soc_arrival_pct).toFixed(0)}% → ${(stop.recommended_charge_to_pct ?? stop.soc_departure_pct).toFixed(0)}%`}
              />
              <ReveStatRow
                icon={<Zap size={14} aria-hidden />}
                label="Potencia de recarga"
                value={`${(stop.effective_charge_power_kw ?? stop.station.max_power_kw).toFixed(0)} kW`}
              />
              {stop.estimated_charge_cost_eur != null && (
                <ReveStatRow
                  icon={<Euro size={14} aria-hidden />}
                  label="Coste estimado"
                  value={`~${formatEsNumber(stop.estimated_charge_cost_eur, 2)} €`}
                />
              )}
            </button>
            <StationNavActions
              lat={stop.station.location.lat}
              lon={stop.station.location.lon}
              label={stationLabel(stop.station)}
              compact
            />
          </div>
        </li>
      ))}
    </ol>
  )
}
