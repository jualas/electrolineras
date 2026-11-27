import type { CapacitorConfig } from '@capacitor/cli'

const config: CapacitorConfig = {
  appId: 'es.jualas.electrolineras',
  appName: 'Electrolineras',
  webDir: 'dist',
  server: {
    androidScheme: 'https',
  },
  plugins: {
    // Peticiones por la pila HTTP nativa: permite cookies de sesión TOTP (SameSite=Lax)
    // entre https://localhost (WebView) y https://electro.jualas.es.
    CapacitorHttp: {
      enabled: true,
    },
    CapacitorCookies: {
      enabled: true,
    },
    Geolocation: {},
  },
}

export default config
