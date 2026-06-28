import type { ExternalUserComment } from '../api/types'

type StationExternalReviewsProps = {
  ratingAvg?: number | null
  ratingCount?: number | null
  comments?: ExternalUserComment[]
  className?: string
  compact?: boolean
}

function formatStars(rating: number): string {
  const rounded = Math.max(1, Math.min(5, Math.round(rating)))
  return `${'★'.repeat(rounded)}${'☆'.repeat(5 - rounded)}`
}

function formatCommentDate(value?: string | null): string | null {
  if (!value) {
    return null
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return null
  }
  return date.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function StationExternalReviews({
  ratingAvg,
  ratingCount,
  comments = [],
  className = 'station-external-reviews',
  compact = false,
}: StationExternalReviewsProps) {
  const hasRating = ratingAvg != null && !Number.isNaN(ratingAvg) && (ratingCount ?? 0) > 0
  const visibleComments = comments.filter((item) => item.comment || item.checkin_label)
  if (!hasRating && visibleComments.length === 0) {
    return null
  }

  return (
    <div className={className}>
      {hasRating && (
        <p className="station-external-reviews__rating">
          <span className="station-external-reviews__stars" aria-hidden="true">
            {formatStars(ratingAvg!)}
          </span>
          <span className="station-external-reviews__score">
            {ratingAvg!.toFixed(1)} · {ratingCount} valoración{ratingCount === 1 ? '' : 'es'}
          </span>
          <span className="station-external-reviews__source">Open Charge Map</span>
        </p>
      )}
      {!compact && visibleComments.length > 0 && (
        <ul className="station-external-reviews__comments" aria-label="Comentarios de usuarios">
          {visibleComments.slice(0, 3).map((item, index) => (
            <li key={`${item.created_at ?? 'comment'}-${index}`} className="station-external-reviews__comment">
              {item.rating != null && (
                <span className="station-external-reviews__comment-rating">{item.rating}/5</span>
              )}
              {item.comment && <span>{item.comment}</span>}
              {!item.comment && item.checkin_label && <span>{item.checkin_label}</span>}
              <span className="station-external-reviews__comment-meta">
                {item.username ? item.username : 'Usuario'}
                {item.created_at && formatCommentDate(item.created_at)
                  ? ` · ${formatCommentDate(item.created_at)}`
                  : ''}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
