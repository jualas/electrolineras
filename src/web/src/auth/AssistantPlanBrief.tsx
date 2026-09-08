import { useState } from 'react'
import { Navigation2 } from 'lucide-react'

import { stationLabel } from '../api/chargingPlan'
import type { ChargingPlanResponse, Station } from '../api/types'
import { formatDurationHm, formatEsNumber } from '../charging/formatTrip'
import { isChargingPlanComplete, routeChargingStops, routeExportSpecFromChargingPlan } from '../charging/planRouteStops'
import { googleMapsRouteUrl } from '../navigation/externalMaps'

type AssistantPlanBriefProps = {
  plan: ChargingPlanResponse
  originLabel?: string | null
  destinationLabel?: string | null
  selectedStationId?: string | null
  onSelectStation?: (station: Station | null) => void
}

/**
 * Vista mínima para el Asistente: una línea útil + Maps + lista compacta colapsable.
 * El detalle REVE/timeline vive en la pestaña de planificador, no aquí.
 */
export function AssistantPlanBrief({
  plan,
  originLabel,
  destinationLabel,
  selectedStationId,
  onSelectStation,
}: AssistantPlanBriefProps) {
  const [showStops, setShowStops] = useState(false)
  const planned = plan.planned_stops ?? []
  const stops = planned.length > 0 ? planned : routeChargingStops(plan)
  const summary = plan.route_trip_summary
  const complete = isChargingPlanComplete(plan)
  const exportSpec = routeExportSpecFromChargingPlan(plan)
  const googleUrl = exportSpec
    ? googleMapsRouteUrl({
        origin: exportSpec.origin,
        destination: exportSpec.destination,
        waypoints: exportSpec.waypoints,
      })
    : null

  const bits: string[] = []
  if (plan.route_distance_km != null) {
    bits.push(`${formatEsNumber(plan.route_distance_km, 0)} km`)
  }
  if (summary) {
    bits.push(formatDurationHm(summary.total_duration_minutes))
    if (summary.stop_count > 0) {
      bits.push(`${summary.stop_count} parada${summary.stop_count === 1 ? '' : 's'}`)
    }
    if (summary.projected_destination_soc_pct != null) {
      bits.push(`llegada ~${summary.projected_destination_soc_pct.toFixed(0)} %`)
    }
  } else if (planned.length > 0) {
    bits.push(`${planned.length} parada${planned.length === 1 ? '' : 's'}`)
  }

  return (
    <div className="assistant-plan-brief">
      {(originLabel || destinationLabel) && (
        <p className="assistant-plan-brief__route">
          {[originLabel, destinationLabel].filter(Boolean).join(' → ')}
        </p>
      )}
      <div className="assistant-plan-brief__row">
        <p className="assistant-plan-brief__meta">{bits.join(' · ') || 'Plan listo en el mapa'}</p>
        {googleUrl && (
          <a
            className="btn btn--secondary assistant-plan-brief__maps"
            href={googleUrl}
            target="_blank"
            rel="noopener noreferrer"
          >
            <Navigation2 size={16} aria-hidden />
            Maps
          </a>
        )}
      </div>

      {!complete && planned.length > 0 && (
        <p className="route-message route-message--error" role="alert">
          Plan incompleto: puede no llegar. Ajusta preferencias en el chat.
        </p>
      )}
      {planned.length === 0 && !plan.reachable_without_stop && (
        <p className="route-message route-message--error" role="alert">
          No hay plan multi-parada. Prueba «evitar peajes», menos kW o cargar antes.
        </p>
      )}
      {plan.reachable_without_stop && planned.length === 0 && (
        <p className="route-message">Llegas sin parar a cargar.</p>
      )}

      {stops.length > 0 && (
        <>
          <button
            type="button"
            className="assistant-plan-brief__toggle"
            onClick={() => setShowStops((prev) => !prev)}
            aria-expanded={showStops}
          >
            {showStops ? 'Ocultar paradas' : `Ver ${stops.length} parada${stops.length === 1 ? '' : 's'}`}
          </button>
          {showStops && (
            <ol className="assistant-plan-brief__stops">
              {stops.map((stop, index) => {
                const station = stop.station
                const order = 'order' in stop && stop.order != null ? stop.order : index + 1
                const arrival = stop.soc_arrival_pct
                const departure = 'soc_departure_pct' in stop ? stop.soc_departure_pct : null
                const charge =
                  'charge_minutes' in stop && typeof stop.charge_minutes === 'number'
                    ? stop.charge_minutes
                    : null
                const active = selectedStationId === station.id
                return (
                  <li key={`${station.id}-${order}`}>
                    <button
                      type="button"
                      className={`assistant-plan-brief__stop${active ? ' assistant-plan-brief__stop--active' : ''}`}
                      onClick={() => onSelectStation?.(station)}
                    >
                      <span className="assistant-plan-brief__stop-order">{order}</span>
                      <span className="assistant-plan-brief__stop-body">
                        <strong>{stationLabel(station)}</strong>
                        <span>
                          {arrival.toFixed(0)}%
                          {departure != null ? `→${departure.toFixed(0)}%` : ''}
                          {charge != null && charge > 0 ? ` · ~${charge.toFixed(0)} min` : ''}
                          {` · ${station.max_power_kw.toFixed(0)} kW`}
                        </span>
                      </span>
                    </button>
                  </li>
                )
              })}
            </ol>
          )}
        </>
      )}
    </div>
  )
}
