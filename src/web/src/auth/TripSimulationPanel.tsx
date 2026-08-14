import { useMemo, useState } from 'react'

import {
  fetchMultiLegChargingPlan,
  fetchTripGuideFromCar,
  parseItineraryFromCar,
} from '../api/auth'
import type {
  ItineraryPlaceResult,
  MultiLegChargingPlanResponse,
  RoutePreference,
  TripGuideResponse,
} from '../api/types'
import { RouteExportActions } from '../components/navigation/RouteExportActions'
import type { RouteExportSpec } from '../navigation/externalMaps'
import { ChargingPlanResults } from '../search/ChargingPlanResults'
import { formatDurationMinutes } from '../search/RoutePreferenceFields'
import type { RevePlanningOptions } from '../search/RevePlanningFields'

type Props = {
  routePreference: RoutePreference
  avoidTolls: boolean
  revePlanning: RevePlanningOptions
  disabled?: boolean
  onPlanForMap: (plan: MultiLegChargingPlanResponse['legs'][0]['plan'] | null) => void
  onBusyChange?: (busy: boolean) => void
}

const PLACEHOLDER =
  'Ej.: Vamos el sábado a Camping Garrote Gordo y volvemos a casa el domingo (salimos al 100 %).'

function multiLegExportSpec(result: MultiLegChargingPlanResponse): RouteExportSpec | null {
  const { origin, final_destination, all_planned_stops } = result.aggregate
  if (!origin || !final_destination) return null
  const waypoints = all_planned_stops.map((stop) => ({
    lat: stop.station.location.lat,
    lon: stop.station.location.lon,
  }))
  const placeWaypoints = result.legs
    .slice(0, -1)
    .map((leg) => ({
      lat: leg.plan.destination?.lat ?? 0,
      lon: leg.plan.destination?.lon ?? 0,
    }))
    .filter((p) => p.lat !== 0)
  const merged = waypoints.length > 0 ? waypoints : placeWaypoints
  return {
    origin,
    destination: final_destination,
    waypoints: merged.length > 0 ? merged : undefined,
    title: 'Simulación de viaje · Electrolineras',
  }
}

function mapPlanFromMulti(result: MultiLegChargingPlanResponse) {
  const base = result.legs[0]?.plan
  if (!base) return null
  return {
    ...base,
    destination: result.aggregate.final_destination,
    planned_stops: result.aggregate.all_planned_stops,
    warnings: [...result.warnings, ...base.warnings],
    route_trip_summary: base.route_trip_summary,
  }
}

function isTruthyFlag(value: unknown): boolean {
  return value === true || value === 1 || value === 'true' || value === 'True'
}

/** Normaliza hitos: Casa + pernocta en ida-vuelta con un destino. */
function normalizeStops(parsed: {
  stops: ItineraryPlaceResult[]
  return_home: boolean
}): ItineraryPlaceResult[] {
  const nonHome = parsed.stops.filter((s) => !isTruthyFlag(s.is_home))
  const roundTrip =
    isTruthyFlag(parsed.return_home) ||
    (parsed.stops.length >= 2 && isTruthyFlag(parsed.stops[parsed.stops.length - 1]?.is_home))

  return parsed.stops.map((stop) => {
    if (isTruthyFlag(stop.is_home)) {
      return {
        ...stop,
        label: 'Casa',
        is_home: true,
        overnight: false,
        nights: null,
      }
    }
    const wantOvernight =
      isTruthyFlag(stop.overnight) || (roundTrip && nonHome.length === 1) || roundTrip
    return {
      ...stop,
      is_home: false,
      overnight: wantOvernight,
      nights: wantOvernight ? (stop.nights ?? 1) : null,
    }
  })
}

export function TripSimulationPanel({
  routePreference,
  avoidTolls,
  revePlanning,
  disabled = false,
  onPlanForMap,
  onBusyChange,
}: Props) {
  const [text, setText] = useState('')
  const [simulate100, setSimulate100] = useState(true)
  const [stops, setStops] = useState<ItineraryPlaceResult[] | null>(null)
  const [parseWarnings, setParseWarnings] = useState<string[]>([])
  const [parsedSoc, setParsedSoc] = useState<number | null>(null)
  const [result, setResult] = useState<MultiLegChargingPlanResponse | null>(null)
  const [guide, setGuide] = useState<TripGuideResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [busyParse, setBusyParse] = useState(false)
  const [busyPlan, setBusyPlan] = useState(false)
  const [busyGuide, setBusyGuide] = useState(false)

  const setBusy = (value: boolean) => onBusyChange?.(value)
  // No incluir `disabled` del padre aquí: el padre usa loadingPlan que este panel
  // enciende vía onBusyChange → deadlock y «Recalcular» queda siempre bloqueado.
  const locallyBusy = busyParse || busyPlan || busyGuide
  const busy = locallyBusy || disabled

  const exportSpec = useMemo(() => (result ? multiLegExportSpec(result) : null), [result])
  const totalChargeStops = result?.aggregate.all_planned_stops.length ?? 0
  const canRecalculate = Boolean(stops?.length) && !locallyBusy

  const toggleOvernight = (order: number) => {
    setStops((prev) =>
      prev
        ? prev.map((stop) =>
            stop.order === order
              ? {
                  ...stop,
                  overnight: !stop.overnight,
                  nights: !stop.overnight ? (stop.nights ?? 1) : null,
                }
              : stop,
          )
        : prev,
    )
    setResult(null)
    setGuide(null)
  }

  const calculatePlan = async (planStops: ItineraryPlaceResult[], departureFromParse: number | null) => {
    const destinations = planStops.filter((stop) => !stop.is_home)
    if (destinations.length === 0) {
      setError('Falta un destino distinto de casa para calcular el plan.')
      return
    }
    setError(null)
    setBusyPlan(true)
    setBusy(true)
    setGuide(null)
    setStatus('Calculando paradas de carga por tramo (puede tardar 30–90 s)…')
    try {
      // Alinear min_kw con el Asistente: con «excluir lentos» el suelo es 50 kW (no 100).
      const planningMinKw = revePlanning.excludeSlowChargers ? 50 : 100
      const departureSoc = simulate100 ? 100 : departureFromParse ?? undefined
      const multi = await fetchMultiLegChargingPlan({
        stops: planStops.map((stop) => ({
          lat: stop.lat,
          lon: stop.lon,
          label: stop.is_home ? 'Casa' : stop.label,
          overnight: Boolean(stop.overnight) && !Boolean(stop.is_home),
          nights: stop.nights,
        })),
        departureSocPercent: departureSoc,
        includeRoute: true,
        routePreference,
        avoidHighways: avoidTolls,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minKw: planningMinKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
      })
      setResult(multi)
      onPlanForMap(mapPlanFromMulti(multi))
      const n = multi.aggregate.all_planned_stops.length
      const socNote = departureSoc != null ? ` · salida simulada ${departureSoc} %` : ''
      setStatus(
        n > 0
          ? `Plan listo: ${n} parada${n === 1 ? '' : 's'} de carga en ${multi.legs.length} tramo${multi.legs.length === 1 ? '' : 's'}.${socNote}`
          : `Plan calculado, pero sin paradas de carga (revisa avisos de cada tramo).${socNote}`,
      )
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo calcular el plan multi-tramo.')
      setResult(null)
      onPlanForMap(null)
      setStatus(null)
    } finally {
      setBusyPlan(false)
      setBusy(false)
    }
  }

  const runParseAndPlan = async () => {
    setError(null)
    setStatus(null)
    setBusyParse(true)
    setBusy(true)
    setResult(null)
    setGuide(null)
    onPlanForMap(null)
    try {
      setStatus('Interpretando itinerario…')
      const parsed = await parseItineraryFromCar({ text })
      const normalized = normalizeStops(parsed)
      setStops(normalized)
      setParseWarnings(parsed.warnings)
      const soc = parsed.departure_soc_percent ?? null
      setParsedSoc(soc)
      if (soc != null && soc >= 95) {
        setSimulate100(true)
      }
      if (normalized.length === 0) {
        setError(parsed.warnings[0] ?? 'No se interpretó ningún destino.')
        setStatus(null)
        return
      }
      if (!normalized.some((stop) => !stop.is_home)) {
        setError('Falta el destino del viaje (solo se detectó casa). Reformula el texto.')
        setStatus(null)
        return
      }
      setBusyParse(false)
      await calculatePlan(normalized, soc)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo interpretar el viaje.')
      setStops(null)
      setStatus(null)
    } finally {
      setBusyParse(false)
      setBusy(false)
    }
  }

  const runPlanOnly = async () => {
    if (!stops?.length) return
    await calculatePlan(stops, parsedSoc)
  }

  const runGuide = async () => {
    if (!result?.legs.length) return
    const last = result.legs[result.legs.length - 1]
    const dest = last.plan.destination
    if (!dest) return
    setBusyGuide(true)
    setBusy(true)
    setError(null)
    try {
      const note = [
        'Simulación de viaje multi-tramo. Analiza riesgos de carga y pernoctas; no inventes estaciones.',
        text.trim(),
        ...result.agent_bullets,
        ...result.warnings.slice(0, 8),
      ]
        .filter(Boolean)
        .join('\n')
      const guideResp = await fetchTripGuideFromCar({
        destLat: dest.lat,
        destLon: dest.lon,
        destLabel: last.to_label,
        includeRoute: false,
        invokeDify: true,
        userNote: note.slice(0, 1900),
        routePreference,
        avoidHighways: avoidTolls,
        departureSocPercent: simulate100 ? 100 : parsedSoc ?? undefined,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
      })
      setGuide(guideResp)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo generar la guía IA.')
    } finally {
      setBusyGuide(false)
      setBusy(false)
    }
  }

  return (
    <div className="trip-simulation">
      <p className="muted small" style={{ marginTop: 0 }}>
        Describe el viaje y pulsa <strong>Calcular ruta de carga</strong>. Se interpretan los hitos y se calculan
        las paradas de cada tramo.
      </p>
      <label className="field" htmlFor="trip-sim-text">
        <span className="field__label">Itinerario</span>
        <textarea
          id="trip-sim-text"
          className="assistant-ai-note"
          rows={4}
          placeholder={PLACEHOLDER}
          value={text}
          disabled={busy}
          onChange={(e) => {
            setText(e.target.value)
            setStops(null)
            setResult(null)
            setGuide(null)
            setStatus(null)
          }}
        />
      </label>
      <label className="assistant-panel__option">
        <input
          type="checkbox"
          checked={simulate100}
          disabled={busy}
          onChange={(e) => {
            setSimulate100(e.target.checked)
            setResult(null)
          }}
        />
        Simular salida al 100 %
      </label>
      <div className="assistant-ai-actions trip-simulation__actions">
        <button
          type="button"
          className="btn btn--primary trip-simulation__primary"
          disabled={locallyBusy || disabled || text.trim().length < 5}
          onClick={() => void runParseAndPlan()}
        >
          {busyParse || busyPlan ? 'Calculando ruta…' : 'Calcular ruta de carga'}
        </button>
        {stops && stops.length > 0 ? (
          <button
            type="button"
            className="btn btn--ghost"
            disabled={!canRecalculate}
            onClick={() => void runPlanOnly()}
          >
            {busyPlan ? 'Recalculando…' : 'Recalcular solo el plan'}
          </button>
        ) : null}
      </div>

      {status ? (
        <p className="panel-hint" role="status">
          {status}
        </p>
      ) : null}

      {parseWarnings.length > 0 && (
        <ul className="trip-simulation__warnings">
          {parseWarnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      {stops && stops.length > 0 && (
        <ol className="trip-simulation__stops">
          {stops.map((stop) => (
            <li key={`${stop.order}-${stop.label}`}>
              <div className="trip-simulation__stop-row">
                <strong>
                  {stop.order}. {stop.is_home ? 'Casa' : stop.label}
                </strong>
                {stop.is_home ? (
                  <span className="muted small"> (origen / regreso)</span>
                ) : (
                  <button
                    type="button"
                    className={`btn btn--ghost trip-simulation__overnight ${stop.overnight ? 'is-on' : ''}`}
                    disabled={busy}
                    onClick={() => toggleOvernight(stop.order)}
                  >
                    {stop.overnight
                      ? `Pernocta · ${stop.nights ?? 1} noche${(stop.nights ?? 1) === 1 ? '' : 's'}`
                      : 'Sin pernocta (pulsar para marcar)'}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}

      {error ? <p className="auth-form__error">{error}</p> : null}

      {result && (
        <div className="trip-simulation__results">
          <p className="assistant-advice__summary">{result.agent_summary}</p>
          <p className="panel-hint">
            {totalChargeStops} parada{totalChargeStops === 1 ? '' : 's'} en ruta
            {result.aggregate.total_charge_minutes > 0
              ? ` (~${formatDurationMinutes(result.aggregate.total_charge_minutes)} carga)`
              : null}
          </p>
          <ul className="assistant-advice__bullets trip-simulation__leg-times">
            {result.legs.map((leg) => {
              const drive = formatDurationMinutes(leg.plan.route_duration_minutes)
              const km = leg.plan.route_distance_km
              const stopsN = leg.plan.planned_stops?.length ?? 0
              return (
                <li key={`leg-time-${leg.order}`}>
                  <strong>
                    {leg.from_label} → {leg.to_label}
                  </strong>
                  {km != null ? ` · ${km.toFixed(0)} km` : null}
                  {drive ? ` · ${drive}` : null}
                  {` · ${leg.departure_soc_pct.toFixed(0)}%→${leg.arrival_soc_pct.toFixed(0)}%`}
                  {stopsN > 0 ? ` · ${stopsN} parada${stopsN === 1 ? '' : 's'}` : null}
                  {leg.overnight ? ' · pernocta' : null}
                </li>
              )
            })}
          </ul>
          {result.warnings.length > 0 ? (
            <details className="assistant-collapsible trip-simulation__warnings-box">
              <summary>Avisos ({result.warnings.length})</summary>
              <ul className="trip-simulation__warnings">
                {result.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </details>
          ) : null}
          {exportSpec ? <RouteExportActions route={exportSpec} variant="assistant" /> : null}
          <button
            type="button"
            className="btn btn--secondary"
            disabled={busy}
            onClick={() => void runGuide()}
          >
            {busyGuide ? 'Analizando con IA…' : 'Analizar con IA'}
          </button>
          {guide?.guide_text ? (
            <details className="assistant-guide assistant-collapsible">
              <summary className="assistant-guide__header">
                <span className="assistant-guide__title">Análisis IA</span>
                <span className="assistant-guide__badge">
                  {guide.guide_source === 'dify' ? 'IA · Cursor' : 'Motor local'}
                </span>
              </summary>
              <pre className="assistant-guide__text">{guide.guide_text}</pre>
            </details>
          ) : null}
          {result.legs.map((leg) => {
            const stopCount = leg.plan.planned_stops?.length ?? 0
            return (
              <details key={leg.order} className="assistant-collapsible">
                <summary>
                  Detalle tramo {leg.order}: {leg.from_label} → {leg.to_label}
                  {stopCount > 0 ? ` · ${stopCount} parada${stopCount === 1 ? '' : 's'}` : ''}
                </summary>
                <ChargingPlanResults plan={leg.plan} variant="assistant" />
              </details>
            )
          })}
        </div>
      )}
    </div>
  )
}
