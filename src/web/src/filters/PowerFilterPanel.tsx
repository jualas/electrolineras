import {
  CUSTOM_KW_MAX,
  CUSTOM_KW_MIN,
  formatPowerRange,
  POWER_PRESETS,
  POWER_PROFILES,
  type PowerFilter,
  type PowerPresetId,
} from './powerPresets'

type PowerFilterPanelProps = {
  filter: PowerFilter
  onPresetChange: (presetId: PowerPresetId) => void
  onCustomRangeChange: (minKw: number, maxKw: number) => void
}

const CHIP_PRESETS = POWER_PRESETS.filter((preset) => preset.id !== 'custom' && preset.id !== 'all')

export function PowerFilterPanel({
  filter,
  onPresetChange,
  onCustomRangeChange,
}: PowerFilterPanelProps) {
  const customMin = filter.minKw ?? CUSTOM_KW_MIN
  const customMax = filter.maxKw ?? CUSTOM_KW_MAX

  return (
    <details className="panel filters-panel collapsible-panel">
      <summary className="collapsible-panel__summary" id="filters-heading">
        <span className="collapsible-panel__title">Potencia</span>
        <span className="collapsible-panel__meta">{formatPowerRange(filter)}</span>
      </summary>

      <div className="collapsible-panel__body">
        <div className="profile-row" role="group" aria-label="Perfil de búsqueda">
          {POWER_PROFILES.map((profile) => (
            <button
              key={profile.id}
              type="button"
              className={`profile-chip ${filter.presetId === profile.presetId ? 'profile-chip--active' : ''}`}
              onClick={() => onPresetChange(profile.presetId)}
            >
              {profile.label}
            </button>
          ))}
        </div>

        <div className="chip-row" role="list" aria-label="Presets de potencia">
          {CHIP_PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              role="listitem"
              className={`chip ${filter.presetId === preset.id ? 'chip--active' : ''}`}
              onClick={() => onPresetChange(preset.id)}
              aria-pressed={filter.presetId === preset.id}
            >
              {preset.shortLabel}
            </button>
          ))}
          <button
            type="button"
            role="listitem"
            className={`chip ${filter.presetId === 'custom' ? 'chip--active' : ''}`}
            onClick={() => onPresetChange('custom')}
            aria-pressed={filter.presetId === 'custom'}
          >
            Personalizado
          </button>
          <button
            type="button"
            role="listitem"
            className={`chip ${filter.presetId === 'all' ? 'chip--active' : ''}`}
            onClick={() => onPresetChange('all')}
            aria-pressed={filter.presetId === 'all'}
          >
            Todo
          </button>
        </div>

        {filter.presetId === 'custom' && (
          <div className="custom-range" aria-label="Rango personalizado kW">
            <div className="custom-range__row">
              <label htmlFor="power-min">Mín kW</label>
              <input
                id="power-min"
                type="range"
                min={CUSTOM_KW_MIN}
                max={CUSTOM_KW_MAX}
                step={1}
                value={customMin}
                onChange={(event) =>
                  onCustomRangeChange(Number(event.target.value), customMax)
                }
              />
              <span className="custom-range__value">{customMin}</span>
            </div>
            <div className="custom-range__row">
              <label htmlFor="power-max">Máx kW</label>
              <input
                id="power-max"
                type="range"
                min={CUSTOM_KW_MIN}
                max={CUSTOM_KW_MAX}
                step={1}
                value={customMax}
                onChange={(event) =>
                  onCustomRangeChange(customMin, Number(event.target.value))
                }
              />
              <span className="custom-range__value">{customMax}</span>
            </div>
          </div>
        )}
      </div>
    </details>
  )
}
