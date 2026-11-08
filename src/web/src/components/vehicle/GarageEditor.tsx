import { useState } from 'react'

import { useVehicleGarage } from '../../hooks/useVehicleProfile'
import {
  CAPACITY_MAX_KWH,
  CAPACITY_MIN_KWH,
  draftFromPreset,
  driverFactor,
  HOMOLOGATED_MAX_KWH_100,
  HOMOLOGATED_MIN_KWH_100,
  homologatedFromRange,
  MAX_GARAGE_VEHICLES,
  PEAK_DC_MAX_KW,
  PEAK_DC_MIN_KW,
  predictedKwhPer100km,
  VEHICLE_NAME_MAX,
  type GarageVehicle,
  type GarageVehicleDraft,
} from '../../vehicle/garage'
import { DEFAULT_VEHICLE_PRESET_ID, VEHICLE_PRESETS } from '../../vehicle/vehiclePresets'

const fmt = (value: number, digits = 1) => value.toLocaleString('es-ES', { maximumFractionDigits: digits })

type EditorTarget = { mode: 'new' } | { mode: 'edit'; vehicleId: string }

export function GarageEditor({ onClose }: { onClose: () => void }) {
  const { garage, selectVehicle, addVehicle, updateVehicle, removeVehicle } = useVehicleGarage()
  const [target, setTarget] = useState<EditorTarget | null>(null)
  const editing =
    target?.mode === 'edit' ? garage.vehicles.find((item) => item.id === target.vehicleId) ?? null : null

  if (target) {
    return (
      <VehicleForm
        key={target.mode === 'edit' ? target.vehicleId : 'new'}
        initial={editing ?? null}
        onCancel={() => setTarget(null)}
        onSave={(draft) => {
          if (editing) {
            updateVehicle(editing.id, draft)
          } else {
            addVehicle(draft)
          }
          setTarget(null)
        }}
      />
    )
  }

  return (
    <div className="garage">
      <ul className="garage__list">
        {garage.vehicles.map((vehicle) => {
          const active = vehicle.id === garage.activeVehicleId
          return (
            <li key={vehicle.id} className={`garage__item ${active ? 'garage__item--active' : ''}`.trim()}>
              <button
                type="button"
                className="garage__select"
                aria-pressed={active}
                onClick={() => selectVehicle(vehicle.id)}
              >
                <span className="garage__name">
                  {vehicle.name}
                  {vehicle.teslaMateLinked ? <span className="garage__tag">TeslaMate</span> : null}
                </span>
                <span className="garage__specs">
                  {fmt(vehicle.usableCapacityKwh)} kWh · {fmt(vehicle.homologatedKwhPer100km)} kWh/100 km homol. ·{' '}
                  {vehicle.peakDcKw} kW DC · previsto {fmt(predictedKwhPer100km(garage, vehicle))} kWh/100 km
                </span>
              </button>
              <div className="garage__item-actions">
                <button
                  type="button"
                  className="btn btn--ghost btn--compact"
                  onClick={() => setTarget({ mode: 'edit', vehicleId: vehicle.id })}
                >
                  Editar
                </button>
                {garage.vehicles.length > 1 && (
                  <button
                    type="button"
                    className="btn btn--ghost btn--compact"
                    aria-label={`Quitar ${vehicle.name}`}
                    onClick={() => removeVehicle(vehicle.id)}
                  >
                    Quitar
                  </button>
                )}
              </div>
            </li>
          )
        })}
      </ul>
      <div className="garage__actions">
        {garage.vehicles.length < MAX_GARAGE_VEHICLES && (
          <button type="button" className="btn btn--secondary" onClick={() => setTarget({ mode: 'new' })}>
            Añadir vehículo
          </button>
        )}
        <button type="button" className="btn btn--ghost" onClick={onClose}>
          Cerrar
        </button>
      </div>
      <DriverProfileFields />
    </div>
  )
}

function VehicleForm({
  initial,
  onSave,
  onCancel,
}: {
  initial: GarageVehicle | null
  onSave: (draft: GarageVehicleDraft) => void
  onCancel: () => void
}) {
  const [draft, setDraft] = useState<GarageVehicleDraft>(() =>
    initial
      ? { ...initial }
      : { ...draftFromPreset(DEFAULT_VEHICLE_PRESET_ID), name: '', basePresetId: null, teslaMateLinked: false },
  )
  const [rangeKm, setRangeKm] = useState('')
  const patch = (next: Partial<GarageVehicleDraft>) => setDraft((current) => ({ ...current, ...next }))
  const numberPatch = (key: 'usableCapacityKwh' | 'homologatedKwhPer100km' | 'peakDcKw', raw: string) => {
    // Vacío → NaN: el campo queda en blanco y `required` impide guardar.
    patch({ [key]: raw.trim() === '' ? Number.NaN : Number(raw.replace(',', '.')) })
  }
  const shown = (value: number) => (Number.isFinite(value) ? value : '')

  return (
    <form
      className="garage-form"
      onSubmit={(event) => {
        event.preventDefault()
        onSave(draft)
      }}
    >
      <p className="garage-form__title">{initial ? `Editar ${initial.name}` : 'Nuevo vehículo'}</p>

      <label className="field">
        <span className="field__label">Partir de un modelo (opcional)</span>
        <select
          value={draft.basePresetId ?? ''}
          onChange={(event) => {
            const presetId = event.target.value
            if (!presetId) {
              patch({ basePresetId: null })
              return
            }
            const fromPreset = draftFromPreset(presetId)
            setDraft((current) => ({
              ...fromPreset,
              name: current.name || fromPreset.name,
              teslaMateLinked: current.teslaMateLinked,
            }))
            setRangeKm('')
          }}
        >
          <option value="">Otro (datos de la ficha técnica)</option>
          {VEHICLE_PRESETS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span className="field__label">Nombre</span>
        <input
          type="text"
          required
          maxLength={VEHICLE_NAME_MAX}
          placeholder="p. ej. Kia EV3 (prueba)"
          value={draft.name}
          onChange={(event) => patch({ name: event.target.value })}
        />
      </label>

      <div className="garage-form__grid">
        <label className="field">
          <span className="field__label">Batería útil (kWh)</span>
          <input
            type="number"
            inputMode="decimal"
            min={CAPACITY_MIN_KWH}
            max={CAPACITY_MAX_KWH}
            step={0.1}
            required
            value={shown(draft.usableCapacityKwh)}
            onChange={(event) => numberPatch('usableCapacityKwh', event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field__label">Carga DC máx. (kW)</span>
          <input
            type="number"
            inputMode="numeric"
            min={PEAK_DC_MIN_KW}
            max={PEAK_DC_MAX_KW}
            step={1}
            required
            value={shown(draft.peakDcKw)}
            onChange={(event) => numberPatch('peakDcKw', event.target.value)}
          />
        </label>
        <label className="field">
          <span className="field__label">Consumo homologado (kWh/100 km)</span>
          <input
            type="number"
            inputMode="decimal"
            min={HOMOLOGATED_MIN_KWH_100}
            max={HOMOLOGATED_MAX_KWH_100}
            step={0.1}
            required
            value={shown(draft.homologatedKwhPer100km)}
            onChange={(event) => {
              numberPatch('homologatedKwhPer100km', event.target.value)
              setRangeKm('')
            }}
          />
        </label>
        <label className="field">
          <span className="field__label">…o autonomía WLTP (km)</span>
          <input
            type="number"
            inputMode="numeric"
            min={50}
            max={1200}
            step={1}
            placeholder="calcula el consumo"
            value={rangeKm}
            onChange={(event) => {
              setRangeKm(event.target.value)
              const derived = homologatedFromRange(draft.usableCapacityKwh, Number(event.target.value))
              if (derived != null) patch({ homologatedKwhPer100km: derived })
            }}
          />
        </label>
      </div>
      <p className="vehicle-panel__hint">
        Usa la misma fuente (WLTP de la ficha) para todos los coches que compares: el perfil de conducción
        corrige la diferencia con tu consumo real.
      </p>

      <label className="field field--checkbox">
        <input
          type="checkbox"
          checked={draft.teslaMateLinked}
          onChange={(event) => patch({ teslaMateLinked: event.target.checked })}
        />
        <span>Es el coche de TeslaMate (SOC y posición en vivo)</span>
      </label>

      <div className="garage__actions">
        <button type="submit" className="btn btn--primary">
          Guardar
        </button>
        <button type="button" className="btn btn--ghost" onClick={onCancel}>
          Cancelar
        </button>
      </div>
    </form>
  )
}

function DriverProfileFields() {
  const { garage, setDriverProfile } = useVehicleGarage()
  const driver = garage.driver
  const factor = driverFactor(garage)
  const [referenceVehicleId, setReferenceVehicleId] = useState(
    driver?.referenceVehicleId ?? garage.vehicles.find((item) => item.teslaMateLinked)?.id ?? garage.activeVehicleId,
  )
  const [measured, setMeasured] = useState(driver ? String(driver.measuredKwhPer100km) : '')
  const reference = garage.vehicles.find((item) => item.id === referenceVehicleId)

  return (
    <fieldset className="garage-driver">
      <legend>Tu perfil de conducción</legend>
      <p className="vehicle-panel__hint">
        Indica tu consumo real medio con un coche que conozcas. Se compara con su homologado y ese factor se
        aplica al resto del garaje.
      </p>
      <div className="garage-form__grid">
        <label className="field">
          <span className="field__label">Coche de referencia</span>
          <select value={referenceVehicleId} onChange={(event) => setReferenceVehicleId(event.target.value)}>
            {garage.vehicles.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span className="field__label">Consumo real (kWh/100 km)</span>
          <input
            type="number"
            inputMode="decimal"
            min={HOMOLOGATED_MIN_KWH_100}
            max={HOMOLOGATED_MAX_KWH_100}
            step={0.1}
            placeholder={reference ? fmt(reference.homologatedKwhPer100km) : ''}
            value={measured}
            onChange={(event) => setMeasured(event.target.value)}
          />
        </label>
      </div>
      <p className="vehicle-panel__hint" aria-live="polite">
        {driver
          ? `Factor actual ×${fmt(factor, 2)} (${fmt(driver.measuredKwhPer100km)} real ÷ homologado del coche de referencia).`
          : 'Sin perfil: se planifica con el consumo homologado (×1).'}
      </p>
      <div className="garage__actions">
        <button
          type="button"
          className="btn btn--secondary"
          disabled={!(Number(measured.replace(',', '.')) > 0)}
          onClick={() =>
            setDriverProfile({
              referenceVehicleId,
              measuredKwhPer100km: Number(measured.replace(',', '.')),
            })
          }
        >
          Aplicar perfil
        </button>
        {driver && (
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => {
              setDriverProfile(null)
              setMeasured('')
            }}
          >
            Quitar perfil
          </button>
        )}
      </div>
    </fieldset>
  )
}
