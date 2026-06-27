export function formatDynamicStatusLabel(status: string): string {
  switch (status.toUpperCase()) {
    case 'AVAILABLE':
      return 'Disponible'
    case 'CHARGING':
      return 'Cargando'
    case 'RESERVED':
      return 'Reservado'
    case 'OUTOFORDER':
    case 'INOPERATIVE':
      return 'Fuera de servicio'
    default:
      return status
  }
}

export function dynamicStatusClassName(status: string, prefix = 'station-dynamic'): string {
  return `${prefix}__status--${status.toLowerCase()}`
}

export function hasDynamicInfo(
  status: string | null | undefined,
  priceEurKwh: number | null | undefined,
): boolean {
  return Boolean(status) || (priceEurKwh != null && !Number.isNaN(priceEurKwh))
}
