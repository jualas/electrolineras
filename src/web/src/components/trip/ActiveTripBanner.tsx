type ActiveTripBannerProps = {
  destinationLabel: string
  waypointCount?: number
  gpsEnabled: boolean
  gpsActive: boolean
  gpsLoading: boolean
  showGpsToggle: boolean
  onGpsEnabledChange: (enabled: boolean) => void
  onEndTrip?: () => void
}

export function ActiveTripBanner({
  destinationLabel,
  waypointCount = 0,
  gpsEnabled,
  gpsActive,
  gpsLoading,
  showGpsToggle,
  onGpsEnabledChange,
  onEndTrip,
}: ActiveTripBannerProps) {
  return (
    <div className="active-trip-banner" role="status">
      <div className="active-trip-banner__main">
        <strong>Viaje en curso</strong>
        <span>
          → {destinationLabel}
          {waypointCount > 0 ? ` · ${waypointCount} vía${waypointCount === 1 ? '' : 's'}` : ''}
        </span>
      </div>
      <div className="active-trip-banner__actions">
        {showGpsToggle ? (
          <label className="field field--checkbox active-trip-banner__gps">
            <input
              type="checkbox"
              checked={gpsEnabled}
              onChange={(event) => onGpsEnabledChange(event.target.checked)}
            />
            <span>
              GPS móvil
              {gpsEnabled && (
                <span className="active-trip-banner__gps-state">
                  {gpsLoading ? ' · localizando…' : gpsActive ? ' · activo' : ' · sin señal'}
                </span>
              )}
            </span>
          </label>
        ) : null}
        {onEndTrip ? (
          <button type="button" className="btn btn--ghost btn--compact" onClick={onEndTrip}>
            Finalizar
          </button>
        ) : null}
      </div>
    </div>
  )
}
