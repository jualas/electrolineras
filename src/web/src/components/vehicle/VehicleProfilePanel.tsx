import type { VehicleProfile } from '../../vehicle/vehicleProfile'
import { VehicleProfileFields } from './VehicleProfileFields'

type VehicleProfilePanelProps = {
  profile: VehicleProfile
  onSocChange: (socPercent: number) => void
  variant?: 'full' | 'compact' | 'advanced'
  className?: string
  socReadOnly?: boolean
  socSourceLabel?: string
}

export function VehicleProfilePanel({
  profile,
  onSocChange,
  variant = 'full',
  className,
  socReadOnly,
  socSourceLabel,
}: VehicleProfilePanelProps) {
  const compact = variant === 'compact'
  const advanced = variant === 'advanced'

  if (advanced) {
    return (
      <VehicleProfileFields
        profile={profile}
        onSocChange={onSocChange}
        variant="advanced"
      />
    )
  }

  return (
    <section
      className={`panel vehicle-panel ${compact ? 'vehicle-panel--compact' : ''} ${className ?? ''}`.trim()}
      aria-labelledby="vehicle-heading"
    >
      <h2 id="vehicle-heading">{compact ? 'Tu vehículo' : 'Vehículo'}</h2>
      <VehicleProfileFields
        profile={profile}
        onSocChange={onSocChange}
        variant={variant}
        socReadOnly={socReadOnly}
        socSourceLabel={socSourceLabel}
      />
    </section>
  )
}
