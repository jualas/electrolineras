import maplibregl from 'maplibre-gl'

const ESRI_HILLSHADE_URL =
  'https://services.arcgisonline.com/arcgis/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}'
const CONTOUR_OTM_URL = 'https://tile.opentopomap.org/{z}/{x}/{y}.png'

export const SHADOW_LAYER_ID = 'relief-hillshade-raster'
export const CONTOUR_OTM_LAYER_ID = 'relief-contour-raster'

/** Sombreado y curvas debajo de carreteras del estilo base. */
const RELIEF_BEFORE_LAYERS = [
  'road_minor',
  'road_secondary_tertiary',
  'road_one_way_arrow',
  'highway-name-minor',
  'label_other',
]

function anchorLayer(map: maplibregl.Map, candidates: string[]): string | undefined {
  for (const layerId of candidates) {
    if (map.getLayer(layerId)) {
      return layerId
    }
  }
  const layers = map.getStyle()?.layers ?? []
  return layers.find((layer) => layer.type === 'line' || layer.type === 'symbol')?.id
}

/**
 * Relieve estilo REVE: sombras Esri + curvas OpenTopoMap en el mismo bloque.
 * Se apilan sombra (abajo) → curvas (arriba), ambas semitransparentes sobre el mapa base.
 */
export function ensureReliefLayers(map: maplibregl.Map): void {
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

  if (!map.getSource(CONTOUR_OTM_LAYER_ID)) {
    map.addSource(CONTOUR_OTM_LAYER_ID, {
      type: 'raster',
      tiles: [CONTOUR_OTM_URL],
      tileSize: 256,
      maxzoom: 17,
      attribution: '© OpenTopoMap (CC-BY-SA)',
    })
  }

  // Primero sombra; luego curvas encima (misma ancla → orden de inserción).
  if (!map.getLayer(SHADOW_LAYER_ID)) {
    map.addLayer(
      {
        id: SHADOW_LAYER_ID,
        type: 'raster',
        source: SHADOW_LAYER_ID,
        layout: { visibility: 'none' },
        paint: {
          'raster-opacity': 0.48,
          'raster-fade-duration': 0,
        },
      },
      beforeId,
    )
  }

  if (!map.getLayer(CONTOUR_OTM_LAYER_ID)) {
    map.addLayer(
      {
        id: CONTOUR_OTM_LAYER_ID,
        type: 'raster',
        source: CONTOUR_OTM_LAYER_ID,
        minzoom: 6,
        layout: { visibility: 'none' },
        paint: {
          // Solo curvas/topo encima del hillshade; el mapa base sigue visible alrededor.
          'raster-opacity': 0.55,
          'raster-fade-duration': 0,
        },
      },
      beforeId,
    )
  }
}

export function setReliefVisible(map: maplibregl.Map, visible: boolean): void {
  ensureReliefLayers(map)
  const visibility = visible ? 'visible' : 'none'
  for (const layerId of [SHADOW_LAYER_ID, CONTOUR_OTM_LAYER_ID]) {
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
