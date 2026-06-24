export function PowerFilterPanel() {
  return (
    <section className="panel filters-panel" aria-labelledby="filters-heading">
      <h2 id="filters-heading">Potencia</h2>
      <p className="panel-hint">Presets — implementación completa en #6033</p>
      <div className="chip-row" role="list">
        <span className="chip chip--active" role="listitem">Viaje ≥100</span>
        <span className="chip" role="listitem">Lento AC</span>
        <span className="chip" role="listitem">Semi-rápido</span>
        <span className="chip" role="listitem">Ultrarrápido</span>
      </div>
    </section>
  )
}
