import { useState } from 'react'

import {
  appleMapsDestinationUrl,
  canShareLocation,
  copyCoordinates,
  formatCoordinates,
  googleMapsDestinationUrl,
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

  const handleCopy = async () => {
    const ok = await copyCoordinates(lat, lon)
    setCopyState(ok ? 'ok' : 'error')
    window.setTimeout(() => setCopyState('idle'), 2000)
  }

  const handleShare = async () => {
    await shareMapLocation(lat, lon, label)
  }

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
      <a
        className="btn btn--secondary btn--nav"
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
