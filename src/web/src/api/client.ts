import { CAR_BRIDGE_KEYS, readBridgePreference, syncCarBridgeApiBase, writeBridgePreference } from '../native/carBridge'

const configuredBase = import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? ''

let runtimePrivateToken: string | null = null
let tokenLoaded = false

if (configuredBase) {
  void syncCarBridgeApiBase(configuredBase)
}

export async function ensurePrivateTokenLoaded(): Promise<string | null> {
  if (tokenLoaded) {
    return runtimePrivateToken
  }
  tokenLoaded = true
  runtimePrivateToken = await readBridgePreference(CAR_BRIDGE_KEYS.privateToken)
  return runtimePrivateToken
}

export async function setStoredPrivateToken(token: string | null): Promise<void> {
  const clean = token?.trim() || null
  runtimePrivateToken = clean
  tokenLoaded = true
  await writeBridgePreference(CAR_BRIDGE_KEYS.privateToken, clean)
}

export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return configuredBase ? `${configuredBase}${normalized}` : normalized
}

let unauthorizedHandler: (() => void) | null = null

/** Se invoca en cualquier 401 de la API, para que el gate de login pueda reaccionar (p. ej. sesión caducada). */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler
}

export async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const token = await ensurePrivateTokenLoaded()
  const headers = new Headers(init?.headers)
  if (token && !headers.has('X-Private-Token')) {
    headers.set('X-Private-Token', token)
  }
  const response = await fetch(apiUrl(path), { ...init, headers, credentials: 'include' })
  if (response.status === 401 && path !== '/api/v1/auth/session' && path !== '/api/v1/auth/login') {
    unauthorizedHandler?.()
  }
  if (!response.ok) {
    let message = `API ${path}: HTTP ${response.status}`
    try {
      const body = (await response.json()) as { detail?: string | { msg: string }[] }
      if (typeof body.detail === 'string') {
        message = body.detail
      } else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        message = body.detail[0].msg
      }
    } catch {
      // keep default message
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export async function checkApiHealth(): Promise<boolean> {
  try {
    const payload = await fetchApi<{ status: string }>('/health')
    return payload.status === 'ok'
  } catch {
    return false
  }
}
