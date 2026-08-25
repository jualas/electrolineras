import { useEffect, useRef, useState } from 'react'

import { fetchTripAdviceFromCar, fetchTripGuideFromCar } from '../api/auth'
import type { GeocodeResult, TripGuideResponse } from '../api/types'
import { VehicleTelemetryStrip } from '../components/vehicle/VehicleTelemetryStrip'
import {
  chargingReachFromNominal,
  nominalRangeKm,
  planningRangeFromNominal,
} from '../vehicle/telemetryProfile'
import { DEFAULT_RESERVE_SOC_PERCENT } from '../vehicle/vehicleProfile'
import { getTerrainFactor } from '../vehicle/vehiclePresets'
import { geocodePlace } from '../api/route'
import { RoutePreferenceFields } from '../search/RoutePreferenceFields'
import {
  ItineraryFields,
  createEmptyStop,
  type ItineraryStopDraft,
} from '../search/ItineraryFields'
import { revePlanningForPreset, type RevePlanningOptions } from '../search/RevePlanningFields'
import { DEFAULT_CHARGING_PREFERENCES } from '../charging/chargingPreferences'
import type { RoutePreference } from '../api/types'
import { ChargingPlanResults } from '../search/ChargingPlanResults'
import {
  defaultDepartureSoc,
  DepartureChargeSimulator,
  departureSocQueryParam,
} from './DepartureChargeSimulator'
import { useAuth } from './AuthContext'
import { LoginPanel } from './LoginPanel'
import { TELEMETRY_POLL_INTERVAL_MS, useVehicleTelemetry } from '../hooks/useVehicleTelemetry'

import type { VehicleProfile } from '../vehicle/vehicleProfile'

type AssistantPanelProps = {
  vehicleProfile: VehicleProfile
  onVehicleSocChange: (socPercent: number) => void
  onPlanResults: (response: import('../api/types').ChargingPlanResponse | null) => void
  onPlanStateChange?: (status: 'idle' | 'loading' | 'ready' | 'error') => void
  onSelectStation?: (station: import('../api/types').Station | null) => void
  selectedStationId?: string | null
}

export function AssistantPanel({
  vehicleProfile,
  onVehicleSocChange,
  onPlanResults,
  onPlanStateChange,
  onSelectStation,
  selectedStationId,
}: AssistantPanelProps) {
  const { loading, authenticated, loginEnabled, privateStackEnabled } = useAuth()
  const [stops, setStops] = useState<ItineraryStopDraft[]>(() => [createEmptyStop()])
  const [advice, setAdvice] = useState<TripGuideResponse | null>(null)
  const [planError, setPlanError] = useState<string | null>(null)
  const [loadingPlan, setLoadingPlan] = useState(false)
  const [loadingGuide, setLoadingGuide] = useState(false)
  const [culturalPoi, setCulturalPoi] = useState(true)
  const [routePreference, setRoutePreference] = useState<RoutePreference>('shortest')
  const [avoidTolls, setAvoidTolls] = useState(false)
  const [revePlanning, setRevePlanning] = useState<RevePlanningOptions>(() =>
    revePlanningForPreset(vehicleProfile.presetId),
  )
  const [simulateDeparture, setSimulateDeparture] = useState(false)
  const [departureSoc, setDepartureSoc] = useState(80)
  const [aiNote, setAiNote] = useState('')
  const [guideError, setGuideError] = useState<string | null>(null)
  const recalcOnPreferenceRef = useRef(false)

  const {
    vehicle,
    loading: loadingVehicle,
    error: vehicleError,
    refresh: loadVehicle,
  } = useVehicleTelemetry({
    syncSoc: true,
    currentSocPercent: vehicleProfile.socPercent,
    onSocChange: onVehicleSocChange,
    pollIntervalMs: TELEMETRY_POLL_INTERVAL_MS,
  })

  useEffect(() => {
    setRevePlanning((prev) => ({
      ...prev,
      maxChargePowerKw: revePlanningForPreset(vehicleProfile.presetId).maxChargePowerKw,
    }))
  }, [vehicleProfile.presetId])

  useEffect(() => {
    if (!vehicle) {
      return
    }
    const live = Math.round(vehicle.battery_level_pct)
    if (!simulateDeparture) {
      setDepartureSoc(live)
      return
    }
    setDepartureSoc((prev) => Math.max(prev, live))
  }, [vehicle?.battery_level_pct, simulateDeparture])

  const departureSocParam =
    vehicle != null
      ? departureSocQueryParam(simulateDeparture, vehicle.battery_level_pct, departureSoc)
      : undefined

  if (loading) {
    return <p className="assistant-panel__muted">Comprobando sesión…</p>
  }

  if (!privateStackEnabled) {
    return (
      <section className="panel search-panel assistant-panel">
        <p className="assistant-panel__muted">
          Zona privada desactivada en el servidor (<code>PRIVATE_STACK_ENABLED</code>).
        </p>
      </section>
    )
  }

  if (!loginEnabled) {
    return (
      <section className="panel search-panel assistant-panel">
        <p className="assistant-panel__muted">
          Falta configurar TOTP en el servidor. Ver <code>scripts/auth/setup_private_auth.py</code>.
        </p>
      </section>
    )
  }

  if (!authenticated) {
    return <LoginPanel />
  }

  const terrain = getTerrainFactor(vehicleProfile.terrainFactorId)
  const nominalKm = vehicle != null ? nominalRangeKm(vehicle) : null
  const planningSocPercent =
    vehicle != null && simulateDeparture ? departureSoc : vehicle?.battery_level_pct ?? 0
  const planKm =
    nominalKm != null && planningSocPercent > 0
      ? planningRangeFromNominal(
          nominalKm,
          planningSocPercent,
          DEFAULT_RESERVE_SOC_PERCENT,
        )
      : null
  const reachKm =
    nominalKm != null && planningSocPercent > 0
      ? chargingReachFromNominal(nominalKm, planningSocPercent)
      : null
  const destination = stops[stops.length - 1]?.point ?? null

  const resolveItinerary = async (): Promise<{
    destination: GeocodeResult
    viaPoints: Array<{ lat: number; lon: number }>
  }> => {
    const nextStops = [...stops]
    const resolved: GeocodeResult[] = []
    for (let index = 0; index < nextStops.length; index += 1) {
      const stop = nextStops[index]
      if (stop.point) {
        resolved.push(stop.point)
        continue
      }
      const trimmed = stop.text.trim()
      if (!trimmed) {
        if (index === nextStops.length - 1) {
          throw new Error('Indica un destino')
        }
        continue
      }
      const geocoded = await geocodePlace(trimmed)
      const point = { label: geocoded.label, lat: geocoded.lat, lon: geocoded.lon }
      nextStops[index] = { ...stop, text: point.label, point }
      resolved.push(point)
    }
    setStops(nextStops)
    if (resolved.length === 0) {
      throw new Error('Selecciona un destino de la lista')
    }
    return {
      destination: resolved[resolved.length - 1],
      viaPoints: resolved.slice(0, -1).map((point) => ({ lat: point.lat, lon: point.lon })),
    }
  }

  const clearPlanState = () => {
    setAdvice(null)
    onPlanResults(null)
    onPlanStateChange?.('idle')
  }

  const runMapPlan = async () => {
    let itinerary: { destination: GeocodeResult; viaPoints: Array<{ lat: number; lon: number }> }
    try {
      itinerary = await resolveItinerary()
    } catch (err) {
      setPlanError(err instanceof Error ? err.message : 'Indica un destino')
      return
    }
    const dest = itinerary.destination
    setLoadingPlan(true)
    setPlanError(null)
    onPlanStateChange?.('loading')
    onPlanResults(null)
    try {
      const result = await fetchTripAdviceFromCar({
        destLat: dest.lat,
        destLon: dest.lon,
        viaPoints: itinerary.viaPoints,
        terrainFactor: terrain.factor,
        reserveSocPercent: DEFAULT_RESERVE_SOC_PERCENT,
        localMobilityKm: 40,
        includeRoute: true,
        routePreference,
        avoidHighways: avoidTolls,
        departureSocPercent: departureSocParam,
        preferredOperators: DEFAULT_CHARGING_PREFERENCES.preferredOperators,
        maxPriceEurKwh: DEFAULT_CHARGING_PREFERENCES.maxPriceEurKwh,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
        consumptionKwhPer100km: revePlanning.consumptionKwhPer100km,
        vehiclePresetId: vehicleProfile.presetId,
        minKw: revePlanning.excludeSlowChargers ? 50 : 100,
      })
      setAdvice((prev) =>
        prev
          ? { ...prev, plan: result.plan, agent_summary: result.agent_summary, agent_bullets: result.agent_bullets, vehicle: result.vehicle ?? prev.vehicle }
          : {
              plan: result.plan,
              agent_summary: result.agent_summary,
              agent_bullets: result.agent_bullets,
              vehicle: result.vehicle,
              guide_text: '',
              guide_source: 'deterministic',
              context: {
                cultural_poi_enabled: culturalPoi,
                poi_hints: [],
                nearest_destination_chargers: [],
                vehicle_snapshot: {},
                plan_snapshot: {},
              },
            },
      )
      onPlanResults(result.plan)
      onPlanStateChange?.('ready')
    } catch (err) {
      setAdvice(null)
      onPlanResults(null)
      onPlanStateChange?.('error')
      setPlanError(err instanceof Error ? err.message : 'Error al planificar')
    } finally {
      setLoadingPlan(false)
    }
  }

  const runAiGuide = async () => {
    let itinerary: { destination: GeocodeResult; viaPoints: Array<{ lat: number; lon: number }> }
    try {
      itinerary = await resolveItinerary()
    } catch (err) {
      setGuideError(err instanceof Error ? err.message : 'Indica un destino')
      return
    }
    const dest = itinerary.destination
    setLoadingGuide(true)
    setGuideError(null)
    setPlanError(null)
    if (!advice?.plan) {
      onPlanStateChange?.('loading')
      onPlanResults(null)
    }
    try {
      const result = await fetchTripGuideFromCar({
        destLat: dest.lat,
        destLon: dest.lon,
        destLabel: dest.label,
        viaPoints: itinerary.viaPoints,
        terrainFactor: terrain.factor,
        reserveSocPercent: DEFAULT_RESERVE_SOC_PERCENT,
        localMobilityKm: 40,
        includeRoute: true,
        culturalPoi,
        invokeDify: true,
        userNote: aiNote.trim() || undefined,
        routePreference,
        avoidHighways: avoidTolls,
        departureSocPercent: departureSocParam,
        preferredOperators: DEFAULT_CHARGING_PREFERENCES.preferredOperators,
        maxPriceEurKwh: DEFAULT_CHARGING_PREFERENCES.maxPriceEurKwh,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
        consumptionKwhPer100km: revePlanning.consumptionKwhPer100km,
        vehiclePresetId: vehicleProfile.presetId,
        minKw: revePlanning.excludeSlowChargers ? 50 : 100,
      })
      setAdvice(result)
      onPlanResults(result.plan)
      onPlanStateChange?.('ready')
    } catch (err) {
      onPlanStateChange?.('error')
      setGuideError(err instanceof Error ? err.message : 'Error al generar la guía IA')
    } finally {
      setLoadingGuide(false)
    }
  }

  const busy = loadingPlan || loadingGuide

  useEffect(() => {
    if (!recalcOnPreferenceRef.current || busy || !advice?.plan || !destination) {
      return
    }
    recalcOnPreferenceRef.current = false
    void runMapPlan()
  }, [routePreference, avoidTolls, revePlanning, busy, advice?.plan, destination])

  const vehicleOrigin =
    vehicle != null
      ? {
          label: vehicle.display_name?.trim() || 'Ubicación del vehículo',
          lat: vehicle.lat,
          lon: vehicle.lon,
        }
      : null
  const viaLabels = stops
    .slice(0, -1)
    .map((stop) => stop.point?.label ?? stop.text.trim())
    .filter(Boolean)
  const hasDestinationInput = stops.some((stop) => stop.point != null || stop.text.trim().length > 0)

  return (
    <section className="panel search-panel assistant-panel">
      <h2>Asistente (coche)</h2>
      <p className="panel-hint">
        Datos en vivo desde TeslaMate (SOC, autonomía del cuadro y modelo). El plan usa esos valores, no presets
        genéricos.
      </p>

      <VehicleTelemetryStrip
        vehicle={vehicle}
        loading={loadingVehicle}
        error={vehicleError}
        onRefresh={() => void loadVehicle()}
      />

      {vehicle && planKm != null && (
        <p className="charge-vehicle-summary">
          ~{planKm} km de plan{reachKm != null && <> · hasta cargador ~{reachKm} km</>}
        </p>
      )}

      {vehicle && nominalKm != null && (
        <DepartureChargeSimulator
          liveSocPercent={vehicle.battery_level_pct}
          departureSocPercent={departureSoc}
          simulateDeparture={simulateDeparture}
          nominalKm={nominalKm}
          disabled={busy}
          onSimulateChange={(enabled) => {
            setSimulateDeparture(enabled)
            if (enabled && vehicle) {
              setDepartureSoc(defaultDepartureSoc(vehicle.battery_level_pct))
            } else if (!enabled && vehicle) {
              setDepartureSoc(Math.round(vehicle.battery_level_pct))
            }
            setAdvice(null)
            onPlanResults(null)
            onPlanStateChange?.('idle')
          }}
          onDepartureSocChange={(value) => {
            setDepartureSoc(value)
            setAdvice(null)
            onPlanResults(null)
            onPlanStateChange?.('idle')
          }}
        />
      )}

      <form className="route-form" onSubmit={(event) => event.preventDefault()}>
        <ItineraryFields
          originText={vehicleOrigin?.label ?? 'Ubicación del vehículo'}
          originPoint={vehicleOrigin}
          vehicleOrigin={vehicleOrigin}
          originSource="car"
          onOriginChange={() => undefined}
          onOriginSelect={() => undefined}
          onUseVehicleOrigin={vehicleOrigin ? () => clearPlanState() : undefined}
          stops={stops}
          onStopChange={(id, text) => {
            setStops((prev) =>
              prev.map((stop) => (stop.id === id ? { ...stop, text, point: null } : stop)),
            )
            clearPlanState()
          }}
          onStopSelect={(id, place) => {
            setStops((prev) =>
              prev.map((stop) =>
                stop.id === id
                  ? { ...stop, text: place.label, point: { label: place.label, lat: place.lat, lon: place.lon } }
                  : stop,
              ),
            )
            clearPlanState()
          }}
          onAddStop={() => {
            setStops((prev) => [...prev, createEmptyStop()])
            clearPlanState()
          }}
          onRemoveStop={(id) => {
            setStops((prev) => (prev.length <= 1 ? prev : prev.filter((stop) => stop.id !== id)))
            clearPlanState()
          }}
          disabled={busy || vehicle == null}
        />

        {viaLabels.length > 0 && (
          <p className="panel-hint">
            Itinerario: {vehicleOrigin?.label ?? 'vehículo'}
            {viaLabels.map((label) => ` → ${label}`).join('')}
            {` → ${stops[stops.length - 1]?.point?.label ?? (stops[stops.length - 1]?.text || 'destino')}`}
            . El plan de carga pasa por todas las paradas.
          </p>
        )}

        <RoutePreferenceFields
          routePreference={routePreference}
          avoidTolls={avoidTolls}
          variant="assistant"
          onRoutePreferenceChange={(value) => {
            setRoutePreference(value)
            if (advice?.plan) {
              recalcOnPreferenceRef.current = true
            } else {
              clearPlanState()
            }
          }}
          onAvoidTollsChange={(value) => {
            setAvoidTolls(value)
            if (advice?.plan) {
              recalcOnPreferenceRef.current = true
            } else {
              clearPlanState()
            }
          }}
          disabled={busy}
        />

        <label className="field field--checkbox">
          <input
            type="checkbox"
            checked={culturalPoi}
            onChange={(e) => setCulturalPoi(e.target.checked)}
          />
          <span>Incluir ideas culturales y gastronomía en la guía</span>
        </label>

        <label className="field" htmlFor="assistant-ai-note">
          <span className="field__label">Pregunta o nota para la IA (opcional)</span>
          <textarea
            id="assistant-ai-note"
            className="assistant-ai-note"
            rows={3}
            placeholder="Ej.: ¿Dónde comer cerca del cargador? ¿Ruta cultural mientras cargo?"
            value={aiNote}
            onChange={(e) => setAiNote(e.target.value)}
            disabled={busy}
          />
        </label>

        <div className="route-form__actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || vehicle == null || !hasDestinationInput}
            onClick={() => void runAiGuide()}
          >
            {loadingGuide ? 'Generando guía IA…' : 'Guía de viaje con IA'}
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            disabled={busy || vehicle == null || !hasDestinationInput}
            onClick={() => void runMapPlan()}
          >
            {loadingPlan ? 'Calculando mapa…' : 'Solo plan en mapa (rápido)'}
          </button>
        </div>
        <p className="panel-hint">
          El mapa es rápido (motor local). La guía IA usa Dify + Cursor y puede tardar 1–2 minutos.
        </p>
      </form>

      {planError && (
        <p className="route-message route-message--error" role="alert">
          {planError}
        </p>
      )}
      {guideError && (
        <p className="route-message route-message--error" role="alert">
          {guideError}
        </p>
      )}

      {advice && (
        <div className="assistant-advice">
          {advice.guide_text && (
            <div className="assistant-guide">
              <div className="assistant-guide__header">
                <h3 className="assistant-guide__title">Guía de viaje</h3>
                <span className="assistant-guide__badge">
                  {advice.guide_source === 'dify' ? 'IA · Cursor' : 'Motor local'}
                </span>
              </div>
              <pre className="assistant-guide__text">{advice.guide_text}</pre>
              <button
                type="button"
                className="assistant-guide__refresh"
                disabled={busy || !hasDestinationInput}
                onClick={() => void runAiGuide()}
              >
                {loadingGuide ? 'Regenerando…' : 'Actualizar guía IA'}
              </button>
            </div>
          )}
          {!advice.guide_text && advice.plan && (advice.plan.planned_stops?.length ?? 0) === 0 && (
            <p className="assistant-panel__muted">
              Plan listo en el mapa. Pulsa <strong>Guía de viaje con IA</strong> para la narrativa.
            </p>
          )}
          {!advice.plan?.route_trip_summary && advice.agent_summary ? (
            <p className="assistant-advice__summary">{advice.agent_summary}</p>
          ) : null}
          {!advice.plan?.planned_stops?.length && advice.agent_bullets.length > 0 && (
            <ul className="assistant-advice__bullets">
              {advice.agent_bullets.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          )}
          <ChargingPlanResults
            plan={advice.plan}
            selectedStationId={selectedStationId}
            onSelectStation={onSelectStation}
            variant="assistant"
            originLabel="Tu coche"
            destinationLabel={destination?.label}
          />
        </div>
      )}
    </section>
  )
}
