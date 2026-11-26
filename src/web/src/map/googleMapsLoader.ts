/* eslint-disable @typescript-eslint/no-explicit-any */

export type GoogleMapsApi = {
  Map: new (element: HTMLElement, options: Record<string, any>) => any
  LatLngBounds: new () => any
  Marker: new (options: Record<string, any>) => any
  Polyline: new (options: Record<string, any>) => any
  Circle: new (options: Record<string, any>) => any
  InfoWindow: new (options?: Record<string, any>) => any
  TrafficLayer: new () => any
  SymbolPath: { CIRCLE: number }
  ControlPosition: Record<string, number>
  importLibrary?: (name: string) => Promise<any>
  event: {
    clearInstanceListeners: (instance: any) => void
  }
}

declare global {
  interface Window {
    google?: {
      maps?: GoogleMapsApi
    }
    __electrolinerasGoogleMapsInit?: () => void
  }
}

const GOOGLE_MAPS_JS_KEY = import.meta.env.VITE_GOOGLE_MAPS_JS_API_KEY?.trim() ?? ''
const MAP_PROVIDER = (import.meta.env.VITE_MAP_PROVIDER?.trim() ?? '').toLowerCase()

let loadPromise: Promise<GoogleMapsApi> | null = null

export function googleMapsApiKey(): string {
  return GOOGLE_MAPS_JS_KEY
}

export function shouldUseGoogleMaps(): boolean {
  if (MAP_PROVIDER === 'maplibre') {
    return false
  }
  return GOOGLE_MAPS_JS_KEY.length > 0
}

export function loadGoogleMapsApi(): Promise<GoogleMapsApi> {
  if (window.google?.maps?.Map) {
    return Promise.resolve(window.google.maps)
  }
  if (loadPromise) {
    return loadPromise
  }
  if (!GOOGLE_MAPS_JS_KEY) {
    return Promise.reject(new Error('VITE_GOOGLE_MAPS_JS_API_KEY no configurada'))
  }

  loadPromise = new Promise<GoogleMapsApi>((resolve, reject) => {
    const existing = document.querySelector<HTMLScriptElement>('script[data-google-maps-js="true"]')
    if (existing && window.google?.maps?.Map) {
      resolve(window.google.maps)
      return
    }

    const callbackName = '__electrolinerasGoogleMapsInit'
    window[callbackName] = () => {
      delete window[callbackName]
      const finish = async () => {
        const gm = window.google?.maps
        if (!gm) {
          loadPromise = null
          reject(new Error('Google Maps JS cargó sin objeto google.maps'))
          return
        }
        if (!gm.Map && typeof gm.importLibrary === 'function') {
          await gm.importLibrary('maps')
        }
        if (window.google?.maps?.Map) {
          resolve(window.google.maps)
        } else {
          loadPromise = null
          reject(new Error('Google Maps JS cargó sin objeto google.maps.Map'))
        }
      }
      void finish().catch((err) => {
        loadPromise = null
        reject(err instanceof Error ? err : new Error('Error inicializando Google Maps JS'))
      })
    }

    const script = document.createElement('script')
    const params = new URLSearchParams({
      key: GOOGLE_MAPS_JS_KEY,
      v: 'weekly',
      language: 'es',
      region: 'ES',
      loading: 'async',
      callback: callbackName,
    })
    script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`
    script.async = true
    script.defer = true
    script.dataset.googleMapsJs = 'true'
    script.onerror = () => {
      delete window[callbackName]
      loadPromise = null
      reject(new Error('No se pudo cargar el script de Google Maps JavaScript API'))
    }
    document.head.appendChild(script)
  })

  return loadPromise
}
