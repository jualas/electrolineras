import { useCallback, useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'

import { chargingPlanToFeatures } from '../api/chargingPlanFeature'
import { nearbyToFeatures } from '../api/nearbyFeature'
import { alongRouteToFeatures } from '../api/route'
import { fetchStationsGeoJSON } from '../api/stations'
import type { AlongRouteResponse, ChargingPlanResponse, GeocodeResult, MapBounds, NearbyResponse, Station } from '../api/types'
import type { ThemeMode } from '../hooks/useTheme'
import {
  clearCityOverlay,
  ensureCityLayers,
  fitMapToBbox,
  fitMapToCityReference,
  setCityReference,
  setCityRadiusCircle,
  updateCityLayerTheme,
} from './cityLayers'
import {
  clearRouteOverlay,
  ensureRouteLayers,
  fitMapToRoute,
  fitMapToPoints,
  setRouteEndpoints,
  setRouteLine,
  setRangeCircle,
  updateRouteLayerTheme,
} from './routeLayers'
import {
  CLUSTER_LAYER_ID,
  ensureStationLayers,
  POINT_LAYER_ID,
  setStationData,
  stationPopupHtml,
  STATIONS_SOURCE_ID,
  updateStationLayerTheme,
} from './stationLayers'

const IBERIAN_CENTER: [number, number] = [-4.5, 40.2]
const DEFAULT_ZOOM = 5.8
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'
const LOAD_DEBOUNCE_MS = 350

type MapBoundsGetter = () => MapBounds | null

type MapViewProps = {
  className?: string
  theme: ThemeMode
  loadStations?: boolean
  minKw?: number
  maxKw?: number
  routeData?: AlongRouteResponse | null
  routeSearching?: boolean
  routeChargePlanData?: ChargingPlanResponse | null
  chargePlanData?: ChargingPlanResponse | null
  chargePlanSearching?: boolean
  cityData?: NearbyResponse | null
  citySearching?: boolean
  focusStation?: Station | null
  mapFocusPlace?: GeocodeResult | null
  cityPickMode?: boolean
  onCityMapPick?: (lat: number, lon: number) => void
  onRegisterMapBounds?: (getter: MapBoundsGetter | null) => void
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

export function MapView({
  className,
  theme,
  loadStations = true,
  minKw,
  maxKw,
  routeData = null,
  routeSearching = false,
  routeChargePlanData = null,
  chargePlanData = null,
  chargePlanSearching = false,
  cityData = null,
  citySearching = false,
  focusStation = null,
  mapFocusPlace = null,
  cityPickMode = false,
  onCityMapPick,
  onRegisterMapBounds,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)
  const popupRef = useRef<maplibregl.Popup | null>(null)
  const debounceRef = useRef<number | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [stationCount, setStationCount] = useState(0)
  const [hasMore, setHasMore] = useState(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [overlayMode, setOverlayMode] = useState<'map' | 'route' | 'charge' | 'city' | 'none'>('none')

  const applyRouteOverlay = useCallback((map: maplibregl.Map, data: AlongRouteResponse, chargePlan?: ChargingPlanResponse | null) => {
    ensureRouteLayers(map, theme)
    clearCityOverlay(map)
    if (data.route_geometry) {
      setRouteLine(map, data.route_geometry)
      fitMapToRoute(map, data.route_geometry)
    }
    setRouteEndpoints(map, data.origin, data.destination)
    if (chargePlan) {
      setRangeCircle(map, chargePlan.origin, chargePlan.charging_reach_km)
    } else {
      setRangeCircle(map, null, null)
    }
    const routeFeatures = alongRouteToFeatures(data.results)
    const originFeatures = chargePlan
      ? chargingPlanToFeatures([], chargePlan.origin_stops).filter(
          (feature) => !routeFeatures.some((routeFeature) => routeFeature.id === feature.id),
        )
      : []
    setStationData(map, {
      type: 'FeatureCollection',
      features: [...originFeatures, ...routeFeatures],
    })
    setStationCount(routeFeatures.length + originFeatures.length)
    setHasMore(false)
    setLoadState(routeFeatures.length + originFeatures.length > 0 ? 'ready' : 'idle')
    setOverlayMode('route')
  }, [theme])

  const applyChargePlanOverlay = useCallback((map: maplibregl.Map, data: ChargingPlanResponse) => {
    ensureRouteLayers(map, theme)
    clearCityOverlay(map)
    const routeGeometry = data.route_geometry ?? data.preview_route_geometry
    if (routeGeometry) {
      setRouteLine(map, routeGeometry)
      fitMapToRoute(map, routeGeometry)
    } else {
      setRouteLine(map, null)
      const mapPoints = [
        data.origin,
        ...data.origin_stops.map((stop) => stop.station.location),
        ...data.stops.map((stop) => stop.station.location),
      ]
      fitMapToPoints(map, mapPoints)
    }
    setRouteEndpoints(map, data.origin, data.destination)
    setRangeCircle(map, data.origin, data.charging_reach_km)
    const features = chargingPlanToFeatures(data.stops, data.origin_stops)
    setStationData(map, {
      type: 'FeatureCollection',
      features,
    })
    setStationCount(features.length)
    setHasMore(false)
    setLoadState(features.length > 0 ? 'ready' : 'idle')
    setOverlayMode('charge')
  }, [theme])

  const applyCityOverlay = useCallback((map: maplibregl.Map, data: NearbyResponse) => {
    ensureCityLayers(map, theme)
    clearRouteOverlay(map)
    setCityReference(map, data.reference)
    if (data.bbox && data.bbox.length === 4) {
      setCityRadiusCircle(map, null, null)
      fitMapToBbox(map, data.bbox[0], data.bbox[1], data.bbox[2], data.bbox[3])
    } else {
      setCityRadiusCircle(map, data.reference, data.radius_m)
      fitMapToCityReference(map, data.reference, data.radius_m)
    }
    setStationData(map, {
      type: 'FeatureCollection',
      features: nearbyToFeatures(data.results),
    })
    setStationCount(data.results.length)
    setHasMore(false)
    setLoadState(data.results.length > 0 ? 'ready' : 'idle')
    setOverlayMode('city')
  }, [theme])

  const clearSearchOverlays = useCallback((map: maplibregl.Map) => {
    clearRouteOverlay(map)
    clearCityOverlay(map)
    setOverlayMode('none')
  }, [])

  const applyMapPlacePin = useCallback(
    (map: maplibregl.Map, place: GeocodeResult | null) => {
      if (!place) {
        return
      }
      ensureCityLayers(map, theme)
      setCityReference(map, place)
      setCityRadiusCircle(map, null, null)
    },
    [theme],
  )

  const loadVisibleStations = useCallback(async (map: maplibregl.Map) => {
    if (!loadStations) {
      return
    }

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoadState('loading')
    setErrorMessage(null)

    try {
      const zoom = map.getZoom()
      const limit = zoom < 7 ? 3000 : zoom < 10 ? 5000 : 4000
      const payload = await fetchStationsGeoJSON(
        { bbox: boundsFromMap(map), limit, minKw, maxKw },
        { signal: controller.signal },
      )

      if (controller.signal.aborted) {
        return
      }

      clearSearchOverlays(map)
      applyMapPlacePin(map, mapFocusPlace)
      setStationData(map, {
        type: 'FeatureCollection',
        features: payload.features,
      })
      setStationCount(payload.features.length)
      setHasMore(payload.pagination.has_more)
      setLoadState('ready')
      setOverlayMode('map')
    } catch (error) {
      if (controller.signal.aborted) {
        return
      }
      const message = error instanceof Error ? error.message : 'Error al cargar estaciones'
      setErrorMessage(message)
      setLoadState('error')
    }
  }, [clearSearchOverlays, loadStations, minKw, maxKw, mapFocusPlace, applyMapPlacePin])

  const scheduleLoad = useCallback(
    (map: maplibregl.Map) => {
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current)
      }
      debounceRef.current = window.setTimeout(() => {
        loadVisibleStations(map)
      }, LOAD_DEBOUNCE_MS)
    },
    [loadVisibleStations],
  )

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

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    map.addControl(new maplibregl.AttributionControl({ compact: true }), 'bottom-right')
    popupRef.current = new maplibregl.Popup({
      closeButton: true,
      closeOnClick: true,
      maxWidth: '280px',
      className: 'station-popup-container',
    })

    map.on('load', () => {
      ensureStationLayers(map, theme)
      ensureRouteLayers(map, theme)
      ensureCityLayers(map, theme)
      if (loadStations) {
        scheduleLoad(map)
      }
    })

    map.on('moveend', () => {
      if (loadStations) {
        scheduleLoad(map)
      }
    })

    map.on('click', CLUSTER_LAYER_ID, (event) => {
      const feature = event.features?.[0]
      if (!feature) {
        return
      }
      const clusterId = feature.properties?.cluster_id
      const source = map.getSource(STATIONS_SOURCE_ID) as maplibregl.GeoJSONSource
      if (clusterId === undefined) {
        return
      }
      source
        .getClusterExpansionZoom(clusterId)
        .then((zoom) => {
          const coordinates = (feature.geometry as { coordinates: [number, number] }).coordinates.slice() as [
            number,
            number,
          ]
          map.easeTo({ center: coordinates, zoom })
        })
        .catch(() => undefined)
    })

    map.on('click', POINT_LAYER_ID, (event) => {
      const feature = event.features?.[0]
      if (!feature || feature.geometry.type !== 'Point') {
        return
      }
      const coordinates = feature.geometry.coordinates.slice() as [number, number]
      const properties = feature.properties ?? {}
      popupRef.current
        ?.setLngLat(coordinates)
        .setHTML(
          stationPopupHtml(properties, {
            lat: coordinates[1],
            lon: coordinates[0],
          }),
        )
        .addTo(map)
    })

    map.on('mouseenter', CLUSTER_LAYER_ID, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', CLUSTER_LAYER_ID, () => {
      map.getCanvas().style.cursor = ''
    })
    map.on('mouseenter', POINT_LAYER_ID, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', POINT_LAYER_ID, () => {
      map.getCanvas().style.cursor = ''
    })

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
  }, [scheduleLoad, loadStations, theme])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) {
      return
    }
    updateStationLayerTheme(map, theme)
    updateRouteLayerTheme(map, theme)
    updateCityLayerTheme(map, theme)
  }, [theme])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) {
      return
    }
    if (loadStations) {
      scheduleLoad(map)
    } else if (routeData) {
      applyRouteOverlay(map, routeData, routeChargePlanData)
    } else if (chargePlanData) {
      applyChargePlanOverlay(map, chargePlanData)
    } else if (cityData) {
      applyCityOverlay(map, cityData)
    } else {
      clearSearchOverlays(map)
      setStationData(map, { type: 'FeatureCollection', features: [] })
      setStationCount(0)
      setHasMore(false)
      setLoadState('idle')
    }
  }, [
    loadStations,
    routeData,
    routeChargePlanData,
    chargePlanData,
    cityData,
    minKw,
    maxKw,
    scheduleLoad,
    applyRouteOverlay,
    applyChargePlanOverlay,
    applyCityOverlay,
    clearSearchOverlays,
  ])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded() || !focusStation) {
      return
    }
    const { lat, lon } = focusStation.location
    map.flyTo({ center: [lon, lat], zoom: 14, duration: 700 })
    popupRef.current
      ?.setLngLat([lon, lat])
      .setHTML(
        stationPopupHtml(
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
          { lat: lat, lon: lon },
        ),
      )
      .addTo(map)
  }, [focusStation])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded() || !loadStations) {
      return
    }
    if (!mapFocusPlace) {
      clearCityOverlay(map)
      return
    }
    applyMapPlacePin(map, mapFocusPlace)
    map.flyTo({
      center: [mapFocusPlace.lon, mapFocusPlace.lat],
      zoom: 12,
      duration: 800,
    })
  }, [mapFocusPlace, loadStations, applyMapPlacePin])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded() || !cityPickMode || !onCityMapPick) {
      return undefined
    }

    const handleMapClick = (event: maplibregl.MapMouseEvent) => {
      const stationHits = map.queryRenderedFeatures(event.point, {
        layers: [POINT_LAYER_ID, CLUSTER_LAYER_ID],
      })
      if (stationHits.length > 0) {
        return
      }
      onCityMapPick(event.lngLat.lat, event.lngLat.lng)
    }

    map.on('click', handleMapClick)
    map.getCanvas().style.cursor = 'crosshair'

    return () => {
      map.off('click', handleMapClick)
      map.getCanvas().style.cursor = ''
    }
  }, [cityPickMode, onCityMapPick])

  const showMapBadge =
    loadStations ||
    routeData !== null ||
    chargePlanData !== null ||
    cityData !== null ||
    routeSearching ||
    chargePlanSearching ||
    citySearching

  const badgeLabel =
    overlayMode === 'route'
      ? `${stationCount} en ruta`
      : overlayMode === 'charge'
        ? `${stationCount} paradas`
        : overlayMode === 'city'
          ? `${stationCount} cerca`
          : `${stationCount} en vista`

  return (
    <div className="map-shell">
      <div
        ref={containerRef}
        className={`${className ?? 'map-view'}${cityPickMode ? ' map-view--pick' : ''}`}
        aria-label="Mapa peninsular"
      />
      {showMapBadge && (
        <div className="map-overlay" aria-live="polite">
          {routeSearching && <span className="map-badge">Calculando ruta…</span>}
          {chargePlanSearching && !routeSearching && <span className="map-badge">Calculando plan…</span>}
          {citySearching && !routeSearching && !chargePlanSearching && (
            <span className="map-badge">Buscando cerca…</span>
          )}
          {!routeSearching &&
            !chargePlanSearching &&
            !citySearching &&
            loadState === 'loading' && <span className="map-badge">Cargando estaciones…</span>}
          {!routeSearching && !chargePlanSearching && !citySearching && loadState === 'ready' && (
            <span className="map-badge map-badge--ok">
              {badgeLabel}
              {overlayMode === 'map' && hasMore ? ' (límite)' : ''}
            </span>
          )}
          {!routeSearching && !chargePlanSearching && !citySearching && loadState === 'error' && (
            <span className="map-badge map-badge--error" title={errorMessage ?? undefined}>
              Error de datos
            </span>
          )}
        </div>
      )}
      {cityPickMode && <div className="map-pick-hint">Toca el mapa para marcar el punto</div>}
    </div>
  )
}
