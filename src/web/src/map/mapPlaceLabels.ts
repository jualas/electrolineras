import maplibregl from 'maplibre-gl'

type PlaceLabelTuning = {
  id: string
  minzoom: number
  maxzoom?: number
  textSize?: maplibregl.ExpressionSpecification
}

/**
 * El estilo Liberty (OpenFreeMap) muestra pueblos desde zoom 6 y aldeas desde 9.
 * Google enseña poblaciones antes; bajamos el umbral y escalamos el texto para zoom bajo.
 */
const PLACE_LABEL_TUNING: PlaceLabelTuning[] = [
  {
    id: 'label_city',
    minzoom: 3,
    textSize: ['interpolate', ['exponential', 1.2], ['zoom'], 4, 10, 7, 13, 11, 18],
  },
  {
    id: 'label_city_capital',
    minzoom: 3,
    textSize: ['interpolate', ['exponential', 1.2], ['zoom'], 4, 11, 7, 14, 11, 20],
  },
  {
    id: 'label_town',
    minzoom: 4,
    textSize: ['interpolate', ['exponential', 1.2], ['zoom'], 4, 9, 6, 11, 7, 12, 11, 14],
  },
  {
    id: 'label_village',
    minzoom: 5.5,
    textSize: ['interpolate', ['exponential', 1.2], ['zoom'], 5.5, 8, 7, 9, 11, 12],
  },
  {
    id: 'label_other',
    minzoom: 5,
    textSize: ['interpolate', ['linear'], ['zoom'], 5, 7, 12, 10],
  },
]

export function enhancePlaceLabels(map: maplibregl.Map): void {
  for (const layer of PLACE_LABEL_TUNING) {
    if (!map.getLayer(layer.id)) {
      continue
    }
    map.setLayerZoomRange(layer.id, layer.minzoom, layer.maxzoom ?? 24)
    if (layer.textSize) {
      map.setLayoutProperty(layer.id, 'text-size', layer.textSize)
    }
  }
}
