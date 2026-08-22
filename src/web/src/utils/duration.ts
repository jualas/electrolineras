/** Duración legible: "2 h 15 min", "1 h" o "45 min". */
export function formatDurationMinutes(minutes: number | null | undefined): string {
  if (minutes == null || minutes <= 0 || !Number.isFinite(minutes)) {
    return ''
  }
  const rounded = Math.round(minutes)
  const hours = Math.floor(rounded / 60)
  const mins = rounded % 60
  if (hours > 0) {
    return mins > 0 ? `${hours} h ${mins} min` : `${hours} h`
  }
  return `${mins} min`
}
