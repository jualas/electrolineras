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
import { getTerrainFactor, TERRAIN_FACTORS, type TerrainFactorId } from '../vehicle/vehiclePresets'
import { PlaceAutocomplete } from '../search/PlaceAutocomplete'
import { RoutePreferenceFields } from '../search/RoutePreferenceFields'
import { revePlanningForPreset, type RevePlanningOptions } from '../search/RevePlanningFields'
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
  onVehicleTerrainChange: (terrainFactorId: TerrainFactorId) => void
  onPlanResults: (response: import('../api/types').ChargingPlanResponse | null) => void
  onPlanStateChange?: (status: 'idle' | 'loading' | 'ready' | 'error') => void
  onSelectStation?: (station: import('../api/types').Station | null) => void
  selectedStationId?: string | null
}

export function AssistantPanel({
  vehicleProfile,
  onVehicleSocChange,
  onVehicleTerrainChange,
  onPlanResults,
  onPlanStateChange,
  onSelectStation,
  selectedStationId,
}: AssistantPanelProps) {
  const { loading, authenticated, loginEnabled, logout, privateStackEnabled } = useAuth()
  const [destination, setDestination] = useState<GeocodeResult | null>(null)
  const [destinationText, setDestinationText] = useState('')
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
      <section className="assistant-panel">
        <p className="assistant-panel__muted">
          Zona privada desactivada en el servidor (<code>PRIVATE_STACK_ENABLED</code>).
        </p>
      </section>
    )
  }

  if (!loginEnabled) {
    return (
      <section className="assistant-panel">
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
  const runMapPlan = async () => {
    if (!destination) {
      setPlanError('Selecciona un destino de la lista')
      return
    }
    setLoadingPlan(true)
    setPlanError(null)
    onPlanStateChange?.('loading')
    onPlanResults(null)
    try {
      const result = await fetchTripAdviceFromCar({
        destLat: destination.lat,
        destLon: destination.lon,
        terrainFactor: terrain.factor,
        reserveSocPercent: DEFAULT_RESERVE_SOC_PERCENT,
        localMobilityKm: 40,
        includeRoute: true,
        routePreference,
        avoidHighways: avoidTolls,
        departureSocPercent: departureSocParam,
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
    if (!destination) {
      setGuideError('Selecciona un destino de la lista')
      return
    }
    setLoadingGuide(true)
    setGuideError(null)
    setPlanError(null)
    if (!advice?.plan) {
      onPlanStateChange?.('loading')
      onPlanResults(null)
    }
    try {
      const result = await fetchTripGuideFromCar({
        destLat: destination.lat,
        destLon: destination.lon,
        destLabel: destination.label,
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

  return (
    <section className="assistant-panel">
      <div className="assistant-panel__header">
        <h2 className="assistant-panel__title">Asistente (coche)</h2>
        <button type="button" className="assistant-panel__logout" onClick={() => void logout()}>
          Salir
        </button>
      </div>
      <p className="assistant-panel__hint">
        Datos en vivo desde TeslaMate (SOC, autonomía del cuadro y modelo). El plan usa esos valores, no presets
        genéricos.
      </p>

      <VehicleTelemetryStrip
        vehicle={vehicle}
        loading={loadingVehicle}
        error={vehicleError}
        onRefresh={() => void loadVehicle()}
      />

      {vehicle && nominalKm != null && (
        <ul className="assistant-vehicle__stats assistant-vehicle__stats--extra">
          {planKm != null && (
            <li>
              Plan reserva {DEFAULT_RESERVE_SOC_PERCENT} %: ~{planKm} km
              {reachKm != null && <> · hasta cargador ≥5 %: ~{reachKm} km</>}
            </li>
          )}
          {vehicle.est_battery_range_km != null &&
            nominalKm != null &&
            Math.abs(vehicle.est_battery_range_km - (nominalKm * vehicle.battery_level_pct) / 100) > 15 && (
              <li className="assistant-panel__muted">
                MQTT est_battery_range_km: ~{vehicle.est_battery_range_km.toFixed(0)} km (no usado en el plan)
              </li>
            )}
        </ul>
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

      <div className="assistant-profile-sync">
        <p className="panel-hint">
          Terreno ajusta el plan si esperas más consumo (sierra, frío). El plan usa el SOC al salir si simulas
          carga; si no, el nivel actual del coche.
        </p>
        <div className="vehicle-panel__terrain">
          <span className="field__label">Terreno</span>
          <div className="chip-row" role="list" aria-label="Factor de terreno">
            {TERRAIN_FACTORS.map((item) => (
              <button
                key={item.id}
                type="button"
                role="listitem"
                className={`chip ${vehicleProfile.terrainFactorId === item.id ? 'chip--active' : ''}`}
                onClick={() => onVehicleTerrainChange(item.id)}
                aria-pressed={vehicleProfile.terrainFactorId === item.id}
                title={item.hint}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <PlaceAutocomplete
        id="assistant-dest"
        label="Destino"
        placeholder="Ciudad o lugar"
        value={destinationText}
        onChange={(text) => {
          setDestinationText(text)
          setDestination(null)
          setAdvice(null)
          onPlanResults(null)
          onPlanStateChange?.('idle')
        }}
        onSelect={(place) => {
          setDestinationText(place.label)
          setDestination(place)
          setAdvice(null)
          onPlanResults(null)
          onPlanStateChange?.('idle')
        }}
      />

      <RoutePreferenceFields
        routePreference={routePreference}
        avoidTolls={avoidTolls}
        variant="assistant"
        comparisonPlan={advice?.plan ?? null}
        onRoutePreferenceChange={(value) => {
          setRoutePreference(value)
          if (advice?.plan) {
            recalcOnPreferenceRef.current = true
          } else {
            setAdvice(null)
            onPlanResults(null)
            onPlanStateChange?.('idle')
          }
        }}
        onAvoidTollsChange={(value) => {
          setAvoidTolls(value)
          if (advice?.plan) {
            recalcOnPreferenceRef.current = true
          } else {
            setAdvice(null)
            onPlanResults(null)
            onPlanStateChange?.('idle')
          }
        }}
        disabled={busy}
      />

      <label className="assistant-panel__option">
        <input
          type="checkbox"
          checked={culturalPoi}
          onChange={(e) => setCulturalPoi(e.target.checked)}
        />
        Incluir ideas culturales y gastronomía en la guía
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

      <div className="assistant-ai-actions">
        <button
          type="button"
          className="assistant-ai-actions__map"
          disabled={busy || !destination}
          onClick={() => void runMapPlan()}
        >
          {loadingPlan ? 'Calculando mapa…' : 'Planificar en mapa'}
        </button>
        <button
          type="button"
          className="assistant-ai-actions__ia auth-form__submit"
          disabled={busy || !destination}
          onClick={() => void runAiGuide()}
        >
          {loadingGuide ? 'Generando guía IA…' : 'Guía de viaje con IA'}
        </button>
      </div>
      <p className="assistant-panel__hint assistant-panel__hint--actions">
        El mapa es rápido (motor local). La guía IA usa Dify + Cursor y puede tardar 1–2 minutos.
      </p>

      {planError && <p className="auth-form__error">{planError}</p>}
      {guideError && <p className="auth-form__error">{guideError}</p>}

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
                disabled={busy || !destination}
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
