# Frontend — Electrolineras Web

React + Vite + TypeScript + MapLibre GL. Scaffold mobile-first (#6031).

## Desarrollo

```bash
# Terminal A — API
make api

# Terminal B — frontend (proxy /api y /health → :8000)
make web
```

Abre http://127.0.0.1:5173

Variables: `VITE_API_URL` en `.env` (vacío = proxy Vite en dev).

## Estructura

```
src/
  api/          # cliente HTTP
  components/   # layout (AppShell, ThemeToggle)
  filters/      # presets potencia (#6033)
  map/          # MapLibre MapView, capas estaciones/ruta/ciudad (#6032–6035)
  search/       # RouteSearchPanel, CitySearchPanel (#6034–6035)
  navigation/   # enlaces Google Maps / copiar coords (#6036)
  hooks/        # tema claro/oscuro
  styles/       # variables CSS tema
```

## Build estático

```bash
cd src/web && npm run build
```

Salida: `src/web/dist/` — servible por nginx o FastAPI (`SERVE_WEB_STATIC=true`).

```bash
SERVE_WEB_STATIC=true make api
# → http://127.0.0.1:8000 (SPA + /api/v1/...)
```
