const configuredBase = import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? ''

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
  const response = await fetch(apiUrl(path), { ...init, credentials: 'include' })
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
