import { Capacitor } from '@capacitor/core'
import { Share } from '@capacitor/share'

export type MapCoords = {
  lat: number
  lon: number
}

export type RouteExportSpec = {
  origin: MapCoords
  destination: MapCoords
  waypoints?: MapCoords[]
  title?: string
}

export { routeExportSpecFromChargingPlan as routeExportSpecFromPlan } from '../charging/planRouteStops'

export function formatCoordinates(lat: number, lon: number): string {
  return `${lat.toFixed(6)}, ${lon.toFixed(6)}`
}

export function googleMapsDestinationUrl(lat: number, lon: number): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}`
}

export function appleMapsDestinationUrl(lat: number, lon: number): string {
  return `https://maps.apple.com/?daddr=${lat},${lon}`
}

/** Formato que la app Tesla parsea al recibir un «Compartir» desde Maps. */
export function teslaMapsPlaceUrl(lat: number, lon: number): string {
  return `https://maps.google.com/?q=${lat},${lon}`
}

export function teslaShareText(lat: number, lon: number, label?: string): string {
  const title = label?.trim() || 'Destino'
  return `${title}\n${teslaMapsPlaceUrl(lat, lon)}`
}

export function teslaAndroidShareIntentUrl(lat: number, lon: number, label?: string): string {
  const text = encodeURIComponent(teslaShareText(lat, lon, label))
  const subject = encodeURIComponent(label?.trim() || 'Destino')
  return (
    'intent:#Intent;' +
    'action=android.intent.action.SEND;' +
    'type=text/plain;' +
    'package=com.teslamotors.tesla;' +
    `S.android.intent.extra.SUBJECT=${subject};` +
    `S.android.intent.extra.TEXT=${text};` +
    'end'
  )
}

export type TeslaHandoffResult = 'share' | 'intent' | 'copied' | 'cancelled' | 'failed'

/** Envía el destino a la app Tesla (Share nativo Capacitor → Web Share → Intent Android → copiar). */
export async function openInTeslaApp(
  lat: number,
  lon: number,
  label?: string,
): Promise<TeslaHandoffResult> {
  const text = teslaShareText(lat, lon, label)
  const title = label?.trim() || 'Destino'
  const url = teslaMapsPlaceUrl(lat, lon)

  if (Capacitor.isNativePlatform()) {
    try {
      await Share.share({ title, text, dialogTitle: 'Enviar a Tesla' })
      return 'share'
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err)
      if (/cancel|abort/i.test(message)) {
        return 'cancelled'
      }
    }
  }

  if (typeof navigator !== 'undefined' && typeof navigator.share === 'function') {
    try {
      await navigator.share({ title, text, url })
      return 'share'
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        return 'cancelled'
      }
    }
  }

  if (
    Capacitor.getPlatform() === 'android' ||
    (typeof navigator !== 'undefined' && /Android/i.test(navigator.userAgent))
  ) {
    try {
      const a = document.createElement('a')
      a.href = teslaAndroidShareIntentUrl(lat, lon, label)
      a.rel = 'noopener'
      a.style.display = 'none'
      document.body.appendChild(a)
      a.click()
      a.remove()
      return 'intent'
    } catch {
      // fallthrough
    }
  }

  const copied = await copyCoordinates(lat, lon)
  return copied ? 'copied' : 'failed'
}

export function googleMapsRouteUrl(options: {
  origin: MapCoords
  destination: MapCoords
  waypoints?: MapCoords[]
  maxWaypoints?: number
}): string {
  const params = new URLSearchParams({
    api: '1',
    travelmode: 'driving',
    origin: formatCoordinates(options.origin.lat, options.origin.lon),
    destination: formatCoordinates(options.destination.lat, options.destination.lon),
  })

  const waypoints = options.waypoints?.slice(0, options.maxWaypoints ?? 8)
  if (waypoints && waypoints.length > 0) {
    params.set(
      'waypoints',
      waypoints.map((point) => formatCoordinates(point.lat, point.lon)).join('|'),
    )
  }

  return `https://www.google.com/maps/dir/?${params.toString()}`
}

export function routeShareText(
  spec: RouteExportSpec,
  mode: 'full' | 'next_stop' = 'full',
  nextStopIndex = 0,
): string {
  const stop = spec.waypoints?.[nextStopIndex]
  if (mode === 'next_stop' && stop) {
    const url = googleMapsDestinationUrl(stop.lat, stop.lon)
    const label = nextStopIndex + 1
    return `Parada de carga ${label} · Electrolineras\n${url}`
  }

  if (mode === 'next_stop' && spec.destination) {
    const url = googleMapsDestinationUrl(spec.destination.lat, spec.destination.lon)
    return `Parada de carga · Electrolineras\n${url}`
  }

  const url = googleMapsRouteUrl({
    origin: spec.origin,
    destination: spec.destination,
    waypoints: spec.waypoints,
  })
  const stopCount = spec.waypoints?.length ?? 0
  if (stopCount > 0) {
    return `Ruta con ${stopCount} parada${stopCount === 1 ? '' : 's'} de carga · Electrolineras\n${url}`
  }
  return `Ruta Electrolineras\n${url}`
}

export function isMobileBrowser(): boolean {
  if (typeof navigator === 'undefined') {
    return false
  }
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)
}

export async function copyCoordinates(lat: number, lon: number): Promise<boolean> {
  const text = formatCoordinates(lat, lon)
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // fallback below
  }

  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.setAttribute('readonly', '')
    textarea.style.position = 'fixed'
    textarea.style.left = '-9999px'
    document.body.appendChild(textarea)
    textarea.select()
    const copied = document.execCommand('copy')
    document.body.removeChild(textarea)
    return copied
  } catch {
    return false
  }
}

export function canShareLocation(): boolean {
  return typeof navigator.share === 'function'
}

export async function shareMapLocation(
  lat: number,
  lon: number,
  label?: string,
): Promise<boolean> {
  if (!canShareLocation()) {
    return false
  }
  try {
    await navigator.share({
      title: label ?? 'Electrolineras',
      text: label ?? formatCoordinates(lat, lon),
      url: googleMapsDestinationUrl(lat, lon),
    })
    return true
  } catch {
    return false
  }
}

/** Compartir ruta (Web Share → app Tesla en móvil, u otra app de navegación). */
export async function shareRoute(
  spec: RouteExportSpec,
  mode: 'full' | 'next_stop' = 'full',
  nextStopIndex = 0,
): Promise<boolean> {
  if (!canShareLocation()) {
    return false
  }
  const text = routeShareText(spec, mode, nextStopIndex)
  const stop = spec.waypoints?.[nextStopIndex]
  const url =
    mode === 'next_stop' && stop
      ? googleMapsDestinationUrl(stop.lat, stop.lon)
      : mode === 'next_stop' && spec.destination
        ? googleMapsDestinationUrl(spec.destination.lat, spec.destination.lon)
        : googleMapsRouteUrl({
            origin: spec.origin,
            destination: spec.destination,
            waypoints: spec.waypoints,
          })
  try {
    await navigator.share({
      title: spec.title ?? 'Electrolineras',
      text,
      url,
    })
    return true
  } catch {
    return false
  }
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
}

export function navigationPopupHtml(lat: number, lon: number): string {
  const googleUrl = escapeHtml(googleMapsDestinationUrl(lat, lon))
  const appleUrl = escapeHtml(appleMapsDestinationUrl(lat, lon))
  const coords = escapeHtml(formatCoordinates(lat, lon))

  return `
    <div class="station-popup__nav">
      <a class="station-popup__nav-link station-popup__nav-link--primary" href="${googleUrl}" target="_blank" rel="noopener noreferrer">Google Maps</a>
      <a class="station-popup__nav-link" href="${appleUrl}" target="_blank" rel="noopener noreferrer">Apple Maps</a>
      <span class="station-popup__coords">${coords}</span>
    </div>
  `
}
