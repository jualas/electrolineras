import { useCallback, useEffect, useState } from 'react'

import {
  createDefaultVehicleProfile,
  loadStoredVehicleProfile,
  normalizeVehicleProfile,
  profileFromPreset,
  storeVehicleProfile,
  type VehicleProfile,
} from '../vehicle/vehicleProfile'
import type { TerrainFactorId, VehiclePresetId } from '../vehicle/vehiclePresets'

export function useVehicleProfile() {
  const [profile, setProfileState] = useState<VehicleProfile>(() => {
    return loadStoredVehicleProfile() ?? createDefaultVehicleProfile()
  })

  useEffect(() => {
    storeVehicleProfile(profile)
  }, [profile])

  const setPresetId = useCallback((presetId: VehiclePresetId) => {
    setProfileState((current) => profileFromPreset(presetId, current))
  }, [])

  const setSocPercent = useCallback((socPercent: number) => {
    setProfileState((current) => normalizeVehicleProfile({ ...current, socPercent }))
  }, [])

  const setConsumptionWhPerKm = useCallback((consumptionWhPerKm: number) => {
    setProfileState((current) => normalizeVehicleProfile({ ...current, consumptionWhPerKm }))
  }, [])

  const setTerrainFactorId = useCallback((terrainFactorId: TerrainFactorId) => {
    setProfileState((current) => normalizeVehicleProfile({ ...current, terrainFactorId }))
  }, [])

  return {
    profile,
    setPresetId,
    setSocPercent,
    setConsumptionWhPerKm,
    setTerrainFactorId,
  }
}
