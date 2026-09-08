import { useEffect, useRef, useState } from 'react'

import { fetchTripGuideFromCar } from '../api/auth'
import type { GeocodeResult, RoutePreference, TripChatOverrides, TripGuideResponse } from '../api/types'
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
import {
  defaultDepartureSoc,
  DepartureChargeSimulator,
  departureSocQueryParam,
} from './DepartureChargeSimulator'
import { AssistantChat } from './AssistantChat'
import { AssistantPlanBrief } from './AssistantPlanBrief'
import { useAuth } from './AuthContext'
import { LoginPanel } from './LoginPanel'
import { useActiveTrip } from '../hooks/useActiveTrip'
import { ActiveTripBanner } from '../components/trip/ActiveTripBanner'
import { ActiveTripProgressBar } from '../components/trip/ActiveTripProgressBar'
import { ReplanOnRouteBar } from '../search/ReplanOnRouteBar'
import { distancePointToRouteKm } from '../charging/routeDeviation'
import { routeChargingStops } from '../charging/planRouteStops'
import { clampTripProgress, bumpReplanTelemetry, EMPTY_REPLAN_TELEMETRY, type ReplanReason } from '../charging/activeTrip'
import {
  consumptionDivergencePct as calcConsumptionDivergencePct,
  effectiveConsumptionWhPerKm,
} from '../charging/consumptionDivergence'
import { replanReasonLabel } from '../charging/replanLabels'
import { vehicleProfileToChargingPlanQuery } from '../vehicle/vehicleProfile'
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
  const { activeTrip, saveActiveTrip, clearActiveTrip, enMarchaSettings, setAutoFollow, markStopCompleted } =
    useActiveTrip()
  const [stops, setStops] = useState<ItineraryStopDraft[]>(() => [createEmptyStop()])
  const [advice, setAdvice] = useState<TripGuideResponse | null>(null)
  const [planError, setPlanError] = useState<string | null>(null)
  const [loadingPlan, setLoadingPlan] = useState(false)
  const [routePreference, setRoutePreference] = useState<RoutePreference>('shortest')
  const [avoidTolls, setAvoidTolls] = useState(true)
  const [revePlanning, setRevePlanning] = useState<RevePlanningOptions>(() =>
    revePlanningForPreset(vehicleProfile.presetId),
  )
  const [simulateDeparture, setSimulateDeparture] = useState(false)
  const [departureSoc, setDepartureSoc] = useState(80)
  const [preferredOperators, setPreferredOperators] = useState<string[]>(
    () => DEFAULT_CHARGING_PREFERENCES.preferredOperators,
  )
  const [maxPriceEurKwh, setMaxPriceEurKwh] = useState<number | null>(
    () => DEFAULT_CHARGING_PREFERENCES.maxPriceEurKwh,
  )
  const recalcOnPreferenceRef = useRef(false)
  const runMapPlanRef = useRef<() => void>(() => {})
  const tripRestoredRef = useRef(false)
  const pendingReplanReasonRef = useRef<ReplanReason | null>(null)

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

  // Restaura viaje activo (vías + destino) sin pisar un itinerario ya escrito.
  useEffect(() => {
    if (!authenticated || tripRestoredRef.current || !activeTrip) {
      return
    }
    const hasInput = stops.some((stop) => stop.point != null || stop.text.trim().length > 0)
    if (hasInput) {
      return
    }
    tripRestoredRef.current = true
    const viaStops = activeTrip.waypoints.map((waypoint) => ({
      id: createEmptyStop().id,
      text: waypoint.label,
      point: {
        label: waypoint.label,
        lat: waypoint.lat,
        lon: waypoint.lon,
      },
    }))
    setStops([
      ...viaStops,
      {
        id: createEmptyStop().id,
        text: activeTrip.destination.label,
        point: {
          label: activeTrip.destination.label,
          lat: activeTrip.destination.lat,
          lon: activeTrip.destination.lon,
        },
      },
    ])
    setRoutePreference(activeTrip.routePreference)
    setAvoidTolls(activeTrip.avoidTolls)
  }, [authenticated, activeTrip, stops])

  const destination = stops[stops.length - 1]?.point ?? null
  const busy = loadingPlan

  // Debe ir antes de cualquier return: si no, al pasar a authenticated React
  // registra un hook de más y la UI queda en blanco.
  useEffect(() => {
    if (!authenticated) {
      return
    }
    if (!recalcOnPreferenceRef.current || busy || !advice?.plan || !destination) {
      return
    }
    recalcOnPreferenceRef.current = false
    runMapPlanRef.current()
  }, [authenticated, routePreference, avoidTolls, revePlanning, busy, advice?.plan, destination])

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

  const resolveItinerary = async (): Promise<{
    destination: GeocodeResult
    viaPoints: Array<{ lat: number; lon: number }>
    waypoints: Array<{ label: string; lat: number; lon: number }>
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
    const waypoints = resolved.slice(0, -1).map((point) => ({
      label: point.label,
      lat: point.lat,
      lon: point.lon,
    }))
    return {
      destination: resolved[resolved.length - 1],
      viaPoints: waypoints.map((point) => ({ lat: point.lat, lon: point.lon })),
      waypoints,
    }
  }

  const persistTripFromPlan = (
    dest: GeocodeResult,
    waypoints: Array<{ label: string; lat: number; lon: number }>,
    plan: import('../api/types').ChargingPlanResponse,
    options: { isReplan: boolean; replanReason: ReplanReason },
  ) => {
    const vehicleQuery = vehicleProfileToChargingPlanQuery(vehicleProfile)
    saveActiveTrip({
      version: 2,
      destination: { label: dest.label, lat: dest.lat, lon: dest.lon },
      waypoints,
      lastPlan: {
        stopIds: (plan.planned_stops ?? []).map((stop) => stop.station.id),
        routeDistanceKm: plan.route_distance_km,
        computedAt: Date.now(),
        consumptionWhPerKmEffective: effectiveConsumptionWhPerKm(vehicleQuery),
      },
      progress: clampTripProgress(
        activeTrip?.progress ?? { completedStopOrders: [], currentLegIndex: 0 },
        routeChargingStops(plan).length,
      ),
      replan: options.isReplan
        ? bumpReplanTelemetry(activeTrip?.replan, options.replanReason)
        : { ...EMPTY_REPLAN_TELEMETRY },
      corridorKm: 10,
      routePreference,
      avoidTolls,
      chargingPreferences: DEFAULT_CHARGING_PREFERENCES,
      originMode: 'car',
      updatedAt: Date.now(),
    })
  }

  const clearPlanState = () => {
    setAdvice(null)
    onPlanResults(null)
    onPlanStateChange?.('idle')
  }

  const runMapPlan = async () => {
    const replanReason = pendingReplanReasonRef.current ?? 'manual'
    pendingReplanReasonRef.current = null
    const isReplan = Boolean(activeTrip?.lastPlan) || Boolean(advice?.plan)

    let itinerary: {
      destination: GeocodeResult
      viaPoints: Array<{ lat: number; lon: number }>
      waypoints: Array<{ label: string; lat: number; lon: number }>
    }
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
      const result = await fetchTripGuideFromCar({
        destLat: dest.lat,
        destLon: dest.lon,
        destLabel: dest.label,
        viaPoints: itinerary.viaPoints,
        terrainFactor: terrain.factor,
        reserveSocPercent: DEFAULT_RESERVE_SOC_PERCENT,
        localMobilityKm: 40,
        includeRoute: true,
        culturalPoi: false,
        invokeDify: false,
        routePreference,
        avoidHighways: avoidTolls,
        departureSocPercent: departureSocParam,
        preferredOperators,
        maxPriceEurKwh,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: revePlanning.maxChargeSocPct,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
        consumptionKwhPer100km: revePlanning.consumptionKwhPer100km,
        vehiclePresetId: vehicleProfile.presetId,
        minKw: 100,
      })
      setAdvice(result)
      onPlanResults(result.plan)
      onPlanStateChange?.('ready')
      persistTripFromPlan(dest, itinerary.waypoints, result.plan, { isReplan, replanReason })
    } catch (err) {
      setAdvice(null)
      onPlanResults(null)
      onPlanStateChange?.('error')
      setPlanError(err instanceof Error ? err.message : 'Error al planificar')
    } finally {
      setLoadingPlan(false)
    }
  }

  const applyChatOverrides = async (overrides: TripChatOverrides) => {
    const nextPreference = overrides.route_preference ?? routePreference
    const nextAvoidTolls =
      overrides.avoid_highways !== undefined ? overrides.avoid_highways : avoidTolls
    const nextMaxCharge =
      overrides.max_charge_soc_pct != null ? overrides.max_charge_soc_pct : revePlanning.maxChargeSocPct
    const nextMaxPrice =
      overrides.max_price_eur_kwh != null ? overrides.max_price_eur_kwh : maxPriceEurKwh
    const nextOperators = overrides.preferred_operators ?? preferredOperators

    if (overrides.route_preference) {
      setRoutePreference(overrides.route_preference)
    }
    if (overrides.avoid_highways !== undefined) {
      setAvoidTolls(overrides.avoid_highways)
    }
    if (overrides.max_charge_soc_pct != null) {
      setRevePlanning((prev) => ({ ...prev, maxChargeSocPct: overrides.max_charge_soc_pct! }))
    }
    if (overrides.max_price_eur_kwh != null) {
      setMaxPriceEurKwh(overrides.max_price_eur_kwh)
    }
    if (overrides.preferred_operators) {
      setPreferredOperators(overrides.preferred_operators)
    }

    let itinerary: {
      destination: GeocodeResult
      viaPoints: Array<{ lat: number; lon: number }>
      waypoints: Array<{ label: string; lat: number; lon: number }>
    }
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
        culturalPoi: false,
        invokeDify: false,
        routePreference: nextPreference,
        avoidHighways: nextAvoidTolls,
        departureSocPercent: departureSocParam,
        preferredOperators: nextOperators,
        maxPriceEurKwh: nextMaxPrice,
        maxChargePowerKw: revePlanning.maxChargePowerKw,
        minDestinationSocPct: revePlanning.minDestinationSocPct,
        minStopArrivalSocPct: revePlanning.minStopArrivalSocPct,
        maxChargeSocPct: nextMaxCharge,
        excludeSlowChargers: revePlanning.excludeSlowChargers,
        consumptionKwhPer100km: revePlanning.consumptionKwhPer100km,
        vehiclePresetId: vehicleProfile.presetId,
        minKw: 100,
      })
      setAdvice(result)
      onPlanResults(result.plan)
      onPlanStateChange?.('ready')
      persistTripFromPlan(dest, itinerary.waypoints, result.plan, {
        isReplan: true,
        replanReason: 'manual',
      })
    } catch (err) {
      onPlanStateChange?.('error')
      setPlanError(err instanceof Error ? err.message : 'Error al recalcular el plan')
    } finally {
      setLoadingPlan(false)
    }
  }

  runMapPlanRef.current = () => {
    void runMapPlan()
  }

  const triggerMapPlan = (reason?: ReplanReason) => {
    if (reason) {
      pendingReplanReasonRef.current = reason
    }
    void runMapPlan()
  }

  const vehicleQueryForDisplay = vehicleProfileToChargingPlanQuery(vehicleProfile)
  const plannedConsumptionWhPerKm = activeTrip?.lastPlan?.consumptionWhPerKmEffective ?? null
  const currentConsumptionWhPerKm = effectiveConsumptionWhPerKm(vehicleQueryForDisplay)
  const consumptionDivergencePct =
    plannedConsumptionWhPerKm != null
      ? calcConsumptionDivergencePct(plannedConsumptionWhPerKm, currentConsumptionWhPerKm)
      : null

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
        {activeTrip ? (
          <ActiveTripBanner
            destinationLabel={activeTrip.destination.label}
            waypointCount={activeTrip.waypoints.length}
            gpsEnabled={false}
            gpsActive={false}
            gpsLoading={false}
            showGpsToggle={false}
            onGpsEnabledChange={() => undefined}
            onEndTrip={clearActiveTrip}
          />
        ) : null}
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

        <div className="route-form__actions">
          <button
            type="button"
            className="btn btn--primary"
            disabled={busy || vehicle == null || !hasDestinationInput}
            onClick={() => void runMapPlan()}
          >
            {loadingPlan ? 'Calculando plan…' : 'Calcular plan'}
          </button>
        </div>
        <p className="panel-hint">Calcula el plan; el chat sirve para cambiarlo. El mapa enseña la ruta.</p>
      </form>

      {planError && (
        <p className="route-message route-message--error" role="alert">
          {planError}
        </p>
      )}

      {advice && (
        <div className="assistant-advice">
          <AssistantChat
            planSnapshot={advice.context?.plan_snapshot}
            disabled={busy || !hasDestinationInput}
            onApplyOverrides={applyChatOverrides}
          />
          <AssistantPlanBrief
            plan={advice.plan}
            originLabel="Tu coche"
            destinationLabel={destination?.label}
            selectedStationId={selectedStationId}
            onSelectStation={onSelectStation}
          />
          {activeTrip &&
            advice.plan &&
            vehicle &&
            (activeTrip.replan.count > 0 ||
              (activeTrip.progress.currentLegIndex ?? 0) > 0 ||
              enMarchaSettings.autoFollow) && (
              <>
                <ReplanOnRouteBar
                  destinationLabel={activeTrip.destination.label}
                  originLabel={vehicleOrigin?.label ?? 'Coche'}
                  socPercent={Math.round(vehicle.battery_level_pct)}
                  socSourceLabel="TeslaMate"
                  loading={loadingPlan}
                  autoFollow={enMarchaSettings.autoFollow}
                  onAutoFollowChange={setAutoFollow}
                  onReplan={() => triggerMapPlan('manual')}
                  canReplan={!busy && hasDestinationInput}
                  lastUpdatedAt={activeTrip.updatedAt}
                  routeDeviationKm={distancePointToRouteKm(
                    { lat: vehicle.lat, lon: vehicle.lon },
                    advice.plan.route_geometry,
                  )}
                  consumptionDivergencePct={consumptionDivergencePct}
                  plannedConsumptionWhPerKm={plannedConsumptionWhPerKm}
                  currentConsumptionWhPerKm={currentConsumptionWhPerKm}
                  replanCount={activeTrip.replan.count}
                  lastReplanReason={replanReasonLabel(activeTrip.replan.lastReason)}
                />
                {routeChargingStops(advice.plan).length > 0 ? (
                  <ActiveTripProgressBar
                    plan={advice.plan}
                    progress={activeTrip.progress}
                    userLocation={{ lat: vehicle.lat, lon: vehicle.lon }}
                    onMarkStopCompleted={(stopOrder) =>
                      markStopCompleted(stopOrder, routeChargingStops(advice.plan).length)
                    }
                    onReplan={() => triggerMapPlan('stop_completed')}
                    replanLoading={loadingPlan}
                  />
                ) : null}
              </>
            )}
        </div>
      )}
    </section>
  )
}
