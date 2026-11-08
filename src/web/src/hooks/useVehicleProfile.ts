import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

import {
  addVehicle as addVehicleToGarage,
  loadStoredGarage,
  removeVehicle as removeVehicleFromGarage,
  selectVehicle as selectGarageVehicle,
  setDriverProfile as setGarageDriverProfile,
  setSoc,
  setTerrain,
  storeGarage,
  updateVehicle as updateGarageVehicle,
  type DriverProfile,
  type GarageState,
  type GarageVehicleDraft,
} from '../vehicle/garage'
import { resolveVehicleProfile, type VehicleProfile } from '../vehicle/vehicleProfile'
import type { TerrainFactorId } from '../vehicle/vehiclePresets'

export type VehicleGarageApi = {
  garage: GarageState
  profile: VehicleProfile
  selectVehicle: (vehicleId: string) => void
  addVehicle: (draft: GarageVehicleDraft) => void
  updateVehicle: (vehicleId: string, draft: GarageVehicleDraft) => void
  removeVehicle: (vehicleId: string) => void
  setDriverProfile: (driver: DriverProfile | null) => void
  setSocPercent: (socPercent: number) => void
  setTerrainFactorId: (terrainFactorId: TerrainFactorId) => void
}

export function useVehicleProfile(): VehicleGarageApi {
  const [garage, setGarage] = useState<GarageState>(loadStoredGarage)

  useEffect(() => {
    storeGarage(garage)
  }, [garage])

  const profile = useMemo(() => resolveVehicleProfile(garage), [garage])

  const selectVehicle = useCallback((vehicleId: string) => {
    setGarage((current) => selectGarageVehicle(current, vehicleId))
  }, [])
  const addVehicle = useCallback((draft: GarageVehicleDraft) => {
    setGarage((current) => addVehicleToGarage(current, draft))
  }, [])
  const updateVehicle = useCallback((vehicleId: string, draft: GarageVehicleDraft) => {
    setGarage((current) => updateGarageVehicle(current, vehicleId, draft))
  }, [])
  const removeVehicle = useCallback((vehicleId: string) => {
    setGarage((current) => removeVehicleFromGarage(current, vehicleId))
  }, [])
  const setDriverProfile = useCallback((driver: DriverProfile | null) => {
    setGarage((current) => setGarageDriverProfile(current, driver))
  }, [])
  const setSocPercent = useCallback((socPercent: number) => {
    setGarage((current) => setSoc(current, socPercent))
  }, [])
  const setTerrainFactorId = useCallback((terrainFactorId: TerrainFactorId) => {
    setGarage((current) => setTerrain(current, terrainFactorId))
  }, [])

  return {
    garage,
    profile,
    selectVehicle,
    addVehicle,
    updateVehicle,
    removeVehicle,
    setDriverProfile,
    setSocPercent,
    setTerrainFactorId,
  }
}

export const VehicleGarageContext = createContext<VehicleGarageApi | null>(null)

/** Garaje compartido (lo provee AppShell). */
export function useVehicleGarage(): VehicleGarageApi {
  const value = useContext(VehicleGarageContext)
  if (!value) {
    throw new Error('useVehicleGarage requiere VehicleGarageContext (AppShell)')
  }
  return value
}
