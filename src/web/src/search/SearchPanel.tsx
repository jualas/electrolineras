import { AssistantPanel } from '../auth/AssistantPanel'
import { useAuth } from '../auth/AuthContext'
import type { AlongRouteResponse, ChargingPlanResponse, Station } from '../api/types'
import type { VehicleProfile } from '../vehicle/vehicleProfile'
import type { VehiclePresetId } from '../vehicle/vehiclePresets'
import type { MapStationFilterState } from '../filters/MapStationFilters'
import { ChargingPlanPanel } from './ChargingPlanPanel'
import { RouteSearchPanel } from './RouteSearchPanel'

export type SearchMode = 'charge' | 'route' | 'assistant'

type SearchPanelProps = {
  mode: SearchMode
  vehicleProfile: VehicleProfile
  onVehiclePresetChange: (presetId: VehiclePresetId) => void
  onVehicleSocChange: (socPercent: number) => void
  onVehicleConsumptionChange: (consumptionWhPerKm: number) => void
  minKw?: number
  maxKw?: number
  mapStationFilters?: MapStationFilterState
  onMapStationFiltersChange?: (next: MapStationFilterState) => void
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
  const { loading: authLoading, privateStackEnabled } = useAuth()

  if (mode === 'assistant') {
    if (authLoading) {
      return <p className="assistant-panel__muted">Comprobando sesión…</p>
    }

    // Sin stack privado (sin coche conectado por TeslaMate), el asistente es el
    // planificador de ruta público estilo REVE, igual que "Plan de carga".
    if (!privateStackEnabled) {
      return (
        <ChargingPlanPanel
          vehicleProfile={vehicleProfile}
          onVehiclePresetChange={onVehiclePresetChange}
          onVehicleSocChange={onVehicleSocChange}
          onVehicleConsumptionChange={onVehicleConsumptionChange}
          minKw={minKw}
          maxKw={maxKw}
          onResults={onChargePlanResults}
          onSelectStation={onChargePlanSelectStation}
          onSearchStateChange={onChargePlanSearchStateChange}
          selectedStationId={selectedStationId}
        />
      )
    }

    return (
      <AssistantPanel
        vehicleProfile={vehicleProfile}
        onVehicleSocChange={onVehicleSocChange}
        onPlanResults={onChargePlanResults}
        onPlanStateChange={onChargePlanSearchStateChange}
        onSelectStation={onChargePlanSelectStation}
        selectedStationId={selectedStationId}
      />
    )
  }

  if (mode === 'charge') {
    return (
      <ChargingPlanPanel
        vehicleProfile={vehicleProfile}
        onVehiclePresetChange={onVehiclePresetChange}
        onVehicleSocChange={onVehicleSocChange}
        onVehicleConsumptionChange={onVehicleConsumptionChange}
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

  return null
}
