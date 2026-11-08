import { describe, expect, it } from 'vitest'

import {
  addVehicle,
  createDefaultGarage,
  draftFromPreset,
  driverFactor,
  homologatedFromRange,
  migrateLegacyProfile,
  normalizeGarage,
  predictedKwhPer100km,
  removeVehicle,
  setDriverProfile,
  updateVehicle,
  type GarageState,
} from './garage'
import {
  estimateChargingReachKm,
  estimateDisplayedRangeKm,
  estimatePlanningRangeKm,
  resolveVehicleProfile,
  vehicleProfileToChargingPlanQuery,
} from './vehicleProfile'

const newCar = {
  name: 'Coche nuevo',
  basePresetId: null,
  usableCapacityKwh: 77,
  homologatedKwhPer100km: 16,
  peakDcKw: 200,
  teslaMateLinked: false,
}

function garageWithTwo(): GarageState {
  return addVehicle(createDefaultGarage(), newCar)
}

describe('garaje', () => {
  it('el garaje por defecto tiene el Tesla vinculado a TeslaMate', () => {
    const garage = createDefaultGarage()
    expect(garage.vehicles).toHaveLength(1)
    expect(garage.vehicles[0].teslaMateLinked).toBe(true)
    expect(garage.vehicles[0].basePresetId).toBe('tesla-model3-sr-2023')
  })

  it('añadir un vehículo lo activa y conserva SOC y terreno del viaje', () => {
    const base = { ...createDefaultGarage(), socPercent: 44, terrainFactorId: 'mountain' as const }
    const garage = addVehicle(base, newCar)
    const profile = resolveVehicleProfile(garage)
    expect(profile.name).toBe('Coche nuevo')
    expect(profile.socPercent).toBe(44)
    expect(profile.terrainFactorId).toBe('mountain')
    expect(profile.presetId).toBeNull()
  })

  it('solo un vehículo puede estar vinculado a TeslaMate', () => {
    const garage = garageWithTwo()
    const second = garage.vehicles[1]
    const linked = updateVehicle(garage, second.id, { ...newCar, teslaMateLinked: true })
    expect(linked.vehicles.filter((item) => item.teslaMateLinked).map((item) => item.id)).toEqual([second.id])
  })

  it('no se puede quitar el último vehículo; quitar el activo cambia al primero', () => {
    const single = createDefaultGarage()
    expect(removeVehicle(single, single.vehicles[0].id)).toBe(single)

    const garage = garageWithTwo()
    const removed = removeVehicle(garage, garage.activeVehicleId)
    expect(removed.vehicles).toHaveLength(1)
    expect(removed.activeVehicleId).toBe(removed.vehicles[0].id)
  })

  it('quitar el coche de referencia borra el perfil de conducción', () => {
    let garage = garageWithTwo()
    const second = garage.vehicles[1]
    garage = setDriverProfile(garage, { referenceVehicleId: second.id, measuredKwhPer100km: 18 })
    expect(garage.driver).not.toBeNull()
    expect(removeVehicle(garage, second.id).driver).toBeNull()
  })

  it('normaliza datos corruptos o fuera de rango', () => {
    const garage = normalizeGarage({
      vehicles: [{ id: 'a', name: '  ', usableCapacityKwh: 5000, homologatedKwhPer100km: -3, peakDcKw: 'x' }],
      activeVehicleId: 'zzz',
      socPercent: 300,
      terrainFactorId: 'luna',
      driver: { referenceVehicleId: 'no-existe', measuredKwhPer100km: 15 },
    })
    const vehicle = garage.vehicles[0]
    expect(vehicle.name).toBe('Mi coche')
    expect(vehicle.usableCapacityKwh).toBe(200)
    expect(vehicle.homologatedKwhPer100km).toBe(8)
    expect(garage.activeVehicleId).toBe('a')
    expect(garage.socPercent).toBe(100)
    expect(garage.terrainFactorId).toBe('flat')
    expect(garage.driver).toBeNull()
    expect(normalizeGarage(null).vehicles).toHaveLength(1)
  })
})

describe('consumo homologado y perfil de conducción', () => {
  it('autonomía WLTP → consumo homologado', () => {
    expect(homologatedFromRange(77, 550)).toBe(14)
    expect(homologatedFromRange(0, 550)).toBeNull()
  })

  it('sin perfil se planifica con el homologado', () => {
    const garage = garageWithTwo()
    expect(driverFactor(garage)).toBe(1)
    expect(resolveVehicleProfile(garage).consumptionWhPerKm).toBe(160)
  })

  it('el factor medido en un coche se aplica a los demás', () => {
    let garage = garageWithTwo()
    const tesla = garage.vehicles[0]
    // Tesla homologado 14 (preset) → real 12,6 ⇒ factor 0,9
    garage = setDriverProfile(garage, {
      referenceVehicleId: tesla.id,
      measuredKwhPer100km: tesla.homologatedKwhPer100km * 0.9,
    })
    expect(driverFactor(garage)).toBeCloseTo(0.9, 2)
    const profile = resolveVehicleProfile(garage) // activo: coche nuevo (16 homologado)
    expect(profile.consumptionWhPerKm).toBe(144)
    expect(predictedKwhPer100km(garage, garage.vehicles[1], 'mountain')).toBe(18)
  })

  it('las autonomías salen de batería y consumo (igual que la API)', () => {
    const garage = { ...garageWithTwo(), socPercent: 50 }
    const profile = resolveVehicleProfile(garage) // 77 kWh, 160 Wh/km
    expect(estimateDisplayedRangeKm(profile)).toBe(241) // 38,5 / 0,16
    expect(estimatePlanningRangeKm(profile)).toBe(193) // 30,8 / 0,16
    expect(estimateChargingReachKm(profile)).toBe(217) // 34,65 / 0,16
  })

  it('la consulta a la API usa los datos del vehículo y omite preset si es libre', () => {
    const query = vehicleProfileToChargingPlanQuery(resolveVehicleProfile(garageWithTwo()))
    expect(query.usable_capacity_kwh).toBe(77)
    expect(query.consumption_wh_per_km).toBe(160)
    expect(query).not.toHaveProperty('vehicle_preset_id')

    const teslaQuery = vehicleProfileToChargingPlanQuery(resolveVehicleProfile(createDefaultGarage()))
    expect(teslaQuery.vehicle_preset_id).toBe('tesla-model3-sr-2023')
  })
})

describe('migración del perfil antiguo', () => {
  it('conserva modelo, SOC y terreno', () => {
    const garage = migrateLegacyProfile({
      presetId: 'vw-id3-pro',
      socPercent: 62,
      consumptionWhPerKm: 136,
      terrainFactorId: 'rolling',
    })
    expect(garage.vehicles[0].basePresetId).toBe('vw-id3-pro')
    expect(garage.socPercent).toBe(62)
    expect(garage.terrainFactorId).toBe('rolling')
    expect(garage.driver).toBeNull()
  })

  it('un consumo ajustado a mano se convierte en perfil de conducción con el mismo resultado', () => {
    const garage = migrateLegacyProfile({ presetId: 'tesla-model3-sr-2023', consumptionWhPerKm: 150 })
    expect(garage.driver?.measuredKwhPer100km).toBe(15)
    expect(resolveVehicleProfile(garage).consumptionWhPerKm).toBe(150)
  })

  it('ignora valores antiguos del catálogo', () => {
    const garage = migrateLegacyProfile({ presetId: 'tesla-model3-sr-2023', consumptionWhPerKm: 142 })
    expect(garage.driver).toBeNull()
    expect(resolveVehicleProfile(garage).consumptionWhPerKm).toBe(
      Math.round(draftFromPreset('tesla-model3-sr-2023').homologatedKwhPer100km * 10),
    )
  })
})
