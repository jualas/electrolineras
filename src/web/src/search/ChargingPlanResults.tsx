import type { ChargingPlanResponse, PlannedRouteStopResult } from '../api/types'
import { RouteExportActions } from '../components/navigation/RouteExportActions'
import {
  classificationClassName,
  formatClassificationLabel,
} from '../charging/classificationDisplay'
import { routeExportSpecFromChargingPlan, routeChargingStops, isChargingPlanComplete } from '../charging/planRouteStops'
import { avoidTollsLabel, formatRouteAlternativesKm } from './RoutePreferenceFields'
import { ChargingStopList } from './ChargingStopList'

type ChargingPlanResultsProps = {
  plan: ChargingPlanResponse
  selectedStationId?: string | null
  onSelectStation?: (station: import('../api/types').Station | null) => void
  variant?: 'full' | 'assistant'
}

/** Estrategias de «cargar antes de salir» — no forman parte del relato de la ruta. */
const ORIGIN_NOISE_STRATEGY_IDS = new Set(['charge_at_origin'])

function plannedStopDistanceLabel(stop: PlannedRouteStopResult): string {
  const drive =
    stop.leg_driving_minutes != null && stop.leg_driving_minutes > 0
      ? ` · ~${stop.leg_driving_minutes.toFixed(0)} min conducción`
      : ''
  const energy =
    stop.leg_energy_kwh != null && stop.leg_energy_kwh > 0
      ? ` · ${stop.leg_energy_kwh.toFixed(1)} kWh`
      : ''
  const cost =
    stop.estimated_charge_cost_eur != null
      ? ` · ~${stop.estimated_charge_cost_eur.toFixed(2)} €`
      : ''
  return `${stop.distance_from_origin_km.toFixed(0)} km · tramo ${stop.leg_distance_km.toFixed(0)} km${drive}${energy} · ${stop.soc_arrival_pct.toFixed(0)}→${stop.soc_departure_pct.toFixed(0)} % · ~${stop.charge_minutes.toFixed(0)} min carga${cost}`
}

function totalPlannedChargeMinutes(stops: PlannedRouteStopResult[]): number {
  return stops.reduce((sum, stop) => sum + stop.charge_minutes, 0)
}

export function ChargingPlanResults({
  plan,
  selectedStationId,
  onSelectStation,
  variant = 'full',
}: ChargingPlanResultsProps) {
  const assistant = variant === 'assistant'
  const plannedStops = plan.planned_stops ?? []
  const routeStops = routeChargingStops(plan)
  const planComplete = isChargingPlanComplete(plan)
  const hasPlannedRoute = routeStops.length > 0
  const routeExport = routeExportSpecFromChargingPlan(plan)
  const routeStrategies = plan.strategies.filter((strategy) => !ORIGIN_NOISE_STRATEGY_IDS.has(strategy.id))
  const tripSummary = plan.route_trip_summary

  return (
    <>
      {tripSummary && plan.mode === 'route' && (
        <div className="reve-trip-summary" aria-label="Resumen del viaje">
          <p className="reve-trip-summary__title">Resumen del viaje</p>
          <ul className="reve-trip-summary__stats">
            <li>
              <strong>{tripSummary.total_duration_minutes.toFixed(0)} min</strong> total
            </li>
            <li>
              <strong>{tripSummary.driving_duration_minutes.toFixed(0)} min</strong> conducción
            </li>
            <li>
              <strong>{tripSummary.total_charge_minutes.toFixed(0)} min</strong> recarga
            </li>
            <li>
              <strong>{tripSummary.stop_count}</strong> parada{tripSummary.stop_count === 1 ? '' : 's'}
            </li>
            <li>
              <strong>{tripSummary.total_energy_kwh.toFixed(0)} kWh</strong> consumo
            </li>
            {tripSummary.projected_destination_soc_pct != null && (
              <li>
                <strong>{tripSummary.projected_destination_soc_pct.toFixed(0)} %</strong> al destino
              </li>
            )}
            {tripSummary.estimated_charge_cost_eur != null && (
              <li>
                <strong>~{tripSummary.estimated_charge_cost_eur.toFixed(2)} €</strong> carga est.
              </li>
            )}
          </ul>
        </div>
      )}

      {plan.warnings.length > 0 && (!assistant || !planComplete) && (
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
              {plan.soc_at_destination_pct != null && !plan.reachable_without_stop && !hasPlannedRoute && (
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
                  ~{plan.projected_soc_at_destination_with_plan.toFixed(0)} % al destino con {plannedStops.length}{' '}
                  parada{plannedStops.length === 1 ? '' : 's'}
                </>
              )}
              {plannedStops.length === 0 && hasPlannedRoute && (
                <>
                  {' · '}
                  {routeStops.length} parada{routeStops.length === 1 ? '' : 's'} sugerida{routeStops.length === 1 ? '' : 's'} en ruta
                </>
              )}
              {plannedStops.length > 0 && (
                <>
                  {' · '}
                  ~{totalPlannedChargeMinutes(plannedStops).toFixed(0)} min carga total
                </>
              )}
            </>
          )}
        </p>
      </div>

      {routeExport && (
        <RouteExportActions route={routeExport} variant={assistant ? 'assistant' : 'default'} />
      )}

      {!assistant && routeStrategies.length > 0 && !hasPlannedRoute && (
        <div className="charge-strategies" aria-label="Estrategias recomendadas">
          {routeStrategies.map((strategy) => (
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
          {hasPlannedRoute ? (
            <>
              <h3 className="charge-section-title">Dónde cargar en la ruta</h3>
              {plannedStops.length > 0 && !planComplete && (
                <p className="route-message route-message--error" role="alert">
                  Plan incompleto: faltan cargadores en algún tramo o no llegarías con batería suficiente.
                  Revisa alertas arriba, amplía corredor o baja el filtro kW.
                </p>
              )}
              <p className="panel-hint charge-section-hint">
                Paradas en orden de viaje (pausa ~2 h DGT, máx. 3 h). Pins numerados en el mapa.
              </p>
              <ChargingStopList
                stops={routeStops}
                selectedStationId={selectedStationId}
                onSelectStation={onSelectStation}
                ariaLabel="Paradas planificadas en la ruta"
                showRouteDeviation
                distanceLabel={(item) =>
                  plannedStops.length > 0
                    ? plannedStopDistanceLabel(item as PlannedRouteStopResult)
                    : `${item.distance_from_origin_km.toFixed(0)} km · ${item.soc_arrival_pct.toFixed(0)} % SOC`
                }
              />
            </>
          ) : plan.reachable_without_stop ? (
            <p className="route-message">Con el SOC actual llegas al destino sin parar a cargar.</p>
          ) : plan.stops.length > 0 ? (
            <>
              <h3 className="charge-section-title">Paradas posibles en ruta</h3>
              <p className="panel-hint charge-section-hint">
                Aún no hay secuencia automática; opciones alcanzables en el corredor.
              </p>
              <ChargingStopList
                stops={plan.stops}
                selectedStationId={selectedStationId}
                onSelectStation={onSelectStation}
                ariaLabel="Paradas en la ruta"
                showRouteDeviation
              />
            </>
          ) : (
            <p className="route-message">No hay paradas en el corredor alcanzables con el SOC actual.</p>
          )}
        </>
      )}
    </>
  )
}
