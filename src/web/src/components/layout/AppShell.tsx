import { useCallback, useEffect, useRef, useState } from 'react'

import { checkApiHealth } from '../../api/client'
import type { AlongRouteResponse, ChargingPlanResponse, MapBounds, NearbyResponse, Station } from '../../api/types'
import { VehicleProfilePanel } from '../vehicle/VehicleProfilePanel'
import { PowerFilterPanel } from '../../filters/PowerFilterPanel'
import { usePowerFilter } from '../../hooks/usePowerFilter'
import { useTheme } from '../../hooks/useTheme'
import { useVehicleProfile } from '../../hooks/useVehicleProfile'
import { MapView } from '../../map/MapView'
import { SearchPanel, type SearchMode } from '../../search/SearchPanel'
import { ThemeToggle } from './ThemeToggle'

const MODES: { id: SearchMode; label: string }[] = [
  { id: 'map', label: 'Mapa' },
  { id: 'charge', label: 'Plan carga' },
  { id: 'route', label: 'En ruta' },
  { id: 'city', label: 'En ciudad' },
]

const MODE_DEFAULT_PRESET: Partial<Record<SearchMode, 'trip' | 'slow'>> = {
  charge: 'trip',
  route: 'trip',
  city: 'slow',
}

export function AppShell() {
  const { theme, toggleTheme } = useTheme()
  const [mode, setMode] = useState<SearchMode>('map')
  const [apiOk, setApiOk] = useState(false)
  const [routeData, setRouteData] = useState<AlongRouteResponse | null>(null)
  const [routeSearching, setRouteSearching] = useState(false)
  const [chargePlanData, setChargePlanData] = useState<ChargingPlanResponse | null>(null)
  const [chargePlanSearching, setChargePlanSearching] = useState(false)
  const [cityData, setCityData] = useState<NearbyResponse | null>(null)
  const [citySearching, setCitySearching] = useState(false)
  const [cityPickMode, setCityPickMode] = useState(false)
  const [cityMapPin, setCityMapPin] = useState<{ label: string; lat: number; lon: number } | null>(null)
  const [selectedStation, setSelectedStation] = useState<Station | null>(null)
  const mapBoundsGetterRef = useRef<(() => MapBounds | null) | null>(null)
  const { filter, setPreset, setCustomRange, apiQuery } = usePowerFilter('all')
  const {
    profile: vehicleProfile,
    setPresetId: setVehiclePresetId,
    setSocPercent: setVehicleSoc,
    setConsumptionWhPerKm: setVehicleConsumption,
    setTerrainFactorId: setVehicleTerrain,
  } = useVehicleProfile()

  useEffect(() => {
    checkApiHealth().then(setApiOk)
  }, [])

  const handleModeChange = (nextMode: SearchMode) => {
    setMode(nextMode)
    const defaultPreset = MODE_DEFAULT_PRESET[nextMode]
    if (defaultPreset) {
      setPreset(defaultPreset)
    }
    if (nextMode !== 'route') {
      setRouteData(null)
      setRouteSearching(false)
    }
    if (nextMode !== 'charge') {
      setChargePlanData(null)
      setChargePlanSearching(false)
    }
    if (nextMode !== 'city') {
      setCityData(null)
      setCitySearching(false)
      setCityPickMode(false)
      setCityMapPin(null)
    }
    setSelectedStation(null)
  }

  const handleRouteResults = useCallback((response: AlongRouteResponse | null) => {
    setRouteData(response)
    setSelectedStation(null)
  }, [])

  const handleRouteSearchStateChange = useCallback((status: 'idle' | 'loading' | 'ready' | 'error') => {
    setRouteSearching(status === 'loading')
  }, [])

  const handleChargePlanResults = useCallback((response: ChargingPlanResponse | null) => {
    setChargePlanData(response)
    setSelectedStation(null)
  }, [])

  const handleChargePlanSearchStateChange = useCallback((status: 'idle' | 'loading' | 'ready' | 'error') => {
    setChargePlanSearching(status === 'loading')
  }, [])

  const handleCityResults = useCallback((response: NearbyResponse | null) => {
    setCityData(response)
    setSelectedStation(null)
  }, [])

  const handleCitySearchStateChange = useCallback((status: 'idle' | 'loading' | 'ready' | 'error') => {
    setCitySearching(status === 'loading')
  }, [])

  const handleCityMapPick = useCallback((lat: number, lon: number) => {
    setCityMapPin({
      label: `${lat.toFixed(4)}, ${lon.toFixed(4)}`,
      lat,
      lon,
    })
  }, [])

  const handleRegisterMapBounds = useCallback((getter: (() => MapBounds | null) | null) => {
    mapBoundsGetterRef.current = getter
  }, [])

  const requestMapBounds = useCallback(() => mapBoundsGetterRef.current?.() ?? null, [])

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
          routeData={mode === 'route' ? routeData : null}
          routeSearching={mode === 'route' && routeSearching}
          chargePlanData={mode === 'charge' ? chargePlanData : null}
          chargePlanSearching={mode === 'charge' && chargePlanSearching}
          cityData={mode === 'city' ? cityData : null}
          citySearching={mode === 'city' && citySearching}
          focusStation={mode !== 'map' ? selectedStation : null}
          cityPickMode={mode === 'city' && cityPickMode}
          onCityMapPick={handleCityMapPick}
          onRegisterMapBounds={handleRegisterMapBounds}
        />
        <aside className={`side-panel${mode === 'charge' ? ' side-panel--charge' : ''}`}>
          <SearchPanel
            mode={mode}
            vehicleProfile={vehicleProfile}
            onVehiclePresetChange={setVehiclePresetId}
            onVehicleSocChange={setVehicleSoc}
            onVehicleConsumptionChange={setVehicleConsumption}
            onVehicleTerrainChange={setVehicleTerrain}
            minKw={apiQuery.minKw}
            maxKw={apiQuery.maxKw}
            onRouteResults={handleRouteResults}
            onRouteSelectStation={setSelectedStation}
            onRouteSearchStateChange={handleRouteSearchStateChange}
            onChargePlanResults={handleChargePlanResults}
            onChargePlanSelectStation={setSelectedStation}
            onChargePlanSearchStateChange={handleChargePlanSearchStateChange}
            onCityResults={handleCityResults}
            onCitySelectStation={setSelectedStation}
            onCitySearchStateChange={handleCitySearchStateChange}
            onCityPickModeChange={setCityPickMode}
            onRequestMapBounds={requestMapBounds}
            cityMapPin={cityMapPin}
            selectedStationId={selectedStation?.id ?? null}
          />
          {mode !== 'charge' && (
            <VehicleProfilePanel
              profile={vehicleProfile}
              onPresetChange={setVehiclePresetId}
              onSocChange={setVehicleSoc}
              onConsumptionChange={setVehicleConsumption}
              onTerrainChange={setVehicleTerrain}
            />
          )}
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
