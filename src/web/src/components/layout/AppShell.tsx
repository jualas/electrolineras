import { useEffect, useState } from 'react'

import { checkApiHealth } from '../../api/client'
import { PowerFilterPanel } from '../../filters/PowerFilterPanel'
import { usePowerFilter } from '../../hooks/usePowerFilter'
import { useTheme } from '../../hooks/useTheme'
import { MapView } from '../../map/MapView'
import { SearchPanel, type SearchMode } from '../../search/SearchPanel'
import { ThemeToggle } from './ThemeToggle'

const MODES: { id: SearchMode; label: string }[] = [
  { id: 'map', label: 'Mapa' },
  { id: 'route', label: 'En ruta' },
  { id: 'city', label: 'En ciudad' },
]

const MODE_DEFAULT_PRESET: Partial<Record<SearchMode, 'trip' | 'slow'>> = {
  route: 'trip',
  city: 'slow',
}

export function AppShell() {
  const { theme, toggleTheme } = useTheme()
  const [mode, setMode] = useState<SearchMode>('map')
  const [apiOk, setApiOk] = useState(false)
  const { filter, setPreset, setCustomRange, apiQuery } = usePowerFilter('all')

  useEffect(() => {
    checkApiHealth().then(setApiOk)
  }, [])

  const handleModeChange = (nextMode: SearchMode) => {
    setMode(nextMode)
    const defaultPreset = MODE_DEFAULT_PRESET[nextMode]
    if (defaultPreset) {
      setPreset(defaultPreset)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__title">
          <h1>Electrolineras</h1>
          <p className="app-header__subtitle">Península ibérica</p>
        </div>
        <div className="app-header__actions">
          <span
            className={`status-pill ${apiOk ? 'status-pill--ok' : 'status-pill--warn'}`}
            title={apiOk ? 'API conectada' : 'API no disponible'}
          >
            {apiOk ? 'API ok' : 'Sin API'}
          </span>
          <ThemeToggle theme={theme} onToggle={toggleTheme} />
        </div>
      </header>

      <nav className="mode-tabs" aria-label="Modo de búsqueda">
        {MODES.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`mode-tab ${mode === item.id ? 'mode-tab--active' : ''}`}
            onClick={() => handleModeChange(item.id)}
            aria-pressed={mode === item.id}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="app-main">
        <MapView
          className="map-view"
          theme={theme}
          loadStations={mode === 'map'}
          minKw={apiQuery.minKw}
          maxKw={apiQuery.maxKw}
        />
        <aside className="side-panel">
          <SearchPanel mode={mode} />
          <PowerFilterPanel
            filter={filter}
            onPresetChange={setPreset}
            onCustomRangeChange={setCustomRange}
          />
        </aside>
      </div>
    </div>
  )
}
