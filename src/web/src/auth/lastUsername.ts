const STORAGE_KEY = 'electrolineras.last_username'

/** Recuerda, solo en este navegador/dispositivo, quién fue la última persona en iniciar sesión. */
export function getLastUsername(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setLastUsername(username: string): void {
  try {
    localStorage.setItem(STORAGE_KEY, username)
  } catch {
    // localStorage no disponible (modo privado, cuota, etc.): no es crítico, simplemente no se recuerda.
  }
}
