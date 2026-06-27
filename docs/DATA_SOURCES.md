# Fuentes de datos

## España — NAP DGT / MITECO (obligatoria por ley)

La **Ley 7/2021** exige que el Gobierno publique la información de puntos de recarga a través del **Punto de Acceso Nacional (NAP)** gestionado por la DGT.

### Metadatos

- Portal: https://nap.dgt.es/dataset/puntos-de-recarga-electrica-para-vehiculos
- Propietario: MITECO
- Formato: **DATEX II v3** (estándar europeo)
- Licencia: libre y gratuita
- Frecuencia: **actualización diaria (~24 h)**

### Feed XML verificado

```
https://infocar.dgt.es/datex2/v3/miterd/EnergyInfrastructureTablePublication/electrolineras.xml
```

Comprobado en junio 2026: responde HTTP 200, XML válido, `publicationTime` reciente.

### Campos relevantes (DATEX II Energy Infrastructure)

- Ubicación (coordenadas, dirección)
- Operador / CPO
- Tipo de conector, modo de carga
- **Potencia y voltaje** por punto
- Horarios, métodos de pago, servicios cercanos (restaurante, hotel…)
- Accesibilidad

Documentación del esquema: https://docs.datex2.eu/levels/mastering/energy/

---

## España — REVE (Red Eléctrica / dinámico)

Mapa oficial con información **en tiempo real** (disponibilidad, precio).

- Web: https://www.mapareve.es/
- Info: https://www.ree.es/es/transicion-ecologica/electrificacion/reve-puntos-de-recarga
- ~25.600+ puntos (2025), ~80 % del mercado y creciendo

### Qué aporta respecto al NAP

| NAP (DGT) | REVE (Red Eléctrica) |
|-----------|----------------------|
| Estático + actualización diaria | Disponibilidad en tiempo real |
| Todos los puntos remitidos al MITECO | Enfoque en públicos con datos dinámicos (≥ 43 kW obligatorio) |
| Estándar DATEX II para terceros | Mapa/app REVE; intercambio CPO↔SGV vía **OCPI** |

### Acceso para desarrolladores (actualizado Fase 2 — jun 2026)

El frontend de [mapareve.es](https://www.mapareve.es/) consume una **API REST pública de lectura** (sin documentación formal para terceros):

| Endpoint | Método | Uso |
|----------|--------|-----|
| `/api/public/v1/stats` | GET | Contadores agregados |
| `/api/public/v1/cpos` | GET | Operadores |
| `/api/public/v1/markers` | POST | Clusters/marcadores por bbox + zoom |
| `/api/public/v1/locations` | POST | Listado paginado con detalle EVSE |
| `/api/public/v1/locations/{id}` | GET | Ficha de emplazamiento |

Base URL: `https://www.mapareve.es/api/public/v1`

Implementación en este repo: `src/ingest/reve_client.py`, sync en `src/ingest/reve_sync.py`. Ver [`PHASE2.md`](PHASE2.md).

**Precauciones:** respetar términos REE/MITECO; sync con cron espaciado (2–4 h); User-Agent identificable; no abusar del servicio público.

El acceso **OCPI directo al SGV** sigue reservado a CPOs registrados en el [portal de clientes REE](https://www.portalclientes.ree.es/).

Normativa de referencia: Resolución SEE nov 2024 (procedimiento SGV), BOE abril 2025 (remisión información dinámica).

---

## Portugal — MOBI.E (NAP)

La red nacional MOBI.E agrega operadores portugueses. Publica feeds NAP en DATEX II.

### Feeds verificados

| Recurso | URL |
|---------|-----|
| Infraestructura (estático) | https://pgm.mobie.pt/integration/nap/evChargingInfra |
| Estado en tiempo real | https://pgm.mobie.pt/integration/nap/evActualStatus |

Comprobado junio 2026: `evChargingInfra` responde 200 (XML grande, ~180 MB).

Entidad agregadora: **EADME** (Entidade Agregadora de Dados para a Mobilidade Eléctrica).  
Protocolos admitidos: DATEX II y OCPI 2.2 / 2.2.1.

---

## Futuro — resto de la UE

El reglamento **AFIR** (2025/655) obliga a estados miembros a publicar datos de infraestructura de recarga accesible al público. Cada país debe tener un **NAP** con formatos interoperables (DATEX II u OCPI).

Recursos:

- NAPCORE: https://napcore.eu/
- Lista UE: https://transport.ec.europa.eu/transport-themes/smart-mobility/road/its-directive-and-action-plan/national-access-points_en

Estrategia: diseñar un **conector por formato** (DATEX II, OCPI) y un **modelo normalizado interno**, no un conector por país.

---

## Esquema normalizado propuesto (borrador)

Cada **punto de recarga** (EVSE) en nuestro modelo:

```json
{
  "id": "es-dgt-D3WNGNOZOHYNQJ9SFOJK-001",
  "source": "es-nap-dgt",
  "country": "ES",
  "site_name": "Estación Example",
  "operator": "Ionity",
  "location": { "lat": 40.42, "lon": -3.70, "address": "..." },
  "connectors": [
    {
      "type": "CCS2",
      "power_kw": 350,
      "voltage_v": 800,
      "current_a": null
    }
  ],
  "max_power_kw": 350,
  "access": "public",
  "payment_methods": ["card", "app"],
  "opening_hours": "...",
  "dynamic": {
    "status": "available",
    "price_eur_kwh": null,
    "updated_at": null
  },
  "raw_ref": "D3WNGNOZOHYNQJ9SFOJK"
}
```

Regla de filtro por potencia: usar `max_power_kw` del sitio o filtrar conectores individuales según UX elegida.

---

## Pipeline de ingestión (previsto)

```
DATEX II (ES) ──┐
                ├──► Parser DATEX ──► Normalizador ──► SQLite (+ SpatiaLite) ──► API ──► Mapa web
                │                              └── ver docs/STORAGE.md
DATEX II (PT) ──┘
REVE/OCPI (ES) ────► sync REVE (fase 2) ──► merge por coords + enrich dinámico
```

Tareas iniciales en `scripts/`:

1. `fetch_es_nap.py` — descarga XML España
2. `fetch_pt_nap.py` — descarga XML Portugal (streaming; archivo grande)
3. `parse_datex.py` — extrae sitios, conectores, potencia
4. `build_geojson.py` — export para mapa
