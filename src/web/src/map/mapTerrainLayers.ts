import mlcontour from 'maplibre-contour'
import maplibregl from 'maplibre-gl'

import { CLUSTER_LAYER_ID } from './stationLayers'

const { DemSource } = mlcontour

const DEM_TILES_URL = 'https://demotiles.maplibre.org/terrain-tiles/{z}/{x}/{y}.png'
const ESRI_HILLSHADE_URL =
  'https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}'
const CONTOUR_OTM_URL = 'https://tile.opentopomap.org/{z}/{x}/{y}.png'

export const TERRAIN_DEM_SOURCE_ID = 'terrain-dem'
export const RELIEF_RASTER_SOURCE_ID = 'relief-hillshade-raster'
export const RELIEF_RASTER_LAYER_ID = 'relief-hillshade-raster'
export const CONTOUR_OTM_SOURCE_ID = 'contour-topo-raster'
export const CONTOUR_OTM_LAYER_ID = 'contour-topo-raster'

/** Hillshade sobre calles, debajo de nombres. */
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

function beforeStationLayers(map: maplibregl.Map): string | undefined {
  if (map.getLayer(CLUSTER_LAYER_ID)) {
    return CLUSTER_LAYER_ID
  }
  return anchorLayer(map, ['highway-name-minor', 'label_other'])
}

function ensureDemSource(): InstanceType<typeof DemSource> {
  if (!demSource) {
    demSource = new DemSource({
      url: DEM_TILES_URL,
      encoding: 'mapbox',
      maxzoom: 12,
      worker: false,
    })
    demSource.setupMaplibre(maplibregl)
  }
  return demSource
}

export function ensureTerrainLayers(map: maplibregl.Map): void {
  const source = ensureDemSource()
  const reliefBefore = anchorLayer(map, RELIEF_BEFORE_LAYERS)

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
}

/** Capas de curvas: OpenTopoMap (fiable en todos los zooms). Tras capas de estaciones. */
export function ensureContourLayers(map: maplibregl.Map): void {
  const beforeId = beforeStationLayers(map)

  if (!map.getSource(CONTOUR_OTM_SOURCE_ID)) {
    map.addSource(CONTOUR_OTM_SOURCE_ID, {
      type: 'raster',
      tiles: [CONTOUR_OTM_URL],
      tileSize: 256,
      maxzoom: 17,
      attribution: '© OpenTopoMap (CC-BY-SA)',
    })
  }

  if (!map.getLayer(CONTOUR_OTM_LAYER_ID)) {
    map.addLayer(
      {
        id: CONTOUR_OTM_LAYER_ID,
        type: 'raster',
        source: CONTOUR_OTM_SOURCE_ID,
        minzoom: 6,
        layout: { visibility: 'none' },
        paint: {
          'raster-opacity': 0.52,
          'raster-fade-duration': 0,
        },
      },
      beforeId,
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
  ensureContourLayers(map)
  const visibility = visible ? 'visible' : 'none'
  if (map.getLayer(CONTOUR_OTM_LAYER_ID)) {
    map.setLayoutProperty(CONTOUR_OTM_LAYER_ID, 'visibility', visibility)
  }
}
