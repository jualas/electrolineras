/** Formatea con coma decimal como REVE (mapareve.es), p.ej. "237,33 km". */
export function formatEsNumber(value: number, decimals = 0): string {
  return value.toLocaleString('es-ES', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

/** Formatea minutos como "5 h 25 min" / "43 min", igual que el resumen de viaje de REVE. */
export function formatDurationHm(totalMinutes: number): string {
  const rounded = Math.round(totalMinutes)
  const hours = Math.floor(rounded / 60)
  const minutes = rounded % 60
  if (hours <= 0) {
    return `${minutes} min`
  }
  if (minutes === 0) {
    return `${hours} h`
  }
  return `${hours} h ${minutes} min`
}
