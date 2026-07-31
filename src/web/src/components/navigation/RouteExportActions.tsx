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
}

export function RouteExportActions({ route, variant = 'default' }: RouteExportActionsProps) {
  const [shareState, setShareState] = useState<'idle' | 'error'>('idle')
  const shareAvailable = canShareLocation()
  const mobile = isMobileBrowser()
  const googleUrl = googleMapsRouteUrl({
    origin: route.origin,
    destination: route.destination,
    waypoints: route.waypoints,
  })
  const hasStops = (route.waypoints?.length ?? 0) > 0
  const assistant = variant === 'assistant'

  const handleShare = async (mode: 'full' | 'next_stop') => {
    const ok = await shareRoute(route, mode)
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
        >
          Abrir en Google Maps
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
            1.ª parada → Tesla
          </button>
        )}
      </div>
      <p className="route-export__hint">
        {mobile ? (
          <>
            <strong>Google Maps:</strong> abre la ruta completa; desde ahí puedes enviarla al coche.{' '}
            <strong>App Tesla:</strong> usa el menú compartir del móvil y elige Tesla (en iOS/Android).
            {hasStops && ' Si la ruta completa falla, prueba «1.ª parada → Tesla».'}
          </>
        ) : (
          <>
            Abre la ruta en Google Maps y compártela al móvil o al coche. En el móvil, el botón Tesla abre el
            menú nativo de compartir.
          </>
        )}{' '}
        Google Maps recalcula la ruta: puede cambiar corredor y tiempos respecto al plan de esta app.
      </p>
      {shareState === 'error' && (
        <p className="route-export__error" role="alert">
          No se pudo compartir. Prueba «Abrir en Google Maps».
        </p>
      )}
    </div>
  )
}
