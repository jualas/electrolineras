import { useMemo, useState } from 'react'

import type { RouteExportSpec } from '../../navigation/externalMaps'
import {
  canShareLocation,
  googleMapsDestinationUrl,
  googleMapsRouteUrl,
  isMobileBrowser,
  shareRoute,
} from '../../navigation/externalMaps'

type RouteExportActionsProps = {
  route: RouteExportSpec
  variant?: 'default' | 'assistant'
}

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // fallback below
  }
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)
    return copied
  } catch {
    return false
  }
}

export function RouteExportActions({ route, variant = 'default' }: RouteExportActionsProps) {
  const [msg, setMsg] = useState<string | null>(null)
  const [showQr, setShowQr] = useState(false)
  const [busy, setBusy] = useState(false)
  const mobile = isMobileBrowser()
  const assistant = variant === 'assistant'
  const hasStops = (route.waypoints?.length ?? 0) > 0

  const googleUrl = useMemo(
    () =>
      googleMapsRouteUrl({
        origin: route.origin,
        destination: route.destination,
        waypoints: route.waypoints,
      }),
    [route.origin, route.destination, route.waypoints],
  )

  const nextStopUrl = useMemo(() => {
    const stop = route.waypoints?.[0]
    if (!stop) return null
    return googleMapsDestinationUrl(stop.lat, stop.lon)
  }, [route.waypoints])

  const qrSrc = useMemo(
    () =>
      `https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(googleUrl)}`,
    [googleUrl],
  )

  const handleShare = async () => {
    setBusy(true)
    setMsg(null)
    try {
      if (canShareLocation()) {
        const ok = await shareRoute(route, 'full')
        if (ok) {
          setMsg('Enlace compartido.')
          return
        }
      }
      const copied = await copyText(googleUrl)
      setMsg(copied ? 'Enlace copiado. Pégalo donde quieras.' : 'No se pudo compartir ni copiar.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className={`route-export route-export--actions${assistant ? ' route-export--assistant' : ''}`}>
      <p className="route-export__hint">
        Flujo recomendado: abre la ruta en <strong>Google Maps en el móvil</strong> y envíala al coche por{' '}
        <strong>Bluetooth</strong> (audio). El mapa de navegación sigue en el teléfono.
      </p>
      <div className="route-export__buttons">
        <a
          className={`btn ${assistant ? 'btn--primary' : 'btn--ghost'}`}
          href={googleUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Abrir en Google Maps
        </a>
        {nextStopUrl ? (
          <a
            className="btn btn--ghost"
            href={nextStopUrl}
            target="_blank"
            rel="noopener noreferrer"
            title="Solo la primera parada de carga"
          >
            Siguiente parada (preacondicionar)
          </a>
        ) : null}
        <button type="button" className={`btn ${assistant ? 'btn--secondary' : 'btn--ghost'}`} disabled={busy} onClick={() => void handleShare()}>
          Compartir enlace
        </button>
        {!mobile ? (
          <button type="button" className="btn btn--ghost" onClick={() => setShowQr((v) => !v)}>
            {showQr ? 'Ocultar QR' : 'QR (móvil)'}
          </button>
        ) : null}
      </div>
      {showQr && !mobile ? (
        <div className="route-export-qr">
          <img src={qrSrc} alt="Código QR con la ruta en Google Maps" width={180} height={180} />
          <p className="route-export__hint">Escanea desde el móvil si estás en el ordenador.</p>
        </div>
      ) : null}
      <p className="route-export__hint">
        {hasStops ? (
          <>
            Preacondicionado: Maps no lo activa. ~30–40 min antes de la carga, usa «Siguiente parada» o fija ese
            pin en el navegador del Tesla.
          </>
        ) : (
          <>Google Maps recalcula la ruta: puede cambiar corredor y tiempos respecto al plan de esta app.</>
        )}
      </p>
      {msg ? (
        <p className="route-export__hint" role="status">
          {msg}
        </p>
      ) : null}
    </div>
  )
}
