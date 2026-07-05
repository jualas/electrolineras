/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL: string
  readonly VITE_CHARGE_PLAN_NAV_ENABLED?: string
  readonly VITE_ROUTE_NAV_ENABLED?: string
  readonly VITE_TOMTOM_API_KEY?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
