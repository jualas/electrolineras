import { useCallback, useEffect, useRef, useState } from 'react'

import { checkApiHealth } from '../../api/client'
import type { AlongRouteResponse, ChargingPlanResponse, GeocodeResult, MapBounds, Station } from '../../api/types'
import { useAuth } from '../../auth/AuthContext'
import { routeChargingStops, type RouteChargingStop } from '../../charging/planRouteStops'
import { MapStationFilters, type MapStationFilterState } from '../../filters/MapStationFilters'
import { PowerFilterPanel } from '../../filters/PowerFilterPanel'
import { usePowerFilter } from '../../hooks/usePowerFilter'
import { useTheme } from '../../hooks/useTheme'
import { useVehicleProfile } from '../../hooks/useVehicleProfile'
import type { MapLayerToggles } from '../../map/MapLayerControl'
import { MapView } from '../../map/MapView'
import { MapFloatingSearch } from '../../map/MapFloatingSearch'
import {
  APP_NAV_MODES,
  CHARGE_PLAN_NAV_ENABLED,
  defaultNavMode,
  isNavModeEnabled,
} from '../../navigation/appModes'
import { SearchPanel, type SearchMode } from '../../search/SearchPanel'
import { ThemeToggle } from './ThemeToggle'
import { VehicleProfilePanel } from '../vehicle/VehicleProfilePanel'

const DEFAULT_MAP_LAYERS: MapLayerToggles = {
  detail: false,
  traffic: false,
}

const DEFAULT_MAP_STATION_FILTERS: MapStationFilterState = {
  availableOnly: false,
  adHocOnly: false,
  connectorTypes: [],
  maxPriceEurKwh: null,
}

const MODE_DEFAULT_PRESET: Partial<Record<SearchMode, 'trip' | 'slow'>> = {
  charge: 'trip',
  route: 'trip',
}

export function AppShell() {
  const { theme, toggleTheme } = useTheme()
  const { privateStackEnabled, authenticated, username, logout } = useAuth()
  const [mode, setMode] = useState<SearchMode>(defaultNavMode)
  const [panelOpen, setPanelOpen] = useState(false)
  const [apiOk, setApiOk] = useState(false)
  const [routeData, setRouteData] = useState<AlongRouteResponse | null>(null)
  const [routeChargePlanData, setRouteChargePlanData] = useState<ChargingPlanResponse | null>(null)
  const [routeSearching, setRouteSearching] = useState(false)
  const [chargePlanData, setChargePlanData] = useState<ChargingPlanResponse | null>(null)
  const [chargePlanSearching, setChargePlanSearching] = useState(false)
  const [selectedStation, setSelectedStation] = useState<Station | null>(null)
  const [selectedPlannedStopOrder, setSelectedPlannedStopOrder] = useState<number | null>(null)
  const [mapFocusPlace, setMapFocusPlace] = useState<GeocodeResult | null>(null)
  const [mapSearchText, setMapSearchText] = useState('')
  const [mapLayers, setMapLayers] = useState<MapLayerToggles>(DEFAULT_MAP_LAYERS)
  const [mapStationFilters, setMapStationFilters] = useState<MapStationFilterState>(DEFAULT_MAP_STATION_FILTERS)
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

  useEffect(() => {
    if (!isNavModeEnabled(mode)) {
      setMode(defaultNavMode())
      setPanelOpen(false)
    }
  }, [mode])

  const handleModeChange = (nextMode: SearchMode) => {
    if (!isNavModeEnabled(nextMode)) {
      return
    }
    setMode(nextMode)
    const defaultPreset = MODE_DEFAULT_PRESET[nextMode]
    if (defaultPreset) {
      setPreset(defaultPreset)
    }
    if (nextMode !== 'route') {
      setRouteData(null)
      setRouteChargePlanData(null)
      setRouteSearching(false)
    }
    if (nextMode !== 'charge' && nextMode !== 'assistant') {
      setChargePlanData(null)
      setChargePlanSearching(false)
    }
    if (nextMode !== 'map') {
      setMapFocusPlace(null)
      setMapSearchText('')
    }
    if (nextMode === 'assistant') {
      setPanelOpen(true)
    }
    setSelectedStation(null)
    setSelectedPlannedStopOrder(null)
    setPanelOpen(nextMode !== 'map')
  }

  const activeChargePlan = useCallback((): ChargingPlanResponse | null => {
    if (mode === 'assistant' || (CHARGE_PLAN_NAV_ENABLED && mode === 'charge')) {
      return chargePlanData
    }
    if (mode === 'route') {
      return routeChargePlanData
    }
    return null
  }, [mode, chargePlanData, routeChargePlanData])

  const resolvePlannedStopOrder = useCallback(
    (station: Station | null, plan: ChargingPlanResponse | null): number | null => {
      if (!station || !plan) {
        return null
      }
      const fromPlanned = plan.planned_stops?.find((stop) => stop.station.id === station.id)
      if (fromPlanned) {
        return fromPlanned.order
      }
      const routeStops = routeChargingStops(plan)
      const index = routeStops.findIndex((stop) => stop.station.id === station.id)
      if (index < 0) {
        return null
      }
      const stop = routeStops[index]
      if ('order' in stop && typeof stop.order === 'number') {
        return stop.order
      }
      return index + 1
    },
    [],
  )

  const handleSelectStation = useCallback(
    (station: Station | null) => {
      setSelectedStation(station)
      setSelectedPlannedStopOrder(resolvePlannedStopOrder(station, activeChargePlan()))
      if (station) {
        setPanelOpen(true)
      }
    },
    [activeChargePlan, resolvePlannedStopOrder],
  )

  const handlePlannedStopSelect = useCallback(
    (stop: RouteChargingStop | null) => {
      if (!stop) {
        setSelectedStation(null)
        setSelectedPlannedStopOrder(null)
        return
      }
      setSelectedStation(stop.station)
      if ('order' in stop && typeof stop.order === 'number') {
        setSelectedPlannedStopOrder(stop.order)
      } else {
        const plan = activeChargePlan()
        const routeStops = plan ? routeChargingStops(plan) : []
        const index = routeStops.findIndex((item) => item.station.id === stop.station.id)
        setSelectedPlannedStopOrder(index >= 0 ? index + 1 : null)
      }
      setPanelOpen(true)
    },
    [activeChargePlan],
  )

  const handleRouteResults = useCallback((response: AlongRouteResponse | null) => {
    setRouteData(response)
    setSelectedStation(null)
    setSelectedPlannedStopOrder(null)
  }, [])

  const handleRouteChargePlanResults = useCallback((response: ChargingPlanResponse | null) => {
    setRouteChargePlanData(response)
  }, [])

  const handleRouteSearchStateChange = useCallback((status: 'idle' | 'loading' | 'ready' | 'error') => {
    setRouteSearching(status === 'loading')
  }, [])

  const handleChargePlanResults = useCallback((response: ChargingPlanResponse | null) => {
    setChargePlanData(response)
    setSelectedStation(null)
    setSelectedPlannedStopOrder(null)
  }, [])

  const handleChargePlanSearchStateChange = useCallback((status: 'idle' | 'loading' | 'ready' | 'error') => {
    setChargePlanSearching(status === 'loading')
  }, [])

  const handleMapFocusPlace = useCallback((place: GeocodeResult | null) => {
    setMapFocusPlace(place)
    setMapSearchText(place?.label ?? '')
    setSelectedStation(null)
    setSelectedPlannedStopOrder(null)
  }, [])

  const handleMapSearchTextChange = useCallback(
    (text: string) => {
      setMapSearchText(text)
      if (mapFocusPlace && text.trim() !== mapFocusPlace.label.trim()) {
        setMapFocusPlace(null)
      }
    },
    [mapFocusPlace],
  )

  const clearMapSearch = useCallback(() => {
    setMapSearchText('')
    setMapFocusPlace(null)
    setSelectedStation(null)
    setSelectedPlannedStopOrder(null)
  }, [])

  const handleRegisterMapBounds = useCallback((getter: (() => MapBounds | null) | null) => {
    mapBoundsGetterRef.current = getter
  }, [])

  return (
    <div className={`app-shell${mode === 'map' ? ' app-shell--map-search' : ''}`}>
      <MapView
        className="app-map"
        theme={theme}
        loadStations={mode === 'map'}
        minKw={mode === 'map' ? apiQuery.minKw : apiQuery.minKw}
        maxKw={mode === 'map' ? apiQuery.maxKw : apiQuery.maxKw}
        publicOpenOnly={mode === 'map'}
        adHocOnly={mode === 'map' ? mapStationFilters.adHocOnly : false}
        availableOnly={mode === 'map' ? mapStationFilters.availableOnly : false}
        maxPriceEurKwh={mode === 'map' ? mapStationFilters.maxPriceEurKwh : null}
        connectorTypes={mode === 'map' ? mapStationFilters.connectorTypes : []}
        mapLayers={mode === 'map' ? mapLayers : undefined}
        onMapLayersChange={mode === 'map' ? setMapLayers : undefined}
        showLayerControl={mode === 'map'}
        routeData={mode === 'route' ? routeData : null}
        routeChargePlanData={mode === 'route' ? routeChargePlanData : null}
        routeSearching={mode === 'route' && routeSearching}
        chargePlanData={
          mode === 'assistant' || (CHARGE_PLAN_NAV_ENABLED && mode === 'charge') ? chargePlanData : null
        }
        chargePlanSearching={
          (mode === 'assistant' || (CHARGE_PLAN_NAV_ENABLED && mode === 'charge')) && chargePlanSearching
        }
        focusStation={mode !== 'map' ? selectedStation : null}
        selectedPlannedStopOrder={mode !== 'map' ? selectedPlannedStopOrder : null}
        onPlannedStopSelect={mode !== 'map' ? handlePlannedStopSelect : undefined}
        mapFocusPlace={mode === 'map' ? mapFocusPlace : null}
        onRegisterMapBounds={handleRegisterMapBounds}
      />

      <div className="map-ui-layer">
        <div className="map-top-cluster">
          <header className="map-top-bar">
            <button
              type="button"
              className="map-menu-btn"
              onClick={() => setPanelOpen((open) => !open)}
              aria-expanded={panelOpen}
              aria-controls="app-side-panel"
              aria-label={panelOpen ? 'Ocultar panel' : 'Mostrar búsqueda y filtros'}
            >
              {panelOpen ? '✕' : '☰'}
            </button>
            <div className="map-top-bar__brand">
              <span className="map-top-bar__title">Electrolineras</span>
              <span
                className={`status-pill status-pill--compact ${apiOk ? 'status-pill--ok' : 'status-pill--warn'}`}
                title={apiOk ? 'API conectada' : 'API no disponible'}
              >
                {apiOk ? '●' : '○'}
              </span>
            </div>
            <nav className="map-mode-tabs" aria-label="Modo de búsqueda">
              {APP_NAV_MODES.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`map-mode-tab ${mode === item.id ? 'map-mode-tab--active' : ''}`}
                  onClick={() => handleModeChange(item.id)}
                  aria-pressed={mode === item.id}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            {privateStackEnabled && authenticated ? (
              <button
                type="button"
                className="map-logout-btn"
                onClick={() => void logout()}
                title={username ? `Cerrar sesión (${username})` : 'Cerrar sesión'}
              >
                Salir
              </button>
            ) : null}
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
          </header>

          {mode === 'map' && (
            <MapFloatingSearch
              value={mapSearchText}
              focusPlace={mapFocusPlace}
              onChange={handleMapSearchTextChange}
              onSelect={handleMapFocusPlace}
              onClear={clearMapSearch}
            />
          )}
        </div>

        {panelOpen && (
          <button
            type="button"
            className={`map-scrim map-scrim--mode-${mode}`}
            aria-label="Cerrar panel"
            onClick={() => setPanelOpen(false)}
          />
        )}

        <aside
          id="app-side-panel"
          className={`map-side-panel${panelOpen ? ' map-side-panel--open' : ''}${mode === 'assistant' || (CHARGE_PLAN_NAV_ENABLED && mode === 'charge') ? ' map-side-panel--charge' : ''}`}
          aria-hidden={!panelOpen}
        >
          <SearchPanel
            mode={mode}
            vehicleProfile={vehicleProfile}
            onVehiclePresetChange={setVehiclePresetId}
            onVehicleSocChange={setVehicleSoc}
            onVehicleConsumptionChange={setVehicleConsumption}
            onVehicleTerrainChange={setVehicleTerrain}
            minKw={apiQuery.minKw}
            maxKw={apiQuery.maxKw}
            mapStationFilters={mapStationFilters}
            onMapStationFiltersChange={setMapStationFilters}
            onRouteResults={handleRouteResults}
            onRouteChargePlanResults={handleRouteChargePlanResults}
            onRouteSelectStation={handleSelectStation}
            onRouteSearchStateChange={handleRouteSearchStateChange}
            onChargePlanResults={handleChargePlanResults}
            onChargePlanSelectStation={handleSelectStation}
            onChargePlanSearchStateChange={handleChargePlanSearchStateChange}
            selectedStationId={selectedStation?.id ?? null}
          />
          {mode === 'map' && (
            <>
              <PowerFilterPanel
                filter={filter}
                onPresetChange={setPreset}
                onCustomRangeChange={setCustomRange}
              />
              <MapStationFilters filter={mapStationFilters} onChange={setMapStationFilters} />
            </>
          )}
          {mode !== 'map' &&
            mode !== 'assistant' &&
            !(CHARGE_PLAN_NAV_ENABLED && mode === 'charge') && (
            <VehicleProfilePanel
              profile={vehicleProfile}
              onPresetChange={setVehiclePresetId}
              onSocChange={setVehicleSoc}
              onConsumptionChange={setVehicleConsumption}
              onTerrainChange={setVehicleTerrain}
            />
          )}
          {mode !== 'map' && (
            <PowerFilterPanel
              filter={filter}
              onPresetChange={setPreset}
              onCustomRangeChange={setCustomRange}
            />
          )}
        </aside>
      </div>
    </div>
  )
}
