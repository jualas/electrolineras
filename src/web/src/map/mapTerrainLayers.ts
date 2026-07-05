import mlcontour from 'maplibre-contour'
import maplibregl from 'maplibre-gl'

const { DemSource } = mlcontour

const DEM_TILES_URL = 'https://demotiles.maplibre.org/terrain-tiles/{z}/{x}/{y}.png'
const ESRI_HILLSHADE_URL =
  'https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}'

export const TERRAIN_DEM_SOURCE_ID = 'terrain-dem'
export const RELIEF_RASTER_SOURCE_ID = 'relief-hillshade-raster'
export const RELIEF_RASTER_LAYER_ID = 'relief-hillshade-raster'
export const CONTOUR_SOURCE_ID = 'contour-source'
export const CONTOUR_LINES_LAYER_ID = 'contour-lines'
export const CONTOUR_LABELS_LAYER_ID = 'contour-labels'

/** Por encima de carreteras, debajo de etiquetas de lugar. */
const CONTOUR_BEFORE_LAYERS = ['label_other', 'label_village', 'label_town', 'highway-name-minor']
/** Hillshade sobre calles y terreno, debajo de nombres. */
const RELIEF_BEFORE_LAYERS = ['highway-name-minor', 'label_other', 'label_village']

let demSource: InstanceType<typeof DemSource> | null = null

function anchorLayer(map: maplibregl.Map, candidates: string[]): string | undefined {
  for (const layerId of candidates) {
    if (map.getLayer(layerId)) {
      return layerId
    }
  }
  const layers = map.getStyle()?.layers ?? []
  return layers.find((layer) => layer.type === 'symbol')?.id
}

function ensureDemSource(): InstanceType<typeof DemSource> {
  if (!demSource) {
    demSource = new DemSource({
      url: DEM_TILES_URL,
      encoding: 'mapbox',
      maxzoom: 12,
      // Evita fallos de worker en bundles de producción.
      worker: false,
    })
    demSource.setupMaplibre(maplibregl)
  }
  return demSource
}

export function ensureTerrainLayers(map: maplibregl.Map): void {
  const source = ensureDemSource()
  const reliefBefore = anchorLayer(map, RELIEF_BEFORE_LAYERS)
  const contourBefore = anchorLayer(map, CONTOUR_BEFORE_LAYERS)

  if (!map.getSource(RELIEF_RASTER_SOURCE_ID)) {
    map.addSource(RELIEF_RASTER_SOURCE_ID, {
      type: 'raster',
      tiles: [ESRI_HILLSHADE_URL],
      tileSize: 256,
      maxzoom: 15,
      attribution: 'Esri, USGS',
    })
  }

  if (!map.getLayer(RELIEF_RASTER_LAYER_ID)) {
    map.addLayer(
      {
        id: RELIEF_RASTER_LAYER_ID,
        type: 'raster',
        source: RELIEF_RASTER_SOURCE_ID,
        layout: { visibility: 'none' },
        paint: {
          'raster-opacity': 0.48,
          'raster-fade-duration': 0,
        },
      },
      reliefBefore,
    )
  }

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
            8: [1000, 3000],
            9: [500, 2000],
            10: [200, 1000],
            11: [100, 500],
            12: [50, 200],
            13: [20, 100],
            14: [10, 50],
          },
          contourLayer: 'contours',
          elevationKey: 'ele',
          levelKey: 'level',
        }),
      ],
      maxzoom: 14,
    })
  }

  if (!map.getLayer(CONTOUR_LINES_LAYER_ID)) {
    map.addLayer(
      {
        id: CONTOUR_LINES_LAYER_ID,
        type: 'line',
        source: CONTOUR_SOURCE_ID,
        'source-layer': 'contours',
        minzoom: 8,
        layout: { visibility: 'none' },
        paint: {
          'line-color': [
            'match',
            ['get', 'level'],
            1,
            'rgba(30, 41, 59, 0.9)',
            'rgba(51, 65, 85, 0.55)',
          ],
          'line-width': ['match', ['get', 'level'], 1, 1.4, 0.75],
        },
      },
      contourBefore,
    )
  }

  if (!map.getLayer(CONTOUR_LABELS_LAYER_ID)) {
    map.addLayer(
      {
        id: CONTOUR_LABELS_LAYER_ID,
        type: 'symbol',
        source: CONTOUR_SOURCE_ID,
        'source-layer': 'contours',
        minzoom: 10,
        filter: ['>', ['get', 'level'], 0],
        layout: {
          visibility: 'none',
          'symbol-placement': 'line',
          'text-size': 11,
          'text-field': ['concat', ['to-string', ['round', ['get', 'ele']]], ' m'],
        },
        paint: {
          'text-color': '#1e293b',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1.5,
        },
      },
      contourBefore,
    )
  }
}

export function setTerrainReliefVisible(map: maplibregl.Map, visible: boolean): void {
  ensureTerrainLayers(map)
  const visibility = visible ? 'visible' : 'none'
  if (map.getLayer(RELIEF_RASTER_LAYER_ID)) {
    map.setLayoutProperty(RELIEF_RASTER_LAYER_ID, 'visibility', visibility)
  }
  if (visible) {
    map.setTerrain({ source: TERRAIN_DEM_SOURCE_ID, exaggeration: 1.25 })
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
