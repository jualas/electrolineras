import type * as maplibregl from 'maplibre-gl'

export const TRAFFIC_SOURCE_ID = 'traffic-flow'
export const TRAFFIC_LAYER_ID = 'traffic-flow-layer'

const TOMTOM_API_KEY = import.meta.env.VITE_TOMTOM_API_KEY?.trim() ?? ''

export function trafficLayerAvailable(): boolean {
  return TOMTOM_API_KEY.length > 0
}

export function ensureTrafficLayer(map: maplibregl.Map): void {
  if (!trafficLayerAvailable()) {
    return
  }

  if (!map.getSource(TRAFFIC_SOURCE_ID)) {
    const tileUrl = `https://api.tomtom.com/traffic/map/4/tile/flow/relative/{z}/{x}/{y}.png?key=${TOMTOM_API_KEY}`
    map.addSource(TRAFFIC_SOURCE_ID, {
      type: 'raster',
      tiles: [tileUrl],
      tileSize: 256,
      maxzoom: 22,
    })
  }

  if (!map.getLayer(TRAFFIC_LAYER_ID)) {
    const beforeId = map.getStyle()?.layers?.find((layer) => layer.id.startsWith('stations-'))?.id
    map.addLayer(
      {
        id: TRAFFIC_LAYER_ID,
        type: 'raster',
        source: TRAFFIC_SOURCE_ID,
        layout: { visibility: 'none' },
        paint: {
          'raster-opacity': 0.72,
          'raster-fade-duration': 0,
        },
      },
      beforeId,
    )
  }
}

export function setTrafficLayerVisible(map: maplibregl.Map, visible: boolean): void {
  if (!trafficLayerAvailable()) {
    return
  }
  ensureTrafficLayer(map)
  if (map.getLayer(TRAFFIC_LAYER_ID)) {
    map.setLayoutProperty(TRAFFIC_LAYER_ID, 'visibility', visible ? 'visible' : 'none')
  }
}
