export type SearchMode = 'map' | 'route' | 'city'

type SearchPanelProps = {
  mode: SearchMode
}

export function SearchPanel({ mode }: SearchPanelProps) {
  if (mode === 'route') {
    return (
      <section className="panel search-panel" aria-labelledby="route-search-heading">
        <h2 id="route-search-heading">En ruta</h2>
        <p className="panel-hint">Origen, destino y corredor — flujo en #6034</p>
        <div className="placeholder-form">
          <div className="placeholder-field">Origen (GPS o ciudad)</div>
          <div className="placeholder-field">Destino</div>
        </div>
      </section>
    )
  }

  if (mode === 'city') {
    return (
      <section className="panel search-panel" aria-labelledby="city-search-heading">
        <h2 id="city-search-heading">En ciudad</h2>
        <p className="panel-hint">Ubicación y radio 1 km — flujo en #6035</p>
        <div className="placeholder-form">
          <div className="placeholder-field">Cerca de mí / dirección / mapa</div>
          <div className="placeholder-field">Radio: 1 km</div>
        </div>
      </section>
    )
  }

  return (
    <section className="panel search-panel" aria-labelledby="map-search-heading">
      <h2 id="map-search-heading">Mapa peninsular</h2>
      <p className="panel-hint">Puntos desde la API al mover o hacer zoom en el mapa.</p>
    </section>
  )
}
