# Electrolineras de la Península Ibérica

Mapa unificado de **puntos de recarga de vehículos eléctricos** en España y Portugal, con filtro por potencia y datos agregados de fuentes oficiales.

## Problema que resolvemos

Hoy la información está dispersa y el **navegador del coche** (p. ej. Tesla) elige paradas que en la práctica son malas:

- Desvíos largos a Superchargers “de paso” cuando ya vas orientado al destino.
- Paradas que obligan a **salir, cambiar de sentido y volver a incorporarse** (ej. Granada → Cartagena con parada en Cullar).

**Caso típico:** desde Granada con 44 % hacia Cartagena, buscar en segundos cargadores **≥ 100 kW en la carretera**, en sentido de marcha, con el menor desvío posible — desde el móvil (web o Android).

Detalle del caso de uso: [`docs/ROUTE_CORRIDOR_SEARCH.md`](docs/ROUTE_CORRIDOR_SEARCH.md).

## Objetivo del producto

**Aplicación web móvil** (y opcionalmente Android) que permita:

1. **Búsqueda rápida en ruta:** cargadores ≥ X kW **en el corredor de la carretera** hacia un destino, sin paradas en sentido contrario ni desvíos absurdos.
2. **Mapa peninsular** con filtro por potencia y operador (datos oficiales NAP).

En una fase posterior, ampliar a **otros países de la UE** cuando publiquen su NAP (reglamento AFIR).

## Fuentes de datos principales

| País | Fuente oficial | Formato | Actualización |
|------|----------------|---------|---------------|
| España (estático) | [NAP DGT / MITECO](https://nap.dgt.es/dataset/puntos-de-recarga-electrica-para-vehiculos) | DATEX II v3 | ~24 h |
| España (dinámico) | [REVE / mapareve.es](https://www.mapareve.es/) (Red Eléctrica) | Web + app; protocolo OCPI entre operadores | Tiempo real |
| Portugal | [MOBI.E NAP](https://pgm.mobie.pt/integration/nap/evChargingInfra) | DATEX II | Tiempo real |

Detalle técnico en [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Clientes previstos

1. **Web / PWA** — mapa interactivo en móvil y escritorio (MVP).
2. **Navegador Tesla** — misma web optimizada para pantalla del coche (sin instalar app nativa).
3. **Futuro** — app nativa o integración con planificadores de ruta si aporta valor.

> Tesla no permite sustituir su navegación nativa por apps de terceros. La vía realista es una **web usable en el coche** o enviar destinos al navegador del vehículo.

## Documentación

### Producto y diseño

- [`docs/VISION.md`](docs/VISION.md) — visión, funcionalidades y fases
- [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) — URLs, formatos y estrategia de ingestión
- [`docs/FILTERS.md`](docs/FILTERS.md) — potencia elegible y acceso público
- [`docs/NAVIGATION.md`](docs/NAVIGATION.md) — envío de paradas y rutas al coche (Tesla, Google Maps)
- [`docs/ROUTE_CORRIDOR_SEARCH.md`](docs/ROUTE_CORRIDOR_SEARCH.md) — búsqueda en corredor de ruta
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitectura propuesta

### Seguimiento

- [`docs/STATUS.md`](docs/STATUS.md) — fase actual, roadmap con IDs de tarea
- [`TASKBOARD.md`](TASKBOARD.md) — espejo del backlog en [TaskBoard](https://kanban.jualas.es) (proyecto `id=7`)

## Estructura del repo

```
Electrolineras/
├── data/          # Datos procesados (raw voluminoso en .gitignore)
├── docs/          # Documentación del proyecto
├── scripts/       # Ingestión DATEX II, normalización, actualización
└── src/           # Backend + frontend web
```

## Estado

**Fase 1 — MVP datos + mapa** (Fase 0 completada). Siguiente tarea: [#6022 Bootstrap](TASKBOARD.md#task-6022).

Detalle del avance: [`docs/STATUS.md`](docs/STATUS.md) · backlog completo: [`TASKBOARD.md`](TASKBOARD.md)
