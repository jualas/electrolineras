import { useState } from 'react'

import type { ChargingPlanResponse } from '../../api/types'
import {
  chargingStopAtLeg,
  haversineKm,
  routeChargingStops,
  routeExportSpecForNextStop,
} from '../../charging/planRouteStops'
import type { ActiveTripProgress } from '../../charging/activeTrip'
import type { MapCoords } from '../../navigation/externalMaps'
import {
  canShareLocation,
  googleMapsDestinationUrl,
  isMobileBrowser,
  shareRoute,
} from '../../navigation/externalMaps'

type ActiveTripProgressBarProps = {
  plan: ChargingPlanResponse
  progress: ActiveTripProgress
  userLocation?: MapCoords | null
  onMarkStopCompleted: (stopOrder: number) => void
  onReplan?: () => void
  replanLoading?: boolean
}

function stopOrderAtLeg(plan: ChargingPlanResponse, legIndex: number): number {
  const stop = chargingStopAtLeg(plan, legIndex)
  if (!stop) {
    return legIndex + 1
  }
  return 'order' in stop && typeof stop.order === 'number' ? stop.order : legIndex + 1
}

export function ActiveTripProgressBar({
  plan,
  progress,
  userLocation,
  onMarkStopCompleted,
  onReplan,
  replanLoading = false,
}: ActiveTripProgressBarProps) {
  const [shareError, setShareError] = useState(false)
  const [showReplanPrompt, setShowReplanPrompt] = useState(false)
  const stops = routeChargingStops(plan)
  const totalStops = stops.length
  if (totalStops === 0) {
    return null
  }

  const legIndex = Math.min(Math.max(0, progress.currentLegIndex), totalStops - 1)
  const currentStop = stops[legIndex]
  const stopOrder = stopOrderAtLeg(plan, legIndex)
  const isCompleted = progress.completedStopOrders.includes(stopOrder)
  const allDone = legIndex >= totalStops - 1 && isCompleted
  const nextExport = routeExportSpecForNextStop(plan, legIndex)
  const shareAvailable = canShareLocation() && nextExport != null
  const mobile = isMobileBrowser()

  const distanceKm =
    userLocation && currentStop
      ? haversineKm(userLocation, currentStop.station.location)
      : null

  const handleShareNext = async () => {
    if (!nextExport) {
      return
    }
    const fullRoute = {
      origin: plan.origin,
      destination: plan.destination!,
      waypoints: stops.map((stop) => stop.station.location),
      title: nextExport.title,
    }
    const ok = await shareRoute(fullRoute, 'next_stop', legIndex)
    setShareError(!ok)
    if (!ok) {
      window.setTimeout(() => setShareError(false), 2500)
    }
  }

  const siteName =
    currentStop.station.site_name?.trim() || currentStop.station.operator || 'Cargador'

  return (
    <section className="trip-progress" aria-label="Progreso del viaje">
      <div className="trip-progress__header">
        <h3 className="trip-progress__title">
          {allDone ? 'Paradas completadas' : `Parada ${legIndex + 1} de ${totalStops}`}
        </h3>
        {distanceKm != null && !allDone && (
          <span className="trip-progress__distance">~{distanceKm.toFixed(0)} km</span>
        )}
      </div>

      {!allDone && (
        <p className="trip-progress__stop">
          <strong>{siteName}</strong>
          {currentStop.station.operator ? ` · ${currentStop.station.operator}` : ''}
        </p>
      )}

      <div className="trip-progress__actions">
        {!isCompleted && !allDone ? (
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => {
              onMarkStopCompleted(stopOrder)
              setShowReplanPrompt(true)
            }}
          >
            Marcar parada completada
          </button>
        ) : null}
        {shareAvailable && !allDone ? (
          <button type="button" className="btn btn--primary" onClick={() => void handleShareNext()}>
            {mobile ? `Parada ${legIndex + 1} → Tesla` : `Enviar parada ${legIndex + 1}`}
          </button>
        ) : null}
        {nextExport && !shareAvailable && !allDone ? (
          <a
            className="btn btn--ghost"
            href={googleMapsDestinationUrl(
              currentStop.station.location.lat,
              currentStop.station.location.lon,
            )}
            target="_blank"
            rel="noopener noreferrer"
          >
            Abrir parada en Maps
          </a>
        ) : null}
      </div>

      {showReplanPrompt && onReplan ? (
        <div className="trip-progress__replan-prompt">
          <p>¿Recalcular el plan desde tu posición y SOC actuales?</p>
          <button type="button" className="btn btn--primary" disabled={replanLoading} onClick={onReplan}>
            {replanLoading ? 'Recalculando…' : 'Recalcular desde aquí'}
          </button>
        </div>
      ) : null}

      <p className="trip-progress__hint">
        Activa <strong>GPS del móvil</strong> para seguir tu posición. La navegación turn-by-turn la hace
        Google Maps o el Tesla; aquí gestionamos las paradas de carga.
      </p>

      {shareError && (
        <p className="route-export__error" role="alert">
          No se pudo compartir. Prueba «Abrir parada en Maps».
        </p>
      )}
    </section>
  )
}
