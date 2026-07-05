import type { SearchMode } from '../search/SearchPanel'

/** Plan de carga dedicado en menú (reservado a despliegues privados / futuro). */
export const CHARGE_PLAN_NAV_ENABLED =
  import.meta.env.VITE_CHARGE_PLAN_NAV_ENABLED === 'true'

export const APP_NAV_MODES: { id: SearchMode; label: string }[] = [
  { id: 'map', label: 'Mapa' },
  ...(CHARGE_PLAN_NAV_ENABLED ? [{ id: 'charge' as const, label: 'Plan carga' }] : []),
  { id: 'route', label: 'En ruta' },
  { id: 'assistant', label: 'Asistente' },
]

export function isNavModeEnabled(mode: SearchMode): boolean {
  return APP_NAV_MODES.some((item) => item.id === mode)
}

export function defaultNavMode(): SearchMode {
  return 'map'
}
