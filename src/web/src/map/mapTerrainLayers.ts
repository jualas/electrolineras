import mlcontour from 'maplibre-contour'
import maplibregl from 'maplibre-gl'

const { DemSource } = mlcontour

const DEM_TILES_URL = 'https://demotiles.maplibre.org/terrain-tiles/{z}/{x}/{y}.png'
const ESRI_HILLSHADE_URL =
  'https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}'

export const TERRAIN_DEM_SOURCE_ID = 'terrain-dem'
export const CONTOUR_SOURCE_ID = 'contour-source'
export const SHADOW_LAYER_ID = 'relief-hillshade-raster'
export const CONTOUR_LINES_LAYER_ID = 'contour-lines'
export const CONTOUR_LABELS_LAYER_ID = 'contour-labels'

/** Sombreado y curvas debajo de carreteras del estilo base. */
const RELIEF_BEFORE_LAYERS = [
  'road_minor',
  'road_secondary_tertiary',
  'road_one_way_arrow',
  'highway-name-minor',
  'label_other',
]

let demSource: InstanceType<typeof DemSource> | null = null

function anchorLayer(map: maplibregl.Map, candidates: string[]): string | undefined {
  for (const layerId of candidates) {
    if (map.getLayer(layerId)) {
      return layerId
    }
  }
  const layers = map.getStyle()?.layers ?? []
  return layers.find((layer) => layer.type === 'line' || layer.type === 'symbol')?.id
}

function ensureDemSource(): InstanceType<typeof DemSource> {
  if (!demSource) {
    demSource = new DemSource({
      url: DEM_TILES_URL,
      encoding: 'mapbox',
      maxzoom: 12,
      worker: false,
      cacheSize: 120,
    })
    demSource.setupMaplibre(maplibregl)
  }
  return demSource
}

/**
 * Relieve estilo REVE: sombras Esri + curvas vectoriales del mismo DEM.
 * Las capas se apilan en orden (abajo→arriba): sombra → líneas → etiquetas.
 */
export function ensureReliefLayers(map: maplibregl.Map): void {
  const dem = ensureDemSource()
  const beforeId = anchorLayer(map, RELIEF_BEFORE_LAYERS)

  if (!map.getSource(SHADOW_LAYER_ID)) {
    map.addSource(SHADOW_LAYER_ID, {
      type: 'raster',
      tiles: [ESRI_HILLSHADE_URL],
      tileSize: 256,
      maxzoom: 15,
      attribution: 'Esri, USGS',
    })
  }

  if (!map.getSource(TERRAIN_DEM_SOURCE_ID)) {
    map.addSource(TERRAIN_DEM_SOURCE_ID, {
      type: 'raster-dem',
      tiles: [dem.sharedDemProtocolUrl],
      encoding: 'mapbox',
      maxzoom: 12,
      tileSize: 256,
    })
  }

  if (!map.getSource(CONTOUR_SOURCE_ID)) {
    map.addSource(CONTOUR_SOURCE_ID, {
      type: 'vector',
      tiles: [
        dem.contourProtocolUrl({
          thresholds: {
            9: [100, 500],
            10: [50, 200],
            11: [25, 100],
            12: [10, 50],
            13: [5, 25],
            14: [2, 10],
          },
          contourLayer: 'contours',
          elevationKey: 'ele',
          levelKey: 'level',
        }),
      ],
      maxzoom: 14,
    })
  }

  // Orden de inserción: la última queda más arriba dentro del bloque relieve.
  if (!map.getLayer(SHADOW_LAYER_ID)) {
    map.addLayer(
      {
        id: SHADOW_LAYER_ID,
        type: 'raster',
        source: SHADOW_LAYER_ID,
        layout: { visibility: 'none' },
        paint: {
          'raster-opacity': 0.5,
          'raster-fade-duration': 0,
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
        minzoom: 9,
        layout: { visibility: 'none' },
        paint: {
          'line-color': [
            'match',
            ['get', 'level'],
            1,
            'rgba(110, 85, 60, 0.9)',
            'rgba(130, 105, 75, 0.6)',
          ],
          'line-width': ['match', ['get', 'level'], 1, 1.2, 0.65],
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
        minzoom: 11,
        filter: ['>', ['get', 'level'], 0],
        layout: {
          visibility: 'none',
          'symbol-placement': 'line',
          'text-size': 10,
          'text-field': ['concat', ['to-string', ['round', ['get', 'ele']]], ' m'],
          'text-padding': 4,
        },
        paint: {
          'text-color': '#6b5344',
          'text-halo-color': 'rgba(255, 252, 245, 0.9)',
          'text-halo-width': 1.2,
        },
      },
      beforeId,
    )
  }
}

export function setReliefVisible(map: maplibregl.Map, visible: boolean): void {
  ensureReliefLayers(map)
  const visibility = visible ? 'visible' : 'none'
  for (const layerId of [SHADOW_LAYER_ID, CONTOUR_LINES_LAYER_ID, CONTOUR_LABELS_LAYER_ID]) {
    if (map.getLayer(layerId)) {
      map.setLayoutProperty(layerId, 'visibility', visibility)
    }
  }
  if (map.getTerrain()) {
    map.setTerrain(null)
  }
}

/** @deprecated */
export function ensureTerrainLayers(map: maplibregl.Map): void {
  ensureReliefLayers(map)
}

/** @deprecated */
export function ensureContourLayers(map: maplibregl.Map): void {
  ensureReliefLayers(map)
}

/** @deprecated */
export function setTerrainReliefVisible(map: maplibregl.Map, visible: boolean): void {
  setReliefVisible(map, visible)
}

/** @deprecated */
export function setContourLinesVisible(map: maplibregl.Map, visible: boolean): void {
  setReliefVisible(map, visible)
}
