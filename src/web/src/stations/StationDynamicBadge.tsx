import {
  dynamicStatusClassName,
  formatDynamicStatusLabel,
  hasDynamicInfo,
} from './dynamicDisplay'
import { formatLivePriceLabel } from './connectorDisplay'

type StationDynamicBadgeProps = {
  status?: string | null
  priceEurKwh?: number | null
  className?: string
}

export function StationDynamicBadge({
  status,
  priceEurKwh,
  className = 'station-dynamic',
}: StationDynamicBadgeProps) {
  if (!hasDynamicInfo(status, priceEurKwh)) {
    return null
  }

  return (
    <p className={className}>
      {status ? (
        <span className={`station-dynamic__status ${dynamicStatusClassName(status)}`}>
          {formatDynamicStatusLabel(status)}
        </span>
      ) : null}
      {status && priceEurKwh != null && !Number.isNaN(priceEurKwh) ? (
        <span className="station-dynamic__sep"> · </span>
      ) : null}
      {priceEurKwh != null && !Number.isNaN(priceEurKwh) ? (
        <span className="station-dynamic__price">{formatLivePriceLabel(priceEurKwh)}</span>
      ) : null}
    </p>
  )
}
