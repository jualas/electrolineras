import type { AlongRouteResponse, ChargingPlanResponse, MapBounds, NearbyResponse, Station } from '../api/types'
import type { VehicleProfile } from '../vehicle/vehicleProfile'
import type { TerrainFactorId, VehiclePresetId } from '../vehicle/vehiclePresets'
import { ChargingPlanPanel } from './ChargingPlanPanel'
import { CitySearchPanel } from './CitySearchPanel'
import { RouteSearchPanel } from './RouteSearchPanel'

export type SearchMode = 'map' | 'charge' | 'route' | 'city'

type SearchPanelProps = {
  mode: SearchMode
  vehicleProfile: VehicleProfile
  onVehiclePresetChange: (presetId: VehiclePresetId) => void
  onVehicleSocChange: (socPercent: number) => void
  onVehicleConsumptionChange: (consumptionWhPerKm: number) => void
  onVehicleTerrainChange: (terrainFactorId: TerrainFactorId) => void
  minKw?: number
  maxKw?: number
  onRouteResults: (response: AlongRouteResponse | null) => void
  onRouteSelectStation?: (station: Station | null) => void
  onRouteSearchStateChange?: (status: 'idle' | 'loading' | 'ready' | 'error') => void
  onChargePlanResults: (response: ChargingPlanResponse | null) => void
  onChargePlanSelectStation?: (station: Station | null) => void
  onChargePlanSearchStateChange?: (status: 'idle' | 'loading' | 'ready' | 'error') => void
  onCityResults: (response: NearbyResponse | null) => void
  onCitySelectStation?: (station: Station | null) => void
  onCitySearchStateChange?: (status: 'idle' | 'loading' | 'ready' | 'error') => void
  onCityPickModeChange?: (active: boolean) => void
  onRequestMapBounds?: () => MapBounds | null
  cityMapPin?: { label: string; lat: number; lon: number } | null
  selectedStationId?: string | null
}

export function SearchPanel({
  mode,
  vehicleProfile,
  onVehiclePresetChange,
  onVehicleSocChange,
  onVehicleConsumptionChange,
  onVehicleTerrainChange,
  minKw,
  maxKw,
  onRouteResults,
  onRouteSelectStation,
  onRouteSearchStateChange,
  onChargePlanResults,
  onChargePlanSelectStation,
  onChargePlanSearchStateChange,
  onCityResults,
  onCitySelectStation,
  onCitySearchStateChange,
  onCityPickModeChange,
  onRequestMapBounds,
  cityMapPin,
  selectedStationId,
}: SearchPanelProps) {
  if (mode === 'charge') {
    return (
      <ChargingPlanPanel
        vehicleProfile={vehicleProfile}
        onVehiclePresetChange={onVehiclePresetChange}
        onVehicleSocChange={onVehicleSocChange}
        onVehicleConsumptionChange={onVehicleConsumptionChange}
        onVehicleTerrainChange={onVehicleTerrainChange}
        minKw={minKw}
        maxKw={maxKw}
        onResults={onChargePlanResults}
        onSelectStation={onChargePlanSelectStation}
        onSearchStateChange={onChargePlanSearchStateChange}
        selectedStationId={selectedStationId}
      />
    )
  }

  if (mode === 'route') {
    return (
      <RouteSearchPanel
        minKw={minKw}
        maxKw={maxKw}
        onResults={onRouteResults}
        onSelectStation={onRouteSelectStation}
        onSearchStateChange={onRouteSearchStateChange}
        selectedStationId={selectedStationId}
      />
    )
  }

  if (mode === 'city') {
    return (
      <CitySearchPanel
        minKw={minKw}
        maxKw={maxKw}
        onResults={onCityResults}
        onSelectStation={onCitySelectStation}
        onSearchStateChange={onCitySearchStateChange}
        onPickModeChange={onCityPickModeChange}
        onRequestMapBounds={onRequestMapBounds}
        mapPin={cityMapPin}
        selectedStationId={selectedStationId}
      />
    )
  }

  return (
    <section className="panel search-panel" aria-labelledby="map-search-heading">
      <h2 id="map-search-heading">Mapa peninsular</h2>
      <p className="panel-hint">Puntos desde la API al mover o hacer zoom en el mapa.</p>
    </section>
  )
}
