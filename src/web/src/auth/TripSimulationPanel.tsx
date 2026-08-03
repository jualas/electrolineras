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
  'Ej.: Salgo de casa al 100 %. Viernes a Santillana del Mar (2 noches). Sábado a Comillas. Domingo vuelta a casa.'

function multiLegExportSpec(result: MultiLegChargingPlanResponse): RouteExportSpec | null {
  const { origin, final_destination, all_planned_stops } = result.aggregate
  if (!origin || !final_destination) return null
  const waypoints = all_planned_stops.map((stop) => ({
    lat: stop.station.location.lat,
    lon: stop.station.location.lon,
  }))
  // Include intermediate place destinations (non-charging) as soft waypoints if few charge stops
  const placeWaypoints = result.legs.slice(0, -1).map((leg) => ({
    lat: leg.plan.destination?.lat ?? 0,
    lon: leg.plan.destination?.lon ?? 0,
  })).filter((p) => p.lat !== 0)
  const merged =
    waypoints.length > 0
      ? waypoints
      : placeWaypoints
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
  const [busyParse, setBusyParse] = useState(false)
  const [busyPlan, setBusyPlan] = useState(false)
  const [busyGuide, setBusyGuide] = useState(false)

  const setBusy = (value: boolean) => onBusyChange?.(value)

  const exportSpec = useMemo(() => (result ? multiLegExportSpec(result) : null), [result])

  const toggleOvernight = (order: number) => {
    setStops((prev) =>
      prev
        ? prev.map((stop) =>
            stop.order === order
              ? {
                  ...stop,
                  overnight: !stop.overnight,
                  nights: !stop.overnight ? stop.nights ?? 1 : null,
                }
              : stop,
          )
        : prev,
    )
    setResult(null)
    setGuide(null)
  }

  const runParse = async () => {
    setError(null)
    setBusyParse(true)
    setBusy(true)
    setResult(null)
    setGuide(null)
    onPlanForMap(null)
    try {
      const parsed = await parseItineraryFromCar({ text })
      setStops(parsed.stops)
      setParseWarnings(parsed.warnings)
      setParsedSoc(parsed.departure_soc_percent ?? null)
      if (parsed.departure_soc_percent != null && parsed.departure_soc_percent >= 95) {
        setSimulate100(true)
      }
      if (parsed.stops.length === 0) {
        setError(parsed.warnings[0] ?? 'No se interpretó ningún destino.')
      } else if (!parsed.stops.some((stop) => !stop.is_home)) {
        setError('Falta el destino del viaje (solo se detectó casa). Reformula el texto.')
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo interpretar el viaje.')
      setStops(null)
    } finally {
      setBusyParse(false)
      setBusy(false)
    }
  }

  const runPlan = async () => {
    if (!stops?.length) return
    const destinations = stops.filter((stop) => !stop.is_home)
    if (destinations.length === 0) {
      setError('Falta un destino distinto de casa para calcular el plan.')
      return
    }
    setError(null)
    setBusyPlan(true)
    setBusy(true)
    setGuide(null)
    try {
      const departureSoc = simulate100 ? 100 : parsedSoc ?? undefined
      const multi = await fetchMultiLegChargingPlan({
        stops: stops.map((stop) => ({
          lat: stop.lat,
          lon: stop.lon,
          label: stop.label,
          overnight: stop.overnight && !stop.is_home,
          nights: stop.nights,
        })),
        departureSocPercent: departureSoc,
        includeRoute: true,
        routePreference,
        avoidHighways: avoidTolls,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
      })
      setResult(multi)
      onPlanForMap(mapPlanFromMulti(multi))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'No se pudo calcular el plan multi-tramo.')
      setResult(null)
      onPlanForMap(null)
    } finally {
      setBusyPlan(false)
      setBusy(false)
    }
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

  const busy = busyParse || busyPlan || busyGuide || disabled

  return (
    <div className="trip-simulation">
      <p className="muted small" style={{ marginTop: 0 }}>
        Describe el viaje en lenguaje natural. Ejemplo: «Vamos el sábado a Camping Garrote Gordo y volvemos a
        casa el domingo (salimos al 100 %)». Luego: Interpretar → revisar hitos → Calcular plan.
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
      <div className="assistant-ai-actions">
        <button
          type="button"
          className="assistant-ai-actions__map"
          disabled={busy || text.trim().length < 5}
          onClick={() => void runParse()}
        >
          {busyParse ? 'Interpretando…' : 'Interpretar viaje'}
        </button>
        <button
          type="button"
          className="assistant-ai-actions__ia auth-form__submit"
          disabled={busy || !stops?.length}
          onClick={() => void runPlan()}
        >
          {busyPlan ? 'Calculando…' : 'Calcular plan'}
        </button>
      </div>

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
              <strong>
                {stop.order}. {stop.label}
              </strong>
              {stop.is_home ? ' · casa' : null}
              {!stop.is_home ? (
                <button
                  type="button"
                  className="btn btn--ghost"
                  style={{ marginLeft: '0.35rem' }}
                  disabled={busy}
                  onClick={() => toggleOvernight(stop.order)}
                >
                  {stop.overnight
                    ? `Pernocta${stop.nights ? ` ${stop.nights}n` : ''}`
                    : 'Marcar pernocta'}
                </button>
              ) : null}
              <span className="muted small"> · {stop.confidence}</span>
            </li>
          ))}
        </ol>
      )}

      {error ? <p className="auth-form__error">{error}</p> : null}

      {result && (
        <div className="trip-simulation__results">
          <p className="assistant-advice__summary">{result.agent_summary}</p>
          <ul className="assistant-advice__bullets">
            {result.agent_bullets.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          {result.warnings.length > 0 && (
            <ul className="trip-simulation__warnings">
              {result.warnings.slice(0, 12).map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
          )}
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
            <details className="assistant-guide assistant-collapsible" open>
              <summary className="assistant-guide__header">
                <span className="assistant-guide__title">Análisis IA</span>
                <span className="assistant-guide__badge">
                  {guide.guide_source === 'dify' ? 'IA · Cursor' : 'Motor local'}
                </span>
              </summary>
              <pre className="assistant-guide__text">{guide.guide_text}</pre>
            </details>
          ) : null}
          {result.legs.map((leg) => (
            <details key={leg.order} className="assistant-collapsible" open={leg.order === 1}>
              <summary>
                Tramo {leg.order}: {leg.from_label} → {leg.to_label}
                {leg.overnight ? ' · pernocta' : ''} · {leg.departure_soc_pct.toFixed(0)}%→
                {leg.arrival_soc_pct.toFixed(0)}%
              </summary>
              <ChargingPlanResults plan={leg.plan} variant="assistant" />
            </details>
          ))}
        </div>
      )}
    </div>
  )
}
