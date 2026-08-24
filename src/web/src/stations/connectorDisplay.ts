export type ConnectorLike = {
  connector_type?: string
  power_kw: number
}

export function summarizeConnectors(connectors: ConnectorLike[]): string {
  if (connectors.length === 0) {
    return '—'
  }

  const counts = new Map<number, number>()
  for (const connector of connectors) {
    const powerKw = Math.round(connector.power_kw)
    counts.set(powerKw, (counts.get(powerKw) ?? 0) + 1)
  }

  return [...counts.entries()]
    .sort((left, right) => right[0] - left[0])
    .map(([powerKw, count]) => (count > 1 ? `${count}×${powerKw} kW` : `${powerKw} kW`))
    .join(', ')
}

export type ConnectorTypeGroup = {
  type: string
  count: number
}

/** Agrupa por tipo de conector (Type 2, CCS2, CHAdeMO…), como las tarjetas de REVE. */
export function groupConnectorsByType(connectors: ConnectorLike[]): ConnectorTypeGroup[] {
  const counts = new Map<string, number>()
  for (const connector of connectors) {
    const type = connector.connector_type?.trim() || 'Otro'
    counts.set(type, (counts.get(type) ?? 0) + 1)
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1])
    .map(([type, count]) => ({ type, count }))
}

export function formatPriceEurKwh(priceEurKwh: number): string {
  return `${priceEurKwh.toFixed(2)} €/kWh`
}

export function formatLivePriceLabel(priceEurKwh: number): string {
  return `${formatPriceEurKwh(priceEurKwh)} sin IVA`
}
