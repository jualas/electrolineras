export type ChargingClassification = 'safe' | 'adjusted' | 'critical' | 'unreachable'

const LABELS: Record<ChargingClassification, string> = {
  safe: 'Segura',
  adjusted: 'Ajustada',
  critical: 'Crítica',
  unreachable: 'Fuera de alcance',
}

export function formatClassificationLabel(classification: ChargingClassification): string {
  return LABELS[classification] ?? classification
}

export function classificationClassName(
  classification: ChargingClassification,
  prefix = 'charging-class',
): string {
  return `${prefix} ${prefix}--${classification}`
}
