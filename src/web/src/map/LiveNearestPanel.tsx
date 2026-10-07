import { Radio } from 'lucide-react'

import { formatDistanceKm } from '../api/nearby'
import { stationLabel } from '../api/route'
import type { Station } from '../api/types'
import { StationNavActions } from '../components/navigation/StationNavActions'
import type { LiveNearestStatus } from '../hooks/useLiveNearestCharger'
import { ConnectorChips } from '../stations/ConnectorChips'

type LiveNearestPanelProps = {
  active: boolean
  status: LiveNearestStatus
  station: Station | null
  distanceKm: number | null
  distanceM: number | null
  usedMinKw: number | null
  powerHint: string
  error: string | null
  onSelectStation: (station: Station) => void
  onToggle: () => void
  onRefresh: () => void
}

export function LiveNearestPanel({
  active,
  status,
  station,
  distanceKm,
  distanceM,
  usedMinKw,
  powerHint,
  error,
  onSelectStation,
  onToggle,
  onRefresh,
}: LiveNearestPanelProps) {
  if (!active) {
    return null
  }

  const distLabel =
    distanceKm != null && distanceM != null ? formatDistanceKm(distanceKm, distanceM) : null

  return (
    <section className="live-nearest-panel" aria-label="Cargador más cercano">
      <header className="live-nearest-panel__head">
        <div className="live-nearest-panel__title-row">
          <Radio size={16} aria-hidden className="live-nearest-panel__pulse" />
          <h2 className="live-nearest-panel__title">Más cercano</h2>
          <span className="live-nearest-panel__badge">GPS</span>
        </div>
        <div className="live-nearest-panel__actions">
          <button type="button" className="btn btn--ghost" onClick={onRefresh}>
            Actualizar
          </button>
          <button type="button" className="btn btn--ghost" onClick={onToggle}>
            Desactivar
          </button>
        </div>
      </header>

      <p className="live-nearest-panel__hint">Filtro: {powerHint}</p>

      {status === 'locating' && <p className="live-nearest-panel__hint">Obteniendo posición GPS…</p>}
      {status === 'loading' && !station && (
        <p className="live-nearest-panel__hint">Buscando cargador cercano…</p>
      )}
      {status === 'empty' && (
        <p className="live-nearest-panel__hint">
          No hay cargadores con {powerHint}
          {usedMinKw != null ? ` (probado ≥${usedMinKw} kW)` : ''} en el radio de búsqueda.
        </p>
      )}
      {error && <p className="live-nearest-panel__error">{error}</p>}

      {station && (
        <button
          type="button"
          className="live-nearest-panel__card route-result route-result--active"
          onClick={() => onSelectStation(station)}
        >
          <div className="route-result__head">
            <span className="route-result__rank" aria-hidden>
              ●
            </span>
            <div>
              <p className="route-result__title">{stationLabel(station)}</p>
              <p className="route-result__operator">{station.operator ?? '—'}</p>
              {station.location.address ? (
                <p className="route-result__address">{station.location.address}</p>
              ) : null}
            </div>
          </div>
          <p className="route-result__meta">
            {station.max_power_kw.toFixed(0)} kW
            {distLabel ? ` · a ${distLabel}` : ''}
          </p>
          <ConnectorChips connectors={station.connectors} />
        </button>
      )}

      {station && (
        <StationNavActions
          lat={station.location.lat}
          lon={station.location.lon}
          label={stationLabel(station)}
          compact
        />
      )}
    </section>
  )
}
