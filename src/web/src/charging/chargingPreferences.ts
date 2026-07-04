export type ChargingPreferencesState = {
  preferredOperators: string[]
  maxPriceEurKwh: number | null
}

export const DEFAULT_CHARGING_PREFERENCES: ChargingPreferencesState = {
  preferredOperators: [],
  maxPriceEurKwh: null,
}

export const CHARGING_PREFERENCES_STORAGE_KEY = 'electrolineras.chargingPreferences'

export const FALLBACK_OPERATOR_CHIPS = [
  'Ionity',
  'Tesla',
  'Repsol',
  'Endesa',
  'Iberdrola',
  'Wenea',
  'Zunder',
] as const

export function normalizeOperatorChip(label: string): string {
  return label.trim()
}

export function toggleOperatorSelection(
  current: string[],
  operator: string,
): string[] {
  const normalized = normalizeOperatorChip(operator)
  const key = normalized.toLowerCase()
  const exists = current.some((item) => item.toLowerCase() === key)
  if (exists) {
    return current.filter((item) => item.toLowerCase() !== key)
  }
  return [...current, normalized]
}

export function chargingPreferencesToQueryParams(
  prefs: ChargingPreferencesState,
): Record<string, string> {
  const params: Record<string, string> = {}
  if (prefs.preferredOperators.length > 0) {
    params.preferred_operators = prefs.preferredOperators.join(',')
  }
  if (prefs.maxPriceEurKwh != null && prefs.maxPriceEurKwh > 0) {
    params.max_price_eur_kwh = String(prefs.maxPriceEurKwh)
  }
  return params
}

export function parseStoredChargingPreferences(raw: string | null): ChargingPreferencesState {
  if (!raw) {
    return DEFAULT_CHARGING_PREFERENCES
  }
  try {
    const parsed = JSON.parse(raw) as Partial<ChargingPreferencesState>
    const preferredOperators = Array.isArray(parsed.preferredOperators)
      ? parsed.preferredOperators
          .filter((item): item is string => typeof item === 'string')
          .map(normalizeOperatorChip)
          .filter(Boolean)
      : []
    const maxPriceEurKwh =
      typeof parsed.maxPriceEurKwh === 'number' && parsed.maxPriceEurKwh > 0
        ? parsed.maxPriceEurKwh
        : null
    return { preferredOperators, maxPriceEurKwh }
  } catch {
    return DEFAULT_CHARGING_PREFERENCES
  }
}

export function formatChargingPreferencesSummary(prefs: ChargingPreferencesState): string {
  const parts: string[] = []
  if (prefs.preferredOperators.length > 0) {
    parts.push(prefs.preferredOperators.slice(0, 3).join(', '))
  }
  if (prefs.maxPriceEurKwh != null) {
    parts.push(`≤ ${prefs.maxPriceEurKwh.toFixed(2)} €/kWh`)
  }
  return parts.join(' · ')
}
