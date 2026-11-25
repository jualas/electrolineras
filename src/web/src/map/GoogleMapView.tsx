/* eslint-disable @typescript-eslint/no-explicit-any */
import { useCallback, useEffect, useRef, useState } from 'react'

import { alongRouteToFeatures } from '../api/route'
import { fetchStationsGeoJSON } from '../api/stations'
import type {
  AlongRouteResponse,
  ChargingPlanResponse,
  MapBounds,
  RouteLineGeometry,
  StationFeature,
} from '../api/types'
import {
  chargingPlanRouteMapFeatures,
  routeChargingStops,
  routeMapFitPoints,
  type RouteChargingStop,
} from '../charging/planRouteStops'
import { loadGoogleMapsApi, type GoogleMapsApi } from './googleMapsLoader'
import { clusterStationsForZoom, stationMarkerColor } from './googleStationClustering'
import { MAP_FOLLOW_ZOOM, shouldRecenterMapOnUserMove } from './mapFollowUser'
import { MapLayerControl } from './MapLayerControl'
import {
  countFeaturesInBounds,
  expandMapBounds,
  extendStationFeatures,
  featuresForViewport,
  shouldFetchStations,
  zoomedInPastTruncatedCoverage,
} from './mapStationMerge'
import type { MapViewProps } from './MapView'
import {
  activeRouteGeometry,
  inactiveRouteGeometries,
  routeVariantGeometriesFromResponse,
} from './routeComparison'
import { stationPopupHtml } from './stationLayers'

const IBERIAN_CENTER = { lat: 40.2, lng: -4.5 }
const DEFAULT_ZOOM = 6
const LOAD_DEBOUNCE_MS = 350
const MAP_FOCUS_ZOOM = 14
const FETCH_BBOX_PADDING = 0.35
const VIEWPORT_RENDER_PADDING = 0.35
const MAX_BROWSE_CACHE = 10_000

type LoadState = 'idle' | 'loading' | 'ready' | 'error'

function getMapUiPadding(): { top: number; bottom: number; left: number; right: number } {
  const cluster = document.querySelector('.map-top-cluster')
  let top = 96
  if (cluster instanceof HTMLElement) {
    top = Math.ceil(cluster.getBoundingClientRect().bottom) + 16
  }
  return { top, bottom: 48, left: 48, right: 48 }
}

function boundsFromGoogleMap(map: any): MapBounds | null {
  const bounds = map.getBounds?.()
  if (!bounds) {
    return null
  }
  const ne = bounds.getNorthEast()
  const sw = bounds.getSouthWest()
  return {
    west: sw.lng(),
    south: sw.lat(),
    east: ne.lng(),
    north: ne.lat(),
  }
}

function trimBrowseCache(features: StationFeature[]): StationFeature[] {
  if (features.length <= MAX_BROWSE_CACHE) {
    return features
  }
  return features.slice(features.length - MAX_BROWSE_CACHE)
}

function clearMapObjects(list: any[]): void {
  for (const item of list) {
    item?.setMap?.(null)
  }
  list.length = 0
}

function toLatLngPath(geometry: RouteLineGeometry): Array<{ lat: number; lng: number }> {
  return geometry.coordinates.map(([lon, lat]) => ({ lat, lng: lon }))
}

export function GoogleMapView({
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
  const gmRef = useRef<GoogleMapsApi | null>(null)
  const mapRef = useRef<any | null>(null)
  const infoWindowRef = useRef<any | null>(null)
  const trafficLayerRef = useRef<any | null>(null)

  const browseMarkersRef = useRef<any[]>([])
  const overlayMarkersRef = useRef<any[]>([])
  const routeLinesRef = useRef<any[]>([])
  const routeEndpointsRef = useRef<any[]>([])
  const rangeCircleRef = useRef<any | null>(null)
  const placePinRef = useRef<any | null>(null)
  const userMarkersRef = useRef<any[]>([])

  const debounceRef = useRef<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)
  const loadSeqRef = useRef(0)
  const loadedFeaturesRef = useRef<StationFeature[]>([])
  const coverageBoundsRef = useRef<MapBounds | null>(null)
  const coverageTruncatedRef = useRef(false)
  const lastLoadedZoomRef = useRef<number | null>(null)
  const pendingForceLoadRef = useRef(false)
  const userMovedMapRef = useRef(false)
  const lastCenteredUserRef = useRef<{ lat: number; lon: number } | null>(null)

  const [mapReady, setMapReady] = useState(false)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [stationCount, setStationCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [mapInitError, setMapInitError] = useState<string | null>(null)
  const [overlayMode, setOverlayMode] = useState<'map' | 'route' | 'charge' | 'none'>('none')

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
  const routeDataRef = useRef(routeData)
  const routeChargePlanDataRef = useRef(routeChargePlanData)
  const chargePlanDataRef = useRef(chargePlanData)
  const selectedPlannedStopOrderRef = useRef(selectedPlannedStopOrder)
  const onPlannedStopSelectRef = useRef(onPlannedStopSelect)
  const tripUserLocationRef = useRef(tripUserLocation)
  const tripTrackingActiveRef = useRef(tripTrackingActive)

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
  routeDataRef.current = routeData
  routeChargePlanDataRef.current = routeChargePlanData
  chargePlanDataRef.current = chargePlanData
  selectedPlannedStopOrderRef.current = selectedPlannedStopOrder
  onPlannedStopSelectRef.current = onPlannedStopSelect
  tripUserLocationRef.current = tripUserLocation
  tripTrackingActiveRef.current = tripTrackingActive

  const resolveRouteChargingStop = useCallback((order: number): RouteChargingStop | null => {
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
  }, [])

  const openStationInfoWindow = useCallback(
    (lat: number, lon: number, properties: Record<string, unknown>) => {
      const map = mapRef.current
      const infoWindow = infoWindowRef.current
      if (!map || !infoWindow) {
        return
      }
      infoWindow.setContent(stationPopupHtml(properties, { lat, lon }))
      infoWindow.setPosition({ lat, lng: lon })
      infoWindow.open({ map })
    },
    [],
  )

  const paintBrowseStations = useCallback(
    (map: any, gm: GoogleMapsApi, features: StationFeature[]) => {
      clearMapObjects(browseMarkersRef.current)
      const visibleBounds = boundsFromGoogleMap(map)
      if (!visibleBounds) {
        return
      }
      const hasOverlay = Boolean(routeDataRef.current || chargePlanDataRef.current)
      const toRender = featuresForViewport(features, visibleBounds, VIEWPORT_RENDER_PADDING)
      const zoom = Number(map.getZoom?.() ?? DEFAULT_ZOOM)
      const items = clusterStationsForZoom(toRender, zoom)

      for (const item of items) {
        if (item.kind === 'cluster') {
          const scale = item.count >= 100 ? 22 : item.count >= 25 ? 18 : 15
          const marker = new gm.Marker({
            map,
            position: { lat: item.lat, lng: item.lon },
            zIndex: 10,
            label: {
              text: String(item.count),
              color: '#ffffff',
              fontSize: '12px',
              fontWeight: '700',
            },
            icon: {
              path: gm.SymbolPath.CIRCLE,
              scale,
              fillColor: '#0d7ea6',
              fillOpacity: 0.92,
              strokeColor: '#ffffff',
              strokeWeight: 2,
            },
          })
          marker.addListener('click', () => {
            const bounds = new gm.LatLngBounds()
            bounds.extend({ lat: item.bounds.south, lng: item.bounds.west })
            bounds.extend({ lat: item.bounds.north, lng: item.bounds.east })
            if (
              Math.abs(item.bounds.north - item.bounds.south) < 1e-4 &&
              Math.abs(item.bounds.east - item.bounds.west) < 1e-4
            ) {
              map.panTo({ lat: item.lat, lng: item.lon })
              map.setZoom(Math.min(zoom + 3, 16))
            } else {
              map.fitBounds(bounds, getMapUiPadding())
            }
          })
          browseMarkersRef.current.push(marker)
        } else {
          const props = (item.feature.properties ?? {}) as Record<string, unknown>
          const color = stationMarkerColor(props)
          const marker = new gm.Marker({
            map,
            position: { lat: item.lat, lng: item.lon },
            zIndex: 20,
            title: String(props.site_name ?? props.operator ?? 'Cargador'),
            icon: {
              path: gm.SymbolPath.CIRCLE,
              scale: hasOverlay ? 6 : 7.5,
              fillColor: color,
              fillOpacity: hasOverlay ? 0.65 : 0.95,
              strokeColor: '#ffffff',
              strokeWeight: 2,
            },
          })
          marker.addListener('click', () => {
            openStationInfoWindow(item.lat, item.lon, props)
          })
          browseMarkersRef.current.push(marker)
        }
      }

      if (!hasOverlay) {
        setStationCount(countFeaturesInBounds(features, visibleBounds))
        setLoadState(features.length > 0 ? 'ready' : 'idle')
        setOverlayMode('map')
      }
    },
    [openStationInfoWindow],
  )

  const paintOverlayStations = useCallback(
    (
      map: any,
      gm: GoogleMapsApi,
      features: StationFeature[],
      mode: 'route' | 'charge',
      keepBrowse: boolean,
    ) => {
      if (!keepBrowse) {
        clearMapObjects(browseMarkersRef.current)
      }
      clearMapObjects(overlayMarkersRef.current)
      const selectedOrder = selectedPlannedStopOrderRef.current

      for (const feature of features) {
        const [lon, lat] = feature.geometry.coordinates
        const props = (feature.properties ?? {}) as Record<string, unknown>
        const rawOrder = props.planned_stop_order
        const isPlanned = rawOrder !== null && rawOrder !== undefined && !Number.isNaN(Number(rawOrder))
        const orderNum = isPlanned ? Number(rawOrder) : null
        const isSelected = orderNum != null && selectedOrder != null && orderNum === selectedOrder
        const color = stationMarkerColor(props, selectedOrder)

        const marker = new gm.Marker({
          map,
          position: { lat, lng: lon },
          zIndex: isSelected ? 90 : isPlanned ? 80 : 50,
          title: String(props.site_name ?? props.operator ?? 'Cargador'),
          label: isPlanned
            ? {
                text: String(orderNum),
                color: '#ffffff',
                fontSize: '12px',
                fontWeight: '700',
              }
            : undefined,
          icon: {
            path: gm.SymbolPath.CIRCLE,
            scale: isPlanned ? (isSelected ? 15 : 13) : 8.5,
            fillColor: color,
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: isSelected ? 3 : 2,
          },
        })

        marker.addListener('click', () => {
          if (orderNum != null) {
            const stop = resolveRouteChargingStop(orderNum)
            if (stop) {
              infoWindowRef.current?.close()
              onPlannedStopSelectRef.current?.(stop)
              return
            }
          }
          openStationInfoWindow(lat, lon, props)
        })
        overlayMarkersRef.current.push(marker)
      }

      setStationCount(features.length)
      setHasMore(false)
      setLoadState(features.length > 0 ? 'ready' : 'idle')
      setOverlayMode(mode)
    },
    [openStationInfoWindow, resolveRouteChargingStop],
  )

  const clearRouteVisuals = useCallback(() => {
    clearMapObjects(routeLinesRef.current)
    clearMapObjects(routeEndpointsRef.current)
    if (rangeCircleRef.current) {
      rangeCircleRef.current.setMap(null)
      rangeCircleRef.current = null
    }
  }, [])

  const paintRouteLinesAndEndpoints = useCallback(
    (
      map: any,
      gm: GoogleMapsApi,
      activeGeometry: RouteLineGeometry | null,
      alternateGeometries: RouteLineGeometry[],
      origin: { lat: number; lon: number },
      destination: { lat: number; lon: number } | null,
      reachKm: number | null,
      fallbackPoints?: Array<{ lat: number; lon: number }>,
    ) => {
      clearRouteVisuals()

      for (const alt of alternateGeometries) {
        const line = new gm.Polyline({
          map,
          path: toLatLngPath(alt),
          strokeColor: '#64748b',
          strokeOpacity: 0.55,
          strokeWeight: 4,
          zIndex: 5,
        })
        routeLinesRef.current.push(line)
      }

      if (activeGeometry) {
        const path = toLatLngPath(activeGeometry)
        const casing = new gm.Polyline({
          map,
          path,
          strokeColor: '#ffffff',
          strokeOpacity: 0.92,
          strokeWeight: 8,
          zIndex: 10,
        })
        const mainLine = new gm.Polyline({
          map,
          path,
          strokeColor: '#2563eb',
          strokeOpacity: 0.95,
          strokeWeight: 5,
          zIndex: 11,
        })
        routeLinesRef.current.push(casing, mainLine)

        const bounds = new gm.LatLngBounds()
        for (const geom of [activeGeometry, ...alternateGeometries]) {
          for (const [lon, lat] of geom.coordinates) {
            bounds.extend({ lat, lng: lon })
          }
        }
        map.fitBounds(bounds, getMapUiPadding())
      } else if (fallbackPoints && fallbackPoints.length > 0) {
        const bounds = new gm.LatLngBounds()
        for (const pt of fallbackPoints) {
          bounds.extend({ lat: pt.lat, lng: pt.lon })
        }
        map.fitBounds(bounds, getMapUiPadding())
      }

      const originMarker = new gm.Marker({
        map,
        position: { lat: origin.lat, lng: origin.lon },
        zIndex: 60,
        title: 'Origen',
        label: { text: 'A', color: '#ffffff', fontSize: '11px', fontWeight: '700' },
        icon: {
          path: gm.SymbolPath.CIRCLE,
          scale: 11,
          fillColor: '#16a34a',
          fillOpacity: 1,
          strokeColor: '#ffffff',
          strokeWeight: 2,
        },
      })
      routeEndpointsRef.current.push(originMarker)

      if (destination) {
        const destMarker = new gm.Marker({
          map,
          position: { lat: destination.lat, lng: destination.lon },
          zIndex: 60,
          title: 'Destino',
          label: { text: 'B', color: '#ffffff', fontSize: '11px', fontWeight: '700' },
          icon: {
            path: gm.SymbolPath.CIRCLE,
            scale: 11,
            fillColor: '#dc2626',
            fillOpacity: 1,
            strokeColor: '#ffffff',
            strokeWeight: 2,
          },
        })
        routeEndpointsRef.current.push(destMarker)
      }

      if (reachKm && reachKm > 0) {
        rangeCircleRef.current = new gm.Circle({
          map,
          center: { lat: origin.lat, lng: origin.lon },
          radius: reachKm * 1000,
          strokeColor: '#2563eb',
          strokeOpacity: 0.45,
          strokeWeight: 1.5,
          fillColor: '#2563eb',
          fillOpacity: 0.06,
          clickable: false,
          zIndex: 2,
        })
      }
    },
    [clearRouteVisuals],
  )

  const applyRouteOverlay = useCallback(
    (
      map: any,
      gm: GoogleMapsApi,
      data: AlongRouteResponse,
      chargePlan: ChargingPlanResponse | null | undefined,
      keepBrowse: boolean,
    ) => {
      const variantGeometries = routeVariantGeometriesFromResponse(data)
      const preference = data.route_preference ?? chargePlan?.route_preference ?? 'fastest'
      const activeGeom = activeRouteGeometry(preference, variantGeometries, data.route_geometry)
      const alternateGeoms = inactiveRouteGeometries(preference, variantGeometries)
      paintRouteLinesAndEndpoints(
        map,
        gm,
        activeGeom,
        alternateGeoms,
        data.origin,
        data.destination,
        chargePlan ? chargePlan.charging_reach_km : null,
      )
      const routeFeatures = alongRouteToFeatures(data.results)
      const chargePlanFeatures =
        chargePlan && routeChargingStops(chargePlan).length > 0
          ? chargingPlanRouteMapFeatures(chargePlan)
          : []
      const overlayFeatures = chargePlanFeatures.length > 0 ? chargePlanFeatures : routeFeatures
      paintOverlayStations(map, gm, overlayFeatures, 'route', keepBrowse)
    },
    [paintOverlayStations, paintRouteLinesAndEndpoints],
  )

  const applyChargePlanOverlay = useCallback(
    (map: any, gm: GoogleMapsApi, data: ChargingPlanResponse, keepBrowse: boolean) => {
      const variantGeometries = routeVariantGeometriesFromResponse(data)
      const preference = data.route_preference ?? 'fastest'
      const activeGeom = activeRouteGeometry(
        preference,
        variantGeometries,
        data.route_geometry ?? data.preview_route_geometry,
      )
      const alternateGeoms = inactiveRouteGeometries(preference, variantGeometries)
      paintRouteLinesAndEndpoints(
        map,
        gm,
        activeGeom,
        alternateGeoms,
        data.origin,
        data.destination,
        data.charging_reach_km,
        routeMapFitPoints(data),
      )
      const features = chargingPlanRouteMapFeatures(data)
      paintOverlayStations(map, gm, features, 'charge', keepBrowse)
    },
    [paintOverlayStations, paintRouteLinesAndEndpoints],
  )

  const loadVisibleStationsRef = useRef<(map: any, gm: GoogleMapsApi, force?: boolean) => void>(() => undefined)
  const scheduleLoadRef = useRef<(map: any, gm: GoogleMapsApi, force?: boolean) => void>(() => undefined)

  const loadVisibleStations = useCallback(
    async (map: any, gm: GoogleMapsApi, force = false) => {
      if (!loadStationsRef.current) {
        return
      }
      const visibleBounds = boundsFromGoogleMap(map)
      if (!visibleBounds) {
        return
      }
      const zoom = Number(map.getZoom?.() ?? DEFAULT_ZOOM)

      if (
        !force &&
        loadedFeaturesRef.current.length > 0 &&
        !shouldFetchStations(
          coverageBoundsRef.current,
          visibleBounds,
          lastLoadedZoomRef.current,
          zoom,
          coverageTruncatedRef.current,
        )
      ) {
        if (!coverageTruncatedRef.current) {
          lastLoadedZoomRef.current = zoom
        }
        paintBrowseStations(map, gm, loadedFeaturesRef.current)
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

        const truncated = payload.pagination.has_more
        coverageBoundsRef.current = fetchBounds
        coverageTruncatedRef.current = truncated
        lastLoadedZoomRef.current = zoom
        setHasMore(truncated)
        const merged = trimBrowseCache(extendStationFeatures(loadedFeaturesRef.current, payload.features))
        loadedFeaturesRef.current = merged
        paintBrowseStations(map, gm, merged)
        if (truncated && zoomedInPastTruncatedCoverage(zoom, Number(map.getZoom?.() ?? zoom))) {
          scheduleLoadRef.current(map, gm, true)
        }
      } catch (error) {
        if (controller.signal.aborted || loadSeq !== loadSeqRef.current) {
          return
        }
        setErrorMessage(error instanceof Error ? error.message : 'Error al cargar estaciones')
        setLoadState('error')
      }
    },
    [paintBrowseStations],
  )

  const scheduleLoad = useCallback((map: any, gm: GoogleMapsApi, force = false) => {
    if (force) {
      pendingForceLoadRef.current = true
    }
    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current)
    }
    debounceRef.current = window.setTimeout(() => {
      const forceLoad = pendingForceLoadRef.current
      pendingForceLoadRef.current = false
      void loadVisibleStationsRef.current(map, gm, forceLoad)
    }, LOAD_DEBOUNCE_MS)
  }, [])

  loadVisibleStationsRef.current = loadVisibleStations
  scheduleLoadRef.current = scheduleLoad

  const easeMapToUser = useCallback((map: any, point: { lat: number; lon: number }, force = false) => {
    if (!force && userMovedMapRef.current) {
      return
    }
    if (!force && !shouldRecenterMapOnUserMove(lastCenteredUserRef.current, point)) {
      return
    }
    lastCenteredUserRef.current = point
    map.panTo({ lat: point.lat, lng: point.lon })
    const currentZoom = Number(map.getZoom?.() ?? DEFAULT_ZOOM)
    if (currentZoom < MAP_FOLLOW_ZOOM) {
      map.setZoom(MAP_FOLLOW_ZOOM)
    }
  }, [])

  const handleCenterOnMeClick = useCallback(() => {
    const map = mapRef.current
    const point = tripUserLocationRef.current
    userMovedMapRef.current = false
    onCenterOnMeChange?.(true)
    if (!map || !point) {
      return
    }
    easeMapToUser(map, point, true)
  }, [easeMapToUser, onCenterOnMeChange])

  useEffect(() => {
    if (!onRegisterMapBounds) {
      return
    }
    onRegisterMapBounds(() => {
      const map = mapRef.current
      if (!map) {
        return null
      }
      return boundsFromGoogleMap(map)
    })
    return () => onRegisterMapBounds(null)
  }, [onRegisterMapBounds])

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return undefined
    }
    let cancelled = false

    void loadGoogleMapsApi()
      .then((gm) => {
        if (cancelled || !containerRef.current) {
          return
        }
        const map = new gm.Map(containerRef.current, {
          center: IBERIAN_CENTER,
          zoom: DEFAULT_ZOOM,
          mapTypeId: mapLayers?.detail ? 'terrain' : 'roadmap',
          streetViewControl: false,
          fullscreenControl: false,
          mapTypeControl: false,
          clickableIcons: false,
          gestureHandling: 'greedy',
        })
        gmRef.current = gm
        mapRef.current = map
        infoWindowRef.current = new gm.InfoWindow({ maxWidth: 290 })
        trafficLayerRef.current = new gm.TrafficLayer()

        map.addListener('idle', () => {
          if (loadStationsRef.current) {
            scheduleLoadRef.current(map, gm)
          }
        })
        map.addListener('dragstart', () => {
          if (tripTrackingActiveRef.current) {
            userMovedMapRef.current = true
          }
        })
        map.addListener('click', () => {
          infoWindowRef.current?.close()
          if (selectedPlannedStopOrderRef.current != null) {
            onPlannedStopSelectRef.current?.(null)
          }
        })

        setMapReady(true)
      })
      .catch((error) => {
        if (cancelled) {
          return
        }
        console.error('No se pudo cargar Google Maps JS', error)
        setMapInitError(
          error instanceof Error ? error.message : 'No se pudo cargar Google Maps JavaScript API',
        )
      })

    return () => {
      cancelled = true
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current)
      }
      abortRef.current?.abort()
      clearMapObjects(browseMarkersRef.current)
      clearMapObjects(overlayMarkersRef.current)
      clearRouteVisuals()
      clearMapObjects(userMarkersRef.current)
      placePinRef.current?.setMap?.(null)
      placePinRef.current = null
      trafficLayerRef.current?.setMap?.(null)
      trafficLayerRef.current = null
      infoWindowRef.current?.close?.()
      infoWindowRef.current = null
      if (mapRef.current && gmRef.current) {
        gmRef.current.event.clearInstanceListeners(mapRef.current)
      }
      mapRef.current = null
      gmRef.current = null
      setMapReady(false)
    }
  }, [clearRouteVisuals])

  // Capas nativas de Google Maps: Relieve (terrain) + Tráfico en vivo (TrafficLayer).
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map) {
      return
    }
    map.setMapTypeId(mapLayers?.detail ? 'terrain' : 'roadmap')
    trafficLayerRef.current?.setMap(mapLayers?.traffic ? map : null)
  }, [mapReady, mapLayers])

  // Ruta, plan de carga y estaciones superpuestas.
  useEffect(() => {
    const map = mapRef.current
    const gm = gmRef.current
    if (!mapReady || !map || !gm) {
      return
    }
    const keepBrowse = loadStations
    if (keepBrowse) {
      if (loadedFeaturesRef.current.length > 0) {
        paintBrowseStations(map, gm, loadedFeaturesRef.current)
      } else {
        scheduleLoad(map, gm, true)
      }
    }
    if (routeData) {
      applyRouteOverlay(map, gm, routeData, routeChargePlanData, keepBrowse)
      return
    }
    if (chargePlanData) {
      applyChargePlanOverlay(map, gm, chargePlanData, keepBrowse)
      return
    }
    clearRouteVisuals()
    clearMapObjects(overlayMarkersRef.current)
    if (!keepBrowse) {
      clearMapObjects(browseMarkersRef.current)
      setOverlayMode('none')
      setStationCount(0)
      setHasMore(false)
      setLoadState('idle')
    } else if (loadedFeaturesRef.current.length > 0) {
      paintBrowseStations(map, gm, loadedFeaturesRef.current)
    }
  }, [
    mapReady,
    loadStations,
    routeData,
    routeChargePlanData,
    chargePlanData,
    selectedPlannedStopOrder,
    applyRouteOverlay,
    applyChargePlanOverlay,
    clearRouteVisuals,
    paintBrowseStations,
    scheduleLoad,
  ])

  const connectorTypesKey = connectorTypes.join('|')

  // Recarga cuando cambian filtros de estación.
  useEffect(() => {
    const map = mapRef.current
    const gm = gmRef.current
    if (!mapReady || !map || !gm || !loadStations) {
      return
    }
    loadedFeaturesRef.current = []
    coverageBoundsRef.current = null
    coverageTruncatedRef.current = false
    lastLoadedZoomRef.current = null
    scheduleLoad(map, gm, true)
  }, [
    mapReady,
    minKw,
    maxKw,
    publicOpenOnly,
    excludeParking,
    adHocOnly,
    availableOnly,
    maxPriceEurKwh,
    connectorTypesKey,
    loadStations,
    scheduleLoad,
  ])

  // Foco en una estación concreta.
  useEffect(() => {
    const map = mapRef.current
    if (!mapReady || !map || !focusStation) {
      return
    }
    const plan = chargePlanData ?? routeChargePlanData
    let isPlannedStop = false
    if (plan) {
      const fromPlanned = plan.planned_stops?.some((stop) => stop.station.id === focusStation.id)
      const fromRoute = routeChargingStops(plan).some((stop) => stop.station.id === focusStation.id)
      isPlannedStop = Boolean(fromPlanned || fromRoute)
    }
    const { lat, lon } = focusStation.location
    map.panTo({ lat, lng: lon })
    map.setZoom(MAP_FOCUS_ZOOM)
    if (isPlannedStop) {
      infoWindowRef.current?.close()
      return
    }
    openStationInfoWindow(lat, lon, {
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
    })
  }, [mapReady, focusStation, chargePlanData, routeChargePlanData, openStationInfoWindow])

  // Foco en ciudad / lugar buscado.
  useEffect(() => {
    const map = mapRef.current
    const gm = gmRef.current
    if (!mapReady || !map || !gm || !loadStations) {
      return
    }
    if (placePinRef.current) {
      placePinRef.current.setMap(null)
      placePinRef.current = null
    }
    if (!mapFocusPlace) {
      return
    }
    placePinRef.current = new gm.Marker({
      map,
      position: { lat: mapFocusPlace.lat, lng: mapFocusPlace.lon },
      title: mapFocusPlace.label,
      zIndex: 70,
    })
    map.panTo({ lat: mapFocusPlace.lat, lng: mapFocusPlace.lon })
    map.setZoom(Math.max(Number(map.getZoom?.() ?? DEFAULT_ZOOM), MAP_FOCUS_ZOOM))
    loadedFeaturesRef.current = []
    coverageBoundsRef.current = null
    coverageTruncatedRef.current = false
    lastLoadedZoomRef.current = null
    scheduleLoad(map, gm, true)
  }, [mapReady, mapFocusPlace, loadStations, scheduleLoad])

  // Posición GPS del usuario.
  useEffect(() => {
    if (!tripTrackingActive && !liveActive) {
      userMovedMapRef.current = false
      lastCenteredUserRef.current = null
    }
  }, [tripTrackingActive, liveActive])

  useEffect(() => {
    const map = mapRef.current
    const gm = gmRef.current
    if (!mapReady || !map || !gm) {
      return
    }
    clearMapObjects(userMarkersRef.current)
    const tracking = tripTrackingActive || liveActive
    if (!tracking || !tripUserLocation) {
      return
    }
    const dot = new gm.Marker({
      map,
      position: { lat: tripUserLocation.lat, lng: tripUserLocation.lon },
      zIndex: 100,
      title: 'Tu posición',
      icon: {
        path: gm.SymbolPath.CIRCLE,
        scale: 8,
        fillColor: '#2563eb',
        fillOpacity: 1,
        strokeColor: '#ffffff',
        strokeWeight: 3,
      },
    })
    userMarkersRef.current.push(dot)
    if (tripUserLocation.accuracyM && tripUserLocation.accuracyM > 15) {
      const accuracyRing = new gm.Circle({
        map,
        center: { lat: tripUserLocation.lat, lng: tripUserLocation.lon },
        radius: Math.min(tripUserLocation.accuracyM, 2000),
        strokeColor: '#2563eb',
        strokeOpacity: 0.35,
        strokeWeight: 1,
        fillColor: '#2563eb',
        fillOpacity: 0.12,
        clickable: false,
        zIndex: 99,
      })
      userMarkersRef.current.push(accuracyRing)
    }
    if (centerOnMe || liveActive) {
      easeMapToUser(map, tripUserLocation)
    }
  }, [mapReady, tripTrackingActive, liveActive, tripUserLocation, centerOnMe, easeMapToUser])

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
      <div ref={containerRef} className={className ?? 'map-view'} aria-label="Mapa peninsular (Google Maps)" />
      {mapInitError && (
        <div className="map-init-error" role="alert">
          <p className="map-init-error__title">No se puede mostrar Google Maps</p>
          <p>{mapInitError}</p>
        </div>
      )}
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
