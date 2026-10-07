import { useEffect, useState } from 'react'

import { fetchHomeLocation } from '../api/auth'

export type HomeLocation = {
  label: string
  lat: number
  lon: number
}

/**
 * Casa del usuario para el atajo «Mi casa». La sirve el API privado (requiere sesión),
 * así la dirección no viaja en el JavaScript público. null sin sesión o sin configurar.
 */
export function useHomeLocation(): HomeLocation | null {
  const [home, setHome] = useState<HomeLocation | null>(null)
  useEffect(() => {
    let cancelled = false
    fetchHomeLocation()
      .then((value) => {
        if (!cancelled) setHome(value)
      })
      .catch(() => {
        if (!cancelled) setHome(null)
      })
    return () => {
      cancelled = true
    }
  }, [])
  return home
}
