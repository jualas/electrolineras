import { useEffect } from 'react'

import { stationLabel } from '../api/chargingPlan'
import type { ChargingPlanStopResult, Station } from '../api/types'
import {
  classificationClassName,
  formatClassificationLabel,
} from '../charging/classificationDisplay'
import { StationNavActions } from '../components/navigation/StationNavActions'
import { ConnectorChips } from '../stations/ConnectorChips'
import { StationDynamicBadge } from '../stations/StationDynamicBadge'
import { StationExternalReviews } from '../stations/StationExternalReviews'

type ChargingStopListProps = {
  stops: ChargingPlanStopResult[]
  selectedStationId?: string | null
  onSelectStation?: (station: Station | null) => void
  ariaLabel: string
  distanceLabel?: (item: ChargingPlanStopResult) => string
  showRouteDeviation?: boolean
}

export function ChargingStopList({
  stops,
  selectedStationId,
  onSelectStation,
  ariaLabel,
  distanceLabel,
  showRouteDeviation = true,
}: ChargingStopListProps) {
  useEffect(() => {
    if (!selectedStationId) {
      return
    }
    const element = document.querySelector(`[data-station-id="${selectedStationId}"]`)
    element?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
  }, [selectedStationId])

  if (stops.length === 0) {
    return null
  }

  return (
    <ol className="route-results" aria-label={ariaLabel}>
      {stops.map((item, index) => (
        <li key={`${item.station.id}-${index}`} className="route-result-card" data-station-id={item.station.id}>
          <button
            type="button"
            className={`route-result ${selectedStationId === item.station.id ? 'route-result--active' : ''}`}
            onClick={() => onSelectStation?.(item.station)}
          >
            <div className="route-result__head">
              <span className="route-result__rank">{index + 1}</span>
              <div>
                <p className="route-result__title">{stationLabel(item.station)}</p>
                <p className="route-result__operator">{item.station.operator ?? '—'}</p>
                {item.station.location.address && (
                  <p className="route-result__address">{item.station.location.address}</p>
                )}
              </div>
            </div>
            <span className={classificationClassName(item.classification, 'charging-class')}>
              {formatClassificationLabel(item.classification)} · {item.soc_arrival_pct.toFixed(0)} % SOC
            </span>
            {showRouteDeviation && (
              <p className="route-result__meta">
                +{item.deviation_km.toFixed(1)} km desvío
                {item.extra_minutes > 0 && <> · +{item.extra_minutes.toFixed(0)} min</>}
              </p>
            )}
            <ConnectorChips connectors={item.station.connectors} />
            <StationDynamicBadge
              status={item.station.dynamic_status}
              priceEurKwh={item.station.dynamic_price_eur_kwh}
              className="route-result__dynamic station-dynamic"
            />
            <StationExternalReviews
              ratingAvg={item.station.external_rating_avg}
              ratingCount={item.station.external_rating_count}
              comments={item.station.external_comments}
              compact
            />
            <p className="route-result__dist">
              {distanceLabel
                ? distanceLabel(item)
                : `A ${item.distance_from_origin_km.toFixed(1)} km desde el origen`}
            </p>
          </button>
          <StationNavActions
            lat={item.station.location.lat}
            lon={item.station.location.lon}
            label={stationLabel(item.station)}
            compact
          />
        </li>
      ))}
    </ol>
  )
}
