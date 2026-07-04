type ReplanOnRouteBarProps = {
  destinationLabel: string
  originLabel: string
  socPercent: number
  socSourceLabel?: string
  loading: boolean
  autoFollow: boolean
  onAutoFollowChange: (value: boolean) => void
  onReplan: () => void
  onRefreshOrigin?: () => void
  canReplan: boolean
  lastUpdatedAt?: number | null
  showAutoFollow?: boolean
}

function formatUpdatedAt(timestamp: number | null | undefined): string | null {
  if (!timestamp) {
    return null
  }
  return new Date(timestamp).toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function ReplanOnRouteBar({
  destinationLabel,
  originLabel,
  socPercent,
  socSourceLabel,
  loading,
  autoFollow,
  onAutoFollowChange,
  onReplan,
  onRefreshOrigin,
  canReplan,
  lastUpdatedAt,
  showAutoFollow = true,
}: ReplanOnRouteBarProps) {
  const updatedLabel = formatUpdatedAt(lastUpdatedAt)

  return (
    <section className="replan-bar" aria-label="Replanificación en marcha">
      <div className="replan-bar__header">
        <h3 className="replan-bar__title">En marcha</h3>
        {updatedLabel ? (
          <span className="replan-bar__updated" role="status">
            Actualizado {updatedLabel}
          </span>
        ) : null}
      </div>

      <dl className="replan-bar__facts">
        <div>
          <dt>Destino</dt>
          <dd>{destinationLabel}</dd>
        </div>
        <div>
          <dt>Desde aquí</dt>
          <dd>{originLabel}</dd>
        </div>
        <div>
          <dt>SOC ahora</dt>
          <dd>
            {socPercent.toFixed(0)} %
            {socSourceLabel ? ` · ${socSourceLabel}` : ''}
          </dd>
        </div>
      </dl>

      <div className="replan-bar__actions">
        <button
          type="button"
          className="btn btn--primary replan-bar__replan"
          disabled={loading || !canReplan}
          onClick={onReplan}
        >
          {loading ? 'Recalculando…' : 'Recalcular desde aquí'}
        </button>
        {onRefreshOrigin ? (
          <button
            type="button"
            className="btn btn--secondary"
            disabled={loading}
            onClick={onRefreshOrigin}
          >
            Actualizar posición
          </button>
        ) : null}
      </div>

      {showAutoFollow ? (
        <label className="field field--checkbox replan-bar__follow">
          <input
            type="checkbox"
            checked={autoFollow}
            onChange={(event) => onAutoFollowChange(event.target.checked)}
            disabled={loading}
          />
          <span>Seguimiento en marcha (recalcular al moverte o cambiar SOC)</span>
        </label>
      ) : null}

      <p className="replan-bar__hint">
        Usa tu posición actual y el SOC de ahora para un nuevo plan de paradas hasta el destino.
      </p>
    </section>
  )
}
