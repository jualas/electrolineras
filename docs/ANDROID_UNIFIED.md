# App Android unificada y telemetría multi-coche (Android Auto / AAOS)

Arquitectura unificada de **Electrolineras** para trabajar con un solo repositorio (web + Android APK) y dejar preparada la integración futura con **Android Auto**, **Android Automotive OS (AAOS)** y **OBD-II Bluetooth**.

## 1. Telemetría multi-coche (agnóstica de marca)

El backend acepta telemetría en vivo desde cualquier vehículo mediante un endpoint autenticado (TOTP cookie o `X-Private-Token`):

```http
POST /api/v1/private/telemetry/ingest
Content-Type: application/json
X-Private-Token: <token>

{
  "lat": 37.25,
  "lon": -3.12,
  "battery_level_pct": 48.0,
  "est_battery_range_km": 195.0,
  "display_name": "Coche AAOS",
  "car_model_label": "Modelo EV",
  "charging_state": "Disconnected",
  "source": "android_car"
}
```

- **Prioridad automática (`VEHICLE_TELEMETRY_PROVIDER=auto`):** si existe una lectura push fresca (< `VEHICLE_TELEMETRY_PUSH_TTL_SECONDS`, default 10 min), el planificador de carga, el mapa y el asistente IA la usan automáticamente; si no, caen a **TeslaMate** (MQTT/API).
- **Fuentes soportadas:** `android_car` (Android Auto / AAOS `CarHardwareManager`), `obd2` (dongle BLE universal), `home_assistant`, `custom`.
- **Cálculo energético sin Tesla:** en fuentes no-Tesla, si no hay `rated_battery_range_km`, se normaliza automáticamente `est_battery_range_km` al 100 % para el motor de paradas.

## 2. Build Android unificado (Capacitor 7)

Desde `src/web/`:

```bash
cd src/web
npm install
# Para APK apunta a producción (y sin meter VITE_PRIVATE_TOKEN en el bundle):
VITE_API_URL=https://electro.jualas.es VITE_PRIVATE_TOKEN= npm run cap:sync
npm run cap:open   # abre Android Studio para generar/firmar APK
```

La primera vez que inicialices la carpeta nativa `src/web/android`:

```bash
cd src/web
npx cap add android
```

### Puente móvil ↔ coche (`SharedPreferences`)

`src/web/src/native/carBridge.ts` persiste en `@capacitor/preferences` (`CapacitorStorage` en Android `SharedPreferences`) las claves `car_api_base_url`, `car_private_token`, `car_filter_min_kw`, `car_filter_max_kw` y `car_vehicle_preset_id`.

## 3. Paso 2 futuro: módulo nativo Android Auto / AAOS

Android Auto y AAOS no permiten renderizar WebViews en la pantalla del coche; exigen plantillas de **Android for Cars App Library (`androidx.car.app`)** en Kotlin dentro del mismo proyecto `src/web/android/`:

1. Añadir `androidx.car.app:app` y un `CarAppService` categoría **POI / EV Charging**.
2. Leer `SharedPreferences("CapacitorStorage")` para heredar URL de API, token y filtro de potencia.
3. Escuchar `CarHardwareManager.carInfo.addEnergyLevelListener(...)` (`batteryPercent` + `rangeRemainingMeters`, comprobando `CarValue.STATUS_SUCCESS`) y enviarlo periódicamente a `POST /api/v1/private/telemetry/ingest`.
4. Pintar `PlaceListMapTemplate` (`/api/v1/stations/nearest-live` o `along-route`) + `PaneTemplate` (`/api/v1/stations/{id}/reliability` + botón **Navegar**).
