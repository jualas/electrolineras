import type { ChargingPlanResponse, PlannedRouteStopResult } from '../api/types'
import {
  classificationClassName,
  formatClassificationLabel,
} from '../charging/classificationDisplay'
import { googleMapsRouteUrl } from '../navigation/externalMaps'
import { avoidTollsLabel, formatRouteAlternativesKm } from './RoutePreferenceFields'
import { ChargingStopList } from './ChargingStopList'

type ChargingPlanResultsProps = {
  plan: ChargingPlanResponse
  selectedStationId?: string | null
  onSelectStation?: (station: import('../api/types').Station | null) => void
  variant?: 'full' | 'assistant'
}

function plannedStopDistanceLabel(stop: PlannedRouteStopResult): string {
  return `${stop.distance_from_origin_km.toFixed(0)} km · tramo ${stop.leg_distance_km.toFixed(0)} km · ${stop.soc_arrival_pct.toFixed(0)}→${stop.soc_departure_pct.toFixed(0)} % · ~${stop.charge_minutes.toFixed(0)} min`
}

export function ChargingPlanResults({
  plan,
  selectedStationId,
  onSelectStation,
  variant = 'full',
}: ChargingPlanResultsProps) {
  const assistant = variant === 'assistant'
  const plannedStops = plan.planned_stops ?? []
  const hasPlannedRoute =
    plan.mode === 'route' && plan.destination != null && plannedStops.length > 0

  return (
    <>
      {!assistant && plan.warnings.length > 0 && (
        <ul className="charge-warnings" aria-label="Alertas del plan">
          {plan.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}

      <div className="charge-summary">
        <p className="route-summary__meta">
          {plan.mode === 'emergency' ? (
            <>
              Modo emergencia · hasta cargador {plan.charging_reach_km} km
              {plan.route_distance_km != null && (
                <> · ruta al más cercano {plan.route_distance_km.toFixed(1)} km</>
              )}
            </>
          ) : (
            <>
              {formatRouteAlternativesKm(plan)}
              {' · '}
              Hasta cargador {plan.charging_reach_km} km
              {plan.range_km < plan.charging_reach_km && <> · plan reserva {plan.range_km} km</>}
              {plan.reachable_without_stop ? ' · llegas sin parar' : ''}
              {avoidTollsLabel(plan.avoid_highways)}
              {plan.soc_at_destination_pct != null && !plan.reachable_without_stop && (
                <>
                  {' · '}
                  {plan.soc_at_destination_pct <= 0
                    ? 'sin paradas: batería agotada antes del destino'
                    : `~${plan.soc_at_destination_pct.toFixed(0)} % SOC al destino (directo)`}
                </>
              )}
              {plan.projected_soc_at_destination_with_plan != null && plannedStops.length > 0 && (
                <>
                  {' · '}
                  ~{plan.projected_soc_at_destination_with_plan.toFixed(0)} % con {plannedStops.length}{' '}
                  parada{plannedStops.length === 1 ? '' : 's'}
                </>
              )}
            </>
          )}
        </p>
      </div>

      {!assistant && hasPlannedRoute && (
        <div className="route-export">
          <a
            className="btn btn--ghost"
            href={googleMapsRouteUrl({
              origin: plan.origin,
              destination: plan.destination!,
              waypoints: plannedStops.map((stop) => stop.station.location),
            })}
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir paradas planificadas en Google Maps
          </a>
        </div>
      )}

      {!assistant && plan.strategies.length > 0 && (
        <div className="charge-strategies" aria-label="Estrategias recomendadas">
          {plan.strategies.map((strategy) => (
            <article
              key={strategy.id}
              className={`charge-strategy ${strategy.station_id ? '' : 'charge-strategy--empty'}`}
            >
              <h3 className="charge-strategy__title">{strategy.label}</h3>
              <p className="charge-strategy__summary">{strategy.summary}</p>
              {strategy.classification && (
                <span className={classificationClassName(strategy.classification, 'charging-class')}>
                  {formatClassificationLabel(strategy.classification)}
                  {strategy.soc_arrival_pct != null && <> · {strategy.soc_arrival_pct.toFixed(0)} % SOC</>}
                </span>
              )}
            </article>
          ))}
        </div>
      )}

      {plan.mode === 'emergency' ? (
        <>
          {plan.stops.some((stop) => stop.classification !== 'unreachable') && (
            <>
              <h3 className="charge-section-title">Alcanzables desde tu posición</h3>
              <ChargingStopList
                stops={plan.stops.filter((stop) => stop.classification !== 'unreachable')}
                selectedStationId={selectedStationId}
                onSelectStation={onSelectStation}
                ariaLabel="Cargadores alcanzables"
                showRouteDeviation={false}
                distanceLabel={(item) => `${item.distance_from_origin_km.toFixed(1)} km desde la salida`}
              />
            </>
          )}
        </>
      ) : (
        <>
          {plannedStops.length > 0 && (
            <>
              <h3 className="charge-section-title">Paradas planificadas</h3>
              <p className="panel-hint charge-section-hint">
                Secuencia automática según autonomía con reserva de planificación. Pins numerados en el mapa.
              </p>
              <ChargingStopList
                stops={plannedStops}
                selectedStationId={selectedStationId}
                onSelectStation={onSelectStation}
                ariaLabel="Paradas planificadas en la ruta"
                showRouteDeviation
                distanceLabel={(item) => plannedStopDistanceLabel(item as PlannedRouteStopResult)}
              />
            </>
          )}

          {plan.origin_stops.length > 0 && (
            <>
              <h3 className="charge-section-title">Desde tu salida</h3>
              <ChargingStopList
                stops={plan.origin_stops}
                selectedStationId={selectedStationId}
                onSelectStation={onSelectStation}
                ariaLabel="Cargadores desde el origen"
                showRouteDeviation={false}
                distanceLabel={(item) => `${item.distance_from_origin_km.toFixed(1)} km desde la salida`}
              />
            </>
          )}

          <h3 className="charge-section-title">En la ruta</h3>
          {plan.stops.length === 0 ? (
            <p className="route-message">No hay paradas en el corredor alcanzables con el SOC actual.</p>
          ) : (
            <ChargingStopList
              stops={plan.stops}
              selectedStationId={selectedStationId}
              onSelectStation={onSelectStation}
              ariaLabel="Paradas en la ruta"
              showRouteDeviation
            />
          )}
        </>
      )}
    </>
  )
}
