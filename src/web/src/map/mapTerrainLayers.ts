import mlcontour from 'maplibre-contour'
import maplibregl from 'maplibre-gl'

import { CLUSTER_LAYER_ID } from './stationLayers'

const { DemSource } = mlcontour

const DEM_TILES_URL = 'https://demotiles.maplibre.org/terrain-tiles/{z}/{x}/{y}.png'

export const TERRAIN_DEM_SOURCE_ID = 'terrain-dem'
export const CONTOUR_SOURCE_ID = 'contour-source'
export const HILLSHADE_LAYER_ID = 'terrain-hillshade'
export const CONTOUR_LINES_LAYER_ID = 'contour-lines'
export const CONTOUR_LABELS_LAYER_ID = 'contour-labels'

/** Hillshade sobre terreno base, debajo de carreteras. */
const HILLSHADE_BEFORE_LAYERS = ['road_minor', 'road_secondary_tertiary', 'road_one_way_arrow', 'highway-name-minor']

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

function beforeStationLayers(map: maplibregl.Map): string | undefined {
  if (map.getLayer(CLUSTER_LAYER_ID)) {
    return CLUSTER_LAYER_ID
  }
  return anchorLayer(map, HILLSHADE_BEFORE_LAYERS)
}

function ensureDemSource(): InstanceType<typeof DemSource> {
  if (!demSource) {
    demSource = new DemSource({
      url: DEM_TILES_URL,
      encoding: 'mapbox',
      maxzoom: 12,
      worker: true,
      cacheSize: 120,
    })
    demSource.setupMaplibre(maplibregl)
  }
  return demSource
}

/** Relieve integrado estilo REVE: sombreado + curvas de nivel sobre el mismo DEM. */
export function ensureReliefLayers(map: maplibregl.Map): void {
  const source = ensureDemSource()
  const hillshadeBefore = anchorLayer(map, HILLSHADE_BEFORE_LAYERS)
  const contourBefore = beforeStationLayers(map)

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

  if (!map.getLayer(HILLSHADE_LAYER_ID)) {
    map.addLayer(
      {
        id: HILLSHADE_LAYER_ID,
        type: 'hillshade',
        source: TERRAIN_DEM_SOURCE_ID,
        layout: { visibility: 'none' },
        paint: {
          'hillshade-exaggeration': 0.55,
          'hillshade-shadow-color': '#3d4f3a',
          'hillshade-highlight-color': '#f5f0e6',
          'hillshade-accent-color': '#6b7c5e',
          'hillshade-illumination-direction': 315,
        },
      },
      hillshadeBefore,
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
            'rgba(120, 95, 70, 0.85)',
            'rgba(140, 115, 85, 0.55)',
          ],
          'line-width': ['match', ['get', 'level'], 1, 1.1, 0.55],
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
          'text-halo-color': 'rgba(255, 252, 245, 0.85)',
          'text-halo-width': 1.2,
        },
      },
      contourBefore,
    )
  }
}

export function setReliefVisible(map: maplibregl.Map, visible: boolean): void {
  ensureReliefLayers(map)
  const visibility = visible ? 'visible' : 'none'
  for (const layerId of [HILLSHADE_LAYER_ID, CONTOUR_LINES_LAYER_ID, CONTOUR_LABELS_LAYER_ID]) {
    if (map.getLayer(layerId)) {
      map.setLayoutProperty(layerId, 'visibility', visibility)
    }
  }
  // Vista 2D como REVE (hillshade + curvas), sin inclinación 3D del terreno.
  if (map.getTerrain()) {
    map.setTerrain(null)
  }
}

/** @deprecated Usar setReliefVisible — relieve y curvas van juntos. */
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
