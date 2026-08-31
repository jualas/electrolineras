import { Battery, Clock, Euro, Navigation2, Share2, Zap } from 'lucide-react'

import type { ChargingPlanResponse, PlannedRouteStopResult } from '../api/types'
import { RouteExportActions } from '../components/navigation/RouteExportActions'
import {
  classificationClassName,
  formatClassificationLabel,
} from '../charging/classificationDisplay'
import { formatDurationHm, formatEsNumber } from '../charging/formatTrip'
import { routeExportSpecFromChargingPlan, routeChargingStops, isChargingPlanComplete } from '../charging/planRouteStops'
import { canShareLocation, googleMapsRouteUrl, shareRoute } from '../navigation/externalMaps'
import type { RouteExportSpec } from '../navigation/externalMaps'
import { avoidTollsLabel, formatRouteAlternativesKm } from './RoutePreferenceFields'
import { ChargingStopList } from './ChargingStopList'
import { RevePlanTimeline } from './RevePlanTimeline'
import { ReveStatRow } from './ReveStatRow'

type ChargingPlanResultsProps = {
  plan: ChargingPlanResponse
  selectedStationId?: string | null
  onSelectStation?: (station: import('../api/types').Station | null) => void
  variant?: 'full' | 'assistant'
  originLabel?: string | null
  destinationLabel?: string | null
  currentLegIndex?: number
}

/** Estrategias de «cargar antes de salir» — no forman parte del relato de la ruta. */
const ORIGIN_NOISE_STRATEGY_IDS = new Set(['charge_at_origin'])

function ReveRouteSummaryCard({
  summary,
  distanceKm,
  originLabel,
  destinationLabel,
  routeExport,
}: {
  summary: NonNullable<ChargingPlanResponse['route_trip_summary']>
  distanceKm?: number | null
  originLabel?: string | null
  destinationLabel?: string | null
  routeExport: RouteExportSpec | null
}) {
  const googleUrl = routeExport
    ? googleMapsRouteUrl({
        origin: routeExport.origin,
        destination: routeExport.destination,
        waypoints: routeExport.waypoints,
      })
    : null
  const shareAvailable = routeExport != null && canShareLocation()

  return (
    <div className="reve-route-summary" aria-label="Resumen del viaje">
      <div className="reve-route-summary__head">
        <div className="reve-route-summary__headline">
          {originLabel && destinationLabel && (
            <p className="reve-route-summary__route">
              {originLabel} a {destinationLabel}
            </p>
          )}
          <p className="reve-route-summary__duration">{formatDurationHm(summary.total_duration_minutes)}</p>
          <p className="reve-route-summary__subline">
            {distanceKm != null && `${formatEsNumber(distanceKm, 2)} km  -  `}
            {summary.stop_count} parada{summary.stop_count === 1 ? '' : 's'}
          </p>
        </div>
        <div className="reve-route-summary__actions">
          {shareAvailable && (
            <button
              type="button"
              className="reve-icon-btn"
              title="Compartir ruta"
              onClick={() => void shareRoute(routeExport, 'full')}
            >
              <Share2 size={18} aria-hidden />
            </button>
          )}
          {googleUrl && (
            <a
              className="reve-icon-btn"
              title={
                (routeExport?.waypoints?.length ?? 0) > 0
                  ? `Google Maps con ${routeExport!.waypoints!.length} paradas de carga`
                  : 'Abrir ruta en Google Maps'
              }
              href={googleUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Navigation2 size={18} aria-hidden />
            </a>
          )}
        </div>
      </div>

      <div className="reve-route-summary__divider" />

      <div className="reve-route-summary__stats">
        <ReveStatRow
          icon={<Clock size={16} aria-hidden />}
          label="Tiempo de recarga estimado"
          value={`${summary.total_charge_minutes.toFixed(0)} min`}
        />
        {summary.projected_destination_soc_pct != null && (
          <ReveStatRow
            icon={<Battery size={16} aria-hidden />}
            label="% de batería al llegar al destino"
            value={`${summary.projected_destination_soc_pct.toFixed(0)}%`}
          />
        )}
        <ReveStatRow
          icon={<Zap size={16} aria-hidden />}
          label="Consumo estimado"
          value={`${formatEsNumber(summary.total_energy_kwh, 2)} kWh`}
        />
        {summary.estimated_charge_cost_eur != null && (
          <ReveStatRow
            icon={<Euro size={16} aria-hidden />}
            label="Coste estimado de recarga"
            value={`~${formatEsNumber(summary.estimated_charge_cost_eur, 2)} €`}
          />
        )}
      </div>
    </div>
  )
}

export function ChargingPlanResults({
  plan,
  selectedStationId,
  onSelectStation,
  variant = 'full',
  originLabel,
  destinationLabel,
  currentLegIndex = 0,
}: ChargingPlanResultsProps) {
  const assistant = variant === 'assistant'
  const plannedStops = plan.planned_stops ?? []
  const routeStops = routeChargingStops(plan)
  const planComplete = isChargingPlanComplete(plan)
  const hasPlannedRoute = routeStops.length > 0
  const routeExport = routeExportSpecFromChargingPlan(plan)
  const routeStrategies = plan.strategies.filter((strategy) => !ORIGIN_NOISE_STRATEGY_IDS.has(strategy.id))
  const tripSummary = plan.route_trip_summary
  const compactPlan = assistant || (plan.mode === 'route' && tripSummary != null && plannedStops.length > 0)
  const corridorFallbackStops =
    plannedStops.length === 0 && !plan.reachable_without_stop ? routeChargingStops(plan) : []
  const displayStops = plannedStops.length > 0 ? routeStops : corridorFallbackStops
  const hasDisplayStops = displayStops.length > 0
  const resolvedOriginLabel = originLabel ?? 'Tu ubicación'

  if (compactPlan && plan.mode === 'route') {
    return (
      <>
        {tripSummary && (
          <ReveRouteSummaryCard
            summary={tripSummary}
            distanceKm={plan.route_distance_km}
            originLabel={originLabel}
            destinationLabel={destinationLabel}
            routeExport={routeExport}
          />
        )}
        {hasDisplayStops ? (
          <>
            <h3 className="charge-section-title">
              {plannedStops.length > 0 ? 'Dónde cargar en la ruta' : 'Cargadores viables en el corredor'}
            </h3>
            {plannedStops.length === 0 && (
              <p className="route-message route-message--error" role="alert">
                No se pudo completar un plan multi-parada con tu autonomía actual. Revisa consumo, kW mínimos
                o carga antes de salir. Estos son los mejores candidatos en ruta.
              </p>
            )}
            {!planComplete && plannedStops.length > 0 && (
              <p className="route-message route-message--error" role="alert">
                Plan incompleto: no llegarías con batería suficiente. Revisa corredor o filtros kW.
              </p>
            )}
            {plannedStops.length > 0 ? (
              <RevePlanTimeline
                originLabel={resolvedOriginLabel}
                originSocPct={plan.vehicle.soc_percent}
                stops={displayStops as PlannedRouteStopResult[]}
                selectedStationId={selectedStationId}
                onSelectStation={onSelectStation}
              />
            ) : (
              <ChargingStopList
                stops={displayStops}
                selectedStationId={selectedStationId}
                onSelectStation={onSelectStation}
                ariaLabel="Candidatos de carga en ruta"
                showRouteDeviation={false}
                distanceLabel={(item) =>
                  `${item.distance_from_origin_km.toFixed(0)} km · ${item.soc_arrival_pct.toFixed(0)} % SOC`
                }
              />
            )}
          </>
        ) : plan.reachable_without_stop ? (
          <p className="route-message">Con el SOC actual llegas al destino sin parar a cargar.</p>
        ) : (
          <>
            <p className="route-message">No hay paradas en el corredor alcanzables con el SOC actual.</p>
            {plan.warnings.length > 0 && (
              <ul className="charge-warnings" aria-label="Alertas del plan">
                {plan.warnings.map((warning) => (
                  <li key={warning}>{warning}</li>
                ))}
              </ul>
            )}
          </>
        )}
      </>
    )
  }

  return (
    <>
      {tripSummary && plan.mode === 'route' && (
        <ReveRouteSummaryCard
          summary={tripSummary}
          distanceKm={plan.route_distance_km}
          originLabel={originLabel}
          destinationLabel={destinationLabel}
          routeExport={routeExport}
        />
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
                  ~{plannedStops.reduce((sum, stop) => sum + stop.charge_minutes, 0).toFixed(0)} min carga total
                </>
              )}
            </>
          )}
        </p>
      </div>

      {routeExport && (
        <RouteExportActions
          route={routeExport}
          variant={assistant ? 'assistant' : 'default'}
          currentLegIndex={currentLegIndex}
        />
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
              {plannedStops.length > 0 ? (
                <RevePlanTimeline
                  originLabel={resolvedOriginLabel}
                  originSocPct={plan.vehicle.soc_percent}
                  stops={routeStops as PlannedRouteStopResult[]}
                  selectedStationId={selectedStationId}
                  onSelectStation={onSelectStation}
                />
              ) : (
                <>
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
                      `${item.distance_from_origin_km.toFixed(0)} km · ${item.soc_arrival_pct.toFixed(0)} % SOC`
                    }
                  />
                </>
              )}
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
