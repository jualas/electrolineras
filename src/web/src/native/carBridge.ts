import { Capacitor } from '@capacitor/core'
import { Preferences } from '@capacitor/preferences'

/**
 * Puente de configuración persistente entre la UI React/Capacitor y el futuro
 * módulo nativo Android Auto / Android Automotive OS (Kotlin CarAppService).
 *
 * En Android, `@capacitor/preferences` guarda en SharedPreferences (`CapacitorStorage`),
 * de modo que el servicio nativo del coche hereda automáticamente el filtro de potencia,
 * el vehículo activo, la URL de la API y el token de acceso sin pedirlos al volante.
 */

export const CAR_BRIDGE_KEYS = {
  apiBaseUrl: 'car_api_base_url',
  privateToken: 'car_private_token',
  minKw: 'car_filter_min_kw',
  maxKw: 'car_filter_max_kw',
  vehiclePresetId: 'car_vehicle_preset_id',
} as const

export function isNativeAndroidApp(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.getPlatform() === 'android'
}

export async function readBridgePreference(key: string): Promise<string | null> {
  try {
    if (Capacitor.isNativePlatform()) {
      const { value } = await Preferences.get({ key })
      return value ?? null
    }
    return window.localStorage.getItem(key)
  } catch {
    return null
  }
}

export async function writeBridgePreference(key: string, value: string | null): Promise<void> {
  try {
    if (Capacitor.isNativePlatform()) {
      if (value == null || value === '') {
        await Preferences.remove({ key })
      } else {
        await Preferences.set({ key, value })
      }
      return
    }
    if (value == null || value === '') {
      window.localStorage.removeItem(key)
    } else {
      window.localStorage.setItem(key, value)
    }
  } catch {
    // Ignorar errores de almacenamiento (modo privado / cuota)
  }
}

export async function syncCarBridgePowerFilter(minKw?: number, maxKw?: number): Promise<void> {
  await Promise.all([
    writeBridgePreference(CAR_BRIDGE_KEYS.minKw, minKw != null ? String(minKw) : null),
    writeBridgePreference(CAR_BRIDGE_KEYS.maxKw, maxKw != null ? String(maxKw) : null),
  ])
}

export async function syncCarBridgeApiBase(apiBaseUrl: string): Promise<void> {
  await writeBridgePreference(CAR_BRIDGE_KEYS.apiBaseUrl, apiBaseUrl.trim() || null)
}
