# Estado del proyecto

Última actualización: 2026-06-23

## Fase actual

**Definición de producto y fuentes de datos.** Visión acordada; feeds oficiales verificados; repositorio con commit inicial.

## Visión acordada

- App **web** (usable en Tesla) con mapa de electrolineras en la **península ibérica**.
- Filtro principal: **potencia de carga (kW)**.
- Datos base: publicación oficial del **gobierno español** (NAP DGT) + **MOBI.E** (Portugal).
- Futuro: ampliar a UE vía NAP de cada país.

## Verificaciones técnicas

| Feed | Estado | Notas |
|------|--------|-------|
| NAP España (DATEX II) | OK | XML accesible, actualizado hoy |
| NAP Portugal (MOBI.E) | OK | XML ~180 MB; requiere descarga por streaming |
| REVE (dinámico) | Pendiente | Sin API pública documentada |

## Roadmap

### Fase 0 — Definición ✅ completada

- [x] Crear repositorio Git
- [x] Documentar visión y fuentes oficiales
- [x] Verificar acceso a feeds DATEX II (ES + PT)
- [x] Commit inicial del repo
- [x] Crear proyecto en TaskBoard (opcional)

### Fase 1 — MVP datos + mapa

- [ ] Parser DATEX II para España
- [ ] Parser DATEX II para Portugal
- [ ] Modelo normalizado + export GeoJSON
- [ ] **Búsqueda en ruta:** corredor + filtro ≥ kW + anti-retroceso (caso Granada→Cartagena)
- [ ] **Búsqueda en ciudad:** potencia + ubicación (GPS / dirección / zona mapa) + acceso
- [ ] Mapa web móvil con resultados en ruta y en ciudad
- [ ] API REST con filtros bbox / kW / radio / corredor de ruta

### Fase 2 — Dinámico y UX Tesla

- [ ] Investigar acceso datos REVE (disponibilidad, precio)
- [ ] UI optimizada para navegador Tesla
- [ ] Enlaces a Google Maps / copiar coordenadas

### Fase 3 — Unión Europea

- [ ] Inventariar NAPs UE (NAPCORE)
- [ ] Conector genérico DATEX II reutilizable

## Decisiones tomadas

| Tema | Decisión |
|------|----------|
| Alcance geográfico inicial | España + Portugal |
| Fuente principal España | NAP DGT (DATEX II) |
| Fuente principal Portugal | MOBI.E NAP (DATEX II) |
| Cliente MVP | Web / PWA (no app nativa Tesla) |
| Filtro diferenciador | Potencia de carga (kW) |
| Radio default modo ciudad | **1 km** |

## Navegación y envío al coche

Documentado en [`docs/NAVIGATION.md`](docs/NAVIGATION.md).

| Necesidad | Enfoque acordado (borrador) |
|-----------|----------------------------|
| Enviar 1 parada | MVP: enlace Google/Apple Maps; v2: Tesla Fleet API |
| Ruta multi-parada | Planificador propio + export Google Maps |
| Ruta completa al nav Tesla | No en v1; parada a parada si Fleet API |
| Uso en Tesla | Web optimizada para navegador del coche |

## Decisiones pendientes

| Tema | Opciones |
|------|----------|
| Almacenamiento | SQLite vs PostGIS |
| Frontend | React vs Svelte vs vanilla |
| Filtro potencia | Por sitio (max) vs por conector |
| Hosting | VPS propio vs cloud estático |
| Integración Tesla | Solo enlaces vs Fleet API en v2 |
| Planificador de ruta | Solo export externo vs SOC/consumo en v3 |
| Filtros potencia/acceso | Ver [`FILTERS.md`](FILTERS.md) — presets + heurísticas CC |

## Notas

REVE ya cubre gran parte del mercado español con datos dinámicos, pero no sustituye nuestro objetivo: **península unificada + filtro por potencia + neutralidad** respecto a Tesla u otros operadores.
