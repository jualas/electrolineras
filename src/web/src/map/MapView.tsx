import { useCallback, useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'

import { chargingPlanToFeatures } from '../api/chargingPlanFeature'
import { alongRouteToFeatures } from '../api/route'
import { fetchStationsGeoJSON } from '../api/stations'
import type { AlongRouteResponse, ChargingPlanResponse, GeocodeResult, MapBounds, Station } from '../api/types'
import type { ThemeMode } from '../hooks/useTheme'
import {
  clearCityOverlay,
  ensureCityLayers,
  setCityReference,
  setCityRadiusCircle,
  updateCityLayerTheme,
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
const MAP_FOCUS_ZOOM = 14

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
  theme: ThemeMode
  loadStations?: boolean
  minKw?: number
  maxKw?: number
  publicOpenOnly?: boolean
  routeData?: AlongRouteResponse | null
  routeSearching?: boolean
  routeChargePlanData?: ChargingPlanResponse | null
  chargePlanData?: ChargingPlanResponse | null
  chargePlanSearching?: boolean
  focusStation?: Station | null
  mapFocusPlace?: GeocodeResult | null
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
  publicOpenOnly = false,
  routeData = null,
  routeSearching = false,
  routeChargePlanData = null,
  chargePlanData = null,
  chargePlanSearching = false,
  focusStation = null,
  mapFocusPlace = null,
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
  const [overlayMode, setOverlayMode] = useState<'map' | 'route' | 'charge' | 'none'>('none')

  const applyRouteOverlay = useCallback((map: maplibregl.Map, data: AlongRouteResponse, chargePlan?: ChargingPlanResponse | null) => {
    ensureRouteLayers(map, theme)
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
      const mapPoints = [
        data.origin,
        ...data.origin_stops.map((stop) => stop.station.location),
        ...data.stops.map((stop) => stop.station.location),
      ]
      fitMapToPoints(map, mapPoints)
    }
    setRouteEndpoints(map, data.origin, data.destination)
    setRangeCircle(map, data.origin, data.charging_reach_km)
    const features = chargingPlanToFeatures(data.stops, data.origin_stops, data.planned_stops ?? [])
    setStationData(map, {
      type: 'FeatureCollection',
      features,
    })
    setStationCount(features.length)
    setHasMore(false)
    setLoadState(features.length > 0 ? 'ready' : 'idle')
    setOverlayMode('charge')
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
        {
          bbox: boundsFromMap(map),
          limit,
          minKw,
          maxKw,
          publicOpenOnly,
        },
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
  }, [clearSearchOverlays, loadStations, minKw, maxKw, publicOpenOnly, mapFocusPlace, applyMapPlacePin])

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
    minKw,
    maxKw,
    scheduleLoad,
    applyRouteOverlay,
    applyChargePlanOverlay,
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
    if (!map || !loadStations) {
      return
    }
    if (!mapFocusPlace) {
      clearCityOverlay(map)
      return
    }
    focusMapOnPlace(map, mapFocusPlace)
  }, [mapFocusPlace, loadStations, focusMapOnPlace])

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
