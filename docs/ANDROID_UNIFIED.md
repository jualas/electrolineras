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

## 3. Módulo nativo Android Auto / AAOS (implementado)

Dentro del mismo proyecto `src/web/android/` (`es.jualas.electrolineras.car`) se incluye el servicio oficial de **Android for Cars App Library (`androidx.car.app:1.7.0`)**, categoría **POI / EV Charging**:

- **`ElectrolinerasCarAppService` + `ElectrolinerasCarSession`:** punto de entrada para Android Auto (proyección) y Android Automotive OS (AAOS), con `HostValidator` seguro en release y abierto en debug para el simulador DHU.
- **`CarPreferencesBridge`:** lee `SharedPreferences("CapacitorStorage")` para heredar URL de la API, token privado y filtro de potencia configurados desde la app del móvil.
- **`CarTelemetryManager`:** se suscribe a `CarHardwareManager.getCarInfo()` (`EnergyLevel` → `batteryPercent` + `rangeRemainingMeters`, y `Model`). Comprueba `CarValue.STATUS_SUCCESS` de forma segura (si el coche actual no expone esos datos, no falla) y empuja los cambios (throttle 60 s / Δ1 % SOC) a `POST /api/v1/private/telemetry/ingest`.
- **`NearbyChargersScreen` (`PlaceListMapTemplate`):** mapa nativo del coche + hasta 6 cargadores cercanos (`/api/v1/stations/nearby`), estado REVE, precio, distancia nativa y cambio rápido de filtro (`≥100 kW` / `≥50 kW` / `Todos`).
- **`StationDetailScreen` (`PaneTemplate`):** verificación mixta en vivo (`GET /api/v1/stations/{id}/reliability?verify_google=true`), semáforo REVE + Google Places, alerta de zona aislada (50 km) / plan B y botón primario **Navegar** (`CarContext.ACTION_NAVIGATE`).

### Compilar APK debug y probar en Android Auto DHU

```bash
cd src/web
VITE_API_URL=https://electro.jualas.es VITE_PRIVATE_TOKEN= npm run cap:sync
cd android
ANDROID_HOME="$HOME/Android/Sdk" ./gradlew testDebugUnitTest assembleDebug
# APK generado en: src/web/android/app/build/outputs/apk/debug/app-debug.apk
```

Para probar en coche real o simulador Desktop Head Unit (DHU):
1. Instala `app-debug.apk` en el móvil y abre la app al menos una vez para conceder permiso de ubicación (GPS).
2. En el móvil: *Ajustes de Android Auto → pulsa 10 veces Versión → Ajustes de desarrollador → Orígenes desconocidos* (o súbelo a una pista de pruebas interna cerrada en Google Play Console para uso estable sin modo desarrollador).
3. Conecta el móvil al coche (o al DHU con `adb forward tcp:5277 tcp:5277` y `desktop-head-unit`).
