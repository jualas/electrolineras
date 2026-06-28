import type { AlongRouteResponse, ChargingPlanResponse, Station } from '../api/types'
import type { VehicleProfile } from '../vehicle/vehicleProfile'
import type { TerrainFactorId, VehiclePresetId } from '../vehicle/vehiclePresets'
import { ChargingPlanPanel } from './ChargingPlanPanel'
import { MapSearchPanel } from './MapSearchPanel'
import { RouteSearchPanel } from './RouteSearchPanel'

export type SearchMode = 'map' | 'charge' | 'route'

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
  onRouteChargePlanResults?: (response: ChargingPlanResponse | null) => void
  onRouteSelectStation?: (station: Station | null) => void
  onRouteSearchStateChange?: (status: 'idle' | 'loading' | 'ready' | 'error') => void
  onChargePlanResults: (response: ChargingPlanResponse | null) => void
  onChargePlanSelectStation?: (station: Station | null) => void
  onChargePlanSearchStateChange?: (status: 'idle' | 'loading' | 'ready' | 'error') => void
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
  onRouteChargePlanResults,
  onRouteSelectStation,
  onRouteSearchStateChange,
  onChargePlanResults,
  onChargePlanSelectStation,
  onChargePlanSearchStateChange,
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
        vehicleProfile={vehicleProfile}
        minKw={minKw}
        maxKw={maxKw}
        onResults={onRouteResults}
        onChargePlanResults={onRouteChargePlanResults}
        onSelectStation={onRouteSelectStation}
        onSearchStateChange={onRouteSearchStateChange}
        selectedStationId={selectedStationId}
      />
    )
  }

  return <MapSearchPanel />
}
