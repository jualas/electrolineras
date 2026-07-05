import mlcontour from 'maplibre-contour'
import maplibregl from 'maplibre-gl'

const { DemSource } = mlcontour

const DEM_TILES_URL = 'https://demotiles.maplibre.org/terrain-tiles/{z}/{x}/{y}.png'

export const TERRAIN_DEM_SOURCE_ID = 'terrain-dem'
export const CONTOUR_SOURCE_ID = 'contour-source'
export const HILLSHADE_LAYER_ID = 'terrain-hillshade'
export const CONTOUR_LINES_LAYER_ID = 'contour-lines'
export const CONTOUR_LABELS_LAYER_ID = 'contour-labels'

let demSource: InstanceType<typeof DemSource> | null = null

function firstSymbolLayerId(map: maplibregl.Map): string | undefined {
  const layers = map.getStyle()?.layers ?? []
  return layers.find((layer) => layer.type === 'symbol')?.id
}

function ensureDemSource(): InstanceType<typeof DemSource> {
  if (!demSource) {
    demSource = new DemSource({
      url: DEM_TILES_URL,
      encoding: 'mapbox',
      maxzoom: 12,
      worker: true,
    })
    demSource.setupMaplibre(maplibregl)
  }
  return demSource
}

export function ensureTerrainLayers(map: maplibregl.Map): void {
  const source = ensureDemSource()
  const beforeId = firstSymbolLayerId(map)

  if (!map.getSource(TERRAIN_DEM_SOURCE_ID)) {
    map.addSource(TERRAIN_DEM_SOURCE_ID, {
      type: 'raster-dem',
      tiles: [source.sharedDemProtocolUrl],
      encoding: 'mapbox',
      maxzoom: 12,
      tileSize: 256,
    })
  }

  if (!map.getSource(CONTOUR_SOURCE_ID)) {
    map.addSource(CONTOUR_SOURCE_ID, {
      type: 'vector',
      tiles: [
        source.contourProtocolUrl({
          thresholds: {
            11: [200, 1000],
            12: [100, 500],
            13: [50, 200],
            14: [20, 100],
          },
          contourLayer: 'contours',
          elevationKey: 'ele',
          levelKey: 'level',
        }),
      ],
      maxzoom: 14,
    })
  }

  if (!map.getLayer(HILLSHADE_LAYER_ID)) {
    map.addLayer(
      {
        id: HILLSHADE_LAYER_ID,
        type: 'hillshade',
        source: TERRAIN_DEM_SOURCE_ID,
        layout: { visibility: 'none' },
        paint: {
          'hillshade-exaggeration': 0.45,
          'hillshade-shadow-color': '#334155',
          'hillshade-highlight-color': '#f8fafc',
          'hillshade-accent-color': '#64748b',
        },
      },
      beforeId,
    )
  }

  if (!map.getLayer(CONTOUR_LINES_LAYER_ID)) {
    map.addLayer(
      {
        id: CONTOUR_LINES_LAYER_ID,
        type: 'line',
        source: CONTOUR_SOURCE_ID,
        'source-layer': 'contours',
        layout: { visibility: 'none' },
        paint: {
          'line-color': [
            'match',
            ['get', 'level'],
            1,
            'rgba(71, 85, 105, 0.75)',
            'rgba(100, 116, 139, 0.45)',
          ],
          'line-width': ['match', ['get', 'level'], 1, 1.2, 0.6],
        },
      },
      beforeId,
    )
  }

  if (!map.getLayer(CONTOUR_LABELS_LAYER_ID)) {
    map.addLayer(
      {
        id: CONTOUR_LABELS_LAYER_ID,
        type: 'symbol',
        source: CONTOUR_SOURCE_ID,
        'source-layer': 'contours',
        filter: ['>', ['get', 'level'], 0],
        layout: {
          visibility: 'none',
          'symbol-placement': 'line',
          'text-size': 10,
          'text-field': ['concat', ['to-string', ['round', ['get', 'ele']]], ' m'],
        },
        paint: {
          'text-color': '#475569',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1,
        },
      },
      beforeId,
    )
  }
}

export function setTerrainReliefVisible(map: maplibregl.Map, visible: boolean): void {
  ensureTerrainLayers(map)
  const visibility = visible ? 'visible' : 'none'
  for (const layerId of [HILLSHADE_LAYER_ID]) {
    if (map.getLayer(layerId)) {
      map.setLayoutProperty(layerId, 'visibility', visibility)
    }
  }
  if (visible) {
    map.setTerrain({ source: TERRAIN_DEM_SOURCE_ID, exaggeration: 1.15 })
  } else if (map.getTerrain()) {
    map.setTerrain(null)
  }
}

export function setContourLinesVisible(map: maplibregl.Map, visible: boolean): void {
  ensureTerrainLayers(map)
  const visibility = visible ? 'visible' : 'none'
  for (const layerId of [CONTOUR_LINES_LAYER_ID, CONTOUR_LABELS_LAYER_ID]) {
    if (map.getLayer(layerId)) {
      map.setLayoutProperty(layerId, 'visibility', visibility)
    }
  }
}
