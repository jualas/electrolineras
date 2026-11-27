import { useState } from 'react'

import {
  appleMapsDestinationUrl,
  canShareLocation,
  copyCoordinates,
  formatCoordinates,
  googleMapsDestinationUrl,
  openInTeslaApp,
  shareMapLocation,
} from '../../navigation/externalMaps'

type StationNavActionsProps = {
  lat: number
  lon: number
  label?: string
  compact?: boolean
}

export function StationNavActions({ lat, lon, label, compact = false }: StationNavActionsProps) {
  const [copyState, setCopyState] = useState<'idle' | 'ok' | 'error'>('idle')
  const [teslaState, setTeslaState] = useState<'idle' | 'ok' | 'copied' | 'cancelled' | 'error'>('idle')

  const handleCopy = async () => {
    const ok = await copyCoordinates(lat, lon)
    setCopyState(ok ? 'ok' : 'error')
    window.setTimeout(() => setCopyState('idle'), 2000)
  }

  const handleTesla = async () => {
    const result = await openInTeslaApp(lat, lon, label)
    if (result === 'share' || result === 'intent') {
      setTeslaState('ok')
    } else if (result === 'copied') {
      setTeslaState('copied')
    } else if (result === 'cancelled') {
      setTeslaState('cancelled')
    } else {
      setTeslaState('error')
    }
    window.setTimeout(() => setTeslaState('idle'), 2500)
  }

  const handleShare = async () => {
    await shareMapLocation(lat, lon, label)
  }

  const teslaLabel =
    teslaState === 'ok'
      ? 'Elige Tesla…'
      : teslaState === 'copied'
        ? 'Coords copiadas'
        : teslaState === 'cancelled'
          ? 'Cancelado'
          : teslaState === 'error'
            ? 'No se pudo enviar'
            : 'Enviar al Tesla'

  return (
    <div className={`nav-actions ${compact ? 'nav-actions--compact' : ''}`}>
      <a
        className="btn btn--primary btn--nav"
        href={googleMapsDestinationUrl(lat, lon)}
        target="_blank"
        rel="noopener noreferrer"
      >
        Navegar
      </a>
      <button
        type="button"
        className="btn btn--secondary btn--nav"
        title="Comparte el punto con la app Tesla (igual que desde Google Maps) para mandarlo al coche."
        onClick={() => void handleTesla()}
      >
        {teslaLabel}
      </button>
      <a
        className="btn btn--ghost btn--nav"
        href={appleMapsDestinationUrl(lat, lon)}
        target="_blank"
        rel="noopener noreferrer"
      >
        Apple Maps
      </a>
      <button type="button" className="btn btn--ghost btn--nav" onClick={() => void handleCopy()}>
        {copyState === 'ok' ? 'Copiado' : copyState === 'error' ? 'Error' : 'Copiar coords'}
      </button>
      {canShareLocation() && (
        <button type="button" className="btn btn--ghost btn--nav" onClick={() => void handleShare()}>
          Compartir
        </button>
      )}
      <span className="nav-actions__coords" title="Coordenadas">
        {formatCoordinates(lat, lon)}
      </span>
    </div>
  )
}
