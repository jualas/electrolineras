const configuredBase = import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? ''

export function apiUrl(path: string): string {
  const normalized = path.startsWith('/') ? path : `/${path}`
  return configuredBase ? `${configuredBase}${normalized}` : normalized
}

export async function fetchApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init)
  if (!response.ok) {
    throw new Error(`API ${path}: HTTP ${response.status}`)
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
