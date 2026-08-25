const CONNECTOR_OPTIONS = [
  { id: 'CCS2', label: 'CCS2' },
  { id: 'TYPE2', label: 'Type 2' },
  { id: 'CHADEMO', label: 'CHAdeMO' },
  { id: 'TESLA', label: 'Tesla' },
] as const

export type MapStationFilterState = {
  availableOnly: boolean
  adHocOnly: boolean
  connectorTypes: string[]
  maxPriceEurKwh: number | null
}

type MapStationFiltersProps = {
  filter: MapStationFilterState
  onChange: (next: MapStationFilterState) => void
}

function summarizeFilters(filter: MapStationFilterState): string {
  const parts: string[] = []
  if (filter.availableOnly) {
    parts.push('solo disponibles')
  }
  if (filter.adHocOnly) {
    parts.push('tarjeta')
  }
  if (filter.connectorTypes.length > 0) {
    parts.push(filter.connectorTypes.join(', '))
  }
  if (filter.maxPriceEurKwh != null) {
    parts.push(`≤ ${filter.maxPriceEurKwh.toFixed(2)} €/kWh`)
  }
  return parts.length > 0 ? parts.join(' · ') : 'Sin filtros extra'
}

export function MapStationFilters({ filter, onChange }: MapStationFiltersProps) {
  const toggleConnector = (connectorId: string) => {
    const next = filter.connectorTypes.includes(connectorId)
      ? filter.connectorTypes.filter((item) => item !== connectorId)
      : [...filter.connectorTypes, connectorId]
    onChange({ ...filter, connectorTypes: next })
  }

  return (
    <details className="panel map-station-filters collapsible-panel">
      <summary className="collapsible-panel__summary" id="map-filters-heading">
        <span className="collapsible-panel__title">Filtros (estilo REVE)</span>
        <span className="collapsible-panel__meta">{summarizeFilters(filter)}</span>
      </summary>

      <div className="collapsible-panel__body">
        <div className="map-station-filters__toggles">
          <label className="map-station-filters__toggle">
            <input
              type="checkbox"
              checked={filter.availableOnly}
              onChange={(event) => onChange({ ...filter, availableOnly: event.target.checked })}
            />
            <span>Solo disponibles</span>
          </label>
          <label className="map-station-filters__toggle">
            <input
              type="checkbox"
              checked={filter.adHocOnly}
              onChange={(event) => onChange({ ...filter, adHocOnly: event.target.checked })}
            />
            <span>Pago con tarjeta</span>
          </label>
        </div>

        <p className="map-station-filters__label">Conectores</p>
        <div className="chip-row" role="group" aria-label="Tipos de conector">
          {CONNECTOR_OPTIONS.map((option) => (
            <button
              key={option.id}
              type="button"
              className={`chip ${filter.connectorTypes.includes(option.id) ? 'chip--active' : ''}`}
              onClick={() => toggleConnector(option.id)}
              aria-pressed={filter.connectorTypes.includes(option.id)}
            >
              {option.label}
            </button>
          ))}
        </div>

        <div className="map-station-filters__price">
          <label htmlFor="map-max-price">Precio máx. €/kWh</label>
          <div className="map-station-filters__price-row">
            <input
              id="map-max-price"
              type="range"
              min={0.2}
              max={1}
              step={0.05}
              value={filter.maxPriceEurKwh ?? 1}
              onChange={(event) => {
                const value = Number(event.target.value)
                onChange({
                  ...filter,
                  maxPriceEurKwh: value >= 1 ? null : value,
                })
              }}
            />
            <span>{filter.maxPriceEurKwh == null ? 'Sin límite' : `${filter.maxPriceEurKwh.toFixed(2)} €`}</span>
          </div>
        </div>
      </div>
    </details>
  )
}
