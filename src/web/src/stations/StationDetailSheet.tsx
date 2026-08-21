import type { TappedStationInfo } from '../map/stationTapInfo'
import { StationDynamicBadge } from './StationDynamicBadge'
import { StationExternalReviews } from './StationExternalReviews'
import { StationNavActions } from '../components/navigation/StationNavActions'

type StationDetailSheetProps = {
  info: TappedStationInfo | null
  onClose: () => void
}

export function StationDetailSheet({ info, onClose }: StationDetailSheetProps) {
  if (!info) {
    return null
  }

  return (
    <div className="station-detail-sheet" role="dialog" aria-label={info.name}>
      <button
        type="button"
        className="station-detail-sheet__handle"
        onClick={onClose}
        aria-label="Cerrar ficha de estación"
      />
      <div className="station-detail-sheet__content">
        <div className="station-detail-sheet__header">
          <div>
            <h2 className="station-detail-sheet__name">{info.name}</h2>
            {info.operator && <p className="station-detail-sheet__operator">{info.operator}</p>}
          </div>
          <button
            type="button"
            className="station-detail-sheet__close"
            onClick={onClose}
            aria-label="Cerrar"
          >
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.8}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <p className="station-detail-sheet__connectors">{info.connectorSummary}</p>
        <StationDynamicBadge
          status={info.dynamicStatus}
          priceEurKwh={info.dynamicPriceEurKwh}
          className="station-detail-sheet__dynamic station-dynamic"
        />
        {info.address && <p className="station-detail-sheet__address">{info.address}</p>}
        <StationExternalReviews
          ratingAvg={info.ratingAvg}
          ratingCount={info.ratingCount}
          comments={info.comments}
          compact
        />
        <div className="station-detail-sheet__nav">
          <StationNavActions lat={info.lat} lon={info.lon} label={info.name} />
        </div>
      </div>
    </div>
  )
}
