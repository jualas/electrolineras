import { useCallback, useEffect, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'

import { chargingPlanRouteMapFeatures, routeChargingStops, routeMapFitPoints, type RouteChargingStop } from '../charging/planRouteStops'
import { alongRouteToFeatures } from '../api/route'
import { fetchStationsGeoJSON } from '../api/stations'
import type { AlongRouteResponse, ChargingPlanResponse, GeocodeResult, MapBounds, Station, StationFeature } from '../api/types'
import {
  clearCityOverlay,
  ensureCityLayers,
  setCityReference,
  setCityRadiusCircle,
} from './cityLayers'
import {
  activeRouteGeometry,
  inactiveRouteGeometries,
  routeVariantGeometriesFromResponse,
} from './routeComparison'
import {
  clearRouteOverlay,
  ensureRouteLayers,
  fitMapToGeometries,
  fitMapToPoints,
  setRouteComparisonLines,
  setRouteEndpoints,
  setRangeCircle,
} from './routeLayers'
import {
  CLUSTER_COUNT_LAYER_ID,
  CLUSTER_LAYER_ID,
  bringOverlayStationLayersToFront,
  clearBrowseStationData,
  clearOverlayStationData,
  ensureStationLayers,
  interactiveStationLayers,
  mapShowsStationGlyphs,
  OVERLAY_POINT_LAYER_ID,
  PLANNED_STOP_CIRCLE_LAYER_ID,
  PLANNED_STOP_LABEL_LAYER_ID,
  POINT_LAYER_ID,
  setBrowseStationData,
  setOverlayStationData,
  setStationMapMode,
  stationPopupHtml,
  STATIONS_BROWSE_SOURCE_ID,
  updatePlannedStopSelection,
  type StationMapMode,
} from './stationLayers'
import {
  countFeaturesInBounds,
  extendStationFeatures,
  expandMapBounds,
  featuresForViewport,
  shouldFetchStations,
} from './mapStationMerge'
import { MapLayerControl, type MapLayerToggles } from './MapLayerControl'
import { enhancePlaceLabels } from './mapPlaceLabels'
import { ensureReliefLayers, setContourVisible, setShadowVisible } from './mapTerrainLayers'
import { ensureTrafficLayer, setTrafficLayerVisible } from './mapTrafficLayer'
import {
  clearUserLocationMarker,
  setUserLocationMarker,
} from './userLocationLayers'
import {
  MAP_FOLLOW_ZOOM,
  shouldRecenterMapOnUserMove,
} from './mapFollowUser'

const IBERIAN_CENTER: [number, number] = [-4.5, 40.2]
const DEFAULT_ZOOM = 5.8
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
const LOAD_DEBOUNCE_MS = 350
const MAP_FOCUS_ZOOM = 14
const FETCH_BBOX_PADDING = 0.35
const VIEWPORT_RENDER_PADDING = 0.35
const CLUSTER_NAV_GUARD_MS = 900
const MAX_BROWSE_CACHE = 10_000

type MapBoundsGetter = () => MapBounds | null

function getMapUiPadding(): maplibregl.PaddingOptions {
  const cluster = document.querySelector('.map-top-cluster')
  let top = 96
  if (cluster instanceof HTMLElement) {
    top = Math.ceil(cluster.getBoundingClientRect().bottom) + 16
  }
  return { top, bottom: 40, left: 48, right: 48 }
}

type MapViewProps = {
  className?: string
  loadStations?: boolean
  minKw?: number
  maxKw?: number
  publicOpenOnly?: boolean
  excludeParking?: boolean
  adHocOnly?: boolean
  availableOnly?: boolean
  maxPriceEurKwh?: number | null
  connectorTypes?: string[]
  mapLayers?: MapLayerToggles
  onMapLayersChange?: (next: MapLayerToggles) => void
  showLayerControl?: boolean
  routeData?: AlongRouteResponse | null
  routeSearching?: boolean
  routeChargePlanData?: ChargingPlanResponse | null
  chargePlanData?: ChargingPlanResponse | null
  chargePlanSearching?: boolean
  focusStation?: Station | null
  selectedPlannedStopOrder?: number | null
  onPlannedStopSelect?: (stop: RouteChargingStop | null) => void
  mapFocusPlace?: GeocodeResult | null
  onRegisterMapBounds?: (getter: MapBoundsGetter | null) => void
  tripUserLocation?: { lat: number; lon: number; accuracyM?: number | null } | null
  tripTrackingActive?: boolean
  centerOnMe?: boolean
  onCenterOnMeChange?: (value: boolean) => void
  liveActive?: boolean
  onLiveActiveChange?: (value: boolean) => void
  livePowerHint?: string
}

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

function boundsFromMap(map: maplibregl.Map): MapBounds {
  const bounds = map.getBounds()
  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  }
}

function trimBrowseCache(features: StationFeature[]): StationFeature[] {
  if (features.length <= MAX_BROWSE_CACHE) {
    return features
  }
  return features.slice(features.length - MAX_BROWSE_CACHE)
}

function showStationPopup(
  map: maplibregl.Map,
  popup: maplibregl.Popup | null,
  coordinates: [number, number],
  properties: Record<string, unknown>,
): void {
  popup
    ?.setLngLat(coordinates)
    .setHTML(
      stationPopupHtml(properties, {
        lat: coordinates[1],
        lon: coordinates[0],
      }),
    )
    .addTo(map)
}

function handleClusterClick(
  map: maplibregl.Map,
  feature: maplibregl.MapGeoJSONFeature,
  clusterNavUntilRef: { current: number },
): void {
  const clusterId = feature.properties?.cluster_id
  const pointCount = Number(feature.properties?.point_count ?? 0)
  const source = map.getSource(STATIONS_BROWSE_SOURCE_ID) as maplibregl.GeoJSONSource
  if (clusterId === undefined) {
    return
  }
  clusterNavUntilRef.current = Date.now() + CLUSTER_NAV_GUARD_MS
  const coordinates = (feature.geometry as { coordinates: [number, number] }).coordinates.slice() as [
    number,
    number,
  ]
  const leafLimit = pointCount > 0 ? pointCount : 50
  void source
    .getClusterLeaves(clusterId, leafLimit, 0)
    .then((leaves) => {
      if (leaves.length > 0 && leaves.length <= 24) {
        const bounds = new maplibregl.LngLatBounds()
        for (const leaf of leaves) {
          if (leaf.geometry.type !== 'Point') {
            continue
          }
          bounds.extend(leaf.geometry.coordinates as [number, number])
        }
        if (!bounds.isEmpty()) {
          map.fitBounds(bounds, { padding: 80, maxZoom: 17, duration: 550 })
          return
        }
      }
      return source.getClusterExpansionZoom(clusterId).then((zoom) => {
        map.easeTo({
          center: coordinates,
          zoom: Math.min(Math.max(zoom + 1, 14), 18),
          duration: 550,
        })
      })
    })
    .catch(() => {
      map.easeTo({ center: coordinates, zoom: Math.min(map.getZoom() + 2, 17), duration: 550 })
    })
}

export function MapView({
  className,
  loadStations = true,
  minKw,
  maxKw,
  publicOpenOnly = false,
  excludeParking = false,
  adHocOnly = false,
  availableOnly = false,
  maxPriceEurKwh = null,
  connectorTypes = [],
  mapLayers,
  onMapLayersChange,
  showLayerControl = false,
  routeData = null,
  routeSearching = false,
  routeChargePlanData = null,
  chargePlanData = null,
  chargePlanSearching = false,
  focusStation = null,
  selectedPlannedStopOrder = null,
  onPlannedStopSelect,
  mapFocusPlace = null,
  onRegisterMapBounds,
  tripUserLocation = null,
  tripTrackingActive = false,
  centerOnMe = false,
  onCenterOnMeChange,
  liveActive = false,
  onLiveActiveChange,
  livePowerHint = 'filtro de potencia',
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const debounceRef = useRef<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const loadSeqRef = useRef(0)
  const loadedFeaturesRef = useRef<StationFeature[]>([])
  const coverageBoundsRef = useRef<MapBounds | null>(null)
  const lastLoadedZoomRef = useRef<number | null>(null)
  const stationMapModeRef = useRef<StationMapMode>('browse')
  const loadStationsRef = useRef(loadStations)
  const mapFocusPlaceRef = useRef(mapFocusPlace)
  const stationFiltersRef = useRef({
    minKw,
    maxKw,
    publicOpenOnly,
    excludeParking,
    adHocOnly,
    availableOnly,
    maxPriceEurKwh,
    connectorTypes,
  })
  const mapLayersRef = useRef(mapLayers)
  const routeDataRef = useRef(routeData)
  const routeChargePlanDataRef = useRef(routeChargePlanData)
  const chargePlanDataRef = useRef(chargePlanData)
  const selectedPlannedStopOrderRef = useRef(selectedPlannedStopOrder)
  const onPlannedStopSelectRef = useRef(onPlannedStopSelect)
  const clusterNavUntilRef = useRef(0)
  const userMovedMapRef = useRef(false)
  const lastCenteredUserRef = useRef<{ lat: number; lon: number } | null>(null)
  const tripUserLocationRef = useRef(tripUserLocation)
  const centerOnMeRef = useRef(centerOnMe)
  const tripTrackingActiveRef = useRef(tripTrackingActive)
  const loadVisibleStationsRef = useRef<(map: maplibregl.Map, force?: boolean) => void>(() => undefined)
  const scheduleLoadRef = useRef<(map: maplibregl.Map, force?: boolean) => void>(() => undefined)
  const applyActiveOverlayRef = useRef<(map: maplibregl.Map) => void>(() => undefined)

  loadStationsRef.current = loadStations
  mapFocusPlaceRef.current = mapFocusPlace
  stationFiltersRef.current = {
    minKw,
    maxKw,
    publicOpenOnly,
    excludeParking,
    adHocOnly,
    availableOnly,
    maxPriceEurKwh,
    connectorTypes,
  }
  mapLayersRef.current = mapLayers
  routeDataRef.current = routeData
  routeChargePlanDataRef.current = routeChargePlanData
  chargePlanDataRef.current = chargePlanData
  selectedPlannedStopOrderRef.current = selectedPlannedStopOrder
  onPlannedStopSelectRef.current = onPlannedStopSelect
  tripUserLocationRef.current = tripUserLocation
  centerOnMeRef.current = centerOnMe
  tripTrackingActiveRef.current = tripTrackingActive

  const easeMapToUser = useCallback((map: maplibregl.Map, point: { lat: number; lon: number }, force = false) => {
    if (!force && userMovedMapRef.current) {
      return
    }
    if (!force && !shouldRecenterMapOnUserMove(lastCenteredUserRef.current, point)) {
      return
    }
    lastCenteredUserRef.current = point
    map.easeTo({
      center: [point.lon, point.lat],
      zoom: Math.max(map.getZoom(), MAP_FOLLOW_ZOOM),
      duration: 900,
      essential: true,
      padding: getMapUiPadding(),
    })
  }, [])

  const handleCenterOnMeClick = useCallback(() => {
    const map = mapRef.current
    const point = tripUserLocationRef.current
    userMovedMapRef.current = false
    onCenterOnMeChange?.(true)
    if (!map || !point) {
      return
    }
    const center = () => easeMapToUser(map, point, true)
    if (map.isStyleLoaded()) {
      center()
      return
    }
    map.once('load', center)
  }, [easeMapToUser, onCenterOnMeChange])

  const resolveRouteChargingStop = useCallback(
    (order: number): RouteChargingStop | null => {
      const plan = chargePlanDataRef.current ?? routeChargePlanDataRef.current
      if (!plan) {
        return null
      }
      const planned = plan.planned_stops?.find((stop) => stop.order === order)
      if (planned) {
        return planned
      }
      const routeStops = routeChargingStops(plan)
      return (
        routeStops.find((stop, index) => {
          if ('order' in stop && typeof stop.order === 'number') {
            return stop.order === order
          }
          return index + 1 === order
        }) ?? null
      )
    },
    [],
  )

  const handlePlannedStopFeatureClick = useCallback(
    (properties: Record<string, unknown>) => {
      const rawOrder = properties.planned_stop_order
      if (rawOrder == null || Number.isNaN(Number(rawOrder))) {
        return false
      }
      const stop = resolveRouteChargingStop(Number(rawOrder))
      if (!stop) {
        return false
      }
      onPlannedStopSelectRef.current?.(stop)
      return true
    },
    [resolveRouteChargingStop],
  )
  const handlePlannedStopFeatureClickRef = useRef(handlePlannedStopFeatureClick)
  handlePlannedStopFeatureClickRef.current = handlePlannedStopFeatureClick

  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [stationCount, setStationCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [overlayMode, setOverlayMode] = useState<'map' | 'route' | 'charge' | 'none'>('none')

  const setStationMapModeState = useCallback((map: maplibregl.Map, mode: StationMapMode) => {
    stationMapModeRef.current = mode
    setStationMapMode(map, mode)
  }, [])

  const applyMapPlacePin = useCallback(
    (map: maplibregl.Map, place: GeocodeResult | null) => {
      if (!place) {
        return
      }
      ensureCityLayers(map)
      setCityReference(map, place)
      setCityRadiusCircle(map, null, null)
    },
    [],
  )

  const paintBrowseStations = useCallback(
    (map: maplibregl.Map, features: StationFeature[]) => {
      ensureStationLayers(map)
      // Si hay una ruta/plan activo, sus paradas se superponen al mapa de estaciones
      // (estilo REVE) en vez de sustituirlo: no se toca la capa overlay ni el badge.
      const hasOverlay = Boolean(routeDataRef.current || chargePlanDataRef.current)
      if (!hasOverlay) {
        clearOverlayStationData(map)
      }
      setStationMapModeState(map, hasOverlay ? 'both' : 'browse')
      const visibleBounds = boundsFromMap(map)
      const toRender = featuresForViewport(features, visibleBounds, VIEWPORT_RENDER_PADDING)
      setBrowseStationData(map, {
        type: 'FeatureCollection',
        features: toRender,
      })
      if (!hasOverlay) {
        setStationCount(countFeaturesInBounds(features, visibleBounds))
        setLoadState(features.length > 0 ? 'ready' : 'idle')
        setOverlayMode('map')
      }
    },
    [setStationMapModeState],
  )

  const paintOverlayStations = useCallback(
    (map: maplibregl.Map, features: StationFeature[], mode: 'route' | 'charge', keepBrowse: boolean) => {
      ensureStationLayers(map)
      if (!keepBrowse) {
        clearBrowseStationData(map)
      }
      setStationMapModeState(map, keepBrowse ? 'both' : 'overlay')
      setOverlayStationData(map, {
        type: 'FeatureCollection',
        features,
      })
      bringOverlayStationLayersToFront(map)
      updatePlannedStopSelection(map, selectedPlannedStopOrderRef.current)
      setStationCount(features.length)
      setHasMore(false)
      setLoadState(features.length > 0 ? 'ready' : 'idle')
      setOverlayMode(mode)
    },
    [setStationMapModeState],
  )

  const applyRouteOverlay = useCallback((map: maplibregl.Map, data: AlongRouteResponse, chargePlan: ChargingPlanResponse | null | undefined, keepBrowse: boolean) => {
    ensureRouteLayers(map)
    clearCityOverlay(map)
    const variantGeometries = routeVariantGeometriesFromResponse(data)
    const preference = data.route_preference ?? chargePlan?.route_preference ?? 'fastest'
    const activeGeometry = activeRouteGeometry(preference, variantGeometries, data.route_geometry)
    const alternateGeometries = inactiveRouteGeometries(preference, variantGeometries)
    if (activeGeometry) {
      setRouteComparisonLines(map, activeGeometry, alternateGeometries)
      const fitGeometries = [activeGeometry, ...alternateGeometries]
      fitMapToGeometries(map, fitGeometries)
    } else {
      setRouteComparisonLines(map, null, [])
    }
    setRouteEndpoints(map, data.origin, data.destination)
    if (chargePlan) {
      setRangeCircle(map, chargePlan.origin, chargePlan.charging_reach_km)
    } else {
      setRangeCircle(map, null, null)
    }
    const routeFeatures = alongRouteToFeatures(data.results)
    const chargePlanFeatures =
      chargePlan && routeChargingStops(chargePlan).length > 0
        ? chargingPlanRouteMapFeatures(chargePlan)
        : []
    const overlayFeatures =
      chargePlanFeatures.length > 0
        ? chargePlanFeatures
        : [
            ...chargePlanFeatures.filter(
              (feature) => !routeFeatures.some((routeFeature) => routeFeature.id === feature.id),
            ),
            ...routeFeatures,
          ]
    paintOverlayStations(map, overlayFeatures, 'route', keepBrowse)
  }, [paintOverlayStations])

  const applyChargePlanOverlay = useCallback((map: maplibregl.Map, data: ChargingPlanResponse, keepBrowse: boolean) => {
    ensureRouteLayers(map)
    clearCityOverlay(map)
    const variantGeometries = routeVariantGeometriesFromResponse(data)
    const preference = data.route_preference ?? 'fastest'
    const routeGeometry = activeRouteGeometry(
      preference,
      variantGeometries,
      data.route_geometry ?? data.preview_route_geometry,
    )
    const alternateGeometries = inactiveRouteGeometries(preference, variantGeometries)
    if (routeGeometry) {
      setRouteComparisonLines(map, routeGeometry, alternateGeometries)
      fitMapToGeometries(map, [routeGeometry, ...alternateGeometries])
    } else {
      setRouteComparisonLines(map, null, [])
      fitMapToPoints(map, routeMapFitPoints(data))
    }
    setRouteEndpoints(map, data.origin, data.destination)
    setRangeCircle(map, data.origin, data.charging_reach_km)
    const features = chargingPlanRouteMapFeatures(data)
    paintOverlayStations(map, features, 'charge', keepBrowse)
  }, [paintOverlayStations])

  const clearSearchOverlays = useCallback((map: maplibregl.Map) => {
    clearRouteOverlay(map)
    clearCityOverlay(map)
    clearBrowseStationData(map)
    clearOverlayStationData(map)
    setStationMapModeState(map, 'none')
    setOverlayMode('none')
  }, [setStationMapModeState])

  const paintStationsOnMap = useCallback(
    (map: maplibregl.Map, features: StationFeature[]) => {
      loadedFeaturesRef.current = trimBrowseCache(features)
      applyMapPlacePin(map, mapFocusPlaceRef.current)
      paintBrowseStations(map, loadedFeaturesRef.current)
    },
    [applyMapPlacePin, paintBrowseStations],
  )

  const applyActiveOverlay = useCallback(
    (map: maplibregl.Map) => {
      const keepBrowse = loadStationsRef.current

      if (keepBrowse) {
        if (loadedFeaturesRef.current.length > 0) {
          paintStationsOnMap(map, loadedFeaturesRef.current)
        } else {
          scheduleLoadRef.current(map, true)
        }
      }

      if (routeDataRef.current) {
        applyRouteOverlay(map, routeDataRef.current, routeChargePlanDataRef.current, keepBrowse)
        return
      }
      if (chargePlanDataRef.current) {
        applyChargePlanOverlay(map, chargePlanDataRef.current, keepBrowse)
        return
      }
      if (keepBrowse) {
        // Sin ruta/plan activo: solo limpiar restos de una ruta anterior (línea,
        // extremos, círculo de alcance), el mapa de estaciones ya lo dejó listo arriba.
        clearRouteOverlay(map)
        clearCityOverlay(map)
        return
      }
      clearSearchOverlays(map)
      setStationCount(0)
      setHasMore(false)
      setLoadState('idle')
    },
    [applyRouteOverlay, applyChargePlanOverlay, clearSearchOverlays, paintStationsOnMap],
  )

  applyActiveOverlayRef.current = applyActiveOverlay

  const runWhenMapReady = useCallback((map: maplibregl.Map, action: (map: maplibregl.Map) => void) => {
    if (map.isStyleLoaded()) {
      action(map)
      return
    }
    map.once('load', () => action(map))
  }, [])

  const focusMapOnPlace = useCallback(
    (map: maplibregl.Map, place: GeocodeResult) => {
      const centerView = () => {
        applyMapPlacePin(map, place)
        map.flyTo({
          center: [place.lon, place.lat],
          zoom: Math.max(map.getZoom(), MAP_FOCUS_ZOOM),
          duration: 700,
          essential: true,
          padding: getMapUiPadding(),
        })
      }

      if (map.isStyleLoaded()) {
        centerView()
        return
      }

      map.once('load', centerView)
    },
    [applyMapPlacePin],
  )

  const loadVisibleStations = useCallback(
    async (map: maplibregl.Map, force = false) => {
      if (!loadStationsRef.current) {
        return
      }
      if (Date.now() < clusterNavUntilRef.current) {
        return
      }

      const zoom = map.getZoom()
      const visibleBounds = boundsFromMap(map)
      const inView = countFeaturesInBounds(loadedFeaturesRef.current, visibleBounds)

      if (
        !force &&
        loadedFeaturesRef.current.length > 0 &&
        !shouldFetchStations(coverageBoundsRef.current, visibleBounds, lastLoadedZoomRef.current, zoom)
      ) {
        const hasOverlay = Boolean(routeDataRef.current || chargePlanDataRef.current)
        if (!hasOverlay) {
          setStationCount(inView)
          setLoadState(inView > 0 || loadedFeaturesRef.current.length > 0 ? 'ready' : 'idle')
        }
        lastLoadedZoomRef.current = zoom
        if (inView > 0 && !mapShowsStationGlyphs(map, 'browse')) {
          paintBrowseStations(map, loadedFeaturesRef.current)
        }
        return
      }

      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller
      const loadSeq = ++loadSeqRef.current

      setLoadState('loading')
      setErrorMessage(null)

      try {
        const filters = stationFiltersRef.current
        const limit = zoom < 7 ? 3000 : zoom < 10 ? 5000 : 4000
        let fetchBounds = expandMapBounds(visibleBounds, FETCH_BBOX_PADDING)
        const stationQuery = {
          bbox: fetchBounds,
          limit,
          minKw: filters.minKw,
          maxKw: filters.maxKw,
          publicOpenOnly: filters.publicOpenOnly,
          excludeParking: filters.excludeParking,
          adHocOnly: filters.adHocOnly,
          availableOnly: filters.availableOnly,
          maxPriceEurKwh: filters.maxPriceEurKwh,
          connectorTypes: filters.connectorTypes,
        }
        let payload = await fetchStationsGeoJSON(stationQuery, { signal: controller.signal })

        if (controller.signal.aborted || loadSeq !== loadSeqRef.current) {
          return
        }

        if (payload.features.length === 0 && zoom >= 11) {
          fetchBounds = expandMapBounds(visibleBounds, 1.0)
          payload = await fetchStationsGeoJSON(
            { ...stationQuery, bbox: fetchBounds },
            { signal: controller.signal },
          )
        }

        if (controller.signal.aborted || loadSeq !== loadSeqRef.current) {
          return
        }

        coverageBoundsRef.current = fetchBounds
        lastLoadedZoomRef.current = zoom
        setHasMore(payload.pagination.has_more)
        const merged = trimBrowseCache(extendStationFeatures(loadedFeaturesRef.current, payload.features))
        loadedFeaturesRef.current = merged
        applyMapPlacePin(map, mapFocusPlaceRef.current)
        paintBrowseStations(map, merged)
      } catch (error) {
        if (controller.signal.aborted || loadSeq !== loadSeqRef.current) {
          return
        }
        const message = error instanceof Error ? error.message : 'Error al cargar estaciones'
        setErrorMessage(message)
        setLoadState('error')
      }
    },
    [applyMapPlacePin, paintBrowseStations],
  )

  const scheduleLoad = useCallback((map: maplibregl.Map, force = false) => {
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current)
    }
    debounceRef.current = window.setTimeout(() => {
      void loadVisibleStationsRef.current(map, force)
    }, LOAD_DEBOUNCE_MS)
  }, [])

  loadVisibleStationsRef.current = loadVisibleStations
  scheduleLoadRef.current = scheduleLoad

  useEffect(() => {
    if (!onRegisterMapBounds) {
      return
    }
    onRegisterMapBounds(() => {
      const map = mapRef.current
      if (!map || !map.isStyleLoaded()) {
        return null
      }
      return boundsFromMap(map)
    })
    return () => onRegisterMapBounds(null)
  }, [onRegisterMapBounds])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return undefined
    }

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: MAP_STYLE,
      center: IBERIAN_CENTER,
      zoom: DEFAULT_ZOOM,
      attributionControl: false,
    })

    map.addControl(
      new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: false }),
      'bottom-right',
    )
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    map.addControl(new maplibregl.AttributionControl({ compact: false }), 'bottom-left')
    popupRef.current = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: false,
      maxWidth: '280px',
      className: 'station-popup-container',
    })

    const onClusterClick = (event: maplibregl.MapLayerMouseEvent) => {
      const feature = event.features?.[0]
      if (!feature) {
        return
      }
      handleClusterClick(map, feature, clusterNavUntilRef)
    }

    const onPointClick = (event: maplibregl.MapLayerMouseEvent) => {
      const feature = event.features?.[0]
      if (!feature || feature.geometry.type !== 'Point') {
        return
      }
      const properties = feature.properties ?? {}
      if (handlePlannedStopFeatureClickRef.current(properties)) {
        popupRef.current?.remove()
        return
      }
      const coordinates = feature.geometry.coordinates.slice() as [number, number]
      showStationPopup(map, popupRef.current, coordinates, properties)
    }

    const onPlannedLabelClick = (event: maplibregl.MapLayerMouseEvent) => {
      const feature = event.features?.[0]
      if (!feature) {
        return
      }
      if (handlePlannedStopFeatureClickRef.current(feature.properties ?? {})) {
        popupRef.current?.remove()
      }
    }

    const onStationPointerEnter = () => {
      map.getCanvas().style.cursor = 'pointer'
    }
    const onStationPointerLeave = () => {
      map.getCanvas().style.cursor = ''
    }

    map.on('load', () => {
      enhancePlaceLabels(map)
      ensureReliefLayers(map)
      ensureTrafficLayer(map)
      ensureStationLayers(map)
      ensureRouteLayers(map)
      ensureCityLayers(map)
      const layers = mapLayersRef.current
      setShadowVisible(map, true)
      if (layers) {
        setContourVisible(map, layers.detail)
        setTrafficLayerVisible(map, layers.traffic)
      }
      applyActiveOverlayRef.current(map)
    })

    map.on('moveend', () => {
      if (Date.now() < clusterNavUntilRef.current) {
        return
      }
      if (loadStationsRef.current) {
        scheduleLoadRef.current(map)
      }
    })

    map.on('dragstart', () => {
      if (tripTrackingActiveRef.current) {
        userMovedMapRef.current = true
      }
    })

    map.on('click', CLUSTER_LAYER_ID, onClusterClick)
    map.on('click', CLUSTER_COUNT_LAYER_ID, onClusterClick)
    map.on('click', POINT_LAYER_ID, onPointClick)
    map.on('click', OVERLAY_POINT_LAYER_ID, onPointClick)
    map.on('click', PLANNED_STOP_CIRCLE_LAYER_ID, onPointClick)
    map.on('click', PLANNED_STOP_LABEL_LAYER_ID, onPlannedLabelClick)

    map.on('click', (event) => {
      const mode = stationMapModeRef.current
      const hit = map.queryRenderedFeatures(event.point, {
        layers: interactiveStationLayers(mode),
      })
      if (hit.length === 0) {
        popupRef.current?.remove()
        if ((mode === 'overlay' || mode === 'both') && selectedPlannedStopOrderRef.current != null) {
          onPlannedStopSelectRef.current?.(null)
        }
      }
    })

    for (const layerId of [
      CLUSTER_LAYER_ID,
      CLUSTER_COUNT_LAYER_ID,
      POINT_LAYER_ID,
      OVERLAY_POINT_LAYER_ID,
      PLANNED_STOP_CIRCLE_LAYER_ID,
      PLANNED_STOP_LABEL_LAYER_ID,
    ]) {
      map.on('mouseenter', layerId, onStationPointerEnter)
      map.on('mouseleave', layerId, onStationPointerLeave)
    }

    mapRef.current = map

    return () => {
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current)
      }
      abortRef.current?.abort()
      popupRef.current?.remove()
      popupRef.current = null
      map.remove()
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }
    runWhenMapReady(map, (readyMap) => {
      // applyActiveOverlay ya decide si (re)pinta el mapa de estaciones, aplica la
      // ruta/plan activo, o ambos a la vez (estilo REVE): nunca hay que elegir uno u otro.
      if (loadStations && loadedFeaturesRef.current.length === 0) {
        coverageBoundsRef.current = null
        lastLoadedZoomRef.current = null
      }
      applyActiveOverlay(readyMap)
    })
  }, [
    loadStations,
    routeData,
    routeChargePlanData,
    chargePlanData,
    minKw,
    maxKw,
    scheduleLoad,
    applyActiveOverlay,
    runWhenMapReady,
  ])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) {
      return
    }
    updatePlannedStopSelection(map, selectedPlannedStopOrder)
  }, [selectedPlannedStopOrder])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded() || !focusStation) {
      return
    }
    const plan = chargePlanData ?? routeChargePlanData
    let plannedOrder: number | null = null
    if (plan) {
      const fromPlanned = plan.planned_stops?.find((stop) => stop.station.id === focusStation.id)
      if (fromPlanned) {
        plannedOrder = fromPlanned.order
      } else {
        const index = routeChargingStops(plan).findIndex((stop) => stop.station.id === focusStation.id)
        if (index >= 0) {
          plannedOrder = index + 1
        }
      }
    }
    const isPlannedStop = plannedOrder != null
    const { lat, lon } = focusStation.location
    map.flyTo({ center: [lon, lat], zoom: 14, duration: 700 })
    if (isPlannedStop) {
      popupRef.current?.remove()
      return
    }
    showStationPopup(
      map,
      popupRef.current,
      [lon, lat],
      {
        id: focusStation.id,
        site_name: focusStation.site_name,
        operator: focusStation.operator,
        max_power_kw: focusStation.max_power_kw,
        connector_count: focusStation.connectors.length,
        country: focusStation.country,
        address: focusStation.location.address ?? null,
        dynamic_status: focusStation.dynamic_status ?? null,
        dynamic_price_eur_kwh: focusStation.dynamic_price_eur_kwh ?? null,
        external_rating_avg: focusStation.external_rating_avg ?? null,
        external_rating_count: focusStation.external_rating_count ?? 0,
        external_comments: focusStation.external_comments ?? [],
      },
    )
  }, [focusStation, chargePlanData, routeChargePlanData])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadStations) {
      return
    }
    if (!mapFocusPlace) {
      clearCityOverlay(map)
      return
    }
    focusMapOnPlace(map, mapFocusPlace)
    loadedFeaturesRef.current = []
    coverageBoundsRef.current = null
    lastLoadedZoomRef.current = null
    scheduleLoad(map, true)
  }, [mapFocusPlace, loadStations, focusMapOnPlace, scheduleLoad])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded() || !mapLayers) {
      return
    }
    setShadowVisible(map, true)
    if (mapLayers) {
      setContourVisible(map, mapLayers.detail)
      setTrafficLayerVisible(map, mapLayers.traffic)
    }
  }, [mapLayers])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !loadStations) {
      return
    }
    loadedFeaturesRef.current = []
    coverageBoundsRef.current = null
    lastLoadedZoomRef.current = null
    scheduleLoad(map, true)
  }, [minKw, maxKw, publicOpenOnly, excludeParking, adHocOnly, availableOnly, maxPriceEurKwh, connectorTypes.join('|'), loadStations, scheduleLoad])

  useEffect(() => {
    if (!tripTrackingActive && !liveActive) {
      userMovedMapRef.current = false
      lastCenteredUserRef.current = null
    }
  }, [tripTrackingActive, liveActive])

  useEffect(() => {
    const map = mapRef.current
    if (!map) {
      return
    }
    const tracking = tripTrackingActive || liveActive
    runWhenMapReady(map, (readyMap) => {
      if (!tracking || !tripUserLocation) {
        clearUserLocationMarker(readyMap)
        return
      }
      setUserLocationMarker(readyMap, tripUserLocation)
      if (centerOnMe || liveActive) {
        easeMapToUser(readyMap, tripUserLocation)
      }
    })
  }, [tripTrackingActive, liveActive, tripUserLocation, centerOnMe, easeMapToUser, runWhenMapReady])

  const showMapBadge =
    loadStations ||
    routeData !== null ||
    chargePlanData !== null ||
    routeSearching ||
    chargePlanSearching

  const badgeLabel =
    overlayMode === 'route'
      ? `${stationCount} en ruta`
      : overlayMode === 'charge'
        ? `${stationCount} paradas`
        : overlayMode === 'map' && publicOpenOnly
          ? `${stationCount} acceso público`
          : `${stationCount} en vista`

  return (
    <div className="map-shell">
      <div ref={containerRef} className={className ?? 'map-view'} aria-label="Mapa peninsular" />
      {showLayerControl && mapLayers && onMapLayersChange && (
        <MapLayerControl value={mapLayers} onChange={onMapLayersChange} />
      )}
      <div className="map-follow-controls" aria-label="Cargador más cercano">
        <button
          type="button"
          className={`map-follow-btn ${liveActive ? 'map-follow-btn--live' : ''}`}
          aria-pressed={liveActive}
          title={
            liveActive
              ? `Desactivar: más cercano (${livePowerHint})`
              : `Más cercano a tu GPS según potencia: ${livePowerHint}`
          }
          onClick={() => onLiveActiveChange?.(!liveActive)}
        >
          {liveActive ? 'Más cercano · ON' : 'Más cercano'}
        </button>
        {tripTrackingActive ? (
          <button
            type="button"
            className={`map-follow-btn ${centerOnMe ? 'map-follow-btn--active' : ''}`}
            aria-pressed={centerOnMe}
            title={centerOnMe ? 'Dejar de centrar en mi posición' : 'Centrar mapa en mi posición'}
            onClick={() => {
              if (centerOnMe) {
                onCenterOnMeChange?.(false)
                return
              }
              handleCenterOnMeClick()
            }}
          >
            {centerOnMe ? 'Centrado en mí' : 'Centrar en mí'}
          </button>
        ) : null}
      </div>
      {showMapBadge && (
        <div className="map-overlay" aria-live="polite">
          {routeSearching && <span className="map-badge">Calculando ruta…</span>}
          {chargePlanSearching && !routeSearching && <span className="map-badge">Calculando plan…</span>}
          {!routeSearching && !chargePlanSearching && loadState === 'loading' && (
            <span className="map-badge">Cargando estaciones…</span>
          )}
          {!routeSearching && !chargePlanSearching && loadState === 'ready' && (
            <span className="map-badge map-badge--ok">
              {badgeLabel}
              {overlayMode === 'map' && hasMore ? ' (límite)' : ''}
            </span>
          )}
          {!routeSearching && !chargePlanSearching && loadState === 'error' && (
            <span className="map-badge map-badge--error" title={errorMessage ?? undefined}>
              Error de datos
            </span>
          )}
        </div>
      )}
    </div>
  )
}
