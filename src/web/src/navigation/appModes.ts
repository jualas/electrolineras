import type { SearchMode } from '../search/SearchPanel'

/** Plan de carga dedicado en menú (reservado a despliegues privados / futuro). */
export const CHARGE_PLAN_NAV_ENABLED =
  import.meta.env.VITE_CHARGE_PLAN_NAV_ENABLED === 'true'

/** Búsqueda «En ruta» en menú (oculto por defecto; el asistente cubre planificación). */
export const ROUTE_NAV_ENABLED = import.meta.env.VITE_ROUTE_NAV_ENABLED === 'true'

// REVE no tiene un modo "Mapa" aparte: el mapa con todos los puntos de carga está
// siempre visible de fondo, y estas pestañas solo controlan qué panel de planificación
// se muestra encima.
export const APP_NAV_MODES: { id: SearchMode; label: string }[] = [
  ...(CHARGE_PLAN_NAV_ENABLED ? [{ id: 'charge' as const, label: 'Plan carga' }] : []),
  ...(ROUTE_NAV_ENABLED ? [{ id: 'route' as const, label: 'En ruta' }] : []),
  { id: 'assistant', label: 'Asistente' },
]

export function isNavModeEnabled(mode: SearchMode): boolean {
  return APP_NAV_MODES.some((item) => item.id === mode)
}

export function defaultNavMode(): SearchMode {
  return APP_NAV_MODES[0]?.id ?? 'assistant'
}
