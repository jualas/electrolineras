import { useState } from 'react'

import { trafficLayerAvailable } from './mapTrafficLayer'

export type MapLayerToggles = {
  /** Sombreado + curvas de nivel (mismo DEM, estilo REVE). */
  relief: boolean
  traffic: boolean
}

type MapLayerControlProps = {
  value: MapLayerToggles
  onChange: (next: MapLayerToggles) => void
}

export function MapLayerControl({ value, onChange }: MapLayerControlProps) {
  const [open, setOpen] = useState(false)
  const trafficAvailable = trafficLayerAvailable()

  const toggle = (key: keyof MapLayerToggles) => {
    onChange({ ...value, [key]: !value[key] })
  }

  return (
    <div className="map-layer-control">
      <button
        type="button"
        className="map-layer-control__toggle"
        aria-expanded={open}
        aria-controls="map-layer-menu"
        onClick={() => setOpen((current) => !current)}
        title="Capas del mapa"
      >
        Capas
      </button>
      {open && (
        <div id="map-layer-menu" className="map-layer-control__menu" role="group" aria-label="Capas del mapa">
          <label className="map-layer-control__item">
            <input
              type="checkbox"
              checked={value.relief}
              onChange={() => toggle('relief')}
            />
            <span>Relieve</span>
          </label>
          <p className="map-layer-control__hint">
            Sombreado del terreno y curvas de nivel superpuestas (estilo REVE).
          </p>
          <label
            className={`map-layer-control__item${trafficAvailable ? '' : ' map-layer-control__item--disabled'}`}
            title={
              trafficAvailable
                ? 'Tráfico en tiempo real (TomTom)'
                : 'Configura VITE_TOMTOM_API_KEY para activar tráfico'
            }
          >
            <input
              type="checkbox"
              checked={value.traffic}
              disabled={!trafficAvailable}
              onChange={() => toggle('traffic')}
            />
            <span>Tráfico</span>
          </label>
        </div>
      )}
    </div>
  )
}
