import { useEffect, useRef, useState, type SyntheticEvent } from 'react'

import { fetchTripAdviceFromCar, fetchTripGuideFromCar } from '../api/auth'
import type {
  ChargingPlanResponse,
  GeocodeResult,
  RoutePreference,
  TripAdviceResponse,
  TripGuideResponse,
} from '../api/types'
import { DEFAULT_CHARGING_PREFERENCES } from '../charging/chargingPreferences'
import { VehicleTelemetryStrip } from '../components/vehicle/VehicleTelemetryStrip'
import { useActiveTrip } from '../hooks/useActiveTrip'
import {
  chargingReachFromNominal,
  nominalRangeKm,
  planningRangeFromNominal,
} from '../vehicle/telemetryProfile'
import { DEFAULT_RESERVE_SOC_PERCENT } from '../vehicle/vehicleProfile'
import { getVehiclePreset, type TerrainFactorId } from '../vehicle/vehiclePresets'
import { PlaceAutocomplete } from '../search/PlaceAutocomplete'
import { ReplanOnRouteBar } from '../search/ReplanOnRouteBar'
import { RoutePreferenceFields } from '../search/RoutePreferenceFields'
import { chargingPlanWithPreference } from '../routing/routeVariantSelection'
import { RevePlanningFields, revePlanningForPreset, type RevePlanningOptions } from '../search/RevePlanningFields'
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

function mergeAdviceFields(
  base: Partial<TripGuideResponse> | null,
  result: TripAdviceResponse,
  displayedPlan: ChargingPlanResponse,
  culturalPoiEnabled: boolean,
): TripGuideResponse {
  return {
    guide_text: base?.guide_text ?? '',
    guide_source: base?.guide_source ?? 'deterministic',
    context: base?.context ?? {
      cultural_poi_enabled: culturalPoiEnabled,
      poi_hints: [],
      nearest_destination_chargers: [],
      vehicle_snapshot: {},
      plan_snapshot: {},
    },
    plan: displayedPlan,
    agent_summary: result.agent_summary,
    agent_bullets: result.agent_bullets,
    vehicle: result.vehicle ?? base?.vehicle ?? null,
    live_soc_percent: result.live_soc_percent,
    departure_soc_percent: result.departure_soc_percent,
    soc_source: result.soc_source,
    consumption_source: result.consumption_source,
    consumption_kwh_per_100km: result.consumption_kwh_per_100km,
    consumption_confidence: result.consumption_confidence,
    consumption_note: result.consumption_note,
    consumption_bin: result.consumption_bin,
    consumption_profile: result.consumption_profile,
    live_consumption_kwh_per_100km: result.live_consumption_kwh_per_100km,
    consumption_divergence_pct: result.consumption_divergence_pct,
    consumption_divergence_alert: result.consumption_divergence_alert,
  }
}

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
  onVehicleTerrainChange: _onVehicleTerrainChange,
  onPlanResults,
  onPlanStateChange,
  onSelectStation,
  selectedStationId,
}: AssistantPanelProps) {
  void _onVehicleTerrainChange
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
  const [settingsOpen, setSettingsOpen] = useState(
    () => typeof window === 'undefined' || !window.matchMedia('(max-width: 640px)').matches,
  )
  const recalcOnRouteSettingsRef = useRef(false)
  const cachedPlanRef = useRef<ChargingPlanResponse | null>(null)
  const { activeTrip, enMarchaSettings, saveActiveTrip, clearActiveTrip, setAutoFollow } =
    useActiveTrip()

  const publishPlan = (plan: ChargingPlanResponse) => {
    cachedPlanRef.current = plan
    const displayed = chargingPlanWithPreference(plan, routePreference) ?? plan
    onPlanResults(displayed)
    return displayed
  }

  const persistActiveTrip = (dest: GeocodeResult) => {
    saveActiveTrip({
      destination: { label: dest.label, lat: dest.lat, lon: dest.lon },
      corridorKm: 10,
      routePreference,
      avoidTolls,
      chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
      originMode: 'car',
      updatedAt: Date.now(),
    })
  }

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

  const vehiclePreset = getVehiclePreset(vehicleProfile.presetId)
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
  const consumptionWhPerKm =
    nominalKm != null && nominalKm > 0
      ? (vehiclePreset.usableCapacityKwh * 1000) / nominalKm
      : vehiclePreset.referenceWhPerKm

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
        terrainFactor: 1.0,
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
        consumptionKwhPer100km: null,
        vehiclePresetId: vehicleProfile.presetId,
        minKw: revePlanning.excludeSlowChargers ? 50 : 100,
      })
      const displayedPlan = publishPlan(result.plan)
      persistActiveTrip(destination)
      setAdvice((prev) => mergeAdviceFields(prev, result, displayedPlan, culturalPoi))
      onPlanStateChange?.('ready')
    } catch (err) {
      setAdvice(null)
      cachedPlanRef.current = null
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
        terrainFactor: 1.0,
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
        consumptionKwhPer100km: null,
        vehiclePresetId: vehicleProfile.presetId,
        minKw: revePlanning.excludeSlowChargers ? 50 : 100,
      })
      const displayedPlan = publishPlan(result.plan)
      persistActiveTrip(destination)
      setAdvice(mergeAdviceFields(result, result, displayedPlan, culturalPoi))
      onPlanStateChange?.('ready')
    } catch (err) {
      onPlanStateChange?.('error')
      setGuideError(err instanceof Error ? err.message : 'Error al generar la guía IA')
    } finally {
      setLoadingGuide(false)
    }
  }

  const runReplanFromHere = async () => {
    if (!destination) {
      return
    }
    // Replan en marcha: SOC vivo (no simulación de casa).
    setSimulateDeparture(false)
    setLoadingPlan(true)
    setPlanError(null)
    onPlanStateChange?.('loading')
    try {
      await loadVehicle()
      const result = await fetchTripAdviceFromCar({
        destLat: destination.lat,
        destLon: destination.lon,
        terrainFactor: 1.0,
        reserveSocPercent: DEFAULT_RESERVE_SOC_PERCENT,
        localMobilityKm: 40,
        includeRoute: true,
        routePreference,
        avoidHighways: avoidTolls,
        departureSocPercent: undefined,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
        consumptionKwhPer100km: null,
        vehiclePresetId: vehicleProfile.presetId,
        minKw: revePlanning.excludeSlowChargers ? 50 : 100,
      })
      const displayedPlan = publishPlan(result.plan)
      persistActiveTrip(destination)
      setAdvice((prev) => mergeAdviceFields(prev, result, displayedPlan, culturalPoi))
      onPlanStateChange?.('ready')
    } catch (err) {
      onPlanStateChange?.('error')
      setPlanError(err instanceof Error ? err.message : 'Error al recalcular')
    } finally {
      setLoadingPlan(false)
    }
  }

  const applyCachedRoutePreference = (preference: RoutePreference) => {
    const cached = cachedPlanRef.current
    if (!cached) {
      return false
    }
    const switched = chargingPlanWithPreference(cached, preference)
    if (!switched) {
      return false
    }
    setAdvice((prev) => (prev ? { ...prev, plan: switched } : prev))
    onPlanResults(switched)
    onSelectStation?.(null)
    return true
  }

  const busy = loadingPlan || loadingGuide
  const lastFollowKeyRef = useRef<string | null>(null)

  useEffect(() => {
    if (!recalcOnRouteSettingsRef.current || busy || !advice?.plan || !destination) {
      return
    }
    recalcOnRouteSettingsRef.current = false
    void runMapPlan()
  }, [avoidTolls, revePlanning, busy, advice?.plan, destination])

  useEffect(() => {
    if (!enMarchaSettings.autoFollow || !advice?.plan || !destination || !vehicle || busy) {
      return
    }
    const key = [
      vehicle.lat.toFixed(3),
      vehicle.lon.toFixed(3),
      Math.round(vehicle.battery_level_pct),
      routePreference,
      avoidTolls ? '1' : '0',
    ].join('|')
    if (lastFollowKeyRef.current == null) {
      lastFollowKeyRef.current = key
      return
    }
    if (key === lastFollowKeyRef.current) {
      return
    }
    lastFollowKeyRef.current = key
    void runReplanFromHere()
  }, [
    avoidTolls,
    advice?.plan,
    busy,
    destination,
    enMarchaSettings.autoFollow,
    routePreference,
    vehicle?.battery_level_pct,
    vehicle?.lat,
    vehicle?.lon,
  ])

  return (
    <section className="assistant-panel">
      <div className="assistant-panel__header">
        <h2 className="assistant-panel__title">Asistente (coche)</h2>
        <button type="button" className="assistant-panel__logout" onClick={() => void logout()}>
          Salir
        </button>
      </div>
      <p className="assistant-panel__hint assistant-panel__hint--desktop">
        Datos en vivo desde TeslaMate (SOC, autonomía del cuadro y modelo). El plan usa esos valores, no presets
        genéricos.
      </p>

      <div className="assistant-panel__block assistant-panel__block--telemetry">
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
      </div>

      {advice?.consumption_divergence_alert && (
        <div className="assistant-divergence-alert assistant-panel__block--alert" role="alert">
          <p>
            El consumo instantáneo diverge más de 15 % respecto al plan
            {advice.consumption_divergence_pct != null
              ? ` (${advice.consumption_divergence_pct > 0 ? '+' : ''}${advice.consumption_divergence_pct.toFixed(0)} %)`
              : ''}
            . Recalcula desde tu posición y SOC actuales.
          </p>
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || !destination}
            onClick={() => void runReplanFromHere()}
          >
            {loadingPlan ? 'Recalculando…' : 'Recalcular desde aquí'}
          </button>
        </div>
      )}

      <>
          {activeTrip && !destination && (
            <p className="panel-hint active-trip-restore" role="status">
              Viaje activo anterior: <strong>{activeTrip.destination.label}</strong>.{' '}
              <button
                type="button"
                className="btn btn--ghost"
                disabled={busy}
                onClick={() => {
                  setDestination({
                    label: activeTrip.destination.label,
                    lat: activeTrip.destination.lat,
                    lon: activeTrip.destination.lon,
                  })
                  setDestinationText(activeTrip.destination.label)
                  setRoutePreference(activeTrip.routePreference)
                  setAvoidTolls(activeTrip.avoidTolls)
                }}
              >
                Usar este destino
              </button>
              <button
                type="button"
                className="btn btn--ghost"
                disabled={busy}
                onClick={() => clearActiveTrip()}
              >
                Descartar
              </button>
            </p>
          )}

          <div className="assistant-panel__block assistant-panel__block--trip">
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
                if (advice?.plan && cachedPlanRef.current) {
                  if (!applyCachedRoutePreference(value)) {
                    recalcOnRouteSettingsRef.current = true
                  }
                } else {
                  setAdvice(null)
                  cachedPlanRef.current = null
                  onPlanResults(null)
                  onPlanStateChange?.('idle')
                }
              }}
              onAvoidTollsChange={(value) => {
                setAvoidTolls(value)
                if (advice?.plan) {
                  recalcOnRouteSettingsRef.current = true
                } else {
                  setAdvice(null)
                  cachedPlanRef.current = null
                  onPlanResults(null)
                  onPlanStateChange?.('idle')
                }
              }}
              disabled={busy}
            />
          </div>

          <div className="assistant-ai-actions assistant-panel__block--cta">
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
          <p className="assistant-panel__hint assistant-panel__hint--actions assistant-panel__hint--desktop">
            El mapa es rápido (motor local). La guía IA usa Dify + Cursor y puede tardar 1–2 minutos.
          </p>

          {planError && <p className="auth-form__error">{planError}</p>}
          {guideError && <p className="auth-form__error">{guideError}</p>}

          {advice?.plan && destination ? (
            <ReplanOnRouteBar
              destinationLabel={destination.label}
              originLabel={
                vehicle
                  ? `${vehicle.display_name ?? 'Coche'} · ${vehicle.lat.toFixed(3)}, ${vehicle.lon.toFixed(3)}`
                  : 'Posición TeslaMate'
              }
              socPercent={vehicle?.battery_level_pct ?? advice.live_soc_percent ?? 0}
              socSourceLabel="TeslaMate"
              loading={busy}
              autoFollow={enMarchaSettings.autoFollow}
              onAutoFollowChange={setAutoFollow}
              onReplan={() => void runReplanFromHere()}
              onRefreshOrigin={() => void loadVehicle()}
              canReplan={Boolean(destination) && !busy}
              lastUpdatedAt={activeTrip?.updatedAt ?? null}
              showAutoFollow
            />
          ) : null}

          {advice && (
            <div className="assistant-advice assistant-panel__block--results">
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
              />
              {advice.guide_text ? (
                <details className="assistant-guide assistant-collapsible">
                  <summary className="assistant-guide__header">
                    <span className="assistant-guide__title">Guía de viaje</span>
                    <span className="assistant-guide__badge">
                      {advice.guide_source === 'dify' ? 'IA · Cursor' : 'Motor local'}
                    </span>
                  </summary>
                  <pre className="assistant-guide__text">{advice.guide_text}</pre>
                  <button
                    type="button"
                    className="assistant-guide__refresh"
                    disabled={busy || !destination}
                    onClick={() => void runAiGuide()}
                  >
                    {loadingGuide ? 'Regenerando…' : 'Actualizar guía IA'}
                  </button>
                </details>
              ) : null}
              {!advice.guide_text && advice.plan && (advice.plan.planned_stops?.length ?? 0) === 0 && (
                <p className="assistant-panel__muted">
                  Plan listo. Pulsa <strong>Guía de viaje con IA</strong> para la narrativa.
                </p>
              )}
              {activeTrip ? (
                <button type="button" className="btn btn--ghost replan-bar__clear" onClick={clearActiveTrip}>
                  Finalizar viaje activo
                </button>
              ) : null}
            </div>
          )}
      </>

      <details
        className="assistant-collapsible assistant-panel__block--settings"
        open={settingsOpen}
        onToggle={(event: SyntheticEvent<HTMLDetailsElement>) => {
          setSettingsOpen(event.currentTarget.open)
        }}
      >
        <summary>Ajustes y detalles</summary>
        <div className="assistant-collapsible__body">
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
              El consumo del plan sale del histórico (≥20 km). El instantáneo MQTT solo alerta si diverge &gt;15 %;
              no cambia el motor hasta que recalcules.
            </p>
            {advice && (
              <ul className="assistant-energy-sources" aria-label="Fuentes de energía del plan">
                <li>
                  SOC:{' '}
                  <strong>
                    {advice.soc_source === 'simulated' ? 'simulado' : 'vivo'}{' '}
                    {(advice.departure_soc_percent ?? advice.live_soc_percent ?? vehicle?.battery_level_pct)?.toFixed(0)} %
                  </strong>
                  {advice.soc_source === 'simulated' && advice.live_soc_percent != null
                    ? ` (ahora ${advice.live_soc_percent.toFixed(0)} %)`
                    : null}
                </li>
                {(advice.consumption_note || advice.plan.consumption_note) && (
                  <li>
                    Consumo plan:{' '}
                    <strong>
                      {(advice.consumption_kwh_per_100km ?? advice.plan.consumption_kwh_per_100km)?.toFixed(1)}{' '}
                      kWh/100 km
                    </strong>
                    {advice.consumption_source ? ` · ${advice.consumption_source}` : null}
                    {advice.consumption_confidence ? ` · confianza ${advice.consumption_confidence}` : null}
                  </li>
                )}
                {advice.live_consumption_kwh_per_100km != null && (
                  <li>
                    Instantáneo MQTT:{' '}
                    <strong>{advice.live_consumption_kwh_per_100km.toFixed(1)} kWh/100 km</strong>
                    {advice.consumption_divergence_pct != null
                      ? ` · ${advice.consumption_divergence_pct > 0 ? '+' : ''}${advice.consumption_divergence_pct.toFixed(0)} % vs plan`
                      : null}
                  </li>
                )}
              </ul>
            )}
          </div>

          <RevePlanningFields
            options={revePlanning}
            consumptionWhPerKm={consumptionWhPerKm}
            disabled={busy}
            hideConsumption
            consumptionNote={advice?.consumption_note ?? advice?.plan.consumption_note}
            consumptionConfidence={advice?.consumption_confidence ?? advice?.plan.consumption_confidence}
            onChange={(value) => {
              setRevePlanning({ ...value, consumptionKwhPer100km: null })
              if (advice?.plan) {
                recalcOnRouteSettingsRef.current = true
              } else {
                setAdvice(null)
                cachedPlanRef.current = null
                onPlanResults(null)
                onPlanStateChange?.('idle')
              }
            }}
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
        </div>
      </details>
    </section>
  )
}
