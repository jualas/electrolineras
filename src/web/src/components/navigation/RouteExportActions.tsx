import { useState } from 'react'

import type { RouteExportSpec } from '../../navigation/externalMaps'
import {
  canShareLocation,
  googleMapsRouteUrl,
  isMobileBrowser,
  shareRoute,
} from '../../navigation/externalMaps'

type RouteExportActionsProps = {
  route: RouteExportSpec
  variant?: 'default' | 'assistant'
  /** Índice de la parada DC actual (0-based) para «Siguiente parada → Tesla». */
  currentLegIndex?: number
}

export function RouteExportActions({
  route,
  variant = 'default',
  currentLegIndex = 0,
}: RouteExportActionsProps) {
  const [shareState, setShareState] = useState<'idle' | 'error'>('idle')
  const shareAvailable = canShareLocation()
  const mobile = isMobileBrowser()
  const stopCount = route.waypoints?.length ?? 0
  const googleUrl = googleMapsRouteUrl({
    origin: route.origin,
    destination: route.destination,
    waypoints: route.waypoints,
  })
  const hasStops = stopCount > 0
  const legIndex = Math.min(Math.max(0, currentLegIndex), Math.max(0, stopCount - 1))
  const assistant = variant === 'assistant'
  const googleLabel =
    stopCount > 0
      ? `Abrir en Google Maps · ${stopCount} parada${stopCount === 1 ? '' : 's'}`
      : 'Abrir en Google Maps'

  const handleShare = async (mode: 'full' | 'next_stop') => {
    const ok = await shareRoute(route, mode, legIndex)
    setShareState(ok ? 'idle' : 'error')
    if (!ok) {
      window.setTimeout(() => setShareState('idle'), 2500)
    }
  }

  return (
    <div className={`route-export route-export--actions${assistant ? ' route-export--assistant' : ''}`}>
      <div className="route-export__buttons">
        <a
          className={`btn ${assistant ? 'btn--primary' : 'btn--ghost'}`}
          href={googleUrl}
          target="_blank"
          rel="noopener noreferrer"
          title={
            hasStops
              ? 'Los cargadores del plan van como paradas (waypoints) en Google Maps'
              : undefined
          }
        >
          {googleLabel}
        </a>
        {shareAvailable && (
          <button
            type="button"
            className={`btn ${assistant ? 'btn--secondary' : 'btn--ghost'}`}
            onClick={() => void handleShare('full')}
          >
            {mobile ? 'Enviar a app Tesla' : 'Compartir ruta'}
          </button>
        )}
        {shareAvailable && hasStops && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => void handleShare('next_stop')}
            title="La app Tesla suele aceptar mejor un solo destino"
          >
            Parada {legIndex + 1} → Tesla
          </button>
        )}
      </div>
      <p className="route-export__hint">
        {hasStops ? (
          mobile ? (
            <>
              <strong>Google Maps:</strong> incluye las <strong>{stopCount} paradas de carga</strong> del
              plan como waypoints. La navegación turn-by-turn la hace Maps o el Tesla; activa{' '}
              <strong>GPS del móvil</strong> para que Electrolineras siga tu posición. Usa «Parada N →
              Tesla» para enviar solo la siguiente.
            </>
          ) : (
            <>
              <strong>Google Maps</strong> recibe origen, <strong>{stopCount} cargador
              {stopCount === 1 ? '' : 'es'}</strong> como paradas y el destino. Activa GPS del móvil para
              seguimiento del plan. Envía paradas al Tesla una a una con «Parada N → Tesla».
            </>
          )
        ) : mobile ? (
          <>
            <strong>Google Maps:</strong> abre la ruta; Google aplica tráfico en vivo. Desde ahí puedes
            enviarla al coche. <strong>App Tesla:</strong> menú compartir → Tesla.
          </>
        ) : (
          <>
            Abrir en Google Maps: Google reinterpretará la ruta con tráfico. Luego puedes compartirla al
            móvil o al coche.
          </>
        )}
      </p>
      {shareState === 'error' && (
        <p className="route-export__error" role="alert">
          No se pudo compartir. Prueba «Abrir en Google Maps».
        </p>
      )}
    </div>
  )
}
