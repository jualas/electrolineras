import { useCallback, useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'

import { fetchStationsGeoJSON } from '../api/stations'
import type { MapBounds } from '../api/types'
import type { ThemeMode } from '../hooks/useTheme'
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

type MapViewProps = {
  className?: string
  theme: ThemeMode
  loadStations?: boolean
  minKw?: number
  maxKw?: number
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

      setStationData(map, {
        type: 'FeatureCollection',
        features: payload.features,
      })
      setStationCount(payload.features.length)
      setHasMore(payload.pagination.has_more)
      setLoadState('ready')
    } catch (error) {
      if (controller.signal.aborted) {
        return
      }
      const message = error instanceof Error ? error.message : 'Error al cargar estaciones'
      setErrorMessage(message)
      setLoadState('error')
    }
  }, [loadStations, minKw, maxKw])

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
      scheduleLoad(map)
    })

    map.on('moveend', () => scheduleLoad(map))

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
        .setHTML(stationPopupHtml(properties))
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
  }, [scheduleLoad])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) {
      return
    }
    updateStationLayerTheme(map, theme)
  }, [theme])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !map.isStyleLoaded()) {
      return
    }
    if (loadStations) {
      scheduleLoad(map)
    } else {
      setStationData(map, { type: 'FeatureCollection', features: [] })
      setStationCount(0)
      setHasMore(false)
      setLoadState('idle')
    }
  }, [loadStations, minKw, maxKw, scheduleLoad])

  return (
    <div className="map-shell">
      <div ref={containerRef} className={className ?? 'map-view'} aria-label="Mapa peninsular" />
      {loadStations && (
        <div className="map-overlay" aria-live="polite">
          {loadState === 'loading' && <span className="map-badge">Cargando estaciones…</span>}
          {loadState === 'ready' && (
            <span className="map-badge map-badge--ok">
              {stationCount} en vista{hasMore ? ' (límite)' : ''}
            </span>
          )}
          {loadState === 'error' && (
            <span className="map-badge map-badge--error" title={errorMessage ?? undefined}>
              Error de datos
            </span>
          )}
        </div>
      )}
    </div>
  )
}
