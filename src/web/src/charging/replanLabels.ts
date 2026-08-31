import type { ReplanReason } from './activeTrip'

const REPLAN_REASON_LABELS: Record<ReplanReason, string> = {
  manual: 'manual',
  auto_follow: 'auto',
  stop_completed: 'tras parada',
}

export function replanReasonLabel(reason: ReplanReason | null | undefined): string | null {
  if (!reason) {
    return null
  }
  return REPLAN_REASON_LABELS[reason]
}
