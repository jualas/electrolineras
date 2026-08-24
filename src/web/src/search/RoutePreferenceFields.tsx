import type { RoutePreference } from '../api/types'

type RoutePreferenceFieldsProps = {
  routePreference: RoutePreference
  avoidTolls: boolean
  onRoutePreferenceChange: (value: RoutePreference) => void
  onAvoidTollsChange: (value: boolean) => void
  disabled?: boolean
  /** Asistente: texto más explícito sobre autovía vs peaje */
  variant?: 'default' | 'assistant'
}

export function RoutePreferenceFields({
  routePreference,
  avoidTolls,
  onRoutePreferenceChange,
  onAvoidTollsChange,
  disabled = false,
  variant = 'default',
}: RoutePreferenceFieldsProps) {
  const fastestHint =
    variant === 'assistant'
      ? 'Menor tiempo con velocidades reales de cada vía; autovía si compensa.'
      : 'Menor tiempo; autovía cuando reduce duración.'

  return (
    <fieldset className="route-preference" disabled={disabled}>
      <legend className="field__label">Tipo de ruta</legend>
      <div className="route-preference__options" role="radiogroup" aria-label="Tipo de ruta">
        <label className="route-preference__option">
          <input
            type="radio"
            name="route-preference"
            value="shortest"
            checked={routePreference === 'shortest'}
            onChange={() => onRoutePreferenceChange('shortest')}
          />
          <span>
            Más directa (menos km)
            <span className="route-preference__hint">
              Prioriza la ruta más recta posible; puede ser más lenta que la rápida.
            </span>
          </span>
        </label>
        <label className="route-preference__option">
          <input
            type="radio"
            name="route-preference"
            value="fastest"
            checked={routePreference === 'fastest'}
            onChange={() => onRoutePreferenceChange('fastest')}
          />
          <span>
            Más rápida
            <span className="route-preference__hint">{fastestHint}</span>
          </span>
        </label>
        <label className="route-preference__option">
          <input
            type="radio"
            name="route-preference"
            value="conventional"
            checked={routePreference === 'conventional'}
            onChange={() => onRoutePreferenceChange('conventional')}
          />
          <span>
            Solo convencionales
            <span className="route-preference__hint">
              Nacionales y locales; sin autovía. El tiempo no importa.
            </span>
          </span>
        </label>
      </div>
      <label className="field field--checkbox route-preference__avoid">
        <input
          type="checkbox"
          checked={avoidTolls}
          onChange={(event) => onAvoidTollsChange(event.target.checked)}
        />
        <span>Evitar autopistas de peaje (sin telepeaje)</span>
      </label>
    </fieldset>
  )
}

export function routePreferenceLabel(preference: RoutePreference | null | undefined): string {
  if (preference === 'shortest') {
    return 'Ruta más directa'
  }
  if (preference === 'fastest') {
    return 'Ruta más rápida'
  }
  if (preference === 'conventional') {
    return 'Ruta convencional'
  }
  return 'Ruta'
}

export function avoidTollsLabel(avoidTolls: boolean | undefined): string {
  return avoidTolls ? ' · sin peajes' : ''
}

type RouteAlternativesKm = {
  route_preference?: RoutePreference | null
  route_distance_km?: number | null
  route_duration_minutes?: number | null
  geodesic_distance_km?: number | null
  route_shortest_distance_km?: number | null
  route_fastest_distance_km?: number | null
  route_conventional_distance_km?: number | null
  route_conventional_duration_minutes?: number | null
  shortest_excess_km?: number | null
  route_variants_approximate?: boolean
}

function formatDurationMinutes(minutes: number | null | undefined): string {
  if (minutes == null || minutes <= 0) {
    return ''
  }
  const rounded = Math.round(minutes)
  const hours = Math.floor(rounded / 60)
  const mins = rounded % 60
  if (hours > 0) {
    return mins > 0 ? `${hours} h ${mins} min` : `${hours} h`
  }
  return `${mins} min`
}

export function formatRouteAlternativesKm(plan: RouteAlternativesKm): string {
  const geodesic = plan.geodesic_distance_km
  const shortest = plan.route_shortest_distance_km ?? plan.route_distance_km
  const fastest = plan.route_fastest_distance_km ?? plan.route_distance_km
  const conventional = plan.route_conventional_distance_km
  const parts: string[] = []

  if (geodesic != null) {
    parts.push(`Línea recta: ${geodesic.toFixed(0)} km`)
  }
  if (shortest != null) {
    const excess =
      plan.shortest_excess_km != null && plan.shortest_excess_km > 0
        ? ` (+${plan.shortest_excess_km.toFixed(0)} km)`
        : ''
    parts.push(`Directa: ${shortest.toFixed(0)} km${excess}`)
  }
  if (fastest != null) {
    const duration =
      plan.route_preference === 'fastest'
        ? formatDurationMinutes(plan.route_duration_minutes)
        : ''
    parts.push(`Rápida: ${fastest.toFixed(0)} km${duration ? ` · ${duration}` : ''}`)
  }
  if (conventional != null) {
    const duration = formatDurationMinutes(plan.route_conventional_duration_minutes)
    const approx =
      plan.route_variants_approximate && plan.route_preference === 'conventional' ? ' ~aprox.' : ''
    parts.push(`Convencionales: ${conventional.toFixed(0)} km${duration ? ` · ${duration}` : ''}${approx}`)
  }

  const selectedKm = plan.route_distance_km
  if (selectedKm != null && plan.route_preference) {
    const selectedLabel =
      plan.route_preference === 'shortest'
        ? 'directa'
        : plan.route_preference === 'fastest'
          ? 'rápida'
          : 'convencionales'
    const approx = plan.route_variants_approximate ? ' ~aprox.' : ''
    parts.push(`Plan: ${selectedLabel} (${selectedKm.toFixed(0)} km${approx})`)
  }

  return parts.join(' · ')
}
