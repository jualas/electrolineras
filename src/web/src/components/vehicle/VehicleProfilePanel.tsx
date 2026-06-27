import type { VehicleProfile } from '../../vehicle/vehicleProfile'
import type { TerrainFactorId, VehiclePresetId } from '../../vehicle/vehiclePresets'
import { VehicleProfileFields } from './VehicleProfileFields'

type VehicleProfilePanelProps = {
  profile: VehicleProfile
  onPresetChange: (presetId: VehiclePresetId) => void
  onSocChange: (socPercent: number) => void
  onConsumptionChange: (consumptionWhPerKm: number) => void
  onTerrainChange: (terrainFactorId: TerrainFactorId) => void
  variant?: 'full' | 'compact' | 'advanced'
  className?: string
}

export function VehicleProfilePanel({
  profile,
  onPresetChange,
  onSocChange,
  onConsumptionChange,
  onTerrainChange,
  variant = 'full',
  className,
}: VehicleProfilePanelProps) {
  const compact = variant === 'compact'
  const advanced = variant === 'advanced'

  if (advanced) {
    return (
      <VehicleProfileFields
        profile={profile}
        onPresetChange={onPresetChange}
        onSocChange={onSocChange}
        onConsumptionChange={onConsumptionChange}
        onTerrainChange={onTerrainChange}
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
        onPresetChange={onPresetChange}
        onSocChange={onSocChange}
        onConsumptionChange={onConsumptionChange}
        onTerrainChange={onTerrainChange}
        variant={variant}
      />
    </section>
  )
}
