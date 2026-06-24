import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'

const IBERIAN_CENTER: [number, number] = [-4.5, 40.2]
const DEFAULT_ZOOM = 5.8
const MAP_STYLE = 'https://tiles.openfreemap.org/styles/liberty'

type MapViewProps = {
  className?: string
}

export function MapView({ className }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<maplibregl.Map | null>(null)

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
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [])

  return <div ref={containerRef} className={className ?? 'map-view'} aria-label="Mapa peninsular" />
}
